"""Tests for human-in-the-loop approval module."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from agentsh.security.approval import (
    ApprovalFlow,
    ApprovalRequest,
    ApprovalResponse,
    ApprovalResult,
    AutoApprover,
)
from agentsh.security.classifier import RiskLevel


class TestApprovalResult:
    """Tests for ApprovalResult enum."""

    def test_result_values(self) -> None:
        """Should have expected result values."""
        assert ApprovalResult.APPROVED.value == "approved"
        assert ApprovalResult.DENIED.value == "denied"
        assert ApprovalResult.EDITED.value == "edited"
        assert ApprovalResult.TIMEOUT.value == "timeout"
        assert ApprovalResult.SKIPPED.value == "skipped"


class TestApprovalRequest:
    """Tests for ApprovalRequest dataclass."""

    def test_create_request(self) -> None:
        """Should create request with required fields."""
        request = ApprovalRequest(
            command="rm -rf /tmp/test",
            risk_level=RiskLevel.HIGH,
            reasons=["Recursive delete"],
            context={"cwd": "/home/user"},
        )
        assert request.command == "rm -rf /tmp/test"
        assert request.risk_level == RiskLevel.HIGH
        assert len(request.reasons) == 1
        assert request.timeout == 30.0  # default

    def test_custom_timeout(self) -> None:
        """Should accept custom timeout."""
        request = ApprovalRequest(
            command="test",
            risk_level=RiskLevel.LOW,
            reasons=[],
            context={},
            timeout=60.0,
        )
        assert request.timeout == 60.0


class TestApprovalResponse:
    """Tests for ApprovalResponse dataclass."""

    def test_create_response(self) -> None:
        """Should create response with required fields."""
        now = datetime.now()
        response = ApprovalResponse(
            result=ApprovalResult.APPROVED,
            command="echo hello",
            approver="test_user",
            timestamp=now,
        )
        assert response.result == ApprovalResult.APPROVED
        assert response.command == "echo hello"
        assert response.approver == "test_user"
        assert response.timestamp == now
        assert response.reason is None

    def test_response_with_reason(self) -> None:
        """Should accept optional reason."""
        response = ApprovalResponse(
            result=ApprovalResult.DENIED,
            command="rm -rf /",
            approver="admin",
            timestamp=datetime.now(),
            reason="Too dangerous",
        )
        assert response.reason == "Too dangerous"


class TestApprovalFlow:
    """Tests for ApprovalFlow class."""

    @pytest.fixture
    def flow(self) -> ApprovalFlow:
        """Create a flow with mocked I/O."""
        return ApprovalFlow(
            use_color=False,
            input_func=MagicMock(return_value="y"),
            output_func=MagicMock(),
        )

    @pytest.fixture
    def approval_request(self) -> ApprovalRequest:
        """Create a test request."""
        return ApprovalRequest(
            command="rm -rf /tmp/test",
            risk_level=RiskLevel.HIGH,
            reasons=["Recursive delete", "Force flag"],
            context={"cwd": "/home/user", "device": "localhost"},
        )

    def test_create_flow_defaults(self) -> None:
        """Should create flow with defaults."""
        flow = ApprovalFlow()
        assert flow.use_color is True

    def test_create_flow_no_color(self) -> None:
        """Should disable colors."""
        flow = ApprovalFlow(use_color=False)
        assert flow.use_color is False

    def test_colorize_with_color(self) -> None:
        """Should apply color when enabled."""
        flow = ApprovalFlow(use_color=True)
        result = flow._colorize("text", "\033[31m")
        assert "\033[31m" in result
        assert "text" in result

    def test_colorize_without_color(self) -> None:
        """Should not apply color when disabled."""
        flow = ApprovalFlow(use_color=False)
        result = flow._colorize("text", "\033[31m")
        assert result == "text"

    def test_approve_command(self, approval_request: ApprovalRequest) -> None:
        """Should approve command when user says yes."""
        output = MagicMock()
        flow = ApprovalFlow(
            use_color=False,
            input_func=MagicMock(return_value="y"),
            output_func=output,
        )

        response = flow.request_approval(approval_request)

        assert response.result == ApprovalResult.APPROVED
        assert response.command == approval_request.command

    def test_approve_command_yes(self, approval_request: ApprovalRequest) -> None:
        """Should approve with 'yes'."""
        flow = ApprovalFlow(
            use_color=False,
            input_func=MagicMock(return_value="yes"),
            output_func=MagicMock(),
        )

        response = flow.request_approval(approval_request)
        assert response.result == ApprovalResult.APPROVED

    def test_deny_command_n(self, approval_request: ApprovalRequest) -> None:
        """Should deny command when user says no."""
        flow = ApprovalFlow(
            use_color=False,
            input_func=MagicMock(return_value="n"),
            output_func=MagicMock(),
        )

        response = flow.request_approval(approval_request)

        assert response.result == ApprovalResult.DENIED
        assert response.command == approval_request.command

    def test_deny_command_no(self, approval_request: ApprovalRequest) -> None:
        """Should deny with 'no'."""
        flow = ApprovalFlow(
            use_color=False,
            input_func=MagicMock(return_value="no"),
            output_func=MagicMock(),
        )

        response = flow.request_approval(approval_request)
        assert response.result == ApprovalResult.DENIED

    def test_deny_command_empty(self, approval_request: ApprovalRequest) -> None:
        """Should deny with empty response."""
        flow = ApprovalFlow(
            use_color=False,
            input_func=MagicMock(return_value=""),
            output_func=MagicMock(),
        )

        response = flow.request_approval(approval_request)
        assert response.result == ApprovalResult.DENIED

    def test_skip_command(self, approval_request: ApprovalRequest) -> None:
        """Should skip when user says skip."""
        flow = ApprovalFlow(
            use_color=False,
            input_func=MagicMock(return_value="s"),
            output_func=MagicMock(),
        )

        response = flow.request_approval(approval_request)

        assert response.result == ApprovalResult.SKIPPED
        assert response.reason == "Skipped by user"

    def test_skip_command_full(self, approval_request: ApprovalRequest) -> None:
        """Should skip with 'skip'."""
        flow = ApprovalFlow(
            use_color=False,
            input_func=MagicMock(return_value="skip"),
            output_func=MagicMock(),
        )

        response = flow.request_approval(approval_request)
        assert response.result == ApprovalResult.SKIPPED

    def test_invalid_response(self, approval_request: ApprovalRequest) -> None:
        """Should deny on invalid response."""
        output = MagicMock()
        flow = ApprovalFlow(
            use_color=False,
            input_func=MagicMock(return_value="maybe"),
            output_func=output,
        )

        response = flow.request_approval(approval_request)

        assert response.result == ApprovalResult.DENIED
        assert "Invalid response" in (response.reason or "")

    def test_edit_and_approve(self, approval_request: ApprovalRequest) -> None:
        """Should allow editing and approving."""
        inputs = iter(["e", "echo safe command", "y"])
        flow = ApprovalFlow(
            use_color=False,
            input_func=lambda: next(inputs),
            output_func=MagicMock(),
        )

        response = flow.request_approval(approval_request)

        assert response.result == ApprovalResult.EDITED
        assert response.command == "echo safe command"

    def test_edit_keep_original(self, approval_request: ApprovalRequest) -> None:
        """Should keep original command if edit is empty."""
        inputs = iter(["e", "", "y"])
        flow = ApprovalFlow(
            use_color=False,
            input_func=lambda: next(inputs),
            output_func=MagicMock(),
        )

        response = flow.request_approval(approval_request)

        assert response.result == ApprovalResult.EDITED
        assert response.command == approval_request.command

    def test_edit_and_deny(self, approval_request: ApprovalRequest) -> None:
        """Should deny if edit confirmation is no."""
        inputs = iter(["e", "new command", "n"])
        flow = ApprovalFlow(
            use_color=False,
            input_func=lambda: next(inputs),
            output_func=MagicMock(),
        )

        response = flow.request_approval(approval_request)

        assert response.result == ApprovalResult.DENIED
        assert response.reason == "Edit cancelled"

    def test_keyboard_interrupt(self, approval_request: ApprovalRequest) -> None:
        """Should deny on keyboard interrupt."""
        def raise_interrupt():
            raise KeyboardInterrupt()

        output = MagicMock()
        flow = ApprovalFlow(
            use_color=False,
            input_func=raise_interrupt,
            output_func=output,
        )

        response = flow.request_approval(approval_request)

        assert response.result == ApprovalResult.DENIED
        assert response.reason == "Cancelled by user"

    def test_keyboard_interrupt_during_edit(self, approval_request: ApprovalRequest) -> None:
        """Should deny on keyboard interrupt during edit."""
        call_count = 0

        def input_with_interrupt():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "e"
            raise KeyboardInterrupt()

        flow = ApprovalFlow(
            use_color=False,
            input_func=input_with_interrupt,
            output_func=MagicMock(),
        )

        response = flow.request_approval(approval_request)

        assert response.result == ApprovalResult.DENIED
        assert response.reason == "Edit cancelled"

    def test_display_request(self, approval_request: ApprovalRequest) -> None:
        """Should display request information."""
        output = MagicMock()
        flow = ApprovalFlow(
            use_color=False,
            input_func=MagicMock(return_value="n"),
            output_func=output,
        )

        flow.request_approval(approval_request)

        # Check that key information was displayed
        output_calls = [str(call) for call in output.call_args_list]
        output_text = " ".join(output_calls)

        assert "APPROVAL REQUIRED" in output_text
        assert "HIGH" in output_text
        assert approval_request.command in output_text

    def test_display_with_no_reasons(self) -> None:
        """Should handle request with no reasons."""
        request = ApprovalRequest(
            command="ls",
            risk_level=RiskLevel.LOW,
            reasons=[],
            context={},
        )
        output = MagicMock()
        flow = ApprovalFlow(
            use_color=False,
            input_func=MagicMock(return_value="y"),
            output_func=output,
        )

        response = flow.request_approval(request)
        assert response.result == ApprovalResult.APPROVED

    def test_display_with_no_context(self) -> None:
        """Should handle request with no context."""
        request = ApprovalRequest(
            command="ls",
            risk_level=RiskLevel.LOW,
            reasons=["Test reason"],
            context={},
        )
        output = MagicMock()
        flow = ApprovalFlow(
            use_color=False,
            input_func=MagicMock(return_value="y"),
            output_func=output,
        )

        response = flow.request_approval(request)
        assert response.result == ApprovalResult.APPROVED

    def test_risk_colors(self) -> None:
        """Should have colors for all risk levels."""
        flow = ApprovalFlow()
        for level in RiskLevel:
            assert level in flow.RISK_COLORS

    def test_default_input_eof(self) -> None:
        """Should handle EOF in default input."""
        flow = ApprovalFlow()

        with patch("builtins.input", side_effect=EOFError()):
            result = flow._default_input()
            assert result == "n"


class TestAutoApprover:
    """Tests for AutoApprover class."""

    @pytest.fixture
    def request_safe(self) -> ApprovalRequest:
        """Create a safe risk request."""
        return ApprovalRequest(
            command="ls -la",
            risk_level=RiskLevel.SAFE,
            reasons=[],
            context={},
        )

    @pytest.fixture
    def request_low(self) -> ApprovalRequest:
        """Create a low risk request."""
        return ApprovalRequest(
            command="cat file.txt",
            risk_level=RiskLevel.LOW,
            reasons=[],
            context={},
        )

    @pytest.fixture
    def request_high(self) -> ApprovalRequest:
        """Create a high risk request."""
        return ApprovalRequest(
            command="rm -rf /",
            risk_level=RiskLevel.HIGH,
            reasons=["Dangerous"],
            context={},
        )

    @pytest.fixture
    def request_critical(self) -> ApprovalRequest:
        """Create a critical risk request."""
        return ApprovalRequest(
            command="dd if=/dev/zero of=/dev/sda",
            risk_level=RiskLevel.CRITICAL,
            reasons=["Disk wipe"],
            context={},
        )

    def test_default_auto_approve_levels(self) -> None:
        """Should default to safe and low."""
        approver = AutoApprover()
        assert RiskLevel.SAFE in approver.auto_approve_levels
        assert RiskLevel.LOW in approver.auto_approve_levels

    def test_auto_approve_safe(self, request_safe: ApprovalRequest) -> None:
        """Should auto-approve safe commands."""
        approver = AutoApprover()
        response = approver.request_approval(request_safe)

        assert response.result == ApprovalResult.APPROVED
        assert "auto:" in response.approver
        assert "Auto-approved" in (response.reason or "")

    def test_auto_approve_low(self, request_low: ApprovalRequest) -> None:
        """Should auto-approve low risk commands."""
        approver = AutoApprover()
        response = approver.request_approval(request_low)

        assert response.result == ApprovalResult.APPROVED

    def test_auto_deny_high(self, request_high: ApprovalRequest) -> None:
        """Should auto-deny high risk commands."""
        approver = AutoApprover()
        response = approver.request_approval(request_high)

        assert response.result == ApprovalResult.DENIED
        assert "not in auto-approve list" in (response.reason or "")

    def test_auto_deny_critical(self, request_critical: ApprovalRequest) -> None:
        """Should auto-deny critical commands."""
        approver = AutoApprover()
        response = approver.request_approval(request_critical)

        assert response.result == ApprovalResult.DENIED

    def test_auto_deny_mode(self, request_safe: ApprovalRequest) -> None:
        """Should deny everything in auto-deny mode."""
        approver = AutoApprover(auto_deny=True)
        response = approver.request_approval(request_safe)

        assert response.result == ApprovalResult.DENIED
        assert response.reason == "Auto-deny enabled"

    def test_custom_auto_approve_levels(
        self, request_high: ApprovalRequest
    ) -> None:
        """Should respect custom auto-approve levels."""
        approver = AutoApprover(
            auto_approve_levels=[RiskLevel.SAFE, RiskLevel.LOW, RiskLevel.HIGH]
        )
        response = approver.request_approval(request_high)

        assert response.result == ApprovalResult.APPROVED

    def test_approver_includes_user(self) -> None:
        """Should include username in approver."""
        request = ApprovalRequest(
            command="ls",
            risk_level=RiskLevel.SAFE,
            reasons=[],
            context={},
        )
        approver = AutoApprover()

        with patch.dict("os.environ", {"USER": "testuser"}):
            response = approver.request_approval(request)
            assert "auto:testuser" in response.approver

    def test_response_has_timestamp(self, request_safe: ApprovalRequest) -> None:
        """Should include timestamp in response."""
        approver = AutoApprover()
        before = datetime.now()
        response = approver.request_approval(request_safe)
        after = datetime.now()

        assert before <= response.timestamp <= after

    def test_response_preserves_command(
        self, request_high: ApprovalRequest
    ) -> None:
        """Should preserve original command in response."""
        approver = AutoApprover()
        response = approver.request_approval(request_high)

        assert response.command == request_high.command
