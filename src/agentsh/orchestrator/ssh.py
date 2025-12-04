"""SSH execution for remote device operations.

Provides SSH-based command execution with connection pooling,
parallel execution, and proper error handling.
"""

import asyncio
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from agentsh.orchestrator.devices import ConnectionMethod, Device, DeviceStatus
from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)

# Try to import paramiko, but make it optional
try:
    import paramiko

    PARAMIKO_AVAILABLE = True
except ImportError:
    PARAMIKO_AVAILABLE = False
    paramiko = None  # type: ignore


@dataclass
class CommandResult:
    """Result of a remote command execution.

    Attributes:
        device_id: ID of the device where command ran
        command: Command that was executed
        exit_code: Command exit code
        stdout: Standard output
        stderr: Standard error
        duration_ms: Execution duration in milliseconds
        success: Whether command succeeded (exit_code == 0)
        error: Error message if execution failed
        timestamp: When command was executed
    """

    device_id: str
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    success: bool
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "device_id": self.device_id,
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class SSHCredentials:
    """SSH credentials for authentication.

    Attributes:
        username: SSH username
        password: Password (optional, prefer key-based auth)
        private_key_path: Path to private key file
        private_key_passphrase: Passphrase for encrypted key
    """

    username: str = "root"
    password: Optional[str] = None
    private_key_path: Optional[Path] = None
    private_key_passphrase: Optional[str] = None

    @classmethod
    def from_env(cls, prefix: str = "SSH") -> "SSHCredentials":
        """Load credentials from environment variables.

        Args:
            prefix: Environment variable prefix

        Returns:
            SSHCredentials instance
        """
        return cls(
            username=os.environ.get(f"{prefix}_USER", "root"),
            password=os.environ.get(f"{prefix}_PASSWORD"),
            private_key_path=Path(os.environ.get(f"{prefix}_KEY", "~/.ssh/id_rsa")).expanduser()
            if os.environ.get(f"{prefix}_KEY")
            else None,
            private_key_passphrase=os.environ.get(f"{prefix}_KEY_PASSPHRASE"),
        )


class SSHConnection:
    """Manages an SSH connection to a device.

    Provides connection establishment, command execution,
    and connection lifecycle management.

    Example:
        conn = SSHConnection(device, credentials)
        conn.connect()
        result = conn.execute("ls -la")
        conn.close()
    """

    def __init__(
        self,
        device: Device,
        credentials: SSHCredentials,
        timeout: float = 30.0,
    ) -> None:
        """Initialize SSH connection.

        Args:
            device: Target device
            credentials: SSH credentials
            timeout: Connection timeout in seconds
        """
        if not PARAMIKO_AVAILABLE:
            raise ImportError(
                "paramiko is required for SSH connections. "
                "Install it with: pip install paramiko"
            )

        self.device = device
        self.credentials = credentials
        self.timeout = timeout
        self._client: Optional["paramiko.SSHClient"] = None
        self._lock = threading.Lock()
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Check if connection is active."""
        if not self._client:
            return False
        try:
            transport = self._client.get_transport()
            return transport is not None and transport.is_active()
        except Exception:
            return False

    def connect(self) -> None:
        """Establish SSH connection.

        Raises:
            ConnectionError: If connection fails
        """
        with self._lock:
            if self._connected and self.is_connected:
                return

            self._client = paramiko.SSHClient()
            self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            host = self.device.ip or self.device.hostname
            port = self.device.connection.port or self.device.port

            try:
                # Try key-based auth first
                if self.credentials.private_key_path:
                    key_path = Path(self.credentials.private_key_path).expanduser()
                    if key_path.exists():
                        self._client.connect(
                            hostname=host,
                            port=port,
                            username=self.credentials.username,
                            key_filename=str(key_path),
                            passphrase=self.credentials.private_key_passphrase,
                            timeout=self.timeout,
                            allow_agent=True,
                            look_for_keys=True,
                        )
                        self._connected = True
                        logger.debug(
                            "SSH connected via key",
                            device_id=self.device.id,
                            host=host,
                        )
                        return

                # Fall back to password auth
                if self.credentials.password:
                    self._client.connect(
                        hostname=host,
                        port=port,
                        username=self.credentials.username,
                        password=self.credentials.password,
                        timeout=self.timeout,
                        allow_agent=True,
                        look_for_keys=True,
                    )
                    self._connected = True
                    logger.debug(
                        "SSH connected via password",
                        device_id=self.device.id,
                        host=host,
                    )
                    return

                # Try with agent/default keys
                self._client.connect(
                    hostname=host,
                    port=port,
                    username=self.credentials.username,
                    timeout=self.timeout,
                    allow_agent=True,
                    look_for_keys=True,
                )
                self._connected = True
                logger.debug(
                    "SSH connected via agent/default keys",
                    device_id=self.device.id,
                    host=host,
                )

            except Exception as e:
                self._connected = False
                logger.error(
                    "SSH connection failed",
                    device_id=self.device.id,
                    host=host,
                    error=str(e),
                )
                raise ConnectionError(f"Failed to connect to {host}: {e}") from e

    def execute(
        self,
        command: str,
        timeout: Optional[float] = None,
        environment: Optional[dict[str, str]] = None,
    ) -> CommandResult:
        """Execute a command on the remote device.

        Args:
            command: Command to execute
            timeout: Command timeout in seconds
            environment: Environment variables to set

        Returns:
            CommandResult with output and status
        """
        if not self.is_connected:
            self.connect()

        start_time = time.perf_counter()
        exec_timeout = timeout or self.timeout

        try:
            # Build environment string if needed
            if environment:
                env_str = " ".join(f"{k}={v}" for k, v in environment.items())
                command = f"env {env_str} {command}"

            stdin, stdout, stderr = self._client.exec_command(
                command,
                timeout=exec_timeout,
            )

            # Read output
            stdout_data = stdout.read().decode("utf-8", errors="replace")
            stderr_data = stderr.read().decode("utf-8", errors="replace")
            exit_code = stdout.channel.recv_exit_status()

            duration_ms = (time.perf_counter() - start_time) * 1000

            logger.debug(
                "SSH command executed",
                device_id=self.device.id,
                command=command[:50],
                exit_code=exit_code,
                duration_ms=duration_ms,
            )

            return CommandResult(
                device_id=self.device.id,
                command=command,
                exit_code=exit_code,
                stdout=stdout_data,
                stderr=stderr_data,
                duration_ms=duration_ms,
                success=exit_code == 0,
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "SSH command failed",
                device_id=self.device.id,
                command=command[:50],
                error=str(e),
            )
            return CommandResult(
                device_id=self.device.id,
                command=command,
                exit_code=-1,
                stdout="",
                stderr="",
                duration_ms=duration_ms,
                success=False,
                error=str(e),
            )

    def close(self) -> None:
        """Close the SSH connection."""
        with self._lock:
            if self._client:
                try:
                    self._client.close()
                except Exception:
                    pass
                self._client = None
            self._connected = False


class SSHConnectionPool:
    """Pool of SSH connections for efficient reuse.

    Manages multiple SSH connections with automatic cleanup
    and connection reuse.

    Example:
        pool = SSHConnectionPool(credentials)
        conn = pool.get_connection(device)
        result = conn.execute("hostname")
        pool.release_connection(device)
    """

    def __init__(
        self,
        credentials: SSHCredentials,
        max_connections_per_device: int = 3,
        connection_timeout: float = 30.0,
    ) -> None:
        """Initialize connection pool.

        Args:
            credentials: Default SSH credentials
            max_connections_per_device: Maximum connections per device
            connection_timeout: Connection timeout in seconds
        """
        self.credentials = credentials
        self.max_connections = max_connections_per_device
        self.timeout = connection_timeout
        self._pools: dict[str, list[SSHConnection]] = {}
        self._lock = threading.Lock()

    def get_connection(
        self,
        device: Device,
        credentials: Optional[SSHCredentials] = None,
    ) -> SSHConnection:
        """Get a connection for a device.

        Args:
            device: Target device
            credentials: Override credentials (optional)

        Returns:
            SSHConnection (may be new or reused)
        """
        with self._lock:
            if device.id not in self._pools:
                self._pools[device.id] = []

            # Try to find an available connection
            pool = self._pools[device.id]
            for conn in pool:
                if conn.is_connected:
                    return conn

            # Create new connection if under limit
            if len(pool) < self.max_connections:
                conn = SSHConnection(
                    device,
                    credentials or self.credentials,
                    self.timeout,
                )
                pool.append(conn)
                return conn

            # Return first connection (may need reconnect)
            return pool[0]

    def release_connection(self, device: Device) -> None:
        """Release a connection back to the pool.

        Args:
            device: Device whose connection to release
        """
        # Connections are kept open for reuse
        pass

    def close_device(self, device_id: str) -> None:
        """Close all connections for a device.

        Args:
            device_id: Device identifier
        """
        with self._lock:
            if device_id in self._pools:
                for conn in self._pools[device_id]:
                    conn.close()
                del self._pools[device_id]

    def close_all(self) -> None:
        """Close all connections in the pool."""
        with self._lock:
            for device_id in list(self._pools.keys()):
                for conn in self._pools[device_id]:
                    conn.close()
            self._pools.clear()


@dataclass
class ParallelResult:
    """Result of parallel execution across multiple devices.

    Attributes:
        results: Individual results by device ID
        total_devices: Number of devices targeted
        successful: Number of successful executions
        failed: Number of failed executions
        duration_ms: Total execution duration
    """

    results: dict[str, CommandResult]
    total_devices: int
    successful: int
    failed: int
    duration_ms: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "results": {k: v.to_dict() for k, v in self.results.items()},
            "total_devices": self.total_devices,
            "successful": self.successful,
            "failed": self.failed,
            "duration_ms": self.duration_ms,
        }


class SSHExecutor:
    """Executes commands on remote devices via SSH.

    Provides single and parallel execution with connection pooling.

    Example:
        executor = SSHExecutor(credentials)

        # Single device
        result = executor.execute(device, "uptime")

        # Multiple devices
        results = executor.execute_parallel(devices, "df -h")
    """

    def __init__(
        self,
        credentials: Optional[SSHCredentials] = None,
        max_concurrent: int = 10,
        connection_timeout: float = 30.0,
        command_timeout: float = 60.0,
    ) -> None:
        """Initialize SSH executor.

        Args:
            credentials: Default SSH credentials
            max_concurrent: Maximum concurrent executions
            connection_timeout: Connection timeout in seconds
            command_timeout: Default command timeout in seconds
        """
        self.credentials = credentials or SSHCredentials.from_env()
        self.max_concurrent = max_concurrent
        self.command_timeout = command_timeout
        self._pool = SSHConnectionPool(
            self.credentials,
            connection_timeout=connection_timeout,
        )

    def execute(
        self,
        device: Device,
        command: str,
        timeout: Optional[float] = None,
        environment: Optional[dict[str, str]] = None,
    ) -> CommandResult:
        """Execute a command on a single device.

        Args:
            device: Target device
            command: Command to execute
            timeout: Command timeout (uses default if not specified)
            environment: Environment variables to set

        Returns:
            CommandResult with output and status
        """
        if device.connection.method != ConnectionMethod.SSH:
            return CommandResult(
                device_id=device.id,
                command=command,
                exit_code=-1,
                stdout="",
                stderr="",
                duration_ms=0,
                success=False,
                error=f"Device uses {device.connection.method.value}, not SSH",
            )

        conn = self._pool.get_connection(device)
        return conn.execute(
            command,
            timeout=timeout or self.command_timeout,
            environment=environment,
        )

    def execute_parallel(
        self,
        devices: list[Device],
        command: str,
        timeout: Optional[float] = None,
        max_concurrent: Optional[int] = None,
        environment: Optional[dict[str, str]] = None,
    ) -> ParallelResult:
        """Execute a command on multiple devices in parallel.

        Args:
            devices: Target devices
            command: Command to execute
            timeout: Command timeout per device
            max_concurrent: Maximum concurrent executions
            environment: Environment variables to set

        Returns:
            ParallelResult with all device results
        """
        start_time = time.perf_counter()
        concurrent = max_concurrent or self.max_concurrent
        results: dict[str, CommandResult] = {}
        semaphore = threading.Semaphore(concurrent)

        def execute_on_device(device: Device) -> None:
            with semaphore:
                results[device.id] = self.execute(
                    device,
                    command,
                    timeout=timeout,
                    environment=environment,
                )

        threads = []
        for device in devices:
            thread = threading.Thread(target=execute_on_device, args=(device,))
            thread.start()
            threads.append(thread)

        for thread in threads:
            thread.join()

        duration_ms = (time.perf_counter() - start_time) * 1000
        successful = sum(1 for r in results.values() if r.success)
        failed = len(results) - successful

        logger.info(
            "Parallel execution completed",
            total_devices=len(devices),
            successful=successful,
            failed=failed,
            duration_ms=duration_ms,
        )

        return ParallelResult(
            results=results,
            total_devices=len(devices),
            successful=successful,
            failed=failed,
            duration_ms=duration_ms,
        )

    async def execute_async(
        self,
        device: Device,
        command: str,
        timeout: Optional[float] = None,
        environment: Optional[dict[str, str]] = None,
    ) -> CommandResult:
        """Execute a command asynchronously.

        Args:
            device: Target device
            command: Command to execute
            timeout: Command timeout
            environment: Environment variables to set

        Returns:
            CommandResult with output and status
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.execute(device, command, timeout, environment),
        )

    async def execute_parallel_async(
        self,
        devices: list[Device],
        command: str,
        timeout: Optional[float] = None,
        max_concurrent: Optional[int] = None,
        environment: Optional[dict[str, str]] = None,
    ) -> ParallelResult:
        """Execute a command on multiple devices asynchronously.

        Args:
            devices: Target devices
            command: Command to execute
            timeout: Command timeout per device
            max_concurrent: Maximum concurrent executions
            environment: Environment variables to set

        Returns:
            ParallelResult with all device results
        """
        start_time = time.perf_counter()
        concurrent = max_concurrent or self.max_concurrent
        semaphore = asyncio.Semaphore(concurrent)
        results: dict[str, CommandResult] = {}

        async def execute_with_semaphore(device: Device) -> None:
            async with semaphore:
                results[device.id] = await self.execute_async(
                    device,
                    command,
                    timeout=timeout,
                    environment=environment,
                )

        await asyncio.gather(*[execute_with_semaphore(d) for d in devices])

        duration_ms = (time.perf_counter() - start_time) * 1000
        successful = sum(1 for r in results.values() if r.success)
        failed = len(results) - successful

        return ParallelResult(
            results=results,
            total_devices=len(devices),
            successful=successful,
            failed=failed,
            duration_ms=duration_ms,
        )

    def close(self) -> None:
        """Close all SSH connections."""
        self._pool.close_all()


# Global executor instance
_executor: Optional[SSHExecutor] = None


def get_ssh_executor() -> SSHExecutor:
    """Get the global SSH executor.

    Returns:
        Global SSHExecutor singleton
    """
    global _executor
    if _executor is None:
        _executor = SSHExecutor()
    return _executor


def set_ssh_executor(executor: SSHExecutor) -> None:
    """Set the global SSH executor.

    Args:
        executor: Executor to use globally
    """
    global _executor
    _executor = executor
