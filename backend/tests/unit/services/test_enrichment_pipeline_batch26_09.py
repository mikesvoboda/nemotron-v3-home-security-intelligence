"""Batch 26 part 09 — mutation kill battery for EnrichmentPipeline.enrich_batch.

Chunk-09 owns 120 mutmut survivors, ALL inside
`EnrichmentPipeline.enrich_batch` (backend/services/enrichment_pipeline.py,
shipped lines 5555-5735): the NEM-5570 cascade debug logging, the NEM-4234 hard
pipeline timeout, the quality-change tracking block, the motion-blur block, the
processing_time_ms arithmetic, the NEM-3797 `enrichment_pipeline.complete` span
event (its name + all 20 attributes) and the trailing `Enrichment complete: ...`
log line.

Rule 1 compliance: every assertion below was PROBED against pristine shipped
source first (probes/c09/probe1.py + probe2.py) — including shipped quirks such as
"the timeout path consumes a third monotonic read, so a timed-out run reports
processing_time_ms of 10000.0 under the deterministic clock" and "the first-frame
path still stores result.image_quality under camera_id".

Seams, all patched at the IMPORT site (backend.services.enrichment_pipeline.X) by
a MODULE-scoped autouse fixture so the patch is in place before any mutant is
bound over the live module dict, and reset per run inside `enrich()`:
  add_span_event, record_cascade_skipped, record_cascade_processed,
  record_enrichment_pipeline_timeout, detect_quality_change,
  interpret_blur_with_motion, logger, time.monotonic.

`logger` is a hand-written double that mirrors the shipped logging.Logger arity
(`msg` is a REQUIRED positional), so a mutant that drops the message (mutmut_40)
or a required lazy-format positional (mutmut_41/42) is caught, and the recorded
(level, args, kwargs) tuple pins the lazy-%-format contract exactly.

Determinism: `time.monotonic` is replaced by a clock that advances a fixed 5.0 s
ONLY for calls made from inside the module under test (frame-global check); the
event loop, asyncio and this file keep the real monotonic clock. A plain run
therefore yields exactly two module reads -> processing_time_ms == 5000.0 exactly;
a timed-out run yields three -> elapsed 5000 ms, final 10000.0 ms. Measured.

No sleeps > 0.1s, no network, no DB, no real models, class-free plain functions.
"""

from __future__ import annotations

import asyncio
import inspect
import sys
import time
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

import pytest

import backend.services.enrichment_pipeline as M

EP = "backend.services.enrichment_pipeline."
IMG = M.Image.new("RGB", (8, 8), "gray")
_REAL_MONOTONIC = time.monotonic
STEP = 5.0
CAMERA = "cam-1"


# --------------------------------------------------------------------------- doubles
def det(det_id=1, cls="person", conf=0.9):
    """DetectionInput stand-in: enrich_batch only reads id/class_name/confidence."""
    d = MagicMock(name="DetectionInput")
    d.id, d.class_name, d.confidence = det_id, cls, conf
    return d


class Clock:
    """time.monotonic() replacement: deterministic inside the module under test."""

    def __init__(self, step: float = STEP, start: float = 1000.0):
        self.step = step
        self.start = start
        self.t = start
        self.module_values: list[float] = []

    def reset(self):
        self.t = self.start
        self.module_values = []

    def __call__(self):
        caller = sys._getframe(1).f_globals.get("__name__")
        if caller == M.__name__:
            self.module_values.append(self.t)
            self.t += self.step
            return self.module_values[-1]
        return _REAL_MONOTONIC()


class LoggerDouble:
    """Records (level, args, kwargs) with the shipped logging.Logger arity enforced.

    `msg` is a required positional on every level method (mirroring
    logging.Logger.debug/info/warning(msg, *args, **kwargs)), so a mutant that
    drops it raises TypeError exactly as the real API would.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []

    def _rec(self, level, *args, **kwargs):
        self.calls.append((level, args, kwargs))

    def debug(self, msg, *args, **kwargs):
        self._rec("debug", msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self._rec("info", msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self._rec("warning", msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self._rec("error", msg, *args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        self._rec("exception", msg, *args, **kwargs)

    def log(self, level, msg, *args, **kwargs):
        self._rec(f"log{level}", msg, *args, **kwargs)

    # --- read helpers ------------------------------------------------------
    def at(self, level: str):
        return [c for c in self.calls if c[0] == level]

    def messages(self, level: str) -> list:
        return [c[1][0] for c in self.at(level)]

    def flat(self, level: str) -> str:
        """Rendered text of every call at `level` (what logging would have emitted)."""
        out = []
        for _lvl, args, _kw in self.at(level):
            msg, rest = args[0], args[1:]
            out.append(str(msg) % rest if rest else str(msg))
        return "\n".join(out)


# module-persistent seam doubles (patched BEFORE any mutant is bound over M.__dict__)
_SEAM = {
    "add_span_event": create_autospec(M.add_span_event),
    "record_cascade_skipped": create_autospec(M.record_cascade_skipped),
    "record_cascade_processed": create_autospec(M.record_cascade_processed),
    "record_enrichment_pipeline_timeout": create_autospec(M.record_enrichment_pipeline_timeout),
    "detect_quality_change": create_autospec(M.detect_quality_change),
    "interpret_blur_with_motion": create_autospec(M.interpret_blur_with_motion),
    "logger": LoggerDouble(),
    "clock": Clock(),
}


@pytest.fixture(scope="module", autouse=True)
def _seams():
    """Patch every collaborator enrich_batch uses, at the import site, for the module."""
    with (
        patch(EP + "add_span_event", new=_SEAM["add_span_event"]),
        patch(EP + "record_cascade_skipped", new=_SEAM["record_cascade_skipped"]),
        patch(EP + "record_cascade_processed", new=_SEAM["record_cascade_processed"]),
        patch(
            EP + "record_enrichment_pipeline_timeout",
            new=_SEAM["record_enrichment_pipeline_timeout"],
        ),
        patch(EP + "detect_quality_change", new=_SEAM["detect_quality_change"]),
        patch(EP + "interpret_blur_with_motion", new=_SEAM["interpret_blur_with_motion"]),
        patch(EP + "logger", new=_SEAM["logger"]),
        patch.object(time, "monotonic", _SEAM["clock"]),
    ):
        yield


# ------------------------------------------------------- shipped-value population
def quality(score=50.0, blurry=False):
    return M.ImageQualityResult(
        quality_score=score,
        brisque_score=40.0,
        is_blurry=blurry,
        is_noisy=False,
        is_low_quality=False,
        quality_issues=[],
    )


def populated(res):
    """Every field the completion log + complete span event reads -> truthy, countable."""
    res.license_plates = [M.LicensePlateResult(bbox=M.BoundingBox(1, 2, 3, 4), text="ABC123")]
    res.faces = [M.FaceResult(bbox=M.BoundingBox(1, 2, 3, 4))]
    res.image_quality = quality()
    res.vision_extraction = {"attrs": 1}
    res.person_reid_matches = {"1": ["match"]}
    res.scene_change = M.SceneChangeResult(change_detected=True, similarity_score=0.4)
    res.clothing_classifications = {"1": "cls"}
    res.clothing_segmentation = {"1": "seg"}
    res.vehicle_damage = {"1": "dmg"}
    res.vehicle_classifications = {"1": "vcls"}
    res.pet_classifications = {"1": "pcls"}
    res.depth_analysis = {"depth": 1}
    res.pose_results = {"1": "pose", "2": "pose"}
    res.action_results = {"a": 1}
    res.person_household_matches = {1: "hm"}
    res.vehicle_household_matches = {2: "hm"}
    res.clip_scene_classification = {"kitchen": 0.9}
    res.clip_threat_matches = {"threat": 0.5}
    res.clip_anomaly_score = 0.7
    return res


def blank(res):
    """Leave every result field at its shipped default (None / empty container)."""
    return res


def blurry_populated(res):
    populated(res)
    res.image_quality = quality(blurry=True)
    return res


class Obs:
    """Immutable snapshot of one enrich_batch() run (later runs cannot mutate it)."""

    def __init__(self):
        self.result = None
        self.store = None
        self.log_calls: list = []
        self.span_calls: list = []
        self.dqc_calls: list = []
        self.ibm_calls: list = []
        self.skipped_n = 0
        self.processed_n = 0
        self.timeout_n = 0
        self.parallel_n = 0
        self.parallel_kwargs: dict = {}
        self.clock_values: list = []

    # --- logger helpers ----------------------------------------------------
    def at(self, level):
        return [c for c in self.log_calls if c[0] == level]

    def messages(self, level):
        return [c[1][0] for c in self.at(level)]

    def flat(self, level):
        out = []
        for _lvl, args, _kw in self.at(level):
            msg, rest = args[0], args[1:]
            out.append(str(msg) % rest if rest else str(msg))
        return "\n".join(out)

    # --- span helpers ------------------------------------------------------
    def event_names(self):
        return [c.args[0] for c in self.span_calls]

    def attrs(self, name="enrichment_pipeline.complete"):
        """The attributes dict passed for span event `name` (None if never passed)."""
        for c in self.span_calls:
            if c.args and c.args[0] == name:
                return c.args[1] if len(c.args) > 1 else None
        return None


# ------------------------------------------------------------------ the seam runner
def enrich(
    *,
    dets=None,
    images=None,
    camera=CAMERA,
    min_confidence=0.5,
    timeout=30.0,
    populate=populated,
    seed_previous=None,
    dqc_return=(False, "Quality stable"),
    blur_context="MOTION-CONTEXT",
    parallel_body=None,
    step=STEP,
):
    """Drive enrich_batch() with every collaborator patched. Returns a snapshot Obs.

    All doubles are module-persistent (so a mutant rebound over the live module dict
    observes them too) and are reset here, so each call is independent; everything a
    test needs is snapshotted into the returned Obs.
    """
    for key in (
        "add_span_event",
        "record_cascade_skipped",
        "record_cascade_processed",
        "record_enrichment_pipeline_timeout",
        "detect_quality_change",
        "interpret_blur_with_motion",
    ):
        _SEAM[key].reset_mock()
    _SEAM["logger"].calls.clear()
    _SEAM["clock"].step = step
    _SEAM["clock"].reset()
    _SEAM["detect_quality_change"].return_value = dqc_return
    _SEAM["interpret_blur_with_motion"].return_value = blur_context

    p = M.EnrichmentPipeline.__new__(M.EnrichmentPipeline)
    p.min_confidence = min_confidence
    p._pipeline_timeout = timeout
    p._previous_quality_results = {}
    p.image_quality_enabled = True
    p.low_light_enhancement_enabled = False
    p.license_plate_enabled = True
    p.face_detection_enabled = True
    p.vision_extraction_enabled = True
    p._load_image = AsyncMock(return_value=IMG)
    p._maybe_enhance_low_light = AsyncMock(return_value=IMG)
    if seed_previous is not None:
        p._previous_quality_results[camera] = seed_previous

    def _default_body(res):
        populate(res)
        return None

    body = parallel_body or _default_body

    async def _parallel(*, result, pil_image, high_conf_detections, images, camera_id):
        out = body(result)
        if inspect.isawaitable(out):
            await out

    p._run_parallel_enrichment = AsyncMock(side_effect=_parallel)

    dets = [det(1, "person", 0.9)] if dets is None else dets
    images = {None: IMG} if images is None else images

    obs = Obs()
    obs.store = p._previous_quality_results
    result = asyncio.run(p.enrich_batch(detections=dets, images=images, camera_id=camera))
    obs.result = result
    obs.log_calls = list(_SEAM["logger"].calls)
    obs.span_calls = list(_SEAM["add_span_event"].call_args_list)
    obs.dqc_calls = list(_SEAM["detect_quality_change"].call_args_list)
    obs.ibm_calls = list(_SEAM["interpret_blur_with_motion"].call_args_list)
    obs.skipped_n = _SEAM["record_cascade_skipped"].call_count
    obs.processed_n = _SEAM["record_cascade_processed"].call_count
    obs.timeout_n = _SEAM["record_enrichment_pipeline_timeout"].call_count
    obs.parallel_n = p._run_parallel_enrichment.call_count
    if p._run_parallel_enrichment.call_args is not None:
        obs.parallel_kwargs = dict(p._run_parallel_enrichment.call_args.kwargs)
    obs.clock_values = list(_SEAM["clock"].module_values)
    return obs


# ============================================================ cascade / early exits
def test_cascade_no_detections_message():
    """Shipped: empty detections -> record_cascade_skipped + that exact debug line."""
    obs = enrich(dets=[], populate=blank)
    assert obs.skipped_n == 1
    assert obs.processed_n == 0
    assert obs.flat("debug") == "Cascade: no detections, skipping all enrichment"
    assert obs.parallel_n == 0
    assert obs.result.processing_time_ms == 0.0
    assert obs.result.errors == []


def test_cascade_debug_message_and_args():
    """Shipped: all-below-threshold -> debug("Cascade: %d ...%.2f...", len(detections), min_conf)."""
    obs = enrich(dets=[det(1, "car", 0.2), det(2, "car", 0.4)], min_confidence=0.75, populate=blank)
    assert obs.skipped_n == 1
    assert obs.processed_n == 0
    assert obs.parallel_n == 0
    assert obs.result.quality_change_detected is False
    assert obs.result.processing_time_ms == 0.0
    calls = obs.at("debug")
    assert len(calls) == 1, obs.log_calls
    args = calls[0][1]
    assert args[0] == "Cascade: %d detections all below min_confidence=%.2f, skipping enrichment"
    assert args[1:] == (2, 0.75)
    assert obs.flat("debug") == (
        "Cascade: 2 detections all below min_confidence=0.75, skipping enrichment"
    )


def test_start_span_event():
    """Shipped: enrichment_pipeline.start carries the 5 count/flag attributes."""
    obs = enrich(populate=blank)
    first = obs.span_calls[0]
    assert first.args[0] == "enrichment_pipeline.start"
    assert first.args[1] == {
        "detection.count": 1,
        "camera.id": CAMERA,
        "license_plate.enabled": True,
        "face_detection.enabled": True,
        "vision_extraction.enabled": True,
    }


# ================================================================= hard timeout (46)
async def _sleepy(result):
    await asyncio.sleep(0.02)
    populated(result)


def test_hard_timeout_fires_and_records():
    """Shipped: asyncio.timeout(self._pipeline_timeout) -> partial result + error + metric."""
    obs = enrich(timeout=0, parallel_body=_sleepy, populate=blank)
    assert obs.timeout_n == 1
    assert obs.result.errors == ["pipeline_timeout: exceeded 0s hard limit"]
    assert obs.result.license_plates == []  # partial: enrichment never finished
    warn = obs.at("warning")
    assert len(warn) == 1, obs.log_calls
    args, kwargs = warn[0][1], warn[0][2]
    assert args[0].startswith("Enrichment pipeline hard timeout after 0s ")
    assert "(5000ms elapsed)" in args[0]
    assert args[1:] == ()
    assert kwargs["extra"] == {
        "camera_id": CAMERA,
        "timeout_seconds": 0,
        "elapsed_ms": 5000.0,
        "error_count": 0,
    }
    # the timeout path consumes a third monotonic read -> 10000.0 ms
    assert obs.clock_values == [1000.0, 1005.0, 1010.0]
    assert obs.result.processing_time_ms == 10000.0


def test_no_timeout_when_pipeline_is_fast():
    """Shipped: with a 30s budget the timeout branch stays untouched."""
    obs = enrich(timeout=30.0, populate=blank)
    assert obs.timeout_n == 0
    assert obs.result.errors == []
    assert obs.at("warning") == []


# ======================================================= quality-change tracking block
def test_quality_change_inputs():
    """Shipped: detect_quality_change(result.image_quality, stored_previous_by_camera_id)."""
    prev = quality(score=90.0)
    obs = enrich(seed_previous=prev, dqc_return=(True, "DESC"), populate=populated)
    assert len(obs.dqc_calls) == 1
    cur, used_prev = obs.dqc_calls[0].args
    assert cur is obs.result.image_quality
    assert used_prev is prev
    assert obs.result.quality_change_detected is True
    assert obs.result.quality_change_description == "DESC"


def test_first_frame_has_no_previous():
    """Shipped: nothing stored for camera_id yet -> previous argument is None."""
    obs = enrich(dqc_return=(False, "First frame, no comparison available"))
    assert len(obs.dqc_calls) == 1
    cur, used_prev = obs.dqc_calls[0].args
    assert cur is obs.result.image_quality
    assert used_prev is None
    assert obs.result.quality_change_detected is False
    assert obs.result.quality_change_description == "First frame, no comparison available"


def test_quality_change_warning_message():
    """Shipped: change_detected -> logger.warning(f"Camera {camera_id}: {description}")."""
    obs = enrich(dqc_return=(True, "Sudden quality drop detected: 90 -> 40 (drop: 50)"))
    assert [c[1] for c in obs.at("warning")] == [
        ("Camera cam-1: Sudden quality drop detected: 90 -> 40 (drop: 50)",)
    ]
    obs2 = enrich(dqc_return=(False, "Quality stable"))
    assert obs2.at("warning") == []


def test_previous_quality_store_updated():
    """Shipped: this frame's quality is stored under camera_id for the next frame."""
    obs = enrich(populate=populated)
    assert set(obs.store) == {CAMERA}
    assert obs.store[CAMERA] is obs.result.image_quality


# ================================================================ motion-blur block
def test_motion_context_requires_blur_and_person():
    """Shipped: interpret_blur_with_motion only when is_blurry AND a PERSON_CLASS detection."""
    obs = enrich(populate=blurry_populated, dqc_return=(True, "DESC"))
    assert len(obs.ibm_calls) == 1
    assert obs.ibm_calls[0].args == (obs.result.image_quality,)
    assert obs.ibm_calls[0].kwargs == {"has_person": True}
    assert "Motion context: MOTION-CONTEXT" in obs.messages("info")


def test_motion_context_absent_without_person():
    """Shipped: blurry frame with only non-person detections -> no motion interpretation."""
    obs = enrich(dets=[det(1, "car", 0.9)], populate=blurry_populated, dqc_return=(True, "DESC"))
    assert obs.ibm_calls == []
    assert "Motion context" not in obs.flat("info")


def test_motion_context_absent_without_blur():
    """Shipped: person present but frame not blurry -> no motion interpretation."""
    obs = enrich(populate=populated, dqc_return=(True, "DESC"))
    assert obs.ibm_calls == []
    assert "Motion context" not in obs.flat("info")


def test_person_filter_uses_high_conf_detections():
    """Shipped: the person probe reads the confidence-filtered list handed to enrichment."""
    keep, drop = det(1, "person", 0.95), det(2, "person", 0.1)
    obs = enrich(dets=[keep, drop], populate=blurry_populated, dqc_return=(True, "D"))
    assert obs.parallel_kwargs["high_conf_detections"] == [keep]
    assert len(obs.ibm_calls) == 1


# ================================================================ timing arithmetic
def test_processing_time_ms_scale():
    """Shipped: processing_time_ms = (monotonic_end - monotonic_start) * 1000."""
    obs = enrich(populate=blank)
    # two module clock reads 5.0 s apart under the deterministic clock -> exactly 5000 ms
    assert obs.clock_values == [1000.0, 1005.0]
    assert obs.result.processing_time_ms == 5000.0


def test_high_conf_detections_passed_to_parallel():
    """Shipped: the qualifying subset (>= min_confidence) is handed to the parallel stage."""
    keep, drop = det(1, "person", 0.9), det(2, "car", 0.2)
    obs = enrich(dets=[keep, drop], min_confidence=0.5, populate=blank)
    assert obs.parallel_n == 1
    assert obs.parallel_kwargs["high_conf_detections"] == [keep]
    assert obs.parallel_kwargs["camera_id"] == CAMERA
    assert obs.parallel_kwargs["result"] is obs.result
    assert obs.parallel_kwargs["pil_image"] is IMG


# =============================================== completion span event: name (84, 86-89)
def test_complete_span_event_name():
    """Shipped: the SECOND span event is named exactly "enrichment_pipeline.complete"."""
    obs = enrich(populate=blank)
    assert len(obs.span_calls) == 2
    assert obs.event_names() == ["enrichment_pipeline.start", "enrichment_pipeline.complete"]
    second = obs.span_calls[1]
    assert second.args[0] == "enrichment_pipeline.complete"
    assert len(second.args) == 2


# ================================ completion span event: 20 attributes (85, 87, 90-134)
POPULATED_ATTRS = {
    "parallel_execution": True,  # NEM-4234: Phase 4 marker
    "license_plate.count": 1,
    "face.count": 1,
    "vision_extraction.enabled": True,
    "reid.has_matches": True,
    "scene_change.detected": True,
    "clothing_classification.count": 1,
    "vehicle_classification.count": 1,
    "pet_classification.count": 1,
    "depth_analysis.enabled": True,
    "pose_result.count": 2,
    "action_recognition.enabled": True,
    "image_quality.assessed": True,
    "household_person_match.count": 1,
    "household_vehicle_match.count": 1,
    "clip_scene_classification.available": True,
    "clip_threat_matches.available": True,
    "clip_anomaly_score.available": True,
    "error.count": 0,
    "processing.duration_ms": 5000,
}

DEFAULT_ATTRS = {
    "parallel_execution": True,  # the only literal-True marker: still True when nothing ran
    "license_plate.count": 0,
    "face.count": 0,
    "vision_extraction.enabled": False,
    "reid.has_matches": False,
    "scene_change.detected": False,
    "clothing_classification.count": 0,
    "vehicle_classification.count": 0,
    "pet_classification.count": 0,
    "depth_analysis.enabled": False,
    "pose_result.count": 0,
    "action_recognition.enabled": False,
    "image_quality.assessed": False,
    "household_person_match.count": 0,
    "household_vehicle_match.count": 0,
    "clip_scene_classification.available": False,
    "clip_threat_matches.available": False,
    "clip_anomaly_score.available": False,
    "error.count": 0,
    "processing.duration_ms": 5000,
}


def test_complete_span_attributes_populated():
    """Shipped attribute dict over a fully populated result: exact keys AND values."""
    obs = enrich(populate=populated)
    assert obs.attrs() == POPULATED_ATTRS


def test_complete_span_attributes_defaults():
    """Shipped attribute dict when every result field is still at its shipped default."""
    obs = enrich(populate=blank)
    assert obs.attrs() == DEFAULT_ATTRS


# ================================================ trailing "Enrichment complete:" log
POPULATED_LOG = (
    "Enrichment complete: 1 plates, 1 faces, vision=yes, reid=yes, scene_change=yes, "
    "clothing_class=1, clothing_seg=1, vehicle_damage=1, vehicle_class=1, pets=1, "
    "depth=yes, pose=2, action=yes, quality=yes, household_persons=1, "
    "household_vehicles=1, clip_scene=yes, clip_threats=yes, clip_anomaly=yes "
    "in 5000.0ms"
)

DEFAULT_LOG = (
    "Enrichment complete: 0 plates, 0 faces, vision=no, reid=no, scene_change=no, "
    "clothing_class=0, clothing_seg=0, vehicle_damage=0, vehicle_class=0, pets=0, "
    "depth=no, pose=0, action=no, quality=no, household_persons=0, "
    "household_vehicles=0, clip_scene=no, clip_threats=no, clip_anomaly=no "
    "in 5000.0ms"
)


def test_completion_log_message_populated():
    """Shipped last info line: positive side of every yes/no ternary."""
    obs = enrich(populate=populated)
    assert obs.at("info")[-1][1] == (POPULATED_LOG,)


def test_completion_log_message_defaults():
    """Shipped last info line: negative side of every yes/no ternary."""
    obs = enrich(populate=blank)
    assert obs.at("info")[-1][1] == (DEFAULT_LOG,)
