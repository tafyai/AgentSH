"""Tab completion for AgentSH shell.

Provides intelligent tab completion for:
- Special commands (:help, :config, etc.)
- Tool names (shell.run, fs.read, etc.)
- File paths
- Command history
"""

import os
import readline
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional


class CompletionType(str, Enum):
    """Types of completions."""

    SPECIAL_COMMAND = "special_command"
    TOOL = "tool"
    FILE_PATH = "file_path"
    HISTORY = "history"
    NONE = "none"


@dataclass
class CompletionResult:
    """Result of a completion attempt."""

    matches: list[str] = field(default_factory=list)
    completion_type: CompletionType = CompletionType.NONE
    prefix: str = ""


class ShellCompleter:
    """Tab completion handler for AgentSH.

    Provides context-aware completions based on:
    - Current input prefix
    - Available tools
    - Special commands
    - File system paths

    Example:
        completer = ShellCompleter()
        completer.register_tool("shell.run", "Execute shell commands")
        completer.register_tool("fs.read", "Read file contents")

        # Install completer
        completer.install()

        # Now tab completion works in readline
    """

    def __init__(self) -> None:
        """Initialize the completer."""
        self._tools: dict[str, str] = {}  # name -> description
        self._special_commands: dict[str, str] = {}  # command -> description
        self._history: list[str] = []
        self._matches: list[str] = []
        self._installed = False

    def register_tool(self, name: str, description: str = "") -> None:
        """Register a tool for completion.

        Args:
            name: Tool name (e.g., 'shell.run')
            description: Tool description for display
        """
        self._tools[name] = description

    def register_tools(self, tools: dict[str, str]) -> None:
        """Register multiple tools.

        Args:
            tools: Dict of tool name -> description
        """
        self._tools.update(tools)

    def register_special_command(self, command: str, description: str = "") -> None:
        """Register a special command for completion.

        Args:
            command: Command name without colon (e.g., 'help')
            description: Command description
        """
        self._special_commands[command] = description

    def register_special_commands(self, commands: dict[str, str]) -> None:
        """Register multiple special commands.

        Args:
            commands: Dict of command name -> description
        """
        self._special_commands.update(commands)

    def add_to_history(self, entry: str) -> None:
        """Add an entry to completion history.

        Args:
            entry: Command/request to add
        """
        if entry and entry not in self._history:
            self._history.append(entry)
            # Keep history bounded
            if len(self._history) > 1000:
                self._history = self._history[-1000:]

    def complete(self, text: str, state: int) -> Optional[str]:
        """Readline completion function.

        Args:
            text: Current word being completed
            state: Completion state (0 for first match, 1 for second, etc.)

        Returns:
            Next matching completion or None
        """
        if state == 0:
            # First call - compute matches
            line = readline.get_line_buffer()
            self._matches = self._get_completions(text, line)

        if state < len(self._matches):
            return self._matches[state]
        return None

    def _get_completions(self, text: str, line: str) -> list[str]:
        """Get completions for current input.

        Args:
            text: Word being completed
            line: Full input line

        Returns:
            List of possible completions
        """
        # Determine completion type based on context
        stripped_line = line.lstrip()

        # Special commands (starting with :)
        if stripped_line.startswith(":"):
            return self._complete_special_command(text, stripped_line)

        # File paths (contains / or starts with . or ~)
        if "/" in text or text.startswith(".") or text.startswith("~"):
            return self._complete_path(text)

        # Tool names (for AI requests)
        if text and not stripped_line.startswith("!"):
            tool_matches = self._complete_tool(text)
            if tool_matches:
                return tool_matches

        # Default: no completions
        return []

    def _complete_special_command(self, text: str, line: str) -> list[str]:
        """Complete special commands.

        Args:
            text: Current word
            line: Full line starting with :

        Returns:
            Matching special commands
        """
        # Remove leading colon for matching
        cmd_text = line[1:] if line.startswith(":") else line

        # If we're completing the command name itself
        if " " not in cmd_text:
            prefix = cmd_text.lower()
            matches = []
            for cmd in self._special_commands:
                if cmd.startswith(prefix):
                    # Return with colon prefix
                    matches.append(f":{cmd}")
            return sorted(matches)

        # After command name, could do argument completion
        # For now, return empty
        return []

    def _complete_tool(self, text: str) -> list[str]:
        """Complete tool names.

        Args:
            text: Current word

        Returns:
            Matching tool names
        """
        prefix = text.lower()
        matches = []
        for tool in self._tools:
            if tool.lower().startswith(prefix):
                matches.append(tool)
        return sorted(matches)

    def _complete_path(self, text: str) -> list[str]:
        """Complete file system paths.

        Args:
            text: Path prefix

        Returns:
            Matching paths
        """
        # Expand ~ to home directory
        if text.startswith("~"):
            expanded = os.path.expanduser(text)
            prefix_len = len(text) - len(expanded.replace(os.path.expanduser("~"), "~"))
        else:
            expanded = text
            prefix_len = 0

        # Get directory and file prefix
        if os.path.isdir(expanded):
            directory = expanded
            file_prefix = ""
        else:
            directory = os.path.dirname(expanded) or "."
            file_prefix = os.path.basename(expanded)

        matches = []
        try:
            for entry in os.listdir(directory):
                if entry.startswith(file_prefix):
                    full_path = os.path.join(directory, entry)
                    # Add trailing slash for directories
                    if os.path.isdir(full_path):
                        entry += "/"
                    # Reconstruct with original prefix style
                    if text.startswith("~"):
                        result = text[:prefix_len] + os.path.join(
                            directory.replace(os.path.expanduser("~"), ""),
                            entry
                        ).lstrip("/")
                    else:
                        result = os.path.join(directory, entry)
                    matches.append(result)
        except (OSError, PermissionError):
            pass

        return sorted(matches)

    def install(self) -> None:
        """Install this completer into readline."""
        if self._installed:
            return

        # Set up readline
        readline.set_completer(self.complete)
        readline.set_completer_delims(" \t\n;")

        # Use tab for completion
        readline.parse_and_bind("tab: complete")

        # For better path completion
        readline.set_completer_delims(
            readline.get_completer_delims().replace("/", "")
        )

        self._installed = True

    def uninstall(self) -> None:
        """Uninstall this completer from readline."""
        if not self._installed:
            return

        readline.set_completer(None)
        self._installed = False


# Global completer instance
_completer: Optional[ShellCompleter] = None


def get_completer() -> ShellCompleter:
    """Get or create the global shell completer.

    Returns:
        Global ShellCompleter instance
    """
    global _completer
    if _completer is None:
        _completer = ShellCompleter()
    return _completer


def setup_completion(
    tools: Optional[dict[str, str]] = None,
    special_commands: Optional[dict[str, str]] = None,
) -> ShellCompleter:
    """Set up tab completion with given tools and commands.

    Args:
        tools: Dict of tool name -> description
        special_commands: Dict of command name -> description

    Returns:
        Configured ShellCompleter
    """
    completer = get_completer()

    if tools:
        completer.register_tools(tools)

    if special_commands:
        completer.register_special_commands(special_commands)

    completer.install()
    return completer
