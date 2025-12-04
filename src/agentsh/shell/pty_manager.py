"""PTY Manager - Manages pseudo-terminal for shell subprocess."""

import os
import signal
import shutil
from pathlib import Path
from typing import Optional

import ptyprocess

from agentsh.telemetry.logger import get_logger, LoggerMixin

logger = get_logger(__name__)


class PTYManager(LoggerMixin):
    """Manages a pseudo-terminal with a shell subprocess.

    This class handles:
    - Spawning a shell process in a PTY
    - Reading/writing to the PTY
    - Terminal size management
    - Graceful shutdown

    Example:
        pty = PTYManager(shell_path="/bin/zsh")
        pty.spawn()
        pty.write(b"ls -la\\n")
        output = pty.read(timeout=1.0)
        pty.close()
    """

    def __init__(
        self,
        shell_path: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
        cwd: Optional[Path] = None,
        dimensions: Optional[tuple[int, int]] = None,
    ) -> None:
        """Initialize PTY manager.

        Args:
            shell_path: Path to shell executable. Auto-detected if None.
            env: Environment variables for the shell. Uses current env if None.
            cwd: Working directory for the shell. Uses current dir if None.
            dimensions: Terminal dimensions (rows, cols). Auto-detected if None.
        """
        self.shell_path = shell_path or self._detect_shell()
        self.env = env or dict(os.environ)
        self.cwd = str(cwd) if cwd else os.getcwd()
        self.dimensions = dimensions or self._get_terminal_size()

        self._process: Optional[ptyprocess.PtyProcess] = None
        self._original_sigwinch: Optional[signal.Handlers] = None

    def _detect_shell(self) -> str:
        """Detect the user's preferred shell."""
        # Try SHELL environment variable first
        shell = os.environ.get("SHELL")
        if shell and shutil.which(shell):
            return shell

        # Fall back to common shells
        for shell_name in ["zsh", "bash", "fish", "sh"]:
            shell_path = shutil.which(shell_name)
            if shell_path:
                return shell_path

        raise RuntimeError("Could not find a suitable shell")

    def _get_terminal_size(self) -> tuple[int, int]:
        """Get current terminal size."""
        try:
            size = os.get_terminal_size()
            return (size.lines, size.columns)
        except OSError:
            # Default size if not in a terminal
            return (24, 80)

    def spawn(self) -> None:
        """Spawn the shell process in a PTY.

        Raises:
            RuntimeError: If already spawned or spawn fails
        """
        if self._process is not None:
            raise RuntimeError("PTY already spawned")

        self.logger.info(
            "Spawning shell",
            shell=self.shell_path,
            cwd=self.cwd,
            dimensions=self.dimensions,
        )

        try:
            self._process = ptyprocess.PtyProcess.spawn(
                [self.shell_path, "-i"],  # -i for interactive
                cwd=self.cwd,
                env=self.env,
                dimensions=self.dimensions,
            )

            # Set up SIGWINCH handler for terminal resize
            self._setup_sigwinch_handler()

            self.logger.debug("Shell spawned", pid=self._process.pid)

        except Exception as e:
            self.logger.error("Failed to spawn shell", error=str(e))
            raise RuntimeError(f"Failed to spawn shell: {e}") from e

    def _setup_sigwinch_handler(self) -> None:
        """Set up handler for terminal resize signals."""
        try:
            self._original_sigwinch = signal.signal(
                signal.SIGWINCH, self._handle_sigwinch
            )
        except (ValueError, OSError):
            # Signal handling may not work in all contexts
            pass

    def _handle_sigwinch(self, signum: int, frame: object) -> None:
        """Handle terminal resize signal."""
        if self._process is not None and self._process.isalive():
            new_size = self._get_terminal_size()
            self.resize(new_size[0], new_size[1])

    def resize(self, rows: int, cols: int) -> None:
        """Resize the PTY.

        Args:
            rows: Number of rows
            cols: Number of columns
        """
        if self._process is not None and self._process.isalive():
            self._process.setwinsize(rows, cols)
            self.dimensions = (rows, cols)
            self.logger.debug("PTY resized", rows=rows, cols=cols)

    def read(self, size: int = 1024, timeout: Optional[float] = None) -> bytes:
        """Read data from the PTY.

        Args:
            size: Maximum bytes to read
            timeout: Read timeout in seconds. None for blocking read.

        Returns:
            Bytes read from PTY

        Raises:
            RuntimeError: If PTY not spawned
            EOFError: If shell has exited
        """
        if self._process is None:
            raise RuntimeError("PTY not spawned")

        if not self._process.isalive():
            raise EOFError("Shell has exited")

        try:
            if timeout is not None:
                # Use read with timeout
                import select

                ready, _, _ = select.select([self._process.fd], [], [], timeout)
                if not ready:
                    return b""

            return self._process.read(size)

        except EOFError:
            raise
        except Exception as e:
            self.logger.error("Read error", error=str(e))
            raise

    def read_nonblocking(self, size: int = 1024) -> bytes:
        """Read data from PTY without blocking.

        Args:
            size: Maximum bytes to read

        Returns:
            Bytes read, or empty bytes if nothing available
        """
        return self.read(size, timeout=0.0)

    def write(self, data: bytes) -> int:
        """Write data to the PTY.

        Args:
            data: Bytes to write

        Returns:
            Number of bytes written

        Raises:
            RuntimeError: If PTY not spawned
        """
        if self._process is None:
            raise RuntimeError("PTY not spawned")

        if not self._process.isalive():
            raise EOFError("Shell has exited")

        try:
            self._process.write(data)
            return len(data)
        except Exception as e:
            self.logger.error("Write error", error=str(e))
            raise

    def write_line(self, line: str) -> int:
        """Write a line to the PTY (adds newline).

        Args:
            line: String to write

        Returns:
            Number of bytes written
        """
        return self.write((line + "\n").encode())

    def send_signal(self, sig: int) -> None:
        """Send a signal to the shell process.

        Args:
            sig: Signal number (e.g., signal.SIGINT)
        """
        if self._process is not None and self._process.isalive():
            self._process.kill(sig)

    def interrupt(self) -> None:
        """Send interrupt signal (Ctrl+C) to the shell."""
        self.send_signal(signal.SIGINT)

    def send_eof(self) -> None:
        """Send EOF (Ctrl+D) to the shell."""
        if self._process is not None:
            self._process.sendeof()

    @property
    def is_alive(self) -> bool:
        """Check if the shell process is still running."""
        return self._process is not None and self._process.isalive()

    @property
    def pid(self) -> Optional[int]:
        """Get the shell process PID."""
        return self._process.pid if self._process else None

    @property
    def exit_status(self) -> Optional[int]:
        """Get the shell exit status (None if still running)."""
        if self._process is None:
            return None
        if self._process.isalive():
            return None
        return self._process.exitstatus

    def close(self, force: bool = False) -> None:
        """Close the PTY and terminate the shell.

        Args:
            force: If True, send SIGKILL immediately. Otherwise try SIGTERM first.
        """
        if self._process is None:
            return

        self.logger.debug("Closing PTY", pid=self._process.pid, force=force)

        # Restore original SIGWINCH handler
        if self._original_sigwinch is not None:
            try:
                signal.signal(signal.SIGWINCH, self._original_sigwinch)
            except (ValueError, OSError):
                pass

        if self._process.isalive():
            if force:
                self._process.kill(signal.SIGKILL)
            else:
                # Try graceful shutdown
                self._process.terminate(force=False)

                # Wait briefly for termination
                try:
                    self._process.wait()
                except Exception:
                    # Force kill if graceful shutdown fails
                    self._process.terminate(force=True)

        self._process = None
        self.logger.info("PTY closed")

    def __enter__(self) -> "PTYManager":
        """Context manager entry."""
        self.spawn()
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        """Context manager exit."""
        self.close()
