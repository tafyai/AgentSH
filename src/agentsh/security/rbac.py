"""RBAC - Role-Based Access Control for AgentSH."""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

from agentsh.security.classifier import RiskLevel
from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)


class Role(IntEnum):
    """User roles with hierarchy.

    Uses IntEnum for easy comparison (ADMIN > OPERATOR > VIEWER)
    """

    VIEWER = 0  # Read-only access
    OPERATOR = 1  # Can execute safe commands
    ADMIN = 2  # Full access with approval for high-risk
    SUPERUSER = 3  # Full access, no restrictions


@dataclass
class Permission:
    """Permission definition for a role and risk level.

    Attributes:
        can_execute: Whether direct execution is allowed
        can_approve: Whether user can approve commands at this level
        requires_approval: Whether command needs approval first
    """

    can_execute: bool = False
    can_approve: bool = False
    requires_approval: bool = False


@dataclass
class User:
    """User identity with role.

    Attributes:
        id: Unique user identifier
        name: Display name
        role: User's role
        device_roles: Per-device role overrides
    """

    id: str
    name: str
    role: Role = Role.OPERATOR
    device_roles: dict[str, Role] = field(default_factory=dict)

    def get_role(self, device_id: Optional[str] = None) -> Role:
        """Get role for a specific device.

        Args:
            device_id: Device identifier (uses default role if not specified)

        Returns:
            Role for the device
        """
        if device_id and device_id in self.device_roles:
            return self.device_roles[device_id]
        return self.role


class RBAC:
    """Role-Based Access Control manager.

    Determines what actions users can take based on their role
    and the risk level of commands.

    Permission Matrix:
    | Role      | SAFE | LOW  | MEDIUM   | HIGH     | CRITICAL |
    |-----------|------|------|----------|----------|----------|
    | VIEWER    | No   | No   | No       | No       | Block    |
    | OPERATOR  | Yes  | Yes  | Approval | No       | Block    |
    | ADMIN     | Yes  | Yes  | Yes      | Approval | Block    |
    | SUPERUSER | Yes  | Yes  | Yes      | Yes      | Approval |

    Example:
        rbac = RBAC()
        user = User(id="user1", name="Alice", role=Role.OPERATOR)

        # Check if user can execute a command
        perm = rbac.get_permission(user.role, RiskLevel.SAFE)
        if perm.can_execute:
            execute_command()
    """

    # Permission matrix: role -> risk_level -> Permission
    PERMISSION_MATRIX: dict[Role, dict[RiskLevel, Permission]] = {
        Role.VIEWER: {
            RiskLevel.SAFE: Permission(can_execute=False, can_approve=False),
            RiskLevel.LOW: Permission(can_execute=False, can_approve=False),
            RiskLevel.MEDIUM: Permission(can_execute=False, can_approve=False),
            RiskLevel.HIGH: Permission(can_execute=False, can_approve=False),
            RiskLevel.CRITICAL: Permission(can_execute=False, can_approve=False),
        },
        Role.OPERATOR: {
            RiskLevel.SAFE: Permission(can_execute=True, can_approve=False),
            RiskLevel.LOW: Permission(can_execute=True, can_approve=False),
            RiskLevel.MEDIUM: Permission(
                can_execute=False, can_approve=False, requires_approval=True
            ),
            RiskLevel.HIGH: Permission(can_execute=False, can_approve=False),
            RiskLevel.CRITICAL: Permission(can_execute=False, can_approve=False),
        },
        Role.ADMIN: {
            RiskLevel.SAFE: Permission(can_execute=True, can_approve=True),
            RiskLevel.LOW: Permission(can_execute=True, can_approve=True),
            RiskLevel.MEDIUM: Permission(can_execute=True, can_approve=True),
            RiskLevel.HIGH: Permission(
                can_execute=False, can_approve=True, requires_approval=True
            ),
            RiskLevel.CRITICAL: Permission(can_execute=False, can_approve=False),
        },
        Role.SUPERUSER: {
            RiskLevel.SAFE: Permission(can_execute=True, can_approve=True),
            RiskLevel.LOW: Permission(can_execute=True, can_approve=True),
            RiskLevel.MEDIUM: Permission(can_execute=True, can_approve=True),
            RiskLevel.HIGH: Permission(can_execute=True, can_approve=True),
            RiskLevel.CRITICAL: Permission(
                can_execute=False, can_approve=True, requires_approval=True
            ),
        },
    }

    def __init__(self) -> None:
        """Initialize the RBAC manager."""
        self._users: dict[str, User] = {}
        logger.info("RBAC initialized")

    def get_permission(self, role: Role, risk_level: RiskLevel) -> Permission:
        """Get permission for a role and risk level.

        Args:
            role: User's role
            risk_level: Command risk level

        Returns:
            Permission object describing what's allowed
        """
        role_perms = self.PERMISSION_MATRIX.get(role, {})
        return role_perms.get(
            risk_level, Permission(can_execute=False, can_approve=False)
        )

    def can_execute(self, role: Role, risk_level: RiskLevel) -> bool:
        """Check if role can directly execute at this risk level.

        Args:
            role: User's role
            risk_level: Command risk level

        Returns:
            True if direct execution is allowed
        """
        return self.get_permission(role, risk_level).can_execute

    def can_approve(self, role: Role, risk_level: RiskLevel) -> bool:
        """Check if role can approve commands at this risk level.

        Args:
            role: User's role
            risk_level: Command risk level

        Returns:
            True if user can approve
        """
        return self.get_permission(role, risk_level).can_approve

    def requires_approval(self, role: Role, risk_level: RiskLevel) -> bool:
        """Check if this combination requires approval.

        Args:
            role: User's role
            risk_level: Command risk level

        Returns:
            True if approval is required
        """
        perm = self.get_permission(role, risk_level)
        return perm.requires_approval or (not perm.can_execute and perm.can_approve)

    def is_blocked(self, role: Role, risk_level: RiskLevel) -> bool:
        """Check if this combination is completely blocked.

        Args:
            role: User's role
            risk_level: Command risk level

        Returns:
            True if action is blocked
        """
        perm = self.get_permission(role, risk_level)
        return not perm.can_execute and not perm.requires_approval

    def check_access(
        self, user: User, risk_level: RiskLevel, device_id: Optional[str] = None
    ) -> tuple[bool, bool, str]:
        """Check if user has access to execute a command.

        Args:
            user: User attempting the action
            risk_level: Risk level of the command
            device_id: Optional device identifier

        Returns:
            Tuple of (allowed, needs_approval, reason)
        """
        role = user.get_role(device_id)
        perm = self.get_permission(role, risk_level)

        if perm.can_execute:
            return True, False, "Execution allowed"

        if perm.requires_approval:
            return False, True, f"Requires approval (role={role.name}, risk={risk_level.name})"

        return False, False, f"Blocked (role={role.name}, risk={risk_level.name})"

    def register_user(self, user: User) -> None:
        """Register a user.

        Args:
            user: User to register
        """
        self._users[user.id] = user
        logger.info("User registered", user_id=user.id, role=user.role.name)

    def get_user(self, user_id: str) -> Optional[User]:
        """Get a registered user.

        Args:
            user_id: User identifier

        Returns:
            User or None if not found
        """
        return self._users.get(user_id)

    def get_current_user(self) -> User:
        """Get the current user (from environment).

        Returns:
            Current user or default operator
        """
        import os

        user_id = os.environ.get("USER", os.environ.get("USERNAME", "unknown"))

        if user_id in self._users:
            return self._users[user_id]

        # Return default operator for unknown users
        return User(id=user_id, name=user_id, role=Role.OPERATOR)
