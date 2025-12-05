"""Tests for security controller module."""

from unittest.mock import MagicMock, patch

import pytest

from agentsh.security.controller import (
    SecurityContext,
    SecurityController,
    SecurityDecision,
    ValidationResult,
)


class MockRiskAssessment:
    """Mock risk assessment for testing."""

    def __init__(
        self,
        risk_level: str = "LOW",
        is_blocked: bool = False,
        reasons: list = None,
    ):
        self.risk_level = MagicMock()
        self.risk_level.name = risk_level
        self.risk_level.value = risk_level.lower()
        # Make risk_level comparable
        level_order = {"SAFE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        self.risk_level.__le__ = lambda self, other: level_order.get(self.name, 1) <= level_order.get(other.name, 1)
        self.is_blocked = is_blocked
        self.reasons = reasons or []


class MockUser:
    """Mock user for testing."""

    def __init__(self, name: str = "testuser"):
        self.name = name


class MockApprovalResponse:
    """Mock approval response."""

    def __init__(
        self,
        result: str = "APPROVED",
        command: str = "ls",
        approver: str = "user",
        reason: str = None,
    ):
        self.result = MagicMock()
        self.result.name = result
        self.result.value = result.lower()
        self.command = command
        self.approver = approver
        self.reason = reason


class TestSecurityContext:
    """Tests for SecurityContext dataclass."""

    def test_creation(self) -> None:
        """Should create context with user."""
        user = MockUser()
        context = SecurityContext(user=user)

        assert context.user is user
        assert context.device_id is None
        assert context.cwd is None
        assert context.env is None
        assert context.interactive is True

    def test_creation_with_all_fields(self) -> None:
        """Should create context with all fields."""
        user = MockUser()
        context = SecurityContext(
            user=user,
            device_id="server-1",
            cwd="/home/user",
            env={"PATH": "/bin"},
            interactive=False,
        )

        assert context.device_id == "server-1"
        assert context.cwd == "/home/user"
        assert context.env == {"PATH": "/bin"}
        assert context.interactive is False


class TestSecurityDecision:
    """Tests for SecurityDecision dataclass."""

    def test_creation(self) -> None:
        """Should create decision with required fields."""
        risk_assessment = MockRiskAssessment()
        decision = SecurityDecision(
            result=ValidationResult.ALLOW,
            command="ls",
            risk_assessment=risk_assessment,
            reason="Allowed",
        )

        assert decision.result == ValidationResult.ALLOW
        assert decision.command == "ls"
        assert decision.reason == "Allowed"
        assert decision.approved_by is None


class TestValidationResult:
    """Tests for ValidationResult enum."""

    def test_values(self) -> None:
        """Should have expected values."""
        assert ValidationResult.ALLOW.value == "allow"
        assert ValidationResult.NEED_APPROVAL.value == "need_approval"
        assert ValidationResult.BLOCKED.value == "blocked"


class TestSecurityControllerInit:
    """Tests for SecurityController initialization."""

    def test_default_initialization(self) -> None:
        """Should initialize with defaults."""
        with patch("agentsh.security.controller.RiskClassifier") as mock_classifier:
            with patch("agentsh.security.controller.PolicyManager") as mock_policy:
                with patch("agentsh.security.controller.RBAC") as mock_rbac:
                    with patch("agentsh.security.controller.ApprovalFlow") as mock_approval:
                        with patch("agentsh.security.controller.AuditLogger") as mock_audit:
                            controller = SecurityController()

                            mock_classifier.assert_called_once()
                            mock_policy.assert_called_once()
                            mock_rbac.assert_called_once()
                            mock_approval.assert_called_once()
                            mock_audit.assert_called_once()

    def test_custom_components(self) -> None:
        """Should use provided components."""
        custom_classifier = MagicMock()
        custom_policy = MagicMock()
        custom_rbac = MagicMock()
        custom_approval = MagicMock()
        custom_audit = MagicMock()

        controller = SecurityController(
            classifier=custom_classifier,
            policy_manager=custom_policy,
            rbac=custom_rbac,
            approval_flow=custom_approval,
            audit_logger=custom_audit,
        )

        assert controller.classifier is custom_classifier
        assert controller.policy_manager is custom_policy
        assert controller.rbac is custom_rbac
        assert controller.approval_flow is custom_approval
        assert controller.audit is custom_audit


class TestSecurityControllerCheck:
    """Tests for SecurityController.check method."""

    @pytest.fixture
    def controller(self) -> SecurityController:
        """Create controller with mocks."""
        return SecurityController(
            classifier=MagicMock(),
            policy_manager=MagicMock(),
            rbac=MagicMock(),
            approval_flow=MagicMock(),
            audit_logger=MagicMock(),
        )

    @pytest.fixture
    def context(self) -> SecurityContext:
        """Create test context."""
        return SecurityContext(user=MockUser())

    def test_blocked_by_classifier(
        self, controller: SecurityController, context: SecurityContext
    ) -> None:
        """Should block command if classifier blocks it."""
        risk_assessment = MockRiskAssessment(is_blocked=True, reasons=["dangerous"])
        controller.classifier.classify.return_value = risk_assessment

        decision = controller.check("rm -rf /", context)

        assert decision.result == ValidationResult.BLOCKED
        assert "blocked" in decision.reason.lower()
        controller.audit.log_command_blocked.assert_called_once()

    def test_blocked_by_policy_mode(
        self, controller: SecurityController, context: SecurityContext
    ) -> None:
        """Should block command if policy mode blocks it."""
        risk_assessment = MockRiskAssessment(is_blocked=False)
        controller.classifier.classify.return_value = risk_assessment

        mock_policy = MagicMock()
        mock_policy.is_blocked_by_mode.return_value = True
        mock_policy.mode.value = "strict"
        controller.policy_manager.get_policy.return_value = mock_policy

        decision = controller.check("sudo apt install", context)

        assert decision.result == ValidationResult.BLOCKED
        assert "mode" in decision.reason.lower()

    def test_blocked_by_rbac(
        self, controller: SecurityController, context: SecurityContext
    ) -> None:
        """Should block command if RBAC denies access."""
        risk_assessment = MockRiskAssessment(is_blocked=False)
        controller.classifier.classify.return_value = risk_assessment

        mock_policy = MagicMock()
        mock_policy.is_blocked_by_mode.return_value = False
        controller.policy_manager.get_policy.return_value = mock_policy

        controller.rbac.check_access.return_value = (False, False, "Access denied")

        decision = controller.check("restricted command", context)

        assert decision.result == ValidationResult.BLOCKED
        assert decision.reason == "Access denied"

    def test_needs_approval_from_rbac(
        self, controller: SecurityController, context: SecurityContext
    ) -> None:
        """Should require approval if RBAC says so."""
        risk_assessment = MockRiskAssessment(is_blocked=False)
        controller.classifier.classify.return_value = risk_assessment

        mock_policy = MagicMock()
        mock_policy.is_blocked_by_mode.return_value = False
        mock_policy.requires_approval.return_value = False
        controller.policy_manager.get_policy.return_value = mock_policy

        controller.rbac.check_access.return_value = (True, True, "Needs approval")

        decision = controller.check("sudo command", context)

        assert decision.result == ValidationResult.NEED_APPROVAL

    def test_needs_approval_from_policy(
        self, controller: SecurityController, context: SecurityContext
    ) -> None:
        """Should require approval if policy says so."""
        risk_assessment = MockRiskAssessment(is_blocked=False)
        controller.classifier.classify.return_value = risk_assessment

        mock_policy = MagicMock()
        mock_policy.is_blocked_by_mode.return_value = False
        mock_policy.requires_approval.return_value = True
        controller.policy_manager.get_policy.return_value = mock_policy

        controller.rbac.check_access.return_value = (True, False, "")

        decision = controller.check("risky command", context)

        assert decision.result == ValidationResult.NEED_APPROVAL

    def test_allowed(
        self, controller: SecurityController, context: SecurityContext
    ) -> None:
        """Should allow safe commands."""
        risk_assessment = MockRiskAssessment(is_blocked=False)
        controller.classifier.classify.return_value = risk_assessment

        mock_policy = MagicMock()
        mock_policy.is_blocked_by_mode.return_value = False
        mock_policy.requires_approval.return_value = False
        controller.policy_manager.get_policy.return_value = mock_policy

        controller.rbac.check_access.return_value = (True, False, "")

        decision = controller.check("ls", context)

        assert decision.result == ValidationResult.ALLOW
        assert "allowed" in decision.reason.lower()


class TestSecurityControllerValidateAndApprove:
    """Tests for SecurityController.validate_and_approve method."""

    @pytest.fixture
    def controller(self) -> SecurityController:
        """Create controller with mocks."""
        return SecurityController(
            classifier=MagicMock(),
            policy_manager=MagicMock(),
            rbac=MagicMock(),
            approval_flow=MagicMock(),
            audit_logger=MagicMock(),
        )

    def test_blocked_returns_immediately(self, controller: SecurityController) -> None:
        """Should return immediately if blocked."""
        context = SecurityContext(user=MockUser())

        risk_assessment = MockRiskAssessment(is_blocked=True, reasons=["blocked"])
        controller.classifier.classify.return_value = risk_assessment

        decision = controller.validate_and_approve("bad command", context)

        assert decision.result == ValidationResult.BLOCKED
        controller.approval_flow.request_approval.assert_not_called()

    def test_allowed_returns_immediately(self, controller: SecurityController) -> None:
        """Should return immediately if allowed."""
        context = SecurityContext(user=MockUser())

        risk_assessment = MockRiskAssessment(is_blocked=False)
        controller.classifier.classify.return_value = risk_assessment

        mock_policy = MagicMock()
        mock_policy.is_blocked_by_mode.return_value = False
        mock_policy.requires_approval.return_value = False
        controller.policy_manager.get_policy.return_value = mock_policy
        controller.rbac.check_access.return_value = (True, False, "")

        decision = controller.validate_and_approve("ls", context)

        assert decision.result == ValidationResult.ALLOW
        controller.approval_flow.request_approval.assert_not_called()

    def test_non_interactive_denies(self, controller: SecurityController) -> None:
        """Should deny if non-interactive and needs approval."""
        context = SecurityContext(user=MockUser(), interactive=False)

        risk_assessment = MockRiskAssessment(is_blocked=False)
        controller.classifier.classify.return_value = risk_assessment

        mock_policy = MagicMock()
        mock_policy.is_blocked_by_mode.return_value = False
        mock_policy.requires_approval.return_value = True
        controller.policy_manager.get_policy.return_value = mock_policy
        controller.rbac.check_access.return_value = (True, False, "")

        decision = controller.validate_and_approve("risky", context)

        assert decision.result == ValidationResult.BLOCKED
        assert "non-interactive" in decision.reason.lower()

    def test_runs_approval_flow(self, controller: SecurityController) -> None:
        """Should run approval flow when needed."""
        context = SecurityContext(user=MockUser(), interactive=True)

        risk_assessment = MockRiskAssessment(is_blocked=False)
        controller.classifier.classify.return_value = risk_assessment

        mock_policy = MagicMock()
        mock_policy.is_blocked_by_mode.return_value = False
        mock_policy.requires_approval.return_value = True
        controller.policy_manager.get_policy.return_value = mock_policy
        controller.rbac.check_access.return_value = (True, False, "")

        mock_response = MockApprovalResponse(result="APPROVED")
        from agentsh.security.approval import ApprovalResult
        mock_response.result = ApprovalResult.APPROVED
        controller.approval_flow.request_approval.return_value = mock_response

        decision = controller.validate_and_approve("risky", context)

        controller.approval_flow.request_approval.assert_called_once()
        assert decision.result == ValidationResult.ALLOW


class TestHandleApprovalResponse:
    """Tests for _handle_approval_response method."""

    @pytest.fixture
    def controller(self) -> SecurityController:
        """Create controller with mocks."""
        return SecurityController(
            classifier=MagicMock(),
            policy_manager=MagicMock(),
            rbac=MagicMock(),
            approval_flow=MagicMock(),
            audit_logger=MagicMock(),
        )

    @pytest.fixture
    def original_decision(self) -> SecurityDecision:
        """Create original decision."""
        return SecurityDecision(
            result=ValidationResult.NEED_APPROVAL,
            command="original",
            risk_assessment=MockRiskAssessment(),
            reason="Needs approval",
        )

    @pytest.fixture
    def context(self) -> SecurityContext:
        """Create test context."""
        return SecurityContext(user=MockUser())

    def test_approved(
        self,
        controller: SecurityController,
        original_decision: SecurityDecision,
        context: SecurityContext,
    ) -> None:
        """Should handle approved response."""
        from agentsh.security.approval import ApprovalResult

        response = MagicMock()
        response.result = ApprovalResult.APPROVED
        response.command = "ls"
        response.approver = "testuser"

        decision = controller._handle_approval_response(
            response, original_decision, context
        )

        assert decision.result == ValidationResult.ALLOW
        assert decision.approved_by == "testuser"
        controller.audit.log_command_approved.assert_called_once()

    def test_edited_and_allowed(
        self,
        controller: SecurityController,
        original_decision: SecurityDecision,
        context: SecurityContext,
    ) -> None:
        """Should handle edited response when new command is allowed."""
        from agentsh.security.approval import ApprovalResult

        response = MagicMock()
        response.result = ApprovalResult.EDITED
        response.command = "ls -la"
        response.approver = "testuser"

        # Set up classifier to allow the edited command
        new_assessment = MockRiskAssessment(is_blocked=False)
        controller.classifier.classify.return_value = new_assessment

        mock_policy = MagicMock()
        mock_policy.is_blocked_by_mode.return_value = False
        mock_policy.requires_approval.return_value = False
        controller.policy_manager.get_policy.return_value = mock_policy
        controller.rbac.check_access.return_value = (True, False, "")

        decision = controller._handle_approval_response(
            response, original_decision, context
        )

        assert decision.result == ValidationResult.ALLOW
        assert decision.command == "ls -la"

    def test_edited_but_blocked(
        self,
        controller: SecurityController,
        original_decision: SecurityDecision,
        context: SecurityContext,
    ) -> None:
        """Should handle edited response when new command is blocked."""
        from agentsh.security.approval import ApprovalResult

        response = MagicMock()
        response.result = ApprovalResult.EDITED
        response.command = "rm -rf /"
        response.approver = "testuser"

        # Set up classifier to block the edited command
        new_assessment = MockRiskAssessment(is_blocked=True, reasons=["dangerous"])
        controller.classifier.classify.return_value = new_assessment

        decision = controller._handle_approval_response(
            response, original_decision, context
        )

        assert decision.result == ValidationResult.BLOCKED
        controller.audit.log_command_denied.assert_called()

    def test_skipped(
        self,
        controller: SecurityController,
        original_decision: SecurityDecision,
        context: SecurityContext,
    ) -> None:
        """Should handle skipped response."""
        from agentsh.security.approval import ApprovalResult

        response = MagicMock()
        response.result = ApprovalResult.SKIPPED
        response.command = "original"
        response.approver = "testuser"

        decision = controller._handle_approval_response(
            response, original_decision, context
        )

        assert decision.result == ValidationResult.BLOCKED
        assert "skipped" in decision.reason.lower()

    def test_denied(
        self,
        controller: SecurityController,
        original_decision: SecurityDecision,
        context: SecurityContext,
    ) -> None:
        """Should handle denied response."""
        from agentsh.security.approval import ApprovalResult

        response = MagicMock()
        response.result = ApprovalResult.DENIED
        response.command = "original"
        response.approver = "testuser"
        response.reason = "Not allowed"

        decision = controller._handle_approval_response(
            response, original_decision, context
        )

        assert decision.result == ValidationResult.BLOCKED
        assert decision.reason == "Not allowed"

    def test_denied_default_reason(
        self,
        controller: SecurityController,
        original_decision: SecurityDecision,
        context: SecurityContext,
    ) -> None:
        """Should use default reason if none provided."""
        from agentsh.security.approval import ApprovalResult

        response = MagicMock()
        response.result = ApprovalResult.DENIED
        response.command = "original"
        response.approver = "testuser"
        response.reason = None

        decision = controller._handle_approval_response(
            response, original_decision, context
        )

        assert decision.result == ValidationResult.BLOCKED
        assert "denied" in decision.reason.lower()


class TestSecurityControllerHelpers:
    """Tests for SecurityController helper methods."""

    @pytest.fixture
    def controller(self) -> SecurityController:
        """Create controller with mocks."""
        return SecurityController(
            classifier=MagicMock(),
            policy_manager=MagicMock(),
            rbac=MagicMock(),
            approval_flow=MagicMock(),
            audit_logger=MagicMock(),
        )

    def test_is_safe_true(self, controller: SecurityController) -> None:
        """Should return True for safe commands."""
        from agentsh.security.classifier import RiskLevel

        assessment = MagicMock()
        assessment.risk_level = RiskLevel.LOW
        assessment.is_blocked = False
        controller.classifier.classify.return_value = assessment

        result = controller.is_safe("ls")

        assert result is True

    def test_is_safe_false_blocked(self, controller: SecurityController) -> None:
        """Should return False for blocked commands."""
        from agentsh.security.classifier import RiskLevel

        assessment = MagicMock()
        assessment.risk_level = RiskLevel.LOW
        assessment.is_blocked = True
        controller.classifier.classify.return_value = assessment

        result = controller.is_safe("rm -rf /")

        assert result is False

    def test_is_safe_false_high_risk(self, controller: SecurityController) -> None:
        """Should return False for high risk commands."""
        from agentsh.security.classifier import RiskLevel

        assessment = MagicMock()
        assessment.risk_level = RiskLevel.HIGH
        assessment.is_blocked = False
        controller.classifier.classify.return_value = assessment

        result = controller.is_safe("sudo rm -rf /home")

        assert result is False

    def test_get_risk_level(self, controller: SecurityController) -> None:
        """Should return risk level from classifier."""
        from agentsh.security.classifier import RiskLevel

        assessment = MagicMock()
        assessment.risk_level = RiskLevel.MEDIUM
        controller.classifier.classify.return_value = assessment

        result = controller.get_risk_level("sudo apt install")

        assert result == RiskLevel.MEDIUM

    def test_set_policy(self, controller: SecurityController) -> None:
        """Should set default policy."""
        mock_policy = MagicMock()
        mock_policy.name = "strict"

        controller.set_policy(mock_policy)

        controller.policy_manager.set_default_policy.assert_called_once_with(mock_policy)

    def test_register_user(self, controller: SecurityController) -> None:
        """Should register user."""
        mock_user = MagicMock()

        controller.register_user(mock_user)

        controller.rbac.register_user.assert_called_once_with(mock_user)
