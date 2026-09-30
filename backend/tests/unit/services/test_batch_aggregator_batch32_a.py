# TARGET-MODULE: backend.services.batch_aggregator
"""Batch-32 kill battery A: BatchAggregator broadcast surface + small fns.

Covers the two functions with ZERO bank kills — ``_broadcast_detection_new``
(35/35 keys survived) and ``_broadcast_detection_batch`` (27/27) — plus
``set_gpu_monitor`` (4 surv), ``get_memory_pressure_level`` (9), ``__init__``
(4) and the two atomic-list helpers (3). 82 survivor keys.

Design notes that decide the kills:

* Both broadcast fns import ``get_broadcaster`` INSIDE the function body, so
  the battery installs a stub ``backend.services.event_broadcaster`` module into
  ``sys.modules`` for the duration of each test and restores whatever was there
  afterwards. The stub records the redis object it was handed (kills the
  ``get_broadcaster(None)`` family) and the payload it was given (kills every
  payload-dict mutation, including ``= None``). In the mutant home this also
  keeps the sweep from importing the TRAMPOLINED event_broadcaster.
* Payloads are compared key-set + ``repr`` per value (batch-31 lesson: ``==``
  is blind to str-subclass enums, and a weak comparator once ledgered 14
  killable keys as equivalent).
* Timestamps are pinned to the EXACT UTC ISO string the shipped code produces.
  ``tz=None`` / dropped-``tz=`` mutants are then caught twice over — no offset
  suffix, and this sandbox runs UTC-4 so the local shift changes the digits.
  The ``datetime.now(UTC)`` in detection.new is pinned by requiring a NON-NAIVE
  parse, which is what ``now(None)`` loses.
* The failure path is exercised too (stub raises): shipped swallows and logs one
  DEBUG with an exact message + exact ``extra`` keys/values, so the log family
  (msg=None, extra=None, extra dropped, key renames) goes red. ``logger.debug(
  extra=...)`` — the drop-the-msg mutant — raises TypeError out of the except
  block, so "must not raise" is itself a kill.
* Every global this battery touches (``ba._gpu_monitor``, the module stub) is
  restored in a finally — batch-31 proved a leaked global pin manufactures
  kill->survive regressions in OTHER modules' verdicts.

Honesty ledger: filled from the FINAL sweep of this file (see
/home/agent/runs/b32-sweep*-a.txt); anything this battery leaves green is
listed there with its equivalence argument, argued against the shipped def.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import types
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Mirror the minimum env the repo conftest sets — the trampoline sweep imports
# this file directly, so backend/tests/conftest.py does not apply. Values
# copied from backend/tests/conftest.py (setdefault: under repo pytest the
# conftest has already set them, so this is a no-op there). BatchAggregator.__init__
# calls get_settings(), which is why the import-time requirement bites here.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://security:security_dev_password@localhost:5432/security",  # pragma: allowlist secret
)
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("OTEL_ENABLED", "false")
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("PYROSCOPE_ENABLED", "false")

# Fragment lives outside the repo tree during authoring (/home/agent/runs/b32-frags);
# the sweep always runs with the repo root (or the mutant home) as cwd.
_ROOT = str(Path.cwd())
if (Path(_ROOT) / "backend" / "services" / "batch_aggregator.py").is_file():
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)

from backend.core.logging import sanitize_log_value  # noqa: E402
from backend.services import batch_aggregator as ba  # noqa: E402
from backend.services.batch_aggregator import BatchAggregator  # noqa: E402

EB = "backend.services.event_broadcaster"

DID = 4242
BATCH = "batch-deadbeef"
CAM = "cam-front"
LABEL = "person"
CONF = 0.87
STARTED = 1_700_000_000.0
CLOSED = 1_700_000_090.5
IDS = [11, 12, 13]
REASON = "max_size"
BOOM = RuntimeError("stub boom")


def _run(coro: Any) -> Any:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _utc_iso(ts: float) -> str:
    """The EXACT string the shipped ``fromtimestamp(ts, tz=UTC).isoformat()``
    produces — computed independently of the module under test."""
    return datetime.fromtimestamp(ts, tz=UTC).isoformat()


# --- log capture ------------------------------------------------------------
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
        ba.logger.addHandler(self._handler)
        self._old_level = ba.logger.level
        ba.logger.setLevel(logging.DEBUG)
        return self

    def __exit__(self, *exc: object) -> None:
        ba.logger.removeHandler(self._handler)
        ba.logger.setLevel(self._old_level)

    def texts(self) -> list[str]:
        return [r.getMessage() for r in self.records]

    def one(self, level: int, needle: str) -> logging.LogRecord:
        hits = [r for r in self.records if r.levelno == level and needle in r.getMessage()]
        assert len(hits) == 1, f"expected one {needle!r} in {self.texts()}"
        return hits[0]


# --- fakes ------------------------------------------------------------------
class FakeClient:
    def __init__(self, *, items: list[bytes | str] | None = None) -> None:
        self.items = items if items is not None else []
        self.rpushed: list[tuple[str, str]] = []
        self.expired: list[tuple[str, int]] = []
        self.lrange_called: list[Any] = []

    async def rpush(self, key: str, value: str) -> int:
        self.rpushed.append((key, value))
        return len(self.rpushed)

    async def expire(self, key: str, ttl: int) -> bool:
        self.expired.append((key, ttl))
        return True

    async def lrange(self, key: Any, start: int, end: int) -> list[bytes | str]:
        self.lrange_called.append((key, start, end))
        return self.items


class FakeRedis:
    def __init__(self, client: FakeClient | None = None) -> None:
        self._client = client if client is not None else FakeClient()


class _FakeBroadcaster:
    def __init__(self) -> None:
        self.new: list[Any] = []
        self.batch: list[Any] = []

    async def broadcast_detection_new(self, payload: Any) -> None:
        self.new.append(payload)

    async def broadcast_detection_batch(self, payload: Any) -> None:
        self.batch.append(payload)


class _BroadcasterStub:
    """Installs a stand-in ``backend.services.event_broadcaster`` module.

    ``calls`` records every redis object the code handed ``get_broadcaster``;
    ``boom`` makes it raise so the except/log arm runs.
    """

    def __init__(self, *, boom: bool = False) -> None:
        self.bc = _FakeBroadcaster()
        self.calls: list[Any] = []
        self._boom = boom
        self._saved: Any = None

    def __enter__(self) -> _BroadcasterStub:
        mod = types.ModuleType(EB)

        async def get_broadcaster(redis: Any) -> _FakeBroadcaster:
            self.calls.append(redis)
            if self._boom:
                raise BOOM
            return self.bc

        mod.get_broadcaster = get_broadcaster  # type: ignore[attr-defined]
        self._saved = sys.modules.get(EB, _MISSING)
        sys.modules[EB] = mod
        return self

    def __exit__(self, *exc: object) -> None:
        if self._saved is _MISSING:
            sys.modules.pop(EB, None)
        else:
            sys.modules[EB] = self._saved


_MISSING = object()


def _agg(redis: Any = None) -> BatchAggregator:
    return BatchAggregator(redis_client=redis)  # type: ignore[arg-type]


def _exact(got: Any, want: Any, what: str) -> None:
    """Type-strict equality with a readable failure."""
    assert repr(got) == repr(want), f"{what}:\n  got  {got!r}\n  want {want!r}"


def _check_payload(got: Any, want: dict[str, Any], extra: set[str] | None = None) -> dict[str, Any]:
    """Key-set equality (plus ``extra`` slots) + ``repr`` equality per value.

    ``repr`` rather than ``==``: the batch-31 lesson — ``==`` is blind to
    str-subclass enums and once hid 14 killable payload mutants.
    """
    assert isinstance(got, dict), f"payload is not a dict: {got!r}"
    keys = set(want) | (extra or set())
    assert set(got) == keys, f"key set: {sorted(got)} vs {sorted(keys)}"
    for k, v in want.items():
        _exact(got[k], v, f"payload[{k!r}]")
    return got


# --- _broadcast_detection_new ----------------------------------------------
def _new_want(**over: Any) -> dict[str, Any]:
    """Expected payload WITHOUT the timestamp slot — ``datetime.now`` is
    unpinnable here, so callers assert ``timestamp`` is an aware ISO string
    separately (which is what the ``now(None)`` naive-dump mutant loses)."""
    want: dict[str, Any] = {
        "detection_id": DID,
        "batch_id": BATCH,
        "camera_id": CAM,
        "label": LABEL,
        "confidence": CONF,
    }
    want.update(over)
    return want


def _assert_aware_stamp(payload: dict[str, Any]) -> None:
    stamp = payload["timestamp"]
    assert isinstance(stamp, str), f"timestamp type {type(stamp).__name__}"
    parsed = datetime.fromisoformat(stamp)
    assert parsed.tzinfo is not None, f"naive timestamp: {stamp}"
    assert parsed.utcoffset() == datetime.now(UTC).utcoffset(), stamp


def _call_new(agg: BatchAggregator, **kw: Any) -> None:
    _run(
        agg._broadcast_detection_new(
            kw.get("detection_id", DID),
            kw.get("batch_id", BATCH),
            kw.get("camera_id", CAM),
            kw.get("label", LABEL),
            kw.get("confidence", CONF),
        )
    )


def test_broadcast_new_sends_exact_payload_and_receives_the_redis_client() -> None:
    redis = FakeRedis()
    agg = _agg(redis)
    with _BroadcasterStub() as stub:
        _call_new(agg)
    assert stub.calls == [redis], f"get_broadcaster got {stub.calls!r}, want [redis]"
    assert len(stub.bc.new) == 1
    got = _check_payload(stub.bc.new[0], _new_want(), extra={"timestamp"})
    # timestamp: an aware UTC ISO string (kills datetime.now(None) -> naive).
    _assert_aware_stamp(got)


def test_broadcast_new_defaults_label_and_confidence() -> None:
    # label=None -> "unknown"; confidence=None -> 0.0. Kills the ``or``/``and``
    # swap, both default-string mutants, the ``is None`` polarity flip and the
    # 1.0 fallback.
    agg = _agg(FakeRedis())
    with _BroadcasterStub() as stub:
        _call_new(agg, label=None, confidence=None)
    assert len(stub.bc.new) == 1
    got = _check_payload(
        stub.bc.new[0],
        _new_want(label="unknown", confidence=0.0),
        extra={"timestamp"},
    )
    _assert_aware_stamp(got)
    # a zero confidence is NOT the same as None: it must be forwarded verbatim
    with _BroadcasterStub() as stub2:
        _call_new(agg, confidence=0.0)
    got2 = _check_payload(stub2.bc.new[0], _new_want(confidence=0.0), extra={"timestamp"})
    _assert_aware_stamp(got2)


def test_broadcast_new_without_redis_is_a_no_op() -> None:
    # The guard's absent polarity: shipped returns before get_broadcaster is
    # even imported-called. ``if self._redis: return`` inverts this.
    agg = _agg(None)
    with _BroadcasterStub() as stub:
        _call_new(agg)
    assert stub.calls == [], stub.calls
    assert stub.bc.new == []


def test_broadcast_new_failure_logs_exact_message_and_extras() -> None:
    agg = _agg(FakeRedis())
    cap = LogCapture()
    with _BroadcasterStub(boom=True) as stub, cap:
        _call_new(agg)  # must NOT raise: broadcast is best-effort
    assert stub.bc.new == []
    rec = cap.one(logging.DEBUG, "Failed to broadcast detection.new event:")
    assert rec.getMessage() == f"Failed to broadcast detection.new event: {BOOM}"
    assert rec.detection_id == DID
    assert rec.batch_id == BATCH
    assert rec.camera_id == CAM


def test_broadcast_new_failure_extra_has_exactly_the_three_keys() -> None:
    # The rename family: every mutant spelling of an extra key must be absent
    # and the shipped spelling present.
    agg = _agg(FakeRedis())
    with _BroadcasterStub(boom=True), LogCapture() as cap:
        _call_new(agg)
    rec = cap.one(logging.DEBUG, "detection.new")
    for key in ("detection_id", "batch_id", "camera_id"):
        assert hasattr(rec, key), f"extra key {key!r} missing from {vars(rec)}"
    for bogus in (
        "XXdetection_idXX",
        "DETECTION_ID",
        "XXbatch_idXX",
        "BATCH_ID",
        "XXcamera_idXX",
        "CAMERA_ID",
    ):
        assert not hasattr(rec, bogus), f"unexpected extra key {bogus!r}"


# --- _broadcast_detection_batch --------------------------------------------
def _batch_want(reason: str | None = REASON) -> dict[str, Any]:
    return {
        "batch_id": BATCH,
        "camera_id": CAM,
        "detection_ids": IDS,
        "detection_count": len(IDS),
        "started_at": _utc_iso(STARTED),
        "closed_at": _utc_iso(CLOSED),
        "close_reason": reason,
    }


def _call_batch(agg: BatchAggregator, reason: str | None = REASON) -> None:
    _run(agg._broadcast_detection_batch(BATCH, CAM, IDS, STARTED, CLOSED, reason))


def test_broadcast_batch_sends_exact_payload() -> None:
    redis = FakeRedis()
    agg = _agg(redis)
    with _BroadcasterStub() as stub:
        _call_batch(agg)
    assert stub.calls == [redis], stub.calls
    assert len(stub.bc.batch) == 1
    _check_payload(stub.bc.batch[0], _batch_want())


def test_broadcast_batch_close_reason_none_is_carried() -> None:
    # close_reason has no default substitution: None must stay None (kills the
    # rename pair and any truthiness swap on that slot).
    agg = _agg(FakeRedis())
    with _BroadcasterStub() as stub:
        _call_batch(agg, None)
    _check_payload(stub.bc.batch[0], _batch_want(None))


def test_broadcast_batch_timestamps_are_utc_aware_exact() -> None:
    # Belt for the tz family: the exact strings above pin tz=UTC, but assert the
    # parsed offsets too so a naive-or-local dump cannot pass by luck.
    agg = _agg(FakeRedis())
    with _BroadcasterStub() as stub:
        _call_batch(agg)
    got = stub.bc.batch[0]
    for field in ("started_at", "closed_at"):
        parsed = datetime.fromisoformat(got[field])
        assert parsed.tzinfo is not None, f"{field} naive: {got[field]}"
        assert parsed.utcoffset() == datetime.now(UTC).utcoffset(), field
    assert datetime.fromisoformat(got["started_at"]).timestamp() == STARTED
    assert datetime.fromisoformat(got["closed_at"]).timestamp() == CLOSED


def test_broadcast_batch_without_redis_is_a_no_op() -> None:
    agg = _agg(None)
    with _BroadcasterStub() as stub:
        _call_batch(agg)
    assert stub.calls == []
    assert stub.bc.batch == []


def test_broadcast_batch_failure_logs_exact_message_and_extras() -> None:
    agg = _agg(FakeRedis())
    cap = LogCapture()
    with _BroadcasterStub(boom=True) as stub, cap:
        _call_batch(agg)
    assert stub.bc.batch == []
    rec = cap.one(logging.DEBUG, "Failed to broadcast detection.batch event:")
    assert rec.getMessage() == f"Failed to broadcast detection.batch event: {BOOM}"
    assert rec.batch_id == BATCH
    assert rec.camera_id == CAM
    assert rec.detection_count == 3


# --- set_gpu_monitor / get_memory_pressure_level ---------------------------
def _with_monitor(monitor: Any) -> _MonitorCtx:
    return _MonitorCtx(monitor)


class _MonitorCtx:
    """Set ``ba._gpu_monitor`` and ALWAYS put the previous value back."""

    def __init__(self, monitor: Any) -> None:
        self.monitor = monitor
        self._saved: Any = None

    def __enter__(self) -> Any:
        self._saved = ba._gpu_monitor
        ba.set_gpu_monitor(self.monitor)
        return ba._gpu_monitor

    def __exit__(self, *exc: object) -> None:
        ba._gpu_monitor = self._saved


class _BoomMonitor:
    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    async def check_memory_pressure(self) -> Any:
        raise self._exc


def test_set_gpu_monitor_sets_the_global_and_logs_exactly() -> None:
    # LogCapture enters FIRST: `with A, B` runs A.__enter__ before B attaches,
    # and set_gpu_monitor logs inside its own __enter__.
    with LogCapture() as cap, _MonitorCtx(None):
        assert ba._gpu_monitor is None  # assigning None is still an assignment
    rec = cap.one(logging.DEBUG, "GPU monitor set")
    assert rec.getMessage() == "GPU monitor set for batch aggregator backpressure"


def test_set_gpu_monitor_assigns_the_object_it_was_given() -> None:
    # The invariant is ``_MonitorCtx``'s restore, NOT the ambient global: in a
    # full-suite run a foreign test may leave a monitor installed (found by
    # reproducing the mutmut coverage-gather order in the mutant home — this
    # test passed in isolation and failed at position ~15k), so assert the
    # before/after identity, never ``is None``.
    ambient = ba._gpu_monitor
    sentinel = object()
    with _MonitorCtx(sentinel) as got:
        assert got is sentinel
    assert ba._gpu_monitor is ambient  # restored, no leak *by this test*


def test_memory_pressure_without_monitor_is_normal() -> None:
    from backend.services.gpu_monitor import MemoryPressureLevel

    with _MonitorCtx(None):
        assert _run(ba.get_memory_pressure_level()) is MemoryPressureLevel.NORMAL


def test_memory_pressure_returns_the_monitors_value() -> None:
    from backend.services.gpu_monitor import MemoryPressureLevel

    class _Ok:
        async def check_memory_pressure(self) -> Any:
            return MemoryPressureLevel.CRITICAL

    with _MonitorCtx(_Ok()):
        assert _run(ba.get_memory_pressure_level()) is MemoryPressureLevel.CRITICAL


def test_memory_pressure_failure_logs_exact_text_and_extras() -> None:
    from backend.services.gpu_monitor import MemoryPressureLevel

    exc = ValueError("gpu exploded")
    with _MonitorCtx(_BoomMonitor(exc)), LogCapture() as cap:
        out = _run(ba.get_memory_pressure_level())
    assert out is MemoryPressureLevel.NORMAL
    rec = cap.one(logging.DEBUG, "Failed to check memory pressure:")
    assert rec.getMessage() == f"Failed to check memory pressure: {exc}"
    assert rec.error == str(exc)
    assert rec.error_type == "ValueError"


def test_memory_pressure_failure_extra_keys_are_exact() -> None:
    with _MonitorCtx(_BoomMonitor(TypeError("t"))), LogCapture() as cap:
        _run(ba.get_memory_pressure_level())
    rec = cap.one(logging.DEBUG, "memory pressure")
    assert rec.error_type == "TypeError"
    for bogus in ("XXerrorXX", "ERROR", "XXerror_typeXX", "ERROR_TYPE", "NoneType"):
        if bogus == "NoneType":
            assert rec.error_type != "NoneType"
            continue
        assert not hasattr(rec, bogus), f"unexpected extra key {bogus!r}"
    assert rec.error == "t"


# --- __init__ --------------------------------------------------------------
class SettingsStub:
    """Only the knobs ``__init__`` reads; ``use_redis_streams`` is optional so
    the getattr-default family becomes observable (the shipped Settings always
    HAS the attribute, which is why those 3 keys survived every prior run)."""

    def __init__(self, *, streams: Any = _MISSING) -> None:
        self.batch_window_seconds = 90
        self.batch_idle_timeout_seconds = 30
        self.fast_path_confidence_threshold = 0.8
        self.fast_path_object_types = ["person", "car"]
        self.batch_max_detections = 25
        if streams is not _MISSING:
            self.use_redis_streams = streams


class _PatchSettings:
    def __init__(self, settings: Any) -> None:
        self.settings = settings
        self._saved: Any = None

    def __enter__(self) -> Any:
        self._saved = ba.get_settings
        ba.get_settings = lambda: self.settings  # type: ignore[assignment]
        return self.settings

    def __exit__(self, *exc: object) -> None:
        ba.get_settings = self._saved  # type: ignore[assignment]


def test_init_stores_every_setting_and_the_analyzer() -> None:
    analyzer = object()
    redis = FakeRedis()
    with _PatchSettings(SettingsStub(streams=True)):
        agg = BatchAggregator(redis_client=redis, analyzer=analyzer)  # type: ignore[arg-type]
    assert agg._redis is redis
    assert agg._analyzer is analyzer  # kills the =None assignment
    assert agg._batch_window == 90
    assert agg._idle_timeout == 30
    assert agg._analysis_queue == ba.ANALYSIS_QUEUE
    assert agg._fast_path_threshold == 0.8
    assert agg._fast_path_types == ["person", "car"]
    assert agg._batch_max_detections == 25
    assert agg._use_redis_streams is True
    assert agg.BATCH_KEY_TTL_SECONDS == 3600


def test_init_defaults_use_redis_streams_to_false_when_absent() -> None:
    # No use_redis_streams attribute at all: shipped default is False. The
    # default->True mutant says True; the no-default getattr mutant RAISES.
    with _PatchSettings(SettingsStub()):
        agg = BatchAggregator()
    assert agg._use_redis_streams is False


def test_init_getattr_default_for_use_redis_streams_is_false() -> None:
    # __init____mutmut_13 (default False -> None) is INVISIBLE on the instance:
    # both spellings end ``is True``-coerced to False. The kill is a call-site
    # spy on the getattr the constructor makes — installed in THIS module's
    # dict (LOAD_GLOBAL finds it before builtins), never in builtins itself,
    # and removed in a finally with a leak assert (batch-31: global patches
    # that leak poison other modules' verdicts).
    import builtins

    seen: list[tuple[Any, ...]] = []
    real_getattr = builtins.getattr

    def _spy(obj: Any, name: str, *default: Any) -> Any:
        if name == "use_redis_streams":
            seen.append(default)
        return real_getattr(obj, name, *default)

    with _PatchSettings(SettingsStub()):  # attribute absent -> default used
        ba.__dict__["getattr"] = _spy
        try:
            agg = BatchAggregator()
        finally:
            ba.__dict__.pop("getattr", None)
        assert "getattr" not in ba.__dict__, "spy leaked into the module dict"
    assert agg._use_redis_streams is False
    assert seen == [(False,)], f"getattr default must be positional False, saw {seen}"


def test_init_locks_are_fresh_per_instance() -> None:
    a, b = BatchAggregator(), BatchAggregator()
    assert isinstance(a._camera_locks, dict) and a._camera_locks == {}
    assert a._camera_locks is not b._camera_locks
    assert a._camera_locks.default_factory is asyncio.Lock
    assert a._batch_close_lock is not b._batch_close_lock
    assert a._locks_lock is not b._locks_lock
    assert a._batch_close_lock is not a._locks_lock


# --- atomic list helpers ---------------------------------------------------
def test_atomic_append_rpushes_string_value_and_refreshes_ttl() -> None:
    client = FakeClient()
    agg = _agg(FakeRedis(client))
    out = _run(agg._atomic_list_append("batch:x:detections", 7, 3600))
    assert client.rpushed == [("batch:x:detections", "7")], client.rpushed
    assert client.expired == [("batch:x:detections", 3600)]
    assert out == 1


def test_atomic_append_without_redis_raises_exact_message() -> None:
    for redis in (None, _NoClient()):
        agg = _agg(redis)
        try:
            _run(agg._atomic_list_append("k", 1, 2))
            raise AssertionError("expected RuntimeError")
        except RuntimeError as exc:
            assert str(exc) == "Redis client not initialized", str(exc)


class _NoClient:
    _client = None


def test_atomic_get_all_converts_and_skips_invalid() -> None:
    client = FakeClient(items=["5", b"6", "nope"])
    agg = _agg(FakeRedis(client))
    with LogCapture() as cap:
        out = _run(agg._atomic_list_get_all("batch:x:detections"))
    assert out == [5, 6], out
    assert client.lrange_called == [("batch:x:detections", 0, -1)]
    rec = cap.one(logging.WARNING, "Invalid detection ID in batch list:")
    assert rec.getMessage() == (f"Invalid detection ID in batch list: {sanitize_log_value('nope')}")


def test_atomic_get_all_without_redis_raises_exact_message() -> None:
    for redis in (None, _NoClient()):
        agg = _agg(redis)
        try:
            _run(agg._atomic_list_get_all("k"))
            raise AssertionError("expected RuntimeError")
        except RuntimeError as exc:
            assert str(exc) == "Redis client not initialized", str(exc)


def test_atomic_get_all_all_valid_logs_nothing() -> None:
    client = FakeClient(items=["1", b"2"])
    agg = _agg(FakeRedis(client))
    with LogCapture() as cap:
        assert _run(agg._atomic_list_get_all("k")) == [1, 2]
    assert cap.texts() == [], cap.texts()
