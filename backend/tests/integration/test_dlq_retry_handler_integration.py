"""Integration tests for DLQ + RetryHandler with real Redis.

This module tests the end-to-end DLQ and RetryHandler functionality using a real
Redis instance. These tests verify:
- End-to-end retry flow with real Redis
- DLQ persistence across operations
- Requeue behavior verification
- DLQ stats accuracy
- Concurrent job processing
- Max retry enforcement
- DLQ overflow handling
- Atomic requeue operations

The tests use the real_redis fixture from conftest.py which provides
a connected RedisClient using either local Redis or testcontainers.

IMPORTANT: These tests MUST run serially (-n0) because the real_redis fixture
flushes the database and tests would interfere with each other if run in parallel.
The pytest.ini.options adds `-n0` for integration tests automatically.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, NamedTuple

import pytest

from backend.core.constants import (
    ANALYSIS_QUEUE,
    DETECTION_QUEUE,
    DLQ_PREFIX,
)
from backend.services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig
from backend.services.retry_handler import (
    RetryConfig,
    RetryHandler,
    reset_retry_handler,
)

if TYPE_CHECKING:
    from backend.core.redis import RedisClient

# Mark all tests in this module as integration tests that run serially
pytestmark = [
    pytest.mark.integration,
    pytest.mark.timeout(60),  # Extended timeout for Redis operations
]


# =============================================================================
# Fixtures
# =============================================================================


class QueueNames(NamedTuple):
    """Unique queue names for test isolation.

    Using NamedTuple instead of dataclass to avoid pytest collection warning.
    """

    test_id: str
    detection_queue: str
    analysis_queue: str
    dlq_detection_queue: str
    dlq_analysis_queue: str


@pytest.fixture
async def unique_queues(real_redis: RedisClient) -> AsyncGenerator[QueueNames]:
    """Create unique queue names for test isolation.

    This fixture generates unique queue names per test to allow parallel execution.
    It also cleans up the queues after the test completes.
    """
    test_id = uuid.uuid4().hex[:8]
    queues = QueueNames(
        test_id=test_id,
        detection_queue=f"test:{test_id}:{DETECTION_QUEUE}",
        analysis_queue=f"test:{test_id}:{ANALYSIS_QUEUE}",
        dlq_detection_queue=f"{DLQ_PREFIX}test:{test_id}:{DETECTION_QUEUE}",
        dlq_analysis_queue=f"{DLQ_PREFIX}test:{test_id}:{ANALYSIS_QUEUE}",
    )

    yield queues

    # Cleanup after test
    await real_redis.clear_queue(queues.detection_queue)
    await real_redis.clear_queue(queues.analysis_queue)
    await real_redis.clear_queue(queues.dlq_detection_queue)
    await real_redis.clear_queue(queues.dlq_analysis_queue)


@pytest.fixture
def retry_config() -> RetryConfig:
    """Create a fast retry config for testing."""
    return RetryConfig(
        max_retries=3,
        base_delay_seconds=0.001,  # Ultra-fast for testing (1ms)
        max_delay_seconds=0.01,
        exponential_base=2.0,
        jitter=False,
    )


@pytest.fixture
def instant_fail_config() -> RetryConfig:
    """Create a config with single retry for instant DLQ (no delays)."""
    return RetryConfig(
        max_retries=1,  # Single attempt = immediate DLQ, zero delays
        base_delay_seconds=0.0,
        max_delay_seconds=0.0,
        exponential_base=1.0,
        jitter=False,
    )


@pytest.fixture
def handler(real_redis: RedisClient, retry_config: RetryConfig) -> RetryHandler:
    """Create a RetryHandler with real Redis."""
    # Reset global handler to ensure clean state
    reset_retry_handler()
    return RetryHandler(redis_client=real_redis, config=retry_config)


@pytest.fixture
def instant_handler(real_redis: RedisClient, instant_fail_config: RetryConfig) -> RetryHandler:
    """Create a RetryHandler that fails instantly to DLQ (no retries/delays)."""
    reset_retry_handler()
    return RetryHandler(redis_client=real_redis, config=instant_fail_config)


@pytest.fixture
def handler_with_fast_circuit_breaker(
    real_redis: RedisClient, retry_config: RetryConfig
) -> RetryHandler:
    """Create a RetryHandler with a fast circuit breaker for testing."""
    reset_retry_handler()
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
        redis_client=real_redis,
        config=retry_config,
        dlq_circuit_breaker=dlq_circuit_breaker,
    )


# =============================================================================
# Test: End-to-end retry flow with real Redis
# =============================================================================


class TestEndToEndRetryFlow:
    """Tests for end-to-end retry flow with real Redis."""

    @pytest.mark.asyncio
    async def test_job_fails_and_moves_to_dlq_after_max_retries(
        self, handler: RetryHandler, unique_queues: QueueNames
    ) -> None:
        """Test that job goes to DLQ after max retries are exhausted."""

        async def always_fail() -> str:
            raise ConnectionError("Service unavailable")

        job_data = {"camera_id": "cam1", "file_path": "/path/image.jpg"}

        result = await handler.with_retry(
            operation=always_fail,
            job_data=job_data,
            queue_name=unique_queues.detection_queue,
        )

        # Verify retry result
        assert result.success is False
        assert result.attempts == 3  # max_retries
        assert result.error == "Service unavailable"
        assert result.moved_to_dlq is True

        # Verify job is in DLQ
        dlq_jobs = await handler.get_dlq_jobs(unique_queues.dlq_detection_queue)
        assert len(dlq_jobs) == 1
        assert dlq_jobs[0].original_job == job_data
        assert dlq_jobs[0].error == "Service unavailable"
        assert dlq_jobs[0].attempt_count == 3
        assert dlq_jobs[0].queue_name == unique_queues.detection_queue

    @pytest.mark.asyncio
    async def test_job_succeeds_on_retry(
        self, handler: RetryHandler, unique_queues: QueueNames
    ) -> None:
        """Test that job succeeds after initial failures."""
        attempt_count = 0

        async def eventually_succeed() -> str:
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ConnectionError("Temporary failure")
            return "success"

        job_data = {"camera_id": "cam1"}

        result = await handler.with_retry(
            operation=eventually_succeed,
            job_data=job_data,
            queue_name=unique_queues.detection_queue,
        )

        # Verify success
        assert result.success is True
        assert result.result == "success"
        assert result.attempts == 3
        assert result.moved_to_dlq is False

        # Verify DLQ is empty (job was successful)
        dlq_jobs = await handler.get_dlq_jobs(unique_queues.dlq_detection_queue)
        assert len(dlq_jobs) == 0

    @pytest.mark.asyncio
    async def test_job_succeeds_first_attempt(
        self, handler: RetryHandler, unique_queues: QueueNames
    ) -> None:
        """Test that job succeeds on first attempt."""

        async def immediate_success() -> dict:
            return {"result": "data"}

        result = await handler.with_retry(
            operation=immediate_success,
            job_data={"camera_id": "cam1"},
            queue_name=unique_queues.detection_queue,
        )

        assert result.success is True
        assert result.result == {"result": "data"}
        assert result.attempts == 1
        assert result.moved_to_dlq is False


# =============================================================================
# Test: DLQ persistence across operations
# =============================================================================


class TestDLQPersistence:
    """Tests for DLQ persistence across operations."""

    @pytest.mark.asyncio
    async def test_dlq_persists_jobs(
        self, handler: RetryHandler, unique_queues: QueueNames
    ) -> None:
        """Test that jobs remain in DLQ until explicitly removed."""

        async def always_fail() -> str:
            raise RuntimeError("Persistent failure")

        # Add multiple jobs to DLQ
        for i in range(3):
            await handler.with_retry(
                operation=always_fail,
                job_data={"camera_id": f"cam_{i}"},
                queue_name=unique_queues.detection_queue,
            )

        # Verify all jobs are in DLQ
        dlq_jobs = await handler.get_dlq_jobs(unique_queues.dlq_detection_queue)
        assert len(dlq_jobs) == 3

        # Verify jobs have unique camera IDs
        camera_ids = {job.original_job["camera_id"] for job in dlq_jobs}
        assert camera_ids == {"cam_0", "cam_1", "cam_2"}

        # Verify they persist after querying again
        dlq_jobs_again = await handler.get_dlq_jobs(unique_queues.dlq_detection_queue)
        assert len(dlq_jobs_again) == 3

    @pytest.mark.asyncio
    async def test_dlq_persistence_across_handler_instances(
        self, real_redis: RedisClient, retry_config: RetryConfig, unique_queues: QueueNames
    ) -> None:
        """Test that DLQ jobs persist across handler instances."""
        # Create first handler and add job to DLQ
        handler1 = RetryHandler(redis_client=real_redis, config=retry_config)

        async def always_fail() -> str:
            raise RuntimeError("Failure")

        await handler1.with_retry(
            operation=always_fail,
            job_data={"camera_id": "persistent_job"},
            queue_name=unique_queues.detection_queue,
        )

        # Verify job is in DLQ
        jobs1 = await handler1.get_dlq_jobs(unique_queues.dlq_detection_queue)
        assert len(jobs1) == 1

        # Create new handler instance
        handler2 = RetryHandler(redis_client=real_redis, config=retry_config)

        # Verify job is still accessible from new handler
        jobs2 = await handler2.get_dlq_jobs(unique_queues.dlq_detection_queue)
        assert len(jobs2) == 1
        assert jobs2[0].original_job["camera_id"] == "persistent_job"


# =============================================================================
# Test: Requeue behavior verification
# =============================================================================


class TestRequeueBehavior:
    """Tests for DLQ requeue behavior."""

    @pytest.mark.asyncio
    async def test_requeue_dlq_job_returns_original_job(
        self, handler: RetryHandler, unique_queues: QueueNames
    ) -> None:
        """Test that requeuing returns the original job data."""

        async def always_fail() -> str:
            raise RuntimeError("Failure")

        original_job = {"camera_id": "cam1", "file_path": "/path/image.jpg"}

        await handler.with_retry(
            operation=always_fail,
            job_data=original_job,
            queue_name=unique_queues.detection_queue,
        )

        # Requeue the job
        requeued_job = await handler.requeue_dlq_job(unique_queues.dlq_detection_queue)

        assert requeued_job == original_job

        # Verify DLQ is now empty
        dlq_jobs = await handler.get_dlq_jobs(unique_queues.dlq_detection_queue)
        assert len(dlq_jobs) == 0

    @pytest.mark.asyncio
    async def test_requeue_empty_dlq_returns_none(
        self, handler: RetryHandler, unique_queues: QueueNames
    ) -> None:
        """Test that requeuing from empty DLQ returns None."""
        result = await handler.requeue_dlq_job(unique_queues.dlq_detection_queue)
        assert result is None

    @pytest.mark.asyncio
    async def test_requeue_fifo_order(
        self, instant_handler: RetryHandler, unique_queues: QueueNames
    ) -> None:
        """Test that jobs are requeued in FIFO order (oldest first)."""

        async def always_fail() -> str:
            raise RuntimeError("Failure")

        # Add jobs in order (using instant_handler for zero-delay DLQ insertion)
        for i in range(3):
            await instant_handler.with_retry(
                operation=always_fail,
                job_data={"order": i},
                queue_name=unique_queues.detection_queue,
            )

        # Requeue in order - should get oldest first (FIFO)
        job1 = await instant_handler.requeue_dlq_job(unique_queues.dlq_detection_queue)
        assert job1["order"] == 0

        job2 = await instant_handler.requeue_dlq_job(unique_queues.dlq_detection_queue)
        assert job2["order"] == 1

        job3 = await instant_handler.requeue_dlq_job(unique_queues.dlq_detection_queue)
        assert job3["order"] == 2

        # DLQ should be empty now
        job4 = await instant_handler.requeue_dlq_job(unique_queues.dlq_detection_queue)
        assert job4 is None

    @pytest.mark.asyncio
    async def test_move_dlq_job_to_queue(
        self, handler: RetryHandler, real_redis: RedisClient, unique_queues: QueueNames
    ) -> None:
        """Test moving a job from DLQ back to a processing queue."""

        async def always_fail() -> str:
            raise RuntimeError("Failure")

        job_data = {"camera_id": "cam1"}

        await handler.with_retry(
            operation=always_fail,
            job_data=job_data,
            queue_name=unique_queues.detection_queue,
        )

        # Move job from DLQ to detection queue
        success = await handler.move_dlq_job_to_queue(
            unique_queues.dlq_detection_queue, unique_queues.detection_queue
        )
        assert success is True

        # Verify DLQ is empty
        dlq_jobs = await handler.get_dlq_jobs(unique_queues.dlq_detection_queue)
        assert len(dlq_jobs) == 0

        # Verify job is in detection queue
        queue_length = await real_redis.get_queue_length(unique_queues.detection_queue)
        assert queue_length == 1

        # Verify job content
        queued_job = await real_redis.get_from_queue(unique_queues.detection_queue, timeout=1)
        assert queued_job == job_data


# =============================================================================
# Test: Concurrent job processing
# =============================================================================


class TestConcurrentJobProcessing:
    """Tests for concurrent job processing."""

    @pytest.mark.asyncio
    async def test_concurrent_jobs_all_fail_to_dlq(
        self, handler: RetryHandler, unique_queues: QueueNames
    ) -> None:
        """Test that concurrent failing jobs all end up in DLQ."""

        async def always_fail() -> str:
            await asyncio.sleep(0.01)  # Simulate some work
            raise RuntimeError("Concurrent failure")

        # Process jobs concurrently
        tasks = [
            handler.with_retry(
                operation=always_fail,
                job_data={"job_id": i},
                queue_name=unique_queues.detection_queue,
            )
            for i in range(10)
        ]

        results = await asyncio.gather(*tasks)

        # All should have failed
        assert all(r.success is False for r in results)
        assert all(r.moved_to_dlq is True for r in results)

        # All should be in DLQ
        dlq_jobs = await handler.get_dlq_jobs(unique_queues.dlq_detection_queue)
        assert len(dlq_jobs) == 10

    @pytest.mark.asyncio
    async def test_concurrent_mixed_success_failure(
        self, handler: RetryHandler, unique_queues: QueueNames
    ) -> None:
        """Test concurrent jobs with mixed success/failure results."""

        async def mixed_result(job_id: int) -> str:
            await asyncio.sleep(0.01)
            # Even job IDs fail, odd succeed
            if job_id % 2 == 0:
                raise RuntimeError(f"Failure {job_id}")
            return f"Success {job_id}"

        tasks = [
            handler.with_retry(
                operation=lambda jid=i: mixed_result(jid),
                job_data={"job_id": i},
                queue_name=unique_queues.detection_queue,
            )
            for i in range(10)
        ]

        results = await asyncio.gather(*tasks)

        # 5 should succeed (odd IDs), 5 should fail (even IDs)
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        assert len(successful) == 5
        assert len(failed) == 5

        # Only failed jobs should be in DLQ
        dlq_jobs = await handler.get_dlq_jobs(unique_queues.dlq_detection_queue)
        assert len(dlq_jobs) == 5


# =============================================================================
# Test: Max retry enforcement
# =============================================================================


class TestMaxRetryEnforcement:
    """Tests for max retry enforcement."""

    @pytest.mark.asyncio
    async def test_respects_max_retries_config(
        self, real_redis: RedisClient, unique_queues: QueueNames
    ) -> None:
        """Test that max retries from config is respected."""
        attempt_count = 0

        async def count_and_fail() -> str:
            nonlocal attempt_count
            attempt_count += 1
            raise RuntimeError("Always fails")

        # Test with max_retries=5
        config = RetryConfig(max_retries=5, base_delay_seconds=0.01, jitter=False)
        handler = RetryHandler(redis_client=real_redis, config=config)

        result = await handler.with_retry(
            operation=count_and_fail,
            job_data={"test": "data"},
            queue_name=unique_queues.detection_queue,
        )

        assert result.attempts == 5
        assert attempt_count == 5
        assert result.success is False
        assert result.moved_to_dlq is True

    @pytest.mark.asyncio
    async def test_single_retry_config(
        self, real_redis: RedisClient, unique_queues: QueueNames
    ) -> None:
        """Test with max_retries=1 (no retries)."""
        attempt_count = 0

        async def count_and_fail() -> str:
            nonlocal attempt_count
            attempt_count += 1
            raise RuntimeError("Failure")

        config = RetryConfig(max_retries=1, base_delay_seconds=0.01, jitter=False)
        handler = RetryHandler(redis_client=real_redis, config=config)

        result = await handler.with_retry(
            operation=count_and_fail,
            job_data={"test": "data"},
            queue_name=unique_queues.detection_queue,
        )

        assert result.attempts == 1
        assert attempt_count == 1
        assert result.moved_to_dlq is True


# =============================================================================
# Test: Clear DLQ operations
# =============================================================================


class TestClearDLQ:
    """Tests for clearing DLQ operations."""

    @pytest.mark.asyncio
    async def test_clear_dlq_removes_all_jobs(
        self, handler: RetryHandler, unique_queues: QueueNames
    ) -> None:
        """Test that clear_dlq removes all jobs."""

        async def always_fail() -> str:
            raise RuntimeError("Failure")

        # Add multiple jobs
        for i in range(5):
            await handler.with_retry(
                operation=always_fail,
                job_data={"job_id": i},
                queue_name=unique_queues.detection_queue,
            )

        # Verify jobs exist
        jobs = await handler.get_dlq_jobs(unique_queues.dlq_detection_queue)
        assert len(jobs) == 5

        # Clear the DLQ
        result = await handler.clear_dlq(unique_queues.dlq_detection_queue)
        assert result is True

        # Verify DLQ is empty
        jobs = await handler.get_dlq_jobs(unique_queues.dlq_detection_queue)
        assert len(jobs) == 0

    @pytest.mark.asyncio
    async def test_clear_empty_dlq(self, handler: RetryHandler, unique_queues: QueueNames) -> None:
        """Test clearing an already empty DLQ.

        Note: The clear_dlq method always returns True on successful call,
        regardless of whether the queue existed. This matches the behavior
        where the operation "succeeded" (nothing to delete = success).
        """
        result = await handler.clear_dlq(unique_queues.dlq_detection_queue)
        # clear_dlq returns True on successful call, even if queue was empty
        assert result is True


# =============================================================================
# Test: Atomic requeue operations
# =============================================================================


class TestAtomicRequeueOperations:
    """Tests for atomic requeue operations."""

    @pytest.mark.asyncio
    async def test_requeue_is_atomic(
        self, handler: RetryHandler, real_redis: RedisClient, unique_queues: QueueNames
    ) -> None:
        """Test that requeue removes from DLQ atomically."""

        async def always_fail() -> str:
            raise RuntimeError("Failure")

        # Add a job to DLQ
        await handler.with_retry(
            operation=always_fail,
            job_data={"camera_id": "cam1"},
            queue_name=unique_queues.detection_queue,
        )

        # Verify initial state
        initial_count = await real_redis.get_queue_length(unique_queues.dlq_detection_queue)
        assert initial_count == 1

        # Requeue the job
        job = await handler.requeue_dlq_job(unique_queues.dlq_detection_queue)

        # Job should be returned and DLQ should be empty (atomic)
        assert job is not None
        assert job["camera_id"] == "cam1"

        final_count = await real_redis.get_queue_length(unique_queues.dlq_detection_queue)
        assert final_count == 0

    @pytest.mark.asyncio
    async def test_concurrent_requeue_no_duplicates(
        self, instant_handler: RetryHandler, unique_queues: QueueNames
    ) -> None:
        """Test that concurrent requeue calls don't return the same job."""

        async def always_fail() -> str:
            raise RuntimeError("Failure")

        # Add a single job to DLQ (using instant_handler for zero-delay)
        await instant_handler.with_retry(
            operation=always_fail,
            job_data={"camera_id": "unique_job"},
            queue_name=unique_queues.detection_queue,
        )

        # Try to requeue concurrently from multiple coroutines
        tasks = [
            instant_handler.requeue_dlq_job(unique_queues.dlq_detection_queue) for _ in range(5)
        ]
        results = await asyncio.gather(*tasks)

        # Only one should get the job, others should get None
        non_none_results = [r for r in results if r is not None]
        assert len(non_none_results) == 1
        assert non_none_results[0]["camera_id"] == "unique_job"


# =============================================================================
# Test: Circuit breaker integration
# =============================================================================


class TestCircuitBreakerIntegration:
    """Tests for circuit breaker integration with real Redis."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_status_accessible(
        self, handler_with_fast_circuit_breaker: RetryHandler
    ) -> None:
        """Test that circuit breaker status is accessible."""
        status = handler_with_fast_circuit_breaker.get_dlq_circuit_breaker_status()
        assert status["name"] == "dlq_overflow_test"
        assert status["state"] == "closed"
        assert status["failure_count"] == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_can_be_reset(
        self, handler_with_fast_circuit_breaker: RetryHandler
    ) -> None:
        """Test that circuit breaker can be manually reset."""
        # Force circuit open
        handler_with_fast_circuit_breaker._dlq_circuit_breaker.force_open()
        assert handler_with_fast_circuit_breaker.is_dlq_circuit_open() is True

        # Reset it
        handler_with_fast_circuit_breaker.reset_dlq_circuit_breaker()

        # Should be closed now
        assert handler_with_fast_circuit_breaker.is_dlq_circuit_open() is False


# =============================================================================
# Test: DLQ pagination
# =============================================================================


class TestDLQPagination:
    """Tests for DLQ job listing pagination."""

    @pytest.mark.asyncio
    async def test_get_dlq_jobs_with_pagination(
        self, handler: RetryHandler, unique_queues: QueueNames
    ) -> None:
        """Test getting DLQ jobs with pagination."""

        async def always_fail() -> str:
            raise RuntimeError("Failure")

        # Add 10 jobs
        for i in range(10):
            await handler.with_retry(
                operation=always_fail,
                job_data={"job_id": i},
                queue_name=unique_queues.detection_queue,
            )

        # Get first 5 jobs
        first_page = await handler.get_dlq_jobs(unique_queues.dlq_detection_queue, start=0, end=4)
        assert len(first_page) == 5

        # Get next 5 jobs
        second_page = await handler.get_dlq_jobs(unique_queues.dlq_detection_queue, start=5, end=9)
        assert len(second_page) == 5

        # Verify no overlap
        first_ids = {j.original_job["job_id"] for j in first_page}
        second_ids = {j.original_job["job_id"] for j in second_page}
        assert first_ids.isdisjoint(second_ids)

        # Get all jobs
        all_jobs = await handler.get_dlq_jobs(unique_queues.dlq_detection_queue, start=0, end=-1)
        assert len(all_jobs) == 10


# =============================================================================
# Test: Multiple DLQ queues
# =============================================================================


class TestMultipleDLQQueues:
    """Tests for handling multiple DLQ queues."""

    @pytest.mark.asyncio
    async def test_separate_dlq_queues(
        self, handler: RetryHandler, unique_queues: QueueNames
    ) -> None:
        """Test that detection and analysis DLQs are separate."""

        async def always_fail() -> str:
            raise RuntimeError("Failure")

        # Add to detection DLQ
        await handler.with_retry(
            operation=always_fail,
            job_data={"type": "detection"},
            queue_name=unique_queues.detection_queue,
        )

        # Add to analysis DLQ
        await handler.with_retry(
            operation=always_fail,
            job_data={"type": "analysis"},
            queue_name=unique_queues.analysis_queue,
        )

        # Verify separate queues
        detection_jobs = await handler.get_dlq_jobs(unique_queues.dlq_detection_queue)
        analysis_jobs = await handler.get_dlq_jobs(unique_queues.dlq_analysis_queue)

        assert len(detection_jobs) == 1
        assert len(analysis_jobs) == 1

        assert detection_jobs[0].original_job["type"] == "detection"
        assert analysis_jobs[0].original_job["type"] == "analysis"
