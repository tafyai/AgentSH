"""Unified memory manager."""

import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

from agentsh.memory.retrieval import MemoryRetrieval, RetrievalConfig
from agentsh.memory.schemas import (
    MemoryMetadata,
    MemoryRecord,
    MemoryType,
    SearchResult,
    Turn,
)
from agentsh.memory.session import SessionConfig, SessionStore
from agentsh.memory.store import MemoryStore, SQLiteMemoryStore
from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)


class MemoryManager:
    """Unified interface for all memory operations.

    Combines session memory, persistent storage, and retrieval
    into a single cohesive API.

    Example:
        manager = MemoryManager()

        # Store a note
        manager.remember("Python venv: python -m venv .venv", tags=["python", "venv"])

        # Recall relevant memories
        results = manager.recall("virtual environment setup")

        # Track conversation
        manager.add_turn(user_input, agent_response, tools_used)
    """

    def __init__(
        self,
        store: Optional[MemoryStore] = None,
        session_config: Optional[SessionConfig] = None,
        retrieval_config: Optional[RetrievalConfig] = None,
        db_path: str = "~/.agentsh/memory.db",
    ) -> None:
        """Initialize memory manager.

        Args:
            store: Memory store backend (defaults to SQLite)
            session_config: Session configuration
            retrieval_config: Retrieval configuration
            db_path: Path to SQLite database
        """
        # Initialize components
        self._store = store or SQLiteMemoryStore(db_path)
        self.session = SessionStore(session_config)
        self.retrieval = MemoryRetrieval(self._store, retrieval_config)

        logger.info(
            "MemoryManager initialized",
            session_id=self.session.session_id,
            db_path=db_path,
        )

    @property
    def session_id(self) -> str:
        """Get the current session ID."""
        return self.session.session_id

    # === User Commands ===

    def remember(
        self,
        note: str,
        title: Optional[str] = None,
        tags: Optional[list[str]] = None,
        memory_type: MemoryType = MemoryType.CUSTOM_NOTE,
        ttl_days: Optional[int] = None,
    ) -> str:
        """Store a note for later recall.

        User command: :remember <note>

        Args:
            note: Content to remember
            title: Optional title (auto-generated if not provided)
            tags: Optional tags for categorization
            memory_type: Type of memory record
            ttl_days: Days until expiration (None for no expiration)

        Returns:
            ID of the stored record
        """
        # Generate title if not provided
        if not title:
            # Use first line or first 50 chars
            first_line = note.split("\n")[0]
            title = first_line[:50] + ("..." if len(first_line) > 50 else "")

        # Create metadata
        metadata = MemoryMetadata(
            tags=tags or [],
            source="user_command",
            expires_at=datetime.now() + timedelta(days=ttl_days) if ttl_days else None,
        )

        # Create and store record
        record = MemoryRecord(
            id=str(uuid.uuid4()),
            type=memory_type,
            title=title,
            content=note,
            metadata=metadata,
        )

        record_id = self._store.store(record)

        logger.debug(
            "Memory stored",
            record_id=record_id,
            type=memory_type.value,
            tags=tags,
        )

        return record_id

    def recall(
        self,
        query: str,
        tags: Optional[list[str]] = None,
        memory_types: Optional[list[MemoryType]] = None,
        limit: int = 5,
    ) -> list[SearchResult]:
        """Recall relevant memories.

        User command: :recall <query>

        Args:
            query: Search query
            tags: Optional tag filter
            memory_types: Optional type filter
            limit: Maximum results

        Returns:
            List of SearchResult
        """
        return self.retrieval.search(
            query=query,
            memory_types=memory_types,
            tags=tags,
            limit=limit,
        )

    def forget(self, record_id: str) -> bool:
        """Forget (delete) a memory.

        User command: :forget <id>

        Args:
            record_id: ID of record to delete

        Returns:
            True if deleted, False if not found
        """
        deleted = self._store.delete(record_id)

        if deleted:
            logger.debug("Memory forgotten", record_id=record_id)

        return deleted

    # === Programmatic Storage ===

    def store(
        self,
        key: str,
        value: Any,
        memory_type: MemoryType = MemoryType.CUSTOM_NOTE,
        metadata: Optional[MemoryMetadata] = None,
        ttl_days: Optional[int] = None,
    ) -> str:
        """Store a memory programmatically.

        Args:
            key: Title/key for the memory
            value: Content to store (will be stringified)
            memory_type: Type of memory
            metadata: Optional metadata
            ttl_days: Days until expiration

        Returns:
            ID of stored record
        """
        # Convert value to string if needed
        if isinstance(value, dict):
            import json
            content = json.dumps(value, indent=2)
        elif isinstance(value, (list, tuple)):
            import json
            content = json.dumps(value)
        else:
            content = str(value)

        # Create metadata
        if not metadata:
            metadata = MemoryMetadata(
                source="programmatic",
                expires_at=datetime.now() + timedelta(days=ttl_days) if ttl_days else None,
            )
        elif ttl_days and not metadata.expires_at:
            metadata.expires_at = datetime.now() + timedelta(days=ttl_days)

        record = MemoryRecord(
            id=str(uuid.uuid4()),
            type=memory_type,
            title=key,
            content=content,
            metadata=metadata,
        )

        return self._store.store(record)

    def get(self, record_id: str) -> Optional[MemoryRecord]:
        """Get a specific memory by ID.

        Args:
            record_id: Record identifier

        Returns:
            MemoryRecord or None
        """
        return self._store.retrieve(record_id)

    def update(self, record: MemoryRecord) -> bool:
        """Update an existing memory.

        Args:
            record: Record with updated data

        Returns:
            True if updated
        """
        return self._store.update(record)

    # === Session Management ===

    def add_turn(
        self,
        user_input: str,
        agent_response: str,
        tools_used: Optional[list[str]] = None,
        success: bool = True,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Add a conversation turn to session.

        Args:
            user_input: User's input
            agent_response: Agent's response
            tools_used: List of tools that were used
            success: Whether the turn was successful
            metadata: Additional metadata
        """
        turn = Turn(
            user_input=user_input,
            agent_response=agent_response,
            tools_used=tools_used or [],
            success=success,
            metadata=metadata or {},
        )

        self.session.append_turn(turn)

    def get_context(
        self,
        query: Optional[str] = None,
        include_session: bool = True,
        include_relevant: bool = True,
        max_tokens: int = 4000,
    ) -> str:
        """Get context for LLM prompt.

        Combines session history with relevant memories.

        Args:
            query: Optional query to find relevant context
            include_session: Include session history
            include_relevant: Include relevant memories
            max_tokens: Maximum estimated tokens

        Returns:
            Formatted context string
        """
        parts = []

        # Get session context
        if include_session:
            session_context = self.session.get_context_window(max_tokens // 2)
            if session_context.strip():
                parts.append(session_context)

        # Get relevant memories
        if include_relevant and query:
            relevant = self.retrieval.get_relevant_context(
                query=query,
                limit=5,
                max_tokens=max_tokens // 2,
            )

            if relevant:
                parts.append("\nRelevant memories:")
                for record in relevant:
                    parts.append(f"- [{record.type.value}] {record.title}")
                    if record.content != record.title:
                        # Add first 200 chars of content
                        preview = record.content[:200]
                        if len(record.content) > 200:
                            preview += "..."
                        parts.append(f"  {preview}")

        return "\n".join(parts)

    def get_session_turns(self, n: int = 10) -> list[Turn]:
        """Get recent session turns.

        Args:
            n: Number of turns to retrieve

        Returns:
            List of recent turns
        """
        return self.session.get_recent(n)

    def get_session_summary(self) -> str:
        """Get a summary of the current session.

        Returns:
            Summary text
        """
        return self.session.summarize()

    # === Knowledge Base Operations ===

    def store_device_config(
        self,
        device_name: str,
        config: dict[str, Any],
        tags: Optional[list[str]] = None,
    ) -> str:
        """Store device configuration.

        Args:
            device_name: Name of the device
            config: Configuration dictionary
            tags: Additional tags

        Returns:
            Record ID
        """
        import json

        return self.store(
            key=f"Device: {device_name}",
            value=json.dumps(config, indent=2),
            memory_type=MemoryType.DEVICE_CONFIG,
            metadata=MemoryMetadata(
                tags=["device", device_name] + (tags or []),
                source="device_config",
            ),
        )

    def store_user_preference(
        self,
        preference_key: str,
        preference_value: Any,
        tags: Optional[list[str]] = None,
    ) -> str:
        """Store user preference.

        Args:
            preference_key: Preference name
            preference_value: Preference value
            tags: Additional tags

        Returns:
            Record ID
        """
        return self.store(
            key=f"Preference: {preference_key}",
            value=preference_value,
            memory_type=MemoryType.USER_PREFERENCE,
            metadata=MemoryMetadata(
                tags=["preference", preference_key] + (tags or []),
                source="user_preference",
            ),
        )

    def store_solved_incident(
        self,
        title: str,
        problem: str,
        solution: str,
        tags: Optional[list[str]] = None,
    ) -> str:
        """Store a solved incident for future reference.

        Args:
            title: Short title
            problem: Problem description
            solution: How it was solved
            tags: Additional tags

        Returns:
            Record ID
        """
        content = f"Problem:\n{problem}\n\nSolution:\n{solution}"

        return self.store(
            key=title,
            value=content,
            memory_type=MemoryType.SOLVED_INCIDENT,
            metadata=MemoryMetadata(
                tags=["incident"] + (tags or []),
                source="incident_resolution",
            ),
        )

    def store_learned_pattern(
        self,
        pattern_name: str,
        pattern_description: str,
        examples: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
    ) -> str:
        """Store a learned pattern.

        Args:
            pattern_name: Name of the pattern
            pattern_description: Description
            examples: Optional examples
            tags: Additional tags

        Returns:
            Record ID
        """
        content = pattern_description
        if examples:
            content += "\n\nExamples:\n" + "\n".join(f"- {e}" for e in examples)

        return self.store(
            key=f"Pattern: {pattern_name}",
            value=content,
            memory_type=MemoryType.LEARNED_PATTERN,
            metadata=MemoryMetadata(
                tags=["pattern", pattern_name] + (tags or []),
                source="pattern_learning",
            ),
        )

    # === Query Operations ===

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
            List of similar memories
        """
        return self.retrieval.find_similar(record, limit)

    def get_by_tags(
        self,
        tags: list[str],
        limit: int = 10,
    ) -> list[MemoryRecord]:
        """Get memories by tags.

        Args:
            tags: Tags to search for
            limit: Maximum results

        Returns:
            List of matching records
        """
        return self.retrieval.get_by_tags(tags, limit)

    def get_recent(
        self,
        memory_type: Optional[MemoryType] = None,
        days: int = 7,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        """Get recently accessed memories.

        Args:
            memory_type: Optional type filter
            days: Look back this many days
            limit: Maximum results

        Returns:
            List of recent records
        """
        return self.retrieval.get_recent(memory_type, days, limit)

    def get_frequently_used(
        self,
        memory_type: Optional[MemoryType] = None,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        """Get frequently accessed memories.

        Args:
            memory_type: Optional type filter
            limit: Maximum results

        Returns:
            List of frequently used records
        """
        return self.retrieval.get_frequently_used(memory_type, limit)

    # === Maintenance ===

    def cleanup(self) -> int:
        """Clean up expired memories.

        Returns:
            Number of records cleaned up
        """
        if hasattr(self._store, "cleanup_expired"):
            return self._store.cleanup_expired()
        return 0

    def clear_session(self) -> None:
        """Clear the current session."""
        self.session.clear()
        logger.debug("Session cleared", session_id=self.session_id)

    def clear_all(self) -> int:
        """Clear all memories (use with caution).

        Returns:
            Number of records deleted
        """
        count = self._store.clear()
        self.session.clear()
        logger.warning("All memories cleared", records_deleted=count)
        return count

    def get_stats(self) -> dict[str, Any]:
        """Get memory statistics.

        Returns:
            Dict with memory stats
        """
        store_stats = {}
        if hasattr(self._store, "get_stats"):
            store_stats = self._store.get_stats()

        return {
            "session_id": self.session_id,
            "session_turns": self.session.turn_count,
            "session_summaries": len(self.session._summaries),
            **store_stats,
        }

    def persist_session(self) -> list[str]:
        """Persist current session to long-term storage.

        Converts session turns to memory records and stores them.

        Returns:
            List of stored record IDs
        """
        records = self.session.to_memory_records()
        record_ids = []

        for record in records:
            record_id = self._store.store(record)
            record_ids.append(record_id)

        logger.info(
            "Session persisted",
            session_id=self.session_id,
            records_stored=len(record_ids),
        )

        return record_ids
