# TARGET-MODULE: backend.services.batch_aggregator
"""Batch-32 kill battery C: close_batch + _close_batch_for_size_limit (162 keys).

The two batch-close owners are the campaign's second-biggest survivor pool:
close_batch 105 of 196 keys green, _close_batch_for_size_limit 57 of 149. Every
one of the 162 was read off the normalized def-diff (script
/home/agent/runs/b32-key-diff.py; deduplicated shapes in
/home/agent/runs/b32-compact-close.txt) and sorted into families by a classifier
over the same def-diffs; the counts below are THAT census (sums to 162), not an
estimate:

* LOG CALLS (106 keys, the big one) — the message becomes ``None`` / ``'XXmsgXX'``
  / ``'msg'`` / ``'MSG'``, the ``extra=`` dict becomes ``None``, gets dropped
  outright, or one of its keys is re-spelled. Killing these needs THREE things
  at once: whole-message ``getMessage()`` equality (a substring assert lets the
  lower/upper-case and XX spellings through), an exact value assert on every
  ``extra`` attr, and a paired ABSENCE assert — a renamed key silently
  disappears, so presence alone cannot tell ``extra={'error': ...}`` from
  ``extra={'XXerrorXX': ...}`` (battery B learned this the hard way: 18 of its
  first-pass greens were exactly this).
* ``log_context(batch_id=..., camera_id=...)`` kwargs (8 keys) — dropped or
  ``None``-swapped. Observable because ``ba.logger`` carries a ContextFilter
  that copies the live context onto every record, so the battery installs that
  filter on its own capture handler and asserts the two attrs on every record.
* DICT KEY renames in the two returned summaries (8 keys: 6 in the
  already-closed return, 2 in the ``summary`` literal) — killed by key-set
  equality plus per-value asserts.
* ``_redis.delete(...)`` argument swaps/drops (10 keys) — the shipped call is
  seven POSITIONAL keys, so the battery asserts the recorded call as an exact
  tuple in order.
* duration math ``(... - ...) * 1000`` (8 keys) — asserted as an exact number
  against a pinned clock.
* ``_broadcast_detection_batch`` kwargs (8 keys) — dropped-kwarg mutants are
  invisible on the instance (batch-31 lesson), so the call site is watched with
  a subclass spy.
* the remaining 14: the closing-flag ``_client.set`` (3), the ``_redis.get``
  metadata sites (2), the ``RuntimeError`` message (1), ``_get_camera_lock``
  (1), ``_atomic_list_get_all`` (1), the ``float(x) if x else time.time()``
  polarity pair (2, killed by the pinned clock's CALL ORDER), the three dead
  initializer stores (3) and the ``decode('utf-8')`` spelling (1) — those last
  four ARE the ledger's equivalents, everything else in the 14 is killed by the
  recording Redis fake / the exact-message raise asserts.

Harness decisions:

* The clock is a stand-in for the ``time`` MODULE inside
  ``batch_aggregator``'s own globals (``ba.__dict__["time"]``), not a patch of
  the shared ``time`` module: the shipped code resolves ``time`` as a global,
  so the module dict wins, and the real module is never touched. A pin
  (t0, +step per call) turns ``started_at``/``closed_at``/``duration_ms`` into
  exact numbers and pins the CALL ORDER, which is what makes the
  ``float(x) if x else time.time()`` polarity mutants observable. Restored in a
  ``finally`` with a leak assert (same discipline as battery A's getattr spy).
* Redis is a recording fake with a ``_client`` sub-fake, because the shipped
  code reaches through it for the closing flag (``set(key, '1', ex=TTL)``) and,
  on the size path, ``lrange(key, 0, -1)``. The closing-flag call is recorded
  and compared as an exact tuple — the ``'1'`` -> dropped mutant dies with a
  TypeError there, which is a kill, not a fake bug.
* ``_use_redis_streams`` is FORCED False in the spy subclass — an assert would
  have tied every test to whatever the ambient .env carries. That costs nothing:
  neither owner has a single survivor key inside the Redis-Streams arm (checked
  against the def-diffs), and the battery still reads the flag back once.
* ``QueueAddResult`` is the REAL dataclass from backend.core.redis, so
  ``had_backpressure`` is the shipped derived property — the backpressure and
  failure arms are reached with production logic, not a scripted boolean.
* Log capture enters BEFORE the clock/stubs in every test (enter order decides
  which handler sees the records — battery A's ordering bug).

Honesty ledger (measured by the FINAL sweep of this file: RED=158 GREEN=4 of
162, shipped-green control OK — 18 tests pass unmutated). All four greens are
EQUIVALENT, each proven by construction (script /home/agent/runs/b32-probe-c.py:
shipped-vs-mutant fingerprints — returned value, raised exception, every log
record with its full attr set, every recorded Redis/spy call and the whole clock
call sequence — compared under BOTH the happy path and the failing-fetch path;
all IDENTICAL), not by diff shape:

``close_batch__mutmut_46`` (``detections: list[int] = []`` -> ``= None``): that
statement is the declaration-initializer only. The very next statement starts a
TaskGroup whose ``fetch_detections`` coroutine rebinds ``detections`` on EVERY
path into the ``try`` (it is the first thing it does, so no exception can leave
the initializer's value in place), and if it raises, ``except*`` re-raises the
group member and close_batch never reads the variable. The initializer is a dead
store — not a list-vs-None behaviour change.
``close_batch__mutmut_47`` / ``__mutmut_48`` (``started_at_str``/
``pipeline_start_time`` ``= None`` -> ``= ''``): same dead-store argument, and
the only reads of either value are truthiness tests (``if started_at_str else
time.time()``, ``_parse_pipeline_ts(x) if x else None``,
``if pipeline_start_time:``), so falsy->falsy is the same program either way —
the batch-30 falsy-swap family, closed by the enumeration rather than by eye.
``_close_batch_for_size_limit__mutmut_41`` (``item.decode('utf-8')`` ->
``decode('UTF-8')``): codec names are looked up case-insensitively —
``codecs.lookup('utf-8') is codecs.lookup('UTF-8')`` is True and both report
name ``utf-8``, i.e. the SAME codec object, so the two spellings cannot differ
for any input.

The other 158 go red. What actually did the work: whole-message
``getMessage()`` equality (not substring) for the XX/lower/UPPER spellings;
exact-value + paired-absence asserts on every ``extra`` attr (a renamed key just
vanishes, so presence cannot distinguish ``extra={'error': ...}`` from
``extra={'XXerrorXX': ...}``); the shipped ContextFilter installed on the capture
handler, which is the only way the eight ``log_context(batch_id=..., camera_id=...)``
mutants are observable at all; a module-global clock stand-in that turns
``duration_ms`` into an exact number and pins the ``time.time()`` CALL ORDER;
``QueueAddResult``'s real derived ``had_backpressure``; and the spy subclass +
recording Redis for the dropped/None-swapped call kwargs, which are invisible on
the batch object (batch-31's lesson).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

# Mirror the repo conftest env (the trampoline sweep imports this file
# directly; setdefault makes this a no-op under repo pytest). See battery A.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://security:security_dev_password@localhost:5432/security",  # pragma: allowlist secret
)
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("OTEL_ENABLED", "false")
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("PYROSCOPE_ENABLED", "false")

_ROOT = str(Path.cwd())
if (Path(_ROOT) / "backend" / "services" / "batch_aggregator.py").is_file():
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)

from backend.core.redis import QueueAddResult, QueueOverflowPolicy  # noqa: E402
from backend.services import batch_aggregator as ba  # noqa: E402
from backend.services.batch_aggregator import BatchAggregator  # noqa: E402

CAM = "cam-west"
BID = "batch-f00dface"
IDS = [11, 12, 13]
IDS2 = [4242, 4243]
STARTED = 1_700_000_000.0
PS = "1700000001.5"
T0 = 1_700_000_100.0
STEP = 0.5
TTL = ba.BATCH_CLOSING_FLAG_TTL_SECONDS
BOOM = RuntimeError("stub fetch boom")
_WARN = "warn-text"
_MISS = object()


# --- event loop -------------------------------------------------------------
def _run(coro: Any) -> Any:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# --- log capture --------------------------------------------------------------
class _ListHandler(logging.Handler):
    def __init__(self, sink: list[logging.LogRecord]) -> None:
        super().__init__()
        self.sink = sink

    def emit(self, record: logging.LogRecord) -> None:
        self.sink.append(record)


class LogCapture:
    """Captures ba.logger records AND applies the shipped ContextFilter.

    The filter is what makes ``log_context(batch_id=..., camera_id=...)``
    observable: it copies the live context onto every record, so a dropped or
    None-swapped context kwarg shows up as an absent/None attr.
    """

    def __enter__(self) -> LogCapture:
        self.records: list[logging.LogRecord] = []
        self._handler = _ListHandler(self.records)
        found = [f for f in ba.logger.filters if type(f).__name__ == "ContextFilter"]
        assert len(found) == 1, f"ba.logger must carry exactly one ContextFilter, got {found}"
        self._filter = found[0]
        self._handler.addFilter(self._filter)
        ba.logger.addHandler(self._handler)
        self._old_level = ba.logger.level
        ba.logger.setLevel(logging.DEBUG)
        return self

    def __exit__(self, *exc: object) -> None:
        ba.logger.removeHandler(self._handler)
        ba.logger.setLevel(self._old_level)

    def texts(self) -> list[str]:
        return [r.getMessage() for r in self.records]

    def one(self, level: int, message: str) -> logging.LogRecord:
        hits = [r for r in self.records if r.levelno == level and r.getMessage() == message]
        assert len(hits) == 1, f"want exactly one {message!r} at {level}, got {self.texts()}"
        return hits[0]

    def count(self, level: int, message: str) -> int:
        return sum(1 for r in self.records if r.levelno == level and r.getMessage() == message)

    def none_at_all(self) -> None:
        assert self.records == [], f"expected no log records, got {self.texts()}"


def _shown(rec: logging.LogRecord) -> str:
    return f"msg={rec.getMessage()!r} attrs={sorted(vars(rec))}"


def _attrs(rec: logging.LogRecord, want: dict[str, Any], absent: tuple[str, ...] = ()) -> None:
    """Exact value per ``extra`` key + explicit ABSENCE of the mutant spellings.

    Presence alone is blind to a renamed key (it just disappears), so every
    assert here is a pair: the shipped key holds the shipped value, and the
    XX-wrapped / UPPER-cased spellings are not on the record at all.
    """
    for key, value in want.items():
        got = getattr(rec, key, _MISS)
        assert got == value, f"extra {key!r} = {got!r}, want {value!r}; {_shown(rec)}"
    for key in absent:
        assert not hasattr(rec, key), f"unexpected extra attr {key!r} on {_shown(rec)}"


def _ctx(rec: logging.LogRecord, batch_id: str = BID, camera_id: str = CAM) -> None:
    """The two log_context kwargs, observed through the shipped ContextFilter."""
    _attrs(rec, {"batch_id": batch_id, "camera_id": camera_id})


def _ctxs(cap: LogCapture, batch_id: str = BID, camera_id: str = CAM) -> None:
    for rec in cap.records:
        _ctx(rec, batch_id, camera_id)


# --- the pinned clock ---------------------------------------------------------
class _TimeShim:
    """Stand-in for the ``time`` module inside batch_aggregator's globals.

    ``ba.time`` IS the shared stdlib module, so patching its attribute would
    mutate a global; instead the module dict gets this object, which the
    shipped ``time.time()`` LOAD_GLOBAL finds first.
    """

    def __init__(self, t0: float = T0, step: float = STEP) -> None:
        self.calls: list[float] = []
        self._t = t0
        self._step = step

    def time(self) -> float:
        self.calls.append(self._t)
        value = self._t
        self._t += self._step
        return value


@contextlib.contextmanager
def _clock(shim: _TimeShim) -> Any:
    saved = ba.__dict__.get("time", _MISS)
    ba.__dict__["time"] = shim
    try:
        yield shim
    finally:
        if saved is _MISS:
            ba.__dict__.pop("time", None)
        else:
            ba.__dict__["time"] = saved
        assert "time" not in ba.__dict__ or ba.__dict__["time"] is saved, "clock shim leaked"


@contextlib.contextmanager
def _stage(shim: _TimeShim) -> Any:
    """Capture FIRST, then the clock — enter order decides who sees records."""
    with LogCapture() as cap, _clock(shim):
        yield SimpleNamespace(cap=cap, clock=shim)


# --- redis fake ---------------------------------------------------------------
class FakeClient:
    """The ``_client`` the shipped code reaches through for set()/lrange()."""

    def __init__(self, raw: list[Any]) -> None:
        self.raw = raw
        self.sets: list[tuple[Any, ...]] = []
        self.lranges: list[Any] = []

    async def set(self, key: Any, value: Any, ex: Any = None) -> bool:
        self.sets.append((key, value, ex))
        return True

    async def lrange(self, key: Any, start: Any, stop: Any) -> list[Any]:
        self.lranges.append((key, start, stop))
        return list(self.raw)


class FakeRedis:
    """Facade with scripted ``get`` answers and an ordered ``delete`` log."""

    def __init__(
        self,
        values: dict[str, Any],
        *,
        raw: list[Any] | None = None,
        result: QueueAddResult | None = None,
        script: dict[str, list[Any]] | None = None,
        raises: dict[str, BaseException] | None = None,
    ) -> None:
        self.values = dict(values)
        self.script = {k: list(v) for k, v in (script or {}).items()}
        self.raises = dict(raises or {})
        self._client = FakeClient(raw if raw is not None else [])
        self.gets: list[Any] = []
        self.deleted: list[tuple[Any, ...]] = []
        self.queue_calls: list[dict[str, Any]] = []
        self.result = result if result is not None else QueueAddResult(True, 7)

    async def get(self, key: Any) -> Any:
        self.gets.append(key)
        if key in self.raises:
            raise self.raises[key]
        seq = self.script.get(key)
        if seq is not None:
            return seq.pop(0) if len(seq) > 1 else seq[0]
        return self.values.get(key)

    async def add_to_queue_safe(self, queue: Any, item: Any, *, overflow_policy: Any = None) -> Any:
        self.queue_calls.append({"queue": queue, "item": item, "overflow_policy": overflow_policy})
        return self.result

    async def delete(self, *keys: Any) -> int:
        self.deleted.append(tuple(keys))
        return len(keys)


# --- spy aggregator -----------------------------------------------------------
class CloseAgg(BatchAggregator):
    """Overrides the three collaborators the close paths delegate to.

    Spying is the only way the DROP/None-swap mutants at those call sites die:
    the mutations are invisible on the batch object itself.
    """

    def __init__(self, redis: Any, *, ids: list[int] | None = None) -> None:
        super().__init__(redis_client=redis)  # type: ignore[arg-type]
        # Pin the LEGACY queue branch deterministically. Neither owner has a
        # single survivor key in the Redis-Streams arm, so pinning the flag
        # costs no coverage and keeps these asserts independent of whatever
        # ``use_redis_streams`` the ambient .env happens to carry.
        self._use_redis_streams = False
        self.ids = list(ids if ids is not None else IDS)
        self._lock = asyncio.Lock()
        self.lock_calls: list[Any] = []
        self.getall_calls: list[Any] = []
        self.getall_raises: BaseException | None = None
        self.broad_calls: list[dict[str, Any]] = []

    async def _get_camera_lock(self, camera_id: Any) -> asyncio.Lock:
        self.lock_calls.append(camera_id)
        return self._lock

    async def _atomic_list_get_all(self, key: Any) -> list[int]:
        self.getall_calls.append(key)
        if self.getall_raises is not None:
            raise self.getall_raises
        return list(self.ids)

    async def _broadcast_detection_batch(self, **kw: Any) -> None:
        self.broad_calls.append(kw)


# --- builders -----------------------------------------------------------------
def _values(**over: Any) -> dict[str, Any]:
    base = {
        f"batch:{BID}:camera_id": CAM,
        f"batch:{BID}:started_at": str(STARTED),
        f"batch:{BID}:pipeline_start_time": PS,
    }
    base.update(over)
    return {k: v for k, v in base.items() if v is not _DROP}


class _Drop:
    """Sentinel: the caller wants this Redis key to be ABSENT, not None."""


_DROP = _Drop()


def _agg(redis: Any, *, ids: list[int] | None = None) -> CloseAgg:
    return CloseAgg(redis, ids=ids)


def _mk(
    values: dict[str, Any],
    *,
    raw: list[Any] | None = None,
    result: QueueAddResult | None = None,
    script: dict[str, list[Any]] | None = None,
    raises: dict[str, BaseException] | None = None,
    ids: list[int] | None = None,
) -> tuple[CloseAgg, FakeRedis]:
    fake = FakeRedis(values, raw=raw, result=result, script=script, raises=raises)
    return _agg(fake, ids=ids), fake


def _del_keys(batch_id: str = BID, camera_id: str = CAM) -> tuple[str, ...]:
    """The seven keys close must delete, IN THE SHIPPED ORDER."""
    return (
        f"batch:{camera_id}:current",
        f"batch:{batch_id}:camera_id",
        f"batch:{batch_id}:detections",
        f"batch:{batch_id}:started_at",
        f"batch:{batch_id}:last_activity",
        f"batch:{batch_id}:pipeline_start_time",
        f"batch:{batch_id}:closing",
    )


def _keys(obj: dict[str, Any], want: set[str]) -> None:
    diff = set(obj) ^ want
    assert not diff, f"key-set differs by {sorted(diff)}; got {sorted(obj)}"


def _close(agg: CloseAgg, batch_id: str = BID) -> Any:
    return _run(agg.close_batch(batch_id))


def _close_size(agg: CloseAgg, batch_id: str = BID) -> Any:
    return _run(agg._close_batch_for_size_limit(batch_id))


def _raises(exc: BaseException, call: Any) -> BaseException:
    try:
        call()
    except type(exc) as got:
        return got
    raise AssertionError(f"expected {type(exc).__name__}({exc!r})")


# --- guards -------------------------------------------------------------------
def test_close_batch_without_redis_raises_and_logs_nothing() -> None:
    shim = _TimeShim()
    with _stage(shim) as st:
        err = _raises(RuntimeError("x"), lambda: _close(_agg(None)))
        assert str(err) == "Redis client not initialized", str(err)
    st.cap.none_at_all()
    assert shim.calls == [], f"no clock reads expected, got {shim.calls}"


def test_size_limit_without_redis_raises_exact_message() -> None:
    with LogCapture() as cap:
        err = _raises(RuntimeError("x"), lambda: _close_size(_agg(None)))
        assert str(err) == "Redis client not initialized", str(err)
    cap.none_at_all()


# --- close_batch: not-found and already-closed ---------------------------------
def test_close_batch_missing_metadata_raises_valueerror_without_touching_anything() -> None:
    shim = _TimeShim()
    agg, fake = _mk(_values(**{f"batch:{BID}:camera_id": None}), ids=[])
    with _stage(shim) as st:
        err = _raises(ValueError("x"), lambda: _close(agg))
        assert str(err) == f"Batch {BID} not found", str(err)
    st.cap.none_at_all()
    assert fake.gets == [f"batch:{BID}:camera_id"], fake.gets
    assert fake._client.sets == [], "must not write a closing flag for an unknown batch"
    assert fake.deleted == [] and agg.broad_calls == [] and agg.lock_calls == []


def test_close_batch_already_closed_returns_exact_summary_and_skips_work() -> None:
    shim = _TimeShim()
    agg, fake = _mk(
        _values(),
        script={f"batch:{BID}:camera_id": [CAM, None]},
        ids=[],
    )
    with _stage(shim) as st:
        out = _close(agg)
    _keys(
        out,
        {
            "batch_id",
            "camera_id",
            "detection_count",
            "detections",
            "started_at",
            "closed_at",
            "already_closed",
        },
    )
    assert out["batch_id"] == BID and out["camera_id"] == CAM, out
    assert out["detection_count"] == 0 and out["detections"] == [], out
    assert out["already_closed"] is True, out
    # two stamps, in order: started_at first, then closed_at
    assert out["started_at"] == T0 and out["closed_at"] == T0 + STEP, out
    assert shim.calls == [T0, T0 + STEP], shim.calls
    rec = st.cap.one(logging.DEBUG, "Batch already closed, skipping")
    _ctx(rec)
    _attrs(rec, {}, ("XXbatch_idXX", "BATCH_ID", "XXcamera_idXX", "CAMERA_ID"))
    assert agg.getall_calls == [], "early return must not fetch the detection list"
    assert fake.deleted == [] and agg.broad_calls == [] and fake.queue_calls == []


# --- close_batch: happy path (legacy queue) ------------------------------------
def test_close_batch_happy_path_summary_queue_call_and_cleanup_are_exact() -> None:
    shim = _TimeShim()
    agg, fake = _mk(_values())
    with _stage(shim) as st:
        out = _close(agg)
    assert agg._use_redis_streams is False, "CloseAgg pins the legacy-queue branch"
    _keys(
        out, {"batch_id", "camera_id", "detection_count", "detections", "started_at", "closed_at"}
    )
    assert out == {
        "batch_id": BID,
        "camera_id": CAM,
        "detection_count": 3,
        "detections": IDS,
        "started_at": STARTED,
        "closed_at": T0,
    }, out
    assert shim.calls == [T0, T0 + STEP], f"closed_at then queue timestamp: {shim.calls}"
    # camera lock + detection list read with the shipped args
    assert agg.lock_calls == [CAM], agg.lock_calls
    assert agg.getall_calls == [f"batch:{BID}:detections"], agg.getall_calls
    assert fake._client.sets == [(f"batch:{BID}:closing", "1", TTL)], fake._client.sets
    assert fake.gets == [
        f"batch:{BID}:camera_id",
        f"batch:{BID}:camera_id",
        f"batch:{BID}:started_at",
        f"batch:{BID}:pipeline_start_time",
    ], fake.gets
    # the queue push, as one call with the shipped kwargs
    assert len(fake.queue_calls) == 1, fake.queue_calls
    call = fake.queue_calls[0]
    assert call["queue"] == agg._analysis_queue, call
    assert call["overflow_policy"] is QueueOverflowPolicy.DLQ, call
    item = call["item"]
    _keys(item, {"batch_id", "camera_id", "detection_ids", "timestamp", "pipeline_start_time"})
    assert item == {
        "batch_id": BID,
        "camera_id": CAM,
        "detection_ids": IDS,
        "timestamp": T0 + STEP,
        "pipeline_start_time": PS,
    }, item
    assert fake.deleted == [_del_keys()], f"delete keys/order: {fake.deleted}"
    # broadcast: exact kwargs (drop/None-swap family)
    assert len(agg.broad_calls) == 1, agg.broad_calls
    _keys(
        agg.broad_calls[0],
        {"batch_id", "camera_id", "detection_ids", "started_at", "closed_at", "close_reason"},
    )
    assert agg.broad_calls[0] == {
        "batch_id": BID,
        "camera_id": CAM,
        "detection_ids": IDS,
        "started_at": STARTED,
        "closed_at": T0,
        "close_reason": "timeout",
    }, agg.broad_calls[0]
    # logs: INFO "Batch closed" with exact extras, DEBUG cleanup, no warning
    info = st.cap.one(logging.INFO, "Batch closed")
    _attrs(
        info,
        {
            "detection_count": 3,
            "duration_ms": (T0 - STARTED) * 1000,
            "close_reason": "timeout",
        },
        (
            "XXdetection_countXX",
            "DETECTION_COUNT",
            "XXduration_msXX",
            "DURATION_MS",
            "XXclose_reasonXX",
            "CLOSE_REASON",
            "XXtimeoutXX",
            "TIMEOUT",
        ),
    )
    debug = st.cap.one(logging.DEBUG, "Cleaned up Redis keys for batch")
    _attrs(debug, {}, ("XXCleaned up Redis keys for batchXX",))
    assert st.cap.count(logging.WARNING, "Queue backpressure detected while pushing batch") == 0
    assert st.cap.count(logging.ERROR, "Failed to push batch to analysis queue") == 0
    _ctxs(st.cap)


def test_close_batch_omits_pipeline_start_time_when_absent() -> None:
    shim = _TimeShim()
    agg, fake = _mk(_values(**{f"batch:{BID}:pipeline_start_time": _DROP}))
    with _stage(shim):
        _close(agg)
    item = fake.queue_calls[0]["item"]
    _keys(item, {"batch_id", "camera_id", "detection_ids", "timestamp"})


def test_close_batch_without_started_at_falls_back_to_the_clock_in_order() -> None:
    shim = _TimeShim()
    agg, fake = _mk(_values(**{f"batch:{BID}:started_at": None}))
    with _stage(shim) as st:
        out = _close(agg)
    # started_at, then closed_at, then the queue timestamp
    assert shim.calls == [T0, T0 + STEP, T0 + 2 * STEP], shim.calls
    assert out["started_at"] == T0 and out["closed_at"] == T0 + STEP, out
    assert fake.queue_calls[0]["item"]["timestamp"] == T0 + 2 * STEP
    assert st.cap.count(logging.INFO, "Batch closed") == 1


# --- close_batch: empty batch -------------------------------------------------
def test_close_batch_with_no_detections_skips_queue_but_still_cleans_up() -> None:
    shim = _TimeShim()
    agg, fake = _mk(_values(), ids=[])
    with _stage(shim) as st:
        out = _close(agg)
    assert out["detection_count"] == 0 and out["detections"] == [], out
    assert fake.queue_calls == [], "empty batch must not be pushed"
    assert fake.deleted == [_del_keys()], fake.deleted
    assert agg.broad_calls[0]["detection_ids"] == [], agg.broad_calls
    rec = st.cap.one(logging.DEBUG, "Batch has no detections, skipping analysis queue")
    _attrs(
        rec,
        {},
        (
            "XXBatch has no detections, skipping analysis queueXX",
            "BATCH HAS NO DETECTIONS, SKIPPING ANALYSIS QUEUE",
            "batch has no detections, skipping analysis queue",
        ),
    )
    assert st.cap.count(logging.INFO, "Batch closed") == 0, "duration log is detections-only"
    assert shim.calls == [T0], shim.calls
    _ctxs(st.cap)


# --- close_batch: queue failure + backpressure --------------------------------
def test_close_batch_queue_failure_logs_exact_error_and_raises() -> None:
    shim = _TimeShim()
    bad = QueueAddResult(False, 42, dropped_count=3, moved_to_dlq_count=2, error="boom-msg")
    agg, fake = _mk(_values(), result=bad)
    with _stage(shim) as st:
        err = _raises(RuntimeError("x"), lambda: _close(agg))
        assert str(err) == "Queue operation failed: boom-msg", str(err)
    rec = st.cap.one(logging.ERROR, "Failed to push batch to analysis queue")
    _attrs(
        rec,
        {
            "detection_count": 3,
            "queue_name": agg._analysis_queue,
            "queue_length": 42,
            "error": "boom-msg",
        },
        (
            "XXdetection_countXX",
            "DETECTION_COUNT",
            "XXqueue_nameXX",
            "QUEUE_NAME",
            "XXqueue_lengthXX",
            "QUEUE_LENGTH",
            "XXerrorXX",
            "ERROR",
        ),
    )
    _ctx(rec)
    assert st.cap.count(logging.INFO, "Batch closed") == 0, "failure must not log a close"
    assert st.cap.count(logging.WARNING, "Queue backpressure detected while pushing batch") == 0
    assert fake.deleted == [], "must not clean up after a failed push"
    assert agg.broad_calls == []


def test_close_batch_backpressure_logs_every_extra_field() -> None:
    shim = _TimeShim()
    press = QueueAddResult(
        True, 99, dropped_count=1, moved_to_dlq_count=2, error=None, warning=_WARN
    )
    agg, fake = _mk(_values(), result=press)
    with _stage(shim) as st:
        assert fake.result.had_backpressure is True, "shipped property must drive this arm"
        _close(agg)
    rec = st.cap.one(logging.WARNING, "Queue backpressure detected while pushing batch")
    _attrs(
        rec,
        {
            "detection_count": 3,
            "queue_name": agg._analysis_queue,
            "queue_length": 99,
            "moved_to_dlq": 2,
            "warning": _WARN,
        },
        (
            "XXdetection_countXX",
            "DETECTION_COUNT",
            "XXqueue_nameXX",
            "QUEUE_NAME",
            "XXqueue_lengthXX",
            "QUEUE_LENGTH",
            "XXmoved_to_dlqXX",
            "MOVED_TO_DLQ",
            "XXwarningXX",
            "WARNING",
        ),
    )
    _ctx(rec)
    assert st.cap.count(logging.INFO, "Batch closed") == 1, "backpressure still closes the batch"
    assert st.cap.count(logging.ERROR, "Failed to push batch to analysis queue") == 0


# --- close_batch: fetch failure -----------------------------------------------
def test_close_batch_fetch_failure_logs_group_member_and_reraises_it() -> None:
    shim = _TimeShim()
    agg, fake = _mk(_values())
    agg.getall_raises = BOOM
    with _stage(shim) as st:
        err = _raises(RuntimeError("x"), lambda: _close(agg))
        assert err is BOOM, f"must re-raise the group member itself, got {err!r}"
    rec = st.cap.one(logging.ERROR, "Failed to fetch batch data (operation 0)")
    _attrs(rec, {"error": str(BOOM)}, ("XXerrorXX", "ERROR"))
    _ctx(rec)
    assert fake.deleted == [] and agg.broad_calls == []
    assert st.cap.count(logging.INFO, "Batch closed") == 0


def test_close_batch_metadata_fetch_failure_is_also_one_error_log() -> None:
    shim = _TimeShim()
    key = f"batch:{BID}:pipeline_start_time"
    agg, fake = _mk(_values(), raises={key: BOOM})
    with _stage(shim) as st:
        err = _raises(RuntimeError("x"), lambda: _close(agg))
        assert err is BOOM, err
    rec = st.cap.one(logging.ERROR, "Failed to fetch batch data (operation 0)")
    _attrs(rec, {"error": str(BOOM)})
    assert len([r for r in st.cap.records if r.levelno == logging.ERROR]) == 1, st.cap.texts()


# --- _close_batch_for_size_limit ----------------------------------------------
def test_size_limit_missing_camera_id_warns_once_and_returns_none() -> None:
    with LogCapture() as cap:
        agg, fake = _mk(_values(**{f"batch:{BID}:camera_id": None}))
        assert _close_size(agg) is None
    rec = cap.one(logging.WARNING, "Cannot close batch: camera_id not found")
    _attrs(
        rec,
        {"batch_id": BID},
        ("XXbatch_idXX", "BATCH_ID", "XXCannot close batch: camera_id not foundXX"),
    )
    assert fake._client.sets == [] and fake.deleted == [] and agg.broad_calls == []
    assert fake.queue_calls == []


def test_size_limit_close_is_exact_end_to_end() -> None:
    shim = _TimeShim()
    agg, fake = _mk(_values(), raw=[b"4242", "4243"], ids=IDS2)
    with _stage(shim) as st:
        out = _close_size(agg)
    assert isinstance(out, dict), out
    _keys(
        out,
        {
            "batch_id",
            "camera_id",
            "detection_ids",
            "started_at",
            "ended_at",
            "reason",
            "pipeline_start_time",
        },
    )
    # bytes AND str members decode through int(); the utf-8 codec swap dies here
    assert out["detection_ids"] == IDS2, out
    assert out["started_at"] == STARTED and out["ended_at"] == T0, out
    assert out["reason"] == "max_size" and out["pipeline_start_time"] == PS, out
    # the size path stamps exactly once (started_at came from Redis)
    assert shim.calls == [T0], shim.calls
    assert fake._client.lranges == [(f"batch:{BID}:detections", 0, -1)], fake._client.lranges
    assert fake._client.sets == [(f"batch:{BID}:closing", "1", TTL)], fake._client.sets
    assert fake.gets == [
        f"batch:{BID}:camera_id",
        f"batch:{BID}:started_at",
        f"batch:{BID}:pipeline_start_time",
    ], fake.gets
    assert len(fake.queue_calls) == 1, fake.queue_calls
    call = fake.queue_calls[0]
    assert (
        call["queue"] == agg._analysis_queue and call["overflow_policy"] is QueueOverflowPolicy.DLQ
    )
    assert call["item"] is out, "the size path pushes the summary object itself"
    assert fake.deleted == [_del_keys()], fake.deleted
    assert len(agg.broad_calls) == 1, agg.broad_calls
    assert agg.broad_calls[0] == {
        "batch_id": BID,
        "camera_id": CAM,
        "detection_ids": IDS2,
        "started_at": STARTED,
        "closed_at": T0,
        "close_reason": "max_size",
    }, agg.broad_calls[0]
    info = st.cap.one(logging.INFO, "Batch closed")
    _attrs(
        info,
        {
            "detection_count": 2,
            "duration_ms": (T0 - STARTED) * 1000,
            "close_reason": "max_size",
        },
        (
            "XXdetection_countXX",
            "DETECTION_COUNT",
            "XXduration_msXX",
            "DURATION_MS",
            "XXclose_reasonXX",
            "CLOSE_REASON",
            "XXmax_sizeXX",
            "MAX_SIZE",
        ),
    )
    assert st.cap.count(logging.WARNING, "Queue overflow handling triggered for batch") == 0
    debug = st.cap.one(logging.DEBUG, "Cleaned up Redis keys for batch")
    _attrs(debug, {}, ("XXCleaned up Redis keys for batchXX", "CLEANED UP REDIS KEYS FOR BATCH"))
    _ctxs(st.cap)


def test_size_limit_records_queue_warning_with_every_field() -> None:
    shim = _TimeShim()
    warn = QueueAddResult(True, 5, dropped_count=0, moved_to_dlq_count=4, warning=_WARN)
    agg, fake = _mk(_values(), raw=[b"4242"], result=warn, ids=IDS2[:1])
    with _stage(shim) as st:
        assert fake.result.warning == _WARN
        _close_size(agg)
    rec = st.cap.one(logging.WARNING, "Queue overflow handling triggered for batch")
    _attrs(
        rec,
        {
            "detection_count": 1,
            "queue_name": agg._analysis_queue,
            "queue_length": 5,
            "moved_to_dlq": 4,
            "warning": _WARN,
        },
        (
            "XXdetection_countXX",
            "DETECTION_COUNT",
            "XXqueue_nameXX",
            "QUEUE_NAME",
            "XXqueue_lengthXX",
            "QUEUE_LENGTH",
            "XXmoved_to_dlqXX",
            "MOVED_TO_DLQ",
            "XXwarningXX",
            "WARNING",
        ),
    )
    _ctx(rec)
    assert st.cap.count(logging.INFO, "Batch closed") == 1


def test_size_limit_empty_batch_skips_queue_but_still_cleans_up() -> None:
    shim = _TimeShim()
    agg, fake = _mk(_values(), raw=[], ids=[])
    with _stage(shim) as st:
        out = _close_size(agg)
    assert out["detection_ids"] == [] and out["reason"] == "max_size", out
    assert fake.queue_calls == [] and fake.deleted == [_del_keys()], (
        fake.queue_calls,
        fake.deleted,
    )
    assert agg.broad_calls[0]["detection_ids"] == []
    rec = st.cap.one(logging.DEBUG, "Batch has no detections, skipping analysis queue")
    _attrs(rec, {}, ("XXBatch has no detections, skipping analysis queueXX",))
    assert st.cap.count(logging.INFO, "Batch closed") == 0


def test_size_limit_without_metadata_uses_the_clock_and_drops_pipeline_key() -> None:
    shim = _TimeShim()
    agg, fake = _mk(
        _values(**{f"batch:{BID}:started_at": None, f"batch:{BID}:pipeline_start_time": _DROP})
    )
    with _stage(shim) as st:
        out = _close_size(agg)
    assert shim.calls == [T0, T0 + STEP], shim.calls
    assert out["started_at"] == T0 and out["ended_at"] == T0 + STEP, out
    _keys(out, {"batch_id", "camera_id", "detection_ids", "started_at", "ended_at", "reason"})
    assert fake.deleted == [_del_keys()], fake.deleted
    _ctxs(st.cap)


# --- the clock shim really is module-local -------------------------------------
def test_clock_shim_does_not_touch_the_stdlib_time_module() -> None:
    real = time.time
    shim = _TimeShim()
    with _clock(shim):
        assert ba.time.time() == T0
        assert time.time is real, "the stdlib module must not be patched"
    assert ba.__dict__.get("time") is not shim, "shim leaked into the module globals"
    assert time.time is real
    assert shim.calls == [T0], shim.calls
