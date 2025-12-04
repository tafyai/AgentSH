"""Security Controller - Central security enforcement."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union

from agentsh.security.approval import (
    ApprovalFlow,
    ApprovalRequest,
    ApprovalResponse,
    ApprovalResult,
    AutoApprover,
)
from agentsh.security.audit import AuditLogger
from agentsh.security.classifier import CommandRiskAssessment, RiskClassifier, RiskLevel
from agentsh.security.policies import PolicyManager, SecurityPolicy
from agentsh.security.rbac import RBAC, Role, User
from agentsh.telemetry.logger import get_logger, LoggerMixin

logger = get_logger(__name__)


class ValidationResult(Enum):
    """Result of security validation."""

    ALLOW = "allow"  # Command can be executed
    NEED_APPROVAL = "need_approval"  # Requires human approval
    BLOCKED = "blocked"  # Command is blocked


@dataclass
class SecurityContext:
    """Context for security decisions.

    Attributes:
        user: Current user
        device_id: Target device (if applicable)
        cwd: Current working directory
        env: Environment variables
        interactive: Whether running interactively
    """

    user: User
    device_id: Optional[str] = None
    cwd: Optional[str] = None
    env: Optional[dict[str, str]] = None
    interactive: bool = True


@dataclass
class SecurityDecision:
    """Result of a security check.

    Attributes:
        result: The validation result
        command: The (possibly modified) command
        risk_assessment: Risk analysis of the command
        reason: Explanation of the decision
        approved_by: Who approved (if applicable)
    """

    result: ValidationResult
    command: str
    risk_assessment: CommandRiskAssessment
    reason: str
    approved_by: Optional[str] = None


class SecurityController(LoggerMixin):
    """Central controller for security enforcement.

    Coordinates risk classification, RBAC checks, policy enforcement,
    approval flow, and audit logging.

    Example:
        controller = SecurityController()
        context = SecurityContext(user=User("alice", "Alice", Role.OPERATOR))

        decision = controller.check("rm -rf ./old_data", context)
        if decision.result == ValidationResult.ALLOW:
            execute(decision.command)
        elif decision.result == ValidationResult.NEED_APPROVAL:
            # Controller will handle approval flow
            final_decision = controller.validate_and_execute(
                "rm -rf ./old_data", context
            )
    """

    def __init__(
        self,
        classifier: Optional[RiskClassifier] = None,
        policy_manager: Optional[PolicyManager] = None,
        rbac: Optional[RBAC] = None,
        approval_flow: Optional[Union[ApprovalFlow, AutoApprover]] = None,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        """Initialize the security controller.

        Args:
            classifier: Risk classifier
            policy_manager: Policy manager
            rbac: RBAC manager
            approval_flow: Approval flow handler
            audit_logger: Audit logger
        """
        self.classifier = classifier or RiskClassifier()
        self.policy_manager = policy_manager or PolicyManager()
        self.rbac = rbac or RBAC()
        self.approval_flow = approval_flow or ApprovalFlow()
        self.audit = audit_logger or AuditLogger()

        self.logger.info("SecurityController initialized")

    def check(
        self,
        command: str,
        context: SecurityContext,
    ) -> SecurityDecision:
        """Check if a command is allowed.

        This performs the security check but does NOT execute
        the approval flow or the command itself.

        Args:
            command: Command to check
            context: Security context

        Returns:
            SecurityDecision with the result
        """
        # Step 1: Classify the command
        risk_assessment = self.classifier.classify(command)

        # Step 2: Check if blocked by classifier
        if risk_assessment.is_blocked:
            self.audit.log_command_blocked(
                command=command,
                reason="Blocked by risk classifier",
                risk_level=risk_assessment.risk_level,
            )
            return SecurityDecision(
                result=ValidationResult.BLOCKED,
                command=command,
                risk_assessment=risk_assessment,
                reason=f"Command blocked: {', '.join(risk_assessment.reasons)}",
            )

        # Step 3: Get policy for device
        policy = self.policy_manager.get_policy(context.device_id)

        # Step 4: Check if blocked by policy mode
        if policy.is_blocked_by_mode(risk_assessment.risk_level):
            self.audit.log_command_blocked(
                command=command,
                reason=f"Blocked by security mode: {policy.mode.value}",
                risk_level=risk_assessment.risk_level,
            )
            return SecurityDecision(
                result=ValidationResult.BLOCKED,
                command=command,
                risk_assessment=risk_assessment,
                reason=f"Blocked by security mode: {policy.mode.value}",
            )

        # Step 5: Check RBAC permissions
        allowed, needs_approval, rbac_reason = self.rbac.check_access(
            context.user, risk_assessment.risk_level, context.device_id
        )

        if not allowed and not needs_approval:
            self.audit.log_command_blocked(
                command=command,
                reason=rbac_reason,
                risk_level=risk_assessment.risk_level,
            )
            return SecurityDecision(
                result=ValidationResult.BLOCKED,
                command=command,
                risk_assessment=risk_assessment,
                reason=rbac_reason,
            )

        # Step 6: Check if policy requires approval
        if policy.requires_approval(risk_assessment.risk_level):
            needs_approval = True

        # Step 7: Return decision
        if needs_approval:
            return SecurityDecision(
                result=ValidationResult.NEED_APPROVAL,
                command=command,
                risk_assessment=risk_assessment,
                reason=f"Requires approval: risk={risk_assessment.risk_level.name}",
            )

        return SecurityDecision(
            result=ValidationResult.ALLOW,
            command=command,
            risk_assessment=risk_assessment,
            reason="Allowed by policy",
        )

    def validate_and_approve(
        self,
        command: str,
        context: SecurityContext,
    ) -> SecurityDecision:
        """Validate a command and handle approval if needed.

        This performs the full security flow including approval.

        Args:
            command: Command to validate
            context: Security context

        Returns:
            Final SecurityDecision
        """
        # First, check the command
        decision = self.check(command, context)

        # If blocked, return immediately
        if decision.result == ValidationResult.BLOCKED:
            return decision

        # If allowed, log and return
        if decision.result == ValidationResult.ALLOW:
            return decision

        # If needs approval, run approval flow
        if decision.result == ValidationResult.NEED_APPROVAL:
            if not context.interactive:
                # Non-interactive mode - deny by default
                self.audit.log_command_denied(
                    command=command,
                    reason="Non-interactive mode, approval required",
                    risk_level=decision.risk_assessment.risk_level,
                )
                return SecurityDecision(
                    result=ValidationResult.BLOCKED,
                    command=command,
                    risk_assessment=decision.risk_assessment,
                    reason="Approval required but running non-interactively",
                )

            # Run approval flow
            approval_request = ApprovalRequest(
                command=command,
                risk_level=decision.risk_assessment.risk_level,
                reasons=decision.risk_assessment.reasons,
                context={
                    "user": context.user.name,
                    "cwd": context.cwd or "unknown",
                    "device": context.device_id or "local",
                },
            )

            approval_response = self.approval_flow.request_approval(approval_request)

            return self._handle_approval_response(
                approval_response, decision, context
            )

        return decision

    def _handle_approval_response(
        self,
        response: ApprovalResponse,
        original_decision: SecurityDecision,
        context: SecurityContext,
    ) -> SecurityDecision:
        """Handle the approval response.

        Args:
            response: Approval response
            original_decision: Original security decision
            context: Security context

        Returns:
            Updated SecurityDecision
        """
        if response.result == ApprovalResult.APPROVED:
            self.audit.log_command_approved(
                command=response.command,
                approver=response.approver,
                risk_level=original_decision.risk_assessment.risk_level,
            )
            return SecurityDecision(
                result=ValidationResult.ALLOW,
                command=response.command,
                risk_assessment=original_decision.risk_assessment,
                reason="Approved by user",
                approved_by=response.approver,
            )

        elif response.result == ApprovalResult.EDITED:
            # Re-check the edited command
            new_decision = self.check(response.command, context)

            if new_decision.result == ValidationResult.BLOCKED:
                self.audit.log_command_denied(
                    command=response.command,
                    reason="Edited command still blocked",
                    risk_level=new_decision.risk_assessment.risk_level,
                )
                return new_decision

            self.audit.log_command_approved(
                command=response.command,
                approver=response.approver,
                risk_level=new_decision.risk_assessment.risk_level,
            )
            return SecurityDecision(
                result=ValidationResult.ALLOW,
                command=response.command,
                risk_assessment=new_decision.risk_assessment,
                reason=f"Edited and approved by {response.approver}",
                approved_by=response.approver,
            )

        elif response.result == ApprovalResult.SKIPPED:
            self.audit.log_command_denied(
                command=response.command,
                reason="Approval skipped by user",
                risk_level=original_decision.risk_assessment.risk_level,
            )
            return SecurityDecision(
                result=ValidationResult.BLOCKED,
                command=response.command,
                risk_assessment=original_decision.risk_assessment,
                reason="Approval skipped",
            )

        else:  # DENIED or TIMEOUT
            self.audit.log_command_denied(
                command=response.command,
                reason=response.reason or "Denied by user",
                risk_level=original_decision.risk_assessment.risk_level,
            )
            return SecurityDecision(
                result=ValidationResult.BLOCKED,
                command=response.command,
                risk_assessment=original_decision.risk_assessment,
                reason=response.reason or "Denied by user",
            )

    def is_safe(self, command: str) -> bool:
        """Quick check if a command is safe.

        Args:
            command: Command to check

        Returns:
            True if command is safe to execute without approval
        """
        assessment = self.classifier.classify(command)
        return assessment.risk_level <= RiskLevel.LOW and not assessment.is_blocked

    def get_risk_level(self, command: str) -> RiskLevel:
        """Get the risk level of a command.

        Args:
            command: Command to analyze

        Returns:
            Risk level
        """
        return self.classifier.classify(command).risk_level

    def set_policy(self, policy: SecurityPolicy) -> None:
        """Set the default security policy.

        Args:
            policy: New policy
        """
        self.policy_manager.set_default_policy(policy)
        self.logger.info("Security policy updated", policy=policy.name)

    def register_user(self, user: User) -> None:
        """Register a user.

        Args:
            user: User to register
        """
        self.rbac.register_user(user)
