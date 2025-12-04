"""Tests for memory schemas."""

import uuid
from datetime import datetime, timedelta

import pytest

from agentsh.memory.schemas import (
    MemoryMetadata,
    MemoryRecord,
    MemoryType,
    SearchResult,
    Turn,
)


class TestMemoryType:
    """Tests for MemoryType enum."""

    def test_all_types_exist(self):
        """Test that all expected types exist."""
        expected = [
            "conversation_turn",
            "session_summary",
            "device_config",
            "user_preference",
            "solved_incident",
            "learned_pattern",
            "workflow_template",
            "workflow_execution",
            "environment_state",
            "command_history",
            "custom_note",
            "bookmark",
        ]
        actual = [t.value for t in MemoryType]
        assert set(expected) == set(actual)

    def test_type_values(self):
        """Test type value access."""
        assert MemoryType.CONVERSATION_TURN.value == "conversation_turn"
        assert MemoryType.CUSTOM_NOTE.value == "custom_note"


class TestMemoryMetadata:
    """Tests for MemoryMetadata dataclass."""

    def test_default_metadata(self):
        """Test default metadata values."""
        metadata = MemoryMetadata()
        assert metadata.tags == []
        assert metadata.confidence == 1.0
        assert metadata.source == ""
        assert metadata.related_ids == []
        assert metadata.expires_at is None
        assert metadata.custom == {}

    def test_custom_metadata(self):
        """Test custom metadata values."""
        expires = datetime.now() + timedelta(days=7)
        metadata = MemoryMetadata(
            tags=["test", "python"],
            confidence=0.8,
            source="test_suite",
            related_ids=["id1", "id2"],
            expires_at=expires,
            custom={"key": "value"},
        )
        assert metadata.tags == ["test", "python"]
        assert metadata.confidence == 0.8
        assert metadata.source == "test_suite"
        assert len(metadata.related_ids) == 2
        assert metadata.expires_at == expires
        assert metadata.custom["key"] == "value"


class TestMemoryRecord:
    """Tests for MemoryRecord dataclass."""

    def test_create_record(self):
        """Test creating a memory record."""
        record = MemoryRecord(
            id=str(uuid.uuid4()),
            type=MemoryType.CUSTOM_NOTE,
            title="Test Note",
            content="This is a test note content.",
        )
        assert record.title == "Test Note"
        assert record.type == MemoryType.CUSTOM_NOTE
        assert record.access_count == 0

    def test_record_with_metadata(self):
        """Test record with custom metadata."""
        metadata = MemoryMetadata(tags=["test"])
        record = MemoryRecord(
            id="test-id",
            type=MemoryType.USER_PREFERENCE,
            title="Preference",
            content="value",
            metadata=metadata,
        )
        assert "test" in record.metadata.tags

    def test_to_dict(self):
        """Test converting record to dictionary."""
        record = MemoryRecord(
            id="test-id",
            type=MemoryType.CUSTOM_NOTE,
            title="Test",
            content="Content",
            metadata=MemoryMetadata(tags=["tag1"]),
        )
        data = record.to_dict()
        assert data["id"] == "test-id"
        assert data["type"] == "custom_note"
        assert data["title"] == "Test"
        assert "tag1" in data["metadata"]["tags"]

    def test_from_dict(self):
        """Test creating record from dictionary."""
        data = {
            "id": "test-id",
            "type": "custom_note",
            "title": "Test",
            "content": "Content",
            "metadata": {
                "tags": ["tag1"],
                "confidence": 0.9,
                "source": "test",
                "related_ids": [],
                "expires_at": None,
                "custom": {},
            },
            "embeddings": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "accessed_at": datetime.now().isoformat(),
            "access_count": 5,
        }
        record = MemoryRecord.from_dict(data)
        assert record.id == "test-id"
        assert record.type == MemoryType.CUSTOM_NOTE
        assert record.access_count == 5

    def test_record_timestamps(self):
        """Test record timestamps are set."""
        before = datetime.now()
        record = MemoryRecord(
            id="test",
            type=MemoryType.CUSTOM_NOTE,
            title="Test",
            content="Content",
        )
        after = datetime.now()
        assert before <= record.created_at <= after
        assert before <= record.updated_at <= after


class TestTurn:
    """Tests for Turn dataclass."""

    def test_create_turn(self):
        """Test creating a conversation turn."""
        turn = Turn(
            user_input="List files",
            agent_response="Here are the files...",
            tools_used=["fs.list"],
        )
        assert turn.user_input == "List files"
        assert turn.success is True
        assert "fs.list" in turn.tools_used

    def test_turn_to_memory_record(self):
        """Test converting turn to memory record."""
        turn = Turn(
            user_input="What is Python?",
            agent_response="Python is a programming language.",
            tools_used=["web.search"],
            success=True,
        )
        record = turn.to_memory_record("session-123")
        assert record.type == MemoryType.CONVERSATION_TURN
        assert "session:session-123" in record.metadata.tags
        assert "web.search" in record.metadata.tags
        assert "Python" in record.content

    def test_turn_metadata(self):
        """Test turn with custom metadata."""
        turn = Turn(
            user_input="Test",
            agent_response="Response",
            metadata={"custom_key": "custom_value"},
        )
        assert turn.metadata["custom_key"] == "custom_value"


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_create_search_result(self):
        """Test creating a search result."""
        record = MemoryRecord(
            id="test",
            type=MemoryType.CUSTOM_NOTE,
            title="Test",
            content="Content",
        )
        result = SearchResult(record=record, score=0.85)
        assert result.score == 0.85
        assert result.match_type == "keyword"

    def test_search_result_sorting(self):
        """Test that search results sort by score descending."""
        records = [
            MemoryRecord(
                id=f"r{i}",
                type=MemoryType.CUSTOM_NOTE,
                title=f"Record {i}",
                content="",
            )
            for i in range(3)
        ]
        results = [
            SearchResult(record=records[0], score=0.5),
            SearchResult(record=records[1], score=0.9),
            SearchResult(record=records[2], score=0.7),
        ]
        sorted_results = sorted(results)
        assert sorted_results[0].score == 0.9  # Highest first
        assert sorted_results[1].score == 0.7
        assert sorted_results[2].score == 0.5
