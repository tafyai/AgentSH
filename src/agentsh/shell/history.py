"""Command History - Manages command history with persistence."""

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)


@dataclass
class HistoryEntry:
    """A single history entry."""

    command: str
    timestamp: datetime
    is_ai_request: bool = False
    exit_code: Optional[int] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "command": self.command,
            "timestamp": self.timestamp.isoformat(),
            "is_ai_request": self.is_ai_request,
            "exit_code": self.exit_code,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HistoryEntry":
        """Create from dictionary."""
        return cls(
            command=data["command"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            is_ai_request=data.get("is_ai_request", False),
            exit_code=data.get("exit_code"),
        )


class HistoryManager:
    """Manages command history with persistence.

    Features:
    - Separate tracking for shell and AI commands
    - Persistence to JSON file
    - Deduplication of consecutive identical commands
    - Search functionality
    - Configurable maximum size

    Example:
        history = HistoryManager(path=Path("~/.agentsh/history.json"))
        history.load()

        history.add("ls -la")
        history.add("find all python files", is_ai_request=True)

        for entry in history.search("python"):
            print(entry.command)

        history.save()
    """

    def __init__(
        self,
        path: Optional[Path] = None,
        max_entries: int = 10000,
        deduplicate: bool = True,
    ) -> None:
        """Initialize history manager.

        Args:
            path: Path to history file. Uses default if None.
            max_entries: Maximum number of entries to keep
            deduplicate: Remove consecutive duplicate commands
        """
        self.path = path or self._default_path()
        self.max_entries = max_entries
        self.deduplicate = deduplicate

        self._entries: list[HistoryEntry] = []
        self._cursor: int = 0  # For up/down navigation

    def _default_path(self) -> Path:
        """Get default history file path."""
        return Path.home() / ".agentsh" / "history.json"

    def load(self) -> bool:
        """Load history from file.

        Returns:
            True if loaded successfully, False otherwise
        """
        if not self.path.exists():
            logger.debug("No history file found", path=str(self.path))
            return False

        try:
            with open(self.path) as f:
                data = json.load(f)

            self._entries = [HistoryEntry.from_dict(e) for e in data.get("entries", [])]
            self._cursor = len(self._entries)

            logger.info("Loaded history", count=len(self._entries))
            return True

        except Exception as e:
            logger.warning("Failed to load history", error=str(e))
            return False

    def save(self) -> bool:
        """Save history to file.

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Ensure directory exists
            self.path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "version": 1,
                "entries": [e.to_dict() for e in self._entries],
            }

            # Write atomically using temp file
            temp_path = self.path.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                json.dump(data, f, indent=2)

            temp_path.rename(self.path)

            logger.debug("Saved history", count=len(self._entries))
            return True

        except Exception as e:
            logger.warning("Failed to save history", error=str(e))
            return False

    def add(
        self,
        command: str,
        is_ai_request: bool = False,
        exit_code: Optional[int] = None,
    ) -> None:
        """Add a command to history.

        Args:
            command: Command string
            is_ai_request: Whether this was an AI request
            exit_code: Exit code of the command
        """
        command = command.strip()
        if not command:
            return

        # Deduplicate consecutive identical commands
        if self.deduplicate and self._entries:
            last = self._entries[-1]
            if last.command == command and last.is_ai_request == is_ai_request:
                # Update timestamp and exit code of existing entry
                self._entries[-1] = HistoryEntry(
                    command=command,
                    timestamp=datetime.now(),
                    is_ai_request=is_ai_request,
                    exit_code=exit_code,
                )
                self._cursor = len(self._entries)
                return

        entry = HistoryEntry(
            command=command,
            timestamp=datetime.now(),
            is_ai_request=is_ai_request,
            exit_code=exit_code,
        )

        self._entries.append(entry)

        # Trim if exceeds max size
        if len(self._entries) > self.max_entries:
            self._entries = self._entries[-self.max_entries :]

        self._cursor = len(self._entries)

    def get_recent(
        self,
        n: int = 20,
        include_ai: bool = True,
        include_shell: bool = True,
    ) -> list[HistoryEntry]:
        """Get recent history entries.

        Args:
            n: Number of entries to return
            include_ai: Include AI requests
            include_shell: Include shell commands

        Returns:
            List of recent entries
        """
        filtered = [
            e
            for e in self._entries
            if (include_ai and e.is_ai_request) or (include_shell and not e.is_ai_request)
        ]
        return filtered[-n:]

    def search(
        self,
        query: str,
        limit: int = 50,
        include_ai: bool = True,
        include_shell: bool = True,
    ) -> list[HistoryEntry]:
        """Search history for matching commands.

        Args:
            query: Search query (case-insensitive substring match)
            limit: Maximum results to return
            include_ai: Include AI requests
            include_shell: Include shell commands

        Returns:
            List of matching entries (most recent first)
        """
        query_lower = query.lower()
        matches = []

        for entry in reversed(self._entries):
            if query_lower in entry.command.lower():
                if (include_ai and entry.is_ai_request) or (
                    include_shell and not entry.is_ai_request
                ):
                    matches.append(entry)
                    if len(matches) >= limit:
                        break

        return matches

    def get_previous(self) -> Optional[str]:
        """Get previous command (for up arrow navigation).

        Returns:
            Previous command or None if at beginning
        """
        if self._cursor > 0:
            self._cursor -= 1
            return self._entries[self._cursor].command
        return None

    def get_next(self) -> Optional[str]:
        """Get next command (for down arrow navigation).

        Returns:
            Next command or None if at end
        """
        if self._cursor < len(self._entries) - 1:
            self._cursor += 1
            return self._entries[self._cursor].command
        elif self._cursor == len(self._entries) - 1:
            self._cursor = len(self._entries)
            return ""  # Return empty for new command
        return None

    def reset_cursor(self) -> None:
        """Reset navigation cursor to end of history."""
        self._cursor = len(self._entries)

    def clear(self) -> None:
        """Clear all history."""
        self._entries.clear()
        self._cursor = 0
        logger.info("History cleared")

    def clear_ai_history(self) -> None:
        """Clear only AI request history."""
        self._entries = [e for e in self._entries if not e.is_ai_request]
        self._cursor = len(self._entries)
        logger.info("AI history cleared")

    def __len__(self) -> int:
        """Get number of history entries."""
        return len(self._entries)

    def __iter__(self) -> Iterator[HistoryEntry]:
        """Iterate over history entries."""
        return iter(self._entries)

    @property
    def shell_commands(self) -> list[HistoryEntry]:
        """Get only shell commands."""
        return [e for e in self._entries if not e.is_ai_request]

    @property
    def ai_requests(self) -> list[HistoryEntry]:
        """Get only AI requests."""
        return [e for e in self._entries if e.is_ai_request]


class ReadlineHistory:
    """Adapter to integrate with Python's readline module.

    This allows using standard readline keybindings for history navigation.
    """

    def __init__(self, manager: HistoryManager) -> None:
        """Initialize readline history adapter.

        Args:
            manager: History manager to wrap
        """
        self.manager = manager

    def setup(self) -> bool:
        """Set up readline with history.

        Returns:
            True if readline is available and configured
        """
        try:
            import readline

            # Load history into readline
            for entry in self.manager.shell_commands:
                readline.add_history(entry.command)

            # Set history file (readline uses its own format)
            readline_path = self.manager.path.with_suffix(".readline")
            if readline_path.exists():
                readline.read_history_file(str(readline_path))

            return True

        except ImportError:
            logger.debug("readline not available")
            return False

    def save(self) -> bool:
        """Save readline history.

        Returns:
            True if saved successfully
        """
        try:
            import readline

            readline_path = self.manager.path.with_suffix(".readline")
            readline_path.parent.mkdir(parents=True, exist_ok=True)
            readline.write_history_file(str(readline_path))
            return True

        except ImportError:
            return False
