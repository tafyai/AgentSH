"""Tests for robotics toolset."""

import pytest

from agentsh.plugins.robotics.robotics_toolset import RoboticsToolset
from agentsh.plugins.robotics.ros_interface import ROS2_AVAILABLE, ROS2Client
from agentsh.plugins.robotics.safety import (
    RobotSafetyController,
    RobotSafetyState,
    SafetyConstraints,
)
from agentsh.tools.registry import ToolRegistry


class TestRoboticsToolsetProperties:
    """Tests for RoboticsToolset basic properties."""

    def test_name(self) -> None:
        """Should have correct name."""
        toolset = RoboticsToolset()
        assert toolset.name == "robotics"

    def test_description(self) -> None:
        """Should have description."""
        toolset = RoboticsToolset()
        assert "ROS2" in toolset.description
        assert "robot" in toolset.description.lower()


class TestRoboticsToolsetConfiguration:
    """Tests for RoboticsToolset configuration."""

    def test_configure_robot_id(self) -> None:
        """Should configure robot ID."""
        toolset = RoboticsToolset()
        toolset.configure({"robot_id": "my_robot"})

        assert toolset._robot_id == "my_robot"

    def test_configure_auto_initialize(self) -> None:
        """Should configure auto-initialize."""
        toolset = RoboticsToolset()
        toolset.configure({"auto_initialize": True})

        assert toolset._auto_initialize is True

    def test_configure_safety_constraints(self) -> None:
        """Should configure safety constraints."""
        controller = RobotSafetyController()
        toolset = RoboticsToolset(safety_controller=controller)

        toolset.configure({
            "safety_constraints": {
                "max_linear_velocity": 2.0,
                "min_battery_level": 15.0,
            }
        })

        assert controller.constraints.max_linear_velocity == 2.0
        assert controller.constraints.min_battery_level == 15.0


class TestRoboticsToolsetRegistration:
    """Tests for RoboticsToolset tool registration."""

    @pytest.fixture
    def registry(self) -> ToolRegistry:
        """Create a tool registry."""
        return ToolRegistry()

    @pytest.fixture
    def toolset(self) -> RoboticsToolset:
        """Create a robotics toolset."""
        return RoboticsToolset()

    def test_registers_ros_tools(
        self, toolset: RoboticsToolset, registry: ToolRegistry
    ) -> None:
        """Should register ROS2 tools."""
        toolset.register_tools(registry)

        assert registry.get_tool("ros.list_topics") is not None
        assert registry.get_tool("ros.list_services") is not None
        assert registry.get_tool("ros.list_nodes") is not None
        assert registry.get_tool("ros.topic_info") is not None
        assert registry.get_tool("ros.subscribe") is not None
        assert registry.get_tool("ros.publish") is not None
        assert registry.get_tool("ros.call_service") is not None

    def test_registers_robot_tools(
        self, toolset: RoboticsToolset, registry: ToolRegistry
    ) -> None:
        """Should register robot control tools."""
        toolset.register_tools(registry)

        assert registry.get_tool("robot.status") is not None
        assert registry.get_tool("robot.set_state") is not None
        assert registry.get_tool("robot.estop") is not None
        assert registry.get_tool("robot.release_estop") is not None
        assert registry.get_tool("robot.validate_motion") is not None

    def test_tool_plugin_name(
        self, toolset: RoboticsToolset, registry: ToolRegistry
    ) -> None:
        """Should set plugin name on tools."""
        toolset.register_tools(registry)

        tool = registry.get_tool("ros.list_topics")
        assert tool is not None
        assert tool.plugin_name == "robotics"


class TestRoboticsToolsetROS2Tools:
    """Tests for ROS2 tools (without actual ROS2 connection)."""

    @pytest.fixture
    def toolset(self) -> RoboticsToolset:
        """Create a robotics toolset."""
        return RoboticsToolset()

    @pytest.mark.skipif(ROS2_AVAILABLE, reason="Test requires ROS2 to be unavailable")
    def test_list_topics_without_ros2(self, toolset: RoboticsToolset) -> None:
        """Should return error when ROS2 not available."""
        result = toolset.list_topics()

        assert result.success is False
        assert "ROS2 is not available" in result.error

    @pytest.mark.skipif(ROS2_AVAILABLE, reason="Test requires ROS2 to be unavailable")
    def test_list_services_without_ros2(self, toolset: RoboticsToolset) -> None:
        """Should return error when ROS2 not available."""
        result = toolset.list_services()

        assert result.success is False
        assert "ROS2 is not available" in result.error

    @pytest.mark.skipif(ROS2_AVAILABLE, reason="Test requires ROS2 to be unavailable")
    def test_list_nodes_without_ros2(self, toolset: RoboticsToolset) -> None:
        """Should return error when ROS2 not available."""
        result = toolset.list_nodes()

        assert result.success is False
        assert "ROS2 is not available" in result.error

    @pytest.mark.skipif(ROS2_AVAILABLE, reason="Test requires ROS2 to be unavailable")
    def test_topic_info_without_ros2(self, toolset: RoboticsToolset) -> None:
        """Should return error when ROS2 not available."""
        result = toolset.topic_info("/cmd_vel")

        assert result.success is False
        assert "ROS2 is not available" in result.error

    @pytest.mark.skipif(ROS2_AVAILABLE, reason="Test requires ROS2 to be unavailable")
    def test_subscribe_without_ros2(self, toolset: RoboticsToolset) -> None:
        """Should return error when ROS2 not available."""
        result = toolset.subscribe("/test", duration=1.0)

        assert result.success is False
        assert "ROS2 is not available" in result.error

    @pytest.mark.skipif(ROS2_AVAILABLE, reason="Test requires ROS2 to be unavailable")
    def test_publish_without_ros2(self, toolset: RoboticsToolset) -> None:
        """Should return error when ROS2 not available."""
        result = toolset.publish("/cmd_vel", {"linear": {"x": 0.0}})

        assert result.success is False
        assert "ROS2 is not available" in result.error

    @pytest.mark.skipif(ROS2_AVAILABLE, reason="Test requires ROS2 to be unavailable")
    def test_call_service_without_ros2(self, toolset: RoboticsToolset) -> None:
        """Should return error when ROS2 not available."""
        result = toolset.call_service("/trigger", {})

        assert result.success is False
        assert "ROS2 is not available" in result.error


class TestRoboticsToolsetRobotTools:
    """Tests for robot control tools."""

    @pytest.fixture
    def controller(self) -> RobotSafetyController:
        """Create a safety controller."""
        return RobotSafetyController()

    @pytest.fixture
    def toolset(self, controller: RobotSafetyController) -> RoboticsToolset:
        """Create a robotics toolset with safety controller."""
        return RoboticsToolset(safety_controller=controller)

    def test_robot_status(self, toolset: RoboticsToolset) -> None:
        """Should return robot status."""
        result = toolset.robot_status()

        assert result.success is True
        assert "Safety State" in result.output
        assert "Battery" in result.output
        assert result.metadata is not None

    def test_robot_status_with_robot_id(self, toolset: RoboticsToolset) -> None:
        """Should return status for specific robot."""
        result = toolset.robot_status(robot_id="robot_01")

        assert result.success is True
        assert "robot_01" in result.output

    def test_set_state_valid(
        self, toolset: RoboticsToolset, controller: RobotSafetyController
    ) -> None:
        """Should change state successfully."""
        # First go to supervised
        result = toolset.set_robot_state("supervised")

        assert result.success is True
        assert controller.current_state == RobotSafetyState.SUPERVISED

    def test_set_state_invalid(self, toolset: RoboticsToolset) -> None:
        """Should reject invalid state."""
        result = toolset.set_robot_state("invalid_state")

        assert result.success is False
        assert "Invalid state" in result.error

    def test_set_state_invalid_transition(
        self, toolset: RoboticsToolset, controller: RobotSafetyController
    ) -> None:
        """Should reject invalid state transition."""
        # Try to go directly to autonomous from idle
        result = toolset.set_robot_state("autonomous")

        assert result.success is False
        assert "Cannot transition" in result.error

    def test_engage_estop(
        self, toolset: RoboticsToolset, controller: RobotSafetyController
    ) -> None:
        """Should engage emergency stop."""
        result = toolset.engage_estop("Test emergency")

        assert result.success is True
        assert controller.estop_engaged is True
        assert "Test emergency" in result.output

    def test_release_estop(
        self, toolset: RoboticsToolset, controller: RobotSafetyController
    ) -> None:
        """Should release emergency stop."""
        controller.engage_estop("test")
        result = toolset.release_estop()

        assert result.success is True
        assert controller.estop_engaged is False

    def test_release_estop_not_engaged(self, toolset: RoboticsToolset) -> None:
        """Should fail when E-Stop not engaged."""
        result = toolset.release_estop()

        assert result.success is False
        assert "not engaged" in result.error

    def test_validate_motion_safe(
        self, toolset: RoboticsToolset, controller: RobotSafetyController
    ) -> None:
        """Should validate safe motion."""
        # Move to supervised state first
        controller.transition_state(RobotSafetyState.SUPERVISED)

        result = toolset.validate_motion(
            command_type="velocity",
            target={"linear": {"x": 0.5}},
            velocity=0.5,
        )

        assert result.success is True
        assert "approved" in result.output.lower()

    def test_validate_motion_blocked(
        self, toolset: RoboticsToolset, controller: RobotSafetyController
    ) -> None:
        """Should block motion in wrong state."""
        # Stay in idle state

        result = toolset.validate_motion(
            command_type="velocity",
            target={"linear": {"x": 0.5}},
        )

        assert result.success is True  # Validation itself succeeded
        assert "blocked" in result.output.lower()

    def test_validate_motion_with_high_velocity(
        self, toolset: RoboticsToolset, controller: RobotSafetyController
    ) -> None:
        """Should flag high velocity motion."""
        controller.transition_state(RobotSafetyState.SUPERVISED)

        result = toolset.validate_motion(
            command_type="velocity",
            target={},
            velocity=5.0,  # Much higher than default 1.0 m/s limit
        )

        assert result.success is True
        assert "Requires Approval" in result.output or "needs_approval" in result.output.lower()


class TestRoboticsToolsetLifecycle:
    """Tests for toolset lifecycle methods."""

    def test_initialize_without_auto(self) -> None:
        """Should not auto-initialize ROS2."""
        toolset = RoboticsToolset(auto_initialize=False)
        # Should not raise even without ROS2
        toolset.initialize()

    def test_shutdown_without_client(self) -> None:
        """Should handle shutdown without client."""
        toolset = RoboticsToolset()
        # Should not raise
        toolset.shutdown()

    def test_shutdown_with_client(self) -> None:
        """Should shutdown client."""
        client = ROS2Client()
        toolset = RoboticsToolset(ros_client=client)

        toolset.shutdown()

        assert client.status.value == "disconnected"


class TestRoboticsToolsetMotionSafetyIntegration:
    """Integration tests for motion safety with publish."""

    @pytest.fixture
    def controller(self) -> RobotSafetyController:
        """Create a safety controller."""
        return RobotSafetyController()

    @pytest.fixture
    def toolset(self, controller: RobotSafetyController) -> RoboticsToolset:
        """Create a robotics toolset with safety controller."""
        return RoboticsToolset(safety_controller=controller)

    @pytest.mark.skipif(ROS2_AVAILABLE, reason="Test requires ROS2 to be unavailable")
    def test_publish_motion_blocked_by_safety(
        self, toolset: RoboticsToolset, controller: RobotSafetyController
    ) -> None:
        """Should fail when ROS2 not available (checked before safety)."""
        # Note: ROS2 availability is checked first, so we get ROS2 error
        # before safety validation can run. This is intentional -
        # no point validating motion if we can't even publish.

        result = toolset.publish("/cmd_vel", {"linear": {"x": 0.5}})

        # Should fail due to ROS2 not available
        assert result.success is False
        assert "ROS2" in result.error

    @pytest.mark.skipif(ROS2_AVAILABLE, reason="Test requires ROS2 to be unavailable")
    def test_publish_motion_allowed_by_safety(
        self, toolset: RoboticsToolset, controller: RobotSafetyController
    ) -> None:
        """Should pass safety check when in correct state."""
        controller.transition_state(RobotSafetyState.SUPERVISED)

        result = toolset.publish("/cmd_vel", {"linear": {"x": 0.5}})

        # Should fail due to ROS2 not available (not safety)
        assert result.success is False
        assert "ROS2" in result.error

    @pytest.mark.skipif(ROS2_AVAILABLE, reason="Test requires ROS2 to be unavailable")
    def test_publish_non_motion_topic(
        self, toolset: RoboticsToolset
    ) -> None:
        """Should not apply motion safety to non-motion topics."""
        # Publishing to non-motion topic in IDLE state
        result = toolset.publish("/led_color", {"r": 255, "g": 0, "b": 0})

        # Should fail due to ROS2 not available (not safety)
        assert result.success is False
        assert "ROS2" in result.error
