"""Integration tests for NemotronAnalyzer service.

Tests the NemotronAnalyzer service with a real SQLite database and mocked
HTTP calls to the Nemotron LLM service. Verifies that detection batches
are properly analyzed and Event records are created correctly.
"""

import json
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.core.redis import RedisClient
from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.services.nemotron_analyzer import NemotronAnalyzer


@pytest.fixture
async def test_db_setup():
    """Set up test database environment."""
    from backend.core.config import get_settings
    from backend.core.database import close_db, init_db

    # Close any existing database connections
    await close_db()

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_nemotron_analyzer.db"
        test_db_url = f"sqlite+aiosqlite:///{db_path}"

        # Store original environment
        original_db_url = os.environ.get("DATABASE_URL")
        original_redis_url = os.environ.get("REDIS_URL")

        # Set test environment
        os.environ["DATABASE_URL"] = test_db_url
        os.environ["REDIS_URL"] = "redis://localhost:6379/15"

        # Clear settings cache to pick up new environment variables
        get_settings.cache_clear()

        # Initialize database explicitly
        await init_db()

        yield test_db_url

        # Cleanup
        await close_db()

        # Restore original environment
        if original_db_url:
            os.environ["DATABASE_URL"] = original_db_url
        else:
            os.environ.pop("DATABASE_URL", None)

        if original_redis_url:
            os.environ["REDIS_URL"] = original_redis_url
        else:
            os.environ.pop("REDIS_URL", None)

        # Clear settings cache again
        get_settings.cache_clear()


@pytest.fixture
async def sample_camera(test_db_setup):
    """Create a sample camera in the database."""
    from backend.core.database import get_session

    camera_id = str(uuid.uuid4())
    async with get_session() as db:
        camera = Camera(
            id=camera_id,
            name="Front Door",
            folder_path="/export/foscam/front_door",
            status="online",
        )
        db.add(camera)
        await db.commit()
        await db.refresh(camera)
        yield camera


@pytest.fixture
async def sample_detections(test_db_setup, sample_camera):
    """Create sample detections in the database."""
    from backend.core.database import get_session

    async with get_session() as db:
        detection1 = Detection(
            camera_id=sample_camera.id,
            file_path="/export/foscam/front_door/img001.jpg",
            file_type="image/jpeg",
            detected_at=datetime(2025, 12, 23, 14, 0, 0),
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=150,
            bbox_width=200,
            bbox_height=400,
        )
        detection2 = Detection(
            camera_id=sample_camera.id,
            file_path="/export/foscam/front_door/img002.jpg",
            file_type="image/jpeg",
            detected_at=datetime(2025, 12, 23, 14, 1, 0),
            object_type="car",
            confidence=0.88,
            bbox_x=300,
            bbox_y=200,
            bbox_width=400,
            bbox_height=300,
        )
        detection3 = Detection(
            camera_id=sample_camera.id,
            file_path="/export/foscam/front_door/img003.jpg",
            file_type="image/jpeg",
            detected_at=datetime(2025, 12, 23, 14, 2, 0),
            object_type="person",
            confidence=0.92,
            bbox_x=150,
            bbox_y=180,
            bbox_width=180,
            bbox_height=380,
        )
        db.add(detection1)
        db.add(detection2)
        db.add(detection3)
        await db.commit()
        await db.refresh(detection1)
        await db.refresh(detection2)
        await db.refresh(detection3)
        yield [detection1, detection2, detection3]


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client."""
    mock_client = AsyncMock(spec=RedisClient)
    return mock_client


@pytest.fixture
def mock_llm_response():
    """Standard mock LLM response."""
    return {
        "content": json.dumps(
            {
                "risk_score": 65,
                "risk_level": "high",
                "summary": "Person detected near entrance with unknown vehicle",
                "reasoning": "Multiple persons detected near the front entrance along with an unknown vehicle. Time of detection suggests regular activity but warrants attention.",
            }
        )
    }


class TestAnalyzeBatchCreatesEvent:
    """Tests for analyze_batch creating Event records."""

    async def test_analyze_batch_creates_event(
        self, test_db_setup, sample_camera, sample_detections, mock_redis_client, mock_llm_response
    ):
        """Test that analyze_batch creates an Event from a batch of detections."""
        from backend.core.database import get_session

        batch_id = f"batch_{uuid.uuid4()}"
        detection_ids = [d.id for d in sample_detections]

        # Setup Redis mock to return batch metadata
        mock_redis_client.get.side_effect = [
            sample_camera.id,  # batch:{batch_id}:camera_id
            json.dumps(detection_ids),  # batch:{batch_id}:detections
        ]
        mock_redis_client.publish.return_value = 1

        # Mock HTTP call to LLM
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_llm_response
        mock_response.raise_for_status = MagicMock()

        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

        with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
            event = await analyzer.analyze_batch(batch_id)

        # Verify event was created
        assert event is not None
        assert event.id is not None
        assert event.batch_id == batch_id
        assert event.camera_id == sample_camera.id

        # Verify event persisted in database
        async with get_session() as db:
            from sqlalchemy import select

            result = await db.execute(select(Event).where(Event.id == event.id))
            db_event = result.scalar_one_or_none()
            assert db_event is not None
            assert db_event.batch_id == batch_id

    async def test_analyze_batch_links_detections_to_event(
        self, test_db_setup, sample_camera, sample_detections, mock_redis_client, mock_llm_response
    ):
        """Test that analyze_batch stores detection IDs in the Event record."""
        batch_id = f"batch_{uuid.uuid4()}"
        detection_ids = [d.id for d in sample_detections]

        # Setup Redis mock
        mock_redis_client.get.side_effect = [
            sample_camera.id,
            json.dumps(detection_ids),
        ]
        mock_redis_client.publish.return_value = 1

        # Mock HTTP call to LLM
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_llm_response
        mock_response.raise_for_status = MagicMock()

        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

        with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
            event = await analyzer.analyze_batch(batch_id)

        # Verify detection_ids are stored
        stored_detection_ids = json.loads(event.detection_ids)
        assert sorted(stored_detection_ids) == sorted(detection_ids)

    async def test_analyze_batch_sets_risk_score(
        self, test_db_setup, sample_camera, sample_detections, mock_redis_client, mock_llm_response
    ):
        """Test that analyze_batch correctly populates risk_score and risk_level."""
        batch_id = f"batch_{uuid.uuid4()}"
        detection_ids = [d.id for d in sample_detections]

        # Setup Redis mock
        mock_redis_client.get.side_effect = [
            sample_camera.id,
            json.dumps(detection_ids),
        ]
        mock_redis_client.publish.return_value = 1

        # Mock HTTP call to LLM
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_llm_response
        mock_response.raise_for_status = MagicMock()

        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

        with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
            event = await analyzer.analyze_batch(batch_id)

        # Verify risk assessment fields
        assert event.risk_score == 65
        assert event.risk_level == "high"
        assert event.summary == "Person detected near entrance with unknown vehicle"
        assert "Multiple persons" in event.reasoning

    async def test_analyze_batch_sets_time_window(
        self, test_db_setup, sample_camera, sample_detections, mock_redis_client, mock_llm_response
    ):
        """Test that analyze_batch correctly sets started_at and ended_at from detections."""
        batch_id = f"batch_{uuid.uuid4()}"
        detection_ids = [d.id for d in sample_detections]

        # Setup Redis mock
        mock_redis_client.get.side_effect = [
            sample_camera.id,
            json.dumps(detection_ids),
        ]
        mock_redis_client.publish.return_value = 1

        # Mock HTTP call to LLM
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_llm_response
        mock_response.raise_for_status = MagicMock()

        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

        with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
            event = await analyzer.analyze_batch(batch_id)

        # Verify time window matches detection times
        assert event.started_at == datetime(2025, 12, 23, 14, 0, 0)
        assert event.ended_at == datetime(2025, 12, 23, 14, 2, 0)


class TestAnalyzeBatchErrorHandling:
    """Tests for analyze_batch error handling."""

    async def test_analyze_batch_handles_llm_failure(
        self, test_db_setup, sample_camera, sample_detections, mock_redis_client
    ):
        """Test that analyze_batch gracefully handles LLM service errors."""
        from backend.core.database import get_session

        batch_id = f"batch_{uuid.uuid4()}"
        detection_ids = [d.id for d in sample_detections]

        # Setup Redis mock
        mock_redis_client.get.side_effect = [
            sample_camera.id,
            json.dumps(detection_ids),
        ]
        mock_redis_client.publish.return_value = 1

        # Mock HTTP call to fail
        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

        with patch.object(
            httpx.AsyncClient, "post", side_effect=httpx.ConnectError("LLM service unavailable")
        ):
            event = await analyzer.analyze_batch(batch_id)

        # Event should still be created with fallback values
        assert event is not None
        assert event.risk_score == 50  # Default fallback
        assert event.risk_level == "medium"  # Default fallback
        assert "LLM service error" in event.summary
        assert "LLM service unavailable" in event.reasoning

        # Verify event persisted
        async with get_session() as db:
            from sqlalchemy import select

            result = await db.execute(select(Event).where(Event.id == event.id))
            db_event = result.scalar_one_or_none()
            assert db_event is not None

    async def test_analyze_batch_empty_detections(
        self, test_db_setup, sample_camera, mock_redis_client
    ):
        """Test that analyze_batch raises error when no detections found in database."""
        batch_id = f"batch_{uuid.uuid4()}"

        # Redis returns detection IDs that don't exist in database
        mock_redis_client.get.side_effect = [
            sample_camera.id,
            json.dumps([99999, 99998, 99997]),  # Non-existent detection IDs
        ]

        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

        with pytest.raises(ValueError, match="No detections found"):
            await analyzer.analyze_batch(batch_id)

    async def test_analyze_batch_missing_batch(self, test_db_setup, mock_redis_client):
        """Test that analyze_batch raises error when batch not found in Redis."""
        batch_id = "nonexistent_batch"

        # Redis returns None for camera_id
        mock_redis_client.get.return_value = None

        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

        with pytest.raises(ValueError, match="not found in Redis"):
            await analyzer.analyze_batch(batch_id)

    async def test_analyze_batch_empty_detection_list(
        self, test_db_setup, sample_camera, mock_redis_client
    ):
        """Test that analyze_batch raises error when batch has no detection IDs."""
        batch_id = f"batch_{uuid.uuid4()}"

        # Redis returns empty detection list
        mock_redis_client.get.side_effect = [
            sample_camera.id,
            json.dumps([]),  # Empty list
        ]

        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

        with pytest.raises(ValueError, match="has no detections"):
            await analyzer.analyze_batch(batch_id)

    async def test_analyze_batch_no_redis_client(self, test_db_setup):
        """Test that analyze_batch raises error when Redis client not initialized."""
        analyzer = NemotronAnalyzer(redis_client=None)

        with pytest.raises(RuntimeError, match="Redis client not initialized"):
            await analyzer.analyze_batch("any_batch_id")


class TestAnalyzeDetectionFastPath:
    """Tests for analyze_detection_fast_path method."""

    async def test_analyze_detection_fast_path(
        self, test_db_setup, sample_camera, sample_detections, mock_redis_client, mock_llm_response
    ):
        """Test fast path analysis for a single high-priority detection."""
        from backend.core.database import get_session

        detection = sample_detections[0]

        # Mock Redis (no batch metadata needed for fast path)
        mock_redis_client.publish.return_value = 1

        # Mock HTTP call to LLM
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_llm_response
        mock_response.raise_for_status = MagicMock()

        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

        with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
            event = await analyzer.analyze_detection_fast_path(sample_camera.id, str(detection.id))

        # Verify event was created with fast path flag
        assert event is not None
        assert event.is_fast_path is True
        assert event.batch_id == f"fast_path_{detection.id}"
        assert event.camera_id == sample_camera.id
        assert event.risk_score == 65

        # Started_at and ended_at should be the same for single detection
        assert event.started_at == detection.detected_at
        assert event.ended_at == detection.detected_at

        # Verify detection_ids contains only the single detection
        stored_ids = json.loads(event.detection_ids)
        assert stored_ids == [detection.id]

        # Verify event persisted
        async with get_session() as db:
            from sqlalchemy import select

            result = await db.execute(select(Event).where(Event.id == event.id))
            db_event = result.scalar_one_or_none()
            assert db_event is not None
            assert db_event.is_fast_path is True

    async def test_analyze_detection_fast_path_missing_detection(
        self, test_db_setup, sample_camera, mock_redis_client
    ):
        """Test fast path raises error when detection not found."""
        mock_redis_client.publish.return_value = 1

        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

        with pytest.raises(ValueError, match="not found in database"):
            await analyzer.analyze_detection_fast_path(sample_camera.id, "99999")

    async def test_analyze_detection_fast_path_invalid_detection_id(
        self, test_db_setup, sample_camera, mock_redis_client
    ):
        """Test fast path raises error for invalid detection ID format."""
        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

        with pytest.raises(ValueError, match="Invalid detection_id"):
            await analyzer.analyze_detection_fast_path(sample_camera.id, "not_a_number")

    async def test_analyze_detection_fast_path_no_redis_client(self, test_db_setup):
        """Test fast path raises error when Redis client not initialized."""
        analyzer = NemotronAnalyzer(redis_client=None)

        with pytest.raises(RuntimeError, match="Redis client not initialized"):
            await analyzer.analyze_detection_fast_path("camera_id", "123")

    async def test_analyze_detection_fast_path_handles_llm_failure(
        self, test_db_setup, sample_camera, sample_detections, mock_redis_client
    ):
        """Test fast path gracefully handles LLM service errors."""
        detection = sample_detections[0]

        mock_redis_client.publish.return_value = 1

        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

        with patch.object(
            httpx.AsyncClient, "post", side_effect=httpx.ConnectError("LLM service unavailable")
        ):
            event = await analyzer.analyze_detection_fast_path(sample_camera.id, str(detection.id))

        # Event should still be created with fallback values
        assert event is not None
        assert event.is_fast_path is True
        assert event.risk_score == 50
        assert event.risk_level == "medium"
        assert "LLM service error" in event.summary


class TestLLMResponseParsing:
    """Tests for LLM response parsing and validation."""

    async def test_analyze_batch_validates_risk_score_bounds(
        self, test_db_setup, sample_camera, sample_detections, mock_redis_client
    ):
        """Test that risk_score is clamped to 0-100 range."""
        batch_id = f"batch_{uuid.uuid4()}"
        detection_ids = [d.id for d in sample_detections]

        mock_redis_client.get.side_effect = [
            sample_camera.id,
            json.dumps(detection_ids),
        ]
        mock_redis_client.publish.return_value = 1

        # LLM returns out-of-bounds risk score
        invalid_response = {
            "content": json.dumps(
                {
                    "risk_score": 150,  # Above 100
                    "risk_level": "critical",
                    "summary": "Test summary",
                    "reasoning": "Test reasoning",
                }
            )
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = invalid_response
        mock_response.raise_for_status = MagicMock()

        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

        with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
            event = await analyzer.analyze_batch(batch_id)

        # Risk score should be clamped to 100
        assert event.risk_score == 100

    async def test_analyze_batch_normalizes_invalid_risk_level(
        self, test_db_setup, sample_camera, sample_detections, mock_redis_client
    ):
        """Test that invalid risk_level is normalized based on risk_score."""
        batch_id = f"batch_{uuid.uuid4()}"
        detection_ids = [d.id for d in sample_detections]

        mock_redis_client.get.side_effect = [
            sample_camera.id,
            json.dumps(detection_ids),
        ]
        mock_redis_client.publish.return_value = 1

        # LLM returns invalid risk_level
        invalid_response = {
            "content": json.dumps(
                {
                    "risk_score": 80,
                    "risk_level": "invalid_level",
                    "summary": "Test summary",
                    "reasoning": "Test reasoning",
                }
            )
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = invalid_response
        mock_response.raise_for_status = MagicMock()

        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

        with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
            event = await analyzer.analyze_batch(batch_id)

        # Risk level should be inferred from score (80 = critical)
        assert event.risk_level == "critical"

    async def test_analyze_batch_handles_json_in_text_response(
        self, test_db_setup, sample_camera, sample_detections, mock_redis_client
    ):
        """Test that LLM response with extra text around JSON is handled."""
        batch_id = f"batch_{uuid.uuid4()}"
        detection_ids = [d.id for d in sample_detections]

        mock_redis_client.get.side_effect = [
            sample_camera.id,
            json.dumps(detection_ids),
        ]
        mock_redis_client.publish.return_value = 1

        # LLM returns JSON embedded in text
        response_with_text = {
            "content": 'Here is my analysis:\n{"risk_score": 45, "risk_level": "medium", "summary": "Analysis", "reasoning": "Details"}\n\nHope this helps!'
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = response_with_text
        mock_response.raise_for_status = MagicMock()

        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

        with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
            event = await analyzer.analyze_batch(batch_id)

        # Should extract JSON from text
        assert event.risk_score == 45
        assert event.risk_level == "medium"


class TestHealthCheck:
    """Tests for the health_check method."""

    async def test_health_check_success(self, test_db_setup):
        """Test health check when LLM is available."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        analyzer = NemotronAnalyzer(redis_client=None)

        with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
            result = await analyzer.health_check()

        assert result is True

    async def test_health_check_failure(self, test_db_setup):
        """Test health check when LLM is unavailable."""
        analyzer = NemotronAnalyzer(redis_client=None)

        with patch.object(
            httpx.AsyncClient, "get", side_effect=httpx.ConnectError("Connection refused")
        ):
            result = await analyzer.health_check()

        assert result is False

    async def test_health_check_non_200_status(self, test_db_setup):
        """Test health check with non-200 response."""
        mock_response = MagicMock()
        mock_response.status_code = 503

        analyzer = NemotronAnalyzer(redis_client=None)

        with patch.object(httpx.AsyncClient, "get", return_value=mock_response):
            result = await analyzer.health_check()

        assert result is False


class TestWebSocketBroadcast:
    """Tests for WebSocket event broadcasting."""

    async def test_broadcast_event_success(
        self, test_db_setup, sample_camera, sample_detections, mock_redis_client, mock_llm_response
    ):
        """Test that event is broadcasted via WebSocket after creation."""
        batch_id = f"batch_{uuid.uuid4()}"
        detection_ids = [d.id for d in sample_detections]

        mock_redis_client.get.side_effect = [
            sample_camera.id,
            json.dumps(detection_ids),
        ]
        mock_redis_client.publish.return_value = 1

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_llm_response
        mock_response.raise_for_status = MagicMock()

        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

        with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
            event = await analyzer.analyze_batch(batch_id)

        # Verify publish was called
        mock_redis_client.publish.assert_called_once()
        call_args = mock_redis_client.publish.call_args
        assert call_args[0][0] == "security_events"  # Canonical channel name

        # Verify message content (envelope format: {"type": "event", "data": {...}})
        message = call_args[0][1]
        assert message["type"] == "event"
        assert message["data"]["event_id"] == event.id
        assert message["data"]["camera_id"] == sample_camera.id

    async def test_broadcast_event_failure_does_not_fail_analysis(
        self, test_db_setup, sample_camera, sample_detections, mock_redis_client, mock_llm_response
    ):
        """Test that WebSocket broadcast failure doesn't fail the analysis."""
        batch_id = f"batch_{uuid.uuid4()}"
        detection_ids = [d.id for d in sample_detections]

        mock_redis_client.get.side_effect = [
            sample_camera.id,
            json.dumps(detection_ids),
        ]
        mock_redis_client.publish.side_effect = Exception("Publish failed")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_llm_response
        mock_response.raise_for_status = MagicMock()

        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

        with patch.object(httpx.AsyncClient, "post", return_value=mock_response):
            # Should not raise exception
            event = await analyzer.analyze_batch(batch_id)

        # Event should still be created
        assert event is not None
        assert event.id is not None
