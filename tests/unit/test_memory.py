"""Tests for shell memory module."""

import time
from pathlib import Path

import pytest

from agentsh.shell.memory import (
    MemoryEntry,
    MemoryStore,
    format_memory_list,
    get_memory_store,
    remember,
    recall,
    forget,
)


class TestMemoryEntry:
    """Tests for MemoryEntry dataclass."""

    def test_create_entry(self) -> None:
        """Should create memory entry."""
        entry = MemoryEntry(
            id=1,
            content="Test note",
            created_at=time.time(),
        )

        assert entry.id == 1
        assert entry.content == "Test note"
        assert entry.tags == []
        assert entry.metadata == {}

    def test_entry_with_tags(self) -> None:
        """Should accept tags."""
        entry = MemoryEntry(
            id=1,
            content="Tagged note",
            created_at=time.time(),
            tags=["work", "important"],
        )

        assert "work" in entry.tags
        assert "important" in entry.tags

    def test_created_datetime(self) -> None:
        """Should convert timestamp to datetime."""
        now = time.time()
        entry = MemoryEntry(id=1, content="Test", created_at=now)

        dt = entry.created_datetime
        assert dt.timestamp() == pytest.approx(now, abs=1)

    def test_age_str_just_now(self) -> None:
        """Should show 'just now' for recent entries."""
        entry = MemoryEntry(id=1, content="Test", created_at=time.time())
        assert entry.age_str == "just now"

    def test_age_str_minutes(self) -> None:
        """Should show minutes for older entries."""
        entry = MemoryEntry(
            id=1,
            content="Test",
            created_at=time.time() - 300,  # 5 minutes ago
        )
        assert "minutes ago" in entry.age_str

    def test_age_str_hours(self) -> None:
        """Should show hours for even older entries."""
        entry = MemoryEntry(
            id=1,
            content="Test",
            created_at=time.time() - 7200,  # 2 hours ago
        )
        assert "hours ago" in entry.age_str

    def test_age_str_days(self) -> None:
        """Should show days for old entries."""
        entry = MemoryEntry(
            id=1,
            content="Test",
            created_at=time.time() - 172800,  # 2 days ago
        )
        assert "days ago" in entry.age_str

    def test_to_dict(self) -> None:
        """Should convert to dict."""
        entry = MemoryEntry(
            id=1,
            content="Test",
            created_at=1234567890.0,
            tags=["tag1"],
            metadata={"key": "value"},
        )

        d = entry.to_dict()

        assert d["id"] == 1
        assert d["content"] == "Test"
        assert d["created_at"] == 1234567890.0
        assert d["tags"] == ["tag1"]
        assert d["metadata"] == {"key": "value"}


class TestMemoryStore:
    """Tests for MemoryStore class."""

    @pytest.fixture
    def store(self, tmp_path: Path) -> MemoryStore:
        """Create memory store in temp directory."""
        db_path = tmp_path / "test_memory.db"
        store = MemoryStore(db_path)
        yield store
        store.close()

    def test_remember(self, store: MemoryStore) -> None:
        """Should store memory."""
        entry_id = store.remember("Test note")

        assert entry_id > 0

    def test_remember_with_tags(self, store: MemoryStore) -> None:
        """Should store memory with tags."""
        entry_id = store.remember("Tagged note", tags=["work", "important"])

        entry = store.get(entry_id)
        assert entry is not None
        assert "work" in entry.tags

    def test_remember_with_metadata(self, store: MemoryStore) -> None:
        """Should store memory with metadata."""
        entry_id = store.remember(
            "Note with metadata",
            metadata={"source": "test"},
        )

        entry = store.get(entry_id)
        assert entry is not None
        assert entry.metadata["source"] == "test"

    def test_recall_all(self, store: MemoryStore) -> None:
        """Should recall all memories without query."""
        store.remember("Note 1")
        store.remember("Note 2")
        store.remember("Note 3")

        results = store.recall()

        assert len(results) == 3

    def test_recall_with_query(self, store: MemoryStore) -> None:
        """Should search memories with query."""
        store.remember("Deploy to production")
        store.remember("Fix bug in login")
        store.remember("Update documentation")

        results = store.recall("production")

        assert len(results) == 1
        assert "production" in results[0].content

    def test_recall_with_limit(self, store: MemoryStore) -> None:
        """Should respect limit."""
        for i in range(10):
            store.remember(f"Note {i}")

        results = store.recall(limit=5)

        assert len(results) == 5

    def test_recall_recent_first(self, store: MemoryStore) -> None:
        """Should return recent memories first."""
        store.remember("Old note")
        time.sleep(0.01)
        store.remember("New note")

        results = store.recall()

        assert results[0].content == "New note"

    def test_forget(self, store: MemoryStore) -> None:
        """Should delete memory."""
        entry_id = store.remember("To be deleted")
        assert store.get(entry_id) is not None

        result = store.forget(entry_id)

        assert result is True
        assert store.get(entry_id) is None

    def test_forget_nonexistent(self, store: MemoryStore) -> None:
        """Should return False for nonexistent ID."""
        result = store.forget(99999)
        assert result is False

    def test_forget_all(self, store: MemoryStore) -> None:
        """Should delete all memories."""
        store.remember("Note 1")
        store.remember("Note 2")
        store.remember("Note 3")

        count = store.forget_all()

        assert count == 3
        assert store.count() == 0

    def test_get(self, store: MemoryStore) -> None:
        """Should get specific memory."""
        entry_id = store.remember("Specific note")

        entry = store.get(entry_id)

        assert entry is not None
        assert entry.id == entry_id
        assert entry.content == "Specific note"

    def test_get_nonexistent(self, store: MemoryStore) -> None:
        """Should return None for nonexistent ID."""
        assert store.get(99999) is None

    def test_count(self, store: MemoryStore) -> None:
        """Should count memories."""
        assert store.count() == 0

        store.remember("Note 1")
        store.remember("Note 2")

        assert store.count() == 2

    def test_persistence(self, tmp_path: Path) -> None:
        """Should persist across instances."""
        db_path = tmp_path / "persist_test.db"

        # Create and store
        store1 = MemoryStore(db_path)
        entry_id = store1.remember("Persistent note")
        store1.close()

        # Reopen and verify
        store2 = MemoryStore(db_path)
        entry = store2.get(entry_id)
        store2.close()

        assert entry is not None
        assert entry.content == "Persistent note"


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_remember_function(self, tmp_path: Path, monkeypatch) -> None:
        """Should store via convenience function."""
        # Use temp path for test
        import agentsh.shell.memory as memory_module

        db_path = tmp_path / "test.db"
        test_store = MemoryStore(db_path)
        monkeypatch.setattr(memory_module, "_memory_store", test_store)

        entry_id = remember("Test via function")

        assert entry_id > 0
        test_store.close()

    def test_recall_function(self, tmp_path: Path, monkeypatch) -> None:
        """Should recall via convenience function."""
        import agentsh.shell.memory as memory_module

        db_path = tmp_path / "test.db"
        test_store = MemoryStore(db_path)
        monkeypatch.setattr(memory_module, "_memory_store", test_store)

        remember("Test note")
        results = recall()

        assert len(results) == 1
        test_store.close()

    def test_forget_function(self, tmp_path: Path, monkeypatch) -> None:
        """Should forget via convenience function."""
        import agentsh.shell.memory as memory_module

        db_path = tmp_path / "test.db"
        test_store = MemoryStore(db_path)
        monkeypatch.setattr(memory_module, "_memory_store", test_store)

        entry_id = remember("To forget")
        result = forget(entry_id)

        assert result is True
        test_store.close()


class TestFormatMemoryList:
    """Tests for format_memory_list function."""

    def test_empty_list(self) -> None:
        """Should handle empty list."""
        result = format_memory_list([])
        assert result == "No memories found."

    def test_format_entries(self) -> None:
        """Should format entries."""
        entries = [
            MemoryEntry(id=1, content="First note", created_at=time.time()),
            MemoryEntry(id=2, content="Second note", created_at=time.time()),
        ]

        result = format_memory_list(entries, use_color=False)

        assert "[1]" in result
        assert "[2]" in result
        assert "First note" in result
        assert "Second note" in result

    def test_truncate_long_content(self) -> None:
        """Should truncate long content."""
        entries = [
            MemoryEntry(
                id=1,
                content="A" * 100,  # Very long content
                created_at=time.time(),
            ),
        ]

        result = format_memory_list(entries, use_color=False)

        assert "..." in result
        assert len(result.split("\n")[0]) < 100

    def test_includes_age(self) -> None:
        """Should include age."""
        entries = [
            MemoryEntry(id=1, content="Note", created_at=time.time()),
        ]

        result = format_memory_list(entries, use_color=False)

        assert "just now" in result
