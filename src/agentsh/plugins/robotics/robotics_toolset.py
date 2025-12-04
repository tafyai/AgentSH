"""Robotics toolset for AgentSH.

Provides tools for interacting with robots via ROS2,
including topic/service interaction, motion control,
and robot status monitoring.
"""

from typing import TYPE_CHECKING, Any, Optional

from agentsh.plugins.base import Toolset
from agentsh.plugins.robotics.ros_interface import (
    ROS2Client,
    ROS2_AVAILABLE,
    ROSConnectionStatus,
    get_ros2_client,
)
from agentsh.plugins.robotics.safety import (
    MotionCommand,
    MotionRiskLevel,
    RobotSafetyController,
    RobotSafetyState,
    RobotStatus,
    SafetyConstraints,
    ValidationResult,
    get_safety_controller,
)
from agentsh.tools.base import RiskLevel, ToolResult
from agentsh.telemetry.logger import get_logger

if TYPE_CHECKING:
    from agentsh.tools.registry import ToolRegistry

logger = get_logger(__name__)


class RoboticsToolset(Toolset):
    """Provides ROS2 and robot control tools.

    Tools:
    - ros.list_topics: List available ROS2 topics
    - ros.list_services: List available ROS2 services
    - ros.list_nodes: List ROS2 nodes
    - ros.topic_info: Get information about a topic
    - ros.subscribe: Subscribe to a topic and get messages
    - ros.publish: Publish a message to a topic
    - ros.call_service: Call a ROS2 service
    - robot.status: Get robot status
    - robot.set_state: Set robot safety state
    - robot.estop: Engage emergency stop
    - robot.release_estop: Release emergency stop
    - robot.validate_motion: Validate a motion command
    """

    def __init__(
        self,
        ros_client: Optional[ROS2Client] = None,
        safety_controller: Optional[RobotSafetyController] = None,
        auto_initialize: bool = False,
    ) -> None:
        """Initialize robotics toolset.

        Args:
            ros_client: ROS2 client instance (uses global if not provided)
            safety_controller: Safety controller (uses global if not provided)
            auto_initialize: Whether to auto-initialize ROS2 on first use
        """
        self._ros_client = ros_client
        self._safety_controller = safety_controller
        self._auto_initialize = auto_initialize
        self._robot_id = "default_robot"

    @property
    def name(self) -> str:
        return "robotics"

    @property
    def description(self) -> str:
        return "Interact with robots via ROS2 and control robot operations safely"

    @property
    def ros_client(self) -> ROS2Client:
        """Get ROS2 client."""
        return self._ros_client or get_ros2_client()

    @property
    def safety_controller(self) -> RobotSafetyController:
        """Get safety controller."""
        return self._safety_controller or get_safety_controller()

    def configure(self, config: dict[str, Any]) -> None:
        """Configure the toolset.

        Args:
            config: Configuration dictionary with keys:
                - robot_id: Robot identifier
                - auto_initialize: Whether to auto-init ROS2
                - safety_constraints: Safety constraint settings
        """
        self._robot_id = config.get("robot_id", "default_robot")
        self._auto_initialize = config.get("auto_initialize", False)

        # Configure safety constraints if provided
        if "safety_constraints" in config:
            constraints = SafetyConstraints.from_dict(config["safety_constraints"])
            self.safety_controller.set_constraints(constraints)

        logger.debug("Robotics toolset configured", robot_id=self._robot_id)

    def initialize(self) -> None:
        """Initialize the toolset."""
        if self._auto_initialize and ROS2_AVAILABLE:
            try:
                self.ros_client.initialize()
            except Exception as e:
                logger.warning("Failed to auto-initialize ROS2", error=str(e))

    def shutdown(self) -> None:
        """Shutdown the toolset."""
        if self._ros_client is not None:
            self._ros_client.shutdown()

    def register_tools(self, registry: "ToolRegistry") -> None:
        """Register robotics tools."""
        # ROS2 introspection tools
        registry.register_tool(
            name="ros.list_topics",
            handler=self.list_topics,
            description="List all available ROS2 topics. Returns topic names, message types, and publisher/subscriber counts.",
            parameters={
                "type": "object",
                "properties": {},
            },
            risk_level=RiskLevel.SAFE,
            plugin_name=self.name,
        )

        registry.register_tool(
            name="ros.list_services",
            handler=self.list_services,
            description="List all available ROS2 services.",
            parameters={
                "type": "object",
                "properties": {},
            },
            risk_level=RiskLevel.SAFE,
            plugin_name=self.name,
        )

        registry.register_tool(
            name="ros.list_nodes",
            handler=self.list_nodes,
            description="List all active ROS2 nodes.",
            parameters={
                "type": "object",
                "properties": {},
            },
            risk_level=RiskLevel.SAFE,
            plugin_name=self.name,
        )

        registry.register_tool(
            name="ros.topic_info",
            handler=self.topic_info,
            description="Get detailed information about a specific ROS2 topic.",
            parameters={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic name (e.g., '/cmd_vel')",
                    },
                },
                "required": ["topic"],
            },
            risk_level=RiskLevel.SAFE,
            plugin_name=self.name,
        )

        registry.register_tool(
            name="ros.subscribe",
            handler=self.subscribe,
            description="Subscribe to a ROS2 topic and collect messages for a duration.",
            parameters={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic name to subscribe to",
                    },
                    "duration": {
                        "type": "number",
                        "description": "Duration in seconds to collect messages",
                        "default": 5.0,
                    },
                    "max_messages": {
                        "type": "integer",
                        "description": "Maximum number of messages to collect",
                        "default": 10,
                    },
                },
                "required": ["topic"],
            },
            risk_level=RiskLevel.SAFE,
            plugin_name=self.name,
        )

        registry.register_tool(
            name="ros.publish",
            handler=self.publish,
            description="Publish a message to a ROS2 topic. Requires safety validation for motion topics.",
            parameters={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic name to publish to",
                    },
                    "message": {
                        "type": "object",
                        "description": "Message data as JSON object",
                    },
                },
                "required": ["topic", "message"],
            },
            risk_level=RiskLevel.MEDIUM,
            requires_confirmation=True,
            plugin_name=self.name,
        )

        registry.register_tool(
            name="ros.call_service",
            handler=self.call_service,
            description="Call a ROS2 service with the given request.",
            parameters={
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service name",
                    },
                    "request": {
                        "type": "object",
                        "description": "Service request data",
                    },
                    "timeout": {
                        "type": "number",
                        "description": "Timeout in seconds",
                        "default": 5.0,
                    },
                },
                "required": ["service", "request"],
            },
            risk_level=RiskLevel.MEDIUM,
            plugin_name=self.name,
        )

        # Robot status and control tools
        registry.register_tool(
            name="robot.status",
            handler=self.robot_status,
            description="Get the current status of the robot including position, battery, and safety state.",
            parameters={
                "type": "object",
                "properties": {
                    "robot_id": {
                        "type": "string",
                        "description": "Robot identifier",
                    },
                },
            },
            risk_level=RiskLevel.SAFE,
            plugin_name=self.name,
        )

        registry.register_tool(
            name="robot.set_state",
            handler=self.set_robot_state,
            description="Set the robot's safety state. Valid states: idle, supervised, autonomous, maintenance.",
            parameters={
                "type": "object",
                "properties": {
                    "state": {
                        "type": "string",
                        "description": "Target safety state",
                        "enum": ["idle", "supervised", "autonomous", "maintenance"],
                    },
                },
                "required": ["state"],
            },
            risk_level=RiskLevel.HIGH,
            requires_confirmation=True,
            plugin_name=self.name,
        )

        registry.register_tool(
            name="robot.estop",
            handler=self.engage_estop,
            description="Engage the robot's emergency stop. Immediately stops all motion.",
            parameters={
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Reason for emergency stop",
                    },
                },
            },
            risk_level=RiskLevel.SAFE,  # E-stop is always safe to engage
            plugin_name=self.name,
        )

        registry.register_tool(
            name="robot.release_estop",
            handler=self.release_estop,
            description="Release the robot's emergency stop. Robot will return to idle state.",
            parameters={
                "type": "object",
                "properties": {},
            },
            risk_level=RiskLevel.HIGH,
            requires_confirmation=True,
            plugin_name=self.name,
        )

        registry.register_tool(
            name="robot.validate_motion",
            handler=self.validate_motion,
            description="Validate a motion command against safety constraints without executing it.",
            parameters={
                "type": "object",
                "properties": {
                    "command_type": {
                        "type": "string",
                        "description": "Type of motion (velocity, position, trajectory)",
                    },
                    "target": {
                        "type": "object",
                        "description": "Target for the motion",
                    },
                    "velocity": {
                        "type": "number",
                        "description": "Commanded velocity",
                    },
                    "acceleration": {
                        "type": "number",
                        "description": "Commanded acceleration",
                    },
                },
                "required": ["command_type", "target"],
            },
            risk_level=RiskLevel.SAFE,
            plugin_name=self.name,
        )

    # ROS2 tool implementations

    def list_topics(self) -> ToolResult:
        """List all available ROS2 topics."""
        if not ROS2_AVAILABLE:
            return ToolResult(
                success=False,
                error="ROS2 is not available. Install rclpy to use robotics features.",
            )

        try:
            self._ensure_ros_connected()
            topics = self.ros_client.list_topics()

            output = "ROS2 Topics:\n"
            output += "-" * 60 + "\n"
            for topic in topics:
                output += f"  {topic.name}\n"
                output += f"    Type: {topic.msg_type}\n"
                output += f"    Publishers: {topic.publishers}, Subscribers: {topic.subscribers}\n"

            return ToolResult(
                success=True,
                output=output,
                metadata={"topics": [t.to_dict() for t in topics]},
            )

        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def list_services(self) -> ToolResult:
        """List all available ROS2 services."""
        if not ROS2_AVAILABLE:
            return ToolResult(
                success=False,
                error="ROS2 is not available. Install rclpy to use robotics features.",
            )

        try:
            self._ensure_ros_connected()
            services = self.ros_client.list_services()

            output = "ROS2 Services:\n"
            output += "-" * 60 + "\n"
            for service in services:
                output += f"  {service.name}\n"
                output += f"    Type: {service.srv_type}\n"

            return ToolResult(
                success=True,
                output=output,
                metadata={"services": [s.to_dict() for s in services]},
            )

        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def list_nodes(self) -> ToolResult:
        """List all active ROS2 nodes."""
        if not ROS2_AVAILABLE:
            return ToolResult(
                success=False,
                error="ROS2 is not available. Install rclpy to use robotics features.",
            )

        try:
            self._ensure_ros_connected()
            nodes = self.ros_client.list_nodes()

            output = "ROS2 Nodes:\n"
            output += "-" * 60 + "\n"
            for node in nodes:
                output += f"  {node}\n"

            return ToolResult(
                success=True,
                output=output,
                metadata={"nodes": nodes},
            )

        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def topic_info(self, topic: str) -> ToolResult:
        """Get information about a specific topic."""
        if not ROS2_AVAILABLE:
            return ToolResult(
                success=False,
                error="ROS2 is not available. Install rclpy to use robotics features.",
            )

        try:
            self._ensure_ros_connected()
            info = self.ros_client.get_topic_info(topic)

            if info is None:
                return ToolResult(
                    success=False,
                    error=f"Topic '{topic}' not found",
                )

            output = f"Topic: {info.name}\n"
            output += f"Type: {info.msg_type}\n"
            output += f"Publishers: {info.publishers}\n"
            output += f"Subscribers: {info.subscribers}\n"

            return ToolResult(
                success=True,
                output=output,
                metadata=info.to_dict(),
            )

        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def subscribe(
        self,
        topic: str,
        duration: float = 5.0,
        max_messages: int = 10,
    ) -> ToolResult:
        """Subscribe to a topic and collect messages."""
        if not ROS2_AVAILABLE:
            return ToolResult(
                success=False,
                error="ROS2 is not available. Install rclpy to use robotics features.",
            )

        try:
            self._ensure_ros_connected()
            messages = self.ros_client.subscribe(topic, duration, max_messages)

            if not messages:
                return ToolResult(
                    success=True,
                    output=f"No messages received from '{topic}' in {duration}s",
                    metadata={"messages": []},
                )

            output = f"Received {len(messages)} messages from '{topic}':\n"
            for i, msg in enumerate(messages, 1):
                output += f"\n[{i}] {msg.timestamp.isoformat()}\n"
                output += f"  {msg.data}\n"

            return ToolResult(
                success=True,
                output=output,
                metadata={"messages": [m.to_dict() for m in messages]},
            )

        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def publish(
        self,
        topic: str,
        message: dict[str, Any],
    ) -> ToolResult:
        """Publish a message to a topic."""
        if not ROS2_AVAILABLE:
            return ToolResult(
                success=False,
                error="ROS2 is not available. Install rclpy to use robotics features.",
            )

        # Check if this is a motion topic
        motion_topics = ["/cmd_vel", "/velocity", "/twist", "/joint"]
        is_motion = any(mt in topic.lower() for mt in motion_topics)

        if is_motion:
            # Validate motion through safety controller
            command = MotionCommand(
                command_type="publish",
                target=message,
            )
            status = self._get_robot_status()
            validation = self.safety_controller.validate_motion(command, status)

            if not validation.allowed:
                return ToolResult(
                    success=False,
                    error=f"Motion blocked: {', '.join(validation.reasons)}",
                    metadata=validation.to_dict(),
                )

        try:
            self._ensure_ros_connected()
            success = self.ros_client.publish(topic, message)

            if success:
                return ToolResult(
                    success=True,
                    output=f"Published to '{topic}'",
                )
            else:
                return ToolResult(
                    success=False,
                    error="Failed to publish message",
                )

        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def call_service(
        self,
        service: str,
        request: dict[str, Any],
        timeout: float = 5.0,
    ) -> ToolResult:
        """Call a ROS2 service."""
        if not ROS2_AVAILABLE:
            return ToolResult(
                success=False,
                error="ROS2 is not available. Install rclpy to use robotics features.",
            )

        try:
            self._ensure_ros_connected()
            response = self.ros_client.call_service(service, request, timeout)

            if response.success:
                return ToolResult(
                    success=True,
                    output=f"Service call succeeded in {response.duration_ms:.1f}ms",
                    metadata={"response": response.response},
                )
            else:
                return ToolResult(
                    success=False,
                    error=response.error or "Service call failed",
                )

        except Exception as e:
            return ToolResult(success=False, error=str(e))

    # Robot control tool implementations

    def robot_status(self, robot_id: Optional[str] = None) -> ToolResult:
        """Get robot status."""
        rid = robot_id or self._robot_id
        status = self._get_robot_status(rid)

        output = f"Robot Status: {rid}\n"
        output += "-" * 40 + "\n"
        output += f"Safety State: {status.safety_state.value}\n"
        output += f"Battery: {status.battery_level}%\n"
        output += f"E-Stop: {'ENGAGED' if status.estop_engaged else 'Released'}\n"
        if status.position:
            output += f"Position: {status.position}\n"
        if status.human_detected:
            output += f"Human Detected: Yes (distance: {status.human_distance}m)\n"
        if status.errors:
            output += f"Errors: {status.errors}\n"

        return ToolResult(
            success=True,
            output=output,
            metadata=status.to_dict(),
        )

    def set_robot_state(self, state: str) -> ToolResult:
        """Set robot safety state."""
        try:
            new_state = RobotSafetyState(state)
        except ValueError:
            return ToolResult(
                success=False,
                error=f"Invalid state '{state}'. Valid states: {[s.value for s in RobotSafetyState]}",
            )

        success = self.safety_controller.transition_state(new_state)

        if success:
            return ToolResult(
                success=True,
                output=f"Robot state changed to {new_state.value}",
            )
        else:
            return ToolResult(
                success=False,
                error=f"Cannot transition to {new_state.value} from current state",
            )

    def engage_estop(self, reason: str = "Manual E-Stop via AgentSH") -> ToolResult:
        """Engage emergency stop."""
        self.safety_controller.engage_estop(reason)

        return ToolResult(
            success=True,
            output=f"Emergency stop engaged: {reason}",
        )

    def release_estop(self) -> ToolResult:
        """Release emergency stop."""
        success = self.safety_controller.release_estop()

        if success:
            return ToolResult(
                success=True,
                output="Emergency stop released. Robot is now in IDLE state.",
            )
        else:
            return ToolResult(
                success=False,
                error="Emergency stop was not engaged",
            )

    def validate_motion(
        self,
        command_type: str,
        target: dict[str, Any],
        velocity: Optional[float] = None,
        acceleration: Optional[float] = None,
    ) -> ToolResult:
        """Validate a motion command."""
        command = MotionCommand(
            command_type=command_type,
            target=target,
            velocity=velocity,
            acceleration=acceleration,
        )

        status = self._get_robot_status()
        validation = self.safety_controller.validate_motion(command, status)

        output = f"Motion Validation Result\n"
        output += "-" * 40 + "\n"
        output += f"Result: {validation.result.value}\n"
        output += f"Risk Level: {validation.risk_level.value}\n"
        output += f"Allowed: {validation.allowed}\n"
        if validation.reasons:
            output += f"Reasons:\n"
            for reason in validation.reasons:
                output += f"  - {reason}\n"
        if validation.requires_approval:
            output += f"Requires Approval: Yes (timeout: {validation.approval_timeout}s)\n"

        return ToolResult(
            success=True,
            output=output,
            metadata=validation.to_dict(),
        )

    # Helper methods

    def _ensure_ros_connected(self) -> None:
        """Ensure ROS2 is connected."""
        if not self.ros_client.is_connected:
            if self._auto_initialize:
                self.ros_client.initialize()
            else:
                raise RuntimeError(
                    "Not connected to ROS2. Initialize with auto_initialize=True "
                    "or call ros_client.initialize() manually."
                )

    def _get_robot_status(self, robot_id: Optional[str] = None) -> RobotStatus:
        """Get current robot status.

        In a full implementation, this would query ROS2 topics
        for actual robot state.
        """
        rid = robot_id or self._robot_id

        # This is a placeholder - in reality, we'd read from ROS2 topics
        return RobotStatus(
            robot_id=rid,
            safety_state=self.safety_controller.current_state,
            battery_level=100.0,
            estop_engaged=self.safety_controller.estop_engaged,
        )
