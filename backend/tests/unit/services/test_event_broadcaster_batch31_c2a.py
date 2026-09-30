# TARGET-MODULE: backend.services.event_broadcaster
"""Batch-31 kill battery C2a: the Redis listener loop + degraded mode.

Covers ``_listen_for_events`` (68 keys), ``_broadcast_degraded_state``
(24) and ``_enter_degraded_mode`` (2). A duck-typed fake redis drives the
async listen generator; ``asyncio.sleep`` is patched (recording delays) and
``random.uniform`` pinned to 0.2 so every recovery-backoff arithmetic mutant
(base/exponent/cap/jitter/+) lands on an EXACT pinned number. Log asserts
pin the ENTIRE formatted message by equality — the XXwrap / case / arg-None
log families die on that (a mutant whose whole message is ``None`` fails
``== "Starting event listener loop"``).

Honesty ledger (updated after the sweep): keys this battery leaves GREEN are
listed here with their equivalence argument — in particular
``_listen_for_events__mutmut_12`` (``break`` -> ``return`` on the
``_is_listening`` guard: both terminate the same way with no tail code) and
``_mutmut_53`` (backoff cap ``min(…, 30)`` -> ``31``: the exponent is at most
``MAX_RECOVERY_ATTEMPTS - 1 = 4``, base 16, so the cap is unreachable).
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import sys
from pathlib import Path
from typing import Any

_ROOT = str(Path.cwd())
if (Path(_ROOT) / "backend" / "services" / "event_broadcaster.py").is_file():
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)

from backend.services import event_broadcaster as eb  # noqa: E402
from backend.services.event_broadcaster import EventBroadcaster  # noqa: E402

CHANNEL = "b31:chan"
EVENT: dict[str, Any] = {"type": "event", "data": {"camera_id": "c9", "risk_score": 90}}


class _ListHandler(logging.Handler):
    def __init__(self, sink: list[logging.LogRecord]) -> None:
        super().__init__()
        self.sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        self.sink.append(record)


class LogCapture:
    def __enter__(self) -> LogCapture:
        self.records: list[logging.LogRecord] = []
        self._handler = _ListHandler(self.records)
        eb.logger.addHandler(self._handler)
        self._old_level = eb.logger.level
        eb.logger.setLevel(logging.DEBUG)
        return self

    def __exit__(self, *exc: object) -> None:
        eb.logger.removeHandler(self._handler)
        eb.logger.setLevel(self._old_level)

    def texts(self) -> list[str]:
        return [r.getMessage() for r in self.records]

    def one(self, level: int, needle: str) -> logging.LogRecord:
        hits = [r for r in self.records if r.levelno == level and needle in r.getMessage()]
        assert len(hits) == 1, f"expected one {needle!r} in {self.texts()}"
        return hits[0]


class FakeWS:
    def __init__(self) -> None:
        self.text: list[str] = []

    async def accept(self) -> None:
        pass

    async def close(self) -> None:
        pass

    async def send_text(self, s: str) -> None:
        self.text.append(s)


class FakeRedis:
    """Minimal duck-type: subscribe/unsubscribe/listen for the listener loop."""

    def __init__(self, messages: list[Any], *, raise_after: bool = False) -> None:
        self.msgs = list(messages)
        self.raise_after = raise_after
        self.listen_args: list[Any] = []

    async def subscribe(self, channel: str) -> object:
        return object()

    async def unsubscribe(self, channel: str) -> None:
        pass

    async def listen(self, pubsub: Any):
        self.listen_args.append(pubsub)
        for m in self.msgs:
            yield m
        if self.raise_after:
            raise RuntimeError("redis died")


class RecordingSleep:
    """Patch asyncio.sleep (module attr) to record requested delays."""

    def __init__(self) -> None:
        self.delays: list[Any] = []
        self._orig: Any = None

    def __enter__(self) -> RecordingSleep:
        self._orig = asyncio.sleep
        outer = self

        async def _fake(t: Any, *_args: Any, **_kwargs: Any) -> None:
            outer.delays.append(t)

        asyncio.sleep = _fake
        return self

    def __exit__(self, *exc: object) -> None:
        asyncio.sleep = self._orig


class PinnedUniform:
    """Patch random.uniform to record its bounds and return exactly 0.2."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, Any]] = []
        self._orig: Any = None

    def __enter__(self) -> PinnedUniform:
        self._orig = random.uniform
        outer = self

        def _fake(a: Any, b: Any) -> float:
            outer.calls.append((a, b))
            return 0.2

        random.uniform = _fake
        return self

    def __exit__(self, *exc: object) -> None:
        random.uniform = self._orig


def _broadcaster(redis: Any) -> EventBroadcaster:
    return EventBroadcaster(redis, channel_name=CHANNEL)


def _started(b: EventBroadcaster, *, listening: bool = True) -> None:
    b._pubsub = object()
    b._is_listening = listening


def _run_listen(b: EventBroadcaster) -> None:
    async def _go() -> None:
        task = asyncio.create_task(b._listen_for_events())
        try:
            await asyncio.wait_for(task, timeout=5)
        finally:
            for t in (b._listener_task,):
                if t is not None and not t.done():
                    t.cancel()
                    try:
                        await t
                    except asyncio.CancelledError:
                        pass

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_go())
    finally:
        loop.close()


# --- _listen_for_events: guards + happy path + flags ------------------------
def test_listen_requires_pubsub_exact_error() -> None:
    b = _broadcaster(FakeRedis([]))
    with LogCapture() as cap:
        _run_listen(b)
    assert cap.texts() == ["Cannot listen for events: pubsub not initialized"]


def test_listen_happy_path_flags_logs_and_delivery() -> None:
    r = FakeRedis([{"type": "message", "data": EVENT}])
    b = _broadcaster(r)
    _started(b)
    ws = FakeWS()
    b._connections.add(ws)
    with LogCapture() as cap:
        _run_listen(b)
    assert r.listen_args == [b._pubsub]  # listen(self._pubsub)
    assert [t for t in cap.texts() if t == "Starting event listener loop"] == [
        "Starting event listener loop"
    ]
    assert [t for t in cap.texts() if t == f"Received event from Redis: {EVENT}"] == [
        f"Received event from Redis: {EVENT}"
    ]
    # loop drains: _is_listening was True every iteration, loop ended by StopAsyncIteration
    assert b._is_listening is True
    assert b._recovery_attempts == 0
    assert b.circuit_breaker._total_successes == 1  # record_success per message
    assert b._listener_task is None  # no recovery happened
    assert b.current_sequence == 1
    assert len(b._message_buffer) == 1
    # delivery: JSON-format client receives exactly the sequenced payload
    assert ws.text == [json.dumps(b._message_buffer[0])]
    sent = json.loads(ws.text[0])
    assert sent["sequence"] == 1
    assert sent["requires_ack"] is True  # risk_score 90 >= 80
    assert sent["data"] == EVENT["data"]


def test_listen_stops_when_not_listening_and_skips_empty_data() -> None:
    # _is_listening False: first message breaks the loop immediately ->
    # NO record_success, NO debug line, nothing delivered.
    r = FakeRedis([{"type": "message", "data": EVENT}])
    b = _broadcaster(r)
    _started(b, listening=False)
    ws = FakeWS()
    b._connections.add(ws)
    with LogCapture() as cap:
        _run_listen(b)
    assert b.circuit_breaker._total_successes == 0
    assert [t for t in cap.texts() if t.startswith("Received event")] == []
    assert ws.text == []

    # data falsy: continue (NOT break) — a FOLLOW-UP good message still
    # processes (kills _continue->break and the not-event_data polarity).
    r2 = FakeRedis(
        [
            {"type": "message", "data": None},
            {"type": "message", "data": {}},
            {"type": "message", "data": EVENT},
        ]
    )
    b2 = _broadcaster(r2)
    _started(b2)
    with LogCapture():
        _run_listen(b2)
    assert b2.circuit_breaker._total_successes == 3  # per-message, even skipped ones
    assert b2.current_sequence == 1  # only the good one sequenced
    assert len(b2._message_buffer) == 1


# --- recovery paths ----------------------------------------------------------
def test_listen_backoff_first_attempt_exact_arithmetic() -> None:
    # attempts 0->1: base=min(2**0,30)=1.0, jitter bounds pinned to (0.1,0.3)
    # returning 0.2 -> backoff 1.2. The restart task then runs on the same
    # loop (its listen raises at once): attempt 2 -> 2.4, and its restart
    # task is cancelled before running. The WHOLE restart-log list is
    # pinned -> attempt number, format and every arithmetic constant.
    r = FakeRedis([], raise_after=True)
    b = _broadcaster(r)
    _started(b)
    with LogCapture() as cap, RecordingSleep() as sl, PinnedUniform() as ju:
        _run_listen(b)
    assert sl.delays == [1.2, 2.4]
    assert ju.calls == [(0.1, 0.3), (0.1, 0.3)]
    assert b._recovery_attempts == 2
    assert [t for t in cap.texts() if t.startswith("Restarting event listener")] == [
        "Restarting event listener after error (attempt 1/5) in 1.2s",
        "Restarting event listener after error (attempt 2/5) in 2.4s",
    ]
    assert b._is_degraded is False
    # the restart ran as a task (kills _66 None / _67 create_task(None))
    assert b._listener_task is not None
    # the listener-error ERROR text itself (kills _34 logger.error(None)):
    assert [t for t in cap.texts() if t.startswith("Error in event listener")] == [
        "Error in event listener: redis died",
        "Error in event listener: redis died",
    ]


def test_listen_boundary_attempts_equal_max_backs_off() -> None:
    # pre 4 -> 5 == MAX: shipped <= takes the BACKOFF branch (base
    # 2**4=16 -> 19.2); the _43 `<` mutant gives up instead (no sleep).
    # The cascade round then hits attempt 6 -> exhausted -> degraded.
    r = FakeRedis([], raise_after=True)
    b = _broadcaster(r)
    _started(b)
    b._recovery_attempts = 4
    with LogCapture() as cap, RecordingSleep() as sl, PinnedUniform():
        _run_listen(b)
    assert sl.delays == [19.2]
    assert [t for t in cap.texts() if t.startswith("Restarting event listener")] == [
        "Restarting event listener after error (attempt 5/5) in 19.2s"
    ]
    assert [t for t in cap.texts() if t.startswith("Event listener recovery failed")] == [
        "Event listener recovery failed after 5 attempts. Giving up - manual restart required."
    ]
    assert b._is_degraded is True


def test_listen_exhausted_attempts_enters_degraded_and_notifies() -> None:
    # pre 5 -> 6 > MAX: give-up ERROR (exact), degraded flags, CRITICAL alert,
    # degraded-state broadcast, NO restart task.
    r = FakeRedis([], raise_after=True)
    b = _broadcaster(r)
    _started(b)
    b._recovery_attempts = 5
    with LogCapture() as cap:
        _run_listen(b)
    err = cap.one(logging.ERROR, "Event listener recovery failed after")
    assert err.getMessage() == (
        "Event listener recovery failed after 5 attempts. Giving up - manual restart required."
    ), err.getMessage()
    assert b._is_degraded is True
    assert b._is_listening is False
    assert b._listener_healthy is False
    crit = cap.one(logging.CRITICAL, "DEGRADED MODE")
    assert crit.getMessage() == (
        "CRITICAL: EventBroadcaster has entered DEGRADED MODE after exhausting all 5 "
        "recovery attempts. Real-time event broadcasting is UNAVAILABLE. "
        "WebSocket clients will not receive live updates. "
        "Manual intervention required to restore functionality. "
        "Check Redis connectivity and restart the service."
    ), crit.getMessage()
    assert b._listener_task is None


def test_listen_breaker_open_blocks_recovery() -> None:
    # force OPEN + no recovery window: is_call_permitted False -> exact OPEN
    # ERROR, degraded, degraded-state, no sleep/restart.
    from backend.core.websocket_circuit_breaker import WebSocketCircuitState

    r = FakeRedis([], raise_after=True)
    b = _broadcaster(r)
    _started(b)
    b.circuit_breaker._state = WebSocketCircuitState.OPEN
    with LogCapture() as cap, RecordingSleep() as sl:
        _run_listen(b)
    assert sl.delays == []
    assert cap.one(logging.ERROR, "circuit breaker is OPEN").getMessage() == (
        "Event listener circuit breaker is OPEN - recovery blocked to allow system stabilization"
    )
    assert b._is_degraded is True
    assert b._listener_task is None


def test_listen_send_failure_logged_with_exc_info_and_continues() -> None:
    # one bad client + one good: shipped catches per-send failure (inner
    # except in _send_to_all_clients), delivers to the good one, and the
    # listen-loop's own except stays silent (no "Failed to broadcast event").
    r = FakeRedis([{"type": "message", "data": EVENT}])
    b = _broadcaster(r)
    _started(b)

    class BadWS(FakeWS):
        async def send_text(self, s: str) -> None:
            raise RuntimeError("client gone")

    bad, good = BadWS(), FakeWS()
    b._connections.update({bad, good})
    with LogCapture() as cap:
        _run_listen(b)
    assert len(good.text) == 1
    assert [t for t in cap.texts() if t.startswith("Failed to broadcast event")] == []
    assert any("Failed to send to WebSocket client" in t for t in cap.texts())

    # the loop's OWN broadcast except: blow up _send_to_all_clients itself ->
    # exact ERROR text + exc_info carries the RuntimeError + loop keeps
    # processing the NEXT message.
    r2 = FakeRedis([{"type": "message", "data": EVENT}, {"type": "message", "data": EVENT}])
    b2 = _broadcaster(r2)
    _started(b2)

    async def boom(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("send all broke")

    b2._send_to_all_clients = boom  # type: ignore[method-assign]
    with LogCapture() as cap2:
        _run_listen(b2)
    errs = [r for r in cap2.records if "Failed to broadcast event" in r.getMessage()]
    assert len(errs) == 2, cap2.texts()
    assert errs[0].getMessage() == (
        "Failed to broadcast event to WebSocket clients: send all broke"
    )
    assert errs[0].exc_info is not None and str(errs[0].exc_info[1]) == "send all broke"
    assert b2.current_sequence == 2  # both messages still processed


class BlockingRedis(FakeRedis):
    async def listen(self, pubsub: Any):
        self.listen_args.append(pubsub)
        await asyncio.Event().wait()  # never yields a message
        yield None


def test_listen_cancelled_logs_info() -> None:
    b = _broadcaster(BlockingRedis([]))
    _started(b)

    async def _go() -> None:
        task = asyncio.create_task(b._listen_for_events())
        await asyncio.sleep(0)
        await asyncio.sleep(0)  # let it block inside the generator await
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    with LogCapture() as cap:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_go())
        finally:
            loop.close()
    assert [t for t in cap.texts() if t == "Event listener cancelled"] == [
        "Event listener cancelled"
    ]


# --- _enter_degraded_mode direct ---------------------------------------------
def test_enter_degraded_mode_sets_flags_and_critical() -> None:
    b = _broadcaster(FakeRedis([]))
    b._is_listening = True
    b._listener_healthy = True
    with LogCapture() as cap:
        b._enter_degraded_mode()
    assert b._is_degraded is True
    assert b._is_listening is False
    assert b._listener_healthy is False
    assert len([r for r in cap.records if r.levelno == logging.CRITICAL]) == 1


# --- _broadcast_degraded_state -------------------------------------------------
def test_broadcast_degraded_state_no_connections_noop() -> None:
    b = _broadcaster(FakeRedis([]))
    with LogCapture() as cap:
        asyncio.new_event_loop().run_until_complete(b._broadcast_degraded_state())
    assert cap.texts() == []


def test_broadcast_degraded_state_payload_and_log_exact() -> None:
    r = FakeRedis([])
    b = _broadcaster(r)
    b._connections.add(FakeWS())  # empty set early-returns (guard mutant _1)
    sent: list[Any] = []

    async def spy(event_data: Any) -> None:
        sent.append(event_data)

    b._send_to_all_clients = spy  # type: ignore[method-assign]
    with LogCapture() as cap:
        asyncio.new_event_loop().run_until_complete(b._broadcast_degraded_state())
    assert sent == [
        {
            "type": "service_status",
            "data": {
                "service": "event_broadcaster",
                "status": "degraded",
                "message": (
                    "Real-time event broadcasting is degraded. Events may be delayed or unavailable."
                ),
                "circuit_state": "closed",
            },
        }
    ], sent
    assert cap.texts() == ["Broadcast degraded state notification to connected clients"]


def test_broadcast_degraded_state_swallows_send_failure() -> None:
    b = _broadcaster(FakeRedis([]))
    b._connections.add(FakeWS())

    async def boom(event_data: Any) -> None:
        raise RuntimeError("send died")

    b._send_to_all_clients = boom  # type: ignore[method-assign]
    with LogCapture() as cap:
        asyncio.new_event_loop().run_until_complete(b._broadcast_degraded_state())
    assert cap.texts() == ["Failed to broadcast degraded state: send died"]
