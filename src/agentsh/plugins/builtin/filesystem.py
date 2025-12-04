"""Filesystem toolset - File operations."""

import fnmatch
import os
import shutil
import stat
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from agentsh.plugins.base import Toolset
from agentsh.tools.base import RiskLevel, ToolResult

if TYPE_CHECKING:
    from agentsh.tools.registry import ToolRegistry


class FilesystemToolset(Toolset):
    """Provides filesystem operation tools.

    Tools:
    - fs.read: Read file contents
    - fs.write: Write to a file
    - fs.list: List directory contents
    - fs.delete: Delete a file or directory
    - fs.copy: Copy a file or directory
    - fs.move: Move or rename a file
    - fs.search: Search for files by pattern
    - fs.info: Get file/directory information
    """

    @property
    def name(self) -> str:
        return "filesystem"

    @property
    def description(self) -> str:
        return "Read, write, and manage files and directories"

    def register_tools(self, registry: "ToolRegistry") -> None:
        """Register filesystem tools."""
        registry.register_tool(
            name="fs.read",
            handler=self.read_file,
            description="Read the contents of a file. Returns the file content as text.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to read",
                    },
                    "encoding": {
                        "type": "string",
                        "description": "File encoding (default: utf-8)",
                    },
                    "max_bytes": {
                        "type": "integer",
                        "description": "Maximum bytes to read (default: 100000)",
                    },
                },
                "required": ["path"],
            },
            risk_level=RiskLevel.SAFE,
            plugin_name=self.name,
        )

        registry.register_tool(
            name="fs.write",
            handler=self.write_file,
            description="Write content to a file. Creates parent directories if needed.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to write",
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["write", "append"],
                        "description": "Write mode (default: write)",
                    },
                    "encoding": {
                        "type": "string",
                        "description": "File encoding (default: utf-8)",
                    },
                },
                "required": ["path", "content"],
            },
            risk_level=RiskLevel.MEDIUM,
            plugin_name=self.name,
        )

        registry.register_tool(
            name="fs.list",
            handler=self.list_directory,
            description="List contents of a directory with optional filtering.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path",
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "List recursively (default: false)",
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern to filter files (e.g., '*.py')",
                    },
                    "include_hidden": {
                        "type": "boolean",
                        "description": "Include hidden files (default: false)",
                    },
                },
                "required": ["path"],
            },
            risk_level=RiskLevel.SAFE,
            plugin_name=self.name,
        )

        registry.register_tool(
            name="fs.delete",
            handler=self.delete_file,
            description="Delete a file or directory. Use recursive=true for directories.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to delete",
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Delete recursively for directories (default: false)",
                    },
                },
                "required": ["path"],
            },
            risk_level=RiskLevel.HIGH,
            requires_confirmation=True,
            plugin_name=self.name,
        )

        registry.register_tool(
            name="fs.copy",
            handler=self.copy_file,
            description="Copy a file or directory to a new location.",
            parameters={
                "type": "object",
                "properties": {
                    "src": {
                        "type": "string",
                        "description": "Source path",
                    },
                    "dst": {
                        "type": "string",
                        "description": "Destination path",
                    },
                },
                "required": ["src", "dst"],
            },
            risk_level=RiskLevel.MEDIUM,
            plugin_name=self.name,
        )

        registry.register_tool(
            name="fs.move",
            handler=self.move_file,
            description="Move or rename a file or directory.",
            parameters={
                "type": "object",
                "properties": {
                    "src": {
                        "type": "string",
                        "description": "Source path",
                    },
                    "dst": {
                        "type": "string",
                        "description": "Destination path",
                    },
                },
                "required": ["src", "dst"],
            },
            risk_level=RiskLevel.MEDIUM,
            plugin_name=self.name,
        )

        registry.register_tool(
            name="fs.search",
            handler=self.search_files,
            description="Search for files matching a pattern in a directory tree.",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern to match (e.g., '*.py', '**/*.txt')",
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory to search in (default: current dir)",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum results to return (default: 100)",
                    },
                },
                "required": ["pattern"],
            },
            risk_level=RiskLevel.SAFE,
            plugin_name=self.name,
        )

        registry.register_tool(
            name="fs.info",
            handler=self.get_info,
            description="Get information about a file or directory (size, permissions, dates).",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to get info for",
                    },
                },
                "required": ["path"],
            },
            risk_level=RiskLevel.SAFE,
            plugin_name=self.name,
        )

    def read_file(
        self,
        path: str,
        encoding: str = "utf-8",
        max_bytes: int = 100000,
    ) -> ToolResult:
        """Read file contents.

        Args:
            path: Path to file
            encoding: Text encoding
            max_bytes: Maximum bytes to read

        Returns:
            ToolResult with file contents
        """
        try:
            file_path = Path(path).expanduser().resolve()

            if not file_path.exists():
                return ToolResult(
                    success=False,
                    error=f"File not found: {path}",
                )

            if not file_path.is_file():
                return ToolResult(
                    success=False,
                    error=f"Not a file: {path}",
                )

            # Check file size
            size = file_path.stat().st_size
            if size > max_bytes:
                with open(file_path, "r", encoding=encoding) as f:
                    content = f.read(max_bytes)
                return ToolResult(
                    success=True,
                    output=f"{content}\n\n... (truncated, file is {size} bytes)",
                )

            with open(file_path, "r", encoding=encoding) as f:
                content = f.read()

            return ToolResult(success=True, output=content)

        except UnicodeDecodeError:
            return ToolResult(
                success=False,
                error=f"Cannot decode file with encoding '{encoding}'. Try a different encoding.",
            )
        except PermissionError:
            return ToolResult(
                success=False,
                error=f"Permission denied: {path}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to read file: {str(e)}",
            )

    def write_file(
        self,
        path: str,
        content: str,
        mode: str = "write",
        encoding: str = "utf-8",
    ) -> ToolResult:
        """Write content to a file.

        Args:
            path: Path to file
            content: Content to write
            mode: 'write' or 'append'
            encoding: Text encoding

        Returns:
            ToolResult with success status
        """
        try:
            file_path = Path(path).expanduser().resolve()

            # Create parent directories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)

            write_mode = "a" if mode == "append" else "w"

            with open(file_path, write_mode, encoding=encoding) as f:
                f.write(content)

            action = "appended to" if mode == "append" else "written to"
            return ToolResult(
                success=True,
                output=f"Successfully {action} {path} ({len(content)} bytes)",
            )

        except PermissionError:
            return ToolResult(
                success=False,
                error=f"Permission denied: {path}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to write file: {str(e)}",
            )

    def list_directory(
        self,
        path: str,
        recursive: bool = False,
        pattern: Optional[str] = None,
        include_hidden: bool = False,
    ) -> ToolResult:
        """List directory contents.

        Args:
            path: Directory path
            recursive: List recursively
            pattern: Glob pattern filter
            include_hidden: Include hidden files

        Returns:
            ToolResult with file listing
        """
        try:
            dir_path = Path(path).expanduser().resolve()

            if not dir_path.exists():
                return ToolResult(
                    success=False,
                    error=f"Directory not found: {path}",
                )

            if not dir_path.is_dir():
                return ToolResult(
                    success=False,
                    error=f"Not a directory: {path}",
                )

            entries = []

            if recursive:
                for item in dir_path.rglob("*"):
                    rel_path = item.relative_to(dir_path)
                    name = str(rel_path)

                    # Skip hidden if not included
                    if not include_hidden and any(
                        p.startswith(".") for p in rel_path.parts
                    ):
                        continue

                    # Apply pattern filter
                    if pattern and not fnmatch.fnmatch(name, pattern):
                        continue

                    entry_type = "d" if item.is_dir() else "f"
                    entries.append(f"[{entry_type}] {name}")
            else:
                for item in dir_path.iterdir():
                    name = item.name

                    # Skip hidden if not included
                    if not include_hidden and name.startswith("."):
                        continue

                    # Apply pattern filter
                    if pattern and not fnmatch.fnmatch(name, pattern):
                        continue

                    entry_type = "d" if item.is_dir() else "f"
                    entries.append(f"[{entry_type}] {name}")

            entries.sort()

            if not entries:
                return ToolResult(
                    success=True,
                    output="(empty directory)",
                )

            return ToolResult(
                success=True,
                output="\n".join(entries),
            )

        except PermissionError:
            return ToolResult(
                success=False,
                error=f"Permission denied: {path}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to list directory: {str(e)}",
            )

    def delete_file(
        self,
        path: str,
        recursive: bool = False,
    ) -> ToolResult:
        """Delete a file or directory.

        Args:
            path: Path to delete
            recursive: Delete directories recursively

        Returns:
            ToolResult with success status
        """
        try:
            file_path = Path(path).expanduser().resolve()

            if not file_path.exists():
                return ToolResult(
                    success=False,
                    error=f"Path not found: {path}",
                )

            if file_path.is_dir():
                if recursive:
                    shutil.rmtree(file_path)
                    return ToolResult(
                        success=True,
                        output=f"Deleted directory: {path}",
                    )
                else:
                    # Try to remove empty directory
                    try:
                        file_path.rmdir()
                        return ToolResult(
                            success=True,
                            output=f"Deleted empty directory: {path}",
                        )
                    except OSError:
                        return ToolResult(
                            success=False,
                            error=f"Directory not empty. Use recursive=true to delete: {path}",
                        )
            else:
                file_path.unlink()
                return ToolResult(
                    success=True,
                    output=f"Deleted file: {path}",
                )

        except PermissionError:
            return ToolResult(
                success=False,
                error=f"Permission denied: {path}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to delete: {str(e)}",
            )

    def copy_file(self, src: str, dst: str) -> ToolResult:
        """Copy a file or directory.

        Args:
            src: Source path
            dst: Destination path

        Returns:
            ToolResult with success status
        """
        try:
            src_path = Path(src).expanduser().resolve()
            dst_path = Path(dst).expanduser().resolve()

            if not src_path.exists():
                return ToolResult(
                    success=False,
                    error=f"Source not found: {src}",
                )

            # Create parent directories
            dst_path.parent.mkdir(parents=True, exist_ok=True)

            if src_path.is_dir():
                shutil.copytree(src_path, dst_path)
                return ToolResult(
                    success=True,
                    output=f"Copied directory: {src} -> {dst}",
                )
            else:
                shutil.copy2(src_path, dst_path)
                return ToolResult(
                    success=True,
                    output=f"Copied file: {src} -> {dst}",
                )

        except PermissionError:
            return ToolResult(
                success=False,
                error=f"Permission denied",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to copy: {str(e)}",
            )

    def move_file(self, src: str, dst: str) -> ToolResult:
        """Move or rename a file or directory.

        Args:
            src: Source path
            dst: Destination path

        Returns:
            ToolResult with success status
        """
        try:
            src_path = Path(src).expanduser().resolve()
            dst_path = Path(dst).expanduser().resolve()

            if not src_path.exists():
                return ToolResult(
                    success=False,
                    error=f"Source not found: {src}",
                )

            # Create parent directories
            dst_path.parent.mkdir(parents=True, exist_ok=True)

            shutil.move(str(src_path), str(dst_path))

            return ToolResult(
                success=True,
                output=f"Moved: {src} -> {dst}",
            )

        except PermissionError:
            return ToolResult(
                success=False,
                error=f"Permission denied",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to move: {str(e)}",
            )

    def search_files(
        self,
        pattern: str,
        path: Optional[str] = None,
        max_results: int = 100,
    ) -> ToolResult:
        """Search for files matching a pattern.

        Args:
            pattern: Glob pattern
            path: Directory to search in
            max_results: Maximum results to return

        Returns:
            ToolResult with matching files
        """
        try:
            search_path = Path(path or ".").expanduser().resolve()

            if not search_path.exists():
                return ToolResult(
                    success=False,
                    error=f"Directory not found: {path}",
                )

            matches = []
            for match in search_path.rglob(pattern):
                rel_path = match.relative_to(search_path)
                entry_type = "d" if match.is_dir() else "f"
                matches.append(f"[{entry_type}] {rel_path}")

                if len(matches) >= max_results:
                    break

            if not matches:
                return ToolResult(
                    success=True,
                    output=f"No files matching '{pattern}' found",
                )

            output = "\n".join(matches)
            if len(matches) >= max_results:
                output += f"\n\n... (limited to {max_results} results)"

            return ToolResult(success=True, output=output)

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Search failed: {str(e)}",
            )

    def get_info(self, path: str) -> ToolResult:
        """Get file/directory information.

        Args:
            path: Path to get info for

        Returns:
            ToolResult with file information
        """
        try:
            file_path = Path(path).expanduser().resolve()

            if not file_path.exists():
                return ToolResult(
                    success=False,
                    error=f"Path not found: {path}",
                )

            stats = file_path.stat()

            info = []
            info.append(f"Path: {file_path}")
            info.append(f"Type: {'directory' if file_path.is_dir() else 'file'}")
            info.append(f"Size: {self._format_size(stats.st_size)}")
            info.append(f"Permissions: {stat.filemode(stats.st_mode)}")
            info.append(
                f"Modified: {datetime.fromtimestamp(stats.st_mtime).isoformat()}"
            )
            info.append(
                f"Created: {datetime.fromtimestamp(stats.st_ctime).isoformat()}"
            )

            if file_path.is_symlink():
                info.append(f"Link target: {os.readlink(file_path)}")

            return ToolResult(success=True, output="\n".join(info))

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to get info: {str(e)}",
            )

    def _format_size(self, size: int) -> str:
        """Format file size in human-readable form."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"
