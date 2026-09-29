"""S3 batch-28 lane 03 - ``pipeline_workers`` group g03 kill battery (73 keys).

Module: ``backend/services/pipeline_workers.py`` (git blob 74649fd3 - byte-identical
to the manifest-proven source and to this lane's copy).  Admitted manifest:
``/tmp/wp-pw/pipeline_workers/`` ``manifest.json`` group 3 (73 KILLABLE /
0 EQUIVALENT / 0 NEEDS_INVESTIGATION), plus ``group_3.keys`` and
``survivors.json`` for the exact per-key diffs.

All 73 keys sit in ``PipelineWorkerManager.stop`` (shipped L1885-1961) across
eleven statement slots.  Every assertion below pins SHIPPED text / SHIPPED
argument values, so a mutant reddens a test by disagreeing with the shipped file
- no test hard-codes a mutant's output.

Test -> mutant-key map
======================
Every key is in ``group_3.keys``.  Occurrence-twin check: each g03 diff
``(function, before, after, line)`` tuple was searched across all 959 survivors -
no pair occurs in another function, so no twin key is carried here and none of
these keys is claimed by another group.  (The structurally identical
``worker.started`` broadcasts in ``start()`` at L1856-1883 carry NO survivors,
and ``QueueMetricsWorker`` has no ``stats`` attribute at all, so the metrics
site's omission of ``items_processed`` is real shipped behaviour, not a default.)

- ``L1894`` ``logger.debug("PipelineWorkerManager not running, nothing to stop")``
  -> ``None`` / ``"XX..XX"`` / all-lower / all-upper  (m2, m3, m4, m5)
  -> ``test_not_running_stop_logs_exactly_the_shipped_debug`` (+ the guard-arm
     re-entry and real-instance legs)
- ``L1897`` ``logger.info("Stopping PipelineWorkerManager")`` -> same four
  (m6, m7, m8, m9)
  -> ``test_running_stop_emits_the_two_ordered_info_records``
- ``L1919-1922`` ``logger.error(f"Error stopping worker during shutdown: {exc}",
  exc_info=exc)`` -> message ``None`` (m16), ``exc_info=None`` (m17), the
  ``exc_info`` argument dropped (m19)
  -> ``test_one_failing_worker_logs_one_error_record_with_the_exc_as_exc_info``,
     ``test_two_failing_workers_log_one_error_record_per_member``
- ``L1924`` ``logger.info("PipelineWorkerManager stopped all workers")`` -> the
  same four (m20, m21, m22, m23)
  -> ``test_running_stop_emits_the_two_ordered_info_records`` and
     ``test_stopped_all_workers_info_is_logged_for_the_no_workers_manager``
- the four ``worker.stopped`` broadcast calls - detection L1928-1935, analysis
  L1937-1944, timeout L1946-1953, metrics L1955-1961 - 58 keys in six slots:
  * ``self._websocket_emitter`` -> ``None``: m25, m44, m62, m82
  * ``"worker.stopped"`` -> ``None`` (m26, m45, m63, m83), ``"XXworker.stoppedXX"``
    (m37, m56, m74, m92), ``"WORKER.STOPPED"`` (m38, m57, m58-slot mirror m75, m93)
  * worker name -> ``None``: m27 (``f"detection_worker_{i}"``), m46, m64, m84;
    name XX-wrap / upper on the two literal sites: m76, m77 (``"timeout_worker"``),
    m94, m95 (``"metrics_worker"``)
  * worker type -> ``None``: m28, m47, m65, m85; XX-wrap / upper: m39, m40
    (``"detection"``), m58, m59, m78, m79, m96, m97
  * ``reason=``: ``None`` (m29, m48, m66, m86), dropped (m35, m54, m72, m91),
    ``"XXgraceful_shutdownXX"`` (m41, m60, m80, m98), ``"GRACEFUL_SHUTDOWN"``
    (m42, m61, m81, m99)
  * ``items_processed=``: ``None`` (m30, m49, m67), dropped (m36, m55, m73)
  -> two end-to-end legs on the emitter double,
     ``test_stopped_broadcasts_emit_four_worker_stopped_events_in_order`` (enum
     member + the ordered ``(worker_name, worker_type)`` list) and
     ``test_stopped_broadcast_payloads_match_the_shipped_contract`` (payload key
     sets, ``reason``, per-site ``items_processed``, metrics-key absence), read
     together with two argument-level legs on an autospec spy of the module-level
     helper - ``test_all_four_stopped_broadcasts_pass_the_shipped_positional_
     arguments`` (emitter identity, event type, name, type for all four calls) and
     ``test_all_four_stopped_broadcasts_pass_the_shipped_keyword_arguments``
     (``reason`` on all four, ``items_processed`` on exactly three).  Every
     emitter-slot key is ALSO killed by the end-to-end legs: with ``None`` in that
     slot the helper takes its own ``if emitter is None`` arm (L103-105) and the
     emitter is never reached, so the emit list comes back empty.

Every leg above is the MEASURED failing set of the in-tree mutant run: each of
the 73 keys was built from its exact survivor diff at its shipped line inside a
``cp -as`` symlink shadow of this tree (cwd outside the main workspace) and this
battery was run against it - 73/73 KILLED, with the pristine file green serially
and co-run with ``test_pipeline_workers_batch28_17.py``.

Two shipped facts the legs lean on are pinned explicitly, because neither is
what a reader would guess:

* ``asyncio.TaskGroup`` wraps even a LONE member error in an ``ExceptionGroup``
  on this 3.14 target, so the ``except ExceptionGroup`` arm at L1915 fires for
  one failing worker as well as two - pinned in
  ``test_one_failing_worker_logs_one_error_record_with_the_exc_as_exc_info``;
  and ``self._running = False`` (L1898) runs BEFORE the group, so the broadcast
  phase is reached whatever the group raises.
* ``record.exc_text`` is snapshotted by ``Logger.makeRecord`` from the ``exc_info``
  argument at creation time, so ``exc_info=None`` (m17) and the dropped argument
  (m19) both leave it ``None`` while shipped keeps a rendered traceback - the
  observable that separates those two keys from a merely-reworded message.

Discipline
----------
* Log assertions use ``caplog`` opened per window (``set_level`` + ``clear()``,
  then filtered to this module's logger name) and read the RAW ``record.msg``
  plus ``record.args`` / ``record.exc_info`` / ``record.exc_text`` /
  ``record.levelno`` (batch27_01 / batch28_17 pattern).  ``time.monotonic`` /
  ``time.perf_counter`` are never patched, and ``timestamp`` is only checked for
  presence + ISO parseability - no duration is asserted.
* Mocks of real attributes are autospec'd (WP4.2 fast path): every worker double
  is ``create_autospec(<shipped worker class>, instance=True)`` (so ``stop()`` is
  a signature-enforcing AsyncMock), the emitter double is
  ``create_autospec(WebSocketEmitterService, instance=True)``, the helper spy is
  ``patch(BROADCAST, autospec=True)``, and the manager double is
  ``create_autospec(PipelineWorkerManager, instance=True)`` whose ``stop`` is
  always invoked as the SHIPPED unbound function (``M.PipelineWorkerManager.stop(dbl)``)
  or through a real instance - never as a mock.
* No import-time global spy.  ``stop()`` reads only instance state plus the
  module-global ``broadcast_worker_event``, so the only global any test touches is
  that one helper, inside a ``patch(...)`` context.
"""

from __future__ import annotations

import asyncio
import builtins
import logging
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, create_autospec, patch

import pytest

from backend.core.websocket.event_types import WebSocketEventType
from backend.services import pipeline_workers as M
from backend.services.pipeline_workers import (
    AnalysisQueueWorker,
    BatchTimeoutWorker,
    DetectionQueueWorker,
    QueueMetricsWorker,
    WebSocketEmitterService,
    WorkerStats,
)

LOG_NAME = M.logger.name  # "backend.services.pipeline_workers" (get_logger(__name__))

pytestmark = [pytest.mark.unit]


# =============================================================================
# Shipped literals, transcribed from backend/services/pipeline_workers.py
# =============================================================================

# L1894: logger.debug("PipelineWorkerManager not running, nothing to stop")
NOT_RUNNING_DEBUG = "PipelineWorkerManager not running, nothing to stop"
# L1897: logger.info("Stopping PipelineWorkerManager")
STOPPING_INFO = "Stopping PipelineWorkerManager"
# L1924: logger.info("PipelineWorkerManager stopped all workers")
STOPPED_ALL_INFO = "PipelineWorkerManager stopped all workers"
# L1920: f"Error stopping worker during shutdown: {exc}"
STOP_ERROR_PREFIX = "Error stopping worker during shutdown: "
# L1930/1939/1948/1957: "worker.stopped", mapped at L112 to this enum member,
# which is the first positional argument handed to emitter.emit() at L131.
EVENT_STOPPED = "worker.stopped"
# L1933/1942/1951/1960: reason="graceful_shutdown"
REASON = "graceful_shutdown"
# L1931/1940/1949/1958 (names) and L1932/1941/1950/1959 (types), in the shipped
# broadcast order: detection list, analysis list, timeout, metrics.
SHIPPED_NAMES = (
    "detection_worker_0",
    "analysis_worker_0",
    "timeout_worker",
    "metrics_worker",
)
SHIPPED_TYPES = ("detection", "analysis", "timeout", "metrics")
SITE_ORDER = ("detection", "analysis", "timeout", "metrics")
# The shipped class behind each slot (pipeline_workers.py:221/764/1186/1366).
WORKER_CLASSES = {
    "detection": DetectionQueueWorker,
    "analysis": AnalysisQueueWorker,
    "timeout": BatchTimeoutWorker,
    "metrics": QueueMetricsWorker,
}
# Payload key sets the helper builds at L125-130 (worker_name, worker_type,
# timestamp) plus the per-site **extra_fields.
BASE_KEYS = {"worker_name", "worker_type", "timestamp"}
# Per-site items_processed values injected by the fixtures.  The shipped code
# reads detection_worker.stats.items_processed (L1934), analysis_worker... (L1943)
# and self._timeout_worker... (L1952); the metrics site passes no such kwarg.
ITEMS = {"detection": 7, "analysis": 3, "timeout": 11, "metrics": 99}
BROADCAST = "backend.services.pipeline_workers.broadcast_worker_event"


# =============================================================================
# Observation helpers (batch27_01 / batch28_17 pattern)
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


def texts(recs: list[logging.LogRecord]) -> list[tuple[int, str]]:
    return [(r.levelno, str(r.msg)) for r in recs]


def pin_plain_record(r: logging.LogRecord, *, msg: str, level: int) -> None:
    """Assert the observable surface of one shipped no-kwargs log call.

    ``record.msg`` is the RAW message.  Every g03 site except L1919 passes a bare
    (already-interpolated) string, so ``args`` must stay empty - a mutated
    message argument lands IN ``msg`` - and both ``exc_info`` and its
    ``makeRecord`` snapshot ``exc_text`` must be absent.
    """
    assert r.msg == msg, f"log text mutated: {r.msg!r} != {msg!r}"
    assert r.levelno == level, f"log level mutated: {r.levelno} != {level}"
    assert tuple(r.args or ()) == (), f"unexpected lazy args for a plain message: {r.args!r}"
    assert r.exc_info is None, (
        f"exc_info present where the shipped call passes none: {r.exc_info!r}"
    )
    assert r.exc_text is None, (
        f"exc_text present where the shipped call passes no exc_info: {r.exc_text!r}"
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
        f"got {texts(recs)}"
    )
    pin_plain_record(recs[0], msg=msg, level=level)
    return recs[0]


# =============================================================================
# Double builders (all autospec'd - WP4.2)
# =============================================================================


def worker_double(cls: type, *, items: int, side_effect: BaseException | None = None) -> Any:
    """autospec'd instance double of a shipped worker class.

    ``create_autospec(cls, instance=True)`` keeps the real signatures: ``stop()``
    becomes an AsyncMock (``side_effect`` makes it fail, as the ERROR-arm tests
    need).  ``stats`` is replaced by a REAL ``WorkerStats`` (the shipped slots
    dataclass at pipeline_workers.py:202) carrying this test's
    ``items_processed``, so the broadcast sites read a genuine attribute of a
    genuine stats object.
    """
    w = create_autospec(cls, instance=True)
    w.stop = AsyncMock(name=f"{cls.__name__}.stop", side_effect=side_effect)
    w.stats = WorkerStats(items_processed=items)
    return w


def emitter_double() -> Any:
    """autospec'd ``WebSocketEmitterService`` instance: ``emit`` is an AsyncMock."""
    return create_autospec(WebSocketEmitterService, instance=True)


def standard_workers() -> dict[str, Any]:
    """The four shipped worker kinds, one each, all stopping cleanly."""
    return {
        "detection": worker_double(DetectionQueueWorker, items=ITEMS["detection"]),
        "analysis": worker_double(AnalysisQueueWorker, items=ITEMS["analysis"]),
        "timeout": worker_double(BatchTimeoutWorker, items=ITEMS["timeout"]),
        "metrics": worker_double(QueueMetricsWorker, items=ITEMS["metrics"]),
    }


def manager_double(
    emitter: Any,
    workers: dict[str, Any] | None = None,
    *,
    running: bool = True,
) -> Any:
    """Instance double whose worker slots hold exactly ``workers``, ``stop`` shipped.

    The manager's ``_detection_workers`` / ``_analysis_workers`` / ``_timeout_worker``
    / ``_metrics_worker`` / ``_websocket_emitter`` / ``_running`` are plain instance
    attributes that ``stop()`` only reads, so they are installed directly; every
    test that uses this double calls the SHIPPED ``PipelineWorkerManager.stop``
    against it, never the double's own attributes.
    """
    m = create_autospec(M.PipelineWorkerManager, instance=True)
    workers = workers if workers is not None else standard_workers()
    m._running = running
    m._detection_workers = [w for k, w in workers.items() if k == "detection"]
    m._analysis_workers = [w for k, w in workers.items() if k == "analysis"]
    m._timeout_worker = workers.get("timeout")
    m._metrics_worker = workers.get("metrics")
    m._websocket_emitter = emitter
    return m


async def stop_shipped(manager: Any) -> Any:
    """Run the SHIPPED ``PipelineWorkerManager.stop`` against ``manager``.

    Called as an unbound function so the double's own ``stop`` attribute can never
    be the thing under test, whatever wrapper this module is loaded behind.
    """
    return await M.PipelineWorkerManager.stop(manager)


def emits(emitter: Any) -> list[tuple[Any, dict[str, Any]]]:
    """The ``(event_type, payload)`` pairs handed to ``emitter.emit``, in order."""
    return [(c.args[0], c.args[1]) for c in emitter.emit.await_args_list]


def emitted_names(emitter: Any) -> list[Any]:
    return [p.get("worker_name") for _t, p in emits(emitter)]


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def emitter() -> Any:
    return emitter_double()


@pytest.fixture
def workers() -> dict[str, Any]:
    return standard_workers()


@pytest.fixture
def manager(emitter: Any, workers: dict[str, Any]) -> Any:
    """Running manager holding all four worker kinds (``stop`` still shipped)."""
    return manager_double(emitter, workers)


# =============================================================================
# A) the not-running guard (L1893-1895) -> m2 (None), m3 (XX), m4 (lower), m5 (upper)
# =============================================================================


async def test_not_running_stop_logs_exactly_the_shipped_debug(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A cold manager ``stop()``s to one DEBUG at L1894 and nothing else.

    Shipped pipeline_workers.py:1893-1895::

        if not self._running:
            logger.debug("PipelineWorkerManager not running, nothing to stop")
            return

    That record is the call's only observable, so all four surviving variants of
    its message (``None`` / ``"XX...XX"`` / all-lower / all-upper) are caught by
    ``record.msg``.  The zero-emit and zero-stop legs matter too: the early
    ``return`` is what keeps the TaskGroup and the whole broadcast phase from
    running, i.e. what makes this def's broadcast-slot mutants observable only on
    the running path.
    """
    workers = standard_workers()
    em = emitter_double()
    manager = manager_double(em, workers, running=False)
    win(caplog)

    assert await stop_shipped(manager) is None

    only(caplog, logging.DEBUG, NOT_RUNNING_DEBUG)
    assert at(caplog, logging.INFO) == [], "the guard arm returns before both INFO sites"
    assert at(caplog, logging.WARNING) == []
    assert at(caplog, logging.ERROR) == []
    assert em.emit.await_count == 0, f"a not-running stop broadcast {em.emit.await_count} events"
    for kind, w in workers.items():
        assert w.stop.await_count == 0, f"{kind} worker was stopped by a cold stop()"
    assert manager._running is False, "the guard arm must not touch the flag"


async def test_second_stop_after_a_real_one_takes_the_guard_arm_again(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The guard is reached through ``self._running``, which stop() cleared at L1898.

    Pins the flag clear and the guard together: the first shutdown must NOT log
    the guard text and the second one must log nothing else - which is also the
    leg that keeps the guard DEBUG and the two INFO bookends from being
    interchangeable.
    """
    workers = standard_workers()
    em = emitter_double()
    manager = manager_double(em, workers)
    win(caplog)

    await stop_shipped(manager)
    assert manager._running is False, "shipped sets self._running = False at L1898"
    first_round = mine(caplog)
    assert (logging.DEBUG, NOT_RUNNING_DEBUG) not in texts(first_round), texts(first_round)

    caplog.clear()
    await stop_shipped(manager)

    only(caplog, logging.DEBUG, NOT_RUNNING_DEBUG)
    assert at(caplog, logging.INFO) == []
    assert em.emit.await_count == 4, f"the second stop re-broadcast: {emitted_names(em)}"
    for kind, w in workers.items():
        assert w.stop.await_count == 1, f"{kind} worker.stop() ran {w.stop.await_count} times"


async def test_guard_debug_is_the_only_record_for_a_never_started_manager(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The shipped lifecycle on a REAL instance built from the shipped class.

    ``__init__`` sets ``self._running = False`` (L1644) and ``get_status()`` is
    side-effect-free, so this exercises the guard without any manager double:
    workers are disabled, no record other than the guard DEBUG may appear.
    """
    manager = M.PipelineWorkerManager(
        redis_client=create_autospec(M.RedisClient, instance=True),
        enable_detection_worker=False,
        enable_analysis_worker=False,
        enable_timeout_worker=False,
        enable_metrics_worker=False,
        websocket_emitter=emitter_double(),
    )
    assert manager.running is False
    assert manager.get_status()["running"] is False
    win(caplog)

    await manager.stop()

    assert texts(mine(caplog)) == [(logging.DEBUG, NOT_RUNNING_DEBUG)], texts(mine(caplog))


# =============================================================================
# B) the two INFO bookends (L1897, L1924) -> m6-m9, m20-m23
# =============================================================================


async def test_running_stop_emits_the_two_ordered_info_records(
    manager: Any,
    workers: dict[str, Any],
    emitter: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped L1897 then L1924, verbatim, with nothing else at INFO.

    ::

        logger.info("Stopping PipelineWorkerManager")               # L1897
        self._running = False                                       # L1898
        try: async with asyncio.TaskGroup() as tg: ...              # L1902-1914
        except ExceptionGroup as eg: ...                            # L1915-1922
        logger.info("PipelineWorkerManager stopped all workers")    # L1924

    Both INFO sites carry four surviving message mutants (``None`` / XX-wrap /
    lower / upper) and every running stop passes through both, so pinning the
    ordered pair kills m6-m9 and m20-m23.  No spy is installed here - the helper
    really runs, which is why ``emit`` also reaches four calls.
    """
    win(caplog)

    assert await stop_shipped(manager) is None

    infos = at(caplog, logging.INFO)
    assert texts(infos) == [
        (logging.INFO, STOPPING_INFO),
        (logging.INFO, STOPPED_ALL_INFO),
    ], texts(infos)
    pin_plain_record(infos[0], msg=STOPPING_INFO, level=logging.INFO)
    pin_plain_record(infos[1], msg=STOPPED_ALL_INFO, level=logging.INFO)
    assert at(caplog, logging.ERROR) == [], texts(at(caplog, logging.ERROR))
    assert manager._running is False
    assert len(emits(emitter)) == 4


async def test_stopped_all_workers_info_is_logged_for_the_no_workers_manager(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """L1924 in a window with zero broadcasts - the cleanest read of that record.

    With all four worker slots empty the TaskGroup gets no tasks and the four
    broadcast loops iterate nothing, so ``mine(caplog)`` is exactly two records
    and the second one is L1924 alone.  This is the leg where the message cannot
    be confused with any other record in the window.
    """
    em = emitter_double()
    manager = manager_double(em, {})
    win(caplog)

    await stop_shipped(manager)

    assert texts(mine(caplog)) == [
        (logging.INFO, STOPPING_INFO),
        (logging.INFO, STOPPED_ALL_INFO),
    ], texts(mine(caplog))
    pin_plain_record(at(caplog, logging.INFO)[1], msg=STOPPED_ALL_INFO, level=logging.INFO)
    assert at(caplog, logging.DEBUG) == [], "the guard arm must not fire on a running manager"
    assert at(caplog, logging.ERROR) == []
    assert em.emit.await_count == 0, "an empty manager has nothing to broadcast"


# =============================================================================
# C) worker.stop() inside one TaskGroup (L1902-1914) - controls; no survivor sits
#    on these lines, but the ERROR-arm and broadcast legs read their effects
# =============================================================================


async def test_every_present_worker_stop_is_awaited_exactly_once(
    manager: Any,
    workers: dict[str, Any],
    emitter: Any,
) -> None:
    """All four kinds are handed to the group (L1905-1914), once each, no args.

    Each shipped worker's own ``stop()`` returns immediately for an
    already-stopped double, so the group completes and the broadcast phase is
    reached.  Await-counts are the only way to see the four ``create_task``
    statements, and the metrics slot is included precisely because its broadcast
    is the one without ``items_processed`` - its stop must still be awaited.
    """
    await stop_shipped(manager)

    for kind in SITE_ORDER:
        w = workers[kind]
        assert w.stop.await_count == 1, (
            f"{kind} worker.stop() awaited {w.stop.await_count} times, expected 1"
        )
        assert w.stop.call_count == w.stop.await_count, (
            f"{kind} worker.stop() was called with arguments: {w.stop.call_args_list}"
        )
    assert manager._running is False
    assert emitted_names(emitter) == list(SHIPPED_NAMES), emitted_names(emitter)


async def test_absent_workers_are_skipped_without_breaking_the_group(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The ``if self._timeout_worker:`` / ``if self._metrics_worker:`` guards.

    Two detection workers, two analysis workers, no singletons: all four are
    stopped, four broadcasts go out, and the per-list index ``i`` shows up in the
    generated names (``f"detection_worker_{i}"`` / ``f"analysis_worker_{i}"``),
    which is the shipped text behind keys m27/m46.
    """
    em = emitter_double()
    det = [
        worker_double(DetectionQueueWorker, items=1),
        worker_double(DetectionQueueWorker, items=2),
    ]
    ana = [
        worker_double(AnalysisQueueWorker, items=3),
        worker_double(AnalysisQueueWorker, items=4),
    ]
    manager = manager_double(em, {})
    manager._detection_workers = det
    manager._analysis_workers = ana
    manager._timeout_worker = None
    manager._metrics_worker = None
    win(caplog)

    await stop_shipped(manager)

    for w in (*det, *ana):
        assert w.stop.await_count == 1
    assert emitted_names(em) == [
        "detection_worker_0",
        "detection_worker_1",
        "analysis_worker_0",
        "analysis_worker_1",
    ], emitted_names(em)
    assert [p.get("worker_type") for _t, p in emits(em)] == [
        "detection",
        "detection",
        "analysis",
        "analysis",
    ]
    assert [p["items_processed"] for _t, p in emits(em)] == [1, 2, 3, 4]
    assert texts(at(caplog, logging.INFO)) == [
        (logging.INFO, STOPPING_INFO),
        (logging.INFO, STOPPED_ALL_INFO),
    ]


def _barrier_stop(barrier: asyncio.Barrier, kind: str, timeouts: list[str]):
    """A ``stop()`` side effect that only returns once all four are in the barrier."""

    async def stop_one() -> None:
        try:
            await asyncio.wait_for(barrier.wait(), timeout=1.0)
        except builtins.TimeoutError:
            timeouts.append(kind)

    return stop_one


async def test_the_four_stops_share_one_task_group_and_run_concurrently() -> None:
    """Concurrency pin for "one ``asyncio.TaskGroup``" (L1903, NEM-5375).

    Each rigged ``stop()`` waits on a shared four-party barrier, so the call only
    completes if all four tasks are alive at the same time.  Had the shipped code
    awaited (or grouped) them one at a time, the barrier would time out - which
    each double records and this test asserts against, so the leg fails loudly
    instead of hanging.
    """
    barrier = asyncio.Barrier(4)
    timeouts: list[str] = []
    workers: dict[str, Any] = {}
    for kind, cls in WORKER_CLASSES.items():
        w = worker_double(cls, items=ITEMS[kind])

        w.stop = AsyncMock(name=f"{kind}.stop", side_effect=_barrier_stop(barrier, kind, timeouts))
        workers[kind] = w
    manager = manager_double(emitter_double(), workers)

    await stop_shipped(manager)

    assert timeouts == [], f"these workers never ran concurrently: {timeouts}"
    for kind in SITE_ORDER:
        assert workers[kind].stop.await_count == 1


# =============================================================================
# D) the ExceptionGroup arm (L1915-1922) -> m16 (msg None), m17/m19 (exc_info)
# =============================================================================


async def test_one_failing_worker_logs_one_error_record_with_the_exc_as_exc_info(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1915-1922, seen through a SINGLE member failure.

    ::

        except ExceptionGroup as eg:
            for exc in eg.exceptions:
                logger.error(
                    f"Error stopping worker during shutdown: {exc}",   # L1920
                    exc_info=exc,                                       # L1921
                )

    Two shipped facts this leg pins that a reader could otherwise assume wrong:
    on this 3.14 target ``TaskGroup`` wraps even a lone error in an
    ``ExceptionGroup``, so this arm - not a bare re-raise - is what the caller
    sees, and the group error is swallowed so ``stop()`` returns ``None``.
    ``record.exc_info`` is the normalised ``(exc, exc, exc)`` tuple whose payload
    IS the group member, and ``record.exc_text`` is the traceback
    ``makeRecord`` snapshotted from it: those two readouts kill ``exc_info=None``
    (m17) and the dropped argument (m19), while ``record.msg`` - which must
    interpolate the exception - kills m16.
    """
    boom = RuntimeError("detection worker wedged")
    det = worker_double(DetectionQueueWorker, items=ITEMS["detection"], side_effect=boom)
    em = emitter_double()
    manager = manager_double(em, {"detection": det})
    win(caplog)

    assert await stop_shipped(manager) is None, "the ExceptionGroup must not escape stop()"

    recs = at(caplog, logging.ERROR)
    assert len(recs) == 1, f"expected 1 ERROR, got {texts(recs)}"
    r = recs[0]
    assert r.msg == f"{STOP_ERROR_PREFIX}{boom}", f"error text mutated: {r.msg!r}"
    assert r.levelno == logging.ERROR
    assert tuple(r.args or ()) == (), f"the shipped call passes no lazy args: {r.args!r}"
    assert isinstance(r.exc_info, tuple) and r.exc_info[1] is boom, (
        f"exc_info does not carry the group member: {r.exc_info!r}"
    )
    assert r.exc_text is not None, (
        "exc_text is None: the shipped call passes exc_info=exc, so makeRecord "
        "must have snapshotted a traceback (m17/m19 erase it)"
    )
    assert "RuntimeError: detection worker wedged" in r.exc_text, r.exc_text
    assert manager._running is False
    assert det.stop.await_count == 1
    # Best-effort shutdown: the failure is logged, not fatal, so the two INFO
    # bookends and this worker's own stopped broadcast still happen.
    assert texts(at(caplog, logging.INFO)) == [
        (logging.INFO, STOPPING_INFO),
        (logging.INFO, STOPPED_ALL_INFO),
    ]
    assert emits(em) and emits(em)[0][0] is WebSocketEventType.WORKER_STOPPED
    assert emits(em)[0][1]["worker_name"] == SHIPPED_NAMES[0]
    assert emits(em)[0][1]["items_processed"] == ITEMS["detection"]


async def test_two_failing_workers_log_one_error_record_per_member(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The ``for exc in eg.exceptions`` loop over a two-member group.

    Both messages and both ``exc_info`` payloads are pinned positionally: a
    message that stopped interpolating ``{exc}`` collapses the pair into two
    identical texts, and an ``exc_info`` that is no longer the member mismatches
    the expected list.  The two workers that stop cleanly prove the group is
    best-effort rather than fail-fast.
    """
    first = RuntimeError("analysis stop failed")
    second = builtins.TimeoutError("metrics stop timed out")
    workers = standard_workers()
    workers["analysis"].stop.side_effect = first
    workers["metrics"].stop.side_effect = second
    em = emitter_double()
    manager = manager_double(em, workers)
    win(caplog)

    await stop_shipped(manager)

    recs = at(caplog, logging.ERROR)
    assert [str(r.msg) for r in recs] == [
        f"{STOP_ERROR_PREFIX}{first}",
        f"{STOP_ERROR_PREFIX}{second}",
    ], [str(r.msg) for r in recs]
    assert [r.exc_info[1] for r in recs] == [first, second], [r.exc_info for r in recs]
    assert all(r.levelno == logging.ERROR for r in recs)
    assert all(r.exc_text is not None for r in recs), (
        "every member error must carry its own exc_info traceback"
    )
    assert all(tuple(r.args or ()) == () for r in recs)
    assert workers["detection"].stop.await_count == 1
    assert workers["timeout"].stop.await_count == 1
    assert texts(at(caplog, logging.INFO)) == [
        (logging.INFO, STOPPING_INFO),
        (logging.INFO, STOPPED_ALL_INFO),
    ]
    assert emitted_names(em) == list(SHIPPED_NAMES), emitted_names(em)


async def test_a_worker_that_stops_cleanly_logs_nothing_at_error_level(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Control: the ERROR arm is silent when the group raised nothing.

    Without this bound the two legs above could be satisfied by an
    always-logging ``logger.error``; here the same manager with four clean
    workers must produce zero ERROR records.
    """
    workers = standard_workers()
    manager = manager_double(emitter_double(), workers)
    win(caplog)

    await stop_shipped(manager)

    assert at(caplog, logging.ERROR) == [], texts(at(caplog, logging.ERROR))
    assert len(at(caplog, logging.INFO)) == 2


# =============================================================================
# E) the four worker.stopped broadcasts, end to end (L1927-1961)
# =============================================================================


async def test_stopped_broadcasts_emit_four_worker_stopped_events_in_order(
    manager: Any,
    emitter: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The manifest's ordered ``(worker_name, worker_type)`` leg, on the emitter.

    The four broadcast calls sit at L1928 (detection), L1937 (analysis), L1946
    (timeout) and L1955 (metrics) and each ends in
    ``await emitter.emit(ws_event_type, payload)`` inside the helper, so the
    ordered triples are the composite observable for every broadcast slot.  The
    event-type slot's twelve keys land here too: an unmapped ``event_type`` makes
    the helper log a WARNING and return before ``emit`` (L119-122), so the emit
    list comes back empty instead of four long.
    """
    win(caplog)

    await stop_shipped(manager)

    pairs = emits(emitter)
    assert [t for t, _p in pairs] == [WebSocketEventType.WORKER_STOPPED] * 4, [t for t, _p in pairs]
    assert [(p["worker_name"], p["worker_type"]) for _t, p in pairs] == list(
        zip(SHIPPED_NAMES, SHIPPED_TYPES, strict=True)
    ), [(p["worker_name"], p["worker_type"]) for _t, p in pairs]
    warnings = at(caplog, logging.WARNING)
    assert warnings == [], [
        f"the shipped event_type maps to WORKER_STOPPED, so no WARNING is allowed: "
        f"{[str(r.msg) for r in warnings]}"
    ]
    assert (
        texts(at(caplog, logging.DEBUG))
        == [(logging.DEBUG, f"Broadcast worker event: {EVENT_STOPPED}")] * 4
    ), texts(at(caplog, logging.DEBUG))


async def test_stopped_broadcast_payloads_match_the_shipped_contract(
    manager: Any,
    emitter: Any,
) -> None:
    """Per-payload keys/values as shipped: L125-130 plus the per-site kwargs.

    The helper builds ``{"worker_name": ..., "worker_type": ...,
    "timestamp": datetime.now(UTC).isoformat(), **extra_fields}``, so the
    detection / analysis / timeout payloads carry ``reason`` AND
    ``items_processed`` while the metrics site passes only ``reason``
    (L1955-1961) - hence the exact key sets below.  The metrics omission is real
    shipped behaviour, not a default: ``QueueMetricsWorker`` has no ``stats``
    attribute at all, so a call site that tried to read one would raise.
    ``timestamp`` is checked only for presence + ISO parseability: no clock is
    patched and no duration is asserted.
    """
    await stop_shipped(manager)

    pairs = emits(emitter)
    assert len(pairs) == 4, f"expected 4 payloads, got {len(pairs)}"
    for (event, payload), name, kind in zip(pairs, SHIPPED_NAMES, SHIPPED_TYPES, strict=True):
        assert event is WebSocketEventType.WORKER_STOPPED
        assert payload["worker_name"] == name, payload
        assert payload["worker_type"] == kind, payload
        assert payload["reason"] == REASON, payload
        stamp = payload["timestamp"]
        assert isinstance(stamp, str) and datetime.fromisoformat(stamp), payload

    by_name = {p["worker_name"]: p for _t, p in pairs}
    for kind in ("detection", "analysis", "timeout"):
        name = dict(zip(SITE_ORDER, SHIPPED_NAMES, strict=True))[kind]
        assert by_name[name]["items_processed"] == ITEMS[kind], (
            f"{name} items_processed mutated: {by_name[name].get('items_processed')!r} "
            f"!= {ITEMS[kind]}"
        )
    assert set(by_name["detection_worker_0"]) == BASE_KEYS | {
        "reason",
        "items_processed",
    }, set(by_name["detection_worker_0"])
    assert set(by_name["analysis_worker_0"]) == BASE_KEYS | {"reason", "items_processed"}
    assert set(by_name["timeout_worker"]) == BASE_KEYS | {"reason", "items_processed"}
    assert set(by_name["metrics_worker"]) == BASE_KEYS | {"reason"}, set(by_name["metrics_worker"])
    assert "items_processed" not in by_name["metrics_worker"], (
        "the shipped metrics broadcast passes no items_processed kwarg, so the key "
        f"must be absent, got {by_name['metrics_worker'].get('items_processed')!r}"
    )


async def test_the_stopped_broadcasts_carry_the_per_site_processed_counts(
    emitter: Any,
) -> None:
    """Distinct per-site counts, so an ``items_processed`` value cannot be swapped.

    With all three shipped counts different numbers, a site that reads another
    worker's stats (or the metrics worker's, which the shipped code never does)
    is visible in the payload list.
    """
    workers = standard_workers()
    manager = manager_double(emitter, workers)

    await stop_shipped(manager)

    assert [p.get("items_processed", "<absent>") for _t, p in emits(emitter)] == [
        7,
        3,
        11,
        "<absent>",
    ], [p for _t, p in emits(emitter)]


# =============================================================================
# F) per-slot argument legs through the helper itself (autospec spy)
# =============================================================================


async def test_all_four_stopped_broadcasts_pass_the_shipped_positional_arguments(
    manager: Any,
    emitter: Any,
) -> None:
    """The four positional args of L1928/1937/1946/1955, exactly as shipped.

    ``stop()`` calls the module-level helper as
    ``broadcast_worker_event(self._websocket_emitter, "worker.stopped", <name>,
    <type>, ...)``.  Spying the helper (autospec'd, so the shipped signature is
    enforced) reads each slot directly:

    * ``self._websocket_emitter`` -> ``None`` (m25/m44/m62/m82) breaks the emitter
      identity in slot 0;
    * the event-type slot (``None`` m26/m45/m63/m83, ``"XXworker.stoppedXX"``
      m37/m56/m74/m92, ``"WORKER.STOPPED"`` m38/m57/m75/m93) breaks slot 1;
    * the name slot ``None`` (m27/m46/m64/m84) breaks slot 2;
    * the type slot ``None`` (m28/m47/m65/m85) breaks slot 3.

    The spy replaces the helper, so nothing reaches the emitter here - the
    emit-side view is the two legs in section E.
    """
    with patch(BROADCAST, autospec=True) as spy:
        await stop_shipped(manager)

    calls = spy.await_args_list
    assert len(calls) == 4, f"stop() made {len(calls)} broadcast calls, expected 4"
    assert [c.args[0] for c in calls] == [emitter] * 4, (
        f"the emitter slot must stay self._websocket_emitter: "
        f"{[c.args[0] is emitter for c in calls]}"
    )
    assert [c.args[1] for c in calls] == [EVENT_STOPPED] * 4, [c.args[1] for c in calls]
    assert [c.args[2] for c in calls] == list(SHIPPED_NAMES), [c.args[2] for c in calls]
    assert [c.args[3] for c in calls] == list(SHIPPED_TYPES), [c.args[3] for c in calls]
    assert emitter.emit.await_count == 0, "the helper itself is the spy here"


async def test_all_four_stopped_broadcasts_pass_the_shipped_keyword_arguments(
    manager: Any,
    emitter: Any,
) -> None:
    """The kwargs of the same four calls, exactly as shipped.

    ``reason="graceful_shutdown"`` is passed by all four sites (its ``None``
    m29/m48/m66/m86, drop m35/m54/m72/m91, XX-wrap m41/m60/m80/m98 and
    ``"GRACEFUL_SHUTDOWN"`` m42/m61/m81/m99 variants all fail the equality or the
    presence pin), while ``items_processed=`` is passed by exactly the first
    three - ``None`` (m30/m49/m67) fails the value pin and a drop (m36/m55/m73)
    fails the presence pin.  The metrics call must carry no ``items_processed``
    at all, which is the shipped asymmetry at L1955-1961.
    """
    with patch(BROADCAST, autospec=True) as spy:
        await stop_shipped(manager)

    calls = spy.await_args_list
    assert len(calls) == 4
    assert [c.kwargs.get("reason") for c in calls] == [REASON] * 4, [c.kwargs for c in calls]
    assert [c.kwargs.get("items_processed", "<absent>") for c in calls] == [
        7,
        3,
        11,
        "<absent>",
    ], [c.kwargs for c in calls]
    assert set(calls[3].kwargs) == {"reason"}, set(calls[3].kwargs)
    for c in calls[:3]:
        assert set(c.kwargs) == {"reason", "items_processed"}, set(c.kwargs)


async def test_the_helper_is_awaited_once_per_site_and_returns_after_the_second_info(
    manager: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Ordering pin: all four calls happen AFTER L1924, never before it.

    The broadcasts are the last phase of ``stop()`` (L1926-1961), so at the
    moment of the first call both INFO records are already logged and at the
    moment of the fourth nothing has been logged since.  ``asyncio.gather`` of the
    helper's own awaits is not involved - each site is awaited in sequence, which
    the call-count-per-site pins below state.
    """
    seen: list[list[tuple[int, str]]] = []
    win(caplog)

    async def record_window(*_args: Any, **_kwargs: Any) -> None:
        seen.append(texts(mine(caplog)))

    with patch(BROADCAST, autospec=True, side_effect=record_window):
        await stop_shipped(manager)

    assert len(seen) == 4, len(seen)
    assert seen[0] == [
        (logging.INFO, STOPPING_INFO),
        (logging.INFO, STOPPED_ALL_INFO),
    ], seen[0]
    for window in seen:
        assert window == [
            (logging.INFO, STOPPING_INFO),
            (logging.INFO, STOPPED_ALL_INFO),
        ], window


# =============================================================================
# G) control: the helper's own failure arm (no survivor sits there)
# =============================================================================


async def test_an_emit_failure_is_swallowed_and_does_not_stop_the_others(
    manager: Any,
    emitter: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:136-138 - ``except Exception`` -> WARNING, best-effort broadcast.

    Stated as a control so the ordered legs in section E cannot be satisfied by a
    call sequence that merely stopped early: with every ``emit`` raising, all four
    sites still reach the emitter, each logging one WARNING, and the DEBUG
    success line at L132 never appears.
    """
    err = builtins.ConnectionError("socket closed")
    emitter.emit.side_effect = err
    win(caplog)

    await stop_shipped(manager)

    assert emitter.emit.await_count == 4, emitter.emit.await_count
    assert emitted_names(emitter) == list(SHIPPED_NAMES), emitted_names(emitter)
    warnings = at(caplog, logging.WARNING)
    assert [str(r.msg) for r in warnings] == [
        f"Failed to broadcast worker event {EVENT_STOPPED}: {err}"
    ] * 4, [str(r.msg) for r in warnings]
    for r in warnings:
        assert r.exc_info is None and r.exc_text is None, "the shipped arm passes no exc_info"
    assert at(caplog, logging.DEBUG) == [], texts(at(caplog, logging.DEBUG))
    assert len(at(caplog, logging.INFO)) == 2
