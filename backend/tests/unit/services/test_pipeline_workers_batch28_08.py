"""S3 batch-28 lane 08 - ``pipeline_workers`` group g08 kill battery (64 keys; 1 eq upheld).

Module: ``backend/services/pipeline_workers.py`` (git blob 74649fd3 - the shipped
source this battery was read from and measured against).  Admitted manifest:
``/tmp/wp-pw/pipeline_workers/manifest.json`` group 8 (65 keys), ``group_8.keys`` and
``survivors.json`` for the exact per-key diffs.

Target: ``DetectionQueueWorker._process_video_detection`` (shipped L627-761).

Upheld EQUIVALENT - deliberately NOT tested (manifest ruling, re-checked here)
=============================================================================
``xǁDetectionQueueWorkerǁ_process_video_detection__mutmut_27``
L670 ``detector_failed = False`` -> ``= None``.  ``detector_failed`` is written three
times (L670 / L714 / L734) and read exactly once, at ``if detector_failed:`` (L747);
the value is never returned, logged or forwarded, and ``if None:`` is ``if False:``.
There is no observable to pin, so no leg is written - reading the local out of the
frame's locals would itself be unshipped behaviour.

Test -> mutant-key map
======================
Occurrence-twin check: every g08 diff ``(function, before, after, line)`` tuple was
searched across all 959 survivors - none occurs twice, so this group carries no twin
keys and no g08 key is claimed by another group.

- L649-652 banner ``logger.info(f"Processing video for detection: {video_path}",
  extra={"camera_id", "video_path"})``: ``m1`` msg -> ``None``, ``m2``
  ``extra=None``, ``m4`` extra DROPPED, ``m5``/``m6`` ``"camera_id"`` ->
  ``"XXcamera_idXX"``/``"CAMERA_ID"``, ``m7``/``m8`` ``"video_path"`` ->
  ``"XXvideo_pathXX"``/``"VIDEO_PATH"`` -> ``pin_banner``, called by EVERY leg (the
  banner is the def's first statement, so all six legs kill all seven keys).
- L656-660 ``extract_frames_for_detection_batch(video_path=..., interval_seconds=
  self._video_frame_interval, max_frames=self._video_max_frames)``: ``m10``/``m11``/
  ``m12`` the three kwargs -> ``None``, ``m14``/``m15`` ``interval_seconds``/
  ``max_frames`` DROPPED -> ``pin_extract_call`` (legs 1-5): the worker's own settings
  are set to the sentinels 7.5 / 9, so ``None`` and the shipped defaults 2.0 / 30 both
  fail the exact-kwargs pin.  ``m13`` (``video_path`` DROPPED) is measured on all six
  legs: the autospec'd signature makes the shipped call a TypeError that escapes the
  def (it sits BEFORE the ``try``), so leg 6's ``pytest.raises(OSError)`` gets a
  ``TypeError`` instead and fails too.
- L663-667 ``logger.warning(f"No frames extracted from video: {video_path}",
  extra={"camera_id", "video_path"})`` then ``return``: ``m17`` msg -> ``None``,
  ``m18`` ``extra=None``, ``m20`` extra DROPPED, ``m21``/``m22``/``m23``/``m24`` the
  two extra keys renamed -> SOLE route:
  ``test_an_empty_frame_list_warns_and_returns_before_the_metadata_query``.
- L669 ``total_detections = 0``: ``m25`` -> ``None``, ``m26`` -> ``1`` -> ``m25`` makes
  the shipped ``total_detections += len(detections)`` at L730 raise ``TypeError``
  inside the per-frame ``try``, so every frame warns and the summary interpolates
  ``None`` - caught by leg 1 (two INFOs / zero WARNINGs pinned), leg 4 (its empty
  WARNING surface) and leg 5 (its one-warning surface); ``m26`` reports one detection
  too many in both the summary text and the ``detection_count`` attribute, caught by
  leg 1 (3 -> 4) and leg 5 (1 -> 2) - the two legs use different counts so neither
  value is propped up by the other.
- L674 ``video_metadata = await self._video_processor.get_video_metadata(video_path)``:
  ``m29`` the whole statement -> ``video_metadata = None`` (the metadata call
  DISAPPEARS), ``m30`` the argument -> ``None`` -> ``m30`` dies on the awaited
  positional argument pinned in legs 1 and 4; ``m29`` dies there too (no await at all,
  and ``detect_objects(video_metadata=...)`` is pinned by IDENTITY so ``None`` cannot
  satisfy it) plus legs 5 and 6 - leg 6 arms the query with a side-effect error that
  then never happens, so its ``pytest.raises(OSError)`` fails.
- L681 ``current_frame = frame_path`` -> ``None`` (``m31``) -> legs 1, 4 and 5: the
  value is captured in the def-time default ``fp: str = current_frame`` (L683-685), so
  the shipped run's own ``detect_objects(image_path=...)`` says ``None`` for a frame
  whose path is a real string.
- L687-693 ``detect_objects(image_path=fp, camera_id=..., session=session,
  video_path=..., video_metadata=...)``: ``m32``-``m36`` the five kwargs -> ``None``,
  ``m37``-``m41`` the five DROPPED -> ``pin_detect_kwargs`` asserts the complete kwargs
  dict (``session`` and ``video_metadata`` by IDENTITY) in leg 1 (once per frame), leg
  4 (frame 1) and leg 5 (frame 2); the three dropped required kwargs are TypeErrors
  from the autospec'd signature, caught through the shipped body in all three legs.
- L696-700 ``with_retry(operation=_detect_frame, job_data=job_data,
  queue_name=self._queue_name)``: ``m44`` ``job_data=None``, ``m45``
  ``queue_name=None`` -> ``pin_with_retry_shape`` in legs 1, 3, 4 and 5, with
  ``job_data`` pinned by IDENTITY to the dict the leg passed and ``queue_name`` to the
  worker's own queue.
- L704-713 ``logger.warning(f"Detector unavailable during video processing:
  {video_path}", extra={camera_id, video_path, frame_path, attempts, moved_to_dlq})``:
  ``m50`` msg -> ``None``, ``m51`` ``extra=None``, ``m52`` msg DROPPED (leaves
  ``logger.warning(extra=...)`` - a keyword-only call that raises TypeError and lands
  in the shipped per-frame ``except``), ``m53`` extra DROPPED, and the ten renames
  ``m54``/``m55`` camera_id, ``m56``/``m57`` video_path, ``m58``/``m59`` frame_path,
  ``m60``/``m61`` attempts, ``m62``/``m63`` moved_to_dlq -> SOLE route (measured):
  ``test_a_retry_failure_on_the_first_frame_warns_breaks_and_raises`` (message pinned
  character-for-character + five RAW record attributes, every payload-specific;
  ``m52`` is the keyword-only ``logger.warning(extra=...)`` TypeError that the shipped
  per-frame ``except`` swallows, so the WARNING vanishes - caught by the same leg).
- L714 ``detector_failed = True``: ``m64`` -> ``None``, ``m65`` -> ``False`` -> SOLE
  leg 3 as measured: with the write degraded the shipped guard at L747 is falsy, so the
  ``DetectorUnavailableError`` the leg ``pytest.raises`` never happens and a summary
  INFO appears instead.  (L734 - the SECOND ``detector_failed = True`` - has no key in
  this group: its own mutants were already killed by the pre-existing suite, so leg 4
  below states that arm for completeness of the contract rather than for a key.)
- L717 ``detections = result.result or []``: ``m67`` the assignment -> ``None``,
  ``m68`` ``Or`` -> ``And`` (a truthy result collapses to ``[]``) -> legs 1, 4 and 5 -
  in every leg the detections actually aggregated before the leg's outcome are pinned,
  so a vanished or ``None``-ed detection list shows up as zero ``add_detection`` calls
  (and in leg 1 as two warnings plus ``0 detections``).
- L721-728 ``add_detection(camera_id, detection_id, _file_path=video_path,
  confidence, object_type, pipeline_start_time)``: ``m70`` ``detection_id=None``,
  ``m71`` ``_file_path=None``, ``m72`` ``confidence=None``, ``m73``
  ``object_type=None``, ``m74`` ``pipeline_start_time=None``, ``m75`` camera_id
  DROPPED, ``m76`` detection_id DROPPED, ``m77`` ``_file_path`` DROPPED, ``m78``
  ``confidence`` DROPPED -> leg 1 pins the complete kwargs dict once per detection, in
  order, across three detections with distinct ids/confidences/types; legs 4-5
  restate it, including the ``_file_path=video_path`` ruling ("Use video path, not
  frame", L724).

The two arms the manifest lists separately
------------------------------------------
``test_a_detector_unavailable_error_from_the_retry_path_breaks_the_loop_and_raises``
states the ``except DetectorUnavailableError`` arm (L732-735) - the only route to the
raise with no warning of its own - and is NOT a control: it is one of the three routes
of the shape/counting families above (measured 40 of the 64 keys).
``test_the_cleanup_runs_even_when_the_metadata_query_raises`` states the
``finally: cleanup_extracted_frames(video_path)`` arm (L743-745) on a body that raises
before the frame loop, so the cleanup pins in legs 1/3/4/5 describe the ``finally``
and not the happy path; measured, it reddens 9 keys (the metadata-query family and the
extraction-signature family) but no key SOLELY.

Discrepancy recorded (the SHIPPED code wins)
--------------------------------------------
The manifest's g08 test_spec says the empty-frame-list path returns "with cleanup
called".  Shipped L662-667 returns from BEFORE the ``try`` whose ``finally``
(L743-745) performs the cleanup, so on an empty frame list ``cleanup_extracted_frames``
is NOT called.  Leg 2 asserts the shipped truth.

Every leg above is the MEASURED failing set of the shadow-tree mutant run (each key
built from its exact survivor diff in a symlinked shadow of this tree and the battery
run against it), and the file is green serially against the pristine source.

Shipped behaviour only - nothing here invents a contract.  Every pinned string is
transcribed from the shipped file at the line quoted in the leg that asserts it, and
every value an assertion depends on is injected by this file (the frame list, the
detections, the RetryResult fields, the settings sentinels, the failures).

Discipline (batch28_17 pattern)
-------------------------------
* ``caplog`` windows opened per leg (``set_level`` + ``clear()``, filtered to this
  module's logger); RAW ``record.msg`` / ``record.args`` / ``record.exc_info`` and RAW
  record attributes for the shipped ``extra=`` payloads, plus the ordered COMPLETE log
  surface per level.
* Collaborators (video processor, detector, aggregator, retry handler, frame buffer,
  redis) are constructor-injected doubles built with
  ``create_autospec(<real class>).return_value`` - signature-enforced, so a DROPPED
  required kwarg raises inside the shipped body instead of silently defaulting, and
  none of them is a patch site at all.  The only name the shipped def resolves
  globally is ``get_session`` (the real DB seam), patched ``autospec=True`` through
  ``patch_global``, whose target is the LIVE name-resolution dict of the function under
  test (three-worlds safe).  ``time`` is never touched and no duration is asserted.
* The per-frame retry is a double, but a load-bearing one: its ``with_retry`` AWATES
  the ``operation`` the shipped body built (L683-693), so the shipped ``detect_objects``
  call, the shipped ``detections = result.result or []`` line, the shipped default
  capture at L681-685 and the shipped ``total_detections +=`` all execute inside the
  shipped run rather than being re-enacted here.
* No import-time spy; nothing leaks past the ``with`` blocks.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, create_autospec, patch

import pytest

from backend.core.redis import RedisClient
from backend.services import pipeline_workers as M
from backend.services.batch_aggregator import BatchAggregator
from backend.services.detector_client import DetectorClient, DetectorUnavailableError
from backend.services.frame_buffer import FrameBuffer
from backend.services.pipeline_workers import DetectionQueueWorker
from backend.services.retry_handler import RetryHandler, RetryResult
from backend.services.video_processor import VideoProcessor

LOG_NAME = M.logger.name

pytestmark = [pytest.mark.unit]


# =============================================================================
# Shipped literals (backend/services/pipeline_workers.py)
# =============================================================================

# L650: f"Processing video for detection: {video_path}"
BANNER_INFO = "Processing video for detection: {}"
# L664: f"No frames extracted from video: {video_path}"
NO_FRAMES_WARNING = "No frames extracted from video: {}"
# L705, and the identical text re-raised at L748-749
DETECTOR_DOWN_TEXT = "Detector unavailable during video processing: {}"
# L738: f"Failed to process frame {frame_path}: {e}"
FRAME_WARNING = "Failed to process frame {}: {}"
# L753-754: f"Processed video {video_path}: {total_detections} detections "
#          f"from {len(frame_paths)} frames"
FINAL_INFO_TPL = "Processed video {}: {} detections from {} frames"


CAM = "cam-driveway-07"
VIDEO = "/export/driveway/clip-2026-09-21-0742.mp4"
JOB = {"camera_id": CAM, "media_type": "video", "file_path": VIDEO, "marker": "batch28-g08"}
PST = "2026-09-21T07:42:11"
FRAMES = [
    "/export/driveway/clip-2026-09-21-0742/frame_0001.jpg",
    "/export/driveway/clip-2026-09-21-0742/frame_0002.jpg",
]
# The settings sentinels the manifest prescribes, distinct from every shipped default
# (interval_seconds=2.0 / max_frames=30) and from None.
VIDEO_INTERVAL = 7.5
VIDEO_MAX_FRAMES = 9


@dataclass(slots=True)
class DetectionLike:
    """The three attributes the shipped body reads off each detection (L723/725/726)."""

    id: int
    confidence: float
    object_type: str


D1 = DetectionLike(id=901, confidence=0.93, object_type="person")
D2 = DetectionLike(id=902, confidence=0.41, object_type="vehicle")
D3 = DetectionLike(id=903, confidence=0.77, object_type="dog")


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
    *,
    extras: dict[str, object] | None = None,
) -> logging.LogRecord:
    """Exactly one record at ``level`` in the window, matching every field."""
    recs = at(caplog, level)
    assert len(recs) == 1, (
        f"expected exactly 1 {logging.getLevelName(level)} record from {LOG_NAME}, "
        f"got {[(r.levelno, r.msg) for r in recs]}"
    )
    pin_record(recs[0], msg=msg, level=level)
    for key, expected in (extras or {}).items():
        assert getattr(recs[0], key, None) == expected, (
            f"log extra {key!r} mutated or lost: {getattr(recs[0], key, None)!r} != {expected!r}"
        )
    return recs[0]


def pin_levels(caplog: pytest.LogCaptureFixture, *, warnings: list[str], infos: list[str]) -> None:
    """The ordered, COMPLETE log surface of the window at each level."""
    assert [r.msg for r in at(caplog, logging.WARNING)] == warnings, (
        f"WARNING surface mutated: {[r.msg for r in at(caplog, logging.WARNING)]!r}"
    )
    assert [r.msg for r in at(caplog, logging.INFO)] == infos, (
        f"INFO surface mutated: {[r.msg for r in at(caplog, logging.INFO)]!r}"
    )


def pin_banner(caplog: pytest.LogCaptureFixture) -> None:
    """Shipped L649-652 - the def's first statement, so the FIRST INFO of every leg.

    The two RAW attributes are the only observable of the shipped ``extra=`` dict, so a
    renamed (m5-m8), ``None``-replaced (m2) or dropped (m4) key shows up as a
    missing/changed attribute, and a ``None`` message (m1) as a missing/changed banner
    text.  ``pin_levels`` then pins the COMPLETE ordered INFO surface, so a leg with two
    INFOs cannot hide an extra or a lost one.
    """
    recs = at(caplog, logging.INFO)
    assert len(recs) >= 1, f"the shipped banner is the def's first statement: {recs!r}"
    pin_record(recs[0], msg=BANNER_INFO.format(VIDEO), level=logging.INFO)
    for key, expected in (("camera_id", CAM), ("video_path", VIDEO)):
        assert getattr(recs[0], key, None) == expected, (
            f"banner log extra {key!r} mutated or lost: "
            f"{getattr(recs[0], key, None)!r} != {expected!r}"
        )


def pin_extract_call(vp: Any) -> None:
    """Shipped L656-660 - the batch-extraction call shape (m10-m15)."""
    assert vp.extract_frames_for_detection_batch.await_count == 1, (
        vp.extract_frames_for_detection_batch.await_count
    )
    c = vp.extract_frames_for_detection_batch.await_args
    assert c is not None
    assert c.args == (), f"the shipped call is keyword-only: {c.args!r}"
    assert c.kwargs == {
        "video_path": VIDEO,
        "interval_seconds": VIDEO_INTERVAL,
        "max_frames": VIDEO_MAX_FRAMES,
    }, f"frame-extraction kwargs mutated: {c.kwargs!r}"


def pin_with_retry_shape(retry: Any, worker: Any, calls: int) -> None:
    """Shipped L696-700 - keyword-only with exactly three kwargs (m44, m45)."""
    assert retry.with_retry.await_count == calls, retry.with_retry.await_count
    for c in retry.with_retry.await_args_list:
        assert c.args == (), f"the shipped call is keyword-only: {c.args!r}"
        assert set(c.kwargs) == {"operation", "job_data", "queue_name"}, c.kwargs
        assert c.kwargs["operation"].__name__ == "_detect_frame", c.kwargs["operation"].__name__
        assert c.kwargs["job_data"] is JOB, "the ORIGINAL job_data dict is forwarded for DLQ"
        assert c.kwargs["queue_name"] == worker._queue_name, (
            f"queue_name kwarg mutated: {c.kwargs['queue_name']!r}"
        )


def pin_detect_kwargs(seen: Any, frame: str) -> None:
    """Shipped L687-693 - the complete per-frame detection call shape (m32-m41)."""
    assert seen.args == (), f"the shipped call is keyword-only: {seen.args!r}"
    assert seen.kwargs == {
        "image_path": frame,
        "camera_id": CAM,
        "session": SESSION,
        "video_path": VIDEO,
        "video_metadata": METADATA,
    }, f"detect_objects kwargs mutated: {seen.kwargs!r}"
    assert seen.kwargs["session"] is SESSION, "the session IS the get_session() object"
    assert seen.kwargs["video_metadata"] is METADATA, (
        "the metadata object is forwarded unchanged (m29 makes it None)"
    )


def pin_add_call(seen: Any, det: DetectionLike) -> None:
    """Shipped L721-728 - the complete per-detection aggregation shape (m70-m78)."""
    assert seen.args == (), f"the shipped call is keyword-only: {seen.args!r}"
    assert seen.kwargs == {
        "camera_id": CAM,
        "detection_id": det.id,
        "_file_path": VIDEO,  # L724: "Use video path, not frame"
        "confidence": det.confidence,
        "object_type": det.object_type,
        "pipeline_start_time": PST,
    }, f"add_detection kwargs mutated: {seen.kwargs!r}"


def pin_final_info(caplog: pytest.LogCaptureFixture, count: int, frames: int) -> None:
    """Shipped L752-760 - the LAST INFO of the leg: text plus its four RAW attributes.

    The summary is the def's final statement, and the four attributes are the only
    observable of its ``extra=`` dict, so a renamed key or a ``None``-ed
    ``detection_count`` shows up here as a changed attribute while the interpolated
    ``total_detections`` (m25/m26/m67/m68) shows up in the text.  ``pin_levels`` pins
    that this really is the complete INFO surface.
    """
    recs = at(caplog, logging.INFO)
    assert len(recs) >= 2, (
        f"the summary INFO is the def's last statement, after the banner: {recs!r}"
    )
    r = recs[-1]
    pin_record(r, msg=FINAL_INFO_TPL.format(VIDEO, count, frames), level=logging.INFO)
    for key, expected in (
        ("camera_id", CAM),
        ("video_path", VIDEO),
        ("frame_count", frames),
        ("detection_count", count),
    ):
        assert getattr(r, key, None) == expected, (
            f"summary log extra {key!r} mutated or lost: {getattr(r, key, None)!r} != {expected!r}"
        )


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
    g = live_globals(M.DetectionQueueWorker._process_video_detection)
    if g is M.__dict__:
        return patch.object(M, name, **kwargs)
    return patch.object(_DictOwner(g), name, create=True, **kwargs)


# =============================================================================
# Worker + collaborator stand-ins
# =============================================================================

SESSION = MagicMock(name="db-session")
METADATA = {"width": 1920, "height": 1080, "fps": 25.0, "probe": "g08"}


def _session_cm() -> MagicMock:
    cm = MagicMock(name="session-cm")
    cm.__aenter__ = AsyncMock(return_value=SESSION)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def video_worker(*, frames: list[str], retry: Any) -> Any:
    """DetectionQueueWorker with autospec'd collaborator doubles injected.

    Every double is ``create_autospec(<real class>).return_value``, so the shipped
    calls are signature-checked and a dropped required kwarg is a TypeError inside the
    shipped body rather than a silent default.  The two video settings are then set to
    the sentinels, which makes ``interval_seconds=None`` / ``max_frames=None`` and the
    shipped defaults 2.0 / 30 all falsifiable at once.
    """
    vp = create_autospec(VideoProcessor).return_value
    vp.extract_frames_for_detection_batch.return_value = frames
    vp.get_video_metadata.return_value = METADATA
    worker = DetectionQueueWorker(
        redis_client=create_autospec(RedisClient).return_value,
        detector_client=create_autospec(DetectorClient).return_value,
        batch_aggregator=create_autospec(BatchAggregator).return_value,
        video_processor=vp,
        retry_handler=retry,
        frame_buffer=create_autospec(FrameBuffer).return_value,
    )
    worker._video_frame_interval = VIDEO_INTERVAL
    worker._video_max_frames = VIDEO_MAX_FRAMES
    return worker


def retry_double(behavior: Callable[[Callable[[], Awaitable[Any]]], Awaitable[RetryResult]]) -> Any:
    """autospec'd ``RetryHandler`` handing the shipped per-frame operation to ``behavior``.

    The shipped body hands ``with_retry`` the ``operation`` it just built (L697), and
    the double passes that operation to ``behavior``, which AWAITS it - so the shipped
    ``detect_objects`` call (L687-693), the shipped default capture at L681-685, the
    shipped ``detections = result.result or []`` (L717) and the shipped
    ``total_detections +=`` (L730) all execute inside the shipped run rather than being
    re-enacted here.  Each leg decides for itself whether the operation runs, exactly as
    a real handler decides: an exhausted or raising call does not run it, a successful
    one did - that choice is what distinguishes the ``success=False`` arm (L702-715)
    from the ``except DetectorUnavailableError`` arm (L732-735) and the generic
    ``except Exception`` arm (L736-741).
    """
    retry = create_autospec(RetryHandler).return_value

    async def with_retry(**kwargs: Any) -> RetryResult:
        return await behavior(kwargs["operation"])

    retry.with_retry.side_effect = with_retry
    return retry


def ok(detections: list[Any], attempts: int = 1) -> RetryResult:
    return RetryResult(
        success=True,
        result=detections,
        error=None,
        attempts=attempts,
        moved_to_dlq=False,
    )


def session_double() -> Any:
    """The only global the shipped def resolves: ``get_session`` (the DB seam)."""
    return patch_global("get_session", autospec=True, side_effect=_session_cm)


# =============================================================================
# 1) two success frames - every forwarded shape, every count
#    (41 keys measured: m1-m2, m4-m8, m10-m15, m25-m26, m29-m41, m44-m45,
#     m67-m68, m70-m78)
# =============================================================================


async def test_two_success_frames_forward_every_shape_and_count_every_detection(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:649-761 success path over two frames carrying three detections.

    ::

        frame_paths = await self._video_processor.extract_frames_for_detection_batch(
            video_path=video_path,
            interval_seconds=self._video_frame_interval,
            max_frames=self._video_max_frames,
        )
        ...
        video_metadata = await self._video_processor.get_video_metadata(video_path)
        async with get_session() as session:
            for frame_path in frame_paths:
                current_frame = frame_path

                async def _detect_frame(fp: str = current_frame) -> list[Any]: ...
                result = await self._retry_handler.with_retry(
                    operation=_detect_frame, job_data=job_data,
                    queue_name=self._queue_name)
                detections = result.result or []
                for detection in detections:
                    await self._aggregator.add_detection(
                        camera_id=camera_id, detection_id=detection.id,
                        _file_path=video_path, ...)
                total_detections += len(detections)
        finally:
            self._video_processor.cleanup_extracted_frames(video_path)
        logger.info(f"Processed video {video_path}: {total_detections} detections "
                    f"from {len(frame_paths)} frames", extra={...})

    Frame 1 carries two detections and frame 2 one, so the total 3 differs from every
    single-frame count, from both shipped defaults and from ``None``/``0``/``1`` - which
    is what makes ``total_detections = None`` (m25: the ``+=`` raises ``TypeError``
    inside this very ``try``, so BOTH frames warn and the summary says
    ``None detections``), ``= 1`` (m26: reports 4), ``detections = None`` (m67: the
    ``for`` iterates ``None`` -> two warnings, nothing aggregated, ``0 detections``) and
    ``result.result and []`` (m68: three real detections silently vanish) all
    observable.  ``session`` and ``video_metadata`` are pinned by IDENTITY and
    ``_file_path`` to the VIDEO - the shipped ruling at L724.
    """
    per_frame = [[D1, D2], [D3]]
    taken: list[list[Any]] = []

    async def behavior(op: Callable[[], Awaitable[Any]]) -> RetryResult:
        detections = per_frame[len(taken)]
        taken.append(detections)
        await op()  # the shipped closure, so the shipped detect_objects call happens
        return ok(detections, attempts=len(taken))

    retry = retry_double(behavior)
    worker = video_worker(frames=list(FRAMES), retry=retry)
    vp, detector, agg = worker._video_processor, worker._detector, worker._aggregator

    win(caplog)
    with session_double() as get_sess:
        assert await worker._process_video_detection(CAM, VIDEO, JOB, PST) is None

        # -- banner (m1-m8) and the extraction shape (m10-m15) -------------------
        pin_banner(caplog)
        pin_extract_call(vp)

        # -- L674: the metadata query, positional, forwarded by identity (m29/m30)
        assert vp.get_video_metadata.await_count == 1, vp.get_video_metadata.await_count
        meta = vp.get_video_metadata.await_args
        assert meta is not None
        assert meta.args == (VIDEO,) and not meta.kwargs, f"metadata argument mutated: {meta!r}"
        assert get_sess.call_count == 1, (
            f"exactly one session wraps the whole frame loop: {get_sess.call_count}"
        )

        # -- L696-700: with_retry shape (m44, m45), once per frame ---------------
        pin_with_retry_shape(retry, worker, 2)

        # -- L681-693: the per-frame detection call (m31-m41) --------------------
        assert detector.detect_objects.await_count == 2, detector.detect_objects.await_count
        for i, frame in enumerate(FRAMES):
            pin_detect_kwargs(detector.detect_objects.await_args_list[i], frame)

        # -- L717-730: three detections, counted; L743-745 finally --------------
        assert agg.add_detection.await_count == 3, agg.add_detection.await_count
        for i, det in enumerate([D1, D2, D3]):
            pin_add_call(agg.add_detection.await_args_list[i], det)
        assert vp.cleanup_extracted_frames.call_args_list == [call(VIDEO)], (
            f"cleanup must run exactly once with the video path: "
            f"{vp.cleanup_extracted_frames.call_args_list!r}"
        )
        pin_levels(
            caplog,
            warnings=[],
            infos=[BANNER_INFO.format(VIDEO), FINAL_INFO_TPL.format(VIDEO, 3, 2)],
        )
        pin_final_info(caplog, 3, 2)


# =============================================================================
# 2) the empty-frame-list arm (SOLE route to m17-m24)
# =============================================================================


async def test_an_empty_frame_list_warns_and_returns_before_the_metadata_query(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:662-667 - no frames -> WARNING + ``return``, and NOTHING else.

    ::

        if not frame_paths:
            logger.warning(
                f"No frames extracted from video: {video_path}",
                extra={"camera_id": camera_id, "video_path": video_path},
            )
            return

    The seven keys here live on that WARNING (message ``None``, ``extra=None``, extra
    dropped, four key renames).  The arm returns from BEFORE the ``try`` whose
    ``finally`` performs the cleanup, so the shipped truth is that
    ``cleanup_extracted_frames`` is NOT called - the manifest's test_spec says otherwise
    and the shipped code wins (recorded in this file's header).  The leg also pins
    everything the early return excludes: no metadata query, no session, no retry, no
    summary INFO.
    """

    async def never(op: Callable[[], Awaitable[Any]]) -> RetryResult:
        raise AssertionError("an empty frame list means the retry handler never runs")

    retry = retry_double(never)
    worker = video_worker(frames=[], retry=retry)
    vp, detector = worker._video_processor, worker._detector

    win(caplog)
    with session_double() as get_sess:
        assert await worker._process_video_detection(CAM, VIDEO, JOB, PST) is None

        pin_banner(caplog)
        pin_extract_call(vp)
        only(
            caplog,
            logging.WARNING,
            NO_FRAMES_WARNING.format(VIDEO),
            extras={"camera_id": CAM, "video_path": VIDEO},
        )
        assert vp.get_video_metadata.await_count == 0, "the empty-frame return precedes the query"
        assert detector.detect_objects.await_count == 0
        assert worker._aggregator.add_detection.await_count == 0
        assert retry.with_retry.await_count == 0
        assert get_sess.call_count == 0, "no session is opened without frames"
        assert vp.cleanup_extracted_frames.call_args_list == [], (
            "shipped returns before the try/finally, so no cleanup runs on this route"
        )

    pin_levels(
        caplog,
        warnings=[NO_FRAMES_WARNING.format(VIDEO)],
        infos=[BANNER_INFO.format(VIDEO)],
    )


# =============================================================================
# 3) the exhausted-retries arm (SOLE route to all 16 keys m50-m65)
# =============================================================================


async def test_a_retry_failure_on_the_first_frame_warns_breaks_and_raises(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:702-715 + 743-750 - the detector-down arm, then the raise.

    ::

        if not result.success:
            logger.warning(
                f"Detector unavailable during video processing: {video_path}",
                extra={"camera_id": camera_id, "video_path": video_path,
                       "frame_path": frame_path, "attempts": result.attempts,
                       "moved_to_dlq": result.moved_to_dlq},
            )
            detector_failed = True
            break
        ...
        finally:
            self._video_processor.cleanup_extracted_frames(video_path)
        if detector_failed:
            raise DetectorUnavailableError(
                f"Detector unavailable during video processing: {video_path}")

    The retry double reports ``success=False`` WITHOUT running the operation (what an
    exhausted handler does), so the failure lands on frame 1 and the ``break`` must
    leave frame 2 untouched.  All five extra payloads are distinct (attempts 3,
    moved_to_dlq True, the frame-1 path), so neither a ``None``-ed nor a dropped nor a
    renamed key can satisfy the attribute pins, and with ``detector_failed`` degraded to
    ``None``/``False`` (m64/m65) the guard at L747 is falsy: no raise at all, and a
    summary INFO instead.
    """
    failure = RetryResult(
        success=False,
        result=None,
        error="detector service unreachable",
        attempts=3,
        moved_to_dlq=True,
    )

    async def exhausted(op: Callable[[], Awaitable[Any]]) -> RetryResult:
        # An exhausted handler has stopped calling the operation - the assert below
        # that detect_objects never ran is what proves this leg stays that shape.
        return failure

    retry = retry_double(exhausted)
    worker = video_worker(frames=list(FRAMES), retry=retry)
    vp, detector = worker._video_processor, worker._detector

    win(caplog)
    with session_double():
        with pytest.raises(DetectorUnavailableError) as exc_info:
            await worker._process_video_detection(CAM, VIDEO, JOB, PST)

        assert str(exc_info.value) == DETECTOR_DOWN_TEXT.format(VIDEO), (
            f"raise message mutated: {str(exc_info.value)!r}"
        )

        pin_banner(caplog)
        pin_extract_call(vp)
        only(
            caplog,
            logging.WARNING,
            DETECTOR_DOWN_TEXT.format(VIDEO),
            extras={
                "camera_id": CAM,
                "video_path": VIDEO,
                "frame_path": FRAMES[0],
                "attempts": 3,
                "moved_to_dlq": True,
            },
        )
        pin_with_retry_shape(retry, worker, 1)
        assert detector.detect_objects.await_count == 0, "the exhausted retry never re-ran it"
        assert worker._aggregator.add_detection.await_count == 0, (
            "a failed frame adds nothing to the batch"
        )
        assert vp.cleanup_extracted_frames.call_args_list == [call(VIDEO)], (
            "the finally still cleans up on the detector-down route"
        )

    pin_levels(
        caplog,
        warnings=[DETECTOR_DOWN_TEXT.format(VIDEO)],
        infos=[BANNER_INFO.format(VIDEO)],
    )


# =============================================================================
# 4) the ``except DetectorUnavailableError`` arm (2nd/3rd route to the shape and
#    counting families: m29-m45, m67-m78 - 40 keys measured)
# =============================================================================


async def test_a_detector_unavailable_error_from_the_retry_path_breaks_the_loop_and_raises(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:681-735 + 743-750 - a frame that DOES detect, then the handler raises.

    ::

        except DetectorUnavailableError:
            # Retry handler already moved to DLQ
            detector_failed = True
            break

    Frame 1 succeeds with one real detection (so the full identity chain runs: the
    metadata object reaches ``detect_objects``, the session object reaches it, the
    frame path reaches it through the L681 default capture, and the detection reaches
    ``add_detection`` with the six shipped kwargs), and the retry call for frame 2 then
    raises ``DetectorUnavailableError`` - the arm the manifest lists separately and the
    only route to the raise with no warning of its own, so the WARNING surface of this
    leg is empty while exactly ONE retry call pair and ONE detection are pinned.  An
    arm that ignored the ``break`` (or the counting it skips) shows up against the
    pinned await counts / detection count / INFO surface.
    """
    state = {"calls": 0}

    async def handler_gives_up(op: Callable[[], Awaitable[Any]]) -> RetryResult:
        state["calls"] += 1
        if state["calls"] == 1:
            await op()  # frame 1 really detects - the full identity chain runs
            return ok([D3])
        raise DetectorUnavailableError("handler said detector down")  # frame 2

    retry = retry_double(handler_gives_up)
    worker = video_worker(frames=list(FRAMES), retry=retry)
    vp, detector, agg = worker._video_processor, worker._detector, worker._aggregator

    win(caplog)
    with session_double():
        with pytest.raises(DetectorUnavailableError) as exc_info:
            await worker._process_video_detection(CAM, VIDEO, JOB, PST)

        # The shipped raise at L748-749 REPLACES the handler's own text with the
        # video-scoped one - pinned so an escaping inner error cannot pass.
        assert str(exc_info.value) == DETECTOR_DOWN_TEXT.format(VIDEO), (
            f"raise message mutated: {str(exc_info.value)!r}"
        )
        pin_banner(caplog)
        pin_extract_call(vp)
        meta = vp.get_video_metadata.await_args
        assert meta is not None
        assert meta.args == (VIDEO,) and not meta.kwargs, f"metadata argument mutated: {meta!r}"
        assert detector.detect_objects.await_count == 1, (
            "the break follows the frame that raised, so frame 2 never detected"
        )
        pin_detect_kwargs(detector.detect_objects.await_args, FRAMES[0])
        pin_with_retry_shape(retry, worker, 2)
        assert agg.add_detection.await_count == 1, "frame 1's detection was aggregated first"
        pin_add_call(agg.add_detection.await_args, D3)
        assert vp.cleanup_extracted_frames.call_args_list == [call(VIDEO)]

    pin_levels(caplog, warnings=[], infos=[BANNER_INFO.format(VIDEO)])


# =============================================================================
# 5) the generic per-frame failure arm (second route to m25/m26 and the shapes)
# =============================================================================


async def test_a_generic_frame_failure_warns_and_continues_to_the_next_frame(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:681-741 - a per-frame ``Exception`` warns and CONTINUES.

    ::

        except Exception as e:
            logger.warning(
                f"Failed to process frame {frame_path}: {e}",
                extra={"camera_id": camera_id, "frame_path": frame_path},
            )
            continue

    Frame 1's retry raises ``ValueError`` before the operation runs, frame 2 succeeds
    with one detection, so the shipped run must warn once about frame 1 with the
    exception interpolated into the text, keep going, and report exactly
    ``1 detections from 2 frames`` - the count that makes ``total_detections = None``
    (m25: the ``+=`` raises inside this very ``try``, so BOTH frames warn and the
    summary interpolates ``None``) and ``= 1`` (m26: 2) observable on values leg 1 never
    uses.  Nothing raises, the cleanup still runs, and frame 2's detection and
    aggregation shapes are pinned again (including the ``_file_path=video_path``
    ruling).
    """
    err = ValueError("frame decode failed")
    state = {"calls": 0}

    async def decode_blip(op: Callable[[], Awaitable[Any]]) -> RetryResult:
        state["calls"] += 1
        if state["calls"] == 1:
            raise err  # the handler itself failed on frame 1 - no operation ran
        await op()
        return ok([D3])

    retry = retry_double(decode_blip)
    worker = video_worker(frames=list(FRAMES), retry=retry)
    vp, detector, agg = worker._video_processor, worker._detector, worker._aggregator

    win(caplog)
    with session_double():
        assert await worker._process_video_detection(CAM, VIDEO, JOB, PST) is None

        pin_banner(caplog)
        pin_extract_call(vp)
        only(
            caplog,
            logging.WARNING,
            FRAME_WARNING.format(FRAMES[0], err),
            extras={"camera_id": CAM, "frame_path": FRAMES[0]},
        )
        pin_with_retry_shape(retry, worker, 2)
        assert detector.detect_objects.await_count == 1, (
            "frame 1's retry raised before its operation ran, so only frame 2 detected"
        )
        pin_detect_kwargs(detector.detect_objects.await_args, FRAMES[1])

    assert agg.add_detection.await_count == 1, agg.add_detection.await_count
    pin_add_call(agg.add_detection.await_args, D3)
    assert vp.cleanup_extracted_frames.call_args_list == [call(VIDEO)]
    pin_levels(
        caplog,
        warnings=[FRAME_WARNING.format(FRAMES[0], err)],
        infos=[BANNER_INFO.format(VIDEO), FINAL_INFO_TPL.format(VIDEO, 1, 2)],
    )
    pin_final_info(caplog, 1, 2)


# =============================================================================
# 6) control: the ``finally`` cleanup on an unwinding body
# =============================================================================


async def test_the_cleanup_runs_even_when_the_metadata_query_raises(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Shipped:672-745 - the outer ``try`` has NO except, so a raised body still cleans up.

    The metadata query fails, the ``finally`` still runs
    ``cleanup_extracted_frames(video_path)``, and the original error then propagates
    untouched - ``exc_info.value is err``, so the shipped body neither catches nor wraps
    it.  Stated so the cleanup pins in legs 1/3/4/5 describe the ``finally`` rather than
    the happy path, and so leg 3's and leg 4's cleanup pins cannot be read as "cleanup
    runs when nothing went wrong".
    """
    err = OSError("ffprobe died")

    async def unused(op: Callable[[], Awaitable[Any]]) -> RetryResult:
        raise AssertionError("the metadata failure precedes the frame loop")

    retry = retry_double(unused)
    worker = video_worker(frames=list(FRAMES), retry=retry)
    vp = worker._video_processor
    vp.get_video_metadata.side_effect = err

    win(caplog)
    with session_double():
        with pytest.raises(OSError) as exc_info:
            await worker._process_video_detection(CAM, VIDEO, JOB, PST)

        assert exc_info.value is err, "the shipped body neither catches nor wraps it"
        assert vp.cleanup_extracted_frames.call_args_list == [call(VIDEO)], (
            "the finally must run on the raising route too"
        )
        assert retry.with_retry.await_count == 0, "the frame loop never started"
        pin_banner(caplog)

    pin_levels(caplog, warnings=[], infos=[BANNER_INFO.format(VIDEO)])
