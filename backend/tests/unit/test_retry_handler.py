"""Unit tests for retry handler with exponential backoff and DLQ.

Tests cover:
- RetryConfig exponential backoff calculations
- RetryHandler.with_retry() success and failure scenarios
- DLQ operations (move, get, clear, requeue)
- Integration with Redis client
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

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


class TestRetryHandler:
    """Tests for RetryHandler class."""

    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        """Create a mock Redis client."""
        redis = MagicMock()
        redis.add_to_queue = AsyncMock(return_value=1)
        redis.add_to_queue_safe = AsyncMock(
            return_value=QueueAddResult(success=True, queue_length=1)
        )
        redis.get_from_queue = AsyncMock(return_value=None)
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

        # Verify DLQ was called
        mock_redis.add_to_queue.assert_called_once()
        call_args = mock_redis.add_to_queue.call_args
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
    async def test_get_dlq_jobs_no_redis(self) -> None:
        """Test getting DLQ jobs without Redis returns empty list."""
        handler = RetryHandler(redis_client=None)
        jobs = await handler.get_dlq_jobs("dlq:detection_queue")
        assert jobs == []

    @pytest.mark.asyncio
    async def test_requeue_dlq_job(self, handler: RetryHandler, mock_redis: MagicMock) -> None:
        """Test requeuing a job from DLQ."""
        mock_redis.get_from_queue = AsyncMock(
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
        mock_redis.get_from_queue.assert_called_once_with("dlq:detection_queue", timeout=0)

    @pytest.mark.asyncio
    async def test_requeue_dlq_job_empty(
        self, handler: RetryHandler, mock_redis: MagicMock
    ) -> None:
        """Test requeuing from empty DLQ returns None."""
        mock_redis.get_from_queue = AsyncMock(return_value=None)

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
    async def test_move_dlq_job_to_queue(
        self, handler: RetryHandler, mock_redis: MagicMock
    ) -> None:
        """Test moving a job from DLQ back to processing queue."""
        mock_redis.get_from_queue = AsyncMock(
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
        mock_redis.add_to_queue.assert_called_once_with("detection_queue", {"camera_id": "cam1"})

    @pytest.mark.asyncio
    async def test_move_dlq_job_empty_queue(
        self, handler: RetryHandler, mock_redis: MagicMock
    ) -> None:
        """Test moving from empty DLQ returns False."""
        mock_redis.get_from_queue = AsyncMock(return_value=None)

        success = await handler.move_dlq_job_to_queue("dlq:detection_queue", "detection_queue")

        assert success is False


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
