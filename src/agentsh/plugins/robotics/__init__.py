"""Robotics plugins for ROS2 integration.

This module provides tools and safety controls for interacting
with robots via ROS2. Features include:

- ROS2 topic/service interaction
- Robot safety state management
- Motion validation and approval
- Emergency stop control

Requirements:
- rclpy (ROS2 Python client) for full functionality
- Without rclpy, only safety features are available

Example:
    from agentsh.plugins.robotics import RoboticsToolset, ROS2Client

    # Create toolset
    toolset = RoboticsToolset(auto_initialize=True)

    # Register with tool registry
    toolset.register_tools(registry)

    # Or use ROS2 client directly
    client = ROS2Client()
    client.initialize()
    topics = client.list_topics()
"""

from agentsh.plugins.robotics.ros_interface import (
    ActionInfo,
    ROS2_AVAILABLE,
    ROS2Client,
    ROSConnectionStatus,
    ROSMessage,
    ServiceInfo,
    ServiceResponse,
    TopicInfo,
    get_ros2_client,
    set_ros2_client,
)
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
from agentsh.plugins.robotics.robotics_toolset import RoboticsToolset

__all__ = [
    # ROS2 Interface
    "ROS2_AVAILABLE",
    "ROS2Client",
    "ROSConnectionStatus",
    "ROSMessage",
    "TopicInfo",
    "ServiceInfo",
    "ActionInfo",
    "ServiceResponse",
    "get_ros2_client",
    "set_ros2_client",
    # Safety
    "RobotSafetyState",
    "MotionRiskLevel",
    "ValidationResult",
    "SafetyConstraints",
    "RobotStatus",
    "MotionCommand",
    "MotionValidation",
    "RobotSafetyController",
    "get_safety_controller",
    "set_safety_controller",
    # Toolset
    "RoboticsToolset",
]
