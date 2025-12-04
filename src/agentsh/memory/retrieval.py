"""Memory retrieval and search functionality."""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from agentsh.memory.schemas import MemoryRecord, MemoryType, SearchResult
from agentsh.memory.store import MemoryStore
from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RetrievalConfig:
    """Configuration for retrieval system.

    Attributes:
        max_results: Maximum results to return
        recency_weight: Weight for recency in scoring (0-1)
        frequency_weight: Weight for access frequency in scoring (0-1)
        relevance_weight: Weight for relevance in scoring (0-1)
        min_score: Minimum score threshold
    """

    max_results: int = 10
    recency_weight: float = 0.3
    frequency_weight: float = 0.2
    relevance_weight: float = 0.5
    min_score: float = 0.1


class MemoryRetrieval:
    """Retrieves and ranks relevant memories.

    Combines keyword search with recency and frequency scoring
    to find the most relevant memories for a given query.

    Example:
        retrieval = MemoryRetrieval(store)
        results = retrieval.search("python virtual environment")
        for result in results:
            print(f"{result.score}: {result.record.title}")
    """

    def __init__(
        self,
        store: MemoryStore,
        config: Optional[RetrievalConfig] = None,
    ) -> None:
        """Initialize retrieval system.

        Args:
            store: Memory store backend
            config: Retrieval configuration
        """
        self.store = store
        self.config = config or RetrievalConfig()

    def search(
        self,
        query: str,
        memory_types: Optional[list[MemoryType]] = None,
        tags: Optional[list[str]] = None,
        limit: Optional[int] = None,
    ) -> list[SearchResult]:
        """Search for relevant memories.

        Args:
            query: Search query
            memory_types: Optional type filter
            tags: Optional tag filter
            limit: Maximum results (uses config default if None)

        Returns:
            List of SearchResult sorted by relevance
        """
        limit = limit or self.config.max_results

        # Get initial results from store
        records = self.store.search(
            query=query,
            memory_types=memory_types,
            tags=tags,
            limit=limit * 2,  # Get extra for re-ranking
        )

        # Score and rank results
        results = []
        for record in records:
            score = self._calculate_score(record, query)
            if score >= self.config.min_score:
                results.append(SearchResult(
                    record=record,
                    score=score,
                    match_type="keyword",
                ))

        # Sort by score and limit
        results.sort()
        return results[:limit]

    def get_relevant_context(
        self,
        query: str,
        limit: int = 5,
        max_tokens: int = 2000,
    ) -> list[MemoryRecord]:
        """Get relevant context for a query.

        Returns records that are most relevant to the query,
        respecting token limits.

        Args:
            query: Query to find context for
            limit: Maximum records
            max_tokens: Estimated token limit

        Returns:
            List of relevant MemoryRecords
        """
        results = self.search(query, limit=limit * 2)

        selected = []
        estimated_tokens = 0

        for result in results:
            # Rough token estimate
            record_tokens = len(result.record.content) // 4

            if estimated_tokens + record_tokens <= max_tokens:
                selected.append(result.record)
                estimated_tokens += record_tokens

            if len(selected) >= limit:
                break

        return selected

    def find_similar(
        self,
        record: MemoryRecord,
        limit: int = 5,
    ) -> list[SearchResult]:
        """Find memories similar to a given record.

        Args:
            record: Record to find similar to
            limit: Maximum results

        Returns:
            List of similar records
        """
        # Use title + first part of content as query
        query = f"{record.title} {record.content[:200]}"

        results = self.search(query, limit=limit + 1)

        # Filter out the original record
        return [r for r in results if r.record.id != record.id][:limit]

    def get_by_tags(
        self,
        tags: list[str],
        limit: int = 10,
    ) -> list[MemoryRecord]:
        """Get records matching any of the given tags.

        Args:
            tags: Tags to search for
            limit: Maximum results

        Returns:
            List of matching records
        """
        # Use empty query with tag filter
        return self.store.search(
            query="",
            tags=tags,
            limit=limit,
        )

    def get_recent(
        self,
        memory_type: Optional[MemoryType] = None,
        days: int = 7,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        """Get recently created or accessed records.

        Args:
            memory_type: Optional type filter
            days: Look back this many days
            limit: Maximum results

        Returns:
            List of recent records
        """
        if memory_type:
            records = self.store.list_by_type(memory_type, limit=limit * 2)
        else:
            # Get from all types
            records = []
            for mt in MemoryType:
                records.extend(self.store.list_by_type(mt, limit=limit))

        # Filter by date
        cutoff = datetime.now() - timedelta(days=days)
        recent = [
            r for r in records
            if r.created_at >= cutoff or r.accessed_at >= cutoff
        ]

        # Sort by most recent access
        recent.sort(key=lambda r: r.accessed_at, reverse=True)
        return recent[:limit]

    def get_frequently_used(
        self,
        memory_type: Optional[MemoryType] = None,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        """Get frequently accessed records.

        Args:
            memory_type: Optional type filter
            limit: Maximum results

        Returns:
            List of frequently used records
        """
        if memory_type:
            records = self.store.list_by_type(memory_type, limit=limit * 2)
        else:
            records = []
            for mt in MemoryType:
                records.extend(self.store.list_by_type(mt, limit=limit))

        # Sort by access count
        records.sort(key=lambda r: r.access_count, reverse=True)
        return records[:limit]

    def _calculate_score(self, record: MemoryRecord, query: str) -> float:
        """Calculate relevance score for a record.

        Combines relevance, recency, and frequency scores.

        Args:
            record: Record to score
            query: Search query

        Returns:
            Score between 0 and 1
        """
        # Relevance score (keyword matching)
        relevance = self._calculate_relevance(record, query)

        # Recency score
        recency = self._calculate_recency(record)

        # Frequency score
        frequency = self._calculate_frequency(record)

        # Weighted combination
        score = (
            self.config.relevance_weight * relevance
            + self.config.recency_weight * recency
            + self.config.frequency_weight * frequency
        )

        return min(1.0, score)

    def _calculate_relevance(self, record: MemoryRecord, query: str) -> float:
        """Calculate keyword relevance score."""
        if not query:
            return 0.5

        query_words = set(re.findall(r'\w+', query.lower()))
        if not query_words:
            return 0.5

        # Check title and content
        title_words = set(re.findall(r'\w+', record.title.lower()))
        content_words = set(re.findall(r'\w+', record.content.lower()))

        # Title matches are worth more
        title_matches = len(query_words & title_words)
        content_matches = len(query_words & content_words)

        title_score = title_matches / len(query_words) if query_words else 0
        content_score = content_matches / len(query_words) if query_words else 0

        # Weight title higher
        return min(1.0, title_score * 0.6 + content_score * 0.4)

    def _calculate_recency(self, record: MemoryRecord) -> float:
        """Calculate recency score (higher for newer records)."""
        now = datetime.now()
        age = now - record.accessed_at

        # Decay over 30 days
        days = age.total_seconds() / 86400
        decay_factor = max(0, 1 - (days / 30))

        return decay_factor

    def _calculate_frequency(self, record: MemoryRecord) -> float:
        """Calculate frequency score (higher for frequently accessed)."""
        # Normalize access count (assume 100 is "very frequent")
        return min(1.0, record.access_count / 100)


class SemanticRetrieval:
    """Semantic/vector-based retrieval (requires embeddings).

    This is a placeholder for future implementation with
    actual embedding models.
    """

    def __init__(
        self,
        store: MemoryStore,
        embedding_client: Optional[object] = None,
    ) -> None:
        """Initialize semantic retrieval.

        Args:
            store: Memory store
            embedding_client: Optional embedding client
        """
        self.store = store
        self.embedding_client = embedding_client
        logger.warning(
            "SemanticRetrieval initialized without embedding client. "
            "Vector search will not be available."
        )

    def search(
        self,
        query: str,
        limit: int = 10,
        min_similarity: float = 0.7,
    ) -> list[SearchResult]:
        """Semantic search (placeholder).

        Args:
            query: Search query
            limit: Maximum results
            min_similarity: Minimum cosine similarity

        Returns:
            List of results (empty if no embedding client)
        """
        if not self.embedding_client:
            logger.debug("Semantic search unavailable - no embedding client")
            return []

        # TODO: Implement vector search when embeddings are available
        # 1. Generate query embedding
        # 2. Search records with embeddings
        # 3. Calculate cosine similarity
        # 4. Return top matches

        return []

    def embed_record(self, record: MemoryRecord) -> Optional[list[float]]:
        """Generate embeddings for a record (placeholder).

        Args:
            record: Record to embed

        Returns:
            Embedding vector or None
        """
        if not self.embedding_client:
            return None

        # TODO: Generate embeddings from record content
        return None
