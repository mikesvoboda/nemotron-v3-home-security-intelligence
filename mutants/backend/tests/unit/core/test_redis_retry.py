"""Unit tests for Redis retry logic and exponential backoff.

Tests cover:
- with_retry() method - max retries exhaustion, different error types
- _calculate_backoff_delay() - jitter bounds, accuracy at various attempts
- Exponential backoff calculation
- Edge cases (zero/negative attempts, max retries, jitter bounds)

Uses mocks for Redis operations and time functions.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.exceptions import ConnectionError, RedisError, TimeoutError

from backend.core.redis import RedisClient

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def redis_client() -> RedisClient:
    """Create a RedisClient instance for testing.

    Returns a client with known backoff settings for predictable testing:
    - base_delay: 1.0 second
    - max_delay: 30.0 seconds
    - jitter_factor: 0.25 (0-25% of delay)
    - max_retries: 3
    """
    with patch("backend.core.redis.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            redis_url="redis://localhost:6379/0",
            redis_ssl_enabled=False,
            redis_ssl_cert_reqs="required",
            redis_ssl_ca_certs=None,
            redis_ssl_certfile=None,
            redis_ssl_keyfile=None,
            redis_ssl_check_hostname=True,
        )
        client = RedisClient()
        # Ensure known settings for tests
        client._base_delay = 1.0
        client._max_delay = 30.0
        client._jitter_factor = 0.25
        client._max_retries = 3
        return client


# =============================================================================
# _calculate_backoff_delay Tests
# =============================================================================


class TestCalculateBackoffDelay:
    """Tests for _calculate_backoff_delay method."""

    def test_backoff_delay_attempt_1(self, redis_client: RedisClient) -> None:
        """Test delay calculation for first attempt.

        With base_delay=1.0 and attempt=1:
        - Base delay: 1.0 * 2^(1-1) = 1.0 * 1 = 1.0
        - Jitter range: 0 to 0.25 (25% of 1.0)
        - Expected: 1.0 to 1.25
        """
        # Mock random to return 0 for deterministic testing (no jitter)
        with patch("backend.core.redis.random.uniform", return_value=0):
            delay = redis_client._calculate_backoff_delay(1)
            assert delay == 1.0

    def test_backoff_delay_attempt_2(self, redis_client: RedisClient) -> None:
        """Test delay calculation for second attempt.

        With base_delay=1.0 and attempt=2:
        - Base delay: 1.0 * 2^(2-1) = 1.0 * 2 = 2.0
        - Jitter range: 0 to 0.5 (25% of 2.0)
        - Expected: 2.0 to 2.5
        """
        with patch("backend.core.redis.random.uniform", return_value=0):
            delay = redis_client._calculate_backoff_delay(2)
            assert delay == 2.0

    def test_backoff_delay_attempt_3(self, redis_client: RedisClient) -> None:
        """Test delay calculation for third attempt.

        With base_delay=1.0 and attempt=3:
        - Base delay: 1.0 * 2^(3-1) = 1.0 * 4 = 4.0
        - Jitter range: 0 to 1.0 (25% of 4.0)
        - Expected: 4.0 to 5.0
        """
        with patch("backend.core.redis.random.uniform", return_value=0):
            delay = redis_client._calculate_backoff_delay(3)
            assert delay == 4.0

    def test_backoff_delay_attempt_4(self, redis_client: RedisClient) -> None:
        """Test delay calculation for fourth attempt.

        With base_delay=1.0 and attempt=4:
        - Base delay: 1.0 * 2^(4-1) = 1.0 * 8 = 8.0
        - Jitter range: 0 to 2.0 (25% of 8.0)
        - Expected: 8.0 to 10.0
        """
        with patch("backend.core.redis.random.uniform", return_value=0):
            delay = redis_client._calculate_backoff_delay(4)
            assert delay == 8.0

    def test_backoff_delay_capped_at_max(self, redis_client: RedisClient) -> None:
        """Test that delay is capped at max_delay.

        With base_delay=1.0, max_delay=30.0, and attempt=6:
        - Calculated delay: 1.0 * 2^(6-1) = 1.0 * 32 = 32.0
        - Capped at: 30.0
        - Jitter range: 0 to 7.5 (25% of 30.0)
        - Expected: 30.0 to 37.5
        """
        with patch("backend.core.redis.random.uniform", return_value=0):
            delay = redis_client._calculate_backoff_delay(6)
            assert delay == 30.0

    def test_backoff_delay_very_high_attempt_still_capped(self, redis_client: RedisClient) -> None:
        """Test that very high attempt numbers are still capped at max_delay."""
        with patch("backend.core.redis.random.uniform", return_value=0):
            delay = redis_client._calculate_backoff_delay(100)
            assert delay == 30.0

    def test_jitter_adds_randomness(self, redis_client: RedisClient) -> None:
        """Test that jitter adds randomness to delay.

        With base_delay=1.0, attempt=1, and jitter_factor=0.25:
        - Base delay: 1.0
        - Maximum jitter: 1.0 * 0.25 = 0.25
        - With max jitter: 1.0 + 0.25 = 1.25
        """
        # Test with maximum jitter
        with patch("backend.core.redis.random.uniform", return_value=0.25):
            delay = redis_client._calculate_backoff_delay(1)
            assert delay == 1.25

    def test_jitter_at_max_delay(self, redis_client: RedisClient) -> None:
        """Test jitter calculation when base delay is capped at max_delay.

        With max_delay=30.0 and jitter_factor=0.25:
        - Capped delay: 30.0
        - Maximum jitter: 30.0 * 0.25 = 7.5
        - With max jitter: 30.0 + 7.5 = 37.5
        """
        with patch("backend.core.redis.random.uniform", return_value=0.25):
            delay = redis_client._calculate_backoff_delay(10)
            assert delay == 37.5

    def test_jitter_within_expected_bounds(self, redis_client: RedisClient) -> None:
        """Test that jitter values fall within expected bounds.

        Run multiple calculations and verify all results are within
        the expected range: [base_delay, base_delay + base_delay * jitter_factor]
        """
        # Don't mock random for this test - use real randomness
        base_delay = 1.0
        jitter_factor = 0.25
        min_expected = base_delay
        max_expected = base_delay + (base_delay * jitter_factor)

        for _ in range(100):
            delay = redis_client._calculate_backoff_delay(1)
            assert min_expected <= delay <= max_expected, (
                f"Delay {delay} not in range [{min_expected}, {max_expected}]"
            )

    def test_jitter_bounds_at_higher_attempts(self, redis_client: RedisClient) -> None:
        """Test jitter bounds at attempt 3 (delay=4.0).

        With base_delay=1.0, attempt=3:
        - Base delay: 4.0
        - Jitter range: 0 to 1.0
        - Expected range: [4.0, 5.0]
        """
        base_delay_attempt_3 = 4.0
        jitter_factor = 0.25
        min_expected = base_delay_attempt_3
        max_expected = base_delay_attempt_3 + (base_delay_attempt_3 * jitter_factor)

        for _ in range(100):
            delay = redis_client._calculate_backoff_delay(3)
            assert min_expected <= delay <= max_expected, (
                f"Delay {delay} not in range [{min_expected}, {max_expected}]"
            )

    def test_zero_attempt_number(self, redis_client: RedisClient) -> None:
        """Test behavior with zero attempt number.

        With attempt=0:
        - Base delay: 1.0 * 2^(0-1) = 1.0 * 0.5 = 0.5
        - This is a mathematical result, not necessarily intended behavior
        """
        with patch("backend.core.redis.random.uniform", return_value=0):
            delay = redis_client._calculate_backoff_delay(0)
            assert delay == 0.5

    def test_negative_attempt_number(self, redis_client: RedisClient) -> None:
        """Test behavior with negative attempt number.

        With attempt=-1:
        - Base delay: 1.0 * 2^(-1-1) = 1.0 * 2^-2 = 1.0 * 0.25 = 0.25
        - This is a mathematical result, not necessarily intended behavior
        """
        with patch("backend.core.redis.random.uniform", return_value=0):
            delay = redis_client._calculate_backoff_delay(-1)
            assert delay == 0.25


# =============================================================================
# with_retry Tests
# =============================================================================


class TestWithRetry:
    """Tests for with_retry method."""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self, redis_client: RedisClient) -> None:
        """Test that successful operation returns immediately."""
        operation = AsyncMock(return_value="success")

        result = await redis_client.with_retry(operation, "test_operation")

        assert result == "success"
        operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_success_after_retry(self, redis_client: RedisClient) -> None:
        """Test that operation succeeds after transient failure."""
        operation = AsyncMock(side_effect=[ConnectionError("fail"), "success"])

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await redis_client.with_retry(operation, "test_operation")

        assert result == "success"
        assert operation.call_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exhausted_connection_error(self, redis_client: RedisClient) -> None:
        """Test that ConnectionError is raised after max retries exhausted."""
        error = ConnectionError("connection failed")
        operation = AsyncMock(side_effect=error)

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(ConnectionError) as exc_info,
        ):
            await redis_client.with_retry(operation, "test_operation")

        assert "connection failed" in str(exc_info.value)
        assert operation.call_count == 3  # Default max_retries

    @pytest.mark.asyncio
    async def test_max_retries_exhausted_timeout_error(self, redis_client: RedisClient) -> None:
        """Test that TimeoutError is raised after max retries exhausted."""
        error = TimeoutError("operation timed out")
        operation = AsyncMock(side_effect=error)

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(TimeoutError) as exc_info,
        ):
            await redis_client.with_retry(operation, "test_operation")

        assert "operation timed out" in str(exc_info.value)
        assert operation.call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exhausted_redis_error(self, redis_client: RedisClient) -> None:
        """Test that RedisError is raised after max retries exhausted."""
        error = RedisError("redis error")
        operation = AsyncMock(side_effect=error)

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(RedisError) as exc_info,
        ):
            await redis_client.with_retry(operation, "test_operation")

        assert "redis error" in str(exc_info.value)
        assert operation.call_count == 3

    @pytest.mark.asyncio
    async def test_custom_max_retries(self, redis_client: RedisClient) -> None:
        """Test that custom max_retries is respected."""
        error = ConnectionError("fail")
        operation = AsyncMock(side_effect=error)

        with patch("asyncio.sleep", new_callable=AsyncMock), pytest.raises(ConnectionError):
            await redis_client.with_retry(operation, "test_operation", max_retries=5)

        assert operation.call_count == 5

    @pytest.mark.asyncio
    async def test_custom_max_retries_one(self, redis_client: RedisClient) -> None:
        """Test with max_retries=1 (no retries)."""
        error = ConnectionError("fail")
        operation = AsyncMock(side_effect=error)

        with pytest.raises(ConnectionError):
            await redis_client.with_retry(operation, "test_operation", max_retries=1)

        assert operation.call_count == 1

    @pytest.mark.asyncio
    async def test_backoff_delay_called_between_retries(self, redis_client: RedisClient) -> None:
        """Test that exponential backoff delays are applied between retries."""
        operation = AsyncMock(side_effect=[ConnectionError("fail")] * 2 + ["success"])
        sleep_mock = AsyncMock()

        with patch("asyncio.sleep", sleep_mock):
            result = await redis_client.with_retry(operation, "test_operation")

        assert result == "success"
        assert operation.call_count == 3
        # Sleep should be called twice (after first and second failure)
        assert sleep_mock.call_count == 2
        # Verify backoff delays are increasing (accounting for jitter)
        first_delay = sleep_mock.call_args_list[0][0][0]
        second_delay = sleep_mock.call_args_list[1][0][0]
        # First delay should be ~1.0-1.25, second ~2.0-2.5
        assert 1.0 <= first_delay <= 1.25
        assert 2.0 <= second_delay <= 2.5

    @pytest.mark.asyncio
    async def test_no_sleep_after_last_attempt(self, redis_client: RedisClient) -> None:
        """Test that no sleep occurs after the final failed attempt."""
        operation = AsyncMock(side_effect=ConnectionError("fail"))
        sleep_mock = AsyncMock()

        with patch("asyncio.sleep", sleep_mock), pytest.raises(ConnectionError):
            await redis_client.with_retry(operation, "test_operation", max_retries=3)

        # With 3 retries, sleep should only be called twice (between attempts)
        assert sleep_mock.call_count == 2

    @pytest.mark.asyncio
    async def test_non_retryable_error_propagates_immediately(
        self, redis_client: RedisClient
    ) -> None:
        """Test that non-retryable errors (e.g., ValueError) propagate immediately."""
        error = ValueError("invalid value")
        operation = AsyncMock(side_effect=error)

        with pytest.raises(ValueError) as exc_info:
            await redis_client.with_retry(operation, "test_operation")

        assert "invalid value" in str(exc_info.value)
        # Only one call - no retry for non-Redis errors
        operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_different_error_types_sequence(self, redis_client: RedisClient) -> None:
        """Test retry handling with different Redis error types in sequence."""
        operation = AsyncMock(
            side_effect=[
                ConnectionError("connection lost"),
                TimeoutError("timeout"),
                "success",
            ]
        )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await redis_client.with_retry(operation, "test_operation")

        assert result == "success"
        assert operation.call_count == 3

    @pytest.mark.asyncio
    async def test_last_error_is_raised(self, redis_client: RedisClient) -> None:
        """Test that the last error is raised when all retries are exhausted."""
        operation = AsyncMock(
            side_effect=[
                ConnectionError("first error"),
                TimeoutError("second error"),
                RedisError("last error"),
            ]
        )

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(RedisError) as exc_info,
        ):
            await redis_client.with_retry(operation, "test_operation")

        assert "last error" in str(exc_info.value)


# =============================================================================
# Integration Tests - Retry with Real Backoff Calculation
# =============================================================================


class TestRetryIntegration:
    """Integration tests combining with_retry and backoff calculation."""

    @pytest.mark.asyncio
    async def test_retry_with_actual_backoff_values(self, redis_client: RedisClient) -> None:
        """Test that actual backoff values are used during retry."""
        operation = AsyncMock(side_effect=[ConnectionError("fail")] * 2 + ["success"])
        sleep_calls: list[float] = []

        async def capture_sleep(delay: float) -> None:
            sleep_calls.append(delay)

        with patch("asyncio.sleep", capture_sleep):
            result = await redis_client.with_retry(operation, "test_operation")

        assert result == "success"
        assert len(sleep_calls) == 2

        # First sleep should be base_delay (1.0) + jitter (0-0.25)
        assert 1.0 <= sleep_calls[0] <= 1.25

        # Second sleep should be 2*base_delay (2.0) + jitter (0-0.5)
        assert 2.0 <= sleep_calls[1] <= 2.5

    @pytest.mark.asyncio
    async def test_retry_respects_max_delay_cap(self, redis_client: RedisClient) -> None:
        """Test that backoff delay is capped at max_delay during retries."""
        # Set very high base delay to test capping
        redis_client._base_delay = 50.0
        redis_client._max_delay = 30.0
        redis_client._max_retries = 2

        operation = AsyncMock(side_effect=[ConnectionError("fail"), "success"])
        sleep_calls: list[float] = []

        async def capture_sleep(delay: float) -> None:
            sleep_calls.append(delay)

        with patch("asyncio.sleep", capture_sleep):
            result = await redis_client.with_retry(operation, "test_operation")

        assert result == "success"
        assert len(sleep_calls) == 1
        # Delay should be capped at max_delay (30.0) + jitter (0-7.5)
        assert 30.0 <= sleep_calls[0] <= 37.5


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Edge case tests for retry logic."""

    @pytest.mark.asyncio
    async def test_zero_max_retries(self, redis_client: RedisClient) -> None:
        """Test behavior with max_retries=0 (no attempts).

        With max_retries=0, range(1, 0+1) = range(1, 1) = empty range.
        The operation is never called and RuntimeError is raised.
        """
        operation = AsyncMock(return_value="success")

        # Note: This is edge case behavior - with 0 retries, the operation
        # is never attempted, and RuntimeError is raised due to last_error being None
        with pytest.raises(RuntimeError) as exc_info:
            await redis_client.with_retry(operation, "test_operation", max_retries=0)

        assert "failed without error" in str(exc_info.value)
        operation.assert_not_called()

    @pytest.mark.asyncio
    async def test_operation_name_in_logging(self, redis_client: RedisClient) -> None:
        """Test that operation_name is used in logging."""
        operation = AsyncMock(side_effect=ConnectionError("fail"))

        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("backend.core.redis.logger") as mock_logger,
            pytest.raises(ConnectionError),
        ):
            await redis_client.with_retry(operation, "custom_op_name")

        # Verify operation name appears in log calls
        warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
        error_calls = [str(call) for call in mock_logger.error.call_args_list]

        assert any("custom_op_name" in call for call in warning_calls)
        assert any("custom_op_name" in call for call in error_calls)

    @pytest.mark.asyncio
    async def test_uses_default_max_retries_when_none(self, redis_client: RedisClient) -> None:
        """Test that default _max_retries is used when max_retries=None."""
        operation = AsyncMock(side_effect=ConnectionError("fail"))
        redis_client._max_retries = 4  # Set custom default

        with patch("asyncio.sleep", new_callable=AsyncMock), pytest.raises(ConnectionError):
            await redis_client.with_retry(operation, "test_operation", max_retries=None)

        assert operation.call_count == 4

    @pytest.mark.asyncio
    async def test_retry_wrapper_methods_use_with_retry(self, redis_client: RedisClient) -> None:
        """Test that retry wrapper methods delegate to with_retry."""
        redis_client._client = MagicMock()
        mock_with_retry = AsyncMock(return_value="result")

        with patch.object(redis_client, "with_retry", mock_with_retry):
            # Test get_from_queue_with_retry
            await redis_client.get_from_queue_with_retry("test_queue", timeout=5)
            assert mock_with_retry.called
            mock_with_retry.reset_mock()

            # Test get_queue_length_with_retry
            await redis_client.get_queue_length_with_retry("test_queue")
            assert mock_with_retry.called
            mock_with_retry.reset_mock()

            # Test get_with_retry
            await redis_client.get_with_retry("test_key")
            assert mock_with_retry.called
            mock_with_retry.reset_mock()

            # Test set_with_retry
            await redis_client.set_with_retry("test_key", "test_value", expire=60)
            assert mock_with_retry.called


class TestBackoffConfiguration:
    """Tests for backoff configuration parameters."""

    def test_default_backoff_settings(self) -> None:
        """Test that default backoff settings are applied."""
        with patch("backend.core.redis.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                redis_url="redis://localhost:6379/0",
                redis_ssl_enabled=False,
                redis_ssl_cert_reqs="required",
                redis_ssl_ca_certs=None,
                redis_ssl_certfile=None,
                redis_ssl_keyfile=None,
                redis_ssl_check_hostname=True,
            )
            client = RedisClient()

            assert client._max_retries == 3
            assert client._base_delay == 1.0
            assert client._max_delay == 30.0
            assert client._jitter_factor == 0.25

    def test_custom_backoff_settings(self) -> None:
        """Test that backoff settings can be customized."""
        with patch("backend.core.redis.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                redis_url="redis://localhost:6379/0",
                redis_ssl_enabled=False,
                redis_ssl_cert_reqs="required",
                redis_ssl_ca_certs=None,
                redis_ssl_certfile=None,
                redis_ssl_keyfile=None,
                redis_ssl_check_hostname=True,
            )
            client = RedisClient()

            # Modify settings
            client._max_retries = 5
            client._base_delay = 2.0
            client._max_delay = 60.0
            client._jitter_factor = 0.1

            # Verify changes
            assert client._max_retries == 5
            assert client._base_delay == 2.0
            assert client._max_delay == 60.0
            assert client._jitter_factor == 0.1

            # Verify backoff calculation uses new settings
            with patch("backend.core.redis.random.uniform", return_value=0):
                delay = client._calculate_backoff_delay(1)
                assert delay == 2.0  # base_delay

                delay = client._calculate_backoff_delay(2)
                assert delay == 4.0  # 2.0 * 2^1

                delay = client._calculate_backoff_delay(10)
                assert delay == 60.0  # Capped at max_delay
