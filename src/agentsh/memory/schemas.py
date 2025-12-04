"""Memory record schemas and types."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class MemoryType(Enum):
    """Types of memory records."""

    # Session-related
    CONVERSATION_TURN = "conversation_turn"
    SESSION_SUMMARY = "session_summary"

    # Knowledge
    DEVICE_CONFIG = "device_config"
    USER_PREFERENCE = "user_preference"
    SOLVED_INCIDENT = "solved_incident"
    LEARNED_PATTERN = "learned_pattern"

    # Workflows
    WORKFLOW_TEMPLATE = "workflow_template"
    WORKFLOW_EXECUTION = "workflow_execution"

    # Environment
    ENVIRONMENT_STATE = "environment_state"
    COMMAND_HISTORY = "command_history"

    # User-defined
    CUSTOM_NOTE = "custom_note"
    BOOKMARK = "bookmark"


@dataclass
class MemoryMetadata:
    """Metadata for a memory record.

    Attributes:
        tags: List of tags for categorization
        confidence: Confidence score (0.0 to 1.0)
        source: Where this memory came from
        related_ids: IDs of related memory records
        expires_at: Optional expiration time
        custom: Additional custom metadata
    """

    tags: list[str] = field(default_factory=list)
    confidence: float = 1.0
    source: str = ""
    related_ids: list[str] = field(default_factory=list)
    expires_at: Optional[datetime] = None
    custom: dict[str, Any] = field(default_factory=dict)


@dataclass
class MemoryRecord:
    """A single memory record.

    Attributes:
        id: Unique identifier
        type: Type of memory
        title: Short title/summary
        content: Full content
        metadata: Additional metadata
        embeddings: Optional vector embeddings
        created_at: Creation timestamp
        updated_at: Last update timestamp
        accessed_at: Last access timestamp
        access_count: Number of times accessed
    """

    id: str
    type: MemoryType
    title: str
    content: str
    metadata: MemoryMetadata = field(default_factory=MemoryMetadata)
    embeddings: Optional[list[float]] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    accessed_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "type": self.type.value,
            "title": self.title,
            "content": self.content,
            "metadata": {
                "tags": self.metadata.tags,
                "confidence": self.metadata.confidence,
                "source": self.metadata.source,
                "related_ids": self.metadata.related_ids,
                "expires_at": self.metadata.expires_at.isoformat() if self.metadata.expires_at else None,
                "custom": self.metadata.custom,
            },
            "embeddings": self.embeddings,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "accessed_at": self.accessed_at.isoformat(),
            "access_count": self.access_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryRecord":
        """Create from dictionary."""
        metadata = MemoryMetadata(
            tags=data.get("metadata", {}).get("tags", []),
            confidence=data.get("metadata", {}).get("confidence", 1.0),
            source=data.get("metadata", {}).get("source", ""),
            related_ids=data.get("metadata", {}).get("related_ids", []),
            expires_at=datetime.fromisoformat(data["metadata"]["expires_at"])
            if data.get("metadata", {}).get("expires_at")
            else None,
            custom=data.get("metadata", {}).get("custom", {}),
        )

        return cls(
            id=data["id"],
            type=MemoryType(data["type"]),
            title=data["title"],
            content=data["content"],
            metadata=metadata,
            embeddings=data.get("embeddings"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            accessed_at=datetime.fromisoformat(data["accessed_at"]),
            access_count=data.get("access_count", 0),
        )


@dataclass
class Turn:
    """A single conversation turn.

    Attributes:
        user_input: What the user said/asked
        agent_response: Agent's response
        tools_used: List of tools that were called
        timestamp: When this turn occurred
        success: Whether the turn was successful
        metadata: Additional turn metadata
    """

    user_input: str
    agent_response: str
    tools_used: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    success: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_memory_record(self, session_id: str) -> MemoryRecord:
        """Convert to a memory record."""
        import uuid

        return MemoryRecord(
            id=str(uuid.uuid4()),
            type=MemoryType.CONVERSATION_TURN,
            title=self.user_input[:100],
            content=f"User: {self.user_input}\n\nAssistant: {self.agent_response}",
            metadata=MemoryMetadata(
                tags=["session:" + session_id] + self.tools_used,
                source="conversation",
                custom={
                    "tools_used": self.tools_used,
                    "success": self.success,
                    **self.metadata,
                },
            ),
            created_at=self.timestamp,
        )


@dataclass
class SearchResult:
    """Result from a memory search.

    Attributes:
        record: The matching memory record
        score: Relevance score (higher is better)
        match_type: How the match was found (keyword, semantic, etc.)
    """

    record: MemoryRecord
    score: float
    match_type: str = "keyword"

    def __lt__(self, other: "SearchResult") -> bool:
        """Sort by score descending."""
        return self.score > other.score
