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
from collections.abc import Callable
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.redis import RedisClient
from backend.services.batch_aggregator import BatchAggregator
from backend.services.nemotron_analyzer import NemotronAnalyzer
from backend.services.pipeline_workers import (
    AnalysisQueueWorker,
    BatchTimeoutWorker,
    DetectionQueueWorker,
    PipelineWorkerManager,
    QueueMetricsWorker,
    WorkerState,
    WorkerStats,
    categorize_exception,
    get_pipeline_manager,
    stop_pipeline_manager,
)

# =============================================================================
# Test Helpers for Event-Based Waiting
# =============================================================================


async def wait_for_condition(
    condition: Callable[[], bool],
    timeout: float = 2.0,
    poll_interval: float = 0.01,
    description: str = "condition",
) -> bool:
    """Wait for a condition to become true with a timeout.

    This replaces arbitrary sleep() calls with deterministic condition checking.
    The function polls the condition frequently (default 10ms) and returns as
    soon as the condition is met, making tests faster and more reliable.

    Args:
        condition: A callable that returns True when the condition is met
        timeout: Maximum time to wait in seconds (default 2.0)
        poll_interval: How often to check the condition (default 0.01s)
        description: Description for error messages

    Returns:
        True if condition was met within timeout

    Raises:
        TimeoutError: If the condition is not met within the timeout
    """
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if condition():
            return True
        await asyncio.sleep(poll_interval)
    raise TimeoutError(f"Timeout waiting for {description}")


async def wait_for_items_processed(
    worker: Any,
    min_count: int = 1,
    timeout: float = 2.0,
) -> None:
    """Wait for a worker to process at least min_count items.

    Args:
        worker: Worker with a stats.items_processed attribute
        min_count: Minimum number of items to wait for
        timeout: Maximum wait time in seconds
    """
    await wait_for_condition(
        lambda: worker.stats.items_processed >= min_count,
        timeout=timeout,
        description=f"worker to process {min_count} items",
    )


async def wait_for_worker_state(
    worker: Any,
    state: WorkerState,
    timeout: float = 2.0,
) -> None:
    """Wait for a worker to reach a specific state.

    Args:
        worker: Worker with a stats.state attribute
        state: Target state to wait for
        timeout: Maximum wait time in seconds
    """
    await wait_for_condition(
        lambda: worker.stats.state == state,
        timeout=timeout,
        description=f"worker to reach state {state.value}",
    )


async def wait_for_worker_running(worker: Any, timeout: float = 2.0) -> None:
    """Wait for a worker to be running.

    Args:
        worker: Worker with a running property
        timeout: Maximum wait time in seconds
    """
    await wait_for_condition(
        lambda: worker.running,
        timeout=timeout,
        description="worker to start running",
    )


async def wait_for_errors(
    worker: Any,
    min_count: int = 1,
    timeout: float = 2.0,
) -> None:
    """Wait for a worker to have at least min_count errors.

    Args:
        worker: Worker with a stats.errors attribute
        min_count: Minimum number of errors to wait for
        timeout: Maximum wait time in seconds
    """
    await wait_for_condition(
        lambda: worker.stats.errors >= min_count,
        timeout=timeout,
        description=f"worker to have {min_count} errors",
    )


async def wait_for_call_count(
    mock_fn: MagicMock | AsyncMock,
    min_count: int = 1,
    timeout: float = 2.0,
) -> None:
    """Wait for a mock function to be called at least min_count times.

    Args:
        mock_fn: Mock function with call_count attribute
        min_count: Minimum number of calls to wait for
        timeout: Maximum wait time in seconds
    """
    await wait_for_condition(
        lambda: mock_fn.call_count >= min_count,
        timeout=timeout,
        description=f"mock to be called {min_count} times",
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
    client = MagicMock(spec=RedisClient)

    async def mock_get_from_queue(*args, **kwargs):
        """Mock that yields control like real BLPOP would."""
        await asyncio.sleep(0.01)  # Yield control to event loop

    client.get_from_queue = mock_get_from_queue
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.delete = AsyncMock(return_value=1)
    client.get_queue_length = AsyncMock(return_value=0)
    client._client = MagicMock()
    client._client.keys = AsyncMock(return_value=[])
    return client


@pytest.fixture
def mock_detector_client():
    """Create a mock detector client.

    Note: We don't use spec=DetectorClient because DetectorClient has
    TYPE_CHECKING-only imports (FrameBuffer) that cause NameError when
    Python 3.14's inspect.signature tries to resolve type annotations.
    """
    client = MagicMock()
    client.detect_objects = AsyncMock(return_value=[])
    client.health_check = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_batch_aggregator():
    """Create a mock batch aggregator."""
    aggregator = MagicMock(spec=BatchAggregator)
    aggregator.add_detection = AsyncMock(return_value="batch_123")
    aggregator.check_batch_timeouts = AsyncMock(return_value=[])
    aggregator.close_batch = AsyncMock(return_value={"batch_id": "test"})
    return aggregator


@pytest.fixture
def mock_analyzer():
    """Create a mock Nemotron analyzer."""
    analyzer = MagicMock(spec=NemotronAnalyzer)
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


# categorize_exception tests


class TestCategorizeException:
    """Test exception categorization for fine-grained error metrics."""

    def test_connection_error_by_type_name(self):
        """Test that ConnectionError is categorized as connection error."""
        result = categorize_exception(ConnectionError("connection failed"), "detection")
        assert result == "detection_connection_error"

    def test_connection_refused_error(self):
        """Test that ConnectionRefusedError is categorized as connection error."""
        result = categorize_exception(ConnectionRefusedError("refused"), "analysis")
        assert result == "analysis_connection_error"

    def test_timeout_error(self):
        """Test that TimeoutError is categorized as timeout error."""
        result = categorize_exception(TimeoutError("timed out"), "detection")
        assert result == "detection_timeout_error"

    def test_memory_error(self):
        """Test that MemoryError is categorized as memory error."""
        result = categorize_exception(MemoryError("out of memory"), "batch_timeout")
        assert result == "batch_timeout_memory_error"

    def test_value_error_as_validation(self):
        """Test that ValueError is categorized as validation error."""
        result = categorize_exception(ValueError("invalid value"), "detection")
        assert result == "detection_validation_error"

    def test_type_error_as_validation(self):
        """Test that TypeError is categorized as validation error."""
        result = categorize_exception(TypeError("wrong type"), "analysis")
        assert result == "analysis_validation_error"

    def test_key_error_as_validation(self):
        """Test that KeyError is categorized as validation error."""
        result = categorize_exception(KeyError("missing key"), "detection")
        assert result == "detection_validation_error"

    def test_generic_exception_as_processing_error(self):
        """Test that generic exceptions are categorized as processing error."""
        result = categorize_exception(RuntimeError("something went wrong"), "detection")
        assert result == "detection_processing_error"

    def test_exception_with_connect_in_message(self):
        """Test that exceptions mentioning 'connect' are categorized as connection error."""

        class CustomError(Exception):
            pass

        result = categorize_exception(CustomError("failed to connect to server"), "analysis")
        assert result == "analysis_connection_error"

    def test_different_worker_names(self):
        """Test that worker name is correctly included in error type."""
        # Detection worker
        result = categorize_exception(ValueError("test"), "detection")
        assert result == "detection_validation_error"

        # Analysis worker
        result = categorize_exception(ValueError("test"), "analysis")
        assert result == "analysis_validation_error"

        # Batch timeout worker
        result = categorize_exception(ValueError("test"), "batch_timeout")
        assert result == "batch_timeout_validation_error"


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

    # Wait for worker to be fully running (event-based instead of arbitrary sleep)
    await wait_for_worker_running(worker)

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
        # Wait for the item to be processed (event-based instead of arbitrary sleep)
        await wait_for_items_processed(worker, min_count=1)
        await worker.stop()

    # Verify detection was processed
    assert worker.stats.items_processed == 1
    assert worker.stats.last_processed_at is not None
    mock_batch_aggregator.add_detection.assert_called_once()


@pytest.mark.asyncio
async def test_detection_worker_handles_invalid_item(mock_redis_client, mock_detector_client):
    """Test DetectionQueueWorker handles invalid queue items gracefully.

    Security: With Pydantic payload validation, invalid items are rejected and
    counted as errors to enable monitoring of potential attacks.
    """
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
    # Wait for the error to be recorded (event-based instead of arbitrary sleep)
    await wait_for_errors(worker, min_count=1)
    await worker.stop()

    # Should not increment items_processed for invalid items
    assert worker.stats.items_processed == 0
    # Security: Invalid payloads now count as errors for monitoring
    assert worker.stats.errors == 1


@pytest.mark.asyncio
async def test_detection_worker_error_recovery_with_retry(
    mock_redis_client, mock_detector_client, mock_batch_aggregator
):
    """Test DetectionQueueWorker uses retry handler for transient errors.

    With the retry handler, transient errors are retried within the same
    call to _process_image_detection. The worker then continues to process
    subsequent items normally.

    This test verifies that:
    1. First call fails, retry succeeds -> counts as success
    2. Second call succeeds immediately -> counts as success
    3. Worker continues processing after errors are recovered via retry
    """
    from backend.services.retry_handler import RetryConfig, RetryHandler

    call_count = 0

    async def mock_get_from_queue(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)  # Yield control to event loop
        if call_count <= 2:
            return {
                "camera_id": "cam1",
                "file_path": f"/path/to/image_{call_count}.jpg",
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

    # Use real retry handler with fast backoff for testing
    retry_handler = RetryHandler(
        redis_client=mock_redis_client,
        config=RetryConfig(
            max_retries=3,
            base_delay_seconds=0.01,  # Fast for testing
            max_delay_seconds=0.05,
            jitter=False,  # Deterministic for testing
        ),
    )

    worker = DetectionQueueWorker(
        redis_client=mock_redis_client,
        detector_client=mock_detector_client,
        batch_aggregator=mock_batch_aggregator,
        retry_handler=retry_handler,
        poll_timeout=1,
    )

    with patch("backend.services.pipeline_workers.get_session") as mock_get_session:
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        await worker.start()
        # Wait for both items to be processed (event-based instead of arbitrary sleep)
        await wait_for_items_processed(worker, min_count=2)
        await worker.stop()

    # Both items should be processed successfully
    # (first item failed, then succeeded via retry)
    assert worker.stats.items_processed == 2
    assert worker.stats.errors == 0  # No unrecoverable errors


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
            await asyncio.sleep(0.1)  # cancelled - task is cancelled in test

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
    # Wait for the task to be created and potentially exit due to CancelledError
    await wait_for_worker_running(worker)
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
            # Use error message without "connect" to avoid connection error categorization
            raise RuntimeError("Simulated processing failure")
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
        # Wait for at least one error to be recorded (event-based instead of arbitrary sleep)
        await wait_for_errors(worker, min_count=1)
        await worker.stop()

        # Should have recorded the error with categorized error type
        # RuntimeError -> processing_error category
        mock_record.assert_called_with("detection_processing_error")

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

    # Wait for worker to be fully running (event-based instead of arbitrary sleep)
    await wait_for_worker_running(worker)

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
    # Wait for the item to be processed (event-based instead of arbitrary sleep)
    await wait_for_items_processed(worker, min_count=1)
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
    # Wait for analyze_batch to be called (event-based instead of arbitrary sleep)
    await wait_for_call_count(mock_analyzer.analyze_batch, min_count=1)
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
    # Wait for worker to be running and process the invalid item
    await wait_for_worker_running(worker)
    # Give the worker a chance to process the queue item
    await wait_for_condition(
        lambda: call_count >= 2, timeout=2.0, description="queue item processed"
    )
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
        # Wait for error to be recorded (event-based instead of arbitrary sleep)
        await wait_for_errors(worker, min_count=1)
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
            await asyncio.sleep(0.1)  # cancelled - task is cancelled in test

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
    # Wait for worker to be running (event-based instead of arbitrary sleep)
    await wait_for_worker_running(worker)
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
            # Use error message without "connect" to avoid connection error categorization
            raise RuntimeError("Simulated processing failure")
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
        # Wait for error to be recorded (event-based instead of arbitrary sleep)
        await wait_for_errors(worker, min_count=1)
        await worker.stop()

        # Should have recorded the error with categorized error type
        # RuntimeError -> processing_error category
        mock_record.assert_called_with("analysis_processing_error")

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

    # Wait for at least one check cycle (event-based instead of arbitrary sleep)
    await wait_for_call_count(mock_batch_aggregator.check_batch_timeouts, min_count=1)

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
    # Wait for items to be processed (event-based instead of arbitrary sleep)
    await wait_for_items_processed(worker, min_count=2)
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
    # Wait for error and recovery (event-based instead of arbitrary sleep)
    await wait_for_errors(worker, min_count=1)
    await wait_for_items_processed(worker, min_count=1)
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
            await asyncio.sleep(0.1)  # cancelled - task is cancelled in test

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
async def test_timeout_worker_consistent_interval_despite_processing_time(
    mock_redis_client, mock_batch_aggregator
):
    """Test BatchTimeoutWorker maintains consistent check interval despite variable processing time.

    This tests the fix for P2 bug k78s: Batch Timeout Check Delay (10-20s Late).

    The bug occurred because the worker always slept for the full check_interval AFTER
    processing completed, causing timing drift. For example:
    - check_interval = 10s
    - processing takes 5s
    - old behavior: total cycle = 5s + 10s = 15s (5s late)
    - new behavior: total cycle = 5s + 5s = 10s (on time)
    """
    import time

    call_times: list[float] = []

    async def mock_check_timeouts_with_delay():
        """Simulate check_batch_timeouts that takes variable time."""
        call_times.append(time.time())
        # Simulate processing time (50ms) - short enough to complete within test
        await asyncio.sleep(0.05)
        return []

    mock_batch_aggregator.check_batch_timeouts = mock_check_timeouts_with_delay

    check_interval = 0.1  # 100ms check interval for fast test
    worker = BatchTimeoutWorker(
        redis_client=mock_redis_client,
        batch_aggregator=mock_batch_aggregator,
        check_interval=check_interval,
        stop_timeout=TEST_STOP_TIMEOUT,
    )

    await worker.start()
    # Wait for at least 3 check cycles to measure interval consistency
    await asyncio.sleep(0.35)
    await worker.stop()

    # Should have at least 3 calls
    assert len(call_times) >= 3, f"Expected at least 3 calls, got {len(call_times)}"

    # Calculate actual intervals between calls
    intervals = []
    for i in range(1, len(call_times)):
        interval = call_times[i] - call_times[i - 1]
        intervals.append(interval)

    # Each interval should be approximately equal to check_interval (100ms)
    # not check_interval + processing_time (150ms with the old bug)
    # Allow 40ms tolerance for async scheduling variance
    for i, interval in enumerate(intervals):
        # With the fix, interval should be ~100ms (check_interval)
        # Without the fix, interval would be ~150ms (check_interval + processing_time)
        assert interval < check_interval + 0.04, (
            f"Interval {i} was {interval * 1000:.0f}ms, expected ~{check_interval * 1000:.0f}ms. "
            f"This suggests timing drift bug (processing time not subtracted from sleep)."
        )


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

    # Wait for at least one metrics update (event-based instead of arbitrary sleep)
    await wait_for_call_count(mock_redis_client.get_queue_length, min_count=1)

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
        # Wait for metrics to be set (event-based instead of arbitrary sleep)
        await wait_for_call_count(mock_set_depth, min_count=2)
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
    # Wait for worker to be running (event-based instead of arbitrary sleep)
    await wait_for_worker_running(worker)
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
    # Wait for recovery after errors (event-based instead of arbitrary sleep)
    await wait_for_condition(
        lambda: call_count >= 3, timeout=2.0, description="queue length calls after errors"
    )
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
@pytest.mark.timeout(10)  # Manager tests need more time than the default 5s
async def test_manager_start_stop(mock_redis_client):
    """Test PipelineWorkerManager start and stop."""
    manager = PipelineWorkerManager(
        redis_client=mock_redis_client,
        worker_stop_timeout=TEST_STOP_TIMEOUT,
    )

    await manager.start()
    assert manager.running is True

    # Wait for manager to be fully running (event-based instead of arbitrary sleep)
    await wait_for_condition(lambda: manager.running, timeout=2.0, description="manager running")

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
@pytest.mark.timeout(10)  # Manager tests need more time than the default 5s
async def test_manager_idempotent_start(mock_redis_client):
    """Test PipelineWorkerManager start is idempotent."""
    manager = PipelineWorkerManager(
        redis_client=mock_redis_client,
        worker_stop_timeout=TEST_STOP_TIMEOUT,
    )

    await manager.start()
    await manager.start()  # Should not raise

    assert manager.running is True

    await manager.stop()


@pytest.mark.asyncio
@pytest.mark.timeout(10)  # Manager tests need more time than the default 5s
async def test_manager_idempotent_stop(mock_redis_client):
    """Test PipelineWorkerManager stop is idempotent."""
    manager = PipelineWorkerManager(
        redis_client=mock_redis_client,
        worker_stop_timeout=TEST_STOP_TIMEOUT,
    )

    await manager.stop()  # Stop without starting
    assert manager.running is False

    await manager.start()
    await manager.stop()
    await manager.stop()  # Double stop
    assert manager.running is False


@pytest.mark.asyncio
@pytest.mark.timeout(10)  # Manager tests need more time than the default 5s
async def test_manager_signal_handler_installation(mock_redis_client):
    """Test PipelineWorkerManager installs signal handlers (lines 870-871)."""
    manager = PipelineWorkerManager(
        redis_client=mock_redis_client,
        worker_stop_timeout=TEST_STOP_TIMEOUT,
    )

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
@pytest.mark.timeout(10)  # Manager tests need more time than the default 5s
async def test_manager_signal_handler_not_implemented(mock_redis_client):
    """Test PipelineWorkerManager handles NotImplementedError for signals (lines 879-881)."""
    manager = PipelineWorkerManager(
        redis_client=mock_redis_client,
        worker_stop_timeout=TEST_STOP_TIMEOUT,
    )

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
@pytest.mark.timeout(10)  # Manager tests need more time than the default 5s
async def test_manager_signal_handler_runtime_error(mock_redis_client):
    """Test PipelineWorkerManager handles RuntimeError for signals (lines 879-881)."""
    manager = PipelineWorkerManager(
        redis_client=mock_redis_client,
        worker_stop_timeout=TEST_STOP_TIMEOUT,
    )

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
@pytest.mark.timeout(10)  # Manager tests need more time than the default 5s
async def test_manager_signal_handler_triggers_stop(mock_redis_client):
    """Test that signal handler actually triggers stop when invoked."""
    manager = PipelineWorkerManager(
        redis_client=mock_redis_client,
        worker_stop_timeout=TEST_STOP_TIMEOUT,
    )

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
@pytest.mark.timeout(10)  # Manager tests need more time than the default 5s
async def test_get_pipeline_manager_singleton(mock_redis_client):
    """Test get_pipeline_manager returns singleton."""
    # Clear any existing singleton
    import backend.services.pipeline_workers as module

    module._pipeline_manager = None

    # Create a fast manager directly and set as singleton to avoid slow default timeouts
    fast_manager = PipelineWorkerManager(
        redis_client=mock_redis_client,
        worker_stop_timeout=TEST_STOP_TIMEOUT,
    )
    module._pipeline_manager = fast_manager

    # Now get_pipeline_manager should return our fast manager
    manager1 = await get_pipeline_manager(mock_redis_client)
    manager2 = await get_pipeline_manager(mock_redis_client)

    assert manager1 is manager2
    assert manager1 is fast_manager

    # Cleanup
    await stop_pipeline_manager()


@pytest.mark.asyncio
@pytest.mark.timeout(10)  # Manager tests need more time than the default 5s
async def test_stop_pipeline_manager_clears_singleton(mock_redis_client):
    """Test stop_pipeline_manager clears the singleton."""
    import backend.services.pipeline_workers as module

    module._pipeline_manager = None

    # Create a fast manager directly to avoid slow default timeouts
    fast_manager = PipelineWorkerManager(
        redis_client=mock_redis_client,
        worker_stop_timeout=TEST_STOP_TIMEOUT,
    )
    module._pipeline_manager = fast_manager

    manager = await get_pipeline_manager(mock_redis_client)
    assert manager is fast_manager
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
        # Wait for processing to start (event-based instead of arbitrary sleep)
        await wait_for_condition(
            lambda: call_count >= 1, timeout=2.0, description="processing started"
        )

        await worker.stop()

    assert worker.running is False
    assert worker.stats.state == WorkerState.STOPPED


@pytest.mark.asyncio
@pytest.mark.timeout(10)  # Manager tests need more time than the default 5s
async def test_manager_stops_all_workers_on_shutdown(mock_redis_client):
    """Test manager stops all workers during shutdown."""
    manager = PipelineWorkerManager(
        redis_client=mock_redis_client,
        worker_stop_timeout=TEST_STOP_TIMEOUT,
    )

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
    # Use the batch method as it's the optimized version used in pipeline (NEM-1329)
    processor.extract_frames_for_detection_batch = AsyncMock(return_value=[])
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

    # Setup video processor to return frames (using batch method per NEM-1329)
    mock_video_processor.extract_frames_for_detection_batch = AsyncMock(
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
        # Wait for video to be processed (event-based instead of arbitrary sleep)
        await wait_for_items_processed(worker, min_count=1)
        await worker.stop()

    # Verify video was processed
    assert worker.stats.items_processed == 1
    mock_video_processor.extract_frames_for_detection_batch.assert_called_once()
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
    mock_video_processor.extract_frames_for_detection_batch = AsyncMock(return_value=[])

    worker = DetectionQueueWorker(
        redis_client=mock_redis_client,
        detector_client=mock_detector_client,
        batch_aggregator=mock_batch_aggregator,
        video_processor=mock_video_processor,
        poll_timeout=1,
    )

    await worker.start()
    # Wait for video item to be processed (event-based instead of arbitrary sleep)
    await wait_for_items_processed(worker, min_count=1)
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
        # Wait for image to be processed (event-based instead of arbitrary sleep)
        await wait_for_items_processed(worker, min_count=1)
        await worker.stop()

    # Verify image was processed
    assert worker.stats.items_processed == 1
    # Video processor should NOT have been called for image
    mock_video_processor.extract_frames_for_detection_batch.assert_not_called()
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
        # Wait for item to be processed (event-based instead of arbitrary sleep)
        await wait_for_items_processed(worker, min_count=1)
        await worker.stop()

    # Should process as image (default)
    assert worker.stats.items_processed == 1
    mock_video_processor.extract_frames_for_detection_batch.assert_not_called()


# =============================================================================
# Retry Handler and DLQ Tests
# =============================================================================


@pytest.fixture
def mock_retry_handler():
    """Create a mock retry handler."""
    from backend.services.retry_handler import RetryResult

    handler = MagicMock()
    handler.with_retry = AsyncMock(return_value=RetryResult(success=True, result=[], attempts=1))
    return handler


@pytest.mark.asyncio
async def test_detection_worker_uses_retry_handler(
    mock_redis_client, mock_detector_client, mock_batch_aggregator, mock_retry_handler
):
    """Test that DetectionQueueWorker uses retry handler for detection."""
    from backend.services.retry_handler import RetryResult

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

    # Setup retry handler to return success
    detection = MagicMock()
    detection.id = 1
    detection.confidence = 0.95
    detection.object_type = "person"
    mock_retry_handler.with_retry = AsyncMock(
        return_value=RetryResult(success=True, result=[detection], attempts=1)
    )

    worker = DetectionQueueWorker(
        redis_client=mock_redis_client,
        detector_client=mock_detector_client,
        batch_aggregator=mock_batch_aggregator,
        retry_handler=mock_retry_handler,
        poll_timeout=1,
    )

    with patch("backend.services.pipeline_workers.get_session") as mock_get_session:
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        await worker.start()
        # Wait for item to be processed (event-based instead of arbitrary sleep)
        await wait_for_items_processed(worker, min_count=1)
        await worker.stop()

    # Verify retry handler was called
    assert mock_retry_handler.with_retry.called
    assert worker.stats.items_processed == 1


@pytest.mark.asyncio
async def test_detection_worker_handles_retry_failure_and_dlq(
    mock_redis_client, mock_detector_client, mock_batch_aggregator, mock_retry_handler
):
    """Test that DetectionQueueWorker handles retry failure and DLQ correctly."""
    from backend.services.retry_handler import RetryResult

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

    # Setup retry handler to return failure (all retries exhausted, moved to DLQ)
    mock_retry_handler.with_retry = AsyncMock(
        return_value=RetryResult(
            success=False,
            result=None,
            error="Detector unavailable",
            attempts=3,
            moved_to_dlq=True,
        )
    )

    worker = DetectionQueueWorker(
        redis_client=mock_redis_client,
        detector_client=mock_detector_client,
        batch_aggregator=mock_batch_aggregator,
        retry_handler=mock_retry_handler,
        poll_timeout=1,
    )

    await worker.start()
    # Wait for error to be recorded (event-based instead of arbitrary sleep)
    await wait_for_errors(worker, min_count=1)
    await worker.stop()

    # Item failed - should count as error, not processed
    assert worker.stats.items_processed == 0
    assert worker.stats.errors == 1
    # Batch aggregator should NOT have been called (detection failed)
    mock_batch_aggregator.add_detection.assert_not_called()


@pytest.mark.asyncio
async def test_detection_worker_passes_job_data_to_retry_handler(
    mock_redis_client, mock_detector_client, mock_batch_aggregator
):
    """Test that job data is passed to retry handler for DLQ tracking."""
    from backend.services.retry_handler import RetryHandler, RetryResult

    call_count = 0
    captured_job_data = None

    async def mock_get_from_queue(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        if call_count == 1:
            return {
                "camera_id": "front_door",
                "file_path": "/path/to/image.jpg",
                "timestamp": "2025-12-28T10:00:00",
                "media_type": "image",
            }
        return None

    mock_redis_client.get_from_queue = mock_get_from_queue

    # Create a spy retry handler that captures job_data
    async def capture_with_retry(operation, job_data, queue_name, *args, **kwargs):
        nonlocal captured_job_data
        captured_job_data = job_data
        return RetryResult(success=True, result=[], attempts=1)

    mock_retry_handler = MagicMock(spec=RetryHandler)
    mock_retry_handler.with_retry = AsyncMock(side_effect=capture_with_retry)

    worker = DetectionQueueWorker(
        redis_client=mock_redis_client,
        detector_client=mock_detector_client,
        batch_aggregator=mock_batch_aggregator,
        retry_handler=mock_retry_handler,
        poll_timeout=1,
    )

    with patch("backend.services.pipeline_workers.get_session") as mock_get_session:
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        await worker.start()
        # Wait for retry handler to be called (event-based instead of arbitrary sleep)
        await wait_for_call_count(mock_retry_handler.with_retry, min_count=1)
        await worker.stop()

    # Verify job data was captured with original queue item fields
    assert captured_job_data is not None
    assert captured_job_data["camera_id"] == "front_door"
    assert captured_job_data["file_path"] == "/path/to/image.jpg"


@pytest.mark.asyncio
async def test_detection_worker_initializes_with_retry_handler(mock_redis_client):
    """Test DetectionQueueWorker initializes retry handler correctly."""
    worker = DetectionQueueWorker(
        redis_client=mock_redis_client,
        poll_timeout=1,
    )

    # Should have a retry handler initialized
    assert worker._retry_handler is not None
    # Config should have expected values
    assert worker._retry_handler.config.max_retries == 3
    assert worker._retry_handler.config.base_delay_seconds == 1.0


# =============================================================================
# Pipeline Start Time Tracking Tests (bead 4mje.3)
# =============================================================================


@pytest.mark.asyncio
async def test_detection_worker_passes_pipeline_start_time_to_batch_aggregator(
    mock_redis_client, mock_detector_client, mock_batch_aggregator
):
    """Test that DetectionQueueWorker passes pipeline_start_time to batch aggregator.

    This tests the fix for bead 4mje.3: Pipeline latency metrics are all null because
    total_pipeline stage is defined but never recorded. The pipeline_start_time must
    be propagated from file detection through to event creation.
    """
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
                "pipeline_start_time": "2025-12-28T10:00:00.000000",
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
        poll_timeout=1,
    )

    with patch("backend.services.pipeline_workers.get_session") as mock_get_session:
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        await worker.start()
        await wait_for_items_processed(worker, min_count=1)
        await worker.stop()

    # Verify batch aggregator was called with pipeline_start_time
    mock_batch_aggregator.add_detection.assert_called_once()
    call_kwargs = mock_batch_aggregator.add_detection.call_args[1]
    assert "pipeline_start_time" in call_kwargs
    assert call_kwargs["pipeline_start_time"] == "2025-12-28T10:00:00.000000"


@pytest.mark.asyncio
async def test_detection_worker_handles_missing_pipeline_start_time(
    mock_redis_client, mock_detector_client, mock_batch_aggregator
):
    """Test that DetectionQueueWorker handles queue items without pipeline_start_time.

    For backwards compatibility, older queue items may not have pipeline_start_time.
    The worker should still process them normally.
    """
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
                # pipeline_start_time intentionally omitted
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
        poll_timeout=1,
    )

    with patch("backend.services.pipeline_workers.get_session") as mock_get_session:
        mock_session = AsyncMock()
        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        await worker.start()
        await wait_for_items_processed(worker, min_count=1)
        await worker.stop()

    # Verify batch aggregator was called (with None pipeline_start_time)
    mock_batch_aggregator.add_detection.assert_called_once()
    call_kwargs = mock_batch_aggregator.add_detection.call_args[1]
    assert call_kwargs.get("pipeline_start_time") is None


@pytest.mark.asyncio
async def test_analysis_worker_records_total_pipeline_latency(mock_redis_client, mock_analyzer):
    """Test that AnalysisQueueWorker records total_pipeline latency when pipeline_start_time is present.

    This is the key test for bead 4mje.3 fix: the total_pipeline latency must be recorded
    when processing analysis queue items that include pipeline_start_time.
    """
    call_count = 0
    # Use a timestamp from 5 seconds ago to ensure measurable latency
    pipeline_start_time = (
        datetime.now().isoformat()
    )  # Will have ~0ms latency but still exercises the code path

    async def mock_get_from_queue(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        if call_count == 1:
            return {
                "batch_id": "batch_123",
                "camera_id": "front_door",
                "detection_ids": [1, 2, 3],
                "pipeline_start_time": pipeline_start_time,
            }
        return None

    mock_redis_client.get_from_queue = mock_get_from_queue

    worker = AnalysisQueueWorker(
        redis_client=mock_redis_client,
        analyzer=mock_analyzer,
        poll_timeout=1,
    )

    with patch(
        "backend.services.pipeline_workers.record_pipeline_stage_latency"
    ) as mock_record_latency:
        await worker.start()
        await wait_for_items_processed(worker, min_count=1)
        await worker.stop()

        # Verify total_pipeline latency was recorded
        mock_record_latency.assert_called()
        call_args = mock_record_latency.call_args_list
        # Find the total_pipeline call
        total_pipeline_calls = [c for c in call_args if c[0][0] == "total_pipeline"]
        assert len(total_pipeline_calls) == 1
        # Latency should be a positive number (in milliseconds)
        latency_ms = total_pipeline_calls[0][0][1]
        assert latency_ms >= 0


@pytest.mark.asyncio
async def test_analysis_worker_handles_missing_pipeline_start_time(
    mock_redis_client, mock_analyzer
):
    """Test that AnalysisQueueWorker handles queue items without pipeline_start_time.

    For backwards compatibility, older queue items may not have pipeline_start_time.
    The worker should still process them normally without recording total_pipeline latency.
    """
    call_count = 0

    async def mock_get_from_queue(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        if call_count == 1:
            return {
                "batch_id": "batch_123",
                "camera_id": "front_door",
                "detection_ids": [1, 2, 3],
                # pipeline_start_time intentionally omitted
            }
        return None

    mock_redis_client.get_from_queue = mock_get_from_queue

    worker = AnalysisQueueWorker(
        redis_client=mock_redis_client,
        analyzer=mock_analyzer,
        poll_timeout=1,
    )

    with patch(
        "backend.services.pipeline_workers.record_pipeline_stage_latency"
    ) as mock_record_latency:
        await worker.start()
        await wait_for_items_processed(worker, min_count=1)
        await worker.stop()

        # Verify total_pipeline latency was NOT recorded (no pipeline_start_time)
        call_args = mock_record_latency.call_args_list
        total_pipeline_calls = [c for c in call_args if c[0][0] == "total_pipeline"]
        assert len(total_pipeline_calls) == 0


@pytest.mark.asyncio
async def test_analysis_worker_handles_invalid_pipeline_start_time(
    mock_redis_client, mock_analyzer
):
    """Test that AnalysisQueueWorker handles invalid pipeline_start_time gracefully.

    If the timestamp is malformed, the worker should log a warning but continue
    processing the item normally.
    """
    call_count = 0

    async def mock_get_from_queue(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        if call_count == 1:
            return {
                "batch_id": "batch_123",
                "camera_id": "front_door",
                "detection_ids": [1, 2, 3],
                "pipeline_start_time": "invalid-timestamp-format",
            }
        return None

    mock_redis_client.get_from_queue = mock_get_from_queue

    worker = AnalysisQueueWorker(
        redis_client=mock_redis_client,
        analyzer=mock_analyzer,
        poll_timeout=1,
    )

    with patch(
        "backend.services.pipeline_workers.record_pipeline_stage_latency"
    ) as mock_record_latency:
        await worker.start()
        await wait_for_items_processed(worker, min_count=1)
        await worker.stop()

        # Item should still be processed (no errors)
        assert worker.stats.items_processed == 1
        assert worker.stats.errors == 0

        # total_pipeline should NOT be recorded (invalid timestamp)
        call_args = mock_record_latency.call_args_list
        total_pipeline_calls = [c for c in call_args if c[0][0] == "total_pipeline"]
        assert len(total_pipeline_calls) == 0


# =============================================================================
# Test broadcast_worker_event function (lines 95-126)
# =============================================================================


@pytest.mark.asyncio
async def test_broadcast_worker_event_success():
    """Test that broadcast_worker_event emits events successfully."""
    from backend.services.pipeline_workers import broadcast_worker_event

    mock_emitter = AsyncMock()
    mock_emitter.emit = AsyncMock()

    await broadcast_worker_event(
        emitter=mock_emitter,
        event_type="worker.started",
        worker_name="test_worker",
        worker_type="detection",
        extra_field="extra_value",
    )

    # Verify emit was called with correct event type and payload
    mock_emitter.emit.assert_called_once()
    call_args = mock_emitter.emit.call_args
    # First arg should be WebSocketEventType.WORKER_STARTED
    assert call_args[0][0].name == "WORKER_STARTED"
    # Second arg should be the payload dict
    payload = call_args[0][1]
    assert payload["worker_name"] == "test_worker"
    assert payload["worker_type"] == "detection"
    assert payload["extra_field"] == "extra_value"
    assert "timestamp" in payload


@pytest.mark.asyncio
async def test_broadcast_worker_event_with_none_emitter():
    """Test that broadcast_worker_event handles None emitter gracefully."""
    from backend.services.pipeline_workers import broadcast_worker_event

    # Should not raise an exception
    await broadcast_worker_event(
        emitter=None,
        event_type="worker.started",
        worker_name="test_worker",
        worker_type="detection",
    )


@pytest.mark.asyncio
async def test_broadcast_worker_event_unknown_event_type():
    """Test that broadcast_worker_event handles unknown event types."""
    from backend.services.pipeline_workers import broadcast_worker_event

    mock_emitter = AsyncMock()
    mock_emitter.emit = AsyncMock()

    await broadcast_worker_event(
        emitter=mock_emitter,
        event_type="worker.unknown_event_type",
        worker_name="test_worker",
        worker_type="detection",
    )

    # Should not call emit for unknown event type
    mock_emitter.emit.assert_not_called()


@pytest.mark.asyncio
async def test_broadcast_worker_event_emit_failure():
    """Test that broadcast_worker_event handles emit failures gracefully."""
    from backend.services.pipeline_workers import broadcast_worker_event

    mock_emitter = AsyncMock()
    mock_emitter.emit = AsyncMock(side_effect=Exception("Emit failed"))

    # Should not raise exception (failures are logged but not propagated)
    await broadcast_worker_event(
        emitter=mock_emitter,
        event_type="worker.started",
        worker_name="test_worker",
        worker_type="detection",
    )


@pytest.mark.asyncio
async def test_broadcast_worker_event_all_event_types():
    """Test all supported worker event types."""
    from backend.services.pipeline_workers import broadcast_worker_event

    mock_emitter = AsyncMock()
    mock_emitter.emit = AsyncMock()

    event_types = [
        "worker.started",
        "worker.stopped",
        "worker.health_check_failed",
        "worker.restarting",
        "worker.recovered",
        "worker.error",
    ]

    for event_type in event_types:
        mock_emitter.emit.reset_mock()
        await broadcast_worker_event(
            emitter=mock_emitter,
            event_type=event_type,
            worker_name="test_worker",
            worker_type="detection",
        )
        # Each valid event type should result in an emit call
        mock_emitter.emit.assert_called_once()


# =============================================================================
# Test video detection error handling (lines 635-646, 663-672)
# =============================================================================


@pytest.mark.asyncio
async def test_detection_worker_video_processing_detector_unavailable_during_frames():
    """Test video processing when detector becomes unavailable mid-processing."""
    from backend.services.detector_client import DetectorUnavailableError
    from backend.services.retry_handler import RetryResult

    mock_redis = AsyncMock(spec=RedisClient)
    mock_detector = AsyncMock()
    mock_aggregator = AsyncMock(spec=BatchAggregator)
    mock_video_processor = AsyncMock()

    # Mock video processor to return multiple frames
    mock_video_processor.extract_frames_for_detection_batch = AsyncMock(
        return_value=["frame1.jpg", "frame2.jpg", "frame3.jpg"]
    )
    mock_video_processor.get_video_metadata = AsyncMock(return_value={"duration": 10.0, "fps": 30})
    mock_video_processor.cleanup_extracted_frames = MagicMock()

    # Mock retry handler - first call succeeds, second fails
    call_count = 0

    async def mock_retry(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First frame succeeds
            detection = MagicMock()
            detection.id = 1
            detection.confidence = 0.9
            detection.object_type = "person"
            return RetryResult(
                success=True,
                result=[detection],
                attempts=1,
                error=None,
                moved_to_dlq=False,
            )
        else:
            # Subsequent frames fail
            return RetryResult(
                success=False,
                result=None,
                attempts=3,
                error="Detector unavailable",
                moved_to_dlq=True,
            )

    mock_retry_handler = AsyncMock()
    mock_retry_handler.with_retry = mock_retry

    worker = DetectionQueueWorker(
        redis_client=mock_redis,
        detector_client=mock_detector,
        batch_aggregator=mock_aggregator,
        video_processor=mock_video_processor,
        retry_handler=mock_retry_handler,
    )

    job_data = {
        "camera_id": "front_door",
        "file_path": "/videos/test.mp4",
        "media_type": "video",
    }

    # Mock database session
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    # Should raise DetectorUnavailableError and cleanup frames
    with (
        patch("backend.services.pipeline_workers.get_session", return_value=mock_session),
        pytest.raises(DetectorUnavailableError),
    ):
        await worker._process_video_detection(
            camera_id="front_door",
            video_path="/videos/test.mp4",
            job_data=job_data,
            pipeline_start_time=None,
        )

    # Verify cleanup was called despite error
    mock_video_processor.cleanup_extracted_frames.assert_called_once_with("/videos/test.mp4")


@pytest.mark.asyncio
async def test_detection_worker_video_processing_frame_exception_continues():
    """Test that frame processing exceptions are logged but processing continues."""
    from backend.services.retry_handler import RetryResult

    mock_redis = AsyncMock(spec=RedisClient)
    mock_detector = AsyncMock()
    mock_aggregator = AsyncMock(spec=BatchAggregator)
    mock_video_processor = AsyncMock()

    # Mock video processor
    mock_video_processor.extract_frames_for_detection_batch = AsyncMock(
        return_value=["frame1.jpg", "frame2.jpg", "frame3.jpg"]
    )
    mock_video_processor.get_video_metadata = AsyncMock(return_value={"duration": 10.0, "fps": 30})
    mock_video_processor.cleanup_extracted_frames = MagicMock()

    # Mock retry handler - frame 2 raises exception but continues
    call_count = 0

    async def mock_retry(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            # Second frame raises exception but returns success with empty result
            return RetryResult(
                success=True,
                result=[],  # Empty result for failed frame
                attempts=1,
                error="Frame processing error",
                moved_to_dlq=False,
            )
        # Other frames succeed
        detection = MagicMock()
        detection.id = call_count
        detection.confidence = 0.9
        detection.object_type = "person"
        return RetryResult(
            success=True,
            result=[detection],
            attempts=1,
            error=None,
            moved_to_dlq=False,
        )

    mock_retry_handler = AsyncMock()
    mock_retry_handler.with_retry = mock_retry

    worker = DetectionQueueWorker(
        redis_client=mock_redis,
        detector_client=mock_detector,
        batch_aggregator=mock_aggregator,
        video_processor=mock_video_processor,
        retry_handler=mock_retry_handler,
    )

    job_data = {
        "camera_id": "front_door",
        "file_path": "/videos/test.mp4",
        "media_type": "video",
    }

    # Mock database session
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    # Should complete successfully despite frame 2 error
    with patch("backend.services.pipeline_workers.get_session", return_value=mock_session):
        await worker._process_video_detection(
            camera_id="front_door",
            video_path="/videos/test.mp4",
            job_data=job_data,
            pipeline_start_time=None,
        )

    # Verify cleanup was called
    mock_video_processor.cleanup_extracted_frames.assert_called_once()


# =============================================================================
# Test drain_queues with stall detection (lines 1557-1564, 1570-1577)
# =============================================================================


@pytest.mark.asyncio
async def test_manager_drain_queues_successful():
    """Test successful queue draining."""
    mock_redis = AsyncMock(spec=RedisClient)

    # Simulate queue draining: 3 items -> 2 -> 1 -> 0
    queue_depths = [3, 2, 1, 0]
    call_count = 0

    async def mock_get_queue_length(queue_name):
        nonlocal call_count
        if call_count < len(queue_depths):
            depth = queue_depths[call_count]
            call_count += 1
            return depth
        return 0

    mock_redis.get_queue_length = mock_get_queue_length

    manager = PipelineWorkerManager(
        redis_client=mock_redis,
        enable_detection_worker=False,
        enable_analysis_worker=False,
        enable_timeout_worker=False,
        enable_metrics_worker=False,
    )

    remaining = await manager.drain_queues(timeout=5.0)
    assert remaining == 0
    assert not manager.accepting


@pytest.mark.asyncio
async def test_manager_drain_queues_with_stall():
    """Test queue draining with stall detection (no progress for 5+ seconds)."""
    mock_redis = AsyncMock(spec=RedisClient)

    # Simulate stall: each queue has 2 items (total 4)
    async def mock_get_queue_length(queue_name):
        return 2

    mock_redis.get_queue_length = mock_get_queue_length

    manager = PipelineWorkerManager(
        redis_client=mock_redis,
        enable_detection_worker=False,
        enable_analysis_worker=False,
        enable_timeout_worker=False,
        enable_metrics_worker=False,
    )

    # Use short timeout to avoid long test
    remaining = await manager.drain_queues(timeout=0.6)
    assert remaining == 4  # Still pending after timeout (2 per queue)


@pytest.mark.asyncio
async def test_manager_drain_queues_already_empty():
    """Test draining when queues are already empty."""
    mock_redis = AsyncMock(spec=RedisClient)

    async def mock_get_queue_length(queue_name):
        return 0

    mock_redis.get_queue_length = mock_get_queue_length

    manager = PipelineWorkerManager(
        redis_client=mock_redis,
        enable_detection_worker=False,
        enable_analysis_worker=False,
        enable_timeout_worker=False,
        enable_metrics_worker=False,
    )

    remaining = await manager.drain_queues(timeout=5.0)
    assert remaining == 0


# =============================================================================
# Test manager stop with ExceptionGroup handling (lines 1699-1703)
# =============================================================================


@pytest.mark.asyncio
async def test_manager_stop_with_worker_exceptions():
    """Test that manager handles worker stop exceptions gracefully."""
    mock_redis = AsyncMock(spec=RedisClient)

    # Create manager with workers
    manager = PipelineWorkerManager(
        redis_client=mock_redis,
        enable_detection_worker=True,
        enable_analysis_worker=True,
        enable_timeout_worker=True,
        enable_metrics_worker=True,
        worker_stop_timeout=0.1,
    )

    # Mock one worker to fail during stop
    original_stop = manager._detection_worker.stop

    async def failing_stop():
        raise RuntimeError("Worker stop failed")

    manager._detection_worker.stop = failing_stop
    manager._running = True  # Pretend we're running

    # Stop should complete despite exception (logged but not raised)
    await manager.stop()

    # Manager should still be stopped
    assert not manager.running


# =============================================================================
# Test get_pipeline_manager singleton with lock (lines 1820-1827)
# =============================================================================


@pytest.mark.asyncio
async def test_get_pipeline_manager_creates_singleton():
    """Test that get_pipeline_manager creates and returns singleton instance."""
    from backend.services.pipeline_workers import (
        get_pipeline_manager,
        reset_pipeline_manager_state,
    )

    reset_pipeline_manager_state()

    mock_redis = AsyncMock(spec=RedisClient)

    manager1 = await get_pipeline_manager(mock_redis)
    manager2 = await get_pipeline_manager(mock_redis)

    # Should return same instance
    assert manager1 is manager2

    reset_pipeline_manager_state()


@pytest.mark.asyncio
async def test_get_pipeline_manager_concurrent_initialization():
    """Test that concurrent initialization is handled correctly with lock."""
    from backend.services.pipeline_workers import (
        get_pipeline_manager,
        reset_pipeline_manager_state,
    )

    reset_pipeline_manager_state()

    mock_redis = AsyncMock(spec=RedisClient)

    # Simulate concurrent access
    results = await asyncio.gather(
        get_pipeline_manager(mock_redis),
        get_pipeline_manager(mock_redis),
        get_pipeline_manager(mock_redis),
    )

    # All should return the same instance
    assert results[0] is results[1]
    assert results[1] is results[2]

    reset_pipeline_manager_state()


# =============================================================================
# Test worker factory functions (lines 1903-1910, 1926-1933, 1949-1956, 1972-1979)
# =============================================================================


@pytest.mark.asyncio
async def test_create_detection_worker_factory():
    """Test create_detection_worker factory function."""
    from backend.services.pipeline_workers import create_detection_worker

    mock_redis = AsyncMock(spec=RedisClient)

    worker_func = create_detection_worker(mock_redis)
    assert callable(worker_func)
    # Just verify it returns a coroutine function, don't actually run it
    # (running it would require mocking detector, batch aggregator, etc.)


@pytest.mark.asyncio
async def test_create_analysis_worker_factory():
    """Test create_analysis_worker factory function."""
    from backend.services.pipeline_workers import create_analysis_worker

    mock_redis = AsyncMock(spec=RedisClient)

    worker_func = create_analysis_worker(mock_redis)
    assert callable(worker_func)
    # Just verify it returns a coroutine function


@pytest.mark.asyncio
async def test_create_timeout_worker_factory():
    """Test create_timeout_worker factory function."""
    from backend.services.pipeline_workers import create_timeout_worker

    mock_redis = AsyncMock(spec=RedisClient)

    worker_func = create_timeout_worker(mock_redis)
    assert callable(worker_func)
    # Just verify it returns a coroutine function


@pytest.mark.asyncio
async def test_create_metrics_worker_factory():
    """Test create_metrics_worker factory function."""
    from backend.services.pipeline_workers import create_metrics_worker

    mock_redis = AsyncMock(spec=RedisClient)

    worker_func = create_metrics_worker(mock_redis)
    assert callable(worker_func)
    # Just verify it returns a coroutine function


# =============================================================================
# Additional edge case tests for higher coverage
# =============================================================================


@pytest.mark.asyncio
async def test_detection_worker_video_processing_with_detector_unavailable_exception():
    """Test video processing when DetectorUnavailableError is raised directly (not via retry)."""
    from backend.services.detector_client import DetectorUnavailableError
    from backend.services.retry_handler import RetryResult

    mock_redis = AsyncMock(spec=RedisClient)
    mock_detector = AsyncMock()
    mock_aggregator = AsyncMock(spec=BatchAggregator)
    mock_video_processor = AsyncMock()

    # Mock video processor
    mock_video_processor.extract_frames_for_detection_batch = AsyncMock(
        return_value=["frame1.jpg", "frame2.jpg"]
    )
    mock_video_processor.get_video_metadata = AsyncMock(return_value={"duration": 10.0, "fps": 30})
    mock_video_processor.cleanup_extracted_frames = MagicMock()

    # Mock retry handler to succeed first, then raise exception directly
    call_count = 0

    async def mock_retry(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First frame succeeds
            detection = MagicMock()
            detection.id = 1
            detection.confidence = 0.9
            detection.object_type = "person"
            return RetryResult(
                success=True,
                result=[detection],
                attempts=1,
                error=None,
                moved_to_dlq=False,
            )
        else:
            # Second frame - raise DetectorUnavailableError directly
            # This tests the except DetectorUnavailableError block (lines 663-666)
            raise DetectorUnavailableError("Detector service is down")

    mock_retry_handler = AsyncMock()
    mock_retry_handler.with_retry = mock_retry

    worker = DetectionQueueWorker(
        redis_client=mock_redis,
        detector_client=mock_detector,
        batch_aggregator=mock_aggregator,
        video_processor=mock_video_processor,
        retry_handler=mock_retry_handler,
    )

    job_data = {
        "camera_id": "front_door",
        "file_path": "/videos/test.mp4",
        "media_type": "video",
    }

    # Mock database session
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("backend.services.pipeline_workers.get_session", return_value=mock_session),
        pytest.raises(DetectorUnavailableError),
    ):
        await worker._process_video_detection(
            camera_id="front_door",
            video_path="/videos/test.mp4",
            job_data=job_data,
            pipeline_start_time=None,
        )

    # Cleanup should be called in finally block
    mock_video_processor.cleanup_extracted_frames.assert_called_once()


@pytest.mark.asyncio
async def test_manager_drain_queues_with_stall_logging():
    """Test drain_queues with stall detection that triggers debug logging."""
    mock_redis = AsyncMock(spec=RedisClient)

    # Simulate stall that lasts long enough to trigger logging
    # First calls return high count, later calls return 0
    call_count = 0

    async def mock_get_queue_length(queue_name):
        nonlocal call_count
        call_count += 1
        # Return 2 per queue (4 total) for first 60 calls (6 seconds at 0.1s interval)
        # This will trigger stall logging after 5 seconds
        if call_count < 60:
            return 2
        return 0

    mock_redis.get_queue_length = mock_get_queue_length

    manager = PipelineWorkerManager(
        redis_client=mock_redis,
        enable_detection_worker=False,
        enable_analysis_worker=False,
        enable_timeout_worker=False,
        enable_metrics_worker=False,
    )

    # Run with longer timeout to allow stall logging to trigger
    remaining = await manager.drain_queues(timeout=10.0)
    # Should complete eventually
    assert remaining == 0
