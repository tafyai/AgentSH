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


class TestRBACExtended:
    """Extended RBAC tests for full coverage."""

    def test_superuser_permissions(self):
        """Test superuser role has maximum permissions."""
        rbac = RBAC()
        user = User(id="super", name="Superuser", role=Role.SUPERUSER)

        # Superuser can execute at all levels except CRITICAL
        allowed, needs_approval, _ = rbac.check_access(user, RiskLevel.SAFE)
        assert allowed and not needs_approval

        allowed, needs_approval, _ = rbac.check_access(user, RiskLevel.HIGH)
        assert allowed and not needs_approval

        # CRITICAL still needs approval even for superuser
        allowed, needs_approval, _ = rbac.check_access(user, RiskLevel.CRITICAL)
        assert not allowed and needs_approval

    def test_device_role_override(self):
        """Test per-device role override."""
        user = User(
            id="multi",
            name="Multi Role",
            role=Role.VIEWER,
            device_roles={"device-1": Role.ADMIN, "device-2": Role.OPERATOR},
        )

        # Default role is VIEWER
        assert user.get_role() == Role.VIEWER

        # Device-specific roles
        assert user.get_role("device-1") == Role.ADMIN
        assert user.get_role("device-2") == Role.OPERATOR

        # Unknown device uses default
        assert user.get_role("device-3") == Role.VIEWER

    def test_permission_helper_methods(self):
        """Test RBAC permission helper methods."""
        rbac = RBAC()

        # can_execute
        assert rbac.can_execute(Role.OPERATOR, RiskLevel.SAFE) is True
        assert rbac.can_execute(Role.OPERATOR, RiskLevel.HIGH) is False

        # can_approve
        assert rbac.can_approve(Role.ADMIN, RiskLevel.HIGH) is True
        assert rbac.can_approve(Role.OPERATOR, RiskLevel.HIGH) is False

        # requires_approval
        assert rbac.requires_approval(Role.OPERATOR, RiskLevel.MEDIUM) is True
        assert rbac.requires_approval(Role.ADMIN, RiskLevel.MEDIUM) is False

        # is_blocked
        assert rbac.is_blocked(Role.VIEWER, RiskLevel.SAFE) is True
        assert rbac.is_blocked(Role.ADMIN, RiskLevel.SAFE) is False

    def test_user_registration_and_retrieval(self):
        """Test user registration and retrieval."""
        rbac = RBAC()
        user = User(id="test_user", name="Test User", role=Role.OPERATOR)

        # Register user
        rbac.register_user(user)

        # Retrieve registered user
        retrieved = rbac.get_user("test_user")
        assert retrieved is not None
        assert retrieved.id == "test_user"

        # Non-existent user returns None
        assert rbac.get_user("nonexistent") is None

    def test_get_current_user(self):
        """Test getting current user from environment."""
        import os
        from unittest.mock import patch

        rbac = RBAC()

        # Test with USER environment variable
        with patch.dict(os.environ, {"USER": "test_env_user"}, clear=False):
            current = rbac.get_current_user()
            assert current.id == "test_env_user"
            assert current.role == Role.OPERATOR

    def test_get_current_user_registered(self):
        """Test getting current user when registered."""
        import os
        from unittest.mock import patch

        rbac = RBAC()
        user = User(id="known_user", name="Known", role=Role.ADMIN)
        rbac.register_user(user)

        with patch.dict(os.environ, {"USER": "known_user"}, clear=False):
            current = rbac.get_current_user()
            assert current.id == "known_user"
            assert current.role == Role.ADMIN

    def test_check_access_with_device(self):
        """Test check_access with device override."""
        rbac = RBAC()
        user = User(
            id="operator",
            name="Operator",
            role=Role.OPERATOR,
            device_roles={"secure-device": Role.VIEWER},
        )
        rbac.register_user(user)

        # Default role allows SAFE commands
        allowed, _, _ = rbac.check_access(user, RiskLevel.SAFE)
        assert allowed

        # On secure-device, role is VIEWER which blocks SAFE commands
        allowed, _, _ = rbac.check_access(user, RiskLevel.SAFE, device_id="secure-device")
        assert not allowed

    def test_role_hierarchy(self):
        """Test role hierarchy comparisons."""
        assert Role.VIEWER < Role.OPERATOR
        assert Role.OPERATOR < Role.ADMIN
        assert Role.ADMIN < Role.SUPERUSER

    def test_permission_matrix_all_roles(self):
        """Test permission matrix covers all role/risk combinations."""
        rbac = RBAC()

        for role in Role:
            for risk in RiskLevel:
                perm = rbac.get_permission(role, risk)
                assert isinstance(perm.can_execute, bool)
                assert isinstance(perm.can_approve, bool)
                assert isinstance(perm.requires_approval, bool)


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


class TestAuditLoggerExtended:
    """Extended tests for AuditLogger."""

    def test_log_command_approved(self):
        """Test logging command approval."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.log"
            audit_logger = AuditLogger(log_path=log_path)

            audit_logger.log_command_approved(
                command="rm -rf ./old_data",
                approver="admin",
                user="alice",
                risk_level=RiskLevel.HIGH,
            )

            events = audit_logger.get_recent(n=1)
            assert len(events) == 1
            assert events[0].action == AuditAction.COMMAND_APPROVED
            assert events[0].approver == "admin"

    def test_log_command_denied(self):
        """Test logging command denial."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.log"
            audit_logger = AuditLogger(log_path=log_path)

            audit_logger.log_command_denied(
                command="rm -rf /",
                reason="Too dangerous",
                risk_level=RiskLevel.CRITICAL,
            )

            events = audit_logger.get_recent(n=1)
            assert events[0].action == AuditAction.COMMAND_DENIED
            assert events[0].result == "Too dangerous"

    def test_log_session_start_and_end(self):
        """Test logging session events."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.log"
            audit_logger = AuditLogger(log_path=log_path)

            audit_logger.log_session_start(metadata={"version": "1.0"})
            audit_logger.log_session_end(metadata={"duration": 3600})

            events = audit_logger.get_recent(n=2)
            assert len(events) == 2
            assert events[0].action == AuditAction.SESSION_END
            assert events[1].action == AuditAction.SESSION_START

    def test_log_security_violation(self):
        """Test logging security violation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.log"
            audit_logger = AuditLogger(log_path=log_path)

            audit_logger.log_security_violation(
                description="Attempted command injection",
                command="; cat /etc/passwd",
                user="malicious_user",
                metadata={"ip": "192.168.1.100"},
            )

            events = audit_logger.get_recent(n=1)
            assert events[0].action == AuditAction.SECURITY_VIOLATION
            assert events[0].risk_level == RiskLevel.CRITICAL

    def test_event_to_json(self):
        """Test event JSON serialization."""
        event = AuditEvent(
            timestamp=datetime.now(),
            action=AuditAction.TOOL_INVOKED,
            user="alice",
            command="shell.run",
            metadata={"arg": "ls"},
        )
        json_str = event.to_json()
        data = json.loads(json_str)
        assert data["action"] == "tool_invoked"

    def test_event_from_dict_minimal(self):
        """Test creating event from minimal dict."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "action": "command_executed",
            "user": "bob",
            "command": "ls",
        }
        event = AuditEvent.from_dict(data)
        assert event.action == AuditAction.COMMAND_EXECUTED
        assert event.risk_level is None
        assert event.approver is None

    def test_event_with_all_optional_fields(self):
        """Test event with all optional fields populated."""
        event = AuditEvent(
            timestamp=datetime.now(),
            action=AuditAction.COMMAND_EXECUTED,
            user="alice",
            command="ls",
            risk_level=RiskLevel.SAFE,
            result="success",
            approver="admin",
            device_id="robot-01",
            session_id="abc123",
            metadata={"key": "value"},
        )
        d = event.to_dict()
        assert d["risk_level"] == "SAFE"
        assert d["result"] == "success"
        assert d["approver"] == "admin"
        assert d["device_id"] == "robot-01"
        assert d["session_id"] == "abc123"
        assert d["metadata"]["key"] == "value"

    def test_get_by_user(self):
        """Test getting events filtered by user."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.log"
            audit_logger = AuditLogger(log_path=log_path)

            audit_logger.log_command_executed("ls", user="alice")
            audit_logger.log_command_executed("pwd", user="bob")
            audit_logger.log_command_executed("cd", user="alice")

            alice_events = audit_logger.get_by_user("alice")
            assert len(alice_events) == 2
            for event in alice_events:
                assert event.user == "alice"

    def test_get_by_action(self):
        """Test getting events filtered by action type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.log"
            audit_logger = AuditLogger(log_path=log_path)

            audit_logger.log_command_executed("ls")
            audit_logger.log_command_blocked("rm -rf /", "Dangerous")
            audit_logger.log_command_executed("pwd")

            blocked = audit_logger.get_by_action(AuditAction.COMMAND_BLOCKED)
            assert len(blocked) == 1
            assert blocked[0].command == "rm -rf /"

    def test_get_recent_empty_log(self):
        """Test getting events from non-existent log."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "nonexistent.log"
            audit_logger = AuditLogger(log_path=log_path)

            events = audit_logger.get_recent()
            assert events == []

    def test_log_rotation(self):
        """Test log file rotation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.log"
            # Set very small max file size to trigger rotation
            audit_logger = AuditLogger(log_path=log_path, max_file_size=100)

            # Write enough to trigger rotation
            for i in range(10):
                audit_logger.log_command_executed(
                    f"command_{i}" * 10,  # Make command long
                    user="alice",
                )

            # Check that rotated file exists
            rotated_files = list(Path(tmpdir).glob("audit.*.log"))
            assert len(rotated_files) >= 1

    def test_log_with_device_id(self):
        """Test logging with device ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "audit.log"
            audit_logger = AuditLogger(log_path=log_path)

            audit_logger.log_command_executed(
                command="ros2 topic list",
                user="operator",
                risk_level=RiskLevel.LOW,
                device_id="robot-01",
            )

            events = audit_logger.get_recent(n=1)
            assert events[0].device_id == "robot-01"

    def test_default_path(self):
        """Test default audit log path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            import agentsh.security.audit as audit_module

            original_home = Path.home

            try:
                # Mock home directory
                Path.home = lambda: Path(tmpdir)

                audit_logger = AuditLogger()
                expected_path = Path(tmpdir) / ".agentsh" / "audit.log"
                assert audit_logger.log_path == expected_path
            finally:
                Path.home = original_home


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
