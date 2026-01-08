"""Unit tests for retry handler with exponential backoff and DLQ.

Tests cover:
- RetryConfig exponential backoff calculations
- RetryHandler.with_retry() success and failure scenarios
- DLQ operations (move, get, clear, requeue)
- Integration with Redis client
- DLQ circuit breaker functionality
- Error handling and edge cases
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.redis import QueueAddResult
from backend.services.retry_handler import (
    DLQStats,
    JobFailure,
    RetryConfig,
    RetryHandler,
    RetryResult,
    get_retry_handler,
    reset_retry_handler,
)

# =============================================================================
# RetryConfig Tests
# =============================================================================


class TestRetryConfig:
    """Tests for RetryConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.base_delay_seconds == 1.0
        assert config.max_delay_seconds == 30.0
        assert config.exponential_base == 2.0
        assert config.jitter is True

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = RetryConfig(
            max_retries=5,
            base_delay_seconds=0.5,
            max_delay_seconds=60.0,
            exponential_base=3.0,
            jitter=False,
        )
        assert config.max_retries == 5
        assert config.base_delay_seconds == 0.5
        assert config.max_delay_seconds == 60.0
        assert config.exponential_base == 3.0
        assert config.jitter is False

    def test_get_delay_exponential_backoff_no_jitter(self) -> None:
        """Test exponential backoff calculation without jitter."""
        config = RetryConfig(
            base_delay_seconds=1.0,
            exponential_base=2.0,
            jitter=False,
        )
        # attempt 1: 1 * 2^0 = 1
        assert config.get_delay(1) == 1.0
        # attempt 2: 1 * 2^1 = 2
        assert config.get_delay(2) == 2.0
        # attempt 3: 1 * 2^2 = 4
        assert config.get_delay(3) == 4.0
        # attempt 4: 1 * 2^3 = 8
        assert config.get_delay(4) == 8.0

    def test_get_delay_respects_max_delay(self) -> None:
        """Test that delay is capped at max_delay_seconds."""
        config = RetryConfig(
            base_delay_seconds=1.0,
            max_delay_seconds=5.0,
            exponential_base=2.0,
            jitter=False,
        )
        # attempt 5: 1 * 2^4 = 16, but capped at 5
        assert config.get_delay(5) == 5.0

    def test_get_delay_with_jitter(self) -> None:
        """Test that jitter adds variation to delay."""
        config = RetryConfig(
            base_delay_seconds=1.0,
            exponential_base=2.0,
            jitter=True,
        )
        # With jitter, delay should be between base and base * 1.25
        delays = [config.get_delay(1) for _ in range(10)]
        # All delays should be >= base (1.0) and <= base * 1.25 (1.25)
        for delay in delays:
            assert delay >= 1.0
            assert delay <= 1.25

    def test_get_delay_with_custom_base(self) -> None:
        """Test exponential backoff with custom base."""
        config = RetryConfig(
            base_delay_seconds=0.5,
            exponential_base=3.0,
            jitter=False,
        )
        # attempt 1: 0.5 * 3^0 = 0.5
        assert config.get_delay(1) == 0.5
        # attempt 2: 0.5 * 3^1 = 1.5
        assert config.get_delay(2) == 1.5
        # attempt 3: 0.5 * 3^2 = 4.5
        assert config.get_delay(3) == 4.5


# =============================================================================
# JobFailure Tests
# =============================================================================


class TestJobFailure:
    """Tests for JobFailure dataclass."""

    def test_to_dict(self) -> None:
        """Test conversion to dictionary."""
        failure = JobFailure(
            original_job={"camera_id": "cam1", "file_path": "/path/to/image.jpg"},
            error="Connection refused",
            attempt_count=3,
            first_failed_at="2025-12-23T10:00:00",
            last_failed_at="2025-12-23T10:00:15",
            queue_name="detection_queue",
        )
        result = failure.to_dict()
        assert result["original_job"] == {"camera_id": "cam1", "file_path": "/path/to/image.jpg"}
        assert result["error"] == "Connection refused"
        assert result["attempt_count"] == 3
        assert result["first_failed_at"] == "2025-12-23T10:00:00"
        assert result["last_failed_at"] == "2025-12-23T10:00:15"
        assert result["queue_name"] == "detection_queue"

    def test_from_dict(self) -> None:
        """Test creation from dictionary."""
        data = {
            "original_job": {"camera_id": "cam1"},
            "error": "Timeout",
            "attempt_count": 2,
            "first_failed_at": "2025-12-23T10:00:00",
            "last_failed_at": "2025-12-23T10:00:10",
            "queue_name": "analysis_queue",
        }
        failure = JobFailure.from_dict(data)
        assert failure.original_job == {"camera_id": "cam1"}
        assert failure.error == "Timeout"
        assert failure.attempt_count == 2
        assert failure.queue_name == "analysis_queue"


# =============================================================================
# DLQStats Tests
# =============================================================================


class TestDLQStats:
    """Tests for DLQStats dataclass."""

    def test_default_values(self) -> None:
        """Test default stats values."""
        stats = DLQStats()
        assert stats.detection_queue_count == 0
        assert stats.analysis_queue_count == 0
        assert stats.total_count == 0

    def test_custom_values(self) -> None:
        """Test custom stats values."""
        stats = DLQStats(
            detection_queue_count=5,
            analysis_queue_count=3,
            total_count=8,
        )
        assert stats.detection_queue_count == 5
        assert stats.analysis_queue_count == 3
        assert stats.total_count == 8


# =============================================================================
# RetryResult Tests
# =============================================================================


class TestRetryResult:
    """Tests for RetryResult dataclass."""

    def test_success_result(self) -> None:
        """Test successful result."""
        result = RetryResult(
            success=True,
            result={"data": "value"},
            attempts=1,
        )
        assert result.success is True
        assert result.result == {"data": "value"}
        assert result.error is None
        assert result.attempts == 1
        assert result.moved_to_dlq is False

    def test_failure_result(self) -> None:
        """Test failure result."""
        result = RetryResult(
            success=False,
            error="Connection refused",
            attempts=3,
            moved_to_dlq=True,
        )
        assert result.success is False
        assert result.result is None
        assert result.error == "Connection refused"
        assert result.attempts == 3
        assert result.moved_to_dlq is True


# =============================================================================
# RetryHandler Tests
# =============================================================================


class TestRetryHandler:
    """Tests for RetryHandler class."""

    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        """Create a mock Redis client."""
        redis = MagicMock()
        redis.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(success=True, queue_length=1)
        )
        redis.get_from_queue = AsyncMock(return_value=None)
        redis.pop_from_queue_nonblocking = AsyncMock(return_value=None)
        redis.get_queue_length = AsyncMock(return_value=0)
        redis.peek_queue = AsyncMock(return_value=[])
        redis.clear_queue = AsyncMock(return_value=True)
        return redis

    @pytest.fixture
    def handler(self, mock_redis: MagicMock) -> RetryHandler:
        """Create a retry handler with mock Redis."""
        config = RetryConfig(
            max_retries=3,
            base_delay_seconds=0.01,  # Fast for testing
            jitter=False,
        )
        return RetryHandler(redis_client=mock_redis, config=config)

    def test_init_default_config(self) -> None:
        """Test initialization with default config."""
        handler = RetryHandler()
        assert handler.config.max_retries == 3
        assert handler._redis is None

    def test_init_custom_config(self, mock_redis: MagicMock) -> None:
        """Test initialization with custom config."""
        config = RetryConfig(max_retries=5)
        handler = RetryHandler(redis_client=mock_redis, config=config)
        assert handler.config.max_retries == 5
        assert handler._redis is mock_redis

    def test_get_dlq_name(self, handler: RetryHandler) -> None:
        """Test DLQ name generation."""
        assert handler._get_dlq_name("detection_queue") == "dlq:detection_queue"
        assert handler._get_dlq_name("analysis_queue") == "dlq:analysis_queue"
        # Already has prefix
        assert handler._get_dlq_name("dlq:detection_queue") == "dlq:detection_queue"

    def test_config_property(self, handler: RetryHandler) -> None:
        """Test config property returns the configuration."""
        config = handler.config
        assert config.max_retries == 3
        assert config.base_delay_seconds == 0.01

    @pytest.mark.asyncio
    async def test_with_retry_success_first_attempt(self, handler: RetryHandler) -> None:
        """Test successful operation on first attempt."""

        async def success_op() -> str:
            return "success"

        result = await handler.with_retry(
            operation=success_op,
            job_data={"camera_id": "cam1"},
            queue_name="detection_queue",
        )

        assert result.success is True
        assert result.result == "success"
        assert result.attempts == 1
        assert result.error is None
        assert result.moved_to_dlq is False

    @pytest.mark.asyncio
    async def test_with_retry_success_after_failures(self, handler: RetryHandler) -> None:
        """Test successful operation after initial failures."""
        attempt_count = 0

        async def eventually_success() -> str:
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ConnectionError("Simulated failure")
            return "success"

        result = await handler.with_retry(
            operation=eventually_success,
            job_data={"camera_id": "cam1"},
            queue_name="detection_queue",
        )

        assert result.success is True
        assert result.result == "success"
        assert result.attempts == 3
        assert result.error is None

    @pytest.mark.asyncio
    async def test_with_retry_all_attempts_fail(
        self, handler: RetryHandler, mock_redis: MagicMock
    ) -> None:
        """Test all retry attempts fail - job moved to DLQ."""

        async def always_fail() -> str:
            raise ConnectionError("Always fails")

        result = await handler.with_retry(
            operation=always_fail,
            job_data={"camera_id": "cam1", "file_path": "/path/image.jpg"},
            queue_name="detection_queue",
        )

        assert result.success is False
        assert result.result is None
        assert result.attempts == 3
        assert result.error == "Always fails"
        assert result.moved_to_dlq is True

        # Verify DLQ was called - now uses add_to_queue_safe
        mock_redis.add_to_queue_safe.assert_called_once()
        call_args = mock_redis.add_to_queue_safe.call_args
        assert call_args[0][0] == "dlq:detection_queue"

    @pytest.mark.asyncio
    async def test_with_retry_no_redis_no_dlq(self) -> None:
        """Test that without Redis, job cannot be moved to DLQ."""
        config = RetryConfig(max_retries=2, base_delay_seconds=0.01, jitter=False)
        handler = RetryHandler(redis_client=None, config=config)

        async def always_fail() -> str:
            raise RuntimeError("Failure")

        result = await handler.with_retry(
            operation=always_fail,
            job_data={"camera_id": "cam1"},
            queue_name="detection_queue",
        )

        assert result.success is False
        assert result.moved_to_dlq is False

    @pytest.mark.asyncio
    async def test_with_retry_passes_args_kwargs(self, handler: RetryHandler) -> None:
        """Test that args and kwargs are passed to the operation."""

        async def op_with_args(x: int, y: str, z: bool = False) -> dict:
            return {"x": x, "y": y, "z": z}

        result = await handler.with_retry(
            op_with_args,
            {},
            "detection_queue",
            42,
            "hello",
            z=True,
        )

        assert result.success is True
        assert result.result == {"x": 42, "y": "hello", "z": True}

    @pytest.mark.asyncio
    async def test_get_dlq_stats(self, handler: RetryHandler, mock_redis: MagicMock) -> None:
        """Test getting DLQ statistics."""
        mock_redis.get_queue_length = AsyncMock(side_effect=[5, 3])

        stats = await handler.get_dlq_stats()

        assert stats.detection_queue_count == 5
        assert stats.analysis_queue_count == 3
        assert stats.total_count == 8

    @pytest.mark.asyncio
    async def test_get_dlq_stats_no_redis(self) -> None:
        """Test DLQ stats without Redis returns zeros."""
        handler = RetryHandler(redis_client=None)
        stats = await handler.get_dlq_stats()

        assert stats.detection_queue_count == 0
        assert stats.analysis_queue_count == 0
        assert stats.total_count == 0

    @pytest.mark.asyncio
    async def test_get_dlq_stats_exception(
        self, handler: RetryHandler, mock_redis: MagicMock
    ) -> None:
        """Test DLQ stats returns empty stats on exception."""
        mock_redis.get_queue_length = AsyncMock(side_effect=RuntimeError("Redis error"))

        stats = await handler.get_dlq_stats()

        assert stats.detection_queue_count == 0
        assert stats.analysis_queue_count == 0
        assert stats.total_count == 0

    @pytest.mark.asyncio
    async def test_get_dlq_jobs(self, handler: RetryHandler, mock_redis: MagicMock) -> None:
        """Test getting jobs from DLQ."""
        mock_redis.peek_queue = AsyncMock(
            return_value=[
                {
                    "original_job": {"camera_id": "cam1"},
                    "error": "Error 1",
                    "attempt_count": 3,
                    "first_failed_at": "2025-12-23T10:00:00",
                    "last_failed_at": "2025-12-23T10:00:15",
                    "queue_name": "detection_queue",
                },
                {
                    "original_job": {"camera_id": "cam2"},
                    "error": "Error 2",
                    "attempt_count": 3,
                    "first_failed_at": "2025-12-23T11:00:00",
                    "last_failed_at": "2025-12-23T11:00:15",
                    "queue_name": "detection_queue",
                },
            ]
        )

        jobs = await handler.get_dlq_jobs("dlq:detection_queue")

        assert len(jobs) == 2
        assert jobs[0].original_job == {"camera_id": "cam1"}
        assert jobs[0].error == "Error 1"
        assert jobs[1].original_job == {"camera_id": "cam2"}

    @pytest.mark.asyncio
    async def test_get_dlq_jobs_with_range(
        self, handler: RetryHandler, mock_redis: MagicMock
    ) -> None:
        """Test getting jobs from DLQ with start and end range."""
        mock_redis.peek_queue = AsyncMock(return_value=[])

        await handler.get_dlq_jobs("dlq:detection_queue", start=5, end=10)

        mock_redis.peek_queue.assert_called_once_with("dlq:detection_queue", 5, 10)

    @pytest.mark.asyncio
    async def test_get_dlq_jobs_no_redis(self) -> None:
        """Test getting DLQ jobs without Redis returns empty list."""
        handler = RetryHandler(redis_client=None)
        jobs = await handler.get_dlq_jobs("dlq:detection_queue")
        assert jobs == []

    @pytest.mark.asyncio
    async def test_get_dlq_jobs_exception(
        self, handler: RetryHandler, mock_redis: MagicMock
    ) -> None:
        """Test DLQ jobs returns empty list on exception."""
        mock_redis.peek_queue = AsyncMock(side_effect=RuntimeError("Redis error"))

        jobs = await handler.get_dlq_jobs("dlq:detection_queue")

        assert jobs == []

    @pytest.mark.asyncio
    async def test_requeue_dlq_job(self, handler: RetryHandler, mock_redis: MagicMock) -> None:
        """Test requeuing a job from DLQ."""
        mock_redis.pop_from_queue_nonblocking = AsyncMock(
            return_value={
                "original_job": {"camera_id": "cam1", "file_path": "/path"},
                "error": "Error",
                "attempt_count": 3,
                "first_failed_at": "2025-12-23T10:00:00",
                "last_failed_at": "2025-12-23T10:00:15",
                "queue_name": "detection_queue",
            }
        )

        job = await handler.requeue_dlq_job("dlq:detection_queue")

        assert job == {"camera_id": "cam1", "file_path": "/path"}
        mock_redis.pop_from_queue_nonblocking.assert_called_once_with("dlq:detection_queue")

    @pytest.mark.asyncio
    async def test_requeue_dlq_job_empty(
        self, handler: RetryHandler, mock_redis: MagicMock
    ) -> None:
        """Test requeuing from empty DLQ returns None."""
        mock_redis.pop_from_queue_nonblocking = AsyncMock(return_value=None)

        job = await handler.requeue_dlq_job("dlq:detection_queue")

        assert job is None

    @pytest.mark.asyncio
    async def test_requeue_dlq_job_no_redis(self) -> None:
        """Test requeuing DLQ job without Redis returns None."""
        handler = RetryHandler(redis_client=None)
        job = await handler.requeue_dlq_job("dlq:detection_queue")
        assert job is None

    @pytest.mark.asyncio
    async def test_requeue_dlq_job_exception(
        self, handler: RetryHandler, mock_redis: MagicMock
    ) -> None:
        """Test requeue_dlq_job returns None on exception."""
        mock_redis.pop_from_queue_nonblocking = AsyncMock(side_effect=RuntimeError("Redis error"))

        job = await handler.requeue_dlq_job("dlq:detection_queue")

        assert job is None

    @pytest.mark.asyncio
    async def test_clear_dlq(self, handler: RetryHandler, mock_redis: MagicMock) -> None:
        """Test clearing a DLQ."""
        mock_redis.clear_queue = AsyncMock(return_value=True)

        success = await handler.clear_dlq("dlq:detection_queue")

        assert success is True
        mock_redis.clear_queue.assert_called_once_with("dlq:detection_queue")

    @pytest.mark.asyncio
    async def test_clear_dlq_no_redis(self) -> None:
        """Test clearing DLQ without Redis returns False."""
        handler = RetryHandler(redis_client=None)
        success = await handler.clear_dlq("dlq:detection_queue")
        assert success is False

    @pytest.mark.asyncio
    async def test_clear_dlq_exception(self, handler: RetryHandler, mock_redis: MagicMock) -> None:
        """Test clear_dlq returns False on exception."""
        mock_redis.clear_queue = AsyncMock(side_effect=RuntimeError("Redis error"))

        success = await handler.clear_dlq("dlq:detection_queue")

        assert success is False

    @pytest.mark.asyncio
    async def test_move_dlq_job_to_queue(
        self, handler: RetryHandler, mock_redis: MagicMock
    ) -> None:
        """Test moving a job from DLQ back to processing queue."""
        mock_redis.pop_from_queue_nonblocking = AsyncMock(
            return_value={
                "original_job": {"camera_id": "cam1"},
                "error": "Error",
                "attempt_count": 3,
                "first_failed_at": "2025-12-23T10:00:00",
                "last_failed_at": "2025-12-23T10:00:15",
                "queue_name": "detection_queue",
            }
        )

        success = await handler.move_dlq_job_to_queue("dlq:detection_queue", "detection_queue")

        assert success is True
        # Now uses add_to_queue_safe instead of add_to_queue
        mock_redis.add_to_queue_safe.assert_called()
        # Verify the queue name and job data
        call_args = mock_redis.add_to_queue_safe.call_args
        assert call_args[0][0] == "detection_queue"
        assert call_args[0][1] == {"camera_id": "cam1"}

    @pytest.mark.asyncio
    async def test_move_dlq_job_empty_queue(
        self, handler: RetryHandler, mock_redis: MagicMock
    ) -> None:
        """Test moving from empty DLQ returns False."""
        mock_redis.pop_from_queue_nonblocking = AsyncMock(return_value=None)

        success = await handler.move_dlq_job_to_queue("dlq:detection_queue", "detection_queue")

        assert success is False

    @pytest.mark.asyncio
    async def test_move_dlq_job_to_queue_no_redis(self) -> None:
        """Test moving DLQ job without Redis returns False."""
        handler = RetryHandler(redis_client=None)
        success = await handler.move_dlq_job_to_queue("dlq:detection_queue", "detection_queue")
        assert success is False

    @pytest.mark.asyncio
    async def test_move_dlq_job_to_queue_add_fails(
        self, handler: RetryHandler, mock_redis: MagicMock
    ) -> None:
        """Test move_dlq_job_to_queue returns False when add_to_queue_safe fails."""
        mock_redis.pop_from_queue_nonblocking = AsyncMock(
            return_value={
                "original_job": {"camera_id": "cam1"},
                "error": "Error",
                "attempt_count": 3,
                "first_failed_at": "2025-12-23T10:00:00",
                "last_failed_at": "2025-12-23T10:00:15",
                "queue_name": "detection_queue",
            }
        )
        mock_redis.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(success=False, queue_length=10000, error="Queue is full")
        )

        success = await handler.move_dlq_job_to_queue("dlq:detection_queue", "detection_queue")

        assert success is False

    @pytest.mark.asyncio
    async def test_move_dlq_job_to_queue_with_backpressure(
        self, handler: RetryHandler, mock_redis: MagicMock
    ) -> None:
        """Test move_dlq_job_to_queue logs warning on backpressure."""
        mock_redis.pop_from_queue_nonblocking = AsyncMock(
            return_value={
                "original_job": {"camera_id": "cam1"},
                "error": "Error",
                "attempt_count": 3,
                "first_failed_at": "2025-12-23T10:00:00",
                "last_failed_at": "2025-12-23T10:00:15",
                "queue_name": "detection_queue",
            }
        )
        mock_redis.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(
                success=True,
                queue_length=9000,
                moved_to_dlq_count=5,  # This triggers had_backpressure
            )
        )

        with patch("backend.services.retry_handler.logger") as mock_logger:
            success = await handler.move_dlq_job_to_queue("dlq:detection_queue", "detection_queue")

            assert success is True
            # Verify warning was logged due to backpressure
            warning_calls = mock_logger.warning.call_args_list
            found_backpressure_warning = any(
                "backpressure" in str(call).lower() for call in warning_calls
            )
            assert found_backpressure_warning, f"Expected backpressure warning: {warning_calls}"

    @pytest.mark.asyncio
    async def test_move_dlq_job_to_queue_exception_in_requeue(
        self, handler: RetryHandler, mock_redis: MagicMock
    ) -> None:
        """Test move_dlq_job_to_queue returns False on exception in requeue."""
        mock_redis.pop_from_queue_nonblocking = AsyncMock(side_effect=RuntimeError("Redis error"))

        success = await handler.move_dlq_job_to_queue("dlq:detection_queue", "detection_queue")

        assert success is False

    @pytest.mark.asyncio
    async def test_move_dlq_job_to_queue_exception_in_add(
        self, handler: RetryHandler, mock_redis: MagicMock
    ) -> None:
        """Test move_dlq_job_to_queue returns False on exception during add_to_queue_safe."""
        # First make requeue succeed
        mock_redis.pop_from_queue_nonblocking = AsyncMock(
            return_value={
                "original_job": {"camera_id": "cam1"},
                "error": "Error",
                "attempt_count": 3,
                "first_failed_at": "2025-12-23T10:00:00",
                "last_failed_at": "2025-12-23T10:00:15",
                "queue_name": "detection_queue",
            }
        )
        # Then make add_to_queue_safe raise an exception
        mock_redis.add_to_queue_safe = AsyncMock(
            side_effect=RuntimeError("Redis connection lost during add")
        )

        success = await handler.move_dlq_job_to_queue("dlq:detection_queue", "detection_queue")

        assert success is False


# =============================================================================
# Global Handler Functions Tests
# =============================================================================


class TestRetryHandlerGlobal:
    """Tests for global retry handler functions."""

    def setup_method(self) -> None:
        """Reset global state before each test."""
        reset_retry_handler()

    def teardown_method(self) -> None:
        """Reset global state after each test."""
        reset_retry_handler()

    def test_get_retry_handler_creates_singleton(self) -> None:
        """Test that get_retry_handler creates a singleton."""
        handler1 = get_retry_handler()
        handler2 = get_retry_handler()
        assert handler1 is handler2

    def test_get_retry_handler_with_redis(self) -> None:
        """Test that Redis client is set on first call."""
        mock_redis = MagicMock()
        handler = get_retry_handler(mock_redis)
        assert handler._redis is mock_redis

    def test_get_retry_handler_updates_redis(self) -> None:
        """Test that Redis can be set on subsequent call if None."""
        handler1 = get_retry_handler()
        assert handler1._redis is None

        mock_redis = MagicMock()
        handler2 = get_retry_handler(mock_redis)
        assert handler2._redis is mock_redis
        assert handler1 is handler2

    def test_reset_retry_handler(self) -> None:
        """Test resetting the global handler."""
        handler1 = get_retry_handler()
        reset_retry_handler()
        handler2 = get_retry_handler()
        assert handler1 is not handler2


# =============================================================================
# Backoff Timing Tests
# =============================================================================


class TestRetryHandlerBackoffTiming:
    """Tests for actual backoff timing behavior."""

    @pytest.mark.asyncio
    async def test_backoff_delays_are_applied(self) -> None:
        """Test that exponential backoff delays are actually applied."""
        config = RetryConfig(
            max_retries=3,
            base_delay_seconds=0.05,  # 50ms base
            exponential_base=2.0,
            jitter=False,
        )
        handler = RetryHandler(redis_client=None, config=config)

        timestamps: list[float] = []

        async def failing_op() -> str:
            timestamps.append(asyncio.get_event_loop().time())
            raise RuntimeError("Always fails")

        start_time = asyncio.get_event_loop().time()
        await handler.with_retry(
            operation=failing_op,
            job_data={},
            queue_name="test_queue",
        )
        end_time = asyncio.get_event_loop().time()

        # Should have 3 timestamps (3 attempts)
        assert len(timestamps) == 3

        # Verify delays between attempts
        # Delay 1: ~0.05s (50ms)
        # Delay 2: ~0.10s (100ms)
        delay1 = timestamps[1] - timestamps[0]
        delay2 = timestamps[2] - timestamps[1]

        assert delay1 >= 0.04  # Allow some tolerance
        assert delay1 <= 0.10
        assert delay2 >= 0.09
        assert delay2 <= 0.15

        # Total time should be at least 0.15s (sum of delays)
        total_time = end_time - start_time
        assert total_time >= 0.14


# =============================================================================
# DLQ Circuit Breaker Tests
# =============================================================================


class TestDLQCircuitBreaker:
    """Tests for DLQ circuit breaker functionality."""

    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        """Create a mock Redis client."""
        redis = MagicMock()
        redis.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(success=True, queue_length=1)
        )
        redis.get_from_queue = AsyncMock(return_value=None)
        redis.pop_from_queue_nonblocking = AsyncMock(return_value=None)
        redis.get_queue_length = AsyncMock(return_value=0)
        redis.peek_queue = AsyncMock(return_value=[])
        redis.clear_queue = AsyncMock(return_value=True)
        return redis

    @pytest.fixture
    def handler_with_low_threshold(self, mock_redis: MagicMock) -> RetryHandler:
        """Create a retry handler with low circuit breaker threshold for testing."""
        from backend.services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

        config = RetryConfig(
            max_retries=3,
            base_delay_seconds=0.01,  # Fast for testing
            jitter=False,
        )
        cb_config = CircuitBreakerConfig(
            failure_threshold=2,  # Low threshold for testing
            recovery_timeout=0.1,  # Fast recovery for testing
            half_open_max_calls=1,
            success_threshold=1,
        )
        dlq_circuit_breaker = CircuitBreaker(
            name="dlq_overflow_test",
            config=cb_config,
        )
        return RetryHandler(
            redis_client=mock_redis,
            config=config,
            dlq_circuit_breaker=dlq_circuit_breaker,
        )

    def test_circuit_breaker_initialized(self, handler_with_low_threshold: RetryHandler) -> None:
        """Test that circuit breaker is initialized."""
        status = handler_with_low_threshold.get_dlq_circuit_breaker_status()
        assert status["name"] == "dlq_overflow_test"
        assert status["state"] == "closed"
        assert status["failure_count"] == 0

    def test_is_dlq_circuit_open_initially_closed(
        self, handler_with_low_threshold: RetryHandler
    ) -> None:
        """Test circuit is initially closed."""
        assert handler_with_low_threshold.is_dlq_circuit_open() is False

    @pytest.mark.asyncio
    async def test_circuit_opens_after_failures(
        self, handler_with_low_threshold: RetryHandler, mock_redis: MagicMock
    ) -> None:
        """Test that circuit opens after threshold failures."""
        # Make DLQ writes fail
        mock_redis.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(success=False, queue_length=10000, error="Queue full")
        )

        async def always_fail() -> str:
            raise ConnectionError("Always fails")

        # First retry exhaustion - should fail to move to DLQ
        await handler_with_low_threshold.with_retry(
            operation=always_fail,
            job_data={"camera_id": "cam1"},
            queue_name="detection_queue",
        )

        # Check circuit breaker has recorded the failure
        status = handler_with_low_threshold.get_dlq_circuit_breaker_status()
        assert status["failure_count"] == 1

        # Second retry exhaustion - should trip the circuit
        await handler_with_low_threshold.with_retry(
            operation=always_fail,
            job_data={"camera_id": "cam2"},
            queue_name="detection_queue",
        )

        # Circuit should now be open
        assert handler_with_low_threshold.is_dlq_circuit_open() is True
        status = handler_with_low_threshold.get_dlq_circuit_breaker_status()
        assert status["state"] == "open"

    @pytest.mark.asyncio
    async def test_open_circuit_skips_dlq_writes(
        self, handler_with_low_threshold: RetryHandler, mock_redis: MagicMock
    ) -> None:
        """Test that open circuit skips DLQ writes."""
        # Make DLQ writes fail to trip the circuit
        mock_redis.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(success=False, queue_length=10000, error="Queue full")
        )

        async def always_fail() -> str:
            raise ConnectionError("Always fails")

        # Trip the circuit with 2 failures
        await handler_with_low_threshold.with_retry(
            operation=always_fail,
            job_data={"camera_id": "cam1"},
            queue_name="detection_queue",
        )
        await handler_with_low_threshold.with_retry(
            operation=always_fail,
            job_data={"camera_id": "cam2"},
            queue_name="detection_queue",
        )

        # Reset mock to track new calls
        mock_redis.add_to_queue_safe.reset_mock()

        # Third failure - circuit is open, should NOT attempt DLQ write
        result = await handler_with_low_threshold.with_retry(
            operation=always_fail,
            job_data={"camera_id": "cam3"},
            queue_name="detection_queue",
        )

        # DLQ write should be skipped when circuit is open
        assert result.moved_to_dlq is False
        # No calls to Redis for DLQ write
        mock_redis.add_to_queue_safe.assert_not_called()

    @pytest.mark.asyncio
    async def test_circuit_recovers_after_timeout(
        self, handler_with_low_threshold: RetryHandler, mock_redis: MagicMock
    ) -> None:
        """Test that circuit transitions to half-open after recovery timeout."""
        # Make DLQ writes fail to trip the circuit
        mock_redis.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(success=False, queue_length=10000, error="Queue full")
        )

        async def always_fail() -> str:
            raise ConnectionError("Always fails")

        # Trip the circuit
        await handler_with_low_threshold.with_retry(
            operation=always_fail,
            job_data={"camera_id": "cam1"},
            queue_name="detection_queue",
        )
        await handler_with_low_threshold.with_retry(
            operation=always_fail,
            job_data={"camera_id": "cam2"},
            queue_name="detection_queue",
        )

        assert handler_with_low_threshold.is_dlq_circuit_open() is True

        # Wait for recovery timeout (0.1 seconds + buffer)
        await asyncio.sleep(0.15)

        # Make DLQ writes succeed now
        mock_redis.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(success=True, queue_length=1)
        )

        # Next failure should allow DLQ write (half-open state)
        result = await handler_with_low_threshold.with_retry(
            operation=always_fail,
            job_data={"camera_id": "cam3"},
            queue_name="detection_queue",
        )

        # Should have successfully moved to DLQ
        assert result.moved_to_dlq is True
        mock_redis.add_to_queue_safe.assert_called_once()

        # Circuit should now be closed (success_threshold=1)
        status = handler_with_low_threshold.get_dlq_circuit_breaker_status()
        assert status["state"] == "closed"

    def test_reset_circuit_breaker(self, handler_with_low_threshold: RetryHandler) -> None:
        """Test manual reset of circuit breaker."""
        # Force circuit open
        handler_with_low_threshold._dlq_circuit_breaker.force_open()
        assert handler_with_low_threshold.is_dlq_circuit_open() is True

        # Reset it
        handler_with_low_threshold.reset_dlq_circuit_breaker()

        # Should be closed now
        assert handler_with_low_threshold.is_dlq_circuit_open() is False
        status = handler_with_low_threshold.get_dlq_circuit_breaker_status()
        assert status["state"] == "closed"
        assert status["failure_count"] == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_tracks_exception_failures(
        self, handler_with_low_threshold: RetryHandler, mock_redis: MagicMock
    ) -> None:
        """Test that circuit breaker tracks failures from exceptions."""
        # Make add_to_queue_safe raise an exception
        mock_redis.add_to_queue_safe = AsyncMock(side_effect=RuntimeError("Redis connection lost"))

        async def always_fail() -> str:
            raise ConnectionError("Always fails")

        # First failure with exception
        await handler_with_low_threshold.with_retry(
            operation=always_fail,
            job_data={"camera_id": "cam1"},
            queue_name="detection_queue",
        )

        status = handler_with_low_threshold.get_dlq_circuit_breaker_status()
        assert status["failure_count"] == 1

        # Second failure trips the circuit
        await handler_with_low_threshold.with_retry(
            operation=always_fail,
            job_data={"camera_id": "cam2"},
            queue_name="detection_queue",
        )

        assert handler_with_low_threshold.is_dlq_circuit_open() is True

    def test_default_circuit_breaker_uses_settings(self, mock_redis: MagicMock) -> None:
        """Test that default circuit breaker uses settings configuration."""
        mock_settings = MagicMock()
        mock_settings.dlq_circuit_breaker_failure_threshold = 10
        mock_settings.dlq_circuit_breaker_recovery_timeout = 120.0
        mock_settings.dlq_circuit_breaker_half_open_max_calls = 5
        mock_settings.dlq_circuit_breaker_success_threshold = 3

        with patch("backend.services.retry_handler.get_settings", return_value=mock_settings):
            handler = RetryHandler(redis_client=mock_redis)

        status = handler.get_dlq_circuit_breaker_status()
        config = status["config"]
        assert config["failure_threshold"] == 10
        assert config["recovery_timeout"] == 120.0
        assert config["half_open_max_calls"] == 5
        assert config["success_threshold"] == 3


# =============================================================================
# DLQ Job Loss Logging Tests
# =============================================================================


class TestDLQJobLossLogging:
    """Tests for DLQ job loss logging fix (wa0t.16)."""

    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        """Create a mock Redis client."""
        redis = MagicMock()
        redis.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(success=False, queue_length=10000, error="Queue full")
        )
        redis.get_from_queue = AsyncMock(return_value=None)
        redis.pop_from_queue_nonblocking = AsyncMock(return_value=None)
        redis.get_queue_length = AsyncMock(return_value=0)
        redis.peek_queue = AsyncMock(return_value=[])
        redis.clear_queue = AsyncMock(return_value=True)
        return redis

    @pytest.fixture
    def handler_with_low_threshold(self, mock_redis: MagicMock) -> RetryHandler:
        """Create a handler with low circuit breaker threshold."""
        from backend.services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

        cb_config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.1,
            half_open_max_calls=1,
            success_threshold=1,
        )
        dlq_circuit_breaker = CircuitBreaker(
            name="test_dlq_overflow",
            config=cb_config,
        )
        return RetryHandler(
            redis_client=mock_redis,
            config=RetryConfig(max_retries=1, base_delay_seconds=0.01),
            dlq_circuit_breaker=dlq_circuit_breaker,
        )

    @pytest.mark.asyncio
    async def test_job_loss_logs_error_with_full_context(
        self, handler_with_low_threshold: RetryHandler, mock_redis: MagicMock
    ) -> None:
        """Test that job loss logs error with full job context when circuit is open."""

        async def always_fail() -> str:
            raise ConnectionError("Service unavailable")

        # Trip the circuit breaker first by failing DLQ writes
        await handler_with_low_threshold.with_retry(
            operation=always_fail,
            job_data={"camera_id": "cam1"},
            queue_name="detection_queue",
        )
        await handler_with_low_threshold.with_retry(
            operation=always_fail,
            job_data={"camera_id": "cam2"},
            queue_name="detection_queue",
        )

        # Verify circuit is open
        assert handler_with_low_threshold.is_dlq_circuit_open() is True

        # Now capture logs when processing job with open circuit
        # When circuit is open, the allow_call() check should log CRITICAL DATA LOSS
        with patch("backend.services.retry_handler.logger") as mock_logger:
            result = await handler_with_low_threshold.with_retry(
                operation=always_fail,
                job_data={"camera_id": "cam3", "file_path": "/path/to/image.jpg"},
                queue_name="detection_queue",
            )

            # Verify the job was NOT moved to DLQ (circuit was open)
            assert result.moved_to_dlq is False

            # Find the error call that contains the critical data loss message
            error_calls = mock_logger.error.call_args_list
            found_critical_data_loss = False
            for call in error_calls:
                call_str = str(call)
                if "CRITICAL DATA LOSS" in call_str:
                    found_critical_data_loss = True
                    # Verify job data is in the extras
                    assert "cam3" in call_str or "lost_job_data" in call_str
                    break

            assert found_critical_data_loss, (
                f"Expected CRITICAL DATA LOSS log message not found. Error calls: {error_calls}"
            )

    @pytest.mark.asyncio
    async def test_job_loss_includes_job_data_in_extra(
        self, handler_with_low_threshold: RetryHandler, mock_redis: MagicMock
    ) -> None:
        """Test that job loss log includes the job data in extras for audit."""

        # Trip the circuit breaker
        async def always_fail() -> str:
            raise ConnectionError("Service unavailable")

        # Trip the circuit
        await handler_with_low_threshold.with_retry(
            operation=always_fail,
            job_data={"camera_id": "cam1"},
            queue_name="detection_queue",
        )
        await handler_with_low_threshold.with_retry(
            operation=always_fail,
            job_data={"camera_id": "cam2"},
            queue_name="detection_queue",
        )

        with patch("backend.services.retry_handler.logger") as mock_logger:
            await handler_with_low_threshold.with_retry(
                operation=always_fail,
                job_data={"camera_id": "cam_lost", "important_data": "should_be_logged"},
                queue_name="detection_queue",
            )

            # Check that the extra field contains job data
            error_calls = list(mock_logger.error.call_args_list)
            has_job_data_in_extra = any(
                "lost_job_data" in str(call) or "cam_lost" in str(call) for call in error_calls
            )
            assert has_job_data_in_extra, f"Job data not found in error logs: {error_calls}"


# =============================================================================
# _move_to_dlq Edge Cases Tests
# =============================================================================


class TestMoveToDlqEdgeCases:
    """Tests for _move_to_dlq edge cases that were previously uncovered."""

    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        """Create a mock Redis client."""
        redis = MagicMock()
        redis.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(success=True, queue_length=1)
        )
        return redis

    @pytest.mark.asyncio
    async def test_move_to_dlq_no_redis_logs_warning(self) -> None:
        """Test _move_to_dlq logs warning when Redis is not initialized."""
        handler = RetryHandler(redis_client=None)

        with patch("backend.services.retry_handler.logger") as mock_logger:
            result = await handler._move_to_dlq(
                job_data={"camera_id": "cam1"},
                error="Test error",
                attempt_count=3,
                first_failed_at="2025-12-23T10:00:00",
                queue_name="detection_queue",
            )

            assert result is False
            # Verify warning was logged
            warning_calls = mock_logger.warning.call_args_list
            found_warning = any(
                "Redis client not initialized" in str(call) for call in warning_calls
            )
            assert found_warning, f"Expected warning not found: {warning_calls}"

    @pytest.mark.asyncio
    async def test_move_to_dlq_success(self, mock_redis: MagicMock) -> None:
        """Test successful _move_to_dlq operation."""
        handler = RetryHandler(redis_client=mock_redis)

        result = await handler._move_to_dlq(
            job_data={"camera_id": "cam1"},
            error="Test error",
            attempt_count=3,
            first_failed_at="2025-12-23T10:00:00",
            queue_name="detection_queue",
        )

        assert result is True
        mock_redis.add_to_queue_safe.assert_called_once()


# =============================================================================
# DLQ Constants Tests
# =============================================================================


class TestDLQConstants:
    """Tests for DLQ constant exports."""

    def test_dlq_prefix_constant(self) -> None:
        """Test DLQ_PREFIX constant is exported."""
        assert RetryHandler.DLQ_PREFIX == "dlq:"

    def test_dlq_detection_queue_constant(self) -> None:
        """Test DLQ_DETECTION_QUEUE constant is exported."""
        assert RetryHandler.DLQ_DETECTION_QUEUE == "dlq:detection_queue"

    def test_dlq_analysis_queue_constant(self) -> None:
        """Test DLQ_ANALYSIS_QUEUE constant is exported."""
        assert RetryHandler.DLQ_ANALYSIS_QUEUE == "dlq:analysis_queue"


# =============================================================================
# Error Context Enrichment Tests (NEM-1474)
# =============================================================================


class TestJobFailureErrorContext:
    """Tests for JobFailure error context enrichment (NEM-1474)."""

    def test_job_failure_includes_error_type(self) -> None:
        """Test JobFailure stores the exception class name."""
        failure = JobFailure(
            original_job={"camera_id": "cam1"},
            error="Connection refused",
            attempt_count=3,
            first_failed_at="2025-12-23T10:00:00",
            last_failed_at="2025-12-23T10:00:15",
            queue_name="detection_queue",
            error_type="ConnectionRefusedError",
        )
        assert failure.error_type == "ConnectionRefusedError"

    def test_job_failure_includes_stack_trace(self) -> None:
        """Test JobFailure stores truncated stack trace."""
        stack_trace = (
            "Traceback (most recent call last):\n"
            '  File "detector.py", line 42, in detect\n'
            "    response = await client.post(url, data=data)\n"
            "ConnectionRefusedError: Connection refused"
        )
        failure = JobFailure(
            original_job={"camera_id": "cam1"},
            error="Connection refused",
            attempt_count=3,
            first_failed_at="2025-12-23T10:00:00",
            last_failed_at="2025-12-23T10:00:15",
            queue_name="detection_queue",
            stack_trace=stack_trace,
        )
        assert failure.stack_trace == stack_trace
        assert "detector.py" in failure.stack_trace

    def test_job_failure_includes_http_status(self) -> None:
        """Test JobFailure stores HTTP status code for network errors."""
        failure = JobFailure(
            original_job={"camera_id": "cam1"},
            error="Service unavailable",
            attempt_count=3,
            first_failed_at="2025-12-23T10:00:00",
            last_failed_at="2025-12-23T10:00:15",
            queue_name="detection_queue",
            http_status=503,
        )
        assert failure.http_status == 503

    def test_job_failure_includes_response_body(self) -> None:
        """Test JobFailure stores truncated AI service response."""
        response_body = '{"error": "Model overloaded", "retry_after": 60}'
        failure = JobFailure(
            original_job={"camera_id": "cam1"},
            error="Service overloaded",
            attempt_count=3,
            first_failed_at="2025-12-23T10:00:00",
            last_failed_at="2025-12-23T10:00:15",
            queue_name="detection_queue",
            response_body=response_body,
        )
        assert failure.response_body == response_body

    def test_job_failure_includes_retry_delays(self) -> None:
        """Test JobFailure stores delays between retry attempts."""
        retry_delays = [1.0, 2.0, 4.0]
        failure = JobFailure(
            original_job={"camera_id": "cam1"},
            error="Timeout",
            attempt_count=3,
            first_failed_at="2025-12-23T10:00:00",
            last_failed_at="2025-12-23T10:00:15",
            queue_name="detection_queue",
            retry_delays=retry_delays,
        )
        assert failure.retry_delays == [1.0, 2.0, 4.0]
        assert len(failure.retry_delays) == 3

    def test_job_failure_includes_system_context(self) -> None:
        """Test JobFailure stores system state snapshot at failure time."""
        context = {
            "detection_queue_depth": 150,
            "analysis_queue_depth": 25,
            "circuit_breaker_states": {"rtdetr": "closed", "nemotron": "half_open"},
            "gpu_utilization": 85.5,
        }
        failure = JobFailure(
            original_job={"camera_id": "cam1"},
            error="GPU OOM",
            attempt_count=3,
            first_failed_at="2025-12-23T10:00:00",
            last_failed_at="2025-12-23T10:00:15",
            queue_name="detection_queue",
            context=context,
        )
        assert failure.context is not None
        assert failure.context["detection_queue_depth"] == 150
        assert failure.context["circuit_breaker_states"]["nemotron"] == "half_open"

    def test_job_failure_default_values_for_new_fields(self) -> None:
        """Test new error context fields have None defaults for backward compatibility."""
        failure = JobFailure(
            original_job={"camera_id": "cam1"},
            error="Error",
            attempt_count=3,
            first_failed_at="2025-12-23T10:00:00",
            last_failed_at="2025-12-23T10:00:15",
            queue_name="detection_queue",
        )
        assert failure.error_type is None
        assert failure.stack_trace is None
        assert failure.http_status is None
        assert failure.response_body is None
        assert failure.retry_delays is None
        assert failure.context is None

    def test_job_failure_to_dict_includes_error_context(self) -> None:
        """Test to_dict() includes all error context fields."""
        failure = JobFailure(
            original_job={"camera_id": "cam1"},
            error="Connection refused",
            attempt_count=3,
            first_failed_at="2025-12-23T10:00:00",
            last_failed_at="2025-12-23T10:00:15",
            queue_name="detection_queue",
            error_type="ConnectionRefusedError",
            stack_trace="Traceback...",
            http_status=503,
            response_body='{"error": "overloaded"}',
            retry_delays=[1.0, 2.0],
            context={"queue_depth": 100},
        )
        result = failure.to_dict()

        assert result["error_type"] == "ConnectionRefusedError"
        assert result["stack_trace"] == "Traceback..."
        assert result["http_status"] == 503
        assert result["response_body"] == '{"error": "overloaded"}'
        assert result["retry_delays"] == [1.0, 2.0]
        assert result["context"] == {"queue_depth": 100}

    def test_job_failure_from_dict_parses_error_context(self) -> None:
        """Test from_dict() correctly parses error context fields."""
        data = {
            "original_job": {"camera_id": "cam1"},
            "error": "Timeout",
            "attempt_count": 2,
            "first_failed_at": "2025-12-23T10:00:00",
            "last_failed_at": "2025-12-23T10:00:10",
            "queue_name": "analysis_queue",
            "error_type": "TimeoutError",
            "stack_trace": "Traceback (most recent call)...",
            "http_status": 504,
            "response_body": '{"status": "timeout"}',
            "retry_delays": [1.0, 2.5],
            "context": {"gpu_utilization": 90},
        }
        failure = JobFailure.from_dict(data)

        assert failure.error_type == "TimeoutError"
        assert failure.stack_trace == "Traceback (most recent call)..."
        assert failure.http_status == 504
        assert failure.response_body == '{"status": "timeout"}'
        assert failure.retry_delays == [1.0, 2.5]
        assert failure.context == {"gpu_utilization": 90}

    def test_job_failure_from_dict_handles_missing_context_fields(self) -> None:
        """Test from_dict() handles missing error context fields (backward compatibility)."""
        data = {
            "original_job": {"camera_id": "cam1"},
            "error": "Error",
            "attempt_count": 2,
            "first_failed_at": "2025-12-23T10:00:00",
            "last_failed_at": "2025-12-23T10:00:10",
            "queue_name": "detection_queue",
            # No error context fields
        }
        failure = JobFailure.from_dict(data)

        assert failure.error_type is None
        assert failure.stack_trace is None
        assert failure.http_status is None
        assert failure.response_body is None
        assert failure.retry_delays is None
        assert failure.context is None


class TestRetryHandlerErrorContextCapture:
    """Tests for RetryHandler capturing error context during failures."""

    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        """Create a mock Redis client."""
        redis = MagicMock()
        redis.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(success=True, queue_length=1)
        )
        redis.get_queue_length = AsyncMock(return_value=50)
        return redis

    @pytest.fixture
    def handler(self, mock_redis: MagicMock) -> RetryHandler:
        """Create a retry handler with mock Redis."""
        config = RetryConfig(
            max_retries=2,
            base_delay_seconds=0.01,
            jitter=False,
        )
        return RetryHandler(redis_client=mock_redis, config=config)

    @pytest.mark.asyncio
    async def test_captures_error_type_from_exception(
        self, handler: RetryHandler, mock_redis: MagicMock
    ) -> None:
        """Test that error_type is captured from the exception class name."""

        async def raise_connection_error() -> str:
            raise ConnectionRefusedError("Connection to AI service refused")

        await handler.with_retry(
            operation=raise_connection_error,
            job_data={"camera_id": "cam1"},
            queue_name="detection_queue",
        )

        # Verify the failure was stored with error_type
        mock_redis.add_to_queue_safe.assert_called_once()
        call_args = mock_redis.add_to_queue_safe.call_args
        job_failure_dict = call_args[0][1]
        assert job_failure_dict["error_type"] == "ConnectionRefusedError"

    @pytest.mark.asyncio
    async def test_captures_stack_trace_on_failure(
        self, handler: RetryHandler, mock_redis: MagicMock
    ) -> None:
        """Test that stack trace is captured when job fails."""

        async def raise_with_traceback() -> str:
            raise ValueError("Invalid detection data")

        await handler.with_retry(
            operation=raise_with_traceback,
            job_data={"camera_id": "cam1"},
            queue_name="detection_queue",
        )

        mock_redis.add_to_queue_safe.assert_called_once()
        call_args = mock_redis.add_to_queue_safe.call_args
        job_failure_dict = call_args[0][1]

        # Stack trace should be captured
        assert job_failure_dict["stack_trace"] is not None
        assert "ValueError" in job_failure_dict["stack_trace"]
        assert "Invalid detection data" in job_failure_dict["stack_trace"]

    @pytest.mark.asyncio
    async def test_stack_trace_is_truncated(
        self, handler: RetryHandler, mock_redis: MagicMock
    ) -> None:
        """Test that very long stack traces are truncated."""

        async def deeply_nested_error() -> str:
            def level_10() -> None:
                raise RuntimeError("Deep error " + "x" * 10000)

            def level_9() -> None:
                level_10()

            def level_8() -> None:
                level_9()

            def level_7() -> None:
                level_8()

            def level_6() -> None:
                level_7()

            def level_5() -> None:
                level_6()

            def level_4() -> None:
                level_5()

            def level_3() -> None:
                level_4()

            def level_2() -> None:
                level_3()

            def level_1() -> None:
                level_2()

            level_1()
            return "never reached"

        await handler.with_retry(
            operation=deeply_nested_error,
            job_data={"camera_id": "cam1"},
            queue_name="detection_queue",
        )

        mock_redis.add_to_queue_safe.assert_called_once()
        call_args = mock_redis.add_to_queue_safe.call_args
        job_failure_dict = call_args[0][1]

        # Stack trace should be truncated to reasonable length
        stack_trace = job_failure_dict["stack_trace"]
        assert stack_trace is not None
        assert len(stack_trace) <= 4096  # Max 4KB for stack traces

    @pytest.mark.asyncio
    async def test_captures_retry_delays(
        self, handler: RetryHandler, mock_redis: MagicMock
    ) -> None:
        """Test that retry delays are recorded."""

        async def always_fail() -> str:
            raise RuntimeError("Always fails")

        await handler.with_retry(
            operation=always_fail,
            job_data={"camera_id": "cam1"},
            queue_name="detection_queue",
        )

        mock_redis.add_to_queue_safe.assert_called_once()
        call_args = mock_redis.add_to_queue_safe.call_args
        job_failure_dict = call_args[0][1]

        # Should have recorded the delays between attempts
        retry_delays = job_failure_dict["retry_delays"]
        assert retry_delays is not None
        # With max_retries=2 and jitter=False, we should have 1 delay recorded
        # (delay before attempt 2)
        assert len(retry_delays) == 1
        # Base delay is 0.01s, first attempt delay is 0.01 * 2^0 = 0.01
        assert retry_delays[0] >= 0.01

    @pytest.mark.asyncio
    async def test_captures_system_context_on_failure(
        self, handler: RetryHandler, mock_redis: MagicMock
    ) -> None:
        """Test that system context (queue depths, circuit breaker states) is captured."""

        async def always_fail() -> str:
            raise RuntimeError("Service unavailable")

        await handler.with_retry(
            operation=always_fail,
            job_data={"camera_id": "cam1"},
            queue_name="detection_queue",
        )

        mock_redis.add_to_queue_safe.assert_called_once()
        call_args = mock_redis.add_to_queue_safe.call_args
        job_failure_dict = call_args[0][1]

        # Context should include queue depths
        context = job_failure_dict["context"]
        assert context is not None
        assert "detection_queue_depth" in context
        assert "analysis_queue_depth" in context
        assert "dlq_circuit_breaker_state" in context

    @pytest.mark.asyncio
    async def test_captures_http_status_from_httpx_error(
        self, handler: RetryHandler, mock_redis: MagicMock
    ) -> None:
        """Test that HTTP status code is captured from httpx response errors."""
        import httpx

        async def raise_http_error() -> str:
            response = httpx.Response(503, text="Service unavailable")
            raise httpx.HTTPStatusError(
                "Service unavailable", request=MagicMock(), response=response
            )

        await handler.with_retry(
            operation=raise_http_error,
            job_data={"camera_id": "cam1"},
            queue_name="detection_queue",
        )

        mock_redis.add_to_queue_safe.assert_called_once()
        call_args = mock_redis.add_to_queue_safe.call_args
        job_failure_dict = call_args[0][1]

        assert job_failure_dict["http_status"] == 503

    @pytest.mark.asyncio
    async def test_captures_response_body_from_httpx_error(
        self, handler: RetryHandler, mock_redis: MagicMock
    ) -> None:
        """Test that response body is captured from httpx response errors."""
        import httpx

        async def raise_http_error() -> str:
            response = httpx.Response(
                500,
                text='{"error": "Internal server error", "details": "GPU OOM"}',
            )
            raise httpx.HTTPStatusError("Server error", request=MagicMock(), response=response)

        await handler.with_retry(
            operation=raise_http_error,
            job_data={"camera_id": "cam1"},
            queue_name="detection_queue",
        )

        mock_redis.add_to_queue_safe.assert_called_once()
        call_args = mock_redis.add_to_queue_safe.call_args
        job_failure_dict = call_args[0][1]

        assert job_failure_dict["response_body"] is not None
        assert "GPU OOM" in job_failure_dict["response_body"]

    @pytest.mark.asyncio
    async def test_response_body_is_truncated(
        self, handler: RetryHandler, mock_redis: MagicMock
    ) -> None:
        """Test that very long response bodies are truncated."""
        import httpx

        async def raise_http_error_with_long_body() -> str:
            long_body = '{"error": "' + "x" * 20000 + '"}'
            response = httpx.Response(500, text=long_body)
            raise httpx.HTTPStatusError("Server error", request=MagicMock(), response=response)

        await handler.with_retry(
            operation=raise_http_error_with_long_body,
            job_data={"camera_id": "cam1"},
            queue_name="detection_queue",
        )

        mock_redis.add_to_queue_safe.assert_called_once()
        call_args = mock_redis.add_to_queue_safe.call_args
        job_failure_dict = call_args[0][1]

        # Response body should be truncated to reasonable length
        response_body = job_failure_dict["response_body"]
        assert response_body is not None
        assert len(response_body) <= 2048  # Max 2KB for response bodies
