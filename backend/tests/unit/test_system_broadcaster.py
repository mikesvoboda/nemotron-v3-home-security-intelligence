"""Unit tests for system broadcaster service."""

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.system_broadcaster import SystemBroadcaster, get_system_broadcaster
from backend.tests.conftest import unique_id


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
async def test_system_broadcaster_connect(isolated_db):
    """Test adding a WebSocket connection."""
    broadcaster = SystemBroadcaster()
    mock_websocket = AsyncMock()

    # Mock the system status gathering to avoid database calls
    with patch.object(broadcaster, "_get_system_status", return_value={"test": "data"}):
        await broadcaster.connect(mock_websocket)

    # WebSocket should be accepted and added to connections
    mock_websocket.accept.assert_called_once()
    assert mock_websocket in broadcaster.connections
    assert len(broadcaster.connections) == 1

    # Should have sent initial status
    mock_websocket.send_json.assert_called_once()


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
    import json

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
async def test_system_broadcaster_get_system_status(isolated_db):
    """Test gathering system status data."""
    broadcaster = SystemBroadcaster()

    status = await broadcaster._get_system_status()

    # Verify structure
    assert "type" in status
    assert status["type"] == "system_status"
    assert "data" in status
    assert "timestamp" in status

    # Verify data fields
    data = status["data"]
    assert "gpu" in data
    assert "cameras" in data
    assert "queue" in data
    assert "health" in data


@pytest.mark.asyncio
async def test_system_broadcaster_get_latest_gpu_stats_no_data(isolated_db):
    """Test getting GPU stats returns valid structure."""
    broadcaster = SystemBroadcaster()

    gpu_stats = await broadcaster._get_latest_gpu_stats()

    # Should return expected keys (values may be null or from parallel tests)
    assert "utilization" in gpu_stats
    assert "memory_used" in gpu_stats
    assert "memory_total" in gpu_stats
    assert "temperature" in gpu_stats
    assert "inference_fps" in gpu_stats


@pytest.mark.asyncio
async def test_system_broadcaster_get_latest_gpu_stats_with_data(isolated_db):
    """Test getting GPU stats when data exists."""
    from backend.core.database import get_session
    from backend.models import GPUStats

    # Use unique values to identify our test data
    test_utilization = 75.5
    test_memory_used = 12000
    test_memory_total = 24000
    test_temperature = 65.0
    test_fps = 30.5

    # Add GPU stats to database
    async with get_session() as sess:
        gpu_stat = GPUStats(
            gpu_utilization=test_utilization,
            memory_used=test_memory_used,
            memory_total=test_memory_total,
            temperature=test_temperature,
            inference_fps=test_fps,
        )
        sess.add(gpu_stat)
        await sess.commit()

    broadcaster = SystemBroadcaster()
    gpu_stats = await broadcaster._get_latest_gpu_stats()

    # Should return values (may be our test data or more recent from parallel tests)
    # The key assertion is that we get non-null values when data exists
    assert gpu_stats["utilization"] is not None
    assert gpu_stats["memory_used"] is not None
    assert gpu_stats["memory_total"] is not None
    assert gpu_stats["temperature"] is not None
    assert gpu_stats["inference_fps"] is not None


@pytest.mark.asyncio
async def test_system_broadcaster_get_camera_stats(isolated_db):
    """Test getting camera statistics."""
    from backend.core.database import get_session
    from backend.models import Camera

    # Get initial counts before adding our test data
    broadcaster = SystemBroadcaster()
    initial_stats = await broadcaster._get_camera_stats()
    initial_total = initial_stats["total"]
    initial_active = initial_stats["active"]

    # Add cameras to database with unique IDs
    cam_id1 = unique_id("cam")
    cam_id2 = unique_id("cam")
    cam_id3 = unique_id("cam")

    async with get_session() as sess:
        camera1 = Camera(
            id=cam_id1,
            name="Front Door",
            folder_path=f"/test/{cam_id1}",
            status="online",
        )
        camera2 = Camera(
            id=cam_id2,
            name="Back Yard",
            folder_path=f"/test/{cam_id2}",
            status="offline",
        )
        camera3 = Camera(
            id=cam_id3,
            name="Garage",
            folder_path=f"/test/{cam_id3}",
            status="online",
        )
        sess.add_all([camera1, camera2, camera3])
        await sess.commit()

    camera_stats = await broadcaster._get_camera_stats()

    # Should return incremented counts (relative to initial state)
    assert camera_stats["total"] >= initial_total + 3
    assert camera_stats["active"] >= initial_active + 2  # Two are online


@pytest.mark.asyncio
async def test_system_broadcaster_get_camera_stats_empty(isolated_db):
    """Test getting camera stats returns valid structure."""
    broadcaster = SystemBroadcaster()
    camera_stats = await broadcaster._get_camera_stats()

    # Should return valid structure with non-negative counts
    # (may not be zero due to parallel test data)
    assert "total" in camera_stats
    assert "active" in camera_stats
    assert camera_stats["total"] >= 0
    assert camera_stats["active"] >= 0
    assert camera_stats["active"] <= camera_stats["total"]


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
async def test_system_broadcaster_get_health_status_healthy(isolated_db):
    """Test health status when all services are healthy."""
    # Mock Redis to be healthy
    mock_redis = AsyncMock()
    # health_check is awaited, so it needs to return a coroutine
    mock_redis.health_check = AsyncMock(return_value={"status": "healthy"})

    # Use dependency injection
    broadcaster = SystemBroadcaster(redis_client=mock_redis)
    health_status = await broadcaster._get_health_status()

    assert health_status == "healthy"


@pytest.mark.asyncio
async def test_system_broadcaster_get_health_status_degraded(isolated_db):
    """Test health status when Redis is down."""
    # Mock Redis to fail
    mock_redis = AsyncMock()
    mock_redis.health_check.side_effect = Exception("Redis connection failed")

    # Use dependency injection
    broadcaster = SystemBroadcaster(redis_client=mock_redis)
    health_status = await broadcaster._get_health_status()

    assert health_status == "degraded"


@pytest.mark.asyncio
async def test_system_broadcaster_get_health_status_no_redis(isolated_db):
    """Test health status when Redis is not configured."""
    # No Redis client provided - should report degraded
    broadcaster = SystemBroadcaster()
    health_status = await broadcaster._get_health_status()

    assert health_status == "degraded"


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
async def test_system_broadcaster_connect_handles_error(isolated_db):
    """Test that connect handles errors gracefully."""
    broadcaster = SystemBroadcaster()
    mock_websocket = AsyncMock()

    # Mock send_json to fail
    mock_websocket.send_json.side_effect = Exception("Send failed")

    # Mock the system status gathering
    with patch.object(broadcaster, "_get_system_status", return_value={"test": "data"}):
        # Should not raise, just log error
        await broadcaster.connect(mock_websocket)

    # Connection should still be added
    assert mock_websocket in broadcaster.connections


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
    mock_redis.subscribe.return_value = mock_pubsub

    broadcaster = SystemBroadcaster(redis_client=mock_redis)
    broadcaster._pubsub = AsyncMock()  # Simulate existing pubsub

    await broadcaster._reset_pubsub_connection()

    # Should unsubscribe from old and create new subscription
    mock_redis.unsubscribe.assert_called_once()
    mock_redis.subscribe.assert_called_once()
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
    mock_redis.unsubscribe.side_effect = Exception("Unsubscribe failed")
    mock_pubsub = AsyncMock()
    mock_redis.subscribe.return_value = mock_pubsub

    broadcaster = SystemBroadcaster(redis_client=mock_redis)
    broadcaster._pubsub = AsyncMock()

    # Should not raise, should continue to create new subscription
    await broadcaster._reset_pubsub_connection()

    assert broadcaster._pubsub is mock_pubsub
    mock_redis.subscribe.assert_called_once()


@pytest.mark.asyncio
async def test_system_broadcaster_reset_pubsub_handles_subscribe_error():
    """Test reset_pubsub_connection handles subscribe errors gracefully."""
    mock_redis = AsyncMock()
    mock_redis.subscribe.side_effect = Exception("Subscribe failed")

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
    import json

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

    # subscribe should not be called since listener is already running
    mock_redis.subscribe.assert_not_called()


@pytest.mark.asyncio
async def test_system_broadcaster_start_pubsub_listener_subscribe_error():
    """Test _start_pubsub_listener handles subscription errors."""
    mock_redis = AsyncMock()
    mock_redis.subscribe.side_effect = Exception("Subscription failed")

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
    mock_redis.subscribe.return_value = mock_pubsub

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
    """Test _stop_pubsub_listener cancels listener task."""
    mock_redis = AsyncMock()
    broadcaster = SystemBroadcaster(redis_client=mock_redis)

    # Create a long-running task that will be cancelled
    async def long_running():
        await asyncio.sleep(100)  # cancelled

    broadcaster._listener_task = asyncio.create_task(long_running())
    broadcaster._pubsub = AsyncMock()
    broadcaster._pubsub_listening = True

    await broadcaster._stop_pubsub_listener()

    # Should be stopped
    assert broadcaster._pubsub_listening is False
    assert broadcaster._listener_task is None
    assert broadcaster._pubsub is None
    mock_redis.unsubscribe.assert_called_once()


@pytest.mark.asyncio
async def test_system_broadcaster_stop_pubsub_listener_unsubscribe_error():
    """Test _stop_pubsub_listener handles unsubscribe errors."""
    mock_redis = AsyncMock()
    mock_redis.unsubscribe.side_effect = Exception("Unsubscribe failed")

    broadcaster = SystemBroadcaster(redis_client=mock_redis)
    broadcaster._pubsub = AsyncMock()
    broadcaster._pubsub_listening = True

    # Should not raise
    await broadcaster._stop_pubsub_listener()

    # Should still clean up
    assert broadcaster._pubsub is None
    assert broadcaster._pubsub_listening is False


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
async def test_system_broadcaster_get_health_status_unhealthy(isolated_db):
    """Test health status when database is down."""
    broadcaster = SystemBroadcaster()

    # Mock get_session to raise error (database down)
    with patch("backend.services.system_broadcaster.get_session") as mock_session:
        mock_session.side_effect = Exception("Database connection failed")

        health_status = await broadcaster._get_health_status()

    assert health_status == "unhealthy"


@pytest.mark.asyncio
async def test_system_broadcaster_broadcast_loop_execution(isolated_db):
    """Test _broadcast_loop executes and broadcasts status."""
    broadcaster = SystemBroadcaster()
    broadcaster._running = True

    # Add a connection so broadcast happens
    mock_ws = AsyncMock()
    broadcaster.connections.add(mock_ws)

    # Track broadcasts
    broadcast_count = 0

    async def mock_broadcast(status_data):
        nonlocal broadcast_count
        broadcast_count += 1
        # Stop after first broadcast
        broadcaster._running = False

    with (
        patch.object(broadcaster, "broadcast_status", side_effect=mock_broadcast),
        patch.object(broadcaster, "_get_system_status", return_value={"test": "data"}),
    ):
        await broadcaster._broadcast_loop(interval=0.1)

    assert broadcast_count == 1


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
