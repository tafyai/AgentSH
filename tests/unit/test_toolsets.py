"""Tests for built-in toolsets."""

import asyncio
import os
import pytest
import tempfile
from pathlib import Path

from agentsh.tools.base import RiskLevel, ToolResult
from agentsh.tools.registry import ToolRegistry
from agentsh.plugins.builtin.shell import ShellToolset
from agentsh.plugins.builtin.filesystem import FilesystemToolset
from agentsh.plugins.builtin.process import ProcessToolset
from agentsh.plugins.builtin.code import CodeToolset


class TestShellToolset:
    """Test shell toolset functionality."""

    @pytest.fixture
    def shell_toolset(self, tool_registry: ToolRegistry) -> ShellToolset:
        """Create shell toolset."""
        toolset = ShellToolset()
        toolset.register_tools(tool_registry)
        return toolset

    def test_register_tools(
        self, tool_registry: ToolRegistry, shell_toolset: ShellToolset
    ) -> None:
        """Should register all shell tools."""
        names = tool_registry.list_tool_names()

        assert "shell.run" in names
        assert "shell.explain" in names
        assert "shell.which" in names
        assert "shell.env" in names

    def test_run_command_success(self, shell_toolset: ShellToolset) -> None:
        """Should run command successfully."""
        result = asyncio.run(shell_toolset.run_command("echo hello"))

        assert result.success
        assert "hello" in result.output

    def test_run_command_failure(self, shell_toolset: ShellToolset) -> None:
        """Should handle command failure."""
        result = asyncio.run(shell_toolset.run_command("exit 1"))

        assert not result.success
        assert result.exit_code == 1

    def test_run_command_timeout(self, shell_toolset: ShellToolset) -> None:
        """Should handle command timeout."""
        result = asyncio.run(
            shell_toolset.run_command("sleep 10", timeout=1)
        )

        assert not result.success
        assert "timed out" in result.error.lower()

    def test_run_command_invalid_cwd(self, shell_toolset: ShellToolset) -> None:
        """Should handle invalid working directory."""
        result = asyncio.run(
            shell_toolset.run_command("pwd", cwd="/nonexistent/path")
        )

        assert not result.success
        assert "does not exist" in result.error.lower()

    def test_explain_command(self, shell_toolset: ShellToolset) -> None:
        """Should explain command."""
        result = shell_toolset.explain_command("ls -la /tmp")

        assert result.success
        assert "ls" in result.output
        assert "List directory" in result.output

    def test_which_found(self, shell_toolset: ShellToolset) -> None:
        """Should find executable in PATH."""
        result = shell_toolset.which("python")

        assert result.success
        assert "python" in result.output.lower()

    def test_which_not_found(self, shell_toolset: ShellToolset) -> None:
        """Should handle missing executable."""
        result = shell_toolset.which("nonexistent_program_xyz")

        assert not result.success
        assert "not found" in result.error.lower()

    def test_get_env_exists(self, shell_toolset: ShellToolset) -> None:
        """Should get existing environment variable."""
        result = shell_toolset.get_env("HOME")

        assert result.success
        assert len(result.output) > 0

    def test_get_env_missing(self, shell_toolset: ShellToolset) -> None:
        """Should handle missing environment variable."""
        result = shell_toolset.get_env("NONEXISTENT_VAR_XYZ")

        assert not result.success
        assert "not set" in result.error.lower()


class TestFilesystemToolset:
    """Test filesystem toolset functionality."""

    @pytest.fixture
    def fs_toolset(self, tool_registry: ToolRegistry) -> FilesystemToolset:
        """Create filesystem toolset."""
        toolset = FilesystemToolset()
        toolset.register_tools(tool_registry)
        return toolset

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_register_tools(
        self, tool_registry: ToolRegistry, fs_toolset: FilesystemToolset
    ) -> None:
        """Should register all filesystem tools."""
        names = tool_registry.list_tool_names()

        assert "fs.read" in names
        assert "fs.write" in names
        assert "fs.list" in names
        assert "fs.delete" in names
        assert "fs.copy" in names
        assert "fs.move" in names
        assert "fs.search" in names
        assert "fs.info" in names

    def test_read_file(
        self, fs_toolset: FilesystemToolset, temp_dir: Path
    ) -> None:
        """Should read file contents."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("hello world")

        result = fs_toolset.read_file(str(test_file))

        assert result.success
        assert "hello world" in result.output

    def test_read_file_not_found(self, fs_toolset: FilesystemToolset) -> None:
        """Should handle missing file."""
        result = fs_toolset.read_file("/nonexistent/file.txt")

        assert not result.success
        assert "not found" in result.error.lower()

    def test_write_file(
        self, fs_toolset: FilesystemToolset, temp_dir: Path
    ) -> None:
        """Should write file."""
        test_file = temp_dir / "output.txt"

        result = fs_toolset.write_file(str(test_file), "test content")

        assert result.success
        assert test_file.read_text() == "test content"

    def test_write_file_append(
        self, fs_toolset: FilesystemToolset, temp_dir: Path
    ) -> None:
        """Should append to file."""
        test_file = temp_dir / "append.txt"
        test_file.write_text("first\n")

        result = fs_toolset.write_file(str(test_file), "second", mode="append")

        assert result.success
        assert test_file.read_text() == "first\nsecond"

    def test_list_directory(
        self, fs_toolset: FilesystemToolset, temp_dir: Path
    ) -> None:
        """Should list directory contents."""
        (temp_dir / "file1.txt").touch()
        (temp_dir / "file2.txt").touch()

        result = fs_toolset.list_directory(str(temp_dir))

        assert result.success
        assert "file1.txt" in result.output
        assert "file2.txt" in result.output

    def test_delete_file(
        self, fs_toolset: FilesystemToolset, temp_dir: Path
    ) -> None:
        """Should delete file."""
        test_file = temp_dir / "to_delete.txt"
        test_file.touch()

        result = fs_toolset.delete_file(str(test_file))

        assert result.success
        assert not test_file.exists()

    def test_copy_file(
        self, fs_toolset: FilesystemToolset, temp_dir: Path
    ) -> None:
        """Should copy file."""
        src = temp_dir / "source.txt"
        dst = temp_dir / "dest.txt"
        src.write_text("copy me")

        result = fs_toolset.copy_file(str(src), str(dst))

        assert result.success
        assert dst.read_text() == "copy me"
        assert src.exists()  # Original still exists

    def test_move_file(
        self, fs_toolset: FilesystemToolset, temp_dir: Path
    ) -> None:
        """Should move file."""
        src = temp_dir / "source.txt"
        dst = temp_dir / "dest.txt"
        src.write_text("move me")

        result = fs_toolset.move_file(str(src), str(dst))

        assert result.success
        assert dst.read_text() == "move me"
        assert not src.exists()  # Original is gone

    def test_search_files(
        self, fs_toolset: FilesystemToolset, temp_dir: Path
    ) -> None:
        """Should search for files."""
        (temp_dir / "test1.py").touch()
        (temp_dir / "test2.py").touch()
        (temp_dir / "readme.md").touch()

        result = fs_toolset.search_files("*.py", path=str(temp_dir))

        assert result.success
        assert "test1.py" in result.output
        assert "test2.py" in result.output
        assert "readme.md" not in result.output

    def test_get_info(
        self, fs_toolset: FilesystemToolset, temp_dir: Path
    ) -> None:
        """Should get file info."""
        test_file = temp_dir / "info.txt"
        test_file.write_text("content")

        result = fs_toolset.get_info(str(test_file))

        assert result.success
        assert "Type:" in result.output
        assert "Size:" in result.output


class TestProcessToolset:
    """Test process toolset functionality."""

    @pytest.fixture
    def process_toolset(self, tool_registry: ToolRegistry) -> ProcessToolset:
        """Create process toolset."""
        toolset = ProcessToolset()
        toolset.register_tools(tool_registry)
        return toolset

    def test_register_tools(
        self, tool_registry: ToolRegistry, process_toolset: ProcessToolset
    ) -> None:
        """Should register all process tools."""
        names = tool_registry.list_tool_names()

        assert "process.list" in names
        assert "process.info" in names
        assert "process.kill" in names

    def test_list_processes(self, process_toolset: ProcessToolset) -> None:
        """Should list processes."""
        result = process_toolset.list_processes()

        assert result.success
        assert "PID" in result.output
        assert "CPU%" in result.output

    def test_list_processes_filtered(
        self, process_toolset: ProcessToolset
    ) -> None:
        """Should filter processes by name."""
        result = process_toolset.list_processes(filter="python")

        assert result.success
        # Should contain python or "No processes matching"
        assert "python" in result.output.lower() or "no processes" in result.output.lower()

    def test_get_process_info(self, process_toolset: ProcessToolset) -> None:
        """Should get process info."""
        # Get info for current process
        pid = os.getpid()
        result = process_toolset.get_process_info(pid)

        assert result.success
        assert str(pid) in result.output

    def test_get_process_info_not_found(
        self, process_toolset: ProcessToolset
    ) -> None:
        """Should handle missing process."""
        result = process_toolset.get_process_info(999999)

        assert not result.success
        assert "not found" in result.error.lower()

    def test_kill_process_safety_check(
        self, process_toolset: ProcessToolset
    ) -> None:
        """Should prevent killing critical processes."""
        result = process_toolset.kill_process(1)

        assert not result.success
        assert "PID <= 1" in result.error

    def test_kill_self_protection(self, process_toolset: ProcessToolset) -> None:
        """Should prevent killing self."""
        result = process_toolset.kill_process(os.getpid())

        assert not result.success
        assert "current process" in result.error.lower()


class TestCodeToolset:
    """Test code toolset functionality."""

    @pytest.fixture
    def code_toolset(self, tool_registry: ToolRegistry) -> CodeToolset:
        """Create code toolset."""
        toolset = CodeToolset()
        toolset.register_tools(tool_registry)
        return toolset

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_register_tools(
        self, tool_registry: ToolRegistry, code_toolset: CodeToolset
    ) -> None:
        """Should register all code tools."""
        names = tool_registry.list_tool_names()

        assert "code.read" in names
        assert "code.edit" in names
        assert "code.search" in names
        assert "code.insert" in names

    def test_read_code(
        self, code_toolset: CodeToolset, temp_dir: Path
    ) -> None:
        """Should read code with line numbers."""
        code_file = temp_dir / "test.py"
        code_file.write_text("line1\nline2\nline3\n")

        result = code_toolset.read_code(str(code_file))

        assert result.success
        assert "1 |" in result.output
        assert "line1" in result.output
        assert "line2" in result.output

    def test_read_code_range(
        self, code_toolset: CodeToolset, temp_dir: Path
    ) -> None:
        """Should read specific line range."""
        code_file = temp_dir / "test.py"
        code_file.write_text("line1\nline2\nline3\nline4\nline5\n")

        result = code_toolset.read_code(str(code_file), start_line=2, end_line=4)

        assert result.success
        assert "line2" in result.output
        assert "line3" in result.output
        assert "line4" in result.output
        assert "line1" not in result.output
        assert "line5" not in result.output

    def test_edit_code(
        self, code_toolset: CodeToolset, temp_dir: Path
    ) -> None:
        """Should edit code."""
        code_file = temp_dir / "test.py"
        code_file.write_text("def foo():\n    return 1\n")

        result = code_toolset.edit_code(
            str(code_file),
            old_text="return 1",
            new_text="return 42",
        )

        assert result.success
        assert code_file.read_text() == "def foo():\n    return 42\n"

    def test_edit_code_not_found(
        self, code_toolset: CodeToolset, temp_dir: Path
    ) -> None:
        """Should handle text not found."""
        code_file = temp_dir / "test.py"
        code_file.write_text("existing content")

        result = code_toolset.edit_code(
            str(code_file),
            old_text="nonexistent",
            new_text="replacement",
        )

        assert not result.success
        assert "not found" in result.error.lower()

    def test_edit_code_ambiguous(
        self, code_toolset: CodeToolset, temp_dir: Path
    ) -> None:
        """Should reject ambiguous edits."""
        code_file = temp_dir / "test.py"
        code_file.write_text("x = 1\nx = 1\n")  # Duplicate lines

        result = code_toolset.edit_code(
            str(code_file),
            old_text="x = 1",
            new_text="x = 2",
        )

        assert not result.success
        assert "appears 2 times" in result.error

    def test_search_code(
        self, code_toolset: CodeToolset, temp_dir: Path
    ) -> None:
        """Should search code."""
        code_file = temp_dir / "test.py"
        code_file.write_text("def hello():\n    print('hello')\n")

        result = code_toolset.search_code("hello", path=str(temp_dir))

        assert result.success
        assert "hello" in result.output

    def test_search_code_regex(
        self, code_toolset: CodeToolset, temp_dir: Path
    ) -> None:
        """Should support regex search."""
        code_file = temp_dir / "test.py"
        code_file.write_text("def foo():\ndef bar():\n")

        result = code_toolset.search_code(r"def \w+\(\)", path=str(temp_dir))

        assert result.success
        assert "match" in result.output.lower()

    def test_insert_code(
        self, code_toolset: CodeToolset, temp_dir: Path
    ) -> None:
        """Should insert code at line."""
        code_file = temp_dir / "test.py"
        code_file.write_text("line1\nline3\n")

        result = code_toolset.insert_code(
            str(code_file),
            line=2,
            text="line2",
        )

        assert result.success
        assert code_file.read_text() == "line1\nline2\nline3\n"


class TestShellToolsetExtended:
    """Extended tests for shell toolset edge cases."""

    @pytest.fixture
    def shell_toolset(self, tool_registry: ToolRegistry) -> ShellToolset:
        """Create shell toolset."""
        toolset = ShellToolset()
        toolset.register_tools(tool_registry)
        return toolset

    def test_run_empty_command(self, shell_toolset: ShellToolset) -> None:
        """Should reject empty command."""
        result = asyncio.run(shell_toolset.run_command(""))
        assert not result.success
        assert "Empty command" in result.error

    def test_run_whitespace_command(self, shell_toolset: ShellToolset) -> None:
        """Should reject whitespace-only command."""
        result = asyncio.run(shell_toolset.run_command("   "))
        assert not result.success
        assert "Empty command" in result.error

    def test_run_command_with_stderr(self, shell_toolset: ShellToolset) -> None:
        """Should capture stderr output."""
        result = asyncio.run(shell_toolset.run_command("ls /nonexistent_dir_xyz"))
        # Command should fail and stderr should be captured
        assert not result.success
        assert "STDERR" in result.output or "No such file" in result.output

    def test_run_command_with_cwd(self, shell_toolset: ShellToolset) -> None:
        """Should run command in specified directory."""
        result = asyncio.run(shell_toolset.run_command("pwd", cwd="/tmp"))
        assert result.success
        assert "/tmp" in result.output

    def test_explain_empty_command(self, shell_toolset: ShellToolset) -> None:
        """Should reject empty command for explain."""
        result = shell_toolset.explain_command("")
        assert not result.success
        assert "Empty command" in result.error

    def test_explain_invalid_syntax(self, shell_toolset: ShellToolset) -> None:
        """Should handle invalid command syntax."""
        result = shell_toolset.explain_command("echo 'unclosed quote")
        assert not result.success
        assert "Invalid command syntax" in result.error

    def test_explain_unknown_command(self, shell_toolset: ShellToolset) -> None:
        """Should provide generic explanation for unknown command."""
        result = shell_toolset.explain_command("some_unknown_cmd -v arg1")
        assert result.success
        assert "some_unknown_cmd" in result.output
        assert "Execute the 'some_unknown_cmd' command" in result.output

    def test_explain_command_flags_and_args(self, shell_toolset: ShellToolset) -> None:
        """Should show flags and arguments."""
        result = shell_toolset.explain_command("grep -r -n pattern file.txt")
        assert result.success
        assert "Flags:" in result.output
        assert "-r" in result.output
        assert "Arguments:" in result.output
        assert "pattern" in result.output

    def test_which_empty_program(self, shell_toolset: ShellToolset) -> None:
        """Should reject empty program name."""
        result = shell_toolset.which("")
        assert not result.success
        assert "Empty program name" in result.error

    def test_get_env_empty_name(self, shell_toolset: ShellToolset) -> None:
        """Should reject empty variable name."""
        result = shell_toolset.get_env("")
        assert not result.success
        assert "Empty variable name" in result.error

    def test_toolset_properties(self, shell_toolset: ShellToolset) -> None:
        """Should have correct name and description."""
        assert shell_toolset.name == "shell"
        assert "shell" in shell_toolset.description.lower()


class TestCodeToolsetExtended:
    """Extended tests for code toolset edge cases."""

    @pytest.fixture
    def code_toolset(self, tool_registry: ToolRegistry) -> CodeToolset:
        """Create code toolset."""
        toolset = CodeToolset()
        toolset.register_tools(tool_registry)
        return toolset

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_read_code_file_not_found(self, code_toolset: CodeToolset) -> None:
        """Should handle missing file."""
        result = code_toolset.read_code("/nonexistent/file.py")
        assert not result.success
        assert "not found" in result.error.lower()

    def test_edit_code_file_not_found(self, code_toolset: CodeToolset) -> None:
        """Should handle missing file for edit."""
        result = code_toolset.edit_code(
            "/nonexistent/file.py",
            old_text="old",
            new_text="new",
        )
        assert not result.success
        assert "not found" in result.error.lower()

    def test_insert_code_invalid_line(
        self, code_toolset: CodeToolset, temp_dir: Path
    ) -> None:
        """Should handle invalid line number."""
        code_file = temp_dir / "test.py"
        code_file.write_text("line1\nline2\n")

        result = code_toolset.insert_code(str(code_file), line=100, text="new")
        assert result.success  # Should append at end for out of range

    def test_search_code_no_matches(
        self, code_toolset: CodeToolset, temp_dir: Path
    ) -> None:
        """Should handle no matches."""
        code_file = temp_dir / "test.py"
        code_file.write_text("hello world")

        result = code_toolset.search_code("nonexistent_xyz", path=str(temp_dir))
        assert result.success
        assert "no matches" in result.output.lower() or result.output == ""


class TestFilesystemToolsetExtended:
    """Extended tests for filesystem toolset edge cases."""

    @pytest.fixture
    def fs_toolset(self, tool_registry: ToolRegistry) -> FilesystemToolset:
        """Create filesystem toolset."""
        toolset = FilesystemToolset()
        toolset.register_tools(tool_registry)
        return toolset

    @pytest.fixture
    def temp_dir(self) -> Path:
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_read_directory_error(self, fs_toolset: FilesystemToolset, temp_dir: Path) -> None:
        """Should handle trying to read a directory as file."""
        result = fs_toolset.read_file(str(temp_dir))
        assert not result.success

    def test_list_nonexistent_directory(self, fs_toolset: FilesystemToolset) -> None:
        """Should handle listing nonexistent directory."""
        result = fs_toolset.list_directory("/nonexistent/dir/xyz")
        assert not result.success

    def test_delete_nonexistent_file(self, fs_toolset: FilesystemToolset) -> None:
        """Should handle deleting nonexistent file."""
        result = fs_toolset.delete_file("/nonexistent/file.txt")
        assert not result.success

    def test_copy_nonexistent_source(self, fs_toolset: FilesystemToolset) -> None:
        """Should handle copying nonexistent source."""
        result = fs_toolset.copy_file("/nonexistent/src.txt", "/tmp/dst.txt")
        assert not result.success

    def test_move_nonexistent_source(self, fs_toolset: FilesystemToolset) -> None:
        """Should handle moving nonexistent source."""
        result = fs_toolset.move_file("/nonexistent/src.txt", "/tmp/dst.txt")
        assert not result.success

    def test_get_info_nonexistent(self, fs_toolset: FilesystemToolset) -> None:
        """Should handle info for nonexistent path."""
        result = fs_toolset.get_info("/nonexistent/file.txt")
        assert not result.success

    def test_toolset_properties(self, fs_toolset: FilesystemToolset) -> None:
        """Should have correct name and description."""
        assert fs_toolset.name == "filesystem"
        assert "file" in fs_toolset.description.lower()
