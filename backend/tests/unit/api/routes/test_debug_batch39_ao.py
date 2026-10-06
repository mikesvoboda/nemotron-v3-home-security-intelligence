"""Campaign #39 battery AO — backend/api/routes/debug.py survivor battery.

Every test is an inventory pin: each assertion was chosen against a specific
mutmut family in /home/agent/runs/c39-inventory.txt (210 survivors, 8
families).  Style follows battery AN (campaign #38): strict recording fakes,
call-sequence pins, message EQUALITY, full-observable equality on returned
models — no fragment asserts, which pass XX-wrapped twins.

Honesty LEDGER (4 keys after the battery's coverage growth renumbered the
target — keys below are the FINAL tree's; pre-run these were m11/m27 + safe
m6, adjudicated by body identity in the run-1 reconcile, KILL LOSSES 0):
  * x__get_websocket_broadcaster_status__mutmut_22
  * x__get_websocket_broadcaster_status__mutmut_38   (BIRTH: new call path)
  * x__get_websocket_broadcaster_status__mutmut_48
    All three DELETE a ``channel_name=None`` kwarg from a
    DebugWebSocketBroadcasterStatus(...) call (event-else / system-present /
    system-else).  DebugWebSocketBroadcasterStatus.channel_name is declared
    ``str | None = Field(default=None)`` (debug.py:161), so the omitted kwarg
    takes the SAME value the shipped call passes explicitly — and BOTH branch
    rows (test_websocket_present_broadcasters_full_equality,
    test_websocket_none_broadcasters_fallback_literals) pin model_dump()
    equality over ALL FIVE observables of every constructor on both paths, so
    the ledger claim is bounded by what was actually observed: the only field
    written by each deleted kwarg is a field whose shipped value equals the
    model default.
  * x__safe_recording_path__mutmut_6 ('-_' -> 'XX-_XX')
    The mutant char-set differs from shipped ONLY by the character 'X', and
    'X'.isalnum() is True — so for EVERY character c: c passes shipped's
    filter (c.isalnum() or c in "-_") iff it passes the mutant's (c.isalnum()
    or c in "XX-_XX").  The sanitizer is character-for-character identical
    under every possible recording_id; measured this session: shipped keeps
    'recX1' unchanged, proving the X-admits path the mutant depends on.

Kill-technique notes:
  * __get_redacted_config m9/m26 (trailing-comma getattr -> 2-arg getattr):
    killed with the pydantic ``del inst.field`` construction (verified on
    pydantic 2.13.5 in this sandbox: after del, hasattr() is False while
    type(inst).model_fields still lists the field).  Shipped getattr carries
    a None default and degrades; the mutant raises AttributeError that the
    function never catches.  The M38 capture that retired the del-based
    discriminator was scoped to SQLAlchemy mapped models; pydantic v2 allows
    the del, so the family is killable HERE.
  * record_pipeline_error_to_redis m4 (datetime.now(UTC) -> now(None)):
    the module attribute ``datetime`` is swapped for a recording fake that
    spans the whole call; the pin is on the tz ARGUMENT the function passes
    (must be UTC), the direct cause — not on an aggregate timestamp shape.
  * _get_recent_errors m1 (signature default limit 10 -> 11): a 12-record
    seed makes the default-call row-count the discriminator.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

import backend.api.routes.debug as dbg
from backend.api.routes.debug import (
    DebugWebSocketBroadcasterStatus,
    _get_queue_depths,
    _get_recent_errors,
    _get_redacted_config,
    _get_redis_info,
    _get_websocket_broadcaster_status,
    _get_workers_status,
    _safe_recording_path,
    record_pipeline_error_to_redis,
)
from backend.core.constants import (
    ANALYSIS_QUEUE,
    DETECTION_QUEUE,
    PIPELINE_ERRORS_KEY,
    PIPELINE_ERRORS_MAX_SIZE,
    PIPELINE_ERRORS_TTL_SECONDS,
)
from backend.core.logging import redact_sensitive_value


def run(coro: Any) -> Any:
    return asyncio.run(coro)


# =============================================================================
# Recording fakes — strict signatures (arg mutations raise TypeError, which is
# what the real redis-py client does on None/missing args), every call logged
# as an (op, *args) tuple so the call list IS the spy.
# =============================================================================


class Redis:
    """Strict recording Redis fake for the debug route helpers."""

    def __init__(
        self,
        *,
        gets: dict[str, str | None] | None = None,
        llens: dict[str, int] | None = None,
        lranges: dict[str, list[str]] | None = None,
        info: dict[str, Any] | None = None,
        channels: list[bytes | str] | None = None,
        numsub: list[tuple[bytes | str, int]] | None = None,
        raises: dict[str, Exception] | None = None,
    ) -> None:
        self.gets = gets or {}
        self.llens = llens or {}
        self.lranges = lranges or {}
        self.info_data = info
        self.channels = channels
        self.numsub = numsub
        self.raises = raises or {}
        self.calls: list[tuple[Any, ...]] = []

    def _gate(self, op: str) -> None:
        if op in self.raises:
            raise self.raises[op]

    async def get(self, key: str) -> str | None:
        self.calls.append(("get", key))
        self._gate("get")
        if not isinstance(key, str):
            msg = f"key must be str, got {type(key).__name__}"
            raise TypeError(msg)
        return self.gets.get(key)

    async def llen(self, key: str) -> int:
        self.calls.append(("llen", key))
        self._gate("llen")
        if not isinstance(key, str):
            msg = f"key must be str, got {type(key).__name__}"
            raise TypeError(msg)
        return self.llens.get(key, 0)

    async def lrange(self, key: str, start: int, stop: int) -> list[str]:
        self.calls.append(("lrange", key, start, stop))
        self._gate("lrange")
        if not isinstance(key, str) or not isinstance(start, int) or not isinstance(stop, int):
            msg = "lrange args must be (str, int, int)"
            raise TypeError(msg)
        return self.lranges.get(key, [])[start : stop + 1]

    async def lpush(self, key: str, *values: str) -> int:
        self.calls.append(("lpush", key, *values))
        self._gate("lpush")
        if not isinstance(key, str):
            msg = f"key must be str, got {type(key).__name__}"
            raise TypeError(msg)
        return len(values)

    async def ltrim(self, key: str, start: int, stop: int) -> bool:
        self.calls.append(("ltrim", key, start, stop))
        self._gate("ltrim")
        if not isinstance(key, str) or not isinstance(start, int) or not isinstance(stop, int):
            msg = "ltrim args must be (str, int, int)"
            raise TypeError(msg)
        return True

    async def expire(self, key: str, seconds: int) -> bool:
        self.calls.append(("expire", key, seconds))
        self._gate("expire")
        if not isinstance(key, str) or not isinstance(seconds, int):
            msg = "expire args must be (str, int)"
            raise TypeError(msg)
        return True

    async def info(self) -> dict[str, Any]:
        self.calls.append(("info",))
        self._gate("info")
        assert self.info_data is not None
        return self.info_data

    async def pubsub_channels(self) -> list[bytes | str]:
        self.calls.append(("pubsub_channels",))
        self._gate("pubsub_channels")
        assert self.channels is not None
        return self.channels

    async def pubsub_numsub(self, *channels: str) -> list[tuple[bytes | str, int]]:
        self.calls.append(("pubsub_numsub", *channels))
        self._gate("pubsub_numsub")
        assert self.numsub is not None
        return self.numsub


class LogRec:
    """Recorder swapped in for dbg.logger; stores (level, message) tuples.

    The debug helpers log plain f-strings (no ``extra=``), so the pin is
    MESSAGE EQUALITY — logger.warning(None) twins die on it.
    """

    def __init__(self) -> None:
        self.records: list[tuple[str, Any]] = []

    def _rec(self, level: str, msg: Any, *_a: Any, **_k: Any) -> None:
        self.records.append((level, msg))

    def debug(self, msg: Any, *a: Any, **k: Any) -> None:
        self._rec("debug", msg, *a, **k)

    def info(self, msg: Any, *a: Any, **k: Any) -> None:
        self._rec("info", msg, *a, **k)

    def warning(self, msg: Any, *a: Any, **k: Any) -> None:
        self._rec("warning", msg, *a, **k)

    def error(self, msg: Any, *a: Any, **k: Any) -> None:
        self._rec("error", msg, *a, **k)


@contextlib.contextmanager
def swap(obj: Any, name: str, value: Any) -> Iterator[Any]:
    old = getattr(obj, name)
    setattr(obj, name, value)
    try:
        yield value
    finally:
        setattr(obj, name, old)


@contextlib.contextmanager
def log_cap() -> Iterator[LogRec]:
    rec = LogRec()
    with swap(dbg, "logger", rec):
        yield rec


class RecordingNow:
    """datetime stand-in that records the tz argument it was handed."""

    FIXED = datetime(2026, 10, 4, 12, 0, 0, tzinfo=UTC)

    def __init__(self) -> None:
        self.tz_args: list[Any] = []

    def now(self, tz: Any = "unset") -> datetime:
        self.tz_args.append(tz)
        return RecordingNow.FIXED


# =============================================================================
# _get_queue_depths — survivors m9, m11, m17, m19, m20
# =============================================================================


def test_queue_depths_none_redis_is_quiet_zero() -> None:
    with log_cap() as rec:
        out = run(_get_queue_depths(None))
    assert (out.detection_queue, out.analysis_queue) == (0, 0)
    assert rec.records == []


def test_queue_depths_presents_exact_keys_and_values() -> None:
    r = Redis(llens={DETECTION_QUEUE: 7, ANALYSIS_QUEUE: 3})
    with log_cap() as rec:
        out = run(_get_queue_depths(r))
    assert (out.detection_queue, out.analysis_queue) == (7, 3)
    assert r.calls == [("llen", DETECTION_QUEUE), ("llen", ANALYSIS_QUEUE)]
    assert rec.records == []


def test_queue_depths_zero_depths_stay_zero() -> None:
    # m17/m19 discriminator: `detection_depth or 0` -> `or 1` needs a FALSY
    # real depth to show the 1 leaking through.
    r = Redis(llens={DETECTION_QUEUE: 0, ANALYSIS_QUEUE: 0})
    out = run(_get_queue_depths(r))
    assert (out.detection_queue, out.analysis_queue) == (0, 0)


def test_queue_depths_failure_message_and_zeros() -> None:
    r = Redis(raises={"llen": RuntimeError("boom")})
    with log_cap() as rec:
        out = run(_get_queue_depths(r))
    assert (out.detection_queue, out.analysis_queue) == (0, 0)
    assert rec.records == [("warning", "Failed to get queue depths: boom")]


# =============================================================================
# _get_workers_status — survivors m6..m104 (55 keys)
# =============================================================================

HEARTBEAT_FW = "2026-10-04T12:00:00+00:00"
HEARTBEAT_DET = "2026-10-04T12:00:01+00:00"
HEARTBEAT_ANA = "2026-10-04T12:00:02+00:00"

DEFAULT_TRIO = {
    "file_watcher": {
        "name": "file_watcher",
        "running": False,
        "last_activity": None,
        "error_count": 0,
    },
    "detector": {"name": "detector", "running": False, "last_activity": None, "error_count": 0},
    "analyzer": {"name": "analyzer", "running": False, "last_activity": None, "error_count": 0},
}


def test_workers_none_redis_defaults_trio() -> None:
    with log_cap() as rec:
        out = run(_get_workers_status(None))
    assert out.model_dump() == DEFAULT_TRIO
    assert rec.records == []


def test_workers_present_full_equality_and_call_order() -> None:
    r = Redis(
        gets={
            "worker:file_watcher:heartbeat": HEARTBEAT_FW,
            "worker:detector:heartbeat": HEARTBEAT_DET,
            "worker:analyzer:heartbeat": HEARTBEAT_ANA,
            "worker:file_watcher:error_count": "3",
            "worker:detector:error_count": "1",
            "worker:analyzer:error_count": "7",
        }
    )
    with log_cap() as rec:
        out = run(_get_workers_status(r))
    assert out.model_dump() == {
        "file_watcher": {
            "name": "file_watcher",
            "running": True,
            "last_activity": HEARTBEAT_FW,
            "error_count": 3,
        },
        "detector": {
            "name": "detector",
            "running": True,
            "last_activity": HEARTBEAT_DET,
            "error_count": 1,
        },
        "analyzer": {
            "name": "analyzer",
            "running": True,
            "last_activity": HEARTBEAT_ANA,
            "error_count": 7,
        },
    }
    assert r.calls == [
        ("get", "worker:file_watcher:heartbeat"),
        ("get", "worker:detector:heartbeat"),
        ("get", "worker:analyzer:heartbeat"),
        ("get", "worker:file_watcher:error_count"),
        ("get", "worker:detector:error_count"),
        ("get", "worker:analyzer:error_count"),
    ]
    assert rec.records == []


def test_workers_all_absent_stay_silent_and_zero() -> None:
    # Absent-side polarity: `or True` polarity mutants crash on int(None)
    # (warning + defaults-with-error) and else->1 mutants show 1s; shipped
    # is SILENT with zeros.
    r = Redis(gets={})
    with log_cap() as rec:
        out = run(_get_workers_status(r))
    assert out.model_dump() == DEFAULT_TRIO
    assert r.calls == [
        ("get", "worker:file_watcher:heartbeat"),
        ("get", "worker:detector:heartbeat"),
        ("get", "worker:analyzer:heartbeat"),
        ("get", "worker:file_watcher:error_count"),
        ("get", "worker:detector:error_count"),
        ("get", "worker:analyzer:error_count"),
    ]
    assert rec.records == []


def test_workers_failure_message_and_default_trio() -> None:
    r = Redis(raises={"get": RuntimeError("kaboom")})
    with log_cap() as rec:
        out = run(_get_workers_status(r))
    assert out.model_dump() == DEFAULT_TRIO
    assert rec.records == [("warning", "Failed to get worker status: kaboom")]


# =============================================================================
# _get_recent_errors — survivors m1..m56 (30 keys)
# =============================================================================


def _seed_rows(n: int) -> list[str]:
    return [
        json.dumps(
            {
                "timestamp": f"2026-10-04T12:00:{i:02d}+00:00",
                "error_type": f"type{i}",
                "component": f"comp{i}",
                "message": f"msg{i}",
            }
        )
        for i in range(n)
    ]


def _expected_rows(indices: list[int]) -> list[dict[str, Any]]:
    return [
        {
            "timestamp": f"2026-10-04T12:00:{i:02d}+00:00",
            "error_type": f"type{i}",
            "component": f"comp{i}",
            "message": f"msg{i}",
        }
        for i in indices
    ]


def test_recent_errors_none_redis_is_empty() -> None:
    with log_cap() as rec:
        assert run(_get_recent_errors(None)) == []
    assert rec.records == []


def test_recent_errors_default_limit_window() -> None:
    # 12 seeded rows: shipped default limit=10 returns exactly 10 (m1 -> 11
    # returns 11); m15 start=1 drops row 0; m16/m17 widen/narrow the stop.
    rows = _seed_rows(12)
    r = Redis(lranges={PIPELINE_ERRORS_KEY: rows})
    with log_cap() as rec:
        out = run(_get_recent_errors(r))
    assert [e.model_dump() for e in out] == _expected_rows(list(range(10)))
    assert r.calls == [("lrange", PIPELINE_ERRORS_KEY, 0, 9)]
    assert rec.records == []


def test_recent_errors_explicit_limit_window() -> None:
    rows = _seed_rows(12)
    r = Redis(lranges={PIPELINE_ERRORS_KEY: rows})
    out = run(_get_recent_errors(r, 2))
    assert [e.model_dump() for e in out] == _expected_rows([0, 1])
    assert r.calls == [("lrange", PIPELINE_ERRORS_KEY, 0, 1)]


def test_recent_errors_cap_clamps_limit_to_max_size() -> None:
    r = Redis(lranges={PIPELINE_ERRORS_KEY: _seed_rows(3)})
    out = run(_get_recent_errors(r, 500))
    assert [e.model_dump() for e in out] == _expected_rows([0, 1, 2])
    assert r.calls == [("lrange", PIPELINE_ERRORS_KEY, 0, PIPELINE_ERRORS_MAX_SIZE - 1)]


def test_recent_errors_malformed_row_is_skipped_with_message() -> None:
    good = _seed_rows(2)
    bad = "not json"
    r = Redis(lranges={PIPELINE_ERRORS_KEY: [good[0], bad, good[1]]})
    try:
        json.loads(bad)
        parse_exc = "unexpected"  # pragma: no cover - bad IS invalid json
    except json.JSONDecodeError as exc:
        parse_exc = str(exc)
    with log_cap() as rec:
        out = run(_get_recent_errors(r, 10))
    assert [e.model_dump() for e in out] == _expected_rows([0, 1])
    assert rec.records == [("warning", f"Failed to parse error record: {parse_exc}")]


def test_recent_errors_absent_optionals_take_declared_defaults() -> None:
    # ABSENT-key polarity for EVERY .get default mutant (timestamp m31 None /
    # m33 2-arg / m36 "XXXX"; error_type m38/m40/m43/m44; component
    # m46/m48/m51/m52): a FULLY absent record makes all four declared defaults
    # observable in one row (first sparse-row version omitted only timestamp
    # and left the error_type/component default mutants GREEN — measured by
    # the disposition sweep).
    sparse = json.dumps({})
    r = Redis(lranges={PIPELINE_ERRORS_KEY: [sparse]})
    with log_cap() as rec:
        out = run(_get_recent_errors(r, 5))
    assert [e.model_dump() for e in out] == [
        {"timestamp": "", "error_type": "unknown", "component": "unknown", "message": None}
    ]
    assert rec.records == []


def test_recent_errors_present_message_survives_only_the_real_lookup() -> None:
    # message kwarg mutants: m25 pins None, m29 deletes the kwarg (model
    # default None), m53/m54/m55 change the lookup key — all diverge when a
    # real message is present.
    row = json.dumps({"timestamp": "ts", "error_type": "et", "component": "ec", "message": "here"})
    r = Redis(lranges={PIPELINE_ERRORS_KEY: [row]})
    out = run(_get_recent_errors(r, 5))
    assert out[0].model_dump() == {
        "timestamp": "ts",
        "error_type": "et",
        "component": "ec",
        "message": "here",
    }


def test_recent_errors_outer_failure_message_and_empty() -> None:
    r = Redis(raises={"lrange": RuntimeError("down")})
    with log_cap() as rec:
        assert run(_get_recent_errors(r, 5)) == []
    assert rec.records == [("warning", "Failed to get recent errors from Redis: down")]


# =============================================================================
# record_pipeline_error_to_redis — survivors m4..m30 (16 keys)
# =============================================================================


def test_record_error_happy_path_call_sequence_and_record() -> None:
    fake_now = RecordingNow()
    r = Redis()
    with swap(dbg, "datetime", fake_now), log_cap() as rec:
        ok = run(record_pipeline_error_to_redis(r, "conn_error", "detector", "detail"))
    assert ok is True
    assert fake_now.tz_args == [UTC]  # m4 (now(None)) dies here
    expected_record = {
        "timestamp": RecordingNow.FIXED.isoformat(),
        "error_type": "conn_error",
        "component": "detector",
        "message": "detail",
    }
    assert r.calls == [
        ("lpush", PIPELINE_ERRORS_KEY, json.dumps(expected_record)),
        ("ltrim", PIPELINE_ERRORS_KEY, 0, PIPELINE_ERRORS_MAX_SIZE - 1),
        ("expire", PIPELINE_ERRORS_KEY, PIPELINE_ERRORS_TTL_SECONDS),
    ]
    assert rec.records == []


def test_record_error_none_message_is_stored_as_none() -> None:
    fake_now = RecordingNow()
    r = Redis()
    with swap(dbg, "datetime", fake_now):
        ok = run(record_pipeline_error_to_redis(r, "t", "c"))
    assert ok is True
    stored = json.loads(r.calls[0][2])
    assert stored["message"] is None


def test_record_error_failure_returns_false_with_message() -> None:
    r = Redis(raises={"lpush": RuntimeError("nope")})
    with log_cap() as rec:
        ok = run(record_pipeline_error_to_redis(r, "t", "c", "m"))
    assert ok is False
    assert rec.records == [("warning", "Failed to record pipeline error to Redis: nope")]


# =============================================================================
# _get_redacted_config — survivors m9..m32 (12 keys)
# =============================================================================


class FakeNested(BaseModel):
    plain_inner: str = "inner-value"
    token_inner: str = "tok-value"
    absent_inner_field: str = "gone-from-instance"


class FakeSettings(BaseModel):
    # Field shapes mirror the REAL Settings (api_keys: list), and every value
    # is a placeholder the field NAME redacts — semgrep's exact-name
    # hardcoded-password rule (bare api_key/password/token assignments) has no
    # site here by construction, so no suppression comment is needed.
    plain: str = "hello"
    api_keys: list[str] = ["k-one", "k-two"]
    none_field: str | None = None
    nested: FakeNested = FakeNested()


def test_redacted_config_full_equality_over_all_observables() -> None:
    settings = FakeSettings()
    # Absent-attribute polarity for the trailing-comma getattr twins (m9 on
    # the top-level getattr, m26 on the nested one): shipped carries the None
    # default, the 2-arg mutant raises AttributeError that the function never
    # catches.  pydantic 2.13.5 del verified this sandbox-side.
    del settings.nested.absent_inner_field
    with swap(dbg, "get_settings", lambda: settings), log_cap() as rec:
        out = _get_redacted_config()
    assert out == {
        "plain": redact_sensitive_value("plain", "hello"),
        # list-valued sensitive field takes redact's ["[REDACTED]"]*len branch
        "api_keys": redact_sensitive_value("api_keys", ["k-one", "k-two"]),
        "none_field": redact_sensitive_value("none_field", None),
        "nested": {
            "plain_inner": redact_sensitive_value("plain_inner", "inner-value"),
            "token_inner": redact_sensitive_value("token_inner", "tok-value"),
            # shipped: absent instance attr -> getattr default None -> redacted
            "absent_inner_field": redact_sensitive_value("absent_inner_field", None),
        },
    }
    assert rec.records == []


def test_redacted_config_top_level_absent_attribute_kills_two_arg_getattr() -> None:
    # m9 needs a TOP-LEVEL model field missing from the instance.
    class MissingTop(BaseModel):
        present: str = "p"
        vanished: str = "v"

    settings = MissingTop()
    del settings.vanished
    with swap(dbg, "get_settings", lambda: settings):
        out = _get_redacted_config()
    assert out == {
        "present": redact_sensitive_value("present", "p"),
        "vanished": redact_sensitive_value("vanished", None),
    }


# =============================================================================
# _get_websocket_broadcaster_status — survivors m11..m32 (12 keys, ledger 2)
# =============================================================================


class CircuitState:
    def __init__(self, value: str) -> None:
        self.value = value


class EventBroadcasterFake:
    def __init__(self) -> None:
        self._connections = ["c1", "c2", "c3"]
        self._is_listening = True
        self._degraded = True
        self._state = CircuitState("HALF_OPEN")
        self.channel_name = "events:channel"

    def is_degraded(self) -> bool:
        return self._degraded

    def get_circuit_state(self) -> CircuitState:
        return self._state


class SystemBroadcasterFake:
    def __init__(self) -> None:
        self.connections = ["s1"]
        self._running = True
        self._is_degraded = False
        self._circuit_breaker = CircuitHolder("CLOSED")


class CircuitHolder:
    def __init__(self, state: str) -> None:
        self._state = CircuitState(state)

    def get_state(self) -> CircuitState:
        return self._state


def test_websocket_present_broadcasters_full_equality() -> None:
    import backend.services.event_broadcaster as eb
    import backend.services.system_broadcaster as sb

    event = EventBroadcasterFake()
    system = SystemBroadcasterFake()
    with swap(eb, "_broadcaster", event), swap(sb, "_system_broadcaster", system):
        ev, sy = _get_websocket_broadcaster_status()
    assert ev.model_dump() == {
        "connection_count": 3,
        "is_listening": True,
        "is_degraded": True,
        "circuit_state": "HALF_OPEN",
        "channel_name": "events:channel",
    }
    assert sy.model_dump() == {
        "connection_count": 1,
        "is_listening": True,
        "is_degraded": False,
        "circuit_state": "CLOSED",
        "channel_name": None,
    }


def test_websocket_none_broadcasters_fallback_literals() -> None:
    # Pins ALL FIVE else-branch observables on both statuses; kills m12..m16
    # and m28..m32.  m11/m27 (deleted channel_name=None kwarg) are the LEDGER:
    # the model default for that field IS None (debug.py:161), so no observable
    # can diverge — see the module docstring argument.
    import backend.services.event_broadcaster as eb
    import backend.services.system_broadcaster as sb

    with swap(eb, "_broadcaster", None), swap(sb, "_system_broadcaster", None):
        ev, sy = _get_websocket_broadcaster_status()
    expected = {
        "connection_count": 0,
        "is_listening": False,
        "is_degraded": False,
        "circuit_state": "UNKNOWN",
        "channel_name": None,
    }
    # BOTH statuses asserted: an only-ev assertion left the five killable
    # system-else literal mutants (m28..m32) unobserved -- the first sweep
    # measured exactly that.
    assert ev.model_dump() == expected
    assert sy.model_dump() == expected
    assert (
        DebugWebSocketBroadcasterStatus(
            connection_count=0, is_listening=False, is_degraded=False, circuit_state="UNKNOWN"
        ).model_dump()
        == expected
    )


# =============================================================================
# _get_redis_info — survivors m5..m98 (79 keys)
# =============================================================================

INFO_FULL: dict[str, Any] = {
    "redis_version": "7.4.2",
    "connected_clients": 12,
    "used_memory_human": "1.50M",
    "used_memory_peak_human": "2.25M",
    "total_connections_received": 100,
    "total_commands_processed": 900,
    "uptime_in_seconds": 5000,
}


def test_redis_info_none_redis_triple() -> None:
    with log_cap() as rec:
        assert run(_get_redis_info(None)) == ("unavailable", None, None)
    assert rec.records == []


def test_redis_info_full_row_exact_assembly() -> None:
    r = Redis(
        info=INFO_FULL,
        channels=[b"chan-a", "chan-b"],
        numsub=[(b"chan-a", 3), ("chan-b", 7)],
    )
    with log_cap() as rec:
        status, info_dict, pubsub = run(_get_redis_info(r))
    assert status == "connected"
    assert info_dict == {
        "redis_version": "7.4.2",
        "connected_clients": 12,
        "used_memory_human": "1.50M",
        "used_memory_peak_human": "2.25M",
        "total_connections_received": 100,
        "total_commands_processed": 900,
        "uptime_in_seconds": 5000,
    }
    assert pubsub == {
        "channels": ["chan-a", "chan-b"],
        "subscriber_counts": {"chan-a": 3, "chan-b": 7},
    }
    assert r.calls == [
        ("info",),
        ("pubsub_channels",),
        ("pubsub_numsub", "chan-a", "chan-b"),
    ]
    assert rec.records == []


def test_redis_info_empty_info_row_exposes_every_default() -> None:
    # Absent-key polarity for the 7 default twins (None / 2-arg get / XX /
    # UPPER / UNKNOWN variants) that a present-key row cannot see.
    r = Redis(info={}, channels=[], numsub=None)
    status, info_dict, pubsub = run(_get_redis_info(r))
    assert status == "connected"
    assert info_dict == {
        "redis_version": "unknown",
        "connected_clients": 0,
        "used_memory_human": "unknown",
        "used_memory_peak_human": "unknown",
        "total_connections_received": 0,
        "total_commands_processed": 0,
        "uptime_in_seconds": 0,
    }
    assert pubsub == {"channels": [], "subscriber_counts": {}}


def test_redis_info_pubsub_failure_falls_back_with_message() -> None:
    r = Redis(
        info=INFO_FULL,
        channels=[b"chan-a"],
        raises={"pubsub_numsub": RuntimeError("psdown")},
    )
    with log_cap() as rec:
        status, info_dict, pubsub = run(_get_redis_info(r))
    assert status == "connected"
    assert info_dict == INFO_FULL and len(info_dict) == 7
    assert pubsub == {"channels": [], "subscriber_counts": {}}
    assert rec.records == [("warning", "Failed to get pub/sub info: psdown")]


def test_redis_info_info_failure_error_tuple_and_message() -> None:
    r = Redis(raises={"info": RuntimeError("boom")})
    with log_cap() as rec:
        status, payload, extra = run(_get_redis_info(r))
    assert status == "error"
    assert payload == {"error": "boom"}
    assert extra is None
    assert rec.records == [("warning", "Failed to get Redis info: boom")]


# =============================================================================
# _safe_recording_path — survivor m6
# =============================================================================


def test_safe_recording_path_sanitizes_and_joins(tmp_path: Path) -> None:
    out = _safe_recording_path("rec-01_A", str(tmp_path))
    assert out == tmp_path / "rec-01_A.json"


def test_safe_recording_path_uppercase_x_is_alnum_so_membership_is_shadowed(
    tmp_path: Path,
) -> None:
    # LEDGER EVIDENCE for m6 ('-_' -> 'XX-_XX'): shipped KEEPS 'X' because
    # 'X'.isalnum() is True, so the mutant's enlarged membership test is
    # unreachable for every character — no id separates the two.
    out = _safe_recording_path("recX1", str(tmp_path))
    assert out == tmp_path / "recX1.json"


def test_safe_recording_path_empty_after_sanitize_is_none(tmp_path: Path) -> None:
    assert _safe_recording_path("!!! ???", str(tmp_path)) is None
