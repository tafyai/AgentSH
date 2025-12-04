"""Tests for async utilities module."""

import asyncio
import pytest
import time

from agentsh.utils.async_utils import (
    AsyncCache,
    AsyncTimeoutError,
    Debouncer,
    RateLimiter,
    RetryResult,
    Throttler,
    cancel_all,
    first_completed,
    gather_with_limit,
    rate_limited,
    retry,
    run_in_executor,
    run_with_timeout,
    safe_cancel,
    timeout,
    with_retry,
)


class TestTimeout:
    """Tests for timeout context manager."""

    @pytest.mark.asyncio
    async def test_timeout_success(self) -> None:
        """Should complete within timeout."""
        async with timeout(1.0):
            await asyncio.sleep(0.1)
        # Should complete without error

    @pytest.mark.asyncio
    async def test_timeout_exceeded(self) -> None:
        """Should raise AsyncTimeoutError when exceeded."""
        with pytest.raises(AsyncTimeoutError) as exc_info:
            async with timeout(0.1):
                await asyncio.sleep(1.0)

        assert exc_info.value.timeout == 0.1

    @pytest.mark.asyncio
    async def test_timeout_custom_message(self) -> None:
        """Should use custom message."""
        with pytest.raises(AsyncTimeoutError) as exc_info:
            async with timeout(0.1, message="Custom timeout"):
                await asyncio.sleep(1.0)

        assert "Custom timeout" in str(exc_info.value)


class TestRunWithTimeout:
    """Tests for run_with_timeout function."""

    @pytest.mark.asyncio
    async def test_success(self) -> None:
        """Should return result on success."""

        async def quick_op() -> str:
            return "result"

        result = await run_with_timeout(quick_op(), 1.0)
        assert result == "result"

    @pytest.mark.asyncio
    async def test_timeout_raises(self) -> None:
        """Should raise on timeout by default."""

        async def slow_op() -> str:
            await asyncio.sleep(1.0)
            return "never"

        with pytest.raises(AsyncTimeoutError):
            await run_with_timeout(slow_op(), 0.1)

    @pytest.mark.asyncio
    async def test_timeout_returns_default(self) -> None:
        """Should return default when raise_on_timeout=False."""

        async def slow_op() -> str:
            await asyncio.sleep(1.0)
            return "never"

        result = await run_with_timeout(
            slow_op(), 0.1, default="default", raise_on_timeout=False
        )
        assert result == "default"


class TestRetry:
    """Tests for retry function."""

    @pytest.mark.asyncio
    async def test_success_first_try(self) -> None:
        """Should succeed on first try."""
        call_count = 0

        async def succeed() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = await retry(succeed, max_attempts=3)

        assert result.success is True
        assert result.result == "success"
        assert result.attempts == 1
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_success_after_retry(self) -> None:
        """Should succeed after retries."""
        call_count = 0

        async def fail_then_succeed() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Failed")
            return "success"

        result = await retry(
            fail_then_succeed,
            max_attempts=5,
            base_delay=0.01,
            jitter=False,
        )

        assert result.success is True
        assert result.result == "success"
        assert result.attempts == 3
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_attempts_exhausted(self) -> None:
        """Should fail after max attempts."""
        call_count = 0

        async def always_fail() -> str:
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Failed")

        result = await retry(
            always_fail,
            max_attempts=3,
            base_delay=0.01,
            jitter=False,
        )

        assert result.success is False
        assert result.attempts == 3
        assert isinstance(result.last_error, ConnectionError)

    @pytest.mark.asyncio
    async def test_on_retry_callback(self) -> None:
        """Should call on_retry callback."""
        retries: list[tuple[int, Exception]] = []

        async def on_retry(attempt: int, error: Exception) -> None:
            retries.append((attempt, error))

        async def fail_twice() -> str:
            if len(retries) < 2:
                raise ConnectionError("Failed")
            return "success"

        await retry(
            fail_twice,
            max_attempts=5,
            base_delay=0.01,
            jitter=False,
            on_retry=on_retry,
        )

        assert len(retries) == 2
        assert retries[0][0] == 1
        assert retries[1][0] == 2


class TestWithRetryDecorator:
    """Tests for with_retry decorator."""

    @pytest.mark.asyncio
    async def test_decorated_success(self) -> None:
        """Should work with decorator."""
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        async def succeed() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = await succeed()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_decorated_retry(self) -> None:
        """Should retry with decorator."""
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        async def fail_once() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Failed")
            return "success"

        result = await fail_once()
        assert result == "success"
        assert call_count == 2


class TestRateLimiter:
    """Tests for RateLimiter class."""

    @pytest.mark.asyncio
    async def test_acquire_immediate(self) -> None:
        """Should acquire immediately when available."""
        limiter = RateLimiter(rate=10, burst=5)
        wait_time = await limiter.acquire()
        assert wait_time == 0.0

    @pytest.mark.asyncio
    async def test_acquire_waits(self) -> None:
        """Should wait when tokens exhausted."""
        limiter = RateLimiter(rate=10, burst=1)

        # First acquisition is immediate
        await limiter.acquire()

        # Second should wait
        start = time.time()
        await limiter.acquire()
        elapsed = time.time() - start

        assert elapsed > 0.05  # Should have waited

    @pytest.mark.asyncio
    async def test_try_acquire_success(self) -> None:
        """Should succeed when tokens available."""
        limiter = RateLimiter(rate=10, burst=5)
        result = await limiter.try_acquire()
        assert result is True

    @pytest.mark.asyncio
    async def test_try_acquire_fail(self) -> None:
        """Should fail when no tokens available."""
        limiter = RateLimiter(rate=10, burst=1)

        # Exhaust tokens
        await limiter.acquire()

        # Should fail immediately
        result = await limiter.try_acquire()
        assert result is False


class TestRateLimitedDecorator:
    """Tests for rate_limited decorator."""

    @pytest.mark.asyncio
    async def test_rate_limited(self) -> None:
        """Should rate limit calls."""
        call_times: list[float] = []

        @rate_limited(rate=100, burst=1)  # Fast for testing
        async def tracked_call() -> None:
            call_times.append(time.time())

        # Make several calls
        for _ in range(3):
            await tracked_call()

        assert len(call_times) == 3


class TestGatherWithLimit:
    """Tests for gather_with_limit function."""

    @pytest.mark.asyncio
    async def test_gather_all(self) -> None:
        """Should gather all results."""

        async def task(n: int) -> int:
            return n * 2

        results = await gather_with_limit(
            task(1), task(2), task(3),
            limit=2,
        )

        assert results == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_gather_respects_limit(self) -> None:
        """Should respect concurrency limit."""
        concurrent = 0
        max_concurrent = 0

        async def tracked_task(n: int) -> int:
            nonlocal concurrent, max_concurrent
            concurrent += 1
            max_concurrent = max(max_concurrent, concurrent)
            await asyncio.sleep(0.1)
            concurrent -= 1
            return n

        await gather_with_limit(
            *[tracked_task(i) for i in range(5)],
            limit=2,
        )

        assert max_concurrent <= 2

    @pytest.mark.asyncio
    async def test_gather_return_exceptions(self) -> None:
        """Should return exceptions when requested."""

        async def fail() -> int:
            raise ValueError("Failed")

        async def succeed() -> int:
            return 42

        results = await gather_with_limit(
            succeed(), fail(),
            limit=2,
            return_exceptions=True,
        )

        assert results[0] == 42
        assert isinstance(results[1], ValueError)


class TestFirstCompleted:
    """Tests for first_completed function."""

    @pytest.mark.asyncio
    async def test_returns_first(self) -> None:
        """Should return first completed result."""

        async def fast() -> str:
            return "fast"

        async def slow() -> str:
            await asyncio.sleep(1.0)
            return "slow"

        result = await first_completed(fast(), slow())
        assert result == "fast"

    @pytest.mark.asyncio
    async def test_cancels_others(self) -> None:
        """Should cancel non-completed tasks."""
        cancelled = False

        async def will_be_cancelled() -> str:
            nonlocal cancelled
            try:
                await asyncio.sleep(10.0)
            except asyncio.CancelledError:
                cancelled = True
                raise
            return "never"

        async def quick() -> str:
            return "quick"

        await first_completed(quick(), will_be_cancelled())

        # Give time for cancellation
        await asyncio.sleep(0.1)
        assert cancelled is True

    @pytest.mark.asyncio
    async def test_timeout(self) -> None:
        """Should timeout if no task completes."""

        async def slow() -> str:
            await asyncio.sleep(10.0)
            return "never"

        with pytest.raises(AsyncTimeoutError):
            await first_completed(slow(), timeout_seconds=0.1)


class TestDebouncer:
    """Tests for Debouncer class."""

    @pytest.mark.asyncio
    async def test_debounce(self) -> None:
        """Should debounce rapid calls."""
        call_count = 0

        async def tracked() -> None:
            nonlocal call_count
            call_count += 1

        debouncer = Debouncer[None](delay=0.1)

        # Rapid calls
        for _ in range(5):
            await debouncer.call(tracked)

        # Wait for debounce
        await asyncio.sleep(0.2)

        # Should only have called once
        assert call_count == 1


class TestThrottler:
    """Tests for Throttler class."""

    @pytest.mark.asyncio
    async def test_throttle(self) -> None:
        """Should throttle rapid calls."""
        call_count = 0

        async def tracked() -> int:
            nonlocal call_count
            call_count += 1
            return call_count

        throttler = Throttler[int](interval=0.1)

        # First call succeeds
        result1 = await throttler.call(tracked)
        assert result1 == 1

        # Immediate second call is throttled
        result2 = await throttler.call(tracked)
        assert result2 is None

        # Wait and try again
        await asyncio.sleep(0.15)
        result3 = await throttler.call(tracked)
        assert result3 == 2


class TestRunInExecutor:
    """Tests for run_in_executor function."""

    @pytest.mark.asyncio
    async def test_run_sync_function(self) -> None:
        """Should run sync function in executor."""

        def blocking_task(x: int) -> int:
            time.sleep(0.01)  # Blocking sleep
            return x * 2

        result = await run_in_executor(blocking_task, 21)
        assert result == 42

    @pytest.mark.asyncio
    async def test_run_with_kwargs(self) -> None:
        """Should support kwargs."""

        def task_with_kwargs(a: int, b: int = 0) -> int:
            return a + b

        result = await run_in_executor(task_with_kwargs, 10, b=5)
        assert result == 15


class TestAsyncCache:
    """Tests for AsyncCache class."""

    @pytest.mark.asyncio
    async def test_get_set(self) -> None:
        """Should get and set values."""
        cache: AsyncCache[str] = AsyncCache(ttl=60)

        await cache.set("key1", "value1")
        result = await cache.get("key1")

        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_missing(self) -> None:
        """Should return None for missing keys."""
        cache: AsyncCache[str] = AsyncCache(ttl=60)
        result = await cache.get("missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_ttl_expiration(self) -> None:
        """Should expire values after TTL."""
        cache: AsyncCache[str] = AsyncCache(ttl=0.1)

        await cache.set("key1", "value1")
        await asyncio.sleep(0.15)

        result = await cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self) -> None:
        """Should delete values."""
        cache: AsyncCache[str] = AsyncCache(ttl=60)

        await cache.set("key1", "value1")
        result = await cache.delete("key1")

        assert result is True
        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_clear(self) -> None:
        """Should clear all values."""
        cache: AsyncCache[str] = AsyncCache(ttl=60)

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")
        await cache.clear()

        assert await cache.get("key1") is None
        assert await cache.get("key2") is None

    @pytest.mark.asyncio
    async def test_max_size_eviction(self) -> None:
        """Should evict oldest on max size."""
        cache: AsyncCache[str] = AsyncCache(ttl=60, max_size=2)

        await cache.set("key1", "value1")
        await asyncio.sleep(0.01)
        await cache.set("key2", "value2")
        await asyncio.sleep(0.01)
        await cache.set("key3", "value3")

        # key1 should be evicted
        assert await cache.get("key1") is None
        assert await cache.get("key2") == "value2"
        assert await cache.get("key3") == "value3"


class TestSafeCancel:
    """Tests for safe_cancel function."""

    @pytest.mark.asyncio
    async def test_cancel_running_task(self) -> None:
        """Should cancel running task."""

        async def long_task() -> str:
            await asyncio.sleep(10.0)
            return "done"

        task = asyncio.create_task(long_task())
        await asyncio.sleep(0.01)

        await safe_cancel(task)

        assert task.cancelled() or task.done()

    @pytest.mark.asyncio
    async def test_cancel_done_task(self) -> None:
        """Should handle already-done task."""

        async def quick_task() -> str:
            return "done"

        task = asyncio.create_task(quick_task())
        await asyncio.sleep(0.01)

        # Should not raise
        await safe_cancel(task)


class TestCancelAll:
    """Tests for cancel_all function."""

    @pytest.mark.asyncio
    async def test_cancel_all_tasks(self) -> None:
        """Should cancel all tasks."""

        async def long_task(n: int) -> int:
            await asyncio.sleep(10.0)
            return n

        tasks = [asyncio.create_task(long_task(i)) for i in range(3)]
        await asyncio.sleep(0.01)

        await cancel_all(tasks)

        for task in tasks:
            assert task.cancelled() or task.done()
