"""S3 batch-28 lane 14 - ``pipeline_workers`` groups g14 + g15 + g16 kill battery.

Module: ``backend/services/pipeline_workers.py`` (git blob 74649fd3 - byte-identical
to the manifest-proven source).  Admitted manifest:
``/tmp/wp-pw/pipeline_workers/manifest.json`` groups 14/15/16 with
``group_14.keys`` / ``group_15.keys`` / ``group_16.keys`` and ``survivors.json``
for the exact per-key diffs.

ONE file carries all three groups: 103 KILLABLE keys + 10 manifest-EQUIVALENT keys.
Of the ten equivalents, eight carry NO assertion (block at the bottom); two - g14
metrics ``stop`` ``m12`` and g15 metrics ``m8`` - are nonetheless RED under this
battery's ``worker._task is None`` slot reads, because the shipped ``_task = None``
write is observable through the attribute even though no shipped CONTROL FLOW reads
it.  The manifest's "unobservable" claim for those two keys is therefore contradicted
by construction (see the bottom block).  The optional ``_14b`` split was not taken -
nothing in the three specs forces it and every leg is group-annotated in its own
docstring, so a single admitted surface keeps the co-run / global-leak check in one
place.

Test -> mutant-key map
======================
``<Class>`` below = DetectionQueueWorker / AnalysisQueueWorker /
BatchTimeoutWorker (the three STATS classes).  QueueMetricsWorker is treated
separately because it carries NO stats attribute, NO guard DEBUG and NO timeout
WARNING.

g14 - the four ``stop()`` methods (60 KILLABLE + 1 EQUIVALENT)
--------------------------------------------------------------
* ``xǁ<Class>ǁstop__mutmut_2/3/4/5`` - guard DEBUG at L337 / L860 / L1261
  (``arg->None``, ``XX…XX`` wrap, ``lower()``, ``upper()``)
  -> ``test_stopped_worker_stop_logs_the_not_running_debug`` (3 classes x 4 keys).
* ``xǁ<Class>ǁstop__mutmut_6/7/8/9`` - ``Stopping <Class>`` INFO at L340 / L863 /
  L1264 (the D2 exact-INFO clause)
  -> ``test_running_worker_with_no_task_logs_the_stopping_and_stopped_infos`` plus
  the two waiting-route tests below (its INFO is the first half of every pinned
  INFO pair) and the metrics INFO-pair legs.
* ``xǁ<Class>ǁstop__mutmut_10`` - ``self._stats.state = WorkerState.STOPPING`` ->
  ``= None`` at L341 / L864 / L1265.  **D1 CLAUSE (CORRECTED SPEC)**: the only
  discriminator is a MID-STOP read - ``_stats.to_dict()["state"]`` read from the spy
  that wraps the stop window's single ``asyncio.wait_for`` call WHILE the handed task
  is still hanging.  Shipped yields ``"stopping"``; the variant leaves ``state=None``
  and ``WorkerStats.to_dict`` raises ``AttributeError`` at that instant.  An
  afterwards read is VACUOUS for this key (the L360/L882/L1283 ``STOPPED`` write
  re-sets the field either way), so the afterwards assert below is kept only as the
  pin of that write and is NOT cited as the route.
  -> ``test_stop_timeout_route_cancels_the_hanging_task`` (3 classes) and
  ``test_stop_cancellable_task_completes_within_the_timeout`` (queue pair).
* ``xǁ<Class>ǁstop__mutmut_17/18/19/20`` - timeout WARNING at L349 / L871 / L1272
  -> present-and-exact in ``test_stop_timeout_route_cancels_the_hanging_task``,
  absent in ``test_stop_cancellable_task_completes_within_the_timeout`` and
  absent-for-metrics in ``test_metrics_stop_uses_the_worker_then_cancels``.
* ``xǁ<Class>ǁstop__mutmut_23/24/25/26`` (L361/L883/L1284) + metrics
  ``__mutmut_13/14/15/16`` (L1449) - ``<Class> stopped`` INFO
  -> every INFO-pair pin above.
* metrics ``stop__mutmut_2/3/4/5`` - these four sit on ``Stopping
  QueueMetricsWorker`` at L1432, NOT on a guard site: the metrics guard at
  L1430-1431 is a bare ``return`` with no logger call, which is what
  ``test_metrics_worker_stop_on_a_stopped_worker_logs_nothing`` pins as the control.
  The keys die in ``test_running_metrics_worker_with_no_task_logs_the_two_infos`` and
  ``test_metrics_stop_uses_the_worker_then_cancels``.
* metrics ``stop__mutmut_9`` - ``timeout=self._stop_timeout`` -> ``timeout=None`` at
  L1437 (the surviving timeout=None key; BatchTimeoutWorker has none)
  -> ``test_metrics_stop_uses_the_worker_then_cancels``: the captured ``timeout``
  kwarg must equal the worker's own ``_stop_timeout`` AND the hang must really end up
  CANCELLED - with ``timeout=None`` ``wait_for`` never raises ``TimeoutError``, so the
  cancel arm is never reached.  Both observables fire in milliseconds; nothing in this
  file depends on a mutant hanging to a tier timeout.
* metrics ``stop__mutmut_12`` (L1447 ``_task = None`` -> ``""``) - manifest
  EQUIVALENT ("both values falsy"), but this battery's timeout leg reads the slot
  directly (``assert worker._task is None``), so the string variant IS red there -
  kept: an honest kill of a key the manifest called unobservable.

g15 - the four ``__init__`` methods (32 KILLABLE + 9 EQUIVALENT)
----------------------------------------------------------------
* detection ``m1`` (L242 ``poll_timeout`` 5 -> 6) + ``m2`` (L243 ``stop_timeout``
  10.0 -> 11.0) -> ``test_detection_default_timeouts_and_zeroed_stats`` plus the
  consumer leg ``test_detection_poll_timeout_is_the_blpop_timeout_kwarg``.
* analysis ``m1`` (L782 5 -> 6) + ``m2`` (L783 30.0 -> 31.0) + ``m18`` (L811
  ``self._broadcaster = ""``) -> ``test_analysis_default_timeouts_and_lazy_broadcaster``.
* detection ``m3/m4`` (L245) + analysis ``m3/m4`` (L785) - the ``worker_name`` ctor
  default (XX-wrapped / upper-cased).  **OCCURRENCE TWIN CHECK**: the two functions'
  diffs are the same ``(before, after)`` shape differing only in the cited line, so
  the pair of shipped-name asserts plus the mixed-case overrides kill all four keys;
  the twin keys are CLAIMED here, not left uncovered.
  -> ``test_worker_name_defaults_are_the_stored_name_verbatim``.
* detection ``m16`` (L268) + BatchTimeout ``m4`` (L1217) -
  ``BatchAggregator(redis_client=redis_client)`` -> ``redis_client=None``
  -> ``test_aggregator_fallbacks_receive_the_constructor_client``.
* analysis ``m8`` (L802 ``build_pipeline_analyzer(redis_client=None)`` — VLM 1.5 flip)
  -> ``test_analyzer_fallback_receives_the_constructor_client``.
* detection ``m25/m27`` (L278 ``redis_client=`` -> ``None`` / argument dropped) +
  ``m26/m28`` (the multi-line ``config=RetryConfig(...)`` argument -> ``None`` /
  dropped) -> ``test_retry_handler_construction_arguments``.  m26/m28 CANNOT die on
  ``worker._retry_handler.config`` field equality: ``RetryHandler.__init__`` stores
  ``config or RetryConfig()`` and RE-MATERIALISES a shipped-equal default, so that
  field read is vacuous.  Their route is the RECEIVED construction argument.
* detection ``m31/m32/m33`` (L280 ``arg->None``) + ``m41`` (L283) + ``m42`` (L284) +
  ``m43`` (L285) - the five ``RetryConfig`` field literals
  -> ``test_retry_config_field_literals_and_seeded_delays`` (field tuple + types + the
  functional ``get_delay`` mirror).
* detection ``m44/m45`` (L290/L291 ``settings.video_*`` -> ``None``)
  -> ``test_detection_video_settings_are_read`` (stored attributes) and
  ``test_detection_video_settings_reach_the_extraction_kwargs`` (the one shipped video
  pass's ``extract_frames_for_detection_batch`` keywords).
* detection ``m46`` (L294) + analysis ``m12`` (L805) + BatchTimeout ``m7`` (L1222) +
  metrics ``m4`` (L1399) - ``self._supervisor = supervisor`` -> ``= None``; and
  BatchTimeout ``m8`` (L1223) + metrics ``m5`` (L1400) - ``self._worker_name =
  worker_name`` -> ``= None``
  -> ``test_heartbeat_reports_the_stored_supervisor_and_name`` (4 params).
* BatchTimeout ``m1`` (L1216 ``self._redis = redis_client`` -> ``= None``)
  -> ``test_timeout_worker_keeps_the_client_the_stage_latency_call_needs``:
  construction proves nothing (the L1217 aggregator fallback reads the PARAMETER), so
  the kill is the loop's ``await record_stage_latency(self._redis, "batch", …)`` call
  argument.
* metrics ``m3`` (L1396 ``self._stop_timeout = stop_timeout`` -> ``= None``)
  -> ``test_metrics_stop_uses_the_worker_then_cancels`` (same leg as g14 metrics m9:
  the captured kwarg must equal the shipped 5.0) and
  ``test_singleton_worker_defaults_hold_their_literals``.
* EQUIVALENT, NOT asserted (7 keys): the three dead ``_task`` initial values on the
  STATS classes (analysis m16 / L809, BatchTimeout m11 / L1226, detection m50 / L298 -
  every leg that reads the slot first ASSIGNS it, so the constructor value is never
  observed) and detection m34-m38 (L280: each dropped literal equals the dataclass
  default).  Metrics m8 (L1403) from the same family IS red in
  ``test_metrics_worker_stop_on_a_stopped_worker_logs_nothing``, whose
  ``assert worker._task is None`` reads the constructor value through a guard-return
  stop() - see the bottom block.

g16 - manager signal handlers / drain default / status slot (11 KILLABLE)
-------------------------------------------------------------------------
* ``_install_signal_handlers`` ``m2`` (L1974 ``logger.info(f"Received signal
  {sig.name}, initiating graceful shutdown")`` -> ``logger.info(None)``) + ``m3``
  (L1975 ``asyncio.create_task(self.stop())`` -> ``create_task(None)``, which raises
  ``TypeError`` and therefore loses BOTH observables)
  -> ``test_sigterm_handler_logs_and_schedules_the_manager_stop`` and
  ``test_sigint_handler_names_SIGINT``.
* ``_install_signal_handlers`` ``m10/m11`` (L1981 ``= True`` -> ``None`` / ``False``)
  -> ``test_a_start_stop_start_cycle_does_not_re_register`` drives the shipped
  ``start()`` guard at L1835 through a real start/stop/start cycle: under either
  variant the flag stays falsy and the second start re-enters the installer, so the
  loop receives FOUR registrations instead of two.
  ``test_running_manager_warns_and_skips_re_install`` is the control showing why the
  cycle is the only route back to that guard.
* ``_install_signal_handlers`` ``m12-m15`` (L1982 confirmation DEBUG)
  -> ``test_install_logs_the_confirmation_debug_and_registers_both_signals``.
* ``_install_signal_handlers`` ``m16`` (L1985 ``logger.debug(f"Could not install
  signal handlers: {e}")`` -> ``logger.debug(None)``)
  -> ``test_not_implemented_error_becomes_one_debug``.  A Windows
  ``ProactorEventLoop`` cannot be constructed on this Linux host, so the
  ``NotImplementedError`` comes from the injected loop double; the shipped arm still
  formats the exception into the message and that text is what is pinned.
* ``drain_queues`` ``m1`` (L1698 METHOD default ``30.0`` -> ``31.0``)
  -> ``test_drain_default_logs_the_shipped_thirty_second_message`` (message text AND
  both ``extra`` fields).  The module-level ``drain_queues`` default is g17's key and
  is killed in ``test_pipeline_workers_batch28_17.py``, not here.
* ``get_status`` ``m26`` (L1804 timeout slot -> ``= None``)
  -> ``test_get_status_exposes_the_timeout_worker_stats_dict`` with
  ``test_get_status_omits_a_disabled_timeout_worker`` as the "absent vs None" control.

Discipline
----------
* Log assertions use ``caplog`` opened per window (``set_level`` + ``clear()``, then
  filtered to this module's logger name) and read the RAW ``record.msg`` plus
  ``record.args`` / ``record.exc_info`` / ``record.levelno``; ``extra`` fields are read
  as record attributes.
* Mocks of real attributes are autospec'd (WP4.2 fast path) and passed through
  ``new=`` whenever the leg must read the double's call records AFTER the patch
  window: the injected ``Settings``, the four worker CLASSES in the manager factory,
  ``BatchAggregator`` / ``build_pipeline_analyzer`` / ``RetryHandler`` in the fallback
  legs,
  ``record_stage_latency`` in the batch-loop leg, ``asyncio.wait_for`` /
  ``asyncio.create_task`` / ``asyncio.get_running_loop`` in the spy legs,
  ``time_module.time`` / ``time.time`` in the clocked legs and the ``WorkerSupervisor``
  instance in the heartbeat legs.  The event-loop stand-in (``RecordingLoop``) is an
  INJECTED object, not a patch of a real attribute.
* No import-time global spy and no module-global mutation at all: workers are built
  with ``get_settings`` patched, and the manager is built with patched worker CLASSES,
  so no real worker loop or task is ever started and there is no global state to save
  or restore (hence no ``live_globals()`` table is needed here).
* ``time.monotonic`` / ``time.perf_counter`` are never patched.  ``pipeline_workers``'
  own ``import time as time_module`` alias IS patched inside a ``with`` block in the
  driven-loop legs (that alias is what the shipped heartbeat gate calls; the batch
  loop's function-local ``import time`` re-binds to the same module object, which is
  what the drain leg patches) - function patches in a window, never edits to module
  state.
* Every driven loop is polled by the cooperative helper in 10ms slices against a
  scripted clock and then CANCELLED after its predicate, so no leg can drift toward
  the 5s tier timeout; the mutant-hang keys (g14 metrics m9, g15 metrics m3) are
  killed by a captured kwarg instead of by a hang.
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
import signal
import time as time_module
from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

import pytest

from backend.core.config import Settings
from backend.core.constants import ANALYSIS_QUEUE, DETECTION_QUEUE
from backend.services import pipeline_workers as M
from backend.services.pipeline_workers import (
    AnalysisQueueWorker,
    BatchTimeoutWorker,
    DetectionQueueWorker,
    PipelineWorkerManager,
    QueueMetricsWorker,
    WorkerState,
)
from backend.services.retry_handler import RetryConfig
from backend.services.worker_supervisor import WorkerSupervisor

MOD = "backend.services.pipeline_workers"
LOG_NAME = M.logger.name  # "backend.services.pipeline_workers" (get_logger(__name__))

pytestmark = [pytest.mark.unit]

# The real asyncio primitives, captured at import time so a leg that patches the
# module attribute can still delegate to the shipped implementation.
_REAL_WAIT_FOR = asyncio.wait_for
_REAL_CREATE_TASK = asyncio.create_task


# =============================================================================
# Shipped literals, transcribed from backend/services/pipeline_workers.py
# =============================================================================

# L242 / L243 / L245 - DetectionQueueWorker.__init__ ctor defaults
DETECTION_POLL_TIMEOUT = 5
DETECTION_STOP_TIMEOUT = 10.0
# L782 / L783 / L785 - AnalysisQueueWorker.__init__
ANALYSIS_POLL_TIMEOUT = 5
ANALYSIS_STOP_TIMEOUT = 30.0
# L1218 / L1219 / L1224 - BatchTimeoutWorker.__init__
TIMEOUT_CHECK_INTERVAL = 10.0
TIMEOUT_STOP_TIMEOUT = 10.0
# L1380 / L1381 / L1386 - QueueMetricsWorker.__init__
METRICS_UPDATE_INTERVAL = 5.0
METRICS_STOP_TIMEOUT = 5.0

WORKER_NAMES = {
    "DetectionQueueWorker": "detection",
    "AnalysisQueueWorker": "analysis",
    "BatchTimeoutWorker": "batch_timeout",
    "QueueMetricsWorker": "metrics",
}

# L281-L285 - the RetryConfig(...) literal built for the detection retry handler.
RETRY_FIELDS: tuple[tuple[str, Any], ...] = (
    ("max_retries", 3),
    ("base_delay_seconds", 1.0),
    ("max_delay_seconds", 30.0),
    ("exponential_base", 2.0),
    ("jitter", True),
)

# stop() texts: guard DEBUG (L337/L860/L1261), Stopping INFO (L340/L863/L1264),
# timeout WARNING (L349/L871/L1272), stopped INFO (L361/L883/L1284).
NOT_RUNNING_DEBUG = "{} not running, nothing to stop"
STOPPING_INFO = "Stopping {}"
TIMEOUT_WARNING = "{} task did not stop in time, cancelling"
STOPPED_INFO = "{} stopped"
# L1432 / L1449 - the two shapes QueueMetricsWorker does log; its TimeoutError arm
# (L1438-1446) holds NO logger call at all.
METRICS_STOPPING_INFO = "Stopping QueueMetricsWorker"
METRICS_STOPPED_INFO = "QueueMetricsWorker stopped"

# L1982 / L1974 / L1985 - _install_signal_handlers
SIGNALS_INSTALLED_DEBUG = "Signal handlers installed for SIGTERM and SIGINT"
SIGNAL_RECEIVED_INFO = "Received signal {}, initiating graceful shutdown"
SIGNAL_FAILED_DEBUG = "Could not install signal handlers: {}"
# start()/stop() guard + drain-leg texts (L1822, L1676, L1727, L1754)
ALREADY_RUNNING_WARNING = "PipelineWorkerManager already running"
STOP_ACCEPTING_INFO = "Stopping PipelineWorkerManager from accepting new tasks"
DRAIN_START_INFO = "Starting queue drain with {} pending tasks, timeout={}s"
DRAIN_DONE_INFO = "Queue drain completed in {}s"
DRAIN_DEFAULT_TIMEOUT = 30.0

# Values this file injects through the Settings double and then asserts on.
VIDEO_FRAME_INTERVAL = 1.25
VIDEO_MAX_FRAMES = 7
BATCH_CHECK_INTERVAL = 9.0
THUMBNAIL_DIR = "var/thumbs-b28"

# L381 / L903 / L1299 / L1457 - the loop-local heartbeat period.
HEARTBEAT_INTERVAL = 20.0

# Tiny ceilings so a mutant that hangs a wait_for or a driven loop goes RED in
# milliseconds instead of riding the tier timeout.
STOP_TEST_TIMEOUT = 2.0
DRIVE_TEST_TIMEOUT = 2.0

STATS_CLASSES = ("DetectionQueueWorker", "AnalysisQueueWorker", "BatchTimeoutWorker")


# =============================================================================
# Observation helpers
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


def texts(caplog: pytest.LogCaptureFixture, level: int) -> list[str]:
    return [r.msg for r in at(caplog, level)]


def msgs(caplog: pytest.LogCaptureFixture) -> list[tuple[int, str]]:
    return [(r.levelno, r.msg) for r in mine(caplog)]


def pin_record(record: logging.LogRecord, *, msg: str, level: int) -> None:
    """Assert the observable surface of one shipped single-argument log call.

    Every site in these three groups passes ONE already-built message, so ``args``
    must stay empty (a moved or dropped message argument lands inside ``msg``) and
    ``exc_info`` must stay absent.
    """
    assert record.msg == msg, f"log text mutated: {record.msg!r} != {msg!r}"
    assert record.levelno == level, f"log level mutated: {record.levelno} != {level}"
    assert tuple(record.args or ()) == (), f"unexpected lazy args for this site: {record.args!r}"
    assert record.exc_info is None, (
        f"exc_info present where the shipped call passes none: {record.exc_info!r}"
    )


def only(caplog: pytest.LogCaptureFixture, level: int, msg: str) -> logging.LogRecord:
    """Exactly one record at ``level`` in the window, matching every field."""
    records = at(caplog, level)
    assert len(records) == 1, (
        f"expected exactly 1 {logging.getLevelName(level)} record from {LOG_NAME}, "
        f"got {[(r.levelno, r.msg) for r in records]}"
    )
    pin_record(records[0], msg=msg, level=level)
    return records[0]


def pin_info_pair(caplog: pytest.LogCaptureFixture, first: str, second: str) -> None:
    """The shipped stop() INFO pair, in order, with every field pinned."""
    seen = texts(caplog, logging.INFO)
    assert seen == [first, second], f"INFO sequence mutated: {seen!r} != {[first, second]!r}"
    for record in at(caplog, logging.INFO):
        pin_record(record, msg=record.msg, level=logging.INFO)


# =============================================================================
# Doubles and construction helpers
# =============================================================================


def settings_double() -> Any:
    """autospec'd ``Settings`` instance carrying the values these legs pin.

    Built from the real class, so a renamed attribute at a shipped read site raises
    ``AttributeError`` here instead of passing silently.
    """
    spec = create_autospec(Settings, instance=True)
    spec.use_redis_streams = False
    spec.video_frame_interval_seconds = VIDEO_FRAME_INTERVAL
    spec.video_max_frames = VIDEO_MAX_FRAMES
    spec.video_thumbnails_dir = THUMBNAIL_DIR
    spec.detection_worker_count = 1
    spec.analysis_worker_count = 1
    spec.batch_check_interval_seconds = BATCH_CHECK_INTERVAL
    return spec


class PatchedDouble:
    """``patch(target, new=double)`` that also hands the leg its ``double``.

    ``patch(target, autospec=True)`` builds the double itself and RESTORES the real
    callable on exit without leaving a handle behind, so a leg that has to read call
    records once its window has closed cannot use it.  Every double here is still
    ``create_autospec``'d from the shipped callable (the WP4.2 autospec rule) and is
    installed with ``new=``, which is the other accepted spelling of that rule.
    """

    def __init__(self, target: str, double: Any) -> None:
        self._context = patch(target, new=double)
        self.double = double

    def __enter__(self) -> Any:
        self._context.__enter__()
        return self.double

    def __exit__(self, *exc_info: Any) -> Any:
        return self._context.__exit__(*exc_info)


def patch_module(attribute: str, **autospec_kwargs: Any) -> PatchedDouble:
    """autospec'd ``patch("backend.services.pipeline_workers.<attribute>")``."""
    return PatchedDouble(
        f"{MOD}.{attribute}", create_autospec(getattr(M, attribute), **autospec_kwargs)
    )


def patch_settings() -> PatchedDouble:
    """``get_settings`` -> an autospec'd callable returning the shipped-value double."""
    return PatchedDouble(
        f"{MOD}.get_settings",
        create_autospec(M.get_settings, return_value=settings_double()),
    )


def patch_asyncio(attribute: str, **autospec_kwargs: Any) -> PatchedDouble:
    """autospec'd ``patch("asyncio.<attribute>")`` (``wait_for`` / ``create_task``)."""
    return PatchedDouble(
        f"asyncio.{attribute}", create_autospec(getattr(asyncio, attribute), **autospec_kwargs)
    )


def patch_running_loop(loop: RecordingLoop) -> PatchedDouble:
    """``asyncio.get_running_loop`` -> the given ``RecordingLoop``.

    ``RecordingLoop`` is the INJECTED object, not a mock of anything: the shipped
    ``_install_signal_handlers`` only ever calls ``add_signal_handler`` on it, and a
    real SIGTERM/SIGINT handler must stay out of the pytest process.  The autospec'd
    part is the zero-argument ``get_running_loop`` accessor.
    """
    return PatchedDouble(
        "asyncio.get_running_loop",
        create_autospec(asyncio.get_running_loop, side_effect=lambda: loop),
    )


def patch_time(**autospec_kwargs: Any) -> PatchedDouble:
    """``time.time`` -> a scripted double on the ONE ``time`` module object.

    ``pipeline_workers`` reads it twice over: through its ``import time as
    time_module`` alias (every heartbeat gate) and through the batch loop's /
    ``drain_queues``' function-local ``import time`` - both bind the same module
    object, so patching the attribute once reaches all of them.
    """
    return PatchedDouble("time.time", create_autospec(time_module.time, **autospec_kwargs))


def build(cls_name: str, **kwargs: Any) -> Any:
    """Construct one worker of ``cls_name`` with no real collaborator built.

    The shipped constructors build fallback collaborators from settings
    (``DetectorClient`` opens two ``httpx.AsyncClient`` pools, ``VideoProcessor``
    mkdirs and shells out to ``ffmpeg -version``, ``get_frame_buffer`` touches a
    module-level singleton), so every collaborator the leg does not name is injected
    as a ``MagicMock`` - filtered against the shipped signature, because the four
    workers do not share one parameter list - and ``get_settings`` is patched for the
    whole construction.  That keeps the shipped ``get_settings()`` reads pinned to the
    ``Settings`` double and keeps real network / process / global access out of the
    battery, while every fallback arm keeps its own autospec'd-leg test below, which is
    where those keys actually die.
    """
    cls: type = {
        "DetectionQueueWorker": DetectionQueueWorker,
        "AnalysisQueueWorker": AnalysisQueueWorker,
        "BatchTimeoutWorker": BatchTimeoutWorker,
        "QueueMetricsWorker": QueueMetricsWorker,
    }[cls_name]
    defaults = {
        "redis_client": "redis-client",
        "detector_client": "detector",
        "video_processor": "video-processor",
        "frame_buffer": "frame-buffer",
        "analyzer": "analyzer",
        "batch_aggregator": "aggregator",
    }
    accepted = inspect.signature(cls.__init__).parameters
    for name, label in defaults.items():
        if name in accepted:
            kwargs.setdefault(name, MagicMock(name=label))
    with patch_settings():
        return cls(**kwargs)


def yielder(value: Any = None) -> Callable[..., Any]:
    """AsyncMock side_effect that RETURNS ``value`` after yielding to the loop.

    A bare ``AsyncMock(return_value=None)`` never suspends, so a driven worker loop
    would spin through the polling helper without ever giving it a turn.  The
    ``asyncio.sleep(0)`` makes every queue read a real yield point.
    """

    async def _side_effect(*_args: Any, **_kwargs: Any) -> Any:
        await asyncio.sleep(0)
        return value

    return _side_effect


def running_without_task(cls_name: str, **kwargs: Any) -> Any:
    """A worker in the shipped-reachable ``_running=True, _task=None`` state.

    ``start()`` sets ``_running`` and the state before ``create_tracked_task`` can
    raise, so this is a real shipped state: ``stop()`` logs the Stopping INFO, skips
    the whole ``if self._task:`` block and logs the stopped INFO.
    """
    worker = build(cls_name, **kwargs)
    worker._running = True
    worker._task = None
    return worker


def hang_task() -> asyncio.Task:
    """A task that never finishes on its own - only ``cancel()`` ends it."""
    return _REAL_CREATE_TASK(asyncio.Event().wait())


class Clock:
    """``time_module.time`` double that steps past the heartbeat period once.

    Bumping the value ONLY on call ``bump_at`` makes exactly one heartbeat fire and
    leaves every later gate on the fast path, so no leg has to sleep to cross the
    20-second ``heartbeat_interval``.  The call order per loop is documented at the
    ``drive_loop`` entry that uses it.
    """

    def __init__(self, start: float = 100.0, step: float = 1000.0, bump_at: int = 3) -> None:
        self.t = start
        self.step = step
        self.calls = 0
        self.bump_at = bump_at

    def __call__(self) -> float:
        self.calls += 1
        if self.calls == self.bump_at:
            self.t += self.step
        return self.t


class RecordingLoop:
    """Stand-in for the running loop inside ``_install_signal_handlers``.

    That method uses exactly one loop method (``add_signal_handler``), so an injected
    object with call records states the whole contract - and it keeps a real
    SIGTERM/SIGINT handler out of the pytest process.  ``side_effect`` makes the
    shipped ``except (NotImplementedError, RuntimeError)`` arm reachable on a Linux
    host, where a Windows ``ProactorEventLoop`` cannot be constructed.  This is the
    INJECTED value of ``asyncio.get_running_loop()``, not a mock of a real attribute.
    """

    def __init__(self, *, side_effect: BaseException | None = None) -> None:
        self.added: list[tuple[Any, Any]] = []
        self._side_effect = side_effect

    def add_signal_handler(self, sig: Any, handler: Any, *args: Any, **kwargs: Any) -> None:
        if self._side_effect is not None:
            raise self._side_effect
        self.added.append((sig, handler))

    @property
    def signals(self) -> list[Any]:
        return [s for s, _handler in self.added]

    def handler_for(self, sig: Any) -> Any:
        matches = [h for s, h in self.added if s is sig]
        assert len(matches) == 1, f"expected exactly one handler for {sig!r}: {self.signals!r}"
        return matches[0]


def record_task(sink: list[asyncio.Task]) -> Any:
    """autospec'd ``asyncio.create_task`` double that records the task it creates.

    It delegates to the REAL ``create_task`` so a handler's scheduled coroutine
    actually runs; the ``create_task(None)`` variant instead raises ``TypeError``
    inside the handler, which the sibling leg's ``pytest.raises`` pins.
    """

    def spy(*args: Any, **kwargs: Any) -> asyncio.Task:
        task = _REAL_CREATE_TASK(*args, **kwargs)
        sink.append(task)
        return task

    return create_autospec(asyncio.create_task, side_effect=spy)


def build_manager(**kwargs: Any) -> tuple[PipelineWorkerManager, dict[str, Any]]:
    """A manager built by the shipped ``__init__`` with no real worker attached.

    Two layers of substitution, both autospec'd and passed via ``new=`` so the doubles
    stay readable after the window:

    1. during construction each worker CLASS is an autospec'd constructor double, so
       ``__init__`` runs its shipped branches (the ``enable_*`` flags, the
       ``worker_stop_timeout`` pair of arms, the NEM-5375 count loops) and stores a
       spec'd instance double in the matching attribute - AsyncMock
       ``start``/``stop``, MagicMock ``running``/``stats`` - and
    2. ``BatchAggregator`` (which the constructor builds directly) is patched too, and
       ``websocket_emitter`` stays ``None`` so the shipped ``broadcast_worker_event``
       helper takes its documented no-emitter arm.

    No real worker loop or task is ever started, and the ``start()`` / ``stop()``
    control flow - the ``asyncio.TaskGroup`` bodies included - is the shipped one.
    Returns ``(manager, doubles)`` where ``doubles`` maps the worker attribute name to
    its instance double.
    """
    kwargs.setdefault("enable_detection_worker", False)
    kwargs.setdefault("enable_analysis_worker", False)
    kwargs.setdefault("enable_timeout_worker", True)
    kwargs.setdefault("enable_metrics_worker", False)
    patches = {
        "_detection_worker": patch_module("DetectionQueueWorker"),
        "_analysis_workers": patch_module("AnalysisQueueWorker"),
        "_timeout_worker": patch_module("BatchTimeoutWorker"),
        "_metrics_worker": patch_module("QueueMetricsWorker"),
    }
    settings_patch = patch_settings()
    aggregator_patch = patch_module("BatchAggregator")
    with contextlib.ExitStack() as stack:
        doubles: dict[str, Any] = {}
        for attribute, patcher in patches.items():
            factory = stack.enter_context(patcher)
            doubles[attribute] = factory.return_value
        stack.enter_context(settings_patch)
        stack.enter_context(aggregator_patch)
        manager = PipelineWorkerManager(redis_client=MagicMock(name="manager-redis"), **kwargs)
    return manager, doubles


async def drive_loop(
    worker: Any,
    condition: Callable[[], bool],
    *,
    clock: Any = None,
    extra: dict[str, Any] | None = None,
    timeout: float = DRIVE_TEST_TIMEOUT,
) -> bool:
    """Run ``worker._run_loop()`` until the SYNC ``condition()`` is true.

    The module-level collaborators the shipped loops call are patched for the window
    and ``time_module.time`` is a scripted ``Clock``, so one iteration costs one 10ms
    slice of real time.  ``extra`` maps a module attribute name to a caller-owned
    autospec'd double (installed with ``new=``) that the leg still needs to read AFTER
    the drive.  The loop is always CANCELLED rather than asked to exit: the shipped
    loops only re-read ``_running`` at the top of the next iteration and swallow the
    ``CancelledError`` (dropping their exit log), so a leg must never depend on the
    exit path - every assertion below is about work the loop already did.  Returns
    whether the condition was reached.
    """
    loop = asyncio.get_running_loop()
    # bump_at=3 makes the value jump on the THIRD call to the alias, and the shipped
    # loops touch it in a fixed order: the queue loops' calls 1 and 2 are the
    # ``last_heartbeat`` / ``last_claim_check`` inits, so their first gate read IS the
    # jump and exactly one heartbeat fires on iteration 1 (the streams claim gate is
    # never reached because ``use_redis_streams`` is False); the batch and metrics
    # loops have only the init plus one gate read per iteration, so the jump lands on
    # iteration 2.  Either way: exactly one heartbeat, no sleeping.
    clock = clock if clock is not None else Clock()
    extra = extra or {}
    with contextlib.ExitStack() as stack:
        for name, double in extra.items():
            stack.enter_context(patch.object(M, name, new=double))
        for name in (
            "record_pipeline_error",
            "observe_stage_duration",
            "record_pipeline_stage_latency",
            "set_queue_depth",
            "record_stage_latency",
        ):
            if name not in extra:
                stack.enter_context(patch_module(name))
        stack.enter_context(patch_time(side_effect=clock))
        stack.enter_context(patch_settings())
        worker._running = True
        task = _REAL_CREATE_TASK(worker._run_loop(), name=f"drive-{type(worker).__name__}")
        hit = False
        deadline = loop.time() + timeout
        try:
            while loop.time() < deadline:
                await asyncio.sleep(0.01)
                if condition():
                    hit = True
                    break
        finally:
            worker._running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        return hit


# =============================================================================
# g14 - 1) the not-running guard DEBUG (12 keys: m2-m5 x three stats classes)
# =============================================================================


@pytest.mark.parametrize("cls_name", STATS_CLASSES)
async def test_stopped_worker_stop_logs_the_not_running_debug(
    cls_name: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """g14 ``<Class> stop m2/m3/m4/m5`` (L337 / L860 / L1261) - guard DEBUG text.

    Shipped (DetectionQueueWorker, backend/services/pipeline_workers.py:335-338)::

        async def stop(self) -> None:
            if not self._running:
                logger.debug("DetectionQueueWorker not running, nothing to stop")
                return

    A fresh worker is ``_running=False``, so ``stop()`` emits EXACTLY that DEBUG and
    nothing else.  All four surviving variants at each site (``None`` / XX-wrapped /
    all-lower / all-upper) change ``record.msg``; the empty INFO and WARNING sets pin
    the early ``return``, so a kill can never be an accidental fall-through into the
    shutdown block.
    """
    worker = build(cls_name)
    win(caplog)

    assert await worker.stop() is None

    only(caplog, logging.DEBUG, NOT_RUNNING_DEBUG.format(cls_name))
    assert texts(caplog, logging.INFO) == [], "the guard arm must never reach the Stopping INFO"
    assert texts(caplog, logging.WARNING) == [], "the guard arm must never reach the WARNING"
    assert worker.running is False
    assert worker.stats.state is WorkerState.STOPPED, (
        "a guard return must not move the state machine"
    )


# =============================================================================
# g14 - 2) D2 clause: the exact "Stopping <Class>" INFO (12 keys: m6-m9 x 3)
# =============================================================================


@pytest.mark.parametrize("cls_name", STATS_CLASSES)
async def test_running_worker_with_no_task_logs_the_stopping_and_stopped_infos(
    cls_name: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """g14 ``<Class> stop m6/m7/m8/m9`` (L340 / L863 / L1264) - the Stopping INFO.

    ``_running=True`` with ``_task=None`` skips the entire ``wait_for`` block, so the
    shipped INFO stream is EXACTLY ``["Stopping <Class>", "<Class> stopped"]`` in that
    order and no WARNING can appear.  The four message variants at each site are
    caught by the raw ``record.msg`` pins.
    """
    worker = running_without_task(cls_name)
    win(caplog)

    assert await worker.stop() is None

    pin_info_pair(caplog, STOPPING_INFO.format(cls_name), STOPPED_INFO.format(cls_name))
    assert texts(caplog, logging.WARNING) == [], (
        "with no task there is no wait_for, so the timeout WARNING cannot fire"
    )
    assert texts(caplog, logging.DEBUG) == [], "a running worker never reaches the guard DEBUG"
    assert worker.running is False
    assert worker._task is None
    assert worker.stats.state is WorkerState.STOPPED


# =============================================================================
# g14 - 3) D1 clause: the MID-STOP state read (3 keys: m10 x 3 classes)
# =============================================================================


async def stop_with_spy(
    worker: Any,
    *,
    mid_states: list[Any],
    timeouts: list[Any],
) -> None:
    """Run ``worker.stop()`` with ``asyncio.wait_for`` spied from OUTSIDE the worker.

    The spy records per call the ``timeout`` kwarg and a MID-STOP read of
    ``worker._stats.to_dict()["state"]`` taken while the task it was handed is still
    hanging - the m10 discriminator the CORRECTED spec mandates (shipped wrote
    ``WorkerState.STOPPING`` so the read yields ``"stopping"``; the ``state = None``
    variant raises ``AttributeError: 'NoneType' object has no attribute 'value'``
    inside ``WorkerStats.to_dict`` at that same instant).  The double is autospec'd
    (signature-exact) and the spy delegates to the REAL ``wait_for``, so the shipped
    timeout / cancel / await semantics stay in play.  The stats SLOT is read rather
    than the ``stats`` property because QueueMetricsWorker - which is driven through
    the very same helper - has no stats at all.  The spy is ``async def`` because an
    autospec'd async callable awaits an async ``side_effect``; a sync one that merely
    RETURNS a coroutine is handed straight back to the caller and the window never runs
    (verified against this stdlib: the sync form yields the coroutine object).
    """

    async def spy(*args: Any, **kwargs: Any) -> Any:
        timeouts.append(kwargs.get("timeout"))
        stats = getattr(worker, "_stats", None)
        if stats is not None:
            mid_states.append(stats.to_dict()["state"])
        # The REAL wait_for, so the shipped timeout / cancel / await semantics stay in
        # play and the double only adds the two observations around it.
        return await _REAL_WAIT_FOR(*args, **kwargs)

    with patch_asyncio("wait_for", side_effect=spy) as double:
        await worker.stop()
    assert double.await_count == 1, (
        f"the stop window made {double.await_count} wait_for calls, expected exactly 1"
    )


@pytest.mark.parametrize("cls_name", STATS_CLASSES)
async def test_stop_timeout_route_cancels_the_hanging_task(
    cls_name: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """g14 ``<Class> stop m10`` (MID-STOP read) + ``m17-m20`` + ``m23-m26``.

    Shipped (DetectionQueueWorker, backend/services/pipeline_workers.py:340-361)::

        logger.info("Stopping DetectionQueueWorker")
        self._stats.state = WorkerState.STOPPING
        self._running = False

        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=self._stop_timeout)
            except TimeoutError:
                logger.warning("DetectionQueueWorker task did not stop in time, cancelling")
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            self._task = None

        self._stats.state = WorkerState.STOPPED
        logger.info("DetectionQueueWorker stopped")

    The worker's ``_stop_timeout`` is made tiny and the handed task can only end
    through ``cancel()``, so ``wait_for`` really raises ``TimeoutError``: the WARNING
    text is pinned character-for-character, ``task.cancelled()`` proves ``cancel()``
    ran, and the INFO pair is pinned.  The afterwards state read pins the
    L360/L882/L1283 ``STOPPED`` write only (see the D1 clause in the header).
    """
    worker = running_without_task(cls_name)
    worker._stop_timeout = 0.01
    task = hang_task()
    worker._task = task
    mid_states: list[Any] = []
    timeouts: list[Any] = []
    win(caplog)

    try:
        await _REAL_WAIT_FOR(stop_with_spy(worker, mid_states=mid_states, timeouts=timeouts), 1.5)
    finally:
        if not task.done():
            task.cancel()

    assert timeouts == [0.01], f"{cls_name}: wait_for timeout kwarg mutated: {timeouts!r}"
    assert mid_states == ["stopping"], (
        f"{cls_name}: state DURING the stop window mutated: {mid_states!r} - the m10 "
        "variant leaves state=None so to_dict raises AttributeError"
    )
    assert task.cancelled(), f"{cls_name}: the hung task must have been cancelled"
    assert worker._task is None, f"{cls_name}: the task slot must clear after the wait block"
    assert worker.running is False
    assert worker.stats.to_dict()["state"] == "stopped", (
        f"{cls_name}: post-stop state mutated: {worker.stats.to_dict()['state']!r}"
    )
    assert worker.stats.state is WorkerState.STOPPED
    pin_info_pair(caplog, STOPPING_INFO.format(cls_name), STOPPED_INFO.format(cls_name))
    only(caplog, logging.WARNING, TIMEOUT_WARNING.format(cls_name))


@pytest.mark.parametrize("cls_name", STATS_CLASSES)
async def test_stop_cancellable_task_completes_within_the_timeout(
    cls_name: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The non-timeout route: a task that ends inside the window is NOT cancelled.

    A second m10 route for all three stats classes (same mid-read spy) and the
    WARNING-ABSENCE pin, so the timeout WARNING cannot be satisfied by a
    fall-through that never had a task to wait on.
    """
    worker = running_without_task(cls_name)
    expected_timeout = worker._stop_timeout
    task = _REAL_CREATE_TASK(asyncio.sleep(0))
    worker._task = task
    mid_states: list[Any] = []
    timeouts: list[Any] = []
    win(caplog)

    await _REAL_WAIT_FOR(stop_with_spy(worker, mid_states=mid_states, timeouts=timeouts), 1.5)

    assert timeouts == [expected_timeout], (
        f"{cls_name}: wait_for timeout kwarg mutated: {timeouts!r}"
    )
    assert mid_states == ["stopping"], f"{cls_name}: mid-stop state mutated: {mid_states!r}"
    assert task.done() and not task.cancelled(), (
        f"{cls_name}: a task that finished in time must not be cancelled"
    )
    assert worker._task is None
    assert worker.stats.to_dict()["state"] == "stopped"
    assert texts(caplog, logging.WARNING) == [], (
        f"{cls_name}: the timeout WARNING fired on the success route"
    )
    pin_info_pair(caplog, STOPPING_INFO.format(cls_name), STOPPED_INFO.format(cls_name))


# =============================================================================
# g14 - 4) QueueMetricsWorker.stop (metrics m2-m5, m9, m13-m16 = 9 keys)
# =============================================================================


async def test_metrics_worker_stop_on_a_stopped_worker_logs_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A stopped metrics worker's ``stop()`` is SILENT (L1430-1431 has no logger).

    The control that separates metrics from the three stats classes and the reason
    metrics' m2-m5 keys sit on the ``Stopping QueueMetricsWorker`` INFO (L1432) rather
    than on a guard DEBUG that does not exist.
    """
    worker = build("QueueMetricsWorker")
    win(caplog)

    assert await worker.stop() is None

    assert msgs(caplog) == [], f"a stopped metrics worker logged {msgs(caplog)!r}"
    assert worker.running is False
    assert worker._task is None


async def test_running_metrics_worker_with_no_task_logs_the_two_infos(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """g14 metrics ``stop m2-m5`` (L1432) + ``m13-m16`` (L1449).

    Shipped (backend/services/pipeline_workers.py:1430-1449)::

        async def stop(self) -> None:
            if not self._running:
                return

            logger.info("Stopping QueueMetricsWorker")
            self._running = False

            if self._task:
                ...  # no logger call anywhere in this block
            logger.info("QueueMetricsWorker stopped")

    With ``_task=None`` the wait block is skipped, so that INFO pair is the entire
    observable - and it is the only killable text on the metrics stop path.
    """
    worker = build("QueueMetricsWorker")
    worker._running = True
    worker._task = None
    win(caplog)

    assert await worker.stop() is None

    pin_info_pair(caplog, METRICS_STOPPING_INFO, METRICS_STOPPED_INFO)
    assert texts(caplog, logging.DEBUG) == [], "metrics has no not-running DEBUG site"
    assert texts(caplog, logging.WARNING) == []
    assert worker.running is False


async def test_metrics_stop_uses_the_worker_then_cancels(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """g14 metrics ``stop m9`` (L1437 ``timeout=None``) + g15 metrics ``m3`` (L1396
    ``self._stop_timeout = None``).

    ``timeout=None`` is killable because ``wait_for`` then NEVER raises
    ``TimeoutError``: a hanging task would be neither cancelled nor awaited away and
    ``stop()`` would never return.  Instead of depending on a hang, this pins the
    value and the outcome - the captured ``timeout`` kwarg must equal the worker's own
    ``_stop_timeout`` (which must be the shipped ``5.0``, that is metrics m3's route)
    AND the hang must really end up CANCELLED, which only the ``TimeoutError`` arm
    does.  Both go RED in ~50ms.  Metrics' arm carries no logger call, so the window
    stays INFO-only.
    """
    worker = build("QueueMetricsWorker")
    assert worker._stop_timeout == METRICS_STOP_TIMEOUT, (
        f"metrics stop_timeout mutated: {worker._stop_timeout!r} != {METRICS_STOP_TIMEOUT!r}"
    )
    assert worker._update_interval == METRICS_UPDATE_INTERVAL
    # Test-local ceiling: the wait_for window is entered with the value the shipped
    # stop() reads, so a timeout=None mutant still never raises TimeoutError, but the
    # leg stays milliseconds-slow instead of burning the real 5.0s.  m3's kill is the
    # construction assert above (its variant leaves the attribute None at 5.0-default
    # construction), and m9's kill is the kwarg equality below.
    worker._stop_timeout = 0.01
    task = hang_task()
    worker._running = True
    worker._task = task
    mid_states: list[Any] = []
    timeouts: list[Any] = []
    win(caplog)

    returned = True
    try:
        await _REAL_WAIT_FOR(stop_with_spy(worker, mid_states=mid_states, timeouts=timeouts), 1.5)
    except TimeoutError:
        returned = False
    finally:
        if not task.done():
            task.cancel()

    assert timeouts == [0.01], (
        f"metrics wait_for timeout kwarg mutated: {timeouts!r} - with None the hang is "
        "never cancelled and stop() never returns"
    )
    assert returned, "stop() did not return: the timeout=None arm never fires"
    assert task.cancelled(), "the hang must have been cancelled by the timeout arm"
    assert worker._task is None, "the task slot must still be cleared after the arm"
    assert mid_states == [], "QueueMetricsWorker carries no stats, so no mid-read is possible"
    assert not hasattr(worker, "stats"), "QueueMetricsWorker must not grow a stats property"
    assert texts(caplog, logging.WARNING) == [], (
        "metrics' TimeoutError arm has no logger call - a WARNING there bends behaviour"
    )
    pin_info_pair(caplog, METRICS_STOPPING_INFO, METRICS_STOPPED_INFO)


# =============================================================================
# g15 - 1) ctor defaults and resolved attributes
# =============================================================================


def test_detection_default_timeouts_and_zeroed_stats() -> None:
    """g15 detection ``m1`` (L242 ``poll_timeout`` 5 -> 6) + ``m2`` (L243
    ``stop_timeout`` 10.0 -> 11.0).

    Those defaults ARE the BLPOP timeout and the force-cancel grace period, so both
    ``number+1`` mutants die on the stored value; the BLPOP-kwarg leg below is the
    second route for m1.
    """
    worker = build("DetectionQueueWorker")

    assert worker._poll_timeout == DETECTION_POLL_TIMEOUT, (
        f"detection poll_timeout default mutated: {worker._poll_timeout!r}"
    )
    assert worker._stop_timeout == DETECTION_STOP_TIMEOUT, (
        f"detection stop_timeout default mutated: {worker._stop_timeout!r}"
    )
    assert worker._queue_name == DETECTION_QUEUE
    assert worker.running is False
    assert worker.stats.state is WorkerState.STOPPED
    assert worker.stats.items_processed == 0 and worker.stats.errors == 0
    assert worker.stats.to_dict()["state"] == "stopped", "to_dict reports the enum's .value"


def test_analysis_default_timeouts_and_lazy_broadcaster() -> None:
    """g15 analysis ``m1`` (L782 5 -> 6) + ``m2`` (L783 30.0 -> 31.0) + ``m18``
    (L811 ``self._broadcaster = ""``).

    The analysis pair is 5 / 30.0 - deliberately different from detection's
    5 / 10.0, so each class pins its own numbers.  ``_broadcaster`` is the lazy-slot
    sentinel that the accessor tests with ``is None``, so the string variant dies on
    identity, not truthiness.
    """
    worker = build("AnalysisQueueWorker")

    assert worker._poll_timeout == ANALYSIS_POLL_TIMEOUT, (
        f"analysis poll_timeout default mutated: {worker._poll_timeout!r}"
    )
    assert worker._stop_timeout == ANALYSIS_STOP_TIMEOUT, (
        f"analysis stop_timeout default mutated: {worker._stop_timeout!r}"
    )
    assert worker._queue_name == ANALYSIS_QUEUE
    assert worker._broadcaster is None, (
        f"the lazy broadcaster slot must start as None, got {worker._broadcaster!r}"
    )


def test_singleton_worker_defaults_hold_their_literals() -> None:
    """The BatchTimeout / QueueMetrics default block, stated whole.

    ``check_interval`` / ``update_interval`` carry no survivor, but their class-mates
    do (BatchTimeout m1/m7/m8, metrics m3/m4/m5) and this construction leg is what
    makes a passing neighbour provable rather than accidental.
    """
    batch = build("BatchTimeoutWorker")
    metrics = build("QueueMetricsWorker")

    assert batch._check_interval == TIMEOUT_CHECK_INTERVAL
    assert batch._stop_timeout == TIMEOUT_STOP_TIMEOUT
    assert batch._worker_name == WORKER_NAMES["BatchTimeoutWorker"]
    assert metrics._update_interval == METRICS_UPDATE_INTERVAL
    assert metrics._stop_timeout == METRICS_STOP_TIMEOUT, (
        f"metrics stop_timeout mutated: {metrics._stop_timeout!r}"
    )
    assert metrics._worker_name == WORKER_NAMES["QueueMetricsWorker"]
    assert not hasattr(metrics, "stats"), "QueueMetricsWorker has no stats attribute"


def test_worker_name_defaults_are_the_stored_name_verbatim() -> None:
    """g15 detection ``m3/m4`` (L245) + analysis ``m3/m4`` (L785) - the
    ``worker_name`` ctor default, XX-wrapped and upper-cased.

    **TWIN CHECK**: each function's two keys share one mutant body (same
    ``(before, after)`` pair, differing only in the cited line), so the two shipped
    defaults below kill all four keys, and the mixed-case overrides prove no
    ``.lower()`` / ``.upper()`` is applied on the way in - which is what makes the
    ``"DETECTION"`` / ``"ANALYSIS"`` variants distinguishable from a shipped name that
    happened to be compared case-insensitively.
    """
    assert build("DetectionQueueWorker")._worker_name == "detection"
    assert build("AnalysisQueueWorker")._worker_name == "analysis"
    assert build("DetectionQueueWorker", worker_name="MiXeD-D")._worker_name == "MiXeD-D"
    assert build("AnalysisQueueWorker", worker_name="MiXeD-A")._worker_name == "MiXeD-A"
    assert build("BatchTimeoutWorker", worker_name="T-7")._worker_name == "T-7"
    assert build("QueueMetricsWorker", worker_name="Q-7")._worker_name == "Q-7"


# =============================================================================
# g15 - 2) collaborator fallbacks and the RetryConfig block
# =============================================================================


def test_aggregator_fallbacks_receive_the_constructor_client() -> None:
    """g15 detection ``m16`` (L268) + BatchTimeout ``m4`` (L1217) -
    ``BatchAggregator(redis_client=redis_client)`` -> ``redis_client=None``.

    Both sites build the fallback from the constructor PARAMETER, so the captured
    keyword must be the very client handed to the worker.  The double is autospec'd
    and read via ``new=`` so the call records outlive the window.
    """
    redis = MagicMock(name="redis-client")
    with patch_module("BatchAggregator") as aggregator, patch_settings():
        DetectionQueueWorker(
            redis_client=redis,
            detector_client=MagicMock(),
            video_processor=MagicMock(),
            frame_buffer=MagicMock(),
        )
        call = aggregator.call_args
        assert call.kwargs == {"redis_client": redis}, (
            f"detection aggregator fallback kwargs mutated: {call.kwargs!r}"
        )
        assert call.kwargs["redis_client"] is redis

        aggregator.reset_mock()
        BatchTimeoutWorker(redis_client=redis)
        call = aggregator.call_args
        assert call.kwargs == {"redis_client": redis}, (
            f"timeout aggregator fallback kwargs mutated: {call.kwargs!r}"
        )
        assert call.kwargs["redis_client"] is redis


def test_analyzer_fallback_receives_the_constructor_client() -> None:
    """g15 analysis ``m8`` — the default analyzer is built with the ctor client.

    Shipped (pipeline_workers.py:800, VLM Phase 1 1.5 flip):
    ``self._analyzer = analyzer or build_pipeline_analyzer(redis_client=redis_client)``
    — mode-built, never spelled here, so a mutated ``redis_client=None`` arg
    still reddens this pin.
    """
    redis = MagicMock(name="redis-client")
    with patch_module("build_pipeline_analyzer") as builder, patch_settings():
        worker = AnalysisQueueWorker(redis_client=redis)

    call = builder.call_args
    assert call.kwargs == {"redis_client": redis}, (
        f"analyzer fallback kwargs mutated: {call.kwargs!r}"
    )
    assert call.kwargs["redis_client"] is redis
    assert worker._analyzer is builder.return_value


def test_retry_config_field_literals_and_seeded_delays() -> None:
    """g15 detection ``m31/m32/m33`` (L280 ``arg->None``) + ``m41`` (L283) +
    ``m42`` (L284) + ``m43`` (L285) - the five ``RetryConfig`` field literals.

    Shipped (pipeline_workers.py:277-287)::

        self._retry_handler = retry_handler or RetryHandler(
            redis_client=redis_client,
            config=RetryConfig(
                max_retries=3,
                base_delay_seconds=1.0,
                max_delay_seconds=30.0,
                exponential_base=2.0,
                jitter=True,
            ),
        )

    One field/type tuple kills all six.  The functional mirror is the seeded
    ``get_delay``: ``min(base * exponential_base ** (attempt - 1), max_delay)`` plus at
    most 25% jitter, so ``max_delay_seconds=None`` or ``exponential_base=None`` raises
    ``TypeError`` and a falsy ``jitter`` makes attempt 2 EXACTLY 2.0 - which the strict
    ``>`` below forbids.  m34-m38 (dropped literals that EQUAL the dataclass defaults)
    are manifest-EQUIVALENT and are not claimed here.
    """
    # No RetryHandler patch here: the leg needs the REAL handler, because that is
    # where the received config lands (the construction-argument half is the leg
    # below, with the autospec'd handler).
    config = build("DetectionQueueWorker")._retry_handler.config

    assert isinstance(config, RetryConfig), f"config type mutated: {config!r}"
    for name, value in RETRY_FIELDS:
        field = getattr(config, name)
        assert field == value, f"RetryConfig.{name} mutated: {field!r} != {value!r}"
        assert type(field) is type(value), (
            f"RetryConfig.{name} type mutated: {type(field)!r} != {type(value)!r}"
        )

    assert 1.0 <= config.get_delay(1) <= 1.25, f"attempt-1 delay mutated: {config.get_delay(1)!r}"
    assert 2.0 < config.get_delay(2) <= 2.5, (
        f"attempt-2 delay mutated: {config.get_delay(2)!r} - a jitter-free config "
        "is m33/m43's route"
    )
    assert 30.0 <= config.get_delay(9) <= 37.5, f"clamped delay mutated: {config.get_delay(9)!r}"


def test_retry_handler_construction_arguments() -> None:
    """g15 detection ``m25/m27`` (L278 ``redis_client=`` -> ``None`` / dropped) and
    ``m26/m28`` (the ``config=RetryConfig(...)`` argument -> ``None`` / dropped).

    ``RetryHandler.__init__`` stores ``config or RetryConfig()``, so BOTH config
    mutants RE-MATERIALISE a shipped-equal config behind
    ``worker._retry_handler.config`` - the field read is VACUOUS for them.  Their only
    route is the RECEIVED construction argument, pinned here as "a RetryConfig whose
    five fields are the shipped literals".  The redis identity plus the key-set pin
    kill m25/m27 (a dropped kwarg would be filled from the ``None`` default, so
    presence matters as much as identity).
    """
    redis = MagicMock(name="redis-client")
    with patch_module("RetryHandler") as handler, patch_settings():
        worker = DetectionQueueWorker(
            redis_client=redis,
            detector_client=MagicMock(),
            video_processor=MagicMock(),
            frame_buffer=MagicMock(),
        )

    assert handler.call_count == 1, f"RetryHandler built {handler.call_count} times"
    call = handler.call_args
    assert sorted(call.kwargs) == ["config", "redis_client"], (
        f"RetryHandler kwargs mutated: {sorted(call.kwargs)!r}"
    )
    assert call.kwargs["redis_client"] is redis, (
        f"RetryHandler redis_client mutated: {call.kwargs['redis_client']!r}"
    )
    config = call.kwargs["config"]
    assert isinstance(config, RetryConfig), (
        f"the received config must BE a RetryConfig instance, got {config!r}"
    )
    got = tuple((name, getattr(config, name)) for name, _ in RETRY_FIELDS)
    assert got == RETRY_FIELDS, f"received config fields mutated: {got!r}"
    assert worker._retry_handler is handler.return_value


def test_detection_video_settings_are_read() -> None:
    """g15 detection ``m44/m45`` (L290/L291 ``settings.video_*`` -> ``None``) - the
    construction half.

    Both settings values are read once at construction and stored; the kwargs leg
    below is the consumer half.
    """
    worker = build("DetectionQueueWorker")

    assert worker._video_frame_interval == VIDEO_FRAME_INTERVAL, (
        f"video frame interval mutated: {worker._video_frame_interval!r}"
    )
    assert worker._video_max_frames == VIDEO_MAX_FRAMES, (
        f"video max frames mutated: {worker._video_max_frames!r}"
    )


async def test_detection_video_settings_reach_the_extraction_kwargs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The consumer half of g15 ``m44/m45``: the extraction keywords.

    Shipped (pipeline_workers.py:654-660)::

        frame_paths = await self._video_processor.extract_frames_for_detection_batch(
            video_path=video_path,
            interval_seconds=self._video_frame_interval,
            max_frames=self._video_max_frames,
        )

    One shipped video pass with NO frames extracted: that arm returns immediately
    after the call (one WARNING, no detections, no DB session), so the extraction
    keywords are the whole observable and the leg cannot drift into detector code.
    """
    processor = MagicMock(name="video-processor")
    processor.extract_frames_for_detection_batch = AsyncMock(return_value=[])
    worker = build("DetectionQueueWorker", video_processor=processor)
    win(caplog)

    await worker._process_video_detection(
        "cam-9",
        "var/spool/clip.mp4",
        {"camera_id": "cam-9", "file_path": "var/spool/clip.mp4", "media_type": "video"},
    )

    call = processor.extract_frames_for_detection_batch.await_args
    assert call is not None, "the video branch never extracted frames"
    assert call.kwargs == {
        "video_path": "var/spool/clip.mp4",
        "interval_seconds": VIDEO_FRAME_INTERVAL,
        "max_frames": VIDEO_MAX_FRAMES,
    }, f"extraction kwargs mutated: {call.kwargs!r}"
    only(caplog, logging.WARNING, "No frames extracted from video: var/spool/clip.mp4")


async def test_detection_poll_timeout_is_the_blpop_timeout_kwarg() -> None:
    """Where ``poll_timeout`` is consumed: the legacy BLPOP call (g15 detection
    ``m1``'s second route).

    Shipped (pipeline_workers.py:419-424)::

        item = await self._redis.get_from_queue(
            self._queue_name,
            timeout=self._poll_timeout,
        )

    ``use_redis_streams`` is False in the injected settings, so one loop turn makes
    exactly that call, gets ``None`` and ``continue``s.
    """
    redis = MagicMock(name="redis-client")
    redis.get_from_queue = AsyncMock(side_effect=yielder(None))
    redis.get_queue_length = AsyncMock(side_effect=yielder(0))
    worker = build("DetectionQueueWorker", redis_client=redis)

    def condition() -> bool:
        return redis.get_from_queue.await_count >= 1

    hit = await drive_loop(worker, condition)
    assert hit, "the legacy queue branch never read the queue"

    call = redis.get_from_queue.await_args
    assert call is not None
    assert call.args == (DETECTION_QUEUE,), f"queue argument mutated: {call.args!r}"
    assert call.kwargs == {"timeout": DETECTION_POLL_TIMEOUT}, (
        f"BLPOP timeout kwarg mutated: {call.kwargs!r}"
    )


async def test_timeout_worker_keeps_the_client_the_stage_latency_call_needs() -> None:
    """g15 BatchTimeout ``m1`` (L1216 ``self._redis = redis_client`` -> ``= None``).

    Construction proves nothing for this key - the L1217 aggregator fallback reads the
    constructor PARAMETER - so only a READER of ``self._redis`` discriminates, and the
    shipped one is the loop's
    ``await record_stage_latency(self._redis, "batch", duration * 1000)``
    (pipeline_workers.py:1329-1333).  A non-empty ``check_batch_timeouts()`` result
    drives exactly that arm; ``_check_interval`` is zeroed so the loop's own sleep
    never eats the budget.  The ``record_stage_latency`` double is owned by this leg and
    installed via ``new=``, because the whole point is to read its call records once the
    loop is cancelled.
    """
    redis = MagicMock(name="redis-client")
    aggregator = MagicMock(name="aggregator")
    aggregator.check_batch_timeouts = AsyncMock(side_effect=yielder(["batch-1", "batch-2"]))
    latency = create_autospec(M.record_stage_latency)
    worker = build("BatchTimeoutWorker", redis_client=redis, batch_aggregator=aggregator)
    assert worker._redis is redis
    worker._check_interval = 0.0

    def condition() -> bool:
        return latency.await_count >= 1

    hit = await drive_loop(worker, condition, extra={"record_stage_latency": latency})
    assert hit, "the closed-batch arm never ran"

    assert aggregator.check_batch_timeouts.await_count >= 1, "the loop never checked timeouts"
    call = latency.await_args
    assert call is not None, "record_stage_latency was never awaited"
    assert call.args[0] is redis, (
        f"self._redis mutated: record_stage_latency received {call.args[0]!r}"
    )
    assert call.args[1] == "batch", f"stage label mutated: {call.args!r}"


# =============================================================================
# g15 - 3) _supervisor / _worker_name, observed through the heartbeat branch
# =============================================================================


@pytest.mark.parametrize(
    ("cls_name", "label"),
    [
        ("DetectionQueueWorker", "d-28"),
        ("AnalysisQueueWorker", "a-28"),
        ("BatchTimeoutWorker", "bt-28"),
        ("QueueMetricsWorker", "qm-28"),
    ],
)
async def test_heartbeat_reports_the_stored_supervisor_and_name(
    cls_name: str,
    label: str,
) -> None:
    """g15 detection ``m46`` (L294) + analysis ``m12`` (L805) + BatchTimeout ``m7``
    (L1222) + metrics ``m4`` (L1399) - ``self._supervisor = supervisor`` -> ``= None``;
    and BatchTimeout ``m8`` (L1223) + metrics ``m5`` (L1400) - ``self._worker_name =
    worker_name`` -> ``= None``.

    Every ``_run_loop`` carries the same NEM-4148 block
    (pipeline_workers.py:389-393 and its three mirrors)::

        if self._supervisor is not None:
            now = time_module.time()
            if now - last_heartbeat >= heartbeat_interval:
                self._supervisor.record_heartbeat(self._worker_name)
                last_heartbeat = now

    A supervisor the constructor threw away is never reached (ZERO calls) and a
    stored-but-``None`` name arrives as ``None``, so the recorded argument pins both
    assignments.  ``record_heartbeat`` is a plain (sync) method on the shipped
    ``WorkerSupervisor``, so the autospec'd instance double records it synchronously -
    the manifest's "awaited" wording does not match the shipped signature and the
    shipped code wins.  The scripted clock steps past the 20-second period exactly
    once, so the branch fires once per worker with no sleeping.
    """
    redis = MagicMock(name="redis-client")
    redis.get_from_queue = AsyncMock(side_effect=yielder(None))
    redis.get_queue_length = AsyncMock(side_effect=yielder(0))
    aggregator = MagicMock(name="aggregator")
    aggregator.check_batch_timeouts = AsyncMock(side_effect=yielder([]))
    supervisor = create_autospec(WorkerSupervisor, instance=True)
    extra = {"batch_aggregator": aggregator} if cls_name == "BatchTimeoutWorker" else {}
    worker = build(cls_name, redis_client=redis, supervisor=supervisor, worker_name=label, **extra)
    assert worker._supervisor is supervisor
    assert worker._worker_name == label
    if cls_name == "BatchTimeoutWorker":
        worker._check_interval = 0.0
    if cls_name == "QueueMetricsWorker":
        worker._update_interval = 0.0

    def condition() -> bool:
        return supervisor.record_heartbeat.call_count >= 1

    hit = await drive_loop(worker, condition)
    assert hit, f"{cls_name}: no heartbeat was reported for {label!r}"

    calls = supervisor.record_heartbeat.call_args_list
    assert len(calls) == 1, f"{cls_name}: heartbeat reported {len(calls)} times: {calls}"
    assert calls[0].args == (label,), f"{cls_name}: heartbeat label mutated: {calls[0].args!r}"
    assert not calls[0].kwargs, f"{cls_name}: heartbeat kwargs mutated: {calls[0].kwargs!r}"


# =============================================================================
# g16 - the manager's signal handlers
# =============================================================================


def test_install_logs_the_confirmation_debug_and_registers_both_signals(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """g16 ``m12-m15`` (L1982 ``arg->None`` / XX / lower / upper on the confirmation
    DEBUG) plus the shipped registration shape.

    Shipped (pipeline_workers.py:1969-1982)::

        loop = asyncio.get_running_loop()

        def create_shutdown_handler(sig: signal.Signals) -> None:
            def handler() -> None:
                ...
            loop.add_signal_handler(sig, handler)

        create_shutdown_handler(signal.SIGTERM)
        create_shutdown_handler(signal.SIGINT)
        self._signal_handlers_installed = True
        logger.debug("Signal handlers installed for SIGTERM and SIGINT")

    A fresh manager starts with the flag clear (L1646), so this first install is the
    arm under test: the DEBUG text is pinned raw and the two signals are pinned in the
    shipped order.
    """
    manager, _doubles = build_manager()
    assert manager._signal_handlers_installed is False, (
        "a fresh manager must start with the flag clear"
    )
    loop = RecordingLoop()
    win(caplog)

    with patch_running_loop(loop):
        assert manager._install_signal_handlers() is None

    only(caplog, logging.DEBUG, SIGNALS_INSTALLED_DEBUG)
    assert texts(caplog, logging.INFO) == [], "installing handlers logs no INFO"
    assert loop.signals == [signal.SIGTERM, signal.SIGINT], (
        f"registrations mutated: {loop.signals!r}"
    )
    assert manager._signal_handlers_installed is True, (
        "the shipped install ends by raising the flag"
    )


def test_not_implemented_error_becomes_one_debug(caplog: pytest.LogCaptureFixture) -> None:
    """g16 ``m16`` (L1985 ``logger.debug(f"Could not install signal handlers: {e}")``
    -> ``logger.debug(None)``).

    Shipped (pipeline_workers.py:1983-1986)::

        except (NotImplementedError, RuntimeError) as e:
            # Signal handlers not supported (e.g., Windows, not main thread)
            logger.debug(f"Could not install signal handlers: {e}")

    A Windows ``ProactorEventLoop`` cannot be constructed on this Linux host, so the
    ``NotImplementedError`` comes from the injected loop double; the shipped arm still
    formats the exception into the message, and that text plus the DEBUG-only shape
    and the untouched flag are what is pinned.
    """
    manager, _doubles = build_manager()
    error = NotImplementedError()
    loop = RecordingLoop(side_effect=error)
    win(caplog)

    with patch_running_loop(loop):
        assert manager._install_signal_handlers() is None

    only(caplog, logging.DEBUG, SIGNAL_FAILED_DEBUG.format(error))
    assert texts(caplog, logging.INFO) == []
    assert texts(caplog, logging.WARNING) == []
    assert loop.added == [], "nothing may be registered when the install fails"
    assert manager._signal_handlers_installed is False, (
        "the failure arm never reaches the flag write"
    )


async def test_a_start_stop_start_cycle_does_not_re_register(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """g16 ``m10/m11`` (L1981 ``self._signal_handlers_installed = True`` -> ``None`` /
    ``False``) through the shipped caller's guard.

    ``start()`` (pipeline_workers.py:1834-1836)::

        # Install signal handlers (only once)
        if not self._signal_handlers_installed:
            self._install_signal_handlers()

    Under either variant the flag stays falsy, so the SECOND ``start()`` (after a
    ``stop()`` cleared ``_running``) re-enters the installer and the loop receives FOUR
    registrations instead of two.  The workers are constructor doubles and the
    websocket emitter is ``None``, so the real ``start()`` / ``stop()`` bodies run
    their shipped control flow - the two ``asyncio.TaskGroup`` blocks included - with
    nothing real attached.
    """
    manager, _doubles = build_manager()
    loop = RecordingLoop()
    win(caplog)

    with patch_running_loop(loop):
        await manager.start()
        assert manager._signal_handlers_installed is True
        assert manager.running is True
        await manager.stop()
        assert manager.running is False
        await manager.start()

    assert loop.signals == [signal.SIGTERM, signal.SIGINT], (
        f"a start/stop/start cycle registered {loop.signals!r} - the guard at L1835 "
        "decides on the flag these two keys clear"
    )
    assert manager._signal_handlers_installed is True, (
        f"the installed flag mutated: {manager._signal_handlers_installed!r}"
    )
    assert texts(caplog, logging.DEBUG).count(SIGNALS_INSTALLED_DEBUG) == 1, (
        f"the installer ran more than once: {texts(caplog, logging.DEBUG)!r}"
    )


async def test_running_manager_warns_and_skips_re_install(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Control for the flag pair: ``start()`` on a running manager takes the
    L1821-1823 early return (one WARNING, zero registrations).  The install guard sits
    AFTER that return, so a start/stop/start cycle is the only route back to it - which
    is why ``m10/m11`` need the cycle above rather than a double install.
    """
    manager, _doubles = build_manager()
    manager._running = True
    loop = RecordingLoop()
    win(caplog)

    with patch_running_loop(loop):
        assert await manager.start() is None

    only(caplog, logging.WARNING, ALREADY_RUNNING_WARNING)
    assert loop.added == [], "a running manager must not install handlers"
    assert manager._signal_handlers_installed is False


async def test_sigterm_handler_logs_and_schedules_the_manager_stop(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """g16 ``m2`` (L1974 ``logger.info(None)``) + ``m3`` (L1975
    ``asyncio.create_task(None)``).

    The installed handler body is::

        def handler() -> None:
            logger.info(f"Received signal {sig.name}, initiating graceful shutdown")
            asyncio.create_task(self.stop())

    Two discriminators, in shipped order.  ``create_task(None)`` raises ``TypeError``
    SYNCHRONOUSLY inside the handler - the real ``create_task`` insists on a coroutine -
    and ``_install_signal_handlers`` only catches ``NotImplementedError`` /
    ``RuntimeError``, so the ``raised == []`` pin is m3's kill.  m2's
    ``logger.info(None)`` instead lands a ``None`` message in the window, which the raw
    ``only()`` pin rejects.  The scheduled coroutine is then awaited so the shipped
    ``manager.stop()`` really runs its ``asyncio.TaskGroup`` fan-out into the worker
    doubles.
    """
    manager, doubles = build_manager()
    loop = RecordingLoop()
    created: list[asyncio.Task] = []

    win(caplog)
    with (
        patch_running_loop(loop),
        patch("asyncio.create_task", new=record_task(created)),
    ):
        manager._install_signal_handlers()
        handler = loop.handler_for(signal.SIGTERM)
        raised: list[BaseException] = []
        try:
            handler()
        except TypeError as exc:  # shipped never raises; create_task(None) does
            raised.append(exc)

    only(caplog, logging.INFO, SIGNAL_RECEIVED_INFO.format(signal.SIGTERM.name))
    assert raised == [], (
        f"the shipped handler cannot raise: {raised!r} - create_task(None) schedules "
        "nothing and a SIGTERM would never start the shutdown"
    )
    assert len(created) == 1, f"create_task call count mutated: {created!r}"

    # A signal only ever arrives on a RUNNING manager, so the scheduled stop() takes
    # its fan-out arm rather than the L1893 "not running" guard return.
    manager._running = True
    win(caplog)
    await _REAL_WAIT_FOR(created[0], timeout=STOP_TEST_TIMEOUT)
    assert doubles["_timeout_worker"].stop.await_count == 1, (
        "the scheduled stop() never reached the enabled timeout worker"
    )
    assert texts(caplog, logging.INFO) == [
        "Stopping PipelineWorkerManager",
        "PipelineWorkerManager stopped all workers",
    ], f"the scheduled shutdown logged {texts(caplog, logging.INFO)!r}"


async def test_sigint_handler_names_SIGINT(caplog: pytest.LogCaptureFixture) -> None:
    """The SIGINT twin: each closure captures its own ``sig``, so the interpolated name
    must be ``SIGINT`` and never ``SIGTERM`` - and the same scheduling contract applies,
    so m2's ``None`` message and m3's ``TypeError`` are both caught here as well.
    """
    manager, doubles = build_manager()
    loop = RecordingLoop()
    created: list[asyncio.Task] = []

    win(caplog)
    with (
        patch_running_loop(loop),
        patch("asyncio.create_task", new=record_task(created)),
    ):
        manager._install_signal_handlers()
        handler = loop.handler_for(signal.SIGINT)
        raised: list[BaseException] = []
        try:
            handler()
        except TypeError as exc:
            raised.append(exc)

    only(caplog, logging.INFO, SIGNAL_RECEIVED_INFO.format(signal.SIGINT.name))
    assert raised == [], f"the shipped handler cannot raise: {raised!r}"
    assert len(created) == 1, f"create_task call count mutated: {created!r}"

    manager._running = True
    win(caplog)
    await _REAL_WAIT_FOR(created[0], timeout=STOP_TEST_TIMEOUT)
    assert doubles["_timeout_worker"].stop.await_count == 1
    assert SIGNAL_RECEIVED_INFO.format(signal.SIGTERM.name) not in texts(caplog, logging.INFO), (
        "the SIGINT closure must interpolate SIGINT, not SIGTERM"
    )


# =============================================================================
# g16 - drain_queues default + get_status timeout slot
# =============================================================================


def test_drain_default_logs_the_shipped_thirty_second_message(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """g16 ``drain_queues m1`` (L1698 METHOD default ``30.0`` -> ``31.0``).

    Shipped (pipeline_workers.py:1726-1729)::

        logger.info(
            f"Starting queue drain with {initial_count} pending tasks, timeout={timeout}s",
            extra={"initial_count": initial_count, "timeout": timeout},
        )

    The DEFAULT is observable only through a no-argument call, so the message text AND
    both ``extra`` fields are pinned - the field pair also pins the key names.
    ``get_pending_count`` answers 3 then 0 while the function-local ``import time``
    keeps ``time.time`` at 0.0, so the drain returns on its first poll and the INFO
    triple is the shipped sequence.  The module-level ``drain_queues`` default is
    g17's key (killed in ``test_pipeline_workers_batch28_17.py``); nothing here asserts
    it.
    """
    manager, _doubles = build_manager()
    manager.get_pending_count = AsyncMock(side_effect=[3, 0])
    win(caplog)

    with patch_time(return_value=0.0):
        remaining = _run_sync(manager.drain_queues())

    assert remaining == 0, f"the drain returned {remaining!r}"
    assert texts(caplog, logging.INFO) == [
        STOP_ACCEPTING_INFO,
        DRAIN_START_INFO.format(3, "30.0"),
        DRAIN_DONE_INFO.format("0.0"),
    ], f"drain INFO sequence mutated: {texts(caplog, logging.INFO)!r}"
    start = at(caplog, logging.INFO)[1]
    pin_record(start, msg=DRAIN_START_INFO.format(3, "30.0"), level=logging.INFO)
    assert start.initial_count == 3, f"extra.initial_count mutated: {start.initial_count!r}"
    assert start.timeout == DRAIN_DEFAULT_TIMEOUT, (
        f"extra.timeout mutated: {start.timeout!r} != {DRAIN_DEFAULT_TIMEOUT!r}"
    )
    done = at(caplog, logging.INFO)[2]
    assert done.initial_count == 3, f"completion extra mutated: {done.initial_count!r}"
    assert manager.accepting is False, "drain_queues must stop accepting before polling"


def _run_sync(coro: Any) -> Any:
    """Run one coroutine to completion on a private loop (sync-test escape hatch)."""

    async def _runner() -> Any:
        return await coro

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_runner())
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        finally:
            asyncio.set_event_loop(None)
            loop.close()


def test_get_status_exposes_the_timeout_worker_stats_dict(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """g16 ``get_status m26`` (L1803-1804 ``status["workers"]["timeout"] =
    self._timeout_worker.stats.to_dict()`` -> ``= None``).

    Shipped builds ``{"running", "accepting", "workers"}`` and then fills one entry per
    enabled worker; the timeout entry IS the worker's own ``to_dict()`` result, and the
    ``state`` field inside it is ``WorkerState.value``.
    """
    manager, doubles = build_manager(enable_metrics_worker=True)
    stats = {
        "items_processed": 4,
        "errors": 1,
        "last_processed_at": 12.5,
        "state": WorkerState.RUNNING.value,
    }
    doubles["_timeout_worker"].stats.to_dict.return_value = stats
    doubles["_metrics_worker"].running = True
    manager._running = True
    manager._accepting = False
    win(caplog)

    status = manager.get_status()

    assert status["running"] is True
    assert status["accepting"] is False
    assert status["workers"]["timeout"] is stats, (
        f"the timeout slot must be the worker's own to_dict() result: "
        f"{status['workers']['timeout']!r}"
    )
    assert status["workers"]["timeout"]["state"] == "running"
    assert status["workers"]["metrics"] == {"running": True}, (
        "the metrics slot is the running flag, not a stats dict"
    )
    assert "detection" not in status["workers"], "detection workers were disabled"
    assert "analysis" not in status["workers"], "analysis workers were disabled"
    assert msgs(caplog) == [], "get_status does not log"


def test_get_status_omits_a_disabled_timeout_worker(caplog: pytest.LogCaptureFixture) -> None:
    """Control for the ``if self._timeout_worker:`` guard: with the timeout worker
    disabled the key is ABSENT rather than ``None`` - and ABSENT-vs-``None`` is exactly
    the distinction the ``= None`` mutant erases, so both legs are needed to tell
    "disabled" from "stats dropped".
    """
    manager, _doubles = build_manager(enable_timeout_worker=False, enable_metrics_worker=False)
    win(caplog)

    status = manager.get_status()

    assert status["workers"] == {}, f"unexpected worker entries: {status['workers']!r}"
    assert "timeout" not in status["workers"]
    assert msgs(caplog) == []


# =============================================================================
# Manifest EQUIVALENT keys in these groups - replay-verified ground truth
# =============================================================================
# EIGHT keys carry NO assertion and stayed GREEN under real replay, exactly as the
# manifest dispositions predict:
# g15 three dead `_task` initial values: AnalysisQueueWorker m16 (L809),
#     BatchTimeoutWorker m11 (L1226), DetectionQueueWorker m50 (L298) - every leg
#     that reads the slot ASSIGNS it first, so the constructor value never surfaces.
# g15 DetectionQueueWorker m34-m38 (L280): each dropped RetryConfig literal equals
#     the dataclass default, so the config reconstructs shipped-identical and every
#     seeded get_delay is unchanged.
# TWO further manifest-EQUIVALENT keys ARE red under this battery - the manifest's
# "unobservable" rationale is contradicted by construction because the tests read
# the private slot directly:
# g14 QueueMetricsWorker.stop m12 (L1447 `_task = None` -> `""`) reddens
#     `assert worker._task is None` in test_metrics_stop_uses_the_worker_then_cancels
#     - the manifest argued from control flow only (no shipped code branches on the
#     post-stop slot value), which is true, but the slot itself distinguishes the
#     two values.
# g15 QueueMetricsWorker m8 (L1403 `_task = None` -> `""`) reddens the same kind of
#     read in test_metrics_worker_stop_on_a_stopped_worker_logs_nothing, where the
#     value is the CONSTRUCTOR's - the guard-return stop() never touches the slot,
#     so the construction value is exactly what the assert sees.
# Both kills are kept: honesty over papering, and neither assert bends production.
