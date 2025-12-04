"""Tests for resilient LLM client module."""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from agentsh.agent.cache import CacheConfig, LLMCache
from agentsh.agent.llm_client import (
    LLMClient,
    LLMResponse,
    Message,
    StopReason,
    ToolDefinition,
)
from agentsh.agent.resilient import (
    CircuitBreakerConfig,
    CircuitBreakerState,
    CircuitState,
    ResilienceConfig,
    ResilientLLMClient,
    RetryConfig,
    create_resilient_client,
)


class MockLLMClient(LLMClient):
    """Mock LLM client for testing."""

    def __init__(
        self,
        responses: list[LLMResponse] = None,
        errors: list[Exception] = None,
    ) -> None:
        """Initialize mock client."""
        self._responses = responses or []
        self._errors = errors or []
        self._call_count = 0
        self._provider = "mock"
        self._model = "mock-model"

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def model(self) -> str:
        return self._model

    async def invoke(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        self._call_count += 1

        if self._errors and self._call_count <= len(self._errors):
            error = self._errors[self._call_count - 1]
            if error:
                raise error

        if self._responses:
            idx = min(self._call_count - 1, len(self._responses) - 1)
            return self._responses[idx]

        return LLMResponse(
            content="Mock response",
            stop_reason=StopReason.END_TURN,
            input_tokens=10,
            output_tokens=20,
            model=self._model,
        )

    async def stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ):
        if self._errors and self._call_count < len(self._errors):
            self._call_count += 1
            raise self._errors[self._call_count - 1]

        self._call_count += 1
        yield "Mock "
        yield "streaming "
        yield "response"


class TestRetryConfig:
    """Tests for RetryConfig dataclass."""

    def test_default_config(self) -> None:
        """Should have sensible defaults."""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.jitter is True

    def test_custom_config(self) -> None:
        """Should accept custom values."""
        config = RetryConfig(max_retries=5, base_delay=2.0)
        assert config.max_retries == 5
        assert config.base_delay == 2.0


class TestCircuitBreakerConfig:
    """Tests for CircuitBreakerConfig dataclass."""

    def test_default_config(self) -> None:
        """Should have sensible defaults."""
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.success_threshold == 2
        assert config.timeout == 30.0

    def test_custom_config(self) -> None:
        """Should accept custom values."""
        config = CircuitBreakerConfig(failure_threshold=3, timeout=60.0)
        assert config.failure_threshold == 3
        assert config.timeout == 60.0


class TestCircuitState:
    """Tests for CircuitState enum."""

    def test_circuit_states(self) -> None:
        """Should have expected states."""
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"


class TestResilientLLMClient:
    """Tests for ResilientLLMClient class."""

    @pytest.fixture
    def mock_client(self) -> MockLLMClient:
        """Create mock LLM client."""
        return MockLLMClient()

    @pytest.fixture
    def resilient_client(self, mock_client: MockLLMClient) -> ResilientLLMClient:
        """Create resilient client with mock."""
        config = ResilienceConfig(
            retry=RetryConfig(max_retries=2, base_delay=0.01, jitter=False),
            circuit_breaker=CircuitBreakerConfig(failure_threshold=3),
            use_cache_fallback=False,
        )
        return ResilientLLMClient(mock_client, config)

    @pytest.mark.asyncio
    async def test_successful_invoke(
        self, resilient_client: ResilientLLMClient
    ) -> None:
        """Should pass through successful requests."""
        messages = [Message.user("Hello")]
        response = await resilient_client.invoke(messages)

        assert response.content == "Mock response"
        assert resilient_client.is_healthy is True
        assert resilient_client.circuit_state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_retry_on_error(self) -> None:
        """Should retry on transient errors."""
        # First call fails, second succeeds
        mock = MockLLMClient(
            errors=[ConnectionError("Failed"), None],
            responses=[
                LLMResponse(content="Success", stop_reason=StopReason.END_TURN)
            ],
        )
        config = ResilienceConfig(
            retry=RetryConfig(max_retries=2, base_delay=0.01, jitter=False),
        )
        client = ResilientLLMClient(mock, config)

        messages = [Message.user("Hello")]
        response = await client.invoke(messages)

        assert response.content == "Success"
        assert mock._call_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exhausted(self) -> None:
        """Should return fallback after max retries."""
        mock = MockLLMClient(
            errors=[
                ConnectionError("Failed 1"),
                ConnectionError("Failed 2"),
                ConnectionError("Failed 3"),
            ]
        )
        config = ResilienceConfig(
            retry=RetryConfig(max_retries=2, base_delay=0.01, jitter=False),
            use_cache_fallback=False,
            fallback_response="Service unavailable",
        )
        client = ResilientLLMClient(mock, config)

        messages = [Message.user("Hello")]
        response = await client.invoke(messages)

        assert response.content == "Service unavailable"
        assert response.stop_reason == StopReason.ERROR
        assert mock._call_count == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens(self) -> None:
        """Should open circuit after threshold failures."""
        mock = MockLLMClient(
            errors=[ConnectionError("Fail")] * 10  # Many failures
        )
        config = ResilienceConfig(
            retry=RetryConfig(max_retries=0, base_delay=0.01),
            circuit_breaker=CircuitBreakerConfig(failure_threshold=3),
            use_cache_fallback=False,
        )
        client = ResilientLLMClient(mock, config)

        messages = [Message.user("Hello")]

        # Make requests until circuit opens
        for i in range(3):
            await client.invoke(messages)

        assert client.circuit_state == CircuitState.OPEN
        assert client.is_healthy is False

    @pytest.mark.asyncio
    async def test_circuit_rejects_when_open(self) -> None:
        """Should reject requests when circuit is open."""
        mock = MockLLMClient()
        config = ResilienceConfig(
            retry=RetryConfig(max_retries=0),
            circuit_breaker=CircuitBreakerConfig(timeout=60.0),
            use_cache_fallback=False,
            fallback_response="Circuit open",
        )
        client = ResilientLLMClient(mock, config)

        # Force circuit open
        client._circuit.state = CircuitState.OPEN
        client._circuit.last_failure_time = datetime.now()

        messages = [Message.user("Hello")]
        response = await client.invoke(messages)

        assert response.content == "Circuit open"
        assert mock._call_count == 0  # Request was rejected

    @pytest.mark.asyncio
    async def test_circuit_half_open_after_timeout(self) -> None:
        """Should transition to half-open after timeout."""
        mock = MockLLMClient()
        config = ResilienceConfig(
            retry=RetryConfig(max_retries=0),
            circuit_breaker=CircuitBreakerConfig(timeout=0.01, success_threshold=1),
        )
        client = ResilientLLMClient(mock, config)

        # Force circuit open with old failure time
        client._circuit.state = CircuitState.OPEN
        client._circuit.last_failure_time = datetime.now() - timedelta(seconds=1)

        messages = [Message.user("Hello")]
        await client.invoke(messages)

        # Should have transitioned to half-open, then closed on success
        assert client.circuit_state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_cache_fallback(self) -> None:
        """Should use cached response when LLM fails."""
        mock = MockLLMClient(errors=[ConnectionError("Fail")] * 5)
        cache = LLMCache(CacheConfig(enabled=True, min_tokens_to_cache=0))

        config = ResilienceConfig(
            retry=RetryConfig(max_retries=1, base_delay=0.01),
            use_cache_fallback=True,
        )
        client = ResilientLLMClient(mock, config, cache)

        # Pre-populate cache
        messages = [Message.user("Hello")]
        cache_key = client._build_cache_key(messages, None, 0.0)
        cache.put(cache_key, "Cached response", tokens_out=100)

        response = await client.invoke(messages)

        assert response.content == "Cached response"

    @pytest.mark.asyncio
    async def test_successful_response_cached(self) -> None:
        """Should cache successful responses."""
        mock = MockLLMClient(
            responses=[
                LLMResponse(
                    content="Response to cache",
                    stop_reason=StopReason.END_TURN,
                    output_tokens=100,
                )
            ]
        )
        cache = LLMCache(CacheConfig(enabled=True, min_tokens_to_cache=0))
        config = ResilienceConfig()
        client = ResilientLLMClient(mock, config, cache)

        messages = [Message.user("Hello")]
        await client.invoke(messages)

        # Check cache was populated
        cache_key = client._build_cache_key(messages, None, 0.0)
        entry = cache.get(cache_key)
        assert entry is not None
        assert entry.response == "Response to cache"

    @pytest.mark.asyncio
    async def test_streaming_success(self, resilient_client: ResilientLLMClient) -> None:
        """Should stream successfully."""
        messages = [Message.user("Hello")]
        chunks = []

        async for chunk in resilient_client.stream(messages):
            chunks.append(chunk)

        assert "".join(chunks) == "Mock streaming response"

    @pytest.mark.asyncio
    async def test_streaming_fallback(self) -> None:
        """Should return fallback on stream failure."""
        mock = MockLLMClient(errors=[ConnectionError("Fail")])
        config = ResilienceConfig(
            use_cache_fallback=False,
            fallback_response="Stream failed",
        )
        client = ResilientLLMClient(mock, config)

        messages = [Message.user("Hello")]
        chunks = []

        async for chunk in client.stream(messages):
            chunks.append(chunk)

        assert "".join(chunks) == "Stream failed"

    def test_get_stats(self, resilient_client: ResilientLLMClient) -> None:
        """Should return stats."""
        stats = resilient_client.get_stats()

        assert stats["provider"] == "mock"
        assert stats["model"] == "mock-model"
        assert stats["is_healthy"] is True
        assert stats["circuit_state"] == "closed"

    def test_reset_circuit(self, resilient_client: ResilientLLMClient) -> None:
        """Should reset circuit breaker."""
        # Set circuit to open
        resilient_client._circuit.state = CircuitState.OPEN
        resilient_client._circuit.failure_count = 10

        resilient_client.reset_circuit()

        assert resilient_client.circuit_state == CircuitState.CLOSED
        assert resilient_client._circuit.failure_count == 0

    @pytest.mark.asyncio
    async def test_health_check_success(self) -> None:
        """Should report healthy on successful check."""
        mock = MockLLMClient()
        client = ResilientLLMClient(mock, ResilienceConfig())

        result = await client.health_check()

        assert result is True
        assert client.is_healthy is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self) -> None:
        """Should report unhealthy on failed check."""
        mock = MockLLMClient(errors=[ConnectionError("Fail")])
        client = ResilientLLMClient(mock, ResilienceConfig())

        result = await client.health_check()

        assert result is False
        assert client.is_healthy is False

    def test_provider_and_model(self, resilient_client: ResilientLLMClient) -> None:
        """Should delegate provider and model to underlying client."""
        assert resilient_client.provider == "mock"
        assert resilient_client.model == "mock-model"

    def test_count_tokens(self, resilient_client: ResilientLLMClient) -> None:
        """Should delegate token counting."""
        count = resilient_client.count_tokens("Hello world")
        assert count > 0


class TestCreateResilientClient:
    """Tests for create_resilient_client function."""

    def test_create_with_defaults(self) -> None:
        """Should create client with defaults."""
        mock = MockLLMClient()
        client = create_resilient_client(mock)

        assert isinstance(client, ResilientLLMClient)
        assert client._config.retry.max_retries == 3
        assert client._config.use_cache_fallback is True

    def test_create_with_custom_settings(self) -> None:
        """Should create client with custom settings."""
        mock = MockLLMClient()
        client = create_resilient_client(
            mock,
            max_retries=5,
            use_cache=False,
            fallback_message="Custom fallback",
        )

        assert client._config.retry.max_retries == 5
        assert client._config.use_cache_fallback is False
        assert client._config.fallback_response == "Custom fallback"
