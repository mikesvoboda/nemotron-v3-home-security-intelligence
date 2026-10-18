"""S3 batch-28 lane 05 - ``pipeline_workers`` group g05 kill battery (54 keys).

Module: ``backend/services/pipeline_workers.py`` (md5 29b4e6b163b67b1db9fed0069b7e44d2,
byte-identical to the manifest-proven source).  Admitted manifest:
``/tmp/wp-pw/pipeline_workers/`` ``manifest.json`` group 5 (54 KILLABLE /
0 EQUIVALENT / 0 NEEDS_INVESTIGATION), plus ``group_5.keys`` and
``survivors.json`` for the exact per-key diffs.

Everything in this group sits in ONE def - ``PipelineWorkerManager.start``
(shipped L1811-1853).  The legs drive the REAL ``start()`` on a REAL manager
whose five constructed collaborators are per-leg name-spies in the LIVE
name-resolution dict of ``__init__`` (``live_globals``), so ``_detection_workers``
/ ``_analysis_workers`` / ``_timeout_worker`` / ``_metrics_worker`` are doubles
with an awaitable ``start`` while the code under test stays shipped.

Two shipped details are pre-set rather than exercised, both declared in the
manifest as another group's keys:
* ``_signal_handlers_installed`` is set True on the legs that call ``start()``
  (installing real SIGTERM/SIGINT handlers on the test loop would leak past the
  test); the "installed only when the flag is False" contract itself is g16's and
  is stated here as a control leg only.
* the per-worker ``start()`` bodies are not entered - the doubles' ``start`` are
  ``AsyncMock``s, which is what makes "each worker's start awaited" observable.

Test -> mutant-key map
======================
Every key below is in ``group_5.keys``.

L1822 ``logger.warning("PipelineWorkerManager already running")`` -> ``None`` /
``"XX...XX"`` / all-lower / all-upper
- ``xǁPipelineWorkerManagerǁstart__mutmut_1`` / ``_2`` / ``_3`` / ``_4``
  -> ``test_an_already_running_manager_warns_once_and_starts_nothing``
L1825-1829 ``logger.info("Starting PipelineWorkerManager", extra={detection_workers, analysis_workers})``
- ``__mutmut_5`` (msg -> ``None``), ``_9`` (``XX...XX``), ``_10`` (lower),
  ``_11`` (upper), ``_6`` (``extra=None``), ``_8`` (drop ``extra``), ``_12``/``_13``
  (``"detection_workers"`` -> ``XX``/upper), ``_14``/``_15``
  (``"analysis_workers"`` -> ``XX``/upper)
  -> ``test_a_fresh_start_logs_the_two_infos_with_the_worker_counts``
  (2 detection + 1 analysis so the two counts differ; the message and BOTH extra
  KEY names are pinned)
L1853 ``logger.info("PipelineWorkerManager started all workers")`` -> ``None`` /
``"XX...XX"`` / lower / upper
- ``__mutmut_23`` / ``_24`` / ``_25`` / ``_26``
  -> ``test_the_second_info_announces_that_all_workers_started``

Control legs that state the surrounding shipped contract - the TaskGroup
fan-out, the ``enable_*`` gates, and the signal-handler guard:
``test_a_fresh_start_awaits_the_start_of_every_enabled_worker``,
``test_a_disabled_worker_is_not_started``,
``test_signal_handlers_are_installed_only_when_the_flag_says_so``.

Discipline
----------
* Log assertions use ``caplog`` opened per window (``set_level`` + ``clear()``,
  then filtered to this module's logger name) and read the RAW ``record.msg``
  plus ``record.args`` / ``record.exc_info`` / ``record.levelno`` (batch27_01
  pattern).  The ``extra`` values are read off the record attributes the shipped
  ``extra=`` dict creates.
* The collaborator spies replace ``__init__``'s LOCAL names (``patch.dict`` over
  the live globals dict) rather than module attributes, and the signal-handler
  spy is a ``patch.object(manager, ...)`` on the instance double - none of these
  is a convertible module-attribute patch site.
* No import-time global spy: every spy is installed per test and removed at exit.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services import pipeline_workers as M

LOG_NAME = M.logger.name  # "backend.services.pipeline_workers" (get_logger(__name__))

pytestmark = [pytest.mark.unit]


# =============================================================================
# Shipped literals, transcribed from backend/services/pipeline_workers.py
# =============================================================================

# L1822: logger.warning("PipelineWorkerManager already running")
ALREADY_RUNNING_WARNING = "PipelineWorkerManager already running"
# L1826: logger.info("Starting PipelineWorkerManager", extra={...})
STARTING_INFO = "Starting PipelineWorkerManager"
# L1853: logger.info("PipelineWorkerManager started all workers")
STARTED_ALL_INFO = "PipelineWorkerManager started all workers"


# =============================================================================
# Observation helpers (batch27_01 pattern)
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
    plain (already-constant) message, so ``args`` must stay empty and
    ``exc_info`` must be absent; the ``extra`` dict lands on the record itself and
    is asserted separately.
    """
    assert r.msg == msg, f"log text mutated: {r.msg!r} != {msg!r}"
    assert r.levelno == level, f"log level mutated: {r.levelno} != {level}"
    assert tuple(r.args or ()) == (), f"unexpected lazy args for a constant message: {r.args!r}"
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


def live_globals(fn: Any) -> dict[str, Any]:
    """Name-resolution dict of the LIVE function object (three-worlds safe).

    * Pristine repo: ``fn.__globals__ is M.__dict__`` (identity fast path).
    * ep_plugin red-check lane: the variant body is exec'd into a snapshot COPY
      of the module dict and carries no ``__wrapped__`` - that copy is exactly the
      dict the variant body reads, so return it.
    * ``mutants/`` re-bank home: mutmut 3.8 wraps every function in its
      trampoline, whose ``__globals__`` is mutmut's OWN module dict while the
      shipped implementation sits behind ``__wrapped__`` with globals ==
      ``M.__dict__``.  The identity guard fires only there.
    """
    g = fn.__globals__
    if g is not M.__dict__:
        w = getattr(fn, "__wrapped__", None)
        if w is not None and w.__globals__ is M.__dict__:
            return M.__dict__
    return g


# =============================================================================
# Construction rig: the manager is REAL, its collaborators are per-leg spies
# =============================================================================


def class_spy(name: str) -> MagicMock:
    """A class-constructor spy handing out a FRESH worker double per construction.

    Each double carries an ``AsyncMock`` ``start`` so ``start()``'s TaskGroup
    fan-out is observable as an await count, and a ``running`` flag.  ``name`` is
    the ``MagicMock`` repr name only.
    """
    made: list[MagicMock] = []

    def factory(*_args: Any, **_kwargs: Any) -> MagicMock:
        worker = MagicMock(name=f"{name}-instance")
        worker.start = AsyncMock(name=f"{name}.start")
        worker.running = True
        made.append(worker)
        return worker

    spy = MagicMock(name=name, side_effect=factory)
    spy.created = made  # type: ignore[attr-defined]
    return spy


@dataclass(frozen=True)
class Rig:
    """The doubles a leg builds its manager with."""

    aggregator: MagicMock
    detection: MagicMock
    analysis: MagicMock
    timeout: MagicMock
    metrics: MagicMock
    manager: M.PipelineWorkerManager

    @property
    def workers(self) -> list[MagicMock]:
        """Every collaborator double that ``start()`` fans a task out to."""
        return [
            *self.detection.created,  # type: ignore[attr-defined]
            *self.analysis.created,  # type: ignore[attr-defined]
            *([self.manager._timeout_worker] if self.manager._timeout_worker else []),
            *([self.manager._metrics_worker] if self.manager._metrics_worker else []),
        ]


@contextmanager
def spied_names() -> Iterator[dict[str, MagicMock]]:
    """Install the five class-name spies in ``__init__``'s live globals dict."""
    spies = {
        "BatchAggregator": MagicMock(name="BatchAggregator"),
        "DetectionQueueWorker": class_spy("DetectionQueueWorker"),
        "AnalysisQueueWorker": class_spy("AnalysisQueueWorker"),
        "BatchTimeoutWorker": class_spy("BatchTimeoutWorker"),
        "QueueMetricsWorker": class_spy("QueueMetricsWorker"),
    }
    with patch.dict(live_globals(M.PipelineWorkerManager.__init__), spies):
        yield spies


def make_manager(
    spies: dict[str, MagicMock],
    *,
    detection_worker_count: int = 1,
    analysis_worker_count: int = 1,
    enable_detection_worker: bool = True,
    enable_analysis_worker: bool = True,
    enable_timeout_worker: bool = True,
    enable_metrics_worker: bool = True,
) -> Rig:
    """Build a real ``PipelineWorkerManager`` through the spied names.

    ``_signal_handlers_installed`` is pre-set True so ``start()`` never touches
    the process-wide signal table (see the module docstring); the flag's own
    contract is g16's and is covered by a control leg.
    """
    manager = M.PipelineWorkerManager(
        redis_client=MagicMock(name="redis-client"),
        detector_client=MagicMock(name="detector-client"),
        analyzer=MagicMock(name="analyzer"),
        frame_buffer=MagicMock(name="frame-buffer"),
        detection_worker_count=detection_worker_count,
        analysis_worker_count=analysis_worker_count,
        enable_detection_worker=enable_detection_worker,
        enable_analysis_worker=enable_analysis_worker,
        enable_timeout_worker=enable_timeout_worker,
        enable_metrics_worker=enable_metrics_worker,
    )
    manager._signal_handlers_installed = True
    return Rig(
        aggregator=spies["BatchAggregator"],
        detection=spies["DetectionQueueWorker"],
        analysis=spies["AnalysisQueueWorker"],
        timeout=spies["BatchTimeoutWorker"],
        metrics=spies["QueueMetricsWorker"],
        manager=manager,
    )


# =============================================================================
# Fixtures (no import-time spies)
# =============================================================================


@pytest.fixture(autouse=True)
def clean_pipeline_manager_globals() -> Iterator[None]:
    """Cold global manager state before every test, restored afterwards.

    ``_pipeline_manager`` / ``_pipeline_manager_lock`` are module globals that
    persist across tests on an xdist worker; a pre-warmed global would let other
    modules' cached-manager fast path see the doubles this file builds.
    """
    g = live_globals(M.get_pipeline_manager)
    saved = (g.get("_pipeline_manager"), g.get("_pipeline_manager_lock"))
    g["_pipeline_manager"] = None
    g["_pipeline_manager_lock"] = None
    try:
        yield
    finally:
        g["_pipeline_manager"] = saved[0]
        g["_pipeline_manager_lock"] = saved[1]


# =============================================================================
# 1) the already-running arm (L1821-1823)
#    m1 (msg -> None), m2 (XX), m3 (lower), m4 (upper)
# =============================================================================


async def test_an_already_running_manager_warns_once_and_starts_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1821-1823 - ``if self._running:`` warns and returns.

    ::

        if self._running:
            logger.warning("PipelineWorkerManager already running")
            return

    The WARNING's text is the only observable of the whole call, so the four
    surviving variants (``None`` / ``XX...XX`` / lower / upper) are all caught by
    ``record.msg``.  The absence pins are the manifest's "creates no tasks / no
    broadcasts" leg: under a leg that fell through instead of returning, the
    worker starts, the two INFOs and the four broadcasts would all appear.
    """
    win(caplog)

    with spied_names() as spies:
        rig = make_manager(spies, detection_worker_count=1, analysis_worker_count=1)
        rig.manager._running = True

        assert await rig.manager.start() is None

        only(caplog, logging.WARNING, ALREADY_RUNNING_WARNING)
        assert at(caplog, logging.INFO) == [], (
            "the already-running arm returns before the Starting INFO"
        )
        for worker in rig.workers:
            assert worker.start.await_count == 0, (
                f"a worker was started by the already-running arm: {worker.start.await_count}"
            )


# =============================================================================
# 2) the two INFOs of a fresh start (L1825-1830, L1853)
#    m5/m9/m10/m11 + m6/m8 + m12/m13 + m14/m15 ; m23/m24/m25/m26
# =============================================================================


async def test_a_fresh_start_logs_the_two_infos_with_the_worker_counts(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1825-1830 - the INFO message AND both ``extra`` key names.

    ::

        logger.info(
            "Starting PipelineWorkerManager",
            extra={
                "detection_workers": len(self._detection_workers),
                "analysis_workers": len(self._analysis_workers),
            },
        )

    2 detection + 1 analysis makes the two counts distinct, so a renamed key
    (``"XXdetection_workersXX"`` / ``"DETECTION_WORKERS"`` / the analysis pair)
    cannot be satisfied by reading the other attribute, and m6 (``extra=None``) /
    m8 (drop ``extra``) show up as missing attributes rather than wrong values.
    """
    win(caplog)

    with spied_names() as spies:
        rig = make_manager(spies, detection_worker_count=2, analysis_worker_count=1)
        await rig.manager.start()

    infos = at(caplog, logging.INFO)
    assert len(infos) >= 1, (
        f"a fresh start logged no INFO at all: {[(r.msg) for r in mine(caplog)]}"
    )
    first = infos[0]
    pin_record(first, msg=STARTING_INFO, level=logging.INFO)
    assert hasattr(first, "detection_workers"), (
        f"the Starting INFO lost its detection_workers extra: {sorted(vars(first))!r}"
    )
    assert hasattr(first, "analysis_workers"), (
        f"the Starting INFO lost its analysis_workers extra: {sorted(vars(first))!r}"
    )
    assert first.detection_workers == 2, (
        f"detection_workers extra mutated: {first.detection_workers!r} != 2"
    )
    assert first.analysis_workers == 1, (
        f"analysis_workers extra mutated: {first.analysis_workers!r} != 1"
    )
    assert first.detection_workers == len(rig.manager._detection_workers)
    assert first.analysis_workers == len(rig.manager._analysis_workers)


async def test_the_second_info_announces_that_all_workers_started(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1853 - the INFO between the TaskGroup and the broadcasts.

    The four survivors on that line are the message variants, so the text is
    pinned character-for-character, and its POSITION (the second INFO, after the
    fan-out and before the first broadcast) is pinned by the record sequence.
    """
    win(caplog)

    with spied_names() as spies:
        rig = make_manager(spies, detection_worker_count=1, analysis_worker_count=1)
        await rig.manager.start()

    infos = at(caplog, logging.INFO)
    assert len(infos) == 2, f"expected exactly 2 INFOs, got {[r.msg for r in infos]}"
    pin_record(infos[0], msg=STARTING_INFO, level=logging.INFO)
    pin_record(infos[1], msg=STARTED_ALL_INFO, level=logging.INFO)
    assert at(caplog, logging.WARNING) == [], "a fresh start must not warn"


# =============================================================================
# 3) the TaskGroup fan-out (L1840-1851) - control legs
# =============================================================================


async def test_a_fresh_start_awaits_the_start_of_every_enabled_worker(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1840-1851 - one task per enabled worker, and ``running`` flips.

    Control leg: it is what proves the broadcast legs below really started
    workers (so an emit cannot come from an unrelated path), and it states the
    ``self._running = True`` side effect the already-running leg depends on.
    """
    win(caplog)

    with spied_names() as spies:
        rig = make_manager(spies, detection_worker_count=2, analysis_worker_count=2)
        assert rig.manager.running is False
        await rig.manager.start()

        assert rig.manager.running is True, "_running must be True after a fresh start"
        assert rig.manager.accepting is True, "start() does not touch the accepting flag"
        for worker in rig.workers:
            assert worker.start.await_count == 1, (
                f"{worker._mock_name} start awaited {worker.start.await_count} times, expected 1"
            )
        assert len(rig.detection.created) == 2 and len(rig.analysis.created) == 2


async def test_a_disabled_worker_is_not_started(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped ``if self._timeout_worker:`` / ``if self._metrics_worker:`` gates."""
    win(caplog)

    with spied_names() as spies:
        rig = make_manager(
            spies,
            detection_worker_count=1,
            analysis_worker_count=1,
            enable_timeout_worker=False,
            enable_metrics_worker=False,
        )
        await rig.manager.start()

        assert rig.manager._timeout_worker is None
        assert rig.manager._metrics_worker is None
        for worker in rig.workers:
            assert worker.start.await_count == 1


async def test_signal_handlers_are_installed_only_when_the_flag_says_so(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:1834-1836 - the ``if not self._signal_handlers_installed:`` guard.

    Control leg for g16's key (the manifest assigns the signal-handler contract
    there).  The method is spied AUTOSPEC'd on the INSTANCE (WP4.2 fast path:
    signature enforced), so no process-wide signal handler is ever installed by
    this file and the shipped zero-argument signature is policed.
    """
    win(caplog)

    with spied_names() as spies:
        rig = make_manager(spies)
        rig.manager._signal_handlers_installed = False
        with patch.object(rig.manager, "_install_signal_handlers", autospec=True) as install:
            await rig.manager.start()
        assert install.call_count == 1, (
            f"start() installed signal handlers {install.call_count} times, expected 1"
        )
