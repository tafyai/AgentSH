"""Resilient LLM Client - Graceful degradation and fault tolerance.

Provides a wrapper around LLM clients that adds:
- Retry with exponential backoff
- Cached response fallback
- Circuit breaker pattern
- Health monitoring
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, AsyncIterator, Callable, Optional

from agentsh.agent.cache import CacheKeyBuilder, LLMCache, get_llm_cache
from agentsh.agent.llm_client import (
    LLMClient,
    LLMResponse,
    Message,
    StopReason,
    ToolDefinition,
)
from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class RetryConfig:
    """Configuration for retry behavior.

    Attributes:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        jitter: Whether to add random jitter
        retryable_exceptions: Exception types that should trigger retry
    """

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple[type[Exception], ...] = field(
        default_factory=lambda: (
            ConnectionError,
            TimeoutError,
            asyncio.TimeoutError,
        )
    )


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker.

    Attributes:
        failure_threshold: Failures before opening circuit
        success_threshold: Successes before closing circuit
        timeout: How long circuit stays open
        half_open_requests: Requests to allow in half-open state
    """

    failure_threshold: int = 5
    success_threshold: int = 2
    timeout: float = 30.0
    half_open_requests: int = 1


@dataclass
class CircuitBreakerState:
    """Runtime state for circuit breaker."""

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    half_open_requests_made: int = 0


@dataclass
class ResilienceConfig:
    """Configuration for resilient LLM client.

    Attributes:
        retry: Retry configuration
        circuit_breaker: Circuit breaker configuration
        use_cache_fallback: Use cached responses when LLM unavailable
        fallback_response: Response when all else fails
        health_check_interval: Seconds between health checks
    """

    retry: RetryConfig = field(default_factory=RetryConfig)
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    use_cache_fallback: bool = True
    fallback_response: str = (
        "I'm temporarily unable to process your request. "
        "Please try again in a moment."
    )
    health_check_interval: float = 30.0


class ResilientLLMClient(LLMClient):
    """LLM client wrapper with resilience features.

    Wraps an existing LLM client and adds:
    - Automatic retry with exponential backoff
    - Circuit breaker to prevent cascade failures
    - Cache-based fallback when service is unavailable
    - Health monitoring and reporting

    Example:
        base_client = AnthropicClient(api_key="...")
        client = ResilientLLMClient(base_client)

        # Will automatically retry on failures
        response = await client.invoke(messages)

        # Check health status
        if client.is_healthy:
            print("LLM service is available")
    """

    def __init__(
        self,
        client: LLMClient,
        config: Optional[ResilienceConfig] = None,
        cache: Optional[LLMCache] = None,
    ) -> None:
        """Initialize resilient client.

        Args:
            client: Underlying LLM client
            config: Resilience configuration
            cache: Cache for fallback responses
        """
        self._client = client
        self._config = config or ResilienceConfig()
        self._cache = cache or get_llm_cache()
        self._circuit = CircuitBreakerState()
        self._last_health_check: Optional[datetime] = None
        self._is_healthy = True

        logger.info(
            "ResilientLLMClient initialized",
            provider=client.provider,
            model=client.model,
            max_retries=self._config.retry.max_retries,
        )

    @property
    def provider(self) -> str:
        """Get the provider name."""
        return self._client.provider

    @property
    def model(self) -> str:
        """Get the model name."""
        return self._client.model

    @property
    def is_healthy(self) -> bool:
        """Check if the LLM service is considered healthy."""
        return self._is_healthy and self._circuit.state != CircuitState.OPEN

    @property
    def circuit_state(self) -> CircuitState:
        """Get current circuit breaker state."""
        return self._circuit.state

    async def invoke(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Invoke LLM with resilience features.

        Args:
            messages: Conversation history
            tools: Available tools
            temperature: Sampling temperature
            max_tokens: Maximum tokens

        Returns:
            LLMResponse from LLM, cache, or fallback
        """
        # Check circuit breaker
        if not self._check_circuit():
            return await self._handle_circuit_open(messages, tools, temperature)

        # Build cache key for potential fallback
        cache_key = self._build_cache_key(messages, tools, temperature)

        # Try with retries
        last_error: Optional[Exception] = None
        for attempt in range(self._config.retry.max_retries + 1):
            try:
                response = await self._invoke_with_timeout(
                    messages, tools, temperature, max_tokens
                )
                self._record_success()

                # Cache successful response
                if self._cache and self._cache.enabled:
                    self._cache.put(
                        cache_key,
                        response.content,
                        tokens_in=response.input_tokens,
                        tokens_out=response.output_tokens,
                        tool_calls=[
                            {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                            for tc in response.tool_calls
                        ]
                        if response.tool_calls
                        else None,
                        provider=self.provider,
                        model=self.model,
                    )

                return response

            except Exception as e:
                last_error = e
                self._record_failure()

                if not self._should_retry(e, attempt):
                    break

                delay = self._calculate_delay(attempt)
                logger.warning(
                    "LLM request failed, retrying",
                    attempt=attempt + 1,
                    delay=delay,
                    error=str(e),
                )
                await asyncio.sleep(delay)

        # All retries exhausted - try fallback
        logger.error(
            "All LLM retries exhausted",
            error=str(last_error),
            cache_fallback=self._config.use_cache_fallback,
        )

        return await self._handle_failure(cache_key, last_error)

    async def stream(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> AsyncIterator[str]:
        """Stream tokens with resilience.

        Note: Streaming has limited fallback support - will yield
        fallback message if service unavailable.

        Args:
            messages: Conversation history
            tools: Available tools
            temperature: Sampling temperature
            max_tokens: Maximum tokens

        Yields:
            Text chunks
        """
        if not self._check_circuit():
            yield self._config.fallback_response
            return

        try:
            async for chunk in self._client.stream(
                messages, tools, temperature, max_tokens
            ):
                yield chunk
            self._record_success()

        except Exception as e:
            self._record_failure()
            logger.error("Streaming failed", error=str(e))

            # Try cache fallback for streaming
            cache_key = self._build_cache_key(messages, tools, temperature)
            if self._config.use_cache_fallback and self._cache:
                entry = self._cache.get(cache_key)
                if entry:
                    yield entry.response
                    return

            yield self._config.fallback_response

    async def health_check(self) -> bool:
        """Perform a health check on the LLM service.

        Returns:
            True if service is healthy
        """
        try:
            # Simple ping with minimal tokens
            messages = [Message.user("ping")]
            response = await self._client.invoke(
                messages, tools=None, temperature=0.0, max_tokens=10
            )
            self._is_healthy = bool(response.content)
            self._last_health_check = datetime.now()
            return self._is_healthy

        except Exception as e:
            logger.warning("Health check failed", error=str(e))
            self._is_healthy = False
            self._last_health_check = datetime.now()
            return False

    def reset_circuit(self) -> None:
        """Reset circuit breaker to closed state."""
        self._circuit = CircuitBreakerState()
        logger.info("Circuit breaker reset")

    def get_stats(self) -> dict[str, Any]:
        """Get resilience statistics.

        Returns:
            Dictionary with stats
        """
        cache_stats = self._cache.get_stats() if self._cache else {}

        return {
            "provider": self.provider,
            "model": self.model,
            "is_healthy": self.is_healthy,
            "circuit_state": self._circuit.state.value,
            "failure_count": self._circuit.failure_count,
            "success_count": self._circuit.success_count,
            "last_failure": (
                self._circuit.last_failure_time.isoformat()
                if self._circuit.last_failure_time
                else None
            ),
            "last_health_check": (
                self._last_health_check.isoformat() if self._last_health_check else None
            ),
            "cache": cache_stats,
        }

    def _check_circuit(self) -> bool:
        """Check if circuit allows request.

        Returns:
            True if request should proceed
        """
        if self._circuit.state == CircuitState.CLOSED:
            return True

        if self._circuit.state == CircuitState.OPEN:
            # Check if timeout has elapsed
            if self._circuit.last_failure_time:
                elapsed = (
                    datetime.now() - self._circuit.last_failure_time
                ).total_seconds()
                if elapsed >= self._config.circuit_breaker.timeout:
                    self._circuit.state = CircuitState.HALF_OPEN
                    self._circuit.half_open_requests_made = 0
                    logger.info("Circuit breaker entering half-open state")
                    return True
            return False

        if self._circuit.state == CircuitState.HALF_OPEN:
            # Allow limited requests in half-open
            if (
                self._circuit.half_open_requests_made
                < self._config.circuit_breaker.half_open_requests
            ):
                self._circuit.half_open_requests_made += 1
                return True
            return False

        return True

    def _record_success(self) -> None:
        """Record a successful request."""
        if self._circuit.state == CircuitState.HALF_OPEN:
            self._circuit.success_count += 1
            if (
                self._circuit.success_count
                >= self._config.circuit_breaker.success_threshold
            ):
                self._circuit.state = CircuitState.CLOSED
                self._circuit.failure_count = 0
                self._circuit.success_count = 0
                logger.info("Circuit breaker closed after recovery")
        else:
            self._circuit.failure_count = 0
            self._circuit.success_count += 1

        self._is_healthy = True

    def _record_failure(self) -> None:
        """Record a failed request."""
        self._circuit.failure_count += 1
        self._circuit.last_failure_time = datetime.now()

        if self._circuit.state == CircuitState.HALF_OPEN:
            # Failure in half-open reopens circuit
            self._circuit.state = CircuitState.OPEN
            logger.warning("Circuit breaker reopened after failure in half-open")

        elif self._circuit.state == CircuitState.CLOSED:
            if (
                self._circuit.failure_count
                >= self._config.circuit_breaker.failure_threshold
            ):
                self._circuit.state = CircuitState.OPEN
                logger.warning(
                    "Circuit breaker opened",
                    failures=self._circuit.failure_count,
                )

    def _should_retry(self, error: Exception, attempt: int) -> bool:
        """Check if error should trigger retry.

        Args:
            error: The exception that occurred
            attempt: Current attempt number (0-indexed)

        Returns:
            True if should retry
        """
        if attempt >= self._config.retry.max_retries:
            return False

        # Check if error type is retryable
        for exc_type in self._config.retry.retryable_exceptions:
            if isinstance(error, exc_type):
                return True

        # Also retry on common API errors
        error_str = str(error).lower()
        retryable_messages = [
            "rate limit",
            "timeout",
            "connection",
            "temporary",
            "503",
            "502",
            "504",
            "overloaded",
        ]
        return any(msg in error_str for msg in retryable_messages)

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for retry.

        Args:
            attempt: Current attempt number

        Returns:
            Delay in seconds
        """
        delay = self._config.retry.base_delay * (
            self._config.retry.exponential_base**attempt
        )
        delay = min(delay, self._config.retry.max_delay)

        if self._config.retry.jitter:
            import random

            delay *= 0.5 + random.random()

        return delay

    async def _invoke_with_timeout(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]],
        temperature: float,
        max_tokens: int,
    ) -> LLMResponse:
        """Invoke with timeout wrapper.

        Args:
            messages: Messages to send
            tools: Available tools
            temperature: Temperature setting
            max_tokens: Max tokens

        Returns:
            LLM response
        """
        return await self._client.invoke(messages, tools, temperature, max_tokens)

    def _build_cache_key(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]],
        temperature: float,
    ) -> str:
        """Build cache key for request.

        Args:
            messages: Request messages
            tools: Available tools
            temperature: Temperature

        Returns:
            Cache key string
        """
        msg_dicts = [m.to_dict() for m in messages]
        tool_dicts = [t.to_openai_format() for t in tools] if tools else None
        return CacheKeyBuilder.build(msg_dicts, tool_dicts, self.model, temperature)

    async def _handle_circuit_open(
        self,
        messages: list[Message],
        tools: Optional[list[ToolDefinition]],
        temperature: float,
    ) -> LLMResponse:
        """Handle request when circuit is open.

        Args:
            messages: Request messages
            tools: Available tools
            temperature: Temperature

        Returns:
            Fallback response
        """
        logger.warning("Circuit open, using fallback")

        # Try cache first
        if self._config.use_cache_fallback and self._cache:
            cache_key = self._build_cache_key(messages, tools, temperature)
            entry = self._cache.get(cache_key)
            if entry:
                logger.info("Using cached response during circuit open")
                return LLMResponse(
                    content=entry.response,
                    stop_reason=StopReason.END_TURN,
                    input_tokens=entry.tokens_in,
                    output_tokens=entry.tokens_out,
                    model=self.model,
                )

        return LLMResponse(
            content=self._config.fallback_response,
            stop_reason=StopReason.ERROR,
            model=self.model,
        )

    async def _handle_failure(
        self, cache_key: str, error: Optional[Exception]
    ) -> LLMResponse:
        """Handle complete failure after retries.

        Args:
            cache_key: Cache key for fallback
            error: The last error

        Returns:
            Fallback response
        """
        # Try cache fallback
        if self._config.use_cache_fallback and self._cache:
            entry = self._cache.get(cache_key)
            if entry:
                logger.info("Using cached response after failure")
                return LLMResponse(
                    content=entry.response,
                    stop_reason=StopReason.END_TURN,
                    input_tokens=entry.tokens_in,
                    output_tokens=entry.tokens_out,
                    model=self.model,
                )

        # Return fallback message
        return LLMResponse(
            content=self._config.fallback_response,
            stop_reason=StopReason.ERROR,
            model=self.model,
        )

    def count_tokens(self, text: str) -> int:
        """Delegate token counting to underlying client."""
        return self._client.count_tokens(text)


def create_resilient_client(
    client: LLMClient,
    max_retries: int = 3,
    use_cache: bool = True,
    fallback_message: Optional[str] = None,
) -> ResilientLLMClient:
    """Create a resilient LLM client with common defaults.

    Args:
        client: Base LLM client
        max_retries: Maximum retry attempts
        use_cache: Whether to use cache fallback
        fallback_message: Custom fallback message

    Returns:
        Configured ResilientLLMClient
    """
    config = ResilienceConfig(
        retry=RetryConfig(max_retries=max_retries),
        use_cache_fallback=use_cache,
    )

    if fallback_message:
        config.fallback_response = fallback_message

    return ResilientLLMClient(client, config)
