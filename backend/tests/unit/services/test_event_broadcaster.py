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
        # Default: no messages - empty async generator pattern
        for _ in []:
            yield {}


# ==============================================================================
# Basic EventBroadcaster Tests
# ==============================================================================


def _create_valid_event_data(
    id: int = 1,
    event_id: int = 1,
    batch_id: str = "batch_123",
    camera_id: str = "cam-uuid",
    risk_score: int = 75,
    risk_level: str = "high",
    summary: str = "Person detected at entrance",
    reasoning: str = "Person detected approaching entrance during daytime hours",
    started_at: str | None = "2025-12-23T12:00:00",
) -> dict[str, Any]:
    """Create valid event data for testing."""
    return {
        "id": id,
        "event_id": event_id,
        "batch_id": batch_id,
        "camera_id": camera_id,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "summary": summary,
        "reasoning": reasoning,
        "started_at": started_at,
    }


@pytest.mark.asyncio
async def test_broadcast_event_wraps_missing_type() -> None:
    """Test that broadcast_event wraps payload missing 'type' key."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    # Use valid event data - will be wrapped with {"type": "event", "data": ...}
    payload = _create_valid_event_data()
    count = await broadcaster.broadcast_event(payload)

    assert count == 1
    redis.publish.assert_awaited_once()
    channel, published = redis.publish.await_args.args
    assert channel == broadcaster.CHANNEL_NAME
    assert published["type"] == "event"
    # Data should be validated and serialized
    assert published["data"]["id"] == 1
    assert published["data"]["risk_score"] == 75


@pytest.mark.asyncio
async def test_broadcast_event_with_valid_event_envelope() -> None:
    """Test that broadcast_event validates and preserves valid event envelope."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    payload = {"type": "event", "data": _create_valid_event_data()}
    count = await broadcaster.broadcast_event(payload)

    assert count == 1
    redis.publish.assert_awaited_once()
    channel, published = redis.publish.await_args.args
    assert channel == broadcaster.CHANNEL_NAME
    assert published["type"] == "event"
    assert published["data"]["id"] == 1


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
    """Test that _listen_for_events restarts listener after non-cancelled errors.

    Uses exponential backoff with jitter: base 1s on first retry + 10-30% jitter.
    """

    class RedisThatErrors(_FakeRedis):
        async def listen(self, _pubsub: Any) -> AsyncIterator[dict[str, Any]]:
            for _ in []:  # Make it an async generator
                yield {}
            raise RuntimeError("redis blew up")

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
    # First retry uses exponential backoff with jitter: base 1s + 10-30% jitter
    # Expected range: 1.1 to 1.3 seconds
    assert len(sleep_calls) == 1
    assert 1.0 <= sleep_calls[0] <= 1.4, f"Expected ~1.1-1.3s with jitter, got {sleep_calls[0]}"
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
        for _ in []:  # Empty async generator
            yield {}

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
            await asyncio.sleep(0.5)  # cancelled - task is cancelled by stop()
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
        await asyncio.sleep(0.5)  # cancelled - task is cancelled immediately after creation

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

    # Use valid event data to pass validation, then fail on publish
    valid_payload = {"type": "event", "data": _create_valid_event_data()}

    with pytest.raises(RuntimeError, match="Publish failed"):
        await broadcaster.broadcast_event(valid_payload)

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
            for _ in []:  # Make it an async generator
                yield {}
            raise asyncio.CancelledError()

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
        for _ in []:  # Empty async generator
            yield {}

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
        for _ in []:  # Empty async generator
            yield {}

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
        for _ in []:  # Empty async generator
            yield {}

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
            for _ in []:  # Make it an async generator
                yield {}
            raise RuntimeError("redis error")

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
            for _ in []:  # Make it an async generator
                yield {}
            raise RuntimeError("redis error")

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

    # First retry uses exponential backoff with jitter: base 1s + 10-30% jitter
    # Expected range: 1.1 to 1.3 seconds
    assert len(sleep_calls) == 1
    assert 1.0 <= sleep_calls[0] <= 1.4, f"Expected ~1.1-1.3s with jitter, got {sleep_calls[0]}"
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
        for _ in []:  # Empty async generator
            yield {}

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
        for _ in []:  # Empty async generator
            yield {}

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


# ==============================================================================
# Tests for WebSocket Message Validation (Acceptance Criteria 2, 4, 5)
# ==============================================================================


@pytest.mark.asyncio
async def test_broadcast_event_validates_valid_message() -> None:
    """Test that broadcast_event validates and accepts valid event messages.

    Acceptance Criteria 5: Test that valid messages pass validation.
    """
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    # Valid event with all required fields
    valid_data = _create_valid_event_data(
        id=42,
        event_id=42,
        batch_id="batch_abc",
        camera_id="cam-123",
        risk_score=85,
        risk_level="critical",
        summary="Critical event detected",
        started_at="2025-12-30T10:00:00",
    )
    payload = {"type": "event", "data": valid_data}

    count = await broadcaster.broadcast_event(payload)

    assert count == 1
    redis.publish.assert_awaited_once()
    _, published = redis.publish.await_args.args
    assert published["type"] == "event"
    assert published["data"]["id"] == 42
    assert published["data"]["risk_level"] == "critical"


@pytest.mark.asyncio
async def test_broadcast_event_validates_all_risk_levels() -> None:
    """Test that broadcast_event accepts all valid risk levels."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    for risk_level in ["low", "medium", "high", "critical"]:
        redis.publish.reset_mock()
        payload = {"type": "event", "data": _create_valid_event_data(risk_level=risk_level)}
        count = await broadcaster.broadcast_event(payload)
        assert count == 1
        _, published = redis.publish.await_args.args
        assert published["data"]["risk_level"] == risk_level


@pytest.mark.asyncio
async def test_broadcast_event_validates_risk_score_bounds() -> None:
    """Test that broadcast_event accepts risk scores within valid bounds (0-100)."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    # Test minimum bound
    payload = {"type": "event", "data": _create_valid_event_data(risk_score=0)}
    count = await broadcaster.broadcast_event(payload)
    assert count == 1

    # Test maximum bound
    redis.publish.reset_mock()
    payload = {"type": "event", "data": _create_valid_event_data(risk_score=100)}
    count = await broadcaster.broadcast_event(payload)
    assert count == 1


@pytest.mark.asyncio
async def test_broadcast_event_rejects_invalid_message_missing_required_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that broadcast_event rejects messages missing required fields.

    Acceptance Criteria 4: Test that malformed messages are rejected.
    """
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    # Missing required fields (id, event_id, etc.)
    invalid_data = {"camera_id": "cam-123"}  # Missing most required fields
    payload = {"type": "event", "data": invalid_data}

    with pytest.raises(ValueError, match="Invalid event message format"):
        await broadcaster.broadcast_event(payload)

    assert "Event message validation failed" in caplog.text
    redis.publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_broadcast_event_rejects_invalid_risk_level(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that broadcast_event rejects messages with invalid risk level.

    Acceptance Criteria 4: Test that malformed messages are rejected.
    """
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    # Invalid risk_level value
    invalid_data = _create_valid_event_data(risk_level="super_critical")  # type: ignore[arg-type]
    payload = {"type": "event", "data": invalid_data}

    with pytest.raises(ValueError, match="Invalid event message format"):
        await broadcaster.broadcast_event(payload)

    redis.publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_broadcast_event_rejects_risk_score_out_of_bounds(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that broadcast_event rejects risk scores outside valid bounds.

    Acceptance Criteria 4: Test that malformed messages are rejected.
    """
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    # Risk score > 100
    invalid_data = _create_valid_event_data(risk_score=101)
    payload = {"type": "event", "data": invalid_data}

    with pytest.raises(ValueError, match="Invalid event message format"):
        await broadcaster.broadcast_event(payload)

    redis.publish.assert_not_awaited()

    # Risk score < 0
    redis.publish.reset_mock()
    invalid_data = _create_valid_event_data(risk_score=-1)
    payload = {"type": "event", "data": invalid_data}

    with pytest.raises(ValueError, match="Invalid event message format"):
        await broadcaster.broadcast_event(payload)


@pytest.mark.asyncio
async def test_broadcast_event_rejects_invalid_data_type(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that broadcast_event rejects messages with wrong data types.

    Acceptance Criteria 4: Test that malformed messages are rejected.
    """
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    # risk_score as string instead of int
    invalid_data = _create_valid_event_data()
    invalid_data["risk_score"] = "high"  # Should be int
    payload = {"type": "event", "data": invalid_data}

    with pytest.raises(ValueError, match="Invalid event message format"):
        await broadcaster.broadcast_event(payload)

    redis.publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_broadcast_event_accepts_nullable_started_at() -> None:
    """Test that broadcast_event accepts events with null started_at."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    # started_at is nullable
    valid_data = _create_valid_event_data(started_at=None)
    payload = {"type": "event", "data": valid_data}

    count = await broadcaster.broadcast_event(payload)

    assert count == 1
    redis.publish.assert_awaited_once()
    _, published = redis.publish.await_args.args
    assert published["data"]["started_at"] is None


@pytest.mark.asyncio
async def test_broadcast_event_normalizes_risk_level_case() -> None:
    """Test that broadcast_event normalizes risk level case (uppercase to lowercase)."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    # Test with uppercase - should be normalized to lowercase
    valid_data = _create_valid_event_data(risk_level="HIGH")
    payload = {"type": "event", "data": valid_data}

    count = await broadcaster.broadcast_event(payload)

    assert count == 1
    redis.publish.assert_awaited_once()
    _, published = redis.publish.await_args.args
    # Should be normalized to lowercase
    assert published["data"]["risk_level"] == "high"


# ==============================================================================
# Tests for Reasoning Field in WebSocket Broadcasts (bead 14lh)
# ==============================================================================


@pytest.mark.asyncio
async def test_broadcast_event_includes_reasoning_field() -> None:
    """Test that broadcast_event includes the reasoning field from Nemotron AI analysis.

    This test verifies the fix for bead 14lh: P2 bug where reasoning was missing
    from WebSocket broadcasts. The reasoning field is essential for users to understand
    why the AI assigned a particular risk score.
    """
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    # Valid event with reasoning field
    valid_data = _create_valid_event_data(
        id=42,
        event_id=42,
        batch_id="batch_abc",
        camera_id="cam-123",
        risk_score=85,
        risk_level="critical",
        summary="Suspicious activity detected",
        reasoning="Multiple unidentified individuals observed near property perimeter at unusual hours",
    )
    payload = {"type": "event", "data": valid_data}

    count = await broadcaster.broadcast_event(payload)

    assert count == 1
    redis.publish.assert_awaited_once()
    _, published = redis.publish.await_args.args

    # Verify reasoning field is present and correct
    assert "reasoning" in published["data"]
    assert (
        published["data"]["reasoning"]
        == "Multiple unidentified individuals observed near property perimeter at unusual hours"
    )


@pytest.mark.asyncio
async def test_broadcast_event_rejects_missing_reasoning_field(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that broadcast_event rejects messages missing the required reasoning field.

    The reasoning field is now required in WebSocketEventData schema.
    """
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    # Event data missing reasoning field
    invalid_data = {
        "id": 1,
        "event_id": 1,
        "batch_id": "batch_123",
        "camera_id": "cam-uuid",
        "risk_score": 75,
        "risk_level": "high",
        "summary": "Person detected",
        # reasoning field intentionally missing
        "started_at": "2025-12-23T12:00:00",
    }
    payload = {"type": "event", "data": invalid_data}

    with pytest.raises(ValueError, match="Invalid event message format"):
        await broadcaster.broadcast_event(payload)

    redis.publish.assert_not_awaited()


# ==============================================================================
# Tests for Bounded Recovery (MAX_RECOVERY_ATTEMPTS)
# ==============================================================================


@pytest.mark.asyncio
async def test_listen_for_events_recovery_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that _listen_for_events stops retrying after MAX_RECOVERY_ATTEMPTS."""
    error_count = 0

    class RedisAlwaysErrors(_FakeRedis):
        async def listen(self, _pubsub: Any) -> AsyncIterator[dict[str, Any]]:
            nonlocal error_count
            error_count += 1
            for _ in []:  # Make it an async generator
                yield {}
            raise RuntimeError("redis blew up")

    redis = RedisAlwaysErrors()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    broadcaster._pubsub = _FakePubSub()
    broadcaster._is_listening = True
    broadcaster._recovery_attempts = 0

    sleep_calls: list[float] = []

    async def _fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        # Simulate error continuing
        if len(sleep_calls) >= broadcaster.MAX_RECOVERY_ATTEMPTS:
            broadcaster._is_listening = False

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)

    # Run the listener - it should stop after MAX_RECOVERY_ATTEMPTS
    await broadcaster._listen_for_events()

    # Should have hit the max recovery attempts
    assert broadcaster._recovery_attempts <= broadcaster.MAX_RECOVERY_ATTEMPTS


@pytest.mark.asyncio
async def test_listen_for_events_recovery_resets_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that _recovery_attempts resets on successful message processing."""
    message_count = 0

    class RedisWithMessages(_FakeRedis):
        async def listen(self, _pubsub: Any) -> AsyncIterator[dict[str, Any]]:
            nonlocal message_count
            message_count += 1
            yield {"data": {"type": "event", "data": {"id": message_count}}}

    redis = RedisWithMessages()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    broadcaster._pubsub = _FakePubSub()
    broadcaster._is_listening = True
    broadcaster._recovery_attempts = 3  # Start with some recovery attempts

    broadcaster._send_to_all_clients = AsyncMock(return_value=None)  # type: ignore[method-assign]

    await broadcaster._listen_for_events()

    # Recovery attempts should be reset to 0 after successful message
    assert broadcaster._recovery_attempts == 0


@pytest.mark.asyncio
async def test_broadcaster_has_max_recovery_constant() -> None:
    """Test that EventBroadcaster has MAX_RECOVERY_ATTEMPTS constant."""
    assert hasattr(EventBroadcaster, "MAX_RECOVERY_ATTEMPTS")
    assert EventBroadcaster.MAX_RECOVERY_ATTEMPTS > 0
    assert EventBroadcaster.MAX_RECOVERY_ATTEMPTS <= 10  # Reasonable upper bound


@pytest.mark.asyncio
async def test_listen_for_events_logs_error_on_max_retries(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that error is logged when max recovery attempts reached."""

    class RedisAlwaysErrors(_FakeRedis):
        async def listen(self, _pubsub: Any) -> AsyncIterator[dict[str, Any]]:
            for _ in []:  # Make it an async generator
                yield {}
            raise RuntimeError("redis connection failed")

    redis = RedisAlwaysErrors()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    broadcaster._pubsub = _FakePubSub()
    broadcaster._is_listening = True
    # Set to one below max so next error triggers the "giving up" log
    broadcaster._recovery_attempts = broadcaster.MAX_RECOVERY_ATTEMPTS

    async def _fake_sleep(seconds: float) -> None:
        pass

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)

    await broadcaster._listen_for_events()

    # Should have logged the "giving up" message
    assert any(
        "recovery failed" in record.message.lower() or "giving up" in record.message.lower()
        for record in caplog.records
    )
    # Should have set _is_listening to False
    assert broadcaster._is_listening is False


# ==============================================================================
# Tests for Listener Supervision (wa0t.40)
# ==============================================================================


@pytest.mark.asyncio
async def test_supervise_listener_detects_dead_listener(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that supervisor detects and restarts dead listener."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    broadcaster._is_listening = True
    broadcaster._listener_healthy = True
    broadcaster._pubsub = _FakePubSub()

    # Create a done task to simulate dead listener
    async def immediate_done() -> None:
        pass

    broadcaster._listener_task = asyncio.create_task(immediate_done())
    await broadcaster._listener_task  # Let it complete

    sleep_calls: list[float] = []
    check_count = 0

    async def _fake_sleep(seconds: float) -> None:
        nonlocal check_count
        sleep_calls.append(seconds)
        check_count += 1
        # Allow one check cycle before stopping
        if check_count >= 2:
            broadcaster._is_listening = False

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)

    await broadcaster._supervise_listener()

    # Should have detected dead listener and logged it, or successfully restarted
    # (the restart creates a new task which also triggers another sleep)
    assert len(sleep_calls) >= 1
    # Either detected the problem or restarted
    detected = any("died unexpectedly" in record.message for record in caplog.records)
    restarted = any("restarting" in record.message.lower() for record in caplog.records)
    assert detected or restarted


@pytest.mark.asyncio
async def test_supervise_listener_respects_max_attempts(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that supervisor gives up after max recovery attempts."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    broadcaster._is_listening = True
    broadcaster._listener_healthy = True
    broadcaster._pubsub = _FakePubSub()
    broadcaster._recovery_attempts = broadcaster.MAX_RECOVERY_ATTEMPTS  # Already at max

    # Create a done task to simulate dead listener
    async def immediate_done() -> None:
        pass

    broadcaster._listener_task = asyncio.create_task(immediate_done())
    await broadcaster._listener_task

    async def _fake_sleep(seconds: float) -> None:
        pass  # Just continue

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)

    await broadcaster._supervise_listener()

    # Should have given up
    assert any("giving up" in record.message.lower() for record in caplog.records)
    assert broadcaster._is_listening is False


@pytest.mark.asyncio
async def test_supervise_listener_resets_recovery_on_healthy(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that supervisor resets recovery counter when listener is healthy."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    broadcaster._is_listening = True
    broadcaster._listener_healthy = True
    broadcaster._pubsub = _FakePubSub()
    broadcaster._recovery_attempts = 3  # Some previous failures

    # Create a running task that doesn't use asyncio.sleep (uses event wait instead)
    done_event = asyncio.Event()

    async def long_running() -> None:
        await done_event.wait()

    broadcaster._listener_task = asyncio.create_task(long_running())

    sleep_count = 0

    async def _fake_sleep(seconds: float) -> None:
        nonlocal sleep_count
        sleep_count += 1
        # Allow 2 sleep cycles: one for supervision interval, then stop
        # This gives the supervisor time to check the healthy listener
        if sleep_count >= 2:
            broadcaster._is_listening = False

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)

    await broadcaster._supervise_listener()

    # Should have reset recovery attempts after seeing healthy listener
    assert broadcaster._recovery_attempts == 0

    # Cleanup
    done_event.set()
    broadcaster._listener_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await broadcaster._listener_task


@pytest.mark.asyncio
async def test_is_listener_healthy() -> None:
    """Test is_listener_healthy method returns correct status."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    # Initially not listening
    assert broadcaster.is_listener_healthy() is False

    # Listening but not healthy
    broadcaster._is_listening = True
    broadcaster._listener_healthy = False
    assert broadcaster.is_listener_healthy() is False

    # Both listening and healthy
    broadcaster._listener_healthy = True
    assert broadcaster.is_listener_healthy() is True


@pytest.mark.asyncio
async def test_start_creates_supervisor_task() -> None:
    """Test that start() creates both listener and supervisor tasks."""
    redis = _FakeRedis()

    # Override listen to return immediately
    async def quick_listen(_pubsub: Any) -> AsyncIterator[dict[str, Any]]:
        for _ in []:  # Empty async generator
            yield {}

    redis.listen = quick_listen  # type: ignore[method-assign]

    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    await broadcaster.start()

    assert broadcaster._listener_task is not None
    assert broadcaster._supervisor_task is not None
    assert broadcaster._is_listening is True
    assert broadcaster._listener_healthy is True

    # Cleanup
    await broadcaster.stop()


@pytest.mark.asyncio
async def test_stop_cancels_supervisor_task() -> None:
    """Test that stop() properly cancels the supervisor task."""
    redis = _FakeRedis()

    async def quick_listen(_pubsub: Any) -> AsyncIterator[dict[str, Any]]:
        for _ in []:  # Empty async generator
            yield {}

    redis.listen = quick_listen  # type: ignore[method-assign]

    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    await broadcaster.start()

    # Store reference before stop
    supervisor_task = broadcaster._supervisor_task
    assert supervisor_task is not None

    await broadcaster.stop()

    assert broadcaster._supervisor_task is None
    assert broadcaster._listener_task is None


@pytest.mark.asyncio
async def test_supervision_interval_constant() -> None:
    """Test that SUPERVISION_INTERVAL is properly defined."""
    assert hasattr(EventBroadcaster, "SUPERVISION_INTERVAL")
    assert EventBroadcaster.SUPERVISION_INTERVAL > 0
    assert EventBroadcaster.SUPERVISION_INTERVAL <= 60  # Reasonable upper bound


# ==============================================================================
# Tests for Degraded Mode Fallback (bead 5smq)
# ==============================================================================


@pytest.mark.asyncio
async def test_broadcaster_initializes_with_degraded_false() -> None:
    """Test that broadcaster initializes with _is_degraded set to False."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    assert broadcaster._is_degraded is False
    assert broadcaster.is_degraded() is False


@pytest.mark.asyncio
async def test_is_degraded_method() -> None:
    """Test the is_degraded() public method."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    # Initially not degraded
    assert broadcaster.is_degraded() is False

    # Manually set degraded
    broadcaster._is_degraded = True
    assert broadcaster.is_degraded() is True

    # Reset
    broadcaster._is_degraded = False
    assert broadcaster.is_degraded() is False


@pytest.mark.asyncio
async def test_enter_degraded_mode_sets_flags(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that _enter_degraded_mode sets appropriate flags."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    broadcaster._is_listening = True
    broadcaster._listener_healthy = True
    broadcaster._is_degraded = False

    broadcaster._enter_degraded_mode()

    # Check all flags are set correctly
    assert broadcaster._is_degraded is True
    assert broadcaster._is_listening is False
    assert broadcaster._listener_healthy is False


@pytest.mark.asyncio
async def test_enter_degraded_mode_logs_critical_alert(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that _enter_degraded_mode logs a CRITICAL level alert."""
    caplog.set_level(logging.CRITICAL)

    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    broadcaster._enter_degraded_mode()

    # Check for CRITICAL log level
    critical_logs = [r for r in caplog.records if r.levelno == logging.CRITICAL]
    assert len(critical_logs) >= 1

    # Check for key phrases in the critical message
    critical_message = critical_logs[0].message
    assert "CRITICAL" in critical_message
    assert "DEGRADED MODE" in critical_message
    assert "recovery attempts" in critical_message.lower()
    assert "Manual intervention required" in critical_message


@pytest.mark.asyncio
async def test_listen_for_events_enters_degraded_mode_after_max_retries(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that _listen_for_events enters degraded mode after max retries."""
    caplog.set_level(logging.CRITICAL)

    class RedisAlwaysErrors(_FakeRedis):
        async def listen(self, _pubsub: Any) -> AsyncIterator[dict[str, Any]]:
            for _ in []:  # Make it an async generator
                yield {}
            raise RuntimeError("redis connection failed")

    redis = RedisAlwaysErrors()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    broadcaster._pubsub = _FakePubSub()
    broadcaster._is_listening = True
    # Set to one below max so next error triggers degraded mode
    broadcaster._recovery_attempts = broadcaster.MAX_RECOVERY_ATTEMPTS

    async def _fake_sleep(seconds: float) -> None:
        pass

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)

    await broadcaster._listen_for_events()

    # Should have entered degraded mode
    assert broadcaster.is_degraded() is True
    assert broadcaster._is_listening is False
    assert broadcaster._listener_healthy is False

    # Check for CRITICAL log
    critical_logs = [r for r in caplog.records if r.levelno == logging.CRITICAL]
    assert len(critical_logs) >= 1


@pytest.mark.asyncio
async def test_supervise_listener_enters_degraded_mode_after_max_retries(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that supervisor enters degraded mode after max recovery attempts."""
    caplog.set_level(logging.CRITICAL)

    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    broadcaster._is_listening = True
    broadcaster._listener_healthy = True
    broadcaster._pubsub = _FakePubSub()
    broadcaster._recovery_attempts = broadcaster.MAX_RECOVERY_ATTEMPTS  # Already at max

    # Create a done task to simulate dead listener
    async def immediate_done() -> None:
        pass

    broadcaster._listener_task = asyncio.create_task(immediate_done())
    await broadcaster._listener_task

    async def _fake_sleep(seconds: float) -> None:
        pass

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)

    await broadcaster._supervise_listener()

    # Should have entered degraded mode
    assert broadcaster.is_degraded() is True
    assert broadcaster._is_listening is False

    # Check for CRITICAL log
    critical_logs = [r for r in caplog.records if r.levelno == logging.CRITICAL]
    assert len(critical_logs) >= 1


@pytest.mark.asyncio
async def test_start_clears_degraded_mode() -> None:
    """Test that start() clears degraded mode on successful start."""
    redis = _FakeRedis()

    async def quick_listen(_pubsub: Any) -> AsyncIterator[dict[str, Any]]:
        for _ in []:  # Empty async generator
            yield {}

    redis.listen = quick_listen  # type: ignore[method-assign]

    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    # Simulate previous degraded state
    broadcaster._is_degraded = True

    await broadcaster.start()

    # Degraded mode should be cleared
    assert broadcaster.is_degraded() is False
    assert broadcaster._is_listening is True

    # Cleanup
    await broadcaster.stop()


@pytest.mark.asyncio
async def test_degraded_mode_does_not_prevent_stop() -> None:
    """Test that stop() works correctly when in degraded mode."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    # Manually set degraded state
    broadcaster._is_degraded = True
    broadcaster._is_listening = False
    broadcaster._listener_healthy = False

    # Stop should work without error
    await broadcaster.stop()

    # Degraded flag is not cleared by stop (intentional - for debugging)
    # The important thing is no exception is raised
    assert broadcaster._listener_task is None
    assert broadcaster._supervisor_task is None


@pytest.mark.asyncio
async def test_enter_degraded_mode_is_idempotent() -> None:
    """Test that calling _enter_degraded_mode multiple times is safe."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    broadcaster._is_listening = True

    # Call multiple times
    broadcaster._enter_degraded_mode()
    broadcaster._enter_degraded_mode()
    broadcaster._enter_degraded_mode()

    # Should still be in degraded mode
    assert broadcaster.is_degraded() is True
    assert broadcaster._is_listening is False


@pytest.mark.asyncio
async def test_degraded_mode_health_check_integration() -> None:
    """Test that is_degraded and is_listener_healthy work together correctly."""
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]

    # Initial state
    assert broadcaster.is_degraded() is False
    assert broadcaster.is_listener_healthy() is False  # Not started yet

    # Enter degraded mode
    broadcaster._enter_degraded_mode()

    # Both should reflect the degraded state
    assert broadcaster.is_degraded() is True
    assert broadcaster.is_listener_healthy() is False
