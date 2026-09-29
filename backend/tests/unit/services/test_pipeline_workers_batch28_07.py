"""S3 batch-28 lane 07 - ``pipeline_workers`` group g07 kill battery (46 keys).

Module: ``backend/services/pipeline_workers.py`` (git blob 74649fd3 - byte-identical
to the manifest-proven source).  Admitted manifest: ``/tmp/wp-pw/pipeline_workers/``
``manifest.json`` group 7 (46 KILLABLE / 0 EQUIVALENT / 0 NEEDS_INVESTIGATION),
plus ``group_7.keys`` and ``survivors.json`` for the exact per-key diffs.

Target: ``DetectionQueueWorker._process_image_detection`` (L549-625).

Test -> mutant-key map
======================
Every key below is in ``group_7.keys``.

- ``xǁDetectionQueueWorkerǁ_process_image_detection__mutmut_1/2/3``  L572-575
  ``detect_objects(image_path=file_path, camera_id=camera_id, session=session)``
  kwargs -> ``None``; ``_mutmut_4/5/6`` the same three kwargs DROPPED
  -> ``test_success_forwards_the_exact_call_shapes`` leg 1 (the inner closure is
  invoked through the ``operation`` kwarg the retry spy captured, so the
  detector-spy kwargs dict is pinned to the exact shipped shape)
- ``_mutmut_10``  L579 ``queue_name=self._queue_name`` -> ``queue_name=None``
  -> same test, leg 2 (the with_retry kwargs pin)
- ``_mutmut_15``  L587 WARNING message -> ``None``; ``_mutmut_17`` message DROPPED
  (``logger.warning(extra={...})`` = keyword-only TypeError);
  ``_mutmut_16`` ``extra={...}`` -> ``extra=None``; ``_mutmut_18`` ``extra``
  DROPPED (leaves ``logger.warning(msg)`` -> no extras)
  -> ``test_dlq_failure_warns_records_and_raises``
- ``_mutmut_19/_20`` ``"camera_id"`` -> ``"XXcamera_idXX"``/``"CAMERA_ID"``;
  ``_mutmut_21/_22`` ``"file_path"``; ``_mutmut_23/_24`` ``"attempts"``;
  ``_mutmut_25/_26`` ``"moved_to_dlq"``; ``_mutmut_27/_28`` ``"error"``
  (all in the DLQ WARNING's ``extra``)  -> same test (five RAW record attributes)
- ``_mutmut_29/_30/_31``  L598 ``record_pipeline_error("detection_max_retries_exceeded")``
  -> ``None`` / ``"XX...XX"`` / all-upper  -> same test (exact call list)
- ``_mutmut_32``  L600 raise message -> ``None``  -> same test
  (``str(exc_info.value)`` == the shipped f-string)
- ``_mutmut_35/_36/_37/_38/_39``  L608 ``add_detection`` kwargs
  camera_id/detection_id/_file_path/confidence/object_type -> ``None``;
  ``_mutmut_41/_42/_43/_44/_45`` the same five kwargs DROPPED
  -> ``test_success_forwards_the_exact_call_shapes`` leg 3 (exact kwargs dict,
  asserted once per detection, in order)
- ``_mutmut_47``  L617 DEBUG message -> ``None``; ``_mutmut_48`` ``extra={...}``
  -> ``extra=None``; ``_mutmut_50`` ``extra`` DROPPED
  -> same test, leg 4 (raw ``record.msg`` + four record attributes)
- ``_mutmut_51/_52`` ``"camera_id"``; ``_mutmut_53/_54`` ``"detection_count"``;
  ``_mutmut_55/_56`` ``"items_processed"``; ``_mutmut_57/_58``
  ``"retry_attempts"`` renames  -> same leg (every value a NON-default number,
  so a missing attribute (``None``) can never satisfy the pin)

``test_empty_success_result_logs_the_zero_detections_debug`` is a SECOND,
independently-valued route for the nine keys ``m47/m48/m50/m51/m52/m53/m54/
m57/m58`` (its 0/1 numerics re-observe the success DEBUG) and states the empty
``result.result or []`` arm; ``test_the_operation_kwarg_is_the_session_wrapped_
detector_call`` kills nothing of its own and states the ``operation`` identity
(live closure: two calls, two sessions) so leg 1's single-call pins sit on a
fully described shape.

Discipline (batch28_17 pattern, verbatim)
-----------------------------------------
* ``caplog`` windows opened per assert (``set_level`` + ``clear()``, filtered to
  this module's logger); RAW ``record.msg`` / ``record.args`` / attribute reads.
* Collaborators (detector, aggregator, retry handler) are constructor-injected
  doubles - never patch sites.  The two module-level names the shipped def
  resolves globally (``get_session`` - real DB seam - and
  ``record_pipeline_error``) are patched ``autospec=True`` through
  ``patch_global``, whose target is the LIVE name-resolution dict of the
  function under test (three-worlds safe).  ``time`` is never touched.
* No import-time spy; nothing leaks past the ``with`` blocks.
"""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from backend.services import pipeline_workers as M
from backend.services.detector_client import DetectorUnavailableError
from backend.services.retry_handler import RetryResult

LOG_NAME = M.logger.name

pytestmark = [pytest.mark.unit]


# =============================================================================
# Shipped literals (backend/services/pipeline_workers.py)
# =============================================================================

# L588-589: f"Detection failed after {result.attempts} attempts for {file_path}, "
#          f"moved to DLQ: {result.moved_to_dlq}"
DLQ_WARN_MSG = "Detection failed after 3 attempts for {}, moved to DLQ: True"
# L591-595: the DLQ WARNING's five extra keys
DLQ_EXTRAS = ("camera_id", "file_path", "attempts", "moved_to_dlq", "error")
# L598: record_pipeline_error("detection_max_retries_exceeded")
MAX_RETRIES_LABEL = "detection_max_retries_exceeded"
# L600-601: f"Detection failed after {result.attempts} retries: {result.error}"
RAISE_TEXT = "Detection failed after 3 retries: detector down"
# L618: f"Processed {len(detections)} detections from image {file_path}"
PROCESSED_DEBUG = "Processed {} detections from image {}"
# L620-623: the success DEBUG's four extra keys
SUCCESS_EXTRAS = ("camera_id", "detection_count", "items_processed", "retry_attempts")


CAM = "cam-patio-03"
FILE = "/export/patio/still-4242.jpg"
JOB = {"camera_id": CAM, "file_path": FILE, "marker": "batch28-g07"}
PST = "2026-09-21T09:00:00"


@dataclass(slots=True)
class DetectionLike:
    """The three attributes the shipped body reads off each detection."""

    id: int
    confidence: float
    object_type: str


DETECTIONS = [
    DetectionLike(id=901, confidence=0.93, object_type="person"),
    DetectionLike(id=902, confidence=0.41, object_type="vehicle"),
]


# =============================================================================
# Observation helpers (batch28_17 pattern)
# =============================================================================


def win(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG, logger=LOG_NAME)
    caplog.clear()


def mine(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == LOG_NAME]


def at(caplog: pytest.LogCaptureFixture, level: int) -> list[logging.LogRecord]:
    return [r for r in mine(caplog) if r.levelno == level]


def pin_record(r: logging.LogRecord, *, msg: str, level: int) -> None:
    assert r.msg == msg, f"log text mutated: {r.msg!r} != {msg!r}"
    assert r.levelno == level, f"log level mutated: {r.levelno} != {level}"
    assert tuple(r.args or ()) == (), f"unexpected lazy args for an f-string message: {r.args!r}"
    assert r.exc_info is None, "exc_info present where the shipped call passes none"


def only(
    caplog: pytest.LogCaptureFixture,
    level: int,
    msg: str,
) -> logging.LogRecord:
    recs = at(caplog, level)
    assert len(recs) == 1, (
        f"expected exactly 1 {logging.getLevelName(level)} record from {LOG_NAME}, "
        f"got {[(r.levelno, r.msg) for r in recs]}"
    )
    pin_record(recs[0], msg=msg, level=level)
    return recs[0]


def live_globals(fn: Any) -> dict[str, Any]:
    """Name-resolution dict of the LIVE function object (three-worlds safe)."""
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
    g = live_globals(M.DetectionQueueWorker._process_image_detection)
    if g is M.__dict__:
        return patch.object(M, name, **kwargs)
    return patch.object(_DictOwner(g), name, create=True, **kwargs)


def calls_of(mock: Any) -> list[Any]:
    return list(mock.call_args_list)


# =============================================================================
# Worker + session stand-ins
# =============================================================================

SESSION = MagicMock(name="db-session")


def _session_cm() -> MagicMock:
    cm = MagicMock(name="session-cm")
    cm.__aenter__ = AsyncMock(return_value=SESSION)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def image_worker() -> Any:
    """DetectionQueueWorker whose detector/aggregator/retry doubles record calls."""
    detector = MagicMock(name="detector")
    detector.detect_objects = AsyncMock(name="detect_objects")
    aggregator = MagicMock(name="aggregator")
    aggregator.add_detection = AsyncMock(name="add_detection")
    retry = MagicMock(name="retry-handler")
    retry.with_retry = AsyncMock(name="with_retry")
    worker = M.DetectionQueueWorker(
        redis_client=MagicMock(name="redis-client"),
        detector_client=detector,
        batch_aggregator=aggregator,
        video_processor=MagicMock(name="video-processor"),
        retry_handler=retry,
        frame_buffer=MagicMock(name="frame-buffer"),
    )
    worker._detector = detector
    worker._aggregator = aggregator
    worker._retry_handler = retry
    return worker


@dataclass
class G:
    get_session: Any
    rec_error: Any


@contextlib.contextmanager
def global_double() -> Any:
    """autospec'd ``get_session`` (DB seam) + ``record_pipeline_error``."""
    with contextlib.ExitStack() as stack:
        get_sess = stack.enter_context(
            patch_global("get_session", autospec=True, side_effect=_session_cm)
        )
        rec_err = stack.enter_context(patch_global("record_pipeline_error", autospec=True))
        yield G(get_session=get_sess, rec_error=rec_err)


# =============================================================================
# 1) success path - the exact call shapes (L569-625)
#    m1-m6, m10, m35-m45, m47, m48, m50, m51-m58
# =============================================================================


async def test_success_forwards_the_exact_call_shapes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:569-625 success path, every forwarded shape pinned.

    ::

        async def _detect_with_session() -> list[Any]:
            async with get_session() as session:
                return await self._detector.detect_objects(
                    image_path=file_path, camera_id=camera_id, session=session)

        result = await self._retry_handler.with_retry(
            operation=_detect_with_session,
            job_data=job_data,
            queue_name=self._queue_name,
        )
        ...  # failure arm -> section 2
        detections = result.result or []
        for detection in detections:
            await self._aggregator.add_detection(
                camera_id=camera_id, detection_id=detection.id,
                _file_path=file_path, confidence=detection.confidence,
                object_type=detection.object_type,
                pipeline_start_time=pipeline_start_time)
        logger.debug(f"Processed {len(detections)} detections from image {file_path}",
                     extra={"camera_id": ..., "detection_count": len(detections),
                            "items_processed": self._stats.items_processed,
                            "retry_attempts": result.attempts})

    The retry handler is a double, so the inner closure is invoked BY THIS TEST
    through the captured ``operation`` kwarg - that is what makes the
    ``detect_objects`` kwargs observable.  Every numeric extra value
    (2 / 7 / 5) is distinct from the shipped default 0/None, so an ``extra``
    that was replaced by ``None`` or dropped (m48/m50) or renamed (m51-m58)
    fails the attribute pin instead of silently reading 0.
    """
    worker = image_worker()
    result = RetryResult(
        success=True, result=list(DETECTIONS), error=None, attempts=5, moved_to_dlq=False
    )
    worker._retry_handler.with_retry.return_value = result
    worker._detector.detect_objects.return_value = DETECTIONS  # the SAME list object
    worker._stats.items_processed = 7  # a chosen non-default for the extra pin

    win(caplog)
    with global_double() as gd:
        assert await worker._process_image_detection(CAM, FILE, JOB, PST) is None

        # -- leg 2: with_retry kwargs (m10) ------------------------------------
        assert len(worker._retry_handler.with_retry.await_args_list) == 1
        wr = worker._retry_handler.with_retry.await_args_list[0]
        assert wr.args == (), f"with_retry is keyword-only as shipped: {wr.args!r}"
        assert set(wr.kwargs) == {"operation", "job_data", "queue_name"}, wr.kwargs
        assert wr.kwargs["queue_name"] == worker._queue_name, (
            f"queue_name kwarg mutated: {wr.kwargs['queue_name']!r}"
        )
        assert wr.kwargs["job_data"] is JOB, "the ORIGINAL job_data dict is forwarded"

        # -- leg 1: detect_objects kwargs via the operation closure (m1-m6) ----
        # The retry handler is a double, so the shipped body never called the
        # closure; THIS test drives it while get_session is still patched.
        op = wr.kwargs["operation"]
        assert callable(op)
        assert await op() is DETECTIONS, "the closure returns the detector's detections"
        assert gd.get_session.call_count == 1, (
            f"get_session ran {gd.get_session.call_count} times, expected 1"
        )
        assert len(worker._detector.detect_objects.await_args_list) == 1
        det = worker._detector.detect_objects.await_args_list[0]
        assert det.args == (), f"detect_objects is keyword-only as shipped here: {det.args!r}"
        assert det.kwargs == {"image_path": FILE, "camera_id": CAM, "session": SESSION}, (
            f"detect_objects kwargs mutated: {det.kwargs!r}"
        )
        assert det.kwargs["session"] is SESSION, "the session IS the get_session() object"

    # -- leg 3: add_detection per detection (m35-m45) ---------------------------
    assert worker._aggregator.add_detection.await_count == 2, (
        worker._aggregator.add_detection.await_count
    )
    for i, det_obj in enumerate(DETECTIONS):
        a = worker._aggregator.add_detection.await_args_list[i]
        assert a.args == (), f"add_detection is keyword-only as shipped: {a.args!r}"
        assert a.kwargs == {
            "camera_id": CAM,
            "detection_id": det_obj.id,
            "_file_path": FILE,
            "confidence": det_obj.confidence,
            "object_type": det_obj.object_type,
            "pipeline_start_time": PST,
        }, f"detection {i} kwargs mutated: {a.kwargs!r}"

    # -- leg 4: the final DEBUG (m47, m48, m50, m51-m58) ------------------------
    rec = only(caplog, logging.DEBUG, PROCESSED_DEBUG.format(2, FILE))
    assert getattr(rec, "camera_id", None) == CAM
    assert getattr(rec, "detection_count", None) == 2, "extra['detection_count'] mutated/lost"
    assert getattr(rec, "items_processed", None) == 7, "extra['items_processed'] mutated/lost"
    assert getattr(rec, "retry_attempts", None) == 5, "extra['retry_attempts'] mutated/lost"

    # -- silence contract -------------------------------------------------------
    assert calls_of(gd.rec_error) == [], "a success path records no pipeline error"
    assert at(caplog, logging.WARNING) == []
    assert at(caplog, logging.ERROR) == []


async def test_empty_success_result_logs_the_zero_detections_debug(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:604 ``result.result or []`` -> the empty-detections DEBUG arm.

    ``result=None`` on a successful RetryResult still DEBUGs "Processed 0
    detections ..." and awaits ``add_detection`` zero times - the ordered
    contract behind leg 3/4 of the main test (and a second, independently
    valued route to the ``detection_count`` key renames).
    """
    worker = image_worker()
    worker._retry_handler.with_retry.return_value = RetryResult(
        success=True, result=None, error=None, attempts=1, moved_to_dlq=False
    )

    win(caplog)
    with global_double():
        assert await worker._process_image_detection(CAM, FILE, JOB) is None

    rec = only(caplog, logging.DEBUG, PROCESSED_DEBUG.format(0, FILE))
    assert getattr(rec, "detection_count", None) == 0
    assert getattr(rec, "retry_attempts", None) == 1
    assert getattr(rec, "camera_id", None) == CAM
    assert worker._aggregator.add_detection.await_count == 0, (
        "no detections means no add_detection calls"
    )


async def test_the_operation_kwarg_is_the_session_wrapped_detector_call() -> None:
    """Control leg for the ``operation`` identity (no survivor sits on m7-m9).

    The captured closure is named ``_detect_with_session`` and calling it twice
    opens TWO sessions / detector calls - it is a live closure, not a cached
    value - which is what makes leg 1's single-call pins meaningful.
    """
    worker = image_worker()
    worker._retry_handler.with_retry.return_value = RetryResult(
        success=True, result=[], error=None, attempts=1, moved_to_dlq=False
    )
    worker._detector.detect_objects.return_value = ["probe"]

    with global_double() as gd:
        await worker._process_image_detection(CAM, FILE, JOB)
        # The body ITSELF never opens a session - only the closure does, and the
        # retry double never ran it:
        assert gd.get_session.call_count == 0, gd.get_session.call_count
        op = worker._retry_handler.with_retry.await_args.kwargs["operation"]
        assert op.__name__ == "_detect_with_session", op.__name__
        assert await op() == ["probe"]
        assert gd.get_session.call_count == 1, gd.get_session.call_count
        assert await op() == ["probe"], "the closure is live: the second call re-runs it"
        assert gd.get_session.call_count == 2, gd.get_session.call_count

    assert worker._detector.detect_objects.await_count == 2


# =============================================================================
# 2) exhausted-retries arm (L585-602) - m15-m32
# =============================================================================


async def test_dlq_failure_warns_records_and_raises(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:585-602 - WARNING surface, label, and the re-raise text.

    ::

        if not result.success:
            logger.warning(
                f"Detection failed after {result.attempts} attempts for {file_path}, "
                f"moved to DLQ: {result.moved_to_dlq}",
                extra={"camera_id": ..., "file_path": ..., "attempts": ...,
                       "moved_to_dlq": ..., "error": ...},
            )
            record_pipeline_error("detection_max_retries_exceeded")
            raise DetectorUnavailableError(
                f"Detection failed after {result.attempts} retries: {result.error}"
            )

    ``attempts=3`` / ``moved_to_dlq=True`` / ``error="detector down"`` make all
    five extra values payload-specific; the raise text is pinned character for
    character so m32's ``DetectorUnavailableError(None)`` ("None") cannot pass.
    """
    worker = image_worker()
    worker._retry_handler.with_retry.return_value = RetryResult(
        success=False,
        result=None,
        error="detector down",
        attempts=3,
        moved_to_dlq=True,
    )

    win(caplog)
    with global_double() as gd, pytest.raises(DetectorUnavailableError) as exc_info:
        await worker._process_image_detection(CAM, FILE, JOB, PST)

    assert str(exc_info.value) == RAISE_TEXT, f"raise message mutated: {str(exc_info.value)!r}"
    assert exc_info.value.args[0] == RAISE_TEXT, exc_info.value.args

    rec = only(caplog, logging.WARNING, DLQ_WARN_MSG.format(FILE))
    for key, expected in zip(
        DLQ_EXTRAS,
        (CAM, FILE, 3, True, "detector down"),
        strict=True,
    ):
        assert getattr(rec, key, None) == expected, (
            f"extra[{key!r}] mutated or lost: {getattr(rec, key, None)!r} != {expected!r}"
        )
    assert rec.exc_info is None

    assert calls_of(gd.rec_error) == [call(MAX_RETRIES_LABEL)], calls_of(gd.rec_error)
    assert worker._aggregator.add_detection.await_count == 0, "the DLQ arm never batches detections"
    assert at(caplog, logging.DEBUG) == [], "the DLQ arm logs no success DEBUG"
    assert at(caplog, logging.ERROR) == [], "the DLQ arm does not log an ERROR itself"
