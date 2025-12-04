"""Tests for the shell wrapper."""

from unittest.mock import MagicMock, patch

import pytest

from agentsh.config.schemas import AgentSHConfig
from agentsh.shell.input_classifier import InputType
from agentsh.shell.prompt import AgentStatus
from agentsh.shell.wrapper import ShellWrapper


class TestShellWrapper:
    """Test cases for ShellWrapper."""

    @pytest.fixture
    def config(self) -> AgentSHConfig:
        """Create a test configuration."""
        return AgentSHConfig()

    @pytest.fixture
    def wrapper(self, config: AgentSHConfig) -> ShellWrapper:
        """Create a shell wrapper for testing."""
        return ShellWrapper(config)

    # Initialization tests
    def test_initialization(self, wrapper: ShellWrapper) -> None:
        """Test that wrapper initializes correctly."""
        assert wrapper._running is False
        assert wrapper._agent_status == AgentStatus.IDLE
        assert wrapper._last_exit_code == 0
        assert wrapper._ai_handler is None

    def test_initialization_with_config(self, config: AgentSHConfig) -> None:
        """Test initialization respects config."""
        config.shell.ai_prefix = "ask "
        config.shell.shell_prefix = "$"
        wrapper = ShellWrapper(config)

        assert wrapper._classifier.ai_prefix == "ask "
        assert wrapper._classifier.shell_prefix == "$"

    # AI handler tests
    def test_set_ai_handler(self, wrapper: ShellWrapper) -> None:
        """Test setting AI handler."""
        handler = MagicMock(return_value="AI response")
        wrapper.set_ai_handler(handler)
        assert wrapper._ai_handler == handler

    # Properties tests
    def test_is_running_property(self, wrapper: ShellWrapper) -> None:
        """Test is_running property."""
        assert wrapper.is_running is False
        wrapper._running = True
        assert wrapper.is_running is True

    def test_stop(self, wrapper: ShellWrapper) -> None:
        """Test stop method."""
        wrapper._running = True
        wrapper.stop()
        assert wrapper._running is False

    # Input processing tests
    def test_process_empty_input(self, wrapper: ShellWrapper) -> None:
        """Test processing empty input does nothing."""
        # Should not raise
        wrapper._process_input("")
        wrapper._process_input("   ")

    def test_process_special_command_help(self, wrapper: ShellWrapper) -> None:
        """Test processing :help command."""
        with patch("agentsh.shell.wrapper.show_help") as mock_help:
            mock_help.return_value = "Help content"
            with patch("builtins.print"):
                wrapper._process_input(":help")
            mock_help.assert_called_once()

    def test_process_special_command_config(self, wrapper: ShellWrapper) -> None:
        """Test processing :config command."""
        with patch.object(wrapper, "_show_config") as mock_config:
            wrapper._process_input(":config")
            mock_config.assert_called_once()

    def test_process_special_command_status(self, wrapper: ShellWrapper) -> None:
        """Test processing :status command."""
        with patch.object(wrapper, "_show_status") as mock_status:
            wrapper._process_input(":status")
            mock_status.assert_called_once()

    def test_process_special_command_history(self, wrapper: ShellWrapper) -> None:
        """Test processing :history command."""
        with patch.object(wrapper, "_show_history") as mock_history:
            wrapper._process_input(":history")
            mock_history.assert_called_once()

    def test_process_special_command_reset(self, wrapper: ShellWrapper) -> None:
        """Test processing :reset command."""
        with patch.object(wrapper, "_reset_context") as mock_reset:
            wrapper._process_input(":reset")
            mock_reset.assert_called_once()

    def test_process_special_command_quit(self, wrapper: ShellWrapper) -> None:
        """Test processing :quit command."""
        wrapper._running = True
        with patch("builtins.print"):
            wrapper._process_input(":quit")
        assert wrapper._running is False

    def test_process_special_command_exit(self, wrapper: ShellWrapper) -> None:
        """Test processing :exit command."""
        wrapper._running = True
        with patch("builtins.print"):
            wrapper._process_input(":exit")
        assert wrapper._running is False

    def test_process_unknown_special_command(self, wrapper: ShellWrapper) -> None:
        """Test processing unknown special command."""
        with patch("builtins.print") as mock_print:
            wrapper._process_input(":unknown")
            # Should print error message
            assert any("Unknown command" in str(call) for call in mock_print.call_args_list)

    # AI request processing tests
    def test_process_ai_request_without_handler(self, wrapper: ShellWrapper) -> None:
        """Test processing AI request without handler shows placeholder."""
        with patch.object(wrapper, "_show_ai_placeholder") as mock_placeholder:
            wrapper._process_input("ai find all files")
            mock_placeholder.assert_called_once()

    def test_process_ai_request_with_handler(self, wrapper: ShellWrapper) -> None:
        """Test processing AI request with handler."""
        handler = MagicMock(return_value="AI response")
        wrapper.set_ai_handler(handler)

        with patch("builtins.print"):
            wrapper._process_input("ai find all files")

        handler.assert_called_once_with("find all files")
        assert wrapper._agent_status == AgentStatus.IDLE
        assert wrapper._last_exit_code == 0

    def test_process_ai_request_handler_error(self, wrapper: ShellWrapper) -> None:
        """Test processing AI request when handler raises error."""
        handler = MagicMock(side_effect=Exception("AI error"))
        wrapper.set_ai_handler(handler)

        with patch("builtins.print"):
            wrapper._process_input("ai test")

        assert wrapper._agent_status == AgentStatus.ERROR
        assert wrapper._last_exit_code == 1

    # Shell command processing tests
    def test_process_shell_command(self, wrapper: ShellWrapper) -> None:
        """Test processing shell command."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            wrapper._process_input("!ls -la")

        mock_run.assert_called_once()
        assert wrapper._last_exit_code == 0

    def test_process_shell_command_with_exit_code(self, wrapper: ShellWrapper) -> None:
        """Test processing shell command with non-zero exit code."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            wrapper._process_input("!false")

        assert wrapper._last_exit_code == 1

    def test_process_shell_command_error(self, wrapper: ShellWrapper) -> None:
        """Test processing shell command when subprocess raises error."""
        with patch("subprocess.run", side_effect=Exception("Command failed")):
            with patch("builtins.print"):
                wrapper._process_input("!bad-command")

        assert wrapper._last_exit_code == 1

    # History integration tests
    def test_shell_command_added_to_history(self, wrapper: ShellWrapper) -> None:
        """Test that shell commands are added to history."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            wrapper._process_input("!ls")

        # Check history contains the command
        recent = wrapper._history.get_recent(1)
        assert len(recent) >= 1
        # Last entry should be 'ls' (without the ! prefix)
        assert any(e.command == "ls" for e in recent)

    def test_ai_request_added_to_history(self, wrapper: ShellWrapper) -> None:
        """Test that AI requests are added to history."""
        with patch.object(wrapper, "_show_ai_placeholder"):
            wrapper._process_input("ai find files")

        recent = wrapper._history.get_recent(1)
        assert len(recent) >= 1
        assert any(e.command == "find files" and e.is_ai_request for e in recent)


class TestShellWrapperHelpers:
    """Test cases for ShellWrapper helper methods."""

    @pytest.fixture
    def config(self) -> AgentSHConfig:
        """Create a test configuration."""
        return AgentSHConfig()

    @pytest.fixture
    def wrapper(self, config: AgentSHConfig) -> ShellWrapper:
        """Create a shell wrapper for testing."""
        return ShellWrapper(config)

    def test_print_welcome(self, wrapper: ShellWrapper) -> None:
        """Test welcome message printing."""
        with patch("builtins.print") as mock_print:
            wrapper._print_welcome()

        # Check that welcome was printed
        calls = [str(call) for call in mock_print.call_args_list]
        assert any("AgentSH" in str(call) for call in calls)

    def test_show_help(self, wrapper: ShellWrapper) -> None:
        """Test help display via show_help function."""
        from agentsh.shell.help import show_help

        output = show_help(use_color=False)
        assert "AgentSH Help" in output

    def test_show_config(self, wrapper: ShellWrapper) -> None:
        """Test config display."""
        with patch("builtins.print") as mock_print:
            wrapper._show_config()

        calls = [str(call) for call in mock_print.call_args_list]
        assert any("Configuration" in str(call) for call in calls)

    def test_show_history_default(self, wrapper: ShellWrapper) -> None:
        """Test history display with defaults."""
        wrapper._history.add("cmd1")
        wrapper._history.add("cmd2")

        with patch("builtins.print") as mock_print:
            wrapper._show_history([])

        calls = [str(call) for call in mock_print.call_args_list]
        assert any("History" in str(call) for call in calls)

    def test_show_history_with_count(self, wrapper: ShellWrapper) -> None:
        """Test history display with count argument."""
        for i in range(10):
            wrapper._history.add(f"cmd{i}")

        with patch("builtins.print"):
            wrapper._show_history(["5"])

        # Should limit to 5 entries
        entries = wrapper._history.get_recent(5)
        assert len(entries) == 5

    def test_show_history_ai_only(self, wrapper: ShellWrapper) -> None:
        """Test history display with --ai flag."""
        wrapper._history.add("shell cmd")
        wrapper._history.add("ai request", is_ai_request=True)

        with patch("builtins.print"):
            wrapper._show_history(["--ai"])

    def test_show_history_shell_only(self, wrapper: ShellWrapper) -> None:
        """Test history display with --shell flag."""
        wrapper._history.add("shell cmd")
        wrapper._history.add("ai request", is_ai_request=True)

        with patch("builtins.print"):
            wrapper._show_history(["--shell"])

    def test_reset_context(self, wrapper: ShellWrapper) -> None:
        """Test context reset."""
        wrapper._history.add("shell cmd")
        wrapper._history.add("ai request", is_ai_request=True)

        with patch("builtins.print"):
            wrapper._reset_context()

        # AI history should be cleared
        assert len(wrapper._history.ai_requests) == 0
        # Shell history should remain
        assert len(wrapper._history.shell_commands) == 1

    def test_show_ai_placeholder(self, wrapper: ShellWrapper) -> None:
        """Test AI placeholder display."""
        with patch("builtins.print") as mock_print:
            wrapper._show_ai_placeholder("test request")

        calls = [str(call) for call in mock_print.call_args_list]
        assert any("Phase 2" in str(call) for call in calls)
