"""Tests for SSH executor."""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentsh.orchestrator.ssh import (
    CommandResult,
    ParallelResult,
    SSHConnection,
    SSHConnectionPool,
    SSHCredentials,
    SSHExecutor,
    get_ssh_executor,
    set_ssh_executor,
)
from agentsh.orchestrator.devices import (
    Device,
    DeviceStatus,
    DeviceType,
)


class TestCommandResult:
    """Tests for CommandResult dataclass."""

    def test_create_success_result(self):
        """Should create successful result."""
        result = CommandResult(
            device_id="server-1",
            command="echo hello",
            exit_code=0,
            stdout="Hello, world!",
            stderr="",
            duration_ms=150.5,
            success=True,
        )
        assert result.success is True
        assert result.exit_code == 0
        assert result.stdout == "Hello, world!"
        assert result.duration_ms == 150.5
        assert result.error is None
        assert result.device_id == "server-1"
        assert result.command == "echo hello"

    def test_create_failure_result(self):
        """Should create failure result."""
        result = CommandResult(
            device_id="server-1",
            command="bad_cmd",
            exit_code=1,
            stdout="",
            stderr="Command not found",
            duration_ms=50.0,
            success=False,
            error="Non-zero exit code",
        )
        assert result.success is False
        assert result.exit_code == 1
        assert result.stderr == "Command not found"
        assert result.error == "Non-zero exit code"

    def test_to_dict(self):
        """Should convert to dictionary."""
        result = CommandResult(
            device_id="server-1",
            command="echo test",
            exit_code=0,
            stdout="output",
            stderr="",
            duration_ms=100.0,
            success=True,
        )
        d = result.to_dict()
        assert d["success"] is True
        assert d["exit_code"] == 0
        assert d["stdout"] == "output"
        assert d["duration_ms"] == 100.0
        assert d["device_id"] == "server-1"
        assert d["command"] == "echo test"


class TestSSHCredentials:
    """Tests for SSHCredentials dataclass."""

    def test_default_values(self):
        """Should have sensible defaults."""
        creds = SSHCredentials()
        assert creds.username == "root"
        assert creds.password is None
        assert creds.private_key_path is None
        assert creds.private_key_passphrase is None

    def test_custom_values(self):
        """Should accept custom values."""
        creds = SSHCredentials(
            username="deploy",
            private_key_path=Path("/home/user/.ssh/id_rsa"),
        )
        assert creds.username == "deploy"
        assert creds.private_key_path == Path("/home/user/.ssh/id_rsa")

    def test_from_env(self):
        """Should load from environment variables."""
        with patch.dict(
            "os.environ",
            {
                "SSH_USER": "testuser",
                "SSH_KEY": "/path/to/key",
            },
        ):
            creds = SSHCredentials.from_env()
            assert creds.username == "testuser"
            assert creds.private_key_path == Path("/path/to/key").expanduser()

    def test_from_env_defaults(self):
        """Should use defaults when env vars not set."""
        with patch.dict("os.environ", {}, clear=True):
            creds = SSHCredentials.from_env()
            assert creds.username == "root"


class TestSSHConnection:
    """Tests for SSHConnection."""

    @pytest.fixture
    def sample_device(self):
        """Create a sample device."""
        return Device(
            id="server-1",
            hostname="server.local",
            device_type=DeviceType.SERVER,
            status=DeviceStatus.ONLINE,
        )

    def test_create_connection_requires_paramiko(self, sample_device):
        """Should require paramiko to create connection."""
        with patch("agentsh.orchestrator.ssh.PARAMIKO_AVAILABLE", False):
            with pytest.raises(ImportError, match="paramiko"):
                SSHConnection(sample_device, SSHCredentials())

    def test_is_connected_false_initially(self, sample_device):
        """Should not be connected initially."""
        with patch("agentsh.orchestrator.ssh.PARAMIKO_AVAILABLE", True):
            with patch("agentsh.orchestrator.ssh.paramiko"):
                conn = SSHConnection(sample_device, SSHCredentials())
                assert conn.is_connected is False


class TestSSHConnectionPool:
    """Tests for SSHConnectionPool."""

    @pytest.fixture
    def pool(self):
        """Create a connection pool."""
        creds = SSHCredentials()
        return SSHConnectionPool(creds, max_connections_per_device=5)

    def test_create_pool(self, pool):
        """Should create pool with max connections."""
        assert pool.max_connections == 5

    def test_close_all(self, pool):
        """Should close all connections."""
        pool.close_all()
        assert len(pool._pools) == 0


class TestParallelResult:
    """Tests for ParallelResult dataclass."""

    def test_create_result(self):
        """Should create parallel result."""
        results = {
            "server-1": CommandResult(
                device_id="server-1",
                command="echo ok",
                exit_code=0,
                stdout="OK",
                stderr="",
                duration_ms=100.0,
                success=True,
            ),
            "server-2": CommandResult(
                device_id="server-2",
                command="echo fail",
                exit_code=1,
                stdout="",
                stderr="Error",
                duration_ms=50.0,
                success=False,
            ),
        }
        parallel = ParallelResult(
            results=results,
            total_devices=2,
            successful=1,
            failed=1,
            duration_ms=150.0,
        )
        assert len(parallel.results) == 2
        assert parallel.successful == 1
        assert parallel.failed == 1

    def test_to_dict(self):
        """Should convert to dictionary."""
        results = {
            "server-1": CommandResult(
                device_id="server-1",
                command="echo ok",
                exit_code=0,
                stdout="OK",
                stderr="",
                duration_ms=100.0,
                success=True,
            ),
        }
        parallel = ParallelResult(
            results=results,
            total_devices=1,
            successful=1,
            failed=0,
            duration_ms=100.0,
        )
        d = parallel.to_dict()
        assert d["successful"] == 1
        assert d["failed"] == 0
        assert "server-1" in d["results"]


class TestSSHExecutor:
    """Tests for SSHExecutor."""

    @pytest.fixture
    def sample_device(self):
        """Create a sample device."""
        return Device(
            id="server-1",
            hostname="server.local",
            device_type=DeviceType.SERVER,
            status=DeviceStatus.ONLINE,
        )

    @pytest.fixture
    def executor(self):
        """Create an SSH executor."""
        return SSHExecutor()

    def test_create_executor(self, executor):
        """Should create executor instance."""
        assert executor is not None
        assert executor.max_concurrent == 10

    def test_execute_parallel_empty_list(self, executor):
        """Should handle empty device list."""
        result = executor.execute_parallel([], "echo hello")
        assert result.successful == 0
        assert result.failed == 0
        assert len(result.results) == 0

    def test_close(self, executor):
        """Should close executor cleanly."""
        executor.close()
        # Should not raise


class TestSSHExecutorSingleton:
    """Tests for global SSH executor."""

    def test_get_set_executor(self):
        """Should get and set global executor."""
        executor = SSHExecutor()
        set_ssh_executor(executor)
        assert get_ssh_executor() is executor

    def test_get_creates_default(self):
        """Should create default executor if not set."""
        set_ssh_executor(None)
        executor = get_ssh_executor()
        assert executor is not None
        assert isinstance(executor, SSHExecutor)


class TestSSHConnectionExtended:
    """Extended tests for SSHConnection."""

    @pytest.fixture
    def sample_device(self):
        """Create a sample device."""
        return Device(
            id="server-1",
            hostname="server.local",
            ip="192.168.1.100",
            device_type=DeviceType.SERVER,
            status=DeviceStatus.ONLINE,
        )

    @pytest.fixture
    def mock_paramiko(self):
        """Mock paramiko module."""
        with patch("agentsh.orchestrator.ssh.PARAMIKO_AVAILABLE", True):
            with patch("agentsh.orchestrator.ssh.paramiko") as mock:
                yield mock

    def test_connect_with_key(self, sample_device, mock_paramiko):
        """Should connect using SSH key."""
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()

        creds = SSHCredentials(
            username="deploy",
            private_key_path=Path("/tmp/test_key"),
        )

        with patch.object(Path, "exists", return_value=True):
            conn = SSHConnection(sample_device, creds)
            conn.connect()

            mock_client.connect.assert_called_once()
            call_kwargs = mock_client.connect.call_args.kwargs
            assert call_kwargs["username"] == "deploy"
            assert "/tmp/test_key" in call_kwargs["key_filename"]

    def test_connect_with_password(self, sample_device, mock_paramiko):
        """Should connect using password."""
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()

        creds = SSHCredentials(
            username="admin",
            password="secret123",
        )

        conn = SSHConnection(sample_device, creds)
        conn.connect()

        mock_client.connect.assert_called_once()
        call_kwargs = mock_client.connect.call_args.kwargs
        assert call_kwargs["password"] == "secret123"

    def test_connect_with_agent(self, sample_device, mock_paramiko):
        """Should connect using SSH agent."""
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()

        creds = SSHCredentials(username="user")

        conn = SSHConnection(sample_device, creds)
        conn.connect()

        mock_client.connect.assert_called_once()
        call_kwargs = mock_client.connect.call_args.kwargs
        assert call_kwargs["allow_agent"] is True

    def test_connect_failure(self, sample_device, mock_paramiko):
        """Should raise ConnectionError on failure."""
        mock_client = MagicMock()
        mock_client.connect.side_effect = Exception("Connection refused")
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()

        creds = SSHCredentials(username="user")
        conn = SSHConnection(sample_device, creds)

        with pytest.raises(ConnectionError, match="Connection refused"):
            conn.connect()

    def test_execute_command(self, sample_device, mock_paramiko):
        """Should execute command and return result."""
        mock_client = MagicMock()
        mock_stdin = MagicMock()
        mock_stdout = MagicMock()
        mock_stderr = MagicMock()

        mock_stdout.read.return_value = b"Hello World"
        mock_stderr.read.return_value = b""
        mock_stdout.channel.recv_exit_status.return_value = 0

        mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
        mock_client.get_transport.return_value.is_active.return_value = True
        mock_paramiko.SSHClient.return_value = mock_client
        mock_paramiko.AutoAddPolicy.return_value = MagicMock()

        creds = SSHCredentials(username="user")
        conn = SSHConnection(sample_device, creds)
        conn._connected = True
        conn._client = mock_client

        result = conn.execute("echo Hello World")

        assert result.success is True
        assert result.stdout == "Hello World"
        assert result.exit_code == 0

    def test_execute_with_environment(self, sample_device, mock_paramiko):
        """Should execute command with environment variables."""
        mock_client = MagicMock()
        mock_stdin = MagicMock()
        mock_stdout = MagicMock()
        mock_stderr = MagicMock()

        mock_stdout.read.return_value = b"output"
        mock_stderr.read.return_value = b""
        mock_stdout.channel.recv_exit_status.return_value = 0

        mock_client.exec_command.return_value = (mock_stdin, mock_stdout, mock_stderr)
        mock_client.get_transport.return_value.is_active.return_value = True
        mock_paramiko.SSHClient.return_value = mock_client

        creds = SSHCredentials(username="user")
        conn = SSHConnection(sample_device, creds)
        conn._connected = True
        conn._client = mock_client

        result = conn.execute("printenv", environment={"MY_VAR": "value"})

        # Command should include env prefix
        call_args = mock_client.exec_command.call_args
        assert "MY_VAR=value" in call_args[0][0]

    def test_execute_failure(self, sample_device, mock_paramiko):
        """Should handle execution failure."""
        mock_client = MagicMock()
        mock_client.exec_command.side_effect = Exception("Timeout")
        mock_client.get_transport.return_value.is_active.return_value = True
        mock_paramiko.SSHClient.return_value = mock_client

        creds = SSHCredentials(username="user")
        conn = SSHConnection(sample_device, creds)
        conn._connected = True
        conn._client = mock_client

        result = conn.execute("slow_command")

        assert result.success is False
        assert result.error == "Timeout"
        assert result.exit_code == -1

    def test_close_connection(self, sample_device, mock_paramiko):
        """Should close connection."""
        mock_client = MagicMock()
        mock_paramiko.SSHClient.return_value = mock_client

        creds = SSHCredentials(username="user")
        conn = SSHConnection(sample_device, creds)
        conn._client = mock_client
        conn._connected = True

        conn.close()

        mock_client.close.assert_called_once()
        assert conn._connected is False

    def test_is_connected_checks_transport(self, sample_device, mock_paramiko):
        """Should check transport is active."""
        mock_client = MagicMock()
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = True
        mock_client.get_transport.return_value = mock_transport
        mock_paramiko.SSHClient.return_value = mock_client

        creds = SSHCredentials(username="user")
        conn = SSHConnection(sample_device, creds)
        conn._client = mock_client

        assert conn.is_connected is True

    def test_is_connected_false_when_transport_inactive(self, sample_device, mock_paramiko):
        """Should return False when transport is inactive."""
        mock_client = MagicMock()
        mock_transport = MagicMock()
        mock_transport.is_active.return_value = False
        mock_client.get_transport.return_value = mock_transport
        mock_paramiko.SSHClient.return_value = mock_client

        creds = SSHCredentials(username="user")
        conn = SSHConnection(sample_device, creds)
        conn._client = mock_client

        assert conn.is_connected is False


class TestSSHConnectionPoolExtended:
    """Extended tests for SSHConnectionPool."""

    @pytest.fixture
    def sample_device(self):
        """Create a sample device."""
        return Device(
            id="server-1",
            hostname="server.local",
            device_type=DeviceType.SERVER,
            status=DeviceStatus.ONLINE,
        )

    @pytest.fixture
    def pool(self):
        """Create a connection pool."""
        creds = SSHCredentials()
        return SSHConnectionPool(creds, max_connections_per_device=3)

    def test_get_connection_creates_new(self, pool, sample_device):
        """Should create new connection for new device."""
        with patch("agentsh.orchestrator.ssh.PARAMIKO_AVAILABLE", True):
            with patch("agentsh.orchestrator.ssh.paramiko"):
                conn = pool.get_connection(sample_device)
                assert conn is not None
                assert sample_device.id in pool._pools

    def test_get_connection_reuses_active(self, pool, sample_device):
        """Should reuse active connection."""
        with patch("agentsh.orchestrator.ssh.PARAMIKO_AVAILABLE", True):
            with patch("agentsh.orchestrator.ssh.paramiko"):
                conn1 = pool.get_connection(sample_device)
                conn1._connected = True

                # Mock is_connected to return True
                with patch.object(SSHConnection, "is_connected", True):
                    conn2 = pool.get_connection(sample_device)
                    assert conn2 is conn1

    def test_get_connection_with_custom_credentials(self, pool, sample_device):
        """Should use custom credentials."""
        custom_creds = SSHCredentials(username="custom")

        with patch("agentsh.orchestrator.ssh.PARAMIKO_AVAILABLE", True):
            with patch("agentsh.orchestrator.ssh.paramiko"):
                conn = pool.get_connection(sample_device, credentials=custom_creds)
                assert conn.credentials.username == "custom"

    def test_close_device(self, pool, sample_device):
        """Should close all connections for a device."""
        with patch("agentsh.orchestrator.ssh.PARAMIKO_AVAILABLE", True):
            with patch("agentsh.orchestrator.ssh.paramiko"):
                pool.get_connection(sample_device)
                pool.close_device(sample_device.id)
                assert sample_device.id not in pool._pools

    def test_release_connection(self, pool, sample_device):
        """Should release connection (no-op for now)."""
        pool.release_connection(sample_device)  # Should not raise


class TestSSHExecutorExtended:
    """Extended tests for SSHExecutor."""

    @pytest.fixture
    def sample_device(self):
        """Create a sample device."""
        from agentsh.orchestrator.devices import ConnectionMethod, ConnectionConfig

        return Device(
            id="server-1",
            hostname="server.local",
            device_type=DeviceType.SERVER,
            status=DeviceStatus.ONLINE,
            connection=ConnectionConfig(method=ConnectionMethod.SSH, port=22),
        )

    @pytest.fixture
    def non_ssh_device(self):
        """Create a non-SSH device."""
        from agentsh.orchestrator.devices import ConnectionMethod, ConnectionConfig

        return Device(
            id="local-1",
            hostname="localhost",
            device_type=DeviceType.WORKSTATION,
            status=DeviceStatus.ONLINE,
            connection=ConnectionConfig(method=ConnectionMethod.LOCAL),
        )

    def test_execute_non_ssh_device(self, non_ssh_device):
        """Should fail for non-SSH device."""
        executor = SSHExecutor()
        result = executor.execute(non_ssh_device, "echo hello")

        assert result.success is False
        assert "not SSH" in result.error

    def test_execute_with_custom_timeout(self, sample_device):
        """Should use custom timeout."""
        executor = SSHExecutor(command_timeout=120.0)

        with patch.object(SSHConnectionPool, "get_connection") as mock_get:
            mock_conn = MagicMock()
            mock_conn.execute.return_value = CommandResult(
                device_id="server-1",
                command="slow",
                exit_code=0,
                stdout="done",
                stderr="",
                duration_ms=100,
                success=True,
            )
            mock_get.return_value = mock_conn

            executor.execute(sample_device, "slow", timeout=60.0)

            mock_conn.execute.assert_called_with(
                "slow",
                timeout=60.0,
                environment=None,
            )

    def test_execute_parallel_with_multiple_devices(self):
        """Should execute on multiple devices."""
        from agentsh.orchestrator.devices import ConnectionMethod, ConnectionConfig

        devices = [
            Device(
                id=f"server-{i}",
                hostname=f"server{i}.local",
                device_type=DeviceType.SERVER,
                status=DeviceStatus.ONLINE,
                connection=ConnectionConfig(method=ConnectionMethod.SSH),
            )
            for i in range(3)
        ]

        executor = SSHExecutor()

        with patch.object(SSHExecutor, "execute") as mock_execute:
            mock_execute.return_value = CommandResult(
                device_id="test",
                command="uptime",
                exit_code=0,
                stdout="up",
                stderr="",
                duration_ms=50,
                success=True,
            )

            result = executor.execute_parallel(devices, "uptime")

            assert result.total_devices == 3
            assert mock_execute.call_count == 3

    def test_execute_parallel_with_max_concurrent(self):
        """Should respect max_concurrent limit."""
        from agentsh.orchestrator.devices import ConnectionMethod, ConnectionConfig

        devices = [
            Device(
                id=f"server-{i}",
                hostname=f"server{i}.local",
                device_type=DeviceType.SERVER,
                status=DeviceStatus.ONLINE,
                connection=ConnectionConfig(method=ConnectionMethod.SSH),
            )
            for i in range(5)
        ]

        executor = SSHExecutor(max_concurrent=2)

        with patch.object(SSHExecutor, "execute") as mock_execute:
            mock_execute.return_value = CommandResult(
                device_id="test",
                command="uptime",
                exit_code=0,
                stdout="up",
                stderr="",
                duration_ms=50,
                success=True,
            )

            result = executor.execute_parallel(devices, "uptime", max_concurrent=2)

            assert result.total_devices == 5

    @pytest.mark.asyncio
    async def test_execute_async(self, sample_device):
        """Should execute asynchronously."""
        executor = SSHExecutor()

        with patch.object(SSHExecutor, "execute") as mock_execute:
            mock_execute.return_value = CommandResult(
                device_id="server-1",
                command="hostname",
                exit_code=0,
                stdout="server",
                stderr="",
                duration_ms=50,
                success=True,
            )

            result = await executor.execute_async(sample_device, "hostname")

            assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_parallel_async(self):
        """Should execute parallel asynchronously."""
        from agentsh.orchestrator.devices import ConnectionMethod, ConnectionConfig

        devices = [
            Device(
                id=f"server-{i}",
                hostname=f"server{i}.local",
                device_type=DeviceType.SERVER,
                status=DeviceStatus.ONLINE,
                connection=ConnectionConfig(method=ConnectionMethod.SSH),
            )
            for i in range(2)
        ]

        executor = SSHExecutor()

        with patch.object(SSHExecutor, "execute_async") as mock_execute:
            mock_execute.return_value = CommandResult(
                device_id="test",
                command="uptime",
                exit_code=0,
                stdout="up",
                stderr="",
                duration_ms=50,
                success=True,
            )

            result = await executor.execute_parallel_async(devices, "uptime")

            assert result.total_devices == 2


class TestSSHCredentialsExtended:
    """Extended tests for SSHCredentials."""

    def test_from_env_with_custom_prefix(self):
        """Should use custom prefix for env vars."""
        with patch.dict(
            "os.environ",
            {
                "DEPLOY_USER": "deployer",
                "DEPLOY_PASSWORD": "pass123",
                "DEPLOY_KEY": "/deploy/key",
                "DEPLOY_KEY_PASSPHRASE": "secret",
            },
        ):
            creds = SSHCredentials.from_env(prefix="DEPLOY")
            assert creds.username == "deployer"
            assert creds.password == "pass123"
            assert creds.private_key_passphrase == "secret"

    def test_from_env_no_key_path(self):
        """Should handle missing key path."""
        with patch.dict("os.environ", {"SSH_USER": "user"}, clear=True):
            creds = SSHCredentials.from_env()
            assert creds.private_key_path is None
