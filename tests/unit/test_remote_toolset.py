"""Tests for remote execution toolset."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from agentsh.plugins.builtin.remote import RemoteToolset
from agentsh.tools.base import ToolResult


class MockDevice:
    """Mock device for testing."""

    def __init__(
        self,
        id: str = "test-device",
        hostname: str = "test.local",
        ip: str = "192.168.1.1",
        port: int = 22,
        status: str = "online",
        device_type: str = "server",
        role: str = "web",
        labels: dict = None,
        capabilities: list = None,
    ):
        self.id = id
        self.hostname = hostname
        self.ip = ip
        self.port = port
        self.status = MagicMock()
        self.status.value = status
        self.device_type = MagicMock()
        self.device_type.value = device_type
        self.role = role
        self.labels = labels or {}
        self.capabilities = capabilities or []
        self.created_at = datetime.now()
        self.last_seen = datetime.now()
        self.connection = MagicMock()
        self.connection.method = MagicMock()
        self.connection.method.value = "ssh"


class MockCommandResult:
    """Mock command result."""

    def __init__(
        self,
        success: bool = True,
        stdout: str = "",
        stderr: str = "",
        error: str = None,
        exit_code: int = 0,
        duration_ms: float = 100.0,
        device_id: str = "test-device",
    ):
        self.success = success
        self.stdout = stdout
        self.stderr = stderr
        self.error = error
        self.exit_code = exit_code
        self.duration_ms = duration_ms
        self.device_id = device_id


class MockParallelResult:
    """Mock parallel execution result."""

    def __init__(
        self,
        results: dict = None,
        total_devices: int = 0,
        successful: int = 0,
        failed: int = 0,
        duration_ms: float = 100.0,
    ):
        self.results = results or {}
        self.total_devices = total_devices
        self.successful = successful
        self.failed = failed
        self.duration_ms = duration_ms


class TestRemoteToolsetProperties:
    """Tests for RemoteToolset basic properties."""

    def test_name(self) -> None:
        """Should return 'remote' as name."""
        toolset = RemoteToolset()
        assert toolset.name == "remote"

    def test_description(self) -> None:
        """Should return description."""
        toolset = RemoteToolset()
        assert "remote" in toolset.description.lower()
        assert "ssh" in toolset.description.lower()

    def test_configure_does_not_raise(self) -> None:
        """Should not raise on configure."""
        toolset = RemoteToolset()
        toolset.configure({"key": "value"})


class TestRemoteToolsetRegisterTools:
    """Tests for tool registration."""

    def test_registers_run_tool(self) -> None:
        """Should register remote.run tool."""
        toolset = RemoteToolset()
        mock_registry = MagicMock()

        toolset.register_tools(mock_registry)

        calls = mock_registry.register_tool.call_args_list
        tool_names = [call.kwargs.get("name") or call.args[0] for call in calls]
        assert "remote.run" in tool_names

    def test_registers_run_parallel_tool(self) -> None:
        """Should register remote.run_parallel tool."""
        toolset = RemoteToolset()
        mock_registry = MagicMock()

        toolset.register_tools(mock_registry)

        calls = mock_registry.register_tool.call_args_list
        tool_names = [call.kwargs.get("name") or call.args[0] for call in calls]
        assert "remote.run_parallel" in tool_names

    def test_registers_list_devices_tool(self) -> None:
        """Should register remote.list_devices tool."""
        toolset = RemoteToolset()
        mock_registry = MagicMock()

        toolset.register_tools(mock_registry)

        calls = mock_registry.register_tool.call_args_list
        tool_names = [call.kwargs.get("name") or call.args[0] for call in calls]
        assert "remote.list_devices" in tool_names

    def test_registers_get_device_tool(self) -> None:
        """Should register remote.get_device tool."""
        toolset = RemoteToolset()
        mock_registry = MagicMock()

        toolset.register_tools(mock_registry)

        calls = mock_registry.register_tool.call_args_list
        tool_names = [call.kwargs.get("name") or call.args[0] for call in calls]
        assert "remote.get_device" in tool_names

    def test_registers_add_device_tool(self) -> None:
        """Should register remote.add_device tool."""
        toolset = RemoteToolset()
        mock_registry = MagicMock()

        toolset.register_tools(mock_registry)

        calls = mock_registry.register_tool.call_args_list
        tool_names = [call.kwargs.get("name") or call.args[0] for call in calls]
        assert "remote.add_device" in tool_names

    def test_registers_remove_device_tool(self) -> None:
        """Should register remote.remove_device tool."""
        toolset = RemoteToolset()
        mock_registry = MagicMock()

        toolset.register_tools(mock_registry)

        calls = mock_registry.register_tool.call_args_list
        tool_names = [call.kwargs.get("name") or call.args[0] for call in calls]
        assert "remote.remove_device" in tool_names

    def test_registers_check_status_tool(self) -> None:
        """Should register remote.check_status tool."""
        toolset = RemoteToolset()
        mock_registry = MagicMock()

        toolset.register_tools(mock_registry)

        calls = mock_registry.register_tool.call_args_list
        tool_names = [call.kwargs.get("name") or call.args[0] for call in calls]
        assert "remote.check_status" in tool_names

    def test_registers_fleet_status_tool(self) -> None:
        """Should register remote.fleet_status tool."""
        toolset = RemoteToolset()
        mock_registry = MagicMock()

        toolset.register_tools(mock_registry)

        calls = mock_registry.register_tool.call_args_list
        tool_names = [call.kwargs.get("name") or call.args[0] for call in calls]
        assert "remote.fleet_status" in tool_names


class TestRunCommand:
    """Tests for _run_command method."""

    def test_device_not_found(self) -> None:
        """Should return error if device not found."""
        toolset = RemoteToolset()

        with patch("agentsh.plugins.builtin.remote.get_device_inventory") as mock_inv:
            mock_inventory = MagicMock()
            mock_inventory.get.return_value = None
            mock_inv.return_value = mock_inventory

            result = toolset._run_command("nonexistent", "ls")

            assert result.success is False
            assert "not found" in result.error

    def test_successful_execution(self) -> None:
        """Should execute command successfully."""
        toolset = RemoteToolset()
        mock_device = MockDevice()

        with patch("agentsh.plugins.builtin.remote.get_device_inventory") as mock_inv:
            mock_inventory = MagicMock()
            mock_inventory.get.return_value = mock_device
            mock_inv.return_value = mock_inventory

            with patch("agentsh.plugins.builtin.remote.get_ssh_executor") as mock_exec:
                mock_executor = MagicMock()
                mock_executor.execute.return_value = MockCommandResult(
                    success=True,
                    stdout="file1.txt\nfile2.txt",
                    exit_code=0,
                )
                mock_exec.return_value = mock_executor

                result = toolset._run_command("test-device", "ls")

                assert result.success is True
                mock_executor.execute.assert_called_once()

    def test_updates_device_status_online(self) -> None:
        """Should update device status to online on success."""
        toolset = RemoteToolset()
        mock_device = MockDevice()

        with patch("agentsh.plugins.builtin.remote.get_device_inventory") as mock_inv:
            mock_inventory = MagicMock()
            mock_inventory.get.return_value = mock_device
            mock_inv.return_value = mock_inventory

            with patch("agentsh.plugins.builtin.remote.get_ssh_executor") as mock_exec:
                mock_executor = MagicMock()
                mock_executor.execute.return_value = MockCommandResult(success=True)
                mock_exec.return_value = mock_executor

                with patch("agentsh.plugins.builtin.remote.DeviceStatus") as mock_status:
                    mock_status.ONLINE = "online"
                    toolset._run_command("test-device", "ls")
                    mock_inventory.update_status.assert_called()

    def test_updates_device_status_offline_on_connection_error(self) -> None:
        """Should update device status to offline on connection error."""
        toolset = RemoteToolset()
        mock_device = MockDevice()

        with patch("agentsh.plugins.builtin.remote.get_device_inventory") as mock_inv:
            mock_inventory = MagicMock()
            mock_inventory.get.return_value = mock_device
            mock_inv.return_value = mock_inventory

            with patch("agentsh.plugins.builtin.remote.get_ssh_executor") as mock_exec:
                mock_executor = MagicMock()
                mock_executor.execute.return_value = MockCommandResult(
                    success=False,
                    error="Connection refused",
                )
                mock_exec.return_value = mock_executor

                with patch("agentsh.plugins.builtin.remote.DeviceStatus") as mock_status:
                    mock_status.OFFLINE = "offline"
                    toolset._run_command("test-device", "ls")
                    mock_inventory.update_status.assert_called()

    def test_passes_timeout_and_environment(self) -> None:
        """Should pass timeout and environment to executor."""
        toolset = RemoteToolset()
        mock_device = MockDevice()

        with patch("agentsh.plugins.builtin.remote.get_device_inventory") as mock_inv:
            mock_inventory = MagicMock()
            mock_inventory.get.return_value = mock_device
            mock_inv.return_value = mock_inventory

            with patch("agentsh.plugins.builtin.remote.get_ssh_executor") as mock_exec:
                mock_executor = MagicMock()
                mock_executor.execute.return_value = MockCommandResult(success=True)
                mock_exec.return_value = mock_executor

                toolset._run_command(
                    "test-device",
                    "ls",
                    timeout=30.0,
                    environment={"PATH": "/bin"},
                )

                mock_executor.execute.assert_called_once_with(
                    mock_device,
                    "ls",
                    timeout=30.0,
                    environment={"PATH": "/bin"},
                )


class TestRunParallel:
    """Tests for _run_parallel method."""

    def test_device_not_found(self) -> None:
        """Should return error if any device not found."""
        toolset = RemoteToolset()

        with patch("agentsh.plugins.builtin.remote.get_device_inventory") as mock_inv:
            mock_inventory = MagicMock()
            mock_inventory.get.return_value = None
            mock_inv.return_value = mock_inventory

            result = toolset._run_parallel(["nonexistent"], "ls")

            assert result.success is False
            assert "not found" in result.error

    def test_no_valid_devices(self) -> None:
        """Should return error if no valid devices."""
        toolset = RemoteToolset()

        with patch("agentsh.plugins.builtin.remote.get_device_inventory") as mock_inv:
            mock_inventory = MagicMock()
            mock_inventory.get.return_value = None
            mock_inv.return_value = mock_inventory

            result = toolset._run_parallel([], "ls")

            assert result.success is False

    def test_successful_parallel_execution(self) -> None:
        """Should execute on multiple devices in parallel."""
        toolset = RemoteToolset()
        mock_device1 = MockDevice(id="device-1")
        mock_device2 = MockDevice(id="device-2")

        with patch("agentsh.plugins.builtin.remote.get_device_inventory") as mock_inv:
            mock_inventory = MagicMock()
            mock_inventory.get.side_effect = lambda x: {"device-1": mock_device1, "device-2": mock_device2}.get(x)
            mock_inv.return_value = mock_inventory

            with patch("agentsh.plugins.builtin.remote.get_ssh_executor") as mock_exec:
                mock_executor = MagicMock()
                mock_executor.execute_parallel.return_value = MockParallelResult(
                    results={
                        "device-1": MockCommandResult(success=True, stdout="ok", device_id="device-1"),
                        "device-2": MockCommandResult(success=True, stdout="ok", device_id="device-2"),
                    },
                    total_devices=2,
                    successful=2,
                    failed=0,
                )
                mock_exec.return_value = mock_executor

                result = toolset._run_parallel(["device-1", "device-2"], "uptime")

                assert result.success is True
                assert "2 devices" in result.output


class TestListDevices:
    """Tests for _list_devices method."""

    def test_no_devices_found(self) -> None:
        """Should return message when no devices match."""
        toolset = RemoteToolset()

        with patch("agentsh.plugins.builtin.remote.get_device_inventory") as mock_inv:
            mock_inventory = MagicMock()
            mock_inventory.filter.return_value = []
            mock_inv.return_value = mock_inventory

            result = toolset._list_devices()

            assert result.success is True
            assert "No devices found" in result.output

    def test_lists_devices(self) -> None:
        """Should list matching devices."""
        toolset = RemoteToolset()
        mock_device = MockDevice()

        with patch("agentsh.plugins.builtin.remote.get_device_inventory") as mock_inv:
            mock_inventory = MagicMock()
            mock_inventory.filter.return_value = [mock_device]
            mock_inv.return_value = mock_inventory

            result = toolset._list_devices()

            assert result.success is True
            assert "1 device" in result.output
            assert mock_device.hostname in result.output

    def test_filters_by_role(self) -> None:
        """Should filter by role."""
        toolset = RemoteToolset()

        with patch("agentsh.plugins.builtin.remote.get_device_inventory") as mock_inv:
            mock_inventory = MagicMock()
            mock_inventory.filter.return_value = []
            mock_inv.return_value = mock_inventory

            toolset._list_devices(role="web")

            mock_inventory.filter.assert_called_once()
            call_kwargs = mock_inventory.filter.call_args.kwargs
            assert call_kwargs.get("role") == "web"

    def test_filters_by_labels(self) -> None:
        """Should filter by labels."""
        toolset = RemoteToolset()

        with patch("agentsh.plugins.builtin.remote.get_device_inventory") as mock_inv:
            mock_inventory = MagicMock()
            mock_inventory.filter.return_value = []
            mock_inv.return_value = mock_inventory

            toolset._list_devices(labels={"env": "prod"})

            mock_inventory.filter.assert_called_once()
            call_kwargs = mock_inventory.filter.call_args.kwargs
            assert call_kwargs.get("labels") == {"env": "prod"}


class TestGetDevice:
    """Tests for _get_device method."""

    def test_device_not_found(self) -> None:
        """Should return error if device not found."""
        toolset = RemoteToolset()

        with patch("agentsh.plugins.builtin.remote.get_device_inventory") as mock_inv:
            mock_inventory = MagicMock()
            mock_inventory.get.return_value = None
            mock_inv.return_value = mock_inventory

            result = toolset._get_device("nonexistent")

            assert result.success is False
            assert "not found" in result.error

    def test_returns_device_details(self) -> None:
        """Should return device details."""
        toolset = RemoteToolset()
        mock_device = MockDevice()

        with patch("agentsh.plugins.builtin.remote.get_device_inventory") as mock_inv:
            mock_inventory = MagicMock()
            mock_inventory.get.return_value = mock_device
            mock_inv.return_value = mock_inventory

            result = toolset._get_device("test-device")

            assert result.success is True
            assert mock_device.hostname in result.output
            assert mock_device.ip in result.output


class TestAddDevice:
    """Tests for _add_device method."""

    def test_duplicate_hostname(self) -> None:
        """Should return error for duplicate hostname."""
        toolset = RemoteToolset()

        with patch("agentsh.plugins.builtin.remote.get_device_inventory") as mock_inv:
            mock_inventory = MagicMock()
            mock_inventory.get_by_hostname.return_value = MockDevice()
            mock_inv.return_value = mock_inventory

            result = toolset._add_device("existing.local")

            assert result.success is False
            assert "already exists" in result.error

    def test_adds_new_device(self) -> None:
        """Should add new device successfully."""
        toolset = RemoteToolset()
        mock_device = MockDevice()

        with patch("agentsh.plugins.builtin.remote.get_device_inventory") as mock_inv:
            mock_inventory = MagicMock()
            mock_inventory.get_by_hostname.return_value = None
            mock_inv.return_value = mock_inventory

            with patch("agentsh.plugins.builtin.remote.create_device") as mock_create:
                mock_create.return_value = mock_device
                with patch("agentsh.plugins.builtin.remote.DeviceType") as mock_type:
                    mock_type.SERVER = "server"

                    result = toolset._add_device("new.local")

                    assert result.success is True
                    mock_inventory.add.assert_called_once()

    def test_handles_add_error(self) -> None:
        """Should handle add error."""
        toolset = RemoteToolset()

        with patch("agentsh.plugins.builtin.remote.get_device_inventory") as mock_inv:
            mock_inventory = MagicMock()
            mock_inventory.get_by_hostname.return_value = None
            mock_inventory.add.side_effect = ValueError("Add failed")
            mock_inv.return_value = mock_inventory

            with patch("agentsh.plugins.builtin.remote.create_device") as mock_create:
                mock_create.return_value = MockDevice()
                with patch("agentsh.plugins.builtin.remote.DeviceType") as mock_type:
                    mock_type.SERVER = "server"

                    result = toolset._add_device("new.local")

                    assert result.success is False


class TestRemoveDevice:
    """Tests for _remove_device method."""

    def test_device_not_found(self) -> None:
        """Should return error if device not found."""
        toolset = RemoteToolset()

        with patch("agentsh.plugins.builtin.remote.get_device_inventory") as mock_inv:
            mock_inventory = MagicMock()
            mock_inventory.remove.return_value = False
            mock_inv.return_value = mock_inventory

            result = toolset._remove_device("nonexistent")

            assert result.success is False
            assert "not found" in result.error

    def test_removes_device(self) -> None:
        """Should remove device successfully."""
        toolset = RemoteToolset()

        with patch("agentsh.plugins.builtin.remote.get_device_inventory") as mock_inv:
            mock_inventory = MagicMock()
            mock_inventory.remove.return_value = True
            mock_inv.return_value = mock_inventory

            result = toolset._remove_device("test-device")

            assert result.success is True
            assert "Removed" in result.output


class TestCheckStatus:
    """Tests for _check_status method."""

    def test_device_not_found(self) -> None:
        """Should return error if device not found."""
        toolset = RemoteToolset()

        with patch("agentsh.plugins.builtin.remote.get_device_inventory") as mock_inv:
            mock_inventory = MagicMock()
            mock_inventory.get.return_value = None
            mock_inv.return_value = mock_inventory

            result = toolset._check_status("nonexistent")

            assert result.success is False
            assert "not found" in result.error

    def test_device_online(self) -> None:
        """Should report device online."""
        toolset = RemoteToolset()
        mock_device = MockDevice()

        with patch("agentsh.plugins.builtin.remote.get_device_inventory") as mock_inv:
            mock_inventory = MagicMock()
            mock_inventory.get.return_value = mock_device
            mock_inv.return_value = mock_inventory

            with patch("agentsh.plugins.builtin.remote.get_ssh_executor") as mock_exec:
                mock_executor = MagicMock()
                mock_executor.execute.return_value = MockCommandResult(
                    success=True,
                    duration_ms=50.0,
                )
                mock_exec.return_value = mock_executor

                with patch("agentsh.plugins.builtin.remote.DeviceStatus") as mock_status:
                    mock_status.ONLINE = "online"
                    result = toolset._check_status("test-device")

                    assert result.success is True
                    assert "online" in result.output.lower()

    def test_device_offline(self) -> None:
        """Should report device offline."""
        toolset = RemoteToolset()
        mock_device = MockDevice()

        with patch("agentsh.plugins.builtin.remote.get_device_inventory") as mock_inv:
            mock_inventory = MagicMock()
            mock_inventory.get.return_value = mock_device
            mock_inv.return_value = mock_inventory

            with patch("agentsh.plugins.builtin.remote.get_ssh_executor") as mock_exec:
                mock_executor = MagicMock()
                mock_executor.execute.return_value = MockCommandResult(
                    success=False,
                    error="Connection refused",
                )
                mock_exec.return_value = mock_executor

                with patch("agentsh.plugins.builtin.remote.DeviceStatus") as mock_status:
                    mock_status.OFFLINE = "offline"
                    result = toolset._check_status("test-device")

                    assert result.success is False
                    assert "offline" in result.output.lower()


class TestFleetStatus:
    """Tests for _fleet_status method."""

    def test_empty_inventory(self) -> None:
        """Should handle empty inventory."""
        toolset = RemoteToolset()

        with patch("agentsh.plugins.builtin.remote.get_device_inventory") as mock_inv:
            mock_inventory = MagicMock()
            mock_inventory.list.return_value = []
            mock_inv.return_value = mock_inventory

            result = toolset._fleet_status()

            assert result.success is True
            assert "No devices" in result.output

    def test_returns_status_summary(self) -> None:
        """Should return fleet status summary."""
        toolset = RemoteToolset()
        mock_device = MockDevice()

        with patch("agentsh.plugins.builtin.remote.get_device_inventory") as mock_inv:
            mock_inventory = MagicMock()
            mock_inventory.list.return_value = [mock_device]
            mock_status = MagicMock()
            mock_status.value = "online"
            mock_inventory.count_by_status.return_value = {mock_status: 1}
            mock_inventory.count.return_value = 1
            mock_inv.return_value = mock_inventory

            result = toolset._fleet_status()

            assert result.success is True
            assert "Fleet Status" in result.output

    def test_checks_connectivity_when_requested(self) -> None:
        """Should check connectivity when check_connectivity is True."""
        toolset = RemoteToolset()
        mock_device = MockDevice()

        with patch("agentsh.plugins.builtin.remote.get_device_inventory") as mock_inv:
            mock_inventory = MagicMock()
            mock_inventory.list.return_value = [mock_device]
            mock_status = MagicMock()
            mock_status.value = "online"
            mock_inventory.count_by_status.return_value = {mock_status: 1}
            mock_inventory.count.return_value = 1
            mock_inv.return_value = mock_inventory

            with patch("agentsh.plugins.builtin.remote.get_ssh_executor") as mock_exec:
                mock_executor = MagicMock()
                mock_executor.execute.return_value = MockCommandResult(success=True)
                mock_exec.return_value = mock_executor

                with patch("agentsh.plugins.builtin.remote.DeviceStatus") as mock_status_enum:
                    mock_status_enum.ONLINE = "online"
                    toolset._fleet_status(check_connectivity=True)

                    mock_executor.execute.assert_called()


class TestFormatResult:
    """Tests for _format_result method."""

    def test_formats_successful_result(self) -> None:
        """Should format successful result."""
        toolset = RemoteToolset()
        cmd_result = MockCommandResult(
            success=True,
            stdout="output here",
            exit_code=0,
            duration_ms=123.4,
        )

        formatted = toolset._format_result(cmd_result)

        assert "Exit Code: 0" in formatted
        assert "Duration: 123.4ms" in formatted
        assert "output here" in formatted

    def test_includes_stderr(self) -> None:
        """Should include stderr if present."""
        toolset = RemoteToolset()
        cmd_result = MockCommandResult(
            success=False,
            stderr="error output",
            exit_code=1,
        )

        formatted = toolset._format_result(cmd_result)

        assert "Stderr:" in formatted
        assert "error output" in formatted

    def test_handles_empty_output(self) -> None:
        """Should handle empty output."""
        toolset = RemoteToolset()
        cmd_result = MockCommandResult(
            success=True,
            stdout="",
            stderr="",
        )

        formatted = toolset._format_result(cmd_result)

        assert "Device:" in formatted
        assert "Exit Code:" in formatted
