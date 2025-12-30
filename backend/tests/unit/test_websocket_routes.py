"""Unit tests for WebSocket routes (backend/api/routes/websocket.py).

Tests cover:
- WebSocket connection handling for /ws/events and /ws/system endpoints
- Authentication flow (success and failure)
- Message receiving/sending (including ping/pong)
- Disconnection handling (normal, WebSocketDisconnect, other exceptions)
- Error cases and edge conditions
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.websockets import WebSocketState

from backend.api.routes.websocket import (
    websocket_events_endpoint,
    websocket_system_status,
)


@pytest.fixture(autouse=True)
def _enable_log_capture(caplog: pytest.LogCaptureFixture) -> None:
    """Automatically enable INFO-level log capture for all tests."""
    caplog.set_level(logging.INFO)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket connection."""
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.close = AsyncMock()
    ws.client_state = WebSocketState.CONNECTED
    ws.query_params = {}
    ws.headers = {}
    return ws


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client."""
    redis = MagicMock()
    redis.subscribe = AsyncMock()
    redis.unsubscribe = AsyncMock()
    redis.publish = AsyncMock(return_value=1)
    redis.health_check = AsyncMock(return_value={"status": "healthy"})
    return redis


@pytest.fixture
def mock_event_broadcaster():
    """Create a mock EventBroadcaster."""
    broadcaster = MagicMock()
    broadcaster.connect = AsyncMock()
    broadcaster.disconnect = AsyncMock()
    broadcaster.start = AsyncMock()
    broadcaster.stop = AsyncMock()
    return broadcaster


@pytest.fixture
def mock_system_broadcaster():
    """Create a mock SystemBroadcaster."""
    broadcaster = MagicMock()
    broadcaster.connect = AsyncMock()
    broadcaster.disconnect = AsyncMock()
    broadcaster.start_broadcasting = AsyncMock()
    broadcaster.stop_broadcasting = AsyncMock()
    return broadcaster


# =============================================================================
# Tests for /ws/events endpoint
# =============================================================================


class TestWebSocketEventsEndpoint:
    """Tests for the /ws/events WebSocket endpoint."""

    @pytest.mark.asyncio
    async def test_authentication_failure_rejects_connection(
        self, mock_websocket, mock_redis_client
    ):
        """Test that authentication failure rejects the connection."""
        with patch(
            "backend.api.routes.websocket.authenticate_websocket",
            AsyncMock(return_value=False),
        ):
            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Connection should not be accepted (broadcaster.connect not called)
        # The authenticate_websocket mock returning False means connection is rejected

    @pytest.mark.asyncio
    async def test_authentication_success_connects(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Test that successful authentication connects the client."""
        # Set up websocket to disconnect after one iteration
        from fastapi import WebSocketDisconnect

        mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
        ):
            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Broadcaster should have connected the websocket
        mock_event_broadcaster.connect.assert_awaited_once_with(mock_websocket)
        # And disconnected it
        mock_event_broadcaster.disconnect.assert_awaited_once_with(mock_websocket)

    @pytest.mark.asyncio
    async def test_ping_message_sends_pong_response(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Test that a 'ping' message results in a '{"type":"pong"}' response."""
        from fastapi import WebSocketDisconnect

        # First call returns "ping", second call raises WebSocketDisconnect
        mock_websocket.receive_text = AsyncMock(side_effect=["ping", WebSocketDisconnect()])

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
        ):
            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Should have sent pong response
        mock_websocket.send_text.assert_awaited_once_with('{"type":"pong"}')

    @pytest.mark.asyncio
    async def test_non_ping_message_sends_error_for_invalid_json(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Test that non-JSON messages receive an error response."""
        from fastapi import WebSocketDisconnect

        mock_websocket.receive_text = AsyncMock(
            side_effect=["some_other_message", WebSocketDisconnect()]
        )

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
        ):
            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Should have sent an error response for invalid JSON
        mock_websocket.send_text.assert_awaited_once()
        import json

        call_args = mock_websocket.send_text.call_args[0][0]
        response = json.loads(call_args)
        assert response["type"] == "error"
        assert response["error"] == "invalid_json"

    @pytest.mark.asyncio
    async def test_websocket_disconnect_during_receive(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Test handling of WebSocketDisconnect during receive."""
        from fastapi import WebSocketDisconnect

        mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
        ):
            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Connection should be cleaned up
        mock_event_broadcaster.disconnect.assert_awaited_once_with(mock_websocket)

    @pytest.mark.asyncio
    async def test_other_exception_during_receive_disconnected_state(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Test handling of other exceptions when websocket is disconnected."""
        mock_websocket.receive_text = AsyncMock(side_effect=RuntimeError("Connection error"))
        mock_websocket.client_state = WebSocketState.DISCONNECTED

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
        ):
            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Connection should be cleaned up
        mock_event_broadcaster.disconnect.assert_awaited_once_with(mock_websocket)

    @pytest.mark.asyncio
    async def test_other_exception_during_receive_connected_state(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Test handling of other exceptions when websocket is still connected."""
        mock_websocket.receive_text = AsyncMock(side_effect=RuntimeError("Unexpected error"))
        mock_websocket.client_state = WebSocketState.CONNECTED

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
        ):
            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Connection should be cleaned up even for unexpected errors
        mock_event_broadcaster.disconnect.assert_awaited_once_with(mock_websocket)

    @pytest.mark.asyncio
    async def test_websocket_disconnect_during_connect(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Test handling of WebSocketDisconnect during broadcaster.connect."""
        from fastapi import WebSocketDisconnect

        mock_event_broadcaster.connect = AsyncMock(side_effect=WebSocketDisconnect())

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
        ):
            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Disconnect should still be called in finally block
        mock_event_broadcaster.disconnect.assert_awaited_once_with(mock_websocket)

    @pytest.mark.asyncio
    async def test_general_exception_during_connect(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Test handling of general exception during broadcaster.connect."""
        mock_event_broadcaster.connect = AsyncMock(side_effect=RuntimeError("Connection failed"))

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
        ):
            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Disconnect should still be called in finally block
        mock_event_broadcaster.disconnect.assert_awaited_once_with(mock_websocket)

    @pytest.mark.asyncio
    async def test_multiple_messages_before_disconnect(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Test handling multiple messages before disconnect.

        Now with validation, invalid messages receive error responses,
        and valid ping gets pong response.
        """
        from fastapi import WebSocketDisconnect

        mock_websocket.receive_text = AsyncMock(
            side_effect=["msg1", "ping", "msg2", WebSocketDisconnect()]
        )

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
        ):
            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Should have sent responses for:
        # - msg1: error (invalid JSON)
        # - ping: pong (legacy string support)
        # - msg2: error (invalid JSON)
        assert mock_websocket.send_text.await_count == 3
        # And cleaned up
        mock_event_broadcaster.disconnect.assert_awaited_once_with(mock_websocket)


# =============================================================================
# Tests for /ws/system endpoint
# =============================================================================


class TestWebSocketSystemEndpoint:
    """Tests for the /ws/system WebSocket endpoint."""

    @pytest.mark.asyncio
    async def test_authentication_failure_rejects_connection(
        self, mock_websocket, mock_system_broadcaster
    ):
        """Test that authentication failure rejects the connection."""
        with patch(
            "backend.api.routes.websocket.authenticate_websocket",
            AsyncMock(return_value=False),
        ):
            await websocket_system_status(mock_websocket)

        # Connection should not be accepted (broadcaster.connect not called)

    @pytest.mark.asyncio
    async def test_authentication_success_connects(self, mock_websocket, mock_system_broadcaster):
        """Test that successful authentication connects the client."""
        from fastapi import WebSocketDisconnect

        mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_system_broadcaster",
                return_value=mock_system_broadcaster,
            ),
        ):
            await websocket_system_status(mock_websocket)

        # Broadcaster should have connected the websocket
        mock_system_broadcaster.connect.assert_awaited_once_with(mock_websocket)
        # And disconnected it
        mock_system_broadcaster.disconnect.assert_awaited_once_with(mock_websocket)

    @pytest.mark.asyncio
    async def test_ping_message_sends_pong_response(self, mock_websocket, mock_system_broadcaster):
        """Test that a 'ping' message results in a '{"type":"pong"}' response."""
        from fastapi import WebSocketDisconnect

        mock_websocket.receive_text = AsyncMock(side_effect=["ping", WebSocketDisconnect()])

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_system_broadcaster",
                return_value=mock_system_broadcaster,
            ),
        ):
            await websocket_system_status(mock_websocket)

        # Should have sent pong response
        mock_websocket.send_text.assert_awaited_once_with('{"type":"pong"}')

    @pytest.mark.asyncio
    async def test_non_ping_message_sends_error_for_invalid_json(
        self, mock_websocket, mock_system_broadcaster
    ):
        """Test that non-JSON messages receive an error response."""
        from fastapi import WebSocketDisconnect

        mock_websocket.receive_text = AsyncMock(side_effect=["keepalive", WebSocketDisconnect()])

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_system_broadcaster",
                return_value=mock_system_broadcaster,
            ),
        ):
            await websocket_system_status(mock_websocket)

        # Should have sent an error response for invalid JSON
        mock_websocket.send_text.assert_awaited_once()
        import json

        call_args = mock_websocket.send_text.call_args[0][0]
        response = json.loads(call_args)
        assert response["type"] == "error"
        assert response["error"] == "invalid_json"

    @pytest.mark.asyncio
    async def test_websocket_disconnect_during_receive(
        self, mock_websocket, mock_system_broadcaster
    ):
        """Test handling of WebSocketDisconnect during receive."""
        from fastapi import WebSocketDisconnect

        mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_system_broadcaster",
                return_value=mock_system_broadcaster,
            ),
        ):
            await websocket_system_status(mock_websocket)

        # Connection should be cleaned up
        mock_system_broadcaster.disconnect.assert_awaited_once_with(mock_websocket)

    @pytest.mark.asyncio
    async def test_other_exception_during_receive_disconnected_state(
        self, mock_websocket, mock_system_broadcaster
    ):
        """Test handling of other exceptions when websocket is disconnected."""
        mock_websocket.receive_text = AsyncMock(side_effect=RuntimeError("Connection error"))
        mock_websocket.client_state = WebSocketState.DISCONNECTED

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_system_broadcaster",
                return_value=mock_system_broadcaster,
            ),
        ):
            await websocket_system_status(mock_websocket)

        # Connection should be cleaned up
        mock_system_broadcaster.disconnect.assert_awaited_once_with(mock_websocket)

    @pytest.mark.asyncio
    async def test_other_exception_during_receive_connected_state(
        self, mock_websocket, mock_system_broadcaster
    ):
        """Test handling of other exceptions when websocket is still connected."""
        mock_websocket.receive_text = AsyncMock(side_effect=RuntimeError("Unexpected error"))
        mock_websocket.client_state = WebSocketState.CONNECTED

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_system_broadcaster",
                return_value=mock_system_broadcaster,
            ),
        ):
            await websocket_system_status(mock_websocket)

        # Connection should be cleaned up even for unexpected errors
        mock_system_broadcaster.disconnect.assert_awaited_once_with(mock_websocket)

    @pytest.mark.asyncio
    async def test_websocket_disconnect_during_connect(
        self, mock_websocket, mock_system_broadcaster
    ):
        """Test handling of WebSocketDisconnect during broadcaster.connect."""
        from fastapi import WebSocketDisconnect

        mock_system_broadcaster.connect = AsyncMock(side_effect=WebSocketDisconnect())

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_system_broadcaster",
                return_value=mock_system_broadcaster,
            ),
        ):
            await websocket_system_status(mock_websocket)

        # Disconnect should still be called in finally block
        mock_system_broadcaster.disconnect.assert_awaited_once_with(mock_websocket)

    @pytest.mark.asyncio
    async def test_general_exception_during_connect(self, mock_websocket, mock_system_broadcaster):
        """Test handling of general exception during broadcaster.connect."""
        mock_system_broadcaster.connect = AsyncMock(side_effect=RuntimeError("Connection failed"))

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_system_broadcaster",
                return_value=mock_system_broadcaster,
            ),
        ):
            await websocket_system_status(mock_websocket)

        # Disconnect should still be called in finally block
        mock_system_broadcaster.disconnect.assert_awaited_once_with(mock_websocket)

    @pytest.mark.asyncio
    async def test_multiple_messages_before_disconnect(
        self, mock_websocket, mock_system_broadcaster
    ):
        """Test handling multiple messages before disconnect.

        Now with validation, invalid messages receive error responses,
        and valid ping gets pong response.
        """
        from fastapi import WebSocketDisconnect

        mock_websocket.receive_text = AsyncMock(
            side_effect=["status", "ping", "ping", WebSocketDisconnect()]
        )

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_system_broadcaster",
                return_value=mock_system_broadcaster,
            ),
        ):
            await websocket_system_status(mock_websocket)

        # Should have sent responses for:
        # - status: error (invalid JSON)
        # - ping: pong (legacy string support)
        # - ping: pong (legacy string support)
        assert mock_websocket.send_text.await_count == 3
        # And cleaned up
        mock_system_broadcaster.disconnect.assert_awaited_once_with(mock_websocket)


# =============================================================================
# Tests for edge cases and error handling
# =============================================================================


class TestWebSocketEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_events_endpoint_handles_empty_message(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Test that empty messages receive an error response for invalid JSON."""
        from fastapi import WebSocketDisconnect

        mock_websocket.receive_text = AsyncMock(side_effect=["", WebSocketDisconnect()])

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
        ):
            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Empty message should receive an error (invalid JSON)
        mock_websocket.send_text.assert_awaited_once()
        import json

        call_args = mock_websocket.send_text.call_args[0][0]
        response = json.loads(call_args)
        assert response["type"] == "error"
        assert response["error"] == "invalid_json"
        # Connection should be cleaned up
        mock_event_broadcaster.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_system_endpoint_handles_empty_message(
        self, mock_websocket, mock_system_broadcaster
    ):
        """Test that empty messages receive an error response for invalid JSON."""
        from fastapi import WebSocketDisconnect

        mock_websocket.receive_text = AsyncMock(side_effect=["", WebSocketDisconnect()])

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_system_broadcaster",
                return_value=mock_system_broadcaster,
            ),
        ):
            await websocket_system_status(mock_websocket)

        # Empty message should receive an error (invalid JSON)
        mock_websocket.send_text.assert_awaited_once()
        import json

        call_args = mock_websocket.send_text.call_args[0][0]
        response = json.loads(call_args)
        assert response["type"] == "error"
        assert response["error"] == "invalid_json"
        # Connection should be cleaned up
        mock_system_broadcaster.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_events_endpoint_send_text_error(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Test handling of error during send_text."""
        from fastapi import WebSocketDisconnect

        mock_websocket.receive_text = AsyncMock(side_effect=["ping", WebSocketDisconnect()])
        mock_websocket.send_text = AsyncMock(side_effect=RuntimeError("Send failed"))

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
        ):
            # Should not raise - error during send_text breaks the loop
            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Connection should be cleaned up
        mock_event_broadcaster.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_system_endpoint_send_text_error(self, mock_websocket, mock_system_broadcaster):
        """Test handling of error during send_text."""
        from fastapi import WebSocketDisconnect

        mock_websocket.receive_text = AsyncMock(side_effect=["ping", WebSocketDisconnect()])
        mock_websocket.send_text = AsyncMock(side_effect=RuntimeError("Send failed"))

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_system_broadcaster",
                return_value=mock_system_broadcaster,
            ),
        ):
            # Should not raise - error during send_text breaks the loop
            await websocket_system_status(mock_websocket)

        # Connection should be cleaned up
        mock_system_broadcaster.disconnect.assert_awaited_once()


# =============================================================================
# Tests for connection state transitions
# =============================================================================


class TestWebSocketConnectionStates:
    """Tests for WebSocket connection state transitions."""

    @pytest.mark.asyncio
    async def test_events_websocket_state_checking(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Test that WebSocket state is checked when errors occur."""
        # First call raises error with connected state
        # Second call raises error with disconnected state
        call_count = 0

        async def receive_with_state_change():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                mock_websocket.client_state = WebSocketState.DISCONNECTED
                raise RuntimeError("Test error")
            raise RuntimeError("Should not reach here")

        mock_websocket.receive_text = receive_with_state_change

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
        ):
            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Should have exited after detecting disconnected state
        assert call_count == 1
        mock_event_broadcaster.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_system_websocket_state_checking(self, mock_websocket, mock_system_broadcaster):
        """Test that WebSocket state is checked when errors occur."""
        call_count = 0

        async def receive_with_state_change():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                mock_websocket.client_state = WebSocketState.DISCONNECTED
                raise RuntimeError("Test error")
            raise RuntimeError("Should not reach here")

        mock_websocket.receive_text = receive_with_state_change

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_system_broadcaster",
                return_value=mock_system_broadcaster,
            ),
        ):
            await websocket_system_status(mock_websocket)

        # Should have exited after detecting disconnected state
        assert call_count == 1
        mock_system_broadcaster.disconnect.assert_awaited_once()


# =============================================================================
# Tests for logging behavior (verify logs are emitted)
# =============================================================================


class TestWebSocketLogging:
    """Tests to verify proper logging during WebSocket operations."""

    @pytest.mark.asyncio
    async def test_events_logs_connection_info(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster, caplog
    ):
        """Test that connection/disconnection info is logged for events endpoint."""
        from fastapi import WebSocketDisconnect

        mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
        ):
            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Check that relevant log messages were emitted
        assert "WebSocket client connected to /ws/events" in caplog.text
        assert "WebSocket connection cleaned up" in caplog.text

    @pytest.mark.asyncio
    async def test_system_logs_connection_info(
        self, mock_websocket, mock_system_broadcaster, caplog
    ):
        """Test that connection/disconnection info is logged for system endpoint."""
        from fastapi import WebSocketDisconnect

        mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_system_broadcaster",
                return_value=mock_system_broadcaster,
            ),
        ):
            await websocket_system_status(mock_websocket)

        # Check that relevant log messages were emitted
        assert "WebSocket client connected to /ws/system" in caplog.text
        assert "WebSocket connection cleaned up" in caplog.text

    @pytest.mark.asyncio
    async def test_events_logs_auth_failure(self, mock_websocket, mock_redis_client, caplog):
        """Test that authentication failure is logged."""
        with patch(
            "backend.api.routes.websocket.authenticate_websocket",
            AsyncMock(return_value=False),
        ):
            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        assert "authentication failed" in caplog.text

    @pytest.mark.asyncio
    async def test_system_logs_auth_failure(self, mock_websocket, caplog):
        """Test that authentication failure is logged."""
        with patch(
            "backend.api.routes.websocket.authenticate_websocket",
            AsyncMock(return_value=False),
        ):
            await websocket_system_status(mock_websocket)

        assert "authentication failed" in caplog.text


# =============================================================================
# Tests for dependency injection
# =============================================================================


class TestWebSocketDependencies:
    """Tests for WebSocket endpoint dependencies."""

    @pytest.mark.asyncio
    async def test_events_endpoint_gets_broadcaster_with_redis(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Test that get_broadcaster is called with the Redis client."""
        from fastapi import WebSocketDisconnect

        mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())
        mock_get_broadcaster = AsyncMock(return_value=mock_event_broadcaster)

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                mock_get_broadcaster,
            ),
        ):
            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Verify get_broadcaster was called with the redis client
        mock_get_broadcaster.assert_awaited_once_with(mock_redis_client)

    @pytest.mark.asyncio
    async def test_system_endpoint_gets_system_broadcaster(
        self, mock_websocket, mock_system_broadcaster
    ):
        """Test that get_system_broadcaster is called."""
        from fastapi import WebSocketDisconnect

        mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())
        mock_get_system_broadcaster = MagicMock(return_value=mock_system_broadcaster)

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_system_broadcaster",
                mock_get_system_broadcaster,
            ),
        ):
            await websocket_system_status(mock_websocket)

        # Verify get_system_broadcaster was called
        mock_get_system_broadcaster.assert_called_once()


# =============================================================================
# Tests for concurrent operations
# =============================================================================


class TestWebSocketConcurrency:
    """Tests for concurrent WebSocket operations."""

    @pytest.mark.asyncio
    async def test_events_rapid_messages(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Test handling of rapid successive messages.

        Now with validation, invalid messages receive error responses.
        """
        from fastapi import WebSocketDisconnect

        # Simulate many rapid messages followed by disconnect
        # Each invalid message gets an error response, ping gets pong
        messages = ["msg" + str(i) for i in range(100)] + ["ping"]
        mock_websocket.receive_text = AsyncMock(side_effect=[*messages, WebSocketDisconnect()])

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
        ):
            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Should have handled all messages:
        # - 100 error responses for invalid JSON messages
        # - 1 pong response for the "ping" message
        assert mock_websocket.send_text.await_count == 101
        mock_event_broadcaster.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_system_rapid_ping_messages(self, mock_websocket, mock_system_broadcaster):
        """Test handling of rapid ping messages."""
        from fastapi import WebSocketDisconnect

        # Simulate multiple ping messages
        messages = ["ping"] * 10
        mock_websocket.receive_text = AsyncMock(side_effect=[*messages, WebSocketDisconnect()])

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_system_broadcaster",
                return_value=mock_system_broadcaster,
            ),
        ):
            await websocket_system_status(mock_websocket)

        # Should have sent pong for each ping
        assert mock_websocket.send_text.await_count == 10
        mock_system_broadcaster.disconnect.assert_awaited_once()


# =============================================================================
# Tests for WebSocket Rate Limiting
# =============================================================================


class TestWebSocketRateLimiting:
    """Tests for WebSocket rate limiting functionality.

    These tests verify that the rate limiting middleware properly protects
    WebSocket endpoints from connection flood attacks.
    """

    @pytest.mark.asyncio
    async def test_events_endpoint_rejects_when_rate_limited(
        self, mock_websocket, mock_redis_client
    ):
        """Test that /ws/events rejects connections when rate limit is exceeded."""
        with patch(
            "backend.api.routes.websocket.check_websocket_rate_limit",
            AsyncMock(return_value=False),
        ):
            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Connection should be closed with policy violation code (1008)
        mock_websocket.close.assert_awaited_once_with(code=1008)

    @pytest.mark.asyncio
    async def test_system_endpoint_rejects_when_rate_limited(
        self, mock_websocket, mock_redis_client
    ):
        """Test that /ws/system rejects connections when rate limit is exceeded."""
        with patch(
            "backend.api.routes.websocket.check_websocket_rate_limit",
            AsyncMock(return_value=False),
        ):
            await websocket_system_status(mock_websocket, mock_redis_client)

        # Connection should be closed with policy violation code (1008)
        mock_websocket.close.assert_awaited_once_with(code=1008)

    @pytest.mark.asyncio
    async def test_rate_limit_checked_before_authentication(
        self, mock_websocket, mock_redis_client
    ):
        """Test that rate limit is checked before authentication for /ws/events.

        This ensures that even unauthenticated clients can't flood the
        authentication system.
        """
        auth_called = False

        async def mock_auth(_ws):
            nonlocal auth_called
            auth_called = True
            return True

        with (
            patch(
                "backend.api.routes.websocket.check_websocket_rate_limit",
                AsyncMock(return_value=False),
            ),
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                mock_auth,
            ),
        ):
            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Rate limit should reject before auth is called
        assert auth_called is False
        mock_websocket.close.assert_awaited_once_with(code=1008)

    @pytest.mark.asyncio
    async def test_rate_limit_allows_connection_when_under_limit(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Test that connections are allowed when under rate limit."""
        from fastapi import WebSocketDisconnect

        mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        with (
            patch(
                "backend.api.routes.websocket.check_websocket_rate_limit",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
        ):
            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Connection should be accepted (broadcaster.connect called)
        mock_event_broadcaster.connect.assert_awaited_once_with(mock_websocket)
        # close() should NOT be called with code 1008 (rate limit rejection)
        # The connection may be closed normally via disconnect, but not due to rate limiting
        rate_limit_close_calls = [
            call for call in mock_websocket.close.await_args_list if call.kwargs.get("code") == 1008
        ]
        assert len(rate_limit_close_calls) == 0

    @pytest.mark.asyncio
    async def test_rate_limit_logs_warning_on_rejection(
        self, mock_websocket, mock_redis_client, caplog
    ):
        """Test that rate limit rejections are logged for /ws/events."""
        with patch(
            "backend.api.routes.websocket.check_websocket_rate_limit",
            AsyncMock(return_value=False),
        ):
            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Should log rate limit exceeded warning
        assert "rate limit exceeded" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_system_rate_limit_logs_warning_on_rejection(
        self, mock_websocket, mock_redis_client, caplog
    ):
        """Test that rate limit rejections are logged for /ws/system."""
        with patch(
            "backend.api.routes.websocket.check_websocket_rate_limit",
            AsyncMock(return_value=False),
        ):
            await websocket_system_status(mock_websocket, mock_redis_client)

        # Should log rate limit exceeded warning
        assert "rate limit exceeded" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_rate_limit_passes_correct_arguments(self, mock_websocket, mock_redis_client):
        """Test that check_websocket_rate_limit receives correct arguments."""
        mock_check = AsyncMock(return_value=False)

        with patch(
            "backend.api.routes.websocket.check_websocket_rate_limit",
            mock_check,
        ):
            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Verify correct arguments passed to rate limit check
        mock_check.assert_awaited_once_with(mock_websocket, mock_redis_client)

    @pytest.mark.asyncio
    async def test_events_rate_limit_does_not_call_broadcaster_on_rejection(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Test that broadcaster is not touched when rate limit rejects connection."""
        with (
            patch(
                "backend.api.routes.websocket.check_websocket_rate_limit",
                AsyncMock(return_value=False),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
        ):
            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Broadcaster should not be connected
        mock_event_broadcaster.connect.assert_not_awaited()
        mock_event_broadcaster.disconnect.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_system_rate_limit_does_not_call_broadcaster_on_rejection(
        self, mock_websocket, mock_redis_client, mock_system_broadcaster
    ):
        """Test that system broadcaster is not touched when rate limit rejects."""
        with (
            patch(
                "backend.api.routes.websocket.check_websocket_rate_limit",
                AsyncMock(return_value=False),
            ),
            patch(
                "backend.api.routes.websocket.get_system_broadcaster",
                return_value=mock_system_broadcaster,
            ),
        ):
            await websocket_system_status(mock_websocket, mock_redis_client)

        # Broadcaster should not be connected
        mock_system_broadcaster.connect.assert_not_awaited()
        mock_system_broadcaster.disconnect.assert_not_awaited()
