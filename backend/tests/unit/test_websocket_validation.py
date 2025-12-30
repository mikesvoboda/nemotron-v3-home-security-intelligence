"""Unit tests for WebSocket message validation.

Tests cover:
- WebSocket schema validation (Pydantic models)
- JSON parsing error handling
- Invalid message format handling
- Unknown message type handling
- Message handler routing
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from backend.api.schemas.websocket import (
    RiskLevel,
    ServiceStatus,
    WebSocketErrorCode,
    WebSocketErrorResponse,
    WebSocketEventData,
    WebSocketEventMessage,
    WebSocketMessage,
    WebSocketMessageType,
    WebSocketPingMessage,
    WebSocketPongResponse,
    WebSocketServiceStatusData,
    WebSocketServiceStatusMessage,
    WebSocketSubscribeMessage,
    WebSocketUnsubscribeMessage,
)

# =============================================================================
# Schema Validation Tests
# =============================================================================


class TestWebSocketMessageSchema:
    """Tests for WebSocketMessage schema validation."""

    def test_valid_ping_message(self) -> None:
        """Test that a valid ping message passes validation."""
        message_data = {"type": "ping"}
        message = WebSocketMessage.model_validate(message_data)
        assert message.type == "ping"
        assert message.data is None

    def test_valid_message_with_data(self) -> None:
        """Test that a message with data passes validation."""
        message_data = {"type": "subscribe", "data": {"channels": ["events"]}}
        message = WebSocketMessage.model_validate(message_data)
        assert message.type == "subscribe"
        assert message.data == {"channels": ["events"]}

    def test_missing_type_field_fails(self) -> None:
        """Test that a message without type field fails validation."""
        message_data = {"data": {"some": "value"}}
        with pytest.raises(ValidationError) as exc_info:
            WebSocketMessage.model_validate(message_data)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("type",) for e in errors)

    def test_empty_type_field_fails(self) -> None:
        """Test that an empty type field fails validation."""
        message_data = {"type": ""}
        with pytest.raises(ValidationError) as exc_info:
            WebSocketMessage.model_validate(message_data)
        errors = exc_info.value.errors()
        assert any("type" in str(e["loc"]) for e in errors)

    def test_type_too_long_fails(self) -> None:
        """Test that a type field exceeding max length fails validation."""
        message_data = {"type": "x" * 51}  # Max is 50
        with pytest.raises(ValidationError) as exc_info:
            WebSocketMessage.model_validate(message_data)
        errors = exc_info.value.errors()
        assert any("type" in str(e["loc"]) for e in errors)

    def test_extra_fields_allowed(self) -> None:
        """Test that extra fields are allowed for forward compatibility."""
        message_data = {"type": "ping", "extra_field": "value", "another": 123}
        message = WebSocketMessage.model_validate(message_data)
        assert message.type == "ping"


class TestWebSocketPingMessage:
    """Tests for WebSocketPingMessage schema."""

    def test_valid_ping(self) -> None:
        """Test valid ping message."""
        message = WebSocketPingMessage(type="ping")
        assert message.type == "ping"

    def test_invalid_type_fails(self) -> None:
        """Test that non-ping type fails."""
        with pytest.raises(ValidationError):
            WebSocketPingMessage(type="pong")  # type: ignore[arg-type]


class TestWebSocketSubscribeMessage:
    """Tests for WebSocketSubscribeMessage schema."""

    def test_valid_subscribe(self) -> None:
        """Test valid subscribe message."""
        message = WebSocketSubscribeMessage(type="subscribe", channels=["events"])
        assert message.type == "subscribe"
        assert message.channels == ["events"]

    def test_multiple_channels(self) -> None:
        """Test subscribe with multiple channels."""
        message = WebSocketSubscribeMessage(
            type="subscribe", channels=["events", "detections", "system"]
        )
        assert len(message.channels) == 3

    def test_empty_channels_fails(self) -> None:
        """Test that empty channels list fails."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketSubscribeMessage(type="subscribe", channels=[])
        errors = exc_info.value.errors()
        assert any("channels" in str(e["loc"]) for e in errors)

    def test_too_many_channels_fails(self) -> None:
        """Test that too many channels fails (max 10)."""
        with pytest.raises(ValidationError) as exc_info:
            WebSocketSubscribeMessage(
                type="subscribe",
                channels=[f"channel{i}" for i in range(11)],
            )
        errors = exc_info.value.errors()
        assert any("channels" in str(e["loc"]) for e in errors)


class TestWebSocketUnsubscribeMessage:
    """Tests for WebSocketUnsubscribeMessage schema."""

    def test_valid_unsubscribe(self) -> None:
        """Test valid unsubscribe message."""
        message = WebSocketUnsubscribeMessage(type="unsubscribe", channels=["events"])
        assert message.type == "unsubscribe"
        assert message.channels == ["events"]


class TestWebSocketErrorResponse:
    """Tests for WebSocketErrorResponse schema."""

    def test_basic_error(self) -> None:
        """Test basic error response."""
        error = WebSocketErrorResponse(
            error="invalid_json",
            message="Message must be valid JSON",
        )
        assert error.type == "error"
        assert error.error == "invalid_json"
        assert error.details is None

    def test_error_with_details(self) -> None:
        """Test error response with details."""
        error = WebSocketErrorResponse(
            error="validation_error",
            message="Invalid message format",
            details={"field": "type", "issue": "missing"},
        )
        assert error.type == "error"
        assert error.details == {"field": "type", "issue": "missing"}

    def test_error_serialization(self) -> None:
        """Test that error response serializes to JSON correctly."""
        error = WebSocketErrorResponse(
            error="invalid_json",
            message="Test error",
        )
        json_str = error.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["type"] == "error"
        assert parsed["error"] == "invalid_json"
        assert parsed["message"] == "Test error"


class TestWebSocketPongResponse:
    """Tests for WebSocketPongResponse schema."""

    def test_pong_response(self) -> None:
        """Test pong response."""
        pong = WebSocketPongResponse()
        assert pong.type == "pong"

    def test_pong_serialization(self) -> None:
        """Test that pong response serializes correctly."""
        pong = WebSocketPongResponse()
        json_str = pong.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed == {"type": "pong"}


class TestWebSocketMessageType:
    """Tests for WebSocketMessageType enum."""

    def test_enum_values(self) -> None:
        """Test that enum has expected values."""
        assert WebSocketMessageType.PING.value == "ping"
        assert WebSocketMessageType.SUBSCRIBE.value == "subscribe"
        assert WebSocketMessageType.UNSUBSCRIBE.value == "unsubscribe"


class TestWebSocketErrorCode:
    """Tests for WebSocketErrorCode constants."""

    def test_error_codes(self) -> None:
        """Test that error codes are defined."""
        assert WebSocketErrorCode.INVALID_JSON == "invalid_json"
        assert WebSocketErrorCode.INVALID_MESSAGE_FORMAT == "invalid_message_format"
        assert WebSocketErrorCode.UNKNOWN_MESSAGE_TYPE == "unknown_message_type"
        assert WebSocketErrorCode.VALIDATION_ERROR == "validation_error"


# =============================================================================
# Message Validation Function Tests
# =============================================================================


class TestValidateWebSocketMessage:
    """Tests for the validate_websocket_message function."""

    @pytest.fixture
    def mock_websocket(self) -> MagicMock:
        """Create a mock WebSocket."""
        ws = MagicMock()
        ws.send_text = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_valid_json_message(self, mock_websocket: MagicMock) -> None:
        """Test validation of a valid JSON message."""
        from backend.api.routes.websocket import validate_websocket_message

        raw_data = '{"type": "ping"}'
        result = await validate_websocket_message(mock_websocket, raw_data)

        assert result is not None
        assert result.type == "ping"
        mock_websocket.send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_json_sends_error(self, mock_websocket: MagicMock) -> None:
        """Test that invalid JSON sends an error response."""
        from backend.api.routes.websocket import validate_websocket_message

        raw_data = "not valid json {"
        result = await validate_websocket_message(mock_websocket, raw_data)

        assert result is None
        mock_websocket.send_text.assert_called_once()
        # Check the error response
        call_args = mock_websocket.send_text.call_args[0][0]
        error_response = json.loads(call_args)
        assert error_response["type"] == "error"
        assert error_response["error"] == WebSocketErrorCode.INVALID_JSON
        assert "JSON" in error_response["message"]

    @pytest.mark.asyncio
    async def test_empty_json_object_fails(self, mock_websocket: MagicMock) -> None:
        """Test that empty JSON object fails validation."""
        from backend.api.routes.websocket import validate_websocket_message

        raw_data = "{}"
        result = await validate_websocket_message(mock_websocket, raw_data)

        assert result is None
        mock_websocket.send_text.assert_called_once()
        call_args = mock_websocket.send_text.call_args[0][0]
        error_response = json.loads(call_args)
        assert error_response["type"] == "error"
        assert error_response["error"] == WebSocketErrorCode.INVALID_MESSAGE_FORMAT

    @pytest.mark.asyncio
    async def test_missing_type_field_fails(self, mock_websocket: MagicMock) -> None:
        """Test that missing type field fails validation."""
        from backend.api.routes.websocket import validate_websocket_message

        raw_data = '{"data": {"key": "value"}}'
        result = await validate_websocket_message(mock_websocket, raw_data)

        assert result is None
        mock_websocket.send_text.assert_called_once()
        call_args = mock_websocket.send_text.call_args[0][0]
        error_response = json.loads(call_args)
        assert error_response["type"] == "error"
        assert error_response["error"] == WebSocketErrorCode.INVALID_MESSAGE_FORMAT
        assert "validation_errors" in error_response["details"]

    @pytest.mark.asyncio
    async def test_truncated_raw_data_in_error(self, mock_websocket: MagicMock) -> None:
        """Test that long invalid data is truncated in error details."""
        from backend.api.routes.websocket import validate_websocket_message

        # Create a long invalid string
        raw_data = "x" * 200
        result = await validate_websocket_message(mock_websocket, raw_data)

        assert result is None
        call_args = mock_websocket.send_text.call_args[0][0]
        error_response = json.loads(call_args)
        # Preview should be truncated to 100 chars
        assert len(error_response["details"]["raw_data_preview"]) == 100


class TestHandleValidatedMessage:
    """Tests for the handle_validated_message function."""

    @pytest.fixture
    def mock_websocket(self) -> MagicMock:
        """Create a mock WebSocket."""
        ws = MagicMock()
        ws.send_text = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_ping_sends_pong(self, mock_websocket: MagicMock) -> None:
        """Test that ping message results in pong response."""
        from backend.api.routes.websocket import handle_validated_message

        message = WebSocketMessage(type="ping")
        await handle_validated_message(mock_websocket, message)

        mock_websocket.send_text.assert_called_once()
        call_args = mock_websocket.send_text.call_args[0][0]
        response = json.loads(call_args)
        assert response["type"] == "pong"

    @pytest.mark.asyncio
    async def test_ping_case_insensitive(self, mock_websocket: MagicMock) -> None:
        """Test that PING (uppercase) also works."""
        from backend.api.routes.websocket import handle_validated_message

        message = WebSocketMessage(type="PING")
        await handle_validated_message(mock_websocket, message)

        mock_websocket.send_text.assert_called_once()
        call_args = mock_websocket.send_text.call_args[0][0]
        response = json.loads(call_args)
        assert response["type"] == "pong"

    @pytest.mark.asyncio
    async def test_unknown_type_sends_error(self, mock_websocket: MagicMock) -> None:
        """Test that unknown message type sends error response."""
        from backend.api.routes.websocket import handle_validated_message

        message = WebSocketMessage(type="unknown_type")
        await handle_validated_message(mock_websocket, message)

        mock_websocket.send_text.assert_called_once()
        call_args = mock_websocket.send_text.call_args[0][0]
        response = json.loads(call_args)
        assert response["type"] == "error"
        assert response["error"] == WebSocketErrorCode.UNKNOWN_MESSAGE_TYPE
        assert "supported_types" in response["details"]

    @pytest.mark.asyncio
    async def test_subscribe_handled_gracefully(self, mock_websocket: MagicMock) -> None:
        """Test that subscribe message is handled (future functionality)."""
        from backend.api.routes.websocket import handle_validated_message

        message = WebSocketMessage(type="subscribe", data={"channels": ["events"]})
        await handle_validated_message(mock_websocket, message)

        # Currently subscribe is just logged, no response sent
        mock_websocket.send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_unsubscribe_handled_gracefully(self, mock_websocket: MagicMock) -> None:
        """Test that unsubscribe message is handled (future functionality)."""
        from backend.api.routes.websocket import handle_validated_message

        message = WebSocketMessage(type="unsubscribe", data={"channels": ["events"]})
        await handle_validated_message(mock_websocket, message)

        # Currently unsubscribe is just logged, no response sent
        mock_websocket.send_text.assert_not_called()


# =============================================================================
# Integration Tests for WebSocket Message Flow
# =============================================================================


class TestWebSocketMessageFlow:
    """Integration tests for complete message validation and handling flow."""

    @pytest.fixture
    def mock_websocket(self) -> MagicMock:
        """Create a mock WebSocket."""
        ws = MagicMock()
        ws.send_text = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_complete_ping_flow(self, mock_websocket: MagicMock) -> None:
        """Test complete ping message flow from raw data to pong response."""
        from backend.api.routes.websocket import (
            handle_validated_message,
            validate_websocket_message,
        )

        # Raw JSON ping message
        raw_data = '{"type": "ping"}'

        # Validate
        message = await validate_websocket_message(mock_websocket, raw_data)
        assert message is not None

        # Handle
        await handle_validated_message(mock_websocket, message)

        # Verify pong response
        mock_websocket.send_text.assert_called_once()
        response = json.loads(mock_websocket.send_text.call_args[0][0])
        assert response == {"type": "pong"}

    @pytest.mark.asyncio
    async def test_malformed_json_error_flow(self, mock_websocket: MagicMock) -> None:
        """Test that malformed JSON results in proper error response."""
        from backend.api.routes.websocket import validate_websocket_message

        raw_data = '{"type": "ping"'  # Missing closing brace
        result = await validate_websocket_message(mock_websocket, raw_data)

        assert result is None
        response = json.loads(mock_websocket.send_text.call_args[0][0])
        assert response["type"] == "error"
        assert response["error"] == "invalid_json"

    @pytest.mark.asyncio
    async def test_null_json_value(self, mock_websocket: MagicMock) -> None:
        """Test handling of null JSON value."""
        from backend.api.routes.websocket import validate_websocket_message

        raw_data = "null"
        result = await validate_websocket_message(mock_websocket, raw_data)

        assert result is None
        mock_websocket.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_json_array_fails(self, mock_websocket: MagicMock) -> None:
        """Test that JSON array (not object) fails validation."""
        from backend.api.routes.websocket import validate_websocket_message

        raw_data = '["ping"]'
        result = await validate_websocket_message(mock_websocket, raw_data)

        assert result is None
        mock_websocket.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_json_primitive_fails(self, mock_websocket: MagicMock) -> None:
        """Test that JSON primitive fails validation."""
        from backend.api.routes.websocket import validate_websocket_message

        raw_data = '"ping"'
        result = await validate_websocket_message(mock_websocket, raw_data)

        assert result is None
        mock_websocket.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_special_characters_in_type(self, mock_websocket: MagicMock) -> None:
        """Test message with special characters in type."""
        from backend.api.routes.websocket import (
            handle_validated_message,
            validate_websocket_message,
        )

        raw_data = '{"type": "test-type_123"}'
        message = await validate_websocket_message(mock_websocket, raw_data)
        assert message is not None

        # Should result in unknown type error
        await handle_validated_message(mock_websocket, message)
        response = json.loads(mock_websocket.send_text.call_args[0][0])
        assert response["type"] == "error"
        assert response["error"] == "unknown_message_type"


# =============================================================================
# RiskLevel Enum Tests
# =============================================================================


class TestRiskLevel:
    """Tests for RiskLevel enum."""

    def test_risk_level_values(self) -> None:
        """Test that RiskLevel enum has expected values."""
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"

    def test_risk_level_str(self) -> None:
        """Test RiskLevel __str__ method returns the value."""
        # This tests line 39: return self.value
        assert str(RiskLevel.LOW) == "low"
        assert str(RiskLevel.MEDIUM) == "medium"
        assert str(RiskLevel.HIGH) == "high"
        assert str(RiskLevel.CRITICAL) == "critical"

    def test_risk_level_string_comparison(self) -> None:
        """Test that RiskLevel can be compared with strings."""
        assert RiskLevel.LOW == "low"
        assert RiskLevel.HIGH == "high"


# =============================================================================
# ServiceStatus Enum Tests
# =============================================================================


class TestServiceStatus:
    """Tests for ServiceStatus enum."""

    def test_service_status_values(self) -> None:
        """Test that ServiceStatus enum has expected values."""
        assert ServiceStatus.HEALTHY.value == "healthy"
        assert ServiceStatus.UNHEALTHY.value == "unhealthy"
        assert ServiceStatus.RESTARTING.value == "restarting"
        assert ServiceStatus.RESTART_FAILED.value == "restart_failed"
        assert ServiceStatus.FAILED.value == "failed"

    def test_service_status_str(self) -> None:
        """Test ServiceStatus __str__ method returns the value."""
        # This tests line 343: return self.value
        assert str(ServiceStatus.HEALTHY) == "healthy"
        assert str(ServiceStatus.UNHEALTHY) == "unhealthy"
        assert str(ServiceStatus.RESTARTING) == "restarting"
        assert str(ServiceStatus.RESTART_FAILED) == "restart_failed"
        assert str(ServiceStatus.FAILED) == "failed"

    def test_service_status_string_comparison(self) -> None:
        """Test that ServiceStatus can be compared with strings."""
        assert ServiceStatus.HEALTHY == "healthy"
        assert ServiceStatus.FAILED == "failed"


# =============================================================================
# WebSocketEventData Schema Tests
# =============================================================================


class TestWebSocketEventData:
    """Tests for WebSocketEventData schema."""

    def test_valid_event_data(self) -> None:
        """Test creating valid event data."""
        event_data = WebSocketEventData(
            id=1,
            event_id=1,
            batch_id="batch_abc123",
            camera_id="cam-uuid",
            risk_score=75,
            risk_level=RiskLevel.HIGH,
            summary="Person detected at front door",
            started_at="2025-12-23T12:00:00",
        )
        assert event_data.id == 1
        assert event_data.risk_score == 75
        assert event_data.risk_level == RiskLevel.HIGH

    def test_risk_level_validator_with_enum(self) -> None:
        """Test risk_level validator when passed a RiskLevel enum directly."""
        # This tests line 258-259: if isinstance(v, RiskLevel): return v
        event_data = WebSocketEventData(
            id=1,
            event_id=1,
            batch_id="batch_abc123",
            camera_id="cam-uuid",
            risk_score=50,
            risk_level=RiskLevel.MEDIUM,
            summary="Test event",
        )
        assert event_data.risk_level == RiskLevel.MEDIUM

    def test_risk_level_validator_with_lowercase_string(self) -> None:
        """Test risk_level validator with lowercase string."""
        # This tests lines 260-262: if isinstance(v, str): return RiskLevel(v.lower())
        event_data = WebSocketEventData(
            id=1,
            event_id=1,
            batch_id="batch_abc123",
            camera_id="cam-uuid",
            risk_score=25,
            risk_level="low",  # type: ignore[arg-type]
            summary="Test event",
        )
        assert event_data.risk_level == RiskLevel.LOW

    def test_risk_level_validator_with_uppercase_string(self) -> None:
        """Test risk_level validator with uppercase string (case-insensitive)."""
        event_data = WebSocketEventData(
            id=1,
            event_id=1,
            batch_id="batch_abc123",
            camera_id="cam-uuid",
            risk_score=100,
            risk_level="CRITICAL",  # type: ignore[arg-type]
            summary="Test event",
        )
        assert event_data.risk_level == RiskLevel.CRITICAL

    def test_risk_level_validator_with_mixed_case_string(self) -> None:
        """Test risk_level validator with mixed case string."""
        event_data = WebSocketEventData(
            id=1,
            event_id=1,
            batch_id="batch_abc123",
            camera_id="cam-uuid",
            risk_score=60,
            risk_level="MeDiUm",  # type: ignore[arg-type]
            summary="Test event",
        )
        assert event_data.risk_level == RiskLevel.MEDIUM

    def test_risk_level_validator_invalid_string(self) -> None:
        """Test risk_level validator with invalid string value."""
        # This tests lines 263-267: except ValueError - invalid string
        with pytest.raises(ValidationError) as exc_info:
            WebSocketEventData(
                id=1,
                event_id=1,
                batch_id="batch_abc123",
                camera_id="cam-uuid",
                risk_score=50,
                risk_level="invalid_level",  # type: ignore[arg-type]
                summary="Test event",
            )
        errors = exc_info.value.errors()
        assert any("risk_level" in str(e["loc"]) for e in errors)
        # Verify error message contains valid values
        error_msg = str(exc_info.value)
        assert "low" in error_msg or "Invalid risk_level" in error_msg

    def test_risk_level_validator_invalid_type(self) -> None:
        """Test risk_level validator with invalid type (not string or enum)."""
        # This tests line 268: raise ValueError for non-string/non-enum type
        with pytest.raises(ValidationError) as exc_info:
            WebSocketEventData(
                id=1,
                event_id=1,
                batch_id="batch_abc123",
                camera_id="cam-uuid",
                risk_score=50,
                risk_level=123,  # type: ignore[arg-type]
                summary="Test event",
            )
        errors = exc_info.value.errors()
        assert any("risk_level" in str(e["loc"]) for e in errors)

    def test_risk_score_bounds(self) -> None:
        """Test risk_score validation bounds (0-100)."""
        # Valid minimum
        event_data = WebSocketEventData(
            id=1,
            event_id=1,
            batch_id="batch_abc123",
            camera_id="cam-uuid",
            risk_score=0,
            risk_level=RiskLevel.LOW,
            summary="Test event",
        )
        assert event_data.risk_score == 0

        # Valid maximum
        event_data = WebSocketEventData(
            id=1,
            event_id=1,
            batch_id="batch_abc123",
            camera_id="cam-uuid",
            risk_score=100,
            risk_level=RiskLevel.CRITICAL,
            summary="Test event",
        )
        assert event_data.risk_score == 100

    def test_risk_score_out_of_bounds(self) -> None:
        """Test risk_score validation fails for out of bounds values."""
        with pytest.raises(ValidationError):
            WebSocketEventData(
                id=1,
                event_id=1,
                batch_id="batch_abc123",
                camera_id="cam-uuid",
                risk_score=101,  # Over max
                risk_level=RiskLevel.HIGH,
                summary="Test event",
            )

        with pytest.raises(ValidationError):
            WebSocketEventData(
                id=1,
                event_id=1,
                batch_id="batch_abc123",
                camera_id="cam-uuid",
                risk_score=-1,  # Below min
                risk_level=RiskLevel.LOW,
                summary="Test event",
            )

    def test_event_data_serialization(self) -> None:
        """Test that event data serializes to JSON correctly."""
        event_data = WebSocketEventData(
            id=1,
            event_id=1,
            batch_id="batch_abc123",
            camera_id="cam-uuid",
            risk_score=75,
            risk_level=RiskLevel.HIGH,
            summary="Person detected at front door",
            started_at="2025-12-23T12:00:00",
        )
        json_str = event_data.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["id"] == 1
        assert parsed["risk_score"] == 75
        assert parsed["risk_level"] == "high"


# =============================================================================
# WebSocketEventMessage Schema Tests
# =============================================================================


class TestWebSocketEventMessage:
    """Tests for WebSocketEventMessage schema."""

    def test_valid_event_message(self) -> None:
        """Test creating valid event message envelope."""
        event_data = WebSocketEventData(
            id=1,
            event_id=1,
            batch_id="batch_abc123",
            camera_id="cam-uuid",
            risk_score=75,
            risk_level=RiskLevel.HIGH,
            summary="Person detected at front door",
        )
        message = WebSocketEventMessage(data=event_data)
        assert message.type == "event"
        assert message.data.id == 1

    def test_event_message_serialization(self) -> None:
        """Test that event message serializes correctly."""
        event_data = WebSocketEventData(
            id=1,
            event_id=1,
            batch_id="batch_abc123",
            camera_id="cam-uuid",
            risk_score=50,
            risk_level=RiskLevel.MEDIUM,
            summary="Test event",
        )
        message = WebSocketEventMessage(data=event_data)
        json_str = message.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["type"] == "event"
        assert parsed["data"]["id"] == 1
        assert parsed["data"]["risk_level"] == "medium"


# =============================================================================
# WebSocketServiceStatusData Schema Tests
# =============================================================================


class TestWebSocketServiceStatusData:
    """Tests for WebSocketServiceStatusData schema."""

    def test_valid_service_status_data(self) -> None:
        """Test creating valid service status data."""
        status_data = WebSocketServiceStatusData(
            service="redis",
            status=ServiceStatus.HEALTHY,
            message="Service responding normally",
        )
        assert status_data.service == "redis"
        assert status_data.status == ServiceStatus.HEALTHY

    def test_status_validator_with_enum(self) -> None:
        """Test status validator when passed a ServiceStatus enum directly."""
        # This tests lines 360-361: if isinstance(v, ServiceStatus): return v
        status_data = WebSocketServiceStatusData(
            service="rtdetr",
            status=ServiceStatus.RESTARTING,
        )
        assert status_data.status == ServiceStatus.RESTARTING

    def test_status_validator_with_lowercase_string(self) -> None:
        """Test status validator with lowercase string."""
        # This tests lines 362-364: if isinstance(v, str): return ServiceStatus(v.lower())
        status_data = WebSocketServiceStatusData(
            service="redis",
            status="healthy",  # type: ignore[arg-type]
        )
        assert status_data.status == ServiceStatus.HEALTHY

    def test_status_validator_with_uppercase_string(self) -> None:
        """Test status validator with uppercase string (case-insensitive)."""
        status_data = WebSocketServiceStatusData(
            service="nemotron",
            status="UNHEALTHY",  # type: ignore[arg-type]
        )
        assert status_data.status == ServiceStatus.UNHEALTHY

    def test_status_validator_with_mixed_case_string(self) -> None:
        """Test status validator with mixed case string."""
        status_data = WebSocketServiceStatusData(
            service="redis",
            status="ReStArTiNg",  # type: ignore[arg-type]
        )
        assert status_data.status == ServiceStatus.RESTARTING

    def test_status_validator_invalid_string(self) -> None:
        """Test status validator with invalid string value."""
        # This tests lines 365-367: except ValueError - invalid string
        with pytest.raises(ValidationError) as exc_info:
            WebSocketServiceStatusData(
                service="redis",
                status="invalid_status",  # type: ignore[arg-type]
            )
        errors = exc_info.value.errors()
        assert any("status" in str(e["loc"]) for e in errors)
        # Verify error message contains valid values
        error_msg = str(exc_info.value)
        assert "healthy" in error_msg or "Invalid status" in error_msg

    def test_status_validator_invalid_type(self) -> None:
        """Test status validator with invalid type (not string or enum)."""
        # This tests line 368: raise ValueError for non-string/non-enum type
        with pytest.raises(ValidationError) as exc_info:
            WebSocketServiceStatusData(
                service="redis",
                status=42,  # type: ignore[arg-type]
            )
        errors = exc_info.value.errors()
        assert any("status" in str(e["loc"]) for e in errors)

    def test_service_status_optional_message(self) -> None:
        """Test that message field is optional."""
        status_data = WebSocketServiceStatusData(
            service="redis",
            status=ServiceStatus.HEALTHY,
        )
        assert status_data.message is None

    def test_service_status_serialization(self) -> None:
        """Test that service status data serializes to JSON correctly."""
        status_data = WebSocketServiceStatusData(
            service="redis",
            status=ServiceStatus.HEALTHY,
            message="All good",
        )
        json_str = status_data.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["service"] == "redis"
        assert parsed["status"] == "healthy"
        assert parsed["message"] == "All good"


# =============================================================================
# WebSocketServiceStatusMessage Schema Tests
# =============================================================================


class TestWebSocketServiceStatusMessage:
    """Tests for WebSocketServiceStatusMessage schema."""

    def test_valid_service_status_message(self) -> None:
        """Test creating valid service status message envelope."""
        status_data = WebSocketServiceStatusData(
            service="redis",
            status=ServiceStatus.HEALTHY,
        )
        message = WebSocketServiceStatusMessage(
            data=status_data,
            timestamp="2025-12-23T12:00:00.000Z",
        )
        assert message.type == "service_status"
        assert message.data.service == "redis"

    def test_service_status_message_serialization(self) -> None:
        """Test that service status message serializes correctly."""
        status_data = WebSocketServiceStatusData(
            service="nemotron",
            status=ServiceStatus.UNHEALTHY,
            message="Model loading failed",
        )
        message = WebSocketServiceStatusMessage(
            data=status_data,
            timestamp="2025-12-23T12:00:00.000Z",
        )
        json_str = message.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["type"] == "service_status"
        assert parsed["data"]["service"] == "nemotron"
        assert parsed["data"]["status"] == "unhealthy"
        assert parsed["timestamp"] == "2025-12-23T12:00:00.000Z"


# =============================================================================
# Additional Edge Case Tests for Validators
# =============================================================================


class TestValidatorEdgeCases:
    """Edge case tests for validator methods."""

    def test_risk_level_all_valid_values(self) -> None:
        """Test all valid risk level string values."""
        for level in ["low", "medium", "high", "critical"]:
            event_data = WebSocketEventData(
                id=1,
                event_id=1,
                batch_id="batch_abc123",
                camera_id="cam-uuid",
                risk_score=50,
                risk_level=level,  # type: ignore[arg-type]
                summary="Test event",
            )
            assert event_data.risk_level.value == level

    def test_service_status_all_valid_values(self) -> None:
        """Test all valid service status string values."""
        for status in ["healthy", "unhealthy", "restarting", "restart_failed", "failed"]:
            status_data = WebSocketServiceStatusData(
                service="test",
                status=status,  # type: ignore[arg-type]
            )
            assert status_data.status.value == status

    def test_risk_level_validator_with_list_type(self) -> None:
        """Test risk_level validator with list type raises error."""
        with pytest.raises(ValidationError):
            WebSocketEventData(
                id=1,
                event_id=1,
                batch_id="batch_abc123",
                camera_id="cam-uuid",
                risk_score=50,
                risk_level=["high"],  # type: ignore[arg-type]
                summary="Test event",
            )

    def test_status_validator_with_dict_type(self) -> None:
        """Test status validator with dict type raises error."""
        with pytest.raises(ValidationError):
            WebSocketServiceStatusData(
                service="redis",
                status={"value": "healthy"},  # type: ignore[arg-type]
            )
