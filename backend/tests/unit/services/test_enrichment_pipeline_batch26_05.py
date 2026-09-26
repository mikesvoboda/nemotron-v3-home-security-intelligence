"""Chunk-05 kill-battery for ``EnrichmentPipeline._run_parallel_enrichment`` (120 keys).

Every assertion pins behaviour MEASURED on the pristine shipped module
(``backend/services/enrichment_pipeline.py`` @ HEAD, method body L2345-2867).

Observation surface (all spies installed on the LIVE module dict / the pipeline
instance, so the ep_plugin mutant — whose ``__globals__`` is a snapshot of the
live module dict taken by the autouse plugin fixture — sees exactly the same
globals as shipped code does):

* every Phase-1/2/3 scheduler method is replaced by a recorder that logs the
  call ``(args, kwargs)`` at SCHEDULE time and appends an ``("task", name,
  args, kwargs)`` entry at AWAIT time.  Schedule-time logging is what makes the
  schedule order (dict insertion order, L2638 ``list(phase1_tasks.keys())``)
  observable, because CPython creates the coroutine object *after* the argument
  references are decref'd — so a dropped argument cannot be observed from a
  real coroutine object, only from the call site.
* ``_process_phase1_results`` / ``_handle_enrichment_error`` are instance stubs
  that record the delivered ``phase1_dict`` key order / the (operation,
  exception-type) pairs.  The key name IS the contract with the assembler
  (``_process_phase1_results`` reads it with ``if "<name>" in phase1_dict``).
* ``bounded_gather`` is wrapped (delegating to the real implementation) so the
  GPU/CPU partition, ``limit`` and ``task_timeout`` are recorded.
* ``record_cascade_model_deferred`` / ``add_span_event`` are module-level spies;
  ``logger`` is the REAL module logger with a capture handler attached and
  DEBUG enabled, so the cascade debug record is seen verbatim (and a broken
  ``%``-template raises from the real formatting machinery).

``asyncio.run`` is used inside plain sync tests (same convention as
``test_batch26_00.py``) so the file does not depend on the asyncio plugin mode.
"""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from typing import Any

import pytest
from PIL import Image

import backend.services.enrichment_pipeline as M
from backend.services.enrichment_pipeline import (
    BoundingBox,
    DetectionInput,
    EnrichmentPipeline,
    EnrichmentResult,
)
from backend.tests.unit.services._bg_dispatch import (
    bg_real,
    install_bg_dispatcher,
    recorder_errors,
    register_recorder,
)

MODULE = "backend.services.enrichment_pipeline"

# ---------------------------------------------------------------------------
# recorder
# ---------------------------------------------------------------------------
REC: dict[str, Any] = {}


def _reset() -> None:
    REC.clear()
    REC.update(
        calls=[],  # ("task", name, args, kwargs) at await time
        scheduled={},  # name -> [(args, kwargs)] at schedule time
        p1=[],  # [list(phase1_dict.keys())] per delivery
        errors=[],  # (operation, exc_type_name)
        cascade=[],  # (model, reason)
        spans=[],  # (name, attrs)
        bg=[],  # SimpleNamespace(names, limit, task_timeout, return_exceptions)
        sync={},  # name -> [args]
    )


_reset()


# --- module-level spies (installed at import time: the plugin snapshots the
# --- live module dict BEFORE each test body runs, so late installation would
# --- leave the mutant body pointing at the unscreened originals) -------------
M.record_cascade_model_deferred = lambda model, reason: REC["cascade"].append((model, reason))
M.add_span_event = lambda name, attrs=None, **kw: REC["spans"].append((name, attrs))
M.observe_enrichment_pipeline_stage = lambda *a, **k: None

_REAL_CASCADE = M.record_cascade_model_deferred
_REAL_SPAN = M.add_span_event
_REAL_STAGE = M.observe_enrichment_pipeline_stage

# ``bounded_gather`` is NOT privately spied here any more.  The slot is one
# global name and batch26_02 registers a ``limit``-shape recorder on it at ITS
# import time: two import-time spies meant "last import wins" and the loser
# either recorded nothing (``REC["bg"]`` stayed empty) or captured the OTHER
# file's spy as its own "original".  Grouped CI runs never interleaved the two
# files, so this only surfaced in mutmut's interleaved 1296-id stats rerun.  The
# shared dispatcher owns the slot permanently; this file just registers a
# recorder and activates it for its own tests (see ``_bg_dispatch``).
install_bg_dispatcher(M)
_REAL_BOUNDED_GATHER = bg_real(M)  # the PRISTINE callee, via the dispatcher tag


def _record_gather(coros: list[Any], kw: dict[str, Any]) -> None:
    """Gather-time view of the phase partition, recorded at SCHEDULE-to-GATHER
    time exactly as the old spy did: the ``_ep_task`` name of every awaitable
    handed to ``bounded_gather`` plus the kwargs the call site passed."""
    names = [getattr(c, "_ep_task", "<coroutine>") for c in coros]
    REC["bg"].append(
        SimpleNamespace(
            names=names,
            limit=kw.get("limit"),
            task_timeout=kw.get("task_timeout"),
            return_exceptions=kw.get("return_exceptions"),
        )
    )


_BG_STATE = register_recorder(_record_gather)

# capture handler on the REAL module logger so ``logger.debug(fmt, *args)`` is
# seen verbatim (record.msg / record.args) and a broken template raises through
# the real ``logging`` formatting machinery exactly as it would in production
# with DEBUG enabled.
_LOG_RECORDS: list[logging.LogRecord] = []


class _Capture(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        _LOG_RECORDS.append(record)


_CAPTURE_HANDLER = _Capture()


# ---------------------------------------------------------------------------
# pipeline construction (bypasses __init__: every attribute the method reads is
# set explicitly, so no service getter / settings / Redis access happens)
# ---------------------------------------------------------------------------
ENABLES = (
    "license_plate_enabled",
    "face_detection_enabled",
    "ocr_enabled",
    "vision_extraction_enabled",
    "reid_enabled",
    "scene_change_enabled",
    "violence_detection_enabled",
    "weather_classification_enabled",
    "clothing_classification_enabled",
    "clothing_segmentation_enabled",
    "vehicle_damage_detection_enabled",
    "vehicle_classification_enabled",
    "image_quality_enabled",
    "pet_classification_enabled",
    "depth_estimation_enabled",
    "pose_estimation_enabled",
    "action_recognition_enabled",
    "scene_ocr_enabled",
    "household_matching_enabled",
    "age_classification_enabled",
    "gender_classification_enabled",
    "smoke_fire_detection_enabled",
    "yolo_world_enabled",
    "osnet_reid_enabled",
    "low_light_enhancement_enabled",
)

SCHEDULERS = (
    "_safe_detect_faces",
    "_safe_detect_plates_fast_alpr",
    "_safe_detect_license_plates",
    "_safe_detect_violence",
    "_enrich_persons_via_unified_service",
    "_enrich_vehicles_via_unified_service",
    "_enrich_animals_via_unified_service",
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
    "_read_plates",
    "_run_reid",
    "_run_clip_anomaly_detection",
    "_run_household_matching",
    "_safe_run_scene_ocr_crops",
    "_recognize_actions_from_skeleton",
    "_extract_batch_attributes",
)


class _Task:
    """Awaitable stand-in for a scheduler coroutine; carries its call signature."""

    __slots__ = ("name", "args", "kwargs", "_ep_task")

    def __init__(self, name: str, args: tuple, kwargs: dict) -> None:
        self.name = name
        self.args = args
        self.kwargs = kwargs
        self._ep_task = name  # read by the bounded_gather spy

    def __await__(self):
        async def _run() -> None:
            REC["calls"].append(("task", self.name, self.args, self.kwargs))

        return _run().__await__()


def _sched(self: Any, name: str, *args: Any, **kwargs: Any) -> _Task:
    REC["scheduled"].setdefault(name, []).append((args, kwargs))
    return _Task(name, args, kwargs)


def _sync(self: Any, name: str, *args: Any, **kwargs: Any) -> bool:
    REC["sync"].setdefault(name, []).append((args, kwargs))
    return False


def pipeline(**attrs: Any) -> EnrichmentPipeline:
    """Bare pipeline whose whole observable surface is recorded in ``REC``."""
    _reset()
    p = EnrichmentPipeline.__new__(EnrichmentPipeline)
    for name in ENABLES:
        setattr(p, name, False)
    p.use_enrichment_service = False
    p.redis_client = None
    p._quality_level = "full"
    p._pipeline_timeout = 30.0
    p._process_phase1_results = lambda result, phase1_dict: REC["p1"].append(list(phase1_dict))
    p._handle_enrichment_error = lambda op, exc, result: REC["errors"].append(
        (op, type(exc).__name__)
    )
    p._is_fast_alpr_available = lambda *a, **k: _sync(p, "_is_fast_alpr_available", *a, **k)
    for name in SCHEDULERS:
        setattr(p, name, lambda *a, _n=name, **k: _sched(p, _n, *a, **k))
    p._vision_extractor = SimpleNamespace(
        extract_batch_attributes=lambda *a, **k: _sched(p, "_extract_batch_attributes", *a, **k)
    )
    p._scene_detector = SimpleNamespace(detect_changes=lambda cid, arr: None)
    p._scene_ocr_service = None
    p._reid_service = None
    for k, v in attrs.items():
        setattr(p, k, v)
    return p


def run(
    p: EnrichmentPipeline,
    image: Any = ...,
    dets: Any = (),
    images: Any = None,
    camera_id: Any = None,
) -> EnrichmentResult:
    result = EnrichmentResult()
    if image is ...:
        image = frame()
    asyncio.run(
        p._run_parallel_enrichment(
            result, image, list(dets), {} if images is None else images, camera_id
        )
    )
    return result


def frame() -> Image.Image:
    return Image.new("RGB", (32, 32), color=(9, 8, 7))


def det(cls: str = "person", conf: float = 0.9, did: int | None = 1) -> DetectionInput:
    return DetectionInput(
        class_name=cls,
        confidence=conf,
        bbox=BoundingBox(x1=0, y1=0, x2=10, y2=10),
        id=did,
    )


def scheduled(name: str) -> list[tuple[tuple, dict]]:
    return REC["scheduled"].get(name, [])


def awaited(name: str) -> list[tuple[tuple, dict]]:
    return [(a, k) for (_t, n, a, k) in REC["calls"] if n == name]


def p1keys() -> list[str]:
    return REC["p1"][-1] if REC["p1"] else []


# scheduler method -> the shipped phase1_tasks key it is stored under (each
# mapping is separately pinned by the gate/argument tests above; the shipped
# GPU/CPU partition at L2656-2662 is computed on the KEY, so the groups are
# reported in key terms here)
KEY_OF = {
    "_safe_detect_faces": "face_detection",
    "_safe_detect_plates_fast_alpr": "license_plate_detection",
    "_safe_detect_license_plates": "license_plate_detection",
    "_safe_detect_violence": "violence_detection",
    "_enrich_persons_via_unified_service": "unified_person_enrichment",
    "_enrich_vehicles_via_unified_service": "unified_vehicle_enrichment",
    "_enrich_animals_via_unified_service": "unified_animal_enrichment",
    "_estimate_poses_via_service": "pose_estimation",
    "_safe_estimate_poses": "pose_estimation",
    "_detect_threats_via_service": "threat_detection",
    "_compute_reid_via_service": "reid_via_service",
    "_safe_classify_person_clothing": "clothing_classification",
    "_safe_classify_vehicle_types": "vehicle_classification",
    "_safe_classify_pets": "pet_classification",
    "_safe_classify_demographics": "demographics",
    "_safe_extract_osnet_embeddings": "osnet_reid",
    "_safe_detect_smoke_fire": "smoke_fire_detection",
    "_safe_detect_yolo_world": "yolo_world_detection",
    "_safe_assess_image_quality": "image_quality",
    "_safe_classify_weather": "weather_classification",
    "_safe_analyze_depth": "depth_estimation",
    "_safe_detect_vehicle_damage": "vehicle_damage",
    "_safe_run_scene_ocr_frame": "scene_ocr_frame",
    "_safe_segment_person_clothing": "clothing_segmentation",
    "_safe_clip_scene_classify": "clip_scene_classification",
    "_safe_clip_threat_match": "clip_threat_matching",
    "_extract_batch_attributes": "_florence",
}


def _keys(names: list[str]) -> list[str]:
    return [KEY_OF.get(n, n) for n in names]


def groups() -> list[tuple[list[str], int, float | None]]:
    """Phase-1 bounded_gather groups only: shipped gives a per-task
    ``task_timeout`` to the GPU/CPU groups (L2672-2693) and none to phase 2/3."""
    return [
        (_keys(b.names), b.limit, b.task_timeout) for b in REC["bg"] if b.task_timeout is not None
    ]


def florence_cascade() -> list[Any]:
    return [reason for (model, reason) in REC["cascade"] if model == "florence2"]


def task_names() -> list[str]:
    """Every phase-1 task that reached a bounded_gather call, in phase1 key terms."""
    return _keys([n for b in REC["bg"] for n in b.names if not n.startswith("<")])


def logs() -> list[tuple[Any, tuple]]:
    return [(r.msg, r.args) for r in _LOG_RECORDS]


def phase1_span() -> dict:
    """Attrs of the last ``super_phase_start`` span that lists the task names.

    Shipped emits the span once per super-phase (L2641-2649) — the call that
    carries ``phase1_tasks`` (a ", ".join of the shipped insertion order) is the
    one that pins the schedule.
    """
    for name, attrs in reversed(REC["spans"]):
        if name == "enrichment_pipeline.super_phase_start" and attrs and "phase1_tasks" in attrs:
            return attrs
    raise AssertionError("no super_phase_start span with a phase1_tasks attribute")


# ---------------------------------------------------------------------------
# log capture fixture (real logger + handler + DEBUG)
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True, scope="module")
def _restore_module_globals():
    """The spies above must be installed at import time (the ep_plugin snapshot of
    the live module dict happens before each test body, so installing later would
    leave a mutant body pointing at the unscreened originals) — this puts the
    module back for any file that runs after this one in a combined session.

    ``bounded_gather`` is deliberately NOT restored here: the slot is held by the
    shared dispatcher, which batch26_02 also depends on, so writing a "real"
    function back into it would silently disarm the other file (the exact
    cross-file clobber this refactor removed).  The dispatcher is behaviour-
    preserving for shipped code and for later files' own patches (a file that
    patches the slot replaces the dispatcher outright and restores it on exit), so
    leaving it installed is the safe state — deactivate + reset is all this file
    owes.
    """
    try:
        yield
    finally:
        M.record_cascade_model_deferred = _REAL_CASCADE
        M.add_span_event = _REAL_SPAN
        M.observe_enrichment_pipeline_stage = _REAL_STAGE
        _BG_STATE["active"] = False
        _reset()


@pytest.fixture(autouse=True)
def _bg_gate():
    """Record gathers only during THIS file's tests (setup True / teardown
    False), so ``REC["bg"]`` is as exact per test as it was when this file owned
    the slot alone."""
    _BG_STATE["active"] = True
    try:
        yield
    finally:
        _BG_STATE["active"] = False
        assert not recorder_errors(_BG_STATE), recorder_errors(_BG_STATE)


@pytest.fixture
def logs_on():
    lvl = M.logger.level
    _LOG_RECORDS.clear()
    M.logger.addHandler(_CAPTURE_HANDLER)
    M.logger.setLevel(logging.DEBUG)
    try:
        yield _LOG_RECORDS
    finally:
        M.logger.removeHandler(_CAPTURE_HANDLER)
        M.logger.setLevel(lvl)
        _LOG_RECORDS.clear()


# ===========================================================================
# A) cascade debug log record — shipped L2392-2398
#    keys: mutmut_37..48
# ===========================================================================
CASCADE_TEMPLATE = "Cascade: %d detections — %d persons, %d vehicles, %d animals"


def test_cascade_debug_record_is_lazily_formatted_with_four_counts(logs_on):
    """Shipped L2392-2398 is the module's FIRST log call, and it passes the shipped
    template VERBATIM plus the 4-count arg tuple in shipped positional order.

    Every shape of this family is visible on the record itself: a mutated/removed
    template shows up in ``record.msg``, a dropped argument shifts the tuple, and an
    argument swapped for ``None`` only shows up once the record is actually
    formatted — ``%``-formatting is lazy, so it takes a real handler (or an explicit
    ``getMessage()``) to raise the ``TypeError`` that shipped code never sees
    because it runs at INFO.
    """
    p = pipeline()
    run(p, dets=[])
    assert logs_on, "shipped emits the cascade debug record first"
    rec = logs_on[0]
    assert rec.msg == CASCADE_TEMPLATE
    assert rec.args == (0, 0, 0, 0)
    assert rec.getMessage() == "Cascade: 0 detections — 0 persons, 0 vehicles, 0 animals"

    logs_on.clear()
    p = pipeline()
    run(p, dets=[det("person"), det("car"), det("dog")])
    assert logs_on, "shipped emits the cascade debug record first"
    rec = logs_on[0]
    assert rec.msg == CASCADE_TEMPLATE
    assert rec.args == (3, 1, 1, 1)
    assert rec.getMessage() == "Cascade: 3 detections — 1 persons, 1 vehicles, 1 animals"


# ===========================================================================
# B) face_detection gate — shipped L2404
#    keys: mutmut_51
# ===========================================================================
def test_face_detection_requires_flag_and_persons():
    """``if self.face_detection_enabled and persons`` — BOTH are required."""
    p = pipeline(face_detection_enabled=True)
    run(p, dets=[det("car")])
    assert scheduled("_safe_detect_faces") == []

    p = pipeline(face_detection_enabled=False)
    run(p, dets=[det("person")])
    assert scheduled("_safe_detect_faces") == []

    p = pipeline(face_detection_enabled=True)
    run(p, dets=[det("person")], images={"i": 1})
    calls = scheduled("_safe_detect_faces")
    assert len(calls) == 1
    (args, kwargs) = calls[0]
    assert kwargs == {}
    assert len(args) == 2
    assert [d.class_name for d in args[0]] == ["person"]
    assert args[1] == {"i": 1}
    assert "face_detection" in p1keys()


# ===========================================================================
# C) license_plate gate + args — shipped L2406-2416
#    keys: mutmut_59, 70, 71
# ===========================================================================
def test_license_plate_gate_and_call_signature():
    """``if self.license_plate_enabled and vehicles`` -> ``_safe_detect_license_plates(vehicles, images)``."""
    p = pipeline(license_plate_enabled=True)
    run(p, dets=[det("person")])
    assert scheduled("_safe_detect_license_plates") == []
    assert scheduled("_is_fast_alpr_available") == []

    p = pipeline(license_plate_enabled=False)
    run(p, dets=[det("car")])
    assert scheduled("_safe_detect_license_plates") == []

    images = {None: "path/to/img.jpg"}
    p = pipeline(license_plate_enabled=True)
    v = det("car", did=11)
    run(p, dets=[v], images=images)
    calls = scheduled("_safe_detect_license_plates")
    assert len(calls) == 1
    (args, kwargs) = calls[0]
    assert kwargs == {}
    assert args[0] is not None and args[0] is not images
    assert [d.id for d in args[0]] == [11]
    assert args[1] is images
    assert REC["sync"]["_is_fast_alpr_available"] == [((), {})]
    assert "license_plate_detection" in p1keys()


# ===========================================================================
# D) violence full-frame argument — shipped L2417-2418
#    keys: mutmut_80
# ===========================================================================
def test_violence_detection_receives_the_full_frame():
    """``_safe_detect_violence(pil_image)`` — the frame object itself, not None."""
    img = frame()
    p = pipeline(violence_detection_enabled=True)
    run(p, image=img, dets=[det("person", did=1), det("person", did=2)])
    calls = scheduled("_safe_detect_violence")
    assert len(calls) == 1
    (args, kwargs) = calls[0]
    assert kwargs == {}
    assert args == (img,)
    assert awaited("_safe_detect_violence") == [((img,), {})]
    assert "violence_detection" in p1keys()

    # shipped gate needs >= 2 persons
    p = pipeline(violence_detection_enabled=True)
    run(p, image=img, dets=[det("person")])
    assert scheduled("_safe_detect_violence") == []


# ===========================================================================
# E) unified person task — shipped L2429-2432
#    keys: mutmut_82, 83, 86
# ===========================================================================
def test_service_unified_person_task_key_and_args():
    """``phase1_tasks["unified_person_enrichment"] = _enrich_persons_via_unified_service(persons, pil_image, camera_id, result)``."""
    img = frame()
    p = pipeline(use_enrichment_service=True)
    result = run(p, image=img, dets=[det("person", did=5)], camera_id="cam4")
    assert "unified_person_enrichment" in p1keys()
    calls = scheduled("_enrich_persons_via_unified_service")
    assert len(calls) == 1
    (args, kwargs) = calls[0]
    assert kwargs == {}
    assert [d.id for d in args[0]] == [5]
    assert args[1] is img
    assert args[2] == "cam4"
    assert args[3] is result
    assert awaited("_enrich_persons_via_unified_service") == calls


# ===========================================================================
# F) unified vehicle task — shipped L2435-2442
#    keys: mutmut_98, 99
# ===========================================================================
def test_service_unified_vehicle_task_key_and_args():
    """``phase1_tasks["unified_vehicle_enrichment"] = _enrich_vehicles_via_unified_service(vehicles, pil_image, result)``."""
    img = frame()
    p = pipeline(
        use_enrichment_service=True, vehicle_classification_enabled=True, _quality_level="standard"
    )
    result = run(p, image=img, dets=[det("car", did=6)])
    assert "unified_vehicle_enrichment" in p1keys()
    calls = scheduled("_enrich_vehicles_via_unified_service")
    assert len(calls) == 1
    (args, kwargs) = calls[0]
    assert kwargs == {}
    assert [d.id for d in args[0]] == [6]
    assert args[1] is img
    assert args[2] is result
    assert awaited("_enrich_vehicles_via_unified_service") == calls

    p = pipeline(
        use_enrichment_service=True, vehicle_classification_enabled=True, _quality_level="minimal"
    )
    run(p, image=img, dets=[det("car")])
    assert "unified_vehicle_enrichment" not in p1keys()


# ===========================================================================
# G) unified animal task — shipped L2445-2452
#    keys: mutmut_112, 113
# ===========================================================================
def test_service_unified_animal_task_key_and_args():
    """``phase1_tasks["unified_animal_enrichment"] = _enrich_animals_via_unified_service(animals, pil_image, result)``."""
    img = frame()
    p = pipeline(
        use_enrichment_service=True, pet_classification_enabled=True, _quality_level="standard"
    )
    result = run(p, image=img, dets=[det("dog", did=7)])
    assert "unified_animal_enrichment" in p1keys()
    calls = scheduled("_enrich_animals_via_unified_service")
    assert len(calls) == 1
    (args, kwargs) = calls[0]
    assert kwargs == {}
    assert [d.id for d in args[0]] == [7]
    assert args[1] is img
    assert args[2] is result
    assert awaited("_enrich_animals_via_unified_service") == calls

    p = pipeline(
        use_enrichment_service=True, pet_classification_enabled=True, _quality_level="minimal"
    )
    run(p, image=img, dets=[det("dog")])
    assert "unified_animal_enrichment" not in p1keys()


# ===========================================================================
# H) service pose task — shipped L2462-2465
#    keys: mutmut_121, 122, 123, 124, 125, 126, 127
# ===========================================================================
def test_service_pose_task_key_and_args():
    """``phase1_tasks["pose_estimation"] = self._estimate_poses_via_service(persons, pil_image)``."""
    img = frame()
    p = pipeline(use_enrichment_service=True, pose_estimation_enabled=True)
    run(p, image=img, dets=[det("person", did=3)])
    assert "pose_estimation" in p1keys()
    calls = scheduled("_estimate_poses_via_service")
    assert len(calls) == 1
    (args, kwargs) = calls[0]
    assert kwargs == {}
    assert [d.id for d in args[0]] == [3]
    assert args[1] is img
    assert len(args) == 2
    assert awaited("_estimate_poses_via_service") == calls

    p = pipeline(use_enrichment_service=True, pose_estimation_enabled=False)
    run(p, image=img, dets=[det("person")])
    assert "pose_estimation" not in p1keys()


# ===========================================================================
# I) service threat task — shipped L2466-2467
#    keys: mutmut_128, 129, 130, 131
# ===========================================================================
def test_service_threat_task_ignores_the_reid_flag_and_uses_the_frame():
    """``if persons: phase1_tasks["threat_detection"] = self._detect_threats_via_service(pil_image)``."""
    img = frame()
    p = pipeline(use_enrichment_service=True, reid_enabled=False)
    run(p, image=img, dets=[det("person")])
    assert "threat_detection" in p1keys()
    calls = scheduled("_detect_threats_via_service")
    assert calls == [((img,), {})]
    assert awaited("_detect_threats_via_service") == calls

    p = pipeline(use_enrichment_service=True)
    run(p, image=img, dets=[det("car")])
    assert "threat_detection" not in p1keys()


# ===========================================================================
# J) service reid gate — shipped L2468-2471
#    keys: mutmut_132
# ===========================================================================
def test_service_reid_requires_flag_and_persons():
    """``if self.reid_enabled and persons`` -> ``_compute_reid_via_service(high_conf_detections, pil_image, result)``."""
    img = frame()
    p = pipeline(use_enrichment_service=True, reid_enabled=True)
    run(p, image=img, dets=[det("car")])
    assert scheduled("_compute_reid_via_service") == []

    p = pipeline(use_enrichment_service=True, reid_enabled=False)
    run(p, image=img, dets=[det("person")])
    assert scheduled("_compute_reid_via_service") == []

    p = pipeline(use_enrichment_service=True, reid_enabled=True)
    result = run(p, image=img, dets=[det("person", did=8)])
    calls = scheduled("_compute_reid_via_service")
    assert len(calls) == 1
    (args, kwargs) = calls[0]
    assert kwargs == {}
    assert [d.id for d in args[0]] == [8]
    assert args[1] is img
    assert args[2] is result
    assert "reid_via_service" in p1keys()


# ===========================================================================
# K) local pose args — shipped L2478-2479
#    keys: mutmut_137, 138
# ===========================================================================
def test_local_pose_task_args():
    """``phase1_tasks["pose_estimation"] = self._safe_estimate_poses(persons, pil_image)``."""
    img = frame()
    p = pipeline(pose_estimation_enabled=True)
    run(p, image=img, dets=[det("person", did=4)])
    calls = scheduled("_safe_estimate_poses")
    assert len(calls) == 1
    (args, kwargs) = calls[0]
    assert kwargs == {}
    assert [d.id for d in args[0]] == [4]
    assert args[1] is img
    assert len(args) == 2
    assert awaited("_safe_estimate_poses") == calls
    assert "pose_estimation" in p1keys()


# ===========================================================================
# L) clothing gate — shipped L2485-2492
#    keys: mutmut_142
# ===========================================================================
def test_clothing_classification_requires_flag_persons_and_standard():
    """``clothing_classification_enabled and persons and _should_run_for_quality("standard")``."""
    for enabled, dets, level, expected in (
        (True, [], "standard", False),
        (False, [det("person")], "standard", False),
        (True, [det("person")], "minimal", False),
        (True, [det("person")], "standard", True),
    ):
        p = pipeline(clothing_classification_enabled=enabled, _quality_level=level)
        run(p, dets=dets)
        assert ("clothing_classification" in p1keys()) is expected, (enabled, level)


# ===========================================================================
# M) demographics gate + task — shipped L2509-2514
#    keys: mutmut_178, 179, 183, 184, 185, 186, 187, 188, 189
# ===========================================================================
def test_demographics_either_flag_and_persons_and_task_args():
    """``(age_enabled or gender_enabled) and persons and _should_run_for_quality("standard")``
    -> ``phase1_tasks["demographics"] = self._safe_classify_demographics(persons, pil_image)``."""
    img = frame()
    # OR of the two flags: either one alone is enough ...
    for age, gender in ((True, False), (False, True)):
        p = pipeline(
            age_classification_enabled=age,
            gender_classification_enabled=gender,
            _quality_level="standard",
        )
        run(p, image=img, dets=[det("person", did=9)])
        assert "demographics" in p1keys(), (age, gender)
    # ... but neither flag is not
    p = pipeline(
        age_classification_enabled=False,
        gender_classification_enabled=False,
        _quality_level="standard",
    )
    run(p, image=img, dets=[det("person")])
    assert "demographics" not in p1keys()
    # persons are required even with a flag on
    p = pipeline(
        age_classification_enabled=True,
        gender_classification_enabled=False,
        _quality_level="standard",
    )
    run(p, image=img, dets=[])
    assert "demographics" not in p1keys()
    assert scheduled("_safe_classify_demographics") == []
    # and so is standard quality
    p = pipeline(age_classification_enabled=True, _quality_level="minimal")
    run(p, image=img, dets=[det("person")])
    assert "demographics" not in p1keys()

    # task value: the call itself, with (persons, pil_image)
    p = pipeline(age_classification_enabled=True, _quality_level="standard")
    run(p, image=img, dets=[det("person", did=9)])
    calls = scheduled("_safe_classify_demographics")
    assert len(calls) == 1
    (args, kwargs) = calls[0]
    assert kwargs == {}
    assert [d.id for d in args[0]] == [9]
    assert args[1] is img
    assert len(args) == 2
    assert awaited("_safe_classify_demographics") == calls


# ===========================================================================
# N) osnet_reid gate + task — shipped L2517-2518
#    keys: mutmut_190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 200, 201
# ===========================================================================
def test_osnet_gate_is_a_full_conjunction_and_the_task_carries_persons():
    """``if self.osnet_reid_enabled and persons and self._should_run_for_quality("standard")``."""
    img = frame()
    for enabled, npeople, level, expected in (
        (True, 1, "standard", True),
        (False, 1, "standard", False),
        (True, 0, "standard", False),
        (True, 1, "minimal", False),
        (False, 0, "minimal", False),
    ):
        p = pipeline(osnet_reid_enabled=enabled, _quality_level=level)
        run(p, image=img, dets=[det("person", did=1 + i) for i in range(npeople)])
        assert ("osnet_reid" in p1keys()) is expected, (enabled, npeople, level)

    p = pipeline(osnet_reid_enabled=True, _quality_level="standard")
    run(p, image=img, dets=[det("person", did=9)])
    calls = scheduled("_safe_extract_osnet_embeddings")
    assert len(calls) == 1
    (args, kwargs) = calls[0]
    assert kwargs == {}
    assert [d.id for d in args[0]] == [9]
    assert args[1] is img
    assert len(args) == 2
    assert awaited("_safe_extract_osnet_embeddings") == calls


# ===========================================================================
# O) smoke/fire task — shipped L2522-2525 ("runs on EVERY frame")
#    keys: mutmut_202, 203, 204, 205, 206, 207, 208
# ===========================================================================
def test_smoke_fire_is_unconditional_and_carries_frame_and_camera():
    """``if self.smoke_fire_detection_enabled: phase1_tasks["smoke_fire_detection"] = self._safe_detect_smoke_fire(pil_image, camera_id)``."""
    img = frame()
    p = pipeline(smoke_fire_detection_enabled=True, _quality_level="minimal")
    run(p, image=img, dets=[], camera_id="cam5")
    assert "smoke_fire_detection" in p1keys()
    calls = scheduled("_safe_detect_smoke_fire")
    assert calls == [((img, "cam5"), {})]
    assert awaited("_safe_detect_smoke_fire") == calls
    # quality level does not gate it
    assert task_names().count("smoke_fire_detection") == 1

    p = pipeline(smoke_fire_detection_enabled=False)
    run(p, image=img, dets=[det("person")], camera_id="cam5")
    assert "smoke_fire_detection" not in p1keys()


# ===========================================================================
# P) yolo-world gate + task — shipped L2528-2535
#    keys: mutmut_210, 214, 215, 216, 217, 218, 219, 220
# ===========================================================================
def test_yolo_world_requires_flag_detections_and_standard():
    """``yolo_world_enabled and high_conf_detections and _should_run_for_quality("standard")``
    -> ``_safe_detect_yolo_world(pil_image, high_conf_detections)``."""
    img = frame()
    for enabled, npeople, level, expected in (
        (True, 0, "standard", False),
        (False, 1, "standard", False),
        (True, 1, "minimal", False),
        (True, 1, "standard", True),
    ):
        p = pipeline(yolo_world_enabled=enabled, _quality_level=level)
        run(p, image=img, dets=[det("person", did=1 + i) for i in range(npeople)])
        assert ("yolo_world_detection" in p1keys()) is expected, (enabled, npeople, level)

    p = pipeline(yolo_world_enabled=True, _quality_level="standard")
    d = det("person", did=12)
    run(p, image=img, dets=[d])
    calls = scheduled("_safe_detect_yolo_world")
    assert len(calls) == 1
    (args, kwargs) = calls[0]
    assert kwargs == {}
    assert args[0] is img
    assert [x.id for x in args[1]] == [12]
    assert len(args) == 2
    assert awaited("_safe_detect_yolo_world") == calls


# ===========================================================================
# Q) image_quality gate + args — shipped L2536-2537
#    keys: mutmut_222, 223, 224, 228, 229
# ===========================================================================
def test_image_quality_needs_standard_quality_and_frame_plus_camera():
    """``if self.image_quality_enabled and self._should_run_for_quality("standard")``
    -> ``_safe_assess_image_quality(pil_image, camera_id)``."""
    img = frame()
    p = pipeline(image_quality_enabled=True, _quality_level="standard")
    run(p, image=img, dets=[], camera_id="cam6")
    assert "image_quality" in p1keys()
    calls = scheduled("_safe_assess_image_quality")
    assert calls == [((img, "cam6"), {})]
    assert awaited("_safe_assess_image_quality") == calls

    p = pipeline(image_quality_enabled=True, _quality_level="minimal")
    run(p, image=img, dets=[], camera_id="cam6")
    assert "image_quality" not in p1keys()
    assert scheduled("_safe_assess_image_quality") == []


# ===========================================================================
# R) weather gate + args — shipped L2538-2539
#    keys: mutmut_233, 234, 235, 239
# ===========================================================================
def test_weather_gate_needs_standard_and_task_gets_the_frame():
    """``if self.weather_classification_enabled and self._should_run_for_quality("standard")``
    -> ``phase1_tasks["weather_classification"] = self._safe_classify_weather(pil_image)``."""
    img = frame()
    p = pipeline(weather_classification_enabled=True, _quality_level="standard")
    run(p, image=img, dets=[])
    assert "weather_classification" in p1keys()
    assert scheduled("_safe_classify_weather") == [((img,), {})]
    assert awaited("_safe_classify_weather") == [((img,), {})]

    p = pipeline(weather_classification_enabled=True, _quality_level="minimal")
    run(p, image=img, dets=[])
    assert "weather_classification" not in p1keys()
    assert scheduled("_safe_classify_weather") == []


# ===========================================================================
# S) depth_estimation gate + args — shipped L2540-2548
#    keys: mutmut_240, 242, 246, 248, 249, 250, 251
# ===========================================================================
def test_depth_estimation_is_local_path_only_and_needs_detections_and_standard():
    """``depth_estimation_enabled and high_conf_detections and _should_run_for_quality("standard") and not use_enrichment_service``
    -> ``_safe_analyze_depth(high_conf_detections, pil_image)``."""
    img = frame()
    # shipped: every one of the four conjuncts is required
    p = pipeline(depth_estimation_enabled=True, _quality_level="standard")
    run(p, image=img, dets=[])
    assert "depth_estimation" not in p1keys()

    p = pipeline(
        depth_estimation_enabled=True, use_enrichment_service=True, _quality_level="standard"
    )
    run(p, image=img, dets=[det("person")])
    assert "depth_estimation" not in p1keys()

    p = pipeline(
        depth_estimation_enabled=True, use_enrichment_service=True, _quality_level="minimal"
    )
    run(p, image=img, dets=[det("person")])
    assert "depth_estimation" not in p1keys()
    assert scheduled("_safe_analyze_depth") == []

    p = pipeline(depth_estimation_enabled=True, _quality_level="minimal")
    run(p, image=img, dets=[det("person")])
    assert "depth_estimation" not in p1keys()

    p = pipeline(depth_estimation_enabled=True, _quality_level="standard")
    d = det("person", did=13)
    run(p, image=img, dets=[d])
    assert "depth_estimation" in p1keys()
    calls = scheduled("_safe_analyze_depth")
    assert len(calls) == 1
    (args, kwargs) = calls[0]
    assert kwargs == {}
    assert [x.id for x in args[0]] == [13]
    assert args[1] is img
    assert len(args) == 2
    assert awaited("_safe_analyze_depth") == calls


# ===========================================================================
# T) vehicle_damage gate — shipped L2549-2554
#    keys: mutmut_255
# ===========================================================================
def test_vehicle_damage_requires_vehicles():
    """``vehicle_damage_detection_enabled and vehicles and _should_run_for_quality("standard")``."""
    for enabled, dets, expected in (
        (True, [det("person")], False),
        (False, [det("car")], False),
        (True, [det("car")], True),
    ):
        p = pipeline(vehicle_damage_detection_enabled=enabled, _quality_level="standard")
        run(p, dets=dets)
        assert ("vehicle_damage" in p1keys()) is expected, (enabled, dets)


# ===========================================================================
# U) scene_ocr_frame gate + args — shipped L2555-2556
#    keys: mutmut_266, 267, 268, 269, 270, 271, 272, 273
# ===========================================================================
def test_scene_ocr_frame_needs_flag_and_standard_and_gets_the_frame():
    """``if self.scene_ocr_enabled and self._should_run_for_quality("standard")``
    -> ``phase1_tasks["scene_ocr_frame"] = self._safe_run_scene_ocr_frame(pil_image)``."""
    img = frame()
    p = pipeline(scene_ocr_enabled=True, _quality_level="standard")
    run(p, image=img, dets=[])
    assert "scene_ocr_frame" in p1keys()
    assert scheduled("_safe_run_scene_ocr_frame") == [((img,), {})]
    assert awaited("_safe_run_scene_ocr_frame") == [((img,), {})]

    p = pipeline(scene_ocr_enabled=True, _quality_level="minimal")
    run(p, image=img, dets=[])
    assert "scene_ocr_frame" not in p1keys()
    assert scheduled("_safe_run_scene_ocr_frame") == []

    p = pipeline(scene_ocr_enabled=False, _quality_level="standard")
    run(p, image=img, dets=[det("person")])
    assert "scene_ocr_frame" not in p1keys()
    assert scheduled("_safe_run_scene_ocr_frame") == []


# ===========================================================================
# V) clothing_segmentation gate — shipped L2559
#    keys: mutmut_274, 275, 276, 277, 278
# ===========================================================================
def test_clothing_segmentation_full_quality_conjunction():
    """``if self.clothing_segmentation_enabled and persons and self._should_run_for_quality("full")``."""
    for enabled, npeople, level, expected in (
        (True, 1, "full", True),
        (False, 1, "full", False),
        (True, 0, "full", False),
        (True, 1, "standard", False),
        (False, 1, "standard", False),
        (False, 0, "full", False),
    ):
        p = pipeline(clothing_segmentation_enabled=enabled, _quality_level=level)
        run(p, dets=[det("person", did=1 + i) for i in range(npeople)])
        assert ("clothing_segmentation" in p1keys()) is expected, (enabled, npeople, level)


# ===========================================================================
# W) CLIP scene classification task — shipped L2563-2564
#    keys: mutmut_290, 291, 292, 293
# ===========================================================================
def test_clip_scene_classification_task_key_and_frame_argument():
    """``if self.reid_enabled and self._should_run_for_quality("full"): phase1_tasks["clip_scene_classification"] = self._safe_clip_scene_classify(pil_image)``."""
    img = frame()
    p = pipeline(reid_enabled=True, _quality_level="full")
    run(p, image=img, dets=[])
    assert "clip_scene_classification" in p1keys()
    assert scheduled("_safe_clip_scene_classify") == [((img,), {})]
    assert awaited("_safe_clip_scene_classify") == [((img,), {})]

    p = pipeline(reid_enabled=True, _quality_level="standard")
    run(p, image=img, dets=[])
    assert "clip_scene_classification" not in p1keys()


# ===========================================================================
# X) CLIP threat matching task — shipped L2565-2566
#    keys: mutmut_298, 299, 300, 301
# ===========================================================================
def test_clip_threat_matching_task_key_and_frame_argument():
    """``if self.reid_enabled and self._should_run_for_quality("full"): phase1_tasks["clip_threat_matching"] = self._safe_clip_threat_match(pil_image)``."""
    img = frame()
    p = pipeline(reid_enabled=True, _quality_level="full")
    run(p, image=img, dets=[])
    assert "clip_threat_matching" in p1keys()
    assert scheduled("_safe_clip_threat_match") == [((img,), {})]
    assert awaited("_safe_clip_threat_match") == [((img,), {})]

    p = pipeline(reid_enabled=False, _quality_level="full")
    run(p, image=img, dets=[])
    assert "clip_threat_matching" not in p1keys()


# ===========================================================================
# Y) Florence-2 default sentinel + confidence threshold — shipped L2572-2573,
#    L2580-2582, L2606-2608
#    keys: mutmut_302, 304, 311
# ===========================================================================
def test_florence_threshold_is_exclusive_and_the_default_is_the_none_sentinel():
    """``florence_task = None`` then ``ambiguous = [d for d in hcd if d.confidence < 0.7]``;
    an empty ambiguous list takes the ``else`` branch and leaves the sentinel
    alone, so ``add_span_event(..., "florence_enabled": florence_task is not None)``
    reports False and no extraction is scheduled."""
    p = pipeline(vision_extraction_enabled=True, _quality_level="standard")
    run(p, image=frame(), dets=[det("person", conf=0.7, did=21)])
    assert scheduled("_extract_batch_attributes") == []
    assert ("florence2", "all_high_confidence") in REC["cascade"]
    # nothing to run at all: the shipped guard ``if phase1_tasks or florence_task:``
    # is False, so the super-phase START span event (the one that carries the
    # task list / florence_enabled, L2641-2649) is never emitted — only the
    # unconditional completion event is
    assert [n for (n, _a) in REC["spans"]] == ["enrichment_pipeline.super_phase_complete"]
    assert task_names() == []
    assert REC["errors"] == []

    # 0.6999999 is ambiguous -> extraction runs and florence_enabled flips
    p = pipeline(vision_extraction_enabled=True, _quality_level="standard")
    run(p, image=frame(), dets=[det("person", conf=0.699999, did=22)])
    assert len(scheduled("_extract_batch_attributes")) == 1
    span = phase1_span()
    assert span["florence_enabled"] is True
    assert span["phase1_task.count"] == 0
    assert task_names() == ["_florence"]

    # a detection at 0.9 is above the shipped 0.7 threshold -> skipped entirely;
    # the threshold constant is 0.7, not 1.7
    p = pipeline(vision_extraction_enabled=True, _quality_level="standard")
    run(p, image=frame(), dets=[det("person", conf=0.9, did=23)])
    assert scheduled("_extract_batch_attributes") == []
    assert ("florence2", "all_high_confidence") in REC["cascade"]

    # with a real phase-1 task present the super-phase does run, and shipped
    # still reports florence_enabled False: the "no florence" state is the None
    # sentinel, and it is NOT handed to bounded_gather as a schedulable task
    p = pipeline(vision_extraction_enabled=True, scene_ocr_enabled=True, _quality_level="standard")
    run(p, image=frame(), dets=[det("person", conf=0.7, did=24)])
    span = phase1_span()
    assert span["florence_enabled"] is False
    assert task_names() == ["scene_ocr_frame"]
    assert REC["errors"] == []


# ===========================================================================
# Z) Florence-2 gate — shipped L2574-2578
#    keys: mutmut_305, 306
# ===========================================================================
def test_florence_gate_requires_flag_frame_and_standard_quality():
    """``if self.vision_extraction_enabled and pil_image and self._should_run_for_quality("standard")``."""
    p = pipeline(vision_extraction_enabled=True, _quality_level="minimal")
    run(p, image=frame(), dets=[det("person", conf=0.5)])
    assert scheduled("_extract_batch_attributes") == []
    assert florence_cascade() == []
    assert task_names() == []

    p = pipeline(vision_extraction_enabled=False, _quality_level="standard")
    run(p, image=frame(), dets=[det("person", conf=0.5)])
    assert scheduled("_extract_batch_attributes") == []

    p = pipeline(vision_extraction_enabled=True, _quality_level="standard")
    run(p, image=None, dets=[det("person", conf=0.5)])
    assert scheduled("_extract_batch_attributes") == []

    # positive control: shipped really does schedule it at standard quality
    p = pipeline(vision_extraction_enabled=True, _quality_level="standard")
    run(p, image=frame(), dets=[det("person", conf=0.5)])
    assert len(scheduled("_extract_batch_attributes")) == 1


# ===========================================================================
# AA) Florence det_dicts payload — shipped L2584-2595
#     keys: mutmut_312, 313
# ===========================================================================
def test_florence_detection_payload_shape():
    """``det_dicts`` is a list of ``{class_name, confidence, bbox, detection_id}``
    dicts built from the ambiguous detections, with ``str(d.id) if d.id else str(i)``
    as the id fallback, passed as the 2nd positional argument of
    ``self._vision_extractor.extract_batch_attributes(pil_image, det_dicts)``."""
    img = frame()
    p = pipeline(vision_extraction_enabled=True, _quality_level="standard")
    run(p, image=img, dets=[det("person", conf=0.5, did=7), det("car", conf=0.4, did=None)])
    calls = scheduled("_extract_batch_attributes")
    assert len(calls) == 1
    (args, kwargs) = calls[0]
    assert kwargs == {}
    assert args[0] is img
    assert args[1] == [
        {"class_name": "person", "confidence": 0.5, "bbox": (0, 0, 10, 10), "detection_id": "7"},
        {"class_name": "car", "confidence": 0.4, "bbox": (0, 0, 10, 10), "detection_id": "1"},
    ]
    assert awaited("_extract_batch_attributes") == calls


# ===========================================================================
# BB) whole-super-phase assembly: partition, order, limits, timeouts
#     (kills any remaining task-name rename / value replacement by diffing the
#     exact shipped task schedule; also pins the measured GPU/CPU split)
#     keys: 45 (syntax-level), and re-disposes the rename/value family above
# ===========================================================================
def test_full_local_super_phase_task_schedule_partition_and_timeouts():
    """Shipped super-phase with everything enabled at "full" quality and one
    person/vehicle/animal detection: 16 phase-1 tasks in shipped insertion
    order, split into the GPU group (limit 2, timeout ``_pipeline_timeout *
    0.7`` = 21.0) and the CPU group (limit 5, timeout ``* 0.5`` = 15.0)."""
    img = frame()
    p = pipeline(
        face_detection_enabled=True,
        license_plate_enabled=True,
        violence_detection_enabled=True,
        pose_estimation_enabled=True,
        clothing_classification_enabled=True,
        vehicle_classification_enabled=True,
        pet_classification_enabled=True,
        age_classification_enabled=True,
        osnet_reid_enabled=True,
        smoke_fire_detection_enabled=True,
        yolo_world_enabled=True,
        weather_classification_enabled=True,
        scene_ocr_enabled=True,
        clothing_segmentation_enabled=True,
        vehicle_damage_detection_enabled=True,
        reid_enabled=True,
        vision_extraction_enabled=True,
        household_matching_enabled=True,
        _quality_level="full",
    )
    run(
        p,
        image=img,
        dets=[
            det("person", conf=0.9, did=1),
            det("car", conf=0.9, did=2),
            det("dog", conf=0.9, did=3),
        ],
        camera_id="cam1",
    )

    assert p1keys() == [
        # shipped reassembly (L2700-2708): the GPU group's keys first, in GPU
        # schedule order, then the CPU group's keys
        "face_detection",
        "license_plate_detection",
        "pose_estimation",
        "demographics",
        "smoke_fire_detection",
        "yolo_world_detection",
        "clothing_segmentation",
        "clip_scene_classification",
        "clip_threat_matching",
        "clothing_classification",
        "vehicle_classification",
        "pet_classification",
        "osnet_reid",
        "weather_classification",
        "vehicle_damage",
        "scene_ocr_frame",
    ]
    assert groups() == [
        (
            [
                "face_detection",
                "license_plate_detection",
                "pose_estimation",
                "demographics",
                "smoke_fire_detection",
                "yolo_world_detection",
                "clothing_segmentation",
                "clip_scene_classification",
                "clip_threat_matching",
            ],
            2,
            21.0,
        ),
        (
            [
                "clothing_classification",
                "vehicle_classification",
                "pet_classification",
                "osnet_reid",
                "weather_classification",
                "vehicle_damage",
                "scene_ocr_frame",
            ],
            5,
            15.0,
        ),
    ]
    # every scheduled task was actually awaited (kills "= None" value swaps)
    assert REC["errors"] == []
    assert len(REC["calls"]) == 16 + 2  # 16 phase-1 + scene_ocr_crop + household
    span = phase1_span()
    assert span["phase1_task.count"] == 16
    assert span["phase1_tasks"] == ", ".join(
        [
            "face_detection",
            "license_plate_detection",
            "pose_estimation",
            "clothing_classification",
            "vehicle_classification",
            "pet_classification",
            "demographics",
            "osnet_reid",
            "smoke_fire_detection",
            "yolo_world_detection",
            "weather_classification",
            "vehicle_damage",
            "scene_ocr_frame",
            "clothing_segmentation",
            "clip_scene_classification",
            "clip_threat_matching",
        ]
    )
    assert span["use_enrichment_service"] is False
    assert span["florence_enabled"] is False
    assert [n for (n, _a) in REC["spans"]][-1] == "enrichment_pipeline.super_phase_complete"
