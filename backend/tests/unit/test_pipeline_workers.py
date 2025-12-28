"""Unit tests for pipeline workers.

Tests cover:
- Worker lifecycle (start/stop/idempotency)
- Queue consumer loops
- Graceful shutdown handling
- Error recovery
- Statistics tracking
- Timeout handling during stop
- Signal handler installation
- Queue metrics worker
"""

import asyncio
import signal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.pipeline_workers import (
    AnalysisQueueWorker,
    BatchTimeoutWorker,
    DetectionQueueWorker,
    PipelineWorkerManager,
    QueueMetricsWorker,
    WorkerState,
    WorkerStats,
    get_pipeline_manager,
    stop_pipeline_manager,
)

# Fixtures


# Test constants - use short timeouts for fast tests
TEST_STOP_TIMEOUT = 0.5  # Fast stop timeout for tests (instead of 10-30s)
TEST_POLL_TIMEOUT = 1  # Fast poll timeout for tests


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client.

    IMPORTANT: get_from_queue must yield control to the event loop,
    otherwise the worker loop will spin without checking _running flag.
    """
    client = MagicMock()

    async def mock_get_from_queue(*args, **kwargs):
        """Mock that yields control like real BLPOP would."""
        await asyncio.sleep(0.01)  # Yield control to event loop

    client.get_from_queue = mock_get_from_queue
    client.add_to_queue = AsyncMock(return_value=1)
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    client.get_queue_length = AsyncMock(return_value=0)
    client._client = MagicMock()
    client._client.keys = AsyncMock(return_value=[])
    return client


@pytest.fixture
def mock_detector_client():
    """Create a mock detector client."""
    client = MagicMock()
    client.detect_objects = AsyncMock(return_value=[])
    client.health_check = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_batch_aggregator():
    """Create a mock batch aggregator."""
    aggregator = MagicMock()
    aggregator.add_detection = AsyncMock(return_value="batch_123")
    aggregator.check_batch_timeouts = AsyncMock(return_value=[])
    aggregator.close_batch = AsyncMock(return_value={"batch_id": "test"})
    return aggregator


@pytest.fixture
def mock_analyzer():
    """Create a mock Nemotron analyzer."""
    analyzer = MagicMock()
    event = MagicMock()
    event.id = 1
    event.risk_score = 50
    event.risk_level = "medium"
    analyzer.analyze_batch = AsyncMock(return_value=event)
    analyzer.health_check = AsyncMock(return_value=True)
    return analyzer


# WorkerStats tests


def test_worker_stats_initialization():
    """Test WorkerStats initializes with zero values."""
    stats = WorkerStats()

    assert stats.items_processed == 0
    assert stats.errors == 0
    assert stats.last_processed_at is None
    assert stats.state == WorkerState.STOPPED


def test_worker_stats_to_dict():
    """Test WorkerStats converts to dictionary."""
    stats = WorkerStats()
    stats.items_processed = 10
    stats.errors = 2
    stats.last_processed_at = 1234567890.0
    stats.state = WorkerState.RUNNING

    result = stats.to_dict()

    assert result == {
        "items_processed": 10,
        "errors": 2,
        "last_processed_at": 1234567890.0,
        "state": "running",
    }


def test_worker_state_values():
    """Test WorkerState enum values."""
    assert WorkerState.STOPPED.value == "stopped"
    assert WorkerState.STARTING.value == "starting"
    assert WorkerState.RUNNING.value == "running"
    assert WorkerState.STOPPING.value == "stopping"
    assert WorkerState.ERROR.value == "error"


# DetectionQueueWorker tests


@pytest.mark.asyncio
async def test_detection_worker_initialization(mock_redis_client, mock_detector_client):
    """Test DetectionQueueWorker initializes correctly."""
    worker = DetectionQueueWorker(
        redis_client=mock_redis_client,
        detector_client=mock_detector_client,
        queue_name="test_queue",
        poll_timeout=1,
    )

    assert worker.running is False
    assert worker.stats.state == WorkerState.STOPPED
    assert worker._queue_name == "test_queue"
    assert worker._poll_timeout == 1


@pytest.mark.asyncio
async def test_detection_worker_start_stop(mock_redis_client, mock_detector_client):
    """Test DetectionQueueWorker start and stop lifecycle."""
    worker = DetectionQueueWorker(
        redis_client=mock_redis_client,
        detector_client=mock_detector_client,
        poll_timeout=TEST_POLL_TIMEOUT,
        stop_timeout=TEST_STOP_TIMEOUT,
    )

    # Start worker
    await worker.start()
    assert worker.running is True
    assert worker.stats.state == WorkerState.RUNNING
    assert worker._task is not None

    # Allow loop to run briefly
    await asyncio.sleep(0.1)

    # Stop worker
    await worker.stop()
    assert worker.running is False
    assert worker.stats.state == WorkerState.STOPPED
    assert worker._task is None


@pytest.mark.asyncio
async def test_detection_worker_idempotent_start(mock_redis_client, mock_detector_client):
    """Test starting DetectionQueueWorker multiple times is idempotent."""
    worker = DetectionQueueWorker(
        redis_client=mock_redis_client,
        detector_client=mock_detector_client,
        poll_timeout=TEST_POLL_TIMEOUT,
        stop_timeout=TEST_STOP_TIMEOUT,
    )

    await worker.start()
    first_task = worker._task

    # Start again - should not create new task
    await worker.start()
    assert worker._task is first_task

    await worker.stop()


@pytest.mark.asyncio
async def test_detection_worker_idempotent_stop(mock_redis_client, mock_detector_client):
    """Test stopping DetectionQueueWorker multiple times is safe."""
    worker = DetectionQueueWorker(
        redis_client=mock_redis_client,
        detector_client=mock_detector_client,
    )

    # Stop without starting - should not raise
    await worker.stop()
    assert worker.running is False

    # Start then stop twice
    await worker.start()
    await worker.stop()
    await worker.stop()
    assert worker.running is False


@pytest.mark.asyncio
async def test_detection_worker_processes_item(
    mock_redis_client, mock_detector_client, mock_batch_aggregator
):
    """Test DetectionQueueWorker processes queue items."""
    # Setup mock to return one item then None
    call_count = 0

    async def mock_get_from_queue(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)  # Yield control to event loop
        if call_count == 1:
            return {
                "camera_id": "front_door",
                "file_path": "/path/to/image.jpg",
                "timestamp": datetime.now().isoformat(),
            }
        return None

    mock_redis_client.get_from_queue = mock_get_from_queue

    # Setup detector to return a detection
    detection = MagicMock()
    detection.id = 1
    detection.confidence = 0.95
    detection.object_type = "person"
    mock_detector_client.detect_objects = AsyncMock(return_value=[detection])

    worker = DetectionQueueWorker(
        redis_client=mock_redis_client,
        detector_client=mock_detector_client,
        batch_aggregator=mock_batch_aggregator,
        poll_timeout=1,
    )

    # Mock database session
    with patch("backend.services.pipeline_workers.get_session") as mock_get_session:
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        await worker.start()
        await asyncio.sleep(0.2)  # Let loop process
        await worker.stop()

    # Verify detection was processed
    assert worker.stats.items_processed == 1
    assert worker.stats.last_processed_at is not None
    mock_batch_aggregator.add_detection.assert_called_once()


@pytest.mark.asyncio
async def test_detection_worker_handles_invalid_item(mock_redis_client, mock_detector_client):
    """Test DetectionQueueWorker handles invalid queue items gracefully."""
    call_count = 0

    async def mock_get_from_queue(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)  # Yield control to event loop
        if call_count == 1:
            return {"invalid": "item"}  # Missing camera_id and file_path
        return None

    mock_redis_client.get_from_queue = mock_get_from_queue

    worker = DetectionQueueWorker(
        redis_client=mock_redis_client,
        detector_client=mock_detector_client,
        poll_timeout=1,
    )

    await worker.start()
    await asyncio.sleep(0.1)
    await worker.stop()

    # Should not increment items_processed for invalid items
    assert worker.stats.items_processed == 0
    # Should not count as error either (just skip)
    assert worker.stats.errors == 0


@pytest.mark.asyncio
async def test_detection_worker_error_recovery(
    mock_redis_client, mock_detector_client, mock_batch_aggregator
):
    """Test DetectionQueueWorker recovers from errors."""
    call_count = 0

    async def mock_get_from_queue(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)  # Yield control to event loop
        if call_count <= 3:
            return {
                "camera_id": "cam1",
                "file_path": "/path/to/image.jpg",
                "timestamp": datetime.now().isoformat(),
            }
        return None

    mock_redis_client.get_from_queue = mock_get_from_queue

    # Detector fails on first call, succeeds on subsequent
    detect_call_count = 0

    async def mock_detect_objects(*args, **kwargs):
        nonlocal detect_call_count
        detect_call_count += 1
        if detect_call_count == 1:
            raise Exception("Detection error")
        return []

    mock_detector_client.detect_objects = mock_detect_objects

    worker = DetectionQueueWorker(
        redis_client=mock_redis_client,
        detector_client=mock_detector_client,
        batch_aggregator=mock_batch_aggregator,
        poll_timeout=1,
    )

    with patch("backend.services.pipeline_workers.get_session") as mock_get_session:
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        await worker.start()
        await asyncio.sleep(0.3)
        await worker.stop()

    # Should have 1 error and 2 successes
    assert worker.stats.errors == 1
    assert worker.stats.items_processed == 2


@pytest.mark.asyncio
async def test_detection_worker_stop_timeout_forces_cancel(mock_redis_client, mock_detector_client):
    """Test DetectionQueueWorker cancels task when stop times out (lines 165-171)."""
    # Create a worker with very short stop timeout
    worker = DetectionQueueWorker(
        redis_client=mock_redis_client,
        detector_client=mock_detector_client,
        poll_timeout=TEST_POLL_TIMEOUT,
        stop_timeout=0.01,  # Very short timeout
    )

    # Create a mock task that takes a long time to complete
    async def long_running_loop():
        while True:
            await asyncio.sleep(1.0)  # cancelled - task is cancelled in test

    await worker.start()
    # Replace the task with one that won't stop easily
    original_task = worker._task
    worker._task = asyncio.create_task(long_running_loop())
    # Cancel the original task
    if original_task:
        original_task.cancel()
        try:
            await original_task
        except asyncio.CancelledError:
            pass

    # Stop should timeout and force cancel
    await worker.stop()

    assert worker.running is False
    assert worker.stats.state == WorkerState.STOPPED
    assert worker._task is None


@pytest.mark.asyncio
async def test_detection_worker_loop_cancelled_error(mock_redis_client, mock_detector_client):
    """Test DetectionQueueWorker handles CancelledError in loop (lines 195-197)."""
    call_count = 0

    async def mock_get_from_queue_that_raises(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            await asyncio.sleep(0.01)
            return None
        # On second call, raise CancelledError
        raise asyncio.CancelledError()

    mock_redis_client.get_from_queue = mock_get_from_queue_that_raises

    worker = DetectionQueueWorker(
        redis_client=mock_redis_client,
        detector_client=mock_detector_client,
        poll_timeout=TEST_POLL_TIMEOUT,
        stop_timeout=TEST_STOP_TIMEOUT,
    )

    await worker.start()
    await asyncio.sleep(0.1)
    # The loop should have exited due to CancelledError
    # Force stop to clean up
    worker._running = False
    if worker._task and not worker._task.done():
        worker._task.cancel()
        try:
            await worker._task
        except asyncio.CancelledError:
            pass
    worker._task = None
    worker._stats.state = WorkerState.STOPPED


@pytest.mark.asyncio
async def test_detection_worker_loop_general_exception_recovery(
    mock_redis_client, mock_detector_client
):
    """Test DetectionQueueWorker recovers from general exceptions (lines 198-209)."""
    call_count = 0

    async def mock_get_from_queue_that_raises(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Simulated Redis connection error")
        await asyncio.sleep(0.01)

    mock_redis_client.get_from_queue = mock_get_from_queue_that_raises

    worker = DetectionQueueWorker(
        redis_client=mock_redis_client,
        detector_client=mock_detector_client,
        poll_timeout=TEST_POLL_TIMEOUT,
        stop_timeout=TEST_STOP_TIMEOUT,
    )

    with patch("backend.services.pipeline_workers.record_pipeline_error") as mock_record:
        await worker.start()
        await asyncio.sleep(0.2)  # Allow time for error recovery
        await worker.stop()

        # Should have recorded the error
        mock_record.assert_called_with("detection_worker_error")

    # Worker should have recovered and be in stopped state
    assert worker.stats.errors >= 1
    assert worker.stats.state == WorkerState.STOPPED


# AnalysisQueueWorker tests


@pytest.mark.asyncio
async def test_analysis_worker_initialization(mock_redis_client, mock_analyzer):
    """Test AnalysisQueueWorker initializes correctly."""
    worker = AnalysisQueueWorker(
        redis_client=mock_redis_client,
        analyzer=mock_analyzer,
        queue_name="test_analysis_queue",
        poll_timeout=2,
    )

    assert worker.running is False
    assert worker.stats.state == WorkerState.STOPPED
    assert worker._queue_name == "test_analysis_queue"
    assert worker._poll_timeout == 2


@pytest.mark.asyncio
async def test_analysis_worker_start_stop(mock_redis_client, mock_analyzer):
    """Test AnalysisQueueWorker start and stop lifecycle."""
    worker = AnalysisQueueWorker(
        redis_client=mock_redis_client,
        analyzer=mock_analyzer,
        poll_timeout=1,
    )

    await worker.start()
    assert worker.running is True
    assert worker.stats.state == WorkerState.RUNNING

    await asyncio.sleep(0.1)

    await worker.stop()
    assert worker.running is False
    assert worker.stats.state == WorkerState.STOPPED


@pytest.mark.asyncio
async def test_analysis_worker_idempotent_start(mock_redis_client, mock_analyzer):
    """Test starting AnalysisQueueWorker multiple times is idempotent (lines 334-335)."""
    worker = AnalysisQueueWorker(
        redis_client=mock_redis_client,
        analyzer=mock_analyzer,
        poll_timeout=TEST_POLL_TIMEOUT,
        stop_timeout=TEST_STOP_TIMEOUT,
    )

    await worker.start()
    first_task = worker._task

    # Start again - should not create new task
    await worker.start()
    assert worker._task is first_task

    await worker.stop()


@pytest.mark.asyncio
async def test_analysis_worker_idempotent_stop(mock_redis_client, mock_analyzer):
    """Test stopping AnalysisQueueWorker multiple times is safe (lines 346-347)."""
    worker = AnalysisQueueWorker(
        redis_client=mock_redis_client,
        analyzer=mock_analyzer,
    )

    # Stop without starting - should not raise
    await worker.stop()
    assert worker.running is False

    # Start then stop twice
    await worker.start()
    await worker.stop()
    await worker.stop()
    assert worker.running is False


@pytest.mark.asyncio
async def test_analysis_worker_processes_batch(mock_redis_client, mock_analyzer):
    """Test AnalysisQueueWorker processes analysis queue items."""
    call_count = 0

    async def mock_get_from_queue(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)  # Yield control to event loop
        if call_count == 1:
            return {
                "batch_id": "batch_123",
                "camera_id": "front_door",
                "detection_ids": [1, 2, 3],
            }
        return None

    mock_redis_client.get_from_queue = mock_get_from_queue

    worker = AnalysisQueueWorker(
        redis_client=mock_redis_client,
        analyzer=mock_analyzer,
        poll_timeout=1,
    )

    await worker.start()
    await asyncio.sleep(0.2)
    await worker.stop()

    assert worker.stats.items_processed == 1
    # Worker now passes camera_id and detection_ids from queue payload
    mock_analyzer.analyze_batch.assert_called_once_with(
        batch_id="batch_123",
        camera_id="front_door",
        detection_ids=[1, 2, 3],
    )


@pytest.mark.asyncio
async def test_analysis_worker_handles_value_error(mock_redis_client, mock_analyzer):
    """Test AnalysisQueueWorker handles ValueError gracefully (batch not found)."""
    call_count = 0

    async def mock_get_from_queue(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)  # Yield control to event loop
        if call_count == 1:
            return {"batch_id": "missing_batch", "camera_id": "cam1"}
        return None

    mock_redis_client.get_from_queue = mock_get_from_queue
    mock_analyzer.analyze_batch = AsyncMock(side_effect=ValueError("Batch not found"))

    worker = AnalysisQueueWorker(
        redis_client=mock_redis_client,
        analyzer=mock_analyzer,
        poll_timeout=1,
    )

    await worker.start()
    await asyncio.sleep(0.2)
    await worker.stop()

    # ValueError should not increment error count (expected case)
    assert worker.stats.errors == 0
    assert worker.stats.items_processed == 0


@pytest.mark.asyncio
async def test_analysis_worker_handles_invalid_item(mock_redis_client, mock_analyzer):
    """Test AnalysisQueueWorker handles invalid queue items (lines 417-418)."""
    call_count = 0

    async def mock_get_from_queue(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        if call_count == 1:
            return {"camera_id": "cam1"}  # Missing batch_id
        return None

    mock_redis_client.get_from_queue = mock_get_from_queue

    worker = AnalysisQueueWorker(
        redis_client=mock_redis_client,
        analyzer=mock_analyzer,
        poll_timeout=1,
    )

    await worker.start()
    await asyncio.sleep(0.1)
    await worker.stop()

    # Should not increment items_processed for invalid items
    assert worker.stats.items_processed == 0
    # analyze_batch should not have been called
    mock_analyzer.analyze_batch.assert_not_called()


@pytest.mark.asyncio
async def test_analysis_worker_general_exception_handling(mock_redis_client, mock_analyzer):
    """Test AnalysisQueueWorker handles general exceptions (lines 449-452)."""
    call_count = 0

    async def mock_get_from_queue(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        if call_count == 1:
            return {"batch_id": "batch_123", "camera_id": "cam1"}
        return None

    mock_redis_client.get_from_queue = mock_get_from_queue
    mock_analyzer.analyze_batch = AsyncMock(side_effect=RuntimeError("Database error"))

    worker = AnalysisQueueWorker(
        redis_client=mock_redis_client,
        analyzer=mock_analyzer,
        poll_timeout=1,
    )

    with patch("backend.services.pipeline_workers.record_pipeline_error") as mock_record:
        await worker.start()
        await asyncio.sleep(0.2)
        await worker.stop()

        mock_record.assert_called_with("analysis_batch_error")

    assert worker.stats.errors == 1
    assert worker.stats.items_processed == 0


@pytest.mark.asyncio
async def test_analysis_worker_stop_timeout_forces_cancel(mock_redis_client, mock_analyzer):
    """Test AnalysisQueueWorker cancels task when stop times out (lines 356-362)."""
    worker = AnalysisQueueWorker(
        redis_client=mock_redis_client,
        analyzer=mock_analyzer,
        poll_timeout=TEST_POLL_TIMEOUT,
        stop_timeout=0.01,  # Very short timeout
    )

    async def long_running_loop():
        while True:
            await asyncio.sleep(1.0)  # cancelled - task is cancelled in test

    await worker.start()
    original_task = worker._task
    worker._task = asyncio.create_task(long_running_loop())
    if original_task:
        original_task.cancel()
        try:
            await original_task
        except asyncio.CancelledError:
            pass

    await worker.stop()

    assert worker.running is False
    assert worker.stats.state == WorkerState.STOPPED
    assert worker._task is None


@pytest.mark.asyncio
async def test_analysis_worker_loop_cancelled_error(mock_redis_client, mock_analyzer):
    """Test AnalysisQueueWorker handles CancelledError in loop (lines 385-387)."""
    call_count = 0

    async def mock_get_from_queue_that_raises(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            await asyncio.sleep(0.01)
            return None
        raise asyncio.CancelledError()

    mock_redis_client.get_from_queue = mock_get_from_queue_that_raises

    worker = AnalysisQueueWorker(
        redis_client=mock_redis_client,
        analyzer=mock_analyzer,
        poll_timeout=TEST_POLL_TIMEOUT,
        stop_timeout=TEST_STOP_TIMEOUT,
    )

    await worker.start()
    await asyncio.sleep(0.1)
    worker._running = False
    if worker._task and not worker._task.done():
        worker._task.cancel()
        try:
            await worker._task
        except asyncio.CancelledError:
            pass
    worker._task = None
    worker._stats.state = WorkerState.STOPPED


@pytest.mark.asyncio
async def test_analysis_worker_loop_general_exception_recovery(mock_redis_client, mock_analyzer):
    """Test AnalysisQueueWorker recovers from general exceptions (lines 388-398)."""
    call_count = 0

    async def mock_get_from_queue_that_raises(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Simulated Redis connection error")
        await asyncio.sleep(0.01)

    mock_redis_client.get_from_queue = mock_get_from_queue_that_raises

    worker = AnalysisQueueWorker(
        redis_client=mock_redis_client,
        analyzer=mock_analyzer,
        poll_timeout=TEST_POLL_TIMEOUT,
        stop_timeout=TEST_STOP_TIMEOUT,
    )

    with patch("backend.services.pipeline_workers.record_pipeline_error") as mock_record:
        await worker.start()
        await asyncio.sleep(0.2)
        await worker.stop()

        mock_record.assert_called_with("analysis_worker_error")

    assert worker.stats.errors >= 1
    assert worker.stats.state == WorkerState.STOPPED


# BatchTimeoutWorker tests


@pytest.mark.asyncio
async def test_timeout_worker_initialization(mock_redis_client, mock_batch_aggregator):
    """Test BatchTimeoutWorker initializes correctly."""
    worker = BatchTimeoutWorker(
        redis_client=mock_redis_client,
        batch_aggregator=mock_batch_aggregator,
        check_interval=5.0,
    )

    assert worker.running is False
    assert worker.stats.state == WorkerState.STOPPED
    assert worker._check_interval == 5.0


@pytest.mark.asyncio
async def test_timeout_worker_start_stop(mock_redis_client, mock_batch_aggregator):
    """Test BatchTimeoutWorker start and stop lifecycle."""
    worker = BatchTimeoutWorker(
        redis_client=mock_redis_client,
        batch_aggregator=mock_batch_aggregator,
        check_interval=0.1,
    )

    await worker.start()
    assert worker.running is True
    assert worker.stats.state == WorkerState.RUNNING

    await asyncio.sleep(0.15)

    await worker.stop()
    assert worker.running is False
    assert worker.stats.state == WorkerState.STOPPED


@pytest.mark.asyncio
async def test_timeout_worker_idempotent_start(mock_redis_client, mock_batch_aggregator):
    """Test starting BatchTimeoutWorker multiple times is idempotent (lines 507-508)."""
    worker = BatchTimeoutWorker(
        redis_client=mock_redis_client,
        batch_aggregator=mock_batch_aggregator,
        check_interval=0.1,
        stop_timeout=TEST_STOP_TIMEOUT,
    )

    await worker.start()
    first_task = worker._task

    # Start again - should not create new task
    await worker.start()
    assert worker._task is first_task

    await worker.stop()


@pytest.mark.asyncio
async def test_timeout_worker_idempotent_stop(mock_redis_client, mock_batch_aggregator):
    """Test stopping BatchTimeoutWorker multiple times is safe (lines 522-523)."""
    worker = BatchTimeoutWorker(
        redis_client=mock_redis_client,
        batch_aggregator=mock_batch_aggregator,
        check_interval=0.1,
    )

    # Stop without starting - should not raise
    await worker.stop()
    assert worker.running is False

    # Start then stop twice
    await worker.start()
    await worker.stop()
    await worker.stop()
    assert worker.running is False


@pytest.mark.asyncio
async def test_timeout_worker_checks_timeouts(mock_redis_client, mock_batch_aggregator):
    """Test BatchTimeoutWorker checks batch timeouts periodically."""
    # Return closed batches on first call
    call_count = 0

    async def mock_check_timeouts():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return ["batch_1", "batch_2"]
        return []

    mock_batch_aggregator.check_batch_timeouts = mock_check_timeouts

    worker = BatchTimeoutWorker(
        redis_client=mock_redis_client,
        batch_aggregator=mock_batch_aggregator,
        check_interval=0.05,
    )

    await worker.start()
    await asyncio.sleep(0.15)
    await worker.stop()

    # Should have processed 2 batches
    assert worker.stats.items_processed == 2
    assert worker.stats.last_processed_at is not None


@pytest.mark.asyncio
async def test_timeout_worker_error_recovery(mock_redis_client, mock_batch_aggregator):
    """Test BatchTimeoutWorker recovers from errors."""
    call_count = 0

    async def mock_check_timeouts():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Redis error")
        return ["batch_1"]

    mock_batch_aggregator.check_batch_timeouts = mock_check_timeouts

    worker = BatchTimeoutWorker(
        redis_client=mock_redis_client,
        batch_aggregator=mock_batch_aggregator,
        check_interval=0.05,
    )

    await worker.start()
    await asyncio.sleep(0.2)
    await worker.stop()

    # Should have recovered from error
    assert worker.stats.errors >= 1
    assert worker.stats.items_processed >= 1


@pytest.mark.asyncio
async def test_timeout_worker_stop_timeout_forces_cancel(mock_redis_client, mock_batch_aggregator):
    """Test BatchTimeoutWorker cancels task when stop times out (lines 532-538)."""
    worker = BatchTimeoutWorker(
        redis_client=mock_redis_client,
        batch_aggregator=mock_batch_aggregator,
        check_interval=0.1,
        stop_timeout=0.01,  # Very short timeout
    )

    async def long_running_loop():
        while True:
            await asyncio.sleep(1.0)  # cancelled - task is cancelled in test

    await worker.start()
    original_task = worker._task
    worker._task = asyncio.create_task(long_running_loop())
    if original_task:
        original_task.cancel()
        try:
            await original_task
        except asyncio.CancelledError:
            pass

    await worker.stop()

    assert worker.running is False
    assert worker.stats.state == WorkerState.STOPPED
    assert worker._task is None


# QueueMetricsWorker tests


@pytest.mark.asyncio
async def test_queue_metrics_worker_initialization(mock_redis_client):
    """Test QueueMetricsWorker initializes correctly."""
    worker = QueueMetricsWorker(
        redis_client=mock_redis_client,
        update_interval=5.0,
    )

    assert worker.running is False
    assert worker._update_interval == 5.0


@pytest.mark.asyncio
async def test_queue_metrics_worker_start_stop(mock_redis_client):
    """Test QueueMetricsWorker start and stop lifecycle."""
    worker = QueueMetricsWorker(
        redis_client=mock_redis_client,
        update_interval=0.1,
    )

    await worker.start()
    assert worker.running is True

    await asyncio.sleep(0.15)

    await worker.stop()
    assert worker.running is False


@pytest.mark.asyncio
async def test_queue_metrics_worker_idempotent_start(mock_redis_client):
    """Test starting QueueMetricsWorker multiple times is idempotent (lines 632-633)."""
    worker = QueueMetricsWorker(
        redis_client=mock_redis_client,
        update_interval=0.1,
    )

    await worker.start()
    first_task = worker._task

    # Start again - should not create new task
    await worker.start()
    assert worker._task is first_task

    await worker.stop()


@pytest.mark.asyncio
async def test_queue_metrics_worker_idempotent_stop(mock_redis_client):
    """Test stopping QueueMetricsWorker multiple times is safe (line 645)."""
    worker = QueueMetricsWorker(
        redis_client=mock_redis_client,
        update_interval=0.1,
    )

    # Stop without starting - should not raise
    await worker.stop()
    assert worker.running is False

    # Start then stop twice
    await worker.start()
    await worker.stop()
    await worker.stop()
    assert worker.running is False


@pytest.mark.asyncio
async def test_queue_metrics_worker_updates_metrics(mock_redis_client):
    """Test QueueMetricsWorker updates queue depth metrics (lines 671-677)."""
    mock_redis_client.get_queue_length = AsyncMock(side_effect=[10, 5])

    worker = QueueMetricsWorker(
        redis_client=mock_redis_client,
        update_interval=0.05,
    )

    with patch("backend.services.pipeline_workers.set_queue_depth") as mock_set_depth:
        await worker.start()
        await asyncio.sleep(0.1)
        await worker.stop()

        # Should have called set_queue_depth for detection and analysis queues
        assert mock_set_depth.call_count >= 2
        # Check that set_queue_depth was called with queue names
        call_args_list = mock_set_depth.call_args_list
        queue_names = [call[0][0] for call in call_args_list]
        assert "detection" in queue_names
        assert "analysis" in queue_names


@pytest.mark.asyncio
async def test_queue_metrics_worker_loop_cancelled_error(mock_redis_client):
    """Test QueueMetricsWorker handles CancelledError in loop (lines 682-683)."""

    async def mock_get_queue_length_that_raises(*args, **kwargs):
        raise asyncio.CancelledError()

    mock_redis_client.get_queue_length = mock_get_queue_length_that_raises

    worker = QueueMetricsWorker(
        redis_client=mock_redis_client,
        update_interval=0.05,
    )

    await worker.start()
    await asyncio.sleep(0.1)
    # Worker should have exited due to CancelledError
    worker._running = False
    if worker._task and not worker._task.done():
        worker._task.cancel()
        try:
            await worker._task
        except asyncio.CancelledError:
            pass
    worker._task = None


@pytest.mark.asyncio
async def test_queue_metrics_worker_handles_redis_error(mock_redis_client):
    """Test QueueMetricsWorker handles Redis errors gracefully."""
    call_count = 0

    async def mock_get_queue_length(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise RuntimeError("Redis connection error")
        return 0

    mock_redis_client.get_queue_length = mock_get_queue_length

    worker = QueueMetricsWorker(
        redis_client=mock_redis_client,
        update_interval=0.05,
    )

    # Should not raise exception
    await worker.start()
    await asyncio.sleep(0.2)
    await worker.stop()

    assert worker.running is False


# PipelineWorkerManager tests


@pytest.mark.asyncio
async def test_manager_initialization(mock_redis_client):
    """Test PipelineWorkerManager initializes correctly."""
    manager = PipelineWorkerManager(
        redis_client=mock_redis_client,
        enable_detection_worker=True,
        enable_analysis_worker=True,
        enable_timeout_worker=True,
    )

    assert manager.running is False
    assert manager._detection_worker is not None
    assert manager._analysis_worker is not None
    assert manager._timeout_worker is not None


@pytest.mark.asyncio
async def test_manager_selective_workers(mock_redis_client):
    """Test PipelineWorkerManager can enable/disable specific workers."""
    manager = PipelineWorkerManager(
        redis_client=mock_redis_client,
        enable_detection_worker=True,
        enable_analysis_worker=False,
        enable_timeout_worker=False,
    )

    assert manager._detection_worker is not None
    assert manager._analysis_worker is None
    assert manager._timeout_worker is None


@pytest.mark.asyncio
async def test_manager_start_stop(mock_redis_client):
    """Test PipelineWorkerManager start and stop."""
    manager = PipelineWorkerManager(redis_client=mock_redis_client)

    await manager.start()
    assert manager.running is True

    await asyncio.sleep(0.1)

    await manager.stop()
    assert manager.running is False


@pytest.mark.asyncio
async def test_manager_get_status(mock_redis_client):
    """Test PipelineWorkerManager status reporting."""
    manager = PipelineWorkerManager(redis_client=mock_redis_client)

    status = manager.get_status()

    assert "running" in status
    assert "workers" in status
    assert "detection" in status["workers"]
    assert "analysis" in status["workers"]
    assert "timeout" in status["workers"]


@pytest.mark.asyncio
async def test_manager_get_status_with_metrics_worker(mock_redis_client):
    """Test PipelineWorkerManager status includes metrics worker."""
    manager = PipelineWorkerManager(
        redis_client=mock_redis_client,
        enable_metrics_worker=True,
    )

    status = manager.get_status()

    assert "metrics" in status["workers"]
    assert "running" in status["workers"]["metrics"]


@pytest.mark.asyncio
async def test_manager_idempotent_start(mock_redis_client):
    """Test PipelineWorkerManager start is idempotent."""
    manager = PipelineWorkerManager(redis_client=mock_redis_client)

    await manager.start()
    await manager.start()  # Should not raise

    assert manager.running is True

    await manager.stop()


@pytest.mark.asyncio
async def test_manager_idempotent_stop(mock_redis_client):
    """Test PipelineWorkerManager stop is idempotent."""
    manager = PipelineWorkerManager(redis_client=mock_redis_client)

    await manager.stop()  # Stop without starting
    assert manager.running is False

    await manager.start()
    await manager.stop()
    await manager.stop()  # Double stop
    assert manager.running is False


@pytest.mark.asyncio
async def test_manager_signal_handler_installation(mock_redis_client):
    """Test PipelineWorkerManager installs signal handlers (lines 870-871)."""
    manager = PipelineWorkerManager(redis_client=mock_redis_client)

    # Mock the signal handler installation
    with patch.object(asyncio, "get_running_loop") as mock_get_loop:
        mock_loop = MagicMock()
        mock_get_loop.return_value = mock_loop

        await manager.start()

        # Verify add_signal_handler was called for SIGTERM and SIGINT
        assert mock_loop.add_signal_handler.call_count == 2
        signal_calls = mock_loop.add_signal_handler.call_args_list
        signals_registered = [call[0][0] for call in signal_calls]
        assert signal.SIGTERM in signals_registered
        assert signal.SIGINT in signals_registered

    await manager.stop()


@pytest.mark.asyncio
async def test_manager_signal_handler_not_implemented(mock_redis_client):
    """Test PipelineWorkerManager handles NotImplementedError for signals (lines 879-881)."""
    manager = PipelineWorkerManager(redis_client=mock_redis_client)

    # Mock the signal handler to raise NotImplementedError (like on Windows)
    with patch.object(asyncio, "get_running_loop") as mock_get_loop:
        mock_loop = MagicMock()
        mock_loop.add_signal_handler.side_effect = NotImplementedError("Signals not supported")
        mock_get_loop.return_value = mock_loop

        # Should not raise, just log debug message
        await manager.start()
        assert manager._signal_handlers_installed is False

    await manager.stop()


@pytest.mark.asyncio
async def test_manager_signal_handler_runtime_error(mock_redis_client):
    """Test PipelineWorkerManager handles RuntimeError for signals (lines 879-881)."""
    manager = PipelineWorkerManager(redis_client=mock_redis_client)

    # Mock the signal handler to raise RuntimeError (e.g., not in main thread)
    with patch.object(asyncio, "get_running_loop") as mock_get_loop:
        mock_loop = MagicMock()
        mock_loop.add_signal_handler.side_effect = RuntimeError("Not in main thread")
        mock_get_loop.return_value = mock_loop

        # Should not raise, just log debug message
        await manager.start()
        assert manager._signal_handlers_installed is False

    await manager.stop()


@pytest.mark.asyncio
async def test_manager_signal_handler_triggers_stop(mock_redis_client):
    """Test that signal handler actually triggers stop when invoked."""
    manager = PipelineWorkerManager(redis_client=mock_redis_client)

    captured_handlers = {}

    def capture_add_signal_handler(sig, handler):
        captured_handlers[sig] = handler

    with patch.object(asyncio, "get_running_loop") as mock_get_loop:
        mock_loop = MagicMock()
        mock_loop.add_signal_handler.side_effect = capture_add_signal_handler
        mock_get_loop.return_value = mock_loop

        await manager.start()

        # Verify handlers were captured
        assert signal.SIGTERM in captured_handlers
        assert signal.SIGINT in captured_handlers

        # Verify the handler creates a stop task when called
        with (
            patch.object(manager, "stop", new_callable=AsyncMock),
            patch("asyncio.create_task") as mock_create_task,
        ):
            # Call the SIGTERM handler
            captured_handlers[signal.SIGTERM]()
            mock_create_task.assert_called_once()

    # Clean up
    manager._running = False
    await manager.stop()


# Global singleton tests


@pytest.mark.asyncio
async def test_get_pipeline_manager_singleton(mock_redis_client):
    """Test get_pipeline_manager returns singleton."""
    # Clear any existing singleton
    import backend.services.pipeline_workers as module

    module._pipeline_manager = None

    manager1 = await get_pipeline_manager(mock_redis_client)
    manager2 = await get_pipeline_manager(mock_redis_client)

    assert manager1 is manager2

    # Cleanup
    await stop_pipeline_manager()


@pytest.mark.asyncio
async def test_stop_pipeline_manager_clears_singleton(mock_redis_client):
    """Test stop_pipeline_manager clears the singleton."""
    import backend.services.pipeline_workers as module

    module._pipeline_manager = None

    manager = await get_pipeline_manager(mock_redis_client)
    await manager.start()

    await stop_pipeline_manager()

    assert module._pipeline_manager is None


@pytest.mark.asyncio
async def test_stop_pipeline_manager_when_none():
    """Test stop_pipeline_manager when no manager exists."""
    import backend.services.pipeline_workers as module

    module._pipeline_manager = None

    # Should not raise
    await stop_pipeline_manager()


# Graceful shutdown tests


@pytest.mark.asyncio
async def test_worker_cancellation_during_processing(
    mock_redis_client, mock_detector_client, mock_batch_aggregator
):
    """Test workers handle cancellation during processing."""

    # Slow processing to test cancellation (uses short sleep, stop timeout is mocked)
    async def slow_detect(*args, **kwargs):
        await asyncio.sleep(0.5)  # Long enough to be in-progress when stop is called
        return []

    mock_detector_client.detect_objects = slow_detect

    call_count = 0

    async def mock_get_from_queue(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)  # Yield control to event loop
        if call_count == 1:
            return {
                "camera_id": "cam1",
                "file_path": "/path/to/image.jpg",
                "timestamp": datetime.now().isoformat(),
            }
        return None

    mock_redis_client.get_from_queue = mock_get_from_queue

    worker = DetectionQueueWorker(
        redis_client=mock_redis_client,
        detector_client=mock_detector_client,
        batch_aggregator=mock_batch_aggregator,
        poll_timeout=TEST_POLL_TIMEOUT,
        stop_timeout=TEST_STOP_TIMEOUT,
    )

    with patch("backend.services.pipeline_workers.get_session") as mock_get_session:
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        await worker.start()
        await asyncio.sleep(0.1)  # Start processing

        await worker.stop()

    assert worker.running is False
    assert worker.stats.state == WorkerState.STOPPED


@pytest.mark.asyncio
async def test_manager_stops_all_workers_on_shutdown(mock_redis_client):
    """Test manager stops all workers during shutdown."""
    manager = PipelineWorkerManager(redis_client=mock_redis_client)

    await manager.start()
    assert manager._detection_worker.running is True
    assert manager._analysis_worker.running is True
    assert manager._timeout_worker.running is True

    await manager.stop()
    assert manager._detection_worker.running is False
    assert manager._analysis_worker.running is False
    assert manager._timeout_worker.running is False


@pytest.mark.asyncio
async def test_manager_with_all_workers_disabled(mock_redis_client):
    """Test PipelineWorkerManager with all workers disabled."""
    manager = PipelineWorkerManager(
        redis_client=mock_redis_client,
        enable_detection_worker=False,
        enable_analysis_worker=False,
        enable_timeout_worker=False,
        enable_metrics_worker=False,
    )

    assert manager._detection_worker is None
    assert manager._analysis_worker is None
    assert manager._timeout_worker is None
    assert manager._metrics_worker is None

    # Should still be able to start/stop without error
    await manager.start()
    assert manager.running is True

    await manager.stop()
    assert manager.running is False


@pytest.mark.asyncio
async def test_manager_get_status_with_no_workers(mock_redis_client):
    """Test PipelineWorkerManager status with no workers enabled."""
    manager = PipelineWorkerManager(
        redis_client=mock_redis_client,
        enable_detection_worker=False,
        enable_analysis_worker=False,
        enable_timeout_worker=False,
        enable_metrics_worker=False,
    )

    status = manager.get_status()

    assert status["running"] is False
    assert status["workers"] == {}


# =============================================================================
# Video Processing Tests
# =============================================================================


@pytest.fixture
def mock_video_processor():
    """Create a mock video processor."""
    processor = MagicMock()
    processor.extract_frames_for_detection = AsyncMock(return_value=[])
    processor.cleanup_extracted_frames = MagicMock(return_value=True)
    processor.get_video_metadata = AsyncMock(
        return_value={
            "duration": 10.0,
            "video_codec": "h264",
            "video_width": 1920,
            "video_height": 1080,
            "file_type": "video/mp4",
        }
    )
    return processor


@pytest.mark.asyncio
async def test_detection_worker_processes_video_item(
    mock_redis_client, mock_detector_client, mock_batch_aggregator, mock_video_processor
):
    """Test DetectionQueueWorker processes video queue items correctly."""
    call_count = 0

    async def mock_get_from_queue(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        if call_count == 1:
            return {
                "camera_id": "front_door",
                "file_path": "/path/to/video.mp4",
                "timestamp": datetime.now().isoformat(),
                "media_type": "video",
            }
        return None

    mock_redis_client.get_from_queue = mock_get_from_queue

    # Setup video processor to return frames
    mock_video_processor.extract_frames_for_detection = AsyncMock(
        return_value=["/data/thumbnails/frame_0.jpg", "/data/thumbnails/frame_1.jpg"]
    )

    # Setup detector to return detections for each frame
    detection = MagicMock()
    detection.id = 1
    detection.confidence = 0.95
    detection.object_type = "person"
    mock_detector_client.detect_objects = AsyncMock(return_value=[detection])

    worker = DetectionQueueWorker(
        redis_client=mock_redis_client,
        detector_client=mock_detector_client,
        batch_aggregator=mock_batch_aggregator,
        video_processor=mock_video_processor,
        poll_timeout=1,
    )

    with patch("backend.services.pipeline_workers.get_session") as mock_get_session:
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        await worker.start()
        await asyncio.sleep(0.2)
        await worker.stop()

    # Verify video was processed
    assert worker.stats.items_processed == 1
    mock_video_processor.extract_frames_for_detection.assert_called_once()
    # Should have called detect_objects for each frame
    assert mock_detector_client.detect_objects.call_count == 2
    # Cleanup should have been called
    mock_video_processor.cleanup_extracted_frames.assert_called_once()


@pytest.mark.asyncio
async def test_detection_worker_handles_video_with_no_frames(
    mock_redis_client, mock_detector_client, mock_batch_aggregator, mock_video_processor
):
    """Test DetectionQueueWorker handles videos that fail frame extraction."""
    call_count = 0

    async def mock_get_from_queue(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        if call_count == 1:
            return {
                "camera_id": "front_door",
                "file_path": "/path/to/corrupted_video.mp4",
                "timestamp": datetime.now().isoformat(),
                "media_type": "video",
            }
        return None

    mock_redis_client.get_from_queue = mock_get_from_queue

    # Setup video processor to return empty frames (extraction failed)
    mock_video_processor.extract_frames_for_detection = AsyncMock(return_value=[])

    worker = DetectionQueueWorker(
        redis_client=mock_redis_client,
        detector_client=mock_detector_client,
        batch_aggregator=mock_batch_aggregator,
        video_processor=mock_video_processor,
        poll_timeout=1,
    )

    await worker.start()
    await asyncio.sleep(0.2)
    await worker.stop()

    # Item should still be marked as processed (even though no frames)
    assert worker.stats.items_processed == 1
    # Detector should not have been called (no frames)
    mock_detector_client.detect_objects.assert_not_called()


@pytest.mark.asyncio
async def test_detection_worker_processes_image_item(
    mock_redis_client, mock_detector_client, mock_batch_aggregator, mock_video_processor
):
    """Test DetectionQueueWorker processes image items without video processing."""
    call_count = 0

    async def mock_get_from_queue(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        if call_count == 1:
            return {
                "camera_id": "front_door",
                "file_path": "/path/to/image.jpg",
                "timestamp": datetime.now().isoformat(),
                "media_type": "image",
            }
        return None

    mock_redis_client.get_from_queue = mock_get_from_queue

    detection = MagicMock()
    detection.id = 1
    detection.confidence = 0.95
    detection.object_type = "person"
    mock_detector_client.detect_objects = AsyncMock(return_value=[detection])

    worker = DetectionQueueWorker(
        redis_client=mock_redis_client,
        detector_client=mock_detector_client,
        batch_aggregator=mock_batch_aggregator,
        video_processor=mock_video_processor,
        poll_timeout=1,
    )

    with patch("backend.services.pipeline_workers.get_session") as mock_get_session:
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        await worker.start()
        await asyncio.sleep(0.2)
        await worker.stop()

    # Verify image was processed
    assert worker.stats.items_processed == 1
    # Video processor should NOT have been called for image
    mock_video_processor.extract_frames_for_detection.assert_not_called()
    mock_video_processor.cleanup_extracted_frames.assert_not_called()
    # Detector should have been called once for the image
    mock_detector_client.detect_objects.assert_called_once()


@pytest.mark.asyncio
async def test_detection_worker_defaults_to_image_media_type(
    mock_redis_client, mock_detector_client, mock_batch_aggregator, mock_video_processor
):
    """Test DetectionQueueWorker defaults to image when media_type is missing."""
    call_count = 0

    async def mock_get_from_queue(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        if call_count == 1:
            return {
                "camera_id": "front_door",
                "file_path": "/path/to/image.jpg",
                "timestamp": datetime.now().isoformat(),
                # media_type is intentionally missing
            }
        return None

    mock_redis_client.get_from_queue = mock_get_from_queue

    mock_detector_client.detect_objects = AsyncMock(return_value=[])

    worker = DetectionQueueWorker(
        redis_client=mock_redis_client,
        detector_client=mock_detector_client,
        batch_aggregator=mock_batch_aggregator,
        video_processor=mock_video_processor,
        poll_timeout=1,
    )

    with patch("backend.services.pipeline_workers.get_session") as mock_get_session:
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        await worker.start()
        await asyncio.sleep(0.2)
        await worker.stop()

    # Should process as image (default)
    assert worker.stats.items_processed == 1
    mock_video_processor.extract_frames_for_detection.assert_not_called()
