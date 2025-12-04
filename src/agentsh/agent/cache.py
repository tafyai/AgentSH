"""LLM response caching for AgentSH.

Provides caching of LLM responses to reduce latency and costs for
repeated or similar queries.
"""

import hashlib
import json
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CacheEntry:
    """A cached LLM response entry.

    Attributes:
        key: Cache key (hash of request)
        response: Cached response content
        tool_calls: Any tool calls in the response
        tokens_in: Input tokens used
        tokens_out: Output tokens generated
        provider: LLM provider
        model: Model used
        created_at: When the entry was created
        accessed_at: When the entry was last accessed
        access_count: Number of times accessed
        ttl_seconds: Time-to-live in seconds
    """

    key: str
    response: str
    tool_calls: Optional[list[dict[str, Any]]] = None
    tokens_in: int = 0
    tokens_out: int = 0
    provider: str = ""
    model: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    accessed_at: datetime = field(default_factory=datetime.now)
    access_count: int = 1
    ttl_seconds: int = 3600  # 1 hour default

    def is_expired(self) -> bool:
        """Check if the entry has expired."""
        age = (datetime.now() - self.created_at).total_seconds()
        return age > self.ttl_seconds

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "key": self.key,
            "response": self.response,
            "tool_calls": self.tool_calls,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "provider": self.provider,
            "model": self.model,
            "created_at": self.created_at.isoformat(),
            "accessed_at": self.accessed_at.isoformat(),
            "access_count": self.access_count,
            "ttl_seconds": self.ttl_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CacheEntry":
        """Create from dictionary."""
        return cls(
            key=data["key"],
            response=data["response"],
            tool_calls=data.get("tool_calls"),
            tokens_in=data.get("tokens_in", 0),
            tokens_out=data.get("tokens_out", 0),
            provider=data.get("provider", ""),
            model=data.get("model", ""),
            created_at=datetime.fromisoformat(data["created_at"]),
            accessed_at=datetime.fromisoformat(data["accessed_at"]),
            access_count=data.get("access_count", 1),
            ttl_seconds=data.get("ttl_seconds", 3600),
        )


@dataclass
class CacheConfig:
    """Configuration for LLM cache.

    Attributes:
        enabled: Whether caching is enabled
        max_entries: Maximum number of entries to keep
        default_ttl: Default TTL in seconds
        cache_path: Path to cache database (None for in-memory)
        exclude_tools: Don't cache responses with tool calls
        min_tokens_to_cache: Minimum tokens to be worth caching
    """

    enabled: bool = True
    max_entries: int = 1000
    default_ttl: int = 3600  # 1 hour
    cache_path: Optional[Path] = None
    exclude_tools: bool = False
    min_tokens_to_cache: int = 10


class CacheKeyBuilder:
    """Builds cache keys from LLM requests."""

    @staticmethod
    def build(
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        model: str = "",
        temperature: float = 0.0,
    ) -> str:
        """Build a cache key from request parameters.

        Args:
            messages: Conversation messages
            tools: Available tools
            model: Model name
            temperature: Temperature setting

        Returns:
            Hash string for cache key
        """
        # Create a canonical representation
        key_data = {
            "messages": messages,
            "tools": tools or [],
            "model": model,
            "temperature": temperature,
        }

        # Serialize and hash
        serialized = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:32]


class LLMCache:
    """In-memory LLM response cache.

    Thread-safe cache for LLM responses with TTL support.

    Example:
        cache = LLMCache(config)

        # Try to get cached response
        key = CacheKeyBuilder.build(messages, tools, model)
        entry = cache.get(key)

        if entry:
            return entry.response

        # Call LLM and cache result
        response = llm.invoke(messages)
        cache.put(key, response, tokens_in, tokens_out)
    """

    def __init__(self, config: Optional[CacheConfig] = None) -> None:
        """Initialize cache.

        Args:
            config: Cache configuration
        """
        self.config = config or CacheConfig()
        self._cache: dict[str, CacheEntry] = {}
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

        logger.debug(
            "LLMCache initialized",
            enabled=self.config.enabled,
            max_entries=self.config.max_entries,
        )

    @property
    def enabled(self) -> bool:
        """Check if caching is enabled."""
        return self.config.enabled

    @property
    def size(self) -> int:
        """Get current cache size."""
        return len(self._cache)

    @property
    def hit_rate(self) -> float:
        """Get cache hit rate."""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def get(self, key: str) -> Optional[CacheEntry]:
        """Get a cached entry.

        Args:
            key: Cache key

        Returns:
            CacheEntry if found and valid, None otherwise
        """
        if not self.config.enabled:
            return None

        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired():
                del self._cache[key]
                self._misses += 1
                return None

            # Update access info
            entry.accessed_at = datetime.now()
            entry.access_count += 1
            self._hits += 1

            logger.debug("Cache hit", key=key[:8])
            return entry

    def put(
        self,
        key: str,
        response: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        tool_calls: Optional[list[dict[str, Any]]] = None,
        provider: str = "",
        model: str = "",
        ttl: Optional[int] = None,
    ) -> None:
        """Store a response in cache.

        Args:
            key: Cache key
            response: Response content
            tokens_in: Input tokens
            tokens_out: Output tokens
            tool_calls: Any tool calls
            provider: LLM provider
            model: Model used
            ttl: TTL in seconds (uses default if None)
        """
        if not self.config.enabled:
            return

        # Check if we should cache
        if tokens_out < self.config.min_tokens_to_cache:
            return

        if self.config.exclude_tools and tool_calls:
            return

        entry = CacheEntry(
            key=key,
            response=response,
            tool_calls=tool_calls,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            provider=provider,
            model=model,
            ttl_seconds=ttl or self.config.default_ttl,
        )

        with self._lock:
            # Evict if at capacity
            if len(self._cache) >= self.config.max_entries:
                self._evict()

            self._cache[key] = entry
            logger.debug("Cache put", key=key[:8], tokens=tokens_out)

    def invalidate(self, key: str) -> bool:
        """Invalidate a cache entry.

        Args:
            key: Cache key to invalidate

        Returns:
            True if entry was found and removed
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def cleanup_expired(self) -> int:
        """Remove expired entries.

        Returns:
            Number of entries removed
        """
        with self._lock:
            expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        return {
            "enabled": self.config.enabled,
            "size": self.size,
            "max_entries": self.config.max_entries,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self.hit_rate,
        }

    def _evict(self) -> None:
        """Evict entries to make room.

        Uses LRU (Least Recently Used) eviction.
        """
        if not self._cache:
            return

        # Find least recently accessed entry
        oldest_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].accessed_at,
        )
        del self._cache[oldest_key]


class SQLiteLLMCache(LLMCache):
    """Persistent LLM cache using SQLite.

    Extends LLMCache with SQLite persistence for cross-session caching.
    """

    def __init__(self, config: Optional[CacheConfig] = None) -> None:
        """Initialize SQLite cache.

        Args:
            config: Cache configuration (must include cache_path)
        """
        super().__init__(config)

        if self.config.cache_path:
            self._db_path = self.config.cache_path
        else:
            # Default to user cache directory
            cache_dir = Path.home() / ".agentsh" / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            self._db_path = cache_dir / "llm_cache.db"

        self._init_db()
        self._load_cache()

    def _init_db(self) -> None:
        """Initialize SQLite database schema."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key TEXT PRIMARY KEY,
                    response TEXT NOT NULL,
                    tool_calls TEXT,
                    tokens_in INTEGER DEFAULT 0,
                    tokens_out INTEGER DEFAULT 0,
                    provider TEXT DEFAULT '',
                    model TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    accessed_at TEXT NOT NULL,
                    access_count INTEGER DEFAULT 1,
                    ttl_seconds INTEGER DEFAULT 3600
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_accessed_at ON cache_entries(accessed_at)"
            )
            conn.commit()

    def _load_cache(self) -> None:
        """Load cache entries from database."""
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM cache_entries")

            for row in cursor:
                entry = CacheEntry(
                    key=row["key"],
                    response=row["response"],
                    tool_calls=json.loads(row["tool_calls"]) if row["tool_calls"] else None,
                    tokens_in=row["tokens_in"],
                    tokens_out=row["tokens_out"],
                    provider=row["provider"],
                    model=row["model"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    accessed_at=datetime.fromisoformat(row["accessed_at"]),
                    access_count=row["access_count"],
                    ttl_seconds=row["ttl_seconds"],
                )

                if not entry.is_expired():
                    self._cache[entry.key] = entry

        # Cleanup expired entries from DB
        self._cleanup_db()

    def put(
        self,
        key: str,
        response: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        tool_calls: Optional[list[dict[str, Any]]] = None,
        provider: str = "",
        model: str = "",
        ttl: Optional[int] = None,
    ) -> None:
        """Store a response in cache and persist to DB."""
        super().put(key, response, tokens_in, tokens_out, tool_calls, provider, model, ttl)

        if not self.config.enabled:
            return

        # Persist to database
        entry = self._cache.get(key)
        if entry:
            self._persist_entry(entry)

    def _persist_entry(self, entry: CacheEntry) -> None:
        """Persist a cache entry to database."""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO cache_entries
                (key, response, tool_calls, tokens_in, tokens_out,
                 provider, model, created_at, accessed_at, access_count, ttl_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.key,
                    entry.response,
                    json.dumps(entry.tool_calls) if entry.tool_calls else None,
                    entry.tokens_in,
                    entry.tokens_out,
                    entry.provider,
                    entry.model,
                    entry.created_at.isoformat(),
                    entry.accessed_at.isoformat(),
                    entry.access_count,
                    entry.ttl_seconds,
                ),
            )
            conn.commit()

    def invalidate(self, key: str) -> bool:
        """Invalidate a cache entry and remove from DB."""
        result = super().invalidate(key)
        if result:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                conn.commit()
        return result

    def clear(self) -> None:
        """Clear all cache entries and database."""
        super().clear()
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM cache_entries")
            conn.commit()

    def _cleanup_db(self) -> None:
        """Remove expired entries from database."""
        with sqlite3.connect(self._db_path) as conn:
            # Delete entries older than their TTL
            conn.execute(
                """
                DELETE FROM cache_entries
                WHERE datetime(created_at, '+' || ttl_seconds || ' seconds') < datetime('now')
                """
            )
            conn.commit()


# Global cache instance
_llm_cache: Optional[LLMCache] = None


def get_llm_cache() -> LLMCache:
    """Get the global LLM cache.

    Returns:
        Global LLMCache instance
    """
    global _llm_cache
    if _llm_cache is None:
        _llm_cache = LLMCache()
    return _llm_cache


def set_llm_cache(cache: Optional[LLMCache]) -> None:
    """Set the global LLM cache.

    Args:
        cache: LLMCache instance to use
    """
    global _llm_cache
    _llm_cache = cache
