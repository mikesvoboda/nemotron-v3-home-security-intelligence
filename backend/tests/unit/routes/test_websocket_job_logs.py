"""Unit tests for WebSocket job logs endpoint (backend/api/routes/websocket.py).

Tests cover:
- WebSocket connection handling for /ws/jobs/{job_id}/logs endpoint
- Authentication flow (success and failure)
- Message receiving/sending (including ping/pong)
- Redis pub/sub subscription and log forwarding
- Disconnection handling (normal, WebSocketDisconnect, other exceptions)
- Proper cleanup on disconnect (heartbeat, log listener, pub/sub)
"""

from __future__ import annotations

import asyncio
import logging
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.websockets import WebSocketState

# Set DATABASE_URL for tests before importing any backend modules
_TEST_DB_URL = "postgresql+asyncpg://test:test@localhost:5432/test"  # pragma: allowlist secret
os.environ.setdefault("DATABASE_URL", _TEST_DB_URL)

from backend.api.routes.websocket import websocket_job_logs  # noqa: E402


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

    # Create a proper mock for create_pubsub that returns an async context manager
    mock_pubsub = MagicMock()
    mock_pubsub.subscribe = AsyncMock()
    mock_pubsub.unsubscribe = AsyncMock()
    mock_pubsub.close = AsyncMock()

    # Make listen() return an async generator that yields nothing initially
    async def mock_listen():
        # Yield nothing, just wait to be cancelled
        try:
            await asyncio.sleep(1000)
        except asyncio.CancelledError:
            return
        # This line is never reached in tests but makes this an async generator
        # We can't use `if False: yield` because vulture detects unsatisfiable conditions
        for _ in []:  # Empty iterable - never executed but makes this a generator
            yield

    mock_pubsub.listen = mock_listen
    redis.create_pubsub = MagicMock(return_value=mock_pubsub)

    return redis


@pytest.fixture
def sample_job_id() -> str:
    """Sample job ID for tests."""
    return "550e8400-e29b-41d4-a716-446655440000"


# =============================================================================
# Tests for /ws/jobs/{job_id}/logs endpoint
# =============================================================================


class TestWebSocketJobLogsEndpoint:
    """Tests for the /ws/jobs/{job_id}/logs WebSocket endpoint."""

    @pytest.mark.asyncio
    async def test_authentication_failure_rejects_connection(
        self,
        mock_websocket,
        mock_redis_client,
        sample_job_id: str,
    ):
        """Test that authentication failure rejects the connection."""
        with patch(
            "backend.api.routes.websocket.authenticate_websocket",
            AsyncMock(return_value=False),
        ):
            await websocket_job_logs(mock_websocket, sample_job_id, mock_redis_client)

        # Connection should not be accepted (websocket.accept not called)
        mock_websocket.accept.assert_not_called()

    @pytest.mark.asyncio
    async def test_rate_limit_rejection(
        self,
        mock_websocket,
        mock_redis_client,
        sample_job_id: str,
    ):
        """Test that rate limit exceeded rejects the connection."""
        with patch(
            "backend.api.routes.websocket.check_websocket_rate_limit",
            AsyncMock(return_value=False),
        ):
            await websocket_job_logs(mock_websocket, sample_job_id, mock_redis_client)

        # Connection should be closed with policy violation code (1008)
        mock_websocket.close.assert_awaited_once_with(code=1008)

    @pytest.mark.asyncio
    async def test_authentication_success_connects(
        self,
        mock_websocket,
        mock_redis_client,
        sample_job_id: str,
    ):
        """Test that successful authentication connects the client."""
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
        ):
            await websocket_job_logs(mock_websocket, sample_job_id, mock_redis_client)

        # Connection should be accepted
        mock_websocket.accept.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_subscribes_to_job_logs_channel(
        self,
        mock_websocket,
        mock_redis_client,
        sample_job_id: str,
    ):
        """Test that endpoint subscribes to the correct Redis channel."""
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
        ):
            await websocket_job_logs(mock_websocket, sample_job_id, mock_redis_client)

        # Should have created a pubsub and subscribed to the job channel
        mock_redis_client.create_pubsub.assert_called_once()
        mock_pubsub = mock_redis_client.create_pubsub.return_value
        mock_pubsub.subscribe.assert_awaited_once_with(f"job:{sample_job_id}:logs")

    @pytest.mark.asyncio
    async def test_ping_message_sends_pong_response(
        self,
        mock_websocket,
        mock_redis_client,
        sample_job_id: str,
    ):
        """Test that a 'ping' message results in a '{"type":"pong"}' response."""
        from fastapi import WebSocketDisconnect

        # First call returns "ping", second call raises WebSocketDisconnect
        mock_websocket.receive_text = AsyncMock(side_effect=["ping", WebSocketDisconnect()])

        with (
            patch(
                "backend.api.routes.websocket.check_websocket_rate_limit",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
        ):
            await websocket_job_logs(mock_websocket, sample_job_id, mock_redis_client)

        # Should have sent pong response
        mock_websocket.send_text.assert_any_call('{"type":"pong"}')

    @pytest.mark.asyncio
    async def test_disconnect_cleans_up_resources(
        self,
        mock_websocket,
        mock_redis_client,
        sample_job_id: str,
    ):
        """Test that disconnection properly cleans up resources."""
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
        ):
            await websocket_job_logs(mock_websocket, sample_job_id, mock_redis_client)

        # Should have unsubscribed from channel
        mock_pubsub = mock_redis_client.create_pubsub.return_value
        mock_pubsub.unsubscribe.assert_awaited_once_with(f"job:{sample_job_id}:logs")
        mock_pubsub.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_timeout_closes_connection(
        self,
        mock_websocket,
        mock_redis_client,
        sample_job_id: str,
    ):
        """Test that idle timeout closes the connection."""
        # Simulate timeout by raising TimeoutError
        mock_websocket.receive_text = AsyncMock(side_effect=TimeoutError())

        with (
            patch(
                "backend.api.routes.websocket.check_websocket_rate_limit",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
        ):
            await websocket_job_logs(mock_websocket, sample_job_id, mock_redis_client)

        # Connection should be closed with idle timeout
        mock_websocket.close.assert_awaited_with(code=1000, reason="Idle timeout")

    @pytest.mark.asyncio
    async def test_unexpected_error_cleans_up(
        self,
        mock_websocket,
        mock_redis_client,
        sample_job_id: str,
    ):
        """Test that unexpected errors properly clean up resources."""
        mock_websocket.receive_text = AsyncMock(side_effect=RuntimeError("Test error"))
        mock_websocket.client_state = WebSocketState.DISCONNECTED

        with (
            patch(
                "backend.api.routes.websocket.check_websocket_rate_limit",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
        ):
            await websocket_job_logs(mock_websocket, sample_job_id, mock_redis_client)

        # Should still clean up pubsub
        mock_pubsub = mock_redis_client.create_pubsub.return_value
        mock_pubsub.unsubscribe.assert_awaited_once()
        mock_pubsub.close.assert_awaited_once()


# =============================================================================
# Tests for log forwarding from Redis to WebSocket
# =============================================================================


class TestLogForwarding:
    """Tests for Redis pub/sub log forwarding to WebSocket."""

    @pytest.mark.asyncio
    async def test_log_message_forwarded_to_websocket(
        self,
        mock_websocket,
        mock_redis_client,
        sample_job_id: str,
    ):
        """Test that log messages from Redis are forwarded to WebSocket."""
        from fastapi import WebSocketDisconnect

        # Track messages received
        received_messages = []

        async def mock_listen():
            # Yield a log message first
            yield {
                "type": "message",
                "data": b'{"type":"log","data":{"level":"INFO","message":"Test"}}',
            }
            # Then raise disconnect
            raise asyncio.CancelledError()

        mock_pubsub = mock_redis_client.create_pubsub.return_value
        mock_pubsub.listen = mock_listen

        # Capture send_text calls
        async def capture_send(text):
            received_messages.append(text)

        mock_websocket.send_text = AsyncMock(side_effect=capture_send)
        # Disconnect after some time
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
        ):
            await websocket_job_logs(mock_websocket, sample_job_id, mock_redis_client)

        # Verify log message was forwarded
        assert any('{"type":"log"' in msg for msg in received_messages)

    @pytest.mark.asyncio
    async def test_bytes_message_decoded(
        self,
        mock_websocket,
        mock_redis_client,
        sample_job_id: str,
    ):
        """Test that byte messages from Redis are decoded properly."""
        from fastapi import WebSocketDisconnect

        async def mock_listen():
            # Yield a bytes message
            yield {
                "type": "message",
                "data": b'{"type":"log","data":{"level":"INFO","message":"Test bytes"}}',
            }
            raise asyncio.CancelledError()

        mock_pubsub = mock_redis_client.create_pubsub.return_value
        mock_pubsub.listen = mock_listen

        sent_messages = []
        original_send = mock_websocket.send_text

        async def capture_send(text):
            sent_messages.append(text)

        mock_websocket.send_text = AsyncMock(side_effect=capture_send)
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
        ):
            await websocket_job_logs(mock_websocket, sample_job_id, mock_redis_client)

        # Verify the bytes were decoded and forwarded
        assert any("Test bytes" in msg for msg in sent_messages)


# =============================================================================
# Tests for logging behavior
# =============================================================================


class TestWebSocketJobLogsLogging:
    """Tests to verify proper logging during WebSocket operations."""

    @pytest.mark.asyncio
    async def test_logs_connection_info(
        self,
        mock_websocket,
        mock_redis_client,
        sample_job_id: str,
        caplog,
    ):
        """Test that connection/disconnection info is logged."""
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
        ):
            await websocket_job_logs(mock_websocket, sample_job_id, mock_redis_client)

        # Check that relevant log messages were emitted
        assert "WebSocket client connected" in caplog.text
        # The job_id is in the endpoint path or cleaned up message
        assert "job" in caplog.text.lower()

    @pytest.mark.asyncio
    async def test_logs_authentication_failure(
        self,
        mock_websocket,
        mock_redis_client,
        sample_job_id: str,
        caplog,
    ):
        """Test that authentication failure is logged."""
        with patch(
            "backend.api.routes.websocket.authenticate_websocket",
            AsyncMock(return_value=False),
        ):
            await websocket_job_logs(mock_websocket, sample_job_id, mock_redis_client)

        assert "authentication failed" in caplog.text

    @pytest.mark.asyncio
    async def test_logs_rate_limit_exceeded(
        self,
        mock_websocket,
        mock_redis_client,
        sample_job_id: str,
        caplog,
    ):
        """Test that rate limit exceeded is logged."""
        with patch(
            "backend.api.routes.websocket.check_websocket_rate_limit",
            AsyncMock(return_value=False),
        ):
            await websocket_job_logs(mock_websocket, sample_job_id, mock_redis_client)

        assert "rate limit exceeded" in caplog.text.lower()


# =============================================================================
# Tests for multiple messages
# =============================================================================


class TestMultipleMessages:
    """Tests for handling multiple WebSocket messages."""

    @pytest.mark.asyncio
    async def test_multiple_ping_messages(
        self,
        mock_websocket,
        mock_redis_client,
        sample_job_id: str,
    ):
        """Test handling of multiple ping messages."""
        from fastapi import WebSocketDisconnect

        mock_websocket.receive_text = AsyncMock(
            side_effect=["ping", "ping", "ping", WebSocketDisconnect()]
        )

        with (
            patch(
                "backend.api.routes.websocket.check_websocket_rate_limit",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
        ):
            await websocket_job_logs(mock_websocket, sample_job_id, mock_redis_client)

        # Should have sent 3 pong responses
        pong_calls = [
            call
            for call in mock_websocket.send_text.call_args_list
            if '{"type":"pong"}' in str(call)
        ]
        assert len(pong_calls) == 3

    @pytest.mark.asyncio
    async def test_invalid_json_message_sends_error(
        self,
        mock_websocket,
        mock_redis_client,
        sample_job_id: str,
    ):
        """Test that invalid JSON messages receive an error response."""
        from fastapi import WebSocketDisconnect

        mock_websocket.receive_text = AsyncMock(side_effect=["not-json", WebSocketDisconnect()])

        with (
            patch(
                "backend.api.routes.websocket.check_websocket_rate_limit",
                AsyncMock(return_value=True),
            ),
            patch(
                "backend.api.routes.websocket.authenticate_websocket",
                AsyncMock(return_value=True),
            ),
        ):
            await websocket_job_logs(mock_websocket, sample_job_id, mock_redis_client)

        # Should have sent an error response
        sent_messages = [str(call) for call in mock_websocket.send_text.call_args_list]
        assert any("invalid_json" in msg for msg in sent_messages)
