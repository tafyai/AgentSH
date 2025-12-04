"""ROS2 interface for AgentSH robotics integration.

Provides a client interface for interacting with ROS2 topics,
services, and actions. Requires rclpy to be installed.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)

# Check for ROS2 availability
try:
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy

    ROS2_AVAILABLE = True
except ImportError:
    rclpy = None
    Node = object
    ROS2_AVAILABLE = False
    logger.debug("rclpy not available - ROS2 features disabled")


class ROSConnectionStatus(str, Enum):
    """ROS2 connection status."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class TopicInfo:
    """Information about a ROS2 topic.

    Attributes:
        name: Topic name (e.g., '/cmd_vel')
        msg_type: Message type (e.g., 'geometry_msgs/msg/Twist')
        publishers: Number of publishers
        subscribers: Number of subscribers
        qos_profile: Quality of service profile info
    """

    name: str
    msg_type: str
    publishers: int = 0
    subscribers: int = 0
    qos_profile: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "msg_type": self.msg_type,
            "publishers": self.publishers,
            "subscribers": self.subscribers,
            "qos_profile": self.qos_profile,
        }


@dataclass
class ServiceInfo:
    """Information about a ROS2 service.

    Attributes:
        name: Service name (e.g., '/set_parameters')
        srv_type: Service type (e.g., 'rcl_interfaces/srv/SetParameters')
    """

    name: str
    srv_type: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "srv_type": self.srv_type,
        }


@dataclass
class ActionInfo:
    """Information about a ROS2 action.

    Attributes:
        name: Action name
        action_type: Action type
    """

    name: str
    action_type: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "action_type": self.action_type,
        }


@dataclass
class ROSMessage:
    """A received ROS2 message.

    Attributes:
        topic: Topic the message was received on
        msg_type: Message type
        data: Message data as dictionary
        timestamp: When the message was received
    """

    topic: str
    msg_type: str
    data: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "topic": self.topic,
            "msg_type": self.msg_type,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ServiceResponse:
    """Response from a ROS2 service call.

    Attributes:
        success: Whether the call succeeded
        response: Response data
        error: Error message if failed
        duration_ms: Call duration in milliseconds
    """

    success: bool
    response: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "response": self.response,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }


class ROS2Client:
    """Client for interacting with ROS2.

    Provides methods to:
    - List and introspect topics, services, and actions
    - Subscribe to topics and collect messages
    - Publish messages to topics
    - Call services

    Example:
        client = ROS2Client("agentsh_client")
        client.initialize()

        # List topics
        topics = client.list_topics()

        # Subscribe and collect messages
        messages = client.subscribe("/scan", duration=5.0)

        # Publish a message
        client.publish("/cmd_vel", {"linear": {"x": 0.5}, "angular": {"z": 0.0}})

        client.shutdown()
    """

    def __init__(
        self,
        node_name: str = "agentsh_ros_client",
        namespace: str = "",
    ) -> None:
        """Initialize ROS2 client.

        Args:
            node_name: Name for the ROS2 node
            namespace: ROS2 namespace
        """
        self.node_name = node_name
        self.namespace = namespace
        self._node: Optional[Any] = None
        self._status = ROSConnectionStatus.DISCONNECTED
        self._subscriptions: dict[str, Any] = {}
        self._publishers: dict[str, Any] = {}
        self._message_buffers: dict[str, list[ROSMessage]] = {}
        self._executor: Optional[Any] = None
        self._spin_thread: Optional[Any] = None

        logger.debug(
            "ROS2Client created",
            node_name=node_name,
            ros2_available=ROS2_AVAILABLE,
        )

    @property
    def is_available(self) -> bool:
        """Check if ROS2 is available."""
        return ROS2_AVAILABLE

    @property
    def is_connected(self) -> bool:
        """Check if connected to ROS2."""
        return self._status == ROSConnectionStatus.CONNECTED

    @property
    def status(self) -> ROSConnectionStatus:
        """Get connection status."""
        return self._status

    def initialize(self) -> bool:
        """Initialize the ROS2 client and create node.

        Returns:
            True if initialization succeeded

        Raises:
            ImportError: If rclpy is not available
        """
        if not ROS2_AVAILABLE:
            raise ImportError(
                "rclpy is not installed. Install with: "
                "sudo apt install ros-<distro>-rclpy or pip install rclpy"
            )

        if self._node is not None:
            return True

        try:
            self._status = ROSConnectionStatus.CONNECTING

            # Initialize ROS2 if not already done
            if not rclpy.ok():
                rclpy.init()

            # Create node
            self._node = rclpy.create_node(
                self.node_name,
                namespace=self.namespace if self.namespace else None,
            )

            self._status = ROSConnectionStatus.CONNECTED
            logger.info("ROS2 client initialized", node_name=self.node_name)
            return True

        except Exception as e:
            self._status = ROSConnectionStatus.ERROR
            logger.error("Failed to initialize ROS2 client", error=str(e))
            raise

    def shutdown(self) -> None:
        """Shutdown the ROS2 client and cleanup resources."""
        if self._node is not None:
            try:
                # Destroy subscriptions
                for sub in self._subscriptions.values():
                    self._node.destroy_subscription(sub)
                self._subscriptions.clear()

                # Destroy publishers
                for pub in self._publishers.values():
                    self._node.destroy_publisher(pub)
                self._publishers.clear()

                # Destroy node
                self._node.destroy_node()
                self._node = None

                logger.info("ROS2 client shutdown")
            except Exception as e:
                logger.error("Error during ROS2 shutdown", error=str(e))

        self._status = ROSConnectionStatus.DISCONNECTED

    def list_topics(self) -> list[TopicInfo]:
        """List all available ROS2 topics.

        Returns:
            List of topic information

        Raises:
            RuntimeError: If not connected to ROS2
        """
        self._ensure_connected()

        topics = []
        topic_names_and_types = self._node.get_topic_names_and_types()

        for name, types in topic_names_and_types:
            # Get publisher/subscriber counts
            pub_info = self._node.get_publishers_info_by_topic(name)
            sub_info = self._node.get_subscriptions_info_by_topic(name)

            topics.append(
                TopicInfo(
                    name=name,
                    msg_type=types[0] if types else "unknown",
                    publishers=len(pub_info),
                    subscribers=len(sub_info),
                )
            )

        logger.debug("Listed topics", count=len(topics))
        return topics

    def list_services(self) -> list[ServiceInfo]:
        """List all available ROS2 services.

        Returns:
            List of service information

        Raises:
            RuntimeError: If not connected to ROS2
        """
        self._ensure_connected()

        services = []
        service_names_and_types = self._node.get_service_names_and_types()

        for name, types in service_names_and_types:
            services.append(
                ServiceInfo(
                    name=name,
                    srv_type=types[0] if types else "unknown",
                )
            )

        logger.debug("Listed services", count=len(services))
        return services

    def list_actions(self) -> list[ActionInfo]:
        """List all available ROS2 actions.

        Returns:
            List of action information

        Raises:
            RuntimeError: If not connected to ROS2
        """
        self._ensure_connected()

        # Actions are discovered from topics with specific patterns
        actions = []
        action_names = set()

        topic_names_and_types = self._node.get_topic_names_and_types()
        for name, _ in topic_names_and_types:
            # Action topics follow pattern: /<action_name>/_action/...
            if "/_action/" in name:
                parts = name.split("/_action/")
                if parts[0] and parts[0] not in action_names:
                    action_names.add(parts[0])
                    actions.append(
                        ActionInfo(
                            name=parts[0],
                            action_type="unknown",  # Would need more introspection
                        )
                    )

        logger.debug("Listed actions", count=len(actions))
        return actions

    def get_topic_info(self, topic: str) -> Optional[TopicInfo]:
        """Get detailed information about a specific topic.

        Args:
            topic: Topic name

        Returns:
            Topic information or None if not found
        """
        self._ensure_connected()

        topic_names_and_types = self._node.get_topic_names_and_types()

        for name, types in topic_names_and_types:
            if name == topic:
                pub_info = self._node.get_publishers_info_by_topic(name)
                sub_info = self._node.get_subscriptions_info_by_topic(name)

                return TopicInfo(
                    name=name,
                    msg_type=types[0] if types else "unknown",
                    publishers=len(pub_info),
                    subscribers=len(sub_info),
                )

        return None

    def subscribe(
        self,
        topic: str,
        duration: float = 5.0,
        max_messages: int = 100,
    ) -> list[ROSMessage]:
        """Subscribe to a topic and collect messages.

        Args:
            topic: Topic name to subscribe to
            duration: How long to collect messages (seconds)
            max_messages: Maximum messages to collect

        Returns:
            List of received messages

        Raises:
            RuntimeError: If not connected or topic doesn't exist
            ValueError: If topic doesn't exist
        """
        self._ensure_connected()

        # Check if topic exists
        topic_info = self.get_topic_info(topic)
        if not topic_info:
            raise ValueError(f"Topic '{topic}' not found")

        # This would require dynamic message type loading
        # For now, return a placeholder implementation
        logger.warning(
            "Dynamic message subscription not fully implemented",
            topic=topic,
        )

        # In a full implementation, we would:
        # 1. Import the message type dynamically
        # 2. Create a subscription
        # 3. Spin and collect messages for duration
        # 4. Return collected messages

        return []

    def publish(
        self,
        topic: str,
        message: dict[str, Any],
        msg_type: Optional[str] = None,
    ) -> bool:
        """Publish a message to a topic.

        Args:
            topic: Topic name to publish to
            message: Message data as dictionary
            msg_type: Message type (optional, will try to infer)

        Returns:
            True if published successfully

        Raises:
            RuntimeError: If not connected
            ValueError: If topic doesn't exist or message invalid
        """
        self._ensure_connected()

        # This would require dynamic message type loading
        logger.warning(
            "Dynamic message publishing not fully implemented",
            topic=topic,
        )

        # In a full implementation, we would:
        # 1. Get or infer message type
        # 2. Create publisher if not exists
        # 3. Convert dict to message
        # 4. Publish

        return False

    def call_service(
        self,
        service: str,
        request: dict[str, Any],
        timeout: float = 5.0,
    ) -> ServiceResponse:
        """Call a ROS2 service.

        Args:
            service: Service name
            request: Request data as dictionary
            timeout: Timeout in seconds

        Returns:
            ServiceResponse with result

        Raises:
            RuntimeError: If not connected
        """
        self._ensure_connected()

        start_time = time.perf_counter()

        # This would require dynamic service type loading
        logger.warning(
            "Dynamic service calling not fully implemented",
            service=service,
        )

        duration_ms = (time.perf_counter() - start_time) * 1000

        return ServiceResponse(
            success=False,
            error="Dynamic service calling not yet implemented",
            duration_ms=duration_ms,
        )

    def get_parameter(
        self,
        node_name: str,
        parameter_name: str,
    ) -> Optional[Any]:
        """Get a parameter from a node.

        Args:
            node_name: Name of the node
            parameter_name: Name of the parameter

        Returns:
            Parameter value or None if not found
        """
        self._ensure_connected()

        # Would call /node_name/get_parameters service
        logger.warning("Parameter getting not fully implemented")
        return None

    def set_parameter(
        self,
        node_name: str,
        parameter_name: str,
        value: Any,
    ) -> bool:
        """Set a parameter on a node.

        Args:
            node_name: Name of the node
            parameter_name: Name of the parameter
            value: Parameter value

        Returns:
            True if set successfully
        """
        self._ensure_connected()

        # Would call /node_name/set_parameters service
        logger.warning("Parameter setting not fully implemented")
        return False

    def list_nodes(self) -> list[str]:
        """List all ROS2 nodes.

        Returns:
            List of node names
        """
        self._ensure_connected()

        node_names_and_namespaces = self._node.get_node_names_and_namespaces()
        nodes = [
            f"{ns}{name}" if ns != "/" else name
            for name, ns in node_names_and_namespaces
        ]

        logger.debug("Listed nodes", count=len(nodes))
        return nodes

    def _ensure_connected(self) -> None:
        """Ensure client is connected to ROS2."""
        if not self.is_connected:
            raise RuntimeError(
                "Not connected to ROS2. Call initialize() first."
            )

    def spin_once(self, timeout_sec: float = 0.0) -> None:
        """Process ROS2 callbacks once.

        Args:
            timeout_sec: Timeout for waiting
        """
        if self._node is not None:
            rclpy.spin_once(self._node, timeout_sec=timeout_sec)


# Global ROS2 client instance
_ros2_client: Optional[ROS2Client] = None


def get_ros2_client() -> ROS2Client:
    """Get the global ROS2 client.

    Returns:
        Global ROS2Client singleton
    """
    global _ros2_client
    if _ros2_client is None:
        _ros2_client = ROS2Client()
    return _ros2_client


def set_ros2_client(client: Optional[ROS2Client]) -> None:
    """Set the global ROS2 client.

    Args:
        client: ROS2Client instance to use globally
    """
    global _ros2_client
    _ros2_client = client
