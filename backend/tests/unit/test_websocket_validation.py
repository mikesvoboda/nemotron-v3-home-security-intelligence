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
    WebSocketErrorCode,
    WebSocketErrorResponse,
    WebSocketMessage,
    WebSocketMessageType,
    WebSocketPingMessage,
    WebSocketPongResponse,
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
