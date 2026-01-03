"""Integration tests for system broadcaster service.

These tests require a real PostgreSQL database connection via the isolated_db fixture.
Unit tests that use mocked dependencies are in backend/tests/unit/test_system_broadcaster.py.
"""

import asyncio
import contextlib
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.system_broadcaster import SystemBroadcaster
from backend.tests.conftest import unique_id

# Mark as integration since these tests require real PostgreSQL database
pytestmark = pytest.mark.integration


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

    # Add cameras to database with unique IDs and names to prevent unique constraint conflicts
    cam_id1 = unique_id("cam")
    cam_id2 = unique_id("cam")
    cam_id3 = unique_id("cam")

    async with get_session() as sess:
        camera1 = Camera(
            id=cam_id1,
            name=f"Front Door {cam_id1[-8:]}",
            folder_path=f"/test/{cam_id1}",
            status="online",
        )
        camera2 = Camera(
            id=cam_id2,
            name=f"Back Yard {cam_id2[-8:]}",
            folder_path=f"/test/{cam_id2}",
            status="offline",
        )
        camera3 = Camera(
            id=cam_id3,
            name=f"Garage {cam_id3[-8:]}",
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
        # Return empty generator for subsequent calls - empty generator pattern
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
