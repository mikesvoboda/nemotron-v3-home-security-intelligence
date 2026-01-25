"""Unit tests for WebSocket batch analysis status schemas (NEM-3607).

Tests for batch analysis status WebSocket message schemas including:
- WebSocketBatchAnalysisStartedData payload validation
- WebSocketBatchAnalysisStartedMessage envelope validation
- WebSocketBatchAnalysisCompletedData payload validation
- WebSocketBatchAnalysisCompletedMessage envelope validation
- WebSocketBatchAnalysisFailedData payload validation
- WebSocketBatchAnalysisFailedMessage envelope validation
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.api.schemas.websocket import (
    WebSocketBatchAnalysisCompletedData,
    WebSocketBatchAnalysisCompletedMessage,
    WebSocketBatchAnalysisFailedData,
    WebSocketBatchAnalysisFailedMessage,
    WebSocketBatchAnalysisStartedData,
    WebSocketBatchAnalysisStartedMessage,
)

# ==============================================================================
# WebSocketBatchAnalysisStartedData Tests
# ==============================================================================


class TestWebSocketBatchAnalysisStartedData:
    """Tests for the WebSocketBatchAnalysisStartedData schema."""

    def test_valid_batch_analysis_started_data(self) -> None:
        """Test valid batch analysis started data with all required fields."""
        data = WebSocketBatchAnalysisStartedData(
            batch_id="batch_abc123",
            camera_id="front_door",
            detection_count=3,
            started_at="2026-01-13T12:01:30.000Z",
        )
        assert data.batch_id == "batch_abc123"
        assert data.camera_id == "front_door"
        assert data.detection_count == 3
        assert data.queue_position is None
        assert data.started_at == "2026-01-13T12:01:30.000Z"

    def test_batch_analysis_started_with_queue_position(self) -> None:
        """Test batch analysis started data with optional queue_position."""
        data = WebSocketBatchAnalysisStartedData(
            batch_id="batch_abc123",
            camera_id="front_door",
            detection_count=5,
            queue_position=2,
            started_at="2026-01-13T12:01:30.000Z",
        )
        assert data.queue_position == 2

    def test_batch_analysis_started_queue_position_zero(self) -> None:
        """Test batch analysis started data with queue_position at zero (front of queue)."""
        data = WebSocketBatchAnalysisStartedData(
            batch_id="batch_abc123",
            camera_id="front_door",
            detection_count=3,
            queue_position=0,
            started_at="2026-01-13T12:01:30.000Z",
        )
        assert data.queue_position == 0

    def test_batch_analysis_started_missing_batch_id_raises(self) -> None:
        """Test that missing batch_id raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketBatchAnalysisStartedData(
                camera_id="front_door",
                detection_count=3,
                started_at="2026-01-13T12:01:30.000Z",
            )
        assert "batch_id" in str(exc_info.value)

    def test_batch_analysis_started_missing_camera_id_raises(self) -> None:
        """Test that missing camera_id raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketBatchAnalysisStartedData(
                batch_id="batch_abc123",
                detection_count=3,
                started_at="2026-01-13T12:01:30.000Z",
            )
        assert "camera_id" in str(exc_info.value)

    def test_batch_analysis_started_negative_detection_count_raises(self) -> None:
        """Test that negative detection_count raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketBatchAnalysisStartedData(
                batch_id="batch_abc123",
                camera_id="front_door",
                detection_count=-1,
                started_at="2026-01-13T12:01:30.000Z",
            )
        assert "detection_count" in str(exc_info.value)

    def test_batch_analysis_started_negative_queue_position_raises(self) -> None:
        """Test that negative queue_position raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketBatchAnalysisStartedData(
                batch_id="batch_abc123",
                camera_id="front_door",
                detection_count=3,
                queue_position=-1,
                started_at="2026-01-13T12:01:30.000Z",
            )
        assert "queue_position" in str(exc_info.value)


# ==============================================================================
# WebSocketBatchAnalysisStartedMessage Tests
# ==============================================================================


class TestWebSocketBatchAnalysisStartedMessage:
    """Tests for the WebSocketBatchAnalysisStartedMessage schema."""

    def test_valid_batch_analysis_started_message(self) -> None:
        """Test valid batch analysis started message envelope."""
        data = WebSocketBatchAnalysisStartedData(
            batch_id="batch_abc123",
            camera_id="front_door",
            detection_count=3,
            started_at="2026-01-13T12:01:30.000Z",
        )
        message = WebSocketBatchAnalysisStartedMessage(data=data)
        assert message.type == "batch.analysis_started"
        assert message.data.batch_id == "batch_abc123"

    def test_batch_analysis_started_message_type_is_literal(self) -> None:
        """Test that message type is the correct literal value."""
        data = WebSocketBatchAnalysisStartedData(
            batch_id="batch_abc123",
            camera_id="front_door",
            detection_count=3,
            started_at="2026-01-13T12:01:30.000Z",
        )
        message = WebSocketBatchAnalysisStartedMessage(data=data)
        assert message.type == "batch.analysis_started"

    def test_batch_analysis_started_message_serialization(self) -> None:
        """Test that message serializes correctly to JSON-compatible dict."""
        data = WebSocketBatchAnalysisStartedData(
            batch_id="batch_abc123",
            camera_id="front_door",
            detection_count=3,
            queue_position=0,
            started_at="2026-01-13T12:01:30.000Z",
        )
        message = WebSocketBatchAnalysisStartedMessage(data=data)
        output = message.model_dump(mode="json")

        assert output["type"] == "batch.analysis_started"
        assert output["data"]["batch_id"] == "batch_abc123"
        assert output["data"]["camera_id"] == "front_door"
        assert output["data"]["detection_count"] == 3
        assert output["data"]["queue_position"] == 0


# ==============================================================================
# WebSocketBatchAnalysisCompletedData Tests
# ==============================================================================


class TestWebSocketBatchAnalysisCompletedData:
    """Tests for the WebSocketBatchAnalysisCompletedData schema."""

    def test_valid_batch_analysis_completed_data(self) -> None:
        """Test valid batch analysis completed data with all required fields."""
        data = WebSocketBatchAnalysisCompletedData(
            batch_id="batch_abc123",
            camera_id="front_door",
            event_id=42,
            risk_score=75,
            risk_level="high",
            duration_ms=2500,
            completed_at="2026-01-13T12:01:35.000Z",
        )
        assert data.batch_id == "batch_abc123"
        assert data.camera_id == "front_door"
        assert data.event_id == 42
        assert data.risk_score == 75
        assert data.risk_level == "high"
        assert data.duration_ms == 2500
        assert data.completed_at == "2026-01-13T12:01:35.000Z"

    def test_batch_analysis_completed_all_risk_levels(self) -> None:
        """Test batch analysis completed data accepts all valid risk levels."""
        for risk_level in ["low", "medium", "high", "critical"]:
            data = WebSocketBatchAnalysisCompletedData(
                batch_id="batch_abc123",
                camera_id="front_door",
                event_id=42,
                risk_score=50,
                risk_level=risk_level,
                duration_ms=2500,
                completed_at="2026-01-13T12:01:35.000Z",
            )
            assert data.risk_level == risk_level

    def test_batch_analysis_completed_risk_score_boundary_values(self) -> None:
        """Test batch analysis completed data with boundary risk scores."""
        # Test minimum (0)
        data_min = WebSocketBatchAnalysisCompletedData(
            batch_id="batch_abc123",
            camera_id="front_door",
            event_id=42,
            risk_score=0,
            risk_level="low",
            duration_ms=2500,
            completed_at="2026-01-13T12:01:35.000Z",
        )
        assert data_min.risk_score == 0

        # Test maximum (100)
        data_max = WebSocketBatchAnalysisCompletedData(
            batch_id="batch_abc123",
            camera_id="front_door",
            event_id=42,
            risk_score=100,
            risk_level="critical",
            duration_ms=2500,
            completed_at="2026-01-13T12:01:35.000Z",
        )
        assert data_max.risk_score == 100

    def test_batch_analysis_completed_risk_score_below_minimum_raises(self) -> None:
        """Test that risk_score below 0 raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketBatchAnalysisCompletedData(
                batch_id="batch_abc123",
                camera_id="front_door",
                event_id=42,
                risk_score=-1,
                risk_level="low",
                duration_ms=2500,
                completed_at="2026-01-13T12:01:35.000Z",
            )
        assert "risk_score" in str(exc_info.value)

    def test_batch_analysis_completed_risk_score_above_maximum_raises(self) -> None:
        """Test that risk_score above 100 raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketBatchAnalysisCompletedData(
                batch_id="batch_abc123",
                camera_id="front_door",
                event_id=42,
                risk_score=101,
                risk_level="critical",
                duration_ms=2500,
                completed_at="2026-01-13T12:01:35.000Z",
            )
        assert "risk_score" in str(exc_info.value)

    def test_batch_analysis_completed_missing_event_id_raises(self) -> None:
        """Test that missing event_id raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketBatchAnalysisCompletedData(
                batch_id="batch_abc123",
                camera_id="front_door",
                risk_score=75,
                risk_level="high",
                duration_ms=2500,
                completed_at="2026-01-13T12:01:35.000Z",
            )
        assert "event_id" in str(exc_info.value)

    def test_batch_analysis_completed_negative_duration_ms_raises(self) -> None:
        """Test that negative duration_ms raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketBatchAnalysisCompletedData(
                batch_id="batch_abc123",
                camera_id="front_door",
                event_id=42,
                risk_score=75,
                risk_level="high",
                duration_ms=-100,
                completed_at="2026-01-13T12:01:35.000Z",
            )
        assert "duration_ms" in str(exc_info.value)


# ==============================================================================
# WebSocketBatchAnalysisCompletedMessage Tests
# ==============================================================================


class TestWebSocketBatchAnalysisCompletedMessage:
    """Tests for the WebSocketBatchAnalysisCompletedMessage schema."""

    def test_valid_batch_analysis_completed_message(self) -> None:
        """Test valid batch analysis completed message envelope."""
        data = WebSocketBatchAnalysisCompletedData(
            batch_id="batch_abc123",
            camera_id="front_door",
            event_id=42,
            risk_score=75,
            risk_level="high",
            duration_ms=2500,
            completed_at="2026-01-13T12:01:35.000Z",
        )
        message = WebSocketBatchAnalysisCompletedMessage(data=data)
        assert message.type == "batch.analysis_completed"
        assert message.data.event_id == 42
        assert message.data.risk_score == 75

    def test_batch_analysis_completed_message_serialization(self) -> None:
        """Test that message serializes correctly to JSON-compatible dict."""
        data = WebSocketBatchAnalysisCompletedData(
            batch_id="batch_abc123",
            camera_id="front_door",
            event_id=42,
            risk_score=75,
            risk_level="high",
            duration_ms=2500,
            completed_at="2026-01-13T12:01:35.000Z",
        )
        message = WebSocketBatchAnalysisCompletedMessage(data=data)
        output = message.model_dump(mode="json")

        assert output["type"] == "batch.analysis_completed"
        assert output["data"]["event_id"] == 42
        assert output["data"]["risk_score"] == 75
        assert output["data"]["risk_level"] == "high"
        assert output["data"]["duration_ms"] == 2500


# ==============================================================================
# WebSocketBatchAnalysisFailedData Tests
# ==============================================================================


class TestWebSocketBatchAnalysisFailedData:
    """Tests for the WebSocketBatchAnalysisFailedData schema."""

    def test_valid_batch_analysis_failed_data(self) -> None:
        """Test valid batch analysis failed data with all required fields."""
        data = WebSocketBatchAnalysisFailedData(
            batch_id="batch_abc123",
            camera_id="front_door",
            error="LLM service timeout after 120 seconds",
            error_type="timeout",
            retryable=True,
            failed_at="2026-01-13T12:03:30.000Z",
        )
        assert data.batch_id == "batch_abc123"
        assert data.camera_id == "front_door"
        assert data.error == "LLM service timeout after 120 seconds"
        assert data.error_type == "timeout"
        assert data.retryable is True
        assert data.failed_at == "2026-01-13T12:03:30.000Z"

    def test_batch_analysis_failed_various_error_types(self) -> None:
        """Test batch analysis failed data accepts various error types."""
        for error_type in ["timeout", "connection", "validation", "processing", "unknown"]:
            data = WebSocketBatchAnalysisFailedData(
                batch_id="batch_abc123",
                camera_id="front_door",
                error="Test error",
                error_type=error_type,
                retryable=False,
                failed_at="2026-01-13T12:03:30.000Z",
            )
            assert data.error_type == error_type

    def test_batch_analysis_failed_retryable_true(self) -> None:
        """Test batch analysis failed data with retryable=True."""
        data = WebSocketBatchAnalysisFailedData(
            batch_id="batch_abc123",
            camera_id="front_door",
            error="Connection timeout",
            error_type="timeout",
            retryable=True,
            failed_at="2026-01-13T12:03:30.000Z",
        )
        assert data.retryable is True

    def test_batch_analysis_failed_retryable_false(self) -> None:
        """Test batch analysis failed data with retryable=False."""
        data = WebSocketBatchAnalysisFailedData(
            batch_id="batch_abc123",
            camera_id="front_door",
            error="Invalid batch format",
            error_type="validation",
            retryable=False,
            failed_at="2026-01-13T12:03:30.000Z",
        )
        assert data.retryable is False

    def test_batch_analysis_failed_missing_error_raises(self) -> None:
        """Test that missing error field raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketBatchAnalysisFailedData(
                batch_id="batch_abc123",
                camera_id="front_door",
                error_type="timeout",
                retryable=True,
                failed_at="2026-01-13T12:03:30.000Z",
            )
        assert "error" in str(exc_info.value)

    def test_batch_analysis_failed_missing_error_type_raises(self) -> None:
        """Test that missing error_type field raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketBatchAnalysisFailedData(
                batch_id="batch_abc123",
                camera_id="front_door",
                error="Test error",
                retryable=True,
                failed_at="2026-01-13T12:03:30.000Z",
            )
        assert "error_type" in str(exc_info.value)

    def test_batch_analysis_failed_missing_retryable_raises(self) -> None:
        """Test that missing retryable field raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketBatchAnalysisFailedData(
                batch_id="batch_abc123",
                camera_id="front_door",
                error="Test error",
                error_type="timeout",
                failed_at="2026-01-13T12:03:30.000Z",
            )
        assert "retryable" in str(exc_info.value)


# ==============================================================================
# WebSocketBatchAnalysisFailedMessage Tests
# ==============================================================================


class TestWebSocketBatchAnalysisFailedMessage:
    """Tests for the WebSocketBatchAnalysisFailedMessage schema."""

    def test_valid_batch_analysis_failed_message(self) -> None:
        """Test valid batch analysis failed message envelope."""
        data = WebSocketBatchAnalysisFailedData(
            batch_id="batch_abc123",
            camera_id="front_door",
            error="LLM service timeout",
            error_type="timeout",
            retryable=True,
            failed_at="2026-01-13T12:03:30.000Z",
        )
        message = WebSocketBatchAnalysisFailedMessage(data=data)
        assert message.type == "batch.analysis_failed"
        assert message.data.error == "LLM service timeout"
        assert message.data.retryable is True

    def test_batch_analysis_failed_message_serialization(self) -> None:
        """Test that message serializes correctly to JSON-compatible dict."""
        data = WebSocketBatchAnalysisFailedData(
            batch_id="batch_abc123",
            camera_id="front_door",
            error="LLM service timeout",
            error_type="timeout",
            retryable=True,
            failed_at="2026-01-13T12:03:30.000Z",
        )
        message = WebSocketBatchAnalysisFailedMessage(data=data)
        output = message.model_dump(mode="json")

        assert output["type"] == "batch.analysis_failed"
        assert output["data"]["batch_id"] == "batch_abc123"
        assert output["data"]["error"] == "LLM service timeout"
        assert output["data"]["error_type"] == "timeout"
        assert output["data"]["retryable"] is True
