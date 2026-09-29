"""S3 batch-28 lane 06 - ``pipeline_workers`` group g06 kill battery (71 keys).

Module: ``backend/services/pipeline_workers.py`` (git blob 74649fd3 - byte-identical
to the manifest-proven source).  Admitted manifest: ``/tmp/wp-pw/pipeline_workers/``
``manifest.json`` group 6 (71 KILLABLE / 0 EQUIVALENT / 0 NEEDS_INVESTIGATION),
plus ``group_6.keys`` and ``survivors.json`` for the exact per-key diffs.

Target: ``DetectionQueueWorker._process_detection_item`` (L454-547).

Test -> mutant-key map
======================
Every key below is in ``group_6.keys``.  Keys whose diff occurs byte-identically
in more than one shipped def are flagged ``(twin)``; those legs close the twin
shapes everywhere they occur, which is a bonus, not a claim-jump.

- ``xǁDetectionQueueWorkerǁ_process_detection_item__mutmut_4``  L477
  ``camera_id = validated.camera_id`` -> ``= None``
  -> every real-camera-kwarg leg (happy-path legs 1/3/4/6 + the video-arm legs)
- ``_mutmut_5``  L478 ``file_path = validated.file_path`` -> ``= None``
  -> the DEBUG-text legs + the log_context / add_span_attributes / dispatch kwargs
- ``_mutmut_8``  L482 ``self._stats.errors += 1`` -> ``= 1``  (twin of m102)
  -> ``test_invalid_payload_counts_one_error_per_call`` (two rejects -> 2)
- ``_mutmut_11/_12/_13``  L483 ``record_pipeline_error("invalid_detection_payload")``
  -> ``None`` / ``"XX...XX"`` / all-upper
  -> ``test_invalid_payload_labels_the_pipeline_error``
- ``_mutmut_14``  L484 ERROR message arg -> ``None``  (the ``raw_item``/``error``
  record attributes survive, so the message pin is the route);  ``_mutmut_15``
  L484 ``extra={...}`` -> ``extra=None`` and ``_mutmut_17`` L484 ``extra=``
  DROPPED - both leave the record without the two extra attributes, which is the
  same observable, so the truncation/``extra`` pin is their shared route
  -> ``test_invalid_payload_rejects_on_message_text_and_truncated_raw_item``
- ``_mutmut_18/_19/_20/_21``  L487 ``"raw_item"`` -> ``"XXraw_itemXX"`` /
  ``"RAW_ITEM"`` / value ``str(None)[:500]`` / slice ``[:501]``;
  ``_mutmut_22/_23/_24``  L488 ``"error"`` -> ``"XXerrorXX"`` / ``"ERROR"`` /
  value ``str(None)``  -> same test (the 600-char item makes the [:500] cut observable)
- ``_mutmut_25/_26/_27`` + ``_mutmut_28/_29/_30``  L497 ``log_context``
  arg->None (camera / file / media) + drop_arg (each kwarg)  -> happy-path leg 1
- ``_mutmut_31/_32/_33``  L498 span name -> ``None`` / ``"XXdetection_processingXX"``
  / ``"DETECTION_PROCESSING"``  -> leg 2
- ``_mutmut_35/_36/_38/_39/_40/_41``  L501 ``set_pipeline_context_attributes``
  camera->None / stage->None / camera dropped / stage dropped / ``"XXdetectXX"``
  / ``"DETECT"``  -> leg 3
- ``_mutmut_42/_43/_44/_45/_46/_47/_48/_49/_50/_51``  L503-508
  ``add_span_attributes`` four kwargs arg->None + four drop_args + the
  ``pipeline_stage`` ``XX``/upper twins  -> leg 4
- ``_mutmut_52``  L509 ``logger.debug(f"Processing detection item: {file_path}")``
  -> ``logger.debug(None)``  -> leg 5 (and the video-arm DEBUG leg)
- ``_mutmut_56/57/58/59`` (arg->None) + ``_mutmut_60/61/62/63`` (drop_arg)  L513
  ``_process_video_detection(camera_id, file_path, item, pipeline_start_time)``
  -> ``test_video_media_type_dispatches_to_the_video_arm``
- ``_mutmut_64/_65``  L517 camera/file arg->None of the image dispatch
  -> ``test_valid_image_payload_drives_the_full_instrumentation_doppels`` leg 6
  (measured failing set; the full 4-arg pin of that call sits in g08's spec)
- ``_mutmut_77``  L525 ``duration = time.time() - start_time`` -> ``+``
  -> legs 7/8/9 (2000.0 ms becomes 2002000.0 ms on the fixed clock)
- ``_mutmut_78/_82/_83``  L526 ``observe_stage_duration`` stage None/XX/upper -> leg 7
- ``_mutmut_84/_85/_88/_89/_90/_91``  L528 ``record_pipeline_stage_latency``
  label None/XX/upper, value None, ``d / 1000``, ``d * 1001``  -> leg 8
- ``_mutmut_93/_94/_98/_99/_100/_101``  L530 ``record_stage_latency`` stage
  None/XX/upper, value None, ``d / 1000``, ``d * 1001``  -> leg 9
- ``_mutmut_102``  L535 ``self._stats.errors += 1`` -> ``= 1``  (twin of m8)
  -> ``test_detector_unavailable_counts_per_call_and_warns`` (two calls -> 2)
- ``_mutmut_105``  L536 ``record_exception(e)`` -> ``record_exception(None)``;
  ``_mutmut_106``  L537 WARNING -> ``logger.warning(None)``
  -> same test (exception-IDENTITY pin + raw WARNING text)

Honest deviation from the manifest proof-sentence *"camera_id=None payload kills
the two camera_id-is-None flips via the log_context/spy kwargs"*: it is
UNREALIZABLE against the shipped schema.  ``DetectionQueuePayload.camera_id``
(backend/api/schemas/queue.py:53-59) is REQUIRED (``...``), ``min_length=1``,
pattern-locked - ``None``, ``""`` and an absent key ALL raise at L476, so no
payload can ever deliver a falsy camera id to L497/L501.
``test_no_falsy_camera_id_can_reach_the_instrumentation`` pins that shipped
fact by construction; m4 / m25 / m35 are killed by the real-value kwargs legs
(CAM is not ``None``), which is the by-construction route.

Every leg above is the MEASURED failing set of the in-tree mutant run (each
key built from its exact survivor diff in a symlinked copy of this tree,
battery run against it: 71/71 KILLED, and pristine 9/9 green serially and
co-run with the template g17 module).  Three keys have measured routes beyond
the header map: m5 additionally reddens the cancellation control (its DEBUG
text), m52 rides the same DEBUG in three tests, and m14 also trips the
no-falsy-camera pin's end-to-end reject call.

Discipline (batch28_17 pattern)
-------------------------------
* ``caplog`` windows opened per assert (``set_level`` + ``clear()``, filtered to
  this module's logger); RAW ``record.msg`` / ``record.args`` /
  ``record.exc_info`` reads only.
* ``time.time`` is never patched (campaign rule).  The shipped def re-imports
  ``time`` INSIDE its body (L470 ``import time``), which binds from
  ``sys.modules`` - so the fixed clock is a per-window swap of ``sys.modules``
  (via ``patch.dict``, an na form) for a delegating stand-in whose answers
  repeat: duration is a fixed 2.0 in every world no matter how many ticks a
  variant body burns.
* Mocks of real callables are autospec'd (WP4.2 fast path): every module-level
  callee of the shipped def is patched with ``autospec=True`` through
  ``patch_global``, whose target is the LIVE name-resolution dict of the
  function under test (``live_globals``) - the same dict the replay-world copy
  of the module executes in, so one helper is correct in every world.
* Worker collaborators are constructor-injected doubles (never patch sites); the
  tracer span, the DB session and the two media-dispatch arms are per-test
  stand-ins.  No import-time spy anywhere.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sys
import time as real_time
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from backend.api.schemas.queue import validate_detection_payload as REAL_VALIDATE
from backend.services import pipeline_workers as M
from backend.services.detector_client import DetectorUnavailableError

LOG_NAME = M.logger.name  # "backend.services.pipeline_workers" (get_logger(__name__))

pytestmark = [pytest.mark.unit]


# =============================================================================
# Shipped literals, transcribed from backend/services/pipeline_workers.py
# =============================================================================

# L483: record_pipeline_error("invalid_detection_payload")
INVALID_LABEL = "invalid_detection_payload"
# L485: f"SECURITY: Rejecting invalid detection queue payload: {e}"
SECURITY_MSG = "SECURITY: Rejecting invalid detection queue payload: {}"
# L487: "raw_item": str(item)[:500]  # Truncate to prevent log injection
RAW_ITEM_KEY = "raw_item"
RAW_ITEM_LIMIT = 500
# L488: "error": str(e)
ERROR_KEY = "error"
# L498: tracer.start_as_current_span("detection_processing")
SPAN_NAME = "detection_processing"
# L501: set_pipeline_context_attributes(span, camera_id=..., stage="detect")
STAGE_ATTR = "detect"
# L503-508: add_span_attributes(..., pipeline_stage="detection")
PIPELINE_STAGE_ATTR = "detection"
# L509: logger.debug(f"Processing detection item: {file_path}")
PROCESSING_DEBUG = "Processing detection item: {}"
# L528: record_pipeline_stage_latency("detect_to_batch", duration * 1000)
BATCH_LABEL = "detect_to_batch"
# L537: logger.warning(f"Detection unavailable, job sent to DLQ: {e}")
DLQ_WARNING = "Detection unavailable, job sent to DLQ: {}"
# L542: record_pipeline_error("detection_processing_error")
GENERIC_LABEL = "detection_processing_error"
# L545: f"Failed to process detection item: {e}"
GENERIC_ERROR_MSG = "Failed to process detection item: {}"


# =============================================================================
# Stimulus payloads (values chosen so every arg->None / drop mutant differs)
# =============================================================================

CAM = "cam-kitchen-01"
FILE = "/export/front-door/frame-0001.jpg"
TS = "2026-09-21T08:15:30.500000"
PST = "2026-09-21T08:15:29.250000"
VCAM = "cam-driveway-02"
VFILE = "/export/driveway/clip-7.mp4"
VPST = "2026-09-21T08:14:55.000000"


def image_item(**over: Any) -> dict[str, Any]:
    item = {
        "camera_id": CAM,
        "file_path": FILE,
        "timestamp": TS,
        "media_type": "image",
        "pipeline_start_time": PST,
    }
    item.update(over)
    return item


def video_item() -> dict[str, Any]:
    return {
        "camera_id": VCAM,
        "file_path": VFILE,
        "timestamp": TS,
        "media_type": "video",
        # Truthy on purpose: m59 flips this dispatch arg to None, so the pin
        # below only sees it if the payload's own value is not None.
        "pipeline_start_time": VPST,
    }


# =============================================================================
# Observation helpers (batch28_17 pattern)
# =============================================================================


def win(caplog: pytest.LogCaptureFixture) -> None:
    """Open a capture window: DEBUG for this module's logger, empty buffer."""
    caplog.set_level(logging.DEBUG, logger=LOG_NAME)
    caplog.clear()


def mine(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == LOG_NAME]


def at(caplog: pytest.LogCaptureFixture, level: int) -> list[logging.LogRecord]:
    return [r for r in mine(caplog) if r.levelno == level]


def pin_record(r: logging.LogRecord, *, msg: str, level: int) -> None:
    """Assert the observable surface of one shipped f-string log call."""
    assert r.msg == msg, f"log text mutated: {r.msg!r} != {msg!r}"
    assert r.levelno == level, f"log level mutated: {r.levelno} != {level}"
    assert tuple(r.args or ()) == (), f"unexpected lazy args for an f-string message: {r.args!r}"


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

    * Pristine repo / replay tree (the mutant module IS the imported module):
      ``fn.__globals__ is M.__dict__`` - identity fast path.
    * ep_plugin-style lane exec'ing a variant body into a snapshot COPY of the
      module dict: that copy is what the body reads, so it is returned and every
      ``patch_global`` binds inside it.
    * ``mutants/`` re-bank home: the mutmut trampoline's ``__globals__`` is
      mutmut's dict while the shipped body sits behind ``__wrapped__`` with
      globals == ``M.__dict__``; the identity guard fires only there.
    """
    g = fn.__globals__
    if g is not M.__dict__:
        w = getattr(fn, "__wrapped__", None)
        if w is not None and w.__globals__ is M.__dict__:
            return M.__dict__
    return g


class _DictOwner:
    """Attribute facade over a module-globals dict for ``patch.object``."""

    def __init__(self, d: dict[str, Any]) -> None:
        self._d = d

    def __getattr__(self, name: str) -> Any:
        try:
            return self._d[name]
        except KeyError as e:
            raise AttributeError(name) from e

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_d":
            super().__setattr__(name, value)
        else:
            self._d[name] = value

    def __delattr__(self, name: str) -> None:
        del self._d[name]


def patch_global(name: str, **kwargs: Any) -> Any:
    """``patch.object`` on the module the function under test resolves through."""
    g = live_globals(M.DetectionQueueWorker._process_detection_item)
    if g is M.__dict__:
        return patch.object(M, name, **kwargs)
    return patch.object(_DictOwner(g), name, create=True, **kwargs)


def calls_of(mock: Any) -> list[Any]:
    """The recorded call list of any mock shape (autospec or plain)."""
    return list(mock.call_args_list)


# =============================================================================
# Fixed clock - the shipped def re-imports time in its BODY (L470), and a
# function-local ``import time`` binds from sys.modules, so the stand-in is
# swapped there (patch.dict - an na form, never a time.time PATCH).
# =============================================================================

CLOCK_TICKS = (1000.0, 1002.0)  # shipped ticks: start, stamp, (repeats), end
DURATION = 2.0  # L525 shipped arithmetic: 1002.0 - 1000.0
DURATION_MS = 2000.0  # duration * 1000 (L528 / L530)
# m77's ``+`` on the fixed clock: 1002.0 + 1000.0 and * 1000 ->
M77_DURATION = 2002.0
M77_MS = M77_DURATION * 1000


class FakeTimeModule:
    """Drop-in for the ``time`` module whose ``time()`` answers run out, then repeat.

    Every other attribute delegates to the real module, so anything else that
    lazily ``import time`` inside the window (logging internals never do;
    asyncio binds at import time) keeps working unchanged.
    """

    def __init__(self, *answers: float) -> None:
        self._answers = answers
        self.calls = 0

    def time(self) -> float:
        i = self.calls
        self.calls += 1
        return self._answers[i] if i < len(self._answers) else self._answers[-1]

    def __getattr__(self, name: str) -> Any:
        return getattr(real_time, name)


@contextlib.contextmanager
def fixed_clock() -> Any:
    """Install the repeating fake clock for the duration of the window."""
    fake = FakeTimeModule(*CLOCK_TICKS)
    with patch.dict(sys.modules, {"time": fake}):
        yield fake


# =============================================================================
# Worker double-injection (constructor args, not patch sites)
# =============================================================================


def detection_worker() -> Any:
    """DetectionQueueWorker with every collaborator injected (no real clients).

    The two media-dispatch arms become instance-level AsyncMock spies: an
    instance attribute beats the class attribute in every world, so a replay
    mutant of ``_process_detection_item`` - which re-sources the shipped class
    and would sail past any class-level patch of the g07-owned
    ``_process_image_detection`` - still lands on the spy.
    """
    worker = M.DetectionQueueWorker(
        redis_client=MagicMock(name="redis-client"),
        detector_client=MagicMock(name="detector"),
        batch_aggregator=MagicMock(name="aggregator"),
        video_processor=MagicMock(name="video-processor"),
        retry_handler=MagicMock(name="retry-handler"),
        frame_buffer=MagicMock(name="frame-buffer"),
    )
    worker._process_video_detection = AsyncMock(name="video-arm")
    worker._process_image_detection = AsyncMock(name="image-arm")
    return worker


# =============================================================================
# Instrumentation stack
# =============================================================================


@dataclass
class Doppels:
    validate: Any
    log_context: Any
    tracer: Any
    span: Any
    set_ctx: Any
    add_attrs: Any
    observe: Any
    stage_latency: Any
    redis_latency: Any
    rec_error: Any
    rec_exc: Any
    get_session: Any


def _span_cm(span: Any) -> MagicMock:
    cm = MagicMock(name="span-cm")
    cm.__enter__ = MagicMock(return_value=span)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


def _session_cm() -> MagicMock:
    cm = MagicMock(name="session-cm")
    cm.__aenter__ = AsyncMock(return_value=MagicMock(name="db-session"))
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


@contextlib.contextmanager
def instrumentation() -> Any:
    """Patch every module-level callee of the shipped def in the LIVE world.

    ``autospec=True`` on every real callable target (WP4.2); ``tracer`` is an
    object swap (new_callable - an na form: the shipped value is a tracer
    instance, not a signature to enforce), and ``get_session`` is stood in by a
    per-test async context manager so no database engine is ever touched.
    """
    span = MagicMock(name="span")
    with contextlib.ExitStack() as stack:
        validate = stack.enter_context(patch_global("validate_detection_payload", autospec=True))
        log_ctx = stack.enter_context(patch_global("log_context", autospec=True))
        tracer = stack.enter_context(
            patch_global("tracer", new_callable=lambda: MagicMock(name="tracer"))
        )
        tracer.start_as_current_span.side_effect = lambda _name: _span_cm(span)
        set_ctx = stack.enter_context(
            patch_global("set_pipeline_context_attributes", autospec=True)
        )
        add_attrs = stack.enter_context(patch_global("add_span_attributes", autospec=True))
        observe = stack.enter_context(patch_global("observe_stage_duration", autospec=True))
        stage = stack.enter_context(patch_global("record_pipeline_stage_latency", autospec=True))
        redis_lat = stack.enter_context(patch_global("record_stage_latency", autospec=True))
        rec_err = stack.enter_context(patch_global("record_pipeline_error", autospec=True))
        rec_exc = stack.enter_context(patch_global("record_exception", autospec=True))
        get_sess = stack.enter_context(
            patch_global("get_session", autospec=True, side_effect=_session_cm)
        )
        yield Doppels(
            validate=validate,
            log_context=log_ctx,
            tracer=tracer,
            span=span,
            set_ctx=set_ctx,
            add_attrs=add_attrs,
            observe=observe,
            stage_latency=stage,
            redis_latency=redis_lat,
            rec_error=rec_err,
            rec_exc=rec_exc,
            get_session=get_sess,
        )


# =============================================================================
# 1) valid payloads - the full instrumentation contract (L476-530)
#    m4, m5, m25-m33, m35-m51, m52, m56-m65, m77, m78, m82-m91, m93-m101
# =============================================================================


async def test_valid_image_payload_drives_the_full_instrumentation_doppels(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:476-530, one happy-path call, every observation pinned.

    ::

        validated = validate_detection_payload(item)
        camera_id = validated.camera_id            # L477 (m4 -> None)
        file_path = validated.file_path            # L478 (m5 -> None)
        ...
        with (log_context(camera_id, file_path, media_type),   # L497
              tracer.start_as_current_span("detection_processing") as span):  # L498
            set_pipeline_context_attributes(span, camera_id=..., stage="detect")  # L501
            add_span_attributes(camera_id=..., file_path=..., media_type=...,
                                pipeline_stage="detection")                        # L503
            logger.debug(f"Processing detection item: {file_path}")                # L509
            ...                                    # image dispatch L517
            duration = time.time() - start_time                                    # L525
            observe_stage_duration("detect", duration)                             # L526
            record_pipeline_stage_latency("detect_to_batch", duration * 1000)      # L528
            await record_stage_latency(self._redis, "detect", duration * 1000)     # L530

    The fake clock answers (1000.0, 1002.0, 1002.0, ...) so ``duration`` is
    exactly ``2.0`` and every millisecond figure is exactly ``2000.0``; m77's
    ``+`` moves them to 2002.0 / 2002000.0 and the ``* 1001`` / ``/ 1000``
    twins move the ms figures off 2000.0.  Every string kwarg below is the
    payload's own value - the only way it becomes ``None`` or disappears is a
    mutated argument.
    """
    worker = detection_worker()
    item = image_item()
    with instrumentation() as d, fixed_clock():
        d.validate.return_value = M.DetectionQueuePayload(**item)
        win(caplog)
        assert await worker._process_detection_item(item) is None

    # -- the validator receives the RAW item positionally ----------------------
    assert len(d.validate.call_args_list) == 1, d.validate.call_args_list
    assert d.validate.call_args_list[0].args == (item,)
    assert not d.validate.call_args_list[0].kwargs

    # -- leg 1: log_context kwargs (m25-m30) -----------------------------------
    assert len(d.log_context.call_args_list) == 1, d.log_context.call_args_list
    lc = d.log_context.call_args_list[0]
    assert lc.args == (), f"log_context is keyword-only as shipped: {lc.args!r}"
    assert lc.kwargs == {"camera_id": CAM, "file_path": FILE, "media_type": "image"}, lc.kwargs

    # -- leg 2: span name (m31/m32/m33) ----------------------------------------
    assert calls_of(d.tracer.start_as_current_span) == [call(SPAN_NAME)], calls_of(
        d.tracer.start_as_current_span
    )

    # -- leg 3: pipeline context attributes (m35/m36/m38/m39/m40/m41) ---------
    assert len(d.set_ctx.call_args_list) == 1, d.set_ctx.call_args_list
    sc = d.set_ctx.call_args_list[0]
    assert sc.args == (d.span,), f"the span object is the positional arg: {sc.args!r}"
    assert sc.kwargs == {"camera_id": CAM, "stage": STAGE_ATTR}, sc.kwargs

    # -- leg 4: legacy span attributes (m42-m51) -------------------------------
    assert len(d.add_attrs.call_args_list) == 1, d.add_attrs.call_args_list
    aa = d.add_attrs.call_args_list[0]
    assert aa.args == (), f"add_span_attributes is keyword-only as shipped: {aa.args!r}"
    assert aa.kwargs == {
        "camera_id": CAM,
        "file_path": FILE,
        "media_type": "image",
        "pipeline_stage": PIPELINE_STAGE_ATTR,
    }, aa.kwargs

    # -- leg 5: the DEBUG names the file path (m52, plus m5) -------------------
    only(caplog, logging.DEBUG, PROCESSING_DEBUG.format(FILE))

    # -- leg 6: image dispatch args (m64/m65) ----------------------------------
    assert worker._process_image_detection.await_count == 1, (
        worker._process_image_detection.await_count
    )
    assert worker._process_video_detection.await_count == 0, (
        "media_type=image must not enter the video arm"
    )
    disp = worker._process_image_detection.await_args
    assert disp is not None
    assert len(disp.args) == 4 and not disp.kwargs, f"image dispatch shape: {disp!r}"
    assert disp.args[0] == CAM, f"camera_id arg mutated: {disp.args[0]!r}"
    assert disp.args[1] == FILE, f"file_path arg mutated: {disp.args[1]!r}"
    assert disp.args[2] is item, "the RAW item - not the validated model - is dispatched"
    assert disp.args[3] == PST, f"pipeline_start_time arg mutated: {disp.args[3]!r}"

    # -- success stats: the two statements between dispatch and timing ---------
    assert worker.stats.items_processed == 1, worker.stats
    assert worker.stats.errors == 0, worker.stats
    assert worker.stats.last_processed_at == CLOCK_TICKS[1], (
        f"L522 stamps the clock's second answer, got {worker.stats.last_processed_at!r}"
    )

    # -- leg 7: duration arithmetic + observe (m77/m78/m82/m83) ----------------
    assert calls_of(d.observe) == [call(STAGE_ATTR, DURATION)], calls_of(d.observe)

    # -- leg 8: in-memory ms tracker (m84/m85/m88/m89/m90/m91) -----------------
    assert calls_of(d.stage_latency) == [call(BATCH_LABEL, DURATION_MS)], calls_of(d.stage_latency)

    # -- leg 9: redis latency (m93/m94/m98/m99/m100/m101) ----------------------
    assert len(d.redis_latency.await_args_list) == 1, d.redis_latency.await_args_list
    rl = d.redis_latency.await_args_list[0]
    assert rl.args == (worker._redis, STAGE_ATTR, DURATION_MS), (
        f"record_stage_latency args mutated: {rl!r}"
    )
    assert not rl.kwargs

    # -- silence contract: nothing on the arms below may fire here -------------
    assert calls_of(d.rec_error) == [], f"success recorded errors: {calls_of(d.rec_error)}"
    assert calls_of(d.rec_exc) == [], f"success recorded exceptions: {calls_of(d.rec_exc)}"
    assert d.get_session.call_count == 0, "the item-level def opens no session itself"
    assert at(caplog, logging.INFO) == [], "the shipped happy path logs exactly one DEBUG"
    assert at(caplog, logging.WARNING) == []
    assert at(caplog, logging.ERROR) == []


async def test_video_media_type_dispatches_to_the_video_arm(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:512-515 - ``media_type == "video"`` routes to the video arm.

    All four positional dispatch args are pinned (m56-m59 arg->None; m60-m63
    drop_arg - a dropped positional shifts every later one), the image spy must
    stay cold, and the timing legs repeat here so the duration mutants own a
    second, differently-valued route.
    """
    worker = detection_worker()
    item = video_item()
    with instrumentation() as d, fixed_clock():
        d.validate.return_value = M.DetectionQueuePayload(**item)
        win(caplog)
        assert await worker._process_detection_item(item) is None

    assert worker._process_video_detection.await_count == 1, (
        worker._process_video_detection.await_count
    )
    assert worker._process_image_detection.await_count == 0, "video items must not reach the arm"
    disp = worker._process_video_detection.await_args
    assert disp is not None
    assert len(disp.args) == 4 and not disp.kwargs, f"video dispatch shape: {disp!r}"
    assert disp.args[0] == VCAM, f"camera_id arg mutated: {disp.args[0]!r}"
    assert disp.args[1] == VFILE, f"file_path arg mutated: {disp.args[1]!r}"
    assert disp.args[2] is item, "the RAW item is dispatched, not a validated copy"
    assert disp.args[3] == VPST, f"pipeline_start_time arg mutated: {disp.args[3]!r}"

    only(caplog, logging.DEBUG, PROCESSING_DEBUG.format(VFILE))
    assert worker.stats.items_processed == 1, worker.stats
    assert worker.stats.errors == 0, worker.stats
    assert calls_of(d.observe) == [call(STAGE_ATTR, DURATION)], calls_of(d.observe)
    assert calls_of(d.stage_latency) == [call(BATCH_LABEL, DURATION_MS)], calls_of(d.stage_latency)
    assert d.redis_latency.await_args_list[0].args == (
        worker._redis,
        STAGE_ATTR,
        DURATION_MS,
    ), d.redis_latency.await_args_list


async def test_no_falsy_camera_id_can_reach_the_instrumentation(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Honest realisation of the manifest's ``camera_id=None payload`` sentence.

    Shipped schema (backend/api/schemas/queue.py:53-59): ``camera_id`` is
    REQUIRED, ``min_length=1``, pattern ``^[a-zA-Z0-9_-]+$`` - so ``None``,
    ``""`` and an absent key are ALL rejected by ``validate_detection_payload``
    before a single instrumentation call opens.  A payload that reaches L497 /
    L501 therefore ALWAYS carries a truthy camera id, which makes the shipped
    ``camera_id=None`` forwarding produced by m4/m25/m35 observable only as a
    DIFFERENCE from the real value (pinned by the kwargs legs above), never as
    an input.  Both halves pinned here: falsy shapes reject with zero
    instrumentation, and the field really is required.
    """
    field = M.DetectionQueuePayload.model_fields["camera_id"]
    assert field.is_required(), "camera_id is a required field: no default exists"

    for shape in (None, ""):
        with pytest.raises(ValueError):
            REAL_VALIDATE(image_item(camera_id=shape))

    # And the reject happens BEFORE the worker's instrumentation opens.  The
    # spy here FORWARDS to the real validator (side_effect), so the def runs
    # end-to-end over the falsy payload and the raise is provably schema
    # behaviour, not a fabricated double.
    worker = detection_worker()
    with instrumentation() as d:
        d.validate.side_effect = REAL_VALIDATE
        win(caplog)
        assert await worker._process_detection_item(image_item(camera_id=None)) is None

    assert len(d.validate.call_args_list) == 1
    assert d.validate.call_args_list[0].args[0]["camera_id"] is None, (
        "the spy really saw the falsy shape"
    )
    assert d.log_context.call_args_list == [], "L497 never runs for a rejected payload"
    assert d.set_ctx.call_args_list == [], "L501 never runs for a rejected payload"
    assert d.add_attrs.call_args_list == []
    assert worker.stats.errors == 1, "the reject arm is the shipped outcome"
    recs = at(caplog, logging.ERROR)
    assert len(recs) == 1, [r.msg for r in recs]
    assert str(recs[0].msg).startswith("SECURITY: Rejecting invalid detection queue payload: "), (
        f"unexpected reject text: {recs[0].msg!r}"
    )
    assert at(caplog, logging.DEBUG) == []


# =============================================================================
# 2) invalid payload - the SECURITY reject arm (L481-491)
#    m8, m11-m13, m14, m15, m17, m18-m24
# =============================================================================


async def test_invalid_payload_rejects_on_message_text_and_truncated_raw_item(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:481-491 - the reject arm's ERROR surface, field for field.

    The raw item carries a 600-char ``file_path`` so the shipped
    ``str(item)[:500]`` truncation is observable: m21's ``[:501]`` lengthens the
    recorded text, m20's ``str(None)[:500]`` replaces it wholesale, and the
    XX/upper key twins (m18/m19/m22/m23) rename the ``extra`` fields the log
    contract promises.  The validator's message lands in ``extra["error"]``
    (m24 -> ``str(None) == "None"``) and in the interpolated message
    (m14 -> ``None``).  m15 (``extra=None``) and m17 (the ``extra`` keyword
    dropped outright) both leave the record with NO ``raw_item``/``error``
    attributes - the shared route for those two keys.
    """
    worker = detection_worker()
    long_path = "/export/" + "x" * 600
    bad = {"camera_id": CAM, "file_path": long_path}  # timestamp is REQUIRED
    reason = "1 validation error for DetectionQueuePayload"
    with instrumentation() as d:
        d.validate.side_effect = ValueError(reason)
        win(caplog)
        assert await worker._process_detection_item(bad) is None

    err = only(caplog, logging.ERROR, SECURITY_MSG.format(reason))
    assert getattr(err, RAW_ITEM_KEY, None) == str(bad)[:RAW_ITEM_LIMIT], (
        f"raw_item truncation mutated: len={len(getattr(err, RAW_ITEM_KEY, ''))}"
    )
    assert len(getattr(err, RAW_ITEM_KEY)) == RAW_ITEM_LIMIT, (
        "a 600+ char item must be cut to exactly 500 chars"
    )
    assert getattr(err, ERROR_KEY, None) == reason, (
        f"extra['error'] mutated: {getattr(err, ERROR_KEY, None)!r}"
    )
    assert err.exc_info is None, "the shipped SECURITY log passes no exc_info"
    # The reject arm returns before any instrumentation opens.
    assert d.log_context.call_args_list == []
    assert calls_of(d.tracer.start_as_current_span) == []
    assert calls_of(d.observe) == []
    assert at(caplog, logging.DEBUG) == []
    assert at(caplog, logging.WARNING) == []


async def test_invalid_payload_counts_one_error_per_call(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``self._stats.errors += 1`` on the reject arm (m8: ``= 1``).

    One reject leaves ``errors == 1`` under BOTH shapes - only the second
    reject separates ``+=`` from ``=``: shipped reaches 2, m8 re-stamps 1.
    """
    worker = detection_worker()
    with instrumentation() as d:
        d.validate.side_effect = ValueError("field required")
        win(caplog)
        await worker._process_detection_item(image_item())
        assert worker.stats.errors == 1, worker.stats
        await worker._process_detection_item(image_item())
        assert worker.stats.errors == 2, f"augmented assignment mutated: {worker.stats.errors}"

    assert len(at(caplog, logging.ERROR)) == 2
    assert calls_of(d.rec_exc) == []
    assert worker.stats.items_processed == 0, worker.stats


async def test_invalid_payload_labels_the_pipeline_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """L483 label pin (m11 None / m12 XX-wrap / m13 upper) + the early return.

    ``record_pipeline_error`` is called exactly once, positionally, with the
    shipped label - and this is the ONLY observable of that label, so the call
    list is pinned to a single ``call(label)``.
    """
    worker = detection_worker()
    with instrumentation() as d:
        d.validate.side_effect = ValueError("media_type invalid")
        win(caplog)
        assert await worker._process_detection_item(image_item(media_type="quantum")) is None

    assert calls_of(d.rec_error) == [call(INVALID_LABEL)], calls_of(d.rec_error)
    assert worker.stats.items_processed == 0, "the reject arm never counts a processed item"
    assert worker.stats.errors == 1, worker.stats


# =============================================================================
# 3) detector-unavailable arm (L532-538) - m102 (m8's twin), m105, m106
# =============================================================================


async def test_detector_unavailable_counts_per_call_and_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:532-537 - errors += 1, ``record_exception(e)``, WARNING text.

    Two calls pin the augmented assignment behind m102 (the same diff as m8 on
    the other arm - each arm needs its own leg), the exception IDENTITY kills
    m105 (``record_exception(None)``), and the raw WARNING text kills m106
    (``logger.warning(None)``).  The arm deliberately records NO pipeline
    error - the shipped comment says the retry handler already did.
    """
    worker = detection_worker()
    err = DetectorUnavailableError("detector at :8501 refused the health probe")
    worker._process_video_detection.side_effect = err
    item = video_item()
    with instrumentation() as d:
        d.validate.return_value = M.DetectionQueuePayload(**item)
        win(caplog)
        await worker._process_detection_item(item)
        assert worker.stats.errors == 1, worker.stats
        await worker._process_detection_item(item)
        assert worker.stats.errors == 2, f"m102 shape: {worker.stats.errors} != 2"

    warns = at(caplog, logging.WARNING)
    assert len(warns) == 2, f"one WARNING per DLQ call: {[(r.levelno, r.msg) for r in warns]}"
    for r in warns:
        pin_record(r, msg=DLQ_WARNING.format(err), level=logging.WARNING)
    exc_calls = calls_of(d.rec_exc)
    assert len(exc_calls) == 2, f"record_exception ran {len(exc_calls)} times: {exc_calls}"
    for c in exc_calls:
        assert c.args == (err,), f"record_exception arg mutated: {c.args!r}"
        assert not c.kwargs
    assert calls_of(d.rec_error) == [], "the DLQ arm must not record a generic pipeline error"
    assert at(caplog, logging.ERROR) == [], "the DLQ arm warns - it logs no ERROR"
    assert worker.stats.items_processed == 0, "a DLQ-bound item is not counted as processed"
    assert calls_of(d.observe) == [], "the timing block sits before the except arms"


# =============================================================================
# 4) generic exception arm (L540-547) - control legs (no survivor sits here)
# =============================================================================


async def test_generic_failure_counts_labels_records_and_logs_the_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:540-547 - stated so section 3's legs cannot be fall-throughs.

    A non-``DetectorUnavailableError`` keeps the generic contract: errors += 1,
    ``record_pipeline_error("detection_processing_error")``,
    ``record_exception(e)`` and an ERROR with ``exc_info=True`` carrying the
    interpolated text.
    """
    worker = detection_worker()
    err = RuntimeError("ffmpeg exploded on frame 3")
    worker._process_video_detection.side_effect = err
    item = video_item()
    with instrumentation() as d:
        d.validate.return_value = M.DetectionQueuePayload(**item)
        win(caplog)
        assert await worker._process_detection_item(item) is None

    assert worker.stats.errors == 1, worker.stats
    assert calls_of(d.rec_error) == [call(GENERIC_LABEL)], calls_of(d.rec_error)
    exc_calls = calls_of(d.rec_exc)
    assert [c.args[0] for c in exc_calls] == [err], exc_calls
    rec = only(caplog, logging.ERROR, GENERIC_ERROR_MSG.format(err))
    assert rec.exc_info is not None, "the shipped call passes exc_info=True"
    assert rec.exc_info[1] is err, f"exc_info must carry the raised exception: {rec.exc_info!r}"
    assert at(caplog, logging.WARNING) == []
    assert worker.stats.items_processed == 0, worker.stats


async def test_dispatch_cancellation_is_not_swallowed_by_the_arms(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """``asyncio.CancelledError`` reaches through both arms (L532/L540).

    Control leg - nothing is counted, recorded, or logged - so the ERROR-arm
    pins above cannot be satisfied by any-exception behaviour.
    """
    worker = detection_worker()
    worker._process_video_detection.side_effect = asyncio.CancelledError()
    item = video_item()
    with instrumentation() as d:
        d.validate.return_value = M.DetectionQueuePayload(**item)
        win(caplog)
        with pytest.raises(asyncio.CancelledError):
            await worker._process_detection_item(item)

    assert worker.stats.errors == 0, worker.stats
    assert calls_of(d.rec_error) == []
    assert calls_of(d.rec_exc) == []
    # The shipped DEBUG at L509 opens before the try block, so it is the ONLY
    # record: neither except arm logs, and no ERROR/WARNING appears.
    only(caplog, logging.DEBUG, PROCESSING_DEBUG.format(VFILE))
    assert at(caplog, logging.WARNING) == []
    assert at(caplog, logging.ERROR) == []
