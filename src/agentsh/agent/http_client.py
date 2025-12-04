"""HTTP client management for LLM providers.

Provides shared HTTP client instances with connection pooling,
timeouts, and retry configuration for efficient API communication.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)


@dataclass
class HTTPClientConfig:
    """Configuration for HTTP clients.

    Attributes:
        timeout: Request timeout in seconds
        connect_timeout: Connection timeout in seconds
        read_timeout: Read timeout in seconds
        max_connections: Maximum connections per host
        max_keepalive_connections: Maximum keep-alive connections
        keepalive_expiry: Keep-alive connection expiry in seconds
        http2: Enable HTTP/2 support
        retries: Number of retries on connection errors
    """

    timeout: float = 60.0
    connect_timeout: float = 10.0
    read_timeout: float = 60.0
    max_connections: int = 100
    max_keepalive_connections: int = 20
    keepalive_expiry: float = 30.0
    http2: bool = True
    retries: int = 3


@dataclass
class ClientStats:
    """Statistics for HTTP client usage.

    Attributes:
        requests_made: Total requests made
        requests_failed: Failed requests
        bytes_sent: Total bytes sent
        bytes_received: Total bytes received
        avg_response_time_ms: Average response time
    """

    requests_made: int = 0
    requests_failed: int = 0
    bytes_sent: int = 0
    bytes_received: int = 0
    total_response_time_ms: float = 0.0

    @property
    def avg_response_time_ms(self) -> float:
        """Calculate average response time."""
        if self.requests_made == 0:
            return 0.0
        return self.total_response_time_ms / self.requests_made

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.requests_made == 0:
            return 100.0
        return ((self.requests_made - self.requests_failed) / self.requests_made) * 100


class HTTPClientManager:
    """Manages shared HTTP clients with connection pooling.

    Provides centralized HTTP client management for LLM providers,
    ensuring connection reuse and proper resource cleanup.

    Example:
        manager = HTTPClientManager()
        client = await manager.get_client("anthropic")
        response = await client.post(url, json=data)
        await manager.close_all()
    """

    def __init__(self, default_config: Optional[HTTPClientConfig] = None) -> None:
        """Initialize the client manager.

        Args:
            default_config: Default configuration for new clients
        """
        self._default_config = default_config or HTTPClientConfig()
        self._clients: dict[str, httpx.AsyncClient] = {}
        self._configs: dict[str, HTTPClientConfig] = {}
        self._stats: dict[str, ClientStats] = {}
        self._lock = asyncio.Lock()

    async def get_client(
        self,
        name: str,
        config: Optional[HTTPClientConfig] = None,
        base_url: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> httpx.AsyncClient:
        """Get or create a named HTTP client.

        Args:
            name: Client identifier (e.g., "anthropic", "openai")
            config: Optional custom configuration
            base_url: Optional base URL for all requests
            headers: Optional default headers

        Returns:
            Configured httpx.AsyncClient
        """
        async with self._lock:
            if name in self._clients:
                return self._clients[name]

            cfg = config or self._default_config
            self._configs[name] = cfg
            self._stats[name] = ClientStats()

            # Create connection limits
            limits = httpx.Limits(
                max_connections=cfg.max_connections,
                max_keepalive_connections=cfg.max_keepalive_connections,
                keepalive_expiry=cfg.keepalive_expiry,
            )

            # Create timeout configuration
            timeout = httpx.Timeout(
                timeout=cfg.timeout,
                connect=cfg.connect_timeout,
                read=cfg.read_timeout,
            )

            # Create transport with retries
            transport = httpx.AsyncHTTPTransport(
                retries=cfg.retries,
                http2=cfg.http2,
            )

            # Create client
            client = httpx.AsyncClient(
                base_url=base_url or "",
                headers=headers or {},
                limits=limits,
                timeout=timeout,
                transport=transport,
            )

            self._clients[name] = client
            logger.info(
                "Created HTTP client",
                name=name,
                max_connections=cfg.max_connections,
                http2=cfg.http2,
            )

            return client

    async def close_client(self, name: str) -> bool:
        """Close a specific client.

        Args:
            name: Client identifier

        Returns:
            True if client was closed
        """
        async with self._lock:
            if name not in self._clients:
                return False

            client = self._clients.pop(name)
            await client.aclose()
            logger.debug("Closed HTTP client", name=name)
            return True

    async def close_all(self) -> None:
        """Close all managed clients."""
        async with self._lock:
            for name, client in list(self._clients.items()):
                try:
                    await client.aclose()
                    logger.debug("Closed HTTP client", name=name)
                except Exception as e:
                    logger.warning("Error closing HTTP client", name=name, error=str(e))

            self._clients.clear()

    def get_stats(self, name: Optional[str] = None) -> dict[str, ClientStats]:
        """Get client statistics.

        Args:
            name: Optional specific client name

        Returns:
            Dict of client names to stats
        """
        if name:
            return {name: self._stats.get(name, ClientStats())}
        return dict(self._stats)

    def record_request(
        self,
        name: str,
        success: bool,
        response_time_ms: float,
        bytes_sent: int = 0,
        bytes_received: int = 0,
    ) -> None:
        """Record request statistics.

        Args:
            name: Client name
            success: Whether request succeeded
            response_time_ms: Response time in milliseconds
            bytes_sent: Bytes sent
            bytes_received: Bytes received
        """
        if name not in self._stats:
            self._stats[name] = ClientStats()

        stats = self._stats[name]
        stats.requests_made += 1
        if not success:
            stats.requests_failed += 1
        stats.total_response_time_ms += response_time_ms
        stats.bytes_sent += bytes_sent
        stats.bytes_received += bytes_received

    @property
    def client_names(self) -> list[str]:
        """Get list of managed client names."""
        return list(self._clients.keys())

    async def __aenter__(self) -> "HTTPClientManager":
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit - close all clients."""
        await self.close_all()


# Global client manager
_client_manager: Optional[HTTPClientManager] = None


def get_http_client_manager() -> HTTPClientManager:
    """Get the global HTTP client manager.

    Returns:
        HTTPClientManager singleton instance
    """
    global _client_manager
    if _client_manager is None:
        _client_manager = HTTPClientManager()
    return _client_manager


async def get_anthropic_client(
    api_key: str,
    config: Optional[HTTPClientConfig] = None,
) -> httpx.AsyncClient:
    """Get configured HTTP client for Anthropic API.

    Args:
        api_key: Anthropic API key
        config: Optional custom configuration

    Returns:
        Configured httpx.AsyncClient
    """
    manager = get_http_client_manager()
    return await manager.get_client(
        name="anthropic",
        config=config,
        base_url="https://api.anthropic.com",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )


async def get_openai_client(
    api_key: str,
    base_url: Optional[str] = None,
    config: Optional[HTTPClientConfig] = None,
) -> httpx.AsyncClient:
    """Get configured HTTP client for OpenAI API.

    Args:
        api_key: OpenAI API key
        base_url: Optional custom base URL (for Azure, etc.)
        config: Optional custom configuration

    Returns:
        Configured httpx.AsyncClient
    """
    manager = get_http_client_manager()
    return await manager.get_client(
        name="openai",
        config=config,
        base_url=base_url or "https://api.openai.com/v1",
        headers={
            "Authorization": f"Bearer {api_key}",
            "content-type": "application/json",
        },
    )


async def cleanup_http_clients() -> None:
    """Clean up all HTTP clients.

    Call this during application shutdown.
    """
    global _client_manager
    if _client_manager:
        await _client_manager.close_all()
        _client_manager = None
