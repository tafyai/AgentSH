"""Code toolset - Code editing and search."""

import re
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from agentsh.plugins.base import Toolset
from agentsh.tools.base import RiskLevel, ToolResult

if TYPE_CHECKING:
    from agentsh.tools.registry import ToolRegistry


class CodeToolset(Toolset):
    """Provides code editing and search tools.

    Tools:
    - code.read: Read code with line numbers
    - code.edit: Make targeted code edits
    - code.search: Search in code files
    - code.insert: Insert text at a specific line
    """

    @property
    def name(self) -> str:
        return "code"

    @property
    def description(self) -> str:
        return "Read, edit, and search code files"

    def register_tools(self, registry: "ToolRegistry") -> None:
        """Register code tools."""
        registry.register_tool(
            name="code.read",
            handler=self.read_code,
            description="Read a code file with line numbers. Use start_line and end_line to read a specific range.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the code file",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Starting line number (1-indexed)",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Ending line number (inclusive)",
                    },
                },
                "required": ["path"],
            },
            risk_level=RiskLevel.SAFE,
            plugin_name=self.name,
        )

        registry.register_tool(
            name="code.edit",
            handler=self.edit_code,
            description="Make a targeted edit to a code file by replacing old_text with new_text. The old_text must be an exact match.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the code file",
                    },
                    "old_text": {
                        "type": "string",
                        "description": "Exact text to find and replace",
                    },
                    "new_text": {
                        "type": "string",
                        "description": "Replacement text",
                    },
                },
                "required": ["path", "old_text", "new_text"],
            },
            risk_level=RiskLevel.MEDIUM,
            plugin_name=self.name,
        )

        registry.register_tool(
            name="code.search",
            handler=self.search_code,
            description="Search for a pattern in code files. Returns matching lines with context.",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Search pattern (regex supported)",
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory to search in (default: current dir)",
                    },
                    "file_pattern": {
                        "type": "string",
                        "description": "Glob pattern for files (e.g., '*.py')",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum results to return (default: 50)",
                    },
                },
                "required": ["pattern"],
            },
            risk_level=RiskLevel.SAFE,
            plugin_name=self.name,
        )

        registry.register_tool(
            name="code.insert",
            handler=self.insert_code,
            description="Insert text at a specific line in a file.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the code file",
                    },
                    "line": {
                        "type": "integer",
                        "description": "Line number to insert at (1-indexed)",
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to insert",
                    },
                },
                "required": ["path", "line", "text"],
            },
            risk_level=RiskLevel.MEDIUM,
            plugin_name=self.name,
        )

    def read_code(
        self,
        path: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
    ) -> ToolResult:
        """Read code file with line numbers.

        Args:
            path: Path to file
            start_line: Starting line (1-indexed)
            end_line: Ending line (inclusive)

        Returns:
            ToolResult with numbered code lines
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

            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            total_lines = len(lines)

            # Handle line range
            if start_line is not None:
                start_idx = max(0, start_line - 1)
            else:
                start_idx = 0

            if end_line is not None:
                end_idx = min(total_lines, end_line)
            else:
                end_idx = total_lines

            # Format with line numbers
            output_lines = []
            for i in range(start_idx, end_idx):
                line_num = i + 1
                line_content = lines[i].rstrip("\n")
                output_lines.append(f"{line_num:>4} | {line_content}")

            if not output_lines:
                return ToolResult(
                    success=True,
                    output=f"(file is empty or line range out of bounds)",
                )

            header = f"File: {path} (lines {start_idx + 1}-{end_idx} of {total_lines})"
            output = header + "\n" + "-" * 60 + "\n" + "\n".join(output_lines)

            return ToolResult(success=True, output=output)

        except UnicodeDecodeError:
            return ToolResult(
                success=False,
                error="Cannot read file: not a text file or encoding error",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to read file: {str(e)}",
            )

    def edit_code(
        self,
        path: str,
        old_text: str,
        new_text: str,
    ) -> ToolResult:
        """Make a targeted edit to a code file.

        Args:
            path: Path to file
            old_text: Text to find (exact match)
            new_text: Replacement text

        Returns:
            ToolResult with edit status
        """
        try:
            file_path = Path(path).expanduser().resolve()

            if not file_path.exists():
                return ToolResult(
                    success=False,
                    error=f"File not found: {path}",
                )

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Check if old_text exists
            if old_text not in content:
                # Try to provide helpful error
                if old_text.strip() in content:
                    return ToolResult(
                        success=False,
                        error="Text not found. Note: whitespace must match exactly.",
                    )
                return ToolResult(
                    success=False,
                    error=f"Text not found in file: {path}",
                )

            # Count occurrences
            count = content.count(old_text)
            if count > 1:
                return ToolResult(
                    success=False,
                    error=f"Text appears {count} times. Please provide more context to make it unique.",
                )

            # Make the replacement
            new_content = content.replace(old_text, new_text)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            # Calculate diff info
            old_lines = old_text.count("\n") + 1
            new_lines = new_text.count("\n") + 1

            return ToolResult(
                success=True,
                output=f"Successfully edited {path}\nReplaced {old_lines} line(s) with {new_lines} line(s)",
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to edit file: {str(e)}",
            )

    def search_code(
        self,
        pattern: str,
        path: Optional[str] = None,
        file_pattern: Optional[str] = None,
        max_results: int = 50,
    ) -> ToolResult:
        """Search for pattern in code files.

        Args:
            pattern: Search pattern (regex)
            path: Directory to search
            file_pattern: Glob pattern for files
            max_results: Maximum results

        Returns:
            ToolResult with matches
        """
        try:
            search_path = Path(path or ".").expanduser().resolve()

            if not search_path.exists():
                return ToolResult(
                    success=False,
                    error=f"Path not found: {path}",
                )

            # Compile regex
            try:
                regex = re.compile(pattern, re.IGNORECASE)
            except re.error as e:
                return ToolResult(
                    success=False,
                    error=f"Invalid regex pattern: {e}",
                )

            # Determine files to search
            if search_path.is_file():
                files = [search_path]
            else:
                glob_pattern = file_pattern or "*"
                files = list(search_path.rglob(glob_pattern))
                files = [f for f in files if f.is_file()]

            matches = []
            files_searched = 0

            for file_path in files:
                # Skip binary files and hidden files
                if file_path.name.startswith("."):
                    continue

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()

                    files_searched += 1

                    for line_num, line in enumerate(lines, 1):
                        if regex.search(line):
                            rel_path = file_path.relative_to(search_path) if search_path.is_dir() else file_path.name
                            matches.append(
                                f"{rel_path}:{line_num}: {line.rstrip()[:100]}"
                            )

                            if len(matches) >= max_results:
                                break

                except (UnicodeDecodeError, PermissionError):
                    continue

                if len(matches) >= max_results:
                    break

            if not matches:
                return ToolResult(
                    success=True,
                    output=f"No matches found for '{pattern}' in {files_searched} files",
                )

            output = f"Found {len(matches)} match(es) in {files_searched} file(s):\n"
            output += "-" * 60 + "\n"
            output += "\n".join(matches)

            if len(matches) >= max_results:
                output += f"\n\n... (limited to {max_results} results)"

            return ToolResult(success=True, output=output)

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Search failed: {str(e)}",
            )

    def insert_code(
        self,
        path: str,
        line: int,
        text: str,
    ) -> ToolResult:
        """Insert text at a specific line.

        Args:
            path: Path to file
            line: Line number (1-indexed)
            text: Text to insert

        Returns:
            ToolResult with insert status
        """
        try:
            file_path = Path(path).expanduser().resolve()

            if not file_path.exists():
                return ToolResult(
                    success=False,
                    error=f"File not found: {path}",
                )

            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Validate line number
            if line < 1:
                return ToolResult(
                    success=False,
                    error="Line number must be >= 1",
                )

            # Insert at the specified line (0-indexed internally)
            insert_idx = min(line - 1, len(lines))

            # Ensure text ends with newline
            if text and not text.endswith("\n"):
                text = text + "\n"

            lines.insert(insert_idx, text)

            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(lines)

            inserted_lines = text.count("\n")
            return ToolResult(
                success=True,
                output=f"Inserted {inserted_lines} line(s) at line {line} in {path}",
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to insert: {str(e)}",
            )
