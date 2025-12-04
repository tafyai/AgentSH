"""Device inventory management for multi-device orchestration.

Provides data structures and management for device fleets including
device definitions, inventory operations, and filtering capabilities.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, List, Optional

import yaml

from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)


class DeviceType(str, Enum):
    """Types of devices that can be managed."""

    SERVER = "server"
    WORKSTATION = "workstation"
    EMBEDDED = "embedded"
    ROBOT = "robot"
    CONTAINER = "container"
    VM = "vm"
    IOT = "iot"
    CUSTOM = "custom"


class DeviceStatus(str, Enum):
    """Device connection/health status."""

    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"
    UNKNOWN = "unknown"


class ConnectionMethod(str, Enum):
    """Methods for connecting to devices."""

    SSH = "ssh"
    LOCAL = "local"
    DOCKER = "docker"
    KUBERNETES = "kubernetes"
    MCP = "mcp"


@dataclass
class ConnectionConfig:
    """Configuration for connecting to a device.

    Attributes:
        method: Connection method (ssh, local, docker, etc.)
        credentials_profile: Name of credentials profile to use
        port: Port for connection (default depends on method)
        options: Additional connection options
    """

    method: ConnectionMethod = ConnectionMethod.SSH
    credentials_profile: Optional[str] = None
    port: Optional[int] = None
    options: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "method": self.method.value,
            "credentials_profile": self.credentials_profile,
            "port": self.port,
            "options": self.options,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConnectionConfig":
        """Create from dictionary."""
        return cls(
            method=ConnectionMethod(data.get("method", "ssh")),
            credentials_profile=data.get("credentials_profile"),
            port=data.get("port"),
            options=data.get("options", {}),
        )


@dataclass
class SafetyConstraints:
    """Safety constraints for device operations.

    Attributes:
        max_concurrent_commands: Maximum concurrent commands allowed
        require_approval_for: Risk levels requiring approval
        blocked_commands: Patterns of blocked commands
        allowed_paths: Paths where operations are allowed
        require_confirmation: Always require confirmation
    """

    max_concurrent_commands: int = 5
    require_approval_for: list[str] = field(default_factory=lambda: ["HIGH", "CRITICAL"])
    blocked_commands: list[str] = field(default_factory=list)
    allowed_paths: list[str] = field(default_factory=list)
    require_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "max_concurrent_commands": self.max_concurrent_commands,
            "require_approval_for": self.require_approval_for,
            "blocked_commands": self.blocked_commands,
            "allowed_paths": self.allowed_paths,
            "require_confirmation": self.require_confirmation,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SafetyConstraints":
        """Create from dictionary."""
        return cls(
            max_concurrent_commands=data.get("max_concurrent_commands", 5),
            require_approval_for=data.get("require_approval_for", ["HIGH", "CRITICAL"]),
            blocked_commands=data.get("blocked_commands", []),
            allowed_paths=data.get("allowed_paths", []),
            require_confirmation=data.get("require_confirmation", False),
        )


@dataclass
class Device:
    """A managed device in the inventory.

    Attributes:
        id: Unique device identifier
        hostname: Device hostname
        ip: IP address (optional)
        port: Default port for connections
        device_type: Type of device
        role: Device role (e.g., "web-server", "database")
        labels: Key-value labels for filtering
        connection: Connection configuration
        capabilities: List of device capabilities
        status: Current device status
        safety_constraints: Safety constraints for operations
        metadata: Additional metadata
        created_at: When device was added
        updated_at: When device was last updated
        last_seen: When device was last contacted
    """

    id: str
    hostname: str
    ip: Optional[str] = None
    port: int = 22
    device_type: DeviceType = DeviceType.SERVER
    role: Optional[str] = None
    labels: dict[str, str] = field(default_factory=dict)
    connection: ConnectionConfig = field(default_factory=ConnectionConfig)
    capabilities: list[str] = field(default_factory=list)
    status: DeviceStatus = DeviceStatus.UNKNOWN
    safety_constraints: SafetyConstraints = field(default_factory=SafetyConstraints)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    last_seen: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert device to dictionary for serialization."""
        return {
            "id": self.id,
            "hostname": self.hostname,
            "ip": self.ip,
            "port": self.port,
            "device_type": self.device_type.value,
            "role": self.role,
            "labels": self.labels,
            "connection": self.connection.to_dict(),
            "capabilities": self.capabilities,
            "status": self.status.value,
            "safety_constraints": self.safety_constraints.to_dict(),
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Device":
        """Create device from dictionary."""
        return cls(
            id=data["id"],
            hostname=data["hostname"],
            ip=data.get("ip"),
            port=data.get("port", 22),
            device_type=DeviceType(data.get("device_type", "server")),
            role=data.get("role"),
            labels=data.get("labels", {}),
            connection=ConnectionConfig.from_dict(data.get("connection", {})),
            capabilities=data.get("capabilities", []),
            status=DeviceStatus(data.get("status", "unknown")),
            safety_constraints=SafetyConstraints.from_dict(
                data.get("safety_constraints", {})
            ),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"])
            if "created_at" in data
            else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"])
            if "updated_at" in data
            else datetime.now(),
            last_seen=datetime.fromisoformat(data["last_seen"])
            if data.get("last_seen")
            else None,
        )

    def matches_filter(
        self,
        role: Optional[str] = None,
        labels: Optional[dict[str, str]] = None,
        status: Optional[DeviceStatus] = None,
        device_type: Optional[DeviceType] = None,
    ) -> bool:
        """Check if device matches filter criteria.

        Args:
            role: Required role (exact match)
            labels: Required labels (all must match)
            status: Required status
            device_type: Required device type

        Returns:
            True if device matches all specified criteria
        """
        if role is not None and self.role != role:
            return False
        if status is not None and self.status != status:
            return False
        if device_type is not None and self.device_type != device_type:
            return False
        if labels:
            for key, value in labels.items():
                if self.labels.get(key) != value:
                    return False
        return True


class DeviceInventory:
    """Manages a collection of devices.

    Provides CRUD operations, persistence, and filtering for device fleets.

    Example:
        inventory = DeviceInventory()
        inventory.load(Path("devices.yaml"))

        # Add a device
        device = Device(id="web-1", hostname="web1.example.com")
        inventory.add(device)

        # Filter devices
        web_servers = inventory.filter(role="web-server", status=DeviceStatus.ONLINE)

        # Save changes
        inventory.save()
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        """Initialize device inventory.

        Args:
            path: Optional path for persistence
        """
        self._devices: dict[str, Device] = {}
        self._path: Optional[Path] = path

        if path and path.exists():
            self.load(path)

        logger.debug("DeviceInventory initialized", device_count=len(self._devices))

    def load(self, path: Path) -> None:
        """Load inventory from YAML file.

        Args:
            path: Path to inventory file
        """
        self._path = path

        if not path.exists():
            logger.warning("Inventory file not found", path=str(path))
            return

        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}

        devices_data = data.get("devices", [])
        for device_data in devices_data:
            try:
                device = Device.from_dict(device_data)
                self._devices[device.id] = device
            except Exception as e:
                logger.error(
                    "Failed to load device",
                    device_id=device_data.get("id"),
                    error=str(e),
                )

        logger.info("Inventory loaded", path=str(path), device_count=len(self._devices))

    def save(self, path: Optional[Path] = None) -> None:
        """Save inventory to YAML file.

        Args:
            path: Optional path (uses original if not specified)
        """
        save_path = path or self._path
        if not save_path:
            raise ValueError("No path specified for saving inventory")

        # Ensure parent directory exists
        save_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "devices": [device.to_dict() for device in self._devices.values()],
        }

        with open(save_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        logger.info("Inventory saved", path=str(save_path), device_count=len(self._devices))

    def get(self, device_id: str) -> Optional[Device]:
        """Get a device by ID.

        Args:
            device_id: Device identifier

        Returns:
            Device if found, None otherwise
        """
        return self._devices.get(device_id)

    def list(self) -> List[Device]:
        """List all devices.

        Returns:
            List of all devices
        """
        return [d for d in self._devices.values()]

    def filter(
        self,
        role: Optional[str] = None,
        labels: Optional[dict[str, str]] = None,
        status: Optional[DeviceStatus] = None,
        device_type: Optional[DeviceType] = None,
    ) -> List[Device]:
        """Filter devices by criteria.

        Args:
            role: Filter by role
            labels: Filter by labels (all must match)
            status: Filter by status
            device_type: Filter by device type

        Returns:
            List of matching devices
        """
        return [
            device
            for device in self._devices.values()
            if device.matches_filter(role, labels, status, device_type)
        ]

    def add(self, device: Device) -> None:
        """Add a device to the inventory.

        Args:
            device: Device to add

        Raises:
            ValueError: If device ID already exists
        """
        if device.id in self._devices:
            raise ValueError(f"Device with ID '{device.id}' already exists")

        self._devices[device.id] = device
        logger.info("Device added", device_id=device.id, hostname=device.hostname)

    def remove(self, device_id: str) -> bool:
        """Remove a device from the inventory.

        Args:
            device_id: ID of device to remove

        Returns:
            True if device was removed, False if not found
        """
        if device_id in self._devices:
            del self._devices[device_id]
            logger.info("Device removed", device_id=device_id)
            return True
        return False

    def update(self, device: Device) -> bool:
        """Update an existing device.

        Args:
            device: Device with updated data

        Returns:
            True if device was updated, False if not found
        """
        if device.id not in self._devices:
            return False

        device.updated_at = datetime.now()
        self._devices[device.id] = device
        logger.info("Device updated", device_id=device.id)
        return True

    def update_status(self, device_id: str, status: DeviceStatus) -> bool:
        """Update device status.

        Args:
            device_id: Device identifier
            status: New status

        Returns:
            True if updated, False if device not found
        """
        device = self._devices.get(device_id)
        if not device:
            return False

        device.status = status
        device.updated_at = datetime.now()
        if status == DeviceStatus.ONLINE:
            device.last_seen = datetime.now()

        logger.debug("Device status updated", device_id=device_id, status=status.value)
        return True

    def get_by_hostname(self, hostname: str) -> Optional[Device]:
        """Get a device by hostname.

        Args:
            hostname: Device hostname

        Returns:
            Device if found, None otherwise
        """
        for device in self._devices.values():
            if device.hostname == hostname:
                return device
        return None

    def get_by_ip(self, ip: str) -> Optional[Device]:
        """Get a device by IP address.

        Args:
            ip: IP address

        Returns:
            Device if found, None otherwise
        """
        for device in self._devices.values():
            if device.ip == ip:
                return device
        return None

    def get_online(self) -> List[Device]:
        """Get all online devices.

        Returns:
            List of online devices
        """
        return self.filter(status=DeviceStatus.ONLINE)

    def count(self) -> int:
        """Get total device count.

        Returns:
            Number of devices in inventory
        """
        return len(self._devices)

    def count_by_status(self) -> dict[DeviceStatus, int]:
        """Get device counts by status.

        Returns:
            Dictionary mapping status to count
        """
        counts: dict[DeviceStatus, int] = {}
        for device in self._devices.values():
            counts[device.status] = counts.get(device.status, 0) + 1
        return counts

    def clear(self) -> None:
        """Remove all devices from inventory."""
        self._devices.clear()
        logger.info("Inventory cleared")


def create_device(
    hostname: str,
    ip: Optional[str] = None,
    device_type: DeviceType = DeviceType.SERVER,
    role: Optional[str] = None,
    labels: Optional[dict[str, str]] = None,
    connection_method: ConnectionMethod = ConnectionMethod.SSH,
    port: int = 22,
) -> Device:
    """Convenience function to create a device with generated ID.

    Args:
        hostname: Device hostname
        ip: IP address
        device_type: Type of device
        role: Device role
        labels: Device labels
        connection_method: Connection method
        port: Connection port

    Returns:
        New Device instance
    """
    device_id = f"{hostname.split('.')[0]}-{uuid.uuid4().hex[:8]}"
    return Device(
        id=device_id,
        hostname=hostname,
        ip=ip,
        port=port,
        device_type=device_type,
        role=role,
        labels=labels or {},
        connection=ConnectionConfig(method=connection_method, port=port),
    )


# Global inventory instance
_inventory: Optional[DeviceInventory] = None


def get_device_inventory() -> DeviceInventory:
    """Get the global device inventory.

    Returns:
        Global DeviceInventory singleton
    """
    global _inventory
    if _inventory is None:
        _inventory = DeviceInventory()
    return _inventory


def set_device_inventory(inventory: DeviceInventory) -> None:
    """Set the global device inventory.

    Args:
        inventory: Inventory to use globally
    """
    global _inventory
    _inventory = inventory
