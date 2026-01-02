"""Comprehensive unit tests for system broadcaster service.

This module provides additional tests to achieve 95%+ coverage for
backend/services/system_broadcaster.py. Tests cover:

- WebSocket connect() method with initial status sending
- Pub/sub listener recovery with bounded retry attempts
- Message origin filtering (skip messages from self)
- Legacy message format handling
- Error handling in database query methods
- Async broadcaster functions (get_system_broadcaster_async, stop_system_broadcaster)
- reset_broadcaster_state for testing
- Thread-safe lock initialization (_get_broadcaster_lock)
- Deprecated _get_health_status method
- Error handling edge cases in _check_ai_health

Tests use pytest, pytest-asyncio, and unittest.mock to mock all external
dependencies (Redis, WebSocket, database sessions).
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.system_broadcaster import (
    PERFORMANCE_UPDATE_CHANNEL,
    SYSTEM_STATUS_CHANNEL,
    SystemBroadcaster,
    _get_broadcaster_lock,
    get_system_broadcaster,
    get_system_broadcaster_async,
    get_system_broadcaster_sync,
    reset_broadcaster_state,
    stop_system_broadcaster,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset global broadcaster state before and after each test."""
    reset_broadcaster_state()
    yield
    reset_broadcaster_state()


@pytest.fixture
def mock_redis_client() -> AsyncMock:
    """Create a mock Redis client."""
    mock = AsyncMock()
    mock.publish = AsyncMock()
    mock.subscribe_dedicated = AsyncMock()
    mock.health_check = AsyncMock()
    mock.get_queue_length = AsyncMock(return_value=0)
    return mock


@pytest.fixture
def mock_websocket() -> AsyncMock:
    """Create a mock WebSocket."""
    mock = AsyncMock()
    mock.accept = AsyncMock()
    mock.send_json = AsyncMock()
    mock.send_text = AsyncMock()
    return mock


@pytest.fixture
def mock_session() -> AsyncMock:
    """Create a mock database session."""
    mock = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalar_one.return_value = 0
    mock.execute.return_value = mock_result
    return mock


# =============================================================================
# WebSocket Connect Tests - Lines 152-161
# =============================================================================


class TestWebSocketConnect:
    """Tests for WebSocket connect() method."""

    @pytest.mark.asyncio
    async def test_connect_accepts_websocket(self, mock_websocket: AsyncMock) -> None:
        """Test that connect() accepts the WebSocket connection."""
        broadcaster = SystemBroadcaster()

        # Mock _get_system_status to avoid database calls
        with patch.object(
            broadcaster, "_get_system_status", return_value={"type": "system_status"}
        ):
            await broadcaster.connect(mock_websocket)

        mock_websocket.accept.assert_called_once()
        assert mock_websocket in broadcaster.connections

    @pytest.mark.asyncio
    async def test_connect_sends_initial_status(self, mock_websocket: AsyncMock) -> None:
        """Test that connect() sends initial status to new connection."""
        broadcaster = SystemBroadcaster()
        expected_status = {"type": "system_status", "data": {"test": "value"}}

        with patch.object(broadcaster, "_get_system_status", return_value=expected_status):
            await broadcaster.connect(mock_websocket)

        mock_websocket.send_json.assert_called_once_with(expected_status)

    @pytest.mark.asyncio
    async def test_connect_handles_initial_status_error(self, mock_websocket: AsyncMock) -> None:
        """Test that connect() handles errors when sending initial status."""
        broadcaster = SystemBroadcaster()

        # Make _get_system_status raise an error
        with patch.object(broadcaster, "_get_system_status", side_effect=Exception("Status error")):
            # Should not raise, should log the error and continue
            await broadcaster.connect(mock_websocket)

        # Connection should still be added
        mock_websocket.accept.assert_called_once()
        assert mock_websocket in broadcaster.connections

    @pytest.mark.asyncio
    async def test_connect_handles_send_json_error(self, mock_websocket: AsyncMock) -> None:
        """Test that connect() handles errors when send_json fails."""
        broadcaster = SystemBroadcaster()
        mock_websocket.send_json.side_effect = Exception("Send failed")

        with patch.object(
            broadcaster, "_get_system_status", return_value={"type": "system_status"}
        ):
            # Should not raise
            await broadcaster.connect(mock_websocket)

        # Connection should still be added
        assert mock_websocket in broadcaster.connections


# =============================================================================
# Pub/Sub Listener Recovery Tests - Lines 453, 457-462, 471
# =============================================================================


class TestListenerRecovery:
    """Tests for _attempt_listener_recovery() method."""

    @pytest.mark.asyncio
    async def test_recovery_increments_attempts(self, mock_redis_client: AsyncMock) -> None:
        """Test that recovery increments attempt counter."""
        broadcaster = SystemBroadcaster(redis_client=mock_redis_client)
        broadcaster._pubsub_listening = True
        broadcaster._recovery_attempts = 0

        # Make reset_pubsub_connection set a new pubsub
        mock_pubsub = AsyncMock()
        mock_redis_client.subscribe_dedicated.return_value = mock_pubsub

        with patch.object(broadcaster, "_reset_pubsub_connection") as mock_reset:

            async def mock_reset_impl():
                broadcaster._pubsub = mock_pubsub

            mock_reset.side_effect = mock_reset_impl

            await broadcaster._attempt_listener_recovery()

        assert broadcaster._recovery_attempts == 1

    @pytest.mark.asyncio
    async def test_recovery_stops_after_max_attempts(self, mock_redis_client: AsyncMock) -> None:
        """Test that recovery stops after MAX_RECOVERY_ATTEMPTS."""
        broadcaster = SystemBroadcaster(redis_client=mock_redis_client)
        broadcaster._pubsub_listening = True
        broadcaster._recovery_attempts = SystemBroadcaster.MAX_RECOVERY_ATTEMPTS

        await broadcaster._attempt_listener_recovery()

        # Should have stopped listening
        assert broadcaster._pubsub_listening is False
        # Should be at MAX + 1
        assert broadcaster._recovery_attempts == SystemBroadcaster.MAX_RECOVERY_ATTEMPTS + 1

    @pytest.mark.asyncio
    async def test_recovery_returns_early_if_not_listening(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """Test that recovery returns early if _pubsub_listening is False."""
        broadcaster = SystemBroadcaster(redis_client=mock_redis_client)
        broadcaster._pubsub_listening = False
        broadcaster._recovery_attempts = 0

        await broadcaster._attempt_listener_recovery()

        # Should not increment attempts
        assert broadcaster._recovery_attempts == 0

    @pytest.mark.asyncio
    async def test_recovery_returns_early_after_sleep_if_not_listening(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """Test that recovery returns early after sleep if listening flag changes."""
        broadcaster = SystemBroadcaster(redis_client=mock_redis_client)
        broadcaster._pubsub_listening = True
        broadcaster._recovery_attempts = 0

        async def stop_listening_during_sleep(delay):
            broadcaster._pubsub_listening = False

        with patch("asyncio.sleep", side_effect=stop_listening_during_sleep):
            await broadcaster._attempt_listener_recovery()

        # Should have incremented but not reset pubsub
        assert broadcaster._recovery_attempts == 1

    @pytest.mark.asyncio
    async def test_recovery_fails_when_reset_returns_none(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """Test that recovery handles reset_pubsub_connection returning None."""
        broadcaster = SystemBroadcaster(redis_client=mock_redis_client)
        broadcaster._pubsub_listening = True
        broadcaster._recovery_attempts = 0
        broadcaster._pubsub = None

        async def mock_reset():
            # Leave pubsub as None (failure case)
            broadcaster._pubsub = None

        with (
            patch.object(broadcaster, "_reset_pubsub_connection", side_effect=mock_reset),
            patch("asyncio.sleep", return_value=None),
        ):
            await broadcaster._attempt_listener_recovery()

        # Should have stopped listening due to failed reset
        assert broadcaster._pubsub_listening is False


# =============================================================================
# Message Origin Filtering Tests - Lines 422-423, 432
# =============================================================================


class TestMessageOriginFiltering:
    """Tests for message origin filtering in _listen_for_updates()."""

    @pytest.mark.asyncio
    async def test_skips_messages_from_self(self, mock_redis_client: AsyncMock) -> None:
        """Test that listener skips messages originating from this instance."""
        mock_pubsub = AsyncMock()
        broadcaster = SystemBroadcaster(redis_client=mock_redis_client)
        broadcaster._pubsub = mock_pubsub
        broadcaster._pubsub_listening = True

        # Create a message from the same instance
        message_from_self = {
            "data": {
                "_origin_instance": broadcaster._instance_id,
                "payload": {"type": "system_status", "test": "should_skip"},
            }
        }

        async def mock_listen(pubsub):
            yield message_from_self

        mock_redis_client.listen = mock_listen

        mock_ws = AsyncMock()
        broadcaster.connections.add(mock_ws)

        await broadcaster._listen_for_updates()

        # Should NOT have sent the message (skipped because from self)
        mock_ws.send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_forwards_messages_from_other_instances(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """Test that listener forwards messages from other instances."""
        mock_pubsub = AsyncMock()
        broadcaster = SystemBroadcaster(redis_client=mock_redis_client)
        broadcaster._pubsub = mock_pubsub
        broadcaster._pubsub_listening = True

        # Create a message from a different instance
        message_from_other = {
            "data": {
                "_origin_instance": "different-instance-id",
                "payload": {"type": "system_status", "test": "should_forward"},
            }
        }

        async def mock_listen(pubsub):
            yield message_from_other

        mock_redis_client.listen = mock_listen

        mock_ws = AsyncMock()
        broadcaster.connections.add(mock_ws)

        await broadcaster._listen_for_updates()

        # Should have sent the payload
        mock_ws.send_text.assert_called_once()
        sent_data = json.loads(mock_ws.send_text.call_args[0][0])
        assert sent_data["test"] == "should_forward"

    @pytest.mark.asyncio
    async def test_handles_legacy_format_without_wrapper(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """Test that listener handles legacy format (no wrapper)."""
        mock_pubsub = AsyncMock()
        broadcaster = SystemBroadcaster(redis_client=mock_redis_client)
        broadcaster._pubsub = mock_pubsub
        broadcaster._pubsub_listening = True

        # Legacy format - dict without _origin_instance
        legacy_message = {"data": {"type": "system_status", "legacy": "format"}}

        async def mock_listen(pubsub):
            yield legacy_message

        mock_redis_client.listen = mock_listen

        mock_ws = AsyncMock()
        broadcaster.connections.add(mock_ws)

        await broadcaster._listen_for_updates()

        # Should forward the legacy message
        mock_ws.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_non_dict_data(self, mock_redis_client: AsyncMock) -> None:
        """Test that listener handles non-dict data (legacy format)."""
        mock_pubsub = AsyncMock()
        broadcaster = SystemBroadcaster(redis_client=mock_redis_client)
        broadcaster._pubsub = mock_pubsub
        broadcaster._pubsub_listening = True

        # Non-dict data (string)
        string_message = {"data": '{"type": "system_status", "raw": "string"}'}

        async def mock_listen(pubsub):
            yield string_message

        mock_redis_client.listen = mock_listen

        mock_ws = AsyncMock()
        broadcaster.connections.add(mock_ws)

        await broadcaster._listen_for_updates()

        # Should forward the string data
        mock_ws.send_text.assert_called_once()


# =============================================================================
# Pub/Sub Close Error Handling - Lines 342-343, 368-369
# =============================================================================


class TestPubSubCloseErrorHandling:
    """Tests for pub/sub close error handling."""

    @pytest.mark.asyncio
    async def test_stop_pubsub_listener_handles_close_error(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """Test _stop_pubsub_listener handles close errors gracefully."""
        broadcaster = SystemBroadcaster(redis_client=mock_redis_client)
        mock_pubsub = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.close = AsyncMock(side_effect=Exception("Close failed"))

        broadcaster._pubsub = mock_pubsub
        broadcaster._pubsub_listening = True

        # Should not raise
        await broadcaster._stop_pubsub_listener()

        # Should still clean up
        assert broadcaster._pubsub is None
        assert broadcaster._pubsub_listening is False

    @pytest.mark.asyncio
    async def test_reset_pubsub_handles_close_error(self, mock_redis_client: AsyncMock) -> None:
        """Test _reset_pubsub_connection handles close errors gracefully."""
        new_pubsub = AsyncMock()
        mock_redis_client.subscribe_dedicated.return_value = new_pubsub

        broadcaster = SystemBroadcaster(redis_client=mock_redis_client)

        old_pubsub = AsyncMock()
        old_pubsub.unsubscribe = AsyncMock()
        old_pubsub.close = AsyncMock(side_effect=Exception("Close error during reset"))
        broadcaster._pubsub = old_pubsub

        # Should not raise
        await broadcaster._reset_pubsub_connection()

        # Should have new pubsub
        assert broadcaster._pubsub is new_pubsub


# =============================================================================
# Database Query Error Handling - Lines 584-586, 640-642, 657
# =============================================================================


class TestDatabaseQueryErrorHandling:
    """Tests for database query error handling."""

    @pytest.mark.asyncio
    async def test_get_latest_gpu_stats_with_session_handles_error(
        self, mock_session: AsyncMock
    ) -> None:
        """Test _get_latest_gpu_stats_with_session handles query errors."""
        broadcaster = SystemBroadcaster()
        mock_session.execute.side_effect = Exception("Database query error")

        result = await broadcaster._get_latest_gpu_stats_with_session(mock_session)

        # Should return null values
        assert result["utilization"] is None
        assert result["memory_used"] is None
        assert result["memory_total"] is None
        assert result["temperature"] is None
        assert result["inference_fps"] is None

    @pytest.mark.asyncio
    async def test_get_camera_stats_with_session_handles_error(
        self, mock_session: AsyncMock
    ) -> None:
        """Test _get_camera_stats_with_session handles query errors."""
        broadcaster = SystemBroadcaster()
        mock_session.execute.side_effect = Exception("Database query error")

        result = await broadcaster._get_camera_stats_with_session(mock_session)

        # Should return zeros
        assert result["active"] == 0
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_get_camera_stats_deprecated_handles_error(self) -> None:
        """Test deprecated _get_camera_stats handles errors."""
        broadcaster = SystemBroadcaster()

        @asynccontextmanager
        async def failing_session():
            raise Exception("Session creation failed")
            yield  # Never reached, but needed for asynccontextmanager

        with patch("backend.services.system_broadcaster.get_session", failing_session):
            result = await broadcaster._get_camera_stats()

        # Should return zeros
        assert result["active"] == 0
        assert result["total"] == 0


# =============================================================================
# AI Health Check Error Handling - Lines 747-748
# =============================================================================


class TestAIHealthCheckErrorHandling:
    """Tests for _check_ai_health error handling."""

    @pytest.mark.asyncio
    async def test_check_ai_health_handles_gather_error(self) -> None:
        """Test _check_ai_health handles asyncio.gather errors."""
        broadcaster = SystemBroadcaster()

        with patch("backend.services.system_broadcaster.asyncio.gather") as mock_gather:
            mock_gather.side_effect = Exception("Gather failed")

            result = await broadcaster._check_ai_health()

        # Should return False for both (error was caught)
        assert result["rtdetr"] is False
        assert result["nemotron"] is False
        assert result["all_healthy"] is False
        assert result["any_healthy"] is False


# =============================================================================
# Deprecated _get_health_status Method - Lines 766-782
# =============================================================================


class TestDeprecatedGetHealthStatus:
    """Tests for deprecated _get_health_status method."""

    @pytest.mark.asyncio
    async def test_get_health_status_healthy(self, mock_redis_client: AsyncMock) -> None:
        """Test _get_health_status returns healthy when all systems ok."""
        broadcaster = SystemBroadcaster(redis_client=mock_redis_client)
        mock_redis_client.health_check.return_value = True

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 0
        mock_session.execute.return_value = mock_result

        @asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with patch("backend.services.system_broadcaster.get_session", mock_get_session):
            result = await broadcaster._get_health_status()

        assert result == "healthy"

    @pytest.mark.asyncio
    async def test_get_health_status_degraded(self, mock_redis_client: AsyncMock) -> None:
        """Test _get_health_status returns degraded when Redis unhealthy."""
        broadcaster = SystemBroadcaster(redis_client=mock_redis_client)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 0
        mock_session.execute.return_value = mock_result

        @asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with (
            patch("backend.services.system_broadcaster.get_session", mock_get_session),
            patch.object(broadcaster, "_check_redis_health", return_value=False),
        ):
            result = await broadcaster._get_health_status()

        assert result == "degraded"

    @pytest.mark.asyncio
    async def test_get_health_status_unhealthy(self) -> None:
        """Test _get_health_status returns unhealthy when database fails."""
        broadcaster = SystemBroadcaster()

        @asynccontextmanager
        async def failing_session():
            raise Exception("Database unavailable")
            yield

        with patch("backend.services.system_broadcaster.get_session", failing_session):
            result = await broadcaster._get_health_status()

        assert result == "unhealthy"


# =============================================================================
# Thread-Safe Lock Initialization - Lines 874-879
# =============================================================================


class TestBroadcasterLock:
    """Tests for _get_broadcaster_lock thread-safe initialization."""

    def test_get_broadcaster_lock_creates_lock(self) -> None:
        """Test that _get_broadcaster_lock creates an asyncio Lock."""
        reset_broadcaster_state()  # Ensure clean state

        lock = _get_broadcaster_lock()

        assert lock is not None
        assert isinstance(lock, asyncio.Lock)

    def test_get_broadcaster_lock_returns_same_lock(self) -> None:
        """Test that _get_broadcaster_lock returns the same lock on subsequent calls."""
        reset_broadcaster_state()

        lock1 = _get_broadcaster_lock()
        lock2 = _get_broadcaster_lock()

        assert lock1 is lock2


# =============================================================================
# Async Broadcaster Functions - Lines 941-963, 973-978
# =============================================================================


class TestAsyncBroadcasterFunctions:
    """Tests for async broadcaster management functions."""

    @pytest.mark.asyncio
    async def test_get_system_broadcaster_async_creates_and_starts(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """Test get_system_broadcaster_async creates and starts broadcaster."""
        reset_broadcaster_state()

        mock_pubsub = AsyncMock()
        mock_redis_client.subscribe_dedicated.return_value = mock_pubsub

        # Mock listen to avoid actual async iteration
        async def empty_listen(pubsub):
            for _ in []:
                yield

        mock_redis_client.listen = empty_listen

        broadcaster = await get_system_broadcaster_async(
            redis_client=mock_redis_client, interval=1.0
        )

        assert broadcaster is not None
        assert broadcaster._running is True

        # Cleanup
        await broadcaster.stop_broadcasting()

    @pytest.mark.asyncio
    async def test_get_system_broadcaster_async_returns_existing_running(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """Test get_system_broadcaster_async returns existing running broadcaster."""
        reset_broadcaster_state()

        mock_pubsub = AsyncMock()
        mock_redis_client.subscribe_dedicated.return_value = mock_pubsub

        async def empty_listen(pubsub):
            for _ in []:
                yield

        mock_redis_client.listen = empty_listen

        # First call creates and starts
        broadcaster1 = await get_system_broadcaster_async(
            redis_client=mock_redis_client, interval=1.0
        )

        # Second call should return same instance (fast path)
        broadcaster2 = await get_system_broadcaster_async(
            redis_client=mock_redis_client, interval=1.0
        )

        assert broadcaster1 is broadcaster2

        # Cleanup
        await broadcaster1.stop_broadcasting()

    @pytest.mark.asyncio
    async def test_get_system_broadcaster_async_updates_redis_client(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """Test get_system_broadcaster_async updates Redis client on existing."""
        reset_broadcaster_state()

        mock_pubsub = AsyncMock()
        mock_redis_client.subscribe_dedicated.return_value = mock_pubsub

        async def empty_listen(pubsub):
            for _ in []:
                yield

        mock_redis_client.listen = empty_listen

        # Create without Redis
        broadcaster1 = await get_system_broadcaster_async(interval=1.0)

        # Update with Redis (fast path - running)
        new_redis = AsyncMock()
        new_redis.subscribe_dedicated.return_value = mock_pubsub
        new_redis.listen = empty_listen
        broadcaster2 = await get_system_broadcaster_async(redis_client=new_redis, interval=1.0)

        assert broadcaster1 is broadcaster2
        assert broadcaster1._redis_client is new_redis

        # Cleanup
        await broadcaster1.stop_broadcasting()

    @pytest.mark.asyncio
    async def test_stop_system_broadcaster_stops_and_clears(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """Test stop_system_broadcaster stops and clears global instance."""
        reset_broadcaster_state()

        mock_pubsub = AsyncMock()
        mock_redis_client.subscribe_dedicated.return_value = mock_pubsub

        async def empty_listen(pubsub):
            for _ in []:
                yield

        mock_redis_client.listen = empty_listen

        # Create broadcaster
        broadcaster = await get_system_broadcaster_async(
            redis_client=mock_redis_client, interval=1.0
        )

        assert broadcaster._running is True

        # Stop it
        await stop_system_broadcaster()

        # Global state should be cleared
        import backend.services.system_broadcaster as module

        assert module._system_broadcaster is None

    @pytest.mark.asyncio
    async def test_stop_system_broadcaster_noop_when_none(self) -> None:
        """Test stop_system_broadcaster is a no-op when no broadcaster exists."""
        reset_broadcaster_state()

        # Should not raise
        await stop_system_broadcaster()


# =============================================================================
# Reset Broadcaster State - Lines 991-992
# =============================================================================


class TestResetBroadcasterState:
    """Tests for reset_broadcaster_state function."""

    def test_reset_broadcaster_state_clears_singleton(self) -> None:
        """Test reset_broadcaster_state clears the global singleton."""
        # Create a broadcaster
        broadcaster = get_system_broadcaster()
        assert broadcaster is not None

        # Reset
        reset_broadcaster_state()

        # Get a new one - should be different instance
        new_broadcaster = get_system_broadcaster()
        assert new_broadcaster is not broadcaster

    def test_reset_broadcaster_state_clears_lock(self) -> None:
        """Test reset_broadcaster_state clears the asyncio lock."""
        # Get a lock
        _get_broadcaster_lock()

        # Reset
        reset_broadcaster_state()

        # Get lock again - should work (creates new one)
        lock = _get_broadcaster_lock()
        assert lock is not None


# =============================================================================
# Sync Alias Test
# =============================================================================


class TestSyncAlias:
    """Test for get_system_broadcaster_sync alias."""

    def test_sync_alias_same_as_get_system_broadcaster(self) -> None:
        """Test that get_system_broadcaster_sync is the same as get_system_broadcaster."""
        assert get_system_broadcaster_sync is get_system_broadcaster


# =============================================================================
# Additional Edge Cases
# =============================================================================


class TestDeprecatedCameraStats:
    """Tests for deprecated _get_camera_stats method (success path)."""

    @pytest.mark.asyncio
    async def test_get_camera_stats_deprecated_success(self) -> None:
        """Test deprecated _get_camera_stats returns valid stats when DB works."""
        broadcaster = SystemBroadcaster()

        mock_session = AsyncMock()
        call_count = 0

        def mock_execute(*args):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                mock_result.scalar_one.return_value = 10  # total
            else:
                mock_result.scalar_one.return_value = 7  # active
            return mock_result

        mock_session.execute.side_effect = mock_execute

        @asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with patch("backend.services.system_broadcaster.get_session", mock_get_session):
            result = await broadcaster._get_camera_stats()

        # Should return the stats from the session method
        assert result["total"] == 10
        assert result["active"] == 7


class TestAsyncBroadcasterSlowPath:
    """Tests for get_system_broadcaster_async slow path (updating existing stopped broadcaster)."""

    @pytest.mark.asyncio
    async def test_get_system_broadcaster_async_slow_path_update_redis(self) -> None:
        """Test get_system_broadcaster_async slow path updates Redis on existing broadcaster."""
        reset_broadcaster_state()

        # Create broadcaster via sync function (without starting)
        broadcaster = get_system_broadcaster()
        assert broadcaster._running is False

        # Now call async with new Redis - this should hit the slow path
        # where broadcaster exists but isn't running
        mock_redis = AsyncMock()
        mock_pubsub = AsyncMock()
        mock_redis.subscribe_dedicated.return_value = mock_pubsub

        async def empty_listen(pubsub):
            for _ in []:
                yield

        mock_redis.listen = empty_listen

        result = await get_system_broadcaster_async(redis_client=mock_redis, interval=1.0)

        # Should be the same broadcaster
        assert result is broadcaster
        # Should have updated Redis client (slow path line 955-956)
        assert result._redis_client is mock_redis
        # Should be running now
        assert result._running is True

        # Cleanup
        await result.stop_broadcasting()


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_listen_resets_recovery_counter_on_success(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """Test that successful message processing resets recovery counter."""
        mock_pubsub = AsyncMock()
        broadcaster = SystemBroadcaster(redis_client=mock_redis_client)
        broadcaster._pubsub = mock_pubsub
        broadcaster._pubsub_listening = True
        broadcaster._recovery_attempts = 3  # Previous recovery attempts

        messages = [{"data": {"type": "test"}}]

        async def mock_listen(pubsub):
            for msg in messages:
                yield msg

        mock_redis_client.listen = mock_listen

        mock_ws = AsyncMock()
        broadcaster.connections.add(mock_ws)

        await broadcaster._listen_for_updates()

        # Recovery attempts should be reset to 0
        assert broadcaster._recovery_attempts == 0

    @pytest.mark.asyncio
    async def test_broadcast_loop_with_connections(self, mock_redis_client: AsyncMock) -> None:
        """Test broadcast loop calls broadcast methods when connections exist."""
        broadcaster = SystemBroadcaster(redis_client=mock_redis_client)
        broadcaster._running = True

        mock_ws = AsyncMock()
        broadcaster.connections.add(mock_ws)

        broadcast_status_called = False
        broadcast_performance_called = False
        loop_count = 0

        async def mock_get_status():
            return {"type": "system_status", "data": {}}

        async def mock_broadcast_status(data):
            nonlocal broadcast_status_called
            broadcast_status_called = True

        async def mock_broadcast_performance():
            nonlocal broadcast_performance_called
            broadcast_performance_called = True

        original_sleep = asyncio.sleep

        async def counting_sleep(delay):
            nonlocal loop_count
            loop_count += 1
            if loop_count >= 1:
                broadcaster._running = False
            await original_sleep(0.01)

        with (
            patch.object(broadcaster, "_get_system_status", side_effect=mock_get_status),
            patch.object(broadcaster, "broadcast_status", side_effect=mock_broadcast_status),
            patch.object(
                broadcaster, "broadcast_performance", side_effect=mock_broadcast_performance
            ),
            patch("asyncio.sleep", side_effect=counting_sleep),
        ):
            await broadcaster._broadcast_loop(0.1)

        assert broadcast_status_called is True
        assert broadcast_performance_called is True

    @pytest.mark.asyncio
    async def test_get_gpu_stats_with_valid_data(self, mock_session: AsyncMock) -> None:
        """Test _get_latest_gpu_stats_with_session returns valid GPU stats."""
        broadcaster = SystemBroadcaster()

        mock_gpu_stat = MagicMock()
        mock_gpu_stat.gpu_utilization = 85.5
        mock_gpu_stat.memory_used = 12000
        mock_gpu_stat.memory_total = 24576
        mock_gpu_stat.temperature = 72.0
        mock_gpu_stat.inference_fps = 25.0

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_gpu_stat
        mock_session.execute.return_value = mock_result

        result = await broadcaster._get_latest_gpu_stats_with_session(mock_session)

        assert result["utilization"] == 85.5
        assert result["memory_used"] == 12000
        assert result["memory_total"] == 24576
        assert result["temperature"] == 72.0
        assert result["inference_fps"] == 25.0

    @pytest.mark.asyncio
    async def test_pubsub_start_listener_no_redis(self) -> None:
        """Test _start_pubsub_listener returns early when Redis unavailable."""
        broadcaster = SystemBroadcaster()  # No Redis

        await broadcaster._start_pubsub_listener()

        # Should not be listening
        assert broadcaster._pubsub_listening is False
        assert broadcaster._pubsub is None

    @pytest.mark.asyncio
    async def test_start_broadcasting_starts_both_loops(self, mock_redis_client: AsyncMock) -> None:
        """Test start_broadcasting starts both broadcast and pubsub listener."""
        mock_pubsub = AsyncMock()
        mock_redis_client.subscribe_dedicated.return_value = mock_pubsub

        async def empty_listen(pubsub):
            for _ in []:
                yield

        mock_redis_client.listen = empty_listen

        broadcaster = SystemBroadcaster(redis_client=mock_redis_client)

        await broadcaster.start_broadcasting(interval=1.0)

        assert broadcaster._running is True
        assert broadcaster._broadcast_task is not None
        assert broadcaster._pubsub_listening is True

        # Cleanup
        await broadcaster.stop_broadcasting()

    @pytest.mark.asyncio
    async def test_instance_id_is_unique(self) -> None:
        """Test that each broadcaster instance gets a unique ID."""
        broadcaster1 = SystemBroadcaster()
        broadcaster2 = SystemBroadcaster()

        assert broadcaster1._instance_id != broadcaster2._instance_id

    @pytest.mark.asyncio
    async def test_max_recovery_attempts_constant(self) -> None:
        """Test MAX_RECOVERY_ATTEMPTS is correctly set."""
        assert SystemBroadcaster.MAX_RECOVERY_ATTEMPTS == 5

    @pytest.mark.asyncio
    async def test_channels_are_defined(self) -> None:
        """Test that pub/sub channels are correctly defined."""
        assert SYSTEM_STATUS_CHANNEL == "system_status"
        assert PERFORMANCE_UPDATE_CHANNEL == "performance_update"
