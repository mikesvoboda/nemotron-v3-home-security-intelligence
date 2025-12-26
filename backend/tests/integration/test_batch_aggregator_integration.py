"""Integration tests for batch aggregator service.

These tests verify the batch aggregator's timeout behavior and integration
with Redis in an end-to-end manner. Time-related functions are mocked to
avoid real timeout waits while still testing timeout logic correctly.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.batch_aggregator import BatchAggregator

# Fixtures


@pytest.fixture
def mock_redis_client():
    """Mock Redis client with in-memory storage for integration testing."""
    storage: dict[str, str] = {}
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
        return count

    async def mock_add_to_queue(queue_name: str, data: dict) -> int:
        if queue_name not in queues:
            queues[queue_name] = []
        queues[queue_name].append(json.dumps(data))
        return len(queues[queue_name])

    async def mock_keys(pattern: str):
        # Simple pattern matching for batch:*:current
        import fnmatch

        return [k for k in storage if fnmatch.fnmatch(k, pattern)]

    mock_client.get = mock_get
    mock_client.set = mock_set
    mock_client.delete = mock_delete
    mock_client.add_to_queue = mock_add_to_queue

    # Internal client for keys operation
    mock_internal = MagicMock()
    mock_internal.keys = mock_keys
    mock_client._client = mock_internal

    # Expose internal storage for assertions
    mock_client._test_storage = storage
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
    camera_id = "front_door"
    file_path = "/export/foscam/front_door/image_001.jpg"

    # Start at time 1000.0
    start_time = 1000.0

    with patch("backend.services.batch_aggregator.time.time", return_value=start_time):
        batch_id = await batch_aggregator.add_detection(camera_id, "det_001", file_path)

    # Verify batch was created
    assert batch_id is not None
    assert mock_redis_client._test_storage.get(f"batch:{camera_id}:current") == batch_id

    # Add activity at 70 seconds to reset idle timer (keeps batch alive via idle timeout)
    with patch("backend.services.batch_aggregator.time.time", return_value=start_time + 70):
        await batch_aggregator.add_detection(camera_id, "det_002", file_path)

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
    camera_id = "back_door"
    detection_id = "det_002"
    file_path = "/export/foscam/back_door/image_002.jpg"

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
    camera_id = "garage"
    file_path = "/export/foscam/garage/image.jpg"

    # Start at time 1000.0
    current_time = 1000.0

    with patch("backend.services.batch_aggregator.time.time", return_value=current_time):
        batch_id = await batch_aggregator.add_detection(camera_id, "det_001", file_path)

    # Add activity at 20 seconds (before 30s idle timeout)
    with patch("backend.services.batch_aggregator.time.time", return_value=current_time + 20):
        await batch_aggregator.add_detection(camera_id, "det_002", file_path)

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

    # Create batch for camera 1
    with patch("backend.services.batch_aggregator.time.time", return_value=current_time):
        batch_id_1 = await batch_aggregator.add_detection("camera1", "det_001", "/path/1.jpg")

    # Create batch for camera 2 at +20s
    with patch("backend.services.batch_aggregator.time.time", return_value=current_time + 20):
        batch_id_2 = await batch_aggregator.add_detection("camera2", "det_002", "/path/2.jpg")

    # Check at +35s - camera1 should timeout (35s idle), camera2 should NOT (15s idle)
    with patch("backend.services.batch_aggregator.time.time", return_value=current_time + 35):
        closed_batches = await batch_aggregator.check_batch_timeouts()

    assert batch_id_1 in closed_batches
    assert batch_id_2 not in closed_batches


@pytest.mark.asyncio
async def test_batch_window_takes_precedence_over_idle(batch_aggregator, mock_redis_client):
    """Test that window timeout fires even with recent activity.

    Uses mocked time to verify window timeout behavior.
    """
    camera_id = "front_door"
    file_path = "/export/foscam/front_door/image.jpg"
    current_time = 1000.0

    # Create batch
    with patch("backend.services.batch_aggregator.time.time", return_value=current_time):
        batch_id = await batch_aggregator.add_detection(camera_id, "det_001", file_path)

    # Add activity at 85 seconds (before 90s window, recent activity)
    with patch("backend.services.batch_aggregator.time.time", return_value=current_time + 85):
        await batch_aggregator.add_detection(camera_id, "det_002", file_path)

    # Check at 91 seconds - window exceeded even though activity was 6s ago
    with patch("backend.services.batch_aggregator.time.time", return_value=current_time + 91):
        closed_batches = await batch_aggregator.check_batch_timeouts()

    # Should be closed due to window timeout, not idle
    assert batch_id in closed_batches


@pytest.mark.asyncio
async def test_batch_close_creates_analysis_queue_item(batch_aggregator, mock_redis_client):
    """Test that closing a batch queues it for analysis with correct format.

    Verifies the analysis queue item structure.
    """
    camera_id = "front_door"
    file_path = "/export/foscam/front_door/image.jpg"
    current_time = 1000.0

    # Create batch with multiple detections
    with patch("backend.services.batch_aggregator.time.time", return_value=current_time):
        batch_id = await batch_aggregator.add_detection(camera_id, "det_001", file_path)
        await batch_aggregator.add_detection(camera_id, "det_002", file_path)
        await batch_aggregator.add_detection(camera_id, "det_003", file_path)

    # Force timeout
    with patch("backend.services.batch_aggregator.time.time", return_value=current_time + 91):
        await batch_aggregator.check_batch_timeouts()

    # Verify queue item
    assert "analysis_queue" in mock_redis_client._test_queues
    queue_items = mock_redis_client._test_queues["analysis_queue"]
    assert len(queue_items) == 1

    queue_item = json.loads(queue_items[0])
    assert queue_item["batch_id"] == batch_id
    assert queue_item["camera_id"] == camera_id
    assert set(queue_item["detection_ids"]) == {"det_001", "det_002", "det_003"}
    assert "timestamp" in queue_item


@pytest.mark.asyncio
async def test_empty_batch_not_queued(batch_aggregator, mock_redis_client):
    """Test that empty batches are not added to analysis queue.

    Creates edge case where batch exists but has no detections.
    """
    camera_id = "test_camera"
    current_time = 1000.0

    # Manually create an empty batch (edge case)
    batch_id = "empty_batch_123"
    with patch("backend.services.batch_aggregator.time.time", return_value=current_time):
        await mock_redis_client.set(f"batch:{camera_id}:current", batch_id)
        await mock_redis_client.set(f"batch:{batch_id}:camera_id", camera_id)
        await mock_redis_client.set(f"batch:{batch_id}:started_at", str(current_time))
        await mock_redis_client.set(f"batch:{batch_id}:last_activity", str(current_time))
        await mock_redis_client.set(f"batch:{batch_id}:detections", json.dumps([]))

    # Force timeout
    with patch("backend.services.batch_aggregator.time.time", return_value=current_time + 91):
        closed_batches = await batch_aggregator.check_batch_timeouts()

    # Batch should be closed but NOT queued
    assert batch_id in closed_batches
    assert (
        "analysis_queue" not in mock_redis_client._test_queues
        or len(mock_redis_client._test_queues.get("analysis_queue", [])) == 0
    )


@pytest.mark.asyncio
async def test_batch_close_cleans_up_redis_keys(batch_aggregator, mock_redis_client):
    """Test that closing a batch removes all associated Redis keys."""
    camera_id = "cleanup_test"
    file_path = "/export/foscam/cleanup_test/image.jpg"
    current_time = 1000.0

    with patch("backend.services.batch_aggregator.time.time", return_value=current_time):
        batch_id = await batch_aggregator.add_detection(camera_id, "det_001", file_path)

    # Verify keys exist
    storage = mock_redis_client._test_storage
    assert f"batch:{camera_id}:current" in storage
    assert f"batch:{batch_id}:camera_id" in storage
    assert f"batch:{batch_id}:detections" in storage
    assert f"batch:{batch_id}:started_at" in storage
    assert f"batch:{batch_id}:last_activity" in storage

    # Force timeout and close
    with patch("backend.services.batch_aggregator.time.time", return_value=current_time + 91):
        await batch_aggregator.check_batch_timeouts()

    # Verify all keys are removed
    assert f"batch:{camera_id}:current" not in storage
    assert f"batch:{batch_id}:camera_id" not in storage
    assert f"batch:{batch_id}:detections" not in storage
    assert f"batch:{batch_id}:started_at" not in storage
    assert f"batch:{batch_id}:last_activity" not in storage


@pytest.mark.asyncio
async def test_rapid_detections_same_batch(batch_aggregator, mock_redis_client):
    """Test that rapid detections all go to the same batch."""
    camera_id = "rapid_test"
    file_path = "/export/foscam/rapid_test/image.jpg"
    current_time = 1000.0

    batch_ids = []

    # Add 10 detections in rapid succession (all within 1 second)
    for i in range(10):
        with patch(
            "backend.services.batch_aggregator.time.time", return_value=current_time + i * 0.1
        ):
            batch_id = await batch_aggregator.add_detection(camera_id, f"det_{i:03d}", file_path)
            batch_ids.append(batch_id)

    # All detections should be in the same batch
    assert len(set(batch_ids)) == 1

    # Verify detection count
    storage = mock_redis_client._test_storage
    detections = json.loads(storage[f"batch:{batch_ids[0]}:detections"])
    assert len(detections) == 10


@pytest.mark.asyncio
async def test_timeout_check_handles_missing_metadata(batch_aggregator, mock_redis_client):
    """Test that timeout check handles batches with missing metadata gracefully."""
    camera_id = "malformed_test"
    current_time = 1000.0

    # Create batch key but without started_at (malformed)
    batch_id = "malformed_batch"
    await mock_redis_client.set(f"batch:{camera_id}:current", batch_id)
    await mock_redis_client.set(f"batch:{batch_id}:camera_id", camera_id)
    # Intentionally skip started_at

    with patch("backend.services.batch_aggregator.time.time", return_value=current_time + 100):
        closed_batches = await batch_aggregator.check_batch_timeouts()

    # Should skip malformed batch without crashing
    assert batch_id not in closed_batches


@pytest.mark.asyncio
async def test_batch_aggregator_exact_boundary_conditions(batch_aggregator, mock_redis_client):
    """Test exact boundary conditions for timeouts.

    Tests that exactly 90s window and exactly 30s idle are handled correctly.
    """
    camera_id = "boundary_test"
    file_path = "/export/foscam/boundary_test/image.jpg"
    current_time = 1000.0

    with patch("backend.services.batch_aggregator.time.time", return_value=current_time):
        batch_id = await batch_aggregator.add_detection(camera_id, "det_001", file_path)

    # Exactly at 90s - should NOT timeout (>= check means exactly 90 should trigger)
    with patch("backend.services.batch_aggregator.time.time", return_value=current_time + 90):
        closed_batches = await batch_aggregator.check_batch_timeouts()

    # At exactly the boundary, the >= comparison should trigger timeout
    assert batch_id in closed_batches


@pytest.mark.asyncio
async def test_concurrent_camera_batch_isolation(batch_aggregator, mock_redis_client):
    """Test that batches from different cameras are properly isolated."""
    current_time = 1000.0
    cameras = ["camera_a", "camera_b", "camera_c"]

    batch_ids = {}

    # Create batches for all cameras at the same time
    with patch("backend.services.batch_aggregator.time.time", return_value=current_time):
        for camera in cameras:
            batch_id = await batch_aggregator.add_detection(
                camera, "det_001", f"/path/{camera}/image.jpg"
            )
            batch_ids[camera] = batch_id

    # All batch IDs should be unique
    assert len(set(batch_ids.values())) == len(cameras)

    # Add more detections to camera_b only
    with patch("backend.services.batch_aggregator.time.time", return_value=current_time + 10):
        await batch_aggregator.add_detection("camera_b", "det_002", "/path/camera_b/image.jpg")

    # Timeout camera_a and camera_c (35s idle), but camera_b should remain (25s idle)
    with patch("backend.services.batch_aggregator.time.time", return_value=current_time + 35):
        closed_batches = await batch_aggregator.check_batch_timeouts()

    assert batch_ids["camera_a"] in closed_batches
    assert batch_ids["camera_b"] not in closed_batches
    assert batch_ids["camera_c"] in closed_batches
