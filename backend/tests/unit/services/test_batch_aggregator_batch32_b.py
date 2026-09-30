# TARGET-MODULE: backend.services.batch_aggregator
"""Batch-32 kill battery B: BatchAggregator.add_detection (126 survivor keys).

``add_detection`` is the module's biggest survivor pool: 126 of 189 keys still
green. The families, read off the normalized def-diffs (script
/home/agent/runs/b32-key-diff.py, output /home/agent/runs/b32-diff-add*.txt):
31 DROP (a call argument, an ``extra=`` slot or a whole call disappears), 29
XX-wrap and 23 UPPER (dict-key / message re-spellings), and ~40 value swaps
(``camera_id=camera_id`` -> ``camera_id=None`` etc.).

Harness decisions those families force:

* The collaborator calls are observed with a SUBCLASS whose overrides record
  the exact args each call site passed. A dropped kwarg or a ``None``-swapped
  kwarg is invisible on the instance (batch-31's dropped-kwarg lesson), so the
  spy — not the object state — is what makes 31 DROP + ~40 swap keys killable.
  Instance-local overrides cannot leak into any other test or module.
* Redis is a recording fake: ``get``/``set`` on the client facade plus
  ``_client.llen`` and a ``pipeline(transaction=True)`` context manager, so the
  key formats (``batch:{cam}:current``, ``batch:{bid}:detections``,
  ``...:last_activity``), the TTL constant and the ``str(current_time)`` values
  are all pinned (their ``= None`` mutants would otherwise TypeError through
  the fake's f-string/format calls, which is ALSO a kill — both are fine).
* ``time.time`` is NOT patched (that would mean mutating the shared ``time``
  module). Instead every timestamp assert is bounded by a before/after capture,
  which distinguishes a real float from ``None``/``str(None)``.
* The §6 wake is observed by stubbing ``backend.services.vlm_client`` in
  ``sys.modules`` (save/restore, same discipline as battery A's broadcaster
  stub), so ``opened_batch`` is pinned in BOTH polarities: exactly one wake on
  the new-batch path, zero wakes on batch-reuse and on all three fast paths —
  which is what the ``opened_batch = False -> None``-style polarity mutants
  and the wake-drop keys need. ``_run`` drains fire-and-forget tasks so no
  "coroutine was never awaited" warning leaks into the suite.
* Log asserts pin the WHOLE formatted message plus each ``extra`` attr, and
  assert the XX-mutants' spellings are ABSENT (ContextFilter is NOT installed
  in these tests' handlers, and the shipped keys are asserted present, so an
  ambient key can never fake a pass).

Honesty ledger (measured by the FINAL sweep of this file: RED=124 GREEN=2 of
126 — both greens EQUIVALENT, argued against the shipped def, not merely
unswept):

``__mutmut_92`` (``opened_batch = False`` -> ``= None``): ``opened_batch`` is
written exactly twice (the ``False`` init and ``True`` in the new-batch branch)
and read exactly once, at ``if opened_batch:``. Nothing else observes the
object, so any falsy init is the same program. The battery pins the OBSERVABLE
half of that variable anyway (one wake on open, zero on reuse and on all three
bypasses), which is what the polarity/wake-drop keys need.
``__mutmut_119`` (``batch_id = None`` -> ``= ''`` after the max-size close): the
reset's ONLY consumer is the very next ``if not batch_id:``, which creates the
new batch; both None and '' take that branch, and the branch overwrites
``batch_id`` with ``generate_batch_id()`` before any other read. Falsy->falsy
substitution on a truthiness-only value (the batch-30 falsy-swap family).

The other 124 go red: the 31 DROP keys (dropped call kwargs and dropped
``extra=`` slots) die to the SUBCLASS call-site spies; the ~40 ``=None`` value
swaps die to the same spies plus the recording Redis fake; the XX-wrap/UPPER
families die to whole-message ``getMessage()`` equality plus paired presence AND
absence asserts on every ``extra`` attr (presence alone is not enough — a
renamed slot silently disappears, which is how 18 of this file's first-pass
greens were still standing until the absence pins landed).
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
import time
import types
from pathlib import Path
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

from backend.services import batch_aggregator as ba  # noqa: E402
from backend.services.batch_aggregator import BatchAggregator  # noqa: E402

CAM = "cam-east"
DID = 4242
EXISTING = "batch-cafeb0be"
NEW_PREFIX = "batch-"
BID_RE = re.compile(r"^batch-[0-9a-f]{8}$")
PS_TIME = "2026-09-29T12:00:00+00:00"


# --- event loop ------------------------------------------------------------
def _run(coro: Any) -> Any:
    """Run ``coro`` to completion, then drain any fire-and-forget tasks it
    spawned (the §6 wake) so asyncio never warns about a destroyed task."""
    loop = asyncio.new_event_loop()

    async def _driver() -> Any:
        out = await coro
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        return out

    try:
        return loop.run_until_complete(_driver())
    finally:
        loop.close()


# --- log capture -------------------------------------------------------------
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

    def count(self, level: int, needle: str) -> int:
        return sum(1 for r in self.records if r.levelno == level and needle in r.getMessage())


def _absent(rec: logging.LogRecord, *names: str) -> None:
    for n in names:
        assert not hasattr(rec, n), f"unexpected extra attr {n!r} on {vars(rec)}"


# --- redis fake --------------------------------------------------------------
class FakePipeline:
    def __init__(self, client: FakeRedisClient) -> None:
        self.client = client
        self.sets: list[tuple[Any, ...]] = []
        self.executed = 0
        self.raises: BaseException | None = None

    async def __aenter__(self) -> FakePipeline:
        self.client.pipelines.append(self)
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    def set(self, key: Any, value: Any, ex: Any = None) -> None:
        self.sets.append((key, value, ex))

    async def execute(self) -> list[Any]:
        self.executed += 1
        if self.raises is not None:
            raise self.raises
        return []


class FakeRedisClient:
    """Records everything add_detection's collaborators touch."""

    def __init__(self, *, llen_result: int = 0) -> None:
        self.llen_result = llen_result
        self.llen_called: list[Any] = []
        self.pipelines: list[FakePipeline] = []
        self.pushed: list[tuple[Any, Any]] = []
        self.expires: list[tuple[Any, Any]] = []

    async def llen(self, key: Any) -> int:
        self.llen_called.append(key)
        return self.llen_result

    def pipeline(self, *, transaction: bool = True) -> FakePipeline:
        assert transaction is True, f"metadata must use a TRANSACTION pipeline, got {transaction!r}"
        return FakePipeline(self)


class FakeRedis:
    """Facade the aggregator uses: get/set on the outside, _client for the
    atomic list/pipeline paths."""

    def __init__(
        self, client: FakeRedisClient | None = None, *, current_batch: str | None = None
    ) -> None:
        self._client = client if client is not None else FakeRedisClient()
        self.current_batch = current_batch
        self.gets: list[Any] = []
        self.sets: list[tuple[Any, Any, Any]] = []

    async def get(self, key: Any) -> str | None:
        self.gets.append(key)
        if key == f"batch:{CAM}:current":
            return self.current_batch
        return None

    async def set(self, key: Any, value: Any, expire: Any = None) -> bool:
        self.sets.append((key, value, expire))
        return True


# --- the module stubs (vlm wake) ----------------------------------------------
VL = "backend.services.vlm_client"
_MISSING = object()


class _WakeStub:
    def __init__(self) -> None:
        self.calls = 0
        self._saved: Any = None

    def __enter__(self) -> _WakeStub:
        mod = types.ModuleType(VL)
        outer = self

        async def wake_ai_vlm() -> None:
            outer.calls += 1

        mod.wake_ai_vlm = wake_ai_vlm  # type: ignore[attr-defined]
        self._saved = sys.modules.get(VL, _MISSING)
        sys.modules[VL] = mod
        return self

    def __exit__(self, *exc: object) -> None:
        if self._saved is _MISSING:
            sys.modules.pop(VL, None)
        else:
            sys.modules[VL] = self._saved


# --- the spy aggregator ------------------------------------------------------
class SpyAggregator(BatchAggregator):
    """Overrides every collaborator add_detection calls with a recording spy.

    ``bypass`` is the scripted answer sequence for should_bypass_batch (the
    threat call is FIRST, the smoke/fire call second); ``use_fast`` scripts
    _should_use_fast_path. Spying here is what makes the DROP/swap families at
    those call sites killable — the mutations are invisible on the instance.
    """

    def __init__(
        self, redis: Any, *, bypass: list[bool] | None = None, use_fast: bool = False
    ) -> None:
        super().__init__(redis_client=redis)  # type: ignore[arg-type]
        self.bypass_answers = list(bypass or [])
        self.bypass_answers_used: list[bool] = []
        self.use_fast = use_fast
        self.bypass_calls: list[dict[str, Any]] = []
        self.fast_check_calls: list[tuple[Any, Any]] = []
        self.threat_calls: list[dict[str, Any]] = []
        self.smoke_calls: list[dict[str, Any]] = []
        self.fast_calls: list[tuple[Any, Any]] = []
        self.lock_calls: list[Any] = []
        self.meta_calls: list[dict[str, Any]] = []
        self.append_calls: list[tuple[Any, Any, Any]] = []
        self.close_calls: list[str] = []
        self.broad_calls: list[dict[str, Any]] = []
        self._append_result = 7

    async def should_bypass_batch(self, **kw: Any) -> bool:
        self.bypass_calls.append(kw)
        if not self.bypass_answers:
            return False
        ans = self.bypass_answers.pop(0)
        self.bypass_answers_used.append(ans)
        return ans

    def _should_use_fast_path(self, confidence: Any, object_type: Any) -> bool:
        self.fast_check_calls.append((confidence, object_type))
        return self.use_fast

    async def _process_threat_fast_path(self, **kw: Any) -> None:
        self.threat_calls.append(kw)

    async def _process_smoke_fire_fast_path(self, **kw: Any) -> None:
        self.smoke_calls.append(kw)

    async def _process_fast_path(self, camera_id: Any, detection_id: Any) -> None:
        self.fast_calls.append((camera_id, detection_id))

    async def _get_camera_lock(self, camera_id: Any) -> asyncio.Lock:
        self.lock_calls.append(camera_id)
        return await super()._get_camera_lock(camera_id)

    async def _create_batch_metadata_atomic(self, **kw: Any) -> None:
        self.meta_calls.append(kw)

    async def _atomic_list_append(self, key: Any, value: Any, ttl: Any) -> int:
        self.append_calls.append((key, value, ttl))
        return self._append_result

    async def _close_batch_for_size_limit(self, batch_id: str) -> None:
        self.close_calls.append(batch_id)

    async def _broadcast_detection_new(self, **kw: Any) -> None:
        self.broad_calls.append(kw)


def _in_window(value: Any, lo: float, hi: float, *, as_str: bool = False) -> float:
    """A real timestamp inside [lo, hi] (time.time() cannot be pinned); returns
    the float. ``as_str`` additionally requires it to arrive as a ``str``, which
    is what the shipped ``str(current_time)`` call does — so the mutants that
    drop the ``str()`` or swap the value for ``None`` fail here."""
    if as_str:
        assert isinstance(value, str), (
            f"want str(current_time), got {type(value).__name__} {value!r}"
        )
    try:
        v = float(value)
    except (TypeError, ValueError) as exc:  # None, "None", ...
        raise AssertionError(f"not a timestamp: {value!r}") from exc
    assert lo - 0.001 <= v <= hi + 0.001, f"{value!r} outside [{lo}, {hi}]"
    return v


def _agg(redis: Any, **spy: Any) -> SpyAggregator:
    return SpyAggregator(redis, **spy)  # type: ignore[arg-type]


def _add(agg: SpyAggregator, **kw: Any) -> Any:
    return _run(
        agg.add_detection(
            kw.get("camera_id", CAM),
            kw.get("detection_id", DID),
            kw.get("file_path", "/frames/f.jpg"),
            kw.get("confidence"),
            kw.get("object_type"),
            kw.get("pipeline_start_time"),
            kw.get("threat_type"),
            kw.get("smoke_fire_type"),
        )
    )


# --- guard + validation ------------------------------------------------------
def test_add_detection_without_redis_raises_exact_message() -> None:
    agg = _agg(None)
    try:
        _add(agg)
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert str(exc) == "Redis client not initialized", str(exc)


def test_invalid_detection_id_raises_exact_valueerror_with_chain() -> None:
    agg = _agg(FakeRedis())
    try:
        _add(agg, detection_id="not-a-number")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert str(exc) == (
            "Invalid detection_id: 'not-a-number'. Detection IDs must be numeric."
        ), str(exc)
        assert isinstance(exc.__cause__, ValueError), "must chain the original error"
    # a numeric STRING normalizes to int everywhere downstream
    agg2 = _agg(FakeRedis())
    with _WakeStub():
        out = _add(agg2, detection_id="4242")
    assert isinstance(out, str)
    assert agg2.append_calls == [(f"batch:{out}:detections", 4242, 3600)], agg2.append_calls


# --- new-batch path ----------------------------------------------------------
def test_new_batch_creates_metadata_appends_and_returns_batch_id() -> None:
    before = time.time()
    redis = FakeRedis()
    agg = _agg(redis)
    with _WakeStub() as wake, LogCapture() as cap:
        out = _add(agg, confidence=0.5, object_type="person", pipeline_start_time=PS_TIME)
    after = time.time()
    assert BID_RE.match(out), out
    assert agg.lock_calls == [CAM]
    assert redis.gets == [f"batch:{CAM}:current"], redis.gets
    assert len(agg.meta_calls) == 1, agg.meta_calls
    meta = agg.meta_calls[0]
    assert set(meta) == {
        "batch_key",
        "batch_id",
        "camera_id",
        "current_time",
        "ttl",
        "pipeline_start_time",
    }, sorted(meta)
    assert meta["batch_key"] == f"batch:{CAM}:current"
    assert meta["batch_id"] == out
    assert meta["camera_id"] == CAM
    assert meta["ttl"] == agg.BATCH_KEY_TTL_SECONDS
    assert meta["pipeline_start_time"] == PS_TIME
    assert isinstance(meta["current_time"], float), type(meta["current_time"]).__name__
    _in_window(meta["current_time"], before, after)
    assert agg.append_calls == [(f"batch:{out}:detections", DID, agg.BATCH_KEY_TTL_SECONDS)]
    assert len(redis.sets) == 1, redis.sets
    key, val, exp = redis.sets[0]
    assert (key, exp) == (f"batch:{out}:last_activity", agg.BATCH_KEY_TTL_SECONDS)
    _in_window(val, before, after, as_str=True)
    assert agg.broad_calls == [
        {
            "detection_id": DID,
            "batch_id": out,
            "camera_id": CAM,
            "label": "person",
            "confidence": 0.5,
        }
    ], agg.broad_calls
    # §6 wake: exactly one, on the open
    assert wake.calls == 1, wake.calls
    rec = cap.one(logging.INFO, "Batch created")
    assert rec.getMessage() == "Batch created"
    assert rec.batch_id == out
    assert rec.camera_id == CAM
    assert rec.detection_count == 1
    _absent(
        rec,
        "XXbatch_idXX",
        "BATCH_ID",
        "XXcamera_idXX",
        "CAMERA_ID",
        "XXdetection_countXX",
        "DETECTION_COUNT",
    )
    dbg = cap.one(logging.DEBUG, "Added detection")
    assert dbg.getMessage() == (
        f"Added detection {DID} to batch {out} (camera: {CAM}, total detections: 7)"
    ), dbg.getMessage()
    assert dbg.detection_count == 7
    assert dbg.camera_id == CAM and dbg.batch_id == out and dbg.detection_id == DID
    _absent(
        dbg,
        "XXcamera_idXX",
        "CAMERA_ID",
        "XXbatch_idXX",
        "BATCH_ID",
        "XXdetection_idXX",
        "DETECTION_ID",
        "XXdetection_countXX",
        "DETECTION_COUNT",
    )
    assert cap.count(logging.INFO, "reached max size") == 0


def test_new_batch_pipeline_start_time_none_is_forwarded_as_none() -> None:
    agg = _agg(FakeRedis())
    with _WakeStub():
        _add(agg)
    assert agg.meta_calls[0]["pipeline_start_time"] is None


def test_wake_does_not_fire_on_batch_reuse() -> None:
    redis = FakeRedis(current_batch=EXISTING)
    agg = _agg(redis)
    with _WakeStub() as wake, LogCapture() as cap:
        out = _add(agg)
    assert out == EXISTING
    assert wake.calls == 0, "opened_batch must stay falsy on the reuse path"
    assert agg.meta_calls == []
    assert cap.count(logging.INFO, "Batch created") == 0
    assert agg.append_calls == [(f"batch:{EXISTING}:detections", DID, 3600)]


# --- max-size path -----------------------------------------------------------
def test_batch_at_max_closes_reopens_and_logs_exact_size_extra() -> None:
    agg = _agg(FakeRedis(FakeRedisClient(), current_batch=EXISTING))
    maxd = agg._batch_max_detections  # settings-driven; never hardcode it
    client = FakeRedisClient(llen_result=maxd)
    redis = FakeRedis(client, current_batch=EXISTING)
    agg = _agg(redis)
    with _WakeStub() as wake, LogCapture() as cap:
        out = _add(agg)
    assert client.llen_called == [f"batch:{EXISTING}:detections"]
    assert agg.close_calls == [EXISTING]
    assert out != EXISTING and BID_RE.match(out)
    rec = cap.one(logging.INFO, "Batch reached max size, closing")
    assert rec.getMessage() == "Batch reached max size, closing"
    assert rec.camera_id == CAM
    assert rec.batch_id == EXISTING
    assert rec.current_size == maxd
    assert rec.max_size == maxd
    _absent(rec, "XXcamera_idXX", "XXbatch_idXX", "XXcurrent_sizeXX", "XXmax_sizeXX")
    assert cap.count(logging.INFO, "Batch created") == 1  # then a fresh batch
    assert wake.calls == 1
    assert agg.meta_calls[0]["batch_id"] == out


def test_batch_one_below_max_is_reused_without_closing() -> None:
    # pins the ``>=`` polarity: 24 < 25 must NOT close (a ``>`` mutant would
    # also not close; the 25 case above pins the other side of that edge).
    maxd = SpyAggregator(FakeRedis())._batch_max_detections
    client = FakeRedisClient(llen_result=maxd - 1)
    redis = FakeRedis(client, current_batch=EXISTING)
    agg = _agg(redis)
    with _WakeStub() as wake:
        out = _add(agg)
    assert out == EXISTING
    assert agg.close_calls == []
    assert wake.calls == 0


# --- threat / smoke-fire / fast-path bypasses ----------------------------------
def test_threat_bypass_logs_calls_and_returns_threat_id() -> None:
    redis = FakeRedis()
    agg = _agg(redis, bypass=[True])
    cap = LogCapture()
    with _WakeStub() as wake, cap:
        out = _add(agg, confidence=0.99, object_type="person", threat_type="gun")
    assert out == f"threat_fast_path_{DID}"
    assert agg.bypass_calls == [
        {"object_type": "person", "confidence": 0.99, "threat_type": "gun"}
    ], agg.bypass_calls
    assert agg.threat_calls == [
        {"camera_id": CAM, "detection_id": DID, "threat_type": "gun", "confidence": 0.99}
    ], agg.threat_calls
    assert agg.smoke_calls == [] and agg.fast_calls == [] and agg.lock_calls == []
    assert wake.calls == 0
    rec = cap.one(logging.INFO, "Threat fast path triggered for detection")
    assert rec.getMessage() == "Threat fast path triggered for detection"
    assert rec.camera_id == CAM
    assert rec.detection_id == DID
    assert rec.confidence == 0.99
    assert rec.threat_type == "gun"
    _absent(
        rec,
        "XXthreat_typeXX",
        "THREAT_TYPE",
        "XXcamera_idXX",
        "CAMERA_ID",
        "XXdetection_idXX",
        "DETECTION_ID",
        "XXconfidenceXX",
        "CONFIDENCE",
    )


def test_smoke_fire_bypass_runs_after_the_threat_check() -> None:
    redis = FakeRedis()
    agg = _agg(redis, bypass=[False, True])  # threat answer False, smoke answer True
    with _WakeStub() as wake, LogCapture() as cap:
        out = _add(agg, confidence=0.95, object_type="car", smoke_fire_type="smoke")
    assert out == f"smoke_fire_fast_path_{DID}"
    assert len(agg.bypass_calls) == 2
    assert agg.bypass_calls[0] == {"object_type": "car", "confidence": 0.95, "threat_type": None}
    assert agg.bypass_calls[1] == {
        "object_type": "car",
        "confidence": 0.95,
        "smoke_fire_type": "smoke",
    }
    assert agg.smoke_calls == [
        {"camera_id": CAM, "detection_id": DID, "smoke_fire_type": "smoke", "confidence": 0.95}
    ]
    assert wake.calls == 0
    rec = cap.one(logging.INFO, "Smoke/fire fast path triggered for detection")
    assert rec.getMessage() == "Smoke/fire fast path triggered for detection"
    assert rec.camera_id == CAM
    assert rec.detection_id == DID
    assert rec.confidence == 0.95
    assert rec.smoke_fire_type == "smoke"
    _absent(
        rec,
        "XXsmoke_fire_typeXX",
        "SMOKE_FIRE_TYPE",
        "XXcamera_idXX",
        "CAMERA_ID",
        "XXdetection_idXX",
        "DETECTION_ID",
        "XXconfidenceXX",
        "CONFIDENCE",
    )
    # the camera_id/detection_id/confidence renames would silently drop a slot
    # from the record; asserting presence above + absence here kills both ways.


def test_fast_path_after_two_bose_bypass_checks() -> None:
    redis = FakeRedis()
    agg = _agg(redis, bypass=[False, False], use_fast=True)
    with _WakeStub() as wake, LogCapture() as cap:
        out = _add(agg, confidence=0.91, object_type="person")
    assert out == f"fast_path_{DID}"
    assert agg.fast_check_calls == [(0.91, "person")], agg.fast_check_calls
    assert agg.fast_calls == [(CAM, DID)]
    assert agg.lock_calls == [] and wake.calls == 0
    rec = cap.one(logging.INFO, "Fast path triggered for detection")
    assert rec.getMessage() == "Fast path triggered for detection"
    assert rec.camera_id == CAM
    assert rec.detection_id == DID
    assert rec.confidence == 0.91
    assert rec.object_type == "person"
    _absent(
        rec,
        "XXobject_typeXX",
        "OBJECT_TYPE",
        "XXcamera_idXX",
        "CAMERA_ID",
        "XXdetection_idXX",
        "DETECTION_ID",
        "XXconfidenceXX",
        "CONFIDENCE",
    )


def test_no_bypass_at_all_falls_through_to_batching() -> None:
    agg = _agg(FakeRedis(), bypass=[False, False], use_fast=False)
    with _WakeStub() as wake:
        out = _add(agg, confidence=0.1, object_type="dog")
    assert BID_RE.match(out)
    assert len(agg.bypass_calls) == 2
    assert agg.fast_calls == [] and agg.threat_calls == [] and agg.smoke_calls == []
    assert wake.calls == 1


# --- metadata pipeline (through the REAL _create_batch_metadata_atomic) ------
class _NoBroadcast(BatchAggregator):
    """Everything REAL except the two collaborators the fake Redis cannot back:
    the WebSocket handoff (which in the mutant home would import the
    TRAMPOLINED event_broadcaster — battery A owns those keys) and the RPUSH
    append. Both are recorded, not executed."""

    def __init__(self, redis: Any) -> None:
        super().__init__(redis_client=redis)  # type: ignore[arg-type]
        self.broad: list[dict[str, Any]] = []
        self.appended: list[tuple[Any, Any, Any]] = []

    async def _broadcast_detection_new(self, **kw: Any) -> None:
        self.broad.append(kw)

    async def _atomic_list_append(self, key: Any, value: Any, ttl: Any) -> int:
        self.appended.append((key, value, ttl))
        return len(self.appended)


def _bare(redis: Any) -> _NoBroadcast:
    return _NoBroadcast(redis)


def test_metadata_pipeline_sets_all_five_keys_in_one_transaction() -> None:
    client = FakeRedisClient()
    redis = FakeRedis(client)
    agg = _bare(redis)
    with _WakeStub():
        out = _add(agg, pipeline_start_time=PS_TIME)
    assert len(client.pipelines) == 1, "exactly one MULTI/EXEC pipeline per open"
    pipe = client.pipelines[0]
    assert pipe.executed == 1
    ttl = agg.BATCH_KEY_TTL_SECONDS
    assert pipe.sets == [
        (f"batch:{CAM}:current", out, ttl),
        (f"batch:{out}:camera_id", CAM, ttl),
        (f"batch:{out}:started_at", pipe.sets[2][1], ttl),
        (f"batch:{out}:last_activity", pipe.sets[3][1], ttl),
        (f"batch:{out}:pipeline_start_time", PS_TIME, ttl),
    ], pipe.sets
    assert float(pipe.sets[2][1]) == float(pipe.sets[3][1])  # started == last_activity


def test_metadata_pipeline_omits_pipeline_start_time_when_absent() -> None:
    client = FakeRedisClient()
    agg = _bare(FakeRedis(client))
    with _WakeStub():
        _add(agg)
    keys = [k for k, _, _ in client.pipelines[0].sets]
    assert all("pipeline_start_time" not in str(k) for k in keys), keys
    assert len(keys) == 4


def test_metadata_failure_logs_and_raises() -> None:
    # The real _create_batch_metadata_atomic path with a pipeline that explodes:
    # shipped logs one ERROR with exact extras then RE-RAISES. add_detection
    # propagates.
    client = FakeRedisClient()
    agg = _bare(FakeRedis(client))
    boom = RuntimeError("MULTI EXEC failed")

    class _Boom(FakePipeline):
        async def execute(self) -> list[Any]:
            self.executed += 1
            raise boom

    client_pipeline = _Boom(client)
    client.pipeline = lambda **_kw: client_pipeline  # type: ignore[assignment]
    cap = LogCapture()
    try:
        with _WakeStub(), cap:
            _add(agg)
        raise AssertionError("expected RuntimeError from metadata")
    except RuntimeError as exc:
        assert exc is boom
    assert client_pipeline.executed == 1
    rec = cap.one(logging.ERROR, "Atomic batch metadata creation failed")
    assert rec.getMessage() == "Atomic batch metadata creation failed - transaction rolled back"
    assert rec.camera_id == CAM
    assert rec.error == "MULTI EXEC failed"


# --- record_batch_max_reached (module-level metric call) ---------------------
def test_max_size_records_the_metric_with_the_camera() -> None:
    seen: list[Any] = []
    real = ba.record_batch_max_reached

    def _spy(camera_id: Any) -> None:
        seen.append(camera_id)

    maxd = SpyAggregator(FakeRedis())._batch_max_detections
    client = FakeRedisClient(llen_result=maxd + 1)
    redis = FakeRedis(client, current_batch=EXISTING)
    agg = _agg(redis)
    ba.record_batch_max_reached = _spy  # type: ignore[assignment]
    try:
        with _WakeStub():
            _add(agg)
    finally:
        ba.record_batch_max_reached = real  # type: ignore[assignment]
    assert seen == [CAM], f"metric spy saw {seen}"


# --- broadcast handoff -------------------------------------------------------
def test_broadcast_gets_object_type_as_label_even_when_none() -> None:
    # label=object_type (not a defaulted copy): None must arrive as None.
    agg = _agg(FakeRedis())
    with _WakeStub():
        out = _add(agg)
    assert agg.broad_calls == [
        {"detection_id": DID, "batch_id": out, "camera_id": CAM, "label": None, "confidence": None}
    ], agg.broad_calls
