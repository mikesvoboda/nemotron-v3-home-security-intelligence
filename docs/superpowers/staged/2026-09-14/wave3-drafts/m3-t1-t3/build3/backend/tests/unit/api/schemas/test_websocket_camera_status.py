"""Unit tests for WebSocket camera status schemas (NEM-2295).

Tests for camera status WebSocket message schemas including:
- WebSocketCameraEventType enum validation
- WebSocketCameraStatusData payload validation
- WebSocketCameraStatusMessage envelope validation
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.api.schemas.websocket import (
    WebSocketCameraEventType,
    WebSocketCameraStatus,
    WebSocketCameraStatusData,
    WebSocketCameraStatusMessage,
)

# ==============================================================================
# WebSocketCameraEventType Tests
# ==============================================================================


class TestWebSocketCameraEventType:
    """Tests for the WebSocketCameraEventType enum."""

    def test_camera_online_event_type(self) -> None:
        """Test CAMERA_ONLINE event type value."""
        assert WebSocketCameraEventType.CAMERA_ONLINE.value == "camera.online"

    def test_camera_offline_event_type(self) -> None:
        """Test CAMERA_OFFLINE event type value."""
        assert WebSocketCameraEventType.CAMERA_OFFLINE.value == "camera.offline"

    def test_camera_error_event_type(self) -> None:
        """Test CAMERA_ERROR event type value."""
        assert WebSocketCameraEventType.CAMERA_ERROR.value == "camera.error"

    def test_camera_updated_event_type(self) -> None:
        """Test CAMERA_UPDATED event type value."""
        assert WebSocketCameraEventType.CAMERA_UPDATED.value == "camera.updated"

    def test_all_event_types_defined(self) -> None:
        """Test that all expected event types are defined."""
        expected = {"camera.online", "camera.offline", "camera.error", "camera.updated"}
        actual = {e.value for e in WebSocketCameraEventType}
        assert actual == expected


# ==============================================================================
# WebSocketCameraStatusData Tests
# ==============================================================================


class TestWebSocketCameraStatusData:
    """Tests for the WebSocketCameraStatusData schema."""

    def test_valid_camera_status_data(self) -> None:
        """Test valid camera status data with all required fields."""
        data = WebSocketCameraStatusData(
            event_type="camera.offline",
            camera_id="front_door",
            camera_name="Front Door Camera",
            status="offline",
            timestamp="2026-01-09T10:30:00Z",
        )
        assert data.event_type == WebSocketCameraEventType.CAMERA_OFFLINE
        assert data.camera_id == "front_door"
        assert data.camera_name == "Front Door Camera"
        assert data.status == WebSocketCameraStatus.OFFLINE
        assert data.timestamp == "2026-01-09T10:30:00Z"

    def test_camera_status_data_with_all_optional_fields(self) -> None:
        """Test camera status data with all optional fields populated."""
        data = WebSocketCameraStatusData(
            event_type="camera.online",
            camera_id="back_yard",
            camera_name="Back Yard Camera",
            status="online",
            timestamp="2026-01-09T10:30:00Z",
            previous_status="offline",
            reason="Camera reconnected",
            details={"ip_address": "192.168.1.100"},
        )
        assert data.previous_status == WebSocketCameraStatus.OFFLINE
        assert data.reason == "Camera reconnected"
        assert data.details == {"ip_address": "192.168.1.100"}

    def test_camera_status_data_optional_fields_default_none(self) -> None:
        """Test that optional fields default to None."""
        data = WebSocketCameraStatusData(
            event_type="camera.online",
            camera_id="front_door",
            camera_name="Front Door Camera",
            status="online",
            timestamp="2026-01-09T10:30:00Z",
        )
        assert data.previous_status is None
        assert data.reason is None
        assert data.details is None

    def test_camera_status_data_requires_event_type(self) -> None:
        """Test that event_type is required."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketCameraStatusData(
                camera_id="front_door",
                camera_name="Front Door Camera",
                status="online",
                timestamp="2026-01-09T10:30:00Z",
            )
        assert "event_type" in str(exc_info.value)

    def test_camera_status_data_requires_camera_id(self) -> None:
        """Test that camera_id is required."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketCameraStatusData(
                event_type="camera.online",
                camera_name="Front Door Camera",
                status="online",
                timestamp="2026-01-09T10:30:00Z",
            )
        assert "camera_id" in str(exc_info.value)

    def test_camera_status_data_requires_camera_name(self) -> None:
        """Test that camera_name is required."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketCameraStatusData(
                event_type="camera.online",
                camera_id="front_door",
                status="online",
                timestamp="2026-01-09T10:30:00Z",
            )
        assert "camera_name" in str(exc_info.value)

    def test_camera_status_data_requires_timestamp(self) -> None:
        """Test that timestamp is required."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketCameraStatusData(
                event_type="camera.online",
                camera_id="front_door",
                camera_name="Front Door Camera",
                status="online",
            )
        assert "timestamp" in str(exc_info.value)

    def test_camera_status_data_validates_event_type(self) -> None:
        """Test that invalid event_type values are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketCameraStatusData(
                event_type="invalid.event",
                camera_id="front_door",
                camera_name="Front Door Camera",
                status="online",
                timestamp="2026-01-09T10:30:00Z",
            )
        assert "event_type" in str(exc_info.value)

    def test_camera_status_data_validates_status(self) -> None:
        """Test that invalid status values are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketCameraStatusData(
                event_type="camera.online",
                camera_id="front_door",
                camera_name="Front Door Camera",
                status="invalid_status",
                timestamp="2026-01-09T10:30:00Z",
            )
        assert "status" in str(exc_info.value)

    def test_camera_status_data_enum_conversion_from_string(self) -> None:
        """Test that string event_type values are converted to enum."""
        data = WebSocketCameraStatusData(
            event_type="camera.error",
            camera_id="front_door",
            camera_name="Front Door Camera",
            status="error",
            timestamp="2026-01-09T10:30:00Z",
        )
        assert isinstance(data.event_type, WebSocketCameraEventType)
        assert data.event_type == WebSocketCameraEventType.CAMERA_ERROR

    def test_camera_status_data_status_enum_conversion(self) -> None:
        """Test that status values are converted to WebSocketCameraStatus enum."""
        data = WebSocketCameraStatusData(
            event_type="camera.error",
            camera_id="front_door",
            camera_name="Front Door Camera",
            status="error",
            timestamp="2026-01-09T10:30:00Z",
        )
        assert isinstance(data.status, WebSocketCameraStatus)
        assert data.status == WebSocketCameraStatus.ERROR

    def test_camera_status_data_json_serialization(self) -> None:
        """Test JSON serialization includes all fields."""
        data = WebSocketCameraStatusData(
            event_type="camera.offline",
            camera_id="front_door",
            camera_name="Front Door Camera",
            status="offline",
            timestamp="2026-01-09T10:30:00Z",
            previous_status="online",
            reason="Connection timeout",
        )
        json_dict = data.model_dump(mode="json")

        assert json_dict["event_type"] == "camera.offline"
        assert json_dict["camera_id"] == "front_door"
        assert json_dict["camera_name"] == "Front Door Camera"
        assert json_dict["status"] == "offline"
        assert json_dict["timestamp"] == "2026-01-09T10:30:00Z"
        assert json_dict["previous_status"] == "online"
        assert json_dict["reason"] == "Connection timeout"


# ==============================================================================
# WebSocketCameraStatusMessage Tests
# ==============================================================================


class TestWebSocketCameraStatusMessage:
    """Tests for the WebSocketCameraStatusMessage envelope schema."""

    def test_valid_camera_status_message(self) -> None:
        """Test valid camera status message envelope."""
        data = WebSocketCameraStatusData(
            event_type="camera.online",
            camera_id="front_door",
            camera_name="Front Door Camera",
            status="online",
            timestamp="2026-01-09T10:30:00Z",
        )
        message = WebSocketCameraStatusMessage(data=data)

        assert message.type == "camera_status"
        assert message.data == data

    def test_camera_status_message_type_is_literal(self) -> None:
        """Test that message type is always 'camera_status'."""
        data = WebSocketCameraStatusData(
            event_type="camera.offline",
            camera_id="front_door",
            camera_name="Front Door Camera",
            status="offline",
            timestamp="2026-01-09T10:30:00Z",
        )
        message = WebSocketCameraStatusMessage(data=data)

        # Type should always be "camera_status"
        assert message.type == "camera_status"

    def test_camera_status_message_json_serialization(self) -> None:
        """Test JSON serialization of message envelope."""
        data = WebSocketCameraStatusData(
            event_type="camera.error",
            camera_id="garage",
            camera_name="Garage Camera",
            status="error",
            timestamp="2026-01-09T10:30:00Z",
            reason="Hardware malfunction",
        )
        message = WebSocketCameraStatusMessage(data=data)
        json_dict = message.model_dump(mode="json")

        assert json_dict["type"] == "camera_status"
        assert json_dict["data"]["event_type"] == "camera.error"
        assert json_dict["data"]["camera_id"] == "garage"
        assert json_dict["data"]["camera_name"] == "Garage Camera"
        assert json_dict["data"]["status"] == "error"
        assert json_dict["data"]["reason"] == "Hardware malfunction"

    def test_camera_status_message_requires_data(self) -> None:
        """Test that data field is required."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketCameraStatusMessage()  # type: ignore[call-arg]
        assert "data" in str(exc_info.value)
