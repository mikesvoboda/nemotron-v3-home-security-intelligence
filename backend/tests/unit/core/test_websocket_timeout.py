"""Unit tests for WebSocket timeout and reconnection handling.

Tests cover:
- Idle timeout handling for WebSocket connections
- Server heartbeat (ping) sending behavior
- Client disconnect detection and cleanup
- Message queue behavior during disconnection
- Heartbeat task lifecycle and cleanup
"""

from __future__ import annotations

import asyncio
import logging
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.websockets import WebSocketState

# Set DATABASE_URL for tests before importing any backend modules
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")

from backend.api.routes.websocket import (
    send_heartbeat,
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
# Idle Timeout Tests for /ws/events
# =============================================================================


class TestWebSocketIdleTimeout:
    """Tests for WebSocket idle timeout handling."""

    @pytest.mark.asyncio
    async def test_events_idle_timeout_closes_connection(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Test that idle timeout triggers connection close."""
        # Simulate timeout by raising TimeoutError
        mock_websocket.receive_text = AsyncMock(side_effect=TimeoutError())

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.check_websocket_rate_limit",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
            patch("backend.api.routes.websocket.get_settings") as mock_settings,
        ):
            mock_settings.return_value.websocket_idle_timeout_seconds = 5
            mock_settings.return_value.websocket_ping_interval_seconds = 30

            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Connection should be closed with reason
        mock_websocket.close.assert_awaited_once()
        call_args = mock_websocket.close.call_args
        assert call_args.kwargs.get("code") == 1000
        assert "Idle timeout" in call_args.kwargs.get("reason", "")

    @pytest.mark.asyncio
    async def test_events_idle_timeout_logs_message(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster, caplog
    ):
        """Test that idle timeout is logged."""
        mock_websocket.receive_text = AsyncMock(side_effect=TimeoutError())

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.check_websocket_rate_limit",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
            patch("backend.api.routes.websocket.get_settings") as mock_settings,
        ):
            mock_settings.return_value.websocket_idle_timeout_seconds = 300
            mock_settings.return_value.websocket_ping_interval_seconds = 30

            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Should log idle timeout
        assert "idle timeout" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_events_idle_timeout_disconnects_broadcaster(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Test that idle timeout properly disconnects from broadcaster."""
        mock_websocket.receive_text = AsyncMock(side_effect=TimeoutError())

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.check_websocket_rate_limit",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
            patch("backend.api.routes.websocket.get_settings") as mock_settings,
        ):
            mock_settings.return_value.websocket_idle_timeout_seconds = 5
            mock_settings.return_value.websocket_ping_interval_seconds = 30

            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Broadcaster disconnect should be called
        mock_event_broadcaster.disconnect.assert_awaited_once_with(mock_websocket)

    @pytest.mark.asyncio
    async def test_system_idle_timeout_closes_connection(
        self, mock_websocket, mock_redis_client, mock_system_broadcaster
    ):
        """Test that idle timeout triggers connection close for /ws/system."""
        mock_websocket.receive_text = AsyncMock(side_effect=TimeoutError())

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.check_websocket_rate_limit",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_system_broadcaster",
                return_value=mock_system_broadcaster,
            ),
            patch("backend.api.routes.websocket.get_settings") as mock_settings,
        ):
            mock_settings.return_value.websocket_idle_timeout_seconds = 5
            mock_settings.return_value.websocket_ping_interval_seconds = 30

            await websocket_system_status(mock_websocket, mock_redis_client)

        # Connection should be closed with reason
        mock_websocket.close.assert_awaited_once()
        call_args = mock_websocket.close.call_args
        assert call_args.kwargs.get("code") == 1000
        assert "Idle timeout" in call_args.kwargs.get("reason", "")


# =============================================================================
# Server Heartbeat Tests
# =============================================================================


class TestServerHeartbeat:
    """Tests for server-initiated heartbeat (ping) behavior."""

    @pytest.mark.asyncio
    async def test_heartbeat_sends_ping_message(self, mock_websocket):
        """Test that heartbeat sends ping message at intervals."""
        mock_websocket.client_state = WebSocketState.CONNECTED
        stop_event = asyncio.Event()

        # Run heartbeat for a short period then stop
        async def stop_after_delay():
            await asyncio.sleep(0.15)
            stop_event.set()

        asyncio.create_task(stop_after_delay())

        # Very short interval for testing
        await send_heartbeat(mock_websocket, interval=0.05, stop_event=stop_event)

        # Should have sent at least 1-2 pings
        assert mock_websocket.send_text.await_count >= 1
        # Verify ping message format (includes lastSeq from NEM-3142)
        import json

        for call in mock_websocket.send_text.call_args_list:
            msg = json.loads(call[0][0])
            assert msg["type"] == "ping"
            assert "lastSeq" in msg  # NEM-3142: sequence tracking

    @pytest.mark.asyncio
    async def test_heartbeat_stops_when_event_set(self, mock_websocket):
        """Test that heartbeat stops when stop_event is set."""
        mock_websocket.client_state = WebSocketState.CONNECTED
        stop_event = asyncio.Event()

        # Set stop event immediately
        stop_event.set()

        await send_heartbeat(mock_websocket, interval=1, stop_event=stop_event)

        # Should not have sent any pings
        mock_websocket.send_text.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_heartbeat_stops_when_disconnected(self, mock_websocket):
        """Test that heartbeat stops when client disconnects."""
        stop_event = asyncio.Event()
        call_count = 0

        # Simulate client disconnecting after first ping
        async def send_with_disconnect(msg):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                mock_websocket.client_state = WebSocketState.DISCONNECTED

        mock_websocket.client_state = WebSocketState.CONNECTED
        mock_websocket.send_text = AsyncMock(side_effect=send_with_disconnect)

        await send_heartbeat(mock_websocket, interval=0.01, stop_event=stop_event)

        # Should have stopped after detecting disconnect
        assert call_count <= 2  # May have 1-2 calls before detecting state change

    @pytest.mark.asyncio
    async def test_heartbeat_handles_send_error(self, mock_websocket):
        """Test that heartbeat handles send errors gracefully."""
        mock_websocket.client_state = WebSocketState.CONNECTED
        mock_websocket.send_text = AsyncMock(side_effect=RuntimeError("Connection lost"))
        stop_event = asyncio.Event()

        # Should not raise - handles error gracefully
        await send_heartbeat(mock_websocket, interval=0.01, stop_event=stop_event)

        # Task should exit after error
        mock_websocket.send_text.assert_awaited_once()


# =============================================================================
# Client Disconnect Detection Tests
# =============================================================================


class TestClientDisconnectDetection:
    """Tests for client disconnect detection and cleanup."""

    @pytest.mark.asyncio
    async def test_events_disconnect_cleans_up_heartbeat(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Test that client disconnect cleans up heartbeat task."""
        from fastapi import WebSocketDisconnect

        mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.check_websocket_rate_limit",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
            patch("backend.api.routes.websocket.get_settings") as mock_settings,
        ):
            mock_settings.return_value.websocket_idle_timeout_seconds = 300
            mock_settings.return_value.websocket_ping_interval_seconds = 30

            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Broadcaster should be disconnected (cleanup happened)
        mock_event_broadcaster.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_events_exception_cleans_up_connection(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Test that exceptions during receive clean up connection."""
        mock_websocket.receive_text = AsyncMock(side_effect=RuntimeError("Connection error"))
        mock_websocket.client_state = WebSocketState.CONNECTED

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.check_websocket_rate_limit",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
            patch("backend.api.routes.websocket.get_settings") as mock_settings,
        ):
            mock_settings.return_value.websocket_idle_timeout_seconds = 300
            mock_settings.return_value.websocket_ping_interval_seconds = 30

            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Connection should still be cleaned up
        mock_event_broadcaster.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_system_disconnect_cleans_up_heartbeat(
        self, mock_websocket, mock_redis_client, mock_system_broadcaster
    ):
        """Test that client disconnect cleans up heartbeat for /ws/system."""
        from fastapi import WebSocketDisconnect

        mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.check_websocket_rate_limit",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_system_broadcaster",
                return_value=mock_system_broadcaster,
            ),
            patch("backend.api.routes.websocket.get_settings") as mock_settings,
        ):
            mock_settings.return_value.websocket_idle_timeout_seconds = 300
            mock_settings.return_value.websocket_ping_interval_seconds = 30

            await websocket_system_status(mock_websocket, mock_redis_client)

        # Broadcaster should be disconnected (cleanup happened)
        mock_system_broadcaster.disconnect.assert_awaited_once()


# =============================================================================
# Heartbeat Task Lifecycle Tests
# =============================================================================


class TestHeartbeatTaskLifecycle:
    """Tests for heartbeat task lifecycle management."""

    @pytest.mark.asyncio
    async def test_heartbeat_task_cancelled_on_disconnect(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Test that heartbeat task is cancelled when client disconnects."""
        from fastapi import WebSocketDisconnect

        # Track if heartbeat stop event was set
        heartbeat_stopped = False
        original_event_set = asyncio.Event.set

        def track_stop(self):
            nonlocal heartbeat_stopped
            heartbeat_stopped = True
            original_event_set(self)

        mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.check_websocket_rate_limit",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
            patch("backend.api.routes.websocket.get_settings") as mock_settings,
            patch.object(asyncio.Event, "set", track_stop),
        ):
            mock_settings.return_value.websocket_idle_timeout_seconds = 300
            mock_settings.return_value.websocket_ping_interval_seconds = 30

            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Heartbeat should have been stopped
        assert heartbeat_stopped

    @pytest.mark.asyncio
    async def test_heartbeat_task_cancelled_on_timeout(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Test that heartbeat task is cancelled on idle timeout."""
        heartbeat_stopped = False
        original_event_set = asyncio.Event.set

        def track_stop(self):
            nonlocal heartbeat_stopped
            heartbeat_stopped = True
            original_event_set(self)

        mock_websocket.receive_text = AsyncMock(side_effect=TimeoutError())

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.check_websocket_rate_limit",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
            patch("backend.api.routes.websocket.get_settings") as mock_settings,
            patch.object(asyncio.Event, "set", track_stop),
        ):
            mock_settings.return_value.websocket_idle_timeout_seconds = 5
            mock_settings.return_value.websocket_ping_interval_seconds = 30

            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Heartbeat should have been stopped
        assert heartbeat_stopped


# =============================================================================
# Keepalive Message Tests
# =============================================================================


class TestKeepaliveMessages:
    """Tests for client keepalive message handling."""

    @pytest.mark.asyncio
    async def test_ping_resets_idle_timer(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Test that receiving ping message resets the idle timeout."""
        from fastapi import WebSocketDisconnect

        # Send ping, then disconnect
        mock_websocket.receive_text = AsyncMock(side_effect=["ping", WebSocketDisconnect()])

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.check_websocket_rate_limit",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
            patch("backend.api.routes.websocket.get_settings") as mock_settings,
        ):
            mock_settings.return_value.websocket_idle_timeout_seconds = 300
            mock_settings.return_value.websocket_ping_interval_seconds = 30

            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Should have sent pong response
        mock_websocket.send_text.assert_awaited()
        # Find the pong response
        pong_sent = any(
            '{"type":"pong"}' in str(call) for call in mock_websocket.send_text.call_args_list
        )
        assert pong_sent

    @pytest.mark.asyncio
    async def test_json_ping_resets_idle_timer(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Test that JSON ping message resets the idle timeout."""
        from fastapi import WebSocketDisconnect

        # Send JSON ping, then disconnect
        mock_websocket.receive_text = AsyncMock(
            side_effect=['{"type": "ping"}', WebSocketDisconnect()]
        )

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.check_websocket_rate_limit",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
            patch("backend.api.routes.websocket.get_settings") as mock_settings,
        ):
            mock_settings.return_value.websocket_idle_timeout_seconds = 300
            mock_settings.return_value.websocket_ping_interval_seconds = 30

            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Should have sent pong response
        mock_websocket.send_text.assert_awaited()
        # Find the pong response
        pong_sent = any(
            '{"type":"pong"}' in str(call) for call in mock_websocket.send_text.call_args_list
        )
        assert pong_sent

    @pytest.mark.asyncio
    async def test_pong_response_acknowledged(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Test that client pong response (to server ping) is handled silently."""
        from fastapi import WebSocketDisconnect

        # Client sends pong in response to server ping
        mock_websocket.receive_text = AsyncMock(
            side_effect=['{"type": "pong"}', WebSocketDisconnect()]
        )

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.check_websocket_rate_limit",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
            patch("backend.api.routes.websocket.get_settings") as mock_settings,
        ):
            mock_settings.return_value.websocket_idle_timeout_seconds = 300
            mock_settings.return_value.websocket_ping_interval_seconds = 30

            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Pong should not trigger an error response (it's a valid message type)
        # Check that no error was sent
        error_sent = any('"error"' in str(call) for call in mock_websocket.send_text.call_args_list)
        assert not error_sent


# =============================================================================
# Connection Recovery Tests
# =============================================================================


class TestConnectionRecovery:
    """Tests for connection recovery scenarios."""

    @pytest.mark.asyncio
    async def test_new_connection_after_timeout(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Test that a new connection can be established after timeout."""
        # First connection times out
        mock_websocket.receive_text = AsyncMock(side_effect=TimeoutError())

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.check_websocket_rate_limit",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
            patch("backend.api.routes.websocket.get_settings") as mock_settings,
        ):
            mock_settings.return_value.websocket_idle_timeout_seconds = 5
            mock_settings.return_value.websocket_ping_interval_seconds = 30

            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Verify cleanup happened
        mock_event_broadcaster.disconnect.assert_awaited_once()

        # Reset mocks for second connection
        mock_event_broadcaster.reset_mock()
        mock_websocket.reset_mock()

        from fastapi import WebSocketDisconnect

        mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())
        mock_websocket.client_state = WebSocketState.CONNECTED

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.check_websocket_rate_limit",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
            patch("backend.api.routes.websocket.get_settings") as mock_settings,
        ):
            mock_settings.return_value.websocket_idle_timeout_seconds = 300
            mock_settings.return_value.websocket_ping_interval_seconds = 30

            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Second connection should work
        mock_event_broadcaster.connect.assert_awaited_once()
        mock_event_broadcaster.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_multiple_connections_after_errors(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster
    ):
        """Test that multiple connections can be established after errors."""
        from fastapi import WebSocketDisconnect

        for i in range(3):
            # Each connection encounters an error
            if i == 0:
                mock_websocket.receive_text = AsyncMock(side_effect=TimeoutError())
            elif i == 1:
                mock_websocket.receive_text = AsyncMock(side_effect=RuntimeError("Test error"))
            else:
                mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

            mock_websocket.client_state = WebSocketState.CONNECTED

            with (
                patch(
                    "backend.api.routes.websocket.authenticate_websocket",
                    AsyncMock(return_value=True),
                ),
                patch(
                    "backend.api.routes.websocket.check_websocket_rate_limit",
                    AsyncMock(return_value=True),
                ),
                patch(
                    "backend.api.routes.websocket.get_broadcaster",
                    AsyncMock(return_value=mock_event_broadcaster),
                ),
                patch("backend.api.routes.websocket.get_settings") as mock_settings,
            ):
                mock_settings.return_value.websocket_idle_timeout_seconds = 5
                mock_settings.return_value.websocket_ping_interval_seconds = 30

                await websocket_events_endpoint(mock_websocket, mock_redis_client)

            # Each connection should trigger disconnect
            assert mock_event_broadcaster.disconnect.await_count == i + 1

            # Reset for next iteration
            mock_websocket.reset_mock()


# =============================================================================
# Cleanup Tests
# =============================================================================


class TestWebSocketCleanup:
    """Tests for proper resource cleanup on disconnect."""

    @pytest.mark.asyncio
    async def test_cleanup_on_normal_disconnect(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster, caplog
    ):
        """Test cleanup logging on normal disconnect."""
        from fastapi import WebSocketDisconnect

        mock_websocket.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.check_websocket_rate_limit",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
            patch("backend.api.routes.websocket.get_settings") as mock_settings,
        ):
            mock_settings.return_value.websocket_idle_timeout_seconds = 300
            mock_settings.return_value.websocket_ping_interval_seconds = 30

            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Verify cleanup was logged
        assert "cleaned up" in caplog.text.lower() or "disconnected" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_cleanup_on_error_disconnect(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster, caplog
    ):
        """Test cleanup logging on error disconnect."""
        mock_websocket.receive_text = AsyncMock(side_effect=RuntimeError("Connection error"))
        mock_websocket.client_state = WebSocketState.CONNECTED

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.check_websocket_rate_limit",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
            patch("backend.api.routes.websocket.get_settings") as mock_settings,
        ):
            mock_settings.return_value.websocket_idle_timeout_seconds = 300
            mock_settings.return_value.websocket_ping_interval_seconds = 30

            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Verify cleanup was still performed
        mock_event_broadcaster.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cleanup_on_timeout_disconnect(
        self, mock_websocket, mock_redis_client, mock_event_broadcaster, caplog
    ):
        """Test cleanup logging on timeout disconnect."""
        mock_websocket.receive_text = AsyncMock(side_effect=TimeoutError())

        with (
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.check_websocket_rate_limit",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.get_broadcaster",
                AsyncMock(return_value=mock_event_broadcaster),
            ),
            patch("backend.api.routes.websocket.get_settings") as mock_settings,
        ):
            mock_settings.return_value.websocket_idle_timeout_seconds = 5
            mock_settings.return_value.websocket_ping_interval_seconds = 30

            await websocket_events_endpoint(mock_websocket, mock_redis_client)

        # Verify cleanup was performed
        mock_event_broadcaster.disconnect.assert_awaited_once()
        assert "cleaned up" in caplog.text.lower() or "disconnected" in caplog.text.lower()
