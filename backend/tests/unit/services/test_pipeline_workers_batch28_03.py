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
Every key is in ``group_3.keys``.

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

Two shipped facts the legs lean on are pinned explicitly, because neither is
what a reader would guess:

* ``asyncio.TaskGroup`` wraps even a LONE member error in an ``ExceptionGroup``
  on this 3.14 target, so the ``except ExceptionGroup`` arm at L1915 fires for
  one failing worker as well as two - pinned in
  ``test_one_failing_worker_logs_one_error_record_with_the_exc_as_exc_info``.
* ``record.exc_text`` is snapshotted by ``Logger.makeRecord`` from the ``exc_info``
  argument at creation time, so ``exc_info=None`` (m17) and the dropped argument
  (m19) both leave it ``None`` while shipped keeps a rendered traceback - the
  observable that separates those two keys from a merely-reworded message.

Discipline
----------
* Log assertions use ``caplog`` opened per window (``set_level`` + ``clear()``,
  then filtered to this module's logger name) and read the RAW ``record.msg``
  plus ``record.args`` / ``record.exc_info`` / ``record.exc_text`` /
  ``record.levelno`` (batch27_01 / batch28_17 pattern).
* Mocks of real attributes are autospec'd (WP4.2 fast path): every worker double
  is ``create_autospec(<shipped worker class>, instance=True)`` (so ``stop()`` is
  a signature-enforcing AsyncMock), and the manager double is
  ``create_autospec(PipelineWorkerManager, instance=True)`` whose ``stop`` is
  always invoked as the SHIPPED unbound function (``M.PipelineWorkerManager.stop(dbl)``)
  or through a real instance - never as a mock.
* No import-time global spy.
"""

from __future__ import annotations

import asyncio
import builtins
import logging
from typing import Any
from unittest.mock import AsyncMock, create_autospec

import pytest

from backend.services import pipeline_workers as M
from backend.services.pipeline_workers import (
    AnalysisQueueWorker,
    BatchTimeoutWorker,
    DetectionQueueWorker,
    QueueMetricsWorker,
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
SITE_ORDER = ("detection", "analysis", "timeout", "metrics")
# The shipped class behind each slot (pipeline_workers.py:221/764/1186/1366).
WORKER_CLASSES = {
    "detection": DetectionQueueWorker,
    "analysis": AnalysisQueueWorker,
    "timeout": BatchTimeoutWorker,
    "metrics": QueueMetricsWorker,
}
ITEMS = {"detection": 7, "analysis": 3, "timeout": 11, "metrics": 99}


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


def standard_workers() -> dict[str, Any]:
    """The four shipped worker kinds, one each, all stopping cleanly."""
    return {
        "detection": worker_double(DetectionQueueWorker, items=ITEMS["detection"]),
        "analysis": worker_double(AnalysisQueueWorker, items=ITEMS["analysis"]),
        "timeout": worker_double(BatchTimeoutWorker, items=ITEMS["timeout"]),
        "metrics": worker_double(QueueMetricsWorker, items=ITEMS["metrics"]),
    }


def manager_double(
    workers: dict[str, Any] | None = None,
    *,
    running: bool = True,
) -> Any:
    """Instance double whose worker slots hold exactly ``workers``, ``stop`` shipped.

    The manager's ``_detection_workers`` / ``_analysis_workers`` / ``_timeout_worker``
    / ``_metrics_worker`` / ``_running`` are plain instance attributes that ``stop()``
    only reads, so they are installed directly; every test that uses this double calls
    the SHIPPED ``PipelineWorkerManager.stop`` against it, never the double's own
    attributes.
    """
    m = create_autospec(M.PipelineWorkerManager, instance=True)
    workers = workers if workers is not None else standard_workers()
    m._running = running
    m._detection_workers = [w for k, w in workers.items() if k == "detection"]
    m._analysis_workers = [w for k, w in workers.items() if k == "analysis"]
    m._timeout_worker = workers.get("timeout")
    m._metrics_worker = workers.get("metrics")
    return m


async def stop_shipped(manager: Any) -> Any:
    """Run the SHIPPED ``PipelineWorkerManager.stop`` against ``manager``.

    Called as an unbound function so the double's own ``stop`` attribute can never
    be the thing under test, whatever wrapper this module is loaded behind.
    """
    return await M.PipelineWorkerManager.stop(manager)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def workers() -> dict[str, Any]:
    return standard_workers()


@pytest.fixture
def manager(workers: dict[str, Any]) -> Any:
    """Running manager holding all four worker kinds (``stop`` still shipped)."""
    return manager_double(workers)


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
    ``record.msg``.
    """
    workers = standard_workers()
    manager = manager_double(workers, running=False)
    win(caplog)

    assert await stop_shipped(manager) is None

    only(caplog, logging.DEBUG, NOT_RUNNING_DEBUG)
    assert at(caplog, logging.INFO) == [], "the guard arm returns before both INFO sites"
    assert at(caplog, logging.WARNING) == []
    assert at(caplog, logging.ERROR) == []
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
    manager = manager_double(workers)
    win(caplog)

    await stop_shipped(manager)
    assert manager._running is False, "shipped sets self._running = False at L1898"
    first_round = mine(caplog)
    assert (logging.DEBUG, NOT_RUNNING_DEBUG) not in texts(first_round), texts(first_round)

    caplog.clear()
    await stop_shipped(manager)

    only(caplog, logging.DEBUG, NOT_RUNNING_DEBUG)
    assert at(caplog, logging.INFO) == []
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
    ordered pair kills m6-m9 and m20-m23.
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


async def test_stopped_all_workers_info_is_logged_for_the_no_workers_manager(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """L1924 in a window with no workers - the cleanest read of that record.

    With all four worker slots empty the TaskGroup gets no tasks, so
    ``mine(caplog)`` is exactly two records and the second one is L1924 alone.
    This is the leg where the message cannot be confused with any other record
    in the window.
    """
    manager = manager_double({})
    win(caplog)

    await stop_shipped(manager)

    assert texts(mine(caplog)) == [
        (logging.INFO, STOPPING_INFO),
        (logging.INFO, STOPPED_ALL_INFO),
    ], texts(mine(caplog))
    pin_plain_record(at(caplog, logging.INFO)[1], msg=STOPPED_ALL_INFO, level=logging.INFO)
    assert at(caplog, logging.DEBUG) == [], "the guard arm must not fire on a running manager"
    assert at(caplog, logging.ERROR) == []


# =============================================================================
# C) worker.stop() inside one TaskGroup (L1902-1914)
# =============================================================================


async def test_every_present_worker_stop_is_awaited_exactly_once(
    manager: Any,
    workers: dict[str, Any],
) -> None:
    """All four kinds are handed to the group (L1905-1914), once each, no args."""
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


async def test_absent_workers_are_skipped_without_breaking_the_group(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The ``if self._timeout_worker:`` / ``if self._metrics_worker:`` guards."""
    det = [
        worker_double(DetectionQueueWorker, items=1),
        worker_double(DetectionQueueWorker, items=2),
    ]
    ana = [
        worker_double(AnalysisQueueWorker, items=3),
        worker_double(AnalysisQueueWorker, items=4),
    ]
    manager = manager_double({})
    manager._detection_workers = det
    manager._analysis_workers = ana
    manager._timeout_worker = None
    manager._metrics_worker = None
    win(caplog)

    await stop_shipped(manager)

    for w in (*det, *ana):
        assert w.stop.await_count == 1
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
    manager = manager_double(workers)

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
    manager = manager_double({"detection": det})
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
    assert texts(at(caplog, logging.INFO)) == [
        (logging.INFO, STOPPING_INFO),
        (logging.INFO, STOPPED_ALL_INFO),
    ]


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
    manager = manager_double(workers)
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


async def test_a_worker_that_stops_cleanly_logs_nothing_at_error_level(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Control: the ERROR arm is silent when the group raised nothing.

    Without this bound the two legs above could be satisfied by an
    always-logging ``logger.error``; here the same manager with four clean
    workers must produce zero ERROR records.
    """
    workers = standard_workers()
    manager = manager_double(workers)
    win(caplog)

    await stop_shipped(manager)

    assert at(caplog, logging.ERROR) == [], texts(at(caplog, logging.ERROR))
    assert len(at(caplog, logging.INFO)) == 2
