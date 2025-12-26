"""Unit tests for EventBroadcaster service."""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

import pytest

from backend.services.event_broadcaster import EventBroadcaster


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


@pytest.mark.asyncio
async def test_broadcast_event_wraps_missing_type() -> None:
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
async def test_start_is_idempotent_when_already_listening(caplog) -> None:
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    broadcaster._is_listening = True

    await broadcaster.start()
    assert "already started" in caplog.text
    redis.subscribe.assert_not_called()


@pytest.mark.asyncio
async def test_listen_for_events_no_pubsub_returns() -> None:
    redis = _FakeRedis()
    broadcaster = EventBroadcaster(redis)  # type: ignore[arg-type]
    broadcaster._pubsub = None

    await broadcaster._listen_for_events()
    redis.subscribe.assert_not_called()


@pytest.mark.asyncio
async def test_send_to_all_clients_removes_disconnected() -> None:
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
async def test_listen_for_events_restarts_after_error(monkeypatch) -> None:
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
