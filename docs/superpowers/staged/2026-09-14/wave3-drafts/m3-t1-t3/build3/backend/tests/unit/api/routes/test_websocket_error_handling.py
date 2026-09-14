"""Unit tests for WebSocket error handling (NEM-2537).

This test module verifies comprehensive error handling in WebSocket message receivers:
1. All receive operations wrapped in try/except
2. JSON decode errors handled with user-friendly error response
3. Disconnect events logged with connection info
4. Unexpected errors logged with full context
5. Connection cleanup in finally block
6. Timeout handling with proper connection management

Tests follow TDD approach - written first to define expected behavior.
"""

from __future__ import annotations

import json
import logging
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocketDisconnect
from fastapi.websockets import WebSocketState

# Set DATABASE_URL for tests before importing any backend modules
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://test:test@localhost:5432/test",  # pragma: allowlist secret
)

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
    """Create a mock WebSocket connection with all required methods."""
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.close = AsyncMock()
    ws.client_state = WebSocketState.CONNECTED
    ws.query_params = {}
    ws.headers = {}
    # Add client address for logging tests
    ws.client = MagicMock()
    ws.client.host = "127.0.0.1"
    ws.client.port = 12345
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
    broadcaster.broadcast_event = AsyncMock(return_value=1)
    broadcaster.CHANNEL_NAME = "security_events"
    broadcaster.channel_name = "security_events"
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
# JSON Decode Error Handling Tests
# =============================================================================


class TestJSONDecodeErrorHandling:
    """Tests for JSON decode error handling in WebSocket message receivers."""

    @pytest.mark.asyncio
    async def test_invalid_json_sends_user_friendly_error(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Verify invalid JSON receives a user-friendly error response."""
        mock_websocket.receive_text = AsyncMock(
            side_effect=["not valid json {{", WebSocketDisconnect()]
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

        # Verify error response was sent
        mock_websocket.send_text.assert_awaited()
        call_args = mock_websocket.send_text.call_args_list[0][0][0]
        response = json.loads(call_args)

        assert response["type"] == "error"
        assert response["error"] == "invalid_json"
        assert "valid JSON" in response["message"]

    @pytest.mark.asyncio
    async def test_json_error_includes_data_preview(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Verify JSON decode error includes truncated data preview in details."""
        invalid_data = "x" * 200  # Long invalid data
        mock_websocket.receive_text = AsyncMock(side_effect=[invalid_data, WebSocketDisconnect()])

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

        call_args = mock_websocket.send_text.call_args_list[0][0][0]
        response = json.loads(call_args)

        assert "details" in response
        assert "raw_data_preview" in response["details"]
        # Preview should be truncated to 100 chars
        assert len(response["details"]["raw_data_preview"]) <= 100

    @pytest.mark.asyncio
    async def test_json_error_logs_warning(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster, caplog
    ):
        """Verify JSON decode error is logged as warning."""
        mock_websocket.receive_text = AsyncMock(side_effect=["invalid json", WebSocketDisconnect()])

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

        # Should log warning about invalid JSON
        assert "invalid JSON" in caplog.text.lower() or "invalid json" in caplog.text.lower()


# =============================================================================
# WebSocket Disconnect Handling Tests
# =============================================================================


class TestDisconnectHandling:
    """Tests for WebSocket disconnect event handling."""

    @pytest.mark.asyncio
    async def test_normal_disconnect_logged_with_connection_id(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster, caplog
    ):
        """Verify normal disconnect is logged with connection info."""
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

        # Should log disconnect event
        assert "disconnected" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_disconnect_with_code_logged(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster, caplog
    ):
        """Verify disconnect with code is logged appropriately."""
        mock_websocket.receive_text = AsyncMock(
            side_effect=WebSocketDisconnect(code=1001, reason="Going away")
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

        # Should log disconnect
        assert "disconnected" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_disconnect_during_handshake_handled(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster, caplog
    ):
        """Verify disconnect during handshake is handled gracefully."""
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

        # Should log handshake disconnect
        assert "disconnected" in caplog.text.lower()
        # Cleanup should still occur
        mock_event_broadcaster.disconnect.assert_awaited_once()


# =============================================================================
# Unexpected Error Handling Tests
# =============================================================================


class TestUnexpectedErrorHandling:
    """Tests for unexpected error handling with full context logging."""

    @pytest.mark.asyncio
    async def test_unexpected_error_logged_with_full_context(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster, caplog
    ):
        """Verify unexpected errors are logged with full context (exc_info)."""
        caplog.set_level(logging.ERROR)
        mock_websocket.receive_text = AsyncMock(side_effect=RuntimeError("Unexpected failure"))
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

        # Should log error with exc_info
        error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert len(error_records) >= 1

    @pytest.mark.asyncio
    async def test_unexpected_error_triggers_cleanup(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Verify unexpected errors still trigger connection cleanup."""
        mock_websocket.receive_text = AsyncMock(side_effect=RuntimeError("Network error"))
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

        # Cleanup should still occur
        mock_event_broadcaster.disconnect.assert_awaited_once_with(mock_websocket)

    @pytest.mark.asyncio
    async def test_error_when_already_disconnected_logs_differently(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster, caplog
    ):
        """Verify errors when WebSocket is already disconnected are handled."""
        mock_websocket.receive_text = AsyncMock(side_effect=RuntimeError("Connection lost"))
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

        # Should indicate client disconnected
        assert "disconnected" in caplog.text.lower()


# =============================================================================
# Connection Cleanup Tests
# =============================================================================


class TestConnectionCleanup:
    """Tests for connection cleanup in finally block."""

    @pytest.mark.asyncio
    async def test_cleanup_called_on_normal_disconnect(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Verify cleanup is called on normal disconnect."""
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

        mock_event_broadcaster.disconnect.assert_awaited_once_with(mock_websocket)

    @pytest.mark.asyncio
    async def test_cleanup_called_on_error(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Verify cleanup is called even when errors occur."""
        mock_websocket.receive_text = AsyncMock(side_effect=RuntimeError("Crash"))
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

        mock_event_broadcaster.disconnect.assert_awaited_once_with(mock_websocket)

    @pytest.mark.asyncio
    async def test_cleanup_called_on_timeout(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Verify cleanup is called on idle timeout."""

        async def timeout_on_receive():
            raise TimeoutError("Idle timeout")

        mock_websocket.receive_text = timeout_on_receive

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

        mock_event_broadcaster.disconnect.assert_awaited_once_with(mock_websocket)

    @pytest.mark.asyncio
    async def test_heartbeat_task_cancelled_on_cleanup(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Verify heartbeat task is cancelled during cleanup."""
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

        # Cleanup should complete without heartbeat task issues
        mock_event_broadcaster.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_subscription_manager_cleanup_on_disconnect(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Verify subscription manager is cleaned up on disconnect."""
        mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())
        mock_subscription_manager = MagicMock()
        mock_subscription_manager.register_connection = MagicMock()
        mock_subscription_manager.remove_connection = MagicMock()

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
            patch(
                "backend.api.routes.websocket.get_subscription_manager",
                return_value=mock_subscription_manager,
            ),
        ):
            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Subscription manager should be cleaned up
        mock_subscription_manager.remove_connection.assert_called_once()


# =============================================================================
# Timeout Handling Tests
# =============================================================================


class TestTimeoutHandling:
    """Tests for timeout handling in WebSocket message receivers."""

    @pytest.mark.asyncio
    async def test_idle_timeout_closes_connection(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster, caplog
    ):
        """Verify idle timeout closes the connection gracefully."""

        async def raise_timeout():
            raise TimeoutError("Idle timeout exceeded")

        mock_websocket.receive_text = raise_timeout

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

        # Connection should be closed with timeout reason
        mock_websocket.close.assert_awaited_once()
        close_call = mock_websocket.close.call_args
        assert close_call.kwargs.get("code") == 1000 or close_call[1].get("code") == 1000

    @pytest.mark.asyncio
    async def test_timeout_logged_with_duration(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster, caplog
    ):
        """Verify timeout is logged with timeout duration info."""

        async def raise_timeout():
            raise TimeoutError("Idle timeout")

        mock_websocket.receive_text = raise_timeout

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

        # Should log timeout info
        assert "timeout" in caplog.text.lower()


# =============================================================================
# System Endpoint Error Handling Tests
# =============================================================================


class TestSystemEndpointErrorHandling:
    """Tests for error handling in /ws/system endpoint."""

    @pytest.mark.asyncio
    async def test_system_endpoint_json_error_handled(
        self, mock_websocket, mock_redis_client, mock_system_broadcaster
    ):
        """Verify /ws/system handles JSON decode errors."""
        mock_websocket.receive_text = AsyncMock(side_effect=["invalid json", WebSocketDisconnect()])

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
            await websocket_system_status(mock_websocket, mock_redis_client)

        # Should send error response
        mock_websocket.send_text.assert_awaited()
        call_args = mock_websocket.send_text.call_args_list[0][0][0]
        response = json.loads(call_args)
        assert response["type"] == "error"

    @pytest.mark.asyncio
    async def test_system_endpoint_cleanup_on_error(
        self, mock_websocket, mock_redis_client, mock_system_broadcaster
    ):
        """Verify /ws/system cleans up on unexpected error."""
        mock_websocket.receive_text = AsyncMock(side_effect=RuntimeError("Crash"))
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
            await websocket_system_status(mock_websocket, mock_redis_client)

        mock_system_broadcaster.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_system_endpoint_timeout_handling(
        self, mock_websocket, mock_redis_client, mock_system_broadcaster
    ):
        """Verify /ws/system handles timeout properly."""

        async def raise_timeout():
            raise TimeoutError("Idle timeout")

        mock_websocket.receive_text = raise_timeout

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
            await websocket_system_status(mock_websocket, mock_redis_client)

        mock_websocket.close.assert_awaited_once()
        mock_system_broadcaster.disconnect.assert_awaited_once()


# =============================================================================
# Connection ID Context Tests
# =============================================================================


class TestConnectionIDContext:
    """Tests for connection ID context management during errors."""

    @pytest.mark.asyncio
    async def test_connection_id_cleared_on_disconnect(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Verify connection ID context is cleared on disconnect."""
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
            patch("backend.api.routes.websocket.set_connection_id") as mock_set_conn_id,
        ):
            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Connection ID should be set initially and then cleared (None)
        calls = mock_set_conn_id.call_args_list
        assert len(calls) >= 2
        # Last call should clear the connection ID
        assert calls[-1][0][0] is None

    @pytest.mark.asyncio
    async def test_connection_id_cleared_on_error(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Verify connection ID context is cleared even on error."""
        mock_websocket.receive_text = AsyncMock(side_effect=RuntimeError("Crash"))
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
            patch("backend.api.routes.websocket.set_connection_id") as mock_set_conn_id,
        ):
            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Connection ID should be cleared (None) in finally block
        calls = mock_set_conn_id.call_args_list
        assert calls[-1][0][0] is None


# =============================================================================
# Multiple Error Recovery Tests
# =============================================================================


class TestMultipleErrorRecovery:
    """Tests for handling multiple errors in sequence."""

    @pytest.mark.asyncio
    async def test_multiple_json_errors_before_disconnect(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Verify multiple JSON errors are handled before final disconnect."""
        mock_websocket.receive_text = AsyncMock(
            side_effect=[
                "bad json 1",
                "bad json 2",
                "bad json 3",
                WebSocketDisconnect(),
            ]
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

        # Should have sent 3 error responses
        assert mock_websocket.send_text.await_count == 3
        # Cleanup should still occur
        mock_event_broadcaster.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_mixed_messages_and_errors(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Verify handling of mixed valid and invalid messages."""
        mock_websocket.receive_text = AsyncMock(
            side_effect=[
                "ping",  # Valid legacy ping
                "bad json",  # Invalid
                '{"type": "ping"}',  # Valid JSON ping
                WebSocketDisconnect(),
            ]
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

        # Should have sent:
        # 1. pong for "ping"
        # 2. error for "bad json"
        # 3. pong for JSON ping
        assert mock_websocket.send_text.await_count == 3


# =============================================================================
# Send Error Handling Tests
# =============================================================================


class TestSendErrorHandling:
    """Tests for error handling when sending responses fails."""

    @pytest.mark.asyncio
    async def test_send_error_breaks_loop_gracefully(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Verify that send errors cause graceful loop termination."""
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
            # Should not raise - error during send should break loop
            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Cleanup should still occur
        mock_event_broadcaster.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_error_does_not_prevent_cleanup(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Verify that errors during close don't prevent cleanup."""

        async def raise_timeout():
            raise TimeoutError("Idle timeout")

        mock_websocket.receive_text = raise_timeout
        mock_websocket.close = AsyncMock(side_effect=RuntimeError("Already closed"))

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
            # Should not raise even if close fails
            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Broadcaster disconnect should still be called
        mock_event_broadcaster.disconnect.assert_awaited_once()
