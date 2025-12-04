"""Tests for the history manager."""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from agentsh.shell.history import HistoryEntry, HistoryManager, ReadlineHistory


class TestHistoryEntry:
    """Test cases for HistoryEntry."""

    def test_create_entry(self) -> None:
        """Test creating a history entry."""
        entry = HistoryEntry(
            command="ls -la",
            timestamp=datetime.now(),
            is_ai_request=False,
            exit_code=0,
        )
        assert entry.command == "ls -la"
        assert entry.is_ai_request is False
        assert entry.exit_code == 0

    def test_create_ai_entry(self) -> None:
        """Test creating an AI request entry."""
        entry = HistoryEntry(
            command="find all python files",
            timestamp=datetime.now(),
            is_ai_request=True,
        )
        assert entry.command == "find all python files"
        assert entry.is_ai_request is True
        assert entry.exit_code is None

    def test_to_dict(self) -> None:
        """Test converting entry to dictionary."""
        ts = datetime(2024, 1, 15, 10, 30, 0)
        entry = HistoryEntry(
            command="git status",
            timestamp=ts,
            is_ai_request=False,
            exit_code=0,
        )
        d = entry.to_dict()
        assert d["command"] == "git status"
        assert d["timestamp"] == "2024-01-15T10:30:00"
        assert d["is_ai_request"] is False
        assert d["exit_code"] == 0

    def test_from_dict(self) -> None:
        """Test creating entry from dictionary."""
        d = {
            "command": "docker ps",
            "timestamp": "2024-01-15T10:30:00",
            "is_ai_request": False,
            "exit_code": 1,
        }
        entry = HistoryEntry.from_dict(d)
        assert entry.command == "docker ps"
        assert entry.timestamp == datetime(2024, 1, 15, 10, 30, 0)
        assert entry.is_ai_request is False
        assert entry.exit_code == 1

    def test_from_dict_missing_optional(self) -> None:
        """Test creating entry with missing optional fields."""
        d = {
            "command": "npm install",
            "timestamp": "2024-01-15T10:30:00",
        }
        entry = HistoryEntry.from_dict(d)
        assert entry.command == "npm install"
        assert entry.is_ai_request is False
        assert entry.exit_code is None


class TestHistoryManager:
    """Test cases for HistoryManager."""

    @pytest.fixture
    def temp_history_path(self) -> Path:
        """Create a temporary history file path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test_history.json"

    @pytest.fixture
    def manager(self, temp_history_path: Path) -> HistoryManager:
        """Create a history manager with temp path."""
        return HistoryManager(path=temp_history_path, max_entries=100)

    # Basic operations
    def test_add_command(self, manager: HistoryManager) -> None:
        """Test adding a command to history."""
        manager.add("ls -la")
        assert len(manager) == 1

    def test_add_ai_request(self, manager: HistoryManager) -> None:
        """Test adding an AI request to history."""
        manager.add("find all files", is_ai_request=True)
        assert len(manager) == 1
        assert manager.ai_requests[0].command == "find all files"

    def test_add_with_exit_code(self, manager: HistoryManager) -> None:
        """Test adding command with exit code."""
        manager.add("exit 42", exit_code=42)
        entries = manager.get_recent(1)
        assert entries[0].exit_code == 42

    def test_add_empty_command_ignored(self, manager: HistoryManager) -> None:
        """Test that empty commands are ignored."""
        manager.add("")
        manager.add("   ")
        assert len(manager) == 0

    # Deduplication
    def test_deduplication(self, manager: HistoryManager) -> None:
        """Test that consecutive duplicates are deduplicated."""
        manager.add("ls")
        manager.add("ls")
        manager.add("ls")
        assert len(manager) == 1

    def test_deduplication_updates_timestamp(self, manager: HistoryManager) -> None:
        """Test that deduplication updates the timestamp."""
        manager.add("ls")
        first_ts = manager.get_recent(1)[0].timestamp
        manager.add("ls")
        second_ts = manager.get_recent(1)[0].timestamp
        assert second_ts >= first_ts

    def test_different_commands_not_deduplicated(
        self, manager: HistoryManager
    ) -> None:
        """Test that different commands are not deduplicated."""
        manager.add("ls")
        manager.add("pwd")
        manager.add("ls")
        assert len(manager) == 3

    def test_deduplication_considers_type(self, manager: HistoryManager) -> None:
        """Test that shell and AI with same text are not deduplicated."""
        manager.add("find files", is_ai_request=False)
        manager.add("find files", is_ai_request=True)
        assert len(manager) == 2

    def test_no_deduplication_when_disabled(self, temp_history_path: Path) -> None:
        """Test that deduplication can be disabled."""
        manager = HistoryManager(path=temp_history_path, deduplicate=False)
        manager.add("ls")
        manager.add("ls")
        assert len(manager) == 2

    # Max entries
    def test_max_entries_enforced(self, temp_history_path: Path) -> None:
        """Test that max entries is enforced."""
        manager = HistoryManager(path=temp_history_path, max_entries=5)
        for i in range(10):
            manager.add(f"cmd{i}")
        assert len(manager) == 5
        # Should keep the most recent
        entries = manager.get_recent(5)
        assert entries[0].command == "cmd5"
        assert entries[-1].command == "cmd9"

    # Get recent
    def test_get_recent(self, manager: HistoryManager) -> None:
        """Test getting recent entries."""
        for i in range(10):
            manager.add(f"cmd{i}")
        entries = manager.get_recent(5)
        assert len(entries) == 5
        assert entries[-1].command == "cmd9"

    def test_get_recent_ai_only(self, manager: HistoryManager) -> None:
        """Test getting only AI entries."""
        manager.add("ls")
        manager.add("find files", is_ai_request=True)
        manager.add("pwd")
        manager.add("explain code", is_ai_request=True)

        entries = manager.get_recent(10, include_shell=False)
        assert len(entries) == 2
        assert all(e.is_ai_request for e in entries)

    def test_get_recent_shell_only(self, manager: HistoryManager) -> None:
        """Test getting only shell entries."""
        manager.add("ls")
        manager.add("find files", is_ai_request=True)
        manager.add("pwd")

        entries = manager.get_recent(10, include_ai=False)
        assert len(entries) == 2
        assert all(not e.is_ai_request for e in entries)

    # Search
    def test_search(self, manager: HistoryManager) -> None:
        """Test searching history."""
        manager.add("ls -la")
        manager.add("git status")
        manager.add("git commit")
        manager.add("docker ps")

        results = manager.search("git")
        assert len(results) == 2
        # Most recent first
        assert results[0].command == "git commit"
        assert results[1].command == "git status"

    def test_search_case_insensitive(self, manager: HistoryManager) -> None:
        """Test that search is case-insensitive."""
        manager.add("Docker Build")
        manager.add("docker ps")

        results = manager.search("docker")
        assert len(results) == 2

    def test_search_with_limit(self, manager: HistoryManager) -> None:
        """Test search with limit."""
        for i in range(10):
            manager.add(f"git cmd{i}")

        results = manager.search("git", limit=3)
        assert len(results) == 3

    def test_search_by_type(self, manager: HistoryManager) -> None:
        """Test searching by type."""
        manager.add("find files", is_ai_request=False)
        manager.add("find all python files", is_ai_request=True)

        # Search AI only
        results = manager.search("find", include_shell=False)
        assert len(results) == 1
        assert results[0].is_ai_request is True

    # Navigation
    def test_get_previous(self, manager: HistoryManager) -> None:
        """Test getting previous command."""
        manager.add("cmd1")
        manager.add("cmd2")
        manager.add("cmd3")

        assert manager.get_previous() == "cmd3"
        assert manager.get_previous() == "cmd2"
        assert manager.get_previous() == "cmd1"
        assert manager.get_previous() is None  # At beginning

    def test_get_next(self, manager: HistoryManager) -> None:
        """Test getting next command."""
        manager.add("cmd1")
        manager.add("cmd2")
        manager.add("cmd3")

        # Navigate to beginning
        manager.get_previous()
        manager.get_previous()
        manager.get_previous()

        assert manager.get_next() == "cmd2"
        assert manager.get_next() == "cmd3"
        assert manager.get_next() == ""  # At end, returns empty

    def test_reset_cursor(self, manager: HistoryManager) -> None:
        """Test resetting navigation cursor."""
        manager.add("cmd1")
        manager.add("cmd2")

        manager.get_previous()
        manager.get_previous()
        manager.reset_cursor()

        assert manager.get_previous() == "cmd2"

    # Clear
    def test_clear(self, manager: HistoryManager) -> None:
        """Test clearing all history."""
        manager.add("cmd1")
        manager.add("cmd2")
        manager.clear()
        assert len(manager) == 0

    def test_clear_ai_history(self, manager: HistoryManager) -> None:
        """Test clearing only AI history."""
        manager.add("ls")
        manager.add("find files", is_ai_request=True)
        manager.add("pwd")
        manager.add("explain code", is_ai_request=True)

        manager.clear_ai_history()
        assert len(manager) == 2
        assert all(not e.is_ai_request for e in manager)

    # Properties
    def test_shell_commands_property(self, manager: HistoryManager) -> None:
        """Test shell_commands property."""
        manager.add("ls")
        manager.add("find files", is_ai_request=True)
        manager.add("pwd")

        shell_cmds = manager.shell_commands
        assert len(shell_cmds) == 2
        assert shell_cmds[0].command == "ls"
        assert shell_cmds[1].command == "pwd"

    def test_ai_requests_property(self, manager: HistoryManager) -> None:
        """Test ai_requests property."""
        manager.add("ls")
        manager.add("find files", is_ai_request=True)
        manager.add("explain code", is_ai_request=True)

        ai_reqs = manager.ai_requests
        assert len(ai_reqs) == 2
        assert ai_reqs[0].command == "find files"

    # Iterator
    def test_iteration(self, manager: HistoryManager) -> None:
        """Test iterating over history."""
        manager.add("cmd1")
        manager.add("cmd2")
        manager.add("cmd3")

        commands = [e.command for e in manager]
        assert commands == ["cmd1", "cmd2", "cmd3"]

    # Persistence
    def test_save_and_load(self, temp_history_path: Path) -> None:
        """Test saving and loading history."""
        manager1 = HistoryManager(path=temp_history_path)
        manager1.add("cmd1")
        manager1.add("cmd2", is_ai_request=True)
        manager1.add("cmd3", exit_code=42)
        manager1.save()

        manager2 = HistoryManager(path=temp_history_path)
        manager2.load()

        assert len(manager2) == 3
        entries = manager2.get_recent(3)
        assert entries[0].command == "cmd1"
        assert entries[1].command == "cmd2"
        assert entries[1].is_ai_request is True
        assert entries[2].command == "cmd3"
        assert entries[2].exit_code == 42

    def test_load_nonexistent_file(self, temp_history_path: Path) -> None:
        """Test loading when file doesn't exist."""
        manager = HistoryManager(path=temp_history_path)
        result = manager.load()
        assert result is False
        assert len(manager) == 0

    def test_save_creates_directory(self, temp_history_path: Path) -> None:
        """Test that save creates parent directory."""
        nested_path = temp_history_path.parent / "nested" / "history.json"
        manager = HistoryManager(path=nested_path)
        manager.add("test")
        result = manager.save()
        assert result is True
        assert nested_path.exists()

    def test_load_invalid_json(self, temp_history_path: Path) -> None:
        """Test loading invalid JSON file."""
        temp_history_path.parent.mkdir(parents=True, exist_ok=True)
        temp_history_path.write_text("invalid json")

        manager = HistoryManager(path=temp_history_path)
        result = manager.load()
        assert result is False


class TestReadlineHistory:
    """Test cases for ReadlineHistory adapter."""

    @pytest.fixture
    def temp_history_path(self) -> Path:
        """Create a temporary history file path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test_history.json"

    def test_setup_with_readline(self, temp_history_path: Path) -> None:
        """Test setting up readline integration."""
        manager = HistoryManager(path=temp_history_path)
        manager.add("cmd1")
        manager.add("cmd2")

        adapter = ReadlineHistory(manager)
        result = adapter.setup()
        # Result depends on readline availability
        assert isinstance(result, bool)

    def test_save_readline_history(self, temp_history_path: Path) -> None:
        """Test saving readline history."""
        manager = HistoryManager(path=temp_history_path)
        adapter = ReadlineHistory(manager)
        adapter.setup()

        result = adapter.save()
        # Result depends on readline availability
        assert isinstance(result, bool)
