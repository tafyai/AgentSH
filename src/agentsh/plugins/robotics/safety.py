"""Robot safety controller for AgentSH.

Provides safety validation and controls for robot operations,
including motion approval, state management, and constraint checking.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)


class RobotSafetyState(str, Enum):
    """Robot safety states.

    The robot can be in one of these states, which affects
    what operations are allowed.
    """

    IDLE = "idle"  # Robot is powered but not active
    SUPERVISED = "supervised"  # Human-supervised operation
    AUTONOMOUS = "autonomous"  # Autonomous operation (highest risk)
    ESTOP = "estop"  # Emergency stop - no motion allowed
    MAINTENANCE = "maintenance"  # Maintenance mode - limited operation


class MotionRiskLevel(str, Enum):
    """Risk levels for robot motions."""

    SAFE = "safe"  # Read-only, no motion
    LOW = "low"  # Small, slow movements
    MEDIUM = "medium"  # Normal operation
    HIGH = "high"  # Fast or large movements
    CRITICAL = "critical"  # Potentially dangerous motions


class ValidationResult(str, Enum):
    """Result of a safety validation."""

    APPROVED = "approved"  # Motion is safe to execute
    NEEDS_APPROVAL = "needs_approval"  # Requires human approval
    BLOCKED = "blocked"  # Motion is not allowed
    ESTOP_ACTIVE = "estop_active"  # Emergency stop is active


@dataclass
class SafetyConstraints:
    """Safety constraints for a robot.

    Attributes:
        max_linear_velocity: Maximum linear velocity (m/s)
        max_angular_velocity: Maximum angular velocity (rad/s)
        max_acceleration: Maximum acceleration (m/s²)
        workspace_bounds: Workspace boundaries [x_min, x_max, y_min, y_max, z_min, z_max]
        joint_limits: Joint angle limits per joint
        min_battery_level: Minimum battery percentage to operate
        require_human_proximity_check: Whether to check human proximity
        human_safe_distance: Minimum safe distance from humans (m)
        blocked_zones: Areas where robot cannot enter
        allowed_states_for_motion: States in which motion is allowed
    """

    max_linear_velocity: float = 1.0
    max_angular_velocity: float = 1.0
    max_acceleration: float = 2.0
    workspace_bounds: Optional[list[float]] = None
    joint_limits: Optional[dict[str, tuple[float, float]]] = None
    min_battery_level: float = 10.0
    require_human_proximity_check: bool = True
    human_safe_distance: float = 0.5
    blocked_zones: list[dict[str, Any]] = field(default_factory=list)
    allowed_states_for_motion: list[RobotSafetyState] = field(
        default_factory=lambda: [
            RobotSafetyState.SUPERVISED,
            RobotSafetyState.AUTONOMOUS,
        ]
    )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "max_linear_velocity": self.max_linear_velocity,
            "max_angular_velocity": self.max_angular_velocity,
            "max_acceleration": self.max_acceleration,
            "workspace_bounds": self.workspace_bounds,
            "joint_limits": self.joint_limits,
            "min_battery_level": self.min_battery_level,
            "require_human_proximity_check": self.require_human_proximity_check,
            "human_safe_distance": self.human_safe_distance,
            "blocked_zones": self.blocked_zones,
            "allowed_states_for_motion": [s.value for s in self.allowed_states_for_motion],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SafetyConstraints":
        """Create from dictionary."""
        allowed_states = data.get("allowed_states_for_motion", [])
        if allowed_states:
            allowed_states = [RobotSafetyState(s) for s in allowed_states]
        else:
            allowed_states = [RobotSafetyState.SUPERVISED, RobotSafetyState.AUTONOMOUS]

        return cls(
            max_linear_velocity=data.get("max_linear_velocity", 1.0),
            max_angular_velocity=data.get("max_angular_velocity", 1.0),
            max_acceleration=data.get("max_acceleration", 2.0),
            workspace_bounds=data.get("workspace_bounds"),
            joint_limits=data.get("joint_limits"),
            min_battery_level=data.get("min_battery_level", 10.0),
            require_human_proximity_check=data.get("require_human_proximity_check", True),
            human_safe_distance=data.get("human_safe_distance", 0.5),
            blocked_zones=data.get("blocked_zones", []),
            allowed_states_for_motion=allowed_states,
        )


@dataclass
class RobotStatus:
    """Current status of a robot.

    Attributes:
        robot_id: Robot identifier
        safety_state: Current safety state
        battery_level: Battery percentage (0-100)
        position: Current position [x, y, z]
        orientation: Current orientation [roll, pitch, yaw] or quaternion
        joint_positions: Current joint positions
        linear_velocity: Current linear velocity
        angular_velocity: Current angular velocity
        human_detected: Whether a human is detected nearby
        human_distance: Distance to nearest human (m)
        estop_engaged: Whether emergency stop is engaged
        errors: List of active errors
        last_updated: When status was last updated
    """

    robot_id: str
    safety_state: RobotSafetyState = RobotSafetyState.IDLE
    battery_level: float = 100.0
    position: Optional[list[float]] = None
    orientation: Optional[list[float]] = None
    joint_positions: Optional[dict[str, float]] = None
    linear_velocity: float = 0.0
    angular_velocity: float = 0.0
    human_detected: bool = False
    human_distance: Optional[float] = None
    estop_engaged: bool = False
    errors: list[str] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "robot_id": self.robot_id,
            "safety_state": self.safety_state.value,
            "battery_level": self.battery_level,
            "position": self.position,
            "orientation": self.orientation,
            "joint_positions": self.joint_positions,
            "linear_velocity": self.linear_velocity,
            "angular_velocity": self.angular_velocity,
            "human_detected": self.human_detected,
            "human_distance": self.human_distance,
            "estop_engaged": self.estop_engaged,
            "errors": self.errors,
            "last_updated": self.last_updated.isoformat(),
        }


@dataclass
class MotionCommand:
    """A motion command to validate.

    Attributes:
        command_type: Type of motion (velocity, position, trajectory, etc.)
        target: Target for the motion (depends on type)
        velocity: Commanded velocity
        acceleration: Commanded acceleration
        duration: Expected duration in seconds
        metadata: Additional command metadata
    """

    command_type: str
    target: Any
    velocity: Optional[float] = None
    acceleration: Optional[float] = None
    duration: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MotionValidation:
    """Result of motion validation.

    Attributes:
        result: Validation result
        risk_level: Assessed risk level
        allowed: Whether motion is allowed
        reasons: Reasons for the decision
        modified_command: Modified command if adjustments were made
        requires_approval: Whether human approval is required
        approval_timeout: Timeout for approval request
    """

    result: ValidationResult
    risk_level: MotionRiskLevel
    allowed: bool
    reasons: list[str] = field(default_factory=list)
    modified_command: Optional[MotionCommand] = None
    requires_approval: bool = False
    approval_timeout: float = 30.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "result": self.result.value,
            "risk_level": self.risk_level.value,
            "allowed": self.allowed,
            "reasons": self.reasons,
            "requires_approval": self.requires_approval,
            "approval_timeout": self.approval_timeout,
        }


class RobotSafetyController:
    """Controller for robot safety validation.

    Validates motion commands against safety constraints and
    current robot status. Enforces state transitions and
    emergency stop functionality.

    Example:
        controller = RobotSafetyController()
        controller.set_constraints(constraints)

        # Validate a motion
        command = MotionCommand(command_type="velocity", target={"linear": 0.5})
        validation = controller.validate_motion(command, robot_status)

        if validation.allowed:
            # Execute motion
            pass
        elif validation.requires_approval:
            # Request human approval
            pass
        else:
            # Motion blocked
            print(f"Blocked: {validation.reasons}")
    """

    def __init__(
        self,
        constraints: Optional[SafetyConstraints] = None,
    ) -> None:
        """Initialize safety controller.

        Args:
            constraints: Safety constraints to enforce
        """
        self._constraints = constraints or SafetyConstraints()
        self._current_state = RobotSafetyState.IDLE
        self._estop_engaged = False
        self._estop_reason: Optional[str] = None
        self._state_change_callbacks: list[Callable[[RobotSafetyState, RobotSafetyState], None]] = []
        self._motion_blocked_callbacks: list[Callable[[MotionCommand, list[str]], None]] = []

        logger.debug("RobotSafetyController initialized")

    @property
    def constraints(self) -> SafetyConstraints:
        """Get current safety constraints."""
        return self._constraints

    @property
    def current_state(self) -> RobotSafetyState:
        """Get current safety state."""
        return self._current_state

    @property
    def estop_engaged(self) -> bool:
        """Check if emergency stop is engaged."""
        return self._estop_engaged

    def set_constraints(self, constraints: SafetyConstraints) -> None:
        """Set safety constraints.

        Args:
            constraints: New safety constraints
        """
        self._constraints = constraints
        logger.info("Safety constraints updated")

    def validate_motion(
        self,
        command: MotionCommand,
        status: RobotStatus,
    ) -> MotionValidation:
        """Validate a motion command against safety constraints.

        Args:
            command: Motion command to validate
            status: Current robot status

        Returns:
            MotionValidation result
        """
        reasons: list[str] = []
        risk_level = MotionRiskLevel.LOW

        # Check emergency stop
        if self._estop_engaged or status.estop_engaged:
            return MotionValidation(
                result=ValidationResult.ESTOP_ACTIVE,
                risk_level=MotionRiskLevel.CRITICAL,
                allowed=False,
                reasons=[f"Emergency stop is active: {self._estop_reason or 'E-Stop engaged'}"],
            )

        # Check safety state
        if status.safety_state not in self._constraints.allowed_states_for_motion:
            return MotionValidation(
                result=ValidationResult.BLOCKED,
                risk_level=MotionRiskLevel.MEDIUM,
                allowed=False,
                reasons=[
                    f"Motion not allowed in {status.safety_state.value} state. "
                    f"Allowed states: {[s.value for s in self._constraints.allowed_states_for_motion]}"
                ],
            )

        # Check battery level
        if status.battery_level < self._constraints.min_battery_level:
            reasons.append(
                f"Low battery: {status.battery_level}% "
                f"(minimum: {self._constraints.min_battery_level}%)"
            )
            risk_level = MotionRiskLevel.HIGH

        # Check human proximity
        if self._constraints.require_human_proximity_check and status.human_detected:
            if status.human_distance is not None:
                if status.human_distance < self._constraints.human_safe_distance:
                    return MotionValidation(
                        result=ValidationResult.BLOCKED,
                        risk_level=MotionRiskLevel.CRITICAL,
                        allowed=False,
                        reasons=[
                            f"Human detected at {status.human_distance:.2f}m "
                            f"(safe distance: {self._constraints.human_safe_distance}m)"
                        ],
                    )
                elif status.human_distance < self._constraints.human_safe_distance * 2:
                    reasons.append(
                        f"Human nearby at {status.human_distance:.2f}m"
                    )
                    risk_level = max(risk_level, MotionRiskLevel.MEDIUM)

        # Check velocity limits
        if command.velocity is not None:
            if command.command_type in ["velocity", "move"]:
                if command.velocity > self._constraints.max_linear_velocity:
                    reasons.append(
                        f"Velocity {command.velocity} exceeds limit "
                        f"{self._constraints.max_linear_velocity}"
                    )
                    risk_level = max(risk_level, MotionRiskLevel.HIGH)

        # Check acceleration limits
        if command.acceleration is not None:
            if command.acceleration > self._constraints.max_acceleration:
                reasons.append(
                    f"Acceleration {command.acceleration} exceeds limit "
                    f"{self._constraints.max_acceleration}"
                )
                risk_level = max(risk_level, MotionRiskLevel.HIGH)

        # Check workspace bounds
        if (
            self._constraints.workspace_bounds is not None
            and command.target is not None
            and isinstance(command.target, dict)
        ):
            position = command.target.get("position", [])
            if position and len(position) >= 3:
                bounds = self._constraints.workspace_bounds
                if len(bounds) >= 6:
                    x, y, z = position[:3]
                    if not (bounds[0] <= x <= bounds[1]):
                        reasons.append(f"X position {x} outside bounds [{bounds[0]}, {bounds[1]}]")
                        risk_level = max(risk_level, MotionRiskLevel.HIGH)
                    if not (bounds[2] <= y <= bounds[3]):
                        reasons.append(f"Y position {y} outside bounds [{bounds[2]}, {bounds[3]}]")
                        risk_level = max(risk_level, MotionRiskLevel.HIGH)
                    if not (bounds[4] <= z <= bounds[5]):
                        reasons.append(f"Z position {z} outside bounds [{bounds[4]}, {bounds[5]}]")
                        risk_level = max(risk_level, MotionRiskLevel.HIGH)

        # Check robot errors
        if status.errors:
            reasons.append(f"Robot has active errors: {status.errors}")
            risk_level = max(risk_level, MotionRiskLevel.HIGH)

        # Determine validation result
        if risk_level == MotionRiskLevel.CRITICAL:
            result = ValidationResult.BLOCKED
            allowed = False
        elif risk_level == MotionRiskLevel.HIGH:
            result = ValidationResult.NEEDS_APPROVAL
            allowed = False
            requires_approval = True
        elif reasons:
            result = ValidationResult.NEEDS_APPROVAL
            allowed = False
            requires_approval = True
        else:
            result = ValidationResult.APPROVED
            allowed = True
            requires_approval = False

        validation = MotionValidation(
            result=result,
            risk_level=risk_level,
            allowed=allowed,
            reasons=reasons,
            requires_approval=not allowed and result != ValidationResult.BLOCKED,
        )

        if not allowed:
            self._notify_motion_blocked(command, reasons)

        logger.debug(
            "Motion validated",
            result=result.value,
            risk_level=risk_level.value,
            allowed=allowed,
            reasons=reasons,
        )

        return validation

    def engage_estop(self, reason: str = "Manual E-Stop") -> None:
        """Engage emergency stop.

        Args:
            reason: Reason for emergency stop
        """
        self._estop_engaged = True
        self._estop_reason = reason
        old_state = self._current_state
        self._current_state = RobotSafetyState.ESTOP

        logger.warning("Emergency stop engaged", reason=reason)
        self._notify_state_change(old_state, RobotSafetyState.ESTOP)

    def release_estop(self) -> bool:
        """Release emergency stop.

        Returns:
            True if released successfully
        """
        if not self._estop_engaged:
            return False

        self._estop_engaged = False
        self._estop_reason = None
        old_state = self._current_state
        self._current_state = RobotSafetyState.IDLE

        logger.info("Emergency stop released")
        self._notify_state_change(old_state, RobotSafetyState.IDLE)
        return True

    def transition_state(
        self,
        new_state: RobotSafetyState,
    ) -> bool:
        """Transition to a new safety state.

        Args:
            new_state: Target safety state

        Returns:
            True if transition was successful
        """
        if self._estop_engaged and new_state != RobotSafetyState.ESTOP:
            logger.warning(
                "Cannot transition while E-Stop engaged",
                requested_state=new_state.value,
            )
            return False

        # Validate state transitions
        valid_transitions = {
            RobotSafetyState.IDLE: [
                RobotSafetyState.SUPERVISED,
                RobotSafetyState.MAINTENANCE,
                RobotSafetyState.ESTOP,
            ],
            RobotSafetyState.SUPERVISED: [
                RobotSafetyState.IDLE,
                RobotSafetyState.AUTONOMOUS,
                RobotSafetyState.ESTOP,
            ],
            RobotSafetyState.AUTONOMOUS: [
                RobotSafetyState.SUPERVISED,
                RobotSafetyState.IDLE,
                RobotSafetyState.ESTOP,
            ],
            RobotSafetyState.MAINTENANCE: [
                RobotSafetyState.IDLE,
                RobotSafetyState.ESTOP,
            ],
            RobotSafetyState.ESTOP: [
                RobotSafetyState.IDLE,
            ],
        }

        allowed = valid_transitions.get(self._current_state, [])
        if new_state not in allowed:
            logger.warning(
                "Invalid state transition",
                current=self._current_state.value,
                requested=new_state.value,
                allowed=[s.value for s in allowed],
            )
            return False

        old_state = self._current_state
        self._current_state = new_state

        logger.info(
            "Safety state transition",
            from_state=old_state.value,
            to_state=new_state.value,
        )
        self._notify_state_change(old_state, new_state)
        return True

    def on_state_change(
        self,
        callback: Callable[[RobotSafetyState, RobotSafetyState], None],
    ) -> None:
        """Register a callback for state changes.

        Args:
            callback: Function called with (old_state, new_state)
        """
        self._state_change_callbacks.append(callback)

    def on_motion_blocked(
        self,
        callback: Callable[[MotionCommand, list[str]], None],
    ) -> None:
        """Register a callback for blocked motions.

        Args:
            callback: Function called with (command, reasons)
        """
        self._motion_blocked_callbacks.append(callback)

    def _notify_state_change(
        self,
        old_state: RobotSafetyState,
        new_state: RobotSafetyState,
    ) -> None:
        """Notify callbacks of state change."""
        for callback in self._state_change_callbacks:
            try:
                callback(old_state, new_state)
            except Exception as e:
                logger.error("State change callback error", error=str(e))

    def _notify_motion_blocked(
        self,
        command: MotionCommand,
        reasons: list[str],
    ) -> None:
        """Notify callbacks of blocked motion."""
        for callback in self._motion_blocked_callbacks:
            try:
                callback(command, reasons)
            except Exception as e:
                logger.error("Motion blocked callback error", error=str(e))


# Global safety controller instance
_safety_controller: Optional[RobotSafetyController] = None


def get_safety_controller() -> RobotSafetyController:
    """Get the global robot safety controller.

    Returns:
        Global RobotSafetyController singleton
    """
    global _safety_controller
    if _safety_controller is None:
        _safety_controller = RobotSafetyController()
    return _safety_controller


def set_safety_controller(controller: Optional[RobotSafetyController]) -> None:
    """Set the global robot safety controller.

    Args:
        controller: RobotSafetyController instance to use globally
    """
    global _safety_controller
    _safety_controller = controller
