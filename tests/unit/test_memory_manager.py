"""Tests for memory manager."""

import tempfile
from pathlib import Path

import pytest

from agentsh.memory.manager import MemoryManager
from agentsh.memory.schemas import MemoryMetadata, MemoryRecord, MemoryType
from agentsh.memory.store import InMemoryStore


class TestMemoryManager:
    """Tests for MemoryManager."""

    @pytest.fixture
    def memory_dir(self):
        """Create a temporary directory for memory database."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def manager(self, memory_dir):
        """Create a memory manager with in-memory store."""
        store = InMemoryStore()
        return MemoryManager(store=store)

    def test_init(self, memory_dir):
        """Test initialization."""
        db_path = str(memory_dir / "test.db")
        manager = MemoryManager(db_path=db_path)
        assert manager.session_id is not None

    def test_remember(self, manager):
        """Test remembering a note."""
        record_id = manager.remember(
            "Python venv: python -m venv .venv",
            tags=["python", "venv"],
        )
        assert record_id is not None

        results = manager.recall("python venv")
        assert len(results) > 0

    def test_remember_with_title(self, manager):
        """Test remembering with custom title."""
        record_id = manager.remember(
            "Long content here...",
            title="Short Title",
            tags=["test"],
        )
        retrieved = manager.get(record_id)
        assert retrieved.title == "Short Title"

    def test_remember_with_ttl(self, manager):
        """Test remembering with TTL."""
        record_id = manager.remember(
            "Temporary note",
            ttl_days=7,
        )
        retrieved = manager.get(record_id)
        assert retrieved.metadata.expires_at is not None

    def test_recall(self, manager):
        """Test recalling memories."""
        manager.remember("Python is a programming language", tags=["python"])
        manager.remember("JavaScript is for web development", tags=["js"])

        results = manager.recall("Python")
        assert len(results) == 1
        assert "Python" in results[0].record.content

    def test_recall_with_filters(self, manager):
        """Test recall with filters."""
        manager.remember("Note 1", tags=["important"])
        manager.remember("Note 2", tags=["casual"])

        results = manager.recall("Note", tags=["important"])
        assert len(results) == 1

    def test_forget(self, manager):
        """Test forgetting a memory."""
        record_id = manager.remember("Forget me")
        assert manager.forget(record_id) is True
        assert manager.get(record_id) is None
        assert manager.forget(record_id) is False

    def test_store_programmatic(self, manager):
        """Test programmatic storage."""
        record_id = manager.store(
            key="Config Value",
            value={"setting": "value"},
            memory_type=MemoryType.USER_PREFERENCE,
        )
        retrieved = manager.get(record_id)
        assert retrieved is not None
        assert retrieved.type == MemoryType.USER_PREFERENCE

    def test_store_with_list(self, manager):
        """Test storing list values."""
        record_id = manager.store(
            key="List Data",
            value=[1, 2, 3],
        )
        retrieved = manager.get(record_id)
        assert "[1, 2, 3]" in retrieved.content

    def test_update(self, manager):
        """Test updating a record."""
        record_id = manager.remember("Original")
        record = manager.get(record_id)
        record.content = "Updated"
        manager.update(record)

        retrieved = manager.get(record_id)
        assert retrieved.content == "Updated"

    # Session tests

    def test_add_turn(self, manager):
        """Test adding conversation turns."""
        manager.add_turn(
            user_input="Hello",
            agent_response="Hi there!",
            tools_used=["greeting.respond"],
        )
        turns = manager.get_session_turns(10)
        assert len(turns) == 1
        assert turns[0].user_input == "Hello"

    def test_get_context(self, manager):
        """Test getting combined context."""
        manager.add_turn(
            user_input="What is Python?",
            agent_response="Python is a programming language.",
        )
        manager.remember("Python tip: use list comprehensions", tags=["python"])

        context = manager.get_context(
            query="Python",
            include_session=True,
            include_relevant=True,
        )
        assert "What is Python?" in context

    def test_get_session_summary(self, manager):
        """Test getting session summary."""
        manager.add_turn(
            user_input="Test",
            agent_response="Response",
            tools_used=["test.tool"],
        )
        summary = manager.get_session_summary()
        assert "1 exchanges" in summary

    # Knowledge base operations

    def test_store_device_config(self, manager):
        """Test storing device configuration."""
        record_id = manager.store_device_config(
            "sensor-001",
            {"baudrate": 9600, "protocol": "serial"},
            tags=["production"],
        )
        record = manager.get(record_id)
        assert record.type == MemoryType.DEVICE_CONFIG
        assert "sensor-001" in record.metadata.tags

    def test_store_user_preference(self, manager):
        """Test storing user preference."""
        record_id = manager.store_user_preference(
            "theme",
            "dark",
        )
        record = manager.get(record_id)
        assert record.type == MemoryType.USER_PREFERENCE

    def test_store_solved_incident(self, manager):
        """Test storing solved incident."""
        record_id = manager.store_solved_incident(
            title="Network Timeout",
            problem="Connection keeps timing out",
            solution="Increase timeout to 30 seconds",
            tags=["network"],
        )
        record = manager.get(record_id)
        assert record.type == MemoryType.SOLVED_INCIDENT
        assert "Problem:" in record.content
        assert "Solution:" in record.content

    def test_store_learned_pattern(self, manager):
        """Test storing learned pattern."""
        record_id = manager.store_learned_pattern(
            pattern_name="Retry on Failure",
            pattern_description="When an operation fails, retry up to 3 times",
            examples=["API calls", "File operations"],
        )
        record = manager.get(record_id)
        assert record.type == MemoryType.LEARNED_PATTERN
        assert "Examples:" in record.content

    # Query operations

    def test_get_by_tags(self, manager):
        """Test getting by tags."""
        manager.remember("Note 1", tags=["important"])
        manager.remember("Note 2", tags=["important", "work"])
        manager.remember("Note 3", tags=["casual"])

        records = manager.get_by_tags(["important"])
        assert len(records) == 2

    def test_get_recent(self, manager):
        """Test getting recent records."""
        manager.remember("Recent note")
        records = manager.get_recent(days=7)
        assert len(records) > 0

    def test_get_frequently_used(self, manager):
        """Test getting frequently used records."""
        record_id = manager.remember("Test note")
        # Access multiple times
        for _ in range(5):
            manager.get(record_id)

        frequent = manager.get_frequently_used(limit=1)
        assert len(frequent) > 0

    # Maintenance

    def test_clear_session(self, manager):
        """Test clearing session."""
        manager.add_turn(
            user_input="Test",
            agent_response="Response",
        )
        manager.clear_session()
        turns = manager.get_session_turns(10)
        assert len(turns) == 0

    def test_clear_all(self, manager):
        """Test clearing all memories."""
        manager.remember("Note 1")
        manager.remember("Note 2")
        count = manager.clear_all()
        assert count == 2

    def test_get_stats(self, manager):
        """Test getting statistics."""
        manager.remember("Note 1")
        manager.add_turn("Q", "A")

        stats = manager.get_stats()
        assert "session_id" in stats
        assert stats["session_turns"] == 1

    def test_persist_session(self, manager):
        """Test persisting session to long-term storage."""
        manager.add_turn(
            user_input="What time is it?",
            agent_response="It's 3 PM.",
        )
        manager.add_turn(
            user_input="Thanks!",
            agent_response="You're welcome!",
        )

        record_ids = manager.persist_session()
        assert len(record_ids) == 2

        # Check that records are stored
        for record_id in record_ids:
            record = manager.get(record_id)
            assert record is not None
            assert record.type == MemoryType.CONVERSATION_TURN
