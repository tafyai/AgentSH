"""Human-in-the-Loop Approval - Interactive command approval."""

import sys
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable, Optional

from agentsh.security.classifier import RiskLevel
from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)


class ApprovalResult(Enum):
    """Result of an approval request."""

    APPROVED = "approved"  # User approved the command
    DENIED = "denied"  # User denied the command
    EDITED = "edited"  # User edited the command
    TIMEOUT = "timeout"  # Request timed out
    SKIPPED = "skipped"  # Approval was skipped (permissive mode)


@dataclass
class ApprovalRequest:
    """Request for human approval.

    Attributes:
        command: Command to approve
        risk_level: Risk level of the command
        reasons: Reasons for requiring approval
        context: Additional context (cwd, device, etc.)
        timeout: Approval timeout in seconds
    """

    command: str
    risk_level: RiskLevel
    reasons: list[str]
    context: dict[str, str]
    timeout: float = 30.0


@dataclass
class ApprovalResponse:
    """Response to an approval request.

    Attributes:
        result: The approval result
        command: The (possibly edited) command
        approver: Who approved/denied
        timestamp: When the decision was made
        reason: Reason for the decision
    """

    result: ApprovalResult
    command: str
    approver: str
    timestamp: datetime
    reason: Optional[str] = None


class ApprovalFlow:
    """Manages the human-in-the-loop approval process.

    Handles displaying approval requests to users and collecting
    their responses.

    Example:
        flow = ApprovalFlow()
        request = ApprovalRequest(
            command="rm -rf ./old_data",
            risk_level=RiskLevel.HIGH,
            reasons=["Recursive delete operation"],
            context={"cwd": "/home/user"},
        )
        response = flow.request_approval(request)
        if response.result == ApprovalResult.APPROVED:
            execute(response.command)
    """

    # Risk level display colors (ANSI)
    RISK_COLORS = {
        RiskLevel.SAFE: "\033[32m",  # Green
        RiskLevel.LOW: "\033[33m",  # Yellow
        RiskLevel.MEDIUM: "\033[33m",  # Yellow
        RiskLevel.HIGH: "\033[31m",  # Red
        RiskLevel.CRITICAL: "\033[91m",  # Bright red
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"

    def __init__(
        self,
        use_color: bool = True,
        input_func: Optional[Callable[[], str]] = None,
        output_func: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Initialize the approval flow.

        Args:
            use_color: Whether to use ANSI colors
            input_func: Custom input function (for testing)
            output_func: Custom output function (for testing)
        """
        self.use_color = use_color
        self._input = input_func or self._default_input
        self._output = output_func or self._default_output

    def _default_input(self) -> str:
        """Default input function."""
        try:
            return input().strip().lower()
        except EOFError:
            return "n"

    def _default_output(self, text: str) -> None:
        """Default output function."""
        print(text, file=sys.stderr)

    def _colorize(self, text: str, color: str) -> str:
        """Apply color to text if colors enabled."""
        if self.use_color:
            return f"{color}{text}{self.RESET}"
        return text

    def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        """Request human approval for a command.

        Displays the command and risk information, then prompts
        the user for approval.

        Args:
            request: The approval request

        Returns:
            ApprovalResponse with the user's decision
        """
        import os

        approver = os.environ.get("USER", os.environ.get("USERNAME", "unknown"))

        # Display approval request
        self._display_request(request)

        # Get user response
        self._output("\n[y]es / [n]o / [e]dit / [s]kip > ")

        try:
            response = self._input()
        except KeyboardInterrupt:
            self._output("\nApproval cancelled.\n")
            return ApprovalResponse(
                result=ApprovalResult.DENIED,
                command=request.command,
                approver=approver,
                timestamp=datetime.now(),
                reason="Cancelled by user",
            )

        # Process response
        if response in ("y", "yes"):
            logger.info("Command approved", command=request.command[:50])
            return ApprovalResponse(
                result=ApprovalResult.APPROVED,
                command=request.command,
                approver=approver,
                timestamp=datetime.now(),
            )

        elif response in ("n", "no", ""):
            logger.info("Command denied", command=request.command[:50])
            return ApprovalResponse(
                result=ApprovalResult.DENIED,
                command=request.command,
                approver=approver,
                timestamp=datetime.now(),
            )

        elif response in ("e", "edit"):
            return self._handle_edit(request, approver)

        elif response in ("s", "skip"):
            logger.info("Approval skipped", command=request.command[:50])
            return ApprovalResponse(
                result=ApprovalResult.SKIPPED,
                command=request.command,
                approver=approver,
                timestamp=datetime.now(),
                reason="Skipped by user",
            )

        else:
            # Invalid response, treat as denied
            self._output("Invalid response. Command denied.\n")
            return ApprovalResponse(
                result=ApprovalResult.DENIED,
                command=request.command,
                approver=approver,
                timestamp=datetime.now(),
                reason=f"Invalid response: {response}",
            )

    def _display_request(self, request: ApprovalRequest) -> None:
        """Display the approval request to the user.

        Args:
            request: Approval request to display
        """
        color = self.RISK_COLORS.get(request.risk_level, "")

        self._output("\n" + "=" * 60)
        self._output(
            self._colorize(
                f"{self.BOLD}  APPROVAL REQUIRED  {self.RESET}", color
            )
        )
        self._output("=" * 60)

        self._output(f"\n  Risk Level: {self._colorize(request.risk_level.name, color)}")
        self._output(f"\n  Command:")
        self._output(f"    {self._colorize(request.command, self.BOLD)}")

        if request.reasons:
            self._output(f"\n  Reasons:")
            for reason in request.reasons:
                self._output(f"    - {reason}")

        if request.context:
            self._output(f"\n  Context:")
            for key, value in request.context.items():
                self._output(f"    {key}: {value}")

        self._output("\n" + "-" * 60)

    def _handle_edit(
        self, request: ApprovalRequest, approver: str
    ) -> ApprovalResponse:
        """Handle command editing.

        Args:
            request: Original approval request
            approver: User doing the editing

        Returns:
            ApprovalResponse with edited command
        """
        self._output("\nEdit command (press Enter to confirm):")
        self._output(f"Original: {request.command}")
        self._output("New command: ")

        try:
            edited = self._input()
            if not edited:
                edited = request.command

            # Re-display for confirmation
            self._output(f"\nEdited command: {edited}")
            self._output("Approve edited command? [y/n] > ")

            confirm = self._input()
            if confirm in ("y", "yes"):
                logger.info(
                    "Command edited and approved",
                    original=request.command[:50],
                    edited=edited[:50],
                )
                return ApprovalResponse(
                    result=ApprovalResult.EDITED,
                    command=edited,
                    approver=approver,
                    timestamp=datetime.now(),
                    reason=f"Edited from: {request.command}",
                )

        except KeyboardInterrupt:
            self._output("\nEdit cancelled.\n")

        return ApprovalResponse(
            result=ApprovalResult.DENIED,
            command=request.command,
            approver=approver,
            timestamp=datetime.now(),
            reason="Edit cancelled",
        )


class AutoApprover:
    """Automatic approver for non-interactive contexts.

    Used when running in batch mode or for testing.
    """

    def __init__(
        self,
        auto_approve_levels: Optional[list[RiskLevel]] = None,
        auto_deny: bool = False,
    ) -> None:
        """Initialize the auto approver.

        Args:
            auto_approve_levels: Risk levels to auto-approve
            auto_deny: If True, deny all requests
        """
        self.auto_approve_levels = auto_approve_levels or [RiskLevel.SAFE, RiskLevel.LOW]
        self.auto_deny = auto_deny

    def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        """Automatically approve or deny based on risk level.

        Args:
            request: Approval request

        Returns:
            Automatic approval response
        """
        import os

        approver = f"auto:{os.environ.get('USER', 'system')}"

        if self.auto_deny:
            return ApprovalResponse(
                result=ApprovalResult.DENIED,
                command=request.command,
                approver=approver,
                timestamp=datetime.now(),
                reason="Auto-deny enabled",
            )

        if request.risk_level in self.auto_approve_levels:
            return ApprovalResponse(
                result=ApprovalResult.APPROVED,
                command=request.command,
                approver=approver,
                timestamp=datetime.now(),
                reason=f"Auto-approved (risk={request.risk_level.name})",
            )

        return ApprovalResponse(
            result=ApprovalResult.DENIED,
            command=request.command,
            approver=approver,
            timestamp=datetime.now(),
            reason=f"Risk level {request.risk_level.name} not in auto-approve list",
        )
