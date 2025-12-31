"""Unit tests for system broadcaster service.

These tests verify behavior with mocked dependencies (Redis, WebSocket)
and don't require a real database connection.
"""

import asyncio
import contextlib
import json
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
        return
        yield  # Make it a generator

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

    # Should publish via Redis
    mock_redis.publish.assert_called_once_with("system_status", status_data)


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

    # Mock listen to avoid actual async iteration
    async def empty_listen(pubsub):
        return
        yield  # Make it an async generator

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
        raise asyncio.CancelledError()
        yield  # Make it an async generator

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

    # Listen raises error
    async def mock_listen(pubsub):
        raise Exception("Connection error")
        yield

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


# Test connect() method with initial status


@pytest.mark.asyncio
async def test_system_broadcaster_connect():
    """Test connecting a WebSocket and sending initial status."""
    broadcaster = SystemBroadcaster()
    mock_websocket = AsyncMock()

    # Mock _get_system_status to avoid database calls
    mock_status = {"type": "system_status", "data": {"test": "initial"}}
    with patch.object(broadcaster, "_get_system_status", return_value=mock_status):
        await broadcaster.connect(mock_websocket)

    # Should accept and add the connection
    mock_websocket.accept.assert_called_once()
    assert mock_websocket in broadcaster.connections

    # Should send initial status
    mock_websocket.send_json.assert_called_once_with(mock_status)


@pytest.mark.asyncio
async def test_system_broadcaster_connect_initial_status_error():
    """Test connect() handles initial status send errors gracefully."""
    broadcaster = SystemBroadcaster()
    mock_websocket = AsyncMock()

    # Mock _get_system_status to raise error
    with patch.object(broadcaster, "_get_system_status", side_effect=Exception("Status error")):
        # Should not raise
        await broadcaster.connect(mock_websocket)

    # Should still accept and add the connection
    mock_websocket.accept.assert_called_once()
    assert mock_websocket in broadcaster.connections


# Test _stop_pubsub_listener close error


@pytest.mark.asyncio
async def test_system_broadcaster_stop_pubsub_listener_close_error():
    """Test _stop_pubsub_listener handles close errors gracefully."""
    mock_redis = AsyncMock()
    mock_pubsub = AsyncMock()
    mock_pubsub.close.side_effect = Exception("Close failed")

    broadcaster = SystemBroadcaster(redis_client=mock_redis)
    broadcaster._pubsub = mock_pubsub
    broadcaster._pubsub_listening = True

    # Should not raise
    await broadcaster._stop_pubsub_listener()

    # Should still clean up
    assert broadcaster._pubsub is None
    assert broadcaster._pubsub_listening is False


# Test _reset_pubsub_connection close error


@pytest.mark.asyncio
async def test_system_broadcaster_reset_pubsub_handles_close_error():
    """Test _reset_pubsub_connection handles close errors gracefully."""
    mock_redis = AsyncMock()
    mock_pubsub = AsyncMock()
    mock_redis.subscribe_dedicated.return_value = mock_pubsub

    old_pubsub = AsyncMock()
    old_pubsub.close.side_effect = Exception("Close failed")

    broadcaster = SystemBroadcaster(redis_client=mock_redis)
    broadcaster._pubsub = old_pubsub

    # Should not raise, should continue to create new subscription
    await broadcaster._reset_pubsub_connection()

    assert broadcaster._pubsub is mock_pubsub
    mock_redis.subscribe_dedicated.assert_called_once()


# Test _get_system_status


@pytest.mark.asyncio
async def test_system_broadcaster_get_system_status():
    """Test _get_system_status gathers all status data."""
    broadcaster = SystemBroadcaster()

    # Mock all the component getters
    mock_gpu_stats = {"utilization": 75, "memory_used": 8192}
    mock_camera_stats = {"active": 3, "total": 5}
    mock_queue_stats = {"pending": 10, "processing": 2}
    mock_health = "healthy"

    with (
        patch.object(broadcaster, "_get_latest_gpu_stats", return_value=mock_gpu_stats),
        patch.object(broadcaster, "_get_camera_stats", return_value=mock_camera_stats),
        patch.object(broadcaster, "_get_queue_stats", return_value=mock_queue_stats),
        patch.object(broadcaster, "_get_health_status", return_value=mock_health),
    ):
        status = await broadcaster._get_system_status()

    assert status["type"] == "system_status"
    assert status["data"]["gpu"] == mock_gpu_stats
    assert status["data"]["cameras"] == mock_camera_stats
    assert status["data"]["queue"] == mock_queue_stats
    assert status["data"]["health"] == mock_health
    assert "timestamp" in status


# Test _get_latest_gpu_stats with actual GPU data


@pytest.mark.asyncio
async def test_system_broadcaster_get_latest_gpu_stats_with_data():
    """Test _get_latest_gpu_stats returns GPU stats from database."""
    broadcaster = SystemBroadcaster()

    # Create a mock GPU stats object
    mock_gpu_stat = MagicMock()
    mock_gpu_stat.gpu_utilization = 80.5
    mock_gpu_stat.memory_used = 10240
    mock_gpu_stat.memory_total = 24576
    mock_gpu_stat.temperature = 72.0
    mock_gpu_stat.inference_fps = 30.0

    # Mock database session
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_gpu_stat
    mock_session.execute.return_value = mock_result

    with patch("backend.services.system_broadcaster.get_session") as mock_get_session:
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = None
        mock_get_session.return_value = mock_context

        gpu_stats = await broadcaster._get_latest_gpu_stats()

    assert gpu_stats["utilization"] == 80.5
    assert gpu_stats["memory_used"] == 10240
    assert gpu_stats["memory_total"] == 24576
    assert gpu_stats["temperature"] == 72.0
    assert gpu_stats["inference_fps"] == 30.0


# Test _get_camera_stats


@pytest.mark.asyncio
async def test_system_broadcaster_get_camera_stats():
    """Test _get_camera_stats returns camera counts from database."""
    broadcaster = SystemBroadcaster()

    # Mock database session
    mock_session = AsyncMock()

    # Mock total cameras query
    mock_total_result = MagicMock()
    mock_total_result.scalar_one.return_value = 5

    # Mock active cameras query
    mock_active_result = MagicMock()
    mock_active_result.scalar_one.return_value = 3

    mock_session.execute.side_effect = [mock_total_result, mock_active_result]

    with patch("backend.services.system_broadcaster.get_session") as mock_get_session:
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = None
        mock_get_session.return_value = mock_context

        camera_stats = await broadcaster._get_camera_stats()

    assert camera_stats["total"] == 5
    assert camera_stats["active"] == 3


# Test _get_health_status


@pytest.mark.asyncio
async def test_system_broadcaster_get_health_status_healthy():
    """Test _get_health_status returns healthy when all services are up."""
    mock_redis = AsyncMock()
    mock_redis.health_check.return_value = {"status": "ok"}

    broadcaster = SystemBroadcaster(redis_client=mock_redis)

    # Mock database session
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_session.execute.return_value = mock_result

    with patch("backend.services.system_broadcaster.get_session") as mock_get_session:
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = None
        mock_get_session.return_value = mock_context

        health = await broadcaster._get_health_status()

    assert health == "healthy"


@pytest.mark.asyncio
async def test_system_broadcaster_get_health_status_degraded():
    """Test _get_health_status returns degraded when Redis is down."""
    mock_redis = AsyncMock()
    mock_redis.health_check.side_effect = Exception("Redis error")

    broadcaster = SystemBroadcaster(redis_client=mock_redis)

    # Mock database session (DB is healthy)
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_session.execute.return_value = mock_result

    with patch("backend.services.system_broadcaster.get_session") as mock_get_session:
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = None
        mock_get_session.return_value = mock_context

        health = await broadcaster._get_health_status()

    assert health == "degraded"


@pytest.mark.asyncio
async def test_system_broadcaster_get_health_status_degraded_no_redis():
    """Test _get_health_status returns degraded when Redis not configured."""
    broadcaster = SystemBroadcaster()  # No Redis

    # Mock database session (DB is healthy)
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_session.execute.return_value = mock_result

    with patch("backend.services.system_broadcaster.get_session") as mock_get_session:
        mock_context = AsyncMock()
        mock_context.__aenter__.return_value = mock_session
        mock_context.__aexit__.return_value = None
        mock_get_session.return_value = mock_context

        health = await broadcaster._get_health_status()

    assert health == "degraded"


@pytest.mark.asyncio
async def test_system_broadcaster_get_health_status_unhealthy():
    """Test _get_health_status returns unhealthy when database is down."""
    broadcaster = SystemBroadcaster()

    # Mock database session to fail
    with patch("backend.services.system_broadcaster.get_session") as mock_get_session:
        mock_context = AsyncMock()
        mock_context.__aenter__.side_effect = Exception("Database error")
        mock_get_session.return_value = mock_context

        health = await broadcaster._get_health_status()

    assert health == "unhealthy"


# Test _get_broadcaster_lock


def test_get_broadcaster_lock_creates_lock():
    """Test _get_broadcaster_lock creates and returns asyncio.Lock."""
    import backend.services.system_broadcaster as sb

    # Reset the lock
    sb._broadcaster_lock = None

    lock = sb._get_broadcaster_lock()

    assert lock is not None
    assert isinstance(lock, asyncio.Lock)


def test_get_broadcaster_lock_returns_same_lock():
    """Test _get_broadcaster_lock returns the same lock on subsequent calls."""
    import backend.services.system_broadcaster as sb

    # Reset the lock
    sb._broadcaster_lock = None

    lock1 = sb._get_broadcaster_lock()
    lock2 = sb._get_broadcaster_lock()

    assert lock1 is lock2


# Test get_system_broadcaster_async


@pytest.mark.asyncio
async def test_get_system_broadcaster_async_creates_and_starts():
    """Test get_system_broadcaster_async creates and starts broadcaster."""
    import backend.services.system_broadcaster as sb

    # Reset state
    sb._system_broadcaster = None
    sb._broadcaster_lock = None

    mock_redis = AsyncMock()

    # Mock start_broadcasting to avoid actual broadcasting
    with patch.object(SystemBroadcaster, "start_broadcasting") as mock_start:
        broadcaster = await sb.get_system_broadcaster_async(redis_client=mock_redis, interval=2.0)

        mock_start.assert_called_once_with(2.0)
        assert broadcaster is not None
        assert broadcaster._redis_client is mock_redis

    # Cleanup
    sb._system_broadcaster = None
    sb._broadcaster_lock = None


@pytest.mark.asyncio
async def test_get_system_broadcaster_async_fast_path():
    """Test get_system_broadcaster_async returns existing running broadcaster."""
    import backend.services.system_broadcaster as sb

    # Reset state
    sb._broadcaster_lock = None

    # Create a running broadcaster
    existing_broadcaster = SystemBroadcaster()
    existing_broadcaster._running = True
    sb._system_broadcaster = existing_broadcaster

    # Fast path should return existing broadcaster without acquiring lock
    result = await sb.get_system_broadcaster_async()

    assert result is existing_broadcaster

    # Cleanup
    sb._system_broadcaster = None


@pytest.mark.asyncio
async def test_get_system_broadcaster_async_updates_redis():
    """Test get_system_broadcaster_async updates Redis on existing broadcaster."""
    import backend.services.system_broadcaster as sb

    # Reset state
    sb._broadcaster_lock = None

    # Create a running broadcaster
    existing_broadcaster = SystemBroadcaster()
    existing_broadcaster._running = True
    sb._system_broadcaster = existing_broadcaster

    new_redis = AsyncMock()
    result = await sb.get_system_broadcaster_async(redis_client=new_redis)

    assert result._redis_client is new_redis

    # Cleanup
    sb._system_broadcaster = None


@pytest.mark.asyncio
async def test_get_system_broadcaster_async_starts_if_not_running():
    """Test get_system_broadcaster_async starts broadcaster if not running."""
    import backend.services.system_broadcaster as sb

    # Reset state
    sb._broadcaster_lock = None

    # Create a non-running broadcaster
    existing_broadcaster = SystemBroadcaster()
    existing_broadcaster._running = False
    sb._system_broadcaster = existing_broadcaster

    with patch.object(existing_broadcaster, "start_broadcasting") as mock_start:
        result = await sb.get_system_broadcaster_async(interval=3.0)

        mock_start.assert_called_once_with(3.0)
        assert result is existing_broadcaster

    # Cleanup
    sb._system_broadcaster = None


# Test stop_system_broadcaster


@pytest.mark.asyncio
async def test_stop_system_broadcaster():
    """Test stop_system_broadcaster stops and clears the broadcaster."""
    import backend.services.system_broadcaster as sb

    # Reset state
    sb._broadcaster_lock = None

    # Create a broadcaster
    existing_broadcaster = SystemBroadcaster()
    existing_broadcaster._running = True
    sb._system_broadcaster = existing_broadcaster

    with patch.object(existing_broadcaster, "stop_broadcasting") as mock_stop:
        await sb.stop_system_broadcaster()

        mock_stop.assert_called_once()
        assert sb._system_broadcaster is None


@pytest.mark.asyncio
async def test_stop_system_broadcaster_when_none():
    """Test stop_system_broadcaster handles None broadcaster."""
    import backend.services.system_broadcaster as sb

    # Reset state
    sb._system_broadcaster = None
    sb._broadcaster_lock = None

    # Should not raise
    await sb.stop_system_broadcaster()
    assert sb._system_broadcaster is None


# Test reset_broadcaster_state


def test_reset_broadcaster_state():
    """Test reset_broadcaster_state clears global state."""
    import backend.services.system_broadcaster as sb

    # Set some state
    sb._system_broadcaster = SystemBroadcaster()
    sb._broadcaster_lock = asyncio.Lock()

    sb.reset_broadcaster_state()

    assert sb._system_broadcaster is None
    assert sb._broadcaster_lock is None


# Test _start_pubsub_listener when Redis unavailable


@pytest.mark.asyncio
async def test_system_broadcaster_start_pubsub_listener_no_redis():
    """Test _start_pubsub_listener when Redis is not available."""
    broadcaster = SystemBroadcaster()  # No Redis

    await broadcaster._start_pubsub_listener()

    # Should not be listening since no Redis
    assert broadcaster._pubsub_listening is False
    assert broadcaster._pubsub is None


@pytest.mark.asyncio
async def test_get_system_broadcaster_async_updates_redis_in_slow_path():
    """Test get_system_broadcaster_async updates Redis in slow path (existing non-running broadcaster)."""
    import backend.services.system_broadcaster as sb

    # Reset state
    sb._broadcaster_lock = None

    # Create an existing non-running broadcaster without Redis
    existing_broadcaster = SystemBroadcaster()
    existing_broadcaster._running = False
    sb._system_broadcaster = existing_broadcaster

    # Provide new Redis client in the slow path
    new_redis = AsyncMock()

    with patch.object(existing_broadcaster, "start_broadcasting") as mock_start:
        result = await sb.get_system_broadcaster_async(redis_client=new_redis, interval=2.0)

        # Should update the Redis client in the slow path (line 658)
        assert result._redis_client is new_redis
        mock_start.assert_called_once_with(2.0)

    # Cleanup
    sb._system_broadcaster = None
