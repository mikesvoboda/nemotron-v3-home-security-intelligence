# TARGET-MODULE: backend.services.event_broadcaster
"""Batch-31 kill battery C1: EventBroadcaster lifecycle.

Covers ``__init__`` (38 keys — the circuit-breaker kwargs + attribute-default
family, killed by whole-attribute reads), ``start`` / ``stop`` (state
transitions + exact logs + breaker effects), ``connect`` / ``disconnect``
(connection set + per-client format/ack maps + exact INFO lines with extras),
and ``record_ack`` (monotonic ACK).

Assertions read shipped values directly (breaker private counters, the client
maps, the exact log text + ``extra`` dict) so the ATTR:init-default, CB:call,
LOG:case/None and dict-mutation families all go red.

Honesty ledger (measured this session, NOT by diff-shape):
``__init____mutmut_23/24/25`` are KWARG DELETIONS, not rename artifacts — each
drops one call argument (``recovery_timeout=30.0``, ``half_open_max_calls=1``,
``success_threshold=1``). They are EQUIVALENT because
``WebSocketCircuitBreaker.__init__``'s own defaults for those three knobs are
exactly ``30.0 / 1 / 1`` (read off ``inspect.signature`` this session), so the
mutant constructs a breaker with identical private counters — which is what the
battery pins (``brk._recovery_timeout == 30.0`` etc.) and why they stay green.
An earlier draft of this file called them "pure def-rename artifacts (diff
IDENTICAL after name normalization)"; the normalized diff shows the deleted
kwargs, so that reason was wrong even though the disposition is right.
``record_ack__mutmut_7`` (``>`` -> ``>=``) is value-equivalent — the only
differing input (sequence == current) makes the mutant store the SAME value
the map already holds. Every other key in this battery's 89-key pool goes red.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Fragment lives outside the repo tree during authoring (/home/agent/runs/b31-frags);
# the sweep always runs with the repo root (or the mutant home) as cwd.
_ROOT = str(Path.cwd())
if (Path(_ROOT) / "backend" / "services" / "event_broadcaster.py").is_file():
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)

from starlette.datastructures import Headers  # noqa: E402

from backend.core.websocket.compression import SerializationFormat  # noqa: E402
from backend.core.websocket_circuit_breaker import WebSocketCircuitState  # noqa: E402
from backend.services import event_broadcaster as eb  # noqa: E402
from backend.services.event_broadcaster import EventBroadcaster  # noqa: E402

CHANNEL = "b31:chan"


def _run(coro: Any) -> Any:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


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


class FakePubSub:
    def __init__(self) -> None:
        self.closed = False


class FakeRedis:
    def __init__(self, *, subscribe_fails: bool = False) -> None:
        self.subscribed: list[str] = []
        self.unsubscribed: list[str] = []
        self._subscribe_fails = subscribe_fails

    async def subscribe(self, channel: str) -> FakePubSub:
        if self._subscribe_fails:
            raise RuntimeError("boom")
        self.subscribed.append(channel)
        return FakePubSub()

    async def unsubscribe(self, channel: str) -> None:
        self.unsubscribed.append(channel)


class FakeWS:
    # Real handshakes always carry headers (empty when the client offered no
    # subprotocols); connect() reads them to pick its B-1 echo, so the fake
    # needs the field the ASGI contract guarantees.
    headers = Headers({})

    def __init__(self) -> None:
        self.accepted = 0
        self.closed = 0
        self.text: list[str] = []

    async def accept(self, subprotocol: str | None = None) -> None:
        self.accepted += 1
        # Recorded, not ignored: B-1 passes the offered token here, so a fake
        # that drops it could not catch an accept that echoes nothing.
        self.accepted_subprotocol = subprotocol

    async def close(self) -> None:
        self.closed += 1

    async def send_text(self, s: str) -> None:
        self.text.append(s)


def _broadcaster(redis: Any | None = None) -> EventBroadcaster:
    return EventBroadcaster(redis or FakeRedis(), channel_name=CHANNEL)


def _noop_listener() -> Any:
    async def _coro() -> None:
        return None

    return _coro


# --- __init__ (38 keys) -----------------------------------------------------
def test_init_defaults_exact() -> None:
    b = _broadcaster()
    assert b.channel_name == CHANNEL
    assert b._is_listening is False
    assert b._recovery_attempts == 0
    assert b._listener_healthy is False
    assert b._is_degraded is False
    assert b._pubsub is None
    assert b._listener_task is None
    assert b._supervisor_task is None
    assert b._connections == set()
    assert b._client_acks == {}
    assert b._client_formats == {}
    assert b.current_sequence == 0
    assert list(b._message_buffer) == []
    assert b._message_buffer.maxlen == 100
    assert isinstance(b.broadcast_metrics, eb.BroadcastRetryMetrics)
    # circuit breaker kwargs are the __init__ default-attr family:
    brk = b.circuit_breaker
    assert b.get_circuit_state() is WebSocketCircuitState.CLOSED
    assert brk._failure_threshold == 5  # = MAX_RECOVERY_ATTEMPTS
    assert brk._recovery_timeout == 30.0
    assert brk._half_open_max_calls == 1
    assert brk._success_threshold == 1
    assert brk._name == "event_broadcaster"


def test_init_channel_override_and_buffer() -> None:
    # maxlen drives the ring buffer: append 101 messages, oldest is evicted.
    b = _broadcaster()
    for i in range(101):
        b._add_sequence_and_buffer({"i": i})
    assert len(b._message_buffer) == 100
    assert b._message_buffer[0]["i"] == 1
    assert b.current_sequence == 101


# --- start (20 keys) --------------------------------------------------------
def test_start_sets_state_and_logs() -> None:
    r = FakeRedis()
    b = _broadcaster(r)
    b._listen_for_events = _noop_listener()
    b._supervise_listener = _noop_listener()
    cap = LogCapture()
    mid: dict[str, Any] = {}

    async def _scenario() -> None:
        with cap:
            await b.start()
        mid["listening"] = b._is_listening
        mid["healthy"] = b._listener_healthy
        mid["degraded"] = b._is_degraded
        mid["attempts"] = b._recovery_attempts
        mid["pubsub"] = b._pubsub
        mid["alive"] = b.is_listener_healthy()
        # _15/_17 replace the create_task calls with None assignments
        mid["listener_task"] = b._listener_task is not None
        mid["supervisor_task"] = b._supervisor_task is not None
        await b.stop()  # same loop: stop() awaits the tasks start() created

    _run(_scenario())
    assert r.subscribed == [CHANNEL]
    assert mid["listening"] is True
    assert mid["healthy"] is True
    assert mid["degraded"] is False
    assert mid["attempts"] == 0
    assert mid["pubsub"] is not None
    assert mid["alive"] is True
    assert mid["listener_task"] is True
    assert mid["supervisor_task"] is True
    rec = cap.one(logging.INFO, "Event broadcaster started, listening on channel:")
    assert rec.getMessage() == f"Event broadcaster started, listening on channel: {CHANNEL}"


def test_start_already_listening_warns() -> None:
    r = FakeRedis()
    b = _broadcaster(r)
    b._is_listening = True
    with LogCapture() as cap:
        _run(b.start())
    assert r.subscribed == []  # early-return: never subscribes
    rec = cap.one(logging.WARNING, "already started")
    assert rec.getMessage() == "Event broadcaster already started", rec.getMessage()


def test_start_failure_logs_and_records_failure_and_raises() -> None:
    r = FakeRedis(subscribe_fails=True)
    b = _broadcaster(r)
    with LogCapture() as cap:
        try:
            _run(b.start())
            raise AssertionError("expected RuntimeError")
        except RuntimeError as exc:
            assert str(exc) == "boom"
    assert b._is_listening is False
    assert b.circuit_breaker._failure_count == 1
    rec = cap.one(logging.ERROR, "Failed to start event broadcaster:")
    assert rec.getMessage() == "Failed to start event broadcaster: boom"


# --- stop (23 keys) ---------------------------------------------------------
def _stop_scenario_capped(
    extra_ws: Any | None = None,
) -> tuple[EventBroadcaster, FakeRedis, FakeWS, list[str], list[str], LogCapture]:
    """Build a started broadcaster AND run stop() on the SAME event loop.

    stop() awaits tasks created by the scenario, so splitting them across
    _run() calls would await tasks belonging to a closed loop.
    """
    r = FakeRedis()
    b = _broadcaster(r)
    ws = FakeWS()
    b._connections.add(ws)
    if extra_ws is not None:
        b._connections.add(extra_ws)
    cap = LogCapture()

    async def _scenario() -> None:
        b._pubsub = await r.subscribe(CHANNEL)
        b._is_listening = True
        b._listener_task = asyncio.create_task(asyncio.sleep(60))  # cancelled by stop()
        b._supervisor_task = asyncio.create_task(asyncio.sleep(60))  # cancelled by stop()
        with cap:
            await b.stop()

    _run(_scenario())
    return b, r, ws, r.subscribed, r.unsubscribed, cap


def test_stop_full_teardown() -> None:
    b, r, ws, _sub, _unsub, cap = _stop_scenario_capped()
    assert b._is_listening is False
    assert b._listener_healthy is False
    assert b._pubsub is None
    assert b._listener_task is None
    assert b._supervisor_task is None
    assert r.unsubscribed == [CHANNEL]
    # NEM-4987 shutdown frame sent before disconnect
    assert len(ws.text) == 1
    frame = json.loads(ws.text[0])
    assert frame["type"] == "system.shutdown"
    assert frame["data"] == {"reason": "Server shutting down", "reconnect": True}
    assert ws.closed == 1
    assert b._connections == set()
    rec = cap.one(logging.INFO, "Event broadcaster stopped")
    assert rec.getMessage() == "Event broadcaster stopped", rec.getMessage()


def test_stop_tolerates_send_failure() -> None:
    # A client whose send_text raises must still be disconnected (best-effort
    # send, hard cleanup) and must not abort stop().
    class BadWS(FakeWS):
        async def send_text(self, s: str) -> None:
            raise RuntimeError("client gone")

    bad = BadWS()
    b, r, _ws, _sub, _unsub, _cap = _stop_scenario_capped(bad)
    assert bad.closed == 1
    assert b._connections == set()
    assert r.unsubscribed == [CHANNEL]


# --- connect / disconnect (5 + 1 keys) --------------------------------------
def test_connect_registers_and_logs_exact() -> None:
    b = _broadcaster()
    ws1, ws2 = FakeWS(), FakeWS()
    _run(b.connect(ws1))  # default JSON
    _run(b.connect(ws2, SerializationFormat.MSGPACK))
    assert ws1.accepted == 1
    assert ws2.accepted == 1
    assert b._connections == {ws1, ws2}
    assert b.get_client_format(ws1) is SerializationFormat.JSON
    assert b.get_client_format(ws2) is SerializationFormat.MSGPACK

    with LogCapture() as cap:
        _run(b.connect(FakeWS(), SerializationFormat.ZLIB))
    rec = cap.one(logging.INFO, "WebSocket connected. Total connections:")
    assert rec.getMessage() == "WebSocket connected. Total connections: 3"
    assert rec.format == "zlib"  # extra={"format": format.value}


def test_get_client_format_defaults_to_json_for_unregistered() -> None:
    # The DEFAULT arm of _client_formats.get: an unregistered client must get
    # JSON. Kills get_client_format__2 (default -> None) and __4 (trailing
    # comma drops the default -> 1-arg dict.get returns None). A registered
    # peer is included so a mutant that returns the default for EVERY client
    # is caught by the other assert too.
    b = _broadcaster()
    ws, other = FakeWS(), FakeWS()
    _run(b.connect(ws, SerializationFormat.MSGPACK))
    assert b.get_client_format(ws) is SerializationFormat.MSGPACK
    assert b.get_client_format(other) is SerializationFormat.JSON
    assert b.get_client_format(FakeWS()) is SerializationFormat.JSON


def test_disconnect_cleans_up_all_maps() -> None:
    b = _broadcaster()
    ws = FakeWS()
    _run(b.connect(ws, SerializationFormat.ZLIB))
    b.record_ack(ws, 7)
    with LogCapture() as cap:
        _run(b.disconnect(ws))
    assert b._connections == set()
    assert ws not in b._client_acks
    assert ws not in b._client_formats
    assert ws.closed == 1
    rec = cap.one(logging.INFO, "WebSocket disconnected. Total connections:")
    assert rec.getMessage() == "WebSocket disconnected. Total connections: 0"


# --- record_ack (2 keys) ----------------------------------------------------
def test_record_ack_monotonic_and_default_zero() -> None:
    b = _broadcaster()
    ws = FakeWS()
    assert b.get_last_ack(ws) == 0
    # first ack at exactly 1: shipped default 0 accepts it (1 > 0); the
    # .get(websocket, 1) mutant rejects it (1 > 1 is False).
    w1 = FakeWS()
    b.record_ack(w1, 1)
    assert b.get_last_ack(w1) == 1
    b.record_ack(ws, 5)
    assert b.get_last_ack(ws) == 5
    b.record_ack(ws, 3)  # lower -> ignored
    assert b.get_last_ack(ws) == 5
    b.record_ack(ws, 9)  # higher -> stored
    assert b.get_last_ack(ws) == 9
    assert b.get_last_ack(FakeWS()) == 0
