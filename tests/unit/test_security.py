"""Tests for security module."""

import pytest
from datetime import datetime
from pathlib import Path
import tempfile
import json

from agentsh.security.classifier import (
    RiskLevel,
    RiskPattern,
    RiskClassifier,
    CommandRiskAssessment,
)
from agentsh.security.policies import (
    SecurityMode,
    SecurityPolicy,
    DevicePolicy,
    PolicyManager,
)
from agentsh.security.rbac import (
    Role,
    Permission,
    User,
    RBAC,
)
from agentsh.security.approval import (
    ApprovalResult,
    ApprovalRequest,
    ApprovalResponse,
    ApprovalFlow,
    AutoApprover,
)
from agentsh.security.audit import (
    AuditAction,
    AuditEvent,
    AuditLogger,
)
from agentsh.security.controller import (
    ValidationResult,
    SecurityContext,
    SecurityDecision,
    SecurityController,
)


class TestRiskLevel:
    """Tests for RiskLevel enum."""

    def test_ordering(self):
        """Test risk levels are properly ordered."""
        assert RiskLevel.SAFE < RiskLevel.LOW
        assert RiskLevel.LOW < RiskLevel.MEDIUM
        assert RiskLevel.MEDIUM < RiskLevel.HIGH
        assert RiskLevel.HIGH < RiskLevel.CRITICAL

    def test_values(self):
        """Test risk level values."""
        assert RiskLevel.SAFE == 0
        assert RiskLevel.CRITICAL == 4


class TestRiskClassifier:
    """Tests for RiskClassifier."""

    def test_safe_command(self):
        """Test safe commands are classified correctly."""
        classifier = RiskClassifier()
        result = classifier.classify("ls -la")
        assert result.risk_level == RiskLevel.SAFE
        assert not result.is_blocked

    def test_low_risk_command(self):
        """Test low risk commands - git operations are LOW risk."""
        classifier = RiskClassifier()
        result = classifier.classify("git commit -m 'test'")
        assert result.risk_level >= RiskLevel.LOW

    def test_high_risk_rm_rf(self):
        """Test rm -rf is classified as high risk."""
        classifier = RiskClassifier()
        result = classifier.classify("rm -rf ./data")
        assert result.risk_level >= RiskLevel.HIGH
        assert len(result.reasons) > 0

    def test_critical_root_delete(self):
        """Test root directory deletion is critical."""
        classifier = RiskClassifier()
        result = classifier.classify("rm -rf /")
        assert result.risk_level == RiskLevel.CRITICAL
        assert result.is_blocked

    def test_critical_dd_if_dev(self):
        """Test dd to disk device is critical."""
        classifier = RiskClassifier()
        result = classifier.classify("dd if=/dev/zero of=/dev/sda")
        assert result.risk_level == RiskLevel.CRITICAL
        assert result.is_blocked

    def test_high_risk_chmod_recursive(self):
        """Test recursive chmod is high risk."""
        classifier = RiskClassifier()
        result = classifier.classify("chmod -R 777 /var")
        assert result.risk_level >= RiskLevel.HIGH

    def test_medium_risk_write_file(self):
        """Test writing to system files is medium risk."""
        classifier = RiskClassifier()
        result = classifier.classify("echo data > /etc/config")
        # Redirect to /etc is MEDIUM or higher risk
        assert result.risk_level >= RiskLevel.MEDIUM

    def test_fork_bomb_blocked(self):
        """Test fork bomb is blocked."""
        classifier = RiskClassifier()
        result = classifier.classify(":(){ :|:& };:")
        assert result.risk_level == RiskLevel.CRITICAL
        assert result.is_blocked

    def test_multiple_patterns_match(self):
        """Test command matching multiple patterns."""
        classifier = RiskClassifier()
        # This matches both 'rm' and 'recursive' patterns
        result = classifier.classify("rm -rf /var/log/*")
        assert len(result.reasons) >= 1

    def test_empty_command(self):
        """Test empty command is safe."""
        classifier = RiskClassifier()
        result = classifier.classify("")
        assert result.risk_level == RiskLevel.SAFE

    def test_simple_echo(self):
        """Test simple echo is safe."""
        classifier = RiskClassifier()
        result = classifier.classify("echo hello world")
        assert result.risk_level == RiskLevel.SAFE


class TestSecurityPolicy:
    """Tests for SecurityPolicy."""

    def test_default_policy(self):
        """Test default policy settings."""
        policy = SecurityPolicy()
        assert policy.mode == SecurityMode.STANDARD
        assert policy.name == "default"

    def test_permissive_mode(self):
        """Test permissive mode allows most operations."""
        policy = SecurityPolicy(mode=SecurityMode.PERMISSIVE)
        assert not policy.is_blocked_by_mode(RiskLevel.HIGH)
        assert not policy.requires_approval(RiskLevel.HIGH)

    def test_standard_mode_approval(self):
        """Test standard mode requires approval for high risk."""
        policy = SecurityPolicy(mode=SecurityMode.STANDARD)
        assert not policy.is_blocked_by_mode(RiskLevel.HIGH)
        assert policy.requires_approval(RiskLevel.HIGH)
        assert not policy.requires_approval(RiskLevel.LOW)

    def test_strict_mode_blocking(self):
        """Test strict mode blocks high risk."""
        policy = SecurityPolicy(mode=SecurityMode.STRICT)
        assert policy.is_blocked_by_mode(RiskLevel.HIGH)
        assert policy.requires_approval(RiskLevel.MEDIUM)

    def test_paranoid_mode(self):
        """Test paranoid mode is most restrictive."""
        policy = SecurityPolicy(mode=SecurityMode.PARANOID)
        assert policy.is_blocked_by_mode(RiskLevel.HIGH)
        assert policy.requires_approval(RiskLevel.LOW)

    def test_blocked_patterns(self):
        """Test custom blocked patterns."""
        policy = SecurityPolicy(blocked_patterns=["dangerous_script.sh"])
        assert "dangerous_script.sh" in policy.blocked_patterns


class TestPolicyManager:
    """Tests for PolicyManager."""

    def test_default_policy(self):
        """Test getting default policy."""
        manager = PolicyManager()
        policy = manager.get_policy()
        assert policy is not None
        assert isinstance(policy, SecurityPolicy)

    def test_device_policy(self):
        """Test device-specific policies."""
        manager = PolicyManager()
        device_policy = DevicePolicy(
            device_id="robot-1",
            policy=SecurityPolicy(mode=SecurityMode.STRICT, name="robot-strict"),
        )
        manager.add_device_policy(device_policy)

        policy = manager.get_policy("robot-1")
        assert policy.mode == SecurityMode.STRICT
        assert policy.name == "robot-strict"

    def test_fallback_to_default(self):
        """Test unknown device falls back to default."""
        manager = PolicyManager()
        policy = manager.get_policy("unknown-device")
        assert policy.mode == SecurityMode.STANDARD


class TestRBAC:
    """Tests for Role-Based Access Control."""

    def test_user_creation(self):
        """Test user creation."""
        user = User(id="alice", name="Alice", role=Role.OPERATOR)
        assert user.id == "alice"
        assert user.role == Role.OPERATOR

    def test_operator_permissions(self):
        """Test operator role permissions."""
        rbac = RBAC()
        user = User(id="alice", name="Alice", role=Role.OPERATOR)
        rbac.register_user(user)

        # Operators can execute safe commands
        allowed, needs_approval, _ = rbac.check_access(user, RiskLevel.SAFE)
        assert allowed
        assert not needs_approval

        # Operators need approval for high risk
        allowed, needs_approval, _ = rbac.check_access(user, RiskLevel.HIGH)
        assert not allowed or needs_approval

    def test_admin_permissions(self):
        """Test admin role permissions."""
        rbac = RBAC()
        user = User(id="bob", name="Bob", role=Role.ADMIN)
        rbac.register_user(user)

        # Admins have more permissions
        allowed, needs_approval, _ = rbac.check_access(user, RiskLevel.MEDIUM)
        assert allowed

    def test_viewer_restrictions(self):
        """Test viewer role is restricted."""
        rbac = RBAC()
        user = User(id="viewer", name="Viewer", role=Role.VIEWER)
        rbac.register_user(user)

        # Viewers shouldn't be able to execute risky commands
        allowed, needs_approval, _ = rbac.check_access(user, RiskLevel.MEDIUM)
        assert not allowed or needs_approval


class TestApprovalFlow:
    """Tests for ApprovalFlow."""

    def test_approval_request_creation(self):
        """Test creating approval request."""
        request = ApprovalRequest(
            command="rm -rf ./old_data",
            risk_level=RiskLevel.HIGH,
            reasons=["Recursive delete"],
            context={"cwd": "/home/user"},
        )
        assert request.command == "rm -rf ./old_data"
        assert request.risk_level == RiskLevel.HIGH

    def test_approval_response(self):
        """Test approval response."""
        response = ApprovalResponse(
            result=ApprovalResult.APPROVED,
            command="ls -la",
            approver="alice",
            timestamp=datetime.now(),
        )
        assert response.result == ApprovalResult.APPROVED

    def test_auto_approver_safe(self):
        """Test auto approver approves safe commands."""
        approver = AutoApprover()
        request = ApprovalRequest(
            command="ls",
            risk_level=RiskLevel.SAFE,
            reasons=[],
            context={},
        )
        response = approver.request_approval(request)
        assert response.result == ApprovalResult.APPROVED

    def test_auto_approver_denies_high(self):
        """Test auto approver denies high risk by default."""
        approver = AutoApprover()
        request = ApprovalRequest(
            command="rm -rf /",
            risk_level=RiskLevel.HIGH,
            reasons=["Dangerous"],
            context={},
        )
        response = approver.request_approval(request)
        assert response.result == ApprovalResult.DENIED

    def test_auto_deny_mode(self):
        """Test auto-deny mode."""
        approver = AutoApprover(auto_deny=True)
        request = ApprovalRequest(
            command="ls",
            risk_level=RiskLevel.SAFE,
            reasons=[],
            context={},
        )
        response = approver.request_approval(request)
        assert response.result == ApprovalResult.DENIED


class TestAuditLogger:
    """Tests for AuditLogger."""

    def test_create_audit_event(self):
        """Test creating audit event."""
        event = AuditEvent(
            timestamp=datetime.now(),
            action=AuditAction.COMMAND_EXECUTED,
            user="alice",
            command="ls -la",
            risk_level=RiskLevel.SAFE,
        )
        assert event.action == AuditAction.COMMAND_EXECUTED

    def test_event_to_dict(self):
        """Test converting event to dict."""
        event = AuditEvent(
            timestamp=datetime.now(),
            action=AuditAction.COMMAND_BLOCKED,
            user="bob",
            command="rm -rf /",
            risk_level=RiskLevel.CRITICAL,
            result="Blocked by policy",
        )
        d = event.to_dict()
        assert d["action"] == "command_blocked"
        assert d["user"] == "bob"
        assert d["risk_level"] == "CRITICAL"

    def test_event_roundtrip(self):
        """Test event serialization roundtrip."""
        original = AuditEvent(
            timestamp=datetime.now(),
            action=AuditAction.COMMAND_APPROVED,
            user="alice",
            command="test",
            risk_level=RiskLevel.MEDIUM,
            approver="bob",
        )
        d = original.to_dict()
        restored = AuditEvent.from_dict(d)
        assert restored.action == original.action
        assert restored.user == original.user
        assert restored.approver == original.approver

    def test_logger_writes_file(self):
        """Test logger writes to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.log"
            logger = AuditLogger(log_path=log_path)

            logger.log_command_executed(
                command="ls",
                user="alice",
                risk_level=RiskLevel.SAFE,
            )

            assert log_path.exists()
            with open(log_path) as f:
                line = f.readline()
                data = json.loads(line)
                assert data["command"] == "ls"
                assert data["action"] == "command_executed"

    def test_logger_get_recent(self):
        """Test getting recent events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.log"
            logger = AuditLogger(log_path=log_path)

            logger.log_command_executed("ls", risk_level=RiskLevel.SAFE)
            logger.log_command_executed("pwd", risk_level=RiskLevel.SAFE)
            logger.log_command_blocked("rm -rf /", "Dangerous", risk_level=RiskLevel.CRITICAL)

            events = logger.get_recent(n=10)
            assert len(events) == 3
            # Most recent first
            assert events[0].action == AuditAction.COMMAND_BLOCKED


class TestSecurityController:
    """Tests for SecurityController."""

    def test_allow_safe_command(self):
        """Test safe commands are allowed."""
        controller = SecurityController()
        user = User(id="alice", name="Alice", role=Role.OPERATOR)
        context = SecurityContext(user=user)

        decision = controller.check("ls -la", context)
        assert decision.result == ValidationResult.ALLOW

    def test_block_critical_command(self):
        """Test critical commands are blocked."""
        controller = SecurityController()
        user = User(id="alice", name="Alice", role=Role.OPERATOR)
        context = SecurityContext(user=user)

        decision = controller.check("rm -rf /", context)
        assert decision.result == ValidationResult.BLOCKED

    def test_require_approval_for_high_risk(self):
        """Test high risk commands require approval."""
        controller = SecurityController()
        user = User(id="alice", name="Alice", role=Role.OPERATOR)
        context = SecurityContext(user=user)

        # Configure standard mode which requires approval for high
        controller.set_policy(SecurityPolicy(mode=SecurityMode.STANDARD))

        decision = controller.check("rm -rf ./temp", context)
        # Should either be blocked or need approval
        assert decision.result in (ValidationResult.BLOCKED, ValidationResult.NEED_APPROVAL)

    def test_is_safe_helper(self):
        """Test is_safe helper method."""
        controller = SecurityController()
        assert controller.is_safe("ls")
        assert controller.is_safe("echo hello")
        assert not controller.is_safe("rm -rf /")

    def test_get_risk_level(self):
        """Test get_risk_level helper."""
        controller = SecurityController()
        assert controller.get_risk_level("ls") == RiskLevel.SAFE
        assert controller.get_risk_level("rm -rf /") == RiskLevel.CRITICAL

    def test_strict_policy_blocks_high(self):
        """Test strict policy blocks high risk."""
        controller = SecurityController()
        controller.set_policy(SecurityPolicy(mode=SecurityMode.STRICT))

        user = User(id="alice", name="Alice", role=Role.OPERATOR)
        context = SecurityContext(user=user)

        decision = controller.check("rm -rf ./temp", context)
        assert decision.result == ValidationResult.BLOCKED

    def test_validate_and_approve_with_auto_approver(self):
        """Test validate_and_approve with auto approver."""
        auto_approver = AutoApprover(auto_approve_levels=[RiskLevel.SAFE, RiskLevel.LOW])
        controller = SecurityController(approval_flow=auto_approver)

        user = User(id="alice", name="Alice", role=Role.OPERATOR)
        context = SecurityContext(user=user)

        # Safe command should be auto-approved
        decision = controller.validate_and_approve("ls", context)
        assert decision.result == ValidationResult.ALLOW

    def test_decision_includes_risk_assessment(self):
        """Test decision includes risk assessment."""
        controller = SecurityController()
        user = User(id="alice", name="Alice", role=Role.OPERATOR)
        context = SecurityContext(user=user)

        decision = controller.check("rm -rf /", context)
        assert decision.risk_assessment is not None
        assert decision.risk_assessment.risk_level == RiskLevel.CRITICAL


class TestIntegration:
    """Integration tests for security module."""

    def test_full_flow_safe_command(self):
        """Test full security flow for safe command."""
        # Setup
        controller = SecurityController()
        user = User(id="alice", name="Alice", role=Role.OPERATOR)
        context = SecurityContext(user=user, cwd="/home/alice")

        # Check and execute
        decision = controller.validate_and_approve("ls -la", context)

        assert decision.result == ValidationResult.ALLOW
        assert decision.risk_assessment.risk_level == RiskLevel.SAFE

    def test_full_flow_blocked_command(self):
        """Test full security flow for blocked command."""
        controller = SecurityController()
        user = User(id="alice", name="Alice", role=Role.OPERATOR)
        context = SecurityContext(user=user)

        decision = controller.validate_and_approve(":(){ :|:& };:", context)

        assert decision.result == ValidationResult.BLOCKED
        assert "blocked" in decision.reason.lower()

    def test_audit_trail(self):
        """Test audit trail is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.log"
            audit = AuditLogger(log_path=log_path)
            controller = SecurityController(audit_logger=audit)

            user = User(id="alice", name="Alice", role=Role.OPERATOR)
            context = SecurityContext(user=user)

            # Execute a blocked command
            controller.validate_and_approve("rm -rf /", context)

            # Check audit log
            events = audit.get_recent(n=10)
            assert len(events) >= 1
            blocked_events = [e for e in events if e.action == AuditAction.COMMAND_BLOCKED]
            assert len(blocked_events) >= 1
