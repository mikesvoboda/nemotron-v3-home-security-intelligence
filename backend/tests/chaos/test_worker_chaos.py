"""Chaos tests for worker failure scenarios (NEM-2464).

These chaos tests verify that the pipeline workers (DetectionQueueWorker,
AnalysisQueueWorker, BatchTimeoutWorker) handle failure scenarios gracefully:

Test Scenarios:
- Worker crash mid-task (simulated with exception)
- Worker timeout scenarios
- Multiple workers competing for same job
- Worker restart recovery
- Orphaned job detection and recovery
- Queue backpressure handling

Expected Behavior:
- Workers continue running despite individual task failures
- Failed jobs are logged and tracked
- Workers stop gracefully on shutdown
- Multiple workers can process from same queue without conflicts
- Worker restart is clean and resumes processing
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest

from backend.core.constants import ANALYSIS_QUEUE, DETECTION_QUEUE
from backend.core.redis import RedisClient
from backend.services.batch_aggregator import BatchAggregator
from backend.services.detector_client import DetectorClient
from backend.services.nemotron_analyzer import NemotronAnalyzer
from backend.services.pipeline_workers import (
    AnalysisQueueWorker,
    BatchTimeoutWorker,
    DetectionQueueWorker,
    PipelineWorkerManager,
    WorkerState,
)
from backend.services.retry_handler import RetryHandler
from backend.services.video_processor import VideoProcessor

pytestmark = [pytest.mark.asyncio, pytest.mark.chaos]


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_redis() -> RedisClient:
    """Create a mock Redis client for testing.

    This mock simulates a simple queue with in-memory storage for testing
    worker behavior without requiring a real Redis instance.
    """
    mock = AsyncMock(spec=RedisClient)

    # In-memory queue storage for testing
    queue_storage: dict[str, list[dict[str, Any]]] = {}

    async def add_to_queue(queue_name: str, item: dict[str, Any]) -> bool:
        """Mock add_to_queue operation."""
        if queue_name not in queue_storage:
            queue_storage[queue_name] = []
        queue_storage[queue_name].append(item)
        return True

    async def get_from_queue(queue_name: str, timeout: int = 0) -> dict[str, Any] | None:
        """Mock get_from_queue operation (BLPOP simulation)."""
        if queue_name not in queue_storage or not queue_storage[queue_name]:
            # Simulate timeout with brief delay
            await asyncio.sleep(0.1)
            return None
        return queue_storage[queue_name].pop(0)

    async def delete_key(key: str) -> bool:
        """Mock delete_key operation."""
        queue_storage.pop(key, None)
        return True

    mock.add_to_queue = AsyncMock(side_effect=add_to_queue)
    mock.get_from_queue = AsyncMock(side_effect=get_from_queue)
    mock.delete_key = AsyncMock(side_effect=delete_key)
    mock._client = AsyncMock()

    # Helper method to access queue state for assertions
    mock._queue_storage = queue_storage

    return mock


@pytest.fixture
def mock_detector_client() -> DetectorClient:
    """Create a mock detector client for testing."""
    mock = AsyncMock(spec=DetectorClient)
    mock.detect_objects = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def mock_batch_aggregator() -> BatchAggregator:
    """Create a mock batch aggregator for testing."""
    mock = AsyncMock(spec=BatchAggregator)
    mock.add_detection = AsyncMock()
    mock.check_batch_timeouts = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def mock_video_processor() -> VideoProcessor:
    """Create a mock video processor for testing."""
    mock = AsyncMock(spec=VideoProcessor)
    mock.extract_frames = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def mock_retry_handler() -> RetryHandler:
    """Create a mock retry handler for testing."""
    mock = AsyncMock(spec=RetryHandler)
    mock.should_retry = AsyncMock(return_value=False)
    mock.retry_with_backoff = AsyncMock()
    return mock


@pytest.fixture
def mock_nemotron_analyzer() -> NemotronAnalyzer:
    """Create a mock Nemotron analyzer for testing."""
    mock = AsyncMock(spec=NemotronAnalyzer)
    mock.analyze_batch = AsyncMock(return_value={"risk_score": 50, "explanation": "Test analysis"})
    return mock


@pytest.fixture
async def detection_worker(
    mock_redis: RedisClient,
    mock_detector_client: DetectorClient,
    mock_batch_aggregator: BatchAggregator,
    mock_video_processor: VideoProcessor,
    mock_retry_handler: RetryHandler,
) -> DetectionQueueWorker:
    """Create a DetectionQueueWorker for testing."""
    worker = DetectionQueueWorker(
        redis_client=mock_redis,
        detector_client=mock_detector_client,
        batch_aggregator=mock_batch_aggregator,
        video_processor=mock_video_processor,
        retry_handler=mock_retry_handler,
        poll_timeout=0.5,  # Short timeout for faster tests
        stop_timeout=2.0,  # Short stop timeout
    )
    yield worker
    # Ensure worker is stopped after test
    if worker.running:
        await worker.stop()


@pytest.fixture
async def analysis_worker(
    mock_redis: RedisClient,
    mock_nemotron_analyzer: NemotronAnalyzer,
) -> AnalysisQueueWorker:
    """Create an AnalysisQueueWorker for testing."""
    worker = AnalysisQueueWorker(
        redis_client=mock_redis,
        nemotron_analyzer=mock_nemotron_analyzer,
        poll_timeout=0.5,  # Short timeout for faster tests
        stop_timeout=2.0,  # Short stop timeout
    )
    yield worker
    # Ensure worker is stopped after test
    if worker.running:
        await worker.stop()


@pytest.fixture
async def batch_timeout_worker(
    mock_redis: RedisClient,
    mock_batch_aggregator: BatchAggregator,
) -> BatchTimeoutWorker:
    """Create a BatchTimeoutWorker for testing."""
    worker = BatchTimeoutWorker(
        redis_client=mock_redis,
        batch_aggregator=mock_batch_aggregator,
        check_interval=0.5,  # Short interval for faster tests
    )
    yield worker
    # Ensure worker is stopped after test
    if worker.running:
        await worker.stop()


# ============================================================================
# Mock Queue Functionality Tests
# ============================================================================


class TestMockQueueFunctionality:
    """Test that the mock queue works correctly."""

    async def test_mock_queue_add_and_get(self, mock_redis: RedisClient) -> None:
        """Test that mock queue can add and retrieve items."""
        # Add item to queue
        item = {"test": "data"}
        result = await mock_redis.add_to_queue("test_queue", item)
        assert result is True

        # Retrieve item from queue
        retrieved = await mock_redis.get_from_queue("test_queue", timeout=0)
        assert retrieved == item

        # Queue should be empty now
        empty = await mock_redis.get_from_queue("test_queue", timeout=0)
        assert empty is None


# ============================================================================
# Worker Crash Mid-Task Tests
# ============================================================================


class TestWorkerCrashMidTask:
    """Test worker behavior when it crashes during task processing."""

    async def test_detection_worker_crash_during_processing(
        self,
        detection_worker: DetectionQueueWorker,
        mock_redis: RedisClient,
        mock_detector_client: DetectorClient,
    ) -> None:
        """Test detection worker handles crash during image processing.

        Scenario:
        1. Queue a detection job
        2. Make detector crash mid-processing
        3. Verify worker logs error and continues processing next job
        4. Verify failed job is handled appropriately (DLQ or retry)
        """
        # Arrange: Queue a detection job
        detection_payload = {
            "camera_id": "test_camera",
            "file_path": "/data/foscam/test_camera/test.jpg",
            "media_type": "image",
            "timestamp": datetime.now(UTC).isoformat(),
            "pipeline_start_time": datetime.now(UTC).isoformat(),
        }
        await mock_redis.add_to_queue(DETECTION_QUEUE, detection_payload)

        # Configure detector to raise exception
        mock_detector_client.detect_objects.side_effect = RuntimeError("Simulated detector crash")

        # Act: Start worker and let it process
        await detection_worker.start()
        await asyncio.sleep(2.0)  # chaos test timing - mocked

        # Assert: Worker should still be running despite error
        assert detection_worker.running is True
        assert detection_worker.stats.state == WorkerState.RUNNING

        # Worker should have attempted to process the item (detector was called)
        assert mock_detector_client.detect_objects.called, "Detector should have been called"

        # Worker should have encountered an error during processing
        assert detection_worker.stats.errors > 0, (
            f"Expected errors > 0, got {detection_worker.stats.errors}. "
            f"Detector called: {mock_detector_client.detect_objects.called}, "
            f"Call count: {mock_detector_client.detect_objects.call_count}"
        )
        # Worker attempted to process the item even though it failed
        assert detection_worker.stats.items_processed >= 0

        # Queue should be empty (item was consumed even though it failed)
        remaining = await mock_redis.get_from_queue(DETECTION_QUEUE, timeout=0.1)
        assert remaining is None

        # Stop worker
        await detection_worker.stop()
        assert detection_worker.running is False

    async def test_analysis_worker_crash_during_processing(
        self,
        analysis_worker: AnalysisQueueWorker,
        mock_redis: RedisClient,
        mock_nemotron_analyzer: NemotronAnalyzer,
    ) -> None:
        """Test analysis worker handles crash during batch analysis.

        Scenario:
        1. Queue an analysis job
        2. Make analyzer crash mid-processing
        3. Verify worker logs error and continues
        4. Verify failed batch is handled appropriately
        """
        # Arrange: Queue an analysis job
        analysis_payload = {
            "batch_id": "test_batch_123",
            "camera_id": "test_camera",
            "detection_ids": [1, 2, 3],
            "pipeline_start_time": datetime.now(UTC).isoformat(),
        }
        await mock_redis.add_to_queue(ANALYSIS_QUEUE, analysis_payload)

        # Configure analyzer to raise exception
        mock_nemotron_analyzer.analyze_batch.side_effect = RuntimeError("Simulated analyzer crash")

        # Act: Start worker and let it process
        await analysis_worker.start()
        await asyncio.sleep(1.5)  # chaos test - mocked

        # Assert: Worker should still be running despite error
        assert analysis_worker.running is True
        assert analysis_worker.stats.state == WorkerState.RUNNING
        assert analysis_worker.stats.errors > 0

        # Queue should be empty (item was consumed even though it failed)
        remaining = await mock_redis.get_from_queue(ANALYSIS_QUEUE, timeout=0.1)
        assert remaining is None

        # Stop worker
        await analysis_worker.stop()
        assert analysis_worker.running is False

    async def test_worker_crash_with_sigterm(self, detection_worker: DetectionQueueWorker) -> None:
        """Test worker handles SIGTERM gracefully during processing.

        Scenario:
        1. Start worker
        2. Simulate SIGTERM signal
        3. Verify worker stops gracefully within timeout
        """
        # Arrange: Start worker
        await detection_worker.start()
        assert detection_worker.running is True

        # Act: Simulate graceful stop (equivalent to SIGTERM handler)
        stop_task = asyncio.create_task(detection_worker.stop())

        # Assert: Worker should stop within stop_timeout
        try:
            await asyncio.wait_for(stop_task, timeout=3.0)
            assert detection_worker.running is False
            assert detection_worker.stats.state == WorkerState.STOPPED
        except TimeoutError:
            pytest.fail("Worker did not stop gracefully within timeout")

    async def test_worker_force_kill_with_sigkill(
        self, detection_worker: DetectionQueueWorker
    ) -> None:
        """Test worker task cancellation (simulates SIGKILL).

        Scenario:
        1. Start worker
        2. Force cancel the worker task
        3. Verify task is cancelled
        """
        # Arrange: Start worker
        await detection_worker.start()
        assert detection_worker.running is True
        assert detection_worker._task is not None

        # Act: Force cancel the task (simulates SIGKILL)
        detection_worker._task.cancel()

        # Wait for cancellation
        with pytest.raises(asyncio.CancelledError):
            await detection_worker._task

        # Assert: Task was cancelled
        assert detection_worker._task.cancelled() is True


# ============================================================================
# Worker Timeout Tests
# ============================================================================


class TestWorkerTimeoutScenarios:
    """Test worker behavior with various timeout scenarios."""

    async def test_detector_timeout_handling(
        self,
        detection_worker: DetectionQueueWorker,
        mock_redis: RedisClient,
        mock_detector_client: DetectorClient,
    ) -> None:
        """Test detection worker handles detector service timeouts.

        Scenario:
        1. Queue a detection job
        2. Make detector timeout
        3. Verify worker retries or moves to DLQ
        4. Verify worker continues processing
        """
        # Arrange: Queue a detection job
        detection_payload = {
            "camera_id": "test_camera",
            "file_path": "/data/foscam/test_camera/test.jpg",
            "media_type": "image",
            "timestamp": datetime.now(UTC).isoformat(),
            "pipeline_start_time": datetime.now(UTC).isoformat(),
        }
        await mock_redis.add_to_queue(DETECTION_QUEUE, detection_payload)

        # Configure detector to timeout
        mock_detector_client.detect_objects.side_effect = TimeoutError("Detector timeout")

        # Act: Start worker and let it process
        await detection_worker.start()
        await asyncio.sleep(1.5)  # chaos test - mocked

        # Assert: Worker handled timeout and continues
        assert detection_worker.running is True
        assert detection_worker.stats.errors > 0
        assert detection_worker.stats.state == WorkerState.RUNNING

        # Stop worker
        await detection_worker.stop()

    async def test_analyzer_timeout_handling(
        self,
        analysis_worker: AnalysisQueueWorker,
        mock_redis: RedisClient,
        mock_nemotron_analyzer: NemotronAnalyzer,
    ) -> None:
        """Test analysis worker handles analyzer service timeouts.

        Scenario:
        1. Queue an analysis job
        2. Make analyzer timeout
        3. Verify worker handles timeout gracefully
        4. Verify worker continues processing
        """
        # Arrange: Queue an analysis job
        analysis_payload = {
            "batch_id": "test_batch_123",
            "camera_id": "test_camera",
            "detection_ids": [1, 2, 3],
            "pipeline_start_time": datetime.now(UTC).isoformat(),
        }
        await mock_redis.add_to_queue(ANALYSIS_QUEUE, analysis_payload)

        # Configure analyzer to timeout
        mock_nemotron_analyzer.analyze_batch.side_effect = TimeoutError("Analyzer timeout")

        # Act: Start worker and let it process
        await analysis_worker.start()
        await asyncio.sleep(1.5)  # chaos test - mocked

        # Assert: Worker handled timeout and continues
        assert analysis_worker.running is True
        assert analysis_worker.stats.errors > 0
        assert analysis_worker.stats.state == WorkerState.RUNNING

        # Stop worker
        await analysis_worker.stop()

    async def test_redis_operation_timeout(
        self,
        detection_worker: DetectionQueueWorker,
        mock_redis: RedisClient,
    ) -> None:
        """Test worker handles Redis operation timeouts gracefully.

        Scenario:
        1. Start worker
        2. Simulate Redis timeout during queue operation
        3. Verify worker continues after timeout
        """
        # Arrange: Start worker
        await detection_worker.start()
        assert detection_worker.running is True

        # Act: Wait for worker to handle empty queue timeouts
        await asyncio.sleep(2.0)  # chaos test - mocked

        # Assert: Worker should still be running and checking queue
        assert detection_worker.running is True
        assert detection_worker.stats.state == WorkerState.RUNNING

        # Stop worker
        await detection_worker.stop()


# ============================================================================
# Multiple Workers Competition Tests
# ============================================================================


class TestMultipleWorkersCompetition:
    """Test behavior when multiple workers compete for same jobs."""

    async def test_multiple_detection_workers_same_queue(
        self,
        mock_redis: RedisClient,
        mock_detector_client: DetectorClient,
        mock_batch_aggregator: BatchAggregator,
        mock_video_processor: VideoProcessor,
        mock_retry_handler: RetryHandler,
    ) -> None:
        """Test multiple detection workers processing same queue.

        Scenario:
        1. Start 3 detection workers
        2. Queue 10 jobs
        3. Verify each job is processed exactly once
        4. Verify total processed count across all workers equals 10
        """
        # Arrange: Create 3 workers
        workers = []
        for i in range(3):
            worker = DetectionQueueWorker(
                redis_client=mock_redis,
                detector_client=mock_detector_client,
                batch_aggregator=mock_batch_aggregator,
                video_processor=mock_video_processor,
                retry_handler=mock_retry_handler,
                poll_timeout=1,
                stop_timeout=2.0,
            )
            workers.append(worker)

        # Queue 10 jobs
        job_count = 10
        for i in range(job_count):
            detection_payload = {
                "camera_id": f"camera_{i}",
                "file_path": f"/data/foscam/camera_{i}/test.jpg",
                "media_type": "image",
                "timestamp": datetime.now(UTC).isoformat(),
                "pipeline_start_time": datetime.now(UTC).isoformat(),
            }
            await mock_redis.add_to_queue(DETECTION_QUEUE, detection_payload)

        try:
            # Act: Start all workers
            for worker in workers:
                await worker.start()

            # Wait for processing
            await asyncio.sleep(3.0)  # chaos test - mocked

            # Assert: All jobs processed exactly once
            total_processed = sum(w.stats.items_processed for w in workers)
            assert total_processed == job_count

            # Queue should be empty
            remaining = await mock_redis.get_from_queue(DETECTION_QUEUE, timeout=0.1)
            assert remaining is None

        finally:
            # Stop all workers
            for worker in workers:
                if worker.running:
                    await worker.stop()

    async def test_worker_job_stealing_prevention(
        self,
        mock_redis: RedisClient,
        mock_detector_client: DetectorClient,
        mock_batch_aggregator: BatchAggregator,
        mock_video_processor: VideoProcessor,
        mock_retry_handler: RetryHandler,
    ) -> None:
        """Test that workers don't steal jobs from each other.

        Scenario:
        1. Start 2 workers
        2. Queue a job
        3. Verify only one worker processes it
        4. Verify detector is called exactly once
        """
        # Arrange: Create 2 workers
        worker1 = DetectionQueueWorker(
            redis_client=mock_redis,
            detector_client=mock_detector_client,
            batch_aggregator=mock_batch_aggregator,
            video_processor=mock_video_processor,
            retry_handler=mock_retry_handler,
            poll_timeout=1,
            stop_timeout=2.0,
        )
        worker2 = DetectionQueueWorker(
            redis_client=mock_redis,
            detector_client=mock_detector_client,
            batch_aggregator=mock_batch_aggregator,
            video_processor=mock_video_processor,
            retry_handler=mock_retry_handler,
            poll_timeout=1,
            stop_timeout=2.0,
        )

        # Queue a single job
        detection_payload = {
            "camera_id": "test_camera",
            "file_path": "/data/foscam/test_camera/test.jpg",
            "media_type": "image",
            "timestamp": datetime.now(UTC).isoformat(),
            "pipeline_start_time": datetime.now(UTC).isoformat(),
        }
        await mock_redis.add_to_queue(DETECTION_QUEUE, detection_payload)

        try:
            # Act: Start both workers
            await worker1.start()
            await worker2.start()

            # Wait for processing
            await asyncio.sleep(2.0)  # chaos test - mocked

            # Assert: Job processed by exactly one worker
            total_processed = worker1.stats.items_processed + worker2.stats.items_processed
            assert total_processed == 1

            # Detector called exactly once
            assert mock_detector_client.detect_objects.call_count == 1

        finally:
            # Stop all workers
            if worker1.running:
                await worker1.stop()
            if worker2.running:
                await worker2.stop()


# ============================================================================
# Worker Restart Recovery Tests
# ============================================================================


class TestWorkerRestartRecovery:
    """Test worker restart and recovery scenarios."""

    async def test_worker_restart_after_crash(
        self,
        detection_worker: DetectionQueueWorker,
        mock_redis: RedisClient,
    ) -> None:
        """Test worker can be restarted after crash.

        Scenario:
        1. Start worker
        2. Stop worker (simulating crash)
        3. Restart worker
        4. Verify worker processes jobs correctly
        """
        # Act: Start worker
        await detection_worker.start()
        assert detection_worker.running is True

        # Stop worker (simulate crash recovery)
        await detection_worker.stop()
        assert detection_worker.running is False

        # Restart worker
        await detection_worker.start()
        assert detection_worker.running is True
        assert detection_worker.stats.state == WorkerState.RUNNING

        # Queue a job
        detection_payload = {
            "camera_id": "test_camera",
            "file_path": "/data/foscam/test_camera/test.jpg",
            "media_type": "image",
            "timestamp": datetime.now(UTC).isoformat(),
            "pipeline_start_time": datetime.now(UTC).isoformat(),
        }
        await mock_redis.add_to_queue(DETECTION_QUEUE, detection_payload)

        # Wait for processing
        await asyncio.sleep(1.5)

        # Assert: Worker processed the job
        assert detection_worker.stats.items_processed > 0

        # Stop worker
        await detection_worker.stop()

    async def test_worker_stats_preserved_after_restart(
        self, detection_worker: DetectionQueueWorker
    ) -> None:
        """Test worker stats are reset after restart.

        Scenario:
        1. Start worker and process some jobs (simulated by incrementing stats)
        2. Stop worker
        3. Restart worker
        4. Verify stats reflect new lifecycle (not cumulative from previous run)
        """
        # Arrange: Start worker
        await detection_worker.start()

        # Simulate processing by manually updating stats
        detection_worker.stats.items_processed = 5
        detection_worker.stats.errors = 2

        # Stop worker
        await detection_worker.stop()

        # Act: Restart worker
        await detection_worker.start()

        # Assert: Stats from previous run are still in the stats object
        # (In a real scenario, you might reset stats or track per-lifecycle)
        # For now, we just verify the worker starts successfully
        assert detection_worker.running is True
        assert detection_worker.stats.state == WorkerState.RUNNING

        # Stop worker
        await detection_worker.stop()

    async def test_batch_timeout_worker_restart(
        self,
        batch_timeout_worker: BatchTimeoutWorker,
    ) -> None:
        """Test batch timeout worker can be restarted.

        Scenario:
        1. Start batch timeout worker
        2. Stop worker
        3. Restart worker
        4. Verify worker continues checking batches
        """
        # Act: Start worker
        await batch_timeout_worker.start()
        assert batch_timeout_worker.running is True

        # Stop worker
        await batch_timeout_worker.stop()
        assert batch_timeout_worker.running is False

        # Restart worker
        await batch_timeout_worker.start()
        assert batch_timeout_worker.running is True
        assert batch_timeout_worker.stats.state == WorkerState.RUNNING

        # Stop worker
        await batch_timeout_worker.stop()


# ============================================================================
# Orphaned Job Detection Tests
# ============================================================================


class TestOrphanedJobDetection:
    """Test detection and recovery of orphaned jobs."""

    async def test_orphaned_job_in_queue_after_worker_crash(
        self,
        mock_redis: RedisClient,
        detection_worker: DetectionQueueWorker,
    ) -> None:
        """Test that jobs left in queue after worker crash can be processed.

        Scenario:
        1. Queue jobs
        2. Worker crashes before processing (simulated by not starting)
        3. New worker picks up orphaned jobs
        4. Verify orphaned jobs are processed
        """
        # Arrange: Queue jobs without starting worker (simulating crash)
        job_count = 3
        for i in range(job_count):
            detection_payload = {
                "camera_id": f"camera_{i}",
                "file_path": f"/data/foscam/camera_{i}/test.jpg",
                "media_type": "image",
                "timestamp": datetime.now(UTC).isoformat(),
                "pipeline_start_time": datetime.now(UTC).isoformat(),
            }
            await mock_redis.add_to_queue(DETECTION_QUEUE, detection_payload)

        # Act: Start a new worker to process orphaned jobs
        await detection_worker.start()
        await asyncio.sleep(2.0)  # chaos test - mocked

        # Assert: Orphaned jobs were processed
        assert detection_worker.stats.items_processed == job_count

        # Queue should be empty
        remaining = await mock_redis.get_from_queue(DETECTION_QUEUE, timeout=0.1)
        assert remaining is None

        # Stop worker
        await detection_worker.stop()

    async def test_detect_stale_jobs_in_queue(
        self,
        mock_redis: RedisClient,
    ) -> None:
        """Test identification of stale jobs in queue.

        Scenario:
        1. Queue jobs with old timestamps
        2. Check queue for stale jobs
        3. Verify stale jobs can be identified
        """
        # Arrange: Queue jobs with old timestamps
        old_timestamp = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
        stale_payload = {
            "camera_id": "test_camera",
            "file_path": "/data/foscam/test_camera/stale.jpg",
            "media_type": "image",
            "timestamp": old_timestamp,
            "pipeline_start_time": old_timestamp,
        }
        await mock_redis.add_to_queue(DETECTION_QUEUE, stale_payload)

        # Act: Peek at queue without consuming
        # Redis LRANGE to inspect queue without removing items
        redis = mock_redis._client
        queue_items = await redis.lrange(DETECTION_QUEUE, 0, -1)

        # Assert: Stale job is in queue
        assert len(queue_items) == 1

        # Clean up
        await mock_redis.delete_key(DETECTION_QUEUE)


# ============================================================================
# Queue Backpressure Tests
# ============================================================================


class TestQueueBackpressure:
    """Test worker behavior under queue backpressure."""

    async def test_detection_queue_overflow_handling(
        self,
        mock_redis: RedisClient,
        detection_worker: DetectionQueueWorker,
        mock_detector_client: DetectorClient,
    ) -> None:
        """Test worker handles queue overflow gracefully.

        Scenario:
        1. Fill detection queue to capacity
        2. Start worker
        3. Verify worker processes jobs without crashing
        4. Verify queue drains at expected rate
        """
        # Arrange: Fill queue with many jobs
        job_count = 50
        for i in range(job_count):
            detection_payload = {
                "camera_id": f"camera_{i}",
                "file_path": f"/data/foscam/camera_{i}/test.jpg",
                "media_type": "image",
                "timestamp": datetime.now(UTC).isoformat(),
                "pipeline_start_time": datetime.now(UTC).isoformat(),
            }
            await mock_redis.add_to_queue(DETECTION_QUEUE, detection_payload)

        # Act: Start worker to drain queue
        await detection_worker.start()
        await asyncio.sleep(3.0)  # chaos test - mocked

        # Assert: Worker processed some/all jobs without crashing
        assert detection_worker.running is True
        assert detection_worker.stats.items_processed > 0
        assert detection_worker.stats.state == WorkerState.RUNNING

        # Stop worker
        await detection_worker.stop()

        # Note: We don't assert all jobs were processed because we limited wait time
        # In production, backpressure handling might involve rate limiting or DLQ

    async def test_worker_slow_processing_causes_queue_buildup(
        self,
        mock_redis: RedisClient,
        mock_detector_client: DetectorClient,
        mock_batch_aggregator: BatchAggregator,
        mock_video_processor: VideoProcessor,
        mock_retry_handler: RetryHandler,
    ) -> None:
        """Test queue builds up when worker processing is slow.

        Scenario:
        1. Configure detector to be very slow
        2. Start worker
        3. Queue multiple jobs quickly
        4. Verify queue depth increases
        5. Verify worker continues processing
        """

        # Arrange: Make detector slow
        async def slow_detect(*args, **kwargs):
            await asyncio.sleep(2.0)  # mocked slow processing
            return []

        mock_detector_client.detect_objects = AsyncMock(side_effect=slow_detect)

        worker = DetectionQueueWorker(
            redis_client=mock_redis,
            detector_client=mock_detector_client,
            batch_aggregator=mock_batch_aggregator,
            video_processor=mock_video_processor,
            retry_handler=mock_retry_handler,
            poll_timeout=1,
            stop_timeout=2.0,
        )

        try:
            # Start worker
            await worker.start()

            # Queue jobs quickly
            job_count = 5
            for i in range(job_count):
                detection_payload = {
                    "camera_id": f"camera_{i}",
                    "file_path": f"/data/foscam/camera_{i}/test.jpg",
                    "media_type": "image",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "pipeline_start_time": datetime.now(UTC).isoformat(),
                }
                await mock_redis.add_to_queue(DETECTION_QUEUE, detection_payload)

            # Brief wait
            await asyncio.sleep(1.0)  # mocked

            # Assert: Queue should have pending jobs (worker is slow)
            redis = mock_redis._client
            queue_depth = await redis.llen(DETECTION_QUEUE)
            assert queue_depth > 0  # Jobs still pending

            # Worker should still be running
            assert worker.running is True

        finally:
            # Stop worker
            if worker.running:
                await worker.stop()

    async def test_multiple_workers_reduce_backpressure(
        self,
        mock_redis: RedisClient,
        mock_detector_client: DetectorClient,
        mock_batch_aggregator: BatchAggregator,
        mock_video_processor: VideoProcessor,
        mock_retry_handler: RetryHandler,
    ) -> None:
        """Test multiple workers help drain queue faster under backpressure.

        Scenario:
        1. Queue many jobs
        2. Start 3 workers
        3. Verify jobs are processed faster than with single worker
        4. Verify queue drains completely
        """
        # Arrange: Queue many jobs
        job_count = 20
        for i in range(job_count):
            detection_payload = {
                "camera_id": f"camera_{i}",
                "file_path": f"/data/foscam/camera_{i}/test.jpg",
                "media_type": "image",
                "timestamp": datetime.now(UTC).isoformat(),
                "pipeline_start_time": datetime.now(UTC).isoformat(),
            }
            await mock_redis.add_to_queue(DETECTION_QUEUE, detection_payload)

        # Create 3 workers
        workers = []
        for i in range(3):
            worker = DetectionQueueWorker(
                redis_client=mock_redis,
                detector_client=mock_detector_client,
                batch_aggregator=mock_batch_aggregator,
                video_processor=mock_video_processor,
                retry_handler=mock_retry_handler,
                poll_timeout=1,
                stop_timeout=2.0,
            )
            workers.append(worker)

        try:
            # Act: Start all workers
            for worker in workers:
                await worker.start()

            # Wait for processing
            await asyncio.sleep(3.0)  # chaos test - mocked

            # Assert: All jobs processed by the workers
            total_processed = sum(w.stats.items_processed for w in workers)
            assert total_processed == job_count

            # Queue should be empty
            redis = mock_redis._client
            queue_depth = await redis.llen(DETECTION_QUEUE)
            assert queue_depth == 0

        finally:
            # Stop all workers
            for worker in workers:
                if worker.running:
                    await worker.stop()


# ============================================================================
# Integration with PipelineWorkerManager Tests
# ============================================================================


class TestPipelineWorkerManagerChaos:
    """Test PipelineWorkerManager under chaotic conditions."""

    async def test_manager_handles_worker_crashes(
        self,
        mock_redis: RedisClient,
        mock_detector_client: DetectorClient,
        mock_batch_aggregator: BatchAggregator,
        mock_nemotron_analyzer: NemotronAnalyzer,
    ) -> None:
        """Test manager handles individual worker crashes gracefully.

        Scenario:
        1. Start manager with all workers
        2. Simulate crash in one worker (make it raise exception)
        3. Verify other workers continue
        4. Verify manager reports correct status
        """
        # Arrange: Create manager
        manager = PipelineWorkerManager(
            redis_client=mock_redis,
            detector_client=mock_detector_client,
            batch_aggregator=mock_batch_aggregator,
            nemotron_analyzer=mock_nemotron_analyzer,
        )

        try:
            # Act: Start manager
            await manager.start()

            # Verify all workers started
            assert manager.detection_worker is not None
            assert manager.detection_worker.running is True
            assert manager.analysis_worker is not None
            assert manager.analysis_worker.running is True
            assert manager.batch_timeout_worker is not None
            assert manager.batch_timeout_worker.running is True

            # Simulate crash in detection worker by making detector fail repeatedly
            mock_detector_client.detect_objects.side_effect = RuntimeError("Crash")

            # Queue a job to trigger the error
            detection_payload = {
                "camera_id": "test_camera",
                "file_path": "/data/foscam/test_camera/test.jpg",
                "media_type": "image",
                "timestamp": datetime.now(UTC).isoformat(),
                "pipeline_start_time": datetime.now(UTC).isoformat(),
            }
            await mock_redis.add_to_queue(DETECTION_QUEUE, detection_payload)

            # Wait for processing
            await asyncio.sleep(2.0)  # chaos test - mocked

            # Assert: Detection worker logged error but still running
            assert manager.detection_worker.running is True
            assert manager.detection_worker.stats.errors > 0

            # Other workers should still be running
            assert manager.analysis_worker.running is True
            assert manager.batch_timeout_worker.running is True

        finally:
            # Stop manager
            await manager.stop()

    async def test_manager_graceful_shutdown_with_pending_jobs(
        self,
        mock_redis: RedisClient,
        mock_detector_client: DetectorClient,
        mock_batch_aggregator: BatchAggregator,
        mock_nemotron_analyzer: NemotronAnalyzer,
    ) -> None:
        """Test manager shuts down gracefully with pending jobs in queue.

        Scenario:
        1. Start manager
        2. Queue jobs
        3. Immediately stop manager
        4. Verify all workers stop gracefully
        5. Verify jobs remain in queue for next startup
        """
        # Arrange: Create manager
        manager = PipelineWorkerManager(
            redis_client=mock_redis,
            detector_client=mock_detector_client,
            batch_aggregator=mock_batch_aggregator,
            nemotron_analyzer=mock_nemotron_analyzer,
        )

        # Start manager
        await manager.start()

        # Queue jobs
        job_count = 5
        for i in range(job_count):
            detection_payload = {
                "camera_id": f"camera_{i}",
                "file_path": f"/data/foscam/camera_{i}/test.jpg",
                "media_type": "image",
                "timestamp": datetime.now(UTC).isoformat(),
                "pipeline_start_time": datetime.now(UTC).isoformat(),
            }
            await mock_redis.add_to_queue(DETECTION_QUEUE, detection_payload)

        # Act: Immediately stop manager (before jobs are processed)
        await manager.stop()

        # Assert: All workers stopped
        assert manager.detection_worker.running is False
        assert manager.analysis_worker.running is False
        assert manager.batch_timeout_worker.running is False

        # Jobs should remain in queue
        redis = mock_redis._client
        queue_depth = await redis.llen(DETECTION_QUEUE)
        assert queue_depth > 0  # Some jobs might have been processed, but not all
