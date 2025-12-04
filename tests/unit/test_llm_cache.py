"""Tests for LLM cache module."""

import pytest
import time
from datetime import datetime, timedelta
from pathlib import Path

from agentsh.agent.cache import (
    CacheConfig,
    CacheEntry,
    CacheKeyBuilder,
    LLMCache,
    SQLiteLLMCache,
    get_llm_cache,
    set_llm_cache,
)


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    def test_create_entry(self) -> None:
        """Should create cache entry."""
        entry = CacheEntry(
            key="test_key",
            response="test response",
            tokens_in=10,
            tokens_out=20,
        )
        assert entry.key == "test_key"
        assert entry.response == "test response"
        assert entry.tokens_in == 10
        assert entry.tokens_out == 20

    def test_entry_not_expired(self) -> None:
        """Should not be expired when fresh."""
        entry = CacheEntry(
            key="test",
            response="response",
            ttl_seconds=3600,
        )
        assert entry.is_expired() is False

    def test_entry_expired(self) -> None:
        """Should be expired after TTL."""
        entry = CacheEntry(
            key="test",
            response="response",
            ttl_seconds=1,
            created_at=datetime.now() - timedelta(seconds=2),
        )
        assert entry.is_expired() is True

    def test_entry_to_dict(self) -> None:
        """Should convert to dictionary."""
        entry = CacheEntry(
            key="test",
            response="response",
            provider="anthropic",
        )
        data = entry.to_dict()
        assert data["key"] == "test"
        assert data["response"] == "response"
        assert data["provider"] == "anthropic"

    def test_entry_from_dict(self) -> None:
        """Should create from dictionary."""
        data = {
            "key": "test",
            "response": "response",
            "tokens_in": 10,
            "tokens_out": 20,
            "created_at": datetime.now().isoformat(),
            "accessed_at": datetime.now().isoformat(),
        }
        entry = CacheEntry.from_dict(data)
        assert entry.key == "test"
        assert entry.tokens_in == 10


class TestCacheConfig:
    """Tests for CacheConfig dataclass."""

    def test_default_config(self) -> None:
        """Should have sensible defaults."""
        config = CacheConfig()
        assert config.enabled is True
        assert config.max_entries == 1000
        assert config.default_ttl == 3600

    def test_custom_config(self) -> None:
        """Should accept custom values."""
        config = CacheConfig(
            enabled=False,
            max_entries=500,
            default_ttl=1800,
        )
        assert config.enabled is False
        assert config.max_entries == 500


class TestCacheKeyBuilder:
    """Tests for CacheKeyBuilder class."""

    def test_build_key_deterministic(self) -> None:
        """Should produce same key for same input."""
        messages = [{"role": "user", "content": "Hello"}]

        key1 = CacheKeyBuilder.build(messages, model="claude")
        key2 = CacheKeyBuilder.build(messages, model="claude")

        assert key1 == key2

    def test_build_key_different_messages(self) -> None:
        """Should produce different keys for different messages."""
        key1 = CacheKeyBuilder.build([{"role": "user", "content": "Hello"}])
        key2 = CacheKeyBuilder.build([{"role": "user", "content": "Hi"}])

        assert key1 != key2

    def test_build_key_different_models(self) -> None:
        """Should produce different keys for different models."""
        messages = [{"role": "user", "content": "Hello"}]

        key1 = CacheKeyBuilder.build(messages, model="claude")
        key2 = CacheKeyBuilder.build(messages, model="gpt-4")

        assert key1 != key2

    def test_build_key_with_tools(self) -> None:
        """Should include tools in key."""
        messages = [{"role": "user", "content": "Hello"}]
        tools = [{"name": "search", "description": "Search"}]

        key_with_tools = CacheKeyBuilder.build(messages, tools=tools)
        key_without_tools = CacheKeyBuilder.build(messages)

        assert key_with_tools != key_without_tools


class TestLLMCache:
    """Tests for LLMCache class."""

    @pytest.fixture
    def cache(self) -> LLMCache:
        """Create cache instance."""
        config = CacheConfig(max_entries=10, default_ttl=60)
        return LLMCache(config)

    @pytest.fixture
    def disabled_cache(self) -> LLMCache:
        """Create disabled cache instance."""
        config = CacheConfig(enabled=False)
        return LLMCache(config)

    def test_cache_put_get(self, cache: LLMCache) -> None:
        """Should store and retrieve entries."""
        cache.put("key1", "response1", tokens_out=100)
        entry = cache.get("key1")

        assert entry is not None
        assert entry.response == "response1"

    def test_cache_miss(self, cache: LLMCache) -> None:
        """Should return None for missing keys."""
        entry = cache.get("nonexistent")
        assert entry is None

    def test_cache_expiration(self, cache: LLMCache) -> None:
        """Should expire entries."""
        cache.put("key1", "response1", tokens_out=100, ttl=1)
        time.sleep(1.5)

        entry = cache.get("key1")
        assert entry is None

    def test_cache_disabled(self, disabled_cache: LLMCache) -> None:
        """Should not cache when disabled."""
        disabled_cache.put("key1", "response1", tokens_out=100)
        entry = disabled_cache.get("key1")
        assert entry is None

    def test_cache_invalidate(self, cache: LLMCache) -> None:
        """Should invalidate entries."""
        cache.put("key1", "response1", tokens_out=100)
        result = cache.invalidate("key1")

        assert result is True
        assert cache.get("key1") is None

    def test_cache_invalidate_nonexistent(self, cache: LLMCache) -> None:
        """Should return False for nonexistent keys."""
        result = cache.invalidate("nonexistent")
        assert result is False

    def test_cache_clear(self, cache: LLMCache) -> None:
        """Should clear all entries."""
        cache.put("key1", "response1", tokens_out=100)
        cache.put("key2", "response2", tokens_out=100)
        cache.clear()

        assert cache.size == 0

    def test_cache_eviction(self, cache: LLMCache) -> None:
        """Should evict oldest entries when full."""
        # Fill cache
        for i in range(15):  # More than max_entries (10)
            cache.put(f"key{i}", f"response{i}", tokens_out=100)
            time.sleep(0.01)  # Ensure different timestamps

        assert cache.size <= 10

    def test_cache_hit_rate(self, cache: LLMCache) -> None:
        """Should track hit rate."""
        cache.put("key1", "response1", tokens_out=100)

        cache.get("key1")  # Hit
        cache.get("key1")  # Hit
        cache.get("key2")  # Miss

        assert cache.hit_rate > 0.5

    def test_cache_stats(self, cache: LLMCache) -> None:
        """Should return stats."""
        cache.put("key1", "response1", tokens_out=100)
        cache.get("key1")

        stats = cache.get_stats()
        assert stats["enabled"] is True
        assert stats["size"] == 1
        assert stats["hits"] == 1

    def test_cache_cleanup_expired(self, cache: LLMCache) -> None:
        """Should cleanup expired entries."""
        cache.put("key1", "response1", tokens_out=100, ttl=1)
        cache.put("key2", "response2", tokens_out=100, ttl=3600)

        time.sleep(1.5)
        removed = cache.cleanup_expired()

        assert removed == 1
        assert cache.size == 1

    def test_cache_min_tokens(self) -> None:
        """Should not cache small responses."""
        config = CacheConfig(min_tokens_to_cache=50)
        cache = LLMCache(config)

        cache.put("key1", "small", tokens_out=10)
        assert cache.get("key1") is None

    def test_cache_exclude_tools(self) -> None:
        """Should not cache responses with tool calls."""
        config = CacheConfig(exclude_tools=True)
        cache = LLMCache(config)

        cache.put(
            "key1",
            "response",
            tokens_out=100,
            tool_calls=[{"name": "search"}],
        )
        assert cache.get("key1") is None


class TestSQLiteLLMCache:
    """Tests for SQLiteLLMCache class."""

    @pytest.fixture
    def cache(self, tmp_path: Path) -> SQLiteLLMCache:
        """Create SQLite cache instance."""
        config = CacheConfig(
            max_entries=10,
            default_ttl=60,
            cache_path=tmp_path / "cache.db",
        )
        return SQLiteLLMCache(config)

    def test_cache_persistence(self, tmp_path: Path) -> None:
        """Should persist entries across instances."""
        db_path = tmp_path / "cache.db"
        config = CacheConfig(cache_path=db_path)

        # First instance
        cache1 = SQLiteLLMCache(config)
        cache1.put("key1", "response1", tokens_out=100)

        # Second instance
        cache2 = SQLiteLLMCache(config)
        entry = cache2.get("key1")

        assert entry is not None
        assert entry.response == "response1"

    def test_cache_invalidate_persists(self, cache: SQLiteLLMCache) -> None:
        """Should persist invalidation."""
        cache.put("key1", "response1", tokens_out=100)
        cache.invalidate("key1")

        # Reload from DB
        cache._load_cache()
        assert cache.get("key1") is None

    def test_cache_clear_persists(self, cache: SQLiteLLMCache) -> None:
        """Should persist clear operation."""
        cache.put("key1", "response1", tokens_out=100)
        cache.clear()

        # Reload from DB
        cache._load_cache()
        assert cache.size == 0


class TestGlobalCache:
    """Tests for global cache functions."""

    def teardown_method(self) -> None:
        """Reset global cache."""
        set_llm_cache(None)

    def test_get_global_cache(self) -> None:
        """Should create and return global cache."""
        cache = get_llm_cache()
        assert isinstance(cache, LLMCache)

        # Should return same instance
        assert get_llm_cache() is cache

    def test_set_global_cache(self) -> None:
        """Should set custom global cache."""
        custom = LLMCache(CacheConfig(max_entries=5))
        set_llm_cache(custom)

        assert get_llm_cache() is custom
