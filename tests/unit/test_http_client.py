"""Tests for HTTP client management module."""

import pytest

from agentsh.agent.http_client import (
    ClientStats,
    HTTPClientConfig,
    HTTPClientManager,
    get_http_client_manager,
    cleanup_http_clients,
)


class TestHTTPClientConfig:
    """Tests for HTTPClientConfig dataclass."""

    def test_default_config(self) -> None:
        """Should have sensible defaults."""
        config = HTTPClientConfig()

        assert config.timeout == 60.0
        assert config.connect_timeout == 10.0
        assert config.max_connections == 100
        assert config.max_keepalive_connections == 20
        assert config.http2 is True
        assert config.retries == 3

    def test_custom_config(self) -> None:
        """Should accept custom values."""
        config = HTTPClientConfig(
            timeout=30.0,
            max_connections=50,
            http2=False,
        )

        assert config.timeout == 30.0
        assert config.max_connections == 50
        assert config.http2 is False


class TestClientStats:
    """Tests for ClientStats dataclass."""

    def test_default_stats(self) -> None:
        """Should have zero defaults."""
        stats = ClientStats()

        assert stats.requests_made == 0
        assert stats.requests_failed == 0
        assert stats.bytes_sent == 0
        assert stats.bytes_received == 0

    def test_avg_response_time_empty(self) -> None:
        """Should return 0 for empty stats."""
        stats = ClientStats()
        assert stats.avg_response_time_ms == 0.0

    def test_avg_response_time(self) -> None:
        """Should calculate average correctly."""
        stats = ClientStats(
            requests_made=10,
            total_response_time_ms=1000.0,
        )
        assert stats.avg_response_time_ms == 100.0

    def test_success_rate_empty(self) -> None:
        """Should return 100% for empty stats."""
        stats = ClientStats()
        assert stats.success_rate == 100.0

    def test_success_rate(self) -> None:
        """Should calculate success rate correctly."""
        stats = ClientStats(
            requests_made=100,
            requests_failed=10,
        )
        assert stats.success_rate == 90.0

    def test_success_rate_all_failed(self) -> None:
        """Should return 0% when all failed."""
        stats = ClientStats(
            requests_made=10,
            requests_failed=10,
        )
        assert stats.success_rate == 0.0


class TestHTTPClientManager:
    """Tests for HTTPClientManager class."""

    @pytest.fixture
    async def manager(self) -> HTTPClientManager:
        """Create fresh manager for testing."""
        mgr = HTTPClientManager()
        yield mgr
        await mgr.close_all()

    @pytest.mark.asyncio
    async def test_get_client_creates_new(self, manager: HTTPClientManager) -> None:
        """Should create new client."""
        client = await manager.get_client("test")

        assert client is not None
        assert "test" in manager.client_names

    @pytest.mark.asyncio
    async def test_get_client_returns_same(self, manager: HTTPClientManager) -> None:
        """Should return same client on second call."""
        client1 = await manager.get_client("test")
        client2 = await manager.get_client("test")

        assert client1 is client2

    @pytest.mark.asyncio
    async def test_get_client_with_base_url(self, manager: HTTPClientManager) -> None:
        """Should set base URL."""
        client = await manager.get_client(
            "api",
            base_url="https://api.example.com",
        )

        assert client.base_url == "https://api.example.com"

    @pytest.mark.asyncio
    async def test_get_client_with_headers(self, manager: HTTPClientManager) -> None:
        """Should set default headers."""
        client = await manager.get_client(
            "api",
            headers={"Authorization": "Bearer token"},
        )

        assert "Authorization" in client.headers

    @pytest.mark.asyncio
    async def test_get_client_with_config(self, manager: HTTPClientManager) -> None:
        """Should use custom config."""
        config = HTTPClientConfig(timeout=30.0, read_timeout=30.0)
        client = await manager.get_client("test", config=config)

        # Verify config was stored
        assert "test" in manager._configs
        assert manager._configs["test"].timeout == 30.0

    @pytest.mark.asyncio
    async def test_close_client(self, manager: HTTPClientManager) -> None:
        """Should close specific client."""
        await manager.get_client("test")
        assert "test" in manager.client_names

        result = await manager.close_client("test")

        assert result is True
        assert "test" not in manager.client_names

    @pytest.mark.asyncio
    async def test_close_client_not_found(self, manager: HTTPClientManager) -> None:
        """Should return False for unknown client."""
        result = await manager.close_client("unknown")
        assert result is False

    @pytest.mark.asyncio
    async def test_close_all(self, manager: HTTPClientManager) -> None:
        """Should close all clients."""
        await manager.get_client("client1")
        await manager.get_client("client2")

        await manager.close_all()

        assert len(manager.client_names) == 0

    @pytest.mark.asyncio
    async def test_record_request_success(self, manager: HTTPClientManager) -> None:
        """Should record successful request."""
        manager.record_request(
            name="test",
            success=True,
            response_time_ms=100.0,
            bytes_sent=500,
            bytes_received=1000,
        )

        stats = manager.get_stats("test")["test"]
        assert stats.requests_made == 1
        assert stats.requests_failed == 0
        assert stats.bytes_sent == 500
        assert stats.bytes_received == 1000

    @pytest.mark.asyncio
    async def test_record_request_failure(self, manager: HTTPClientManager) -> None:
        """Should record failed request."""
        manager.record_request(
            name="test",
            success=False,
            response_time_ms=50.0,
        )

        stats = manager.get_stats("test")["test"]
        assert stats.requests_made == 1
        assert stats.requests_failed == 1

    @pytest.mark.asyncio
    async def test_get_stats_all(self, manager: HTTPClientManager) -> None:
        """Should return all stats."""
        manager.record_request("client1", True, 100.0)
        manager.record_request("client2", True, 200.0)

        all_stats = manager.get_stats()

        assert "client1" in all_stats
        assert "client2" in all_stats

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """Should work as async context manager."""
        async with HTTPClientManager() as manager:
            client = await manager.get_client("test")
            assert client is not None

        # After exit, clients should be closed
        assert len(manager.client_names) == 0

    @pytest.mark.asyncio
    async def test_multiple_clients(self, manager: HTTPClientManager) -> None:
        """Should manage multiple clients."""
        client1 = await manager.get_client("anthropic", base_url="https://api.anthropic.com")
        client2 = await manager.get_client("openai", base_url="https://api.openai.com")

        assert client1 is not client2
        assert len(manager.client_names) == 2


class TestGlobalManager:
    """Tests for global manager functions."""

    @pytest.mark.asyncio
    async def test_get_http_client_manager_singleton(self) -> None:
        """Should return same instance."""
        manager1 = get_http_client_manager()
        manager2 = get_http_client_manager()

        assert manager1 is manager2

        # Cleanup
        await cleanup_http_clients()

    @pytest.mark.asyncio
    async def test_cleanup_http_clients(self) -> None:
        """Should cleanup global manager."""
        manager = get_http_client_manager()
        await manager.get_client("test")

        await cleanup_http_clients()

        # Getting manager again should create new one
        new_manager = get_http_client_manager()
        assert "test" not in new_manager.client_names

        # Final cleanup
        await cleanup_http_clients()
