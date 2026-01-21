"""Unit tests for backend/api/routes/websocket.py.

This test file provides comprehensive coverage for WebSocket API routes,
focusing on:
- Message validation (JSON parsing, schema validation)
- Message handling (ping/pong, subscribe/unsubscribe)
- Event filtering patterns
- Idle timeout behavior
- Connection management
- Helper functions

These tests complement the integration tests in backend/tests/unit/routes/test_websocket_routes.py
by focusing on unit-level validation and helper function behavior.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocket
from fastapi.websockets import WebSocketState

from backend.api.routes.websocket import (
    handle_validated_message,
    send_heartbeat,
    validate_websocket_message,
)
from backend.api.schemas.websocket import (
    WebSocketErrorCode,
    WebSocketMessage,
    WebSocketMessageType,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket connection."""
    ws = MagicMock(spec=WebSocket)
    ws.send_text = AsyncMock()
    ws.send_json = AsyncMock()
    ws.client_state = WebSocketState.CONNECTED
    return ws


@pytest.fixture
def mock_subscription_manager():
    """Create a mock subscription manager."""
    manager = MagicMock()
    manager.subscribe = MagicMock(return_value=["alert.*", "camera.status_changed"])
    manager.unsubscribe = MagicMock(return_value=["alert.*"])
    return manager


# =============================================================================
# Tests for validate_websocket_message
# =============================================================================


class TestValidateWebSocketMessage:
    """Tests for the validate_websocket_message helper function."""

    @pytest.mark.asyncio
    async def test_valid_json_ping_message(self, mock_websocket):
        """Test validating a valid JSON ping message."""
        raw_data = '{"type": "ping"}'
        message = await validate_websocket_message(mock_websocket, raw_data)

        assert message is not None
        assert message.type == "ping"
        assert message.data is None
        mock_websocket.send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_valid_json_subscribe_message(self, mock_websocket):
        """Test validating a valid JSON subscribe message with data."""
        raw_data = '{"type": "subscribe", "data": {"events": ["alert.*"]}}'
        message = await validate_websocket_message(mock_websocket, raw_data)

        assert message is not None
        assert message.type == "subscribe"
        assert message.data is not None
        assert message.data["events"] == ["alert.*"]
        mock_websocket.send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_json_returns_none_and_sends_error(self, mock_websocket):
        """Test that invalid JSON returns None and sends error response."""
        raw_data = "not valid json {{"
        message = await validate_websocket_message(mock_websocket, raw_data)

        assert message is None
        mock_websocket.send_text.assert_awaited_once()

        # Verify error response content
        call_args = mock_websocket.send_text.call_args[0][0]
        error_response = json.loads(call_args)
        assert error_response["type"] == "error"
        assert error_response["error"] == WebSocketErrorCode.INVALID_JSON
        assert "valid JSON" in error_response["message"]

    @pytest.mark.asyncio
    async def test_empty_string_returns_none_and_sends_error(self, mock_websocket):
        """Test that empty string returns None and sends error response."""
        raw_data = ""
        message = await validate_websocket_message(mock_websocket, raw_data)

        assert message is None
        mock_websocket.send_text.assert_awaited_once()

        # Verify error response
        call_args = mock_websocket.send_text.call_args[0][0]
        error_response = json.loads(call_args)
        assert error_response["type"] == "error"
        assert error_response["error"] == WebSocketErrorCode.INVALID_JSON

    @pytest.mark.asyncio
    async def test_malformed_json_structure_returns_none_and_sends_error(self, mock_websocket):
        """Test that JSON with wrong structure returns None and sends error."""
        # Valid JSON but missing required 'type' field
        raw_data = '{"data": {"events": ["alert.*"]}}'
        message = await validate_websocket_message(mock_websocket, raw_data)

        assert message is None
        mock_websocket.send_text.assert_awaited_once()

        # Verify error response
        call_args = mock_websocket.send_text.call_args[0][0]
        error_response = json.loads(call_args)
        assert error_response["type"] == "error"
        assert error_response["error"] == WebSocketErrorCode.INVALID_MESSAGE_FORMAT
        assert "schema" in error_response["message"]
        assert "validation_errors" in error_response["details"]

    @pytest.mark.asyncio
    async def test_type_field_too_long_returns_none_and_sends_error(self, mock_websocket):
        """Test that type field exceeding max length returns None and sends error."""
        # Type field longer than 50 characters
        raw_data = '{"type": "' + "a" * 51 + '"}'
        message = await validate_websocket_message(mock_websocket, raw_data)

        assert message is None
        mock_websocket.send_text.assert_awaited_once()

        # Verify error response
        call_args = mock_websocket.send_text.call_args[0][0]
        error_response = json.loads(call_args)
        assert error_response["type"] == "error"
        assert error_response["error"] == WebSocketErrorCode.INVALID_MESSAGE_FORMAT

    @pytest.mark.asyncio
    async def test_extra_fields_allowed(self, mock_websocket):
        """Test that extra fields are allowed for forward compatibility."""
        raw_data = '{"type": "ping", "extra_field": "ignored", "another": 123}'
        message = await validate_websocket_message(mock_websocket, raw_data)

        assert message is not None
        assert message.type == "ping"
        mock_websocket.send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_data_preview_in_error_response(self, mock_websocket):
        """Test that invalid JSON error includes data preview."""
        raw_data = "x" * 150  # Longer than 100 characters
        message = await validate_websocket_message(mock_websocket, raw_data)

        assert message is None

        call_args = mock_websocket.send_text.call_args[0][0]
        error_response = json.loads(call_args)
        assert "raw_data_preview" in error_response["details"]
        # Should be truncated to 100 characters
        assert len(error_response["details"]["raw_data_preview"]) == 100


# =============================================================================
# Tests for handle_validated_message
# =============================================================================


class TestHandleValidatedMessage:
    """Tests for the handle_validated_message helper function."""

    @pytest.mark.asyncio
    async def test_ping_message_sends_pong(self, mock_websocket, mock_subscription_manager):
        """Test that ping message receives pong response."""
        message = WebSocketMessage(type="ping")

        with patch(
            "backend.api.routes.websocket.get_subscription_manager",
            return_value=mock_subscription_manager,
        ):
            await handle_validated_message(mock_websocket, message, "conn-123")

        # Verify pong response sent
        mock_websocket.send_text.assert_awaited_once()
        call_args = mock_websocket.send_text.call_args[0][0]
        response = json.loads(call_args)
        assert response["type"] == "pong"

    @pytest.mark.asyncio
    async def test_pong_message_no_response(self, mock_websocket, mock_subscription_manager):
        """Test that pong message is acknowledged silently."""
        message = WebSocketMessage(type="pong")

        with patch(
            "backend.api.routes.websocket.get_subscription_manager",
            return_value=mock_subscription_manager,
        ):
            await handle_validated_message(mock_websocket, message, "conn-123")

        # Pong should not send any response
        mock_websocket.send_text.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_subscribe_with_events_array(self, mock_websocket, mock_subscription_manager):
        """Test subscribe message with events array."""
        message = WebSocketMessage(type="subscribe", data={"events": ["alert.*", "camera.*"]})

        with patch(
            "backend.api.routes.websocket.get_subscription_manager",
            return_value=mock_subscription_manager,
        ):
            await handle_validated_message(mock_websocket, message, "conn-123")

        # Verify subscription manager was called
        mock_subscription_manager.subscribe.assert_called_once_with(
            "conn-123", ["alert.*", "camera.*"]
        )

        # Verify acknowledgment sent
        mock_websocket.send_text.assert_awaited_once()
        call_args = mock_websocket.send_text.call_args[0][0]
        response = json.loads(call_args)
        assert response["action"] == "subscribed"
        assert "events" in response

    @pytest.mark.asyncio
    async def test_subscribe_with_channels_backwards_compat(
        self, mock_websocket, mock_subscription_manager
    ):
        """Test subscribe message with 'channels' field for backwards compatibility."""
        message = WebSocketMessage(type="subscribe", data={"channels": ["alerts", "events"]})

        with patch(
            "backend.api.routes.websocket.get_subscription_manager",
            return_value=mock_subscription_manager,
        ):
            await handle_validated_message(mock_websocket, message, "conn-123")

        # Should use channels when events not present
        mock_subscription_manager.subscribe.assert_called_once_with(
            "conn-123", ["alerts", "events"]
        )

    @pytest.mark.asyncio
    async def test_subscribe_without_events_sends_error(
        self, mock_websocket, mock_subscription_manager
    ):
        """Test subscribe message without events array sends error."""
        message = WebSocketMessage(type="subscribe", data={})

        with patch(
            "backend.api.routes.websocket.get_subscription_manager",
            return_value=mock_subscription_manager,
        ):
            await handle_validated_message(mock_websocket, message, "conn-123")

        # Should send error response
        mock_websocket.send_text.assert_awaited_once()
        call_args = mock_websocket.send_text.call_args[0][0]
        response = json.loads(call_args)
        assert response["type"] == "error"
        assert response["error"] == WebSocketErrorCode.VALIDATION_ERROR
        assert "events" in response["message"]

    @pytest.mark.asyncio
    async def test_subscribe_with_wildcard_pattern(self, mock_websocket, mock_subscription_manager):
        """Test subscribe with wildcard pattern."""
        message = WebSocketMessage(type="subscribe", data={"events": ["*"]})

        with patch(
            "backend.api.routes.websocket.get_subscription_manager",
            return_value=mock_subscription_manager,
        ):
            await handle_validated_message(mock_websocket, message, "conn-123")

        # Verify wildcard subscription
        mock_subscription_manager.subscribe.assert_called_once_with("conn-123", ["*"])

    @pytest.mark.asyncio
    async def test_subscribe_with_exact_match(self, mock_websocket, mock_subscription_manager):
        """Test subscribe with exact event match."""
        message = WebSocketMessage(
            type="subscribe", data={"events": ["camera.status_changed", "alert.created"]}
        )

        with patch(
            "backend.api.routes.websocket.get_subscription_manager",
            return_value=mock_subscription_manager,
        ):
            await handle_validated_message(mock_websocket, message, "conn-123")

        mock_subscription_manager.subscribe.assert_called_once_with(
            "conn-123", ["camera.status_changed", "alert.created"]
        )

    @pytest.mark.asyncio
    async def test_unsubscribe_with_specific_events(
        self, mock_websocket, mock_subscription_manager
    ):
        """Test unsubscribe from specific events."""
        message = WebSocketMessage(type="unsubscribe", data={"events": ["alert.*"]})

        with patch(
            "backend.api.routes.websocket.get_subscription_manager",
            return_value=mock_subscription_manager,
        ):
            await handle_validated_message(mock_websocket, message, "conn-123")

        # Verify unsubscription
        mock_subscription_manager.unsubscribe.assert_called_once_with("conn-123", ["alert.*"])

        # Verify acknowledgment
        mock_websocket.send_text.assert_awaited_once()
        call_args = mock_websocket.send_text.call_args[0][0]
        response = json.loads(call_args)
        assert response["action"] == "unsubscribed"

    @pytest.mark.asyncio
    async def test_unsubscribe_from_all_events(self, mock_websocket, mock_subscription_manager):
        """Test unsubscribe from all events (no patterns specified)."""
        message = WebSocketMessage(type="unsubscribe", data={})

        with patch(
            "backend.api.routes.websocket.get_subscription_manager",
            return_value=mock_subscription_manager,
        ):
            await handle_validated_message(mock_websocket, message, "conn-123")

        # Should unsubscribe from all (no events argument)
        mock_subscription_manager.unsubscribe.assert_called_once_with("conn-123")

    @pytest.mark.asyncio
    async def test_unsubscribe_with_channels_backwards_compat(
        self, mock_websocket, mock_subscription_manager
    ):
        """Test unsubscribe with 'channels' field for backwards compatibility."""
        message = WebSocketMessage(type="unsubscribe", data={"channels": ["alerts"]})

        with patch(
            "backend.api.routes.websocket.get_subscription_manager",
            return_value=mock_subscription_manager,
        ):
            await handle_validated_message(mock_websocket, message, "conn-123")

        # Should use channels when events not present
        mock_subscription_manager.unsubscribe.assert_called_once_with("conn-123", ["alerts"])

    @pytest.mark.asyncio
    async def test_unknown_message_type_sends_error(
        self, mock_websocket, mock_subscription_manager
    ):
        """Test that unknown message type sends error response."""
        message = WebSocketMessage(type="unknown_action")

        with patch(
            "backend.api.routes.websocket.get_subscription_manager",
            return_value=mock_subscription_manager,
        ):
            await handle_validated_message(mock_websocket, message, "conn-123")

        # Should send error for unknown type
        mock_websocket.send_text.assert_awaited_once()
        call_args = mock_websocket.send_text.call_args[0][0]
        response = json.loads(call_args)
        assert response["type"] == "error"
        assert response["error"] == WebSocketErrorCode.UNKNOWN_MESSAGE_TYPE
        assert "unknown_action" in response["message"]
        assert "supported_types" in response["details"]
        # Verify all supported types are listed
        supported = response["details"]["supported_types"]
        assert "ping" in supported
        assert "pong" in supported
        assert "subscribe" in supported
        assert "unsubscribe" in supported
        assert "resync" in supported

    @pytest.mark.asyncio
    async def test_resync_message_sends_ack(self, mock_websocket, mock_subscription_manager):
        """Test that resync message receives resync_ack response."""
        message = WebSocketMessage(type="resync", data={"channel": "events", "last_sequence": 42})

        with patch(
            "backend.api.routes.websocket.get_subscription_manager",
            return_value=mock_subscription_manager,
        ):
            await handle_validated_message(mock_websocket, message, "conn-123")

        # Verify resync_ack response sent
        mock_websocket.send_text.assert_awaited_once()
        call_args = mock_websocket.send_text.call_args[0][0]
        response = json.loads(call_args)
        assert response["type"] == "resync_ack"
        assert response["channel"] == "events"
        assert response["last_sequence"] == 42

    @pytest.mark.asyncio
    async def test_resync_message_with_missing_data_uses_defaults(
        self, mock_websocket, mock_subscription_manager
    ):
        """Test that resync message with missing data uses default values."""
        message = WebSocketMessage(type="resync", data=None)

        with patch(
            "backend.api.routes.websocket.get_subscription_manager",
            return_value=mock_subscription_manager,
        ):
            await handle_validated_message(mock_websocket, message, "conn-123")

        # Verify resync_ack with defaults
        mock_websocket.send_text.assert_awaited_once()
        call_args = mock_websocket.send_text.call_args[0][0]
        response = json.loads(call_args)
        assert response["type"] == "resync_ack"
        assert response["channel"] == "unknown"
        assert response["last_sequence"] == 0

    @pytest.mark.asyncio
    async def test_case_insensitive_message_types(self, mock_websocket, mock_subscription_manager):
        """Test that message types are case-insensitive."""
        # Test with uppercase PING
        message_upper = WebSocketMessage(type="PING")

        with patch(
            "backend.api.routes.websocket.get_subscription_manager",
            return_value=mock_subscription_manager,
        ):
            await handle_validated_message(mock_websocket, message_upper, "conn-123")

        # Should still send pong
        assert mock_websocket.send_text.await_count == 1


# =============================================================================
# Tests for send_heartbeat
# =============================================================================


class TestSendHeartbeat:
    """Tests for the send_heartbeat helper function."""

    @pytest.mark.asyncio
    async def test_sends_periodic_pings(self, mock_websocket):
        """Test that heartbeat sends periodic ping messages."""
        stop_event = asyncio.Event()
        interval = 0.1  # 100ms for fast test

        # Start heartbeat task
        task = asyncio.create_task(send_heartbeat(mock_websocket, interval, stop_event))

        # Wait for a few pings
        await asyncio.sleep(0.35)

        # Stop the heartbeat
        stop_event.set()
        await task

        # Should have sent approximately 3 pings (0.35s / 0.1s interval)
        assert mock_websocket.send_text.await_count >= 2
        assert mock_websocket.send_text.await_count <= 4

        # Verify ping message format (includes lastSeq for gap detection, NEM-3142)
        call_args = mock_websocket.send_text.call_args[0][0]
        assert call_args == '{"type": "ping", "lastSeq": 0}'

    @pytest.mark.asyncio
    async def test_stops_when_event_is_set(self, mock_websocket):
        """Test that heartbeat stops when stop event is set."""
        stop_event = asyncio.Event()
        interval = 0.1

        # Start heartbeat
        task = asyncio.create_task(send_heartbeat(mock_websocket, interval, stop_event))

        # Wait a bit
        await asyncio.sleep(0.15)

        # Signal stop
        stop_event.set()
        await task

        # Record number of pings sent
        pings_sent = mock_websocket.send_text.await_count

        # Wait more and verify no additional pings
        await asyncio.sleep(0.2)
        assert mock_websocket.send_text.await_count == pings_sent

    @pytest.mark.asyncio
    async def test_stops_when_websocket_disconnected(self, mock_websocket):
        """Test that heartbeat stops when WebSocket is disconnected."""
        stop_event = asyncio.Event()
        interval = 0.1

        # Change state to disconnected after first ping
        async def send_then_disconnect(msg):
            mock_websocket.client_state = WebSocketState.DISCONNECTED

        mock_websocket.send_text.side_effect = send_then_disconnect

        # Start heartbeat
        task = asyncio.create_task(send_heartbeat(mock_websocket, interval, stop_event))

        # Wait for it to detect disconnection
        await asyncio.sleep(0.3)

        # Should have stopped on its own
        assert task.done()

        # Cleanup
        stop_event.set()
        try:
            await task
        except Exception:
            pass

    @pytest.mark.asyncio
    async def test_handles_send_error_gracefully(self, mock_websocket):
        """Test that heartbeat handles send errors gracefully."""
        stop_event = asyncio.Event()
        interval = 0.1

        # Raise error on send
        mock_websocket.send_text.side_effect = RuntimeError("Connection closed")

        # Start heartbeat
        task = asyncio.create_task(send_heartbeat(mock_websocket, interval, stop_event))

        # Wait for error to occur
        await asyncio.sleep(0.2)

        # Should have stopped without raising
        assert task.done()

        # Cleanup
        stop_event.set()
        try:
            await task
        except Exception:
            pass

    @pytest.mark.asyncio
    async def test_checks_websocket_state_before_sending(self, mock_websocket):
        """Test that heartbeat checks WebSocket state before each ping."""
        stop_event = asyncio.Event()
        interval = 0.1

        # Start with connected, then change to disconnected
        states = [WebSocketState.CONNECTED, WebSocketState.CONNECTED, WebSocketState.DISCONNECTED]
        state_index = 0

        def get_state():
            nonlocal state_index
            result = states[min(state_index, len(states) - 1)]
            state_index += 1
            return result

        type(mock_websocket).client_state = property(lambda _self: get_state())

        # Start heartbeat
        task = asyncio.create_task(send_heartbeat(mock_websocket, interval, stop_event))

        # Wait for disconnection to be detected
        await asyncio.sleep(0.35)

        # Should have stopped after detecting disconnected state
        # Maximum 2 pings before disconnection
        assert mock_websocket.send_text.await_count <= 2

        # Cleanup
        stop_event.set()
        try:
            await task
        except Exception:
            pass

    @pytest.mark.asyncio
    async def test_respects_configured_interval(self, mock_websocket):
        """Test that heartbeat respects the configured interval."""
        stop_event = asyncio.Event()
        interval = 0.2  # 200ms

        # Start heartbeat
        task = asyncio.create_task(send_heartbeat(mock_websocket, interval, stop_event))

        # Wait for less than 2 intervals
        await asyncio.sleep(0.35)

        # Stop
        stop_event.set()
        await task

        # Should have sent 1-2 pings (0.35s / 0.2s interval = 1.75)
        assert mock_websocket.send_text.await_count >= 1
        assert mock_websocket.send_text.await_count <= 2


# =============================================================================
# Tests for WebSocket message type validation
# =============================================================================


class TestWebSocketMessageTypes:
    """Tests for WebSocket message type enum and validation."""

    def test_all_message_types_defined(self):
        """Test that all expected message types are defined."""
        expected_types = ["ping", "pong", "subscribe", "unsubscribe", "resync"]

        for msg_type in expected_types:
            # Verify enum has the type
            assert hasattr(WebSocketMessageType, msg_type.upper())

    def test_message_type_values_are_lowercase(self):
        """Test that message type enum values are lowercase."""
        for msg_type in WebSocketMessageType:
            assert msg_type.value == msg_type.value.lower()

    def test_can_create_message_with_all_types(self):
        """Test that WebSocketMessage can be created with all message types."""
        for msg_type in WebSocketMessageType:
            message = WebSocketMessage(type=msg_type.value)
            assert message.type == msg_type.value


# =============================================================================
# Tests for error response format
# =============================================================================


class TestWebSocketErrorResponses:
    """Tests for WebSocket error response formatting."""

    @pytest.mark.asyncio
    async def test_invalid_json_error_includes_preview(self, mock_websocket):
        """Test that invalid JSON error includes data preview."""
        raw_data = "not json" * 20  # Create long invalid string
        await validate_websocket_message(mock_websocket, raw_data)

        call_args = mock_websocket.send_text.call_args[0][0]
        response = json.loads(call_args)

        assert response["type"] == "error"
        assert response["error"] == WebSocketErrorCode.INVALID_JSON
        assert "details" in response
        assert "raw_data_preview" in response["details"]
        # Preview should be truncated
        assert len(response["details"]["raw_data_preview"]) <= 100

    @pytest.mark.asyncio
    async def test_invalid_schema_error_includes_validation_errors(self, mock_websocket):
        """Test that schema validation errors include detailed validation info."""
        # Valid JSON but invalid schema (type field too long)
        raw_data = '{"type": "' + "x" * 100 + '"}'
        await validate_websocket_message(mock_websocket, raw_data)

        call_args = mock_websocket.send_text.call_args[0][0]
        response = json.loads(call_args)

        assert response["type"] == "error"
        assert response["error"] == WebSocketErrorCode.INVALID_MESSAGE_FORMAT
        assert "details" in response
        assert "validation_errors" in response["details"]
        # Should have at least one validation error
        assert len(response["details"]["validation_errors"]) > 0


# =============================================================================
# Tests for subscription/unsubscription edge cases
# =============================================================================


class TestSubscriptionEdgeCases:
    """Tests for edge cases in subscription management."""

    @pytest.mark.asyncio
    async def test_subscribe_with_empty_events_array_sends_error(
        self, mock_websocket, mock_subscription_manager
    ):
        """Test that subscribe with empty events array sends error."""
        message = WebSocketMessage(type="subscribe", data={"events": []})

        with patch(
            "backend.api.routes.websocket.get_subscription_manager",
            return_value=mock_subscription_manager,
        ):
            await handle_validated_message(mock_websocket, message, "conn-123")

        # Empty events should be treated as missing events
        mock_websocket.send_text.assert_awaited_once()
        call_args = mock_websocket.send_text.call_args[0][0]
        response = json.loads(call_args)
        assert response["type"] == "error"

    @pytest.mark.asyncio
    async def test_subscribe_null_data_sends_error(self, mock_websocket, mock_subscription_manager):
        """Test that subscribe with null data sends error."""
        message = WebSocketMessage(type="subscribe", data=None)

        with patch(
            "backend.api.routes.websocket.get_subscription_manager",
            return_value=mock_subscription_manager,
        ):
            await handle_validated_message(mock_websocket, message, "conn-123")

        # Null data should result in error
        mock_websocket.send_text.assert_awaited_once()
        call_args = mock_websocket.send_text.call_args[0][0]
        response = json.loads(call_args)
        assert response["type"] == "error"

    @pytest.mark.asyncio
    async def test_unsubscribe_with_empty_events_unsubscribes_all(
        self, mock_websocket, mock_subscription_manager
    ):
        """Test that unsubscribe with empty events array unsubscribes from all."""
        message = WebSocketMessage(type="unsubscribe", data={"events": []})

        with patch(
            "backend.api.routes.websocket.get_subscription_manager",
            return_value=mock_subscription_manager,
        ):
            await handle_validated_message(mock_websocket, message, "conn-123")

        # Empty events array should unsubscribe from all
        mock_subscription_manager.unsubscribe.assert_called_once_with("conn-123")

    @pytest.mark.asyncio
    async def test_subscribe_response_includes_subscribed_patterns(
        self, mock_websocket, mock_subscription_manager
    ):
        """Test that subscribe response includes the patterns that were subscribed."""
        mock_subscription_manager.subscribe.return_value = [
            "alert.*",
            "camera.status_changed",
            "event.*",
        ]

        message = WebSocketMessage(
            type="subscribe", data={"events": ["alert.*", "camera.status_changed", "event.*"]}
        )

        with patch(
            "backend.api.routes.websocket.get_subscription_manager",
            return_value=mock_subscription_manager,
        ):
            await handle_validated_message(mock_websocket, message, "conn-123")

        call_args = mock_websocket.send_text.call_args[0][0]
        response = json.loads(call_args)
        assert response["action"] == "subscribed"
        assert response["events"] == ["alert.*", "camera.status_changed", "event.*"]

    @pytest.mark.asyncio
    async def test_unsubscribe_response_includes_removed_patterns(
        self, mock_websocket, mock_subscription_manager
    ):
        """Test that unsubscribe response includes the patterns that were removed."""
        mock_subscription_manager.unsubscribe.return_value = ["alert.*", "camera.*"]

        message = WebSocketMessage(type="unsubscribe", data={"events": ["alert.*", "camera.*"]})

        with patch(
            "backend.api.routes.websocket.get_subscription_manager",
            return_value=mock_subscription_manager,
        ):
            await handle_validated_message(mock_websocket, message, "conn-123")

        call_args = mock_websocket.send_text.call_args[0][0]
        response = json.loads(call_args)
        assert response["action"] == "unsubscribed"
        assert response["events"] == ["alert.*", "camera.*"]
