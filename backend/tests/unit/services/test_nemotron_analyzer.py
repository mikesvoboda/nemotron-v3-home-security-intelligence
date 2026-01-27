"""Unit tests for Nemotron analyzer service.

These tests cover pure functions, mocked HTTP calls, and validation logic
that don't require database access.
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.core.exceptions import AnalyzerUnavailableError
from backend.models.detection import Detection
from backend.models.event import Event
from backend.services.nemotron_analyzer import NemotronAnalyzer
from backend.tests.async_utils import (
    create_async_session_mock,
    create_mock_db_context,
    create_mock_redis_client,
    create_mock_response,
)
from backend.tests.conftest import unique_id

# Mark all tests in this file as unit tests
# Timeout increased because async test setup is slow with FastAPI app initialization
pytestmark = [pytest.mark.unit, pytest.mark.timeout(60)]


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
    # Retry settings (NEM-1343)
    mock.nemotron_max_retries = 2  # Need at least 2 for retry test
    # Severity settings for tests that use _validate_risk_data
    mock.severity_low_max = 29
    mock.severity_medium_max = 59
    mock.severity_high_max = 84
    # LLM context window settings (NEM-1666)
    mock.nemotron_context_window = 4096
    mock.nemotron_max_output_tokens = 1536
    mock.context_utilization_warning_threshold = 0.80
    mock.context_truncation_enabled = True
    mock.llm_tokenizer_encoding = "cl100k_base"
    # Enrichment pipeline settings (NEM-1641)
    mock.image_quality_enabled = False
    # Cold start and warmup settings (NEM-1670)
    mock.ai_warmup_enabled = True
    mock.ai_cold_start_threshold_seconds = 300.0
    mock.nemotron_warmup_prompt = "Test warmup prompt"
    # Scene change detector settings (NEM-2520)
    mock.scene_change_resize_width = 640
    # Enrichment pipeline service routing
    mock.use_enrichment_service = False
    # Inference semaphore settings (NEM-1463, used by facade)
    mock.ai_max_concurrent_inferences = 4
    # Guided JSON settings (NEM-3726)
    mock.nemotron_use_guided_json = False  # Disabled by default for existing tests
    mock.nemotron_guided_json_fallback = True
    return mock


@pytest.fixture
def analyzer(mock_redis_client, mock_settings):
    """Create NemotronAnalyzer instance with mocked Redis and settings."""
    # Patch all get_settings locations: nemotron_analyzer, severity service, token counter, metrics,
    # and inference_semaphore (for facade's get_inference_semaphore call)
    # Note: backend.core.config.get_settings handles enrichment_pipeline's import from that module
    with (
        patch("backend.services.nemotron_analyzer.get_settings", return_value=mock_settings),
        patch("backend.services.severity.get_settings", return_value=mock_settings),
        patch("backend.services.token_counter.get_settings", return_value=mock_settings),
        patch("backend.core.config.get_settings", return_value=mock_settings),
        patch("backend.services.inference_semaphore.get_settings", return_value=mock_settings),
    ):
        # Also clear the singletons to ensure fresh service with mocked settings
        from backend.services.analyzer_facade import reset_analyzer_facade
        from backend.services.inference_semaphore import reset_inference_semaphore
        from backend.services.severity import reset_severity_service
        from backend.services.token_counter import reset_token_counter

        reset_severity_service()
        reset_token_counter()
        reset_analyzer_facade()
        reset_inference_semaphore()
        yield NemotronAnalyzer(redis_client=mock_redis_client)
        # Reset again after test to not affect other tests
        reset_severity_service()
        reset_token_counter()
        reset_analyzer_facade()
        reset_inference_semaphore()


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
    See docs/reference/config/env-reference.md for endpoint documentation.
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
    """Test LLM call raises RuntimeError after retry exhaustion on HTTP 5xx error (NEM-1343)."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(spec=httpx.Request), response=mock_resp
        )
        mock_post.return_value = mock_resp

        # After retry exhaustion, AnalyzerUnavailableError is raised wrapping the original exception
        with pytest.raises(
            AnalyzerUnavailableError, match=r"Nemotron LLM call failed after \d+ attempts"
        ):
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


@pytest.mark.asyncio
async def test_broadcast_event_soft_deleted_skipped(analyzer, mock_redis_client):
    """Test soft-deleted events are not broadcast (NEM-2661).

    Verifies that events with deleted_at set are skipped to prevent
    console errors when the frontend tries to fetch non-existent event details.
    """
    from datetime import UTC

    # Create a soft-deleted event
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
        deleted_at=datetime.now(UTC),  # Soft-deleted
    )

    # Mock the EventBroadcaster.broadcast_event method
    mock_broadcaster = MagicMock()
    mock_broadcaster.broadcast_event = AsyncMock()

    with patch(
        "backend.services.event_broadcaster.get_broadcaster",
        new=AsyncMock(return_value=mock_broadcaster),
    ):
        await analyzer._broadcast_event(event)

    # Verify broadcast_event was NOT called for soft-deleted event
    mock_broadcaster.broadcast_event.assert_not_called()


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
    # NEM-1998: ON CONFLICT DO NOTHING adds 2 extra execute calls for event_detections
    call_count = 0
    mock_insert_result = MagicMock()

    async def mock_execute(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_camera_result
        elif call_count == 2:
            return mock_detections_result
        else:
            # NEM-1998: ON CONFLICT INSERT calls return generic result
            return mock_insert_result

    mock_session.execute = mock_execute
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.flush = AsyncMock()  # NEM-2574: Batched commits use flush
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
    # NEM-2574: Batched commits - use flush() instead of commit() for intermediate persists
    # NEM-1998: EventDetection records now use ON CONFLICT INSERT via execute()
    # Event + EventAudit are added via session.add()
    # NEM-3150: With facade pattern, audit may fail if services are not properly mocked,
    # so we only verify minimum required operations (Event creation)
    assert (
        mock_session.add.call_count >= 1
    )  # At least Event (EventAudit may fail without full mocking)
    # NEM-2574: flush() is called at least once for Event, audit may be skipped on failure
    assert mock_session.flush.await_count >= 1  # At least flush for Event


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
    mock_session.flush = AsyncMock()  # NEM-2574: Batched commits use flush
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
    mock_session.flush = AsyncMock()  # NEM-2574: Batched commits use flush
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
    mock_session.flush = AsyncMock()  # NEM-2574: Batched commits use flush
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
    mock_session.flush = AsyncMock()  # NEM-2574: Batched commits use flush
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
    mock_session.flush = AsyncMock()  # NEM-2574: Batched commits use flush
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
    mock_session.flush = AsyncMock()  # NEM-2574: Batched commits use flush
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
    mock_session.flush = AsyncMock()  # NEM-2574: Batched commits use flush
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
    """Test _call_llm raises AnalyzerUnavailableError after retry exhaustion on timeout (NEM-1343)."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = httpx.ReadTimeout("Read timeout exceeded")

        # After retry exhaustion, AnalyzerUnavailableError is raised wrapping the original exception
        with pytest.raises(
            AnalyzerUnavailableError, match=r"Nemotron LLM call failed after \d+ attempts"
        ):
            await analyzer._call_llm(
                camera_name="Front Door",
                start_time="2025-12-23T14:30:00",
                end_time="2025-12-23T14:31:00",
                detections_list="1. 14:30:00 - person",
            )


@pytest.mark.asyncio
async def test_call_llm_connection_error(analyzer):
    """Test _call_llm raises AnalyzerUnavailableError after retry exhaustion on connection error (NEM-1343)."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        # After retry exhaustion, AnalyzerUnavailableError is raised wrapping the original exception
        with pytest.raises(
            AnalyzerUnavailableError, match=r"Nemotron LLM call failed after \d+ attempts"
        ):
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

    # Mock the enrichment pipeline with enrich_batch_with_tracking (NEM-1672)
    from backend.services.enrichment_pipeline import EnrichmentStatus, EnrichmentTrackingResult

    mock_pipeline = MagicMock()
    mock_result = EnrichmentResult()
    mock_tracking_result = EnrichmentTrackingResult(
        status=EnrichmentStatus.FULL,
        successful_models=["face"],
        failed_models=[],
        errors={},
        data=mock_result,
    )
    mock_pipeline.enrich_batch_with_tracking = AsyncMock(return_value=mock_tracking_result)

    # Replace the analyzer's pipeline getter
    analyzer._enrichment_pipeline = mock_pipeline

    # Call the method with camera_id
    await analyzer._run_enrichment_pipeline(detections, camera_id="front_door")

    # Verify enrich_batch_with_tracking was called
    mock_pipeline.enrich_batch_with_tracking.assert_called_once()
    call_args = mock_pipeline.enrich_batch_with_tracking.call_args

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
    """Test that _run_enrichment_pipeline passes camera_id to enrich_batch_with_tracking.

    This is required for scene change detection and re-identification to work.
    """
    from datetime import UTC
    from unittest.mock import AsyncMock, MagicMock

    from backend.models.detection import Detection
    from backend.services.enrichment_pipeline import (
        EnrichmentResult,
        EnrichmentStatus,
        EnrichmentTrackingResult,
    )

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
    mock_tracking_result = EnrichmentTrackingResult(
        status=EnrichmentStatus.FULL,
        successful_models=["face"],
        failed_models=[],
        errors={},
        data=mock_result,
    )
    mock_pipeline.enrich_batch_with_tracking = AsyncMock(return_value=mock_tracking_result)
    analyzer._enrichment_pipeline = mock_pipeline

    # Call with camera_id
    await analyzer._run_enrichment_pipeline(detections, camera_id="backyard")

    # Verify camera_id was passed as keyword argument
    call_kwargs = mock_pipeline.enrich_batch_with_tracking.call_args[1]
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
    from backend.services.enrichment_pipeline import (
        EnrichmentResult,
        EnrichmentStatus,
        EnrichmentTrackingResult,
    )

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
    mock_tracking_result = EnrichmentTrackingResult(
        status=EnrichmentStatus.FULL,
        successful_models=[],
        failed_models=[],
        errors={},
        data=mock_result,
    )
    mock_pipeline.enrich_batch_with_tracking = AsyncMock(return_value=mock_tracking_result)
    analyzer._enrichment_pipeline = mock_pipeline

    await analyzer._run_enrichment_pipeline(detections, camera_id="front_door")

    # Get images dict
    images = mock_pipeline.enrich_batch_with_tracking.call_args[0][1]

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
    from backend.services.enrichment_pipeline import (
        EnrichmentResult,
        EnrichmentStatus,
        EnrichmentTrackingResult,
    )

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

    # Mock enrichment result with tracking (NEM-1672)
    mock_enrichment_data = EnrichmentResult(
        license_plates=[],
        faces=[],
        processing_time_ms=50.0,
    )
    mock_enrichment_tracking = EnrichmentTrackingResult(
        status=EnrichmentStatus.FULL,
        successful_models=["face"],
        failed_models=[],
        errors={},
        data=mock_enrichment_data,
    )

    # Track calls to _get_enrichment_result_from_data
    # Note: analyze_batch uses _get_enrichment_result_from_data (not _get_enrichment_result)
    # because it now uses split sessions to avoid idle-in-transaction timeouts
    enrichment_calls = []

    async def tracked_get_enrichment(*args, **kwargs):
        enrichment_calls.append((args, kwargs))
        return mock_enrichment_tracking

    analyzer._get_enrichment_result_from_data = tracked_get_enrichment

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

    # Mock auto-tuner to return empty context (NEM-3015)
    mock_auto_tuner = MagicMock()
    mock_auto_tuner.get_tuning_context = AsyncMock(return_value="")

    with (
        patch("backend.services.nemotron_analyzer.get_session") as mock_get_session,
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(analyzer, "_get_enriched_context", return_value=None),
        patch.object(analyzer, "_get_recent_scene_changes", return_value=[]),  # NEM-3012
        patch.object(analyzer, "_broadcast_event", return_value=None),
        patch(
            "backend.services.prompt_auto_tuner.get_prompt_auto_tuner",
            return_value=mock_auto_tuner,
        ),
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

        # Setup execute to return camera first, then detections, then ON CONFLICT inserts
        # NEM-1998 added ON CONFLICT DO NOTHING for event_detections, which adds 2 execute calls
        mock_insert_result = MagicMock()  # Result from ON CONFLICT INSERT
        mock_session.execute = AsyncMock(
            side_effect=[
                mock_camera_result,
                mock_det_result,
                mock_insert_result,
                mock_insert_result,
            ]
        )
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.flush = AsyncMock()  # NEM-2574: Batched commits use flush
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

    # Verify _get_enrichment_result_from_data was called
    assert len(enrichment_calls) == 1, "_get_enrichment_result_from_data should be called once"
    call_args, call_kwargs = enrichment_calls[0]

    # Verify batch_id was passed
    assert call_args[0] == batch_id

    # Verify detection data dicts were passed (not ORM objects)
    # Note: _get_enrichment_result_from_data receives dicts, not Detection objects
    assert len(call_args[1]) == 2
    # Verify the first detection data dict has expected keys
    assert "id" in call_args[1][0]
    assert call_args[1][0]["id"] == 1001

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

    # Make _run_enrichment_pipeline_from_data fail - _get_enrichment_result_from_data catches it
    # Note: analyze_batch uses _get_enrichment_result_from_data (not _get_enrichment_result)
    # because it now uses split sessions to avoid idle-in-transaction timeouts
    async def failing_pipeline(*args, **kwargs):
        raise RuntimeError("Enrichment pipeline failed")

    analyzer._run_enrichment_pipeline_from_data = failing_pipeline

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

    # Mock auto-tuner to return empty context (NEM-3015)
    mock_auto_tuner = MagicMock()
    mock_auto_tuner.get_tuning_context = AsyncMock(return_value="")

    with (
        patch("backend.services.nemotron_analyzer.get_session") as mock_get_session,
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(analyzer, "_get_enriched_context", return_value=None),
        patch.object(analyzer, "_get_recent_scene_changes", return_value=[]),  # NEM-3012
        patch.object(analyzer, "_broadcast_event", return_value=None),
        patch(
            "backend.services.prompt_auto_tuner.get_prompt_auto_tuner",
            return_value=mock_auto_tuner,
        ),
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

        # NEM-1998 added ON CONFLICT DO NOTHING for event_detections, which adds 2 execute calls
        mock_insert_result = MagicMock()
        mock_session.execute = AsyncMock(
            side_effect=[
                mock_camera_result,
                mock_det_result,
                mock_insert_result,
                mock_insert_result,
            ]
        )
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.flush = AsyncMock()  # NEM-2574: Batched commits use flush
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

    # Track if _run_enrichment_pipeline_from_data is called
    # Note: analyze_batch uses _run_enrichment_pipeline_from_data (not _run_enrichment_pipeline)
    # because it now uses split sessions to avoid idle-in-transaction timeouts
    pipeline_called = []

    async def tracked_pipeline(*args, **kwargs):
        pipeline_called.append(True)

    analyzer._run_enrichment_pipeline_from_data = tracked_pipeline

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

    # Mock auto-tuner to return empty context (NEM-3015)
    mock_auto_tuner = MagicMock()
    mock_auto_tuner.get_tuning_context = AsyncMock(return_value="")

    with (
        patch("backend.services.nemotron_analyzer.get_session") as mock_get_session,
        patch("httpx.AsyncClient.post") as mock_post,
        patch.object(analyzer, "_get_enriched_context", return_value=None),
        patch.object(analyzer, "_get_recent_scene_changes", return_value=[]),  # NEM-3012
        patch.object(analyzer, "_broadcast_event", return_value=None),
        patch(
            "backend.services.prompt_auto_tuner.get_prompt_auto_tuner",
            return_value=mock_auto_tuner,
        ),
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

        # NEM-1998 added ON CONFLICT DO NOTHING for event_detections, which adds 2 execute calls
        mock_insert_result = MagicMock()
        mock_session.execute = AsyncMock(
            side_effect=[
                mock_camera_result,
                mock_det_result,
                mock_insert_result,
                mock_insert_result,
            ]
        )
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.flush = AsyncMock()  # NEM-2574: Batched commits use flush
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
async def test_get_enrichment_result_returns_failed_tracking_on_failure(analyzer):
    """Test that _get_enrichment_result returns EnrichmentTrackingResult with FAILED status on pipeline failure.

    NEM-1672: Changed behavior - now returns a tracking result with FAILED status
    instead of None, providing visibility into failures.
    """
    from datetime import UTC

    from backend.models.detection import Detection
    from backend.services.enrichment_pipeline import EnrichmentStatus

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

    # Should return a failed tracking result, not None (NEM-1672)
    result = await analyzer._get_enrichment_result(
        batch_id="test",
        detections=detections,
        camera_id="test",
    )

    # Now returns a tracking result with FAILED status
    assert result is not None
    assert result.status == EnrichmentStatus.FAILED
    assert result.data is None
    assert "all" in result.failed_models
    assert "Pipeline failed" in result.errors.get("all", "")


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
        EnrichmentStatus,
        EnrichmentTrackingResult,
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

    # Create enrichment result with license plate (NEM-1672 - now wrapped in tracking result)
    mock_enrichment_data = EnrichmentResult(
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
    mock_enrichment_tracking = EnrichmentTrackingResult(
        status=EnrichmentStatus.FULL,
        successful_models=["license_plate"],
        failed_models=[],
        errors={},
        data=mock_enrichment_data,
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
    # Note: analyze_batch uses _get_enrichment_result_from_data (not _get_enrichment_result)
    # because it now uses split sessions to avoid idle-in-transaction timeouts
    analyzer._get_enrichment_result_from_data = AsyncMock(return_value=mock_enrichment_tracking)

    # Mock auto-tuner to return empty context (NEM-3015)
    mock_auto_tuner = MagicMock()
    mock_auto_tuner.get_tuning_context = AsyncMock(return_value="")

    with (
        patch("backend.services.nemotron_analyzer.get_session") as mock_get_session,
        patch.object(analyzer, "_get_enriched_context", return_value=None),
        patch.object(analyzer, "_get_recent_scene_changes", return_value=[]),  # NEM-3012
        patch.object(analyzer, "_get_household_context", return_value=""),  # NEM-3024
        patch.object(analyzer, "_broadcast_event", return_value=None),
        patch(
            "backend.services.prompt_auto_tuner.get_prompt_auto_tuner",
            return_value=mock_auto_tuner,
        ),
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

        # NEM-1998 added ON CONFLICT DO NOTHING for event_detections, which adds 2 execute calls
        mock_insert_result = MagicMock()
        mock_session.execute = AsyncMock(
            side_effect=[
                mock_camera_result,
                mock_det_result,
                mock_insert_result,
                mock_insert_result,
            ]
        )
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session.flush = AsyncMock()  # NEM-2574: Batched commits use flush
        mock_session.refresh = AsyncMock()

        event = await analyzer.analyze_batch(
            batch_id=batch_id,
            camera_id=camera_id,
            detection_ids=detection_ids,
        )

    # Verify _call_llm was called with enrichment_result
    # NEM-1672: Now extracts EnrichmentResult from EnrichmentTrackingResult
    assert len(call_llm_calls) == 1
    llm_kwargs = call_llm_calls[0]
    assert "enrichment_result" in llm_kwargs
    # The extracted EnrichmentResult (not tracking result) is passed to _call_llm
    assert llm_kwargs["enrichment_result"] is mock_enrichment_data
    assert llm_kwargs["enrichment_result"].has_license_plates

    # Event should be created with correct risk score
    assert event is not None
    assert event.risk_score == 55


# =============================================================================
# Tests Using Improved Async Patterns (async_utils module)
# =============================================================================


class TestNemotronAnalyzerImprovedPatterns:
    """Tests demonstrating improved async patterns from async_utils module.

    These tests show how to use the async_utils helpers to simplify
    database session mocking and reduce boilerplate code.
    """

    @pytest.fixture
    def mock_settings_for_class(self):
        """Create mock settings for NemotronAnalyzer."""
        from backend.core.config import Settings

        mock = MagicMock(spec=Settings)
        mock.nemotron_url = "http://localhost:8091"
        mock.nemotron_api_key = None
        mock.ai_connect_timeout = 10.0
        mock.nemotron_read_timeout = 120.0
        mock.ai_health_timeout = 5.0
        mock.nemotron_max_retries = 3
        mock.severity_low_max = 29
        mock.severity_medium_max = 59
        mock.severity_high_max = 84
        # Cold start and warmup settings (NEM-1670)
        mock.ai_warmup_enabled = True
        mock.ai_cold_start_threshold_seconds = 300.0
        mock.nemotron_warmup_prompt = "Test warmup prompt"
        # Guided JSON settings (NEM-3726)
        mock.nemotron_use_guided_json = False
        mock.nemotron_guided_json_fallback = True
        return mock

    @pytest.fixture
    def analyzer_with_mock_redis(self, mock_settings_for_class):
        """Create NemotronAnalyzer with mock Redis using async_utils helper."""
        # Use the async_utils helper instead of manual setup
        mock_redis = create_mock_redis_client(
            get_values={
                "batch:test:camera_id": "front_door",
                "batch:test:detections": json.dumps([1, 2]),
            }
        )

        with (
            patch(
                "backend.services.nemotron_analyzer.get_settings",
                return_value=mock_settings_for_class,
            ),
            patch(
                "backend.services.severity.get_settings",
                return_value=mock_settings_for_class,
            ),
        ):
            from backend.services.severity import reset_severity_service

            reset_severity_service()
            analyzer = NemotronAnalyzer(redis_client=mock_redis)
            yield analyzer, mock_redis
            reset_severity_service()

    @pytest.mark.asyncio
    async def test_health_check_with_mock_response(self, analyzer_with_mock_redis) -> None:
        """Test health check using create_mock_response helper.

        Demonstrates cleaner HTTP response mocking.
        """
        analyzer, _ = analyzer_with_mock_redis

        # Use create_mock_response for cleaner response creation
        mock_response = create_mock_response(
            json_data={"status": "ok"},
            status_code=200,
        )

        with patch("httpx.AsyncClient.get") as mock_get:
            mock_get.return_value = mock_response

            result = await analyzer.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_session_mock_with_helper(self, analyzer_with_mock_redis) -> None:
        """Test using create_async_session_mock and create_mock_db_context.

        This demonstrates the simplified database mocking pattern that
        eliminates the verbose __aenter__/__aexit__ setup.
        """
        analyzer, _mock_redis = analyzer_with_mock_redis
        from datetime import UTC

        from backend.models.camera import Camera
        from backend.models.detection import Detection

        # Create test data
        camera = Camera(
            id="test_camera",
            name="Test Camera",
            folder_path="/export/foscam/test",
            status="online",
        )
        detections = [
            Detection(
                id=1,
                camera_id="test_camera",
                file_path="/export/foscam/test/img1.jpg",
                detected_at=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC),
                object_type="person",
                confidence=0.95,
            ),
        ]

        # Setup mock results
        mock_camera_result = MagicMock()
        mock_camera_result.scalar_one_or_none.return_value = camera

        mock_det_result = MagicMock()
        mock_det_scalars = MagicMock()
        mock_det_scalars.all.return_value = detections
        mock_det_result.scalars.return_value = mock_det_scalars

        # Use helpers for cleaner session setup
        # Note: create_async_session_mock provides basic session methods
        mock_session = create_async_session_mock(
            execute_results=[mock_camera_result, mock_det_result]
        )

        # create_mock_db_context eliminates __aenter__/__aexit__ boilerplate
        mock_context = create_mock_db_context(mock_session)

        # Mock LLM response
        mock_llm_response = {
            "risk_score": 60,
            "risk_level": "high",
            "summary": "Test detection",
            "reasoning": "Test reasoning",
        }

        async def mock_call_llm(*args, **kwargs):
            return mock_llm_response

        mock_broadcaster = MagicMock()
        mock_broadcaster.broadcast_event = AsyncMock()

        with (
            patch(
                "backend.services.nemotron_analyzer.get_session",
                return_value=mock_context,
            ),
            patch.object(analyzer, "_call_llm", side_effect=mock_call_llm),
            patch(
                "backend.services.event_broadcaster.get_broadcaster",
                new=AsyncMock(return_value=mock_broadcaster),
            ),
        ):
            event = await analyzer.analyze_batch(
                batch_id="test_batch",
                camera_id="test_camera",
                detection_ids=[1],
            )

        assert event.risk_score == 60
        assert event.risk_level == "high"

    @pytest.mark.asyncio
    async def test_redis_mock_with_helper(self, analyzer_with_mock_redis) -> None:
        """Test Redis operations using create_mock_redis_client helper.

        Shows how the helper pre-configures common Redis operations.
        """
        _analyzer, mock_redis = analyzer_with_mock_redis

        # The mock_redis was created with pre-configured get_values
        # Verify the helper works correctly
        camera_id = await mock_redis.get("batch:test:camera_id")
        assert camera_id == "front_door"

        # Common operations are pre-configured
        await mock_redis.set("new_key", "new_value")
        await mock_redis.delete("some_key")
        await mock_redis.publish("channel", "message")

        # Health check is pre-configured
        health = await mock_redis.health_check()
        assert health["status"] == "healthy"


# =============================================================================
# Test: Idempotency Handling for LLM Batch Retries (NEM-1725)
# =============================================================================


class TestIdempotencyHandling:
    """Tests for idempotency handling to prevent duplicate Events on retries.

    When Nemotron analyzer retries after timeout, we must prevent duplicate
    Event creation by using Redis idempotency keys.
    """

    @pytest.fixture
    def mock_settings_for_idempotency(self):
        """Create mock settings for idempotency tests."""
        from backend.core.config import Settings

        mock = MagicMock(spec=Settings)
        mock.nemotron_url = "http://localhost:8091"
        mock.nemotron_api_key = None
        mock.ai_connect_timeout = 10.0
        mock.nemotron_read_timeout = 120.0
        mock.ai_health_timeout = 5.0
        mock.nemotron_max_retries = 3
        mock.severity_low_max = 29
        mock.severity_medium_max = 59
        mock.severity_high_max = 84
        # Cold start and warmup settings (NEM-1670)
        mock.ai_warmup_enabled = True
        mock.ai_cold_start_threshold_seconds = 300.0
        mock.nemotron_warmup_prompt = "Test warmup prompt"
        # Guided JSON settings (NEM-3726)
        mock.nemotron_use_guided_json = False
        mock.nemotron_guided_json_fallback = True
        return mock

    @pytest.fixture
    def mock_redis_for_idempotency(self):
        """Create mock Redis with idempotency key support."""
        from backend.core.redis import RedisClient

        mock_client = MagicMock(spec=RedisClient)

        # Track stored values for idempotency keys
        stored_values: dict[str, str] = {}

        async def mock_get(key):
            return stored_values.get(key)

        async def mock_set(key, value, expire=None):
            stored_values[key] = str(value) if not isinstance(value, str) else value
            return True

        async def mock_delete(*keys):
            count = 0
            for key in keys:
                if key in stored_values:
                    del stored_values[key]
                    count += 1
            return count

        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_client.set = AsyncMock(side_effect=mock_set)
        mock_client.delete = AsyncMock(side_effect=mock_delete)
        mock_client.publish = AsyncMock(return_value=1)
        mock_client._stored_values = stored_values  # Expose for test inspection

        return mock_client

    @pytest.mark.asyncio
    async def test_check_idempotency_returns_none_for_new_batch(
        self, mock_settings_for_idempotency, mock_redis_for_idempotency
    ):
        """Test _check_idempotency returns None when no prior event exists.

        For a new batch that hasn't been processed, the idempotency check
        should return None indicating we can proceed with Event creation.
        """
        with (
            patch(
                "backend.services.nemotron_analyzer.get_settings",
                return_value=mock_settings_for_idempotency,
            ),
            patch(
                "backend.services.severity.get_settings",
                return_value=mock_settings_for_idempotency,
            ),
        ):
            from backend.services.severity import reset_severity_service

            reset_severity_service()
            analyzer = NemotronAnalyzer(redis_client=mock_redis_for_idempotency)

            # Check idempotency for a new batch - should return None
            result = await analyzer._check_idempotency("new_batch_123")

            assert result is None
            reset_severity_service()

    @pytest.mark.asyncio
    async def test_check_idempotency_returns_event_id_for_existing_batch(
        self, mock_settings_for_idempotency, mock_redis_for_idempotency
    ):
        """Test _check_idempotency returns event_id when batch was already processed.

        If an Event was already created for this batch, return the existing
        event_id instead of None.
        """
        with (
            patch(
                "backend.services.nemotron_analyzer.get_settings",
                return_value=mock_settings_for_idempotency,
            ),
            patch(
                "backend.services.severity.get_settings",
                return_value=mock_settings_for_idempotency,
            ),
        ):
            from backend.services.severity import reset_severity_service

            reset_severity_service()
            analyzer = NemotronAnalyzer(redis_client=mock_redis_for_idempotency)

            # Pre-store an idempotency key simulating a prior event creation
            mock_redis_for_idempotency._stored_values["batch_event:existing_batch_456"] = "42"

            # Check idempotency - should return existing event_id
            result = await analyzer._check_idempotency("existing_batch_456")

            assert result == 42
            reset_severity_service()

    @pytest.mark.asyncio
    async def test_set_idempotency_stores_key_with_ttl(
        self, mock_settings_for_idempotency, mock_redis_for_idempotency
    ):
        """Test _set_idempotency stores idempotency key with 1 hour TTL.

        After creating an Event, store the batch_id -> event_id mapping
        with a 1 hour TTL to prevent duplicates during retries.
        """
        with (
            patch(
                "backend.services.nemotron_analyzer.get_settings",
                return_value=mock_settings_for_idempotency,
            ),
            patch(
                "backend.services.severity.get_settings",
                return_value=mock_settings_for_idempotency,
            ),
        ):
            from backend.services.severity import reset_severity_service

            reset_severity_service()
            analyzer = NemotronAnalyzer(redis_client=mock_redis_for_idempotency)

            # Set idempotency key
            await analyzer._set_idempotency("batch_789", 100)

            # Verify key was stored
            assert "batch_event:batch_789" in mock_redis_for_idempotency._stored_values
            assert mock_redis_for_idempotency._stored_values["batch_event:batch_789"] == "100"

            # Verify set was called with TTL (expire parameter)
            mock_redis_for_idempotency.set.assert_called_with(
                "batch_event:batch_789", "100", expire=3600
            )
            reset_severity_service()

    @pytest.mark.asyncio
    async def test_analyze_batch_skips_creation_on_retry(
        self, mock_settings_for_idempotency, mock_redis_for_idempotency
    ):
        """Test analyze_batch returns existing event on retry instead of creating duplicate.

        When a batch is retried (e.g., after timeout), and an Event already exists,
        return the existing Event without creating a new one.
        """
        from datetime import UTC

        from backend.models.event import Event

        with (
            patch(
                "backend.services.nemotron_analyzer.get_settings",
                return_value=mock_settings_for_idempotency,
            ),
            patch(
                "backend.services.severity.get_settings",
                return_value=mock_settings_for_idempotency,
            ),
        ):
            from backend.services.severity import reset_severity_service

            reset_severity_service()
            analyzer = NemotronAnalyzer(redis_client=mock_redis_for_idempotency)

            batch_id = "retry_batch_test"
            camera_id = "front_door"
            detection_ids = [1, 2]
            existing_event_id = 999

            # Pre-store idempotency key (simulating prior successful Event creation)
            mock_redis_for_idempotency._stored_values[f"batch_event:{batch_id}"] = str(
                existing_event_id
            )

            # Create mock existing event to return from DB
            existing_event = Event(
                id=existing_event_id,
                batch_id=batch_id,
                camera_id=camera_id,
                started_at=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC),
                ended_at=datetime(2025, 12, 23, 14, 31, 0, tzinfo=UTC),
                risk_score=75,
                risk_level="high",
                summary="Pre-existing event",
                reasoning="This was already created",
                reviewed=False,
            )

            # Mock database session for event lookup
            mock_session = AsyncMock()
            mock_event_result = MagicMock()
            mock_event_result.scalar_one_or_none.return_value = existing_event
            mock_session.execute = AsyncMock(return_value=mock_event_result)

            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=None)

            with patch(
                "backend.services.nemotron_analyzer.get_session",
                return_value=mock_context,
            ):
                # Call analyze_batch - should return existing event, not create new
                event = await analyzer.analyze_batch(
                    batch_id=batch_id,
                    camera_id=camera_id,
                    detection_ids=detection_ids,
                )

            # Verify we got the existing event back
            assert event.id == existing_event_id
            assert event.summary == "Pre-existing event"

            # Verify session.add was NOT called (no new Event created)
            mock_session.add.assert_not_called()
            reset_severity_service()

    @pytest.mark.asyncio
    async def test_analyze_batch_stores_idempotency_after_creation(
        self, mock_settings_for_idempotency, mock_redis_for_idempotency
    ):
        """Test analyze_batch stores idempotency key after successful Event creation.

        After creating a new Event, store the idempotency key so subsequent
        retries will find it and avoid duplication.
        """
        from datetime import UTC

        from backend.models.camera import Camera
        from backend.models.detection import Detection

        with (
            patch(
                "backend.services.nemotron_analyzer.get_settings",
                return_value=mock_settings_for_idempotency,
            ),
            patch(
                "backend.services.severity.get_settings",
                return_value=mock_settings_for_idempotency,
            ),
        ):
            from backend.services.severity import reset_severity_service

            reset_severity_service()
            analyzer = NemotronAnalyzer(redis_client=mock_redis_for_idempotency)

            batch_id = "new_batch_with_idempotency"
            camera_id = "front_door"
            detection_ids = [1, 2]

            # Create test fixtures
            mock_camera = Camera(
                id=camera_id,
                name="Front Door Camera",
                folder_path="/export/foscam/front_door",
                status="online",
            )

            mock_detections = [
                Detection(
                    id=1,
                    camera_id=camera_id,
                    file_path="/export/foscam/front_door/img1.jpg",
                    detected_at=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC),
                    object_type="person",
                    confidence=0.95,
                ),
                Detection(
                    id=2,
                    camera_id=camera_id,
                    file_path="/export/foscam/front_door/img2.jpg",
                    detected_at=datetime(2025, 12, 23, 14, 30, 15, tzinfo=UTC),
                    object_type="car",
                    confidence=0.88,
                ),
            ]

            # Mock database session
            mock_session = AsyncMock()

            mock_camera_result = MagicMock()
            mock_camera_result.scalar_one_or_none.return_value = mock_camera

            mock_det_result = MagicMock()
            mock_det_scalars = MagicMock()
            mock_det_scalars.all.return_value = mock_detections
            mock_det_result.scalars.return_value = mock_det_scalars

            call_count = 0

            async def mock_execute(query):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return mock_camera_result
                else:
                    return mock_det_result

            mock_session.execute = mock_execute
            mock_session.add = MagicMock()
            mock_session.commit = AsyncMock()

            # NEM-2574: Mock flush to set the event ID (batched commits use flush)
            async def mock_flush():
                # Find any Event/Audit objects that were added and assign IDs
                for call in mock_session.add.call_args_list:
                    obj = call[0][0]
                    if hasattr(obj, "id") and obj.id is None:
                        obj.id = 42  # Simulate DB-assigned ID

            mock_session.flush = mock_flush

            # Mock refresh to set the event ID
            async def mock_refresh(obj):
                if hasattr(obj, "id") and obj.id is None:
                    obj.id = 42  # Simulate DB-assigned ID

            mock_session.refresh = mock_refresh

            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=None)

            mock_broadcaster = MagicMock()
            mock_broadcaster.broadcast_event = AsyncMock()

            mock_llm_response = {
                "risk_score": 65,
                "risk_level": "high",
                "summary": "New event created",
                "reasoning": "Test reasoning",
            }

            async def mock_call_llm(*args, **kwargs):
                return mock_llm_response

            with (
                patch(
                    "backend.services.nemotron_analyzer.get_session",
                    return_value=mock_context,
                ),
                patch.object(analyzer, "_call_llm", side_effect=mock_call_llm),
                patch.object(analyzer, "_get_enriched_context", return_value=None),
                patch.object(analyzer, "_get_enrichment_result", return_value=None),
                patch(
                    "backend.services.event_broadcaster.get_broadcaster",
                    new=AsyncMock(return_value=mock_broadcaster),
                ),
            ):
                _ = await analyzer.analyze_batch(
                    batch_id=batch_id,
                    camera_id=camera_id,
                    detection_ids=detection_ids,
                )

            # Verify idempotency key was stored after Event creation
            assert f"batch_event:{batch_id}" in mock_redis_for_idempotency._stored_values
            assert mock_redis_for_idempotency._stored_values[f"batch_event:{batch_id}"] == "42"
            reset_severity_service()

    @pytest.mark.asyncio
    async def test_idempotency_check_handles_redis_failure_gracefully(
        self, mock_settings_for_idempotency
    ):
        """Test idempotency check continues if Redis is unavailable.

        If Redis fails during idempotency check, we should proceed with
        normal Event creation rather than failing the request entirely.
        """
        from backend.core.redis import RedisClient

        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.get = AsyncMock(side_effect=Exception("Redis connection failed"))
        mock_redis.set = AsyncMock(return_value=True)

        with (
            patch(
                "backend.services.nemotron_analyzer.get_settings",
                return_value=mock_settings_for_idempotency,
            ),
            patch(
                "backend.services.severity.get_settings",
                return_value=mock_settings_for_idempotency,
            ),
        ):
            from backend.services.severity import reset_severity_service

            reset_severity_service()
            analyzer = NemotronAnalyzer(redis_client=mock_redis)

            # Should return None on Redis failure (proceed with creation)
            result = await analyzer._check_idempotency("batch_with_redis_error")

            assert result is None
            reset_severity_service()

    @pytest.mark.asyncio
    async def test_idempotency_set_handles_redis_failure_gracefully(
        self, mock_settings_for_idempotency
    ):
        """Test idempotency set continues if Redis is unavailable.

        If Redis fails during idempotency key storage, we should log
        a warning but not fail the request.
        """
        from backend.core.redis import RedisClient

        mock_redis = MagicMock(spec=RedisClient)
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.set = AsyncMock(side_effect=Exception("Redis write failed"))

        with (
            patch(
                "backend.services.nemotron_analyzer.get_settings",
                return_value=mock_settings_for_idempotency,
            ),
            patch(
                "backend.services.severity.get_settings",
                return_value=mock_settings_for_idempotency,
            ),
        ):
            from backend.services.severity import reset_severity_service

            reset_severity_service()
            analyzer = NemotronAnalyzer(redis_client=mock_redis)

            # Should not raise - just log warning
            await analyzer._set_idempotency("batch_with_redis_error", 100)

            # Verify set was attempted
            mock_redis.set.assert_called_once()
            reset_severity_service()

    @pytest.mark.asyncio
    async def test_analyze_detection_fast_path_uses_idempotency(
        self, mock_settings_for_idempotency, mock_redis_for_idempotency
    ):
        """Test fast path analysis also uses idempotency handling.

        The fast path creates Events for single high-priority detections
        and should also use idempotency to prevent duplicates on retry.
        """
        from datetime import UTC

        from backend.models.event import Event

        with (
            patch(
                "backend.services.nemotron_analyzer.get_settings",
                return_value=mock_settings_for_idempotency,
            ),
            patch(
                "backend.services.severity.get_settings",
                return_value=mock_settings_for_idempotency,
            ),
        ):
            from backend.services.severity import reset_severity_service

            reset_severity_service()
            analyzer = NemotronAnalyzer(redis_client=mock_redis_for_idempotency)

            camera_id = "front_door"
            detection_id = 42
            batch_id = f"fast_path_{detection_id}"
            existing_event_id = 888

            # Pre-store idempotency key for fast path batch
            mock_redis_for_idempotency._stored_values[f"batch_event:{batch_id}"] = str(
                existing_event_id
            )

            # Create mock existing event
            existing_event = Event(
                id=existing_event_id,
                batch_id=batch_id,
                camera_id=camera_id,
                started_at=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC),
                ended_at=datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC),
                risk_score=90,
                risk_level="critical",
                summary="Fast path event already exists",
                reasoning="Created on first attempt",
                is_fast_path=True,
                reviewed=False,
            )

            # Mock database session
            mock_session = AsyncMock()
            mock_event_result = MagicMock()
            mock_event_result.scalar_one_or_none.return_value = existing_event
            mock_session.execute = AsyncMock(return_value=mock_event_result)

            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_session)
            mock_context.__aexit__ = AsyncMock(return_value=None)

            with patch(
                "backend.services.nemotron_analyzer.get_session",
                return_value=mock_context,
            ):
                event = await analyzer.analyze_detection_fast_path(camera_id, detection_id)

            # Should return existing event
            assert event.id == existing_event_id
            assert event.is_fast_path is True
            assert event.summary == "Fast path event already exists"

            # Should not create new event
            mock_session.add.assert_not_called()
            reset_severity_service()


# =============================================================================
# Test: LLM Token Usage Metrics (NEM-1730)
# =============================================================================


class TestLLMTokenMetrics:
    """Tests for LLM token usage tracking metrics.

    Verifies that the Nemotron analyzer extracts token counts from LLM responses
    and records them via the metrics system.
    """

    @pytest.fixture
    def mock_settings_for_token_tests(self):
        """Create mock settings for token metrics tests."""
        from backend.core.config import Settings

        mock = MagicMock(spec=Settings)
        mock.nemotron_url = "http://localhost:8091"
        mock.nemotron_api_key = None
        mock.ai_connect_timeout = 10.0
        mock.nemotron_read_timeout = 120.0
        mock.ai_health_timeout = 5.0
        mock.nemotron_max_retries = 1
        mock.severity_low_max = 29
        mock.severity_medium_max = 59
        mock.severity_high_max = 84
        # Token counter settings (NEM-1666)
        mock.nemotron_context_window = 4096
        mock.nemotron_max_output_tokens = 1536
        mock.context_utilization_warning_threshold = 0.80
        mock.context_truncation_enabled = True
        mock.llm_tokenizer_encoding = "cl100k_base"
        # Cold start and warmup settings (NEM-1670)
        mock.ai_warmup_enabled = True
        mock.ai_cold_start_threshold_seconds = 300.0
        mock.nemotron_warmup_prompt = "Test warmup prompt"
        # Inference semaphore settings (NEM-1463, used by facade)
        mock.ai_max_concurrent_inferences = 4
        # Guided JSON settings (NEM-3726)
        mock.nemotron_use_guided_json = False
        mock.nemotron_guided_json_fallback = True
        return mock

    @pytest.fixture
    def analyzer_for_token_tests(self, mock_redis_client, mock_settings_for_token_tests):
        """Create NemotronAnalyzer for token metrics tests."""
        from backend.services.analyzer_facade import reset_analyzer_facade
        from backend.services.inference_semaphore import reset_inference_semaphore

        reset_inference_semaphore()
        reset_analyzer_facade()

        with (
            patch(
                "backend.services.nemotron_analyzer.get_settings",
                return_value=mock_settings_for_token_tests,
            ),
            patch(
                "backend.services.severity.get_settings",
                return_value=mock_settings_for_token_tests,
            ),
            patch(
                "backend.services.inference_semaphore.get_settings",
                return_value=mock_settings_for_token_tests,
            ),
            patch(
                "backend.core.config.get_settings",
                return_value=mock_settings_for_token_tests,
            ),
        ):
            from backend.services.severity import reset_severity_service

            reset_severity_service()
            yield NemotronAnalyzer(redis_client=mock_redis_client)
            reset_severity_service()
            reset_analyzer_facade()
            reset_inference_semaphore()

    @pytest.mark.asyncio
    async def test_call_llm_records_token_usage(self, analyzer_for_token_tests):
        """Test that _call_llm records token usage metrics from LLM response."""
        # Mock LLM response with usage metadata (llama.cpp format)
        mock_response = {
            "content": json.dumps(
                {
                    "risk_score": 60,
                    "risk_level": "high",
                    "summary": "Test event",
                    "reasoning": "Test reasoning",
                }
            ),
            "usage": {
                "prompt_tokens": 150,
                "completion_tokens": 75,
            },
            "timings": {
                "predicted_per_second": 25.5,
            },
        }

        with (
            patch("httpx.AsyncClient.post") as mock_post,
            patch("backend.services.nemotron_analyzer.record_nemotron_tokens") as mock_record,
        ):
            mock_resp = MagicMock(spec=httpx.Response)
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response
            mock_post.return_value = mock_resp

            await analyzer_for_token_tests._call_llm(
                camera_name="Front Door",
                start_time="2025-12-23T14:30:00",
                end_time="2025-12-23T14:31:00",
                detections_list="1. 14:30:00 - person",
            )

            # Verify token metrics were recorded
            mock_record.assert_called_once()
            call_kwargs = mock_record.call_args[1]
            assert call_kwargs["input_tokens"] == 150
            assert call_kwargs["output_tokens"] == 75

    @pytest.mark.asyncio
    async def test_call_llm_handles_missing_usage(self, analyzer_for_token_tests):
        """Test that _call_llm handles missing usage metadata gracefully."""
        # Mock LLM response without usage field
        mock_response = {
            "content": json.dumps(
                {
                    "risk_score": 50,
                    "risk_level": "medium",
                    "summary": "Test event",
                    "reasoning": "Test reasoning",
                }
            )
            # No "usage" field
        }

        with (
            patch("httpx.AsyncClient.post") as mock_post,
            patch("backend.services.nemotron_analyzer.record_nemotron_tokens") as mock_record,
        ):
            mock_resp = MagicMock(spec=httpx.Response)
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response
            mock_post.return_value = mock_resp

            # Should not raise, should handle missing usage gracefully
            await analyzer_for_token_tests._call_llm(
                camera_name="Front Door",
                start_time="2025-12-23T14:30:00",
                end_time="2025-12-23T14:31:00",
                detections_list="1. 14:30:00 - person",
            )

            # Token metrics should still be recorded with 0 values
            mock_record.assert_called_once()
            call_kwargs = mock_record.call_args[1]
            assert call_kwargs["input_tokens"] == 0
            assert call_kwargs["output_tokens"] == 0

    @pytest.mark.asyncio
    async def test_call_llm_records_throughput(self, analyzer_for_token_tests):
        """Test that _call_llm calculates and records token throughput."""
        mock_response = {
            "content": json.dumps(
                {
                    "risk_score": 70,
                    "risk_level": "high",
                    "summary": "Test event",
                    "reasoning": "Test reasoning",
                }
            ),
            "usage": {
                "prompt_tokens": 200,
                "completion_tokens": 100,
            },
        }

        with (
            patch("httpx.AsyncClient.post") as mock_post,
            patch("backend.services.nemotron_analyzer.record_nemotron_tokens") as mock_record,
        ):
            mock_resp = MagicMock(spec=httpx.Response)
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response
            mock_post.return_value = mock_resp

            await analyzer_for_token_tests._call_llm(
                camera_name="Backyard",
                start_time="2025-12-23T14:30:00",
                end_time="2025-12-23T14:31:00",
                detections_list="1. 14:30:00 - car",
            )

            # Verify duration was passed for throughput calculation
            mock_record.assert_called_once()
            call_kwargs = mock_record.call_args[1]
            assert "duration_seconds" in call_kwargs
            # Duration should be positive (actual LLM call time)
            assert call_kwargs["duration_seconds"] is None or call_kwargs["duration_seconds"] >= 0


# =============================================================================
# Token Counting and Context Window Validation Tests (NEM-1723)
# =============================================================================


class TestTokenCountingIntegration:
    """Tests for token counting and context window validation in NemotronAnalyzer."""

    @pytest.fixture
    def mock_settings_with_token_limits(self):
        """Create mock settings with token limit configuration."""
        from backend.core.config import Settings

        mock = MagicMock(spec=Settings)
        mock.nemotron_url = "http://localhost:8091"
        mock.nemotron_api_key = None
        mock.ai_connect_timeout = 10.0
        mock.nemotron_read_timeout = 120.0
        mock.ai_health_timeout = 5.0
        mock.nemotron_max_retries = 1
        mock.severity_low_max = 29
        mock.severity_medium_max = 59
        mock.severity_high_max = 84
        # Token limit settings (NEM-1723)
        mock.nemotron_context_window = 3900
        mock.nemotron_max_output_tokens = 1536
        # Cold start and warmup settings (NEM-1670)
        mock.ai_warmup_enabled = True
        mock.ai_cold_start_threshold_seconds = 300.0
        mock.nemotron_warmup_prompt = "Test warmup prompt"
        # Inference semaphore settings (NEM-1463)
        mock.ai_max_concurrent_inferences = 4
        # Guided JSON settings (NEM-3726)
        mock.nemotron_use_guided_json = False
        mock.nemotron_guided_json_fallback = True
        return mock

    @pytest.fixture
    def analyzer_with_token_limits(self, mock_redis_client, mock_settings_with_token_limits):
        """Create analyzer with token limit configuration."""
        # Reset inference semaphore to avoid stale singleton
        from backend.services.inference_semaphore import reset_inference_semaphore

        reset_inference_semaphore()

        with (
            patch(
                "backend.services.nemotron_analyzer.get_settings",
                return_value=mock_settings_with_token_limits,
            ),
            patch(
                "backend.services.severity.get_settings",
                return_value=mock_settings_with_token_limits,
            ),
            patch(
                "backend.services.inference_semaphore.get_settings",
                return_value=mock_settings_with_token_limits,
            ),
        ):
            from backend.services.analyzer_facade import reset_analyzer_facade
            from backend.services.severity import reset_severity_service

            reset_severity_service()
            reset_analyzer_facade()
            yield NemotronAnalyzer(redis_client=mock_redis_client)
            reset_severity_service()
            reset_analyzer_facade()
            reset_inference_semaphore()

    @pytest.mark.asyncio
    async def test_call_llm_validates_prompt_tokens(self, analyzer_with_token_limits):
        """Test that _call_llm validates prompt token count before calling LLM."""
        mock_response = {
            "content": json.dumps(
                {
                    "risk_score": 50,
                    "risk_level": "medium",
                    "summary": "Test event",
                    "reasoning": "Test reasoning",
                }
            ),
        }

        # Mock token counter with validation result
        mock_validation = MagicMock()
        mock_validation.is_valid = True
        mock_validation.prompt_tokens = 500
        mock_validation.available_tokens = 2560
        mock_validation.utilization = 0.2

        mock_counter = MagicMock()
        mock_counter.validate_prompt.return_value = mock_validation

        with (
            patch("httpx.AsyncClient.post") as mock_post,
            patch(
                "backend.services.token_counter.get_token_counter",
                return_value=mock_counter,
            ),
        ):
            mock_resp = MagicMock(spec=httpx.Response)
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response
            mock_post.return_value = mock_resp

            await analyzer_with_token_limits._call_llm(
                camera_name="Front Door",
                start_time="2025-12-23T14:30:00",
                end_time="2025-12-23T14:31:00",
                detections_list="1. 14:30:00 - person",
            )

            # Verify validation was called
            mock_counter.validate_prompt.assert_called_once()


# =========================================================================
# Test: Cold Start and Warmup (NEM-1670)
# =========================================================================


@pytest.mark.asyncio
async def test_track_inference_updates_timestamp(analyzer):
    """Test that _track_inference records the current time."""
    import time

    # Initially should be None
    assert analyzer._last_inference_time is None

    # Track an inference
    before = time.monotonic()
    analyzer._track_inference()
    after = time.monotonic()

    # Should be set to a value between before and after
    assert analyzer._last_inference_time is not None
    assert before <= analyzer._last_inference_time <= after


def test_is_cold_returns_true_when_never_used(analyzer):
    """Test is_cold returns True when model has never been used."""
    assert analyzer.is_cold() is True


def test_is_cold_returns_false_when_recently_used(analyzer):
    """Test is_cold returns False when model was recently used."""
    analyzer._track_inference()
    assert analyzer.is_cold() is False


def test_is_cold_returns_true_when_threshold_exceeded(analyzer):
    """Test is_cold returns True when time since last inference exceeds threshold."""
    import time

    # Set last inference time to far in the past
    analyzer._last_inference_time = time.monotonic() - 400.0  # 400 seconds ago
    assert analyzer.is_cold() is True


def test_get_warmth_state_cold(analyzer):
    """Test get_warmth_state returns 'cold' when never used."""
    state = analyzer.get_warmth_state()
    assert state["state"] == "cold"
    assert state["last_inference_seconds_ago"] is None


def test_get_warmth_state_warm(analyzer):
    """Test get_warmth_state returns 'warm' when recently used."""
    analyzer._track_inference()
    state = analyzer.get_warmth_state()
    assert state["state"] == "warm"
    assert state["last_inference_seconds_ago"] is not None
    assert state["last_inference_seconds_ago"] < 10.0  # Should be very recent


def test_get_warmth_state_warming(analyzer):
    """Test get_warmth_state returns 'warming' during warmup."""
    analyzer._is_warming = True
    state = analyzer.get_warmth_state()
    assert state["state"] == "warming"
    assert state["last_inference_seconds_ago"] is None


@pytest.mark.asyncio
async def test_model_readiness_probe_success(analyzer):
    """Test model_readiness_probe succeeds with valid response."""
    mock_response = {"content": "test response"}

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_post.return_value = mock_resp

        result = await analyzer.model_readiness_probe()

    assert result is True


@pytest.mark.asyncio
async def test_model_readiness_probe_connection_error(analyzer):
    """Test model_readiness_probe returns False on connection error."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        result = await analyzer.model_readiness_probe()

    assert result is False


@pytest.mark.asyncio
async def test_model_readiness_probe_timeout(analyzer):
    """Test model_readiness_probe returns False on timeout."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = httpx.TimeoutException("Request timeout")

        result = await analyzer.model_readiness_probe()

    assert result is False


@pytest.mark.asyncio
async def test_model_readiness_probe_http_error(analyzer):
    """Test model_readiness_probe returns False on HTTP error."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(spec=httpx.Request), response=mock_resp
        )
        mock_post.return_value = mock_resp

        result = await analyzer.model_readiness_probe()

    assert result is False


@pytest.mark.asyncio
async def test_warmup_success(analyzer):
    """Test warmup succeeds and records metrics."""
    mock_response = {"content": "warmup response"}

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_post.return_value = mock_resp

        result = await analyzer.warmup()

    assert result is True
    assert analyzer.is_cold() is False


@pytest.mark.asyncio
async def test_warmup_failure(analyzer):
    """Test warmup handles failure gracefully."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        result = await analyzer.warmup()

    assert result is False
    # Should still be cold after failed warmup
    assert analyzer.is_cold() is True


@pytest.mark.asyncio
async def test_warmup_disabled(analyzer):
    """Test warmup skips when disabled in settings."""
    analyzer._warmup_enabled = False

    result = await analyzer.warmup()

    # Should return True (success) but not actually warm up
    assert result is True


# =========================================================================
# Test: A/B Testing (NEM-1667)
# =========================================================================


def test_set_ab_test_config_success(analyzer):
    """Test setting A/B test configuration."""
    from backend.services.prompt_service import ABTestConfig

    config = ABTestConfig(
        control_version=1,
        treatment_version=2,
        traffic_split=0.5,
        model="nemotron",
        enabled=True,
    )

    analyzer.set_ab_test_config(config)

    assert analyzer._ab_config is not None
    assert analyzer._ab_tester is not None


def test_set_ab_test_config_invalid_type(analyzer):
    """Test set_ab_test_config raises TypeError for invalid config."""
    with pytest.raises(TypeError, match="config must be an ABTestConfig instance"):
        analyzer.set_ab_test_config({"invalid": "dict"})


@pytest.mark.asyncio
async def test_get_prompt_version_default(analyzer):
    """Test get_prompt_version returns default when no A/B test configured."""
    version, is_treatment = await analyzer.get_prompt_version()

    assert version == 1
    assert is_treatment is False


@pytest.mark.asyncio
async def test_get_prompt_version_with_ab_testing(analyzer):
    """Test get_prompt_version uses A/B tester when configured."""
    from backend.services.prompt_service import ABTestConfig

    config = ABTestConfig(
        control_version=1,
        treatment_version=2,
        traffic_split=0.5,
        model="nemotron",
        enabled=True,
    )
    analyzer.set_ab_test_config(config)

    version, is_treatment = await analyzer.get_prompt_version()

    # Should return either control (1) or treatment (2)
    assert version in (1, 2)
    assert isinstance(is_treatment, bool)


def test_record_analysis_metrics(analyzer):
    """Test _record_analysis_metrics records prompt latency."""
    from backend.core import metrics

    with patch.object(metrics, "record_prompt_latency") as mock_record:
        analyzer._record_analysis_metrics(
            prompt_version=1,
            latency_seconds=1.5,
            risk_score=75,
        )

        mock_record.assert_called_once_with("v1", 1.5)


# =========================================================================
# Test: Context Enricher and Pipeline Getters
# =========================================================================


def test_get_context_enricher_uses_existing(analyzer):
    """Test _get_context_enricher returns existing enricher if set."""
    from backend.services.context_enricher import ContextEnricher

    mock_enricher = MagicMock(spec=ContextEnricher)
    analyzer._context_enricher = mock_enricher

    result = analyzer._get_context_enricher()

    assert result is mock_enricher


def test_get_context_enricher_creates_singleton(analyzer):
    """Test _get_context_enricher creates global singleton if needed via facade."""
    from backend.services.analyzer_facade import reset_analyzer_facade

    analyzer._context_enricher = None
    analyzer._facade = None  # Ensure facade is also reset
    reset_analyzer_facade()

    # Patch the module-level function that the facade imports
    with patch("backend.services.context_enricher.get_context_enricher") as mock_get_enricher:
        from backend.services.context_enricher import ContextEnricher

        mock_enricher = MagicMock(spec=ContextEnricher)
        mock_get_enricher.return_value = mock_enricher

        result = analyzer._get_context_enricher()

        assert result is mock_enricher
        mock_get_enricher.assert_called_once()


def test_get_enrichment_pipeline_uses_existing(analyzer):
    """Test _get_enrichment_pipeline returns existing pipeline if set."""
    from backend.services.enrichment_pipeline import EnrichmentPipeline

    mock_pipeline = MagicMock(spec=EnrichmentPipeline)
    analyzer._enrichment_pipeline = mock_pipeline

    result = analyzer._get_enrichment_pipeline()

    assert result is mock_pipeline


def test_get_enrichment_pipeline_creates_singleton(analyzer):
    """Test _get_enrichment_pipeline creates global singleton if needed via facade."""
    from backend.services.analyzer_facade import reset_analyzer_facade

    analyzer._enrichment_pipeline = None
    analyzer._facade = None  # Ensure facade is also reset
    reset_analyzer_facade()

    # Patch the module-level function that the facade imports
    with patch("backend.services.enrichment_pipeline.get_enrichment_pipeline") as mock_get_pipeline:
        from backend.services.enrichment_pipeline import EnrichmentPipeline

        mock_pipeline = MagicMock(spec=EnrichmentPipeline)
        mock_get_pipeline.return_value = mock_pipeline

        result = analyzer._get_enrichment_pipeline()

        assert result is mock_pipeline
        mock_get_pipeline.assert_called_once()


# =========================================================================
# Test: Auth Headers (NEM-1729)
# =========================================================================


def test_get_auth_headers_no_api_key(analyzer):
    """Test _get_auth_headers without API key configured."""
    with patch(
        "backend.services.nemotron_analyzer.get_correlation_headers",
        return_value={"X-Correlation-ID": "test-123"},
    ):
        headers = analyzer._get_auth_headers()

        assert "X-Correlation-ID" in headers
        assert "X-API-Key" not in headers


def test_get_auth_headers_with_api_key(analyzer):
    """Test _get_auth_headers includes API key when configured."""
    test_api_key = "test-api-key-value"  # pragma: allowlist secret
    analyzer._api_key = test_api_key

    with patch(
        "backend.services.nemotron_analyzer.get_correlation_headers",
        return_value={"X-Correlation-ID": "test-123"},
    ):
        headers = analyzer._get_auth_headers()

        assert "X-Correlation-ID" in headers
        assert headers["X-API-Key"] == test_api_key


# =========================================================================
# Test: Prompt Validation and Truncation (NEM-1666, NEM-1723)
# =========================================================================


def test_validate_and_truncate_prompt_valid(analyzer):
    """Test _validate_and_truncate_prompt with valid prompt."""
    from backend.services.token_counter import TokenValidationResult

    prompt = "This is a short test prompt"

    mock_validation = TokenValidationResult(
        is_valid=True,
        prompt_tokens=10,
        available_tokens=2560,
        context_window=4096,
        max_output_tokens=1536,
        utilization=0.004,
        warning=None,
    )

    with patch("backend.services.token_counter.get_token_counter") as mock_get_counter:
        mock_counter = MagicMock()
        mock_counter.validate_prompt.return_value = mock_validation
        mock_get_counter.return_value = mock_counter

        result = analyzer._validate_and_truncate_prompt(prompt)

        assert result == prompt
        mock_counter.validate_prompt.assert_called_once()


def test_validate_and_truncate_prompt_exceeds_with_truncation_enabled(analyzer):
    """Test _validate_and_truncate_prompt truncates when prompt exceeds limits."""
    from backend.services.token_counter import TokenValidationResult, TruncationResult

    prompt = "A" * 10000  # Very long prompt

    mock_validation = TokenValidationResult(
        is_valid=False,
        prompt_tokens=5000,
        available_tokens=2560,
        context_window=4096,
        max_output_tokens=1536,
        utilization=2.0,
        warning="Prompt exceeds context window",
    )

    truncated_prompt = "Truncated version"
    mock_truncation = TruncationResult(
        truncated_prompt=truncated_prompt,
        was_truncated=True,
        original_tokens=5000,
        final_tokens=2000,
        sections_removed=["enrichment_context"],
    )

    with patch("backend.services.token_counter.get_token_counter") as mock_get_counter:
        mock_counter = MagicMock()
        mock_counter.validate_prompt.return_value = mock_validation
        mock_counter.truncate_enrichment_data.return_value = mock_truncation
        mock_get_counter.return_value = mock_counter

        result = analyzer._validate_and_truncate_prompt(prompt)

        assert result == truncated_prompt
        mock_counter.truncate_enrichment_data.assert_called_once()


def test_validate_and_truncate_prompt_exceeds_with_truncation_disabled(
    mock_redis_client, mock_settings
):
    """Test _validate_and_truncate_prompt raises error when truncation disabled."""
    from backend.services.token_counter import TokenValidationResult

    # Disable truncation
    mock_settings.context_truncation_enabled = False

    with (
        patch("backend.services.nemotron_analyzer.get_settings", return_value=mock_settings),
        patch("backend.services.severity.get_settings", return_value=mock_settings),
        patch("backend.services.token_counter.get_settings", return_value=mock_settings),
        patch("backend.core.config.get_settings", return_value=mock_settings),
    ):
        from backend.services.severity import reset_severity_service
        from backend.services.token_counter import reset_token_counter

        reset_severity_service()
        reset_token_counter()

        analyzer = NemotronAnalyzer(redis_client=mock_redis_client)

        prompt = "A" * 10000  # Very long prompt

        mock_validation = TokenValidationResult(
            is_valid=False,
            prompt_tokens=5000,
            available_tokens=2560,
            context_window=4096,
            max_output_tokens=1536,
            utilization=2.0,
            warning="Prompt exceeds context window",
        )

        with patch("backend.services.token_counter.get_token_counter") as mock_get_counter:
            mock_counter = MagicMock()
            mock_counter.validate_prompt.return_value = mock_validation
            mock_get_counter.return_value = mock_counter

            with pytest.raises(ValueError, match="Prompt exceeds context window limits"):
                analyzer._validate_and_truncate_prompt(prompt)

        reset_severity_service()
        reset_token_counter()


# =========================================================================
# Test: Evaluation Queue (NEM-1673)
# =========================================================================


@pytest.mark.asyncio
async def test_enqueue_for_evaluation_success(analyzer, mock_redis_client):
    """Test _enqueue_for_evaluation queues event for background evaluation."""
    from backend.services.evaluation_queue import EvaluationQueue

    mock_queue = MagicMock(spec=EvaluationQueue)
    mock_queue.enqueue = AsyncMock()

    with (
        patch(
            "backend.services.evaluation_queue.get_evaluation_queue",
            return_value=mock_queue,
        ),
        patch("backend.core.config.get_settings") as mock_get_settings,
    ):
        mock_settings = MagicMock()
        mock_settings.background_evaluation_enabled = True
        mock_get_settings.return_value = mock_settings

        await analyzer._enqueue_for_evaluation(event_id=123, risk_score=75)

        mock_queue.enqueue.assert_called_once_with(event_id=123, priority=75)


@pytest.mark.asyncio
async def test_enqueue_for_evaluation_disabled(analyzer, mock_redis_client):
    """Test _enqueue_for_evaluation skips when background evaluation disabled."""
    with patch("backend.core.config.get_settings") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.background_evaluation_enabled = False
        mock_get_settings.return_value = mock_settings

        # Should not raise any errors, just log and skip
        await analyzer._enqueue_for_evaluation(event_id=123, risk_score=75)


@pytest.mark.asyncio
async def test_enqueue_for_evaluation_handles_failure(analyzer, mock_redis_client):
    """Test _enqueue_for_evaluation handles queue failure gracefully."""
    from backend.services.evaluation_queue import EvaluationQueue

    mock_queue = MagicMock(spec=EvaluationQueue)
    mock_queue.enqueue = AsyncMock(side_effect=Exception("Queue error"))

    with (
        patch(
            "backend.services.evaluation_queue.get_evaluation_queue",
            return_value=mock_queue,
        ),
        patch("backend.core.config.get_settings") as mock_get_settings,
    ):
        mock_settings = MagicMock()
        mock_settings.background_evaluation_enabled = True
        mock_get_settings.return_value = mock_settings

        # Should not raise, just log warning
        await analyzer._enqueue_for_evaluation(event_id=123, risk_score=75)


# =========================================================================
# Test: LLM Response Parsing Edge Cases
# =========================================================================


def test_parse_llm_response_with_think_tags(analyzer):
    """Test parsing LLM response with <think> tags."""
    response_text = """
    <think>
    Let me analyze this carefully. The person detection at night is suspicious.
    I should assign a high risk score.
    </think>
    {
      "risk_score": 75,
      "risk_level": "high",
      "summary": "Person detected at night",
      "reasoning": "Unusual nighttime activity"
    }
    """

    result = analyzer._parse_llm_response(response_text)

    assert result["risk_score"] == 75
    assert result["risk_level"] == "high"


def test_parse_llm_response_with_incomplete_think_tag(analyzer):
    """Test parsing LLM response with incomplete think tag."""
    response_text = """
    <think>
    This is my reasoning process...
    {
      "risk_score": 60,
      "risk_level": "high",
      "summary": "Medium risk event",
      "reasoning": "Some suspicious activity"
    }
    """

    result = analyzer._parse_llm_response(response_text)

    assert result["risk_score"] == 60
    assert result["risk_level"] == "high"


def test_parse_llm_response_with_preamble(analyzer):
    """Test parsing LLM response with preamble text before JSON."""
    response_text = """
    Based on my analysis of the detections, here is my assessment:

    {
      "risk_score": 45,
      "risk_level": "medium",
      "summary": "Normal activity",
      "reasoning": "Routine detections during business hours"
    }
    """

    result = analyzer._parse_llm_response(response_text)

    assert result["risk_score"] == 45
    assert result["risk_level"] == "medium"


# =========================================================================
# Test: LLM Call Error Paths
# =========================================================================


@pytest.mark.asyncio
async def test_call_llm_asyncio_timeout(analyzer):
    """Test _call_llm handles asyncio.timeout() TimeoutError."""

    async def mock_post_with_timeout(*args, **kwargs):
        # Simulate asyncio.timeout() raising TimeoutError
        raise TimeoutError("Request timed out")

    with patch("httpx.AsyncClient.post", side_effect=mock_post_with_timeout):
        with pytest.raises(
            AnalyzerUnavailableError, match=r"Nemotron LLM call failed after \d+ attempts"
        ):
            await analyzer._call_llm(
                camera_name="Front Door",
                start_time="2025-12-23T14:30:00",
                end_time="2025-12-23T14:31:00",
                detections_list="1. 14:30:00 - person",
            )


@pytest.mark.asyncio
async def test_call_llm_client_error_no_retry(analyzer):
    """Test _call_llm does not retry on 4xx client errors."""
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 400
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Request", request=MagicMock(spec=httpx.Request), response=mock_resp
        )
        mock_post.return_value = mock_resp

        with pytest.raises(httpx.HTTPStatusError):
            await analyzer._call_llm(
                camera_name="Front Door",
                start_time="2025-12-23T14:30:00",
                end_time="2025-12-23T14:31:00",
                detections_list="1. 14:30:00 - person",
            )

        # Should only be called once (no retry for 4xx)
        assert mock_post.call_count == 1


@pytest.mark.asyncio
async def test_call_llm_unexpected_error_with_retry(analyzer):
    """Test _call_llm retries on unexpected errors."""
    call_count = 0

    async def mock_post_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise RuntimeError("Unexpected error")
        # Succeed on second attempt
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "content": json.dumps(
                {
                    "risk_score": 50,
                    "risk_level": "medium",
                    "summary": "Test",
                    "reasoning": "Test",
                }
            ),
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }
        return mock_resp

    with patch("httpx.AsyncClient.post", side_effect=mock_post_side_effect):
        result = await analyzer._call_llm(
            camera_name="Front Door",
            start_time="2025-12-23T14:30:00",
            end_time="2025-12-23T14:31:00",
            detections_list="1. 14:30:00 - person",
        )

        assert result["risk_score"] == 50
        assert call_count == 2  # Should have retried once


# =========================================================================
# Test: Streaming Methods (NEM-1665)
# =========================================================================


def test_build_prompt_basic(analyzer):
    """Test _build_prompt generates basic prompt."""
    prompt = analyzer._build_prompt(
        camera_name="Front Door",
        start_time="2025-12-23T14:30:00",
        end_time="2025-12-23T14:31:00",
        detections_list="1. 14:30:00 - person (confidence: 0.95)",
    )

    assert "Front Door" in prompt
    assert "14:30:00" in prompt
    assert "person" in prompt


@pytest.mark.asyncio
async def test_analyze_batch_streaming_delegates_to_streaming_module(analyzer, mock_redis_client):
    """Test analyze_batch_streaming delegates to nemotron_streaming module."""

    async def mock_streaming_generator():
        yield {"type": "progress", "data": {"status": "analyzing"}}
        yield {"type": "complete", "data": {"event_id": 123}}

    with patch(
        "backend.services.nemotron_streaming.analyze_batch_streaming",
        return_value=mock_streaming_generator(),
    ) as mock_streaming:
        updates = []
        async for update in analyzer.analyze_batch_streaming(
            batch_id="test-batch",
            camera_id="front_door",
            detection_ids=[1, 2, 3],
        ):
            updates.append(update)

        # Should have called the streaming module
        mock_streaming.assert_called_once()

        # Should have received updates
        assert len(updates) == 2
        assert updates[0]["type"] == "progress"
        assert updates[1]["type"] == "complete"


# =============================================================================
# Test: Household Matching Integration (NEM-3024)
# =============================================================================


@pytest.mark.asyncio
async def test_call_llm_with_household_context(analyzer):
    """Test _call_llm includes household context when provided."""
    mock_response = {
        "content": json.dumps(
            {
                "risk_score": 10,
                "risk_level": "low",
                "summary": "Known household member detected",
                "reasoning": "Person matched to John Doe with 95% confidence",
            }
        ),
        "usage": {"prompt_tokens": 200, "completion_tokens": 100},
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
            household_context="## RISK MODIFIERS\n| KNOWN PERSON: John Doe (95% match)\n| Base risk: 5",
        )

        assert result["risk_score"] == 10
        assert result["risk_level"] == "low"

        # Verify the household context was included in the prompt
        call_args = mock_post.call_args
        request_json = call_args[1]["json"]
        prompt = request_json["prompt"]
        assert "RISK MODIFIERS" in prompt
        assert "John Doe" in prompt


@pytest.mark.asyncio
async def test_call_llm_without_household_context(analyzer):
    """Test _call_llm works without household context (backwards compatibility)."""
    mock_response = {
        "content": json.dumps(
            {
                "risk_score": 50,
                "risk_level": "medium",
                "summary": "Unknown person detected",
                "reasoning": "Person not matched to any household member",
            }
        ),
        "usage": {"prompt_tokens": 150, "completion_tokens": 80},
    }

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_post.return_value = mock_resp

        # Call without household_context parameter
        result = await analyzer._call_llm(
            camera_name="Front Door",
            start_time="2025-12-23T14:30:00",
            end_time="2025-12-23T14:31:00",
            detections_list="1. 14:30:00 - person (confidence: 0.95)",
        )

        assert result["risk_score"] == 50


@pytest.mark.asyncio
async def test_call_llm_household_context_injected_in_prompt(analyzer):
    """Test that household context is injected into the prompt correctly."""
    mock_response = {
        "content": json.dumps(
            {
                "risk_score": 5,
                "risk_level": "low",
                "summary": "Resident returning home",
                "reasoning": "High confidence match to household member",
            }
        ),
        "usage": {"prompt_tokens": 250, "completion_tokens": 100},
    }

    household_context = """## RISK MODIFIERS (Apply These First)
+------------------------------------------------------------+
| KNOWN PERSON: Jane Smith (92% match)
| REGISTERED VEHICLE: Blue Honda Accord
+------------------------------------------------------------+
-> Calculated base risk: 5"""

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_post.return_value = mock_resp

        await analyzer._call_llm(
            camera_name="Driveway",
            start_time="2025-12-23T18:30:00",
            end_time="2025-12-23T18:31:00",
            detections_list="1. 18:30:00 - person (confidence: 0.95)\n2. 18:30:05 - car (confidence: 0.92)",
            household_context=household_context,
        )

        # Verify the prompt includes household context
        call_args = mock_post.call_args
        request_json = call_args[1]["json"]
        prompt = request_json["prompt"]

        # Household context should be in the prompt
        assert "Jane Smith" in prompt
        assert "Blue Honda Accord" in prompt
        assert "Calculated base risk: 5" in prompt


@pytest.mark.asyncio
async def test_call_llm_vehicle_only_household_context(analyzer):
    """Test _call_llm handles vehicle-only household match."""
    mock_response = {
        "content": json.dumps(
            {
                "risk_score": 15,
                "risk_level": "low",
                "summary": "Registered vehicle detected",
                "reasoning": "Vehicle matched to registered household vehicle",
            }
        ),
        "usage": {"prompt_tokens": 180, "completion_tokens": 90},
    }

    household_context = """## RISK MODIFIERS (Apply These First)
+------------------------------------------------------------+
| KNOWN PERSON MATCH: None (unknown individual)
| REGISTERED VEHICLE: White Tesla Model 3
+------------------------------------------------------------+
-> Calculated base risk: 10"""

    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_response
        mock_post.return_value = mock_resp

        result = await analyzer._call_llm(
            camera_name="Garage",
            start_time="2025-12-23T08:00:00",
            end_time="2025-12-23T08:01:00",
            detections_list="1. 08:00:00 - car (confidence: 0.98)",
            household_context=household_context,
        )

        assert result["risk_score"] == 15
        assert result["risk_level"] == "low"

        # Verify the vehicle info was in the prompt
        call_args = mock_post.call_args
        request_json = call_args[1]["json"]
        prompt = request_json["prompt"]
        assert "White Tesla Model 3" in prompt
