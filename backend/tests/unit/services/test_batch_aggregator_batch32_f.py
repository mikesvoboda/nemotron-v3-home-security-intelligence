# TARGET-MODULE: backend.services.batch_aggregator
"""Batch-32 kill battery F: the A-residual trio (85 survivor keys).

Targets (campaign #6 residual sweep, b33-sweep-a: 85 residual GREENs, all in
these three functions — def-diff census /home/agent/runs/b33-f-defdiffs.txt):

* ``BatchAggregator.should_apply_backpressure`` (17 keys) — two log sites:
  the CRITICAL warning (msg None/case/XX + extra None/dropped/key-rename)
  and the except-path debug (same families + ``str(None)`` + ``type(None)``).
* ``BatchAggregator._create_batch_metadata_atomic`` (20 keys) — the
  ``or``->``and`` guard, the five ``ex=ttl`` mutations (drop / ``ex=None``)
  across the four+one pipeline sets, two key->``None``, three value->``None``,
  two ``str(None)``, and the rolled-back error log's key renames.
* ``recover_orphaned_detections`` (48 keys) — three stmt-shape mutants
  (``outerjoin`` on-clause -> ``None`` / dropped, ``load_only(Detection.id,
  ...)`` arg-drop) + 45 log-family mutants across four sites.

Kill mechanisms (all observations cross a boundary the mutant cannot fake):

* Log assertions compare ``getMessage()`` EXACTLY and read each extra attr by
  VALUE (``getattr(rec, k, _MISS) == expected``), never bare ``hasattr`` —
  the shipped ContextFilter rides the capture handler (battery D's idiom), and
  the ambient-key audit from batteries A/D holds: none of the bogus renames
  (``XXkeyXX`` / ``KEY``) is an ambient context key, so absence is proven too.
* The stmt mutants are caught by RECORDING the expression builder: the exact
  outerjoin on-clause tuple (``None`` and absent are both visible), the exact
  ``load_only`` column tuple (the ``Detection.id`` drop is visible), the where
  conditions with the exact cutoff ``datetime``, order and limit.
* ``pipe.set`` calls are compared as exact ``(args, kwargs)`` tuples — key,
  value and ``ex=`` are each individually asserted per position.

Honesty ledger (pre-registered, reconcile after the bank pass):
- ``should_apply_backpressure`` False-paths (NORMAL monitor, raising monitor
  verdict) guard polarity; the CRITICAL/None and error-key sets are complete.
- The guard test asserts the shipped ``RuntimeError`` TYPE and message — the
  ``and`` mutant dies by producing an AttributeError instead (narrow catch).
- ``exc_info`` for the outer recover error is asserted truthy, so both
  ``exc_info=None`` and ``exc_info=False`` die; shipped always attaches.
- No test edits production; every global (``ba._gpu_monitor``, ``ba.datetime``,
  the five stubbed ``sys.modules`` slots) is saved and restored.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import types
from datetime import UTC, datetime, timedelta
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
from backend.services.gpu_monitor import MemoryPressureLevel  # noqa: E402

# --- constants ---------------------------------------------------------------
CAM = "cam-north"
CAM2 = "cam-south"
BID = "batch-cccc3333"
BKEY = f"batch:{CAM}:current"
T0 = 1_700_000_100.0
TTL = 42
PST = "2026-09-29T12:00:00+00:00"
T0DT = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)
BP_BOOM = RuntimeError("bp monitor boom")
DB_BOOM = RuntimeError("session boom")
EXEC_BOOM = RuntimeError("pipeline execute boom")
_MISS = object()


def _run(coro: Any) -> Any:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# --- log capture (battery D idiom: shipped ContextFilter rides the handler) --
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
        found = [f for f in ba.logger.filters if type(f).__name__ == "ContextFilter"]
        assert len(found) == 1, f"ba.logger must carry exactly one ContextFilter, got {found}"
        self._handler.addFilter(found[0])
        ba.logger.addHandler(self._handler)
        self._old_level = ba.logger.level
        ba.logger.setLevel(logging.DEBUG)
        return self

    def __exit__(self, *exc: object) -> None:
        ba.logger.removeHandler(self._handler)
        ba.logger.setLevel(self._old_level)

    def texts(self) -> list[str]:
        return [r.getMessage() for r in self.records]

    def at(self, level: int, message: str) -> list[logging.LogRecord]:
        return [r for r in self.records if r.levelno == level and r.getMessage() == message]

    def one(self, level: int, message: str) -> logging.LogRecord:
        hits = self.at(level, message)
        assert len(hits) == 1, f"want exactly one {message!r} at {level}, got {self.texts()}"
        return hits[0]


def _attrs(rec: logging.LogRecord, want: dict[str, Any], bogus: tuple[str, ...]) -> None:
    """Extras by VALUE (never bare hasattr) + bogus spellings absent."""
    for key, value in want.items():
        assert getattr(rec, key, _MISS) == value, (
            f"extra[{key!r}] != {value!r}: {getattr(rec, key, _MISS)!r}"
        )
    for key in bogus:
        assert not hasattr(rec, key), f"unexpected extra key {key!r}"


# =============================================================================
# Pool B — should_apply_backpressure (17 keys)
# =============================================================================
class _Monitor:
    """A GPU-monitor stand-in: hands back ``level`` or raises ``exc``."""

    def __init__(self, level: Any = None, exc: BaseException | None = None) -> None:
        self.level = level
        self.exc = exc

    async def check_memory_pressure(self) -> Any:
        if self.exc is not None:
            raise self.exc
        return self.level


class _MonitorSetter:
    """Set ``ba._gpu_monitor`` via the shipped setter; ALWAYS restore it."""

    def __init__(self, monitor: _Monitor) -> None:
        self.monitor = monitor
        self._saved: Any = None

    def __enter__(self) -> _Monitor:
        self._saved = ba._gpu_monitor
        ba.set_gpu_monitor(self.monitor)  # type: ignore[arg-type]
        return self.monitor

    def __exit__(self, *exc: object) -> None:
        ba._gpu_monitor = self._saved


BP_MSG = "Backpressure active due to critical GPU memory pressure"
BP_BOGUS = ("XXpressure_levelXX", "PRESSURE_LEVEL")


def test_backpressure_critical_returns_true_and_logs_exact_warning() -> None:
    agg = BatchAggregator(redis_client=None)
    with (
        _MonitorSetter(_Monitor(level=MemoryPressureLevel.CRITICAL)),
        LogCapture() as cap,
    ):
        verdict = _run(agg.should_apply_backpressure())
    assert verdict is True
    rec = cap.one(logging.WARNING, BP_MSG)
    _attrs(
        rec,
        {"pressure_level": MemoryPressureLevel.CRITICAL.value},
        BP_BOGUS,
    )


def test_backpressure_normal_returns_false_and_logs_no_warning() -> None:
    # Polarity guard: only CRITICAL throttles.
    agg = BatchAggregator(redis_client=None)
    with (
        _MonitorSetter(_Monitor(level=MemoryPressureLevel.NORMAL)),
        LogCapture() as cap,
    ):
        verdict = _run(agg.should_apply_backpressure())
    assert verdict is False
    assert cap.at(logging.WARNING, BP_MSG) == []


class _PressureBoomer:
    """``ba.get_memory_pressure_level`` stand-in that RAISES.

    The shipped helper swallows monitor errors and returns NORMAL, so the
    only way to drive ``should_apply_backpressure``'s except arm is a raising
    helper itself — exactly what its docstring invites ("can be mocked in
    tests"). The bare-name call site resolves through the module dict, so the
    patch is seen by the mutant bodies too; the save/restore keeps it honest.
    """

    def __init__(self) -> None:
        self._saved: Any = None

    def __enter__(self) -> None:
        async def boom() -> Any:
            raise BP_BOOM

        self._saved = ba.get_memory_pressure_level
        ba.get_memory_pressure_level = boom  # type: ignore[assignment]

    def __exit__(self, *exc: object) -> None:
        ba.get_memory_pressure_level = self._saved  # type: ignore[assignment]


def test_backpressure_monitor_failure_logs_exact_debug_and_returns_false() -> None:
    agg = BatchAggregator(redis_client=None)
    with _PressureBoomer(), LogCapture() as cap:
        verdict = _run(agg.should_apply_backpressure())
    assert verdict is False
    rec = cap.one(logging.DEBUG, f"Error checking backpressure: {BP_BOOM}")
    assert rec.getMessage() == f"Error checking backpressure: {BP_BOOM}"
    _attrs(
        rec,
        {"error": str(BP_BOOM), "error_type": "RuntimeError"},
        ("XXerrorXX", "ERROR", "XXerror_typeXX", "ERROR_TYPE"),
    )


# =============================================================================
# Pool M — _create_batch_metadata_atomic (20 keys)
# =============================================================================
class FakePipe:
    """Records every ``set`` as an exact (args, kwargs) pair; ``execute`` spies."""

    def __init__(self, *, boom: bool = False) -> None:
        self.sets: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self.executes = 0
        self._boom = boom

    def set(self, *args: Any, **kwargs: Any) -> None:
        self.sets.append((args, kwargs))

    async def execute(self) -> None:
        self.executes += 1
        if self._boom:
            raise EXEC_BOOM


class _PipeCM:
    """``async with client.pipeline(...) as pipe`` — hands out the FakePipe."""

    def __init__(self, pipe: FakePipe) -> None:
        self.pipe = pipe

    async def __aenter__(self) -> FakePipe:
        return self.pipe

    async def __aexit__(self, *exc: object) -> None:
        return None


class FakePipelineClient:
    def __init__(self, *, boom: bool = False) -> None:
        self.pipe = FakePipe(boom=boom)
        self.pipeline_kwargs: list[dict[str, Any]] = []

    def pipeline(self, **kwargs: Any) -> _PipeCM:
        self.pipeline_kwargs.append(kwargs)
        return _PipeCM(self.pipe)


class FakeRedisWithClient:
    def __init__(self, client: FakePipelineClient) -> None:
        self._client = client


class GuardRedis:
    """redis object present, its ``_client`` absent — the shipped guard case."""

    _client = None


def _meta_agg(*, boom: bool = False) -> tuple[BatchAggregator, FakePipelineClient, FakePipe]:
    client = FakePipelineClient(boom=boom)
    return BatchAggregator(redis_client=FakeRedisWithClient(client)), client, client.pipe  # type: ignore[arg-type]


def _raises(want: type[BaseException], call: Any) -> BaseException:
    """Captures ONLY the declared exception type (D's discipline)."""
    try:
        call()
    except want as exc:
        return exc
    raise AssertionError(f"expected {want.__name__}")


META_EXPECTED = [
    ((BKEY, BID), {"ex": TTL}),
    ((f"batch:{BID}:camera_id", CAM), {"ex": TTL}),
    ((f"batch:{BID}:started_at", str(T0)), {"ex": TTL}),
    ((f"batch:{BID}:last_activity", str(T0)), {"ex": TTL}),
]


def test_meta_guard_rejects_redis_without_client() -> None:
    agg = BatchAggregator(redis_client=GuardRedis())  # type: ignore[arg-type]
    exc = _raises(
        RuntimeError,
        lambda: _run(agg._create_batch_metadata_atomic(BKEY, BID, CAM, T0, TTL)),
    )
    assert str(exc) == "Redis client not initialized"


def test_meta_sets_exact_keys_values_and_ttls() -> None:
    # One assertion over the full call list kills every key->None, value->None,
    # str(None), ex-dropped and ex=None mutant on the four unconditional sets.
    agg, client, pipe = _meta_agg()
    _run(agg._create_batch_metadata_atomic(BKEY, BID, CAM, T0, TTL))
    assert client.pipeline_kwargs == [{"transaction": True}]
    assert pipe.sets == META_EXPECTED
    assert pipe.executes == 1


def test_meta_appends_pipeline_start_time_when_given() -> None:
    agg, _, pipe = _meta_agg()
    _run(agg._create_batch_metadata_atomic(BKEY, BID, CAM, T0, TTL, pipeline_start_time=PST))
    assert pipe.sets == [
        *META_EXPECTED,
        ((f"batch:{BID}:pipeline_start_time", PST), {"ex": TTL}),
    ]


def test_meta_omits_pipeline_start_time_when_none() -> None:
    agg, _, pipe = _meta_agg()
    _run(agg._create_batch_metadata_atomic(BKEY, BID, CAM, T0, TTL, pipeline_start_time=None))
    assert pipe.sets == META_EXPECTED


def test_meta_execute_failure_logs_exact_error_and_reraises() -> None:
    agg, _, pipe = _meta_agg(boom=True)
    with LogCapture() as cap:
        exc = _raises(
            RuntimeError,
            lambda: _run(agg._create_batch_metadata_atomic(BKEY, BID, CAM, T0, TTL)),
        )
    assert exc is EXEC_BOOM
    assert pipe.executes == 1
    rec = cap.one(logging.ERROR, "Atomic batch metadata creation failed - transaction rolled back")
    _attrs(
        rec,
        {"batch_id": BID, "camera_id": CAM, "error": str(EXEC_BOOM)},
        ("XXbatch_idXX", "BATCH_ID", "XXcamera_idXX", "CAMERA_ID", "XXerrorXX", "ERROR"),
    )


# =============================================================================
# Pool R — recover_orphaned_detections (48 keys)
# =============================================================================
class _Det:
    """One orphaned detection row (only the load_only columns + id matter)."""

    def __init__(self, id_: str, camera: str) -> None:
        self.id = id_
        self.camera_id = camera
        self.file_path = f"/frames/{id_}.jpg"
        self.confidence = 0.87
        self.object_type = "person"


class _Recorder:
    """Captures the exact SQLAlchemy expression the shipped builder builds."""

    def __init__(self) -> None:
        self.outerjoin_on: list[tuple[Any, ...]] = []
        self.wheres: list[Any] = []
        self.load_only: tuple[str, ...] | None = None
        self.ordered_by: Any = None
        self.limit: Any = _MISS


class _Col:
    """Detection/EventDetection column stub; operators RECORD, never evaluate."""

    def __init__(self, name: str, rec: _Recorder) -> None:
        self._name = name
        self._rec = rec

    def is_(self, other: Any) -> Any:
        return ("IS", self._name, other)

    def __lt__(self, other: Any) -> Any:
        return ("LT", self._name, other)

    def asc(self) -> Any:
        return ("ASC", self._name)

    # The shipped join clause is built with ==; recording it (and letting
    # != / other comparisons fall back to identity) is what makes the
    # on-clause -> None and on-clause -> dropped mutants observable.
    def __eq__(self, other: Any) -> Any:
        return ("EQ", self._name, getattr(other, "_name", other))

    def __hash__(self) -> int:
        return hash(self._name)


class _Model:
    """Model stub: every referenced attribute is a recording _Col."""

    def __init__(self, names: tuple[str, ...], rec: _Recorder) -> None:
        for name in names:
            setattr(self, name, _Col(name, rec))


class _LoadOnly:
    def __init__(self, cols: tuple[Any, ...]) -> None:
        self.cols = cols


class _Select:
    def __init__(self, rec: _Recorder) -> None:
        self._rec = rec

    def outerjoin(self, _target: Any, *on: Any) -> _Select:
        self._rec.outerjoin_on.append(tuple(on))
        return self

    def where(self, *conditions: Any) -> _Select:
        self._rec.wheres.extend(conditions)
        return self

    def options(self, *opts: _LoadOnly) -> _Select:
        assert self._rec.load_only is None, "options() called twice"
        self._rec.load_only = tuple(col._name for col in opts[0].cols)
        return self

    def order_by(self, clause: Any) -> _Select:
        self._rec.ordered_by = clause
        return self

    def limit(self, n: int) -> _Select:
        self._rec.limit = n
        return self


class _Result:
    def __init__(self, dets: list[_Det]) -> None:
        self._dets = dets

    def scalars(self) -> _Result:
        return self

    def all(self) -> list[_Det]:
        return self._dets


class _Session:
    def __init__(self, dets: list[_Det], *, boom: bool) -> None:
        self._dets = dets
        self._boom = boom
        self.executed: list[_Select] = []

    async def execute(self, stmt: _Select) -> _Result:
        if self._boom:
            raise DB_BOOM
        self.executed.append(stmt)
        return _Result(self._dets)

    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


class _DateTime(datetime):
    """``ba.datetime`` shim so the cutoff computation is deterministic."""

    @staticmethod
    def now(tz: Any = None) -> datetime:
        return T0DT.astimezone(tz) if tz is not None else T0DT


class _RecoverStubs:
    """Installs the five in-function-import targets + the clock shim.

    ``dets`` become the query result; ``boom`` makes ``execute`` raise, driving
    the outer except arm.
    """

    STUBBED = (
        "sqlalchemy",
        "sqlalchemy.orm",
        "backend.core.database",
        "backend.models.detection",
        "backend.models.event_detection",
    )

    def __init__(self, dets: list[_Det], *, boom: bool = False) -> None:
        self.rec = _Recorder()
        self.session = _Session(dets, boom=boom)
        self._saved: dict[str, Any] = {}

    def __enter__(self) -> _RecoverStubs:
        rec = self.rec
        detection = _Model(
            ("id", "camera_id", "file_path", "confidence", "object_type", "detected_at"), rec
        )
        event_detection = _Model(("event_id", "detection_id"), rec)

        sa = types.ModuleType("sqlalchemy")

        def select(*entities: Any) -> _Select:
            assert entities == (detection,)
            return _Select(rec)

        sa.select = select  # type: ignore[attr-defined]
        sa_orm = types.ModuleType("sqlalchemy.orm")
        sa_orm.load_only = lambda *cols: _LoadOnly(cols)  # type: ignore[attr-defined]

        db = types.ModuleType("backend.core.database")
        db.get_session = lambda: self.session  # type: ignore[attr-defined]

        det_mod = types.ModuleType("backend.models.detection")
        det_mod.Detection = detection  # type: ignore[attr-defined]
        ed_mod = types.ModuleType("backend.models.event_detection")
        ed_mod.EventDetection = event_detection  # type: ignore[attr-defined]

        for name, mod in zip(self.STUBBED, (sa, sa_orm, db, det_mod, ed_mod), strict=True):
            self._saved[name] = sys.modules.get(name, _MISS)
            sys.modules[name] = mod
        self._saved_dt = ba.datetime
        ba.datetime = _DateTime  # type: ignore[misc]
        return self

    def __exit__(self, *exc: object) -> None:
        ba.datetime = self._saved_dt  # type: ignore[misc]
        for name in reversed(self.STUBBED):
            saved = self._saved[name]
            if saved is _MISS:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = saved


class RecoverAgg(BatchAggregator):
    """Spies add_detection; ``boom`` is the detection_id whose add raises."""

    def __init__(self, *, boom: str | None = None) -> None:
        super().__init__(redis_client=None)
        self.added: list[dict[str, Any]] = []
        self.boom = boom

    async def add_detection(self, **kwargs: Any) -> None:
        self.added.append(kwargs)
        if kwargs.get("detection_id") == self.boom:
            raise DB_BOOM


RECOV_MSG_CAM = "Recovered orphaned detections for camera"
RECOV_MSG_ALL = "Recovered orphaned detections across cameras"
RECOV_MSG_DET = "Failed to recover orphaned detection"
RECOV_MSG_FAIL = "Orphaned detection recovery failed"


def _check_query(rec: _Recorder) -> None:
    """The stmt-shape assertions (keys 14, 16, 25) + full query honesty."""
    # One tuple per outerjoin holding its on-clause exprs: key 14 gives
    # [(None,)], key 16 gives [] — both distinguishable from shipped.
    assert rec.outerjoin_on == [(("EQ", "id", "detection_id"),)], rec.outerjoin_on
    cutoff = T0DT - timedelta(minutes=ba.ORPHAN_MIN_AGE_MINUTES)
    assert rec.wheres == [("IS", "event_id", None), ("LT", "detected_at", cutoff)]
    # load_only(Detection.id, ...) — the id arg-drop (key 25) is visible here.
    assert rec.load_only == ("id", "camera_id", "file_path", "confidence", "object_type")
    assert rec.ordered_by == ("ASC", "detected_at")
    assert rec.limit == ba.ORPHAN_RECOVERY_LIMIT


def test_recover_no_orphans_returns_zero_and_logs_nothing() -> None:
    agg = RecoverAgg()
    with _RecoverStubs([]), LogCapture() as cap:
        assert _run(ba.recover_orphaned_detections(agg)) == 0
    assert agg.added == []
    assert cap.records == []


def test_recover_reinjects_exact_kwargs_and_logs_exact_warnings() -> None:
    d1, d2, d3 = _Det("det-1", CAM), _Det("det-2", CAM), _Det("det-3", CAM2)
    agg = RecoverAgg()
    stubs = _RecoverStubs([d1, d2, d3])
    with stubs, LogCapture() as cap:
        assert _run(ba.recover_orphaned_detections(agg)) == 3
    _check_query(stubs.rec)
    assert [a["detection_id"] for a in agg.added] == ["det-1", "det-2", "det-3"]
    for det, added in zip([d1, d2, d3], agg.added, strict=True):
        assert added == {
            "camera_id": det.camera_id,
            "detection_id": det.id,
            "_file_path": det.file_path,
            "confidence": det.confidence,
            "object_type": det.object_type,
        }
    cam_recs = cap.at(logging.WARNING, RECOV_MSG_CAM)
    assert len(cam_recs) == 2
    for rec, (cam, count) in zip(cam_recs, ((CAM, 2), (CAM2, 1)), strict=True):
        _attrs(
            rec,
            {"camera_id": cam, "detection_count": count},
            ("XXcamera_idXX", "CAMERA_ID", "XXdetection_countXX", "DETECTION_COUNT"),
        )
    _attrs(
        cap.one(logging.WARNING, RECOV_MSG_ALL),
        {"total_recovered": 3, "camera_count": 2},
        ("XXtotal_recoveredXX", "TOTAL_RECOVERED", "XXcamera_countXX", "CAMERA_COUNT"),
    )


def test_recover_detection_failure_logs_exact_error_and_continues() -> None:
    # det-2's add raises; det-3 on the OTHER camera must still be recovered.
    d1, d2, d3 = _Det("det-1", CAM), _Det("det-2", CAM), _Det("det-3", CAM2)
    agg = RecoverAgg(boom="det-2")
    with _RecoverStubs([d1, d2, d3]), LogCapture() as cap:
        assert _run(ba.recover_orphaned_detections(agg)) == 2
    rec = cap.one(logging.ERROR, RECOV_MSG_DET)
    _attrs(
        rec,
        {"detection_id": "det-2", "camera_id": CAM, "error": str(DB_BOOM)},
        ("XXdetection_idXX", "DETECTION_ID", "XXcamera_idXX", "CAMERA_ID", "XXerrorXX", "ERROR"),
    )
    cam_recs = cap.at(logging.WARNING, RECOV_MSG_CAM)
    assert len(cam_recs) == 2  # the partially failed camera still reports its scan
    _attrs(
        cap.one(logging.WARNING, RECOV_MSG_ALL),
        {"total_recovered": 2, "camera_count": 2},
        ("XXtotal_recoveredXX", "TOTAL_RECOVERED", "XXcamera_countXX", "CAMERA_COUNT"),
    )


def test_recover_query_failure_logs_exact_error_with_exc_info_and_returns_zero() -> None:
    agg = RecoverAgg()
    with _RecoverStubs([], boom=True), LogCapture() as cap:
        assert _run(ba.recover_orphaned_detections(agg)) == 0
    rec = cap.one(logging.ERROR, RECOV_MSG_FAIL)
    _attrs(rec, {"error": str(DB_BOOM)}, ("XXerrorXX", "ERROR"))
    assert rec.exc_info is not None and rec.exc_info is not False
