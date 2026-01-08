"""Unit tests for Nemotron streaming service (NEM-1665).

These tests cover streaming LLM calls and SSE response generation
for progressive analysis updates.
"""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.api.schemas.streaming import (
    StreamingCompleteEvent,
    StreamingErrorCode,
    StreamingErrorEvent,
    StreamingProgressEvent,
)
from backend.models.detection import Detection
from backend.models.event import Event
from backend.services.nemotron_streaming import (
    analyze_batch_streaming,
    call_llm_streaming,
)

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


# Fixtures


@pytest.fixture
def mock_analyzer():
    """Create a mock analyzer instance for streaming tests."""
    analyzer = MagicMock()
    analyzer._llm_url = "http://localhost:8091"
    analyzer._timeout = httpx.Timeout(connect=10.0, read=120.0, write=120.0, pool=10.0)
    analyzer._redis = AsyncMock()
    analyzer._redis.get = AsyncMock(return_value=None)

    # Mock methods used by streaming
    analyzer._build_prompt = MagicMock(return_value="Test prompt")
    analyzer._validate_and_truncate_prompt = MagicMock(side_effect=lambda x: x)
    analyzer._get_auth_headers = MagicMock(return_value={})
    analyzer._format_detections = MagicMock(return_value="1. 14:30:00 - person (confidence: 0.95)")
    analyzer._parse_llm_response = MagicMock(
        return_value={
            "risk_score": 75,
            "risk_level": "high",
            "summary": "Test summary",
            "reasoning": "Test reasoning",
        }
    )
    analyzer._validate_risk_data = MagicMock(
        side_effect=lambda x: x  # Pass through
    )
    analyzer._check_idempotency = AsyncMock(return_value=None)
    analyzer._set_idempotency = AsyncMock()
    analyzer._get_existing_event = AsyncMock(return_value=None)
    analyzer._get_enriched_context = AsyncMock(return_value=None)
    analyzer._get_enrichment_result = AsyncMock(return_value=None)
    analyzer._broadcast_event = AsyncMock()

    return analyzer


@pytest.fixture
def mock_settings():
    """Create mock settings for streaming tests."""
    mock = MagicMock()
    mock.nemotron_max_output_tokens = 1536
    return mock


@pytest.fixture
def sample_detections():
    """Sample detections for testing."""
    base_time = datetime(2025, 12, 23, 14, 30, 0, tzinfo=UTC)
    return [
        Detection(
            id=1,
            camera_id="test_camera",
            file_path="/export/foscam/test_camera/img1.jpg",
            detected_at=base_time,
            object_type="person",
            confidence=0.95,
        ),
        Detection(
            id=2,
            camera_id="test_camera",
            file_path="/export/foscam/test_camera/img2.jpg",
            detected_at=datetime(2025, 12, 23, 14, 30, 15, tzinfo=UTC),
            object_type="car",
            confidence=0.88,
        ),
    ]


# Test: Streaming Progress Events


class TestStreamingProgressEvent:
    """Tests for StreamingProgressEvent schema."""

    def test_progress_event_defaults(self):
        """Test progress event has correct default values."""
        event = StreamingProgressEvent(content="chunk", accumulated_text="chunk")

        assert event.event_type == "progress"
        assert event.content == "chunk"
        assert event.accumulated_text == "chunk"
        assert event.progress_percent is None

    def test_progress_event_with_all_fields(self):
        """Test progress event with all fields specified."""
        event = StreamingProgressEvent(
            content="new chunk",
            accumulated_text="accumulated text",
            progress_percent=0.5,
        )

        assert event.event_type == "progress"
        assert event.content == "new chunk"
        assert event.accumulated_text == "accumulated text"
        assert event.progress_percent == 0.5


class TestStreamingCompleteEvent:
    """Tests for StreamingCompleteEvent schema."""

    def test_complete_event_creation(self):
        """Test complete event contains all required fields."""
        event = StreamingCompleteEvent(
            event_id=123,
            risk_score=75,
            risk_level="high",
            summary="Test summary",
            reasoning="Test reasoning",
        )

        assert event.event_type == "complete"
        assert event.event_id == 123
        assert event.risk_score == 75
        assert event.risk_level == "high"
        assert event.summary == "Test summary"
        assert event.reasoning == "Test reasoning"


class TestStreamingErrorEvent:
    """Tests for StreamingErrorEvent schema."""

    def test_error_event_with_enum(self):
        """Test error event with StreamingErrorCode enum."""
        event = StreamingErrorEvent(
            error_code=StreamingErrorCode.LLM_TIMEOUT,
            error_message="Connection timed out",
            recoverable=True,
        )

        assert event.event_type == "error"
        assert event.error_code == StreamingErrorCode.LLM_TIMEOUT
        assert event.error_message == "Connection timed out"
        assert event.recoverable is True

    def test_error_event_with_string_code(self):
        """Test error event with string error code."""
        event = StreamingErrorEvent(
            error_code="CUSTOM_ERROR",
            error_message="Custom error occurred",
            recoverable=False,
        )

        assert event.error_code == "CUSTOM_ERROR"
        assert event.recoverable is False


# Test: call_llm_streaming


class TestCallLLMStreaming:
    """Tests for call_llm_streaming function."""

    @pytest.mark.asyncio
    async def test_call_llm_streaming_yields_chunks(self, mock_analyzer, mock_settings):
        """Test that streaming yields content chunks from SSE response."""
        # Mock SSE response data
        sse_lines = [
            'data: {"content": "Based"}',
            'data: {"content": " on"}',
            'data: {"content": " the"}',
            "data: [DONE]",
        ]

        # Create mock response
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.aiter_lines = AsyncMock(return_value=iter(sse_lines))

        # Need to make aiter_lines an async generator
        async def async_line_generator():
            for line in sse_lines:
                yield line

        mock_response.aiter_lines = async_line_generator

        # Create mock stream context manager
        mock_client = MagicMock()

        class MockStreamCM:
            async def __aenter__(self):
                return mock_response

            async def __aexit__(self, *args):
                pass

        mock_client.stream = MagicMock(return_value=MockStreamCM())

        with (
            patch("backend.services.nemotron_streaming.get_settings", return_value=mock_settings),
            patch("backend.services.nemotron_streaming.get_inference_semaphore") as mock_semaphore,
            patch("httpx.AsyncClient") as mock_httpx,
        ):
            # Setup semaphore mock
            mock_semaphore.return_value = AsyncMock()
            mock_semaphore.return_value.__aenter__ = AsyncMock()
            mock_semaphore.return_value.__aexit__ = AsyncMock()

            # Setup httpx client mock
            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock()

            chunks = []
            async for chunk in call_llm_streaming(
                analyzer=mock_analyzer,
                camera_name="test_camera",
                start_time="2025-12-23T14:30:00",
                end_time="2025-12-23T14:31:00",
                detections_list="1. 14:30:00 - person (0.95)",
            ):
                chunks.append(chunk)

            assert chunks == ["Based", " on", " the"]

    @pytest.mark.asyncio
    async def test_call_llm_streaming_handles_empty_content(self, mock_analyzer, mock_settings):
        """Test that streaming skips SSE lines with empty content."""
        sse_lines = [
            'data: {"content": ""}',  # Empty content, should be skipped
            'data: {"content": "Hello"}',
            "data: [DONE]",
        ]

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        async def async_line_generator():
            for line in sse_lines:
                yield line

        mock_response.aiter_lines = async_line_generator

        mock_client = MagicMock()

        class MockStreamCM:
            async def __aenter__(self):
                return mock_response

            async def __aexit__(self, *args):
                pass

        mock_client.stream = MagicMock(return_value=MockStreamCM())

        with (
            patch("backend.services.nemotron_streaming.get_settings", return_value=mock_settings),
            patch("backend.services.nemotron_streaming.get_inference_semaphore") as mock_semaphore,
            patch("httpx.AsyncClient") as mock_httpx,
        ):
            mock_semaphore.return_value = AsyncMock()
            mock_semaphore.return_value.__aenter__ = AsyncMock()
            mock_semaphore.return_value.__aexit__ = AsyncMock()

            mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx.return_value.__aexit__ = AsyncMock()

            chunks = []
            async for chunk in call_llm_streaming(
                analyzer=mock_analyzer,
                camera_name="test_camera",
                start_time="2025-12-23T14:30:00",
                end_time="2025-12-23T14:31:00",
                detections_list="1. 14:30:00 - person (0.95)",
            ):
                chunks.append(chunk)

            # Only non-empty content should be yielded
            assert chunks == ["Hello"]


# Test: analyze_batch_streaming


class TestAnalyzeBatchStreaming:
    """Tests for analyze_batch_streaming function."""

    @pytest.mark.asyncio
    async def test_analyze_batch_streaming_no_redis_returns_error(self, mock_analyzer):
        """Test that missing Redis client returns error event."""
        mock_analyzer._redis = None

        events = []
        async for event in analyze_batch_streaming(
            analyzer=mock_analyzer,
            batch_id="test_batch_123",
        ):
            events.append(event)

        assert len(events) == 1
        assert events[0]["event_type"] == "error"
        assert events[0]["error_code"] == StreamingErrorCode.INTERNAL_ERROR
        assert "Redis" in events[0]["error_message"]

    @pytest.mark.asyncio
    async def test_analyze_batch_streaming_idempotency_hit(self, mock_analyzer, sample_detections):
        """Test that idempotency hit returns existing event."""
        # Setup idempotency hit
        mock_analyzer._check_idempotency = AsyncMock(return_value=123)
        existing_event = Event(
            id=123,
            batch_id="test_batch",
            camera_id="test_camera",
            risk_score=75,
            risk_level="high",
            summary="Existing summary",
            reasoning="Existing reasoning",
        )
        mock_analyzer._get_existing_event = AsyncMock(return_value=existing_event)

        events = []
        async for event in analyze_batch_streaming(
            analyzer=mock_analyzer,
            batch_id="test_batch",
        ):
            events.append(event)

        assert len(events) == 1
        assert events[0]["event_type"] == "complete"
        assert events[0]["event_id"] == 123
        assert events[0]["summary"] == "Existing summary"

    @pytest.mark.asyncio
    async def test_analyze_batch_streaming_batch_not_found(self, mock_analyzer):
        """Test that missing batch returns error event."""
        mock_analyzer._redis.get = AsyncMock(return_value=None)

        events = []
        async for event in analyze_batch_streaming(
            analyzer=mock_analyzer,
            batch_id="nonexistent_batch",
            camera_id=None,  # Force Redis lookup
        ):
            events.append(event)

        assert len(events) == 1
        assert events[0]["event_type"] == "error"
        assert events[0]["error_code"] == StreamingErrorCode.BATCH_NOT_FOUND

    @pytest.mark.asyncio
    async def test_analyze_batch_streaming_no_detections(self, mock_analyzer):
        """Test that empty detection list returns error event."""
        mock_analyzer._redis.get = AsyncMock(return_value="[]")  # Empty detections

        events = []
        async for event in analyze_batch_streaming(
            analyzer=mock_analyzer,
            batch_id="test_batch",
            camera_id="test_camera",
            detection_ids=[],  # Empty list
        ):
            events.append(event)

        assert len(events) == 1
        assert events[0]["event_type"] == "error"
        assert events[0]["error_code"] == StreamingErrorCode.NO_DETECTIONS

    @pytest.mark.asyncio
    async def test_analyze_batch_streaming_invalid_detection_ids(self, mock_analyzer):
        """Test that invalid detection IDs return error event."""
        # Mock the database session to avoid initialization error
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.execute = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_session.execute.return_value = mock_result

        with patch("backend.services.nemotron_streaming.get_session", return_value=mock_session):
            events = []
            async for event in analyze_batch_streaming(
                analyzer=mock_analyzer,
                batch_id="test_batch",
                camera_id="test_camera",
                detection_ids=["invalid", "not_a_number"],  # Invalid IDs
            ):
                events.append(event)

            assert len(events) == 1
            assert events[0]["event_type"] == "error"
            assert events[0]["error_code"] == StreamingErrorCode.INTERNAL_ERROR
            assert "Invalid detection_id" in events[0]["error_message"]


# Test: Error Handling


class TestStreamingErrorHandling:
    """Tests for streaming error handling scenarios."""

    def test_streaming_error_codes_are_strings(self):
        """Test that error codes serialize properly."""
        event = StreamingErrorEvent(
            error_code=StreamingErrorCode.LLM_TIMEOUT,
            error_message="Timeout",
        )
        dumped = event.model_dump()

        assert dumped["error_code"] == "LLM_TIMEOUT"

    def test_all_error_codes_exist(self):
        """Test that all expected error codes are defined."""
        expected_codes = [
            "LLM_TIMEOUT",
            "LLM_CONNECTION_ERROR",
            "LLM_SERVER_ERROR",
            "BATCH_NOT_FOUND",
            "NO_DETECTIONS",
            "CANCELLED",
            "INTERNAL_ERROR",
        ]

        for code in expected_codes:
            assert hasattr(StreamingErrorCode, code), f"Missing error code: {code}"


# Test: SSE Format


class TestSSEFormat:
    """Tests for SSE event formatting."""

    def test_progress_event_model_dump(self):
        """Test progress event serializes correctly for SSE."""
        event = StreamingProgressEvent(
            content="chunk",
            accumulated_text="accumulated chunk",
        )
        dumped = event.model_dump()

        # Should be JSON-serializable
        json_str = json.dumps(dumped)
        parsed = json.loads(json_str)

        assert parsed["event_type"] == "progress"
        assert parsed["content"] == "chunk"
        assert parsed["accumulated_text"] == "accumulated chunk"

    def test_complete_event_model_dump(self):
        """Test complete event serializes correctly for SSE."""
        event = StreamingCompleteEvent(
            event_id=123,
            risk_score=75,
            risk_level="high",
            summary="Test summary",
            reasoning="Test reasoning",
        )
        dumped = event.model_dump()

        json_str = json.dumps(dumped)
        parsed = json.loads(json_str)

        assert parsed["event_type"] == "complete"
        assert parsed["event_id"] == 123
        assert parsed["risk_score"] == 75

    def test_error_event_model_dump(self):
        """Test error event serializes correctly for SSE."""
        event = StreamingErrorEvent(
            error_code=StreamingErrorCode.LLM_TIMEOUT,
            error_message="Connection timed out",
            recoverable=True,
        )
        dumped = event.model_dump()

        json_str = json.dumps(dumped)
        parsed = json.loads(json_str)

        assert parsed["event_type"] == "error"
        assert parsed["error_code"] == "LLM_TIMEOUT"
        assert parsed["recoverable"] is True
