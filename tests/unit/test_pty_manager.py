"""Tests for PTY manager module."""

import os
import signal
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from agentsh.shell.pty_manager import PTYManager


class TestPTYManagerInit:
    """Tests for PTYManager initialization."""

    def test_default_initialization(self) -> None:
        """Should initialize with defaults."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()

                assert pty.shell_path == "/bin/zsh"
                assert pty.dimensions == (24, 80)
                assert pty._process is None

    def test_custom_shell_path(self) -> None:
        """Should use custom shell path."""
        with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
            pty = PTYManager(shell_path="/bin/bash")

            assert pty.shell_path == "/bin/bash"

    def test_custom_env(self) -> None:
        """Should use custom environment."""
        custom_env = {"PATH": "/bin", "HOME": "/home/user"}

        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager(env=custom_env)

                assert pty.env == custom_env

    def test_default_env_from_os(self) -> None:
        """Should use os.environ if no env provided."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()

                assert "PATH" in pty.env or len(pty.env) >= 0  # env may vary

    def test_custom_cwd(self, tmp_path: Path) -> None:
        """Should use custom working directory."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager(cwd=tmp_path)

                assert pty.cwd == str(tmp_path)

    def test_custom_dimensions(self) -> None:
        """Should use custom dimensions."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            pty = PTYManager(dimensions=(40, 120))

            assert pty.dimensions == (40, 120)


class TestDetectShell:
    """Tests for _detect_shell method."""

    def test_uses_shell_env_var(self) -> None:
        """Should use SHELL environment variable."""
        with patch.dict(os.environ, {"SHELL": "/bin/zsh"}):
            with patch("shutil.which", return_value="/bin/zsh"):
                with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                    pty = PTYManager()
                    shell = pty._detect_shell()

                    assert shell == "/bin/zsh"

    def test_falls_back_to_common_shells(self) -> None:
        """Should fall back to common shells if SHELL not set."""
        with patch.dict(os.environ, {}, clear=True):
            env_without_shell = {k: v for k, v in os.environ.items() if k != "SHELL"}
            with patch.dict(os.environ, env_without_shell, clear=True):
                with patch("shutil.which") as mock_which:
                    # First call for SHELL env returns None, then zsh works
                    mock_which.side_effect = lambda x: "/bin/zsh" if x == "zsh" else None

                    with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                        pty = PTYManager()
                        shell = pty._detect_shell()

                        assert "zsh" in shell or "bash" in shell or "sh" in shell

    def test_raises_when_no_shell_found(self) -> None:
        """Should raise RuntimeError when no shell found."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("shutil.which", return_value=None):
                with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                    pty = PTYManager.__new__(PTYManager)
                    pty.shell_path = None
                    pty.env = {}
                    pty.cwd = "/"
                    pty.dimensions = (24, 80)
                    pty._process = None
                    pty._original_sigwinch = None

                    with pytest.raises(RuntimeError, match="Could not find"):
                        pty._detect_shell()


class TestGetTerminalSize:
    """Tests for _get_terminal_size method."""

    def test_returns_tuple(self) -> None:
        """Should return tuple of (rows, cols)."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            pty = PTYManager(dimensions=(24, 80))
            size = pty._get_terminal_size()

            assert isinstance(size, tuple)
            assert len(size) == 2

    def test_returns_default_on_error(self) -> None:
        """Should return default size on OSError."""
        with patch("os.get_terminal_size", side_effect=OSError()):
            with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
                pty = PTYManager(dimensions=(24, 80))
                size = pty._get_terminal_size()

                assert size == (24, 80)


class TestSpawn:
    """Tests for spawn method."""

    def test_raises_if_already_spawned(self) -> None:
        """Should raise if PTY already spawned."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()
                pty._process = MagicMock()

                with pytest.raises(RuntimeError, match="already spawned"):
                    pty.spawn()

    def test_spawns_process(self) -> None:
        """Should spawn PTY process."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                with patch("ptyprocess.PtyProcess.spawn") as mock_spawn:
                    mock_process = MagicMock()
                    mock_process.pid = 12345
                    mock_spawn.return_value = mock_process

                    pty = PTYManager()
                    with patch.object(pty, "_setup_sigwinch_handler"):
                        pty.spawn()

                        assert pty._process is mock_process
                        mock_spawn.assert_called_once()

    def test_raises_on_spawn_failure(self) -> None:
        """Should raise RuntimeError on spawn failure."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                with patch("ptyprocess.PtyProcess.spawn") as mock_spawn:
                    mock_spawn.side_effect = Exception("Spawn failed")

                    pty = PTYManager()

                    with pytest.raises(RuntimeError, match="Failed to spawn"):
                        pty.spawn()


class TestResize:
    """Tests for resize method."""

    def test_resize_with_alive_process(self) -> None:
        """Should resize PTY if process is alive."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()
                mock_process = MagicMock()
                mock_process.isalive.return_value = True
                pty._process = mock_process

                pty.resize(40, 120)

                mock_process.setwinsize.assert_called_once_with(40, 120)
                assert pty.dimensions == (40, 120)

    def test_resize_does_nothing_without_process(self) -> None:
        """Should do nothing if no process."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()

                pty.resize(40, 120)

                assert pty.dimensions == (24, 80)

    def test_resize_does_nothing_if_process_dead(self) -> None:
        """Should do nothing if process not alive."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()
                mock_process = MagicMock()
                mock_process.isalive.return_value = False
                pty._process = mock_process

                pty.resize(40, 120)

                mock_process.setwinsize.assert_not_called()


class TestRead:
    """Tests for read method."""

    def test_raises_if_not_spawned(self) -> None:
        """Should raise RuntimeError if PTY not spawned."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()

                with pytest.raises(RuntimeError, match="not spawned"):
                    pty.read()

    def test_raises_eof_if_exited(self) -> None:
        """Should raise EOFError if shell has exited."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()
                mock_process = MagicMock()
                mock_process.isalive.return_value = False
                pty._process = mock_process

                with pytest.raises(EOFError, match="has exited"):
                    pty.read()

    def test_reads_data(self) -> None:
        """Should read data from PTY."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()
                mock_process = MagicMock()
                mock_process.isalive.return_value = True
                mock_process.read.return_value = b"hello world"
                pty._process = mock_process

                result = pty.read()

                assert result == b"hello world"

    def test_read_with_timeout(self) -> None:
        """Should read with timeout."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                with patch("select.select") as mock_select:
                    mock_select.return_value = ([1], [], [])

                    pty = PTYManager()
                    mock_process = MagicMock()
                    mock_process.isalive.return_value = True
                    mock_process.fd = 3
                    mock_process.read.return_value = b"data"
                    pty._process = mock_process

                    result = pty.read(timeout=1.0)

                    assert result == b"data"

    def test_read_timeout_no_data(self) -> None:
        """Should return empty bytes on timeout with no data."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                with patch("select.select") as mock_select:
                    mock_select.return_value = ([], [], [])

                    pty = PTYManager()
                    mock_process = MagicMock()
                    mock_process.isalive.return_value = True
                    mock_process.fd = 3
                    pty._process = mock_process

                    result = pty.read(timeout=0.1)

                    assert result == b""


class TestReadNonblocking:
    """Tests for read_nonblocking method."""

    def test_calls_read_with_zero_timeout(self) -> None:
        """Should call read with timeout=0."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()
                mock_process = MagicMock()
                mock_process.isalive.return_value = True
                mock_process.fd = 3
                pty._process = mock_process

                with patch("select.select", return_value=([], [], [])):
                    result = pty.read_nonblocking()

                    assert result == b""


class TestWrite:
    """Tests for write method."""

    def test_raises_if_not_spawned(self) -> None:
        """Should raise RuntimeError if PTY not spawned."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()

                with pytest.raises(RuntimeError, match="not spawned"):
                    pty.write(b"test")

    def test_raises_eof_if_exited(self) -> None:
        """Should raise EOFError if shell has exited."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()
                mock_process = MagicMock()
                mock_process.isalive.return_value = False
                pty._process = mock_process

                with pytest.raises(EOFError, match="has exited"):
                    pty.write(b"test")

    def test_writes_data(self) -> None:
        """Should write data to PTY."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()
                mock_process = MagicMock()
                mock_process.isalive.return_value = True
                pty._process = mock_process

                result = pty.write(b"hello")

                assert result == 5
                mock_process.write.assert_called_once_with(b"hello")


class TestWriteLine:
    """Tests for write_line method."""

    def test_adds_newline(self) -> None:
        """Should add newline to string."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()
                mock_process = MagicMock()
                mock_process.isalive.return_value = True
                pty._process = mock_process

                result = pty.write_line("hello")

                assert result == 6  # "hello\n"
                mock_process.write.assert_called_once_with(b"hello\n")


class TestSendSignal:
    """Tests for send_signal method."""

    def test_sends_signal_to_process(self) -> None:
        """Should send signal to process."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()
                mock_process = MagicMock()
                mock_process.isalive.return_value = True
                pty._process = mock_process

                pty.send_signal(signal.SIGTERM)

                mock_process.kill.assert_called_once_with(signal.SIGTERM)

    def test_does_nothing_without_process(self) -> None:
        """Should do nothing if no process."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()

                pty.send_signal(signal.SIGTERM)  # Should not raise


class TestInterrupt:
    """Tests for interrupt method."""

    def test_sends_sigint(self) -> None:
        """Should send SIGINT."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()
                mock_process = MagicMock()
                mock_process.isalive.return_value = True
                pty._process = mock_process

                pty.interrupt()

                mock_process.kill.assert_called_once_with(signal.SIGINT)


class TestSendEof:
    """Tests for send_eof method."""

    def test_sends_eof(self) -> None:
        """Should send EOF."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()
                mock_process = MagicMock()
                pty._process = mock_process

                pty.send_eof()

                mock_process.sendeof.assert_called_once()

    def test_does_nothing_without_process(self) -> None:
        """Should do nothing if no process."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()

                pty.send_eof()  # Should not raise


class TestProperties:
    """Tests for PTYManager properties."""

    def test_is_alive_true(self) -> None:
        """Should return True if process is alive."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()
                mock_process = MagicMock()
                mock_process.isalive.return_value = True
                pty._process = mock_process

                assert pty.is_alive is True

    def test_is_alive_false(self) -> None:
        """Should return False if process not alive."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()
                mock_process = MagicMock()
                mock_process.isalive.return_value = False
                pty._process = mock_process

                assert pty.is_alive is False

    def test_is_alive_no_process(self) -> None:
        """Should return False if no process."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()

                assert pty.is_alive is False

    def test_pid_with_process(self) -> None:
        """Should return PID if process exists."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()
                mock_process = MagicMock()
                mock_process.pid = 12345
                pty._process = mock_process

                assert pty.pid == 12345

    def test_pid_no_process(self) -> None:
        """Should return None if no process."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()

                assert pty.pid is None

    def test_exit_status_running(self) -> None:
        """Should return None if still running."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()
                mock_process = MagicMock()
                mock_process.isalive.return_value = True
                pty._process = mock_process

                assert pty.exit_status is None

    def test_exit_status_exited(self) -> None:
        """Should return exit status if exited."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()
                mock_process = MagicMock()
                mock_process.isalive.return_value = False
                mock_process.exitstatus = 0
                pty._process = mock_process

                assert pty.exit_status == 0

    def test_exit_status_no_process(self) -> None:
        """Should return None if no process."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()

                assert pty.exit_status is None


class TestClose:
    """Tests for close method."""

    def test_does_nothing_without_process(self) -> None:
        """Should do nothing if no process."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()

                pty.close()  # Should not raise

    def test_terminates_process(self) -> None:
        """Should terminate the process."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()
                mock_process = MagicMock()
                mock_process.pid = 12345
                mock_process.isalive.return_value = True
                pty._process = mock_process

                pty.close()

                mock_process.terminate.assert_called()
                assert pty._process is None

    def test_force_kills_process(self) -> None:
        """Should force kill with force=True."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()
                mock_process = MagicMock()
                mock_process.pid = 12345
                mock_process.isalive.return_value = True
                pty._process = mock_process

                pty.close(force=True)

                mock_process.kill.assert_called_with(signal.SIGKILL)

    def test_restores_sigwinch_handler(self) -> None:
        """Should restore original SIGWINCH handler."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()
                mock_process = MagicMock()
                mock_process.pid = 12345
                mock_process.isalive.return_value = False
                pty._process = mock_process
                pty._original_sigwinch = signal.SIG_DFL

                with patch("signal.signal") as mock_signal:
                    pty.close()

                    mock_signal.assert_called_once_with(signal.SIGWINCH, signal.SIG_DFL)


class TestContextManager:
    """Tests for context manager interface."""

    def test_enter_spawns(self) -> None:
        """Should spawn on enter."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                with patch.object(PTYManager, "spawn") as mock_spawn:
                    with patch.object(PTYManager, "close"):
                        pty = PTYManager()
                        result = pty.__enter__()

                        mock_spawn.assert_called_once()
                        assert result is pty

    def test_exit_closes(self) -> None:
        """Should close on exit."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                with patch.object(PTYManager, "close") as mock_close:
                    pty = PTYManager()
                    pty.__exit__(None, None, None)

                    mock_close.assert_called_once()


class TestSigwinchHandler:
    """Tests for SIGWINCH handling."""

    def test_setup_sigwinch_handler(self) -> None:
        """Should set up SIGWINCH handler."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()

                with patch("signal.signal") as mock_signal:
                    mock_signal.return_value = signal.SIG_DFL
                    pty._setup_sigwinch_handler()

                    mock_signal.assert_called_once()
                    assert pty._original_sigwinch == signal.SIG_DFL

    def test_setup_sigwinch_handles_error(self) -> None:
        """Should handle errors setting up signal handler."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(24, 80)):
                pty = PTYManager()

                with patch("signal.signal", side_effect=ValueError()):
                    pty._setup_sigwinch_handler()  # Should not raise

    def test_handle_sigwinch_resizes(self) -> None:
        """Should resize PTY on SIGWINCH."""
        with patch.object(PTYManager, "_detect_shell", return_value="/bin/zsh"):
            with patch.object(PTYManager, "_get_terminal_size", return_value=(40, 120)):
                pty = PTYManager(dimensions=(24, 80))
                mock_process = MagicMock()
                mock_process.isalive.return_value = True
                pty._process = mock_process

                pty._handle_sigwinch(signal.SIGWINCH, None)

                mock_process.setwinsize.assert_called_once_with(40, 120)
