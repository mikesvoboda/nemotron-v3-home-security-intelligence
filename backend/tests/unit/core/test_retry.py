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
    return DetectorUnavailableError("YOLO26 timeout")


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
