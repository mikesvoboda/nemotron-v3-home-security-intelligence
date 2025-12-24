"""Unit tests for system broadcaster service."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from backend.services.system_broadcaster import SystemBroadcaster, get_system_broadcaster


@pytest.mark.asyncio
async def test_system_broadcaster_init():
    """Test SystemBroadcaster initialization."""
    broadcaster = SystemBroadcaster()

    assert broadcaster.connections == set()
    assert broadcaster._broadcast_task is None
    assert broadcaster._running is False


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
    """Test broadcasting status to all connections."""
    broadcaster = SystemBroadcaster()
    mock_ws1 = AsyncMock()
    mock_ws2 = AsyncMock()
    broadcaster.connections.add(mock_ws1)
    broadcaster.connections.add(mock_ws2)

    status_data = {"type": "system_status", "data": {"test": "value"}}
    await broadcaster.broadcast_status(status_data)

    # Both connections should receive the message
    mock_ws1.send_json.assert_called_once_with(status_data)
    mock_ws2.send_json.assert_called_once_with(status_data)


@pytest.mark.asyncio
async def test_system_broadcaster_broadcast_status_removes_failed():
    """Test that failed connections are removed during broadcast."""
    broadcaster = SystemBroadcaster()
    mock_ws_good = AsyncMock()
    mock_ws_bad = AsyncMock()
    mock_ws_bad.send_json.side_effect = Exception("Connection failed")

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
    """Test getting GPU stats when no data exists."""
    broadcaster = SystemBroadcaster()

    gpu_stats = await broadcaster._get_latest_gpu_stats()

    # Should return null values
    assert gpu_stats["utilization"] is None
    assert gpu_stats["memory_used"] is None
    assert gpu_stats["memory_total"] is None
    assert gpu_stats["temperature"] is None
    assert gpu_stats["inference_fps"] is None


@pytest.mark.asyncio
async def test_system_broadcaster_get_latest_gpu_stats_with_data(isolated_db):
    """Test getting GPU stats when data exists."""
    from backend.core.database import get_session
    from backend.models import GPUStats

    # Add GPU stats to database
    async with get_session() as session:
        gpu_stat = GPUStats(
            gpu_utilization=75.5,
            memory_used=12000,
            memory_total=24000,
            temperature=65.0,
            inference_fps=30.5,
        )
        session.add(gpu_stat)
        await session.commit()

    broadcaster = SystemBroadcaster()
    gpu_stats = await broadcaster._get_latest_gpu_stats()

    # Should return actual values
    assert gpu_stats["utilization"] == 75.5
    assert gpu_stats["memory_used"] == 12000
    assert gpu_stats["memory_total"] == 24000
    assert gpu_stats["temperature"] == 65.0
    assert gpu_stats["inference_fps"] == 30.5


@pytest.mark.asyncio
async def test_system_broadcaster_get_camera_stats(isolated_db):
    """Test getting camera statistics."""
    from backend.core.database import get_session
    from backend.models import Camera

    # Add cameras to database
    async with get_session() as session:
        camera1 = Camera(
            id="camera1",
            name="Front Door",
            folder_path="/test/camera1",
            status="online",
        )
        camera2 = Camera(
            id="camera2",
            name="Back Yard",
            folder_path="/test/camera2",
            status="offline",
        )
        camera3 = Camera(
            id="camera3",
            name="Garage",
            folder_path="/test/camera3",
            status="online",
        )
        session.add_all([camera1, camera2, camera3])
        await session.commit()

    broadcaster = SystemBroadcaster()
    camera_stats = await broadcaster._get_camera_stats()

    # Should return correct counts
    assert camera_stats["total"] == 3
    assert camera_stats["active"] == 2  # Two are online


@pytest.mark.asyncio
async def test_system_broadcaster_get_camera_stats_empty(isolated_db):
    """Test getting camera stats with no cameras."""
    broadcaster = SystemBroadcaster()
    camera_stats = await broadcaster._get_camera_stats()

    # Should return zeros
    assert camera_stats["total"] == 0
    assert camera_stats["active"] == 0


@pytest.mark.asyncio
async def test_system_broadcaster_get_queue_stats():
    """Test getting queue statistics from Redis."""
    broadcaster = SystemBroadcaster()

    # Mock Redis client
    mock_redis = AsyncMock()
    mock_redis.get_queue_length.side_effect = lambda queue: {
        "detection_queue": 5,
        "analysis_queue": 2,
    }.get(queue, 0)

    with patch("backend.services.system_broadcaster._redis_client", mock_redis):
        queue_stats = await broadcaster._get_queue_stats()

    # Should return correct counts
    assert queue_stats["pending"] == 5
    assert queue_stats["processing"] == 2


@pytest.mark.asyncio
async def test_system_broadcaster_get_queue_stats_redis_unavailable():
    """Test getting queue stats when Redis is unavailable."""
    broadcaster = SystemBroadcaster()

    # Mock Redis client to be None
    with patch("backend.services.system_broadcaster._redis_client", None):
        queue_stats = await broadcaster._get_queue_stats()

    # Should return zeros
    assert queue_stats["pending"] == 0
    assert queue_stats["processing"] == 0


@pytest.mark.asyncio
async def test_system_broadcaster_get_queue_stats_redis_error():
    """Test getting queue stats when Redis raises an error."""
    broadcaster = SystemBroadcaster()

    # Mock Redis to raise an exception
    mock_redis = AsyncMock()
    mock_redis.get_queue_length.side_effect = Exception("Redis error")

    with patch("backend.services.system_broadcaster._redis_client", mock_redis):
        queue_stats = await broadcaster._get_queue_stats()

    # Should return zeros on error
    assert queue_stats["pending"] == 0
    assert queue_stats["processing"] == 0


@pytest.mark.asyncio
async def test_system_broadcaster_get_health_status_healthy(isolated_db):
    """Test health status when all services are healthy."""
    broadcaster = SystemBroadcaster()

    # Mock Redis to be healthy
    mock_redis = AsyncMock()
    # health_check is awaited, so it needs to return a coroutine
    mock_redis.health_check = AsyncMock(return_value={"status": "healthy"})

    with patch("backend.services.system_broadcaster._redis_client", mock_redis):
        health_status = await broadcaster._get_health_status()

    assert health_status == "healthy"


@pytest.mark.asyncio
async def test_system_broadcaster_get_health_status_degraded(isolated_db):
    """Test health status when Redis is down."""
    broadcaster = SystemBroadcaster()

    # Mock Redis to fail
    mock_redis = AsyncMock()
    mock_redis.health_check.side_effect = Exception("Redis connection failed")

    with patch("backend.services.system_broadcaster._redis_client", mock_redis):
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
    broadcaster._broadcast_task = asyncio.create_task(asyncio.sleep(10))

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
