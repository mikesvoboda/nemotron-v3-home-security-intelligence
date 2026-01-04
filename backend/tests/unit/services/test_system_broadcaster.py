"""Unit tests for system broadcaster service.

These tests verify behavior with mocked dependencies (Redis, WebSocket)
and don't require a real database connection.
"""

import asyncio
import contextlib
import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.system_broadcaster import SystemBroadcaster, get_system_broadcaster


@pytest.mark.asyncio
async def test_system_broadcaster_init():
    """Test SystemBroadcaster initialization."""
    broadcaster = SystemBroadcaster()

    assert broadcaster.connections == set()
    assert broadcaster._broadcast_task is None
    assert broadcaster._running is False
    assert broadcaster._redis_client is None
    assert broadcaster._redis_getter is None


@pytest.mark.asyncio
async def test_system_broadcaster_init_with_redis_client():
    """Test SystemBroadcaster initialization with Redis client."""
    mock_redis = AsyncMock()
    broadcaster = SystemBroadcaster(redis_client=mock_redis)

    assert broadcaster._redis_client is mock_redis
    assert broadcaster._redis_getter is None


@pytest.mark.asyncio
async def test_system_broadcaster_init_with_redis_getter():
    """Test SystemBroadcaster initialization with Redis getter."""
    mock_redis = AsyncMock()
    mock_getter = MagicMock(return_value=mock_redis)
    broadcaster = SystemBroadcaster(redis_getter=mock_getter)

    assert broadcaster._redis_client is None
    assert broadcaster._redis_getter is mock_getter
    # Calling _get_redis should use the getter
    assert broadcaster._get_redis() is mock_redis
    mock_getter.assert_called_once()


@pytest.mark.asyncio
async def test_system_broadcaster_get_redis_prefers_client():
    """Test that _get_redis prefers direct client over getter."""
    mock_client = AsyncMock()
    mock_getter_redis = AsyncMock()
    mock_getter = MagicMock(return_value=mock_getter_redis)

    broadcaster = SystemBroadcaster(redis_client=mock_client, redis_getter=mock_getter)

    # Should return the direct client, not call the getter
    assert broadcaster._get_redis() is mock_client
    mock_getter.assert_not_called()


@pytest.mark.asyncio
async def test_system_broadcaster_get_redis_returns_none():
    """Test that _get_redis returns None when no Redis is configured."""
    broadcaster = SystemBroadcaster()
    assert broadcaster._get_redis() is None


@pytest.mark.asyncio
async def test_system_broadcaster_set_redis_client():
    """Test setting Redis client after initialization."""
    broadcaster = SystemBroadcaster()
    assert broadcaster._redis_client is None

    mock_redis = AsyncMock()
    broadcaster.set_redis_client(mock_redis)
    assert broadcaster._redis_client is mock_redis
    assert broadcaster._get_redis() is mock_redis


@pytest.mark.asyncio
async def test_system_broadcaster_disconnect():
    """Test removing a WebSocket connection."""
    broadcaster = SystemBroadcaster()
    mock_websocket = AsyncMock()
    broadcaster.connections.add(mock_websocket)

    await broadcaster.disconnect(mock_websocket)

    assert mock_websocket not in broadcaster.connections
    assert len(broadcaster.connections) == 0


@pytest.mark.asyncio
async def test_system_broadcaster_broadcast_status():
    """Test broadcasting status to all connections.

    When Redis is not available, broadcast_status falls back to _send_to_local_clients
    which uses send_text with JSON-serialized data.
    """
    broadcaster = SystemBroadcaster()
    mock_ws1 = AsyncMock()
    mock_ws2 = AsyncMock()
    broadcaster.connections.add(mock_ws1)
    broadcaster.connections.add(mock_ws2)

    status_data = {"type": "system_status", "data": {"test": "value"}}
    await broadcaster.broadcast_status(status_data)

    # Both connections should receive the message via send_text (JSON serialized)
    expected_message = json.dumps(status_data)
    mock_ws1.send_text.assert_called_once_with(expected_message)
    mock_ws2.send_text.assert_called_once_with(expected_message)


@pytest.mark.asyncio
async def test_system_broadcaster_broadcast_status_removes_failed():
    """Test that failed connections are removed during broadcast.

    When Redis is not available, broadcast_status falls back to _send_to_local_clients
    which uses send_text. Failed connections should be removed.
    """
    broadcaster = SystemBroadcaster()
    mock_ws_good = AsyncMock()
    mock_ws_bad = AsyncMock()
    mock_ws_bad.send_text.side_effect = Exception("Connection failed")

    broadcaster.connections.add(mock_ws_good)
    broadcaster.connections.add(mock_ws_bad)

    status_data = {"type": "system_status", "data": {"test": "value"}}
    await broadcaster.broadcast_status(status_data)

    # Good connection should still be in set
    assert mock_ws_good in broadcaster.connections
    # Bad connection should be removed
    assert mock_ws_bad not in broadcaster.connections


@pytest.mark.asyncio
async def test_system_broadcaster_broadcast_status_empty_connections():
    """Test broadcasting with no connections doesn't error."""
    broadcaster = SystemBroadcaster()
    status_data = {"type": "system_status", "data": {"test": "value"}}

    # Should not raise an error
    await broadcaster.broadcast_status(status_data)


@pytest.mark.asyncio
async def test_system_broadcaster_get_queue_stats():
    """Test getting queue statistics from Redis."""
    # Mock Redis client
    mock_redis = AsyncMock()
    mock_redis.get_queue_length.side_effect = lambda queue: {
        "detection_queue": 5,
        "analysis_queue": 2,
    }.get(queue, 0)

    # Use dependency injection
    broadcaster = SystemBroadcaster(redis_client=mock_redis)
    queue_stats = await broadcaster._get_queue_stats()

    # Should return correct counts
    assert queue_stats["pending"] == 5
    assert queue_stats["processing"] == 2


@pytest.mark.asyncio
async def test_system_broadcaster_get_queue_stats_redis_unavailable():
    """Test getting queue stats when Redis is unavailable."""
    # No Redis client provided
    broadcaster = SystemBroadcaster()
    queue_stats = await broadcaster._get_queue_stats()

    # Should return zeros
    assert queue_stats["pending"] == 0
    assert queue_stats["processing"] == 0


@pytest.mark.asyncio
async def test_system_broadcaster_get_queue_stats_redis_error():
    """Test getting queue stats when Redis raises an error."""
    # Mock Redis to raise an exception
    mock_redis = AsyncMock()
    mock_redis.get_queue_length.side_effect = Exception("Redis error")

    # Use dependency injection
    broadcaster = SystemBroadcaster(redis_client=mock_redis)
    queue_stats = await broadcaster._get_queue_stats()

    # Should return zeros on error
    assert queue_stats["pending"] == 0
    assert queue_stats["processing"] == 0


@pytest.mark.asyncio
async def test_system_broadcaster_start_broadcasting():
    """Test starting periodic broadcasting."""
    broadcaster = SystemBroadcaster()

    # Mock broadcast loop to avoid actual sleeping
    with patch.object(broadcaster, "_broadcast_loop"):
        await broadcaster.start_broadcasting(interval=1.0)

    assert broadcaster._running is True
    assert broadcaster._broadcast_task is not None


@pytest.mark.asyncio
async def test_system_broadcaster_stop_broadcasting():
    """Test stopping periodic broadcasting."""
    broadcaster = SystemBroadcaster()
    broadcaster._running = True
    broadcaster._broadcast_task = asyncio.create_task(
        asyncio.sleep(10)  # cancelled in stop_broadcasting
    )

    await broadcaster.stop_broadcasting()

    assert broadcaster._running is False
    assert broadcaster._broadcast_task is None


@pytest.mark.asyncio
async def test_system_broadcaster_start_broadcasting_already_running():
    """Test that starting broadcasting when already running doesn't create duplicate tasks."""
    broadcaster = SystemBroadcaster()
    broadcaster._running = True

    await broadcaster.start_broadcasting()

    # Should log warning but not error


@pytest.mark.asyncio
async def test_get_system_broadcaster_singleton():
    """Test that get_system_broadcaster returns singleton instance."""
    # Clear global instance first
    import backend.services.system_broadcaster

    backend.services.system_broadcaster._system_broadcaster = None

    broadcaster1 = get_system_broadcaster()
    broadcaster2 = get_system_broadcaster()

    # Should be the same instance
    assert broadcaster1 is broadcaster2

    # Cleanup
    backend.services.system_broadcaster._system_broadcaster = None


@pytest.mark.asyncio
async def test_get_system_broadcaster_with_redis_client():
    """Test that get_system_broadcaster accepts Redis client."""
    # Clear global instance first
    import backend.services.system_broadcaster

    backend.services.system_broadcaster._system_broadcaster = None

    mock_redis = AsyncMock()
    broadcaster = get_system_broadcaster(redis_client=mock_redis)

    assert broadcaster._redis_client is mock_redis
    assert broadcaster._get_redis() is mock_redis

    # Cleanup
    backend.services.system_broadcaster._system_broadcaster = None


@pytest.mark.asyncio
async def test_get_system_broadcaster_updates_redis_client():
    """Test that subsequent calls to get_system_broadcaster can update Redis client."""
    # Clear global instance first
    import backend.services.system_broadcaster

    backend.services.system_broadcaster._system_broadcaster = None

    # First call without Redis
    broadcaster1 = get_system_broadcaster()
    assert broadcaster1._redis_client is None

    # Second call with Redis - should update existing singleton
    mock_redis = AsyncMock()
    broadcaster2 = get_system_broadcaster(redis_client=mock_redis)

    assert broadcaster1 is broadcaster2  # Same singleton
    assert broadcaster1._redis_client is mock_redis

    # Cleanup
    backend.services.system_broadcaster._system_broadcaster = None


@pytest.mark.asyncio
async def test_get_system_broadcaster_with_redis_getter():
    """Test that get_system_broadcaster accepts Redis getter."""
    # Clear global instance first
    import backend.services.system_broadcaster

    backend.services.system_broadcaster._system_broadcaster = None

    mock_redis = AsyncMock()
    mock_getter = MagicMock(return_value=mock_redis)
    broadcaster = get_system_broadcaster(redis_getter=mock_getter)

    assert broadcaster._redis_getter is mock_getter
    assert broadcaster._get_redis() is mock_redis

    # Cleanup
    backend.services.system_broadcaster._system_broadcaster = None


@pytest.mark.asyncio
async def test_system_broadcaster_get_latest_gpu_stats_error():
    """Test GPU stats getter handles database errors gracefully."""
    broadcaster = SystemBroadcaster()

    # Mock get_session to raise error
    with patch("backend.services.system_broadcaster.get_session") as mock_session:
        mock_session.side_effect = Exception("Database error")

        gpu_stats = await broadcaster._get_latest_gpu_stats()

    # Should return null values on error
    assert gpu_stats["utilization"] is None
    assert gpu_stats["memory_used"] is None
    assert gpu_stats["memory_total"] is None


@pytest.mark.asyncio
async def test_system_broadcaster_get_camera_stats_error():
    """Test camera stats getter handles database errors gracefully."""
    broadcaster = SystemBroadcaster()

    # Mock get_session to raise error
    with patch("backend.services.system_broadcaster.get_session") as mock_session:
        mock_session.side_effect = Exception("Database error")

        camera_stats = await broadcaster._get_camera_stats()

    # Should return zeros on error
    assert camera_stats["active"] == 0
    assert camera_stats["total"] == 0


@pytest.mark.asyncio
async def test_system_broadcaster_reset_pubsub_connection():
    """Test resetting pub/sub connection for error recovery."""
    mock_redis = AsyncMock()
    mock_pubsub = AsyncMock()
    mock_redis.subscribe_dedicated.return_value = mock_pubsub

    broadcaster = SystemBroadcaster(redis_client=mock_redis)
    old_pubsub = AsyncMock()  # Simulate existing pubsub
    broadcaster._pubsub = old_pubsub

    await broadcaster._reset_pubsub_connection()

    # Should unsubscribe and close old pubsub, then create new subscription
    old_pubsub.unsubscribe.assert_called_once()
    old_pubsub.close.assert_called_once()
    mock_redis.subscribe_dedicated.assert_called_once()
    assert broadcaster._pubsub is mock_pubsub


@pytest.mark.asyncio
async def test_system_broadcaster_reset_pubsub_connection_no_redis():
    """Test reset_pubsub_connection when Redis is not available."""
    broadcaster = SystemBroadcaster()
    broadcaster._pubsub = AsyncMock()

    await broadcaster._reset_pubsub_connection()

    # Should clear pubsub when Redis unavailable
    assert broadcaster._pubsub is None


@pytest.mark.asyncio
async def test_system_broadcaster_reset_pubsub_handles_unsubscribe_error():
    """Test reset_pubsub_connection handles unsubscribe errors gracefully."""
    mock_redis = AsyncMock()
    mock_pubsub = AsyncMock()
    mock_redis.subscribe_dedicated.return_value = mock_pubsub

    old_pubsub = AsyncMock()
    old_pubsub.unsubscribe.side_effect = Exception("Unsubscribe failed")

    broadcaster = SystemBroadcaster(redis_client=mock_redis)
    broadcaster._pubsub = old_pubsub

    # Should not raise, should continue to create new subscription
    await broadcaster._reset_pubsub_connection()

    assert broadcaster._pubsub is mock_pubsub
    mock_redis.subscribe_dedicated.assert_called_once()


@pytest.mark.asyncio
async def test_system_broadcaster_reset_pubsub_handles_subscribe_error():
    """Test reset_pubsub_connection handles subscribe errors gracefully."""
    mock_redis = AsyncMock()
    mock_redis.subscribe_dedicated.side_effect = Exception("Subscribe failed")

    broadcaster = SystemBroadcaster(redis_client=mock_redis)
    broadcaster._pubsub = AsyncMock()

    await broadcaster._reset_pubsub_connection()

    # Should set pubsub to None on failure
    assert broadcaster._pubsub is None


@pytest.mark.asyncio
async def test_system_broadcaster_listen_restarts_with_fresh_connection():
    """Test that listener restarts with fresh pub/sub connection after error."""
    mock_redis = AsyncMock()
    mock_pubsub = AsyncMock()

    # First call to listen raises error, subsequent calls work
    call_count = 0

    async def mock_listen(pubsub):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("readuntil() called while another coroutine is waiting")
        # Return empty generator for subsequent calls
        for _ in []:
            yield

    mock_redis.listen = mock_listen
    mock_redis.subscribe.return_value = mock_pubsub

    broadcaster = SystemBroadcaster(redis_client=mock_redis)
    broadcaster._pubsub = mock_pubsub
    broadcaster._pubsub_listening = True

    # Mock _reset_pubsub_connection to verify it's called
    with patch.object(broadcaster, "_reset_pubsub_connection") as mock_reset:
        # Make reset set a new pubsub
        async def set_pubsub():
            broadcaster._pubsub = mock_pubsub

        mock_reset.side_effect = set_pubsub

        # Run listener - should encounter error, try to reset, and restart
        await broadcaster._listen_for_updates()

        # Wait for error handler sleep - mocked, short timeout
        await asyncio.sleep(0.1)  # mocked

        # Should have called reset
        mock_reset.assert_called_once()


@pytest.mark.asyncio
async def test_system_broadcaster_broadcast_status_via_redis():
    """Test broadcast_status publishes via Redis when available."""
    mock_redis = AsyncMock()
    broadcaster = SystemBroadcaster(redis_client=mock_redis)

    status_data = {"type": "system_status", "data": {"test": "value"}}
    await broadcaster.broadcast_status(status_data)

    # Should publish via Redis with instance origin wrapper
    mock_redis.publish.assert_called_once()
    call_args = mock_redis.publish.call_args
    assert call_args[0][0] == "system_status"  # Channel name
    published_message = call_args[0][1]
    assert "_origin_instance" in published_message  # Has instance ID
    assert published_message["payload"] == status_data  # Payload is the original data


@pytest.mark.asyncio
async def test_system_broadcaster_broadcast_status_redis_publish_failure():
    """Test broadcast_status falls back to direct when Redis publish fails."""
    mock_redis = AsyncMock()
    mock_redis.publish.side_effect = Exception("Redis publish failed")

    broadcaster = SystemBroadcaster(redis_client=mock_redis)
    mock_ws = AsyncMock()
    broadcaster.connections.add(mock_ws)

    status_data = {"type": "system_status", "data": {"test": "value"}}
    await broadcaster.broadcast_status(status_data)

    # Should fall back to direct send
    expected_message = json.dumps(status_data)
    mock_ws.send_text.assert_called_once_with(expected_message)


@pytest.mark.asyncio
async def test_system_broadcaster_start_pubsub_listener_already_running():
    """Test _start_pubsub_listener when already running."""
    mock_redis = AsyncMock()
    broadcaster = SystemBroadcaster(redis_client=mock_redis)
    broadcaster._pubsub_listening = True

    # Should return early without creating new subscription
    await broadcaster._start_pubsub_listener()

    # subscribe_dedicated should not be called since listener is already running
    mock_redis.subscribe_dedicated.assert_not_called()


@pytest.mark.asyncio
async def test_system_broadcaster_start_pubsub_listener_subscribe_error():
    """Test _start_pubsub_listener handles subscription errors."""
    mock_redis = AsyncMock()
    mock_redis.subscribe_dedicated.side_effect = Exception("Subscription failed")

    broadcaster = SystemBroadcaster(redis_client=mock_redis)

    # Should not raise, should handle error
    await broadcaster._start_pubsub_listener()

    # Should not be listening
    assert broadcaster._pubsub_listening is False


@pytest.mark.asyncio
async def test_system_broadcaster_start_pubsub_listener_success():
    """Test _start_pubsub_listener successful subscription."""
    mock_redis = AsyncMock()
    mock_pubsub = AsyncMock()
    mock_redis.subscribe_dedicated.return_value = mock_pubsub

    broadcaster = SystemBroadcaster(redis_client=mock_redis)

    # Mock listen to avoid actual async iteration - empty generator pattern
    async def empty_listen(pubsub):
        for _ in []:
            yield

    mock_redis.listen = empty_listen

    await broadcaster._start_pubsub_listener()

    # Should be listening with pubsub set
    assert broadcaster._pubsub_listening is True
    assert broadcaster._pubsub is mock_pubsub
    assert broadcaster._listener_task is not None

    # Cleanup
    broadcaster._pubsub_listening = False
    if broadcaster._listener_task:
        broadcaster._listener_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await broadcaster._listener_task


@pytest.mark.asyncio
async def test_system_broadcaster_stop_pubsub_listener_with_task():
    """Test _stop_pubsub_listener cancels listener task and closes dedicated pubsub."""
    mock_redis = AsyncMock()
    broadcaster = SystemBroadcaster(redis_client=mock_redis)

    # Create a long-running task that will be cancelled
    async def long_running():
        await asyncio.sleep(100)  # cancelled

    broadcaster._listener_task = asyncio.create_task(long_running())
    mock_pubsub = AsyncMock()
    broadcaster._pubsub = mock_pubsub
    broadcaster._pubsub_listening = True

    await broadcaster._stop_pubsub_listener()

    # Should be stopped
    assert broadcaster._pubsub_listening is False
    assert broadcaster._listener_task is None
    assert broadcaster._pubsub is None
    # Should unsubscribe and close the dedicated pubsub connection
    mock_pubsub.unsubscribe.assert_called_once()
    mock_pubsub.close.assert_called_once()


@pytest.mark.asyncio
async def test_system_broadcaster_stop_pubsub_listener_unsubscribe_error():
    """Test _stop_pubsub_listener handles unsubscribe errors."""
    mock_redis = AsyncMock()
    mock_pubsub = AsyncMock()
    mock_pubsub.unsubscribe.side_effect = Exception("Unsubscribe failed")

    broadcaster = SystemBroadcaster(redis_client=mock_redis)
    broadcaster._pubsub = mock_pubsub
    broadcaster._pubsub_listening = True

    # Should not raise
    await broadcaster._stop_pubsub_listener()

    # Should still clean up
    assert broadcaster._pubsub is None
    assert broadcaster._pubsub_listening is False
    # close should still be called even if unsubscribe fails
    mock_pubsub.close.assert_called_once()


@pytest.mark.asyncio
async def test_system_broadcaster_listen_for_updates_no_pubsub():
    """Test _listen_for_updates returns early when pubsub not initialized."""
    broadcaster = SystemBroadcaster()
    broadcaster._pubsub = None

    # Should return immediately without error
    await broadcaster._listen_for_updates()


@pytest.mark.asyncio
async def test_system_broadcaster_listen_for_updates_no_redis():
    """Test _listen_for_updates returns early when Redis not available."""
    broadcaster = SystemBroadcaster()
    broadcaster._pubsub = AsyncMock()  # Pubsub set but no Redis

    # Should return immediately without error
    await broadcaster._listen_for_updates()


@pytest.mark.asyncio
async def test_system_broadcaster_listen_for_updates_processes_messages():
    """Test _listen_for_updates processes messages and forwards to clients."""

    mock_redis = AsyncMock()
    mock_pubsub = AsyncMock()

    # Create messages to receive
    messages = [
        {"data": {"type": "system_status", "test": "value1"}},
        {"data": {"type": "system_status", "test": "value2"}},
        {"data": None},  # Should be skipped
    ]

    # Create async generator for messages
    async def mock_listen(pubsub):
        for msg in messages:
            yield msg

    mock_redis.listen = mock_listen
    mock_redis.subscribe.return_value = mock_pubsub

    broadcaster = SystemBroadcaster(redis_client=mock_redis)
    broadcaster._pubsub = mock_pubsub
    broadcaster._pubsub_listening = True

    # Add a websocket connection
    mock_ws = AsyncMock()
    broadcaster.connections.add(mock_ws)

    # Run the listener (will exit after processing all messages)
    await broadcaster._listen_for_updates()

    # Should have sent both messages (not the None one)
    assert mock_ws.send_text.call_count == 2


@pytest.mark.asyncio
async def test_system_broadcaster_listen_for_updates_cancelled_error():
    """Test _listen_for_updates handles CancelledError gracefully."""
    mock_redis = AsyncMock()
    mock_pubsub = AsyncMock()

    async def mock_listen(pubsub):
        for _ in []:  # Make it an async generator
            yield
        raise asyncio.CancelledError()

    mock_redis.listen = mock_listen

    broadcaster = SystemBroadcaster(redis_client=mock_redis)
    broadcaster._pubsub = mock_pubsub
    broadcaster._pubsub_listening = True

    # Should not raise CancelledError - should be caught
    try:
        await broadcaster._listen_for_updates()
    except asyncio.CancelledError:
        pytest.fail("CancelledError should be caught")


@pytest.mark.asyncio
async def test_system_broadcaster_listen_for_updates_reconnection_failure():
    """Test _listen_for_updates handles reconnection failure."""
    mock_redis = AsyncMock()
    mock_pubsub = AsyncMock()

    # Listen raises error - async generator pattern
    async def mock_listen(pubsub):
        for _ in []:
            yield
        raise Exception("Connection error")

    mock_redis.listen = mock_listen
    mock_redis.subscribe.return_value = None  # Reconnection will fail

    broadcaster = SystemBroadcaster(redis_client=mock_redis)
    broadcaster._pubsub = mock_pubsub
    broadcaster._pubsub_listening = True

    # Mock _reset_pubsub_connection to set pubsub to None (simulating failure)
    async def reset_fail():
        broadcaster._pubsub = None

    with patch.object(broadcaster, "_reset_pubsub_connection", side_effect=reset_fail):
        await broadcaster._listen_for_updates()
        await asyncio.sleep(0.1)  # mocked, short wait for test

    # Should have stopped listening
    assert broadcaster._pubsub_listening is False


@pytest.mark.asyncio
async def test_system_broadcaster_broadcast_loop_no_connections():
    """Test _broadcast_loop skips broadcast when no connections."""
    broadcaster = SystemBroadcaster()
    broadcaster._running = True

    # No connections
    broadcast_called = False

    async def mock_broadcast(status_data):
        nonlocal broadcast_called
        broadcast_called = True

    loop_count = 0

    original_sleep = asyncio.sleep

    async def counting_sleep(delay):
        nonlocal loop_count
        loop_count += 1
        if loop_count >= 2:
            broadcaster._running = False
        await original_sleep(0.01)  # Short sleep for test

    with (
        patch.object(broadcaster, "broadcast_status", side_effect=mock_broadcast),
        patch("asyncio.sleep", side_effect=counting_sleep),
    ):
        await broadcaster._broadcast_loop(interval=0.1)

    # Broadcast should not be called (no connections)
    assert broadcast_called is False


@pytest.mark.asyncio
async def test_system_broadcaster_broadcast_loop_handles_error():
    """Test _broadcast_loop handles errors and continues."""
    broadcaster = SystemBroadcaster()
    broadcaster._running = True

    # Add a connection
    mock_ws = AsyncMock()
    broadcaster.connections.add(mock_ws)

    call_count = 0

    async def mock_get_status():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Status error")
        broadcaster._running = False
        return {"test": "data"}

    with (
        patch.object(broadcaster, "_get_system_status", side_effect=mock_get_status),
        patch.object(broadcaster, "broadcast_status"),
    ):
        await broadcaster._broadcast_loop(interval=0.01)

    # Should have tried at least twice (error then success)
    assert call_count >= 2


@pytest.mark.asyncio
async def test_system_broadcaster_broadcast_loop_cancelled():
    """Test _broadcast_loop exits on CancelledError."""
    broadcaster = SystemBroadcaster()
    broadcaster._running = True

    # Add connection
    mock_ws = AsyncMock()
    broadcaster.connections.add(mock_ws)

    async def raise_cancelled():
        raise asyncio.CancelledError()

    with patch.object(broadcaster, "_get_system_status", side_effect=raise_cancelled):
        # Should exit cleanly
        await broadcaster._broadcast_loop(interval=0.1)


@pytest.mark.asyncio
async def test_system_broadcaster_send_to_local_clients_string_message():
    """Test _send_to_local_clients with string message."""
    broadcaster = SystemBroadcaster()
    mock_ws = AsyncMock()
    broadcaster.connections.add(mock_ws)

    # Send string directly (already JSON)
    await broadcaster._send_to_local_clients('{"test": "value"}')

    mock_ws.send_text.assert_called_once_with('{"test": "value"}')


@pytest.mark.asyncio
async def test_system_broadcaster_get_gpu_stats_none_result():
    """Test _get_latest_gpu_stats when database returns no GPU stats."""
    broadcaster = SystemBroadcaster()

    # Mock database session to return None for GPU stats
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    async def mock_get_session():
        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_session
        mock_cm.__aexit__.return_value = None
        return mock_cm

    # Use a context manager mock
    with patch("backend.services.system_broadcaster.get_session") as mock_session_getter:
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = None
        mock_session_getter.return_value = mock_context

        gpu_stats = await broadcaster._get_latest_gpu_stats()

    # Should return null values
    assert gpu_stats["utilization"] is None
    assert gpu_stats["memory_used"] is None
    assert gpu_stats["memory_total"] is None
    assert gpu_stats["temperature"] is None
    assert gpu_stats["inference_fps"] is None


@pytest.mark.asyncio
async def test_system_broadcaster_listen_stops_when_flag_false():
    """Test _listen_for_updates stops when _pubsub_listening is set to False."""
    mock_redis = AsyncMock()
    mock_pubsub = AsyncMock()

    messages_processed = 0

    async def mock_listen(pubsub):
        nonlocal messages_processed
        for i in range(5):
            messages_processed += 1
            yield {"data": {"count": i}}

    mock_redis.listen = mock_listen

    broadcaster = SystemBroadcaster(redis_client=mock_redis)
    broadcaster._pubsub = mock_pubsub
    broadcaster._pubsub_listening = True

    # Add a connection to receive messages
    mock_ws = AsyncMock()
    broadcaster.connections.add(mock_ws)

    # Override send to stop after first message
    original_send = broadcaster._send_to_local_clients

    async def send_and_stop(data):
        await original_send(data)
        broadcaster._pubsub_listening = False

    with patch.object(broadcaster, "_send_to_local_clients", side_effect=send_and_stop):
        await broadcaster._listen_for_updates()

    # Should stop early (the loop checks _pubsub_listening at the start of each iteration)
    # The first message is processed, flag is set to False, second message may be yielded
    # before the check, so we allow 1-2 messages processed
    assert messages_processed <= 2


# ============================================================================
# Tests for PerformanceCollector integration
# ============================================================================


@pytest.mark.asyncio
async def test_system_broadcaster_set_performance_collector():
    """Test setting PerformanceCollector after initialization."""
    broadcaster = SystemBroadcaster()
    assert broadcaster._performance_collector is None

    mock_collector = AsyncMock()
    broadcaster.set_performance_collector(mock_collector)
    assert broadcaster._performance_collector is mock_collector


@pytest.mark.asyncio
async def test_system_broadcaster_broadcast_performance_no_collector():
    """Test broadcast_performance returns early when no collector configured."""
    broadcaster = SystemBroadcaster()
    broadcaster._performance_collector = None

    # Should not raise, should return early
    await broadcaster.broadcast_performance()
    # No error means success - method returned early


@pytest.mark.asyncio
async def test_system_broadcaster_broadcast_performance_with_collector():
    """Test broadcast_performance collects and broadcasts metrics."""
    mock_redis = AsyncMock()
    broadcaster = SystemBroadcaster(redis_client=mock_redis)

    # Create mock performance update
    mock_performance_update = MagicMock()
    mock_performance_update.model_dump.return_value = {
        "timestamp": "2025-12-31T10:00:00Z",
        "gpu": {"name": "Test GPU", "utilization": 50.0},
        "alerts": [],
    }

    mock_collector = AsyncMock()
    mock_collector.collect_all.return_value = mock_performance_update

    broadcaster.set_performance_collector(mock_collector)

    await broadcaster.broadcast_performance()

    # Should have called collect_all
    mock_collector.collect_all.assert_called_once()

    # Should have published via Redis with instance origin wrapper
    mock_redis.publish.assert_called_once()
    call_args = mock_redis.publish.call_args
    assert call_args[0][0] == "performance_update"  # Channel name
    published_message = call_args[0][1]
    assert "_origin_instance" in published_message  # Has instance ID
    assert published_message["payload"]["type"] == "performance_update"  # Payload has message type


@pytest.mark.asyncio
async def test_system_broadcaster_broadcast_performance_fallback_to_direct():
    """Test broadcast_performance falls back to direct send when Redis publish fails."""
    mock_redis = AsyncMock()
    mock_redis.publish.side_effect = Exception("Redis publish failed")

    broadcaster = SystemBroadcaster(redis_client=mock_redis)

    # Create mock performance update
    mock_performance_update = MagicMock()
    mock_performance_update.model_dump.return_value = {
        "timestamp": "2025-12-31T10:00:00Z",
        "gpu": None,
        "alerts": [],
    }

    mock_collector = AsyncMock()
    mock_collector.collect_all.return_value = mock_performance_update

    broadcaster.set_performance_collector(mock_collector)

    # Add a connection
    mock_ws = AsyncMock()
    broadcaster.connections.add(mock_ws)

    await broadcaster.broadcast_performance()

    # Should have fallen back to direct send
    mock_ws.send_text.assert_called_once()


@pytest.mark.asyncio
async def test_system_broadcaster_broadcast_performance_no_redis():
    """Test broadcast_performance sends directly when Redis not available."""
    broadcaster = SystemBroadcaster()  # No Redis

    # Create mock performance update
    mock_performance_update = MagicMock()
    mock_performance_update.model_dump.return_value = {
        "timestamp": "2025-12-31T10:00:00Z",
        "alerts": [],
    }

    mock_collector = AsyncMock()
    mock_collector.collect_all.return_value = mock_performance_update

    broadcaster.set_performance_collector(mock_collector)

    # Add a connection
    mock_ws = AsyncMock()
    broadcaster.connections.add(mock_ws)

    await broadcaster.broadcast_performance()

    # Should have sent directly
    mock_ws.send_text.assert_called_once()
    # Verify the message contains the performance_update type
    call_args = mock_ws.send_text.call_args
    import json as json_mod

    sent_data = json_mod.loads(call_args[0][0])
    assert sent_data["type"] == "performance_update"


@pytest.mark.asyncio
async def test_system_broadcaster_broadcast_performance_collector_error():
    """Test broadcast_performance handles collector errors gracefully."""
    broadcaster = SystemBroadcaster()

    mock_collector = AsyncMock()
    mock_collector.collect_all.side_effect = Exception("Collector error")

    broadcaster.set_performance_collector(mock_collector)

    # Should not raise
    await broadcaster.broadcast_performance()
    # No error means success - error was handled


@pytest.mark.asyncio
async def test_system_broadcaster_broadcast_loop_calls_performance():
    """Test that _broadcast_loop calls broadcast_performance alongside broadcast_status."""
    broadcaster = SystemBroadcaster()
    broadcaster._running = True

    # Add a connection
    mock_ws = AsyncMock()
    broadcaster.connections.add(mock_ws)

    # Track calls
    performance_called = False
    status_called = False
    loop_count = 0

    async def mock_broadcast_performance():
        nonlocal performance_called
        performance_called = True

    async def mock_broadcast_status(data):
        nonlocal status_called
        status_called = True

    async def mock_get_status():
        return {"test": "data"}

    original_sleep = asyncio.sleep

    async def counting_sleep(delay):
        nonlocal loop_count
        loop_count += 1
        if loop_count >= 1:
            broadcaster._running = False
        await original_sleep(0.01)

    with (
        patch.object(broadcaster, "broadcast_performance", side_effect=mock_broadcast_performance),
        patch.object(broadcaster, "broadcast_status", side_effect=mock_broadcast_status),
        patch.object(broadcaster, "_get_system_status", side_effect=mock_get_status),
        patch("asyncio.sleep", side_effect=counting_sleep),
    ):
        await broadcaster._broadcast_loop(interval=0.1)

    # Both should have been called
    assert status_called is True
    assert performance_called is True


@pytest.mark.asyncio
async def test_system_broadcaster_init_has_no_performance_collector():
    """Test that SystemBroadcaster initializes with no performance collector."""
    broadcaster = SystemBroadcaster()
    assert broadcaster._performance_collector is None


@pytest.mark.asyncio
async def test_system_broadcaster_set_performance_collector_to_none():
    """Test setting performance collector to None clears it."""
    broadcaster = SystemBroadcaster()

    mock_collector = AsyncMock()
    broadcaster.set_performance_collector(mock_collector)
    assert broadcaster._performance_collector is mock_collector

    broadcaster.set_performance_collector(None)
    assert broadcaster._performance_collector is None


# ============================================================================
# Tests for consolidated database session handling (connection pool fix)
# ============================================================================


@pytest.mark.asyncio
async def test_system_broadcaster_get_system_status_uses_single_session():
    """Test that _get_system_status uses a single database session.

    This is critical for preventing 'Too many connections' errors when
    broadcasting status at high frequency (every 5 seconds).
    """
    broadcaster = SystemBroadcaster()

    # Track how many times get_session is called
    session_call_count = 0

    # Mock session context manager
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalar_one.return_value = 0
    mock_session.execute.return_value = mock_result

    @asynccontextmanager
    async def counting_session():
        nonlocal session_call_count
        session_call_count += 1
        yield mock_session

    with (
        patch("backend.services.system_broadcaster.get_session", counting_session),
        patch.object(broadcaster, "_get_queue_stats", return_value={"pending": 0, "processing": 0}),
        patch.object(broadcaster, "_check_redis_health", return_value=True),
        patch.object(
            broadcaster,
            "_check_ai_health",
            return_value={
                "all_healthy": True,
                "any_healthy": True,
                "rtdetr": True,
                "nemotron": True,
            },
        ),
    ):
        status = await broadcaster._get_system_status()

    # Should only open ONE session for both GPU and camera queries
    assert session_call_count == 1, f"Expected 1 session, got {session_call_count}"

    # Verify status structure
    assert status["type"] == "system_status"
    assert "gpu" in status["data"]
    assert "cameras" in status["data"]
    assert "health" in status["data"]


@pytest.mark.asyncio
async def test_system_broadcaster_get_gpu_stats_with_session():
    """Test _get_latest_gpu_stats_with_session uses provided session."""
    broadcaster = SystemBroadcaster()

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_gpu_stat = MagicMock()
    mock_gpu_stat.gpu_utilization = 75.5
    mock_gpu_stat.memory_used = 8192
    mock_gpu_stat.memory_total = 24576
    mock_gpu_stat.temperature = 65.0
    mock_gpu_stat.inference_fps = 30.5
    mock_result.scalar_one_or_none.return_value = mock_gpu_stat
    mock_session.execute.return_value = mock_result

    gpu_stats = await broadcaster._get_latest_gpu_stats_with_session(mock_session)

    # Should use the provided session
    mock_session.execute.assert_called_once()

    # Should return correct values
    assert gpu_stats["utilization"] == 75.5
    assert gpu_stats["memory_used"] == 8192
    assert gpu_stats["memory_total"] == 24576
    assert gpu_stats["temperature"] == 65.0
    assert gpu_stats["inference_fps"] == 30.5


@pytest.mark.asyncio
async def test_system_broadcaster_get_camera_stats_with_session():
    """Test _get_camera_stats_with_session uses provided session."""
    broadcaster = SystemBroadcaster()

    mock_session = AsyncMock()

    # First call returns total count, second returns active count
    call_count = 0

    def mock_execute(*args):
        nonlocal call_count
        call_count += 1
        mock_result = MagicMock()
        if call_count == 1:
            mock_result.scalar_one.return_value = 5  # total
        else:
            mock_result.scalar_one.return_value = 3  # active
        return mock_result

    mock_session.execute.side_effect = mock_execute

    camera_stats = await broadcaster._get_camera_stats_with_session(mock_session)

    # Should call execute twice (total and active counts)
    assert mock_session.execute.call_count == 2

    # Should return correct counts
    assert camera_stats["total"] == 5
    assert camera_stats["active"] == 3


@pytest.mark.asyncio
async def test_system_broadcaster_get_system_status_handles_db_error():
    """Test _get_system_status handles database errors gracefully."""
    broadcaster = SystemBroadcaster()

    @asynccontextmanager
    async def failing_session():
        for _ in []:  # Make it a generator for asynccontextmanager
            yield
        raise Exception("Database connection error")

    with (
        patch("backend.services.system_broadcaster.get_session", failing_session),
        patch.object(broadcaster, "_get_queue_stats", return_value={"pending": 0, "processing": 0}),
        patch.object(broadcaster, "_check_redis_health", return_value=True),
        patch.object(
            broadcaster,
            "_check_ai_health",
            return_value={
                "all_healthy": True,
                "any_healthy": True,
                "rtdetr": True,
                "nemotron": True,
            },
        ),
    ):
        status = await broadcaster._get_system_status()

    # Should still return a valid status with null GPU values
    assert status["type"] == "system_status"
    assert status["data"]["gpu"]["utilization"] is None
    assert status["data"]["cameras"]["active"] == 0
    assert status["data"]["health"] == "unhealthy"


@pytest.mark.asyncio
async def test_system_broadcaster_check_redis_health_success():
    """Test _check_redis_health returns True when Redis is healthy."""
    mock_redis = AsyncMock()
    mock_redis.health_check.return_value = True

    broadcaster = SystemBroadcaster(redis_client=mock_redis)

    result = await broadcaster._check_redis_health()

    assert result is True
    mock_redis.health_check.assert_called_once()


@pytest.mark.asyncio
async def test_system_broadcaster_check_redis_health_failure():
    """Test _check_redis_health returns False when Redis health check fails."""
    mock_redis = AsyncMock()
    mock_redis.health_check.side_effect = Exception("Redis not available")

    broadcaster = SystemBroadcaster(redis_client=mock_redis)

    result = await broadcaster._check_redis_health()

    assert result is False


@pytest.mark.asyncio
async def test_system_broadcaster_check_redis_health_no_client():
    """Test _check_redis_health returns False when no Redis client."""
    broadcaster = SystemBroadcaster()  # No Redis client

    result = await broadcaster._check_redis_health()

    assert result is False


@pytest.mark.asyncio
async def test_system_broadcaster_get_system_status_degraded_when_redis_unhealthy():
    """Test that health status is degraded when Redis is unhealthy."""
    broadcaster = SystemBroadcaster()

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalar_one.return_value = 0
    mock_session.execute.return_value = mock_result

    @asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.system_broadcaster.get_session", mock_get_session),
        patch.object(broadcaster, "_get_queue_stats", return_value={"pending": 0, "processing": 0}),
        patch.object(broadcaster, "_check_redis_health", return_value=False),
        patch.object(
            broadcaster,
            "_check_ai_health",
            return_value={
                "all_healthy": True,
                "any_healthy": True,
                "rtdetr": True,
                "nemotron": True,
            },
        ),
    ):
        status = await broadcaster._get_system_status()

    # Database is healthy, Redis is not - should be degraded
    assert status["data"]["health"] == "degraded"


# ============================================================================
# Tests for AI health check (_check_ai_health method)
# ============================================================================


@pytest.mark.asyncio
async def test_system_broadcaster_check_ai_health_both_healthy():
    """Test _check_ai_health when both AI services respond with 200."""
    broadcaster = SystemBroadcaster()

    with patch("backend.services.system_broadcaster.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client_cls.return_value.__aexit__.return_value = None

        result = await broadcaster._check_ai_health()

    assert result["rtdetr"] is True
    assert result["nemotron"] is True
    assert result["all_healthy"] is True
    assert result["any_healthy"] is True


@pytest.mark.asyncio
async def test_system_broadcaster_check_ai_health_both_unhealthy():
    """Test _check_ai_health when both AI services fail."""
    broadcaster = SystemBroadcaster()

    with patch("backend.services.system_broadcaster.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection refused")
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client_cls.return_value.__aexit__.return_value = None

        result = await broadcaster._check_ai_health()

    assert result["rtdetr"] is False
    assert result["nemotron"] is False
    assert result["all_healthy"] is False
    assert result["any_healthy"] is False


@pytest.mark.asyncio
async def test_system_broadcaster_check_ai_health_non_200_status():
    """Test _check_ai_health when services return non-200 status codes."""
    broadcaster = SystemBroadcaster()

    with patch("backend.services.system_broadcaster.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 500  # Server error
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client_cls.return_value.__aexit__.return_value = None

        result = await broadcaster._check_ai_health()

    # Non-200 status should be treated as unhealthy
    assert result["rtdetr"] is False
    assert result["nemotron"] is False
    assert result["all_healthy"] is False
    assert result["any_healthy"] is False


@pytest.mark.asyncio
async def test_system_broadcaster_check_ai_health_timeout():
    """Test _check_ai_health handles timeouts gracefully."""
    import httpx as real_httpx

    broadcaster = SystemBroadcaster()

    with patch("backend.services.system_broadcaster.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.side_effect = real_httpx.TimeoutException("Timeout")
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client_cls.return_value.__aexit__.return_value = None

        result = await broadcaster._check_ai_health()

    # Timeout should be treated as unhealthy
    assert result["rtdetr"] is False
    assert result["nemotron"] is False
    assert result["all_healthy"] is False
    assert result["any_healthy"] is False


@pytest.mark.asyncio
async def test_system_broadcaster_get_system_status_includes_ai_status():
    """Test that _get_system_status includes AI health status in response."""
    broadcaster = SystemBroadcaster()

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalar_one.return_value = 0
    mock_session.execute.return_value = mock_result

    @asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.system_broadcaster.get_session", mock_get_session),
        patch.object(broadcaster, "_get_queue_stats", return_value={"pending": 0, "processing": 0}),
        patch.object(broadcaster, "_check_redis_health", return_value=True),
        patch.object(
            broadcaster,
            "_check_ai_health",
            return_value={
                "rtdetr": True,
                "nemotron": True,
                "all_healthy": True,
                "any_healthy": True,
            },
        ),
    ):
        status = await broadcaster._get_system_status()

    # Verify AI status is included in the response
    assert "ai" in status["data"]
    assert status["data"]["ai"]["status"] == "healthy"
    assert status["data"]["ai"]["rtdetr"] == "healthy"
    assert status["data"]["ai"]["nemotron"] == "healthy"
    # Overall health should be healthy when all services are healthy
    assert status["data"]["health"] == "healthy"


@pytest.mark.asyncio
async def test_system_broadcaster_get_system_status_ai_degraded():
    """Test that health is degraded when only one AI service is healthy."""
    broadcaster = SystemBroadcaster()

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalar_one.return_value = 0
    mock_session.execute.return_value = mock_result

    @asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.system_broadcaster.get_session", mock_get_session),
        patch.object(broadcaster, "_get_queue_stats", return_value={"pending": 0, "processing": 0}),
        patch.object(broadcaster, "_check_redis_health", return_value=True),
        patch.object(
            broadcaster,
            "_check_ai_health",
            return_value={
                "rtdetr": True,
                "nemotron": False,  # Nemotron unhealthy - LLM service error scenario
                "all_healthy": False,
                "any_healthy": True,
            },
        ),
    ):
        status = await broadcaster._get_system_status()

    # AI status should show degraded when one service is unhealthy
    assert status["data"]["ai"]["status"] == "degraded"
    assert status["data"]["ai"]["rtdetr"] == "healthy"
    assert status["data"]["ai"]["nemotron"] == "unhealthy"
    # Overall health should be degraded when AI is not all healthy
    assert status["data"]["health"] == "degraded"


@pytest.mark.asyncio
async def test_system_broadcaster_get_system_status_ai_unhealthy():
    """Test that AI status is unhealthy when all AI services are down."""
    broadcaster = SystemBroadcaster()

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalar_one.return_value = 0
    mock_session.execute.return_value = mock_result

    @asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.system_broadcaster.get_session", mock_get_session),
        patch.object(broadcaster, "_get_queue_stats", return_value={"pending": 0, "processing": 0}),
        patch.object(broadcaster, "_check_redis_health", return_value=True),
        patch.object(
            broadcaster,
            "_check_ai_health",
            return_value={
                "rtdetr": False,
                "nemotron": False,
                "all_healthy": False,
                "any_healthy": False,
            },
        ),
    ):
        status = await broadcaster._get_system_status()

    # AI status should show unhealthy when all services are down
    assert status["data"]["ai"]["status"] == "unhealthy"
    assert status["data"]["ai"]["rtdetr"] == "unhealthy"
    assert status["data"]["ai"]["nemotron"] == "unhealthy"
    # Overall health should be degraded (DB/Redis healthy, but AI is down)
    assert status["data"]["health"] == "degraded"


# ============================================================================
# Tests for is_degraded() method (NEM-1075)
# ============================================================================


@pytest.mark.asyncio
async def test_system_broadcaster_is_degraded_initially_false():
    """Test that is_degraded() returns False initially."""
    broadcaster = SystemBroadcaster()
    assert broadcaster.is_degraded() is False


@pytest.mark.asyncio
async def test_system_broadcaster_is_degraded_after_max_recovery_attempts():
    """Test that is_degraded() returns True after max recovery attempts exhausted."""
    mock_redis = AsyncMock()
    broadcaster = SystemBroadcaster(redis_client=mock_redis)

    # Simulate having exhausted recovery attempts
    broadcaster._recovery_attempts = broadcaster.MAX_RECOVERY_ATTEMPTS + 1
    broadcaster._pubsub_listening = True

    # Mock _broadcast_degraded_state to avoid WebSocket interactions
    with patch.object(broadcaster, "_broadcast_degraded_state"):
        await broadcaster._attempt_listener_recovery()

    # Should be in degraded mode
    assert broadcaster.is_degraded() is True
    assert broadcaster._pubsub_listening is False


@pytest.mark.asyncio
async def test_system_broadcaster_is_degraded_after_circuit_breaker_open():
    """Test that is_degraded() returns True when circuit breaker blocks recovery."""
    from backend.core.websocket_circuit_breaker import WebSocketCircuitState

    mock_redis = AsyncMock()
    broadcaster = SystemBroadcaster(redis_client=mock_redis)
    broadcaster._pubsub_listening = True

    # Force circuit breaker to block calls by setting state to OPEN
    broadcaster._circuit_breaker._state = WebSocketCircuitState.OPEN

    # Mock _broadcast_degraded_state to avoid WebSocket interactions
    with patch.object(broadcaster, "_broadcast_degraded_state"):
        await broadcaster._attempt_listener_recovery()

    # Should be in degraded mode
    assert broadcaster.is_degraded() is True
    assert broadcaster._pubsub_listening is False


@pytest.mark.asyncio
async def test_system_broadcaster_is_degraded_cleared_on_successful_start():
    """Test that is_degraded() returns False after successful pub/sub start."""
    mock_redis = AsyncMock()
    mock_pubsub = AsyncMock()
    mock_redis.subscribe_dedicated.return_value = mock_pubsub

    broadcaster = SystemBroadcaster(redis_client=mock_redis)

    # Manually set degraded mode
    broadcaster._is_degraded = True
    assert broadcaster.is_degraded() is True

    # Mock listen to avoid actual async iteration
    async def empty_listen(pubsub):
        for _ in []:
            yield

    mock_redis.listen = empty_listen

    await broadcaster._start_pubsub_listener()

    # Should have cleared degraded mode on successful start
    assert broadcaster.is_degraded() is False
    assert broadcaster._pubsub_listening is True

    # Cleanup
    broadcaster._pubsub_listening = False
    if broadcaster._listener_task:
        broadcaster._listener_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await broadcaster._listener_task


@pytest.mark.asyncio
async def test_system_broadcaster_is_degraded_after_reestablish_failure():
    """Test that is_degraded() returns True when re-establishing connection fails."""
    mock_redis = AsyncMock()
    # Make subscribe_dedicated return None to simulate failure
    mock_redis.subscribe_dedicated.side_effect = Exception("Connection failed")

    broadcaster = SystemBroadcaster(redis_client=mock_redis)
    broadcaster._pubsub_listening = True
    broadcaster._recovery_attempts = 1  # Not at max yet

    # Mock _reset_pubsub_connection to set pubsub to None (simulating failure)
    async def reset_fail():
        broadcaster._pubsub = None

    # Mock _broadcast_degraded_state to avoid WebSocket interactions
    with (
        patch.object(broadcaster, "_reset_pubsub_connection", side_effect=reset_fail),
        patch.object(broadcaster, "_broadcast_degraded_state"),
    ):
        await broadcaster._attempt_listener_recovery()

    # Should be in degraded mode
    assert broadcaster.is_degraded() is True
    assert broadcaster._pubsub_listening is False


@pytest.mark.asyncio
async def test_system_broadcaster_degraded_flag_init():
    """Test that _is_degraded is properly initialized in __init__."""
    broadcaster = SystemBroadcaster()
    assert hasattr(broadcaster, "_is_degraded")
    assert broadcaster._is_degraded is False
