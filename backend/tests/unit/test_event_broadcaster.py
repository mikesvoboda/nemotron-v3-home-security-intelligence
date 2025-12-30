"""Unit tests for EventBroadcaster service."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

import pytest

from backend.services import event_broadcaster
from backend.services.event_broadcaster import (
    EventBroadcaster,
    get_broadcaster,
    get_event_channel,
    reset_broadcaster_state,
    stop_broadcaster,
)


@pytest.fixture(autouse=True)
def _enable_log_capture(caplog: pytest.LogCaptureFixture) -> None:
    """Automatically enable INFO-level log capture for all tests."""
    caplog.set_level(logging.INFO)


@pytest.fixture(autouse=True)
def _reset_broadcaster_state() -> None:
    """Reset global broadcaster state before each test for isolation."""
    reset_broadcaster_state()


class _FakePubSub:
    pass


class _FakeRedis:
    def __init__(self) -> None:
        self.subscribe = AsyncMock(return_value=_FakePubSub())
        self.unsubscribe = AsyncMock(return_value=None)
        self.publish = AsyncMock(return_value=1)

    async def listen(self, _pubsub: Any) -> AsyncIterator[dict[str, Any]]:
        # Default: no messages
        if False:  # pragma: no cover
            yield {}
        return


# ==============================================================================
# Basic EventBroadcaster Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_broadcast_event_wraps_missing_type() -> None:
    """Test that broadcast_event wraps payload missing 'type' key."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    payload = {"id": 123, "risk_score": 42}
    count = await broadcaster.broadcast_event(payload)

    assert count == 1
    redis.publish.assert_awaited_once()
    channel, published = redis.publish.await_args.args
    assert channel == broadcaster.CHANNEL_NAME
    assert published["type"] == "event"
    assert published["data"] == payload


@pytest.mark.asyncio
async def test_broadcast_event_preserves_existing_type() -> None:
    """Test that broadcast_event preserves an existing 'type' key."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    payload = {"type": "custom_event", "data": {"id": 456}}
    count = await broadcaster.broadcast_event(payload)

    assert count == 1
    redis.publish.assert_awaited_once()
    channel, published = redis.publish.await_args.args
    assert channel == broadcaster.CHANNEL_NAME
    # Type should be preserved, not wrapped
    assert published["type"] == "custom_event"


@pytest.mark.asyncio
async def test_start_is_idempotent_when_already_listening(caplog: pytest.LogCaptureFixture) -> None:
    """Test that start() is idempotent when already listening."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    broadcaster._is_listening = True

    await broadcaster.start()
    assert "already started" in caplog.text
    redis.subscribe.assert_not_called()


@pytest.mark.asyncio
async def test_listen_for_events_no_pubsub_returns(caplog: pytest.LogCaptureFixture) -> None:
    """Test that _listen_for_events returns early when pubsub is None."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    broadcaster._pubsub = None

    await broadcaster._listen_for_events()
    redis.subscribe.assert_not_called()
    assert "pubsub not initialized" in caplog.text


@pytest.mark.asyncio
async def test_send_to_all_clients_removes_disconnected() -> None:
    """Test that _send_to_all_clients removes disconnected WebSocket clients."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    ok_ws = AsyncMock()
    bad_ws = AsyncMock()
    ok_ws.send_text = AsyncMock(return_value=None)
    bad_ws.send_text = AsyncMock(side_effect=RuntimeError("boom"))
    ok_ws.close = AsyncMock(return_value=None)
    bad_ws.close = AsyncMock(return_value=None)

    broadcaster._connections = {ok_ws, bad_ws}  # type: ignore[assignment]

    await broadcaster._send_to_all_clients({"type": "event", "data": {"id": 1}})

    ok_ws.send_text.assert_awaited()
    bad_ws.send_text.assert_awaited()
    assert ok_ws in broadcaster._connections
    assert bad_ws not in broadcaster._connections


@pytest.mark.asyncio
async def test_listen_for_events_processes_messages_and_sends() -> None:
    """Test that _listen_for_events processes messages and sends to clients."""

    class RedisWithMessages(_FakeRedis):
        async def listen(self, _pubsub: Any) -> AsyncIterator[dict[str, Any]]:
            yield {"data": {"type": "event", "data": {"id": 1}}}

    redis = RedisWithMessages()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    broadcaster._pubsub = _FakePubSub()
    broadcaster._is_listening = True

    broadcaster._send_to_all_clients = AsyncMock(return_value=None)  # type: ignore[method-assign]

    await broadcaster._listen_for_events()
    broadcaster._send_to_all_clients.assert_awaited_once()


@pytest.mark.asyncio
async def test_listen_for_events_restarts_after_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that _listen_for_events restarts listener after non-cancelled errors."""

    class RedisThatErrors(_FakeRedis):
        async def listen(self, _pubsub: Any) -> AsyncIterator[dict[str, Any]]:
            raise RuntimeError("redis blew up")
            if False:  # pragma: no cover
                yield {}

    redis = RedisThatErrors()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    broadcaster._pubsub = _FakePubSub()
    broadcaster._is_listening = True

    sleep_calls: list[float] = []

    async def _fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    created: list[asyncio.Task[None]] = []

    real_create_task = asyncio.create_task

    def _fake_create_task(coro: Any) -> asyncio.Task[None]:
        # Use the real create_task to avoid recursion after monkeypatching.
        task: asyncio.Task[None] = real_create_task(coro)
        created.append(task)
        return task

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)
    monkeypatch.setattr(asyncio, "create_task", _fake_create_task)

    await broadcaster._listen_for_events()
    assert sleep_calls == [1]
    assert broadcaster._listener_task is not None
    assert created

    # Cleanup: cancel the restarted task to avoid it running beyond this test.
    for task in created:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@pytest.mark.asyncio
async def test_stop_unsubscribes_and_disconnects_all_connections() -> None:
    """Test that stop() unsubscribes from channel and disconnects all WebSocket clients."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    broadcaster._is_listening = True
    broadcaster._pubsub = _FakePubSub()

    ws1 = AsyncMock()
    ws2 = AsyncMock()
    ws1.close = AsyncMock(return_value=None)
    ws2.close = AsyncMock(return_value=None)
    broadcaster._connections = {ws1, ws2}  # type: ignore[assignment]

    await broadcaster.stop()
    redis.unsubscribe.assert_awaited_once_with(broadcaster.CHANNEL_NAME)
    assert broadcaster._connections == set()


# ==============================================================================
# Tests for Missing Coverage Lines 50-57: start() successful case
# ==============================================================================


@pytest.mark.asyncio
async def test_start_subscribes_and_creates_listener_task(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that start() subscribes to Redis channel and creates listener task (lines 50-57)."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    # Override listen to return immediately to prevent blocking
    async def quick_listen(_pubsub: Any) -> AsyncIterator[dict[str, Any]]:
        if False:  # pragma: no cover
            yield {}
        return

    redis.listen = quick_listen  # type: ignore[method-assign]

    await broadcaster.start()

    # Verify subscription occurred
    redis.subscribe.assert_awaited_once_with(broadcaster.CHANNEL_NAME)
    assert broadcaster._is_listening is True
    assert broadcaster._listener_task is not None
    assert broadcaster._pubsub is not None
    assert "Event broadcaster started" in caplog.text

    # Cleanup
    await broadcaster.stop()


@pytest.mark.asyncio
async def test_start_raises_on_subscribe_failure(caplog: pytest.LogCaptureFixture) -> None:
    """Test that start() raises and logs error when subscribe fails (lines 55-57)."""
    redis = _FakeRedis()
    redis.subscribe = AsyncMock(side_effect=RuntimeError("Redis subscribe failed"))
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="Redis subscribe failed"):
        await broadcaster.start()

    assert "Failed to start event broadcaster" in caplog.text
    assert broadcaster._is_listening is False


# ==============================================================================
# Tests for Missing Coverage Lines 64-67: stop() cancels listener task
# ==============================================================================


@pytest.mark.asyncio
async def test_stop_cancels_listener_task() -> None:
    """Test that stop() properly cancels the listener task (lines 64-67)."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    broadcaster._is_listening = True
    broadcaster._pubsub = _FakePubSub()

    # Create a mock task that simulates a long-running listener
    async def long_running_task() -> None:
        try:
            await asyncio.sleep(100)  # cancelled - task is cancelled by stop()
        except asyncio.CancelledError:
            raise

    broadcaster._listener_task = asyncio.create_task(long_running_task())

    await broadcaster.stop()

    assert broadcaster._listener_task is None
    assert broadcaster._pubsub is None
    assert broadcaster._is_listening is False


@pytest.mark.asyncio
async def test_stop_handles_task_already_cancelled() -> None:
    """Test that stop() handles an already-cancelled listener task gracefully."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    broadcaster._is_listening = True
    broadcaster._pubsub = _FakePubSub()

    # Create and immediately cancel a task
    async def dummy() -> None:
        await asyncio.sleep(100)  # cancelled - task is cancelled immediately after creation

    task = asyncio.create_task(dummy())
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    broadcaster._listener_task = task

    # Should not raise
    await broadcaster.stop()
    assert broadcaster._listener_task is None


# ==============================================================================
# Tests for Missing Coverage Lines 85-87: connect() WebSocket accept
# ==============================================================================


@pytest.mark.asyncio
async def test_connect_accepts_websocket_and_registers(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that connect() accepts WebSocket and adds to connections (lines 85-87)."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    mock_ws = AsyncMock()
    mock_ws.accept = AsyncMock(return_value=None)

    await broadcaster.connect(mock_ws)

    mock_ws.accept.assert_awaited_once()
    assert mock_ws in broadcaster._connections
    assert "WebSocket connected" in caplog.text
    assert "Total connections: 1" in caplog.text


@pytest.mark.asyncio
async def test_connect_multiple_websockets() -> None:
    """Test that connect() properly tracks multiple WebSocket connections."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    ws1 = AsyncMock()
    ws1.accept = AsyncMock(return_value=None)
    ws2 = AsyncMock()
    ws2.accept = AsyncMock(return_value=None)

    await broadcaster.connect(ws1)
    await broadcaster.connect(ws2)

    assert len(broadcaster._connections) == 2
    assert ws1 in broadcaster._connections
    assert ws2 in broadcaster._connections


# ==============================================================================
# Tests for Missing Coverage Lines 137-139: broadcast_event() exception handling
# ==============================================================================


@pytest.mark.asyncio
async def test_broadcast_event_raises_on_publish_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that broadcast_event() raises and logs when publish fails (lines 137-139)."""
    redis = _FakeRedis()
    redis.publish = AsyncMock(side_effect=RuntimeError("Publish failed"))
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    with pytest.raises(RuntimeError, match="Publish failed"):
        await broadcaster.broadcast_event({"type": "event", "data": {"id": 1}})

    assert "Failed to broadcast event" in caplog.text


# ==============================================================================
# Tests for Missing Coverage Line 157: _listen_for_events() break on not listening
# ==============================================================================


@pytest.mark.asyncio
async def test_listen_for_events_breaks_when_listening_false() -> None:
    """Test that _listen_for_events() breaks when _is_listening becomes False (line 157)."""
    message_count = 0

    class RedisStopsListening(_FakeRedis):
        async def listen(self, _pubsub: Any) -> AsyncIterator[dict[str, Any]]:
            nonlocal message_count
            # Yield first message, then check if listening is still True
            yield {"data": {"type": "event", "data": {"id": 1}}}
            message_count += 1
            # This should trigger the break
            yield {"data": {"type": "event", "data": {"id": 2}}}
            message_count += 1

    redis = RedisStopsListening()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    broadcaster._pubsub = _FakePubSub()
    broadcaster._is_listening = True

    send_calls = 0

    async def mock_send(event_data: Any) -> None:
        nonlocal send_calls
        send_calls += 1
        # After first message, set _is_listening to False
        broadcaster._is_listening = False

    broadcaster._send_to_all_clients = mock_send  # type: ignore[method-assign]

    await broadcaster._listen_for_events()

    # Only first message should have been processed before break
    assert send_calls == 1


# ==============================================================================
# Tests for Missing Coverage Line 162: _listen_for_events() continue on empty data
# ==============================================================================


@pytest.mark.asyncio
async def test_listen_for_events_skips_empty_data() -> None:
    """Test that _listen_for_events() continues when message has no data (line 162)."""

    class RedisWithEmptyMessage(_FakeRedis):
        async def listen(self, _pubsub: Any) -> AsyncIterator[dict[str, Any]]:
            # Message with no data - should be skipped
            yield {"data": None}
            yield {"data": ""}
            yield {}  # No data key at all
            # Valid message
            yield {"data": {"type": "event", "data": {"id": 1}}}

    redis = RedisWithEmptyMessage()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    broadcaster._pubsub = _FakePubSub()
    broadcaster._is_listening = True

    send_calls = []

    async def mock_send(event_data: Any) -> None:
        send_calls.append(event_data)

    broadcaster._send_to_all_clients = mock_send  # type: ignore[method-assign]

    await broadcaster._listen_for_events()

    # Only the valid message should have been sent
    assert len(send_calls) == 1
    assert send_calls[0] == {"type": "event", "data": {"id": 1}}


# ==============================================================================
# Tests for Missing Coverage Line 170: _listen_for_events() CancelledError handling
# ==============================================================================


@pytest.mark.asyncio
async def test_listen_for_events_handles_cancelled_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that _listen_for_events() handles CancelledError gracefully (line 170)."""

    class RedisThatGetssCancelled(_FakeRedis):
        async def listen(self, _pubsub: Any) -> AsyncIterator[dict[str, Any]]:
            raise asyncio.CancelledError()
            if False:  # pragma: no cover
                yield {}

    redis = RedisThatGetssCancelled()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    broadcaster._pubsub = _FakePubSub()
    broadcaster._is_listening = True

    # Should not raise or restart - just log and return
    await broadcaster._listen_for_events()

    assert "Event listener cancelled" in caplog.text
    # Listener task should NOT be recreated for CancelledError
    assert broadcaster._listener_task is None


# ==============================================================================
# Tests for Missing Coverage Line 187: _send_to_all_clients() empty connections
# ==============================================================================


@pytest.mark.asyncio
async def test_send_to_all_clients_returns_early_with_no_connections() -> None:
    """Test that _send_to_all_clients() returns early when no connections (line 187)."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    # Ensure connections is empty
    broadcaster._connections = set()

    # Should return immediately without error
    await broadcaster._send_to_all_clients({"type": "event", "data": {"id": 1}})

    # No assertions needed - just verifying no exception is raised


@pytest.mark.asyncio
async def test_send_to_all_clients_serializes_dict_to_json() -> None:
    """Test that _send_to_all_clients() JSON-serializes dict data."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    mock_ws = AsyncMock()
    mock_ws.send_text = AsyncMock(return_value=None)
    mock_ws.close = AsyncMock(return_value=None)
    broadcaster._connections = {mock_ws}  # type: ignore[assignment]

    await broadcaster._send_to_all_clients({"type": "event", "data": {"id": 1}})

    mock_ws.send_text.assert_awaited_once()
    # Verify JSON serialization
    sent_message = mock_ws.send_text.await_args.args[0]
    assert '"type": "event"' in sent_message or '"type":"event"' in sent_message


@pytest.mark.asyncio
async def test_send_to_all_clients_passes_string_directly() -> None:
    """Test that _send_to_all_clients() sends strings without re-serializing."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    mock_ws = AsyncMock()
    mock_ws.send_text = AsyncMock(return_value=None)
    mock_ws.close = AsyncMock(return_value=None)
    broadcaster._connections = {mock_ws}  # type: ignore[assignment]

    await broadcaster._send_to_all_clients('{"already": "serialized"}')

    mock_ws.send_text.assert_awaited_once_with('{"already": "serialized"}')


# ==============================================================================
# Tests for Missing Coverage Lines 224-228: get_broadcaster() creates instance
# ==============================================================================


@pytest.mark.asyncio
async def test_get_broadcaster_creates_and_starts_instance() -> None:
    """Test that get_broadcaster() creates and starts broadcaster (lines 224-228)."""
    # Note: global state is reset by _reset_broadcaster_state fixture
    redis = _FakeRedis()

    # Override listen to return immediately
    async def quick_listen(_pubsub: Any) -> AsyncIterator[dict[str, Any]]:
        if False:  # pragma: no cover
            yield {}
        return

    redis.listen = quick_listen  # type: ignore[method-assign]

    broadcaster = await get_broadcaster(redis)  # type: ignore[arg-type]

    assert broadcaster is not None
    assert broadcaster._is_listening is True
    redis.subscribe.assert_awaited_once()

    # Cleanup
    await stop_broadcaster()


@pytest.mark.asyncio
async def test_get_broadcaster_returns_existing_instance() -> None:
    """Test that get_broadcaster() returns existing instance on subsequent calls."""
    # Reset global state
    event_broadcaster._broadcaster = None

    redis = _FakeRedis()

    # Override listen to return immediately
    async def quick_listen(_pubsub: Any) -> AsyncIterator[dict[str, Any]]:
        if False:  # pragma: no cover
            yield {}
        return

    redis.listen = quick_listen  # type: ignore[method-assign]

    # First call creates instance
    broadcaster1 = await get_broadcaster(redis)  # type: ignore[arg-type]

    # Second call should return same instance
    redis2 = _FakeRedis()
    broadcaster2 = await get_broadcaster(redis2)  # type: ignore[arg-type]

    assert broadcaster1 is broadcaster2
    # Only first Redis should have been subscribed
    redis.subscribe.assert_awaited_once()
    redis2.subscribe.assert_not_awaited()

    # Cleanup
    await stop_broadcaster()


# ==============================================================================
# Tests for Missing Coverage Lines 235-237: stop_broadcaster() stops instance
# ==============================================================================


@pytest.mark.asyncio
async def test_stop_broadcaster_stops_and_clears_global_instance() -> None:
    """Test that stop_broadcaster() stops and clears global broadcaster (lines 235-237)."""
    # Reset global state
    event_broadcaster._broadcaster = None

    redis = _FakeRedis()

    # Override listen to return immediately
    async def quick_listen(_pubsub: Any) -> AsyncIterator[dict[str, Any]]:
        if False:  # pragma: no cover
            yield {}
        return

    redis.listen = quick_listen  # type: ignore[method-assign]

    # Create a broadcaster
    await get_broadcaster(redis)  # type: ignore[arg-type]
    assert event_broadcaster._broadcaster is not None

    # Stop it
    await stop_broadcaster()

    assert event_broadcaster._broadcaster is None
    redis.unsubscribe.assert_awaited_once()


@pytest.mark.asyncio
async def test_stop_broadcaster_does_nothing_when_not_started() -> None:
    """Test that stop_broadcaster() is safe to call when no broadcaster exists."""
    # Reset global state
    event_broadcaster._broadcaster = None

    # Should not raise
    await stop_broadcaster()

    assert event_broadcaster._broadcaster is None


# ==============================================================================
# Additional Edge Case Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_disconnect_removes_websocket_from_connections(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that disconnect() properly removes WebSocket from connections set."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    mock_ws = AsyncMock()
    mock_ws.close = AsyncMock(return_value=None)
    broadcaster._connections = {mock_ws}  # type: ignore[assignment]

    await broadcaster.disconnect(mock_ws)

    assert mock_ws not in broadcaster._connections
    mock_ws.close.assert_awaited_once()
    assert "WebSocket disconnected" in caplog.text


@pytest.mark.asyncio
async def test_disconnect_handles_close_exception() -> None:
    """Test that disconnect() suppresses exceptions when closing WebSocket."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    mock_ws = AsyncMock()
    mock_ws.close = AsyncMock(side_effect=RuntimeError("Close failed"))
    broadcaster._connections = {mock_ws}  # type: ignore[assignment]

    # Should not raise
    await broadcaster.disconnect(mock_ws)

    assert mock_ws not in broadcaster._connections


@pytest.mark.asyncio
async def test_disconnect_handles_missing_websocket() -> None:
    """Test that disconnect() handles WebSocket not in connections set."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    mock_ws = AsyncMock()
    mock_ws.close = AsyncMock(return_value=None)

    # WebSocket not in connections
    broadcaster._connections = set()

    # Should not raise
    await broadcaster.disconnect(mock_ws)


@pytest.mark.asyncio
async def test_listen_for_events_does_not_restart_when_listening_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that _listen_for_events() does not restart when _is_listening is False."""

    class RedisThatErrors(_FakeRedis):
        async def listen(self, _pubsub: Any) -> AsyncIterator[dict[str, Any]]:
            raise RuntimeError("redis error")
            if False:  # pragma: no cover
                yield {}

    redis = RedisThatErrors()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    broadcaster._pubsub = _FakePubSub()
    broadcaster._is_listening = False  # Not listening

    sleep_calls: list[float] = []

    async def _fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)

    await broadcaster._listen_for_events()

    # Should not have slept (no restart attempt)
    assert sleep_calls == []


@pytest.mark.asyncio
async def test_listen_for_events_does_not_restart_second_time_when_listening_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that _listen_for_events() checks _is_listening after sleep before restarting."""

    class RedisThatErrors(_FakeRedis):
        async def listen(self, _pubsub: Any) -> AsyncIterator[dict[str, Any]]:
            raise RuntimeError("redis error")
            if False:  # pragma: no cover
                yield {}

    redis = RedisThatErrors()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    broadcaster._pubsub = _FakePubSub()
    broadcaster._is_listening = True

    sleep_calls: list[float] = []

    async def _fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        # After sleep, set _is_listening to False to prevent restart
        broadcaster._is_listening = False

    create_task_calls = []

    def _fake_create_task(coro: Any) -> asyncio.Task[None]:
        create_task_calls.append(coro)
        # Clean up the coroutine to avoid warnings
        coro.close()
        return None  # type: ignore[return-value]

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)
    monkeypatch.setattr(asyncio, "create_task", _fake_create_task)

    await broadcaster._listen_for_events()

    assert sleep_calls == [1]
    # Should not have created a new task since _is_listening became False
    assert create_task_calls == []


@pytest.mark.asyncio
async def test_stop_when_not_started() -> None:
    """Test that stop() is safe to call when broadcaster was never started."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    # Should not raise
    await broadcaster.stop()

    assert broadcaster._is_listening is False
    assert broadcaster._listener_task is None


@pytest.mark.asyncio
async def test_channel_name_constant() -> None:
    """Test that the CHANNEL_NAME and get_event_channel return the default channel name."""
    # Test the module-level function
    assert get_event_channel() == "security_events"

    # Test the instance property (for backward compatibility)
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    assert broadcaster.CHANNEL_NAME == "security_events"
    assert broadcaster.channel_name == "security_events"


@pytest.mark.asyncio
async def test_send_to_all_clients_logs_cleanup_count(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that _send_to_all_clients logs the number of cleaned up clients."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    # Multiple failing connections
    bad_ws1 = AsyncMock()
    bad_ws1.send_text = AsyncMock(side_effect=RuntimeError("fail1"))
    bad_ws1.close = AsyncMock(return_value=None)

    bad_ws2 = AsyncMock()
    bad_ws2.send_text = AsyncMock(side_effect=RuntimeError("fail2"))
    bad_ws2.close = AsyncMock(return_value=None)

    broadcaster._connections = {bad_ws1, bad_ws2}  # type: ignore[assignment]

    await broadcaster._send_to_all_clients({"type": "event", "data": {"id": 1}})

    assert "Cleaned up 2 disconnected clients" in caplog.text
    assert len(broadcaster._connections) == 0


# ==============================================================================
# Tests for Race Condition Prevention in get_broadcaster()
# ==============================================================================


@pytest.mark.asyncio
async def test_get_broadcaster_concurrent_initialization() -> None:
    """Test that concurrent get_broadcaster() calls don't create multiple instances.

    This test verifies that the race condition fix works correctly by
    calling get_broadcaster() concurrently from multiple coroutines.
    """
    redis = _FakeRedis()

    # Override listen to return immediately
    async def quick_listen(_pubsub: Any) -> AsyncIterator[dict[str, Any]]:
        if False:  # pragma: no cover
            yield {}
        return

    redis.listen = quick_listen  # type: ignore[method-assign]

    # Call get_broadcaster concurrently from multiple coroutines
    results = await asyncio.gather(
        get_broadcaster(redis),  # type: ignore[arg-type]
        get_broadcaster(redis),  # type: ignore[arg-type]
        get_broadcaster(redis),  # type: ignore[arg-type]
        get_broadcaster(redis),  # type: ignore[arg-type]
        get_broadcaster(redis),  # type: ignore[arg-type]
    )

    # All results should be the same instance
    first_broadcaster = results[0]
    for broadcaster in results[1:]:
        assert broadcaster is first_broadcaster

    # subscribe should only have been called once
    redis.subscribe.assert_awaited_once()

    # Cleanup
    await stop_broadcaster()


@pytest.mark.asyncio
async def test_reset_broadcaster_state_clears_global_state() -> None:
    """Test that reset_broadcaster_state() properly clears global state."""
    redis = _FakeRedis()

    # Override listen to return immediately
    async def quick_listen(_pubsub: Any) -> AsyncIterator[dict[str, Any]]:
        if False:  # pragma: no cover
            yield {}
        return

    redis.listen = quick_listen  # type: ignore[method-assign]

    # Create a broadcaster
    broadcaster1 = await get_broadcaster(redis)  # type: ignore[arg-type]
    assert broadcaster1 is not None

    # Stop and reset
    await stop_broadcaster()
    reset_broadcaster_state()

    # Verify global state is cleared
    assert event_broadcaster._broadcaster is None
    assert event_broadcaster._broadcaster_lock is None

    # Create a new broadcaster - should be a different instance
    redis2 = _FakeRedis()
    redis2.listen = quick_listen  # type: ignore[method-assign]
    broadcaster2 = await get_broadcaster(redis2)  # type: ignore[arg-type]

    assert broadcaster2 is not broadcaster1

    # Cleanup
    await stop_broadcaster()
