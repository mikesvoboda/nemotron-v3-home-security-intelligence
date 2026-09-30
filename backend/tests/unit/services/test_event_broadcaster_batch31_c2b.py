# TARGET-MODULE: backend.services.event_broadcaster
"""Batch-31 kill battery C2b: supervision loop + WebSocket send machinery.

Covers ``_supervise_listener`` (26), ``_handle_dead_listener`` (25),
``_handle_healthy_listener`` (8), ``_send_to_all_clients`` (13),
``_send_to_single_client`` (2) and ``_resubscribe_for_supervisor`` (2).
Log asserts pin WHOLE formatted messages by equality; supervisor loops run
as tasks with a recording/blocked patched asyncio.sleep so the iteration
count and the SUPERVISION_INTERVAL constant are pinned by the recorded
delays list.

Honesty ledger (measured by the FINAL sweep: RED=74 GREEN=2 of the 76 keys
installed at sweep time, plus 2 keys added to the pool afterwards).

The two sweep greens, each argued against the shipped def:
``_supervise_listener__mutmut_7`` and ``__mutmut_13`` (``break`` -> ``return``
at both loop exits): the ``while`` is the LAST statement inside the ``try`` --
there is no ``else`` and no tail code -- so both spellings run the same
``except`` arms and the same ``finally`` INFO line
("Listener supervision task stopped") and return ``None``.

``_send_to_all_clients__mutmut_8`` and ``__mutmut_25`` are bank survivors too,
but they entered this battery's pool only after the final sweep ran, so their
disposition here is argued, not swept:
``__mutmut_8`` (``message_str = json.dumps(event_data)`` -> ``json.dumps(None)``):
``message_str`` is read ONLY on the ``message_dict is None`` arm of the
prepared-cache loop, and the only way to reach that arm from the non-string
branch is ``event_data is None`` (a str payload goes through ``json.loads`` and
a non-str payload makes ``message_dict = event_data`` truthy) -- and there
``json.dumps(event_data)`` IS ``json.dumps(None)``.
``__mutmut_25`` (trailing comma after ``track_stats=True``): the comma DELETES
the kwarg, and ``prepare_message_with_format``'s own default for that knob is
``True`` -- verified this session via ``inspect.signature``:
``(message, *, format=JSON, threshold=None, level=None, track_stats=True)`` --
so the mutant makes the identical call.

CORRECTION, kept because it is how two of these were first mis-graded: an
earlier draft of this ledger also listed ``_send_to_all_clients__mutmut_6`` and
``__mutmut_23`` as equivalent, with the two arguments above. BOTH are wrong --
the final sweep takes them RED (killed by
``test_send_all_clients_json_exact_and_stats_tracked`` and
``test_send_all_clients_msgpack_format_bytes_exact``) and the bank agrees
(exit 1). ``_23``'s trailing comma sits after ``format=client_format``, which
deletes ``track_stats=True`` on the ``message_dict is not None`` arm where the
stats call is observable; the ``track_stats``-default equivalence only holds for
``_25``, whose comma sits after the kwarg itself. Diff-shape reasoning about
which kwarg a trailing comma drops is not a substitute for the sweep.

Every other key in this battery's pool goes red.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

_ROOT = str(Path.cwd())
if (Path(_ROOT) / "backend" / "services" / "event_broadcaster.py").is_file():
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)

from backend.core.websocket.compression import (  # noqa: E402
    SerializationFormat,
    get_compression_stats,
)
from backend.core.websocket_circuit_breaker import WebSocketCircuitState  # noqa: E402
from backend.services import event_broadcaster as eb  # noqa: E402
from backend.services.event_broadcaster import EventBroadcaster  # noqa: E402

CHANNEL = "b31:chan"


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


class FakeRedis:
    def __init__(self, *, subscribe_fails: bool = False) -> None:
        self.subscribed: list[Any] = []
        self._subscribe_fails = subscribe_fails

    async def subscribe(self, channel: Any) -> object:
        self.subscribed.append(channel)
        if self._subscribe_fails:
            raise RuntimeError("redis dead")
        return object()


class FakeWS:
    def __init__(self) -> None:
        self.text: list[Any] = []
        self.raw: list[Any] = []
        self.closed = 0

    async def accept(self) -> None:
        pass

    async def close(self) -> None:
        self.closed += 1

    async def send_text(self, s: Any) -> None:
        self.text.append(s)

    async def send_bytes(self, b: Any) -> None:
        self.raw.append(b)


class BadWS(FakeWS):
    async def send_text(self, s: Any) -> None:
        raise RuntimeError("client gone")

    async def send_bytes(self, b: Any) -> None:
        raise RuntimeError("client gone")


def _broadcaster(redis: Any | None = None) -> EventBroadcaster:
    return EventBroadcaster(redis or FakeRedis(), channel_name=CHANNEL)


_REAL_SLEEP = asyncio.sleep  # captured before any SleepRecorder patches it


def _run(coro: Any) -> Any:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class SleepRecorder:
    """Patch asyncio.sleep to record delays and return immediately."""

    def __init__(self, *, block: bool = False) -> None:
        self.delays: list[Any] = []
        self._orig: Any = None
        self._block = block

    def __enter__(self) -> SleepRecorder:
        self._orig = asyncio.sleep
        outer = self

        async def _fake(t: Any, *_args: Any, **_kwargs: Any) -> None:
            outer.delays.append(t)
            if outer._block:
                await asyncio.Event().wait()
            else:
                await outer._orig(0)

        asyncio.sleep = _fake
        return self

    def __exit__(self, *exc: object) -> None:
        asyncio.sleep = self._orig


# --- _supervise_listener ------------------------------------------------------
def test_supervise_healthy_iteration_exact() -> None:
    # alive listener task -> _handle_healthy_listener once, one sleep at the
    # EXACT SUPERVISION_INTERVAL, then _is_listening flips (spy) and the
    # loop's guard breaks. Whole-text pins on the start/stop INFO lines.
    b = _broadcaster()
    b._is_listening = True
    calls: list[str] = []

    async def _healthy() -> None:
        calls.append("healthy")
        b._is_listening = False  # end the loop after one iteration

    async def _dead() -> bool:
        calls.append("dead")
        return True

    b._handle_healthy_listener = _healthy  # type: ignore[method-assign]
    b._handle_dead_listener = _dead  # type: ignore[method-assign]

    async def _go() -> None:
        async def _alive() -> None:
            await asyncio.Event().wait()

        b._listener_task = asyncio.create_task(_alive())
        task = asyncio.create_task(b._supervise_listener())
        with LogCapture() as cap, SleepRecorder() as sl:
            await asyncio.wait_for(task, timeout=5)
            sl_ref.append(sl)
            cap_ref.append(cap)
        b._listener_task.cancel()
        try:
            await b._listener_task
        except asyncio.CancelledError:
            pass

    sl_ref: list[Any] = []
    cap_ref: list[Any] = []
    _run(_go())
    assert calls == ["healthy"]  # kills listener_alive polarity family _8-_11
    assert sl_ref[0].delays == [30.0]
    assert cap_ref[0].texts() == [
        "Listener supervision task started",
        "Listener supervision task stopped",
    ], cap_ref[0].texts()


def test_supervise_dead_listener_breaks_loop() -> None:
    # done listener task -> _handle_dead_listener returns True -> loop breaks
    # (mutant _12 should_break=None keeps looping: more sleeps recorded).
    b = _broadcaster()
    b._is_listening = True
    calls: list[str] = []

    async def _healthy() -> None:
        calls.append("healthy")

    async def _dead() -> bool:
        calls.append("dead")
        return True

    b._handle_healthy_listener = _healthy  # type: ignore[method-assign]
    b._handle_dead_listener = _dead  # type: ignore[method-assign]

    async def _go() -> None:
        done = asyncio.create_task(asyncio.sleep(0))
        await asyncio.sleep(0)  # finish it: task.done() True
        b._listener_task = done
        task = asyncio.create_task(b._supervise_listener())
        with LogCapture() as cap, SleepRecorder() as sl:
            await asyncio.wait_for(task, timeout=5)
            sl_ref.append(sl)
            cap_ref.append(cap)

    sl_ref: list[Any] = []
    cap_ref: list[Any] = []
    _run(_go())
    assert calls == ["dead"]
    assert sl_ref[0].delays == [30.0]  # exactly one iteration
    assert cap_ref[0].texts() == [
        "Listener supervision task started",
        "Listener supervision task stopped",
    ]


def test_supervise_cancelled_and_unexpected_errors_exact() -> None:
    b = _broadcaster()
    b._is_listening = True

    async def _go_cancel() -> None:
        task = asyncio.create_task(b._supervise_listener())
        await _REAL_SLEEP(0)
        await _REAL_SLEEP(0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    with SleepRecorder(block=True):
        with LogCapture() as cap:
            _run(_go_cancel())
    assert cap.texts() == [
        "Listener supervision task started",
        "Listener supervision task cancelled",
        "Listener supervision task stopped",
    ], cap.texts()

    # unexpected error inside the loop: exact ERROR text + exc_info payload
    async def _boom() -> None:
        raise RuntimeError("handler exploded")

    b2 = _broadcaster()
    b2._is_listening = True
    b2._handle_healthy_listener = _boom  # type: ignore[method-assign]

    async def _alive_coro() -> None:
        await asyncio.Event().wait()

    async def _go_error() -> None:
        b2._listener_task = asyncio.create_task(_alive_coro())
        task = asyncio.create_task(b2._supervise_listener())
        with SleepRecorder(), LogCapture() as cap2:
            await asyncio.wait_for(task, timeout=5)
            cap_ref.append(cap2)
        b2._listener_task.cancel()
        try:
            await b2._listener_task
        except asyncio.CancelledError:
            pass

    cap_ref: list[Any] = []
    _run(_go_error())
    rec = cap_ref[0].one(logging.ERROR, "Unexpected error in supervisor task")
    assert rec.getMessage() == "Unexpected error in supervisor task: handler exploded"
    assert rec.exc_info is not None and str(rec.exc_info[1]) == "handler exploded"
    assert cap_ref[0].texts()[-1] == "Listener supervision task stopped"


# --- _handle_healthy_listener -------------------------------------------------
def test_handle_healthy_resets_only_when_attempts_positive() -> None:
    b = _broadcaster()
    b._listener_healthy = False
    _run(b._handle_healthy_listener())
    assert b._listener_healthy is True
    assert b.circuit_breaker._total_successes == 1
    assert b._recovery_attempts == 0

    b._listener_healthy = False
    b._recovery_attempts = 1
    with LogCapture() as cap:
        _run(b._handle_healthy_listener())
    assert b._listener_healthy is True
    assert b._recovery_attempts == 0  # reset happened at attempts == 1
    assert [t for t in cap.texts() if t.startswith("Listener recovered")] == [
        "Listener recovered successfully, resetting recovery counter"
    ]

    # attempts == 0: NO reset log (kills `>= 0` always-true mutant)
    b._recovery_attempts = 0
    with LogCapture() as cap2:
        _run(b._handle_healthy_listener())
    assert [t for t in cap2.texts() if t.startswith("Listener recovered")] == []


# --- _handle_dead_listener ------------------------------------------------------
def test_dead_listener_breaker_open_blocks_and_degrades() -> None:
    b = _broadcaster()
    b._is_listening = True
    b.circuit_breaker._state = WebSocketCircuitState.OPEN
    degraded_calls: list[int] = []

    async def _spy_degraded() -> None:
        degraded_calls.append(1)

    b._broadcast_degraded_state = _spy_degraded  # type: ignore[method-assign]
    with LogCapture() as cap:
        stop = _run(b._handle_dead_listener())
    assert stop is True  # kills _10 return True -> False
    assert b._is_degraded is True
    assert degraded_calls == [1]
    assert b.circuit_breaker._total_failures == 1  # record_failure happened
    assert cap.texts()[0] == ("Listener task died unexpectedly. Recovery attempts: 0/5"), (
        cap.texts()
    )
    err = cap.one(logging.ERROR, "circuit breaker is OPEN")
    assert err.getMessage() == (
        "Supervisor: circuit breaker is OPEN - recovery blocked to allow system stabilization"
    ), err.getMessage()


def test_dead_listener_max_attempts_gives_up() -> None:
    b = _broadcaster()
    b._is_listening = True
    b._recovery_attempts = 5

    async def _spy_degraded() -> None:
        pass

    b._broadcast_degraded_state = _spy_degraded  # type: ignore[method-assign]
    with LogCapture() as cap:
        stop = _run(b._handle_dead_listener())
    assert stop is True  # kills _16
    assert b._is_degraded is True
    err = cap.one(logging.ERROR, "Supervisor giving up")
    assert err.getMessage() == (
        "Supervisor giving up - max recovery attempts reached. Manual intervention required."
    ), err.getMessage()
    assert b._listener_task is None  # never restarted


def test_dead_listener_recovers_with_attempt_arithmetic() -> None:
    # pre 2 -> 3: every += mutant (=1 / -=1 / +=2) changes BOTH INFO texts.
    # The restart task's coro is stubbed: on the same loop the real
    # _listen_for_events would error and cascade the attempt counter.
    b = _broadcaster()
    b._is_listening = True
    b._recovery_attempts = 2
    b._pubsub = object()  # present: resubscribe branch skipped (kills _23 on
    # the pubsub-present path via the created-task + return-False asserts)

    async def _noop_coro() -> None:
        return None

    b._listen_for_events = _noop_coro  # type: ignore[method-assign]
    state: dict[str, Any] = {}

    async def _go() -> None:
        with LogCapture() as cap:
            state["stop"] = await b._handle_dead_listener()
            state["attempts"] = b._recovery_attempts
            state["healthy"] = b._listener_healthy
            state["task"] = b._listener_task
            state["texts"] = cap.texts()
            t = b._listener_task
            if t is not None and not t.done():
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass

    _run(_go())
    assert state["stop"] is False  # kills _33
    assert state["attempts"] == 3
    assert state["healthy"] is True
    assert state["task"] is not None
    assert [t for t in state["texts"] if t.startswith("Supervisor restarting")] == [
        "Supervisor restarting listener (attempt 3)"
    ], state["texts"]
    assert [t for t in state["texts"] if t == "Supervisor successfully restarted listener"] == [
        "Supervisor successfully restarted listener"
    ]


def test_dead_listener_resubscribe_polarities() -> None:
    # pubsub MISSING + subscribe OK -> shipped skips the retry-return branch
    # and restarts (the _23 polarity mutant returns False with no task).
    r = FakeRedis()
    b = _broadcaster(r)
    b._is_listening = True

    async def _noop_coro() -> None:
        return None

    b._listen_for_events = _noop_coro  # type: ignore[method-assign]
    state: dict[str, Any] = {}

    async def _go() -> None:
        with LogCapture():
            state["stop"] = await b._handle_dead_listener()
            state["task"] = b._listener_task
            t = b._listener_task
            if t is not None and not t.done():
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass

    _run(_go())
    assert state["stop"] is False
    assert r.subscribed == [CHANNEL]  # exact channel (kills resubscribe(None))
    assert b._pubsub is not None
    assert state["task"] is not None

    # subscribe FAILS -> shipped returns False and creates NO task; the _23
    # polarity mutant would create one anyway.
    r2 = FakeRedis(subscribe_fails=True)
    b2 = _broadcaster(r2)
    b2._is_listening = True
    with LogCapture() as cap2:
        stop2 = _run(b2._handle_dead_listener())
    assert stop2 is False
    assert b2._listener_task is None
    err = cap2.one(logging.ERROR, "Failed to re-subscribe")
    assert err.getMessage() == "Failed to re-subscribe: redis dead"


# --- _resubscribe_for_supervisor ------------------------------------------------
def test_resubscribe_success_and_failure_channels_exact() -> None:
    r = FakeRedis()
    b = _broadcaster(r)
    ok = _run(b._resubscribe_for_supervisor())
    assert ok is True
    assert r.subscribed == [CHANNEL]
    assert b._pubsub is not None
    assert b.circuit_breaker._total_successes == 1

    r2 = FakeRedis(subscribe_fails=True)
    b2 = _broadcaster(r2)
    bad = _run(b2._resubscribe_for_supervisor())
    assert bad is False  # kills _4 return False -> True
    assert b2._pubsub is None
    assert b2.circuit_breaker._total_failures == 1


# --- _send_to_all_clients --------------------------------------------------------
def test_send_all_clients_json_exact_and_stats_tracked() -> None:
    event = {"type": "event", "data": {"n": 1}}
    b = _broadcaster()
    ws = FakeWS()
    b._connections.add(ws)
    stats = get_compression_stats()
    before = stats.total_messages
    _run(b._send_to_all_clients(event))
    assert ws.text == [json.dumps(event)]
    assert ws.raw == []
    # track_stats=True reaches prepare_message_with_format: the JSON path
    # bumps total_messages once per unique client format (kills the
    # track_stats None/False mutants; a dropped kwarg keeps the True default)
    assert stats.total_messages == before + 1


def test_send_all_clients_msgpack_format_bytes_exact() -> None:
    # The expected bytes come from the (unmutated) compression helper, so the
    # format-marker prefix and the msgpack body are both pinned exactly.
    from backend.core.websocket.compression import prepare_message_with_format

    event = {"type": "event", "data": {"n": 2}}
    expected, fmt = prepare_message_with_format(
        event, format=SerializationFormat.MSGPACK, track_stats=True
    )
    assert fmt is SerializationFormat.MSGPACK
    b = _broadcaster()
    mp = FakeWS()
    b._connections.add(mp)
    b._client_formats[mp] = SerializationFormat.MSGPACK
    _run(b._send_to_all_clients(event))
    assert mp.raw == [expected]
    assert mp.text == []


def test_send_all_clients_non_dict_event_serialized_via_json_dumps() -> None:
    # event_data=None takes the NON-string branch, so message_str is
    # json.dumps(None) == "null" while message_dict is None: the cache then
    # ships message_str as plain text. Kills the message_str = None mutant
    # (send_text(None) raises) and pins the json.dumps() call.
    b = _broadcaster()
    ws = FakeWS()
    b._connections.add(ws)
    _run(b._send_to_all_clients(None))
    assert ws.text == ["null"], ws.text
    assert ws.raw == []
    assert ws in b._connections  # no cleanup happened


class BroadcastAborted(BaseException):
    """A BaseException (NOT Exception): slips past ``except Exception``.

    CancelledError is unusable here because ``str(CancelledError("x"))`` is
    empty, and KeyboardInterrupt aborts the event loop itself.
    """


class CancellingWS(FakeWS):
    """Raises a BaseException the inner ``except Exception`` cannot catch."""

    async def send_text(self, s: Any) -> None:
        raise BroadcastAborted("send aborted")


def test_send_all_clients_base_exception_isolated_by_gather() -> None:
    # return_exceptions=True is the ONLY thing that keeps a BaseException
    # escaping one client from aborting the whole broadcast. A cancelled send
    # bypasses send_to_client's `except Exception`, so the _34/_36/_38
    # return_exceptions mutants (None/absent/False) re-raise out of gather —
    # while shipped logs it as an UNEXPECTED broadcast error and does NOT
    # treat the client as disconnected.
    event = {"type": "event", "data": {"n": 5}}
    b = _broadcaster()
    good, bad = FakeWS(), CancellingWS()
    b._connections.update({good, bad})
    with LogCapture() as cap:
        _run(b._send_to_all_clients(event))
    assert good.text == [json.dumps(event)], good.text
    assert bad in b._connections  # BaseException != send failure: no cleanup
    assert bad.closed == 0
    err = cap.one(logging.ERROR, "Unexpected error during concurrent broadcast")
    assert err.getMessage() == ("Unexpected error during concurrent broadcast: send aborted"), (
        err.getMessage()
    )
    assert [t for t in cap.texts() if "Cleaned up" in t] == []


def test_send_all_clients_nonjson_string_sent_verbatim() -> None:
    b = _broadcaster()
    ws = FakeWS()
    b._connections.add(ws)
    raw = "not-json-payload"
    _run(b._send_to_all_clients(raw))
    assert ws.text == [raw]


def test_send_all_clients_empty_connections_noop() -> None:
    b = _broadcaster()
    _run(b._send_to_all_clients({"x": 1}))  # must return without error


def test_send_all_clients_failed_send_cleaned_up() -> None:
    event = {"type": "x"}
    b = _broadcaster()
    good, bad = FakeWS(), BadWS()
    b._connections.update({good, bad})
    with LogCapture() as cap:
        _run(b._send_to_all_clients(event))
    assert good.text == [json.dumps(event)]
    assert bad not in b._connections  # disconnected and cleaned
    assert bad.closed == 1
    warn = cap.one(logging.WARNING, "Failed to send to WebSocket client")
    assert warn.getMessage() == "Failed to send to WebSocket client: client gone"
    info = cap.one(logging.INFO, "Cleaned up")
    assert info.getMessage() == "Cleaned up 1 disconnected clients"


def test_send_all_clients_result_loop_processes_every_result() -> None:
    # Three failing clients + one success: the results loop's `continue`
    # (success arm) must NOT become `break` (mutant _45) — a break would stop
    # at the success and leave the two later failures undisconnected. With
    # asyncio.gather preserving input order (results[i] <-> snapshot[i]) and
    # the good client FIRST, the mutant cleans up 0 of 3 while shipped cleans
    # up all 3: order-deterministic, no set-iteration luck involved.
    event = {"type": "x"}
    b = _broadcaster()
    good, bad1, bad2, bad3 = FakeWS(), BadWS(), BadWS(), BadWS()
    b._connections.update({good, bad1, bad2, bad3})
    with LogCapture() as cap:
        _run(b._send_to_all_clients(event))
    assert good.text == [json.dumps(event)]
    assert bad1 not in b._connections and bad2 not in b._connections
    assert bad3 not in b._connections
    assert (bad1.closed, bad2.closed, bad3.closed) == (1, 1, 1)
    info = cap.one(logging.INFO, "Cleaned up")
    assert info.getMessage() == "Cleaned up 3 disconnected clients"
    # the BaseException arm (_46 logger.error(None), _47 append(None),
    # _48 disconnect(None)) is covered by the isolated-abort test above;
    # here every failure is an ordinary Exception routed to cleanup.


# --- _send_to_single_client ------------------------------------------------------
def test_send_single_client_branch_matrix() -> None:
    b = _broadcaster()
    ws = FakeWS()
    # compressed bytes -> send_bytes
    assert _run(b._send_to_single_client(ws, b"payload", True)) is None
    assert ws.raw == [b"payload"]
    # UNcompressed bytes -> shipped sends NOTHING (kills _1 `and`->`or`:
    # the mutant would send_bytes here)
    assert _run(b._send_to_single_client(ws, b"raw2", False)) is None
    assert ws.raw == [b"payload"]
    # text -> send_text
    assert _run(b._send_to_single_client(ws, "hello", False)) is None
    assert ws.text == ["hello"]
    # failing client -> warning + the ws itself for cleanup
    bad = BadWS()
    with LogCapture() as cap:
        result = _run(b._send_to_single_client(bad, "hello", False))
    assert result is bad
    assert cap.texts() == ["Failed to send to WebSocket client: client gone"]
