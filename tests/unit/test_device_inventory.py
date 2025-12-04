"""Tests for device inventory management."""

import tempfile
from pathlib import Path

import pytest

from agentsh.orchestrator.devices import (
    ConnectionConfig,
    ConnectionMethod,
    Device,
    DeviceInventory,
    DeviceStatus,
    DeviceType,
    SafetyConstraints,
    create_device,
    get_device_inventory,
    set_device_inventory,
)


class TestDeviceType:
    """Tests for DeviceType enum."""

    def test_device_type_values(self):
        """Should have expected device type values."""
        assert DeviceType.SERVER.value == "server"
        assert DeviceType.WORKSTATION.value == "workstation"
        assert DeviceType.EMBEDDED.value == "embedded"
        assert DeviceType.ROBOT.value == "robot"
        assert DeviceType.CONTAINER.value == "container"
        assert DeviceType.VM.value == "vm"


class TestDeviceStatus:
    """Tests for DeviceStatus enum."""

    def test_status_values(self):
        """Should have expected status values."""
        assert DeviceStatus.ONLINE.value == "online"
        assert DeviceStatus.OFFLINE.value == "offline"
        assert DeviceStatus.DEGRADED.value == "degraded"
        assert DeviceStatus.MAINTENANCE.value == "maintenance"
        assert DeviceStatus.UNKNOWN.value == "unknown"


class TestConnectionMethod:
    """Tests for ConnectionMethod enum."""

    def test_connection_values(self):
        """Should have expected connection method values."""
        assert ConnectionMethod.SSH.value == "ssh"
        assert ConnectionMethod.LOCAL.value == "local"
        assert ConnectionMethod.DOCKER.value == "docker"
        assert ConnectionMethod.KUBERNETES.value == "kubernetes"


class TestConnectionConfig:
    """Tests for ConnectionConfig dataclass."""

    def test_default_values(self):
        """Should have sensible defaults."""
        config = ConnectionConfig()
        assert config.method == ConnectionMethod.SSH
        assert config.credentials_profile is None
        assert config.port is None
        assert config.options == {}

    def test_custom_values(self):
        """Should accept custom values."""
        config = ConnectionConfig(
            method=ConnectionMethod.DOCKER,
            port=2222,
        )
        assert config.method == ConnectionMethod.DOCKER
        assert config.port == 2222

    def test_to_dict(self):
        """Should convert to dictionary."""
        config = ConnectionConfig(method=ConnectionMethod.SSH, port=22)
        d = config.to_dict()
        assert d["method"] == "ssh"
        assert d["port"] == 22

    def test_from_dict(self):
        """Should create from dictionary."""
        data = {"method": "docker", "port": 2375}
        config = ConnectionConfig.from_dict(data)
        assert config.method == ConnectionMethod.DOCKER
        assert config.port == 2375


class TestSafetyConstraints:
    """Tests for SafetyConstraints dataclass."""

    def test_default_values(self):
        """Should have safe defaults."""
        constraints = SafetyConstraints()
        assert constraints.max_concurrent_commands == 5
        assert constraints.require_approval_for == ["HIGH", "CRITICAL"]
        assert constraints.blocked_commands == []
        assert constraints.require_confirmation is False

    def test_custom_values(self):
        """Should accept custom values."""
        constraints = SafetyConstraints(
            max_concurrent_commands=10,
            blocked_commands=["rm -rf /", "dd"],
        )
        assert constraints.max_concurrent_commands == 10
        assert constraints.blocked_commands == ["rm -rf /", "dd"]


class TestDevice:
    """Tests for Device dataclass."""

    def test_create_device_minimal(self):
        """Should create device with minimal fields."""
        device = Device(
            id="test-1",
            hostname="test.local",
            device_type=DeviceType.SERVER,
        )
        assert device.id == "test-1"
        assert device.hostname == "test.local"
        assert device.device_type == DeviceType.SERVER
        assert device.port == 22
        assert device.status == DeviceStatus.UNKNOWN

    def test_create_device_full(self):
        """Should create device with all fields."""
        device = Device(
            id="robot-arm-1",
            hostname="arm.local",
            ip="192.168.1.100",
            port=2222,
            device_type=DeviceType.ROBOT,
            role="manipulator",
            labels={"env": "production", "location": "lab"},
            status=DeviceStatus.ONLINE,
            connection=ConnectionConfig(port=2222),
            safety_constraints=SafetyConstraints(max_concurrent_commands=10),
        )
        assert device.id == "robot-arm-1"
        assert device.ip == "192.168.1.100"
        assert device.port == 2222
        assert device.role == "manipulator"
        assert device.labels["env"] == "production"
        assert device.connection.port == 2222
        assert device.safety_constraints.max_concurrent_commands == 10

    def test_to_dict(self):
        """Should convert device to dictionary."""
        device = Device(
            id="test-1",
            hostname="test.local",
            device_type=DeviceType.SERVER,
            labels={"env": "test"},
        )
        d = device.to_dict()
        assert d["id"] == "test-1"
        assert d["hostname"] == "test.local"
        assert d["device_type"] == "server"
        assert d["labels"]["env"] == "test"

    def test_from_dict(self):
        """Should create device from dictionary."""
        data = {
            "id": "test-1",
            "hostname": "test.local",
            "device_type": "server",
            "port": 22,
            "status": "online",
            "labels": {"env": "test"},
        }
        device = Device.from_dict(data)
        assert device.id == "test-1"
        assert device.hostname == "test.local"
        assert device.device_type == DeviceType.SERVER
        assert device.status == DeviceStatus.ONLINE
        assert device.labels["env"] == "test"


class TestCreateDeviceHelper:
    """Tests for create_device helper function."""

    def test_create_device_basic(self):
        """Should create device with hostname."""
        device = create_device(hostname="server.local")
        assert device.hostname == "server.local"
        assert device.id is not None
        assert device.device_type == DeviceType.SERVER

    def test_create_device_with_options(self):
        """Should create device with all options."""
        device = create_device(
            hostname="robot.local",
            ip="10.0.0.50",
            device_type=DeviceType.ROBOT,
            role="arm",
            port=2222,
            labels={"zone": "A"},
        )
        assert device.hostname == "robot.local"
        assert device.ip == "10.0.0.50"
        assert device.device_type == DeviceType.ROBOT
        assert device.role == "arm"
        assert device.port == 2222
        assert device.labels["zone"] == "A"

    def test_create_device_generates_id(self):
        """Should generate unique ID if not provided."""
        device1 = create_device(hostname="server1.local")
        device2 = create_device(hostname="server2.local")
        assert device1.id != device2.id


class TestDeviceInventory:
    """Tests for DeviceInventory."""

    @pytest.fixture
    def temp_inventory_path(self):
        """Create a temporary inventory file path."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            path = Path(f.name)
        yield path
        # Cleanup
        if path.exists():
            path.unlink()

    @pytest.fixture
    def inventory(self, temp_inventory_path):
        """Create an inventory instance."""
        return DeviceInventory(temp_inventory_path)

    @pytest.fixture
    def sample_devices(self):
        """Create sample devices."""
        return [
            Device(
                id="server-1",
                hostname="server1.local",
                device_type=DeviceType.SERVER,
                role="web",
                labels={"env": "production"},
                status=DeviceStatus.ONLINE,
            ),
            Device(
                id="server-2",
                hostname="server2.local",
                device_type=DeviceType.SERVER,
                role="db",
                labels={"env": "production"},
                status=DeviceStatus.ONLINE,
            ),
            Device(
                id="robot-1",
                hostname="robot1.local",
                device_type=DeviceType.ROBOT,
                role="arm",
                labels={"env": "test"},
                status=DeviceStatus.OFFLINE,
            ),
        ]

    def test_add_device(self, inventory):
        """Should add device to inventory."""
        device = create_device(hostname="test.local")
        inventory.add(device)
        assert inventory.get(device.id) is not None
        assert inventory.count() == 1

    def test_add_duplicate_raises(self, inventory):
        """Should raise error when adding duplicate ID."""
        device = create_device(hostname="test.local")
        inventory.add(device)
        with pytest.raises(ValueError, match="already exists"):
            inventory.add(device)

    def test_get_device(self, inventory, sample_devices):
        """Should get device by ID."""
        for device in sample_devices:
            inventory.add(device)

        result = inventory.get("server-1")
        assert result is not None
        assert result.hostname == "server1.local"

    def test_get_nonexistent(self, inventory):
        """Should return None for nonexistent device."""
        assert inventory.get("nonexistent") is None

    def test_get_by_hostname(self, inventory, sample_devices):
        """Should get device by hostname."""
        for device in sample_devices:
            inventory.add(device)

        result = inventory.get_by_hostname("server2.local")
        assert result is not None
        assert result.id == "server-2"

    def test_list_devices(self, inventory, sample_devices):
        """Should list all devices."""
        for device in sample_devices:
            inventory.add(device)

        devices = inventory.list()
        assert len(devices) == 3

    def test_remove_device(self, inventory, sample_devices):
        """Should remove device from inventory."""
        for device in sample_devices:
            inventory.add(device)

        assert inventory.remove("server-1") is True
        assert inventory.get("server-1") is None
        assert inventory.count() == 2

    def test_remove_nonexistent(self, inventory):
        """Should return False when removing nonexistent device."""
        assert inventory.remove("nonexistent") is False

    def test_update_status(self, inventory, sample_devices):
        """Should update device status."""
        for device in sample_devices:
            inventory.add(device)

        inventory.update_status("server-1", DeviceStatus.DEGRADED)
        device = inventory.get("server-1")
        assert device.status == DeviceStatus.DEGRADED

    def test_filter_by_role(self, inventory, sample_devices):
        """Should filter devices by role."""
        for device in sample_devices:
            inventory.add(device)

        web_devices = inventory.filter(role="web")
        assert len(web_devices) == 1
        assert web_devices[0].id == "server-1"

    def test_filter_by_labels(self, inventory, sample_devices):
        """Should filter devices by labels."""
        for device in sample_devices:
            inventory.add(device)

        prod_devices = inventory.filter(labels={"env": "production"})
        assert len(prod_devices) == 2

    def test_filter_by_status(self, inventory, sample_devices):
        """Should filter devices by status."""
        for device in sample_devices:
            inventory.add(device)

        online_devices = inventory.filter(status=DeviceStatus.ONLINE)
        assert len(online_devices) == 2

    def test_filter_by_device_type(self, inventory, sample_devices):
        """Should filter devices by type."""
        for device in sample_devices:
            inventory.add(device)

        robots = inventory.filter(device_type=DeviceType.ROBOT)
        assert len(robots) == 1
        assert robots[0].id == "robot-1"

    def test_filter_combined(self, inventory, sample_devices):
        """Should filter with multiple criteria."""
        for device in sample_devices:
            inventory.add(device)

        result = inventory.filter(
            device_type=DeviceType.SERVER,
            status=DeviceStatus.ONLINE,
        )
        assert len(result) == 2

    def test_count(self, inventory, sample_devices):
        """Should count total devices."""
        for device in sample_devices:
            inventory.add(device)

        assert inventory.count() == 3

    def test_count_by_status(self, inventory, sample_devices):
        """Should count devices by status."""
        for device in sample_devices:
            inventory.add(device)

        counts = inventory.count_by_status()
        assert counts[DeviceStatus.ONLINE] == 2
        assert counts[DeviceStatus.OFFLINE] == 1

    def test_save_and_load(self, inventory, sample_devices, temp_inventory_path):
        """Should save and load inventory from file."""
        for device in sample_devices:
            inventory.add(device)

        inventory.save()

        # Create new inventory and load
        new_inventory = DeviceInventory(temp_inventory_path)
        new_inventory.load(temp_inventory_path)

        assert new_inventory.count() == 3
        device = new_inventory.get("server-1")
        assert device is not None
        assert device.hostname == "server1.local"
        assert device.labels["env"] == "production"

    def test_load_creates_file_if_missing(self, temp_inventory_path):
        """Should handle missing file gracefully."""
        # Delete file if exists
        if temp_inventory_path.exists():
            temp_inventory_path.unlink()

        inventory = DeviceInventory(temp_inventory_path)
        inventory.load(temp_inventory_path)  # Should not raise
        assert inventory.count() == 0

    def test_clear(self, inventory, sample_devices):
        """Should clear all devices."""
        for device in sample_devices:
            inventory.add(device)

        inventory.clear()
        assert inventory.count() == 0


class TestDeviceInventorySingleton:
    """Tests for global device inventory."""

    def test_get_set_inventory(self):
        """Should get and set global inventory."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            path = Path(f.name)

        try:
            inv = DeviceInventory(path)
            set_device_inventory(inv)
            assert get_device_inventory() is inv
        finally:
            if path.exists():
                path.unlink()

    def test_get_creates_default(self):
        """Should create default inventory if not set."""
        set_device_inventory(None)
        inv = get_device_inventory()
        assert inv is not None
        assert isinstance(inv, DeviceInventory)
