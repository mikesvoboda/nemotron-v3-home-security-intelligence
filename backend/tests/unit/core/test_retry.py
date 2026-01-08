"""Unit tests for the retry decorators module.

Tests cover:
- Exponential backoff with jitter
- Retry on specific exception types
- Max retries enforcement
- Success on retry scenarios
- Immediate success (no retries needed)
- Async retry decorator
- Sync retry decorator
- Metrics integration
- Logging behavior
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.core.exceptions import (
    DatabaseError,
    DetectorUnavailableError,
    ExternalServiceError,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def transient_error() -> ExternalServiceError:
    """Create a transient external service error."""
    return ExternalServiceError("Connection failed", service_name="test_service")


@pytest.fixture
def detector_error() -> DetectorUnavailableError:
    """Create a detector unavailable error."""
    return DetectorUnavailableError("RT-DETR timeout")


# =============================================================================
# Retry Configuration Tests
# =============================================================================


class TestRetryConfig:
    """Tests for retry configuration."""

    def test_default_retry_config_values(self) -> None:
        """Test that default retry config has expected values."""
        from backend.core.retry import RetryConfig

        config = RetryConfig()
        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter == 0.1

    def test_custom_retry_config(self) -> None:
        """Test custom retry configuration."""
        from backend.core.retry import RetryConfig

        config = RetryConfig(
            max_retries=5,
            base_delay=0.5,
            max_delay=30.0,
            exponential_base=3.0,
            jitter=0.2,
        )
        assert config.max_retries == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 30.0
        assert config.exponential_base == 3.0
        assert config.jitter == 0.2

    def test_retry_config_immutable(self) -> None:
        """Test that retry config is immutable (frozen dataclass)."""
        from backend.core.retry import RetryConfig

        config = RetryConfig()
        with pytest.raises(AttributeError):
            config.max_retries = 10  # type: ignore[misc]


# =============================================================================
# Backoff Calculation Tests
# =============================================================================


class TestBackoffCalculation:
    """Tests for backoff delay calculation."""

    def test_calculate_delay_first_retry(self) -> None:
        """Test delay calculation for first retry."""
        from backend.core.retry import RetryConfig, calculate_delay

        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=0.0)
        delay = calculate_delay(attempt=1, config=config)
        assert delay == 1.0

    def test_calculate_delay_exponential_growth(self) -> None:
        """Test that delay grows exponentially."""
        from backend.core.retry import RetryConfig, calculate_delay

        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=0.0)

        assert calculate_delay(attempt=1, config=config) == 1.0
        assert calculate_delay(attempt=2, config=config) == 2.0
        assert calculate_delay(attempt=3, config=config) == 4.0
        assert calculate_delay(attempt=4, config=config) == 8.0

    def test_calculate_delay_respects_max_delay(self) -> None:
        """Test that delay is capped at max_delay."""
        from backend.core.retry import RetryConfig, calculate_delay

        config = RetryConfig(base_delay=1.0, max_delay=5.0, exponential_base=2.0, jitter=0.0)

        # Attempt 4 would normally be 8.0, but should be capped at 5.0
        delay = calculate_delay(attempt=4, config=config)
        assert delay == 5.0

    def test_calculate_delay_with_jitter(self) -> None:
        """Test that jitter adds randomness to delay."""
        from backend.core.retry import RetryConfig, calculate_delay

        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=0.5)

        # With 50% jitter, delay for attempt 1 should be in range [0.5, 1.5]
        delays = [calculate_delay(attempt=1, config=config) for _ in range(100)]

        assert min(delays) >= 0.5
        assert max(delays) <= 1.5
        # Verify there's actually variation (not all the same)
        assert len(set(delays)) > 1


# =============================================================================
# Async Retry Decorator Tests
# =============================================================================


class TestAsyncRetryDecorator:
    """Tests for the async retry decorator."""

    @pytest.mark.asyncio
    async def test_immediate_success_no_retry(self) -> None:
        """Test that successful calls don't trigger retries."""
        from backend.core.retry import retry_async

        call_count = 0

        @retry_async(max_retries=3)
        async def successful_func() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = await successful_func()

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_transient_error(self, transient_error: ExternalServiceError) -> None:
        """Test that transient errors trigger retries."""
        from backend.core.retry import retry_async

        call_count = 0

        @retry_async(max_retries=3, base_delay=0.01, retry_on=(ExternalServiceError,))
        async def failing_then_success() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise transient_error
            return "success"

        result = await failing_then_success()

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, transient_error: ExternalServiceError) -> None:
        """Test that max retries is enforced."""
        from backend.core.retry import retry_async

        call_count = 0

        @retry_async(max_retries=2, base_delay=0.01, retry_on=(ExternalServiceError,))
        async def always_failing() -> str:
            nonlocal call_count
            call_count += 1
            raise transient_error

        with pytest.raises(ExternalServiceError):
            await always_failing()

        # Initial call + 2 retries = 3 total calls
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_non_retryable_exception(self) -> None:
        """Test that non-retryable exceptions are raised immediately."""
        from backend.core.retry import retry_async

        call_count = 0

        @retry_async(max_retries=3, base_delay=0.01, retry_on=(ExternalServiceError,))
        async def raises_value_error() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("Not retryable")

        with pytest.raises(ValueError, match="Not retryable"):
            await raises_value_error()

        # Should not retry, only one call
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_with_multiple_exception_types(self) -> None:
        """Test retry with multiple exception types."""
        from backend.core.retry import retry_async

        call_count = 0

        @retry_async(
            max_retries=3,
            base_delay=0.01,
            retry_on=(ExternalServiceError, DatabaseError),
        )
        async def alternating_errors() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ExternalServiceError("Service down")
            if call_count == 2:
                raise DatabaseError("Connection lost")
            return "success"

        result = await alternating_errors()

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_preserves_function_metadata(self) -> None:
        """Test that decorator preserves function name and docstring."""
        from backend.core.retry import retry_async

        @retry_async(max_retries=3)
        async def documented_func() -> str:
            """This is a documented function."""
            return "result"

        assert documented_func.__name__ == "documented_func"
        assert documented_func.__doc__ == "This is a documented function."


# =============================================================================
# Sync Retry Decorator Tests
# =============================================================================


class TestSyncRetryDecorator:
    """Tests for the sync retry decorator."""

    def test_sync_immediate_success(self) -> None:
        """Test that successful sync calls don't trigger retries."""
        from backend.core.retry import retry_sync

        call_count = 0

        @retry_sync(max_retries=3, base_delay=0.01)
        def successful_func() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = successful_func()

        assert result == "success"
        assert call_count == 1

    def test_sync_retries_on_error(self, transient_error: ExternalServiceError) -> None:
        """Test that sync errors trigger retries."""
        from backend.core.retry import retry_sync

        call_count = 0

        @retry_sync(max_retries=3, base_delay=0.01, retry_on=(ExternalServiceError,))
        def failing_then_success() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise transient_error
            return "success"

        result = failing_then_success()

        assert result == "success"
        assert call_count == 2

    def test_sync_max_retries_exceeded(self, transient_error: ExternalServiceError) -> None:
        """Test that max retries is enforced for sync functions."""
        from backend.core.retry import retry_sync

        call_count = 0

        @retry_sync(max_retries=2, base_delay=0.01, retry_on=(ExternalServiceError,))
        def always_failing() -> str:
            nonlocal call_count
            call_count += 1
            raise transient_error

        with pytest.raises(ExternalServiceError):
            always_failing()

        # Initial call + 2 retries = 3 total calls
        assert call_count == 3


# =============================================================================
# Logging Tests
# =============================================================================


class TestRetryLogging:
    """Tests for retry logging behavior."""

    @pytest.mark.asyncio
    async def test_logs_retry_attempts(self, transient_error: ExternalServiceError) -> None:
        """Test that retry attempts are logged."""
        from backend.core.retry import retry_async

        @retry_async(max_retries=2, base_delay=0.01, retry_on=(ExternalServiceError,))
        async def failing_func() -> str:
            raise transient_error

        with patch("backend.core.retry.logger") as mock_logger:
            with pytest.raises(ExternalServiceError):
                await failing_func()

            # Should have warning logs for each retry
            assert mock_logger.warning.call_count >= 2

    @pytest.mark.asyncio
    async def test_logs_success_after_retry(self, transient_error: ExternalServiceError) -> None:
        """Test that success after retry is logged."""
        from backend.core.retry import retry_async

        call_count = 0

        @retry_async(max_retries=3, base_delay=0.01, retry_on=(ExternalServiceError,))
        async def eventually_succeeds() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise transient_error
            return "success"

        with patch("backend.core.retry.logger") as mock_logger:
            result = await eventually_succeeds()

            assert result == "success"
            # Should log the successful recovery
            mock_logger.info.assert_called()


# =============================================================================
# Metrics Integration Tests
# =============================================================================


class TestRetryMetrics:
    """Tests for retry metrics integration."""

    @pytest.mark.asyncio
    async def test_records_retry_metrics(self, transient_error: ExternalServiceError) -> None:
        """Test that retry attempts are recorded in metrics."""
        from backend.core.retry import retry_async

        call_count = 0

        @retry_async(
            max_retries=3,
            base_delay=0.01,
            retry_on=(ExternalServiceError,),
            operation_name="test_operation",
        )
        async def failing_func() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise transient_error
            return "success"

        with patch("backend.core.retry.RETRY_ATTEMPTS_TOTAL") as mock_counter:
            mock_labels = MagicMock()
            mock_counter.labels.return_value = mock_labels

            await failing_func()

            # Should have incremented the retry counter
            mock_counter.labels.assert_called()


# =============================================================================
# Context Manager Tests
# =============================================================================


class TestRetryContextManager:
    """Tests for retry as context manager."""

    @pytest.mark.asyncio
    async def test_retry_context_success(self) -> None:
        """Test retry context manager with successful operation."""
        from backend.core.retry import RetryContext

        call_count = 0

        async with RetryContext(max_retries=3, base_delay=0.01) as retry:
            while retry.should_retry():
                try:
                    call_count += 1
                    # Succeeds on first try
                    break
                except ExternalServiceError:
                    await retry.wait()

        assert call_count == 1
        # attempts is only incremented via can_retry(), which wasn't called
        # for a successful first try
        assert retry.attempts == 0

    @pytest.mark.asyncio
    async def test_retry_context_with_failures(self, transient_error: ExternalServiceError) -> None:
        """Test retry context manager with failures then success."""
        from backend.core.retry import RetryContext

        call_count = 0

        async with RetryContext(
            max_retries=3, base_delay=0.01, retry_on=(ExternalServiceError,)
        ) as retry:
            while retry.should_retry():
                try:
                    call_count += 1
                    if call_count < 3:
                        raise transient_error
                    break
                except ExternalServiceError as e:
                    if not retry.can_retry(e):
                        raise
                    await retry.wait()

        assert call_count == 3
        # can_retry() was called twice (for 2 failures before success)
        assert retry.attempts == 2


# =============================================================================
# Edge Cases
# =============================================================================


class TestRetryEdgeCases:
    """Tests for edge cases in retry behavior."""

    @pytest.mark.asyncio
    async def test_zero_max_retries(self, transient_error: ExternalServiceError) -> None:
        """Test behavior with zero max retries (no retries)."""
        from backend.core.retry import retry_async

        call_count = 0

        @retry_async(max_retries=0, base_delay=0.01, retry_on=(ExternalServiceError,))
        async def no_retries() -> str:
            nonlocal call_count
            call_count += 1
            raise transient_error

        with pytest.raises(ExternalServiceError):
            await no_retries()

        # Only initial call, no retries
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_with_arguments(self, transient_error: ExternalServiceError) -> None:
        """Test that function arguments are preserved across retries."""
        from backend.core.retry import retry_async

        call_count = 0
        received_args: list[tuple[int, str]] = []

        @retry_async(max_retries=3, base_delay=0.01, retry_on=(ExternalServiceError,))
        async def func_with_args(x: int, y: str) -> str:
            nonlocal call_count
            call_count += 1
            received_args.append((x, y))
            if call_count < 2:
                raise transient_error
            return f"{x}-{y}"

        result = await func_with_args(42, "test")

        assert result == "42-test"
        assert all(args == (42, "test") for args in received_args)

    @pytest.mark.asyncio
    async def test_retry_with_return_none(self) -> None:
        """Test that None return values are handled correctly."""
        from backend.core.retry import retry_async

        @retry_async(max_retries=3)
        async def returns_none() -> None:
            return None

        result = await returns_none()
        assert result is None

    @pytest.mark.asyncio
    async def test_retry_subclass_exceptions(self) -> None:
        """Test that exception subclasses are caught for retry."""
        from backend.core.retry import retry_async

        call_count = 0

        @retry_async(
            max_retries=3,
            base_delay=0.01,
            retry_on=(ExternalServiceError,),  # Parent class
        )
        async def raises_subclass() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise DetectorUnavailableError()  # Subclass
            return "success"

        result = await raises_subclass()

        assert result == "success"
        assert call_count == 2


# =============================================================================
# with_retry Decorator Tests (NEM-1445 Specification)
# =============================================================================


class TestWithRetryDecorator:
    """Tests for the with_retry decorator matching NEM-1445 specification.

    The with_retry decorator should support:
    - max_attempts: int = 3 (total attempts, not retries)
    - base_delay: float = 1.0
    - max_delay: float = 30.0
    - exponential_base: float = 2.0
    - jitter: bool = True (when True, multiply delay by 0.5 + random())
    - retryable_exceptions: tuple[type[Exception], ...]
    - on_retry: Callable[[int, Exception], None] | None
    """

    @pytest.mark.asyncio
    async def test_success_on_first_attempt_no_retry(self) -> None:
        """Test that successful call on first attempt doesn't trigger retries."""
        from backend.core.retry import with_retry

        call_count = 0

        @with_retry(max_attempts=3, retryable_exceptions=(ExternalServiceError,))
        async def successful_func() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = await successful_func()

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_success_after_retries(self) -> None:
        """Test that function succeeds after transient failures."""
        from backend.core.retry import with_retry

        call_count = 0

        @with_retry(
            max_attempts=3,
            base_delay=0.01,
            retryable_exceptions=(ExternalServiceError,),
        )
        async def failing_then_success() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ExternalServiceError("Transient failure", service_name="test")
            return "success"

        result = await failing_then_success()

        assert result == "success"
        assert call_count == 3  # 3 total attempts

    @pytest.mark.asyncio
    async def test_max_attempts_exceeded_raises(self) -> None:
        """Test that exceeding max_attempts raises the last exception."""
        from backend.core.retry import with_retry

        call_count = 0

        @with_retry(
            max_attempts=3,
            base_delay=0.01,
            retryable_exceptions=(ExternalServiceError,),
        )
        async def always_failing() -> str:
            nonlocal call_count
            call_count += 1
            raise ExternalServiceError("Always fails", service_name="test")

        with pytest.raises(ExternalServiceError, match="Always fails"):
            await always_failing()

        # Should have attempted exactly 3 times (max_attempts)
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_non_retryable_exception_raises_immediately(self) -> None:
        """Test that non-retryable exceptions are raised without retry."""
        from backend.core.retry import with_retry

        call_count = 0

        @with_retry(
            max_attempts=3,
            base_delay=0.01,
            retryable_exceptions=(ExternalServiceError,),
        )
        async def raises_value_error() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("Not retryable")

        with pytest.raises(ValueError, match="Not retryable"):
            await raises_value_error()

        # Should not retry, only one attempt
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_on_retry_callback_invoked(self) -> None:
        """Test that on_retry callback is called with attempt number and exception."""
        from backend.core.retry import with_retry

        retry_calls: list[tuple[int, Exception]] = []

        def on_retry_callback(attempt: int, exc: Exception) -> None:
            retry_calls.append((attempt, exc))

        call_count = 0

        @with_retry(
            max_attempts=3,
            base_delay=0.01,
            retryable_exceptions=(ExternalServiceError,),
            on_retry=on_retry_callback,
        )
        async def failing_then_success() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ExternalServiceError(f"Failure {call_count}", service_name="test")
            return "success"

        result = await failing_then_success()

        assert result == "success"
        assert len(retry_calls) == 2  # Called before retry 2 and 3
        assert retry_calls[0][0] == 1  # First retry (after attempt 1)
        assert retry_calls[1][0] == 2  # Second retry (after attempt 2)
        assert isinstance(retry_calls[0][1], ExternalServiceError)
        assert isinstance(retry_calls[1][1], ExternalServiceError)

    @pytest.mark.asyncio
    async def test_on_retry_callback_not_called_on_success(self) -> None:
        """Test that on_retry callback is not called when first attempt succeeds."""
        from backend.core.retry import with_retry

        callback_called = False

        def on_retry_callback(attempt: int, exc: Exception) -> None:
            nonlocal callback_called
            callback_called = True

        @with_retry(
            max_attempts=3,
            retryable_exceptions=(ExternalServiceError,),
            on_retry=on_retry_callback,
        )
        async def successful_func() -> str:
            return "success"

        result = await successful_func()

        assert result == "success"
        assert callback_called is False

    @pytest.mark.asyncio
    async def test_jitter_enabled_varies_delay(self) -> None:
        """Test that jitter=True varies the delay using 0.5 + random() formula.

        When jitter=True, delay should be: base_delay * (exponential_base ^ (attempt-1)) * (0.5 + random())
        For attempt 1 with base_delay=1.0, exponential_base=2.0: delay = 1.0 * (0.5 + random())
        This means delay should be in range [0.5, 1.5)
        """
        from backend.core.retry import with_retry

        start_times: list[float] = []
        import time

        call_count = 0

        @with_retry(
            max_attempts=3,
            base_delay=0.1,  # 100ms base delay
            jitter=True,
            retryable_exceptions=(ExternalServiceError,),
        )
        async def failing_func() -> str:
            nonlocal call_count
            start_times.append(time.monotonic())
            call_count += 1
            raise ExternalServiceError("Always fails", service_name="test")

        # Run multiple times to verify jitter varies
        delays_collected: list[float] = []
        for _ in range(5):
            call_count = 0
            start_times.clear()
            try:
                await failing_func()
            except ExternalServiceError:
                pass

            # Calculate actual delays between calls
            if len(start_times) >= 2:
                delay = start_times[1] - start_times[0]
                delays_collected.append(delay)

        # With jitter, delays should vary (not all exactly the same)
        # Allow for some timing variance but delays should be roughly in [0.05, 0.15] range
        # (0.1 * (0.5 + random()) where random() is in [0, 1))
        assert len(delays_collected) > 0
        for delay in delays_collected:
            # With jitter formula: delay * (0.5 + random()), delay should be in [0.05, 0.15)
            assert delay >= 0.04, f"Delay {delay} is too short"  # Allow small timing variance
            assert delay < 0.20, f"Delay {delay} is too long"

    @pytest.mark.asyncio
    async def test_jitter_disabled_consistent_delay(self) -> None:
        """Test that jitter=False produces consistent delay."""
        import time

        from backend.core.retry import with_retry

        call_count = 0
        start_times: list[float] = []

        @with_retry(
            max_attempts=3,
            base_delay=0.05,  # 50ms base delay
            jitter=False,
            retryable_exceptions=(ExternalServiceError,),
        )
        async def failing_func() -> str:
            nonlocal call_count
            start_times.append(time.monotonic())
            call_count += 1
            raise ExternalServiceError("Always fails", service_name="test")

        try:
            await failing_func()
        except ExternalServiceError:
            pass

        # Calculate actual delay between first two calls
        if len(start_times) >= 2:
            delay = start_times[1] - start_times[0]
            # Without jitter, delay should be approximately base_delay (0.05s)
            assert 0.04 <= delay <= 0.07, f"Delay {delay} should be close to 0.05s"

    @pytest.mark.asyncio
    async def test_exponential_backoff(self) -> None:
        """Test that delay increases exponentially with each attempt."""
        import time

        from backend.core.retry import with_retry

        call_count = 0
        start_times: list[float] = []

        @with_retry(
            max_attempts=4,
            base_delay=0.02,  # 20ms base delay
            exponential_base=2.0,
            jitter=False,
            max_delay=10.0,
            retryable_exceptions=(ExternalServiceError,),
        )
        async def failing_func() -> str:
            nonlocal call_count
            start_times.append(time.monotonic())
            call_count += 1
            raise ExternalServiceError("Always fails", service_name="test")

        try:
            await failing_func()
        except ExternalServiceError:
            pass

        # Calculate delays between attempts
        if len(start_times) >= 3:
            delay1 = start_times[1] - start_times[0]  # Should be ~0.02s
            delay2 = start_times[2] - start_times[1]  # Should be ~0.04s (2x)
            delay3 = start_times[3] - start_times[2]  # Should be ~0.08s (2x)

            # Each delay should roughly double (within timing variance)
            assert delay2 > delay1 * 1.5, f"delay2 ({delay2}) should be > 1.5 * delay1 ({delay1})"
            assert delay3 > delay2 * 1.5, f"delay3 ({delay3}) should be > 1.5 * delay2 ({delay2})"

    @pytest.mark.asyncio
    async def test_max_delay_caps_backoff(self) -> None:
        """Test that max_delay caps the exponential growth."""
        import time

        from backend.core.retry import with_retry

        call_count = 0
        start_times: list[float] = []

        @with_retry(
            max_attempts=5,
            base_delay=0.05,  # 50ms base delay
            exponential_base=4.0,  # Aggressive growth
            max_delay=0.1,  # Cap at 100ms
            jitter=False,
            retryable_exceptions=(ExternalServiceError,),
        )
        async def failing_func() -> str:
            nonlocal call_count
            start_times.append(time.monotonic())
            call_count += 1
            raise ExternalServiceError("Always fails", service_name="test")

        try:
            await failing_func()
        except ExternalServiceError:
            pass

        # Calculate delays - later delays should be capped at max_delay
        if len(start_times) >= 4:
            delay3 = start_times[3] - start_times[2]
            delay4 = start_times[4] - start_times[3]

            # Both should be capped at max_delay (0.1s)
            assert delay3 <= 0.15, f"delay3 ({delay3}) should be capped at ~0.1s"
            assert delay4 <= 0.15, f"delay4 ({delay4}) should be capped at ~0.1s"

    @pytest.mark.asyncio
    async def test_default_values(self) -> None:
        """Test that default values match NEM-1445 specification."""
        from backend.core.retry import with_retry

        # The decorator should work with just retryable_exceptions
        @with_retry(retryable_exceptions=(ExternalServiceError,))
        async def test_func() -> str:
            return "success"

        # Should be able to call without errors
        result = await test_func()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_preserves_function_metadata(self) -> None:
        """Test that decorator preserves function name and docstring."""
        from backend.core.retry import with_retry

        @with_retry(retryable_exceptions=(ExternalServiceError,))
        async def documented_function() -> str:
            """This function has documentation."""
            return "result"

        assert documented_function.__name__ == "documented_function"
        assert documented_function.__doc__ == "This function has documentation."

    @pytest.mark.asyncio
    async def test_preserves_function_arguments(self) -> None:
        """Test that function arguments are preserved across retries."""
        from backend.core.retry import with_retry

        call_count = 0
        received_args: list[tuple[int, str, dict]] = []

        @with_retry(
            max_attempts=3,
            base_delay=0.01,
            retryable_exceptions=(ExternalServiceError,),
        )
        async def func_with_args(x: int, y: str, z: dict) -> str:
            nonlocal call_count
            call_count += 1
            received_args.append((x, y, z.copy()))
            if call_count < 2:
                raise ExternalServiceError("Transient", service_name="test")
            return f"{x}-{y}-{z['key']}"

        result = await func_with_args(42, "test", {"key": "value"})

        assert result == "42-test-value"
        assert len(received_args) == 2
        assert all(args == (42, "test", {"key": "value"}) for args in received_args)

    @pytest.mark.asyncio
    async def test_single_attempt_with_max_attempts_one(self) -> None:
        """Test that max_attempts=1 means no retries, just one attempt."""
        from backend.core.retry import with_retry

        call_count = 0

        @with_retry(
            max_attempts=1,
            base_delay=0.01,
            retryable_exceptions=(ExternalServiceError,),
        )
        async def single_attempt() -> str:
            nonlocal call_count
            call_count += 1
            raise ExternalServiceError("Fails", service_name="test")

        with pytest.raises(ExternalServiceError):
            await single_attempt()

        # Only one attempt, no retries
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_on_retry_callback_receives_correct_exception(self) -> None:
        """Test that on_retry receives the actual exception that was raised."""
        from backend.core.retry import with_retry

        exceptions_received: list[Exception] = []

        def on_retry_callback(attempt: int, exc: Exception) -> None:
            exceptions_received.append(exc)

        call_count = 0

        @with_retry(
            max_attempts=3,
            base_delay=0.01,
            retryable_exceptions=(ExternalServiceError,),
            on_retry=on_retry_callback,
        )
        async def raises_specific_errors() -> str:
            nonlocal call_count
            call_count += 1
            raise ExternalServiceError(f"Error {call_count}", service_name="test")

        with pytest.raises(ExternalServiceError):
            await raises_specific_errors()

        # on_retry should be called 2 times (before retry 2 and 3)
        assert len(exceptions_received) == 2
        assert "Error 1" in str(exceptions_received[0])
        assert "Error 2" in str(exceptions_received[1])

    @pytest.mark.asyncio
    async def test_multiple_retryable_exception_types(self) -> None:
        """Test retry with multiple exception types in retryable_exceptions."""
        from backend.core.retry import with_retry

        call_count = 0

        @with_retry(
            max_attempts=4,
            base_delay=0.01,
            retryable_exceptions=(ExternalServiceError, DatabaseError),
        )
        async def alternating_errors() -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ExternalServiceError("Service error", service_name="test")
            if call_count == 2:
                raise DatabaseError("Database error")
            if call_count == 3:
                raise ExternalServiceError("Another service error", service_name="test")
            return "success"

        result = await alternating_errors()

        assert result == "success"
        assert call_count == 4
