"""Tests for robot safety controller."""

import pytest

from agentsh.plugins.robotics.safety import (
    MotionCommand,
    MotionRiskLevel,
    MotionValidation,
    RobotSafetyController,
    RobotSafetyState,
    RobotStatus,
    SafetyConstraints,
    ValidationResult,
    get_safety_controller,
    set_safety_controller,
)


class TestSafetyConstraints:
    """Tests for SafetyConstraints dataclass."""

    def test_default_constraints(self) -> None:
        """Should create constraints with default values."""
        constraints = SafetyConstraints()

        assert constraints.max_linear_velocity == 1.0
        assert constraints.max_angular_velocity == 1.0
        assert constraints.max_acceleration == 2.0
        assert constraints.min_battery_level == 10.0
        assert constraints.require_human_proximity_check is True
        assert constraints.human_safe_distance == 0.5

    def test_custom_constraints(self) -> None:
        """Should create constraints with custom values."""
        constraints = SafetyConstraints(
            max_linear_velocity=2.0,
            max_angular_velocity=1.5,
            workspace_bounds=[-5, 5, -5, 5, 0, 2],
            min_battery_level=20.0,
        )

        assert constraints.max_linear_velocity == 2.0
        assert constraints.workspace_bounds == [-5, 5, -5, 5, 0, 2]
        assert constraints.min_battery_level == 20.0

    def test_constraints_to_dict(self) -> None:
        """Should convert constraints to dictionary."""
        constraints = SafetyConstraints(max_linear_velocity=1.5)
        data = constraints.to_dict()

        assert data["max_linear_velocity"] == 1.5
        assert "allowed_states_for_motion" in data

    def test_constraints_from_dict(self) -> None:
        """Should create constraints from dictionary."""
        data = {
            "max_linear_velocity": 2.5,
            "min_battery_level": 15.0,
            "allowed_states_for_motion": ["supervised"],
        }

        constraints = SafetyConstraints.from_dict(data)

        assert constraints.max_linear_velocity == 2.5
        assert constraints.min_battery_level == 15.0
        assert RobotSafetyState.SUPERVISED in constraints.allowed_states_for_motion


class TestRobotStatus:
    """Tests for RobotStatus dataclass."""

    def test_default_status(self) -> None:
        """Should create status with default values."""
        status = RobotStatus(robot_id="test_robot")

        assert status.robot_id == "test_robot"
        assert status.safety_state == RobotSafetyState.IDLE
        assert status.battery_level == 100.0
        assert status.estop_engaged is False
        assert status.errors == []

    def test_status_to_dict(self) -> None:
        """Should convert status to dictionary."""
        status = RobotStatus(
            robot_id="robot1",
            safety_state=RobotSafetyState.SUPERVISED,
            battery_level=75.0,
        )

        data = status.to_dict()

        assert data["robot_id"] == "robot1"
        assert data["safety_state"] == "supervised"
        assert data["battery_level"] == 75.0


class TestMotionCommand:
    """Tests for MotionCommand dataclass."""

    def test_velocity_command(self) -> None:
        """Should create velocity command."""
        command = MotionCommand(
            command_type="velocity",
            target={"linear": {"x": 0.5}},
            velocity=0.5,
        )

        assert command.command_type == "velocity"
        assert command.velocity == 0.5

    def test_position_command(self) -> None:
        """Should create position command."""
        command = MotionCommand(
            command_type="position",
            target={"position": [1.0, 2.0, 0.5]},
            acceleration=1.0,
        )

        assert command.command_type == "position"
        assert command.acceleration == 1.0


class TestRobotSafetyController:
    """Tests for RobotSafetyController."""

    @pytest.fixture
    def controller(self) -> RobotSafetyController:
        """Create a safety controller for testing."""
        return RobotSafetyController()

    @pytest.fixture
    def supervised_status(self) -> RobotStatus:
        """Create a robot status in supervised mode."""
        return RobotStatus(
            robot_id="test_robot",
            safety_state=RobotSafetyState.SUPERVISED,
            battery_level=80.0,
        )

    def test_initial_state(self, controller: RobotSafetyController) -> None:
        """Should start in IDLE state."""
        assert controller.current_state == RobotSafetyState.IDLE
        assert controller.estop_engaged is False

    def test_set_constraints(self, controller: RobotSafetyController) -> None:
        """Should update safety constraints."""
        constraints = SafetyConstraints(max_linear_velocity=2.0)
        controller.set_constraints(constraints)

        assert controller.constraints.max_linear_velocity == 2.0

    # State transition tests

    def test_valid_state_transitions(self, controller: RobotSafetyController) -> None:
        """Should allow valid state transitions."""
        # IDLE -> SUPERVISED
        assert controller.transition_state(RobotSafetyState.SUPERVISED)
        assert controller.current_state == RobotSafetyState.SUPERVISED

        # SUPERVISED -> AUTONOMOUS
        assert controller.transition_state(RobotSafetyState.AUTONOMOUS)
        assert controller.current_state == RobotSafetyState.AUTONOMOUS

        # AUTONOMOUS -> IDLE
        assert controller.transition_state(RobotSafetyState.IDLE)
        assert controller.current_state == RobotSafetyState.IDLE

    def test_invalid_state_transition(self, controller: RobotSafetyController) -> None:
        """Should reject invalid state transitions."""
        # IDLE -> AUTONOMOUS (not allowed, must go through SUPERVISED)
        assert not controller.transition_state(RobotSafetyState.AUTONOMOUS)
        assert controller.current_state == RobotSafetyState.IDLE

    def test_transition_to_maintenance(self, controller: RobotSafetyController) -> None:
        """Should allow transition to maintenance from IDLE."""
        assert controller.transition_state(RobotSafetyState.MAINTENANCE)
        assert controller.current_state == RobotSafetyState.MAINTENANCE

        # From MAINTENANCE, can only go to IDLE
        assert not controller.transition_state(RobotSafetyState.SUPERVISED)
        assert controller.transition_state(RobotSafetyState.IDLE)

    def test_transition_blocked_during_estop(
        self, controller: RobotSafetyController
    ) -> None:
        """Should block transitions while E-Stop is engaged."""
        controller.engage_estop("test")

        assert not controller.transition_state(RobotSafetyState.SUPERVISED)
        assert controller.current_state == RobotSafetyState.ESTOP

    # E-Stop tests

    def test_engage_estop(self, controller: RobotSafetyController) -> None:
        """Should engage emergency stop."""
        controller.engage_estop("Safety test")

        assert controller.estop_engaged
        assert controller.current_state == RobotSafetyState.ESTOP

    def test_release_estop(self, controller: RobotSafetyController) -> None:
        """Should release emergency stop."""
        controller.engage_estop("test")
        result = controller.release_estop()

        assert result is True
        assert not controller.estop_engaged
        assert controller.current_state == RobotSafetyState.IDLE

    def test_release_estop_when_not_engaged(
        self, controller: RobotSafetyController
    ) -> None:
        """Should return False when releasing non-engaged E-Stop."""
        result = controller.release_estop()
        assert result is False

    # Motion validation tests

    def test_validate_safe_motion(
        self,
        controller: RobotSafetyController,
        supervised_status: RobotStatus,
    ) -> None:
        """Should approve safe motion commands."""
        command = MotionCommand(
            command_type="velocity",
            target={"linear": {"x": 0.5}},
            velocity=0.5,
        )

        validation = controller.validate_motion(command, supervised_status)

        assert validation.result == ValidationResult.APPROVED
        assert validation.allowed is True
        assert validation.risk_level == MotionRiskLevel.LOW

    def test_motion_blocked_in_idle_state(
        self, controller: RobotSafetyController
    ) -> None:
        """Should block motion in IDLE state."""
        status = RobotStatus(
            robot_id="test",
            safety_state=RobotSafetyState.IDLE,
        )
        command = MotionCommand(command_type="velocity", target={})

        validation = controller.validate_motion(command, status)

        assert validation.result == ValidationResult.BLOCKED
        assert validation.allowed is False

    def test_motion_blocked_during_estop(
        self,
        controller: RobotSafetyController,
        supervised_status: RobotStatus,
    ) -> None:
        """Should block all motion during E-Stop."""
        controller.engage_estop("test")
        command = MotionCommand(command_type="velocity", target={})

        validation = controller.validate_motion(command, supervised_status)

        assert validation.result == ValidationResult.ESTOP_ACTIVE
        assert validation.allowed is False
        assert validation.risk_level == MotionRiskLevel.CRITICAL

    def test_motion_blocked_when_status_estop(
        self, controller: RobotSafetyController
    ) -> None:
        """Should block motion when status reports E-Stop."""
        status = RobotStatus(
            robot_id="test",
            safety_state=RobotSafetyState.SUPERVISED,
            estop_engaged=True,
        )
        command = MotionCommand(command_type="velocity", target={})

        validation = controller.validate_motion(command, status)

        assert validation.result == ValidationResult.ESTOP_ACTIVE
        assert validation.allowed is False

    def test_motion_needs_approval_low_battery(
        self,
        controller: RobotSafetyController,
        supervised_status: RobotStatus,
    ) -> None:
        """Should require approval for low battery."""
        supervised_status.battery_level = 5.0
        command = MotionCommand(command_type="velocity", target={})

        validation = controller.validate_motion(command, supervised_status)

        assert validation.result == ValidationResult.NEEDS_APPROVAL
        assert validation.requires_approval is True
        assert "Low battery" in validation.reasons[0]

    def test_motion_blocked_human_too_close(
        self, controller: RobotSafetyController
    ) -> None:
        """Should block motion when human is too close."""
        status = RobotStatus(
            robot_id="test",
            safety_state=RobotSafetyState.SUPERVISED,
            human_detected=True,
            human_distance=0.3,  # Less than default 0.5m
        )
        command = MotionCommand(command_type="velocity", target={})

        validation = controller.validate_motion(command, status)

        assert validation.result == ValidationResult.BLOCKED
        assert validation.allowed is False
        assert "Human detected" in validation.reasons[0]

    def test_motion_needs_approval_human_nearby(
        self, controller: RobotSafetyController
    ) -> None:
        """Should warn when human is nearby but not too close."""
        status = RobotStatus(
            robot_id="test",
            safety_state=RobotSafetyState.SUPERVISED,
            human_detected=True,
            human_distance=0.8,  # Between 0.5m and 1.0m
        )
        command = MotionCommand(command_type="velocity", target={})

        validation = controller.validate_motion(command, status)

        assert validation.requires_approval is True
        assert "Human nearby" in validation.reasons[0]

    def test_motion_needs_approval_velocity_exceeded(
        self,
        controller: RobotSafetyController,
        supervised_status: RobotStatus,
    ) -> None:
        """Should require approval for exceeded velocity."""
        command = MotionCommand(
            command_type="velocity",
            target={},
            velocity=2.0,  # Exceeds default 1.0 m/s
        )

        validation = controller.validate_motion(command, supervised_status)

        assert validation.requires_approval is True
        assert "Velocity" in validation.reasons[0]

    def test_motion_workspace_bounds_check(
        self,
        controller: RobotSafetyController,
        supervised_status: RobotStatus,
    ) -> None:
        """Should check workspace bounds."""
        controller.set_constraints(
            SafetyConstraints(workspace_bounds=[-1, 1, -1, 1, 0, 1])
        )
        command = MotionCommand(
            command_type="position",
            target={"position": [2.0, 0.0, 0.5]},  # X outside bounds
        )

        validation = controller.validate_motion(command, supervised_status)

        assert validation.requires_approval is True
        assert "X position" in validation.reasons[0]

    def test_motion_blocked_with_errors(
        self,
        controller: RobotSafetyController,
        supervised_status: RobotStatus,
    ) -> None:
        """Should flag motion when robot has errors."""
        supervised_status.errors = ["Motor driver fault"]
        command = MotionCommand(command_type="velocity", target={})

        validation = controller.validate_motion(command, supervised_status)

        assert validation.requires_approval is True
        assert "active errors" in validation.reasons[0]

    # Callback tests

    def test_state_change_callback(self, controller: RobotSafetyController) -> None:
        """Should notify state change callbacks."""
        changes: list[tuple[RobotSafetyState, RobotSafetyState]] = []
        controller.on_state_change(lambda old, new: changes.append((old, new)))

        controller.transition_state(RobotSafetyState.SUPERVISED)

        assert len(changes) == 1
        assert changes[0] == (RobotSafetyState.IDLE, RobotSafetyState.SUPERVISED)

    def test_motion_blocked_callback(
        self, controller: RobotSafetyController
    ) -> None:
        """Should notify motion blocked callbacks."""
        blocked: list[tuple[MotionCommand, list[str]]] = []
        controller.on_motion_blocked(lambda cmd, reasons: blocked.append((cmd, reasons)))

        # Use supervised state with low battery - this triggers callback
        # (not an early return case like IDLE state)
        status = RobotStatus(
            robot_id="test",
            safety_state=RobotSafetyState.SUPERVISED,
            battery_level=5.0,  # Low battery triggers needs_approval
        )
        command = MotionCommand(command_type="velocity", target={})

        controller.validate_motion(command, status)

        assert len(blocked) == 1
        assert blocked[0][0] == command


class TestGlobalSafetyController:
    """Tests for global safety controller functions."""

    def teardown_method(self) -> None:
        """Reset global controller after each test."""
        set_safety_controller(None)

    def test_get_global_controller(self) -> None:
        """Should create and return global controller."""
        controller = get_safety_controller()
        assert isinstance(controller, RobotSafetyController)

        # Should return same instance
        assert get_safety_controller() is controller

    def test_set_global_controller(self) -> None:
        """Should set custom global controller."""
        custom = RobotSafetyController(
            constraints=SafetyConstraints(max_linear_velocity=5.0)
        )
        set_safety_controller(custom)

        assert get_safety_controller() is custom
        assert get_safety_controller().constraints.max_linear_velocity == 5.0
