"""Persistent memory storage backends."""

import json
import sqlite3
import threading
from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, Optional

from agentsh.memory.schemas import MemoryMetadata, MemoryRecord, MemoryType
from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)


class MemoryStore(ABC):
    """Abstract base class for memory storage.

    Defines the interface for persistent memory storage backends.
    """

    @abstractmethod
    def store(
        self,
        record: MemoryRecord,
    ) -> str:
        """Store a memory record.

        Args:
            record: Record to store

        Returns:
            ID of the stored record
        """
        pass

    @abstractmethod
    def retrieve(self, record_id: str) -> Optional[MemoryRecord]:
        """Retrieve a memory record by ID.

        Args:
            record_id: Record identifier

        Returns:
            MemoryRecord or None if not found
        """
        pass

    @abstractmethod
    def delete(self, record_id: str) -> bool:
        """Delete a memory record.

        Args:
            record_id: Record identifier

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    def list_by_type(
        self,
        memory_type: MemoryType,
        limit: int = 100,
    ) -> list[MemoryRecord]:
        """List records by type.

        Args:
            memory_type: Type to filter by
            limit: Maximum records to return

        Returns:
            List of matching records
        """
        pass

    @abstractmethod
    def search(
        self,
        query: str,
        memory_types: Optional[list[MemoryType]] = None,
        tags: Optional[list[str]] = None,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        """Search for memory records.

        Args:
            query: Search query
            memory_types: Optional type filter
            tags: Optional tag filter
            limit: Maximum results

        Returns:
            List of matching records
        """
        pass

    @abstractmethod
    def update(self, record: MemoryRecord) -> bool:
        """Update an existing record.

        Args:
            record: Record with updated data

        Returns:
            True if updated, False if not found
        """
        pass

    @abstractmethod
    def clear(self) -> int:
        """Clear all records.

        Returns:
            Number of records deleted
        """
        pass


class SQLiteMemoryStore(MemoryStore):
    """SQLite-based persistent memory store.

    Stores memory records in a SQLite database with full-text search
    support and automatic TTL enforcement.

    Example:
        store = SQLiteMemoryStore("~/.agentsh/memory.db")
        store.store(record)
        results = store.search("python project")
    """

    def __init__(
        self,
        db_path: str = "~/.agentsh/memory.db",
        enable_fts: bool = True,
    ) -> None:
        """Initialize SQLite store.

        Args:
            db_path: Path to database file
            enable_fts: Enable full-text search
        """
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.enable_fts = enable_fts
        self._local = threading.local()

        self._init_db()

        logger.info(
            "SQLiteMemoryStore initialized",
            db_path=str(self.db_path),
            fts_enabled=enable_fts,
        )

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a thread-local database connection."""
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
            )
            self._local.conn.row_factory = sqlite3.Row

        yield self._local.conn

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Main records table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory_records (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    embeddings TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    accessed_at TEXT NOT NULL,
                    access_count INTEGER DEFAULT 0
                )
            """)

            # Tags table for efficient tag queries
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory_tags (
                    record_id TEXT NOT NULL,
                    tag TEXT NOT NULL,
                    PRIMARY KEY (record_id, tag),
                    FOREIGN KEY (record_id) REFERENCES memory_records(id)
                        ON DELETE CASCADE
                )
            """)

            # Indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_records_type
                ON memory_records(type)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_records_created
                ON memory_records(created_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tags_tag
                ON memory_tags(tag)
            """)

            # Full-text search table
            if self.enable_fts:
                cursor.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts
                    USING fts5(
                        id,
                        title,
                        content,
                        content='memory_records',
                        content_rowid='rowid'
                    )
                """)

                # Triggers to keep FTS in sync
                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS memory_ai AFTER INSERT ON memory_records
                    BEGIN
                        INSERT INTO memory_fts(rowid, id, title, content)
                        VALUES (NEW.rowid, NEW.id, NEW.title, NEW.content);
                    END
                """)

                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS memory_ad AFTER DELETE ON memory_records
                    BEGIN
                        INSERT INTO memory_fts(memory_fts, rowid, id, title, content)
                        VALUES ('delete', OLD.rowid, OLD.id, OLD.title, OLD.content);
                    END
                """)

                cursor.execute("""
                    CREATE TRIGGER IF NOT EXISTS memory_au AFTER UPDATE ON memory_records
                    BEGIN
                        INSERT INTO memory_fts(memory_fts, rowid, id, title, content)
                        VALUES ('delete', OLD.rowid, OLD.id, OLD.title, OLD.content);
                        INSERT INTO memory_fts(rowid, id, title, content)
                        VALUES (NEW.rowid, NEW.id, NEW.title, NEW.content);
                    END
                """)

            conn.commit()

    def store(self, record: MemoryRecord) -> str:
        """Store a memory record."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Serialize metadata and embeddings
            metadata_json = json.dumps({
                "tags": record.metadata.tags,
                "confidence": record.metadata.confidence,
                "source": record.metadata.source,
                "related_ids": record.metadata.related_ids,
                "expires_at": record.metadata.expires_at.isoformat()
                if record.metadata.expires_at
                else None,
                "custom": record.metadata.custom,
            })

            embeddings_json = (
                json.dumps(record.embeddings) if record.embeddings else None
            )

            cursor.execute(
                """
                INSERT OR REPLACE INTO memory_records
                (id, type, title, content, metadata, embeddings,
                 created_at, updated_at, accessed_at, access_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.type.value,
                    record.title,
                    record.content,
                    metadata_json,
                    embeddings_json,
                    record.created_at.isoformat(),
                    record.updated_at.isoformat(),
                    record.accessed_at.isoformat(),
                    record.access_count,
                ),
            )

            # Store tags
            cursor.execute(
                "DELETE FROM memory_tags WHERE record_id = ?",
                (record.id,),
            )
            for tag in record.metadata.tags:
                cursor.execute(
                    "INSERT INTO memory_tags (record_id, tag) VALUES (?, ?)",
                    (record.id, tag),
                )

            conn.commit()

            logger.debug("Record stored", record_id=record.id, type=record.type.value)
            return record.id

    def retrieve(self, record_id: str) -> Optional[MemoryRecord]:
        """Retrieve a memory record by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM memory_records WHERE id = ?",
                (record_id,),
            )
            row = cursor.fetchone()

            if not row:
                return None

            record = self._row_to_record(row)

            # Update access stats
            cursor.execute(
                """
                UPDATE memory_records
                SET accessed_at = ?, access_count = access_count + 1
                WHERE id = ?
                """,
                (datetime.now().isoformat(), record_id),
            )
            conn.commit()

            return record

    def delete(self, record_id: str) -> bool:
        """Delete a memory record."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "DELETE FROM memory_records WHERE id = ?",
                (record_id,),
            )
            conn.commit()

            deleted = cursor.rowcount > 0
            if deleted:
                logger.debug("Record deleted", record_id=record_id)

            return deleted

    def list_by_type(
        self,
        memory_type: MemoryType,
        limit: int = 100,
    ) -> list[MemoryRecord]:
        """List records by type."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM memory_records
                WHERE type = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (memory_type.value, limit),
            )

            return [self._row_to_record(row) for row in cursor.fetchall()]

    def search(
        self,
        query: str,
        memory_types: Optional[list[MemoryType]] = None,
        tags: Optional[list[str]] = None,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        """Search for memory records."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if self.enable_fts and query:
                # Use full-text search
                sql = """
                    SELECT r.* FROM memory_records r
                    JOIN memory_fts f ON r.id = f.id
                    WHERE memory_fts MATCH ?
                """
                params: list[Any] = [query]
            else:
                # Fallback to LIKE search
                sql = """
                    SELECT * FROM memory_records
                    WHERE (title LIKE ? OR content LIKE ?)
                """
                params = [f"%{query}%", f"%{query}%"]

            # Add type filter
            if memory_types:
                type_placeholders = ",".join("?" * len(memory_types))
                sql += f" AND type IN ({type_placeholders})"
                params.extend(t.value for t in memory_types)

            # Add tag filter
            if tags:
                tag_placeholders = ",".join("?" * len(tags))
                sql += f"""
                    AND id IN (
                        SELECT record_id FROM memory_tags
                        WHERE tag IN ({tag_placeholders})
                    )
                """
                params.extend(tags)

            sql += " ORDER BY accessed_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(sql, params)
            return [self._row_to_record(row) for row in cursor.fetchall()]

    def update(self, record: MemoryRecord) -> bool:
        """Update an existing record."""
        record.updated_at = datetime.now()
        self.store(record)
        return True

    def clear(self) -> int:
        """Clear all records."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM memory_records")
            count = cursor.fetchone()[0]

            cursor.execute("DELETE FROM memory_records")
            cursor.execute("DELETE FROM memory_tags")
            conn.commit()

            logger.info("Memory store cleared", records_deleted=count)
            return count

    def cleanup_expired(self) -> int:
        """Remove expired records.

        Returns:
            Number of records deleted
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()

            # Find expired records
            cursor.execute(
                """
                SELECT id, metadata FROM memory_records
                """,
            )

            expired_ids = []
            for row in cursor.fetchall():
                metadata = json.loads(row["metadata"])
                expires_at = metadata.get("expires_at")
                if expires_at and expires_at < now:
                    expired_ids.append(row["id"])

            # Delete expired
            for record_id in expired_ids:
                cursor.execute(
                    "DELETE FROM memory_records WHERE id = ?",
                    (record_id,),
                )

            conn.commit()

            if expired_ids:
                logger.info("Expired records cleaned up", count=len(expired_ids))

            return len(expired_ids)

    def get_stats(self) -> dict[str, Any]:
        """Get storage statistics.

        Returns:
            Dict with storage stats
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Total count
            cursor.execute("SELECT COUNT(*) FROM memory_records")
            total = cursor.fetchone()[0]

            # Count by type
            cursor.execute(
                """
                SELECT type, COUNT(*) as count
                FROM memory_records
                GROUP BY type
                """
            )
            by_type = {row["type"]: row["count"] for row in cursor.fetchall()}

            # Database size
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

            return {
                "total_records": total,
                "by_type": by_type,
                "db_size_bytes": db_size,
                "db_path": str(self.db_path),
            }

    def _row_to_record(self, row: sqlite3.Row) -> MemoryRecord:
        """Convert a database row to MemoryRecord."""
        metadata_dict = json.loads(row["metadata"])
        embeddings = (
            json.loads(row["embeddings"]) if row["embeddings"] else None
        )

        metadata = MemoryMetadata(
            tags=metadata_dict.get("tags", []),
            confidence=metadata_dict.get("confidence", 1.0),
            source=metadata_dict.get("source", ""),
            related_ids=metadata_dict.get("related_ids", []),
            expires_at=datetime.fromisoformat(metadata_dict["expires_at"])
            if metadata_dict.get("expires_at")
            else None,
            custom=metadata_dict.get("custom", {}),
        )

        return MemoryRecord(
            id=row["id"],
            type=MemoryType(row["type"]),
            title=row["title"],
            content=row["content"],
            metadata=metadata,
            embeddings=embeddings,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            accessed_at=datetime.fromisoformat(row["accessed_at"]),
            access_count=row["access_count"],
        )


class InMemoryStore(MemoryStore):
    """Simple in-memory store for testing.

    Does not persist data between restarts.
    """

    def __init__(self) -> None:
        """Initialize in-memory store."""
        self._records: dict[str, MemoryRecord] = {}

    def store(self, record: MemoryRecord) -> str:
        """Store a record."""
        self._records[record.id] = record
        return record.id

    def retrieve(self, record_id: str) -> Optional[MemoryRecord]:
        """Retrieve a record."""
        record = self._records.get(record_id)
        if record:
            record.accessed_at = datetime.now()
            record.access_count += 1
        return record

    def delete(self, record_id: str) -> bool:
        """Delete a record."""
        if record_id in self._records:
            del self._records[record_id]
            return True
        return False

    def list_by_type(
        self,
        memory_type: MemoryType,
        limit: int = 100,
    ) -> list[MemoryRecord]:
        """List records by type."""
        records = [
            r for r in self._records.values() if r.type == memory_type
        ]
        records.sort(key=lambda r: r.created_at, reverse=True)
        return records[:limit]

    def search(
        self,
        query: str,
        memory_types: Optional[list[MemoryType]] = None,
        tags: Optional[list[str]] = None,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        """Search for records."""
        query_lower = query.lower()
        results = []

        for record in self._records.values():
            # Type filter
            if memory_types and record.type not in memory_types:
                continue

            # Tag filter
            if tags and not any(t in record.metadata.tags for t in tags):
                continue

            # Query match
            if (
                query_lower in record.title.lower()
                or query_lower in record.content.lower()
            ):
                results.append(record)

        results.sort(key=lambda r: r.accessed_at, reverse=True)
        return results[:limit]

    def update(self, record: MemoryRecord) -> bool:
        """Update a record."""
        if record.id in self._records:
            record.updated_at = datetime.now()
            self._records[record.id] = record
            return True
        return False

    def clear(self) -> int:
        """Clear all records."""
        count = len(self._records)
        self._records.clear()
        return count
