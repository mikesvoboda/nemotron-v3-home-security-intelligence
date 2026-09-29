"""batch-28 lane 15 - ``pipeline_workers`` group g15: the four worker ``__init__``s.

Module: ``backend/services/pipeline_workers.py`` (md5 d6e3c91fc85bfaea19f0d907491eefbf,
git blob 05b50f5a).  Admitted manifest: ``/tmp/wp-pw/pipeline_workers/manifest.json``
``idx == 15`` with ``group_15.keys`` (41 keys = 32 KILLABLE + 9 manifest-EQUIVALENT) and
``diffs.json`` / ``survivors.json`` for the per-key diffs.  Every line number below is a
coordinate in the CURRENT blob, and every assert is justified by that shipped text.

The four constructors under test
================================
* ``DetectionQueueWorker.__init__``  - L234-300
* ``AnalysisQueueWorker.__init__``   - L778-814
* ``BatchTimeoutWorker.__init__``    - L1200-1230
* ``QueueMetricsWorker.__init__``    - L1380-1406

Test -> mutant-key map (32 KILLABLE keys)
=========================================
* detection ``m1`` (L243 ``poll_timeout: int = 5`` -> ``6``) + ``m2`` (L244
  ``stop_timeout: float = 10.0`` -> ``11.0``)
  -> ``test_detection_defaults_hold_their_shipped_literals`` plus the consumer leg
  ``test_detection_poll_timeout_is_the_blpop_timeout_kwarg``.
* detection ``m3/m4`` (L246) + analysis ``m3/m4`` (L786) - the ``worker_name`` ctor
  default, XX-wrapped / upper-cased.  **OCCURRENCE-TWIN CHECK**: the two functions carry
  the same ``(before, after)`` pair shape differing only in the cited line, so the two
  shipped-name asserts plus the two mixed-case overrides below claim all four keys.
  -> ``test_worker_name_defaults_are_the_stored_name_verbatim``.
* analysis ``m1`` (L783 5 -> 6) + ``m2`` (L784 30.0 -> 31.0) + ``m18`` (L814
  ``self._broadcaster: Any = None`` -> ``""``; the shipped accessor tests this slot with
  ``is None``, so IDENTITY - not truthiness - is the discriminator)
  -> ``test_analysis_defaults_and_the_lazy_broadcaster_slot``.
* analysis ``m8`` (L802 - the shipped VLM 1.5 form is
  ``analyzer or build_pipeline_analyzer(redis_client=redis_client)``; the variant passes
  ``redis_client=None``)
  -> ``test_analyzer_fallback_receives_the_constructor_client``.
* analysis ``m12`` (L808 ``self._supervisor = supervisor`` -> ``= None``) + detection
  ``m46`` (L295) + BatchTimeout ``m7`` (L1225) - the same assignment; and BatchTimeout
  ``m8`` (L1226) + metrics ``m5`` (L1403) - ``self._worker_name = worker_name`` ->
  ``= None``; plus metrics ``m4`` (L1402)
  -> ``test_heartbeat_reports_the_stored_supervisor_and_name`` (4 params).
* BatchTimeout ``m1`` (L1219 ``self._redis = redis_client`` -> ``= None``)
  -> ``test_timeout_worker_keeps_the_client_the_stage_latency_call_needs``:
  construction proves NOTHING for this key (the L1220 aggregator fallback reads the
  constructor PARAMETER, not the attribute), so the only discriminator is a shipped
  READER of ``self._redis`` - the loop's ``record_stage_latency(self._redis, …)``.
* BatchTimeout ``m4`` (L1220) + detection ``m16`` (L269) -
  ``BatchAggregator(redis_client=redis_client)`` -> ``redis_client=None``
  -> ``test_aggregator_fallbacks_receive_the_constructor_client``.
* detection ``m25`` (L280 ``redis_client=redis_client`` -> ``None``) + ``m27`` (that
  argument DROPPED) + ``m26`` (L281 ``config=RetryConfig(…)`` -> ``config=None``) +
  ``m28`` (that argument DROPPED)
  -> ``test_retry_handler_construction_receives_the_shipped_config``.
  **REWORK LOG CARRIED FORWARD**: m26/m28 must NOT rest on
  ``worker._retry_handler.config`` field equality.  ``RetryHandler.__init__`` stores
  ``self._config = config or RetryConfig()``, so BOTH variants RE-MATERIALISE a
  shipped-equal config behind that attribute and the field read is VACUOUS for them.
  Their route is the CAPTURED ``config=`` construction argument (a ``RetryConfig`` whose
  five fields are the shipped literals) - and the identity invariant
  ``handler.config is received_arg`` asserted here is what makes that capture
  load-bearing rather than decorative.
* detection ``m31`` (L284 ``max_delay_seconds=30.0`` -> ``None``) + ``m32`` (L285
  ``exponential_base=2.0`` -> ``None``) + ``m33`` (L286 ``jitter=True`` -> ``None``) +
  ``m41`` (L284 -> ``31.0``) + ``m42`` (L285 -> ``3.0``) + ``m43`` (L286 -> ``False``)
  -> ``test_retry_config_field_literals_and_seeded_delays``: the five-field tuple
  ``(3, 1.0, 30.0, 2.0, True)`` kills all six, and the ``get_delay`` mirror restates the
  same thing functionally (``max_delay``/``exponential_base`` as ``None`` raise
  ``TypeError`` inside the shipped formula; falsy ``jitter`` makes attempt 2 EXACTLY 2.0,
  which the strict ``>`` forbids).
* detection ``m44`` (L291 ``settings.video_frame_interval_seconds`` -> ``None``) +
  ``m45`` (L292 ``settings.video_max_frames`` -> ``None``)
  -> ``test_detection_video_settings_are_read`` (the stored pair) and
  ``test_detection_video_settings_reach_the_extraction_kwargs`` (the same two values
  arriving as the ``extract_frames_for_detection_batch`` keywords at L657-661).
* metrics ``m3`` (L1399 ``self._stop_timeout = stop_timeout`` -> ``None``)
  -> ``test_metrics_stop_timeout_reaches_the_wait_for_kwarg``: the mutant leaves the
  shipped ``stop()`` parked forever in ``wait_for(…, None)``, so the leg drives the
  cancel arm under a bounded test-local ceiling and pins the CAPTURED ``timeout`` kwarg
  against the stored attribute.  The construction half is
  ``test_metrics_and_timeout_defaults``.

EQUIVALENT keys - manifest exceptions, deliberately NOT asserted (9)
====================================================================
``_task`` DEAD-INITIAL-VALUE family (4 keys).  The write
``self._task: asyncio.Task | None = None`` -> ``= ""`` cannot be observed, because every
shipped reader runs only AFTER ``start()`` has overwritten the slot with a real task, and
the guard ahead of the reader returns first.  Both candidate values are falsy:
* ``…xǁAnalysisQueueWorkerǁ__init____mutmut_16`` (L812) - reader ``if self._task:`` at
  L870, behind the ``if not self._running: return`` guard at L862.
* ``…xǁBatchTimeoutWorkerǁ__init____mutmut_11`` (L1229) - reader ``if self._task:`` at
  L1271, same guard shape at L1263.
* ``…xǁDetectionQueueWorkerǁ__init____mutmut_50`` (L299) - sole in-scope reader
  ``if self._task:`` in ``stop()`` at L345, behind ``if not self._running: return`` at
  L337; ``start()`` overwrites at L325.  Both candidate values are falsy.
* ``…xǁQueueMetricsWorkerǁ__init____mutmut_8`` (L1406) - reader ``if self._task:`` at
  L1438 behind the ``if not self._running: return`` guard at L1432, same shape.

DROPPED-RETRYCONFIG-LITERAL family (5 keys).  The declared ``RetryConfig`` defaults at
``backend/services/retry_handler.py:68-72`` ARE ``(max_retries=3,
base_delay_seconds=1.0, max_delay_seconds=30.0, exponential_base=2.0, jitter=True)`` -
byte-equal to the shipped call literals at L282-286 - so dropping any one of them
reconstructs a config identical to shipped and an identical seeded ``get_delay``:
``…xǁDetectionQueueWorkerǁ__init____mutmut_34`` (drops ``max_retries=3``), ``_35``
(``base_delay_seconds=1.0``), ``_36`` (``max_delay_seconds=30.0``), ``_37``
(``exponential_base=2.0``), ``_38`` (``jitter=True``).

Discipline
==========
* Every patch of a real attribute is ``create_autospec``'d and installed with ``new=``
  (so the double outlives its window for call-record reads).  No import-time global spy,
  no module-global mutation: workers are built with ``get_settings`` patched, so no real
  collaborator (network pool, ffmpeg subprocess, module singleton) is ever constructed.
* Exact shipped strings / numbers / call arguments only.  Log legs read the RAW
  ``record.msg``, the level, and the absence of lazy args and ``exc_info``.
* ``time.monotonic`` / ``time.perf_counter`` are never patched.  ``pipeline_workers``'
  own ``import time as time_module`` alias IS patched inside a ``with`` window in the
  driven-loop legs (that alias is what the shipped heartbeat gate calls) - a function
  patch in a window, never an edit to module state.
* Driven loops are polled in 10 ms slices against a scripted clock and CANCELLED after
  their predicate, so no leg can drift toward a tier timeout; the hang-shaped mutant
  (metrics ``m3``) dies on a captured kwarg rather than on a hang.
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import logging
import time as time_module
from collections.abc import Callable
from dataclasses import fields as dataclass_fields
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
    QueueMetricsWorker,
    WorkerState,
)
from backend.services.retry_handler import RetryConfig
from backend.services.worker_supervisor import WorkerSupervisor

MOD = "backend.services.pipeline_workers"
LOG_NAME = M.logger.name  # "backend.services.pipeline_workers"

pytestmark = [pytest.mark.unit]

# The real asyncio primitives, captured at import time so a leg that patches the module
# attribute can still delegate to the shipped implementation.
_REAL_WAIT_FOR = asyncio.wait_for
_REAL_CREATE_TASK = asyncio.create_task
# Captured before any leg patches the module attribute, so a leg that spies the shipped
# RetryHandler CALL can still build a REAL handler from the recorded arguments.
_REAL_RETRY_HANDLER = M.RetryHandler

# =============================================================================
# Shipped literals, transcribed from the current blob
# =============================================================================

# L243 / L244 / (L242 queue_name) / L246 - DetectionQueueWorker.__init__ defaults
DETECTION_POLL_TIMEOUT = 5
DETECTION_STOP_TIMEOUT = 10.0
DETECTION_WORKER_NAME = "detection"
# L783 / L784 / L785 / L786 - AnalysisQueueWorker.__init__
ANALYSIS_POLL_TIMEOUT = 5
ANALYSIS_STOP_TIMEOUT = 30.0
ANALYSIS_WORKER_NAME = "analysis"
# L1204 / L1205 / (L1203) / L1207 - BatchTimeoutWorker.__init__
TIMEOUT_CHECK_INTERVAL = 10.0
TIMEOUT_STOP_TIMEOUT = 10.0
TIMEOUT_WORKER_NAME = "batch_timeout"
# L1383 / L1384 / (L1382) / L1386 - QueueMetricsWorker.__init__
METRICS_UPDATE_INTERVAL = 5.0
METRICS_STOP_TIMEOUT = 5.0
METRICS_WORKER_NAME = "metrics"

# L282-L286 - the RetryConfig(...) literal handed to the detection RetryHandler.
RETRY_FIELDS: tuple[tuple[str, Any], ...] = (
    ("max_retries", 3),
    ("base_delay_seconds", 1.0),
    ("max_delay_seconds", 30.0),
    ("exponential_base", 2.0),
    ("jitter", True),
)
# Guards the transcription above against a field rename/reorder in the dataclass whose
# defaults this battery cites as the EQUIVALENT basis for detection m34-m38.
assert [name for name, _ in RETRY_FIELDS] == [field.name for field in dataclass_fields(RetryConfig)]

# L1435 / L1452 - the only two texts the shipped QueueMetricsWorker.stop() logs; its
# TimeoutError arm (L1441-L1449) holds NO logger call at all.
METRICS_STOPPING_INFO = "Stopping QueueMetricsWorker"
METRICS_STOPPED_INFO = "QueueMetricsWorker stopped"
# L664-L668 - the arm the video leg lands in when extraction yields nothing.
NO_FRAMES_WARNING = "No frames extracted from video: {}"

# Values this file INJECTS through the Settings double and then asserts on.
VIDEO_FRAME_INTERVAL = 1.25
VIDEO_MAX_FRAMES = 7
THUMBNAIL_DIR = "var/thumbs-b28-15"

HEARTBEAT_INTERVAL = 20.0  # L382 - the loop-local heartbeat period
DRIVE_TEST_TIMEOUT = 2.0  # ceiling on a driven-loop predicate, never a shipped value
STOP_TEST_TIMEOUT = 1.5  # ceiling on a stop() window entered with a test-local override


# =============================================================================
# Observation helpers (inlined - the sibling battery keeps them file-locally)
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


def pin_record(record: logging.LogRecord, *, msg: str, level: int) -> None:
    """Assert the observable surface of one shipped single-argument log call.

    Every site this file cites passes ONE already-built message, so ``args`` must stay
    empty (a moved or dropped message argument lands inside ``msg``) and ``exc_info``
    must stay absent.
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
    ``AttributeError`` here instead of passing silently.  ``use_redis_streams`` is False
    so the legacy BLPOP arms (which consume ``_poll_timeout``) are the ones driven.
    """
    spec = create_autospec(Settings, instance=True)
    spec.use_redis_streams = False
    spec.video_frame_interval_seconds = VIDEO_FRAME_INTERVAL
    spec.video_max_frames = VIDEO_MAX_FRAMES
    spec.video_thumbnails_dir = THUMBNAIL_DIR
    spec.detection_worker_count = 1
    spec.analysis_worker_count = 1
    return spec


class PatchedDouble:
    """``patch(target, new=double)`` that also hands the leg its ``double``.

    ``patch(target, autospec=True)`` builds the double itself and RESTORES the real
    callable on exit without leaving a handle behind, so a leg that must read call
    records AFTER its window has closed cannot use that spelling.  Every double here is
    still ``create_autospec``'d from the shipped callable (the autospec rule) and is
    installed with ``new=``, the other accepted spelling of that rule.
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
        f"{MOD}.{attribute}",
        create_autospec(getattr(M, attribute), **autospec_kwargs),
    )


def patch_settings() -> PatchedDouble:
    """``get_settings`` -> an autospec'd callable returning the shipped-value double."""
    return PatchedDouble(
        f"{MOD}.get_settings",
        create_autospec(M.get_settings, return_value=settings_double()),
    )


def patch_asyncio(attribute: str, **autospec_kwargs: Any) -> PatchedDouble:
    """autospec'd ``patch("asyncio.<attribute>")`` (``wait_for`` here)."""
    return PatchedDouble(
        f"asyncio.{attribute}",
        create_autospec(getattr(asyncio, attribute), **autospec_kwargs),
    )


def patch_time(**autospec_kwargs: Any) -> PatchedDouble:
    """``time.time`` -> a scripted double on the ONE ``time`` module object.

    ``pipeline_workers`` reads it through its ``import time as time_module`` alias (the
    heartbeat gates); patching the attribute once reaches every reader of that object.
    """
    return PatchedDouble("time.time", create_autospec(time_module.time, **autospec_kwargs))


def build(cls_name: str, **kwargs: Any) -> Any:
    """Construct one worker of ``cls_name`` with no real collaborator built.

    The shipped constructors build fallback collaborators from settings
    (``DetectorClient`` opens two ``httpx.AsyncClient`` pools, ``VideoProcessor`` mkdirs
    and shells out to ``ffmpeg -version``, ``get_frame_buffer`` touches a module-level
    singleton), so every collaborator the leg does NOT name is injected - filtered
    against the shipped signature, because the four workers do not share one parameter
    list - and ``get_settings`` is patched for the whole construction.  Every fallback
    arm keeps its own autospec'd leg below, which is where those keys actually die.
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

    A bare ``AsyncMock(return_value=None)`` never suspends, so a driven worker loop would
    spin through the polling helper without ever giving it a turn.
    """

    async def _side_effect(*_args: Any, **_kwargs: Any) -> Any:
        await asyncio.sleep(0)
        return value

    return _side_effect


def hang_task() -> asyncio.Task:
    """A task that never finishes on its own - only ``cancel()`` ends it."""
    return _REAL_CREATE_TASK(asyncio.Event().wait())


class Clock:
    """``time_module.time`` double that steps past the heartbeat period once.

    Bumping the value ONLY on call ``bump_at`` makes exactly one heartbeat fire and
    leaves every later gate on the fast path, so no leg has to sleep to cross the
    20-second period.  The shipped queue loops touch the alias twice before any gate
    (the ``last_heartbeat`` / ``last_claim_check`` inits), so ``bump_at=3`` puts the jump
    on the first gate read.
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


async def drive_loop(
    worker: Any,
    condition: Callable[[], bool],
    *,
    extra: dict[str, Any] | None = None,
    timeout: float = DRIVE_TEST_TIMEOUT,
) -> bool:
    """Run ``worker._run_loop()`` until the SYNC ``condition()`` is true.

    The module-level collaborators the shipped loops call are patched for the window and
    ``time_module.time`` is a scripted ``Clock``, so one iteration costs one 10 ms slice
    of real time.  ``extra`` maps a module attribute name to a caller-owned autospec'd
    double (installed with ``new=``) that the leg still needs to read AFTER the drive.
    The loop is always CANCELLED rather than asked to exit: the shipped loops re-read
    ``_running`` only at the top of the next iteration and swallow the
    ``CancelledError``, so a leg must never depend on the exit path - every assertion
    below is about work the loop already did.
    """
    loop = asyncio.get_running_loop()
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
        stack.enter_context(patch_time(side_effect=Clock()))
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
            with contextlib.suppress(asyncio.CancelledError):
                await task
        return hit


async def metrics_stop_with_spy(
    worker: Any,
    *,
    timeouts: list[Any],
) -> None:
    """Run ``worker.stop()`` with ``asyncio.wait_for`` spied from OUTSIDE the worker.

    The spy records the ``timeout`` kwarg the shipped ``stop()`` passes (L1440
    ``timeout=self._stop_timeout``) and delegates to the REAL ``wait_for`` so the shipped
    timeout / cancel / await semantics stay in play.  The double is autospec'd
    (signature-exact) and the spy is ``async def`` because an autospec'd async callable
    awaits an async ``side_effect``.
    """

    async def spy(*args: Any, **kwargs: Any) -> Any:
        timeouts.append(kwargs.get("timeout"))
        return await _REAL_WAIT_FOR(*args, **kwargs)

    with patch_asyncio("wait_for", side_effect=spy) as double:
        await worker.stop()
    assert double.await_count == 1, (
        f"the stop window made {double.await_count} wait_for calls, expected exactly 1"
    )


# =============================================================================
# g15 - 1) constructor defaults read off the shipped objects
# =============================================================================


def test_detection_defaults_hold_their_shipped_literals() -> None:
    """g15 detection ``m1`` (L243 ``poll_timeout: int = 5`` -> ``6``) + ``m2`` (L244
    ``stop_timeout: float = 10.0`` -> ``11.0``) + the ``_queue_name`` slot.

    Those defaults ARE the BLPOP timeout and the force-cancel grace period, so both
    ``number+1`` mutants die on the stored value; the BLPOP-kwarg leg below is m1's
    second route.  Detection's pair is 5 / 10.0 - deliberately different from analysis'
    5 / 30.0 - so each class pins its own numbers.
    """
    worker = build("DetectionQueueWorker")

    assert worker._poll_timeout == DETECTION_POLL_TIMEOUT, (
        f"detection poll_timeout default mutated: {worker._poll_timeout!r}"
    )
    assert worker._stop_timeout == DETECTION_STOP_TIMEOUT, (
        f"detection stop_timeout default mutated: {worker._stop_timeout!r}"
    )
    assert worker._queue_name == DETECTION_QUEUE, (
        f"detection queue name mutated: {worker._queue_name!r}"
    )
    assert worker.running is False
    assert worker.stats.state is WorkerState.STOPPED
    assert worker.stats.items_processed == 0 and worker.stats.errors == 0
    assert worker.stats.to_dict()["state"] == "stopped", "to_dict reports the enum's .value"


def test_analysis_defaults_and_the_lazy_broadcaster_slot() -> None:
    """g15 analysis ``m1`` (L783 ``5`` -> ``6``) + ``m2`` (L784 ``30.0`` -> ``31.0``) +
    ``m18`` (L814 ``self._broadcaster: Any = None`` -> ``""``).

    ``_broadcaster`` is the lazy slot the shipped accessor tests with ``is None``, so the
    string variant dies on IDENTITY, not on truthiness (``""`` is falsy but is not
    ``None``).
    """
    worker = build("AnalysisQueueWorker")

    assert worker._poll_timeout == ANALYSIS_POLL_TIMEOUT, (
        f"analysis poll_timeout default mutated: {worker._poll_timeout!r}"
    )
    assert worker._stop_timeout == ANALYSIS_STOP_TIMEOUT, (
        f"analysis stop_timeout default mutated: {worker._stop_timeout!r}"
    )
    assert worker._queue_name == ANALYSIS_QUEUE, (
        f"analysis queue name mutated: {worker._queue_name!r}"
    )
    assert worker._broadcaster is None, (
        f"the lazy broadcaster slot must start as None, got {worker._broadcaster!r}"
    )


def test_metrics_and_timeout_defaults() -> None:
    """The BatchTimeout / QueueMetrics default block, stated whole.

    ``check_interval`` (L1204) and ``update_interval`` (L1383) carry no survivor in this
    group, but their class-mates do (BatchTimeout m1/m7/m8, metrics m3/m4/m5) and this
    construction leg is what makes a passing neighbour provable rather than accidental.
    The metrics ``_stop_timeout`` read here is the first half of metrics ``m3``'s kill;
    the consumer half is ``test_metrics_stop_timeout_reaches_the_wait_for_kwarg``.
    """
    batch = build("BatchTimeoutWorker")
    metrics = build("QueueMetricsWorker")

    assert batch._check_interval == TIMEOUT_CHECK_INTERVAL, (
        f"batch check_interval mutated: {batch._check_interval!r}"
    )
    assert batch._stop_timeout == TIMEOUT_STOP_TIMEOUT, (
        f"batch stop_timeout mutated: {batch._stop_timeout!r}"
    )
    assert metrics._update_interval == METRICS_UPDATE_INTERVAL, (
        f"metrics update_interval mutated: {metrics._update_interval!r}"
    )
    assert metrics._stop_timeout == METRICS_STOP_TIMEOUT, (
        f"metrics stop_timeout mutated: {metrics._stop_timeout!r}"
    )
    assert not hasattr(metrics, "stats"), "QueueMetricsWorker carries no stats attribute"


def test_worker_name_defaults_are_the_stored_name_verbatim() -> None:
    """g15 detection ``m3/m4`` (L246) + analysis ``m3/m4`` (L786) - the ``worker_name``
    ctor default XX-wrapped / upper-cased.  Also pins the BatchTimeout (L1207) and
    metrics (L1386) defaults.

    **OCCURRENCE-TWIN CHECK**: each pair of functions carries the same
    ``(before, after)`` shape differing only in the cited line, so the two shipped
    defaults below kill all four keys.  The mixed-case overrides prove no ``.lower()`` /
    ``.upper()`` is applied on the way in, which is what makes the ``"DETECTION"`` /
    ``"ANALYSIS"`` variants distinguishable from a shipped name that merely happened to
    be compared case-insensitively.
    """
    assert build("DetectionQueueWorker")._worker_name == DETECTION_WORKER_NAME
    assert build("AnalysisQueueWorker")._worker_name == ANALYSIS_WORKER_NAME
    assert build("BatchTimeoutWorker")._worker_name == TIMEOUT_WORKER_NAME
    assert build("QueueMetricsWorker")._worker_name == METRICS_WORKER_NAME
    assert build("DetectionQueueWorker", worker_name="MiXeD-D")._worker_name == "MiXeD-D"
    assert build("AnalysisQueueWorker", worker_name="MiXeD-A")._worker_name == "MiXeD-A"


# =============================================================================
# g15 - 2) collaborator fallbacks and the RetryConfig block
# =============================================================================


def test_aggregator_fallbacks_receive_the_constructor_client() -> None:
    """g15 detection ``m16`` (L269) + BatchTimeout ``m4`` (L1220) -
    ``BatchAggregator(redis_client=redis_client)`` -> ``redis_client=None``.

    Both sites build the fallback from the constructor PARAMETER, so the captured keyword
    must be the very client handed to the worker.  The double is autospec'd and installed
    with ``new=`` so its call records outlive the window.
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
        assert call is not None, "the detection aggregator fallback never ran"
        assert call.kwargs == {"redis_client": redis}, (
            f"detection aggregator fallback kwargs mutated: {call.kwargs!r}"
        )
        assert call.kwargs["redis_client"] is redis

        aggregator.reset_mock()
        BatchTimeoutWorker(redis_client=redis)
        call = aggregator.call_args
        assert call is not None, "the timeout aggregator fallback never ran"
        assert call.kwargs == {"redis_client": redis}, (
            f"timeout aggregator fallback kwargs mutated: {call.kwargs!r}"
        )
        assert call.kwargs["redis_client"] is redis


def test_analyzer_fallback_receives_the_constructor_client() -> None:
    """g15 analysis ``m8`` - the default analyzer is built with the ctor client.

    Shipped (pipeline_workers.py:800-802)::

        # 1.5: the analyzer is mode-built (PIPELINE_MODE), never spelled
        # here - vlm mode must not silently run this legacy analyzer.
        self._analyzer = analyzer or build_pipeline_analyzer(redis_client=redis_client)

    The variant passes ``redis_client=None``, which reddens the captured-kwarg identity
    assert below.  ``_analyzer`` receiving the builder's return value is the shipped
    ``or`` arm's other half.
    """
    redis = MagicMock(name="redis-client")
    with patch_module("build_pipeline_analyzer") as builder, patch_settings():
        worker = AnalysisQueueWorker(redis_client=redis)

    call = builder.call_args
    assert call is not None, "the analyzer fallback never ran"
    assert call.kwargs == {"redis_client": redis}, (
        f"analyzer fallback kwargs mutated: {call.kwargs!r}"
    )
    assert call.kwargs["redis_client"] is redis
    assert worker._analyzer is builder.return_value


def test_retry_config_field_literals_and_seeded_delays() -> None:
    """g15 detection ``m31``/``m32``/``m33``/``m41``/``m42``/``m43`` - the five
    ``RetryConfig`` field literals at L282-L286.

    Shipped (pipeline_workers.py:277-288)::

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

    One field/value/type tuple kills all six keys.  The functional mirror is the shipped
    ``get_delay`` (retry_handler.py:88-96): ``min(base * exponential_base ** (attempt-1),
    max_delay)`` plus at most 25% jitter, so with ``max_delay_seconds=None`` or
    ``exponential_base=None`` the formula raises ``TypeError``, and a falsy ``jitter``
    makes attempt 2 EXACTLY 2.0 - which the strict ``>`` below forbids.  Detection
    ``m34``-``m38`` (dropped literals that EQUAL the dataclass defaults at
    retry_handler.py:68-72) are manifest-EQUIVALENT and are not claimed here.
    """
    # No RetryHandler patch in this leg: it needs the REAL handler, because that is
    # where the config lands after the shipped `config or RetryConfig()`.  The
    # construction-argument half is the leg below.
    config = build("DetectionQueueWorker")._retry_handler.config

    assert isinstance(config, RetryConfig), f"config type mutated: {config!r}"
    for name, value in RETRY_FIELDS:
        field = getattr(config, name)
        assert field == value, f"RetryConfig.{name} mutated: {field!r} != {value!r}"
        assert type(field) is type(value), (
            f"RetryConfig.{name} type mutated: {type(field)!r} != {type(value)!r}"
        )

    first = config.get_delay(1)
    second = config.get_delay(2)
    clamped = config.get_delay(9)
    assert 1.0 <= first <= 1.25, f"attempt-1 delay mutated: {first!r}"
    assert 2.0 < second <= 2.5, (
        f"attempt-2 delay mutated: {second!r} - a jitter-free config lands exactly on 2.0"
    )
    assert 30.0 <= clamped <= 37.5, f"clamped delay mutated: {clamped!r}"


def test_retry_handler_construction_receives_the_shipped_config() -> None:
    """g15 detection ``m25``/``m27`` (L280) + ``m26``/``m28`` (L281) - the two
    ``RetryHandler`` construction arguments.

    **REWORK LOG (mandated route)**: ``RetryHandler.__init__`` does
    ``self._config = config or RetryConfig()`` (retry_handler.py:230), so BOTH config
    mutants (``config=None`` and the dropped kwarg) RE-MATERIALISE a shipped-equal config
    behind ``worker._retry_handler.config`` - reading that attribute is VACUOUS for them.
    The kill is the CAPTURED construction argument, and the identity invariant
    ``handler.config IS the received argument`` is what makes the capture load-bearing
    rather than decorative.

    Both need the handler to be REAL, so the double here is an autospec'd callable that
    RECORDS the shipped call and then builds a real ``RetryHandler`` from exactly those
    arguments - the shipped code therefore keeps its real collaborator and the capture
    stays observable from outside.  Under ``m26`` the received argument is ``None`` (the
    ``isinstance`` assert fails and the identity read fails behind it); under ``m28`` the
    ``config`` key is absent from the captured kwargs at all; under ``m27`` so is
    ``redis_client``, and under ``m25`` that value is no longer the constructor's client.
    """
    redis = MagicMock(name="redis-client")
    received_calls: list[dict[str, Any]] = []

    def record_and_build(**kwargs: Any) -> Any:
        received_calls.append(kwargs)
        return _REAL_RETRY_HANDLER(**kwargs)

    with (
        PatchedDouble(
            f"{MOD}.RetryHandler",
            create_autospec(M.RetryHandler, side_effect=record_and_build),
        ),
        patch_settings(),
    ):
        worker = DetectionQueueWorker(
            redis_client=redis,
            detector_client=MagicMock(),
            video_processor=MagicMock(),
            frame_buffer=MagicMock(),
        )

    assert len(received_calls) == 1, (
        f"RetryHandler built {len(received_calls)} times by one construction"
    )
    kwargs = received_calls[0]
    assert sorted(kwargs) == ["config", "redis_client"], (
        f"RetryHandler kwargs mutated: {sorted(kwargs)!r}"
    )
    assert kwargs["redis_client"] is redis, (
        f"RetryHandler redis_client mutated: {kwargs['redis_client']!r}"
    )
    received = kwargs["config"]
    assert isinstance(received, RetryConfig), (
        f"the received config must BE a RetryConfig instance, got {received!r}"
    )
    got = tuple((name, getattr(received, name)) for name, _ in RETRY_FIELDS)
    assert got == RETRY_FIELDS, f"received config fields mutated: {got!r}"
    # The identity invariant that makes the capture above load-bearing: the shipped
    # `config or RetryConfig()` stores THIS object, so a mutant that passes None (or
    # nothing) re-materialises a different one and fails here too.
    assert worker._retry_handler.config is received, (
        "RetryHandler did not store the received config object, so the capture above "
        "would not describe what the shipped code used"
    )


def test_detection_video_settings_are_read() -> None:
    """g15 detection ``m44`` (L291 ``settings.video_frame_interval_seconds`` -> ``None``)
    + ``m45`` (L292 ``settings.video_max_frames`` -> ``None``) - the stored half.

    Both settings values are read once at construction and stored; the kwargs leg below is
    the consumer half.  The injected ``Settings`` double carries values that are neither
    ``None`` nor a default, so a dropped read cannot pass.
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
    """The consumer half of g15 ``m44``/``m45``: the extraction keywords.

    Shipped (pipeline_workers.py:657-661)::

        frame_paths = await self._video_processor.extract_frames_for_detection_batch(
            video_path=video_path,
            interval_seconds=self._video_frame_interval,
            max_frames=self._video_max_frames,
        )

    One shipped video pass with NO frames extracted: that arm returns immediately after
    the call (one WARNING, no detections, no DB session), so the extraction keywords are
    the whole observable and the leg cannot drift into detector code.
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
    only(caplog, logging.WARNING, NO_FRAMES_WARNING.format("var/spool/clip.mp4"))


# =============================================================================
# g15 - 3) the readers that make the stored attributes observable
# =============================================================================


async def test_detection_poll_timeout_is_the_blpop_timeout_kwarg() -> None:
    """Where ``_poll_timeout`` is consumed: the legacy BLPOP call - g15 detection
    ``m1``'s second route (L243).

    Shipped (pipeline_workers.py:422-425)::

        item = await self._redis.get_from_queue(
            self._queue_name,
            timeout=self._poll_timeout,
        )

    ``use_redis_streams`` is False in the injected settings, so one loop turn makes
    exactly that call, gets ``None`` and continues.
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
    """g15 BatchTimeout ``m1`` (L1219 ``self._redis = redis_client`` -> ``= None``).

    Construction proves NOTHING for this key - the L1220 aggregator fallback reads the
    constructor PARAMETER - so only a READER of ``self._redis`` discriminates, and the
    shipped one is the loop's
    ``await record_stage_latency(self._redis, "batch", duration * 1000)``
    (pipeline_workers.py:1329).  A non-empty ``check_batch_timeouts()`` result drives
    exactly that arm, and ``_check_interval`` is zeroed so the loop's own sleep never eats
    the budget.  The ``record_stage_latency`` double is owned by this leg and installed
    via ``new=``, because the whole point is to read its call records after the loop is
    cancelled.
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


async def test_metrics_stop_timeout_reaches_the_wait_for_kwarg(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """g15 metrics ``m3`` (L1399 ``self._stop_timeout = stop_timeout`` -> ``= None``) -
    the consumer half.

    Shipped (pipeline_workers.py:1438-1440)::

        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=self._stop_timeout)

    With the attribute mutated to ``None`` the shipped ``stop()`` parks forever in
    ``wait_for`` and never returns, so this leg does not depend on a hang: it asserts the
    stored value is the shipped 5.0 and that the CAPTURED ``timeout`` kwarg equals that
    stored attribute, and it proves the ``TimeoutError`` arm really fires by giving the
    hang a bounded test-local ceiling.  The metrics arm carries no logger call, so the
    INFO pair is the whole log observable and no WARNING may appear.
    """
    worker = build("QueueMetricsWorker")
    assert worker._stop_timeout == METRICS_STOP_TIMEOUT, (
        f"metrics stop_timeout mutated: {worker._stop_timeout!r} != {METRICS_STOP_TIMEOUT!r}"
    )
    shipped_value = worker._stop_timeout
    # Test-local ceiling only: the wait_for window is entered with the value the shipped
    # stop() reads, so a None mutant still never raises TimeoutError, but this leg stays
    # milliseconds-slow instead of burning the real 5.0s.
    worker._stop_timeout = 0.01
    task = hang_task()
    worker._running = True
    worker._task = task
    timeouts: list[Any] = []
    win(caplog)

    returned = True
    try:
        await _REAL_WAIT_FOR(metrics_stop_with_spy(worker, timeouts=timeouts), STOP_TEST_TIMEOUT)
    except TimeoutError:
        returned = False
    finally:
        if not task.done():
            task.cancel()

    assert timeouts == [0.01], (
        f"metrics wait_for timeout kwarg mutated: {timeouts!r} - the shipped call passes "
        f"timeout=self._stop_timeout ({shipped_value!r} at construction)"
    )
    assert returned, "stop() did not return: a None timeout never raises TimeoutError"
    assert task.cancelled(), "the hang must have been cancelled by the timeout arm"
    assert worker._task is None, "the task slot must still be cleared after the arm"
    assert texts(caplog, logging.WARNING) == [], (
        "metrics' TimeoutError arm has no logger call - a WARNING there bends behaviour"
    )
    pin_info_pair(caplog, METRICS_STOPPING_INFO, METRICS_STOPPED_INFO)


# =============================================================================
# g15 - 4) _supervisor / _worker_name, observed through the heartbeat branch
# =============================================================================


@pytest.mark.parametrize(
    ("cls_name", "label"),
    [
        ("DetectionQueueWorker", "d-15"),
        ("AnalysisQueueWorker", "a-15"),
        ("BatchTimeoutWorker", "bt-15"),
        ("QueueMetricsWorker", "qm-15"),
    ],
)
async def test_heartbeat_reports_the_stored_supervisor_and_name(
    cls_name: str,
    label: str,
) -> None:
    """g15 detection ``m46`` (L295) + analysis ``m12`` (L808) + BatchTimeout ``m7``
    (L1225) + metrics ``m4`` (L1402) - ``self._supervisor = supervisor`` -> ``= None``;
    and BatchTimeout ``m8`` (L1226) + metrics ``m5`` (L1403) - ``self._worker_name =
    worker_name`` -> ``= None``.

    Every ``_run_loop`` carries the same NEM-4148 block (pipeline_workers.py:391-395 and
    its three mirrors)::

        if self._supervisor is not None:
            now = time_module.time()
            if now - last_heartbeat >= heartbeat_interval:
                self._supervisor.record_heartbeat(self._worker_name)
                last_heartbeat = now

    A supervisor the constructor threw away is never reached (ZERO calls) and a
    stored-but-``None`` name arrives as ``None``, so the recorded argument pins both
    assignments.  ``record_heartbeat`` is a plain (sync) method on the shipped
    ``WorkerSupervisor``, so the autospec'd instance double records it synchronously -
    the manifest's "awaited" wording does not match the shipped signature and the shipped
    code wins.  The scripted clock steps past the 20-second period exactly once, so the
    branch fires once per worker with no sleeping.
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
# EQUIVALENT disposition (9 keys) - stated, deliberately not asserted
# =============================================================================

EQUIVALENT_KEYS: tuple[str, ...] = (
    "backend.services.pipeline_workers.xǁAnalysisQueueWorkerǁ__init____mutmut_16",
    "backend.services.pipeline_workers.xǁBatchTimeoutWorkerǁ__init____mutmut_11",
    "backend.services.pipeline_workers.xǁDetectionQueueWorkerǁ__init____mutmut_34",
    "backend.services.pipeline_workers.xǁDetectionQueueWorkerǁ__init____mutmut_35",
    "backend.services.pipeline_workers.xǁDetectionQueueWorkerǁ__init____mutmut_36",
    "backend.services.pipeline_workers.xǁDetectionQueueWorkerǁ__init____mutmut_37",
    "backend.services.pipeline_workers.xǁDetectionQueueWorkerǁ__init____mutmut_38",
    "backend.services.pipeline_workers.xǁDetectionQueueWorkerǁ__init____mutmut_50",
    "backend.services.pipeline_workers.xǁQueueMetricsWorkerǁ__init____mutmut_8",
)


def test_equivalent_keys_are_stated_and_not_claimed() -> None:
    """The nine manifest-EQUIVALENT g15 keys, recorded so the battery's coverage claim is
    exact rather than implied.

    Four are ``_task`` DEAD-INITIAL-VALUE writes (analysis L812 / BatchTimeout L1229 /
    detection L299 / metrics L1406): every shipped reader runs only after ``start()`` has
    replaced the slot with a real task and sits behind a ``if not self._running: return``
    guard, and both candidate values are falsy - no construction-time read can be both
    shipped-faithful and discriminating.  Five are dropped ``RetryConfig`` literals whose
    values ARE the declared defaults at retry_handler.py:68-72, so the reconstructed
    config is identical to shipped (the tuple assert below is the positive statement of
    that equivalence: it holds under each of the five variants, which is exactly why they
    are EQUIVALENT and not claimed).
    """
    assert len(EQUIVALENT_KEYS) == 9
    defaults = {field.name: field.default for field in dataclass_fields(RetryConfig)}
    assert tuple((name, defaults[name]) for name, _ in RETRY_FIELDS) == RETRY_FIELDS, (
        "the retry_handler.py:68-72 defaults no longer equal the shipped L282-L286 "
        "literals - the m34-m38 EQUIVALENT ruling would be stale"
    )
