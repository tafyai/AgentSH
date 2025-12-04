"""Async utilities for AgentSH.

Provides common async patterns and helpers:
- Timeout wrappers
- Retry decorators
- Rate limiting
- Parallel execution
- Debouncing/throttling
"""

import asyncio
import functools
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    Generic,
    Optional,
    TypeVar,
)

from agentsh.telemetry.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


class AsyncTimeoutError(Exception):
    """Raised when an async operation times out."""

    def __init__(self, message: str = "Operation timed out", timeout: float = 0) -> None:
        super().__init__(message)
        self.timeout = timeout


@asynccontextmanager
async def timeout(seconds: float, message: Optional[str] = None) -> AsyncIterator[None]:
    """Async context manager for timeouts.

    Args:
        seconds: Timeout in seconds
        message: Custom timeout message

    Raises:
        AsyncTimeoutError: If operation exceeds timeout

    Example:
        async with timeout(5.0):
            await long_running_operation()
    """
    try:
        async with asyncio.timeout(seconds):
            yield
    except asyncio.TimeoutError:
        msg = message or f"Operation timed out after {seconds}s"
        raise AsyncTimeoutError(msg, seconds)


async def run_with_timeout(
    coro: Awaitable[T],
    seconds: float,
    default: Optional[T] = None,
    raise_on_timeout: bool = True,
) -> Optional[T]:
    """Run a coroutine with a timeout.

    Args:
        coro: Coroutine to run
        seconds: Timeout in seconds
        default: Default value if timeout (only if raise_on_timeout=False)
        raise_on_timeout: Whether to raise on timeout

    Returns:
        Result of coroutine or default value

    Raises:
        AsyncTimeoutError: If timeout and raise_on_timeout is True
    """
    try:
        return await asyncio.wait_for(coro, timeout=seconds)
    except asyncio.TimeoutError:
        if raise_on_timeout:
            raise AsyncTimeoutError(f"Operation timed out after {seconds}s", seconds)
        return default


@dataclass
class RetryResult(Generic[T]):
    """Result of a retry operation.

    Attributes:
        success: Whether the operation succeeded
        result: The result if successful
        attempts: Number of attempts made
        total_time: Total time spent in seconds
        last_error: The last error if failed
    """

    success: bool
    result: Optional[T] = None
    attempts: int = 0
    total_time: float = 0.0
    last_error: Optional[Exception] = None


async def retry(
    func: Callable[..., Awaitable[T]],
    *args: Any,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[int, Exception], Awaitable[None]]] = None,
    **kwargs: Any,
) -> RetryResult[T]:
    """Retry an async function with exponential backoff.

    Args:
        func: Async function to retry
        *args: Positional arguments for func
        max_attempts: Maximum number of attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        jitter: Whether to add random jitter
        retryable_exceptions: Exception types to retry on
        on_retry: Callback on each retry (attempt, error)
        **kwargs: Keyword arguments for func

    Returns:
        RetryResult with success status and result/error
    """
    import random

    start_time = time.time()
    last_error: Optional[Exception] = None

    for attempt in range(max_attempts):
        try:
            result = await func(*args, **kwargs)
            return RetryResult(
                success=True,
                result=result,
                attempts=attempt + 1,
                total_time=time.time() - start_time,
            )
        except retryable_exceptions as e:
            last_error = e

            if attempt < max_attempts - 1:
                delay = min(base_delay * (exponential_base**attempt), max_delay)
                if jitter:
                    delay *= 0.5 + random.random()

                if on_retry:
                    await on_retry(attempt + 1, e)

                await asyncio.sleep(delay)

    return RetryResult(
        success=False,
        attempts=max_attempts,
        total_time=time.time() - start_time,
        last_error=last_error,
    )


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """Decorator for automatic retry with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        retryable_exceptions: Exception types to retry on

    Returns:
        Decorated function

    Example:
        @with_retry(max_attempts=3, retryable_exceptions=(ConnectionError,))
        async def fetch_data():
            return await api.get("/data")
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await retry(
                func,
                *args,
                max_attempts=max_attempts,
                base_delay=base_delay,
                max_delay=max_delay,
                retryable_exceptions=retryable_exceptions,
                **kwargs,
            )
            if result.success:
                return result.result
            raise result.last_error or Exception("Retry failed")

        return wrapper  # type: ignore

    return decorator


@dataclass
class RateLimiter:
    """Token bucket rate limiter for async operations.

    Attributes:
        rate: Tokens per second
        burst: Maximum burst size
    """

    rate: float
    burst: int
    _tokens: float = field(init=False)
    _last_update: float = field(init=False)
    _lock: asyncio.Lock = field(init=False, default_factory=asyncio.Lock)

    def __post_init__(self) -> None:
        self._tokens = float(self.burst)
        self._last_update = time.time()

    async def acquire(self, tokens: int = 1) -> float:
        """Acquire tokens, waiting if necessary.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            Wait time in seconds (0 if immediate)
        """
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_update
            self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
            self._last_update = now

            if self._tokens >= tokens:
                self._tokens -= tokens
                return 0.0

            wait_time = (tokens - self._tokens) / self.rate
            await asyncio.sleep(wait_time)

            self._tokens = 0
            self._last_update = time.time()
            return wait_time

    async def try_acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens without waiting.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            True if tokens were acquired
        """
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_update
            self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
            self._last_update = now

            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False


def rate_limited(rate: float, burst: int = 1) -> Callable[[F], F]:
    """Decorator for rate limiting async functions.

    Args:
        rate: Calls per second
        burst: Maximum burst size

    Returns:
        Decorated function

    Example:
        @rate_limited(rate=10, burst=5)  # 10 calls/sec, burst of 5
        async def api_call():
            return await api.get("/data")
    """
    limiter = RateLimiter(rate=rate, burst=burst)

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            await limiter.acquire()
            return await func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator


async def gather_with_limit(
    *coros: Awaitable[T],
    limit: int = 10,
    return_exceptions: bool = False,
) -> list[T | BaseException]:
    """Run coroutines concurrently with a concurrency limit.

    Args:
        *coros: Coroutines to run
        limit: Maximum concurrent coroutines
        return_exceptions: Return exceptions instead of raising

    Returns:
        List of results in order

    Example:
        results = await gather_with_limit(
            fetch(url1), fetch(url2), fetch(url3),
            limit=2,  # Only 2 concurrent
        )
    """
    semaphore = asyncio.Semaphore(limit)

    async def bounded(coro: Awaitable[T]) -> T | BaseException:
        async with semaphore:
            if return_exceptions:
                try:
                    return await coro
                except BaseException as e:
                    return e
            return await coro

    return await asyncio.gather(
        *[bounded(c) for c in coros],
        return_exceptions=return_exceptions,
    )


async def first_completed(
    *coros: Awaitable[T],
    timeout_seconds: Optional[float] = None,
) -> T:
    """Return result of first completed coroutine, cancel others.

    Args:
        *coros: Coroutines to race
        timeout_seconds: Overall timeout

    Returns:
        Result of first completed coroutine

    Raises:
        AsyncTimeoutError: If timeout before any complete
        Exception: If all coroutines fail
    """
    tasks = [asyncio.create_task(c) for c in coros]

    try:
        if timeout_seconds:
            done, pending = await asyncio.wait(
                tasks,
                timeout=timeout_seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )
        else:
            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )

        # Cancel pending tasks
        for task in pending:
            task.cancel()

        if not done:
            raise AsyncTimeoutError(
                f"No task completed within {timeout_seconds}s", timeout_seconds or 0
            )

        # Return first result (may raise if it errored)
        return done.pop().result()

    except Exception:
        # Cancel all tasks on error
        for task in tasks:
            task.cancel()
        raise


class Debouncer(Generic[T]):
    """Debounce async function calls.

    Only executes after a period of inactivity.

    Example:
        debouncer = Debouncer(delay=0.5)

        async def save():
            await debouncer.call(save_to_disk)
        # Rapidly calling save() will only trigger one save
    """

    def __init__(self, delay: float) -> None:
        """Initialize debouncer.

        Args:
            delay: Delay in seconds
        """
        self.delay = delay
        self._task: Optional[asyncio.Task[T]] = None
        self._last_call: Optional[datetime] = None

    async def call(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Schedule a debounced call.

        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments
        """
        # Cancel previous pending call
        if self._task and not self._task.done():
            self._task.cancel()

        async def delayed() -> T:
            await asyncio.sleep(self.delay)
            return await func(*args, **kwargs)

        self._task = asyncio.create_task(delayed())
        self._last_call = datetime.now()


class Throttler(Generic[T]):
    """Throttle async function calls.

    Ensures minimum time between executions.

    Example:
        throttler = Throttler(interval=1.0)

        async def log_event():
            await throttler.call(send_to_server, event)
        # Calls at most once per second
    """

    def __init__(self, interval: float) -> None:
        """Initialize throttler.

        Args:
            interval: Minimum interval in seconds
        """
        self.interval = interval
        self._last_call: Optional[datetime] = None
        self._lock = asyncio.Lock()

    async def call(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> Optional[T]:
        """Execute function if interval has passed.

        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result or None if throttled
        """
        async with self._lock:
            now = datetime.now()

            if self._last_call:
                elapsed = (now - self._last_call).total_seconds()
                if elapsed < self.interval:
                    return None

            self._last_call = now
            return await func(*args, **kwargs)


async def run_in_executor(
    func: Callable[..., T],
    *args: Any,
    **kwargs: Any,
) -> T:
    """Run a sync function in the default executor.

    Useful for running blocking I/O in async context.

    Args:
        func: Sync function to run
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        Function result

    Example:
        data = await run_in_executor(open_large_file, path)
    """
    loop = asyncio.get_event_loop()
    if kwargs:
        func = functools.partial(func, **kwargs)
    return await loop.run_in_executor(None, func, *args)


class AsyncCache(Generic[T]):
    """Simple async-aware cache with TTL.

    Example:
        cache = AsyncCache[str](ttl=60)

        async def get_data(key: str) -> str:
            cached = await cache.get(key)
            if cached:
                return cached
            data = await fetch_data(key)
            await cache.set(key, data)
            return data
    """

    def __init__(self, ttl: float = 300, max_size: int = 1000) -> None:
        """Initialize cache.

        Args:
            ttl: Time-to-live in seconds
            max_size: Maximum cache size
        """
        self.ttl = ttl
        self.max_size = max_size
        self._cache: dict[str, tuple[T, datetime]] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[T]:
        """Get a cached value.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        async with self._lock:
            if key in self._cache:
                value, timestamp = self._cache[key]
                if (datetime.now() - timestamp).total_seconds() < self.ttl:
                    return value
                del self._cache[key]
            return None

    async def set(self, key: str, value: T) -> None:
        """Set a cached value.

        Args:
            key: Cache key
            value: Value to cache
        """
        async with self._lock:
            # Evict if at capacity
            if len(self._cache) >= self.max_size:
                # Remove oldest entry
                oldest_key = min(self._cache, key=lambda k: self._cache[k][1])
                del self._cache[oldest_key]

            self._cache[key] = (value, datetime.now())

    async def delete(self, key: str) -> bool:
        """Delete a cached value.

        Args:
            key: Cache key

        Returns:
            True if key was found and deleted
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def clear(self) -> None:
        """Clear all cached values."""
        async with self._lock:
            self._cache.clear()


async def safe_cancel(task: asyncio.Task[Any], timeout: float = 5.0) -> None:
    """Safely cancel an asyncio task.

    Args:
        task: Task to cancel
        timeout: Time to wait for cancellation
    """
    if task.done():
        return

    task.cancel()
    try:
        await asyncio.wait_for(
            asyncio.shield(task),
            timeout=timeout,
        )
    except (asyncio.CancelledError, asyncio.TimeoutError):
        pass


async def cancel_all(
    tasks: list[asyncio.Task[Any]], timeout: float = 5.0
) -> None:
    """Cancel all tasks and wait for them to complete.

    Args:
        tasks: Tasks to cancel
        timeout: Time to wait for each task
    """
    for task in tasks:
        await safe_cancel(task, timeout)
