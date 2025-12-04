"""Shell memory for storing user notes and context.

Provides persistent storage for notes, reminders, and context
that the AI can access during conversations.
"""

import json
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MemoryEntry:
    """A memory entry.

    Attributes:
        id: Unique identifier
        content: The memory content
        created_at: Creation timestamp
        tags: Optional tags for categorization
        metadata: Additional metadata
    """

    id: int
    content: str
    created_at: float
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def created_datetime(self) -> datetime:
        """Get created_at as datetime."""
        return datetime.fromtimestamp(self.created_at)

    @property
    def age_str(self) -> str:
        """Get human-readable age string."""
        age = time.time() - self.created_at
        if age < 60:
            return "just now"
        elif age < 3600:
            return f"{int(age / 60)} minutes ago"
        elif age < 86400:
            return f"{int(age / 3600)} hours ago"
        else:
            return f"{int(age / 86400)} days ago"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "content": self.content,
            "created_at": self.created_at,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_row(cls, row: tuple) -> "MemoryEntry":
        """Create from database row."""
        return cls(
            id=row[0],
            content=row[1],
            created_at=row[2],
            tags=json.loads(row[3]) if row[3] else [],
            metadata=json.loads(row[4]) if row[4] else {},
        )


class MemoryStore:
    """SQLite-based memory storage.

    Stores notes and context in a local SQLite database for
    persistence across sessions.

    Example:
        store = MemoryStore(Path("~/.agentsh/memory.db"))
        entry_id = store.remember("Deploy to production on Friday")
        results = store.recall("production")
        store.forget(entry_id)
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        """Initialize memory store.

        Args:
            db_path: Path to SQLite database file
        """
        if db_path is None:
            db_path = Path.home() / ".agentsh" / "memory.db"

        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        self._conn = sqlite3.connect(str(self.db_path))

        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                created_at REAL NOT NULL,
                tags TEXT,
                metadata TEXT
            )
        """)

        # Create full-text search index
        self._conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                content,
                content='memories',
                content_rowid='id'
            )
        """)

        # Triggers to keep FTS in sync
        self._conn.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
            END
        """)

        self._conn.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, content)
                VALUES('delete', old.id, old.content);
            END
        """)

        self._conn.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, content)
                VALUES('delete', old.id, old.content);
                INSERT INTO memories_fts(rowid, content) VALUES (new.id, new.content);
            END
        """)

        self._conn.commit()
        logger.debug("Memory store initialized", path=str(self.db_path))

    def remember(
        self,
        content: str,
        tags: Optional[list[str]] = None,
        metadata: Optional[dict] = None,
    ) -> int:
        """Store a memory.

        Args:
            content: Memory content
            tags: Optional tags for categorization
            metadata: Optional additional metadata

        Returns:
            Memory entry ID
        """
        if not self._conn:
            raise RuntimeError("Memory store not initialized")

        cursor = self._conn.execute(
            """
            INSERT INTO memories (content, created_at, tags, metadata)
            VALUES (?, ?, ?, ?)
            """,
            (
                content,
                time.time(),
                json.dumps(tags or []),
                json.dumps(metadata or {}),
            ),
        )
        self._conn.commit()

        entry_id = cursor.lastrowid
        logger.info("Stored memory", id=entry_id, content_length=len(content))
        return entry_id

    def recall(
        self,
        query: Optional[str] = None,
        limit: int = 10,
        tags: Optional[list[str]] = None,
    ) -> list[MemoryEntry]:
        """Search memories.

        Args:
            query: Search query (uses full-text search)
            limit: Maximum results to return
            tags: Filter by tags

        Returns:
            List of matching memory entries
        """
        if not self._conn:
            raise RuntimeError("Memory store not initialized")

        if query:
            # Full-text search
            cursor = self._conn.execute(
                """
                SELECT m.id, m.content, m.created_at, m.tags, m.metadata
                FROM memories m
                JOIN memories_fts f ON m.id = f.rowid
                WHERE memories_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit),
            )
        else:
            # Return recent memories
            cursor = self._conn.execute(
                """
                SELECT id, content, created_at, tags, metadata
                FROM memories
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            )

        entries = [MemoryEntry.from_row(row) for row in cursor.fetchall()]

        # Filter by tags if specified
        if tags:
            entries = [e for e in entries if any(t in e.tags for t in tags)]

        logger.debug("Recalled memories", query=query, count=len(entries))
        return entries

    def forget(self, entry_id: int) -> bool:
        """Delete a memory.

        Args:
            entry_id: Memory entry ID

        Returns:
            True if deleted, False if not found
        """
        if not self._conn:
            raise RuntimeError("Memory store not initialized")

        cursor = self._conn.execute(
            "DELETE FROM memories WHERE id = ?",
            (entry_id,),
        )
        self._conn.commit()

        deleted = cursor.rowcount > 0
        if deleted:
            logger.info("Deleted memory", id=entry_id)
        return deleted

    def forget_all(self) -> int:
        """Delete all memories.

        Returns:
            Number of deleted entries
        """
        if not self._conn:
            raise RuntimeError("Memory store not initialized")

        cursor = self._conn.execute("DELETE FROM memories")
        self._conn.commit()

        count = cursor.rowcount
        logger.info("Deleted all memories", count=count)
        return count

    def get(self, entry_id: int) -> Optional[MemoryEntry]:
        """Get a specific memory by ID.

        Args:
            entry_id: Memory entry ID

        Returns:
            MemoryEntry or None if not found
        """
        if not self._conn:
            raise RuntimeError("Memory store not initialized")

        cursor = self._conn.execute(
            """
            SELECT id, content, created_at, tags, metadata
            FROM memories
            WHERE id = ?
            """,
            (entry_id,),
        )

        row = cursor.fetchone()
        return MemoryEntry.from_row(row) if row else None

    def count(self) -> int:
        """Get total memory count.

        Returns:
            Number of stored memories
        """
        if not self._conn:
            raise RuntimeError("Memory store not initialized")

        cursor = self._conn.execute("SELECT COUNT(*) FROM memories")
        return cursor.fetchone()[0]

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None


# Global memory store
_memory_store: Optional[MemoryStore] = None


def get_memory_store() -> MemoryStore:
    """Get the global memory store.

    Returns:
        MemoryStore instance
    """
    global _memory_store
    if _memory_store is None:
        _memory_store = MemoryStore()
    return _memory_store


def remember(content: str, tags: Optional[list[str]] = None) -> int:
    """Store a memory (convenience function).

    Args:
        content: Memory content
        tags: Optional tags

    Returns:
        Memory entry ID
    """
    return get_memory_store().remember(content, tags)


def recall(query: Optional[str] = None, limit: int = 10) -> list[MemoryEntry]:
    """Search memories (convenience function).

    Args:
        query: Search query
        limit: Maximum results

    Returns:
        List of matching entries
    """
    return get_memory_store().recall(query, limit)


def forget(entry_id: int) -> bool:
    """Delete a memory (convenience function).

    Args:
        entry_id: Memory entry ID

    Returns:
        True if deleted
    """
    return get_memory_store().forget(entry_id)


def format_memory_list(entries: list[MemoryEntry], use_color: bool = True) -> str:
    """Format memory entries for display.

    Args:
        entries: List of memory entries
        use_color: Whether to use ANSI colors

    Returns:
        Formatted string
    """
    if not entries:
        return "No memories found."

    from agentsh.utils.ux import Color, colorize

    lines = []
    for entry in entries:
        if use_color:
            id_str = colorize(f"[{entry.id}]", Color.CYAN)
            time_str = colorize(entry.age_str, Color.DIM)
        else:
            id_str = f"[{entry.id}]"
            time_str = entry.age_str

        # Truncate long content
        content = entry.content
        if len(content) > 60:
            content = content[:57] + "..."

        lines.append(f"{id_str} {content} ({time_str})")

    return "\n".join(lines)
