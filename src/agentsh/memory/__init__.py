"""Memory and context management.

This module provides persistent memory and context management for AgentSH,
including session history, long-term storage, and intelligent retrieval.

Components:
    - schemas: Memory record types and data classes
    - session: In-memory session/conversation tracking
    - store: Persistent storage backends (SQLite, in-memory)
    - retrieval: Search and retrieval system
    - manager: Unified memory interface
"""

from agentsh.memory.manager import MemoryManager
from agentsh.memory.retrieval import MemoryRetrieval, RetrievalConfig, SemanticRetrieval
from agentsh.memory.schemas import (
    MemoryMetadata,
    MemoryRecord,
    MemoryType,
    SearchResult,
    Turn,
)
from agentsh.memory.session import (
    MultiSessionStore,
    SessionConfig,
    SessionStore,
)
from agentsh.memory.store import (
    InMemoryStore,
    MemoryStore,
    SQLiteMemoryStore,
)

__all__ = [
    # Manager
    "MemoryManager",
    # Schemas
    "MemoryType",
    "MemoryMetadata",
    "MemoryRecord",
    "Turn",
    "SearchResult",
    # Session
    "SessionStore",
    "SessionConfig",
    "MultiSessionStore",
    # Store
    "MemoryStore",
    "SQLiteMemoryStore",
    "InMemoryStore",
    # Retrieval
    "MemoryRetrieval",
    "RetrievalConfig",
    "SemanticRetrieval",
]
