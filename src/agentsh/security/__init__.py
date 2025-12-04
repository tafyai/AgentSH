"""Security and permission controls for AgentSH."""

from agentsh.security.approval import (
    ApprovalFlow,
    ApprovalRequest,
    ApprovalResponse,
    ApprovalResult,
    AutoApprover,
)
from agentsh.security.audit import AuditAction, AuditEvent, AuditLogger
from agentsh.security.classifier import (
    CommandRiskAssessment,
    RiskClassifier,
    RiskLevel,
    RiskPattern,
)
from agentsh.security.controller import (
    SecurityContext,
    SecurityController,
    SecurityDecision,
    ValidationResult,
)
from agentsh.security.policies import (
    DevicePolicy,
    PolicyManager,
    SecurityMode,
    SecurityPolicy,
)
from agentsh.security.rbac import Permission, RBAC, Role, User

__all__ = [
    # Risk Classification
    "RiskLevel",
    "RiskPattern",
    "RiskClassifier",
    "CommandRiskAssessment",
    # Policies
    "SecurityMode",
    "SecurityPolicy",
    "DevicePolicy",
    "PolicyManager",
    # RBAC
    "Role",
    "Permission",
    "User",
    "RBAC",
    # Approval
    "ApprovalResult",
    "ApprovalRequest",
    "ApprovalResponse",
    "ApprovalFlow",
    "AutoApprover",
    # Audit
    "AuditAction",
    "AuditEvent",
    "AuditLogger",
    # Controller
    "ValidationResult",
    "SecurityContext",
    "SecurityDecision",
    "SecurityController",
]
