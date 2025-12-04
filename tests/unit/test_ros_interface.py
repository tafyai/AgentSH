"""Tests for ROS2 interface module."""

import pytest

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


class TestTopicInfo:
    """Tests for TopicInfo dataclass."""

    def test_create_topic_info(self) -> None:
        """Should create topic info with all fields."""
        topic = TopicInfo(
            name="/cmd_vel",
            msg_type="geometry_msgs/msg/Twist",
            publishers=1,
            subscribers=2,
        )

        assert topic.name == "/cmd_vel"
        assert topic.msg_type == "geometry_msgs/msg/Twist"
        assert topic.publishers == 1
        assert topic.subscribers == 2

    def test_topic_info_defaults(self) -> None:
        """Should have sensible defaults."""
        topic = TopicInfo(name="/test", msg_type="std_msgs/msg/String")

        assert topic.publishers == 0
        assert topic.subscribers == 0
        assert topic.qos_profile is None

    def test_topic_info_to_dict(self) -> None:
        """Should convert to dictionary."""
        topic = TopicInfo(
            name="/scan",
            msg_type="sensor_msgs/msg/LaserScan",
            publishers=1,
            subscribers=3,
        )

        data = topic.to_dict()

        assert data["name"] == "/scan"
        assert data["msg_type"] == "sensor_msgs/msg/LaserScan"
        assert data["publishers"] == 1
        assert data["subscribers"] == 3


class TestServiceInfo:
    """Tests for ServiceInfo dataclass."""

    def test_create_service_info(self) -> None:
        """Should create service info."""
        service = ServiceInfo(
            name="/set_parameters",
            srv_type="rcl_interfaces/srv/SetParameters",
        )

        assert service.name == "/set_parameters"
        assert service.srv_type == "rcl_interfaces/srv/SetParameters"

    def test_service_info_to_dict(self) -> None:
        """Should convert to dictionary."""
        service = ServiceInfo(name="/trigger", srv_type="std_srvs/srv/Trigger")

        data = service.to_dict()

        assert data["name"] == "/trigger"
        assert data["srv_type"] == "std_srvs/srv/Trigger"


class TestActionInfo:
    """Tests for ActionInfo dataclass."""

    def test_create_action_info(self) -> None:
        """Should create action info."""
        action = ActionInfo(
            name="/navigate_to_pose",
            action_type="nav2_msgs/action/NavigateToPose",
        )

        assert action.name == "/navigate_to_pose"
        assert action.action_type == "nav2_msgs/action/NavigateToPose"

    def test_action_info_to_dict(self) -> None:
        """Should convert to dictionary."""
        action = ActionInfo(name="/dock", action_type="DockRobot")

        data = action.to_dict()

        assert data["name"] == "/dock"
        assert data["action_type"] == "DockRobot"


class TestROSMessage:
    """Tests for ROSMessage dataclass."""

    def test_create_ros_message(self) -> None:
        """Should create ROS message with data."""
        msg = ROSMessage(
            topic="/odom",
            msg_type="nav_msgs/msg/Odometry",
            data={"pose": {"position": {"x": 1.0, "y": 2.0}}},
        )

        assert msg.topic == "/odom"
        assert msg.msg_type == "nav_msgs/msg/Odometry"
        assert msg.data["pose"]["position"]["x"] == 1.0

    def test_ros_message_timestamp(self) -> None:
        """Should have automatic timestamp."""
        msg = ROSMessage(topic="/test", msg_type="String", data={})

        assert msg.timestamp is not None

    def test_ros_message_to_dict(self) -> None:
        """Should convert to dictionary with ISO timestamp."""
        msg = ROSMessage(topic="/test", msg_type="String", data={"value": 42})

        data = msg.to_dict()

        assert data["topic"] == "/test"
        assert data["data"]["value"] == 42
        assert "timestamp" in data


class TestServiceResponse:
    """Tests for ServiceResponse dataclass."""

    def test_successful_response(self) -> None:
        """Should create successful response."""
        response = ServiceResponse(
            success=True,
            response={"result": "ok"},
            duration_ms=15.5,
        )

        assert response.success is True
        assert response.response == {"result": "ok"}
        assert response.error is None

    def test_failed_response(self) -> None:
        """Should create failed response."""
        response = ServiceResponse(
            success=False,
            error="Service timeout",
            duration_ms=5000.0,
        )

        assert response.success is False
        assert response.error == "Service timeout"

    def test_response_to_dict(self) -> None:
        """Should convert to dictionary."""
        response = ServiceResponse(success=True, duration_ms=10.0)

        data = response.to_dict()

        assert data["success"] is True
        assert data["duration_ms"] == 10.0


class TestROSConnectionStatus:
    """Tests for ROSConnectionStatus enum."""

    def test_all_statuses(self) -> None:
        """Should have all expected statuses."""
        assert ROSConnectionStatus.DISCONNECTED == "disconnected"
        assert ROSConnectionStatus.CONNECTING == "connecting"
        assert ROSConnectionStatus.CONNECTED == "connected"
        assert ROSConnectionStatus.ERROR == "error"


class TestROS2Client:
    """Tests for ROS2Client class."""

    def test_create_client(self) -> None:
        """Should create client with defaults."""
        client = ROS2Client()

        assert client.node_name == "agentsh_ros_client"
        assert client.namespace == ""
        assert client.status == ROSConnectionStatus.DISCONNECTED
        assert client.is_connected is False

    def test_create_client_with_name(self) -> None:
        """Should create client with custom name."""
        client = ROS2Client(node_name="my_robot", namespace="/robot1")

        assert client.node_name == "my_robot"
        assert client.namespace == "/robot1"

    def test_is_available(self) -> None:
        """Should report ROS2 availability."""
        client = ROS2Client()
        # This will be False in test environment without rclpy
        assert client.is_available == ROS2_AVAILABLE

    @pytest.mark.skipif(ROS2_AVAILABLE, reason="Test requires ROS2 to be unavailable")
    def test_initialize_without_ros2(self) -> None:
        """Should raise ImportError when ROS2 is not available."""
        client = ROS2Client()

        with pytest.raises(ImportError, match="rclpy is not installed"):
            client.initialize()

    @pytest.mark.skipif(ROS2_AVAILABLE, reason="Test requires ROS2 to be unavailable")
    def test_list_topics_not_connected(self) -> None:
        """Should raise when not connected."""
        client = ROS2Client()

        with pytest.raises(RuntimeError, match="Not connected"):
            client.list_topics()

    @pytest.mark.skipif(ROS2_AVAILABLE, reason="Test requires ROS2 to be unavailable")
    def test_list_services_not_connected(self) -> None:
        """Should raise when not connected."""
        client = ROS2Client()

        with pytest.raises(RuntimeError, match="Not connected"):
            client.list_services()

    @pytest.mark.skipif(ROS2_AVAILABLE, reason="Test requires ROS2 to be unavailable")
    def test_list_nodes_not_connected(self) -> None:
        """Should raise when not connected."""
        client = ROS2Client()

        with pytest.raises(RuntimeError, match="Not connected"):
            client.list_nodes()

    @pytest.mark.skipif(ROS2_AVAILABLE, reason="Test requires ROS2 to be unavailable")
    def test_subscribe_not_connected(self) -> None:
        """Should raise when not connected."""
        client = ROS2Client()

        with pytest.raises(RuntimeError, match="Not connected"):
            client.subscribe("/test", duration=1.0)

    @pytest.mark.skipif(ROS2_AVAILABLE, reason="Test requires ROS2 to be unavailable")
    def test_publish_not_connected(self) -> None:
        """Should raise when not connected."""
        client = ROS2Client()

        with pytest.raises(RuntimeError, match="Not connected"):
            client.publish("/cmd_vel", {"linear": {"x": 0.0}})

    @pytest.mark.skipif(ROS2_AVAILABLE, reason="Test requires ROS2 to be unavailable")
    def test_call_service_not_connected(self) -> None:
        """Should raise when not connected."""
        client = ROS2Client()

        with pytest.raises(RuntimeError, match="Not connected"):
            client.call_service("/trigger", {})

    def test_shutdown_when_not_connected(self) -> None:
        """Should handle shutdown when not connected."""
        client = ROS2Client()
        # Should not raise
        client.shutdown()
        assert client.status == ROSConnectionStatus.DISCONNECTED


class TestGlobalROS2Client:
    """Tests for global ROS2 client functions."""

    def teardown_method(self) -> None:
        """Reset global client after each test."""
        set_ros2_client(None)

    def test_get_global_client(self) -> None:
        """Should create and return global client."""
        client = get_ros2_client()
        assert isinstance(client, ROS2Client)

        # Should return same instance
        assert get_ros2_client() is client

    def test_set_global_client(self) -> None:
        """Should set custom global client."""
        custom = ROS2Client(node_name="custom_client")
        set_ros2_client(custom)

        assert get_ros2_client() is custom
        assert get_ros2_client().node_name == "custom_client"
