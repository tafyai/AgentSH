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
