"""Tests for process toolset."""

import os
import signal
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from agentsh.plugins.builtin.process import ProcessToolset


class TestProcessToolsetProperties:
    """Test toolset properties."""

    def test_name(self) -> None:
        """Should have correct name."""
        toolset = ProcessToolset()
        assert toolset.name == "process"

    def test_description(self) -> None:
        """Should have description."""
        toolset = ProcessToolset()
        assert "process" in toolset.description.lower()


class TestProcessToolsetRegistration:
    """Test tool registration."""

    def test_register_tools(self) -> None:
        """Should register all tools."""
        toolset = ProcessToolset()
        registry = MagicMock()

        toolset.register_tools(registry)

        registered_names = [
            call[1]["name"] for call in registry.register_tool.call_args_list
        ]
        assert "process.list" in registered_names
        assert "process.info" in registered_names
        assert "process.kill" in registered_names


class TestListProcesses:
    """Tests for list_processes method."""

    @pytest.fixture
    def toolset(self) -> ProcessToolset:
        """Create a process toolset."""
        return ProcessToolset()

    def test_list_processes_success(self, toolset: ProcessToolset) -> None:
        """Should list processes."""
        mock_output = """USER       PID  %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
root         1   0.0  0.1 168936  9876 ?        Ss   Jan01   0:10 /sbin/init
user      1234   5.0  1.0 500000 50000 pts/0    S+   10:00   0:05 python script.py
user      5678   2.0  0.5 250000 25000 pts/1    R    11:00   0:02 bash"""

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = mock_output
            mock_run.return_value.stderr = ""

            result = toolset.list_processes()

            assert result.success
            assert "PID" in result.output
            assert "CPU" in result.output

    def test_list_processes_with_filter(self, toolset: ProcessToolset) -> None:
        """Should filter processes by name."""
        mock_output = """USER       PID  %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
user      1234   5.0  1.0 500000 50000 pts/0    S+   10:00   0:05 python script.py
user      5678   2.0  0.5 250000 25000 pts/1    R    11:00   0:02 bash
user      9012   1.0  0.3 100000 10000 pts/2    S    12:00   0:01 python other.py"""

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = mock_output
            mock_run.return_value.stderr = ""

            result = toolset.list_processes(filter="python")

            assert result.success
            assert "python" in result.output.lower()
            assert "bash" not in result.output.lower()

    def test_list_processes_with_limit(self, toolset: ProcessToolset) -> None:
        """Should limit results."""
        mock_output = """USER       PID  %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
user      1001   5.0  1.0 500000 50000 pts/0    S+   10:00   0:05 process1
user      1002   4.0  1.0 500000 50000 pts/0    S+   10:00   0:05 process2
user      1003   3.0  1.0 500000 50000 pts/0    S+   10:00   0:05 process3
user      1004   2.0  1.0 500000 50000 pts/0    S+   10:00   0:05 process4"""

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = mock_output
            mock_run.return_value.stderr = ""

            result = toolset.list_processes(limit=2)

            assert result.success
            # Count data lines (excluding header and separator)
            lines = [l for l in result.output.split("\n") if l and not l.startswith("-")]
            # Should have header + 2 data lines
            assert len(lines) == 3

    def test_list_processes_sort_by_pid(self, toolset: ProcessToolset) -> None:
        """Should sort by PID."""
        mock_output = """USER       PID  %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
user      5678   5.0  1.0 500000 50000 pts/0    S+   10:00   0:05 process2
user      1234   4.0  1.0 500000 50000 pts/0    S+   10:00   0:05 process1"""

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = mock_output
            mock_run.return_value.stderr = ""

            result = toolset.list_processes(sort_by="pid")

            assert result.success
            lines = result.output.split("\n")
            # First data line after header and separator should have lower PID
            data_lines = [l for l in lines if l and not l.startswith("-") and "PID" not in l]
            assert "1234" in data_lines[0]

    def test_list_processes_sort_by_name(self, toolset: ProcessToolset) -> None:
        """Should sort by name."""
        mock_output = """USER       PID  %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
user      1234   5.0  1.0 500000 50000 pts/0    S+   10:00   0:05 zebra_process
user      5678   4.0  1.0 500000 50000 pts/0    S+   10:00   0:05 alpha_process"""

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = mock_output
            mock_run.return_value.stderr = ""

            result = toolset.list_processes(sort_by="name")

            assert result.success
            lines = result.output.split("\n")
            data_lines = [l for l in lines if l and not l.startswith("-") and "PID" not in l]
            assert "alpha" in data_lines[0]

    def test_list_processes_command_failed(self, toolset: ProcessToolset) -> None:
        """Should handle command failure."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = "Command failed"

            result = toolset.list_processes()

            assert not result.success
            assert "failed" in result.error.lower()

    def test_list_processes_timeout(self, toolset: ProcessToolset) -> None:
        """Should handle timeout."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("ps", 10)

            result = toolset.list_processes()

            assert not result.success
            assert "timed out" in result.error.lower()

    def test_list_processes_exception(self, toolset: ProcessToolset) -> None:
        """Should handle exceptions."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Unexpected error")

            result = toolset.list_processes()

            assert not result.success
            assert "failed" in result.error.lower()

    def test_list_processes_no_match(self, toolset: ProcessToolset) -> None:
        """Should handle no matching processes."""
        mock_output = """USER       PID  %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
user      1234   5.0  1.0 500000 50000 pts/0    S+   10:00   0:05 bash"""

        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = mock_output
            mock_run.return_value.stderr = ""

            result = toolset.list_processes(filter="nonexistent")

            assert result.success
            assert "no processes" in result.output.lower()

    def test_list_processes_empty(self, toolset: ProcessToolset) -> None:
        """Should handle empty output."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = ""

            result = toolset.list_processes()

            assert result.success
            assert "No processes" in result.output


class TestGetProcessInfo:
    """Tests for get_process_info method."""

    @pytest.fixture
    def toolset(self) -> ProcessToolset:
        """Create a process toolset."""
        return ProcessToolset()

    def test_get_process_info_success(self, toolset: ProcessToolset) -> None:
        """Should get process info."""
        mock_output = """  PID  PPID USER     %CPU %MEM STAT STARTED      TIME COMMAND
 1234   100 user      5.0  1.0 S+   Jan01    0:05:00 python script.py"""

        with patch("os.kill") as mock_kill, patch("subprocess.run") as mock_run:
            mock_kill.return_value = None
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = mock_output
            mock_run.return_value.stderr = ""

            result = toolset.get_process_info(1234)

            assert result.success
            assert "Process: 1234" in result.output
            assert "Parent PID:" in result.output
            assert "User:" in result.output

    def test_get_process_info_not_found(self, toolset: ProcessToolset) -> None:
        """Should handle process not found."""
        with patch("os.kill") as mock_kill:
            mock_kill.side_effect = ProcessLookupError()

            result = toolset.get_process_info(99999)

            assert not result.success
            assert "not found" in result.error.lower()

    def test_get_process_info_permission_denied_on_check(self, toolset: ProcessToolset) -> None:
        """Should continue if permission denied on check (process exists)."""
        mock_output = """  PID  PPID USER     %CPU %MEM STAT STARTED      TIME COMMAND
 1234   100 root      5.0  1.0 S+   Jan01    0:05:00 protected_process"""

        with patch("os.kill") as mock_kill, patch("subprocess.run") as mock_run:
            mock_kill.side_effect = PermissionError()
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = mock_output
            mock_run.return_value.stderr = ""

            result = toolset.get_process_info(1234)

            # Should succeed because process exists
            assert result.success

    def test_get_process_info_ps_failed(self, toolset: ProcessToolset) -> None:
        """Should handle ps command failure."""
        with patch("os.kill"), patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = "No such process"

            result = toolset.get_process_info(1234)

            assert not result.success

    def test_get_process_info_timeout(self, toolset: ProcessToolset) -> None:
        """Should handle timeout."""
        with patch("os.kill"), patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("ps", 5)

            result = toolset.get_process_info(1234)

            assert not result.success
            assert "timed out" in result.error.lower()

    def test_get_process_info_short_output(self, toolset: ProcessToolset) -> None:
        """Should handle short ps output."""
        mock_output = """  PID  PPID USER
 1234   100 user"""

        with patch("os.kill"), patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = mock_output
            mock_run.return_value.stderr = ""

            result = toolset.get_process_info(1234)

            # Should succeed but with limited info
            assert result.success
            assert "Process: 1234" in result.output


class TestKillProcess:
    """Tests for kill_process method."""

    @pytest.fixture
    def toolset(self) -> ProcessToolset:
        """Create a process toolset."""
        return ProcessToolset()

    def test_kill_process_success(self, toolset: ProcessToolset) -> None:
        """Should kill process with TERM signal."""
        with patch("os.kill") as mock_kill, patch("os.getpid", return_value=9999):
            mock_kill.return_value = None

            result = toolset.kill_process(1234)

            assert result.success
            mock_kill.assert_called_once_with(1234, signal.SIGTERM)
            assert "TERM" in result.output

    def test_kill_process_with_kill_signal(self, toolset: ProcessToolset) -> None:
        """Should send KILL signal."""
        with patch("os.kill") as mock_kill, patch("os.getpid", return_value=9999):
            mock_kill.return_value = None

            result = toolset.kill_process(1234, signal_name="KILL")

            assert result.success
            mock_kill.assert_called_once_with(1234, signal.SIGKILL)

    def test_kill_process_with_int_signal(self, toolset: ProcessToolset) -> None:
        """Should send INT signal."""
        with patch("os.kill") as mock_kill, patch("os.getpid", return_value=9999):
            mock_kill.return_value = None

            result = toolset.kill_process(1234, signal_name="INT")

            assert result.success
            mock_kill.assert_called_once_with(1234, signal.SIGINT)

    def test_kill_process_with_hup_signal(self, toolset: ProcessToolset) -> None:
        """Should send HUP signal."""
        with patch("os.kill") as mock_kill, patch("os.getpid", return_value=9999):
            mock_kill.return_value = None

            result = toolset.kill_process(1234, signal_name="HUP")

            assert result.success
            mock_kill.assert_called_once_with(1234, signal.SIGHUP)

    def test_kill_process_invalid_signal_defaults_to_term(self, toolset: ProcessToolset) -> None:
        """Should default to TERM for invalid signal."""
        with patch("os.kill") as mock_kill, patch("os.getpid", return_value=9999):
            mock_kill.return_value = None

            result = toolset.kill_process(1234, signal_name="INVALID")

            assert result.success
            mock_kill.assert_called_once_with(1234, signal.SIGTERM)

    def test_kill_process_not_found(self, toolset: ProcessToolset) -> None:
        """Should handle process not found."""
        with patch("os.kill") as mock_kill, patch("os.getpid", return_value=9999):
            mock_kill.side_effect = ProcessLookupError()

            result = toolset.kill_process(1234)

            assert not result.success
            assert "not found" in result.error.lower()

    def test_kill_process_permission_denied(self, toolset: ProcessToolset) -> None:
        """Should handle permission denied."""
        with patch("os.kill") as mock_kill, patch("os.getpid", return_value=9999):
            mock_kill.side_effect = PermissionError()

            result = toolset.kill_process(1234)

            assert not result.success
            assert "Permission denied" in result.error

    def test_kill_process_critical_pid_zero(self, toolset: ProcessToolset) -> None:
        """Should not kill PID 0."""
        result = toolset.kill_process(0)

        assert not result.success
        assert "Cannot kill" in result.error

    def test_kill_process_critical_pid_one(self, toolset: ProcessToolset) -> None:
        """Should not kill PID 1 (init)."""
        result = toolset.kill_process(1)

        assert not result.success
        assert "Cannot kill" in result.error

    def test_kill_process_own_pid(self, toolset: ProcessToolset) -> None:
        """Should not kill own process."""
        with patch("os.getpid", return_value=1234):
            result = toolset.kill_process(1234)

            assert not result.success
            assert "current process" in result.error.lower()

    def test_kill_process_exception(self, toolset: ProcessToolset) -> None:
        """Should handle exceptions."""
        with patch("os.kill") as mock_kill, patch("os.getpid", return_value=9999):
            mock_kill.side_effect = Exception("Unexpected error")

            result = toolset.kill_process(1234)

            assert not result.success
            assert "failed" in result.error.lower()
