"""Tests for shell tab completion."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentsh.shell.completer import (
    CompletionResult,
    CompletionType,
    ShellCompleter,
    get_completer,
    setup_completion,
)


class TestCompletionType:
    """Tests for CompletionType enum."""

    def test_completion_types(self) -> None:
        """Should have expected completion types."""
        assert CompletionType.SPECIAL_COMMAND == "special_command"
        assert CompletionType.TOOL == "tool"
        assert CompletionType.FILE_PATH == "file_path"
        assert CompletionType.HISTORY == "history"
        assert CompletionType.NONE == "none"


class TestCompletionResult:
    """Tests for CompletionResult dataclass."""

    def test_default_result(self) -> None:
        """Should have sensible defaults."""
        result = CompletionResult()
        assert result.matches == []
        assert result.completion_type == CompletionType.NONE
        assert result.prefix == ""

    def test_custom_result(self) -> None:
        """Should accept custom values."""
        result = CompletionResult(
            matches=["help", "history"],
            completion_type=CompletionType.SPECIAL_COMMAND,
            prefix=":",
        )
        assert len(result.matches) == 2
        assert result.completion_type == CompletionType.SPECIAL_COMMAND
        assert result.prefix == ":"


class TestShellCompleter:
    """Tests for ShellCompleter class."""

    @pytest.fixture
    def completer(self) -> ShellCompleter:
        """Create a completer for testing."""
        c = ShellCompleter()
        # Register some tools
        c.register_tool("shell.run", "Execute shell commands")
        c.register_tool("shell.env", "Get environment variable")
        c.register_tool("fs.read", "Read file")
        c.register_tool("fs.write", "Write file")
        c.register_tool("fs.list", "List directory")
        # Register special commands
        c.register_special_command("help", "Show help")
        c.register_special_command("history", "Show history")
        c.register_special_command("config", "Show config")
        c.register_special_command("quit", "Exit shell")
        return c

    def test_register_tool(self) -> None:
        """Should register tools."""
        c = ShellCompleter()
        c.register_tool("test.tool", "Test tool")
        assert "test.tool" in c._tools
        assert c._tools["test.tool"] == "Test tool"

    def test_register_tools(self) -> None:
        """Should register multiple tools."""
        c = ShellCompleter()
        c.register_tools({
            "tool1": "First tool",
            "tool2": "Second tool",
        })
        assert len(c._tools) == 2
        assert "tool1" in c._tools
        assert "tool2" in c._tools

    def test_register_special_command(self) -> None:
        """Should register special commands."""
        c = ShellCompleter()
        c.register_special_command("test", "Test command")
        assert "test" in c._special_commands
        assert c._special_commands["test"] == "Test command"

    def test_register_special_commands(self) -> None:
        """Should register multiple special commands."""
        c = ShellCompleter()
        c.register_special_commands({
            "cmd1": "First command",
            "cmd2": "Second command",
        })
        assert len(c._special_commands) == 2

    def test_add_to_history(self) -> None:
        """Should add entries to history."""
        c = ShellCompleter()
        c.add_to_history("ls -la")
        c.add_to_history("git status")
        assert len(c._history) == 2
        assert "ls -la" in c._history

    def test_add_to_history_no_duplicates(self) -> None:
        """Should not add duplicate entries."""
        c = ShellCompleter()
        c.add_to_history("ls -la")
        c.add_to_history("ls -la")
        assert len(c._history) == 1

    def test_add_to_history_empty(self) -> None:
        """Should not add empty entries."""
        c = ShellCompleter()
        c.add_to_history("")
        assert len(c._history) == 0

    def test_complete_special_command(self, completer: ShellCompleter) -> None:
        """Should complete special commands."""
        matches = completer._complete_special_command("h", ":h")
        assert ":help" in matches
        assert ":history" in matches
        assert ":config" not in matches

    def test_complete_special_command_full(self, completer: ShellCompleter) -> None:
        """Should complete exact match."""
        matches = completer._complete_special_command("help", ":help")
        assert ":help" in matches
        assert len(matches) == 1

    def test_complete_special_command_empty(self, completer: ShellCompleter) -> None:
        """Should list all commands for empty prefix."""
        matches = completer._complete_special_command("", ":")
        assert len(matches) == 4
        assert ":help" in matches
        assert ":quit" in matches

    def test_complete_tool(self, completer: ShellCompleter) -> None:
        """Should complete tool names."""
        matches = completer._complete_tool("shell")
        assert "shell.run" in matches
        assert "shell.env" in matches
        assert "fs.read" not in matches

    def test_complete_tool_partial(self, completer: ShellCompleter) -> None:
        """Should complete partial tool names."""
        matches = completer._complete_tool("fs")
        assert len(matches) == 3
        assert "fs.read" in matches
        assert "fs.write" in matches
        assert "fs.list" in matches

    def test_complete_tool_case_insensitive(self, completer: ShellCompleter) -> None:
        """Should be case insensitive."""
        matches = completer._complete_tool("SHELL")
        assert "shell.run" in matches

    def test_complete_path_directory(self) -> None:
        """Should complete directory paths."""
        c = ShellCompleter()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some test files
            Path(tmpdir, "file1.txt").touch()
            Path(tmpdir, "file2.txt").touch()
            subdir = Path(tmpdir, "subdir")
            subdir.mkdir()

            matches = c._complete_path(tmpdir + "/")
            assert any("file1.txt" in m for m in matches)
            assert any("file2.txt" in m for m in matches)
            assert any("subdir/" in m for m in matches)

    def test_complete_path_partial(self) -> None:
        """Should complete partial paths."""
        c = ShellCompleter()
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "test_file.txt").touch()
            Path(tmpdir, "test_data.json").touch()
            Path(tmpdir, "other.txt").touch()

            matches = c._complete_path(tmpdir + "/test")
            assert len(matches) == 2
            assert any("test_file.txt" in m for m in matches)
            assert any("test_data.json" in m for m in matches)

    def test_complete_path_home(self) -> None:
        """Should expand ~ in paths."""
        c = ShellCompleter()
        matches = c._complete_path("~/")
        # Should return something (home directory contents)
        assert isinstance(matches, list)

    def test_get_completions_special_command(self, completer: ShellCompleter) -> None:
        """Should get special command completions."""
        matches = completer._get_completions("h", ":h")
        assert ":help" in matches
        assert ":history" in matches

    def test_get_completions_tool(self, completer: ShellCompleter) -> None:
        """Should get tool completions."""
        matches = completer._get_completions("shell", "shell")
        assert "shell.run" in matches
        assert "shell.env" in matches

    def test_get_completions_path(self, completer: ShellCompleter) -> None:
        """Should get path completions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "test.txt").touch()
            matches = completer._get_completions(
                tmpdir + "/",
                f"cat {tmpdir}/"
            )
            assert any("test.txt" in m for m in matches)

    def test_get_completions_shell_command(self, completer: ShellCompleter) -> None:
        """Should not complete tools for shell commands."""
        matches = completer._get_completions("shell", "!shell")
        # Tools should not complete after !
        assert "shell.run" not in matches

    @patch("agentsh.shell.completer.readline")
    def test_complete_state_0(
        self, mock_readline: MagicMock, completer: ShellCompleter
    ) -> None:
        """Should compute matches on state 0."""
        mock_readline.get_line_buffer.return_value = ":h"
        result = completer.complete("h", 0)
        assert result in [":help", ":history"]

    @patch("agentsh.shell.completer.readline")
    def test_complete_state_1(
        self, mock_readline: MagicMock, completer: ShellCompleter
    ) -> None:
        """Should return next match on subsequent states."""
        mock_readline.get_line_buffer.return_value = ":h"
        # First call computes matches
        completer.complete("h", 0)
        # Second call returns next match
        result = completer.complete("h", 1)
        assert result in [":help", ":history", None]

    @patch("agentsh.shell.completer.readline")
    def test_complete_no_more_matches(
        self, mock_readline: MagicMock, completer: ShellCompleter
    ) -> None:
        """Should return None when no more matches."""
        mock_readline.get_line_buffer.return_value = ":h"
        completer.complete("h", 0)
        completer.complete("h", 1)
        result = completer.complete("h", 100)
        assert result is None

    @patch("agentsh.shell.completer.readline")
    def test_install(self, mock_readline: MagicMock) -> None:
        """Should install completer into readline."""
        c = ShellCompleter()
        c.install()

        mock_readline.set_completer.assert_called_once_with(c.complete)
        mock_readline.parse_and_bind.assert_called()
        assert c._installed is True

    @patch("agentsh.shell.completer.readline")
    def test_install_idempotent(self, mock_readline: MagicMock) -> None:
        """Should not reinstall if already installed."""
        c = ShellCompleter()
        c.install()
        c.install()

        # Should only be called once
        assert mock_readline.set_completer.call_count == 1

    @patch("agentsh.shell.completer.readline")
    def test_uninstall(self, mock_readline: MagicMock) -> None:
        """Should uninstall completer."""
        c = ShellCompleter()
        c.install()
        c.uninstall()

        assert c._installed is False
        # Last call should be set_completer(None)
        mock_readline.set_completer.assert_called_with(None)

    @patch("agentsh.shell.completer.readline")
    def test_uninstall_not_installed(self, mock_readline: MagicMock) -> None:
        """Should do nothing if not installed."""
        c = ShellCompleter()
        c.uninstall()

        mock_readline.set_completer.assert_not_called()


class TestGlobalCompleter:
    """Tests for global completer functions."""

    def test_get_completer(self) -> None:
        """Should return completer instance."""
        completer = get_completer()
        assert isinstance(completer, ShellCompleter)

    def test_get_completer_same_instance(self) -> None:
        """Should return same instance."""
        c1 = get_completer()
        c2 = get_completer()
        assert c1 is c2

    @patch("agentsh.shell.completer.readline")
    def test_setup_completion(self, mock_readline: MagicMock) -> None:
        """Should set up completion with tools and commands."""
        # Reset global completer for this test
        import agentsh.shell.completer as module
        module._completer = None

        completer = setup_completion(
            tools={"tool1": "Tool 1", "tool2": "Tool 2"},
            special_commands={"help": "Help", "quit": "Quit"},
        )

        assert "tool1" in completer._tools
        assert "tool2" in completer._tools
        assert "help" in completer._special_commands
        assert "quit" in completer._special_commands
        assert completer._installed is True

    @patch("agentsh.shell.completer.readline")
    def test_setup_completion_empty(self, mock_readline: MagicMock) -> None:
        """Should work with no tools or commands."""
        import agentsh.shell.completer as module
        module._completer = None

        completer = setup_completion()

        assert completer._installed is True


class TestPathCompletion:
    """Additional tests for path completion edge cases."""

    def test_complete_nonexistent_directory(self) -> None:
        """Should handle nonexistent directories."""
        c = ShellCompleter()
        matches = c._complete_path("/nonexistent/path/")
        assert matches == []

    def test_complete_permission_denied(self) -> None:
        """Should handle permission denied."""
        c = ShellCompleter()
        # /root is typically not readable by regular users
        matches = c._complete_path("/root/")
        # Should return empty list, not raise
        assert isinstance(matches, list)

    def test_complete_current_directory(self) -> None:
        """Should complete in current directory."""
        c = ShellCompleter()
        matches = c._complete_path("./")
        # Should return list of current directory contents
        assert isinstance(matches, list)
