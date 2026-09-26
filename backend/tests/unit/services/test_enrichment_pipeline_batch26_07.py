"""Batch 26 part 07 — mutation kill battery for backend/services/enrichment_pipeline.py.

Chunk-07 survivors live in exactly two homes:
  EnrichmentPipeline._run_parallel_enrichment  (32 keys: phase2/phase3 gates,
      phase3 task bookkeeping, strict zip, stage observability, timing log)
  EnrichmentPipeline.enrich_batch_with_tracking (88 keys: skipped-path kwargs,
      record_enrichment_batch_status("skipped"), enrich_batch camera_id,
      error_model_mapping, error loop, image/person/animal gating)

Every assert below pins SHIPPED behaviour measured with this same harness first
(rule 1).  Observation seams are the names the pipeline itself sees — patched AT
THE IMPORT SITE (backend.services.enrichment_pipeline.X) so the ep_plugin swap
of a mutant over the live module dict is observed exactly as under shipped code.
The four metrics helpers are imported *inside* enrich_batch_with_tracking, so
that function-body import resolves through backend.core.metrics at call time;
those four are patched there (still the import site for that import).

Class-free plain functions; async driven through asyncio.run (no plugin
dependency).  No sleeps, no network, no DB, no model loading — every collaborator
is a stub.  Shipped source line refs are HEAD:backend/services/enrichment_pipeline.py.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import backend.services.enrichment_pipeline as M

EP = "backend.services.enrichment_pipeline."

# ---------------------------------------------------------------- helpers ----

TRACK_METRICS = (
    "record_enrichment_batch_status",
    "record_enrichment_failure",
    "record_enrichment_partial_batch",
    "set_enrichment_success_rate",
)

PARALLEL_SEAMS = (
    "observe_enrichment_pipeline_stage",
    "record_cascade_model_deferred",
    "add_span_event",
)

# The shipped error_model_mapping (HEAD lines 7321-7336), pinned verbatim.
SHIPPED_ERROR_MODEL_MAPPING = {
    "license_plate_detection": "license_plate",
    "face_detection": "face",
    "vision_extraction": "vision",
    "re_identification": "reid",
    "scene_change_detection": "scene_change",
    "violence_detection": "violence",
    "weather_classification": "weather",
    "clothing_classification": "clothing",
    "clothing_segmentation": "segformer",
    "vehicle_damage_detection": "vehicle_damage",
    "vehicle_classification": "vehicle_class",
    "image_quality_assessment": "image_quality",
    "pet_classification": "pet",
    "depth_estimation": "depth",
}

ALL_FEATURES_OFF = {
    "license_plate_enabled": False,
    "face_detection_enabled": False,
    "vision_extraction_enabled": False,
    "reid_enabled": False,
    "scene_change_enabled": False,
    "violence_detection_enabled": False,
    "weather_classification_enabled": False,
    "clothing_classification_enabled": False,
    "clothing_segmentation_enabled": False,
    "vehicle_damage_detection_enabled": False,
    "vehicle_classification_enabled": False,
    "image_quality_enabled": False,
    "pet_classification_enabled": False,
    "depth_estimation_enabled": False,
}


def _det(cls: str = "person", conf: float = 0.9, det_id: int | None = 1):
    return M.DetectionInput(class_name=cls, confidence=conf, bbox=None, id=det_id)


def _img():
    return MagicMock(name="pil_image")


def _class_names():
    """Shipped class-name constants as concrete member names for probes."""
    animal = sorted(M.ANIMAL_CLASSES)[0] if M.ANIMAL_CLASSES else "dog"
    vehicle = sorted(M.VEHICLE_CLASSES)[0] if M.VEHICLE_CLASSES else "car"
    return M.PERSON_CLASS, animal, vehicle


def _tracking_pipeline(**over):
    """EnrichmentPipeline shell for enrich_batch_with_tracking.

    Only the attributes the method actually touches are present
    (HEAD lines 7269-7485): the 14 *_enabled flags, min_confidence, redis_client.
    """
    p = M.EnrichmentPipeline.__new__(M.EnrichmentPipeline)
    p.min_confidence = 0.5
    p.redis_client = None
    for name, val in ALL_FEATURES_OFF.items():
        setattr(p, name, val)
    for k, v in over.items():
        setattr(p, k, v)
    return p


def _enrich_result(**over):
    er = M.EnrichmentResult()
    for k, v in over.items():
        setattr(er, k, v)
    return er


@contextlib.contextmanager
def tracking_seams():
    """Patch the four metrics helpers exactly where enrich_batch_with_tracking imports them."""
    with ExitStack() as st:
        yield {
            n: st.enter_context(patch("backend.core.metrics." + n, autospec=True))
            for n in TRACK_METRICS
        }


def run_tracking(p, detections, images, camera_id=None):
    with tracking_seams() as m:
        tr = asyncio.run(p.enrich_batch_with_tracking(detections, images, camera_id))
    return tr, m


# ------------------------------------------------- 1. skipped path -----------
# HEAD lines 7302-7311.  Pins: short-circuit before enrich_batch, the four
# explicit kwargs of the skipped EnrichmentTrackingResult and the "skipped"
# metric call.


def test_skipped_short_circuit_and_kwargs():
    p = _tracking_pipeline()
    p.enrich_batch = AsyncMock(side_effect=AssertionError("enrich_batch must not run"))

    tr, m = run_tracking(p, [], {})

    assert isinstance(tr, M.EnrichmentTrackingResult)
    assert tr.status is M.EnrichmentStatus.SKIPPED
    assert tr.successful_models == []
    assert tr.failed_models == []
    assert tr.errors == {}
    assert tr.data is None
    assert tr.success_rate == 1.0
    p.enrich_batch.assert_not_awaited()
    m["record_enrichment_batch_status"].assert_called_once_with("skipped")
    m["record_enrichment_failure"].assert_not_called()
    m["record_enrichment_partial_batch"].assert_not_called()
    m["set_enrichment_success_rate"].assert_not_called()


def test_skipped_metric_argument_is_positional_string():
    """record_enrichment_batch_status("skipped") is positional, one str arg."""
    p = _tracking_pipeline()
    with tracking_seams() as m:
        asyncio.run(p.enrich_batch_with_tracking([], {}))
    calls = m["record_enrichment_batch_status"].call_args_list
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert kwargs == {}
    assert len(args) == 1
    assert isinstance(args[0], str) and args[0] == "skipped"


# ------------------------------------------------ 2. non-skipped core --------
# HEAD lines 7314 + 7461-7485: camera_id forwarded positionally to enrich_batch,
# data=result, status/`record_enrichment_batch_status` come from compute_status.


def test_camera_id_forwarded_and_data_attached():
    p = _tracking_pipeline(license_plate_enabled=True)
    er = _enrich_result()
    p.enrich_batch = AsyncMock(return_value=er)
    dets = [_det(_class_names()[2], 0.9, 7)]

    tr, m = run_tracking(p, dets, {}, "cam-7")

    p.enrich_batch.assert_awaited_once_with(dets, {}, "cam-7")
    assert tr.data is er
    assert tr.status is M.EnrichmentStatus.FULL
    assert tr.successful_models == ["license_plate"] and tr.failed_models == []
    m["record_enrichment_batch_status"].assert_called_once_with(M.EnrichmentStatus.FULL.value)
    m["record_enrichment_partial_batch"].assert_not_called()
    m["record_enrichment_failure"].assert_not_called()


def test_all_models_off_computes_skipped_status_not_shortcut():
    """Non-empty detections still reach compute_status([], []) == SKIPPED (HEAD 604-606)."""
    p = _tracking_pipeline()
    er = _enrich_result()
    p.enrich_batch = AsyncMock(return_value=er)

    tr, m = run_tracking(p, [_det("person", 0.9)], {})

    p.enrich_batch.assert_awaited_once()
    assert tr.status is M.EnrichmentStatus.SKIPPED
    assert tr.successful_models == [] and tr.failed_models == [] and tr.errors == {}
    assert tr.data is er  # data is attached even when the status is SKIPPED
    m["record_enrichment_batch_status"].assert_called_once_with("skipped")
    m["record_enrichment_partial_batch"].assert_not_called()


# --------------------------------------------- 3. error_model_mapping --------
# HEAD lines 7321-7345.  One test pins the whole 14-entry mapping plus the
# failure bookkeeping side effects (errors dict value + record_enrichment_failure).


def test_error_mapping_drives_failed_models_errors_and_metric():
    for operation, model in SHIPPED_ERROR_MODEL_MAPPING.items():
        msg = f"{operation} failed: boom"
        p = _tracking_pipeline()
        p.enrich_batch = AsyncMock(return_value=_enrich_result(errors=[msg]))

        tr, m = run_tracking(p, [_det("person", 0.9)], {})

        assert tr.failed_models == [model], (operation, tr.failed_models)
        assert tr.errors == {model: msg}, (operation, tr.errors)
        m["record_enrichment_failure"].assert_called_once_with(model)
        assert tr.status is M.EnrichmentStatus.FAILED
        assert tr.successful_models == []


def test_error_mapping_matches_on_startswith_not_membership():
    """The probe is ``error_msg.startswith(operation)`` (HEAD line 7341)."""
    p = _tracking_pipeline()
    msg = "face_detection failed: boom and extra context"
    p.enrich_batch = AsyncMock(return_value=_enrich_result(errors=[msg]))

    tr, m = run_tracking(p, [_det("person", 0.9)], {})

    assert tr.failed_models == ["face"]
    assert tr.errors == {"face": msg}
    m["record_enrichment_failure"].assert_called_once_with("face")


def test_unmapped_error_message_is_ignored():
    p = _tracking_pipeline()
    p.enrich_batch = AsyncMock(return_value=_enrich_result(errors=["totally_unrelated failed: x"]))

    tr, m = run_tracking(p, [_det("person", 0.9)], {})

    assert tr.failed_models == [] and tr.errors == {}
    m["record_enrichment_failure"].assert_not_called()


# ------------------------------------------- 4. image availability gates ------
# HEAD lines 7349-7350 + 7376-7381.


def test_shared_image_present_enables_vision_success():
    """images[None] present -> pil_image_available True -> vision tracked."""
    p = _tracking_pipeline(vision_extraction_enabled=True)
    er = _enrich_result(vision_extraction=MagicMock(name="batch_extraction"))
    p.enrich_batch = AsyncMock(return_value=er)
    img = _img()

    tr, m = run_tracking(p, [_det("person", 0.9)], {None: img})

    assert "vision" in tr.successful_models
    assert ("vision", 1.0) in [c.args for c in m["set_enrichment_success_rate"].call_args_list]


def test_shared_image_absent_disables_vision_gate():
    p = _tracking_pipeline(vision_extraction_enabled=True)
    er = _enrich_result(vision_extraction=MagicMock(name="batch_extraction"))
    p.enrich_batch = AsyncMock(return_value=er)

    tr, m = run_tracking(p, [_det("person", 0.9)], {})

    assert tr.successful_models == []
    assert tr.failed_models == []
    m["set_enrichment_success_rate"].assert_not_called()


def test_vision_gate_requires_enabled_and_image():
    """``vision_extraction_enabled and pil_image_available`` — both required."""
    # enabled False, image present -> gate closed
    p = _tracking_pipeline(vision_extraction_enabled=False)
    p.enrich_batch = AsyncMock(return_value=_enrich_result(vision_extraction=MagicMock(name="be")))
    tr, m = run_tracking(p, [_det("person", 0.9)], {None: _img()})
    assert tr.successful_models == []
    m["set_enrichment_success_rate"].assert_not_called()


def test_vision_success_requires_not_failed_and_present():
    """HEAD 7377/7380: append requires "vision" not in failed AND value present."""
    ve = MagicMock(name="batch_extraction")

    # (a) present, not failed -> appended + rate 1.0
    p = _tracking_pipeline(vision_extraction_enabled=True)
    p.enrich_batch = AsyncMock(return_value=_enrich_result(vision_extraction=ve))
    tr, m = run_tracking(p, [_det("person", 0.9)], {None: _img()})
    assert tr.successful_models == ["vision"]
    assert ("vision", 1.0) in [c.args for c in m["set_enrichment_success_rate"].call_args_list]
    assert ("vision", 0.0) not in [c.args for c in m["set_enrichment_success_rate"].call_args_list]

    # (b) failed -> NOT appended, elif branch sets rate 0.0
    p = _tracking_pipeline(vision_extraction_enabled=True)
    p.enrich_batch = AsyncMock(
        return_value=_enrich_result(vision_extraction=ve, errors=["vision_extraction failed: x"])
    )
    tr, m = run_tracking(p, [_det("person", 0.9)], {None: _img()})
    assert "vision" not in tr.successful_models
    assert tr.failed_models == ["vision"]
    assert ("vision", 0.0) in [c.args for c in m["set_enrichment_success_rate"].call_args_list]

    # (c) present-but-absent value, no failure -> neither branch, no rate call
    p = _tracking_pipeline(vision_extraction_enabled=True)
    p.enrich_batch = AsyncMock(return_value=_enrich_result(vision_extraction=None))
    tr, m = run_tracking(p, [_det("person", 0.9)], {None: _img()})
    assert tr.successful_models == [] and tr.failed_models == []
    m["set_enrichment_success_rate"].assert_not_called()


def test_vision_failure_key_in_elif_branch():
    """HEAD 7380: the elif tests the literal "vision" in failed_models."""
    p = _tracking_pipeline(vision_extraction_enabled=True)
    p.enrich_batch = AsyncMock(
        return_value=_enrich_result(vision_extraction=None, errors=["vision_extraction failed: x"])
    )

    tr, m = run_tracking(p, [_det("person", 0.9)], {None: _img()})

    assert tr.failed_models == ["vision"]
    assert "vision" not in tr.successful_models
    assert ("vision", 0.0) in [c.args for c in m["set_enrichment_success_rate"].call_args_list]


# ------------------------------------------- 5. and/or gate conjunctions -----


def test_license_plate_gate_requires_enabled_and_vehicles():
    person, animal, vehicle = _class_names()

    # enabled + vehicle -> tracked
    p = _tracking_pipeline(license_plate_enabled=True)
    p.enrich_batch = AsyncMock(return_value=_enrich_result())
    tr, m = run_tracking(p, [_det(vehicle, 0.9)], {})
    assert tr.successful_models == ["license_plate"]

    # disabled + vehicle -> gate closed (and, not or)
    p = _tracking_pipeline(license_plate_enabled=False)
    p.enrich_batch = AsyncMock(return_value=_enrich_result())
    tr, m = run_tracking(p, [_det(vehicle, 0.9)], {})
    assert tr.successful_models == []
    m["set_enrichment_success_rate"].assert_not_called()

    # enabled + no vehicle -> gate closed
    p = _tracking_pipeline(license_plate_enabled=True)
    p.enrich_batch = AsyncMock(return_value=_enrich_result())
    tr, m = run_tracking(p, [_det(person, 0.9)], {})
    assert tr.successful_models == []
    m["set_enrichment_success_rate"].assert_not_called()


def test_license_plate_failure_sets_rate_zero_not_success():
    """HEAD 7362-7367: "license_plate" in failed_models -> rate 0.0, no append."""
    person, animal, vehicle = _class_names()
    p = _tracking_pipeline(license_plate_enabled=True)
    p.enrich_batch = AsyncMock(
        return_value=_enrich_result(errors=["license_plate_detection failed: boom"])
    )

    tr, m = run_tracking(p, [_det(vehicle, 0.9)], {})

    assert tr.failed_models == ["license_plate"]
    assert "license_plate" not in tr.successful_models
    assert ("license_plate", 0.0) in [
        c.args for c in m["set_enrichment_success_rate"].call_args_list
    ]
    assert ("license_plate", 1.0) not in [
        c.args for c in m["set_enrichment_success_rate"].call_args_list
    ]


def test_face_gate_requires_enabled_and_persons():
    person, animal, vehicle = _class_names()

    p = _tracking_pipeline(face_detection_enabled=True)
    p.enrich_batch = AsyncMock(return_value=_enrich_result())
    tr, m = run_tracking(p, [_det(person, 0.9)], {})
    assert tr.successful_models == ["face"]

    # disabled + person present -> gate closed (and, not or)
    p = _tracking_pipeline(face_detection_enabled=False)
    p.enrich_batch = AsyncMock(return_value=_enrich_result())
    tr, m = run_tracking(p, [_det(person, 0.9)], {})
    assert tr.successful_models == []
    m["set_enrichment_success_rate"].assert_not_called()

    # enabled + no person -> gate closed
    p = _tracking_pipeline(face_detection_enabled=True)
    p.enrich_batch = AsyncMock(return_value=_enrich_result())
    tr, m = run_tracking(p, [_det(vehicle, 0.9)], {})
    assert tr.successful_models == []
    m["set_enrichment_success_rate"].assert_not_called()


# ---------------------------------------- 6. has_persons / has_animals -------


def test_has_persons_drives_clothing_and_segformer_gates():
    person, animal, vehicle = _class_names()

    # person present -> clothing + segformer tracked
    p = _tracking_pipeline(
        clothing_classification_enabled=True,
        clothing_segmentation_enabled=True,
    )
    p.enrich_batch = AsyncMock(return_value=_enrich_result())
    tr, _ = run_tracking(p, [_det(person, 0.9)], {None: _img()})
    assert tr.successful_models == ["clothing", "segformer"]

    # person-only list but has_persons computed with != would be False
    p = _tracking_pipeline(clothing_classification_enabled=True)
    p.enrich_batch = AsyncMock(return_value=_enrich_result())
    tr, m = run_tracking(p, [_det(vehicle, 0.9)], {None: _img()})
    assert tr.successful_models == []
    m["set_enrichment_success_rate"].assert_not_called()


def test_has_animals_drives_pet_gate():
    person, animal, vehicle = _class_names()

    p = _tracking_pipeline(pet_classification_enabled=True)
    p.enrich_batch = AsyncMock(return_value=_enrich_result())
    tr, _ = run_tracking(p, [_det(animal, 0.9)], {None: _img()})
    assert tr.successful_models == ["pet"]

    # no animal -> gate closed
    p = _tracking_pipeline(pet_classification_enabled=True)
    p.enrich_batch = AsyncMock(return_value=_enrich_result())
    tr, m = run_tracking(p, [_det(person, 0.9)], {None: _img()})
    assert tr.successful_models == []
    m["set_enrichment_success_rate"].assert_not_called()

    # animal present but membership inverted -> would be False on the animal list
    p = _tracking_pipeline(pet_classification_enabled=True)
    p.enrich_batch = AsyncMock(return_value=_enrich_result())
    tr, m = run_tracking(p, [_det(animal, 0.9), _det(person, 0.9)], {None: _img()})
    assert "pet" in tr.successful_models


# ------------------------------------- 7. has_multiple_persons threshold -----


def test_violence_gate_needs_at_least_two_persons():
    person, animal, vehicle = _class_names()

    def gate(n_persons):
        p = _tracking_pipeline(violence_detection_enabled=True)
        p.enrich_batch = AsyncMock(return_value=_enrich_result())
        dets = [_det(person, 0.9, i + 1) for i in range(n_persons)]
        tr, m = run_tracking(p, dets, {None: _img()})
        return "violence" in tr.successful_models, m

    ok1, m1 = gate(1)
    assert ok1 is False
    m1["set_enrichment_success_rate"].assert_not_called()

    ok2, m2 = gate(2)
    assert ok2 is True
    assert ("violence", 1.0) in [c.args for c in m2["set_enrichment_success_rate"].call_args_list]

    ok3, _ = gate(3)
    assert ok3 is True


def test_violence_gate_not_satisfied_by_non_persons():
    """sum(1 for ... == PERSON_CLASS) counts persons only, not the complement."""
    person, animal, vehicle = _class_names()
    p = _tracking_pipeline(violence_detection_enabled=True)
    p.enrich_batch = AsyncMock(return_value=_enrich_result())

    tr, m = run_tracking(p, [_det(vehicle, 0.9, 1), _det(animal, 0.9, 2)], {None: _img()})

    assert "violence" not in tr.successful_models
    m["set_enrichment_success_rate"].assert_not_called()


# ------------------------------ 8. _run_parallel_enrichment harness ----------


class _Gather:
    """Stand-in for bounded_gather: records each payload, awaits real coroutines."""

    def __init__(self, canned=None):
        self.payloads: list[list] = []
        self.calls: list[dict] = []
        self._canned: list = list(canned) if canned is not None else []

    def reset(self, canned=None):
        self.payloads = []
        self.calls = []
        self._canned = list(canned) if canned is not None else []

    async def __call__(self, items, *, limit=None, task_timeout=None, return_exceptions=False):
        items = list(items)
        self.payloads.append(items)
        self.calls.append({"limit": limit, "return_exceptions": return_exceptions})
        if self._canned:
            res = self._canned.pop(0)
            for it in items:
                close = getattr(it, "close", None)
                if close is not None:
                    close()
            return res
        return await asyncio.gather(*items, return_exceptions=True)


class _Clock:
    """Deterministic monotonic clock: 1000.0, 1001.0, 1002.0 ... per read."""

    def __init__(self, start=1000.0, step=1.0):
        self.start = start
        self.step = step
        self.t = start

    def reset(self):
        self.t = self.start

    def monotonic(self):
        v = self.t
        self.t += self.step
        return v


# The seams _run_parallel_enrichment reads through are installed ONCE for the whole
# session (see the fixture below), not per test: ep_plugin snapshots the live module
# dict when it binds a mutant, so patches that start *after* that snapshot would be
# invisible to the mutant.  Session-wide install + per-run reset gives the mutant and
# shipped code the identical view while keeping every measurement per-run.
_GATHER = _Gather()
_CLOCK = _Clock()
_SEAMS: dict = {}


@pytest.fixture(scope="module", autouse=True)
def _install_parallel_seams():
    """Put every _run_parallel_enrichment seam into the module dict for this file only.

    Module (not session) scope so the seams never leak into other test files that share
    the session: they are removed again as soon as this file's tests finish.
    """
    with ExitStack() as st:
        seams = {n: st.enter_context(patch(EP + n, autospec=True)) for n in PARALLEL_SEAMS}
        seams["logger"] = st.enter_context(patch(EP + "logger", autospec=True))
        seams["time"] = st.enter_context(patch(EP + "time", autospec=True))
        seams["gather"] = _GATHER
        st.enter_context(patch(EP + "bounded_gather", new=_GATHER))
        seams["time"].monotonic.side_effect = _CLOCK.monotonic
        _SEAMS.update(seams)
        yield seams


_STUBBED = (
    "_safe_detect_faces",
    "_safe_detect_plates_fast_alpr",
    "_safe_detect_license_plates",
    "_safe_detect_violence",
    "_estimate_poses_via_service",
    "_detect_threats_via_service",
    "_compute_reid_via_service",
    "_safe_estimate_poses",
    "_safe_classify_person_clothing",
    "_safe_classify_vehicle_types",
    "_safe_classify_pets",
    "_safe_classify_demographics",
    "_safe_extract_osnet_embeddings",
    "_safe_detect_smoke_fire",
    "_safe_detect_yolo_world",
    "_safe_assess_image_quality",
    "_safe_classify_weather",
    "_safe_analyze_depth",
    "_safe_detect_vehicle_damage",
    "_safe_run_scene_ocr_frame",
    "_safe_segment_person_clothing",
    "_safe_clip_scene_classify",
    "_safe_clip_threat_match",
    "_run_reid",
    "_run_clip_anomaly_detection",
    "_run_household_matching",
    "_read_plates",
    "_safe_run_scene_ocr_crops",
    "_recognize_actions_from_skeleton",
    "_enrich_persons_via_unified_service",
    "_enrich_vehicles_via_unified_service",
    "_enrich_animals_via_unified_service",
)

# called synchronously (not awaited) by the shipped method -> sync stubs are set
# directly in _parallel_pipeline (_process_phase1_results, _is_fast_alpr_available).


def _parallel_pipeline(quality="full", reid=False, household=False, redis=None):
    """Pipeline shell exposing exactly the attributes _run_parallel_enrichment reads."""
    p = M.EnrichmentPipeline.__new__(M.EnrichmentPipeline)
    p.use_enrichment_service = False
    p._quality_level = quality
    p.redis_client = redis
    p._pipeline_timeout = 30.0
    p._vision_extractor = MagicMock(name="vision_extractor")
    p._scene_detector = MagicMock(name="scene_detector")
    p._scene_ocr_service = None
    for name in ALL_FEATURES_OFF:
        setattr(p, name, False)
    p.ocr_enabled = False
    p.scene_ocr_enabled = False
    p.smoke_fire_detection_enabled = False
    p.yolo_world_enabled = False
    p.osnet_reid_enabled = False
    p.age_classification_enabled = False
    p.gender_classification_enabled = False
    p.action_recognition_enabled = False
    p.pose_estimation_enabled = False
    p.low_light_enhancement_enabled = False
    p.household_matching_enabled = household
    p.reid_enabled = reid
    for name in _STUBBED:
        setattr(p, name, AsyncMock(name=name))
    p._process_phase1_results = MagicMock(name="_process_phase1_results")
    p._is_fast_alpr_available = MagicMock(name="_is_fast_alpr_available", return_value=False)
    return p


@contextlib.contextmanager
def parallel_seams(canned=None):
    """Reset the session-installed seams for one run and hand back the mock set."""
    _GATHER.reset(canned)
    _CLOCK.reset()
    for name in PARALLEL_SEAMS + ("logger",):
        _SEAMS[name].reset_mock()
    yield _SEAMS


def run_parallel(p, result, pil_image, dets, images, camera_id):
    with parallel_seams() as m:
        asyncio.run(p._run_parallel_enrichment(result, pil_image, dets, images, camera_id))
    return m


def run_parallel_with(canned, p, result, pil_image, dets, images, camera_id):
    with parallel_seams(canned) as m:
        asyncio.run(p._run_parallel_enrichment(result, pil_image, dets, images, camera_id))
    return m


# ------------------------------------- 9. stage observation + durations ------
# HEAD 2737-2738, 2817-2818, 2855-2859.  With the deterministic clock the shipped
# durations are exactly 1.0 / 1.0 / 1.0 / 7.0 (8 monotonic() reads).


def test_stage_observations_shipped_names_order_and_durations():
    p = _parallel_pipeline()
    er = _enrich_result()
    dets = [_det("person", 0.9)]

    m = run_parallel(p, er, _img(), dets, {}, "cam-1")

    obs = m["observe_enrichment_pipeline_stage"]
    names = [c.args[0] for c in obs.call_args_list]
    assert names == ["phase1_and_florence", "phase2", "phase3", "total"]
    durs = [c.args[1] for c in obs.call_args_list]
    assert durs == [1.0, 1.0, 1.0, 7.0]
    assert all(isinstance(c.args[0], str) for c in obs.call_args_list)
    # phase2/phase3 durations are differences, never sums
    assert durs[1] < 100.0 and durs[3] < 100.0


def test_stage_observation_count_is_four_per_run():
    p = _parallel_pipeline()
    er = _enrich_result()

    m = run_parallel(p, er, _img(), [_det("person", 0.9)], {}, "cam-1")

    obs = m["observe_enrichment_pipeline_stage"]
    assert obs.call_count == 4
    # every observation carries exactly (name, duration) — no extra/omitted stages
    assert all(len(c.args) == 2 and not c.kwargs for c in obs.call_args_list)


# ------------------------------------------------------ 10. timing log -------
# HEAD 2860-2867.


def test_timing_log_line_is_emitted_verbatim():
    p = _parallel_pipeline(quality="full")
    er = _enrich_result()

    m = run_parallel(p, er, _img(), [_det("person", 0.9)], {}, "cam-1")

    expected = (
        "Enrichment pipeline timing: "
        "phase1+florence=1.00s, "
        "phase2=1.00s, "
        "phase3=1.00s, "
        "total=7.00s, "
        "quality=full"
    )
    assert m["logger"].info.call_args == ((expected,), {})


def test_timing_log_reflects_quality_level_and_durations():
    p = _parallel_pipeline(quality="standard")
    er = _enrich_result()

    m = run_parallel(p, er, _img(), [_det("person", 0.9)], {}, "cam-1")

    (msg,) = m["logger"].info.call_args.args
    assert msg.startswith("Enrichment pipeline timing: phase1+florence=1.00s, ")
    assert msg.endswith("total=7.00s, quality=standard")
    assert "phase3=1.00s" in msg


# ------------------------------- 11. phase3 clip-anomaly gate conjunctions ---
# HEAD 2824-2835.  Observable through the phase3 bounded_gather payload: with
# household matching on, the payload holds exactly the enabled phase-3 tasks.


def test_clip_anomaly_gate_all_five_terms_required():
    """HEAD 2824-2830: clip task needs reid AND image AND camera AND redis AND full tier.

    Each term is flipped false exactly once (household matching stays on so phase 3
    still runs); a flipped term must stop the clip task from being awaited, which is
    what distinguishes the shipped conjunction from any `or` mutant.
    """
    person, _, _ = _class_names()
    dets = [_det(person, 0.9)]
    img = _img()

    def ran(**over):
        # default = gate fully open (all five shipped terms truthy)
        redis = over.pop("redis", object())
        p = _parallel_pipeline(
            quality=over.pop("quality", "full"),
            reid=over.pop("reid", True),
            household=True,
            redis=redis,
        )
        er = _enrich_result()
        with parallel_seams():
            asyncio.run(
                p._run_parallel_enrichment(
                    er,
                    over.pop("pil_image", img),
                    dets,
                    {},
                    over.pop("camera_id", "cam-1"),
                )
            )
        return (p._run_clip_anomaly_detection.await_count, p._run_household_matching.await_count)

    # shipped: all terms satisfied -> both phase-3 tasks run
    assert ran() == (1, 1)
    # shipped: each single term flipped false closes the clip gate (and, not or)
    assert ran(reid=False) == (0, 1)
    assert ran(pil_image=None) == (0, 1)
    assert ran(camera_id=None) == (0, 1)
    assert ran(redis=None) == (0, 1)
    assert ran(quality="standard") == (0, 1)
    # "minimal" closes the household gate too
    assert ran(quality="minimal") == (0, 0)


def test_clip_anomaly_task_registered_and_awaited_when_gate_open():
    """Gate open creates the clip task and it is awaited by phase 3."""
    person, _, _ = _class_names()
    p = _parallel_pipeline(quality="full", reid=True, household=True, redis=object())
    er = _enrich_result()

    with parallel_seams() as m:
        asyncio.run(p._run_parallel_enrichment(er, _img(), [_det(person, 0.9)], {}, "cam-1"))

    assert len(m["gather"].payloads[-1]) == 2
    p._run_clip_anomaly_detection.assert_awaited_once()
    p._run_household_matching.assert_awaited_once()


# ---------------------------------------- 12. household gate (flag + tier) ---
# HEAD 2837-2842.


def _household_ran(**over):
    p = _parallel_pipeline(
        quality=over.pop("quality", "full"),
        reid=False,
        household=over.pop("household", True),
        redis=over.pop("redis", None),
    )
    er = _enrich_result()
    asyncio.run(
        p._run_parallel_enrichment(
            er,
            over.pop("pil_image", _img()),
            [_det("person", 0.9)],
            {},
            over.pop("camera_id", "cam-1"),
        )
    )
    return p._run_household_matching.await_count


def test_household_gate_requires_flag_and_standard_tier():
    assert _household_ran(household=True, quality="full") == 1
    assert _household_ran(household=True, quality="standard") == 1
    # standard tier not reached -> no household task
    assert _household_ran(household=True, quality="minimal") == 0
    # flag off -> no household task even at full quality
    assert _household_ran(household=False, quality="full") == 0
    assert _household_ran(household=False, quality="standard") == 0


def test_household_matching_called_with_detections_and_result():
    p = _parallel_pipeline(quality="standard", household=True)
    er = _enrich_result()
    dets = [_det("person", 0.9, 1), _det("person", 0.9, 2)]

    asyncio.run(p._run_parallel_enrichment(er, _img(), dets, {}, "cam-1"))

    assert p._run_household_matching.await_count == 1
    args = p._run_household_matching.await_args.args
    assert len(args) == 2
    assert args[0] is dets
    assert args[1] is er


def test_household_task_is_registered_under_household_matching_key():
    """Failure surfaces through _handle_enrichment_error keyed by the dict key."""
    p = _parallel_pipeline(quality="standard", household=True)
    er = _enrich_result()
    boom = RuntimeError("household down")
    p._run_household_matching = AsyncMock(side_effect=boom)

    with patch.object(M.EnrichmentPipeline, "_handle_enrichment_error", autospec=True) as handle:
        asyncio.run(p._run_parallel_enrichment(er, _img(), [_det("person", 0.9)], {}, "cam-1"))

    assert handle.call_count == 1
    args = handle.call_args.args
    assert args[1] == "household_matching"
    assert args[2] is boom
    assert args[3] is er


# --------------------------------- 13. phase3 task value / zip strictness ----


def test_phase3_task_value_is_a_coroutine_and_runs():
    p = _parallel_pipeline(quality="standard", household=True)
    er = _enrich_result()

    with parallel_seams() as m:
        asyncio.run(p._run_parallel_enrichment(er, _img(), [_det("person", 0.9)], {}, "cam-1"))

    payload = m["gather"].payloads[-1]
    assert len(payload) == 1
    assert payload[0] is not None
    assert hasattr(payload[0], "send"), "phase3 task value must be awaitable"
    assert p._run_household_matching.await_count == 1


def test_phase3_zip_is_strict_on_length_mismatch():
    """zip(..., strict=True): a short result sequence raises, never truncates."""
    p = _parallel_pipeline(quality="full", reid=True, household=True, redis=object())
    er = _enrich_result()
    # phase1 gather -> 2 results, phase2 gather -> 1, phase3 gather -> only 1 of 2
    canned = [[None, None], [None], [RuntimeError("boom")]]

    with pytest.raises(ValueError, match="shorter than|length mismatch"):
        with parallel_seams(canned) as m:
            asyncio.run(p._run_parallel_enrichment(er, _img(), [_det("person", 0.9)], {}, "cam-1"))
    assert len(m["gather"].payloads[-1]) == 2


def test_phase3_exception_is_passed_through_to_error_handler():
    """HEAD 2851-2853: the gathered Exception itself is the second argument."""
    p = _parallel_pipeline(quality="full", reid=True, household=True, redis=object())
    er = _enrich_result()
    boom = RuntimeError("clip down")
    canned = [[None, None], [None], [boom, boom]]

    with patch.object(M.EnrichmentPipeline, "_handle_enrichment_error", autospec=True) as handle:
        with parallel_seams(canned) as m:
            asyncio.run(p._run_parallel_enrichment(er, _img(), [_det("person", 0.9)], {}, "cam-1"))

    keys = [c.args[1] for c in handle.call_args_list]
    assert keys == ["clip_anomaly_detection", "household_matching"]
    assert all(c.args[2] is boom for c in handle.call_args_list)
    assert all(c.args[3] is er for c in handle.call_args_list)
