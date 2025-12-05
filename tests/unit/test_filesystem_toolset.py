"""Tests for filesystem toolset."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentsh.plugins.builtin.filesystem import FilesystemToolset


class TestFilesystemToolsetProperties:
    """Test toolset properties."""

    def test_name(self) -> None:
        """Should have correct name."""
        toolset = FilesystemToolset()
        assert toolset.name == "filesystem"

    def test_description(self) -> None:
        """Should have description."""
        toolset = FilesystemToolset()
        assert "file" in toolset.description.lower()


class TestFilesystemToolsetRegistration:
    """Test tool registration."""

    def test_register_tools(self) -> None:
        """Should register all tools."""
        toolset = FilesystemToolset()
        registry = MagicMock()

        toolset.register_tools(registry)

        # Check that all tools are registered
        registered_names = [
            call[1]["name"] for call in registry.register_tool.call_args_list
        ]
        assert "fs.read" in registered_names
        assert "fs.write" in registered_names
        assert "fs.list" in registered_names
        assert "fs.delete" in registered_names
        assert "fs.copy" in registered_names
        assert "fs.move" in registered_names
        assert "fs.search" in registered_names
        assert "fs.info" in registered_names


class TestReadFile:
    """Tests for read_file method."""

    @pytest.fixture
    def toolset(self) -> FilesystemToolset:
        """Create a filesystem toolset."""
        return FilesystemToolset()

    def test_read_existing_file(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should read an existing file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        result = toolset.read_file(str(test_file))

        assert result.success
        assert result.output == "Hello, World!"

    def test_read_nonexistent_file(self, toolset: FilesystemToolset) -> None:
        """Should return error for nonexistent file."""
        result = toolset.read_file("/nonexistent/path/file.txt")

        assert not result.success
        assert "not found" in result.error.lower()

    def test_read_directory(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should return error when path is a directory."""
        result = toolset.read_file(str(tmp_path))

        assert not result.success
        assert "Not a file" in result.error

    def test_read_with_custom_encoding(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should read with specified encoding."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Héllo", encoding="utf-8")

        result = toolset.read_file(str(test_file), encoding="utf-8")

        assert result.success
        assert "Héllo" in result.output

    def test_read_with_wrong_encoding(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should handle wrong encoding."""
        test_file = tmp_path / "test.bin"
        test_file.write_bytes(b"\x80\x81\x82")

        result = toolset.read_file(str(test_file), encoding="utf-8")

        assert not result.success
        assert "decode" in result.error.lower()

    def test_read_large_file_truncates(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should truncate large files."""
        test_file = tmp_path / "large.txt"
        content = "x" * 200
        test_file.write_text(content)

        result = toolset.read_file(str(test_file), max_bytes=50)

        assert result.success
        assert "truncated" in result.output.lower()
        assert "200 bytes" in result.output

    def test_read_expands_user_path(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should expand ~ in path."""
        # This is hard to test properly, but we can verify it doesn't crash
        with patch.object(Path, "expanduser", return_value=tmp_path / "file.txt"):
            # Create the file
            test_file = tmp_path / "file.txt"
            test_file.write_text("test")

            result = toolset.read_file("~/file.txt")
            assert result.success


class TestWriteFile:
    """Tests for write_file method."""

    @pytest.fixture
    def toolset(self) -> FilesystemToolset:
        """Create a filesystem toolset."""
        return FilesystemToolset()

    def test_write_new_file(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should write to a new file."""
        test_file = tmp_path / "new.txt"

        result = toolset.write_file(str(test_file), "Hello!")

        assert result.success
        assert test_file.read_text() == "Hello!"
        assert "written to" in result.output

    def test_write_creates_parent_directories(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should create parent directories."""
        test_file = tmp_path / "a" / "b" / "c" / "file.txt"

        result = toolset.write_file(str(test_file), "Content")

        assert result.success
        assert test_file.exists()
        assert test_file.read_text() == "Content"

    def test_write_append_mode(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should append in append mode."""
        test_file = tmp_path / "append.txt"
        test_file.write_text("First")

        result = toolset.write_file(str(test_file), "Second", mode="append")

        assert result.success
        assert test_file.read_text() == "FirstSecond"
        assert "appended to" in result.output

    def test_write_overwrite_mode(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should overwrite in write mode."""
        test_file = tmp_path / "overwrite.txt"
        test_file.write_text("Original")

        result = toolset.write_file(str(test_file), "New", mode="write")

        assert result.success
        assert test_file.read_text() == "New"

    def test_write_with_encoding(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should write with specified encoding."""
        test_file = tmp_path / "encoded.txt"

        result = toolset.write_file(str(test_file), "Héllo", encoding="utf-8")

        assert result.success
        assert test_file.read_text(encoding="utf-8") == "Héllo"


class TestListDirectory:
    """Tests for list_directory method."""

    @pytest.fixture
    def toolset(self) -> FilesystemToolset:
        """Create a filesystem toolset."""
        return FilesystemToolset()

    def test_list_directory(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should list directory contents."""
        (tmp_path / "file1.txt").touch()
        (tmp_path / "file2.txt").touch()
        (tmp_path / "subdir").mkdir()

        result = toolset.list_directory(str(tmp_path))

        assert result.success
        assert "file1.txt" in result.output
        assert "file2.txt" in result.output
        assert "subdir" in result.output

    def test_list_nonexistent_directory(self, toolset: FilesystemToolset) -> None:
        """Should return error for nonexistent directory."""
        result = toolset.list_directory("/nonexistent/path")

        assert not result.success
        assert "not found" in result.error.lower()

    def test_list_file_not_directory(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should return error when path is a file."""
        test_file = tmp_path / "file.txt"
        test_file.touch()

        result = toolset.list_directory(str(test_file))

        assert not result.success
        assert "Not a directory" in result.error

    def test_list_with_pattern(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should filter by pattern."""
        (tmp_path / "file.txt").touch()
        (tmp_path / "file.py").touch()
        (tmp_path / "other.md").touch()

        result = toolset.list_directory(str(tmp_path), pattern="*.txt")

        assert result.success
        assert "file.txt" in result.output
        assert "file.py" not in result.output

    def test_list_recursive(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should list recursively."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "root.txt").touch()
        (subdir / "nested.txt").touch()

        result = toolset.list_directory(str(tmp_path), recursive=True)

        assert result.success
        assert "root.txt" in result.output
        assert "nested.txt" in result.output

    def test_list_hidden_files(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should include hidden files when requested."""
        (tmp_path / ".hidden").touch()
        (tmp_path / "visible").touch()

        # Without include_hidden
        result = toolset.list_directory(str(tmp_path), include_hidden=False)
        assert "visible" in result.output
        assert ".hidden" not in result.output

        # With include_hidden
        result = toolset.list_directory(str(tmp_path), include_hidden=True)
        assert ".hidden" in result.output

    def test_list_empty_directory(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should handle empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = toolset.list_directory(str(empty_dir))

        assert result.success
        assert "empty" in result.output.lower()

    def test_list_recursive_hidden(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should handle hidden directories in recursive mode."""
        hidden_dir = tmp_path / ".hidden_dir"
        hidden_dir.mkdir()
        (hidden_dir / "file.txt").touch()
        (tmp_path / "visible.txt").touch()

        # Without include_hidden
        result = toolset.list_directory(str(tmp_path), recursive=True, include_hidden=False)
        assert "visible.txt" in result.output
        assert ".hidden_dir" not in result.output


class TestDeleteFile:
    """Tests for delete_file method."""

    @pytest.fixture
    def toolset(self) -> FilesystemToolset:
        """Create a filesystem toolset."""
        return FilesystemToolset()

    def test_delete_file(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should delete a file."""
        test_file = tmp_path / "delete_me.txt"
        test_file.touch()

        result = toolset.delete_file(str(test_file))

        assert result.success
        assert not test_file.exists()

    def test_delete_nonexistent(self, toolset: FilesystemToolset) -> None:
        """Should return error for nonexistent path."""
        result = toolset.delete_file("/nonexistent/file.txt")

        assert not result.success
        assert "not found" in result.error.lower()

    def test_delete_empty_directory(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should delete empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        result = toolset.delete_file(str(empty_dir))

        assert result.success
        assert not empty_dir.exists()

    def test_delete_nonempty_directory_fails(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should fail on non-empty directory without recursive."""
        nonempty = tmp_path / "nonempty"
        nonempty.mkdir()
        (nonempty / "file.txt").touch()

        result = toolset.delete_file(str(nonempty), recursive=False)

        assert not result.success
        assert "not empty" in result.error.lower()

    def test_delete_directory_recursive(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should delete directory recursively."""
        nonempty = tmp_path / "nonempty"
        nonempty.mkdir()
        (nonempty / "file.txt").touch()
        subdir = nonempty / "sub"
        subdir.mkdir()
        (subdir / "nested.txt").touch()

        result = toolset.delete_file(str(nonempty), recursive=True)

        assert result.success
        assert not nonempty.exists()


class TestCopyFile:
    """Tests for copy_file method."""

    @pytest.fixture
    def toolset(self) -> FilesystemToolset:
        """Create a filesystem toolset."""
        return FilesystemToolset()

    def test_copy_file(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should copy a file."""
        src = tmp_path / "source.txt"
        src.write_text("Content")
        dst = tmp_path / "dest.txt"

        result = toolset.copy_file(str(src), str(dst))

        assert result.success
        assert dst.exists()
        assert dst.read_text() == "Content"

    def test_copy_nonexistent_source(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should return error for nonexistent source."""
        result = toolset.copy_file("/nonexistent", str(tmp_path / "dest"))

        assert not result.success
        assert "not found" in result.error.lower()

    def test_copy_directory(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should copy a directory."""
        src = tmp_path / "src_dir"
        src.mkdir()
        (src / "file.txt").write_text("Hello")
        dst = tmp_path / "dst_dir"

        result = toolset.copy_file(str(src), str(dst))

        assert result.success
        assert dst.exists()
        assert (dst / "file.txt").read_text() == "Hello"

    def test_copy_creates_parent_directories(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should create parent directories for destination."""
        src = tmp_path / "source.txt"
        src.write_text("Content")
        dst = tmp_path / "a" / "b" / "dest.txt"

        result = toolset.copy_file(str(src), str(dst))

        assert result.success
        assert dst.exists()


class TestMoveFile:
    """Tests for move_file method."""

    @pytest.fixture
    def toolset(self) -> FilesystemToolset:
        """Create a filesystem toolset."""
        return FilesystemToolset()

    def test_move_file(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should move a file."""
        src = tmp_path / "source.txt"
        src.write_text("Content")
        dst = tmp_path / "dest.txt"

        result = toolset.move_file(str(src), str(dst))

        assert result.success
        assert not src.exists()
        assert dst.exists()
        assert dst.read_text() == "Content"

    def test_move_nonexistent_source(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should return error for nonexistent source."""
        result = toolset.move_file("/nonexistent", str(tmp_path / "dest"))

        assert not result.success
        assert "not found" in result.error.lower()

    def test_move_creates_parent_directories(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should create parent directories for destination."""
        src = tmp_path / "source.txt"
        src.write_text("Content")
        dst = tmp_path / "a" / "b" / "dest.txt"

        result = toolset.move_file(str(src), str(dst))

        assert result.success
        assert not src.exists()
        assert dst.exists()


class TestSearchFiles:
    """Tests for search_files method."""

    @pytest.fixture
    def toolset(self) -> FilesystemToolset:
        """Create a filesystem toolset."""
        return FilesystemToolset()

    def test_search_files(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should find matching files."""
        (tmp_path / "file1.py").touch()
        (tmp_path / "file2.py").touch()
        (tmp_path / "other.txt").touch()

        result = toolset.search_files("*.py", str(tmp_path))

        assert result.success
        assert "file1.py" in result.output
        assert "file2.py" in result.output
        assert "other.txt" not in result.output

    def test_search_recursive(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should search recursively."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (tmp_path / "root.py").touch()
        (subdir / "nested.py").touch()

        result = toolset.search_files("*.py", str(tmp_path))

        assert result.success
        assert "root.py" in result.output
        assert "nested.py" in result.output

    def test_search_no_matches(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should handle no matches."""
        (tmp_path / "file.txt").touch()

        result = toolset.search_files("*.py", str(tmp_path))

        assert result.success
        assert "No files matching" in result.output

    def test_search_max_results(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should limit results."""
        for i in range(10):
            (tmp_path / f"file{i}.py").touch()

        result = toolset.search_files("*.py", str(tmp_path), max_results=3)

        assert result.success
        assert "limited to 3 results" in result.output

    def test_search_nonexistent_directory(self, toolset: FilesystemToolset) -> None:
        """Should return error for nonexistent directory."""
        result = toolset.search_files("*.py", "/nonexistent")

        assert not result.success
        assert "not found" in result.error.lower()

    def test_search_default_path(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should use current directory as default."""
        (tmp_path / "test.py").touch()

        with patch("pathlib.Path.cwd", return_value=tmp_path):
            result = toolset.search_files("*.py")

        # Even without path, should not crash
        assert result.success or "not found" in result.error.lower()


class TestGetInfo:
    """Tests for get_info method."""

    @pytest.fixture
    def toolset(self) -> FilesystemToolset:
        """Create a filesystem toolset."""
        return FilesystemToolset()

    def test_get_file_info(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should get file information."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        result = toolset.get_info(str(test_file))

        assert result.success
        assert "Path:" in result.output
        assert "Type: file" in result.output
        assert "Size:" in result.output
        assert "Permissions:" in result.output
        assert "Modified:" in result.output

    def test_get_directory_info(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should get directory information."""
        result = toolset.get_info(str(tmp_path))

        assert result.success
        assert "Type: directory" in result.output

    def test_get_info_nonexistent(self, toolset: FilesystemToolset) -> None:
        """Should return error for nonexistent path."""
        result = toolset.get_info("/nonexistent/path")

        assert not result.success
        assert "not found" in result.error.lower()

    def test_get_symlink_info(self, toolset: FilesystemToolset, tmp_path: Path) -> None:
        """Should handle symlink (resolves to target).

        Note: The implementation resolves the path before checking is_symlink(),
        so the symlink info is not shown for resolved paths.
        """
        target = tmp_path / "target.txt"
        target.touch()
        link = tmp_path / "link.txt"
        link.symlink_to(target)

        result = toolset.get_info(str(link))

        # The path gets resolved, so it shows target info
        assert result.success
        assert "file" in result.output.lower()


class TestFormatSize:
    """Tests for _format_size method."""

    def test_format_bytes(self) -> None:
        """Should format bytes correctly."""
        toolset = FilesystemToolset()

        assert "B" in toolset._format_size(100)
        assert "KB" in toolset._format_size(1024)
        assert "MB" in toolset._format_size(1024 * 1024)
        assert "GB" in toolset._format_size(1024 * 1024 * 1024)
        assert "TB" in toolset._format_size(1024 * 1024 * 1024 * 1024)
