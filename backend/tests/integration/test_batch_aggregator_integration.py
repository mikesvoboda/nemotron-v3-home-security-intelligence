"""Integration tests for batch aggregator service.

These tests verify the batch aggregator's timeout behavior and integration
with Redis in an end-to-end manner. Time-related functions are mocked to
avoid real timeout waits while still testing timeout logic correctly.
"""

import json
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.redis import QueueAddResult
from backend.services.batch_aggregator import BatchAggregator
from backend.tests.conftest import unique_id


@dataclass
class MockQueueAddResult:
    """Mock QueueAddResult for testing."""

    success: bool
    queue_length: int
    dropped_count: int = 0
    moved_to_dlq_count: int = 0
    error: str | None = None
    warning: str | None = None

    @property
    def had_backpressure(self) -> bool:
        """Return True if backpressure was applied."""
        return self.dropped_count > 0 or self.moved_to_dlq_count > 0 or self.error is not None


# Fixtures


@pytest.fixture
def mock_redis_client():
    """Mock Redis client with in-memory storage for integration testing."""
    storage: dict[str, str] = {}
    lists: dict[str, list[str]] = {}  # For RPUSH/LRANGE operations
    queues: dict[str, list] = {}

    mock_client = AsyncMock()

    async def mock_get(key: str) -> str | None:
        return storage.get(key)

    async def mock_set(key: str, value: str, *args, **kwargs) -> bool:
        storage[key] = value
        return True

    async def mock_delete(*keys: str) -> int:
        count = 0
        for key in keys:
            if key in storage:
                del storage[key]
                count += 1
            if key in lists:
                del lists[key]
                count += 1
        return count

    async def mock_add_to_queue_safe(queue_name: str, data: dict, **kwargs) -> QueueAddResult:
        """Mock add_to_queue_safe that returns a successful QueueAddResult."""
        if queue_name not in queues:
            queues[queue_name] = []
        queues[queue_name].append(json.dumps(data))
        return QueueAddResult(
            success=True,
            queue_length=len(queues[queue_name]),
        )

    async def mock_scan_iter(match: str = "*", count: int = 100):
        """Async generator for SCAN iteration (replacement for KEYS)."""
        import fnmatch

        for k in storage:
            if fnmatch.fnmatch(k, match):
                yield k

    # Internal client mock for direct Redis operations (rpush, lrange, expire)
    async def mock_rpush(key: str, value: str) -> int:
        """Mock RPUSH operation - atomically append to list."""
        if key not in lists:
            lists[key] = []
        lists[key].append(value)
        return len(lists[key])

    async def mock_lrange(key: str, start: int, end: int) -> list[str]:
        """Mock LRANGE operation - get list elements."""
        if key not in lists:
            return []
        if end == -1:
            return lists[key][start:]
        return lists[key][start : end + 1]

    async def mock_expire(key: str, ttl: int) -> bool:
        """Mock EXPIRE operation - set key TTL."""
        # In real Redis this sets expiration; for testing we just return True
        return True

    class MockPipeline:
        """Mock Redis pipeline that collects commands and executes them."""

        def __init__(self, storage_ref: dict[str, str]):
            self._commands: list[tuple[str, tuple]] = []
            self._storage = storage_ref

        def get(self, key: str) -> MockPipeline:
            """Add GET command to pipeline."""
            self._commands.append(("get", (key,)))
            return self

        async def execute(self) -> list:
            """Execute all commands and return results."""
            results = []
            for cmd, args in self._commands:
                if cmd == "get":
                    results.append(self._storage.get(args[0]))
            return results

    def mock_pipeline() -> MockPipeline:
        """Create a new mock pipeline."""
        return MockPipeline(storage)

    mock_client.get = mock_get
    mock_client.set = mock_set
    mock_client.delete = mock_delete
    mock_client.add_to_queue_safe = mock_add_to_queue_safe
    mock_client.pipeline = mock_pipeline

    # Internal client for scan_iter, list operations, and pipeline
    mock_internal = MagicMock()
    mock_internal.scan_iter = mock_scan_iter
    mock_internal.rpush = mock_rpush  # AsyncMock will be called with await
    mock_internal.lrange = mock_lrange  # AsyncMock will be called with await
    mock_internal.expire = mock_expire  # AsyncMock will be called with await
    mock_internal.pipeline = mock_pipeline  # Pipeline method on inner client
    mock_client._client = mock_internal

    # Expose internal storage for assertions
    mock_client._test_storage = storage
    mock_client._test_lists = lists
    mock_client._test_queues = queues

    return mock_client


@pytest.fixture
def batch_aggregator(mock_redis_client):
    """Create batch aggregator with mocked Redis client."""
    with patch("backend.services.batch_aggregator.get_settings") as mock_settings:
        mock_settings.return_value.batch_window_seconds = 90
        mock_settings.return_value.batch_idle_timeout_seconds = 30
        mock_settings.return_value.fast_path_confidence_threshold = 0.90
        mock_settings.return_value.fast_path_object_types = ["person"]

        aggregator = BatchAggregator(redis_client=mock_redis_client)
        return aggregator


# Integration Tests - Batch Lifecycle with Mocked Time


@pytest.mark.asyncio
async def test_batch_window_timeout_with_mocked_time(batch_aggregator, mock_redis_client):
    """Test that batch closes after 90-second window expires.

    Uses mocked time to avoid real waits while verifying timeout logic.
    Tests that window timeout (90s) fires even with continuous activity
    (which keeps idle timeout from triggering first).
    """
    camera_id = unique_id("front_door")
    file_path = f"/export/foscam/{camera_id}/image_001.jpg"

    # Start at time 1000.0
    start_time = 1000.0

    with patch("backend.services.batch_aggregator.time.time", return_value=start_time):
        batch_id = await batch_aggregator.add_detection(camera_id, 1, file_path)

    # Verify batch was created
    assert batch_id is not None
    assert mock_redis_client._test_storage.get(f"batch:{camera_id}:current") == batch_id

    # Add activity at 70 seconds to reset idle timer (keeps batch alive via idle timeout)
    with patch("backend.services.batch_aggregator.time.time", return_value=start_time + 70):
        await batch_aggregator.add_detection(camera_id, 2, file_path)

    # Check at 89 seconds from start (19s since last activity, under 30s idle)
    with patch("backend.services.batch_aggregator.time.time", return_value=start_time + 89):
        closed_batches = await batch_aggregator.check_batch_timeouts()

    # Batch should NOT be closed yet (window is 90s, we're at 89s)
    assert batch_id not in closed_batches
    assert mock_redis_client._test_storage.get(f"batch:{camera_id}:current") == batch_id

    # Check at 91 seconds from start (21s since last activity, under 30s idle)
    # But window timeout (91s >= 90s) should trigger
    with patch("backend.services.batch_aggregator.time.time", return_value=start_time + 91):
        closed_batches = await batch_aggregator.check_batch_timeouts()

    # Batch should be closed due to window timeout (not idle timeout)
    assert batch_id in closed_batches
    assert mock_redis_client._test_storage.get(f"batch:{camera_id}:current") is None

    # Should have been queued for analysis
    assert "analysis_queue" in mock_redis_client._test_queues


@pytest.mark.asyncio
async def test_batch_idle_timeout_with_mocked_time(batch_aggregator, mock_redis_client):
    """Test that batch closes after 30-second idle period.

    Uses mocked time to avoid real waits while verifying timeout logic.
    """
    camera_id = unique_id("back_door")
    detection_id = 2
    file_path = f"/export/foscam/{camera_id}/image_002.jpg"

    # Start at time 1000.0
    current_time = 1000.0

    with patch("backend.services.batch_aggregator.time.time", return_value=current_time):
        batch_id = await batch_aggregator.add_detection(camera_id, detection_id, file_path)

    # Simulate time passing - 25 seconds (not yet idle timeout)
    with patch("backend.services.batch_aggregator.time.time", return_value=current_time + 25):
        closed_batches = await batch_aggregator.check_batch_timeouts()

    # Batch should NOT be closed yet
    assert batch_id not in closed_batches

    # Simulate time passing - 35 seconds (idle timeout exceeded)
    with patch("backend.services.batch_aggregator.time.time", return_value=current_time + 35):
        closed_batches = await batch_aggregator.check_batch_timeouts()

    # Batch should be closed now
    assert batch_id in closed_batches


@pytest.mark.asyncio
async def test_batch_activity_resets_idle_timeout(batch_aggregator, mock_redis_client):
    """Test that adding detections resets the idle timeout.

    Uses mocked time to verify that activity keeps batch alive.
    """
    camera_id = unique_id("garage")
    file_path = f"/export/foscam/{camera_id}/image.jpg"

    # Start at time 1000.0
    current_time = 1000.0

    with patch("backend.services.batch_aggregator.time.time", return_value=current_time):
        batch_id = await batch_aggregator.add_detection(camera_id, 1, file_path)

    # Add activity at 20 seconds (before 30s idle timeout)
    with patch("backend.services.batch_aggregator.time.time", return_value=current_time + 20):
        await batch_aggregator.add_detection(camera_id, 2, file_path)

    # Check at 45 seconds from start (but only 25s from last activity)
    with patch("backend.services.batch_aggregator.time.time", return_value=current_time + 45):
        closed_batches = await batch_aggregator.check_batch_timeouts()

    # Batch should NOT be closed - activity reset the idle timer
    assert batch_id not in closed_batches

    # Check at 55 seconds from start (35s from last activity)
    with patch("backend.services.batch_aggregator.time.time", return_value=current_time + 55):
        closed_batches = await batch_aggregator.check_batch_timeouts()

    # Now batch should be closed due to idle timeout
    assert batch_id in closed_batches


@pytest.mark.asyncio
async def test_multiple_cameras_independent_timeouts(batch_aggregator, mock_redis_client):
    """Test that timeouts are independent per camera.

    Uses mocked time to verify cameras don't affect each other's timeouts.
    """
    current_time = 1000.0
    camera1 = unique_id("camera1")
    camera2 = unique_id("camera2")

    # Create batch for camera 1
    with patch("backend.services.batch_aggregator.time.time", return_value=current_time):
        batch_id_1 = await batch_aggregator.add_detection(camera1, 1, f"/path/{camera1}/1.jpg")

    # Create batch for camera 2 at +20s
    with patch("backend.services.batch_aggregator.time.time", return_value=current_time + 20):
        batch_id_2 = await batch_aggregator.add_detection(camera2, 2, f"/path/{camera2}/2.jpg")

    # Check at +35s - camera1 should timeout (35s idle), camera2 should NOT (15s idle)
    with patch("backend.services.batch_aggregator.time.time", return_value=current_time + 35):
        closed_batches = await batch_aggregator.check_batch_timeouts()

    assert batch_id_1 in closed_batches
    assert batch_id_2 not in closed_batches


@pytest.mark.asyncio
async def test_batch_close_cleans_up_redis_keys(batch_aggregator, mock_redis_client):
    """Test that batch close removes all Redis keys for the batch.

    Verifies that:
    1. All batch-related keys are removed
    2. Detection list is converted to analysis queue entry
    3. Camera's current batch reference is cleared
    """
    camera_id = unique_id("kitchen")
    file_path = f"/export/foscam/{camera_id}/image.jpg"
    current_time = 1000.0

    # Create batch and add detection
    with patch("backend.services.batch_aggregator.time.time", return_value=current_time):
        batch_id = await batch_aggregator.add_detection(camera_id, 1, file_path)
        await batch_aggregator.add_detection(camera_id, 2, file_path)

    # Verify keys were created
    storage = mock_redis_client._test_storage
    lists = mock_redis_client._test_lists
    assert f"batch:{camera_id}:current" in storage
    assert f"batch:{batch_id}:camera_id" in storage
    assert f"batch:{batch_id}:started_at" in storage
    assert f"batch:{batch_id}:last_activity" in storage
    assert f"batch:{batch_id}:detections" in lists
    assert len(lists[f"batch:{batch_id}:detections"]) == 2

    # Close batch manually
    with patch("backend.services.batch_aggregator.time.time", return_value=current_time + 100):
        summary = await batch_aggregator.close_batch(batch_id)

    # Verify keys were cleaned up
    assert f"batch:{camera_id}:current" not in storage
    assert f"batch:{batch_id}:camera_id" not in storage
    assert f"batch:{batch_id}:started_at" not in storage
    assert f"batch:{batch_id}:last_activity" not in storage
    assert f"batch:{batch_id}:detections" not in lists

    # Verify batch was queued for analysis
    assert "analysis_queue" in mock_redis_client._test_queues
    queue_item = json.loads(mock_redis_client._test_queues["analysis_queue"][0])
    assert queue_item["batch_id"] == batch_id
    assert queue_item["camera_id"] == camera_id
    assert queue_item["detection_ids"] == [1, 2]

    # Verify summary
    assert summary["batch_id"] == batch_id
    assert summary["camera_id"] == camera_id
    assert summary["detection_count"] == 2


@pytest.mark.asyncio
async def test_batch_timeout_check_handles_missing_batch_data(batch_aggregator, mock_redis_client):
    """Test that timeout check gracefully handles incomplete batch data.

    Verifies robustness when batch keys are partially present (e.g., due to
    concurrent deletion or Redis key expiration).
    """
    camera_id = unique_id("incomplete")

    # Manually create a batch reference without full metadata
    mock_redis_client._test_storage[f"batch:{camera_id}:current"] = "orphan_batch_id"
    # No started_at, last_activity, or detections keys

    current_time = 1000.0
    with patch("backend.services.batch_aggregator.time.time", return_value=current_time):
        # Should not raise - should handle gracefully
        closed_batches = await batch_aggregator.check_batch_timeouts()

    # Orphan batch should be skipped (missing started_at)
    assert "orphan_batch_id" not in closed_batches


@pytest.mark.asyncio
async def test_concurrent_detections_same_camera(batch_aggregator, mock_redis_client):
    """Test that concurrent detections for the same camera are handled safely.

    While mocking prevents true concurrency, this tests the batch aggregation
    logic when multiple detections arrive for the same camera's batch.
    """
    camera_id = unique_id("multi_detect")
    current_time = 1000.0

    with patch("backend.services.batch_aggregator.time.time", return_value=current_time):
        batch_id_1 = await batch_aggregator.add_detection(camera_id, 1, f"/path/{camera_id}/1.jpg")
        batch_id_2 = await batch_aggregator.add_detection(camera_id, 2, f"/path/{camera_id}/2.jpg")
        batch_id_3 = await batch_aggregator.add_detection(camera_id, 3, f"/path/{camera_id}/3.jpg")

    # All should be added to the same batch
    assert batch_id_1 == batch_id_2 == batch_id_3

    # Verify all detections are in the list
    lists = mock_redis_client._test_lists
    detections = lists.get(f"batch:{batch_id_1}:detections", [])
    assert len(detections) == 3
    assert "1" in detections
    assert "2" in detections
    assert "3" in detections
