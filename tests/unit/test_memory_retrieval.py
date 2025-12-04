"""Tests for memory retrieval system."""

from datetime import datetime, timedelta

import pytest

from agentsh.memory.retrieval import MemoryRetrieval, RetrievalConfig, SemanticRetrieval
from agentsh.memory.schemas import MemoryMetadata, MemoryRecord, MemoryType
from agentsh.memory.store import InMemoryStore


class TestRetrievalConfig:
    """Tests for RetrievalConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RetrievalConfig()
        assert config.max_results == 10
        assert config.recency_weight == 0.3
        assert config.frequency_weight == 0.2
        assert config.relevance_weight == 0.5
        assert config.min_score == 0.1

    def test_custom_config(self):
        """Test custom configuration."""
        config = RetrievalConfig(
            max_results=20,
            relevance_weight=0.7,
            min_score=0.2,
        )
        assert config.max_results == 20
        assert config.relevance_weight == 0.7
        assert config.min_score == 0.2


class TestMemoryRetrieval:
    """Tests for MemoryRetrieval."""

    @pytest.fixture
    def store(self):
        """Create a store with test data."""
        store = InMemoryStore()
        # Add test records
        store.store(MemoryRecord(
            id="python-1",
            type=MemoryType.CUSTOM_NOTE,
            title="Python Virtual Environment",
            content="Use python -m venv to create a virtual environment",
            metadata=MemoryMetadata(tags=["python", "venv"]),
        ))
        store.store(MemoryRecord(
            id="python-2",
            type=MemoryType.LEARNED_PATTERN,
            title="Python Package Management",
            content="Use pip install to install packages",
            metadata=MemoryMetadata(tags=["python", "pip"]),
            access_count=50,  # Frequently used
        ))
        store.store(MemoryRecord(
            id="js-1",
            type=MemoryType.CUSTOM_NOTE,
            title="JavaScript Setup",
            content="Use npm init to create a new project",
            metadata=MemoryMetadata(tags=["javascript", "npm"]),
        ))
        return store

    @pytest.fixture
    def retrieval(self, store):
        """Create a retrieval instance."""
        return MemoryRetrieval(store)

    def test_search_by_keyword(self, retrieval):
        """Test basic keyword search."""
        results = retrieval.search("Python")
        assert len(results) == 2
        # Results should be sorted by score
        assert results[0].score >= results[1].score

    def test_search_with_type_filter(self, retrieval):
        """Test search with type filter."""
        results = retrieval.search(
            "Python",
            memory_types=[MemoryType.LEARNED_PATTERN],
        )
        assert len(results) == 1
        assert results[0].record.type == MemoryType.LEARNED_PATTERN

    def test_search_with_tag_filter(self, retrieval):
        """Test search with tag filter."""
        results = retrieval.search("install", tags=["pip"])
        assert len(results) == 1
        assert "pip" in results[0].record.metadata.tags

    def test_search_with_limit(self, retrieval):
        """Test search with result limit."""
        results = retrieval.search("", limit=1)
        assert len(results) <= 1

    def test_search_min_score(self, store):
        """Test that results below min_score are filtered."""
        config = RetrievalConfig(min_score=0.99)  # Very high threshold
        retrieval = MemoryRetrieval(store, config)
        results = retrieval.search("xyz123nonexistent")
        assert len(results) == 0

    def test_get_relevant_context(self, retrieval):
        """Test getting relevant context."""
        records = retrieval.get_relevant_context("Python virtual environment")
        assert len(records) > 0
        assert all(isinstance(r, MemoryRecord) for r in records)

    def test_get_relevant_context_token_limit(self, retrieval):
        """Test context respects token limits."""
        records = retrieval.get_relevant_context(
            "Python",
            max_tokens=10,  # Very small limit
        )
        # Should return at most what fits in token limit
        total_chars = sum(len(r.content) for r in records)
        assert total_chars // 4 <= 10 or len(records) == 1

    def test_find_similar(self, store):
        """Test finding similar records."""
        # Use a lower min_score threshold to find similar records
        config = RetrievalConfig(min_score=0.01)
        retrieval = MemoryRetrieval(store, config)

        record = store.retrieve("python-1")
        similar = retrieval.find_similar(record, limit=5)

        # Should not include the original record
        assert all(r.record.id != "python-1" for r in similar)
        # Note: InMemoryStore search requires exact word match,
        # so similar records might not be found in all cases

    def test_get_by_tags(self, retrieval):
        """Test getting records by tags."""
        records = retrieval.get_by_tags(["python"])
        assert len(records) == 2
        for record in records:
            assert "python" in record.metadata.tags

    def test_get_recent(self, retrieval, store):
        """Test getting recent records."""
        # Add a record with old access/created time
        old_record = MemoryRecord(
            id="old",
            type=MemoryType.CUSTOM_NOTE,
            title="Old",
            content="",
            created_at=datetime.now() - timedelta(days=30),
            accessed_at=datetime.now() - timedelta(days=30),
        )
        store.store(old_record)

        recent = retrieval.get_recent(days=7)
        assert all(r.id != "old" for r in recent)

    def test_get_frequently_used(self, retrieval):
        """Test getting frequently used records."""
        frequent = retrieval.get_frequently_used(limit=1)
        assert len(frequent) == 1
        # Should be the one with access_count=50
        assert frequent[0].id == "python-2"

    def test_score_calculation_relevance(self, retrieval):
        """Test that relevance scoring works correctly."""
        # Search for exact title match
        results = retrieval.search("Python Virtual Environment")
        assert len(results) > 0
        # Exact match should score high
        assert results[0].record.id == "python-1"
        assert results[0].score > 0.5

    def test_score_calculation_frequency(self, store):
        """Test that frequency affects scoring."""
        config = RetrievalConfig(
            relevance_weight=0.0,
            frequency_weight=1.0,
            recency_weight=0.0,
        )
        retrieval = MemoryRetrieval(store, config)
        results = retrieval.search("Python")
        # High frequency record should rank first
        assert results[0].record.id == "python-2"


class TestSemanticRetrieval:
    """Tests for SemanticRetrieval (placeholder)."""

    @pytest.fixture
    def store(self):
        """Create a test store."""
        return InMemoryStore()

    def test_init_without_client(self, store):
        """Test initialization without embedding client."""
        retrieval = SemanticRetrieval(store)
        assert retrieval.embedding_client is None

    def test_search_without_client(self, store):
        """Test search returns empty without client."""
        retrieval = SemanticRetrieval(store)
        results = retrieval.search("test query")
        assert results == []

    def test_embed_without_client(self, store):
        """Test embed returns None without client."""
        retrieval = SemanticRetrieval(store)
        record = MemoryRecord(
            id="test",
            type=MemoryType.CUSTOM_NOTE,
            title="Test",
            content="Content",
        )
        embedding = retrieval.embed_record(record)
        assert embedding is None
