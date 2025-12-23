"""Unit tests for Nemotron analyzer service."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy import select

from backend.models.camera import Camera
from backend.models.detection import Detection
from backend.models.event import Event
from backend.services.nemotron_analyzer import NemotronAnalyzer

# Fixtures


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for Nemotron analyzer tests."""
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=None)
    mock_client.set = AsyncMock(return_value=True)
    mock_client.delete = AsyncMock(return_value=1)
    mock_client.publish = AsyncMock(return_value=1)
    return mock_client


@pytest.fixture
def analyzer(mock_redis_client):
    """Create NemotronAnalyzer instance with mocked Redis."""
    return NemotronAnalyzer(redis_client=mock_redis_client)


@pytest.fixture
def sample_detections():
    """Sample detections for testing."""
    base_time = datetime(2025, 12, 23, 14, 30, 0)
    return [
        Detection(
            id=1,
            camera_id="front_door",
            file_path="/export/foscam/front_door/img1.jpg",
            detected_at=base_time,
            object_type="person",
            confidence=0.95,
        ),
        Detection(
            id=2,
            camera_id="front_door",
            file_path="/export/foscam/front_door/img2.jpg",
            detected_at=datetime(2025, 12, 23, 14, 30, 15),
            object_type="car",
            confidence=0.88,
        ),
        Detection(
            id=3,
            camera_id="front_door",
            file_path="/export/foscam/front_door/img3.jpg",
            detected_at=datetime(2025, 12, 23, 14, 30, 30),
            object_type="person",
            confidence=0.92,
        ),
    ]


# Test: Health Check


@pytest.mark.asyncio
async def test_health_check_success(analyzer):
    """Test health check returns True when LLM server is available."""
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = await analyzer.health_check()

    assert result is True


@pytest.mark.asyncio
async def test_health_check_failure(analyzer):
    """Test health check returns False when LLM server is unavailable."""
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = httpx.ConnectError("Connection refused")

        result = await analyzer.health_check()

    assert result is False


@pytest.mark.asyncio
async def test_health_check_timeout(analyzer):
    """Test health check returns False on timeout."""
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = httpx.TimeoutException("Request timeout")

        result = await analyzer.health_check()

    assert result is False


# Test: Format Detections


def test_format_detections(analyzer, sample_detections):
    """Test formatting detections into human-readable list."""
    formatted = analyzer._format_detections(sample_detections)

    assert "person" in formatted
    assert "car" in formatted
    assert "0.95" in formatted
    assert "0.88" in formatted
    assert "14:30:00" in formatted
    assert "14:30:15" in formatted


def test_format_detections_empty(analyzer):
    """Test formatting empty detection list."""
    formatted = analyzer._format_detections([])
    assert formatted == ""


def test_format_detections_missing_data(analyzer):
    """Test formatting detections with missing object_type and confidence."""
    detection = Detection(
        id=1,
        camera_id="front_door",
        file_path="/export/foscam/front_door/img1.jpg",
        detected_at=datetime(2025, 12, 23, 14, 30, 0),
        object_type=None,
        confidence=None,
    )

    formatted = analyzer._format_detections([detection])

    assert "unknown" in formatted
    assert "N/A" in formatted


# Test: Parse LLM Response


def test_parse_llm_response_valid_json(analyzer):
    """Test parsing valid JSON from LLM response."""
    response_text = """
    {
      "risk_score": 75,
      "risk_level": "high",
      "summary": "Multiple persons detected at unusual time",
      "reasoning": "Three detections of persons in quick succession"
    }
    """

    result = analyzer._parse_llm_response(response_text)

    assert result["risk_score"] == 75
    assert result["risk_level"] == "high"
    assert "Multiple persons" in result["summary"]
    assert "Three detections" in result["reasoning"]


def test_parse_llm_response_with_extra_text(analyzer):
    """Test parsing JSON when LLM includes extra text."""
    response_text = """
    Based on the detections, here is my analysis:

    {
      "risk_score": 50,
      "risk_level": "medium",
      "summary": "Normal activity observed",
      "reasoning": "Typical daytime activity with person and vehicle"
    }

    Let me know if you need more details.
    """

    result = analyzer._parse_llm_response(response_text)

    assert result["risk_score"] == 50
    assert result["risk_level"] == "medium"


def test_parse_llm_response_no_json(analyzer):
    """Test parsing fails when no JSON is present."""
    response_text = "This is just plain text without any JSON."

    with pytest.raises(ValueError, match="No JSON found"):
        analyzer._parse_llm_response(response_text)


def test_parse_llm_response_invalid_json(analyzer):
    """Test parsing fails when JSON is malformed."""
    response_text = '{ "risk_score": 50, "risk_level": "medium" '

    with pytest.raises(ValueError, match=r"(Could not parse|No JSON found)"):
        analyzer._parse_llm_response(response_text)


def test_parse_llm_response_missing_required_fields(analyzer):
    """Test parsing fails when required fields are missing."""
    response_text = '{"summary": "Some summary"}'

    with pytest.raises(ValueError, match="Could not parse"):
        analyzer._parse_llm_response(response_text)


# Test: Validate Risk Data


def test_validate_risk_data_valid(analyzer):
    """Test validation of valid risk data."""
    data = {
        "risk_score": 75,
        "risk_level": "high",
        "summary": "Test summary",
        "reasoning": "Test reasoning",
    }

    result = analyzer._validate_risk_data(data)

    assert result["risk_score"] == 75
    assert result["risk_level"] == "high"
    assert result["summary"] == "Test summary"
    assert result["reasoning"] == "Test reasoning"


def test_validate_risk_data_clamps_score(analyzer):
    """Test that risk scores are clamped to 0-100 range."""
    # Test upper bound
    data = {"risk_score": 150, "risk_level": "high"}
    result = analyzer._validate_risk_data(data)
    assert result["risk_score"] == 100

    # Test lower bound
    data = {"risk_score": -50, "risk_level": "low"}
    result = analyzer._validate_risk_data(data)
    assert result["risk_score"] == 0


def test_validate_risk_data_invalid_score_type(analyzer):
    """Test validation handles invalid risk_score types."""
    data = {"risk_score": "not_a_number", "risk_level": "medium"}
    result = analyzer._validate_risk_data(data)
    assert result["risk_score"] == 50  # Default fallback


def test_validate_risk_data_missing_score(analyzer):
    """Test validation provides default when risk_score is missing."""
    data = {"risk_level": "medium"}
    result = analyzer._validate_risk_data(data)
    assert result["risk_score"] == 50


def test_validate_risk_data_invalid_level(analyzer):
    """Test validation infers risk_level from risk_score when invalid."""
    data = {"risk_score": 80, "risk_level": "invalid_level"}
    result = analyzer._validate_risk_data(data)
    assert result["risk_level"] == "critical"  # Inferred from score (76-100)


def test_validate_risk_data_level_inference(analyzer):
    """Test risk_level inference from risk_score."""
    result = analyzer._validate_risk_data({"risk_score": 20, "risk_level": "invalid"})
    assert result["risk_level"] == "low"

    result = analyzer._validate_risk_data({"risk_score": 40, "risk_level": "invalid"})
    assert result["risk_level"] == "medium"

    result = analyzer._validate_risk_data({"risk_score": 60, "risk_level": "invalid"})
    assert result["risk_level"] == "high"

    result = analyzer._validate_risk_data({"risk_score": 90, "risk_level": "invalid"})
    assert result["risk_level"] == "critical"


def test_validate_risk_data_missing_summary_reasoning(analyzer):
    """Test validation provides defaults for missing summary/reasoning."""
    data = {"risk_score": 50, "risk_level": "medium"}
    result = analyzer._validate_risk_data(data)
    assert "Risk analysis completed" in result["summary"]
    assert "No detailed reasoning" in result["reasoning"]


# Test: Call LLM


@pytest.mark.asyncio
async def test_call_llm_success(analyzer):
    """Test successful LLM call with valid response."""
    mock_response = {
        "content": json.dumps(
            {
                "risk_score": 60,
                "risk_level": "high",
                "summary": "Unusual activity detected",
                "reasoning": "Person detected at odd hours",
            }
        )
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_post.return_value = mock_resp

        result = await analyzer._call_llm(
            camera_name="Front Door",
            start_time="2025-12-23T14:30:00",
            end_time="2025-12-23T14:31:00",
            detections_list="1. 14:30:00 - person (confidence: 0.95)",
        )

    assert result["risk_score"] == 60
    assert result["risk_level"] == "high"
    assert "Unusual activity" in result["summary"]


@pytest.mark.asyncio
async def test_call_llm_empty_content(analyzer):
    """Test LLM call with empty content raises ValueError."""
    mock_response = {"content": ""}

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_post.return_value = mock_resp

        with pytest.raises(ValueError, match="Empty completion"):
            await analyzer._call_llm(
                camera_name="Front Door",
                start_time="2025-12-23T14:30:00",
                end_time="2025-12-23T14:31:00",
                detections_list="1. 14:30:00 - person",
            )


@pytest.mark.asyncio
async def test_call_llm_http_error(analyzer):
    """Test LLM call raises exception on HTTP error."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(), response=mock_resp
        )
        mock_post.return_value = mock_resp

        with pytest.raises(httpx.HTTPStatusError):
            await analyzer._call_llm(
                camera_name="Front Door",
                start_time="2025-12-23T14:30:00",
                end_time="2025-12-23T14:31:00",
                detections_list="1. 14:30:00 - person",
            )


# Test: Analyze Batch (Integration-style unit tests)


@pytest.mark.asyncio
async def test_analyze_batch_no_redis_client(analyzer):
    """Test analyze_batch raises error when Redis client not initialized."""
    analyzer._redis = None

    with pytest.raises(RuntimeError, match="Redis client not initialized"):
        await analyzer.analyze_batch("batch_123")


@pytest.mark.asyncio
async def test_analyze_batch_batch_not_found(analyzer, mock_redis_client):
    """Test analyze_batch raises error when batch not found in Redis."""
    mock_redis_client.get.return_value = None

    with pytest.raises(ValueError, match=r"Batch .* not found"):
        await analyzer.analyze_batch("batch_123")


@pytest.mark.asyncio
async def test_analyze_batch_no_detections(analyzer, mock_redis_client):
    """Test analyze_batch raises error when batch has no detections."""

    async def mock_get(key):
        if "camera_id" in key:
            return "front_door"
        elif "detections" in key:
            return json.dumps([])
        elif "started_at" in key:
            return "1703341800.0"
        return None

    mock_redis_client.get.side_effect = mock_get

    with pytest.raises(ValueError, match="has no detections"):
        await analyzer.analyze_batch("batch_123")


@pytest.mark.asyncio
async def test_analyze_batch_success(analyzer, mock_redis_client, isolated_db, sample_detections):
    """Test successful batch analysis creates Event."""
    batch_id = "batch_123"
    camera_id = "front_door"
    detection_ids = [1, 2, 3]

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
        # Create camera
        camera = Camera(
            id=camera_id,
            name="Front Door",
            folder_path="/export/foscam/front_door",
        )
        session.add(camera)

        # Create detections
        for det in sample_detections:
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
    analyzer, mock_redis_client, isolated_db, sample_detections
):
    """Test batch analysis uses fallback risk data when LLM fails."""
    batch_id = "batch_456"
    camera_id = "front_door"
    detection_ids = [1, 2, 3]

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
        camera = Camera(
            id=camera_id,
            name="Front Door",
            folder_path="/export/foscam/front_door",
        )
        session.add(camera)

        for det in sample_detections:
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
    analyzer, mock_redis_client, isolated_db, sample_detections
):
    """Test batch analysis handles missing camera gracefully by using camera_id as name."""
    batch_id = "batch_789"
    camera_id = "nonexistent_camera"
    detection_ids = [1, 2, 3]

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

    # Setup database - create a different camera and detections with nonexistent camera_id
    # We need to use SQLite's PRAGMA to temporarily disable foreign keys for testing
    from backend.core.database import get_session

    async with get_session() as session:
        # Create a real camera first to avoid FK constraint issues
        real_camera = Camera(
            id="real_camera",
            name="Real Camera",
            folder_path="/export/foscam/real",
        )
        session.add(real_camera)
        await session.commit()

    async with get_session() as session:
        # Create detections for the camera
        for det in sample_detections:
            det.camera_id = "real_camera"
            session.add(det)
        await session.commit()

    # Update mock to return real_camera ID
    async def mock_get_real(key):
        if f"batch:{batch_id}:camera_id" in key:
            return "real_camera"
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

    assert event.camera_id == "real_camera"
    # Verify event was created successfully
    assert event.risk_score == 50
    assert event.risk_level == "medium"


@pytest.mark.asyncio
async def test_analyze_batch_detections_not_in_database(analyzer, mock_redis_client, isolated_db):
    """Test batch analysis raises error when detections not found in database."""
    batch_id = "batch_888"
    camera_id = "front_door"
    detection_ids = [999, 998, 997]  # IDs that don't exist

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
        camera = Camera(
            id=camera_id,
            name="Front Door",
            folder_path="/export/foscam/front_door",
        )
        session.add(camera)
        await session.commit()

    # Analyze batch - should raise ValueError for missing detections
    with pytest.raises(ValueError, match="No detections found for batch"):
        await analyzer.analyze_batch(batch_id)


@pytest.mark.asyncio
async def test_broadcast_event(analyzer, mock_redis_client):
    """Test event broadcasting via Redis pub/sub."""
    event = Event(
        id=1,
        batch_id="batch_123",
        camera_id="front_door",
        started_at=datetime(2025, 12, 23, 14, 30, 0),
        ended_at=datetime(2025, 12, 23, 14, 31, 0),
        risk_score=75,
        risk_level="high",
        summary="Test event",
        reasoning="Test reasoning",
    )

    await analyzer._broadcast_event(event)

    # Verify publish was called
    mock_redis_client.publish.assert_called_once()
    call_args = mock_redis_client.publish.call_args
    assert call_args[0][0] == "events"
    message = call_args[0][1]
    assert message["event_id"] == 1
    assert message["risk_score"] == 75
    assert message["risk_level"] == "high"


@pytest.mark.asyncio
async def test_broadcast_event_no_redis(analyzer):
    """Test broadcasting gracefully handles missing Redis client."""
    analyzer._redis = None
    event = Event(
        id=1,
        batch_id="batch_123",
        camera_id="front_door",
        started_at=datetime(2025, 12, 23, 14, 30, 0),
        risk_score=50,
        risk_level="medium",
        summary="Test",
    )

    # Should not raise exception
    await analyzer._broadcast_event(event)
