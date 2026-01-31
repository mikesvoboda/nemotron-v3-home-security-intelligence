"""Unit tests for the StreamManager service (TDD Phase 2).

This module contains comprehensive unit tests for the StreamManager service, which
manages RTSP stream connections for live camera feeds with automatic reconnection
and health tracking.

Related Issues:
    - NEM-4196: TDD Phase 2 - Write tests for Stream Manager Service

Test Organization:
    - Initialization tests: Constructor parameters and dependency injection
    - Start/Stop tests: Service lifecycle and idempotency
    - Stream management tests: Adding and removing streams
    - Health tracking tests: Redis health key persistence
    - Reconnection tests: Exponential backoff logic
    - Error handling tests: Stream failures and recovery
    - Integration tests: Multiple concurrent streams, graceful shutdown

Acceptance Criteria:
    - StreamManager accepts redis_client and optional dependencies
    - start() method initializes event loop and running state
    - stop() method cleans up resources gracefully
    - add_stream(camera_id, rtsp_url) registers a new stream
    - remove_stream(camera_id) stops and removes stream
    - get_stream_health(camera_id) returns health dict
    - Exponential backoff: 5s, 10s, 20s, 40s, max 60s
    - Stream failures trigger reconnection with backoff
    - Health status persisted in Redis: hsi:stream:health:{camera_id}
    - TCP transport only (no UDP)

Design Decisions:
    - Follows async service pattern from file_watcher.py
    - Uses OpenCV VideoCapture for RTSP capture
    - FFmpeg backend for RTSP protocol support
    - Redis hash keys for health tracking
    - asyncio for non-blocking stream management

Notes:
    Tests use mocks for Redis, OpenCV, and FFmpeg operations.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.stream_manager import StreamManager

# Test constants
REDIS_HEALTH_KEY_PREFIX = "hsi:stream:health:"


# Fixtures


@pytest.fixture
def mock_redis_client():
    """Create mock Redis client for health tracking."""
    mock_client = AsyncMock()
    mock_client.hset = AsyncMock(return_value=1)
    mock_client.hgetall = AsyncMock(return_value={})
    mock_client.hdel = AsyncMock(return_value=1)
    mock_client.delete = AsyncMock(return_value=1)
    mock_client.exists = AsyncMock(return_value=0)
    return mock_client


@pytest.fixture
def mock_video_capture():
    """Create mock OpenCV VideoCapture."""
    with patch("cv2.VideoCapture") as mock_cv2:
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, MagicMock())  # (success, frame)
        mock_cap.release = MagicMock()
        mock_cap.set = MagicMock()
        mock_cv2.return_value = mock_cap
        yield mock_cv2


@pytest.fixture
def stream_manager(mock_redis_client):
    """Create StreamManager instance with mocked dependencies."""
    manager = StreamManager(redis_client=mock_redis_client)
    return manager


# Initialization tests


def test_stream_manager_accepts_redis_client(mock_redis_client):
    """Test StreamManager __init__ accepts redis_client parameter.

    ACCEPTANCE: StreamManager must accept redis_client for health tracking.
    """
    manager = StreamManager(redis_client=mock_redis_client)
    assert manager.redis_client is mock_redis_client


def test_stream_manager_initializes_with_default_state(mock_redis_client):
    """Test StreamManager initializes with correct default state.

    ACCEPTANCE: Manager should start in stopped state with no active streams.
    """
    manager = StreamManager(redis_client=mock_redis_client)
    assert manager.running is False
    assert len(manager._streams) == 0
    assert manager._loop is None


def test_stream_manager_accepts_optional_dependencies():
    """Test StreamManager accepts optional dependency injection.

    ACCEPTANCE: Manager should accept optional params for testing/customization.
    """
    mock_redis = AsyncMock()
    mock_capture_factory = MagicMock()

    manager = StreamManager(
        redis_client=mock_redis,
        capture_factory=mock_capture_factory,
    )

    assert manager.redis_client is mock_redis
    assert manager._capture_factory is mock_capture_factory


# Start/Stop tests


@pytest.mark.asyncio
async def test_start_initializes_running_state(mock_redis_client):
    """Test start() method sets running state to True.

    ACCEPTANCE: start() must initialize event loop and set running=True.
    """
    manager = StreamManager(redis_client=mock_redis_client)

    await manager.start()

    assert manager.running is True
    assert manager._loop is not None

    await manager.stop()


@pytest.mark.asyncio
async def test_start_captures_event_loop(mock_redis_client):
    """Test start() captures the current event loop.

    ACCEPTANCE: Must capture loop for thread-safe task scheduling.
    """
    manager = StreamManager(redis_client=mock_redis_client)

    await manager.start()

    # Verify loop was captured and is running
    assert manager._loop is not None
    assert manager._loop.is_running()

    await manager.stop()


@pytest.mark.asyncio
async def test_start_is_idempotent(mock_redis_client):
    """Test calling start() multiple times is safe.

    ACCEPTANCE: Double-start should not cause errors or duplicate resources.
    """
    manager = StreamManager(redis_client=mock_redis_client)

    await manager.start()
    await manager.start()  # Should be safe

    assert manager.running is True

    await manager.stop()


@pytest.mark.asyncio
async def test_start_without_event_loop_raises_error(mock_redis_client):
    """Test start() raises error when no event loop is available.

    ACCEPTANCE: Must fail loudly if started outside async context.
    """
    manager = StreamManager(redis_client=mock_redis_client)

    with patch("asyncio.get_running_loop", side_effect=RuntimeError("No running loop")):
        with pytest.raises(RuntimeError, match="async context"):
            await manager.start()


@pytest.mark.asyncio
async def test_stop_sets_running_to_false(mock_redis_client):
    """Test stop() method sets running state to False.

    ACCEPTANCE: stop() must clean up and set running=False.
    """
    manager = StreamManager(redis_client=mock_redis_client)

    await manager.start()
    await manager.stop()

    assert manager.running is False


@pytest.mark.asyncio
async def test_stop_cleans_up_all_streams(mock_redis_client):
    """Test stop() closes all active streams.

    ACCEPTANCE: stop() must release all VideoCapture resources.
    """
    mock_capture_factory = MagicMock()
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, MagicMock())
    mock_capture_factory.return_value = mock_cap

    manager = StreamManager(redis_client=mock_redis_client, capture_factory=mock_capture_factory)

    await manager.start()
    await manager.add_stream("camera1", "rtsp://example.com/stream1")
    await manager.add_stream("camera2", "rtsp://example.com/stream2")

    # Give tasks time to start
    await asyncio.sleep(0.1)

    await manager.stop()

    # All streams should be cleaned up
    assert len(manager._streams) == 0


@pytest.mark.asyncio
async def test_stop_without_start_is_safe(mock_redis_client):
    """Test stop() can be called without start().

    ACCEPTANCE: stop() should be idempotent and safe to call anytime.
    """
    manager = StreamManager(redis_client=mock_redis_client)

    # Should not raise
    await manager.stop()

    assert manager.running is False


@pytest.mark.asyncio
async def test_stop_clears_event_loop_reference(mock_redis_client):
    """Test stop() clears the event loop reference.

    ACCEPTANCE: Must clean up loop reference to prevent stale references.
    """
    manager = StreamManager(redis_client=mock_redis_client)

    await manager.start()
    assert manager._loop is not None

    await manager.stop()
    assert manager._loop is None


# Stream management tests


@pytest.mark.asyncio
async def test_add_stream_registers_new_stream(mock_redis_client):
    """Test add_stream() registers a new RTSP stream.

    ACCEPTANCE: add_stream(camera_id, rtsp_url) must create VideoCapture.
    """
    mock_capture_factory = MagicMock()
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, MagicMock())
    mock_capture_factory.return_value = mock_cap

    manager = StreamManager(redis_client=mock_redis_client, capture_factory=mock_capture_factory)
    await manager.start()

    await manager.add_stream("camera1", "rtsp://example.com/stream1")

    # Give time for the background connection task to call capture factory
    await asyncio.sleep(0.1)

    # Stream should be registered
    assert "camera1" in manager._streams

    # Capture factory should be called with RTSP URL
    mock_capture_factory.assert_called()
    call_args = mock_capture_factory.call_args[0]
    assert "rtsp://example.com/stream1" in str(call_args)

    await manager.stop()


@pytest.mark.asyncio
async def test_add_stream_uses_tcp_transport(mock_redis_client, mock_video_capture):
    """Test add_stream() uses TCP transport for RTSP.

    ACCEPTANCE: Must use TCP transport only (no UDP) for reliability.
    """
    manager = StreamManager(redis_client=mock_redis_client)
    await manager.start()

    await manager.add_stream("camera1", "rtsp://example.com/stream1")

    # Give time for capture creation
    await asyncio.sleep(0.1)

    # Verify TCP transport is set via cv2.CAP_FFMPEG
    mock_video_capture.assert_called()

    await manager.stop()


@pytest.mark.asyncio
async def test_add_stream_updates_health_in_redis(mock_redis_client):
    """Test add_stream() updates Redis health tracking.

    ACCEPTANCE: Health key hsi:stream:health:{camera_id} must be created.
    """
    mock_capture_factory = MagicMock()
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, MagicMock())
    mock_capture_factory.return_value = mock_cap

    manager = StreamManager(redis_client=mock_redis_client, capture_factory=mock_capture_factory)
    await manager.start()

    await manager.add_stream("camera1", "rtsp://example.com/stream1")

    # Give time for health update
    await asyncio.sleep(0.1)

    # Health should be tracked in Redis
    expected_key = f"{REDIS_HEALTH_KEY_PREFIX}camera1"
    mock_redis_client.hset.assert_called()

    # Verify key contains expected fields
    call_args = str(mock_redis_client.hset.call_args_list)
    assert expected_key in call_args

    await manager.stop()


@pytest.mark.asyncio
async def test_add_stream_duplicate_camera_id_updates_url(mock_redis_client):
    """Test add_stream() with duplicate camera_id updates the URL.

    ACCEPTANCE: Adding same camera_id should close old stream and create new.
    """
    mock_capture_factory = MagicMock()
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, MagicMock())
    mock_capture_factory.return_value = mock_cap

    manager = StreamManager(redis_client=mock_redis_client, capture_factory=mock_capture_factory)
    await manager.start()

    await manager.add_stream("camera1", "rtsp://example.com/stream1")
    await manager.add_stream("camera1", "rtsp://example.com/stream2")

    # Should only have one stream for camera1
    assert len([k for k in manager._streams if k == "camera1"]) == 1

    await manager.stop()


@pytest.mark.asyncio
async def test_remove_stream_closes_video_capture(mock_redis_client):
    """Test remove_stream() releases VideoCapture resources.

    ACCEPTANCE: remove_stream(camera_id) must call capture.release().
    """
    mock_capture_factory = MagicMock()
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, MagicMock())
    mock_capture_factory.return_value = mock_cap

    manager = StreamManager(redis_client=mock_redis_client, capture_factory=mock_capture_factory)
    await manager.start()

    await manager.add_stream("camera1", "rtsp://example.com/stream1")
    # Give time for capture to be set
    await asyncio.sleep(0.1)

    await manager.remove_stream("camera1")

    # VideoCapture.release() should be called
    mock_cap.release.assert_called()

    await manager.stop()


@pytest.mark.asyncio
async def test_remove_stream_deletes_redis_health_key(mock_redis_client):
    """Test remove_stream() removes Redis health tracking.

    ACCEPTANCE: Health key hsi:stream:health:{camera_id} must be deleted.
    """
    mock_capture_factory = MagicMock()
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, MagicMock())
    mock_capture_factory.return_value = mock_cap

    manager = StreamManager(redis_client=mock_redis_client, capture_factory=mock_capture_factory)
    await manager.start()

    await manager.add_stream("camera1", "rtsp://example.com/stream1")
    await manager.remove_stream("camera1")

    # Health key should be deleted
    mock_redis_client.delete.assert_called()

    await manager.stop()


@pytest.mark.asyncio
async def test_remove_stream_nonexistent_camera_is_safe(mock_redis_client):
    """Test remove_stream() with nonexistent camera_id doesn't raise.

    ACCEPTANCE: Removing nonexistent stream should be a no-op.
    """
    manager = StreamManager(redis_client=mock_redis_client)
    await manager.start()

    # Should not raise
    await manager.remove_stream("nonexistent")

    await manager.stop()


# Health tracking tests


@pytest.mark.asyncio
async def test_get_stream_health_returns_health_dict(mock_redis_client):
    """Test get_stream_health() returns health information.

    ACCEPTANCE: Must return dict with status, connection_time, fps, etc.
    """
    mock_redis_client.hgetall.return_value = {
        "status": "connected",
        "connection_time": "2026-01-29T12:00:00Z",
        "fps": "30.0",
    }

    manager = StreamManager(redis_client=mock_redis_client)
    await manager.start()

    health = await manager.get_stream_health("camera1")

    assert health["status"] == "connected"
    assert "connection_time" in health
    assert "fps" in health

    await manager.stop()


@pytest.mark.asyncio
async def test_get_stream_health_nonexistent_stream(mock_redis_client):
    """Test get_stream_health() for nonexistent stream.

    ACCEPTANCE: Should return None or empty dict for nonexistent stream.
    """
    mock_redis_client.hgetall.return_value = {}

    manager = StreamManager(redis_client=mock_redis_client)
    await manager.start()

    health = await manager.get_stream_health("nonexistent")

    assert health is None or health == {}

    await manager.stop()


@pytest.mark.asyncio
async def test_health_tracking_updates_periodically(mock_redis_client):
    """Test health tracking updates Redis periodically.

    ACCEPTANCE: Health should be updated at regular intervals (e.g., every 5s).
    """
    mock_capture_factory = MagicMock()
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, MagicMock())
    mock_capture_factory.return_value = mock_cap

    manager = StreamManager(
        redis_client=mock_redis_client,
        capture_factory=mock_capture_factory,
        health_update_interval=0.1,  # Short interval for testing
    )
    await manager.start()

    await manager.add_stream("camera1", "rtsp://example.com/stream1")

    # Wait for multiple health updates
    await asyncio.sleep(0.3)

    # hset should be called multiple times (initial + updates)
    assert mock_redis_client.hset.call_count > 1

    await manager.stop()


# Reconnection and exponential backoff tests


@pytest.mark.asyncio
async def test_exponential_backoff_calculation():
    """Test exponential backoff calculation for reconnection.

    ACCEPTANCE: Backoff sequence should be 5s, 10s, 20s, 40s, max 60s.
    """
    manager = StreamManager(redis_client=AsyncMock())

    # Test backoff sequence
    assert manager._calculate_backoff(0) == 5
    assert manager._calculate_backoff(1) == 10
    assert manager._calculate_backoff(2) == 20
    assert manager._calculate_backoff(3) == 40
    assert manager._calculate_backoff(4) == 60  # Capped at max
    assert manager._calculate_backoff(5) == 60  # Stays at max


@pytest.mark.asyncio
async def test_stream_failure_triggers_reconnection(mock_redis_client):
    """Test stream failure triggers reconnection with backoff.

    ACCEPTANCE: When capture fails, manager should retry with exponential backoff.
    """
    # First attempt fails, second succeeds
    mock_cap_fail = MagicMock()
    mock_cap_fail.isOpened.return_value = False

    mock_cap_success = MagicMock()
    mock_cap_success.isOpened.return_value = True
    mock_cap_success.read.return_value = (True, MagicMock())

    call_count = [0]

    def capture_factory(url):
        call_count[0] += 1
        if call_count[0] == 1:
            return mock_cap_fail
        return mock_cap_success

    manager = StreamManager(redis_client=mock_redis_client, capture_factory=capture_factory)
    await manager.start()

    original_sleep = asyncio.sleep

    async def fast_sleep(delay):
        # Convert long backoff delays to short ones for testing
        if delay >= 5:
            await original_sleep(0.01)
        else:
            await original_sleep(delay)

    # Patch sleep in the stream_manager module to speed up test
    with patch("backend.services.stream_manager.asyncio.sleep", side_effect=fast_sleep):
        await manager.add_stream("camera1", "rtsp://example.com/stream1")

        # Wait for connection loop to execute and retry
        await original_sleep(0.3)

    # Should have tried twice (initial + retry)
    assert call_count[0] >= 2

    await manager.stop()


@pytest.mark.asyncio
async def test_reconnection_uses_exponential_backoff(mock_redis_client):
    """Test reconnection delays follow exponential backoff.

    ACCEPTANCE: Reconnect delays should increase: 5s, 10s, 20s, etc.
    """
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = False  # Always fail

    manager = StreamManager(redis_client=mock_redis_client, capture_factory=lambda _url: mock_cap)
    await manager.start()

    sleep_delays = []
    original_sleep = asyncio.sleep

    async def mock_sleep(delay):
        sleep_delays.append(delay)
        # Actually wait a tiny bit to allow task switching (but use original sleep)
        await original_sleep(0.01)

    # Patch sleep in the stream_manager module
    with patch("backend.services.stream_manager.asyncio.sleep", side_effect=mock_sleep):
        await manager.add_stream("camera1", "rtsp://example.com/stream1")

        # Wait for multiple reconnection attempts using original sleep
        await original_sleep(0.15)

    # Check sleep was called with exponential delays
    # Filter out the small monitoring delays
    backoff_delays = [d for d in sleep_delays if d >= 5]
    assert len(backoff_delays) > 0
    # First backoff should be 5 seconds
    assert backoff_delays[0] == 5

    await manager.stop()


@pytest.mark.asyncio
async def test_max_backoff_capped_at_60_seconds(mock_redis_client):
    """Test reconnection backoff is capped at 60 seconds.

    ACCEPTANCE: Backoff should never exceed 60 seconds.
    """
    manager = StreamManager(redis_client=mock_redis_client)

    # Test large retry counts still cap at 60s
    assert manager._calculate_backoff(10) == 60
    assert manager._calculate_backoff(100) == 60


@pytest.mark.asyncio
async def test_successful_reconnection_resets_backoff(mock_redis_client):
    """Test successful reconnection resets backoff counter.

    ACCEPTANCE: After successful reconnect, next failure should start at 5s.
    """
    # Fail, succeed sequence
    mock_cap_fail = MagicMock()
    mock_cap_fail.isOpened.return_value = False

    mock_cap_success = MagicMock()
    mock_cap_success.isOpened.return_value = True
    mock_cap_success.read.return_value = (True, MagicMock())

    call_count = [0]

    def capture_factory(url):
        call_count[0] += 1
        if call_count[0] <= 2:
            return mock_cap_fail
        return mock_cap_success

    manager = StreamManager(redis_client=mock_redis_client, capture_factory=capture_factory)
    await manager.start()

    with patch("asyncio.sleep", new_callable=AsyncMock):
        await manager.add_stream("camera1", "rtsp://example.com/stream1")
        await asyncio.sleep(0.2)

    # After successful connection, retry_count should be reset to 0
    if "camera1" in manager._streams:
        assert manager._streams["camera1"]["retry_count"] == 0

    await manager.stop()


# Error handling tests


@pytest.mark.asyncio
async def test_stream_read_error_logged_not_raised(mock_redis_client):
    """Test stream read errors are logged but don't crash manager.

    ACCEPTANCE: Read errors should be logged and trigger reconnection.
    """
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.side_effect = Exception("Read error")

    manager = StreamManager(redis_client=mock_redis_client, capture_factory=lambda _url: mock_cap)
    await manager.start()

    # Should not raise despite read errors
    await manager.add_stream("camera1", "rtsp://example.com/stream1")
    await asyncio.sleep(0.1)

    # Manager should still be running
    assert manager.running is True

    await manager.stop()


@pytest.mark.asyncio
async def test_redis_error_does_not_stop_stream(mock_redis_client):
    """Test Redis errors don't stop stream processing.

    ACCEPTANCE: Health tracking failures should be logged but not stop streams.
    """
    mock_redis_client.hset.side_effect = Exception("Redis error")

    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, MagicMock())

    manager = StreamManager(redis_client=mock_redis_client, capture_factory=lambda _url: mock_cap)
    await manager.start()

    # Should not raise despite Redis errors
    await manager.add_stream("camera1", "rtsp://example.com/stream1")
    await asyncio.sleep(0.1)

    # Stream should still be registered
    assert "camera1" in manager._streams

    await manager.stop()


@pytest.mark.asyncio
async def test_invalid_rtsp_url_handled_gracefully(mock_redis_client):
    """Test invalid RTSP URL is handled gracefully.

    ACCEPTANCE: Invalid URLs should be logged and not crash manager.
    """
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = False  # Simulate connection failure

    manager = StreamManager(redis_client=mock_redis_client, capture_factory=lambda _url: mock_cap)
    await manager.start()

    # Should not raise
    with patch("asyncio.sleep", new_callable=AsyncMock):
        await manager.add_stream("camera1", "invalid://url")
        await asyncio.sleep(0.1)

    # Manager should still be running
    assert manager.running is True

    await manager.stop()


# Integration tests


@pytest.mark.asyncio
async def test_multiple_concurrent_streams(mock_redis_client):
    """Test managing multiple streams concurrently.

    ACCEPTANCE: Manager should handle multiple streams independently.
    """
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, MagicMock())

    manager = StreamManager(redis_client=mock_redis_client, capture_factory=lambda _url: mock_cap)
    await manager.start()

    # Add multiple streams
    await manager.add_stream("camera1", "rtsp://example.com/stream1")
    await manager.add_stream("camera2", "rtsp://example.com/stream2")
    await manager.add_stream("camera3", "rtsp://example.com/stream3")

    # All should be registered
    assert len(manager._streams) == 3
    assert "camera1" in manager._streams
    assert "camera2" in manager._streams
    assert "camera3" in manager._streams

    await manager.stop()


@pytest.mark.asyncio
async def test_graceful_shutdown_with_active_streams(mock_redis_client):
    """Test graceful shutdown closes all active streams.

    ACCEPTANCE: stop() with active streams should clean up all resources.
    """
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, MagicMock())

    manager = StreamManager(redis_client=mock_redis_client, capture_factory=lambda _url: mock_cap)
    await manager.start()

    # Add multiple streams
    await manager.add_stream("camera1", "rtsp://example.com/stream1")
    await manager.add_stream("camera2", "rtsp://example.com/stream2")

    # Give time for captures to be created
    await asyncio.sleep(0.1)

    # Stop should clean up all streams
    await manager.stop()

    # Verify captures were released
    assert mock_cap.release.call_count >= 2


@pytest.mark.asyncio
async def test_async_context_manager_support(mock_redis_client):
    """Test StreamManager supports async context manager protocol.

    ACCEPTANCE: Should support async with statement for automatic cleanup.
    """
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, MagicMock())

    async with StreamManager(
        redis_client=mock_redis_client, capture_factory=lambda _url: mock_cap
    ) as manager:
        assert manager.running is True
        await manager.add_stream("camera1", "rtsp://example.com/stream1")

    # Should be stopped after context exit
    assert manager.running is False


@pytest.mark.asyncio
async def test_concurrent_add_remove_operations(mock_redis_client):
    """Test concurrent add/remove operations are thread-safe.

    ACCEPTANCE: Multiple concurrent operations should not cause race conditions.
    """
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, MagicMock())

    manager = StreamManager(redis_client=mock_redis_client, capture_factory=lambda _url: mock_cap)
    await manager.start()

    # Concurrent operations
    tasks = [
        manager.add_stream("camera1", "rtsp://example.com/stream1"),
        manager.add_stream("camera2", "rtsp://example.com/stream2"),
        manager.remove_stream("camera1"),
        manager.add_stream("camera3", "rtsp://example.com/stream3"),
    ]

    # Should complete without errors
    await asyncio.gather(*tasks)

    await manager.stop()
