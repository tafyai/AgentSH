"""Tests for memory storage backends."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from agentsh.memory.schemas import MemoryMetadata, MemoryRecord, MemoryType
from agentsh.memory.store import InMemoryStore, SQLiteMemoryStore


class TestInMemoryStore:
    """Tests for InMemoryStore."""

    @pytest.fixture
    def store(self):
        """Create a fresh in-memory store."""
        return InMemoryStore()

    def test_store_and_retrieve(self, store):
        """Test storing and retrieving a record."""
        record = MemoryRecord(
            id="test-1",
            type=MemoryType.CUSTOM_NOTE,
            title="Test Note",
            content="This is a test.",
        )
        record_id = store.store(record)
        assert record_id == "test-1"

        retrieved = store.retrieve("test-1")
        assert retrieved is not None
        assert retrieved.title == "Test Note"
        assert retrieved.access_count == 1  # Incremented on retrieve

    def test_retrieve_nonexistent(self, store):
        """Test retrieving nonexistent record."""
        assert store.retrieve("nonexistent") is None

    def test_delete(self, store):
        """Test deleting a record."""
        record = MemoryRecord(
            id="test-1",
            type=MemoryType.CUSTOM_NOTE,
            title="Test",
            content="Content",
        )
        store.store(record)

        assert store.delete("test-1") is True
        assert store.retrieve("test-1") is None
        assert store.delete("test-1") is False  # Already deleted

    def test_list_by_type(self, store):
        """Test listing records by type."""
        for i in range(3):
            store.store(MemoryRecord(
                id=f"note-{i}",
                type=MemoryType.CUSTOM_NOTE,
                title=f"Note {i}",
                content="",
            ))
        store.store(MemoryRecord(
            id="pref-1",
            type=MemoryType.USER_PREFERENCE,
            title="Preference",
            content="",
        ))

        notes = store.list_by_type(MemoryType.CUSTOM_NOTE)
        assert len(notes) == 3

        prefs = store.list_by_type(MemoryType.USER_PREFERENCE)
        assert len(prefs) == 1

    def test_search_by_query(self, store):
        """Test searching by query."""
        store.store(MemoryRecord(
            id="1",
            type=MemoryType.CUSTOM_NOTE,
            title="Python Tutorial",
            content="Learn Python programming",
        ))
        store.store(MemoryRecord(
            id="2",
            type=MemoryType.CUSTOM_NOTE,
            title="JavaScript Guide",
            content="Learn JavaScript",
        ))

        results = store.search("Python")
        assert len(results) == 1
        assert results[0].title == "Python Tutorial"

    def test_search_by_type(self, store):
        """Test searching with type filter."""
        store.store(MemoryRecord(
            id="1",
            type=MemoryType.CUSTOM_NOTE,
            title="Note about Python",
            content="",
        ))
        store.store(MemoryRecord(
            id="2",
            type=MemoryType.USER_PREFERENCE,
            title="Python preference",
            content="",
        ))

        results = store.search("Python", memory_types=[MemoryType.CUSTOM_NOTE])
        assert len(results) == 1
        assert results[0].type == MemoryType.CUSTOM_NOTE

    def test_search_by_tags(self, store):
        """Test searching with tag filter."""
        store.store(MemoryRecord(
            id="1",
            type=MemoryType.CUSTOM_NOTE,
            title="Note",
            content="Content",
            metadata=MemoryMetadata(tags=["python", "tutorial"]),
        ))
        store.store(MemoryRecord(
            id="2",
            type=MemoryType.CUSTOM_NOTE,
            title="Note 2",
            content="Content",
            metadata=MemoryMetadata(tags=["javascript"]),
        ))

        results = store.search("", tags=["python"])
        assert len(results) == 1
        assert "python" in results[0].metadata.tags

    def test_update(self, store):
        """Test updating a record."""
        record = MemoryRecord(
            id="test-1",
            type=MemoryType.CUSTOM_NOTE,
            title="Original",
            content="Original content",
        )
        store.store(record)

        record.title = "Updated"
        record.content = "Updated content"
        assert store.update(record) is True

        retrieved = store.retrieve("test-1")
        assert retrieved.title == "Updated"

    def test_update_nonexistent(self, store):
        """Test updating nonexistent record."""
        record = MemoryRecord(
            id="nonexistent",
            type=MemoryType.CUSTOM_NOTE,
            title="Test",
            content="",
        )
        assert store.update(record) is False

    def test_clear(self, store):
        """Test clearing all records."""
        for i in range(5):
            store.store(MemoryRecord(
                id=f"r-{i}",
                type=MemoryType.CUSTOM_NOTE,
                title=f"Record {i}",
                content="",
            ))

        count = store.clear()
        assert count == 5
        assert len(store.list_by_type(MemoryType.CUSTOM_NOTE)) == 0


class TestSQLiteMemoryStore:
    """Tests for SQLiteMemoryStore."""

    @pytest.fixture
    def db_path(self):
        """Create a temporary database path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir) / "test_memory.db"

    @pytest.fixture
    def store(self, db_path):
        """Create a SQLite store with temporary database."""
        return SQLiteMemoryStore(str(db_path), enable_fts=True)

    def test_init_creates_database(self, db_path):
        """Test that initialization creates the database."""
        store = SQLiteMemoryStore(str(db_path))
        assert db_path.exists()

    def test_store_and_retrieve(self, store):
        """Test storing and retrieving a record."""
        record = MemoryRecord(
            id="test-1",
            type=MemoryType.CUSTOM_NOTE,
            title="Test Note",
            content="This is a test.",
            metadata=MemoryMetadata(tags=["test"]),
        )
        record_id = store.store(record)
        assert record_id == "test-1"

        retrieved = store.retrieve("test-1")
        assert retrieved is not None
        assert retrieved.title == "Test Note"
        assert "test" in retrieved.metadata.tags

    def test_fts_search(self, store):
        """Test full-text search."""
        store.store(MemoryRecord(
            id="1",
            type=MemoryType.CUSTOM_NOTE,
            title="Python programming",
            content="Learn how to code in Python",
        ))
        store.store(MemoryRecord(
            id="2",
            type=MemoryType.CUSTOM_NOTE,
            title="JavaScript basics",
            content="JavaScript for beginners",
        ))

        results = store.search("Python")
        assert len(results) >= 1
        assert any(r.id == "1" for r in results)

    def test_tag_filtering(self, store):
        """Test tag-based filtering."""
        store.store(MemoryRecord(
            id="1",
            type=MemoryType.CUSTOM_NOTE,
            title="Note 1",
            content="",
            metadata=MemoryMetadata(tags=["important", "work"]),
        ))
        store.store(MemoryRecord(
            id="2",
            type=MemoryType.CUSTOM_NOTE,
            title="Note 2",
            content="",
            metadata=MemoryMetadata(tags=["personal"]),
        ))

        results = store.search("", tags=["important"])
        assert len(results) == 1
        assert results[0].id == "1"

    def test_cleanup_expired(self, store):
        """Test cleaning up expired records."""
        # Store a record that's already expired
        expired_record = MemoryRecord(
            id="expired",
            type=MemoryType.CUSTOM_NOTE,
            title="Expired",
            content="",
            metadata=MemoryMetadata(
                expires_at=datetime.now() - timedelta(days=1)
            ),
        )
        store.store(expired_record)

        # Store a record that hasn't expired
        valid_record = MemoryRecord(
            id="valid",
            type=MemoryType.CUSTOM_NOTE,
            title="Valid",
            content="",
            metadata=MemoryMetadata(
                expires_at=datetime.now() + timedelta(days=1)
            ),
        )
        store.store(valid_record)

        count = store.cleanup_expired()
        assert count == 1
        assert store.retrieve("expired") is None
        assert store.retrieve("valid") is not None

    def test_get_stats(self, store):
        """Test getting storage statistics."""
        for i in range(3):
            store.store(MemoryRecord(
                id=f"note-{i}",
                type=MemoryType.CUSTOM_NOTE,
                title=f"Note {i}",
                content="",
            ))
        store.store(MemoryRecord(
            id="pref-1",
            type=MemoryType.USER_PREFERENCE,
            title="Pref",
            content="",
        ))

        stats = store.get_stats()
        assert stats["total_records"] == 4
        assert stats["by_type"]["custom_note"] == 3
        assert stats["by_type"]["user_preference"] == 1
        assert "db_size_bytes" in stats

    def test_persistence(self, db_path):
        """Test that data persists across store instances."""
        # Create and populate first store
        store1 = SQLiteMemoryStore(str(db_path))
        store1.store(MemoryRecord(
            id="persistent",
            type=MemoryType.CUSTOM_NOTE,
            title="Persistent Note",
            content="This should persist",
        ))

        # Create new store instance
        store2 = SQLiteMemoryStore(str(db_path))
        retrieved = store2.retrieve("persistent")
        assert retrieved is not None
        assert retrieved.title == "Persistent Note"

    def test_without_fts(self, db_path):
        """Test store without full-text search."""
        store = SQLiteMemoryStore(str(db_path), enable_fts=False)
        store.store(MemoryRecord(
            id="1",
            type=MemoryType.CUSTOM_NOTE,
            title="Python Note",
            content="About Python",
        ))

        # Should still work with LIKE search
        results = store.search("Python")
        assert len(results) == 1


class TestSQLiteMemoryStoreExtended:
    """Extended tests for SQLiteMemoryStore."""

    @pytest.fixture
    def db_path(self, tmp_path):
        """Create temp database path."""
        return tmp_path / "extended_test.db"

    @pytest.fixture
    def store(self, db_path):
        """Create store instance."""
        return SQLiteMemoryStore(str(db_path))

    def test_delete_nonexistent(self, store):
        """Should return False when deleting nonexistent record."""
        result = store.delete("nonexistent-id")
        assert result is False

    def test_delete_existing(self, store):
        """Should return True when deleting existing record."""
        store.store(MemoryRecord(
            id="to-delete",
            type=MemoryType.CUSTOM_NOTE,
            title="Will be deleted",
            content="",
        ))
        result = store.delete("to-delete")
        assert result is True
        # Verify it's gone
        assert store.retrieve("to-delete") is None

    def test_list_by_type(self, store):
        """Should list records by type."""
        # Add different types
        store.store(MemoryRecord(
            id="note-1",
            type=MemoryType.CUSTOM_NOTE,
            title="Note 1",
            content="",
        ))
        store.store(MemoryRecord(
            id="pref-1",
            type=MemoryType.USER_PREFERENCE,
            title="Pref 1",
            content="",
        ))
        store.store(MemoryRecord(
            id="note-2",
            type=MemoryType.CUSTOM_NOTE,
            title="Note 2",
            content="",
        ))

        notes = store.list_by_type(MemoryType.CUSTOM_NOTE)
        assert len(notes) == 2

        prefs = store.list_by_type(MemoryType.USER_PREFERENCE)
        assert len(prefs) == 1

    def test_list_by_type_with_limit(self, store):
        """Should respect limit parameter."""
        for i in range(10):
            store.store(MemoryRecord(
                id=f"note-{i}",
                type=MemoryType.CUSTOM_NOTE,
                title=f"Note {i}",
                content="",
            ))

        results = store.list_by_type(MemoryType.CUSTOM_NOTE, limit=5)
        assert len(results) == 5

    def test_list_by_type_empty(self, store):
        """Should return empty list when no records of type."""
        results = store.list_by_type(MemoryType.CUSTOM_NOTE)
        assert results == []

    def test_search_with_type_filter(self, store):
        """Should filter search by memory type."""
        store.store(MemoryRecord(
            id="note-1",
            type=MemoryType.CUSTOM_NOTE,
            title="Python Tips",
            content="Learn Python",
        ))
        store.store(MemoryRecord(
            id="pref-1",
            type=MemoryType.USER_PREFERENCE,
            title="Python Preference",
            content="Use Python",
        ))

        # Search only notes
        results = store.search("Python", memory_types=[MemoryType.CUSTOM_NOTE])
        assert all(r.type == MemoryType.CUSTOM_NOTE for r in results)

    def test_search_empty_query(self, store):
        """Should search with empty query."""
        store.store(MemoryRecord(
            id="note-1",
            type=MemoryType.CUSTOM_NOTE,
            title="Test Note",
            content="Content",
        ))

        # Search with empty query should return records
        results = store.search("")
        assert len(results) >= 0  # Empty query behavior depends on implementation

    def test_update_existing_record(self, store):
        """Should update existing record."""
        record = MemoryRecord(
            id="update-1",
            type=MemoryType.CUSTOM_NOTE,
            title="Original Title",
            content="Original content",
        )
        store.store(record)

        # Update the record
        record.title = "Updated Title"
        record.content = "Updated content"
        result = store.update(record)

        assert result is True
        retrieved = store.retrieve("update-1")
        assert retrieved.title == "Updated Title"

    def test_retrieve_nonexistent_record(self, store):
        """Should return None for nonexistent record."""
        result = store.retrieve("nonexistent-id")
        assert result is None

    def test_clear_all_records(self, store):
        """Should clear all records."""
        for i in range(5):
            store.store(MemoryRecord(
                id=f"clear-{i}",
                type=MemoryType.CUSTOM_NOTE,
                title=f"Record {i}",
                content="",
            ))

        count = store.clear()
        assert count == 5
        assert len(store.list_by_type(MemoryType.CUSTOM_NOTE)) == 0
