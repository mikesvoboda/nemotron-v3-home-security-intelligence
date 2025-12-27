"""Unit tests for pipeline workers.

Tests cover:
- Worker lifecycle (start/stop/idempotency)
- Queue consumer loops
- Graceful shutdown handling
- Error recovery
- Statistics tracking
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.pipeline_workers import (
    AnalysisQueueWorker,
    BatchTimeoutWorker,
    DetectionQueueWorker,
    PipelineWorkerManager,
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
        return None

    client.get_from_queue = mock_get_from_queue
    client.add_to_queue = AsyncMock(return_value=1)
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
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
    mock_analyzer.analyze_batch.assert_called_once_with("batch_123")


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
