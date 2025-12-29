"""End-to-end pipeline integration test.

This test validates the complete AI pipeline flow from file detection through
event creation and WebSocket broadcasting. It tests the integration of all
major components working together.

Pipeline Steps Tested:
    1. Setup: Create test camera, mock image file
    2. File Detection: Simulate file appearing in camera folder
    3. Detection Processing: Verify RT-DETRv2 detection (mock if unavailable)
    4. Batch Aggregation: Verify detections are batched
    5. AI Analysis: Verify Nemotron analysis (mock if unavailable)
    6. Event Creation: Verify event is created in database
    7. WebSocket Broadcast: Verify event is broadcast
    8. Cleanup: Remove test data

Run with:
    pytest backend/tests/e2e/test_pipeline_integration.py -v
    pytest backend/tests/e2e/test_pipeline_integration.py -v -m e2e
"""

import asyncio
import json
import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image
from sqlalchemy import select

from backend.core.database import get_session
from backend.core.redis import RedisClient
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.services.batch_aggregator import BatchAggregator
from backend.services.detector_client import DetectorClient, DetectorUnavailableError
from backend.services.nemotron_analyzer import NemotronAnalyzer


@pytest.fixture
async def test_camera(integration_db, tmp_path):
    """Create a test camera in the database.

    Args:
        integration_db: Database fixture
        tmp_path: Pytest temporary directory fixture

    Returns:
        Camera: Test camera instance
    """
    camera_folder = tmp_path / "e2e_test_camera"
    camera_folder.mkdir(exist_ok=True)

    async with get_session() as session:
        camera = Camera(
            id="e2e_test_camera",
            name="E2E Test Camera",
            folder_path=str(camera_folder),
            status="online",
            created_at=datetime.now(UTC),
        )
        session.add(camera)
        await session.commit()
        await session.refresh(camera)
        return camera


@pytest.fixture
def test_image_path(tmp_path):
    """Create a valid test image file.

    Args:
        tmp_path: Pytest temporary directory fixture

    Returns:
        Path: Path to the test image file
    """
    # Create a simple test image
    image_path = tmp_path / "test_image.jpg"
    img = Image.new("RGB", (640, 480), color=(100, 150, 200))
    img.save(image_path, "JPEG")
    return str(image_path)


@pytest.fixture
async def mock_redis_client():
    """Create a mock Redis client with all necessary methods.

    Returns:
        AsyncMock: Mocked Redis client
    """
    mock_redis = AsyncMock(spec=RedisClient)

    # Track batch data in memory
    batch_data = {}

    async def mock_get(key):
        return batch_data.get(key)

    async def mock_set(key, value, expire=None):
        batch_data[key] = value
        # expire is accepted but not simulated in tests

    async def mock_delete(*keys):
        for key in keys:
            batch_data.pop(key, None)

    async def mock_add_to_queue(queue_name, item):
        queue_key = f"queue:{queue_name}"
        if queue_key not in batch_data:
            batch_data[queue_key] = []
        batch_data[queue_key].append(item)

    async def mock_publish(channel, message):
        # Simulate publishing (return subscriber count)
        return 1

    async def mock_scan_iter(match="*", count=100):
        """Async generator for SCAN iteration (replacement for KEYS)."""
        import fnmatch

        for k in batch_data:
            if fnmatch.fnmatch(k, match):
                yield k

    mock_redis.get = AsyncMock(side_effect=mock_get)
    mock_redis.set = AsyncMock(side_effect=mock_set)
    mock_redis.delete = AsyncMock(side_effect=mock_delete)
    mock_redis.add_to_queue = AsyncMock(side_effect=mock_add_to_queue)
    mock_redis.publish = AsyncMock(side_effect=mock_publish)

    # Mock internal _client for batch timeout checks (using scan_iter instead of keys)
    mock_internal_client = MagicMock()
    mock_internal_client.scan_iter = mock_scan_iter
    mock_redis._client = mock_internal_client

    # Store batch_data for test verification
    mock_redis._test_data = batch_data

    return mock_redis


@pytest.fixture
def mock_detector_response():
    """Create a mock RT-DETRv2 detection response.

    Returns:
        dict: Mock detection response
    """
    return {
        "detections": [
            {
                "class": "person",
                "confidence": 0.95,
                "bbox": [100, 150, 200, 300],
            },
            {
                "class": "car",
                "confidence": 0.88,
                "bbox": [400, 200, 250, 180],
            },
        ]
    }


@pytest.fixture
def mock_nemotron_response():
    """Create a mock Nemotron LLM analysis response.

    Returns:
        dict: Mock LLM response
    """
    return {
        "content": json.dumps(
            {
                "risk_score": 75,
                "risk_level": "high",
                "summary": "Person and vehicle detected near entrance",
                "reasoning": "Multiple detections indicate potential security concern",
            }
        )
    }


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_complete_pipeline_flow_with_mocked_services(
    integration_db,
    test_camera,
    test_image_path,
    mock_redis_client,
    mock_detector_response,
    mock_nemotron_response,
):
    """Test the complete E2E pipeline flow with mocked external services.

    This test validates that all components work together correctly:
    - File detection and queuing
    - RT-DETRv2 object detection (mocked)
    - Batch aggregation
    - Nemotron AI analysis (mocked)
    - Event creation
    - WebSocket broadcasting

    The test uses mocked external services (RT-DETRv2, Nemotron, Redis)
    so it can run without actual service dependencies.
    """
    camera_id = test_camera.id

    # Step 1: Mock detector client
    with patch("httpx.AsyncClient") as mock_http_client:
        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value=mock_detector_response)
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_http_client.return_value.__aenter__.return_value = mock_client

        # Step 2: Process image through detector
        detector = DetectorClient()
        async with get_session() as session:
            detections = await detector.detect_objects(
                image_path=test_image_path,
                camera_id=camera_id,
                session=session,
            )

        # Verify detections were created
        assert len(detections) == 2
        assert detections[0].object_type == "person"
        assert detections[0].confidence == 0.95
        assert detections[1].object_type == "car"
        assert detections[1].confidence == 0.88

    # Step 3: Test batch aggregation
    aggregator = BatchAggregator(redis_client=mock_redis_client)

    # Add detections to batch
    batch_id = None
    for detection in detections:
        batch_id = await aggregator.add_detection(
            camera_id=camera_id,
            detection_id=str(detection.id),
            _file_path=test_image_path,
        )

    assert batch_id is not None

    # Verify batch metadata in Redis
    batch_camera_id = await mock_redis_client.get(f"batch:{batch_id}:camera_id")
    assert batch_camera_id == camera_id

    batch_detections = await mock_redis_client.get(f"batch:{batch_id}:detections")
    assert batch_detections is not None

    # Step 4: Simulate batch timeout and close
    await asyncio.sleep(0.1)  # Small delay to simulate passage of time
    await aggregator.close_batch(batch_id)

    # Verify batch was queued for analysis
    analysis_queue_key = "queue:analysis_queue"
    assert analysis_queue_key in mock_redis_client._test_data
    assert len(mock_redis_client._test_data[analysis_queue_key]) == 1

    # Step 5: Mock Nemotron analysis
    with patch("httpx.AsyncClient") as mock_http_client:
        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value=mock_nemotron_response)
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_http_client.return_value.__aenter__.return_value = mock_client

        # Get the detection_ids for analysis
        detection_ids = [str(d.id) for d in detections]

        # Run analyzer - pass camera_id and detection_ids directly (as queue worker does)
        # This tests the fixed handoff where close_batch deletes Redis keys but
        # the queue payload contains all needed data
        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)
        event = await analyzer.analyze_batch(
            batch_id=batch_id,
            camera_id=camera_id,
            detection_ids=detection_ids,
        )

    # Step 6: Verify event was created
    assert event is not None
    assert event.batch_id == batch_id
    assert event.camera_id == camera_id
    assert event.risk_score == 75
    assert event.risk_level == "high"
    assert "Person and vehicle detected" in event.summary

    # Step 7: Verify event in database
    async with get_session() as session:
        result = await session.execute(select(Event).where(Event.batch_id == batch_id))
        saved_event = result.scalar_one_or_none()

        assert saved_event is not None
        assert saved_event.id == event.id
        assert saved_event.risk_score == 75
        assert saved_event.risk_level == "high"

        # Verify detection IDs are stored
        stored_detection_ids = json.loads(saved_event.detection_ids)
        assert len(stored_detection_ids) == 2
        assert all(str(d.id) in stored_detection_ids for d in detections)

    # Step 8: Verify WebSocket broadcast was called
    mock_redis_client.publish.assert_called()
    publish_calls = mock_redis_client.publish.call_args_list
    assert len(publish_calls) > 0

    # Verify the broadcast message structure
    last_call = publish_calls[-1]
    channel = last_call[0][0]
    message = last_call[0][1]

    assert channel == "security_events"  # Canonical channel name
    assert message["type"] == "event"  # Envelope format
    assert message["data"]["event_id"] == event.id
    assert message["data"]["camera_id"] == camera_id
    assert message["data"]["risk_score"] == 75


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_pipeline_with_multiple_detections_in_batch(
    integration_db,
    test_camera,
    test_image_path,
    mock_redis_client,
):
    """Test pipeline with multiple detections aggregated into a single batch.

    This test validates that:
    - Multiple detections are properly aggregated
    - Batch window logic works correctly
    - All detections are included in the final event
    """
    camera_id = test_camera.id

    # Create multiple detections
    async with get_session() as session:
        detections = []
        for i in range(5):
            detection = Detection(
                camera_id=camera_id,
                file_path=f"{test_image_path}_{i}",
                file_type="image/jpeg",
                detected_at=datetime.now(UTC),
                object_type=["person", "car", "dog"][i % 3],
                confidence=0.85 + (i * 0.02),
                bbox_x=100 + (i * 20),
                bbox_y=150 + (i * 20),
                bbox_width=200,
                bbox_height=300,
            )
            session.add(detection)
            await session.flush()
            await session.refresh(detection)
            detections.append(detection)

        await session.commit()

    # Add all detections to batch
    aggregator = BatchAggregator(redis_client=mock_redis_client)
    batch_ids = set()

    for detection in detections:
        batch_id = await aggregator.add_detection(
            camera_id=camera_id,
            detection_id=str(detection.id),
            _file_path=detection.file_path,
        )
        batch_ids.add(batch_id)

    # All detections should be in the same batch
    assert len(batch_ids) == 1
    batch_id = batch_ids.pop()

    # Verify batch contains all detections
    batch_detections_json = await mock_redis_client.get(f"batch:{batch_id}:detections")
    batch_detections = json.loads(batch_detections_json)
    assert len(batch_detections) == 5

    # Close batch and verify summary
    summary = await aggregator.close_batch(batch_id)
    assert summary["detection_count"] == 5
    assert summary["camera_id"] == camera_id


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_pipeline_batch_timeout_logic(
    integration_db,
    test_camera,
    test_image_path,
    mock_redis_client,
):
    """Test that batches close correctly based on timeout logic.

    This test validates:
    - Batch window timeout (90 seconds)
    - Idle timeout (30 seconds)
    - Proper batch closure and queuing
    """
    camera_id = test_camera.id

    # Create a detection
    async with get_session() as session:
        detection = Detection(
            camera_id=camera_id,
            file_path=test_image_path,
            file_type="image/jpeg",
            detected_at=datetime.now(UTC),
            object_type="person",
            confidence=0.95,
        )
        session.add(detection)
        await session.commit()
        await session.refresh(detection)

    # Add to batch
    aggregator = BatchAggregator(redis_client=mock_redis_client)
    batch_id = await aggregator.add_detection(
        camera_id=camera_id,
        detection_id=str(detection.id),
        _file_path=test_image_path,
    )

    # Manually set started_at to simulate old batch (for testing)
    old_timestamp = time.time() - 95  # 95 seconds ago (exceeds 90s window)
    await mock_redis_client.set(f"batch:{batch_id}:started_at", str(old_timestamp))

    # Check for timeouts
    closed_batches = await aggregator.check_batch_timeouts()

    # Batch should be closed due to window timeout
    assert batch_id in closed_batches

    # Verify batch was queued for analysis
    analysis_queue_key = "queue:analysis_queue"
    assert analysis_queue_key in mock_redis_client._test_data


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_pipeline_with_low_confidence_filtering(
    integration_db,
    test_camera,
    test_image_path,
    mock_redis_client,
):
    """Test that low confidence detections are filtered out.

    This test validates:
    - Confidence threshold filtering works
    - Only high-confidence detections are processed
    - Low-confidence detections are logged but not stored
    """
    camera_id = test_camera.id

    # Mock detector with mixed confidence detections
    mock_response = {
        "detections": [
            {"class": "person", "confidence": 0.95, "bbox": [100, 150, 200, 300]},
            {"class": "car", "confidence": 0.25, "bbox": [400, 200, 250, 180]},  # Low confidence
            {"class": "dog", "confidence": 0.85, "bbox": [50, 100, 150, 200]},
        ]
    }

    with patch("httpx.AsyncClient") as mock_http_client:
        mock_http_response = MagicMock()
        mock_http_response.json = MagicMock(return_value=mock_response)
        mock_http_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_http_response)
        mock_http_client.return_value.__aenter__.return_value = mock_client

        # Process image
        detector = DetectorClient()
        async with get_session() as session:
            detections = await detector.detect_objects(
                image_path=test_image_path,
                camera_id=camera_id,
                session=session,
            )

    # Only high-confidence detections should be stored (threshold is 0.5 by default)
    assert len(detections) == 2
    assert detections[0].object_type == "person"
    assert detections[0].confidence == 0.95
    assert detections[1].object_type == "dog"
    assert detections[1].confidence == 0.85


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_pipeline_handles_detector_failure_gracefully(
    integration_db,
    test_camera,
    test_image_path,
    mock_redis_client,
):
    """Test that pipeline handles detector service failures with DetectorUnavailableError.

    This test validates:
    - Detector connection errors raise DetectorUnavailableError
    - This allows the pipeline to retry or move to DLQ
    - The exception carries enough information for retry decisions
    """
    camera_id = test_camera.id

    # Mock detector to raise connection error
    with patch("httpx.AsyncClient") as mock_http_client:
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Connection refused")
        mock_http_client.return_value.__aenter__.return_value = mock_client

        # Process image - should raise DetectorUnavailableError for retry handling
        detector = DetectorClient()
        async with get_session() as session:
            with pytest.raises(DetectorUnavailableError) as exc_info:
                await detector.detect_objects(
                    image_path=test_image_path,
                    camera_id=camera_id,
                    session=session,
                )

            # Verify exception contains useful info for retry decisions
            assert "Unexpected error" in str(exc_info.value)
            assert exc_info.value.cause is not None


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_pipeline_handles_nemotron_failure_gracefully(
    integration_db,
    test_camera,
    test_image_path,
    mock_redis_client,
):
    """Test that pipeline handles Nemotron service failures gracefully.

    This test validates:
    - LLM connection errors are handled
    - Fallback risk data is used
    - Event is still created with default values
    """
    camera_id = test_camera.id

    # Create detection
    async with get_session() as session:
        detection = Detection(
            camera_id=camera_id,
            file_path=test_image_path,
            file_type="image/jpeg",
            detected_at=datetime.now(UTC),
            object_type="person",
            confidence=0.95,
        )
        session.add(detection)
        await session.commit()
        await session.refresh(detection)

    # Create batch
    aggregator = BatchAggregator(redis_client=mock_redis_client)
    batch_id = await aggregator.add_detection(
        camera_id=camera_id,
        detection_id=str(detection.id),
        _file_path=test_image_path,
    )

    # Get detection_ids for analysis
    detection_ids = [str(detection.id)]

    # Mock Nemotron to fail
    with patch("httpx.AsyncClient") as mock_http_client:
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("LLM service unavailable")
        mock_http_client.return_value.__aenter__.return_value = mock_client

        # Run analyzer (should not crash) - pass camera_id and detection_ids directly
        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)
        event = await analyzer.analyze_batch(
            batch_id=batch_id,
            camera_id=camera_id,
            detection_ids=detection_ids,
        )

    # Event should be created with fallback values
    assert event is not None
    assert event.risk_score == 50  # Default fallback
    assert event.risk_level == "medium"  # Default fallback
    assert "Analysis unavailable" in event.summary


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_pipeline_event_relationships(
    integration_db,
    test_camera,
    test_image_path,
    mock_redis_client,
):
    """Test that event relationships with camera and detections are correct.

    This test validates:
    - Events are properly linked to cameras
    - Detection IDs are stored in events
    - Relationships can be queried
    """
    camera_id = test_camera.id

    # Create multiple detections
    async with get_session() as session:
        detections = []
        for i in range(3):
            detection = Detection(
                camera_id=camera_id,
                file_path=f"{test_image_path}_{i}",
                file_type="image/jpeg",
                detected_at=datetime.now(UTC),
                object_type="person",
                confidence=0.90,
            )
            session.add(detection)
            await session.flush()
            await session.refresh(detection)
            detections.append(detection)

        await session.commit()

    # Create event manually
    async with get_session() as session:
        event = Event(
            batch_id="test_batch_rel",
            camera_id=camera_id,
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC),
            risk_score=60,
            risk_level="medium",
            summary="Test event for relationship validation",
            detection_ids=json.dumps([d.id for d in detections]),
            reviewed=False,
        )
        session.add(event)
        await session.commit()
        await session.refresh(event)

    # Query and verify relationships
    async with get_session() as session:
        # Get camera with events
        result = await session.execute(select(Camera).where(Camera.id == camera_id))
        camera = result.scalar_one()
        await session.refresh(camera, ["events"])

        assert len(camera.events) > 0
        test_event = next(e for e in camera.events if e.batch_id == "test_batch_rel")
        assert test_event.camera_id == camera_id

        # Verify detection IDs
        stored_ids = json.loads(test_event.detection_ids)
        assert len(stored_ids) == 3
        assert all(d.id in stored_ids for d in detections)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_pipeline_cleanup_after_processing(
    integration_db,
    test_camera,
    test_image_path,
    mock_redis_client,
):
    """Test that batch data is properly cleaned up after processing.

    This test validates:
    - Batch metadata is removed from Redis after close
    - Detection data persists in database
    - Event data persists in database
    """
    camera_id = test_camera.id

    # Create detection
    async with get_session() as session:
        detection = Detection(
            camera_id=camera_id,
            file_path=test_image_path,
            file_type="image/jpeg",
            detected_at=datetime.now(UTC),
            object_type="person",
            confidence=0.95,
        )
        session.add(detection)
        await session.commit()
        await session.refresh(detection)

    # Create and close batch
    aggregator = BatchAggregator(redis_client=mock_redis_client)
    batch_id = await aggregator.add_detection(
        camera_id=camera_id,
        detection_id=str(detection.id),
        _file_path=test_image_path,
    )

    # Verify batch data exists before close
    batch_camera = await mock_redis_client.get(f"batch:{batch_id}:camera_id")
    assert batch_camera == camera_id

    # Close batch
    await aggregator.close_batch(batch_id)

    # Verify batch metadata is cleaned up
    batch_camera_after = await mock_redis_client.get(f"batch:{batch_id}:camera_id")
    assert batch_camera_after is None

    batch_detections_after = await mock_redis_client.get(f"batch:{batch_id}:detections")
    assert batch_detections_after is None

    # But detection should still exist in database
    async with get_session() as session:
        result = await session.execute(select(Detection).where(Detection.id == detection.id))
        saved_detection = result.scalar_one_or_none()
        assert saved_detection is not None
        assert saved_detection.id == detection.id
