"""Remote execution toolset for multi-device operations.

Provides tools for executing commands on remote devices,
managing device inventory, and orchestrating fleet operations.
"""

from typing import Any, Optional

from agentsh.orchestrator.devices import (
    Device,
    DeviceInventory,
    DeviceStatus,
    DeviceType,
    create_device,
    get_device_inventory,
)
from agentsh.orchestrator.ssh import CommandResult, SSHExecutor, get_ssh_executor
from agentsh.plugins.base import Toolset
from agentsh.security.classifier import RiskLevel
from agentsh.tools.base import Tool, ToolResult
from agentsh.tools.registry import ToolRegistry


class RemoteToolset(Toolset):
    """Toolset for remote device operations.

    Provides tools for:
    - Executing commands on remote devices
    - Managing device inventory
    - Querying device status
    - Fleet-wide operations

    Example:
        toolset = RemoteToolset()
        toolset.register_tools(registry)

        # Execute on single device
        result = registry.get_tool("remote.run").handler(
            device_id="web-1",
            command="uptime"
        )

        # List devices
        devices = registry.get_tool("remote.list_devices").handler()
    """

    @property
    def name(self) -> str:
        """Return toolset name."""
        return "remote"

    @property
    def description(self) -> str:
        """Return toolset description."""
        return "Tools for remote device operations via SSH"

    def configure(self, config: dict[str, Any]) -> None:
        """Configure the toolset.

        Args:
            config: Configuration dictionary
        """
        # Configuration is handled via global inventory/executor
        pass

    def register_tools(self, registry: ToolRegistry) -> None:
        """Register remote execution tools.

        Args:
            registry: Tool registry to register with
        """
        # remote.run - Execute command on remote device
        registry.register_tool(
            name="remote.run",
            handler=self._run_command,
            schema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "ID of the device to execute on",
                    },
                    "command": {
                        "type": "string",
                        "description": "Command to execute",
                    },
                    "timeout": {
                        "type": "number",
                        "description": "Command timeout in seconds (default: 60)",
                    },
                    "environment": {
                        "type": "object",
                        "description": "Environment variables to set",
                        "additionalProperties": {"type": "string"},
                    },
                },
                "required": ["device_id", "command"],
            },
            risk_level=RiskLevel.MEDIUM,
            description="Execute a command on a remote device via SSH",
        )

        # remote.run_parallel - Execute on multiple devices
        registry.register_tool(
            name="remote.run_parallel",
            handler=self._run_parallel,
            schema={
                "type": "object",
                "properties": {
                    "device_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "IDs of devices to execute on",
                    },
                    "command": {
                        "type": "string",
                        "description": "Command to execute",
                    },
                    "timeout": {
                        "type": "number",
                        "description": "Command timeout per device in seconds",
                    },
                    "max_concurrent": {
                        "type": "integer",
                        "description": "Maximum concurrent executions",
                    },
                },
                "required": ["device_ids", "command"],
            },
            risk_level=RiskLevel.HIGH,
            description="Execute a command on multiple devices in parallel",
        )

        # remote.list_devices - List devices in inventory
        registry.register_tool(
            name="remote.list_devices",
            handler=self._list_devices,
            schema={
                "type": "object",
                "properties": {
                    "role": {
                        "type": "string",
                        "description": "Filter by device role",
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by status (online, offline, etc.)",
                    },
                    "labels": {
                        "type": "object",
                        "description": "Filter by labels",
                        "additionalProperties": {"type": "string"},
                    },
                },
            },
            risk_level=RiskLevel.SAFE,
            description="List devices in the inventory with optional filters",
        )

        # remote.get_device - Get device details
        registry.register_tool(
            name="remote.get_device",
            handler=self._get_device,
            schema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "ID of the device",
                    },
                },
                "required": ["device_id"],
            },
            risk_level=RiskLevel.SAFE,
            description="Get detailed information about a device",
        )

        # remote.add_device - Add a device to inventory
        registry.register_tool(
            name="remote.add_device",
            handler=self._add_device,
            schema={
                "type": "object",
                "properties": {
                    "hostname": {
                        "type": "string",
                        "description": "Device hostname",
                    },
                    "ip": {
                        "type": "string",
                        "description": "Device IP address",
                    },
                    "device_type": {
                        "type": "string",
                        "description": "Device type (server, workstation, etc.)",
                    },
                    "role": {
                        "type": "string",
                        "description": "Device role",
                    },
                    "labels": {
                        "type": "object",
                        "description": "Device labels",
                        "additionalProperties": {"type": "string"},
                    },
                    "port": {
                        "type": "integer",
                        "description": "SSH port (default: 22)",
                    },
                },
                "required": ["hostname"],
            },
            risk_level=RiskLevel.MEDIUM,
            description="Add a new device to the inventory",
        )

        # remote.remove_device - Remove a device
        registry.register_tool(
            name="remote.remove_device",
            handler=self._remove_device,
            schema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "ID of the device to remove",
                    },
                },
                "required": ["device_id"],
            },
            risk_level=RiskLevel.MEDIUM,
            description="Remove a device from the inventory",
        )

        # remote.check_status - Check device connectivity
        registry.register_tool(
            name="remote.check_status",
            handler=self._check_status,
            schema={
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "ID of the device to check",
                    },
                },
                "required": ["device_id"],
            },
            risk_level=RiskLevel.SAFE,
            description="Check if a device is reachable via SSH",
        )

        # remote.fleet_status - Get status of all devices
        registry.register_tool(
            name="remote.fleet_status",
            handler=self._fleet_status,
            schema={
                "type": "object",
                "properties": {
                    "check_connectivity": {
                        "type": "boolean",
                        "description": "Actually test connectivity (slower but accurate)",
                    },
                },
            },
            risk_level=RiskLevel.SAFE,
            description="Get status summary of all devices in the fleet",
        )

    def _run_command(
        self,
        device_id: str,
        command: str,
        timeout: Optional[float] = None,
        environment: Optional[dict[str, str]] = None,
    ) -> ToolResult:
        """Execute a command on a remote device.

        Args:
            device_id: Target device ID
            command: Command to execute
            timeout: Command timeout in seconds
            environment: Environment variables to set

        Returns:
            ToolResult with command output
        """
        inventory = get_device_inventory()
        device = inventory.get(device_id)

        if not device:
            return ToolResult(
                success=False,
                output="",
                error=f"Device '{device_id}' not found in inventory",
            )

        executor = get_ssh_executor()
        result = executor.execute(
            device,
            command,
            timeout=timeout,
            environment=environment,
        )

        # Update device status based on result
        if result.success:
            inventory.update_status(device_id, DeviceStatus.ONLINE)
        elif result.error and "connection" in result.error.lower():
            inventory.update_status(device_id, DeviceStatus.OFFLINE)

        return ToolResult(
            success=result.success,
            output=self._format_result(result),
            error=result.error,
        )

    def _run_parallel(
        self,
        device_ids: list[str],
        command: str,
        timeout: Optional[float] = None,
        max_concurrent: Optional[int] = None,
    ) -> ToolResult:
        """Execute a command on multiple devices in parallel.

        Args:
            device_ids: Target device IDs
            command: Command to execute
            timeout: Command timeout per device
            max_concurrent: Maximum concurrent executions

        Returns:
            ToolResult with aggregated results
        """
        inventory = get_device_inventory()
        devices = []

        for device_id in device_ids:
            device = inventory.get(device_id)
            if device:
                devices.append(device)
            else:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Device '{device_id}' not found in inventory",
                )

        if not devices:
            return ToolResult(
                success=False,
                output="",
                error="No valid devices specified",
            )

        executor = get_ssh_executor()
        result = executor.execute_parallel(
            devices,
            command,
            timeout=timeout,
            max_concurrent=max_concurrent,
        )

        # Update device statuses
        for device_id, cmd_result in result.results.items():
            if cmd_result.success:
                inventory.update_status(device_id, DeviceStatus.ONLINE)
            elif cmd_result.error and "connection" in cmd_result.error.lower():
                inventory.update_status(device_id, DeviceStatus.OFFLINE)

        output_lines = [
            f"Executed on {result.total_devices} devices:",
            f"  Successful: {result.successful}",
            f"  Failed: {result.failed}",
            f"  Duration: {result.duration_ms:.1f}ms",
            "",
            "Results:",
        ]

        for device_id, cmd_result in result.results.items():
            status = "✓" if cmd_result.success else "✗"
            output_lines.append(f"\n[{status}] {device_id}:")
            if cmd_result.stdout:
                output_lines.append(f"  stdout: {cmd_result.stdout[:200]}")
            if cmd_result.stderr:
                output_lines.append(f"  stderr: {cmd_result.stderr[:200]}")
            if cmd_result.error:
                output_lines.append(f"  error: {cmd_result.error}")

        return ToolResult(
            success=result.failed == 0,
            output="\n".join(output_lines),
            error=None if result.failed == 0 else f"{result.failed} devices failed",
        )

    def _list_devices(
        self,
        role: Optional[str] = None,
        status: Optional[str] = None,
        labels: Optional[dict[str, str]] = None,
    ) -> ToolResult:
        """List devices in the inventory.

        Args:
            role: Filter by role
            status: Filter by status
            labels: Filter by labels

        Returns:
            ToolResult with device list
        """
        inventory = get_device_inventory()

        status_enum = DeviceStatus(status) if status else None
        devices = inventory.filter(
            role=role,
            labels=labels,
            status=status_enum,
        )

        if not devices:
            return ToolResult(
                success=True,
                output="No devices found matching criteria",
            )

        output_lines = [f"Found {len(devices)} device(s):", ""]
        for device in devices:
            labels_str = ", ".join(f"{k}={v}" for k, v in device.labels.items())
            output_lines.append(
                f"  {device.id}: {device.hostname} "
                f"[{device.status.value}] "
                f"({device.device_type.value})"
                f"{f' labels: {labels_str}' if labels_str else ''}"
            )

        return ToolResult(success=True, output="\n".join(output_lines))

    def _get_device(self, device_id: str) -> ToolResult:
        """Get device details.

        Args:
            device_id: Device ID

        Returns:
            ToolResult with device details
        """
        inventory = get_device_inventory()
        device = inventory.get(device_id)

        if not device:
            return ToolResult(
                success=False,
                output="",
                error=f"Device '{device_id}' not found",
            )

        output_lines = [
            f"Device: {device.id}",
            f"  Hostname: {device.hostname}",
            f"  IP: {device.ip or 'not set'}",
            f"  Port: {device.port}",
            f"  Type: {device.device_type.value}",
            f"  Role: {device.role or 'not set'}",
            f"  Status: {device.status.value}",
            f"  Connection: {device.connection.method.value}",
            f"  Labels: {device.labels or 'none'}",
            f"  Capabilities: {device.capabilities or 'none'}",
            f"  Created: {device.created_at.isoformat()}",
            f"  Last Seen: {device.last_seen.isoformat() if device.last_seen else 'never'}",
        ]

        return ToolResult(success=True, output="\n".join(output_lines))

    def _add_device(
        self,
        hostname: str,
        ip: Optional[str] = None,
        device_type: Optional[str] = None,
        role: Optional[str] = None,
        labels: Optional[dict[str, str]] = None,
        port: int = 22,
    ) -> ToolResult:
        """Add a device to the inventory.

        Args:
            hostname: Device hostname
            ip: IP address
            device_type: Device type
            role: Device role
            labels: Device labels
            port: SSH port

        Returns:
            ToolResult with new device info
        """
        inventory = get_device_inventory()

        # Check for duplicate hostname
        if inventory.get_by_hostname(hostname):
            return ToolResult(
                success=False,
                output="",
                error=f"Device with hostname '{hostname}' already exists",
            )

        dtype = DeviceType(device_type) if device_type else DeviceType.SERVER
        device = create_device(
            hostname=hostname,
            ip=ip,
            device_type=dtype,
            role=role,
            labels=labels,
            port=port,
        )

        try:
            inventory.add(device)
            return ToolResult(
                success=True,
                output=f"Added device '{device.id}' ({hostname})",
            )
        except ValueError as e:
            return ToolResult(success=False, output="", error=str(e))

    def _remove_device(self, device_id: str) -> ToolResult:
        """Remove a device from the inventory.

        Args:
            device_id: Device ID

        Returns:
            ToolResult indicating success
        """
        inventory = get_device_inventory()

        if inventory.remove(device_id):
            return ToolResult(
                success=True,
                output=f"Removed device '{device_id}'",
            )
        else:
            return ToolResult(
                success=False,
                output="",
                error=f"Device '{device_id}' not found",
            )

    def _check_status(self, device_id: str) -> ToolResult:
        """Check if a device is reachable.

        Args:
            device_id: Device ID

        Returns:
            ToolResult with connectivity status
        """
        inventory = get_device_inventory()
        device = inventory.get(device_id)

        if not device:
            return ToolResult(
                success=False,
                output="",
                error=f"Device '{device_id}' not found",
            )

        executor = get_ssh_executor()
        result = executor.execute(device, "echo ok", timeout=10)

        if result.success:
            inventory.update_status(device_id, DeviceStatus.ONLINE)
            return ToolResult(
                success=True,
                output=f"Device '{device_id}' is online ({result.duration_ms:.1f}ms)",
            )
        else:
            inventory.update_status(device_id, DeviceStatus.OFFLINE)
            return ToolResult(
                success=False,
                output=f"Device '{device_id}' is offline",
                error=result.error,
            )

    def _fleet_status(
        self,
        check_connectivity: bool = False,
    ) -> ToolResult:
        """Get status summary of all devices.

        Args:
            check_connectivity: Whether to actively check connectivity

        Returns:
            ToolResult with fleet status summary
        """
        inventory = get_device_inventory()
        devices = inventory.list()

        if not devices:
            return ToolResult(
                success=True,
                output="No devices in inventory",
            )

        if check_connectivity:
            # Actually ping each device
            executor = get_ssh_executor()
            for device in devices:
                result = executor.execute(device, "echo ok", timeout=5)
                if result.success:
                    inventory.update_status(device.id, DeviceStatus.ONLINE)
                else:
                    inventory.update_status(device.id, DeviceStatus.OFFLINE)

        counts = inventory.count_by_status()
        total = inventory.count()

        output_lines = [
            f"Fleet Status ({total} devices):",
            "",
        ]

        for status, count in sorted(counts.items(), key=lambda x: x[0].value):
            percentage = (count / total * 100) if total > 0 else 0
            output_lines.append(f"  {status.value}: {count} ({percentage:.1f}%)")

        # Add breakdown by type
        types: dict[DeviceType, int] = {}
        for device in devices:
            types[device.device_type] = types.get(device.device_type, 0) + 1

        output_lines.append("")
        output_lines.append("By Type:")
        for dtype, count in sorted(types.items(), key=lambda x: x[0].value):
            output_lines.append(f"  {dtype.value}: {count}")

        return ToolResult(success=True, output="\n".join(output_lines))

    def _format_result(self, result: CommandResult) -> str:
        """Format a command result for display.

        Args:
            result: Command result

        Returns:
            Formatted string
        """
        lines = [
            f"Device: {result.device_id}",
            f"Exit Code: {result.exit_code}",
            f"Duration: {result.duration_ms:.1f}ms",
        ]

        if result.stdout:
            lines.append(f"\nStdout:\n{result.stdout}")
        if result.stderr:
            lines.append(f"\nStderr:\n{result.stderr}")

        return "\n".join(lines)
