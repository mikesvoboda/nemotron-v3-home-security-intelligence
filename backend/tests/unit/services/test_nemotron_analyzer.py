"""Unit tests for Nemotron analyzer service.

These tests cover pure functions, mocked HTTP calls, and validation logic
that don't require database access.
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.models.detection import Detection
from backend.models.event import Event
from backend.services.nemotron_analyzer import NemotronAnalyzer
from backend.tests.conftest import unique_id

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


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
def mock_settings():
    """Create mock settings for NemotronAnalyzer."""
    from backend.core.config import Settings

    mock = MagicMock(spec=Settings)
    mock.nemotron_url = "http://localhost:8091"
    mock.nemotron_api_key = None  # Optional API key
    mock.ai_connect_timeout = 10.0
    mock.nemotron_read_timeout = 120.0
    mock.ai_health_timeout = 5.0
    # Severity settings for tests that use _validate_risk_data
    mock.severity_low_max = 29
    mock.severity_medium_max = 59
    mock.severity_high_max = 84
    return mock


@pytest.fixture
def analyzer(mock_redis_client, mock_settings):
    """Create NemotronAnalyzer instance with mocked Redis and settings."""
    # Patch both get_settings locations: nemotron_analyzer and severity service
    with (
        patch("backend.services.nemotron_analyzer.get_settings", return_value=mock_settings),
        patch("backend.services.severity.get_settings", return_value=mock_settings),
    ):
        # Also clear the severity service cache to ensure fresh service with mocked settings
        from backend.services.severity import reset_severity_service

        reset_severity_service()
        yield NemotronAnalyzer(redis_client=mock_redis_client)
        # Reset again after test to not affect other tests
        reset_severity_service()


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


@pytest.fixture
def sample_detections(sample_detections_factory):
    """Sample detections for testing (backwards compatibility).

    Note: For parallel test safety, prefer using sample_detections_factory
    with unique camera_id per test.
    """
    # Use a unique camera_id to avoid conflicts in parallel tests
    camera_id = unique_id("camera")
    return sample_detections_factory(camera_id)


# Test: Health Check


@pytest.mark.asyncio
async def test_health_check_success(analyzer):
    """Test health check returns True when LLM server is available."""
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock(spec=httpx.Response)
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
    # With backend thresholds: HIGH is 60-84, CRITICAL is 85-100
    data = {"risk_score": 80, "risk_level": "invalid_level"}
    result = analyzer._validate_risk_data(data)
    assert result["risk_level"] == "high"  # Inferred from score (60-84)

    # Test critical inference
    data_critical = {"risk_score": 90, "risk_level": "invalid_level"}
    result_critical = analyzer._validate_risk_data(data_critical)
    assert result_critical["risk_level"] == "critical"  # Inferred from score (85-100)


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
        mock_resp = MagicMock(spec=httpx.Response)
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
async def test_call_llm_uses_completion_endpoint(analyzer):
    """Test LLM call uses the correct /completion endpoint path.

    This test ensures the Nemotron analyzer uses the llama.cpp server's
    /completion endpoint (not /v1/chat/completions or other variants).
    See docs/RUNTIME_CONFIG.md for endpoint documentation.
    """
    mock_response = {
        "content": json.dumps(
            {
                "risk_score": 50,
                "risk_level": "medium",
                "summary": "Normal activity",
                "reasoning": "Test reasoning",
            }
        )
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_post.return_value = mock_resp

        await analyzer._call_llm(
            camera_name="Front Door",
            start_time="2025-12-23T14:30:00",
            end_time="2025-12-23T14:31:00",
            detections_list="1. 14:30:00 - person",
        )

        # Verify the endpoint path is /completion (llama.cpp completion API)
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        url = call_args[0][0]  # First positional argument is the URL
        assert url.endswith("/completion"), (
            f"Expected URL to end with '/completion', got: {url}. "
            "The Nemotron analyzer should use the llama.cpp /completion endpoint."
        )


@pytest.mark.asyncio
async def test_call_llm_empty_content(analyzer):
    """Test LLM call with empty content raises ValueError."""
    mock_response = {"content": ""}

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock(spec=httpx.Response)
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
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(spec=httpx.Request), response=mock_resp
        )
        mock_post.return_value = mock_resp

        with pytest.raises(httpx.HTTPStatusError):
            await analyzer._call_llm(
                camera_name="Front Door",
                start_time="2025-12-23T14:30:00",
                end_time="2025-12-23T14:31:00",
                detections_list="1. 14:30:00 - person",
            )


# Test: Analyze Batch (Unit tests - no DB)


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


# Test: Broadcast Event


@pytest.mark.asyncio
async def test_broadcast_event(analyzer, mock_redis_client):
    """Test event broadcasting via EventBroadcaster.

    Verifies that events are published via EventBroadcaster.broadcast_event()
    with the standard message envelope format: {"type": "event", "data": {...}}.
    """
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

    # Mock the EventBroadcaster.broadcast_event method
    mock_broadcaster = MagicMock()
    mock_broadcaster.broadcast_event = AsyncMock()

    with patch(
        "backend.services.event_broadcaster.get_broadcaster",
        new=AsyncMock(return_value=mock_broadcaster),
    ):
        await analyzer._broadcast_event(event)

    # Verify broadcast_event was called
    mock_broadcaster.broadcast_event.assert_called_once()
    call_args = mock_broadcaster.broadcast_event.call_args

    # Verify message envelope format: {"type": "event", "data": {...}}
    message = call_args[0][0]
    assert message["type"] == "event"
    assert "data" in message
    data = message["data"]
    assert data["id"] == 1
    assert data["event_id"] == 1  # Legacy field for compatibility
    assert data["risk_score"] == 75
    assert data["risk_level"] == "high"


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


# Test: Fast Path Analysis (Unit tests - no DB)


@pytest.mark.asyncio
async def test_analyze_detection_fast_path_no_redis_client(analyzer):
    """Test fast path analysis raises error when Redis client not initialized."""
    analyzer._redis = None

    with pytest.raises(RuntimeError, match="Redis client not initialized"):
        await analyzer.analyze_detection_fast_path("front_door", "123")


@pytest.mark.asyncio
async def test_analyze_detection_fast_path_invalid_detection_id(analyzer, mock_redis_client):
    """Test fast path analysis raises error for invalid detection ID."""
    with pytest.raises(ValueError, match="Invalid detection_id"):
        await analyzer.analyze_detection_fast_path("front_door", "not_a_number")


# =============================================================================
# Test: Full analyze_batch Integration (with mocked DB/LLM)
# =============================================================================


@pytest.fixture
def mock_camera():
    """Create a mock camera for testing."""
    from backend.models.camera import Camera

    return Camera(
        id="front_door",
        name="Front Door Camera",
        folder_path="/export/foscam/front_door",
        status="online",
    )


@pytest.fixture
def mock_detections_for_batch():
    """Create mock detections for batch analysis."""
    from datetime import UTC

    from backend.models.detection import Detection

    base_time = datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC)
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
            detected_at=datetime(2025, 12, 23, 14, 30, 15, tzinfo=UTC),
            object_type="car",
            confidence=0.88,
        ),
    ]


@pytest.fixture
def mock_llm_response():
    """Create a mock LLM response."""
    return {
        "risk_score": 75,
        "risk_level": "high",
        "summary": "Suspicious activity detected near front door",
        "reasoning": "Person detected at unusual time with vehicle present",
    }


@pytest.mark.asyncio
async def test_analyze_batch_success(
    analyzer, mock_redis_client, mock_camera, mock_detections_for_batch, mock_llm_response
):
    """Test successful batch analysis with mocked database and LLM."""
    batch_id = "batch_test_123"
    camera_id = "front_door"
    detection_ids = [1, 2]

    # Mock database session
    mock_session = AsyncMock()

    # Mock camera query result
    mock_camera_result = MagicMock()
    mock_camera_result.scalar_one_or_none.return_value = mock_camera

    # Mock detections query result
    mock_detections_result = MagicMock()
    mock_detections_scalars = MagicMock()
    mock_detections_scalars.all.return_value = mock_detections_for_batch
    mock_detections_result.scalars.return_value = mock_detections_scalars

    # Configure mock session to return appropriate results based on query
    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_camera_result
        else:
            return mock_detections_result

    mock_session.execute = mock_execute
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    # Mock the event broadcaster
    mock_broadcaster = MagicMock()
    mock_broadcaster.broadcast_event = AsyncMock()

    # Mock LLM call
    async def mock_call_llm(*args, **kwargs):
        return mock_llm_response

    with (
        patch("backend.services.nemotron_analyzer.get_session") as mock_get_session,
        patch.object(analyzer, "_call_llm", side_effect=mock_call_llm),
        patch(
            "backend.services.event_broadcaster.get_broadcaster",
            new=AsyncMock(return_value=mock_broadcaster),
        ),
    ):
        # Create async context manager mock
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = None
        mock_get_session.return_value = mock_context

        event = await analyzer.analyze_batch(
            batch_id=batch_id, camera_id=camera_id, detection_ids=detection_ids
        )

    # Verify event was created with correct properties
    assert event.batch_id == batch_id
    assert event.camera_id == camera_id
    assert event.risk_score == 75
    assert event.risk_level == "high"
    assert "Suspicious activity" in event.summary
    assert event.reviewed is False

    # Verify session operations were called
    # Event + EventAudit are both added, committed, and refreshed
    assert mock_session.add.call_count == 2  # Event and EventAudit
    assert mock_session.commit.await_count == 2  # Commit for Event and EventAudit
    assert mock_session.refresh.await_count == 2  # Refresh for Event and EventAudit


@pytest.mark.asyncio
async def test_analyze_batch_llm_failure_fallback(
    analyzer, mock_redis_client, mock_camera, mock_detections_for_batch
):
    """Test batch analysis falls back to default risk when LLM fails."""
    batch_id = "batch_test_456"
    camera_id = "front_door"
    detection_ids = [1, 2]

    # Mock database session
    mock_session = AsyncMock()

    # Mock camera query result
    mock_camera_result = MagicMock()
    mock_camera_result.scalar_one_or_none.return_value = mock_camera

    # Mock detections query result
    mock_detections_result = MagicMock()
    mock_detections_scalars = MagicMock()
    mock_detections_scalars.all.return_value = mock_detections_for_batch
    mock_detections_result.scalars.return_value = mock_detections_scalars

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_camera_result
        else:
            return mock_detections_result

    mock_session.execute = mock_execute
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    # Mock the event broadcaster
    mock_broadcaster = MagicMock()
    mock_broadcaster.broadcast_event = AsyncMock()

    # Mock LLM call to fail
    async def mock_call_llm_fail(*args, **kwargs):
        raise httpx.ConnectError("LLM service unavailable")

    with (
        patch("backend.services.nemotron_analyzer.get_session") as mock_get_session,
        patch.object(analyzer, "_call_llm", side_effect=mock_call_llm_fail),
        patch(
            "backend.services.event_broadcaster.get_broadcaster",
            new=AsyncMock(return_value=mock_broadcaster),
        ),
    ):
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = None
        mock_get_session.return_value = mock_context

        event = await analyzer.analyze_batch(
            batch_id=batch_id, camera_id=camera_id, detection_ids=detection_ids
        )

    # Verify fallback risk values were used
    assert event.risk_score == 50
    assert event.risk_level == "medium"
    assert "Analysis unavailable" in event.summary
    assert "service error" in event.reasoning


@pytest.mark.asyncio
async def test_analyze_batch_no_detections_in_db(analyzer, mock_redis_client, mock_camera):
    """Test batch analysis raises error when no detections found in database."""
    batch_id = "batch_no_detections"
    camera_id = "front_door"
    detection_ids = [99, 100]  # IDs that don't exist

    # Mock database session
    mock_session = AsyncMock()

    # Mock camera query result
    mock_camera_result = MagicMock()
    mock_camera_result.scalar_one_or_none.return_value = mock_camera

    # Mock detections query - return empty
    mock_detections_result = MagicMock()
    mock_detections_scalars = MagicMock()
    mock_detections_scalars.all.return_value = []
    mock_detections_result.scalars.return_value = mock_detections_scalars

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_camera_result
        else:
            return mock_detections_result

    mock_session.execute = mock_execute

    with patch("backend.services.nemotron_analyzer.get_session") as mock_get_session:
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = None
        mock_get_session.return_value = mock_context

        with pytest.raises(ValueError, match="No detections found"):
            await analyzer.analyze_batch(
                batch_id=batch_id, camera_id=camera_id, detection_ids=detection_ids
            )


@pytest.mark.asyncio
async def test_analyze_batch_invalid_detection_ids(analyzer, mock_redis_client, mock_camera):
    """Test batch analysis raises error when detection IDs are invalid (non-numeric)."""
    batch_id = "batch_invalid_ids"
    camera_id = "front_door"
    detection_ids = ["abc", "def"]  # Invalid non-numeric IDs

    # Mock database session
    mock_session = AsyncMock()

    # Mock camera query result
    mock_camera_result = MagicMock()
    mock_camera_result.scalar_one_or_none.return_value = mock_camera

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        return mock_camera_result

    mock_session.execute = mock_execute

    with patch("backend.services.nemotron_analyzer.get_session") as mock_get_session:
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = None
        mock_get_session.return_value = mock_context

        with pytest.raises(ValueError, match="Invalid detection_id"):
            await analyzer.analyze_batch(
                batch_id=batch_id, camera_id=camera_id, detection_ids=detection_ids
            )


@pytest.mark.asyncio
async def test_analyze_batch_broadcast_failure_continues(
    analyzer, mock_redis_client, mock_camera, mock_detections_for_batch, mock_llm_response
):
    """Test that broadcast failure does not prevent event creation."""
    batch_id = "batch_broadcast_fail"
    camera_id = "front_door"
    detection_ids = [1, 2]

    mock_session = AsyncMock()

    mock_camera_result = MagicMock()
    mock_camera_result.scalar_one_or_none.return_value = mock_camera

    mock_detections_result = MagicMock()
    mock_detections_scalars = MagicMock()
    mock_detections_scalars.all.return_value = mock_detections_for_batch
    mock_detections_result.scalars.return_value = mock_detections_scalars

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_camera_result
        else:
            return mock_detections_result

    mock_session.execute = mock_execute
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    # Mock broadcaster to fail
    mock_broadcaster = MagicMock()
    mock_broadcaster.broadcast_event = AsyncMock(side_effect=Exception("Broadcast failed"))

    async def mock_call_llm(*args, **kwargs):
        return mock_llm_response

    with (
        patch("backend.services.nemotron_analyzer.get_session") as mock_get_session,
        patch.object(analyzer, "_call_llm", side_effect=mock_call_llm),
        patch(
            "backend.services.event_broadcaster.get_broadcaster",
            new=AsyncMock(return_value=mock_broadcaster),
        ),
    ):
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = None
        mock_get_session.return_value = mock_context

        # Should not raise exception even though broadcast fails
        event = await analyzer.analyze_batch(
            batch_id=batch_id, camera_id=camera_id, detection_ids=detection_ids
        )

    # Event should still be created successfully
    assert event.batch_id == batch_id
    assert event.risk_score == 75


@pytest.mark.asyncio
async def test_analyze_batch_redis_fallback_lookup(analyzer, mock_redis_client):
    """Test batch analysis fetches camera_id from Redis when not provided."""
    batch_id = "batch_redis_lookup"

    # Setup Redis mock to return batch metadata
    async def mock_redis_get(key):
        if "camera_id" in key:
            return "front_door"
        elif "detections" in key:
            return json.dumps([1, 2])
        return None

    mock_redis_client.get.side_effect = mock_redis_get

    # Mock database session
    mock_session = AsyncMock()

    from backend.models.camera import Camera
    from backend.models.detection import Detection

    mock_camera = Camera(
        id="front_door",
        name="Front Door",
        folder_path="/export/foscam/front_door",
        status="online",
    )

    base_time = datetime(2025, 12, 23, 14, 30, 0)
    mock_detections = [
        Detection(
            id=1,
            camera_id="front_door",
            file_path="/export/foscam/front_door/img1.jpg",
            detected_at=base_time,
            object_type="person",
            confidence=0.95,
        ),
    ]

    mock_camera_result = MagicMock()
    mock_camera_result.scalar_one_or_none.return_value = mock_camera

    mock_detections_result = MagicMock()
    mock_detections_scalars = MagicMock()
    mock_detections_scalars.all.return_value = mock_detections
    mock_detections_result.scalars.return_value = mock_detections_scalars

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_camera_result
        else:
            return mock_detections_result

    mock_session.execute = mock_execute
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    mock_broadcaster = MagicMock()
    mock_broadcaster.broadcast_event = AsyncMock()

    mock_llm_response = {
        "risk_score": 50,
        "risk_level": "medium",
        "summary": "Normal activity",
        "reasoning": "No concerns",
    }

    async def mock_call_llm(*args, **kwargs):
        return mock_llm_response

    with (
        patch("backend.services.nemotron_analyzer.get_session") as mock_get_session,
        patch.object(analyzer, "_call_llm", side_effect=mock_call_llm),
        patch(
            "backend.services.event_broadcaster.get_broadcaster",
            new=AsyncMock(return_value=mock_broadcaster),
        ),
    ):
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = None
        mock_get_session.return_value = mock_context

        # Call without camera_id and detection_ids - should fetch from Redis
        event = await analyzer.analyze_batch(batch_id=batch_id)

    assert event.camera_id == "front_door"


# =============================================================================
# Test: Full analyze_detection_fast_path Integration (with mocked DB/LLM)
# =============================================================================


@pytest.mark.asyncio
async def test_analyze_detection_fast_path_success(
    analyzer, mock_redis_client, mock_camera, mock_llm_response
):
    """Test successful fast path analysis with mocked database and LLM."""
    camera_id = "front_door"
    detection_id = 42

    from datetime import UTC

    from backend.models.detection import Detection

    mock_detection = Detection(
        id=42,
        camera_id="front_door",
        file_path="/export/foscam/front_door/alert_img.jpg",
        detected_at=datetime(2025, 12, 23, 14, 45, 0, tzinfo=UTC),
        object_type="person",
        confidence=0.98,
    )

    mock_session = AsyncMock()

    # Mock camera query result
    mock_camera_result = MagicMock()
    mock_camera_result.scalar_one_or_none.return_value = mock_camera

    # Mock detection query result
    mock_detection_result = MagicMock()
    mock_detection_result.scalar_one_or_none.return_value = mock_detection

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_camera_result
        else:
            return mock_detection_result

    mock_session.execute = mock_execute
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    mock_broadcaster = MagicMock()
    mock_broadcaster.broadcast_event = AsyncMock()

    async def mock_call_llm(*args, **kwargs):
        return mock_llm_response

    with (
        patch("backend.services.nemotron_analyzer.get_session") as mock_get_session,
        patch.object(analyzer, "_call_llm", side_effect=mock_call_llm),
        patch(
            "backend.services.event_broadcaster.get_broadcaster",
            new=AsyncMock(return_value=mock_broadcaster),
        ),
    ):
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = None
        mock_get_session.return_value = mock_context

        event = await analyzer.analyze_detection_fast_path(camera_id, detection_id)

    # Verify event was created with correct properties
    assert event.batch_id == f"fast_path_{detection_id}"
    assert event.camera_id == camera_id
    assert event.risk_score == 75
    assert event.risk_level == "high"
    assert event.is_fast_path is True
    assert event.reviewed is False


@pytest.mark.asyncio
async def test_analyze_detection_fast_path_detection_not_found(
    analyzer, mock_redis_client, mock_camera
):
    """Test fast path analysis raises error when detection not found."""
    camera_id = "front_door"
    detection_id = 999  # Non-existent detection

    mock_session = AsyncMock()

    mock_camera_result = MagicMock()
    mock_camera_result.scalar_one_or_none.return_value = mock_camera

    # Detection not found
    mock_detection_result = MagicMock()
    mock_detection_result.scalar_one_or_none.return_value = None

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_camera_result
        else:
            return mock_detection_result

    mock_session.execute = mock_execute

    with patch("backend.services.nemotron_analyzer.get_session") as mock_get_session:
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = None
        mock_get_session.return_value = mock_context

        with pytest.raises(ValueError, match="not found in database"):
            await analyzer.analyze_detection_fast_path(camera_id, detection_id)


@pytest.mark.asyncio
async def test_analyze_detection_fast_path_llm_failure_fallback(
    analyzer, mock_redis_client, mock_camera
):
    """Test fast path analysis falls back to default risk when LLM fails."""
    camera_id = "front_door"
    detection_id = 42

    from datetime import UTC

    from backend.models.detection import Detection

    mock_detection = Detection(
        id=42,
        camera_id="front_door",
        file_path="/export/foscam/front_door/alert_img.jpg",
        detected_at=datetime(2025, 12, 23, 14, 45, 0, tzinfo=UTC),
        object_type="person",
        confidence=0.98,
    )

    mock_session = AsyncMock()

    mock_camera_result = MagicMock()
    mock_camera_result.scalar_one_or_none.return_value = mock_camera

    mock_detection_result = MagicMock()
    mock_detection_result.scalar_one_or_none.return_value = mock_detection

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_camera_result
        else:
            return mock_detection_result

    mock_session.execute = mock_execute
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    mock_broadcaster = MagicMock()
    mock_broadcaster.broadcast_event = AsyncMock()

    async def mock_call_llm_fail(*args, **kwargs):
        raise httpx.TimeoutException("LLM timeout")

    with (
        patch("backend.services.nemotron_analyzer.get_session") as mock_get_session,
        patch.object(analyzer, "_call_llm", side_effect=mock_call_llm_fail),
        patch(
            "backend.services.event_broadcaster.get_broadcaster",
            new=AsyncMock(return_value=mock_broadcaster),
        ),
    ):
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = None
        mock_get_session.return_value = mock_context

        event = await analyzer.analyze_detection_fast_path(camera_id, detection_id)

    # Verify fallback risk values
    assert event.risk_score == 50
    assert event.risk_level == "medium"
    assert "Analysis unavailable" in event.summary
    assert event.is_fast_path is True


@pytest.mark.asyncio
async def test_analyze_detection_fast_path_broadcast_failure_continues(
    analyzer, mock_redis_client, mock_camera, mock_llm_response
):
    """Test that broadcast failure does not prevent fast path event creation."""
    camera_id = "front_door"
    detection_id = 42

    from datetime import UTC

    from backend.models.detection import Detection

    mock_detection = Detection(
        id=42,
        camera_id="front_door",
        file_path="/export/foscam/front_door/alert_img.jpg",
        detected_at=datetime(2025, 12, 23, 14, 45, 0, tzinfo=UTC),
        object_type="person",
        confidence=0.98,
    )

    mock_session = AsyncMock()

    mock_camera_result = MagicMock()
    mock_camera_result.scalar_one_or_none.return_value = mock_camera

    mock_detection_result = MagicMock()
    mock_detection_result.scalar_one_or_none.return_value = mock_detection

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_camera_result
        else:
            return mock_detection_result

    mock_session.execute = mock_execute
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    # Mock broadcaster to fail
    mock_broadcaster = MagicMock()
    mock_broadcaster.broadcast_event = AsyncMock(side_effect=Exception("Broadcast failed"))

    async def mock_call_llm(*args, **kwargs):
        return mock_llm_response

    with (
        patch("backend.services.nemotron_analyzer.get_session") as mock_get_session,
        patch.object(analyzer, "_call_llm", side_effect=mock_call_llm),
        patch(
            "backend.services.event_broadcaster.get_broadcaster",
            new=AsyncMock(return_value=mock_broadcaster),
        ),
    ):
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = None
        mock_get_session.return_value = mock_context

        # Should not raise exception even though broadcast fails
        event = await analyzer.analyze_detection_fast_path(camera_id, detection_id)

    assert event.is_fast_path is True
    assert event.risk_score == 75


@pytest.mark.asyncio
async def test_analyze_detection_fast_path_string_detection_id(
    analyzer, mock_redis_client, mock_camera, mock_llm_response
):
    """Test fast path analysis handles string detection ID correctly."""
    camera_id = "front_door"
    detection_id = "42"  # String that should be converted to int

    from datetime import UTC

    from backend.models.detection import Detection

    mock_detection = Detection(
        id=42,
        camera_id="front_door",
        file_path="/export/foscam/front_door/alert_img.jpg",
        detected_at=datetime(2025, 12, 23, 14, 45, 0, tzinfo=UTC),
        object_type="person",
        confidence=0.98,
    )

    mock_session = AsyncMock()

    mock_camera_result = MagicMock()
    mock_camera_result.scalar_one_or_none.return_value = mock_camera

    mock_detection_result = MagicMock()
    mock_detection_result.scalar_one_or_none.return_value = mock_detection

    call_count = 0

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_camera_result
        else:
            return mock_detection_result

    mock_session.execute = mock_execute
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    mock_broadcaster = MagicMock()
    mock_broadcaster.broadcast_event = AsyncMock()

    async def mock_call_llm(*args, **kwargs):
        return mock_llm_response

    with (
        patch("backend.services.nemotron_analyzer.get_session") as mock_get_session,
        patch.object(analyzer, "_call_llm", side_effect=mock_call_llm),
        patch(
            "backend.services.event_broadcaster.get_broadcaster",
            new=AsyncMock(return_value=mock_broadcaster),
        ),
    ):
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = None
        mock_get_session.return_value = mock_context

        event = await analyzer.analyze_detection_fast_path(camera_id, detection_id)

    assert event.batch_id == "fast_path_42"
    assert event.is_fast_path is True


# =============================================================================
# Test: Additional _call_llm edge cases
# =============================================================================


@pytest.mark.asyncio
async def test_call_llm_invalid_json_in_response(analyzer):
    """Test _call_llm raises error when response contains invalid JSON."""
    mock_response = {"content": "This is not valid JSON at all"}

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_post.return_value = mock_resp

        with pytest.raises(ValueError, match="No JSON found"):
            await analyzer._call_llm(
                camera_name="Front Door",
                start_time="2025-12-23T14:30:00",
                end_time="2025-12-23T14:31:00",
                detections_list="1. 14:30:00 - person",
            )


@pytest.mark.asyncio
async def test_call_llm_timeout(analyzer):
    """Test _call_llm raises timeout exception."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = httpx.ReadTimeout("Read timeout exceeded")

        with pytest.raises(httpx.ReadTimeout):
            await analyzer._call_llm(
                camera_name="Front Door",
                start_time="2025-12-23T14:30:00",
                end_time="2025-12-23T14:31:00",
                detections_list="1. 14:30:00 - person",
            )


@pytest.mark.asyncio
async def test_call_llm_connection_error(analyzer):
    """Test _call_llm raises connection error."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(httpx.ConnectError):
            await analyzer._call_llm(
                camera_name="Front Door",
                start_time="2025-12-23T14:30:00",
                end_time="2025-12-23T14:31:00",
                detections_list="1. 14:30:00 - person",
            )


# =============================================================================
# Test: Additional validation edge cases
# =============================================================================


def test_validate_risk_data_float_score(analyzer):
    """Test validation handles float risk scores."""
    data = {"risk_score": 75.5, "risk_level": "high"}
    result = analyzer._validate_risk_data(data)
    assert result["risk_score"] == 75  # Converted to int


def test_validate_risk_data_string_score_valid(analyzer):
    """Test validation handles valid string risk scores."""
    data = {"risk_score": "80", "risk_level": "high"}
    result = analyzer._validate_risk_data(data)
    assert result["risk_score"] == 80


def test_validate_risk_data_none_score(analyzer):
    """Test validation handles None risk score."""
    data = {"risk_score": None, "risk_level": "medium"}
    result = analyzer._validate_risk_data(data)
    assert result["risk_score"] == 50  # Default


def test_validate_risk_data_uppercase_level(analyzer):
    """Test validation handles uppercase risk levels."""
    data = {"risk_score": 75, "risk_level": "HIGH"}
    result = analyzer._validate_risk_data(data)
    assert result["risk_level"] == "high"


def test_validate_risk_data_critical_boundary(analyzer):
    """Test risk level inference at critical boundary (85)."""
    result = analyzer._validate_risk_data({"risk_score": 85, "risk_level": "invalid"})
    assert result["risk_level"] == "critical"


def test_validate_risk_data_low_boundary(analyzer):
    """Test risk level inference at low boundary (29)."""
    result = analyzer._validate_risk_data({"risk_score": 29, "risk_level": "invalid"})
    assert result["risk_level"] == "low"


def test_validate_risk_data_medium_boundary(analyzer):
    """Test risk level inference at medium boundary (30)."""
    result = analyzer._validate_risk_data({"risk_score": 30, "risk_level": "invalid"})
    assert result["risk_level"] == "medium"


def test_validate_risk_data_high_boundary(analyzer):
    """Test risk level inference at high boundary (60)."""
    result = analyzer._validate_risk_data({"risk_score": 60, "risk_level": "invalid"})
    assert result["risk_level"] == "high"


# =============================================================================
# Test: Parse LLM Response edge cases
# =============================================================================


def test_parse_llm_response_multiple_json_objects(analyzer):
    """Test parsing when multiple JSON objects are present (takes first valid one)."""
    response_text = """
    First some noise: {"other": "data"}

    Then the real response:
    {
      "risk_score": 60,
      "risk_level": "high",
      "summary": "Test summary",
      "reasoning": "Test reasoning"
    }
    """

    result = analyzer._parse_llm_response(response_text)
    assert result["risk_score"] == 60
    assert result["risk_level"] == "high"


def test_parse_llm_response_nested_json(analyzer):
    """Test parsing handles simple nested JSON structures."""
    response_text = """
    {
      "risk_score": 45,
      "risk_level": "medium",
      "summary": "Normal activity",
      "reasoning": "Typical pattern"
    }
    """

    result = analyzer._parse_llm_response(response_text)
    assert result["risk_score"] == 45


# =============================================================================
# Test: _run_enrichment_pipeline shared image and camera_id fix
# =============================================================================


@pytest.mark.asyncio
async def test_run_enrichment_pipeline_sets_shared_image(analyzer):
    """Test that _run_enrichment_pipeline sets images[None] for full-frame analysis.

    This verifies the fix for the enrichment pipeline missing shared image bug.
    The shared image (images[None]) is required for:
    - Vision extraction (Florence-2 attributes)
    - Scene change detection
    - CLIP re-identification
    """
    from datetime import UTC
    from unittest.mock import AsyncMock, MagicMock

    from backend.models.detection import Detection
    from backend.services.enrichment_pipeline import EnrichmentResult

    # Create detections with bounding boxes and file paths
    detections = [
        Detection(
            id=1,
            camera_id="front_door",
            file_path="/export/foscam/front_door/img1.jpg",
            detected_at=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC),
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=100,
            bbox_width=50,
            bbox_height=100,
        ),
        Detection(
            id=2,
            camera_id="front_door",
            file_path="/export/foscam/front_door/img2.jpg",
            detected_at=datetime(2025, 12, 23, 14, 30, 15, tzinfo=UTC),
            object_type="car",
            confidence=0.88,
            bbox_x=200,
            bbox_y=150,
            bbox_width=100,
            bbox_height=60,
        ),
    ]

    # Mock the enrichment pipeline
    mock_pipeline = MagicMock()
    mock_result = EnrichmentResult()
    mock_pipeline.enrich_batch = AsyncMock(return_value=mock_result)

    # Replace the analyzer's pipeline getter
    analyzer._enrichment_pipeline = mock_pipeline

    # Call the method with camera_id
    await analyzer._run_enrichment_pipeline(detections, camera_id="front_door")

    # Verify enrich_batch was called
    mock_pipeline.enrich_batch.assert_called_once()
    call_args = mock_pipeline.enrich_batch.call_args

    # Get the images dict that was passed
    detection_inputs = call_args[0][0]
    images = call_args[0][1]
    kwargs = call_args[1]

    # Verify images[None] is set to first detection's file_path
    assert None in images, "images[None] should be set for shared full-frame image"
    assert images[None] == "/export/foscam/front_door/img1.jpg"

    # Verify individual detection images are also set
    assert images[1] == "/export/foscam/front_door/img1.jpg"
    assert images[2] == "/export/foscam/front_door/img2.jpg"

    # Verify camera_id is passed
    assert kwargs.get("camera_id") == "front_door"

    # Verify detection inputs were created correctly
    assert len(detection_inputs) == 2
    assert detection_inputs[0].id == 1
    assert detection_inputs[0].class_name == "person"
    assert detection_inputs[1].id == 2
    assert detection_inputs[1].class_name == "car"


@pytest.mark.asyncio
async def test_run_enrichment_pipeline_passes_camera_id(analyzer):
    """Test that _run_enrichment_pipeline passes camera_id to enrich_batch.

    This is required for scene change detection and re-identification to work.
    """
    from datetime import UTC
    from unittest.mock import AsyncMock, MagicMock

    from backend.models.detection import Detection
    from backend.services.enrichment_pipeline import EnrichmentResult

    detections = [
        Detection(
            id=1,
            camera_id="backyard",
            file_path="/export/foscam/backyard/img1.jpg",
            detected_at=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC),
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=100,
            bbox_width=50,
            bbox_height=100,
        ),
    ]

    mock_pipeline = MagicMock()
    mock_result = EnrichmentResult()
    mock_pipeline.enrich_batch = AsyncMock(return_value=mock_result)
    analyzer._enrichment_pipeline = mock_pipeline

    # Call with camera_id
    await analyzer._run_enrichment_pipeline(detections, camera_id="backyard")

    # Verify camera_id was passed as keyword argument
    call_kwargs = mock_pipeline.enrich_batch.call_args[1]
    assert call_kwargs["camera_id"] == "backyard"


@pytest.mark.asyncio
async def test_run_enrichment_pipeline_no_detections_with_bbox(analyzer):
    """Test that pipeline returns None when no detections have bounding boxes."""
    from datetime import UTC

    from backend.models.detection import Detection

    # Detections without bounding boxes
    detections = [
        Detection(
            id=1,
            camera_id="front_door",
            file_path="/export/foscam/front_door/img1.jpg",
            detected_at=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC),
            object_type="person",
            confidence=0.95,
            # No bbox_x, bbox_y, etc.
        ),
    ]

    result = await analyzer._run_enrichment_pipeline(detections, camera_id="front_door")

    # Should return None since no detections have valid bboxes
    assert result is None


@pytest.mark.asyncio
async def test_run_enrichment_pipeline_empty_detections(analyzer):
    """Test that pipeline returns None for empty detection list."""
    result = await analyzer._run_enrichment_pipeline([], camera_id="front_door")
    assert result is None


@pytest.mark.asyncio
async def test_run_enrichment_pipeline_no_file_path_for_shared_image(analyzer):
    """Test handling when first detection has no file_path."""
    from datetime import UTC
    from unittest.mock import AsyncMock, MagicMock

    from backend.models.detection import Detection
    from backend.services.enrichment_pipeline import EnrichmentResult

    detections = [
        Detection(
            id=1,
            camera_id="front_door",
            file_path=None,  # No file path!
            detected_at=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC),
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=100,
            bbox_width=50,
            bbox_height=100,
        ),
        Detection(
            id=2,
            camera_id="front_door",
            file_path="/export/foscam/front_door/img2.jpg",
            detected_at=datetime(2025, 12, 23, 14, 30, 15, tzinfo=UTC),
            object_type="car",
            confidence=0.88,
            bbox_x=200,
            bbox_y=150,
            bbox_width=100,
            bbox_height=60,
        ),
    ]

    mock_pipeline = MagicMock()
    mock_result = EnrichmentResult()
    mock_pipeline.enrich_batch = AsyncMock(return_value=mock_result)
    analyzer._enrichment_pipeline = mock_pipeline

    await analyzer._run_enrichment_pipeline(detections, camera_id="front_door")

    # Get images dict
    images = mock_pipeline.enrich_batch.call_args[0][1]

    # images[None] should NOT be set since first detection has no file_path
    assert None not in images or images.get(None) is None

    # But the second detection's image should still be mapped
    assert images.get(2) == "/export/foscam/front_door/img2.jpg"


# =============================================================================
# Test: EnrichmentPipeline Integration in analyze_batch (bead z1zt)
# =============================================================================


@pytest.mark.asyncio
async def test_analyze_batch_calls_enrichment_pipeline(analyzer, mock_redis_client, mock_camera):
    """Test that analyze_batch calls _get_enrichment_result with correct parameters.

    This verifies the EnrichmentPipeline is wired into the batch processing flow.
    """
    import json
    from datetime import UTC
    from unittest.mock import AsyncMock, patch

    from backend.models.detection import Detection
    from backend.services.enrichment_pipeline import EnrichmentResult

    batch_id = "test_batch_enrichment"
    camera_id = mock_camera.id
    detection_ids = [1001, 1002]

    # Create sample detections
    detections = [
        Detection(
            id=1001,
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/img1.jpg",
            detected_at=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC),
            object_type="person",
            confidence=0.95,
            bbox_x=100,
            bbox_y=100,
            bbox_width=50,
            bbox_height=100,
        ),
        Detection(
            id=1002,
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/img2.jpg",
            detected_at=datetime(2025, 12, 23, 14, 30, 15, tzinfo=UTC),
            object_type="car",
            confidence=0.88,
            bbox_x=200,
            bbox_y=150,
            bbox_width=100,
            bbox_height=60,
        ),
    ]

    # Mock enrichment result
    mock_enrichment_result = EnrichmentResult(
        license_plates=[],
        faces=[],
        processing_time_ms=50.0,
    )

    # Track calls to _get_enrichment_result
    enrichment_calls = []

    async def tracked_get_enrichment(*args, **kwargs):
        enrichment_calls.append((args, kwargs))
        return mock_enrichment_result

    analyzer._get_enrichment_result = tracked_get_enrichment

    # Mock database and LLM
    mock_llm_response = {
        "content": json.dumps(
            {
                "risk_score": 50,
                "risk_level": "medium",
                "summary": "Test summary",
                "reasoning": "Test reasoning",
            }
        )
    }

    with (
        patch("backend.services.nemotron_analyzer.get_session") as mock_get_session,
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(analyzer, "_get_enriched_context", return_value=None),
        patch.object(analyzer, "_broadcast_event", return_value=None),
    ):
        # Mock database session
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_get_session.return_value = mock_session

        # Mock camera query
        mock_camera_result = MagicMock()
        mock_camera_result.scalar_one_or_none.return_value = mock_camera

        # Mock detections query
        mock_det_result = MagicMock()
        mock_det_scalars = MagicMock()
        mock_det_scalars.all.return_value = detections
        mock_det_result.scalars.return_value = mock_det_scalars

        # Setup execute to return camera first, then detections
        mock_session.execute = AsyncMock(side_effect=[mock_camera_result, mock_det_result])
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        # Mock LLM response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_llm_response
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        # Call analyze_batch
        event = await analyzer.analyze_batch(
            batch_id=batch_id,
            camera_id=camera_id,
            detection_ids=detection_ids,
        )

    # Verify _get_enrichment_result was called
    assert len(enrichment_calls) == 1, "_get_enrichment_result should be called once"
    call_args, call_kwargs = enrichment_calls[0]

    # Verify batch_id was passed
    assert call_args[0] == batch_id

    # Verify detections were passed
    assert len(call_args[1]) == 2

    # Verify camera_id was passed
    assert call_kwargs.get("camera_id") == camera_id

    # Verify event was created
    assert event is not None
    assert event.risk_score == 50


@pytest.mark.asyncio
async def test_analyze_batch_handles_enrichment_failure_gracefully(
    analyzer, mock_redis_client, mock_camera
):
    """Test that analyze_batch continues when enrichment pipeline fails.

    If enrichment fails, the analyzer should still send to Nemotron with None
    enrichment and complete successfully. The _get_enrichment_result method
    catches exceptions from _run_enrichment_pipeline and returns None.
    """
    import json
    from datetime import UTC
    from unittest.mock import AsyncMock, patch

    from backend.models.detection import Detection

    batch_id = "test_batch_enrichment_fail"
    camera_id = mock_camera.id
    detection_ids = [2001, 2002]

    detections = [
        Detection(
            id=2001,
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/img1.jpg",
            detected_at=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC),
            object_type="person",
            confidence=0.95,
        ),
        Detection(
            id=2002,
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/img2.jpg",
            detected_at=datetime(2025, 12, 23, 14, 30, 15, tzinfo=UTC),
            object_type="car",
            confidence=0.88,
        ),
    ]

    # Make _run_enrichment_pipeline fail - _get_enrichment_result should catch it
    async def failing_pipeline(*args, **kwargs):
        raise RuntimeError("Enrichment pipeline failed")

    analyzer._run_enrichment_pipeline = failing_pipeline

    mock_llm_response = {
        "content": json.dumps(
            {
                "risk_score": 45,
                "risk_level": "medium",
                "summary": "Test without enrichment",
                "reasoning": "Enrichment failed but analysis continues",
            }
        )
    }

    with (
        patch("backend.services.nemotron_analyzer.get_session") as mock_get_session,
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(analyzer, "_get_enriched_context", return_value=None),
        patch.object(analyzer, "_broadcast_event", return_value=None),
    ):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_get_session.return_value = mock_session

        mock_camera_result = MagicMock()
        mock_camera_result.scalar_one_or_none.return_value = mock_camera

        mock_det_result = MagicMock()
        mock_det_scalars = MagicMock()
        mock_det_scalars.all.return_value = detections
        mock_det_result.scalars.return_value = mock_det_scalars

        mock_session.execute = AsyncMock(side_effect=[mock_camera_result, mock_det_result])
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_llm_response
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        # Should complete successfully despite enrichment failure
        event = await analyzer.analyze_batch(
            batch_id=batch_id,
            camera_id=camera_id,
            detection_ids=detection_ids,
        )

    # Event should still be created
    assert event is not None
    assert event.risk_score == 45


@pytest.mark.asyncio
async def test_analyze_batch_skips_enrichment_when_disabled(mock_redis_client, mock_settings):
    """Test that analyze_batch skips enrichment when use_enrichment_pipeline=False."""
    import json
    from datetime import UTC
    from unittest.mock import AsyncMock, MagicMock, patch

    from backend.models.camera import Camera
    from backend.models.detection import Detection

    # Create analyzer with enrichment disabled
    with (
        patch("backend.services.nemotron_analyzer.get_settings", return_value=mock_settings),
        patch("backend.services.severity.get_settings", return_value=mock_settings),
    ):
        from backend.services.severity import reset_severity_service

        reset_severity_service()
        analyzer = NemotronAnalyzer(
            redis_client=mock_redis_client,
            use_enrichment_pipeline=False,  # Disabled!
        )

    batch_id = "test_batch_no_enrichment"
    camera_id = "test_camera_no_enrich"
    detection_ids = [3001, 3002]

    mock_camera = Camera(id=camera_id, name="Test Camera", folder_path="/export/foscam/test")

    detections = [
        Detection(
            id=3001,
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/img1.jpg",
            detected_at=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC),
            object_type="person",
            confidence=0.95,
        ),
        Detection(
            id=3002,
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/img2.jpg",
            detected_at=datetime(2025, 12, 23, 14, 30, 15, tzinfo=UTC),
            object_type="car",
            confidence=0.88,
        ),
    ]

    # Track if _run_enrichment_pipeline is called
    pipeline_called = []

    async def tracked_pipeline(*args, **kwargs):
        pipeline_called.append(True)

    analyzer._run_enrichment_pipeline = tracked_pipeline

    mock_llm_response = {
        "content": json.dumps(
            {
                "risk_score": 40,
                "risk_level": "medium",
                "summary": "Test without enrichment",
                "reasoning": "Enrichment disabled",
            }
        )
    }

    with (
        patch("backend.services.nemotron_analyzer.get_session") as mock_get_session,
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(analyzer, "_get_enriched_context", return_value=None),
        patch.object(analyzer, "_broadcast_event", return_value=None),
    ):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_get_session.return_value = mock_session

        mock_camera_result = MagicMock()
        mock_camera_result.scalar_one_or_none.return_value = mock_camera

        mock_det_result = MagicMock()
        mock_det_scalars = MagicMock()
        mock_det_scalars.all.return_value = detections
        mock_det_result.scalars.return_value = mock_det_scalars

        mock_session.execute = AsyncMock(side_effect=[mock_camera_result, mock_det_result])
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_llm_response
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        event = await analyzer.analyze_batch(
            batch_id=batch_id,
            camera_id=camera_id,
            detection_ids=detection_ids,
        )

    # Enrichment pipeline should NOT have been called
    assert len(pipeline_called) == 0, "Enrichment pipeline should not be called when disabled"

    # Event should still be created
    assert event is not None


@pytest.mark.asyncio
async def test_get_enrichment_result_returns_none_on_failure(analyzer):
    """Test that _get_enrichment_result returns None on pipeline failure."""
    from datetime import UTC

    from backend.models.detection import Detection

    detections = [
        Detection(
            id=4001,
            camera_id="test",
            file_path="/export/foscam/test/img1.jpg",
            detected_at=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC),
            object_type="person",
            confidence=0.95,
        ),
    ]

    # Make _run_enrichment_pipeline raise an exception
    async def failing_pipeline(*args, **kwargs):
        raise RuntimeError("Pipeline failed")

    analyzer._run_enrichment_pipeline = failing_pipeline

    # Should return None, not raise
    result = await analyzer._get_enrichment_result(
        batch_id="test",
        detections=detections,
        camera_id="test",
    )

    assert result is None


@pytest.mark.asyncio
async def test_get_enrichment_result_returns_none_when_disabled(analyzer):
    """Test that _get_enrichment_result returns None when enrichment is disabled."""
    from datetime import UTC

    from backend.models.detection import Detection

    # Disable enrichment
    analyzer._use_enrichment_pipeline = False

    detections = [
        Detection(
            id=5001,
            camera_id="test",
            file_path="/export/foscam/test/img1.jpg",
            detected_at=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC),
            object_type="person",
            confidence=0.95,
        ),
    ]

    result = await analyzer._get_enrichment_result(
        batch_id="test",
        detections=detections,
        camera_id="test",
    )

    assert result is None


@pytest.mark.asyncio
async def test_analyze_batch_passes_enrichment_to_call_llm(
    analyzer, mock_redis_client, mock_camera
):
    """Test that analyze_batch passes enrichment result to _call_llm."""
    from datetime import UTC
    from unittest.mock import AsyncMock, MagicMock, patch

    from backend.models.detection import Detection
    from backend.services.enrichment_pipeline import (
        BoundingBox,
        EnrichmentResult,
        LicensePlateResult,
    )

    batch_id = "test_batch_enrichment_to_llm"
    camera_id = mock_camera.id
    detection_ids = [6001, 6002]

    detections = [
        Detection(
            id=6001,
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/img1.jpg",
            detected_at=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC),
            object_type="person",
            confidence=0.95,
        ),
        Detection(
            id=6002,
            camera_id=camera_id,
            file_path=f"/export/foscam/{camera_id}/img2.jpg",
            detected_at=datetime(2025, 12, 23, 14, 30, 15, tzinfo=UTC),
            object_type="car",
            confidence=0.88,
        ),
    ]

    # Create enrichment result with license plate
    mock_enrichment_result = EnrichmentResult(
        license_plates=[
            LicensePlateResult(
                bbox=BoundingBox(x1=100, y1=100, x2=200, y2=150),
                text="ABC123",
                confidence=0.95,
                ocr_confidence=0.90,
            )
        ],
        faces=[],
        processing_time_ms=75.0,
    )

    # Track _call_llm calls
    call_llm_calls = []

    async def tracked_call_llm(*args, **kwargs):
        call_llm_calls.append(kwargs)
        return {
            "risk_score": 55,
            "risk_level": "medium",
            "summary": "Vehicle with plate detected",
            "reasoning": "License plate ABC123 identified",
        }

    analyzer._call_llm = tracked_call_llm
    analyzer._get_enrichment_result = AsyncMock(return_value=mock_enrichment_result)

    with (
        patch("backend.services.nemotron_analyzer.get_session") as mock_get_session,
        patch.object(analyzer, "_get_enriched_context", return_value=None),
        patch.object(analyzer, "_broadcast_event", return_value=None),
    ):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_get_session.return_value = mock_session

        mock_camera_result = MagicMock()
        mock_camera_result.scalar_one_or_none.return_value = mock_camera

        mock_det_result = MagicMock()
        mock_det_scalars = MagicMock()
        mock_det_scalars.all.return_value = detections
        mock_det_result.scalars.return_value = mock_det_scalars

        mock_session.execute = AsyncMock(side_effect=[mock_camera_result, mock_det_result])
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        event = await analyzer.analyze_batch(
            batch_id=batch_id,
            camera_id=camera_id,
            detection_ids=detection_ids,
        )

    # Verify _call_llm was called with enrichment_result
    assert len(call_llm_calls) == 1
    llm_kwargs = call_llm_calls[0]
    assert "enrichment_result" in llm_kwargs
    assert llm_kwargs["enrichment_result"] is mock_enrichment_result
    assert llm_kwargs["enrichment_result"].has_license_plates

    # Event should be created with correct risk score
    assert event is not None
    assert event.risk_score == 55
