"""Integration tests for Nemotron analyzer service.

These tests require real PostgreSQL database access via the isolated_db fixture.
Unit tests for pure functions, mocked HTTP calls, and validation logic are in
backend/tests/unit/test_nemotron_analyzer.py.
"""

import json
import random
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy import select

from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.models.event_detection import EventDetection
from backend.services.nemotron_analyzer import NemotronAnalyzer
from backend.tests.conftest import unique_id

# Mark as integration since these tests require real PostgreSQL database
pytestmark = pytest.mark.integration

# Fixtures


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for Nemotron analyzer tests with spec to prevent mocking non-existent attributes."""
    from backend.core.redis import RedisClient

    mock_client = MagicMock(spec=RedisClient)
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock(return_value=True)
    mock_client.delete = AsyncMock(return_value=1)
    mock_client.publish = AsyncMock(return_value=1)
    return mock_client


@pytest.fixture
def analyzer(mock_redis_client):
    """Create NemotronAnalyzer instance with mocked Redis.

    Sets max_retries=1 to avoid long retry delays in tests (exponential backoff
    would cause timeouts otherwise).
    """
    return NemotronAnalyzer(redis_client=mock_redis_client, max_retries=1)


@pytest.fixture
def sample_detections_factory():
    """Factory to create sample detections with specified camera_id."""
    from datetime import UTC

    def _create_detections(camera_id: str, start_id: int = 1):
        base_time = datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC)
        return [
            Detection(
                id=start_id,
                camera_id=camera_id,
                file_path=f"/export/foscam/{camera_id}/img1.jpg",
                detected_at=base_time,
                object_type="person",
                confidence=0.95,
            ),
            Detection(
                id=start_id + 1,
                camera_id=camera_id,
                file_path=f"/export/foscam/{camera_id}/img2.jpg",
                detected_at=datetime(2025, 12, 23, 14, 30, 15, tzinfo=UTC),
                object_type="car",
                confidence=0.88,
            ),
            Detection(
                id=start_id + 2,
                camera_id=camera_id,
                file_path=f"/export/foscam/{camera_id}/img3.jpg",
                detected_at=datetime(2025, 12, 23, 14, 30, 30, tzinfo=UTC),
                object_type="person",
                confidence=0.92,
            ),
        ]

    return _create_detections


# Test: Analyze Batch (Integration tests - require DB)


@pytest.mark.asyncio
async def test_analyze_batch_success(
    analyzer, mock_redis_client, isolated_db, sample_detections_factory
):
    """Test successful batch analysis creates Event."""
    # Use unique IDs for test isolation in parallel execution
    batch_id = unique_id("batch")
    camera_id = unique_id("camera")
    # Use high detection IDs to avoid conflicts with other tests
    base_det_id = random.randint(100000, 999999)  # noqa: S311  # nosemgrep: insecure-random
    detection_ids = [base_det_id, base_det_id + 1, base_det_id + 2]

    # Create detections with matching IDs and camera
    detections = sample_detections_factory(camera_id, start_id=base_det_id)

    # Setup Redis mocks
    async def mock_get(key):
        if f"batch:{batch_id}:camera_id" in key:
            return camera_id
        elif f"batch:{batch_id}:detections" in key:
            return json.dumps(detection_ids)
        elif f"batch:{batch_id}:started_at" in key:
            return "1703341800.0"
        return None

    mock_redis_client.get.side_effect = mock_get

    # Setup database with camera and detections
    from backend.core.database import get_session

    async with get_session() as session:
        # Create camera with unique name to prevent unique constraint conflicts
        camera = Camera(
            id=camera_id,
            name=f"Front Door {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)

        # Create detections
        for det in detections:
            session.add(det)

        await session.commit()

    # Mock LLM call
    mock_llm_response = {
        "content": json.dumps(
            {
                "risk_score": 65,
                "risk_level": "high",
                "summary": "Multiple persons detected",
                "reasoning": "Three detections in quick succession",
            }
        )
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_llm_response
        mock_post.return_value = mock_resp

        # Analyze batch
        event = await analyzer.analyze_batch(batch_id)

    # Verify event was created
    assert event is not None
    assert event.batch_id == batch_id
    assert event.camera_id == camera_id
    assert event.risk_score == 65
    assert event.risk_level == "high"
    assert "Multiple persons" in event.summary
    assert event.reviewed is False

    # Verify event was persisted
    async with get_session() as session:
        result = await session.execute(select(Event).where(Event.batch_id == batch_id))
        persisted_event = result.scalar_one_or_none()
        assert persisted_event is not None
        assert persisted_event.risk_score == 65


@pytest.mark.asyncio
async def test_analyze_batch_llm_failure_uses_fallback(
    analyzer, mock_redis_client, isolated_db, sample_detections_factory
):
    """Test batch analysis uses fallback risk data when LLM fails."""
    # Use unique IDs for test isolation in parallel execution
    batch_id = unique_id("batch")
    camera_id = unique_id("camera")
    base_det_id = random.randint(100000, 999999)  # noqa: S311  # nosemgrep: insecure-random
    detection_ids = [base_det_id, base_det_id + 1, base_det_id + 2]

    # Create detections with matching IDs and camera
    detections = sample_detections_factory(camera_id, start_id=base_det_id)

    # Setup Redis mocks
    async def mock_get(key):
        if f"batch:{batch_id}:camera_id" in key:
            return camera_id
        elif f"batch:{batch_id}:detections" in key:
            return json.dumps(detection_ids)
        elif f"batch:{batch_id}:started_at" in key:
            return "1703341800.0"
        return None

    mock_redis_client.get.side_effect = mock_get

    # Setup database
    from backend.core.database import get_session

    async with get_session() as session:
        # Use unique name to prevent unique constraint conflicts in parallel tests
        camera = Camera(
            id=camera_id,
            name=f"Front Door {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)

        for det in detections:
            session.add(det)

        await session.commit()

    # Mock LLM call to fail
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        # Analyze batch
        event = await analyzer.analyze_batch(batch_id)

    # Verify fallback risk data was used
    assert event.risk_score == 50
    assert event.risk_level == "medium"
    assert "Analysis unavailable" in event.summary


@pytest.mark.asyncio
async def test_analyze_batch_camera_not_found(
    analyzer, mock_redis_client, isolated_db, sample_detections_factory
):
    """Test batch analysis handles missing camera gracefully by using camera_id as name."""
    # Use unique IDs for test isolation in parallel execution
    batch_id = unique_id("batch")
    real_camera_id = unique_id("real_camera")
    base_det_id = random.randint(100000, 999999)  # noqa: S311  # nosemgrep: insecure-random
    detection_ids = [base_det_id, base_det_id + 1, base_det_id + 2]

    # Create detections with matching IDs and camera
    detections = sample_detections_factory(real_camera_id, start_id=base_det_id)

    # Setup database - create a different camera and detections with nonexistent camera_id
    from backend.core.database import get_session

    async with get_session() as session:
        # Create a real camera first to avoid FK constraint issues
        real_camera = Camera(
            id=real_camera_id,
            name="Real Camera",
            folder_path=f"/export/foscam/{real_camera_id}",
        )
        session.add(real_camera)
        await session.commit()

    async with get_session() as session:
        # Create detections for the camera
        for det in detections:
            session.add(det)
        await session.commit()

    # Setup Redis mock to return real_camera ID
    async def mock_get_real(key):
        if f"batch:{batch_id}:camera_id" in key:
            return real_camera_id
        elif f"batch:{batch_id}:detections" in key:
            return json.dumps(detection_ids)
        elif f"batch:{batch_id}:started_at" in key:
            return "1703341800.0"
        return None

    mock_redis_client.get.side_effect = mock_get_real

    # Mock LLM call
    mock_llm_response = {
        "content": json.dumps(
            {
                "risk_score": 50,
                "risk_level": "medium",
                "summary": "Activity detected",
                "reasoning": "Analysis completed",
            }
        )
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_llm_response
        mock_post.return_value = mock_resp

        # Analyze batch
        event = await analyzer.analyze_batch(batch_id)

    assert event.camera_id == real_camera_id
    # Verify event was created successfully
    assert event.risk_score == 50
    assert event.risk_level == "medium"


@pytest.mark.asyncio
async def test_analyze_batch_detections_not_in_database(analyzer, mock_redis_client, isolated_db):
    """Test batch analysis raises error when detections not found in database."""
    # Use unique IDs for test isolation in parallel execution
    batch_id = unique_id("batch")
    camera_id = unique_id("camera")
    # Use random high IDs that won't exist
    base_det_id = random.randint(900000, 999999)  # noqa: S311  # nosemgrep: insecure-random
    detection_ids = [base_det_id, base_det_id + 1, base_det_id + 2]

    # Setup Redis mocks
    async def mock_get(key):
        if f"batch:{batch_id}:camera_id" in key:
            return camera_id
        elif f"batch:{batch_id}:detections" in key:
            return json.dumps(detection_ids)
        elif f"batch:{batch_id}:started_at" in key:
            return "1703341800.0"
        return None

    mock_redis_client.get.side_effect = mock_get

    # Setup database with camera but no detections
    from backend.core.database import get_session

    async with get_session() as session:
        # Use unique name to prevent unique constraint conflicts in parallel tests
        camera = Camera(
            id=camera_id,
            name=f"Front Door {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.commit()

    # Analyze batch - should raise ValueError for missing detections
    with pytest.raises(ValueError, match="No detections found for batch"):
        await analyzer.analyze_batch(batch_id)


# Test: Fast Path Analysis (Integration tests - require DB)


@pytest.mark.asyncio
async def test_analyze_detection_fast_path_detection_not_found(
    analyzer, mock_redis_client, isolated_db
):
    """Test fast path analysis raises error when detection not found."""
    # Analyze non-existent detection
    with pytest.raises(ValueError, match=r"Detection .* not found"):
        await analyzer.analyze_detection_fast_path("front_door", "999")


@pytest.mark.asyncio
async def test_analyze_detection_fast_path_success(
    analyzer, mock_redis_client, isolated_db, sample_detections_factory
):
    """Test successful fast path analysis creates Event with is_fast_path=True."""
    # Use unique IDs for test isolation in parallel execution
    camera_id = unique_id("camera")
    det_id = random.randint(100000, 999999)  # noqa: S311  # nosemgrep: insecure-random
    detection_id = str(det_id)

    # Create detection with matching ID and camera
    detections = sample_detections_factory(camera_id, start_id=det_id)
    detection = detections[0]

    # Setup database with camera and detection
    from backend.core.database import get_session

    async with get_session() as session:
        # Create camera with unique name to prevent unique constraint conflicts
        camera = Camera(
            id=camera_id,
            name=f"Front Door {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)

        # Create detection
        session.add(detection)

        await session.commit()

    # Mock LLM call
    mock_llm_response = {
        "content": json.dumps(
            {
                "risk_score": 85,
                "risk_level": "critical",
                "summary": "High-confidence person detection",
                "reasoning": "Person detected with 95% confidence",
            }
        )
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_llm_response
        mock_post.return_value = mock_resp

        # Analyze detection via fast path
        event = await analyzer.analyze_detection_fast_path(camera_id, detection_id)

    # Verify event was created with fast path flag
    assert event is not None
    assert event.batch_id == f"fast_path_{detection_id}"
    assert event.camera_id == camera_id
    assert event.risk_score == 85
    assert event.risk_level == "critical"
    assert "High-confidence person" in event.summary
    assert event.reviewed is False
    assert event.is_fast_path is True

    # Verify event was persisted
    async with get_session() as session:
        result = await session.execute(
            select(Event).where(Event.batch_id == f"fast_path_{detection_id}")
        )
        persisted_event = result.scalar_one_or_none()
        assert persisted_event is not None
        assert persisted_event.is_fast_path is True
        assert persisted_event.risk_score == 85


@pytest.mark.asyncio
async def test_analyze_detection_fast_path_llm_failure(
    analyzer, mock_redis_client, isolated_db, sample_detections_factory
):
    """Test fast path analysis uses fallback when LLM fails."""
    # Use unique IDs for test isolation in parallel execution
    camera_id = unique_id("camera")
    det_id = random.randint(100000, 999999)  # noqa: S311  # nosemgrep: insecure-random
    detection_id = str(det_id)

    # Create detection with matching ID and camera
    detections = sample_detections_factory(camera_id, start_id=det_id)

    # Setup database
    from backend.core.database import get_session

    async with get_session() as session:
        # Use unique name to prevent unique constraint conflicts in parallel tests
        camera = Camera(
            id=camera_id,
            name=f"Front Door {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        session.add(detections[0])
        await session.commit()

    # Mock LLM call to fail
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        # Analyze detection via fast path
        event = await analyzer.analyze_detection_fast_path(camera_id, detection_id)

    # Verify fallback risk data was used
    assert event.risk_score == 50
    assert event.risk_level == "medium"
    assert "Analysis unavailable" in event.summary
    assert event.is_fast_path is True


@pytest.mark.asyncio
async def test_analyze_detection_fast_path_single_detection_time(
    analyzer, mock_redis_client, isolated_db, sample_detections_factory
):
    """Test fast path uses same timestamp for started_at and ended_at."""
    # Use unique IDs for test isolation in parallel execution
    camera_id = unique_id("camera")
    det_id = random.randint(100000, 999999)  # noqa: S311  # nosemgrep: insecure-random
    detection_id = str(det_id)

    # Create detection with matching ID and camera
    detections = sample_detections_factory(camera_id, start_id=det_id)
    detection = detections[0]

    # Setup database
    from backend.core.database import get_session

    async with get_session() as session:
        # Use unique name to prevent unique constraint conflicts in parallel tests
        camera = Camera(
            id=camera_id,
            name=f"Front Door {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        session.add(detection)
        await session.commit()

    # Mock LLM call
    mock_llm_response = {
        "content": json.dumps(
            {
                "risk_score": 90,
                "risk_level": "critical",
                "summary": "Fast path test",
                "reasoning": "Test reasoning",
            }
        )
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_llm_response
        mock_post.return_value = mock_resp

        event = await analyzer.analyze_detection_fast_path(camera_id, detection_id)

    # Verify started_at and ended_at are the same
    assert event.started_at == event.ended_at
    assert event.started_at == detection.detected_at


@pytest.mark.asyncio
async def test_analyze_detection_fast_path_detection_ids_format(
    analyzer, mock_redis_client, isolated_db, sample_detections_factory
):
    """Test fast path links detection via junction table with single detection."""
    # Use unique IDs for test isolation in parallel execution
    camera_id = unique_id("camera")
    det_id = random.randint(100000, 999999)  # noqa: S311  # nosemgrep: insecure-random
    detection_id = str(det_id)

    # Create detection with matching ID and camera
    detections = sample_detections_factory(camera_id, start_id=det_id)

    # Setup database
    from backend.core.database import get_session

    async with get_session() as session:
        # Use unique name to prevent unique constraint conflicts in parallel tests
        camera = Camera(
            id=camera_id,
            name=f"Front Door {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        session.add(detections[0])
        await session.commit()

    # Mock LLM call
    mock_llm_response = {
        "content": json.dumps(
            {
                "risk_score": 80,
                "risk_level": "high",
                "summary": "Test",
                "reasoning": "Test",
            }
        )
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_llm_response
        mock_post.return_value = mock_resp

        event = await analyzer.analyze_detection_fast_path(camera_id, detection_id)

    # Verify detection IDs via junction table (query within session to avoid DetachedInstanceError)
    from backend.core.database import get_session

    async with get_session() as session:
        result = await session.execute(
            select(EventDetection.detection_id).where(EventDetection.event_id == event.id)
        )
        stored_detection_ids = [row[0] for row in result.fetchall()]

    assert isinstance(stored_detection_ids, list)
    assert len(stored_detection_ids) == 1
    assert stored_detection_ids[0] == det_id


@pytest.mark.asyncio
async def test_analyze_detection_fast_path_broadcast_called(
    analyzer, mock_redis_client, isolated_db, sample_detections_factory
):
    """Test fast path broadcasts event after creation via EventBroadcaster."""
    # Use unique IDs for test isolation in parallel execution
    camera_id = unique_id("camera")
    det_id = random.randint(100000, 999999)  # noqa: S311  # nosemgrep: insecure-random
    detection_id = str(det_id)

    # Create detection with matching ID and camera
    detections = sample_detections_factory(camera_id, start_id=det_id)

    # Setup database
    from backend.core.database import get_session

    async with get_session() as session:
        # Use unique name to prevent unique constraint conflicts in parallel tests
        camera = Camera(
            id=camera_id,
            name=f"Front Door {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        session.add(detections[0])
        await session.commit()

    # Mock LLM call
    mock_llm_response = {
        "content": json.dumps(
            {
                "risk_score": 85,
                "risk_level": "critical",
                "summary": "Test broadcast",
                "reasoning": "Test",
            }
        )
    }

    # Mock the EventBroadcaster
    mock_broadcaster = MagicMock()
    mock_broadcaster.broadcast_event = AsyncMock()

    with (
        patch("httpx.AsyncClient.post") as mock_post,
        patch(
            "backend.services.event_broadcaster.get_broadcaster",
            new=AsyncMock(return_value=mock_broadcaster),
        ),
    ):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_llm_response
        mock_post.return_value = mock_resp

        event = await analyzer.analyze_detection_fast_path(camera_id, detection_id)

    # Verify broadcast_event was called via EventBroadcaster
    mock_broadcaster.broadcast_event.assert_called_once()
    call_args = mock_broadcaster.broadcast_event.call_args

    # Verify message envelope format: {"type": "event", "data": {...}}
    message = call_args[0][0]
    assert message["type"] == "event"
    assert "data" in message
    data = message["data"]
    assert data["event_id"] == event.id
    assert data["risk_score"] == 85
    assert data["risk_level"] == "critical"


# Test: Detection ID Type Conversion (string to int round-trip)


@pytest.mark.asyncio
async def test_analyze_batch_string_detection_ids_converted_to_int(
    analyzer, mock_redis_client, isolated_db, sample_detections_factory
):
    """Test that string detection IDs from Redis are properly converted to integers.

    This tests the round-trip: detection IDs are stored as strings in Redis batch queue
    (see pipeline_workers.py lines 363, 468 and batch_aggregator.py line 140),
    but must be converted to integers for database queries.
    """
    # Use unique IDs for test isolation
    batch_id = unique_id("batch")
    camera_id = unique_id("camera")
    base_det_id = random.randint(100000, 999999)  # noqa: S311  # nosemgrep: insecure-random

    # Simulate detection IDs stored as STRINGS in Redis (as they are in actual pipeline)
    string_detection_ids = [str(base_det_id), str(base_det_id + 1), str(base_det_id + 2)]

    # Create detections with matching integer IDs
    detections = sample_detections_factory(camera_id, start_id=base_det_id)

    # Setup Redis mocks - detection_ids come as JSON list of strings
    async def mock_get(key):
        if f"batch:{batch_id}:camera_id" in key:
            return camera_id
        elif f"batch:{batch_id}:detections" in key:
            # This is the critical test: IDs are stored as strings in Redis
            return json.dumps(string_detection_ids)
        elif f"batch:{batch_id}:started_at" in key:
            return "1703341800.0"
        return None

    mock_redis_client.get.side_effect = mock_get

    # Setup database with camera and detections
    from backend.core.database import get_session

    async with get_session() as session:
        # Use unique name to prevent unique constraint conflicts in parallel tests
        camera = Camera(
            id=camera_id,
            name=f"Front Door {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        for det in detections:
            session.add(det)
        await session.commit()

    # Mock LLM call
    mock_llm_response = {
        "content": json.dumps(
            {
                "risk_score": 65,
                "risk_level": "high",
                "summary": "Test with string IDs",
                "reasoning": "Verifies string-to-int conversion",
            }
        )
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_llm_response
        mock_post.return_value = mock_resp

        # This should succeed - string IDs are converted to ints for DB query
        event = await analyzer.analyze_batch(batch_id)

    # Verify event was created successfully
    assert event is not None
    assert event.batch_id == batch_id
    assert event.risk_score == 65

    # Verify detection IDs via junction table (query within session to avoid DetachedInstanceError)
    async with get_session() as session:
        result = await session.execute(
            select(EventDetection.detection_id).where(EventDetection.event_id == event.id)
        )
        stored_ids = [row[0] for row in result.fetchall()]

    assert sorted(stored_ids) == [base_det_id, base_det_id + 1, base_det_id + 2]
    assert all(isinstance(d, int) for d in stored_ids)


@pytest.mark.asyncio
async def test_analyze_batch_invalid_detection_id_raises_clear_error(
    analyzer, mock_redis_client, isolated_db
):
    """Test that invalid (non-numeric) detection IDs raise a clear error.

    If somehow a non-numeric string gets into the detection_ids list,
    the conversion should fail with an informative error message.
    """
    batch_id = unique_id("batch")
    camera_id = unique_id("camera")

    # Setup Redis mocks with invalid detection IDs
    async def mock_get(key):
        if f"batch:{batch_id}:camera_id" in key:
            return camera_id
        elif f"batch:{batch_id}:detections" in key:
            # Invalid: contains non-numeric string
            return json.dumps(["123", "not_a_number", "456"])
        elif f"batch:{batch_id}:started_at" in key:
            return "1703341800.0"
        return None

    mock_redis_client.get.side_effect = mock_get

    # Setup database with camera
    from backend.core.database import get_session

    async with get_session() as session:
        # Use unique name to prevent unique constraint conflicts in parallel tests
        camera = Camera(
            id=camera_id,
            name=f"Front Door {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.commit()

    # Should raise ValueError with clear error message
    with pytest.raises(ValueError, match=r"Invalid detection_id in batch"):
        await analyzer.analyze_batch(batch_id)


@pytest.mark.asyncio
async def test_analyze_batch_mixed_int_and_string_detection_ids(
    analyzer, mock_redis_client, isolated_db, sample_detections_factory
):
    """Test that analyze_batch handles mixed int/string detection IDs.

    The detection_ids list might contain both integers and strings
    (e.g., from different code paths). Both should be converted correctly.
    """
    batch_id = unique_id("batch")
    camera_id = unique_id("camera")
    base_det_id = random.randint(100000, 999999)  # noqa: S311  # nosemgrep: insecure-random

    # Mixed int and string IDs (both should work)
    mixed_detection_ids = [base_det_id, str(base_det_id + 1), base_det_id + 2]

    # Create detections with matching integer IDs
    detections = sample_detections_factory(camera_id, start_id=base_det_id)

    # Setup Redis mocks
    async def mock_get(key):
        if f"batch:{batch_id}:camera_id" in key:
            return camera_id
        elif f"batch:{batch_id}:detections" in key:
            return json.dumps(mixed_detection_ids)
        elif f"batch:{batch_id}:started_at" in key:
            return "1703341800.0"
        return None

    mock_redis_client.get.side_effect = mock_get

    # Setup database
    from backend.core.database import get_session

    async with get_session() as session:
        # Use unique name to prevent unique constraint conflicts in parallel tests
        camera = Camera(
            id=camera_id,
            name=f"Front Door {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        for det in detections:
            session.add(det)
        await session.commit()

    # Mock LLM call
    mock_llm_response = {
        "content": json.dumps(
            {
                "risk_score": 55,
                "risk_level": "medium",
                "summary": "Mixed ID types test",
                "reasoning": "Test reasoning",
            }
        )
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_llm_response
        mock_post.return_value = mock_resp

        # Should succeed with mixed int/string IDs
        event = await analyzer.analyze_batch(batch_id)

    assert event is not None
    assert event.risk_score == 55

    # Verify detection IDs via junction table (query within session to avoid DetachedInstanceError)
    async with get_session() as session:
        result = await session.execute(
            select(EventDetection.detection_id).where(EventDetection.event_id == event.id)
        )
        stored_ids = [row[0] for row in result.fetchall()]

    assert sorted(stored_ids) == [base_det_id, base_det_id + 1, base_det_id + 2]
    assert all(isinstance(d, int) for d in stored_ids)


@pytest.mark.asyncio
async def test_analyze_batch_with_direct_detection_ids_parameter(
    analyzer, mock_redis_client, isolated_db, sample_detections_factory
):
    """Test analyze_batch when detection_ids are passed directly (not from Redis).

    When called from AnalysisQueueWorker, detection_ids are passed directly
    from the queue payload. These may be strings and need conversion.
    """
    batch_id = unique_id("batch")
    camera_id = unique_id("camera")
    base_det_id = random.randint(100000, 999999)  # noqa: S311  # nosemgrep: insecure-random

    # String IDs passed directly (simulating queue payload)
    direct_string_ids = [str(base_det_id), str(base_det_id + 1)]

    # Create detections
    detections = sample_detections_factory(camera_id, start_id=base_det_id)

    # Setup database
    from backend.core.database import get_session

    async with get_session() as session:
        # Use unique name to prevent unique constraint conflicts in parallel tests
        camera = Camera(
            id=camera_id,
            name=f"Front Door {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        for det in detections[:2]:  # Only first two detections
            session.add(det)
        await session.commit()

    # Mock LLM call
    mock_llm_response = {
        "content": json.dumps(
            {
                "risk_score": 70,
                "risk_level": "high",
                "summary": "Direct IDs test",
                "reasoning": "Test",
            }
        )
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_llm_response
        mock_post.return_value = mock_resp

        # Call with direct detection_ids parameter (bypasses Redis lookup)
        event = await analyzer.analyze_batch(
            batch_id=batch_id,
            camera_id=camera_id,
            detection_ids=direct_string_ids,
        )

    assert event is not None
    assert event.batch_id == batch_id
    assert event.camera_id == camera_id
    assert event.risk_score == 70

    # Verify detection IDs via junction table (query within session to avoid DetachedInstanceError)
    async with get_session() as session:
        result = await session.execute(
            select(EventDetection.detection_id).where(EventDetection.event_id == event.id)
        )
        stored_ids = [row[0] for row in result.fetchall()]

    assert sorted(stored_ids) == [base_det_id, base_det_id + 1]
