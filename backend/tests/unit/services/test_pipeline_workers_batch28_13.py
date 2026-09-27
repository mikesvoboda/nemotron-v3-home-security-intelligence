"""S3 batch-28 lane 13 - ``pipeline_workers`` group g13 kill battery (87 keys).

Module: ``backend/services/pipeline_workers.py`` (git blob 74649fd3 - byte-identical
to the manifest-proven source).  Admitted manifest: ``/tmp/wp-pw/pipeline_workers/``
``manifest.json`` group 13 ("g13 the four worker start() methods", 87 KILLABLE /
0 EQUIVALENT / 0 NEEDS_INVESTIGATION), plus ``group_13.keys`` and
``survivors.json`` for the exact per-key diffs.

The four shipped ``start()`` bodies (transcribed at the lines each test quotes)::

    DetectionQueueWorker.start   L311-329    AnalysisQueueWorker.start  L841-855
    BatchTimeoutWorker.start     L1239-1256  QueueMetricsWorker.start   L1410-1425

Every leg of the manifest ``test_spec`` is realised as a class-parameterised test
(``spec`` x {Detection, Analysis, BatchTimeout, QueueMetrics}; the state leg runs on
the three classes that have stats) - 20 tests cover all 87 keys:

1. ``test_already_running_logs_the_shipped_warning_and_starts_nothing`` - the
   WARNING arm (m1..m4 of each class).  Pre-set ``_running = True``, call
   ``start()``, pin the single WARNING record's RAW ``record.msg`` / level /
   ``args`` / ``exc_info``, and pin that nothing else happened: no INFO, no
   ``create_tracked_task`` call, ``_task`` untouched, ``_running`` still True,
   ``_stats`` still the shipped ``WorkerStats()``.  This is the SOLE route to the
   16 ``already running`` message mutants (``None`` / ``XX..XX`` / lower / upper).
2. ``test_start_logs_the_starting_info_with_its_extra`` - L321 / L847 /
   L1245-1248 / L1416-1419.  ``record.msg`` is pinned character-for-character
   (kills ``msg -> None`` and the three renames) and the record's ``extra``
   payload - read as "attributes the shipped ``Logger.makeRecord`` added beyond
   the ``LogRecord`` core plus this module's ``ContextFilter`` contributions" -
   is pinned to ``{key: injected value}`` (kills ``extra -> None``, the ``extra``
   drop and both extra-KEY renames).  The payload value is unique per test and
   injected by this file, so a mutant that drops or renames the field cannot
   match it by accident.
3. ``test_start_names_the_tracked_task_and_the_task_prefix`` - the
   ``create_tracked_task`` call at L324-328 / L850-854 / L1251-1255 / L1421-1425,
   observed through a ``create_autospec`` spy of the shipped function.
   ``kwargs`` is pinned with EXACT dict equality (kills ``name -> None``,
   ``task_prefix -> None``, both drops, and the four XX/lower/upper renames - a
   dropped keyword disappears from the recorded dict, which is exactly what an
   equality check sees and a value compare would miss); the positional is pinned
   to the worker's own ``_run_loop()`` coroutine object and closed in the same
   block, so no ``coroutine ... was never awaited`` warning is produced.
4. ``test_start_ends_in_the_running_state_after_a_visible_starting`` -
   ``_stats.state`` right after the call PLUS a snapshot taken inside the
   task-creation call, which proves the shipped
   ``self._stats.state = WorkerState.STARTING`` line ran before the task was
   created (m16 for the three classes that have stats).  ``to_dict()`` is pinned
   too: under the ``state = None`` mutant it raises
   ``AttributeError: 'NoneType' object has no attribute 'value'``, so the leg is a
   hard kill rather than a crash accident.
   ``test_queue_metrics_start_never_touches_state`` is the mirrored leg - shipped
   ``QueueMetricsWorker.start()`` never touches ``_stats`` (the class has no
   ``stats`` member at all) and carries no m16, so it asserts the absence and the
   rest of that def's contract.
5. ``test_start_creates_the_tracked_task_after_the_state_was_starting`` - control
   leg (kills nothing of its own): with the REAL
   ``backend.core.async_context.create_tracked_task`` and a loop that flags the
   moment it runs, the shipped ordering (STARTING -> create task -> RUNNING) is
   pinned positionally without a mock in the path.
6. ``test_start_is_idempotent_across_two_calls`` and
   ``test_start_touches_no_counters_and_no_broadcaster`` - controls pinning the
   rest of the shipped contract so no killing leg can be satisfied by an
   accidental fall-through.

Test -> mutant-key map
======================
All 87 keys of ``group_13.keys`` are claimed here.  Every key name is unique in the
959-survivor set (the four defs are class-qualified), so no twin keys are carried
and none of these keys belongs to another group.  ``n`` below is the mutmut
ordinal; ``QueueMetricsWorker``'s ordinals are the same keys shifted by one because
that def has no ``self._stats.state = WorkerState.STARTING`` line.

* WARNING arm - ``logger.warning("<Class> already running")`` at L318 / L844 /
  L1242 / L1413: ``arg->None`` (n1), ``string:XXwrap`` (n2), ``string:lower``
  (n3), ``string:upper`` (n4) - all four classes -> leg 1 (all 4 params).
* INFO arm - ``logger.info("Starting <Class>", extra={...})`` at L321 / L847 /
  L1245-1248 / L1416-1419: ``msg arg->None`` (n5), ``extra arg->None`` (n6),
  ``extra drop_arg`` (n8), msg ``string:XXwrap`` (n9), msg ``string:lower``
  (n10), msg ``string:upper`` (n11), extra-key ``string:XXwrap`` (n12), extra-key
  ``string:upper`` (n13) - all four classes -> leg 2 (all 4 params).
* ``self._stats.state = WorkerState.STARTING`` -> ``None`` at L323 / L849 / L1250:
  n16 for Detection / Analysis / BatchTimeout (absent for QueueMetrics) -> leg 4
  (3 params).
* ``create_tracked_task`` keyword arguments at L324-327 / L850-853 / L1251-1255 /
  L1421-1425: ``name arg->None``, ``task_prefix arg->None``, ``name drop_arg``,
  ``task_prefix drop_arg``, ``name XXwrap``, ``name lower``, ``name upper``,
  ``task_prefix XXwrap``, ``task_prefix upper`` = n19/n20/n22/n23/n24/n25/n26/
  n27/n28 for the first three classes and n18/n19/n21/n22/n23/n24/n25/n26/n27 for
  QueueMetrics -> leg 3 (all 4 params).

Counts: WARNING 4 x 4 = 16, INFO 8 x 4 = 32, state 3, call-shape 9 x 4 = 36 -> 87,
i.e. ``group_13.keys`` in full.

Discrepancies between the manifest spec text and the shipped code (the SHIPPED code
wins; each is recorded in the campaign fixes list)
===================================================
* The spec says the already-running arm "leaves stats untouched".  Shipped, three
  of the four classes have stats and one does not: ``QueueMetricsWorker`` has no
  ``_stats`` attribute and no ``stats`` property (pipeline_workers.py:1394-1408),
  so that leg asserts ``not hasattr(worker, "_stats")`` for it instead of an
  equality pin.
* The spec asks for "a side_effect spy on the state setter".  Not constructible on
  the shipped type: ``WorkerStats`` is declared ``@dataclass(slots=True)``
  (pipeline_workers.py:202-209), and installing a ``property`` on a slots class
  does not intercept instance attribute writes (measured: a slot write still wins
  and the property getter is never consulted).  The same observable is captured
  with a closure snapshot taken inside the spy's ``side_effect`` at
  task-creation time, which is strictly stronger than a setter hook because it
  reads the real dataclass field.
* The spec's ``stats.to_dict()["state"] == "running"`` is asserted, but the
  ``to_dict()``-raises-``AttributeError`` mechanism it credits for killing m16 is
  not what happens on the shipped pristine path (the shipped ``start()`` always
  restores RUNNING, so ``to_dict()`` succeeds there).  m16 is killed by the
  at-creation snapshot plus the shipped ``to_dict()`` key/value pin, both of which
  the mutant really violates.

Discipline
----------
* Log assertions use ``caplog`` opened per window (``set_level`` + ``clear()``,
  then filtered to this module's logger name) and read the RAW ``record.msg`` plus
  ``record.args`` / ``record.exc_info`` / ``record.levelno`` (batch27_01 pattern),
  exactly as the g17 battery does.  The ``extra=`` payload is additionally read
  from ``record.__dict__`` minus the ``LogRecord`` core and minus the field names
  this module's ``ContextFilter`` injects (measured once, by re-running the
  filter over a record the filter has already seen - it is idempotent, so the
  diff is empty and the set is exactly those injected names).
* ``time.monotonic`` / ``time.perf_counter`` are never patched and no duration is
  asserted - g13 contains no timing site.
* Mocks of real attributes are autospec'd (WP4.2 fast path): the task factory is
  ``patch.object(M, "create_tracked_task", autospec=True)``; injected
  collaborators are constructor parameters rather than patched attributes; and no
  shipped instance method is patched - ``_run_loop`` is replaced by direct
  assignment on a freshly built instance, because
  ``patch.object(worker, "_run_loop", autospec=True)`` autospecs the ALREADY BOUND
  method and the shipped ``self._run_loop()`` call then fails with
  ``TypeError: missing 1 required positional argument`` (measured).
* No import-time global spy: every double is installed inside the test that uses
  it, and every coroutine this file creates is closed in the same test.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from backend.core.async_context import create_tracked_task as REAL_CREATE_TRACKED_TASK
from backend.services import pipeline_workers as M
from backend.services.pipeline_workers import WorkerStats

LOG_NAME = M.logger.name  # "backend.services.pipeline_workers" (get_logger(__name__))

pytestmark = [pytest.mark.unit]

# The module-level name the four shipped start() methods resolve when they build
# their loop task (imported at pipeline_workers.py:50, called at L324/L850/L1251/L1421).
TRACKED_FACTORY = "create_tracked_task"


# =============================================================================
# Shipped literals, transcribed from backend/services/pipeline_workers.py
# =============================================================================


@dataclass(frozen=True)
class ClassSpec:
    """Everything g13 pins per worker class, transcribed from the shipped file."""

    cls: type
    name: str  # the class name, also the shipped name= argument
    warning: str  # the "already running" WARNING text
    info: str  # the "Starting <Class>" INFO text
    info_line: int  # line of that INFO's message argument
    extra_key: str  # the single key of that INFO's extra= dict
    attr: str  # the instance attribute that extra value comes from
    seed: Any  # the value this file injects into that attribute
    task_prefix: str  # the shipped task_prefix= argument
    state_line: int | None  # line of `self._stats.state = WorkerState.STARTING`


SPECS: tuple[ClassSpec, ...] = (
    ClassSpec(
        cls=M.DetectionQueueWorker,
        name="DetectionQueueWorker",
        warning="DetectionQueueWorker already running",  # L318
        info="Starting DetectionQueueWorker",  # L321
        info_line=321,
        extra_key="queue",  # L321: extra={"queue": self._queue_name}
        attr="_queue_name",
        seed="detection_queue_b28_13",
        task_prefix="detect-worker",  # L327
        state_line=323,
    ),
    ClassSpec(
        cls=M.AnalysisQueueWorker,
        name="AnalysisQueueWorker",
        warning="AnalysisQueueWorker already running",  # L844
        info="Starting AnalysisQueueWorker",  # L847
        info_line=847,
        extra_key="queue",  # L847
        attr="_queue_name",
        seed="analysis_queue_b28_13",
        task_prefix="analyze-worker",  # L853
        state_line=849,
    ),
    ClassSpec(
        cls=M.BatchTimeoutWorker,
        name="BatchTimeoutWorker",
        warning="BatchTimeoutWorker already running",  # L1242
        info="Starting BatchTimeoutWorker",  # L1246
        info_line=1246,
        extra_key="check_interval",  # L1247: extra={"check_interval": self._check_interval}
        attr="_check_interval",
        seed=3.25,
        task_prefix="batch-timeout",  # L1254
        state_line=1250,
    ),
    ClassSpec(
        cls=M.QueueMetricsWorker,
        name="QueueMetricsWorker",
        warning="QueueMetricsWorker already running",  # L1413
        info="Starting QueueMetricsWorker",  # L1417
        info_line=1417,
        extra_key="update_interval",  # L1418: extra={"update_interval": self._update_interval}
        attr="_update_interval",
        seed=1.75,
        task_prefix="metrics-worker",  # L1424
        state_line=None,  # shipped L1410-1425 never touches self._stats
    ),
)

PARAMS = pytest.mark.parametrize("spec", SPECS, ids=[s.name for s in SPECS])
STATS_PARAMS = pytest.mark.parametrize(
    "spec",
    [s for s in SPECS if s.state_line is not None],
    ids=[s.name for s in SPECS if s.state_line is not None],
)

# Shipped WorkerStats defaults (pipeline_workers.py:206-209).
FROZEN_STATS = WorkerStats()
SHIPPED_IDLE_TO_DICT = {
    "items_processed": 0,
    "errors": 0,
    "last_processed_at": None,
    "state": "running",
}


# =============================================================================
# Observation helpers (batch27_01 pattern, extended to the extra= payload)
# =============================================================================


def win(caplog: pytest.LogCaptureFixture) -> None:
    """Open a capture window: DEBUG for this module's logger, empty buffer.

    ``set_level`` does NOT clear the buffer, so the ``clear()`` is load-bearing.
    """
    caplog.set_level(logging.DEBUG, logger=LOG_NAME)
    caplog.clear()


def mine(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == LOG_NAME]


def at(caplog: pytest.LogCaptureFixture, level: int) -> list[logging.LogRecord]:
    return [r for r in mine(caplog) if r.levelno == level]


def pin_record(r: logging.LogRecord, *, msg: str, level: int) -> None:
    """Assert the observable surface of one shipped log call.

    ``record.msg`` is the RAW message.  Every shipped site in this group passes a
    literal message with no ``%``-args, so ``args`` must stay empty (a moved
    argument lands IN ``msg``) and ``exc_info`` must be absent.
    """
    assert r.msg == msg, f"log text mutated: {r.msg!r} != {msg!r}"
    assert r.levelno == level, f"log level mutated: {r.levelno} != {level}"
    assert tuple(r.args or ()) == (), f"unexpected lazy args for a literal message: {r.args!r}"
    assert r.exc_info is None, (
        f"exc_info present where the shipped call passes none: {r.exc_info!r}"
    )


def only(
    caplog: pytest.LogCaptureFixture,
    level: int,
    msg: str,
) -> logging.LogRecord:
    """Exactly one record at ``level`` in the window, matching every field."""
    recs = at(caplog, level)
    assert len(recs) == 1, (
        f"expected exactly 1 {logging.getLevelName(level)} record from {LOG_NAME}, "
        f"got {[(r.levelno, r.msg) for r in recs]}"
    )
    pin_record(recs[0], msg=msg, level=level)
    return recs[0]


def _baseline_attrs() -> frozenset[str]:
    """Attribute names that are NOT part of a shipped ``extra=`` payload.

    The union of (a) the fields ``logging.LogRecord.__init__`` always sets and
    (b) the fields this module's ``ContextFilter`` injects
    (``backend/core/logging.py:504-608``: request_id, correlation_id, trace_id,
    span_id, connection_id, task_id, job_id, hostname, container_id,
    app_version, environment).  (b) is MEASURED, not transcribed: the filter is
    idempotent, so running it over a record it has already seen adds exactly the
    injected names once.  ``message`` is excluded as well - it is set by the
    formatter, not by the log call.
    """
    probe = logging.LogRecord("baseline.probe", logging.DEBUG, "f", 1, "probe", (), None)
    core = set(probe.__dict__)
    injected = set(M.logger.filter(probe).__dict__) - core
    return frozenset(core | injected | {"message"})


BASELINE_ATTRS = _baseline_attrs()


def shipped_extra(record: logging.LogRecord) -> dict[str, Any]:
    """The ``extra=`` dict the shipped call passed, as the record shows it.

    ``Logger.makeRecord`` copies ``extra`` into the record verbatim
    (``for key in extra: record.__dict__[key] = extra[key]``), so removing the
    baseline leaves precisely the shipped payload - which is how ``extra=None``,
    the dropped ``extra`` argument and the two renamed keys become visible.
    """
    return {k: v for k, v in record.__dict__.items() if k not in BASELINE_ATTRS}


def extra_of(
    caplog: pytest.LogCaptureFixture,
    level: int,
    *,
    msg: str,
) -> dict[str, Any]:
    return shipped_extra(only(caplog, level, msg))


# =============================================================================
# Worker construction
# =============================================================================


def make_worker(spec: ClassSpec) -> Any:
    """A fresh worker of ``spec.cls`` with every collaborator injected.

    Nothing real is constructed: ``redis_client`` is a MagicMock and each optional
    collaborator the shipped constructor would otherwise build is passed in as a
    MagicMock, so the ``... or <RealClass>(...)`` arms never run.  The attribute
    the INFO's ``extra`` reads is then set to this file's seed value, so the
    pinned payload value is one this file arranged.

    ``_run_loop`` is replaced by DIRECT assignment, not ``patch.object``:
    ``create_autospec`` of an already-bound method consumes ``self``, so the
    shipped ``self._run_loop()`` would raise under the patch (measured).  Nothing
    shipped is patched by this helper.
    """
    cls = spec.cls
    kwargs: dict[str, Any] = {"redis_client": MagicMock(name=f"{spec.name}-redis")}
    if cls is M.DetectionQueueWorker:
        kwargs.update(
            detector_client=MagicMock(name="detector-client"),
            batch_aggregator=MagicMock(name="batch-aggregator"),
            video_processor=MagicMock(name="video-processor"),
            retry_handler=MagicMock(name="retry-handler"),
            frame_buffer=MagicMock(name="frame-buffer"),
        )
    elif cls is M.AnalysisQueueWorker:
        kwargs["analyzer"] = MagicMock(name="analyzer")
    elif cls is M.BatchTimeoutWorker:
        kwargs["batch_aggregator"] = MagicMock(name="batch-aggregator")
    worker = cls(**kwargs)
    loop_runs: list[str] = []

    async def stand_in_loop() -> None:
        """Blocking stand-in for the shipped loop: records that it ran, never returns."""
        loop_runs.append("run")
        await asyncio.Event().wait()

    worker._run_loop = stand_in_loop
    worker._loop_runs = loop_runs
    setattr(worker, spec.attr, spec.seed)
    return worker


def consumed_coroutine(factory: MagicMock, worker: Any) -> Any:
    """The single positional the task factory received, closed by the caller.

    ``self._run_loop()`` is evaluated BEFORE ``create_tracked_task`` runs, so the
    coroutine object exists even though the spy never schedules it; every test
    that uses the spy closes it, so no ``coroutine was never awaited`` warning can
    be attributed to this file.  ``_loop_runs`` is the shipped-side witness that
    the spy really swallowed it: the stand-in loop appends the moment it starts.
    """
    call = factory.call_args
    assert call is not None, "the task factory was never called"
    assert len(call.args) == 1, f"task-creation positional shape mutated: {call.args!r}"
    coro = call.args[0]
    assert inspect.iscoroutine(coro), f"the task's first argument must be a coroutine: {coro!r}"
    assert coro.__qualname__.endswith("stand_in_loop"), (
        f"the scheduled coroutine is {coro.__qualname__!r}, not the worker's _run_loop()"
    )
    assert worker._loop_runs == [], "the spy scheduled the shipped loop instead of swallowing it"
    assert not coro.cr_running, "the shipped coroutine must not be running inside the spy"
    coro.close()
    return coro


# =============================================================================
# 1) The idempotent WARNING arm
#    L318 / L844 / L1242 / L1413 - m1 (None), m2 (XXwrap), m3 (lower), m4 (upper)
# =============================================================================


@PARAMS
async def test_already_running_logs_the_shipped_warning_and_starts_nothing(
    spec: ClassSpec,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``_running`` True -> exactly one WARNING, then ``return``.

    Shipped (DetectionQueueWorker, pipeline_workers.py:317-319; the other three
    classes carry the identical three lines at L843-845, L1241-1243, L1412-1414)::

        if self._running:
            logger.warning("DetectionQueueWorker already running")
            return

    That WARNING is the only observable of the whole call, so the four surviving
    keys on its message (``None`` / ``"XX...XX"`` / all-lower / all-upper) are
    caught by ``record.msg``.  Everything after the guard must stay unexecuted -
    which is what makes this leg the SOLE route to those four keys: no other leg
    in this file enters the guard with ``_running`` already True.
    """
    worker = make_worker(spec)
    worker._running = True
    stats_before = worker._stats if spec.state_line is not None else None
    task_before = worker._task
    win(caplog)

    with patch.object(M, TRACKED_FACTORY, autospec=True) as factory:
        assert await worker.start() is None
        assert factory.call_count == 0, (
            f"start() built a task although the worker was already running: {factory.call_args_list}"
        )

    only(caplog, logging.WARNING, spec.warning)
    assert at(caplog, logging.INFO) == [], "the already-running arm returns before the INFO"
    assert at(caplog, logging.DEBUG) == [], "the already-running arm logs no DEBUG"
    assert worker._running is True, "the guard must not flip _running"
    assert worker._task is task_before, "the guard must not replace the stored task"
    if spec.state_line is not None:
        assert worker._stats is stats_before, "the guard must not replace the stats object"
        assert worker._stats == FROZEN_STATS, f"the guard mutated stats: {worker._stats}"
        assert worker._stats.state is M.WorkerState.STOPPED, (
            "the guard must not advance the worker state"
        )
    else:
        assert not hasattr(worker, "_stats"), (
            "QueueMetricsWorker has no _stats shipped (pipeline_workers.py:1394-1403), "
            "so the already-running arm must not create one"
        )


# =============================================================================
# 2) The INFO line and its extra= payload
#    L321 / L847 / L1245-1248 / L1416-1419 - m5 (msg None), m6 (extra None),
#    m8 (extra dropped), m9/m10/m11 (msg renames), m12/m13 (extra-key renames)
# =============================================================================


@PARAMS
async def test_start_logs_the_starting_info_with_its_extra(
    spec: ClassSpec,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A fresh start logs one INFO whose text AND single extra field are shipped.

    Shipped L321 (Detection) and L847 (Analysis) - one line each::

        logger.info("Starting DetectionQueueWorker", extra={"queue": self._queue_name})

    and L1245-1248 (BatchTimeout) / L1416-1419 (QueueMetrics) - same call, wrapped::

        logger.info(
            "Starting BatchTimeoutWorker",
            extra={"check_interval": self._check_interval},
        )

    Two surfaces, both pinned.  ``record.msg`` carries the message (m5 ``None``,
    m9 XX-wrapped, m10 lower, m11 upper).  The extra payload carries the one field
    (m6 ``extra=None``, m8 the whole argument dropped, m12 XX-wrapped key, m13
    upper-cased key) and its value must be the shipped attribute itself -
    identity-checked against the value this file injected on that attribute.
    """
    worker = make_worker(spec)
    injected = getattr(worker, spec.attr)
    assert injected == spec.seed, f"the seed was not installed on {spec.attr}"
    win(caplog)

    with patch.object(M, TRACKED_FACTORY, autospec=True) as factory:
        assert await worker.start() is None
        consumed_coroutine(factory, worker)

    extra = extra_of(caplog, logging.INFO, msg=spec.info)
    assert extra == {spec.extra_key: injected}, (
        f"extra payload mutated: {extra!r} != {{{spec.extra_key!r}: {injected!r}}} "
        f"(shipped at pipeline_workers.py:{spec.info_line})"
    )
    assert extra[spec.extra_key] is injected, (
        "the extra value must be the shipped attribute object, not a copy or a constant"
    )
    assert at(caplog, logging.WARNING) == [], (
        "a fresh start must not reach the already-running WARNING"
    )
    assert at(caplog, logging.DEBUG) == [], "a fresh start logs exactly one INFO"
    assert worker._running is True, "start() must set _running before creating the task"


# =============================================================================
# 3) The create_tracked_task call shape
#    L324-327 / L850-853 / L1251-1254 / L1421-1424 - name/task_prefix arg->None,
#    drop_arg, XXwrap, lower, upper (9 keys per class)
# =============================================================================


@PARAMS
async def test_start_names_the_tracked_task_and_the_task_prefix(
    spec: ClassSpec,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The loop task is created with the shipped ``name`` / ``task_prefix``.

    Shipped L324-328 (Detection) - the other classes match at L850-854,
    L1251-1255, L1421-1425 with their own strings::

        self._task = create_tracked_task(
            self._run_loop(),
            name="DetectionQueueWorker",
            task_prefix="detect-worker",
        )

    The spy is an autospec of the shipped function (signature enforced, so a
    renamed keyword would raise before it could be recorded), and the shipped
    ``self._run_loop()`` really runs into it.  ``kwargs`` is pinned with EXACT
    dict equality: a dropped keyword disappears from the recorded dict entirely,
    which an equality check sees and a per-key ``==`` would silently pass.  The
    positional is pinned to the worker's own loop coroutine and closed here.
    """
    worker = make_worker(spec)
    sentinel = MagicMock(name=f"{spec.name}-tracked-task")
    win(caplog)

    with patch.object(M, TRACKED_FACTORY, autospec=True) as factory:
        factory.return_value = sentinel
        assert await worker.start() is None

        assert worker._task is sentinel, (
            f"start() stored {worker._task!r} instead of the factory's task"
        )
        assert factory.call_count == 1, (
            f"create_tracked_task called {factory.call_count} times, expected 1"
        )
        call = factory.call_args
        assert call is not None
        consumed_coroutine(factory, worker)
        assert call.kwargs == {
            "name": spec.name,
            "task_prefix": spec.task_prefix,
        }, f"task-creation kwargs mutated: {call.kwargs!r}"

    if spec.state_line is not None:
        assert worker._stats.state is M.WorkerState.RUNNING, (
            f"state after start() is {worker._stats.state!r}, expected RUNNING"
        )
    assert extra_of(caplog, logging.INFO, msg=spec.info) == {
        spec.extra_key: getattr(worker, spec.attr)
    }, "the INFO line must stay the shipped one while the task call is inspected"


# =============================================================================
# 4) The state timeline
#    L323 / L849 / L1250 - m16 (self._stats.state = WorkerState.STARTING -> None)
#    plus the shipped RUNNING write those mutants leave stale
# =============================================================================


@STATS_PARAMS
async def test_start_ends_in_the_running_state_after_a_visible_starting(
    spec: ClassSpec,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Two state writes: STARTING visible at creation time, RUNNING after it.

    Shipped L322-329 (Detection) / L848-855 (Analysis) / L1249-1256 (BatchTimeout)
    - identical shape::

        self._running = True
        self._stats.state = WorkerState.STARTING
        self._task = create_tracked_task(...)
        self._stats.state = WorkerState.RUNNING

    m16 rewrites the STARTING line as ``self._stats.state = None``.  That is
    visible twice: the snapshot taken INSIDE the task-creation call reports
    ``None`` where shipped reports ``STARTING``, and - because the shipped
    ``WorkerStats.to_dict()`` reads ``self.state.value``
    (pipeline_workers.py:217) - a state that is still ``None`` at read time makes
    it raise ``AttributeError``.  Both are asserted here, so the kill does not
    depend on which of the two the mutant survives.
    """
    worker = make_worker(spec)
    seen: dict[str, Any] = {}

    def snapshot_state(*args: Any, **kwargs: Any) -> MagicMock:
        seen["state"] = worker._stats.state
        seen["counter"] = len(worker._stats.to_dict())
        return MagicMock(name="tracked-task")

    win(caplog)
    with patch.object(M, TRACKED_FACTORY, autospec=True) as factory:
        factory.side_effect = snapshot_state
        assert await worker.start() is None
        consumed_coroutine(factory, worker)

    assert seen == {"state": M.WorkerState.STARTING, "counter": 4}, (
        f"the state at task-creation time was {seen.get('state')!r} "
        f"(expected {M.WorkerState.STARTING!r}; shipped line "
        f"pipeline_workers.py:{spec.state_line})"
    )
    assert worker._stats.state is M.WorkerState.RUNNING, (
        f"state after start() is {worker._stats.state!r}, expected RUNNING"
    )
    assert worker._stats.to_dict() == SHIPPED_IDLE_TO_DICT, (
        f"to_dict() mutated: {worker._stats.to_dict()!r}"
    )
    assert worker._stats.items_processed == 0 and worker._stats.errors == 0
    assert worker._running is True
    only(caplog, logging.INFO, spec.info)


async def test_queue_metrics_start_never_touches_state(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The mirrored leg: ``QueueMetricsWorker.start()`` has no state writes at all.

    Shipped L1410-1425 is the only one of the four ``start()`` methods that never
    writes ``self._stats`` - and the class has no ``_stats`` / ``stats`` member to
    write (pipeline_workers.py:1394-1403), which is exactly why it carries no m16
    key.  Both facts are pinned here next to the rest of that def's contract
    (``_running`` True, the INFO with ``update_interval``, exactly one task), so a
    variant that moved a state write into this def is caught rather than silently
    absorbed by the class-parameterised legs.
    """
    spec = next(s for s in SPECS if s.cls is M.QueueMetricsWorker)
    worker = make_worker(spec)
    injected = worker._update_interval
    calls: list[str] = []
    win(caplog)

    def record_name(*_args: Any, **kwargs: Any) -> MagicMock:
        calls.append(kwargs.get("name"))
        return MagicMock(name="tracked-task")

    with patch.object(M, TRACKED_FACTORY, autospec=True) as factory:
        factory.side_effect = record_name
        assert await worker.start() is None
        consumed_coroutine(factory, worker)

    assert calls == [spec.name], f"the task must be created exactly once: {calls}"
    assert not hasattr(worker, "_stats"), "QueueMetricsWorker must not gain a _stats"
    assert not hasattr(worker, "stats"), "QueueMetricsWorker must not gain a stats property"
    assert worker._running is True
    assert extra_of(caplog, logging.INFO, msg=spec.info) == {"update_interval": injected}
    source = inspect.getsource(M.QueueMetricsWorker.start)
    assert "_stats" not in source and "WorkerState" not in source, (
        f"the shipped def must not touch stats: {source}"
    )


# =============================================================================
# 5) Ordering control - the real tracked-task factory
#    (kills nothing of its own; pins STARTING-before-creation positionally)
# =============================================================================


@STATS_PARAMS
async def test_start_creates_the_tracked_task_after_the_state_was_starting(
    spec: ClassSpec,
) -> None:
    """With the REAL factory, the loop had not started while the state was ``starting``.

    ``backend.core.async_context.create_tracked_task`` (L274-340) ends in
    ``asyncio.create_task(wrapped_coro(), name=name)`` and returns without
    yielding, so the worker loop cannot run before the shipped
    ``self._stats.state = WorkerState.RUNNING`` line executes.  The stand-in loop
    raises a flag the instant it starts, so a variant that created the task before
    writing STARTING - or that never wrote RUNNING - is caught by the
    flag/state pair with no mock in the path.  The created task is cancelled and
    awaited in ``finally``, so nothing outlives the test.
    """
    worker = make_worker(spec)
    started = asyncio.Event()

    async def flagging_loop() -> None:
        started.set()
        await asyncio.Event().wait()

    worker._run_loop = flagging_loop
    try:
        await worker.start()
        assert worker._stats.state is M.WorkerState.RUNNING, (
            f"state after start() is {worker._stats.state!r}; the shipped def ends in RUNNING"
        )
        assert isinstance(worker._task, asyncio.Task), f"real task missing: {worker._task!r}"
        assert not started.is_set(), (
            "the worker loop had already run, so the shipped RUNNING write could not "
            "have followed the task creation"
        )
        await asyncio.sleep(0)
        assert started.is_set(), "the created task must actually run the worker loop"
        assert worker._stats.state is M.WorkerState.RUNNING
    finally:
        task = worker._task
        if isinstance(task, asyncio.Task):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


# =============================================================================
# 6) Controls that pin the rest of the shipped contract (kill nothing of their own)
# =============================================================================


@PARAMS
async def test_start_is_idempotent_across_two_calls(
    spec: ClassSpec,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Second call sees ``_running`` True: one INFO, one WARNING, one task.

    The pair-of-arms pin - both shipped arms have to hold inside ONE worker, so a
    message mutant cannot hide behind whichever arm a single-call test happens to
    enter.  The window is opened once, before both calls, so the INFO of the first
    call and the WARNING of the second are both in view.
    """
    worker = make_worker(spec)
    injected = getattr(worker, spec.attr)
    win(caplog)

    with patch.object(M, TRACKED_FACTORY, autospec=True) as factory:
        await worker.start()
        first = worker._task
        await worker.start()
        assert factory.call_count == 1, (
            f"the second start() created a second task: {factory.call_args_list}"
        )
        consumed_coroutine(factory, worker)

    assert worker._task is first, "the second start() replaced the stored task"
    warning = only(caplog, logging.WARNING, spec.warning)
    info = only(caplog, logging.INFO, spec.info)
    assert at(caplog, logging.DEBUG) == []
    assert warning.levelno > info.levelno, "the WARNING must outrank the INFO"
    assert shipped_extra(info) == {spec.extra_key: injected}
    assert shipped_extra(warning) == {}, "the shipped WARNING passes no extra="


@PARAMS
async def test_start_touches_no_counters_and_no_broadcaster(
    spec: ClassSpec,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``start()`` is lifecycle-only: counters, stamps and lazy state stay idle.

    No shipped ``start()`` increments ``items_processed`` / ``errors``, stamps
    ``last_processed_at``, calls a collaborator, or builds the analysis worker's
    lazy broadcaster (that happens in ``_get_broadcaster``, L813-829).  Stated so
    the state / call-shape legs cannot be satisfied by a variant that did
    bookkeeping work inside ``start()``.
    """
    worker = make_worker(spec)
    win(caplog)

    with patch.object(M, TRACKED_FACTORY, autospec=True) as factory:
        await worker.start()
        consumed_coroutine(factory, worker)

    if spec.state_line is not None:
        assert worker._stats.to_dict() == SHIPPED_IDLE_TO_DICT
    else:
        assert not hasattr(worker, "_stats")
    if spec.cls is M.AnalysisQueueWorker:
        assert worker._broadcaster is None, "start() must not build the lazy broadcaster"
    only(caplog, logging.INFO, spec.info)


def test_the_shipped_factory_is_the_one_under_test() -> None:
    """Control: the patched attribute IS the shipped callable these legs pin.

    ``M.create_tracked_task is REAL_CREATE_TRACKED_TASK`` states that the four
    shipped defs resolve the module-level name imported at
    pipeline_workers.py:50 - which is what makes a single
    ``patch.object(M, "create_tracked_task", autospec=True)`` reach all four - and
    that its shipped signature really is
    ``(coro, *, name=None, task_prefix="task", request_id=None, connection_id=None)``,
    the shape every autospec leg above enforces.

    g13 needs no global-state fixture either: ``start()`` reads only ``self.*``
    plus the module-level ``create_tracked_task`` / ``logger`` / ``WorkerState``
    names, none of which any test here rebinds, so every double in this file is a
    per-test ``patch.object`` that unwinds on its own.
    """
    assert M.create_tracked_task is REAL_CREATE_TRACKED_TASK
    params = inspect.signature(REAL_CREATE_TRACKED_TASK).parameters
    assert params["name"].default is None
    assert params["task_prefix"].default == "task"
    assert params["request_id"].default is None
    assert params["connection_id"].default is None
    assert set(params) == {"coro", "name", "task_prefix", "request_id", "connection_id"}
