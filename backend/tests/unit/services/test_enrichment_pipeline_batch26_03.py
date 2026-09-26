"""Chunk-03 kill battery — backend/services/enrichment_pipeline mutation survivors.

Every assertion was PROBED against pristine shipped source
(`git show HEAD:backend/services/enrichment_pipeline.py`) and pins what shipped code
ACTUALLY does. Shipped line numbers are cited in verdicts_03.json.

Seams used (each verified visible to ep_plugin-injected variant bodies):
  * pipeline workers      -> stubbed on the instance (`self.X` lookup at call time)
  * log `extra={...}`     -> own logging.Handler on M.logger; `extra` keys surface as
                             direct LogRecord attributes (no __extra__ anywhere)
  * prometheus metrics    -> patch backend.core.metrics.ENRICHMENT_MODEL_DURATION /
                             ENRICHMENT_MODEL_ERRORS_TOTAL (the real metric helpers
                             look these up at call time; mutants call the helpers)
  * OTel span attributes  -> patch backend.core.telemetry.get_current_span
  * module-level inference fns (classify_weather / assess_image_quality) are patched
                             in a MODULE-scoped autouse fixture so the replacement is
                             already in M.__dict__ when the plugin snapshots module
                             globals for the mutant. (Measured: a patch applied inside
                             a test body is NOT observed by a variant body.)

Groups g06/g07/g08 (`_should_run_for_quality("full")` -> None / "XXfullXX" / "FULL")
carry NO test on purpose: they are provably value-identical to shipped — see
verdicts_03.json for the reachability argument.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from PIL import Image

import backend.core.metrics as MET
import backend.core.telemetry as TEL
import backend.services.enrichment_pipeline as M

# ---------------------------------------------------------------------- plumbing

_MISSING = "<MISSING>"

# LogRecord's own bookkeeping + what backend.core.logging's filter/formatter injects.
_STD_ATTRS = set(logging.LogRecord("n", 0, "p", 0, "m", (), {}).__dict__) | {
    "request_id",
    "correlation_id",
    "trace_id",
    "span_id",
    "connection_id",
    "task_id",
    "job_id",
    "hostname",
    "container_id",
    "app_version",
    "environment",
    "message",
    "taskName",
    "asctime",
    "extras",
}


@contextmanager
def _logs():
    """Capture M.logger records on our own handler (immune to conftest propagation)."""
    recs: list[logging.LogRecord] = []

    class _H(logging.Handler):
        def emit(self, record):
            recs.append(record)

    h = _H()
    old_lvl, old_prop = M.logger.level, M.logger.propagate
    M.logger.addHandler(h)
    M.logger.setLevel(logging.DEBUG)
    M.logger.propagate = False
    try:
        yield recs
    finally:
        M.logger.removeHandler(h)
        M.logger.setLevel(old_lvl)
        M.logger.propagate = old_prop


def _rec(recs, needle):
    for r in recs:
        if needle in r.getMessage():
            return r
    raise AssertionError(
        f"no record matching {needle!r}; got {[r.getMessage()[:70] for r in recs]}"
    )


def _attr(rec, key):
    """A shipped `extra=` key surfaces as a direct attribute on the record."""
    return getattr(rec, key, _MISSING)


def _extras(rec):
    return {k: v for k, v in rec.__dict__.items() if k not in _STD_ATTRS}


@contextmanager
def _metrics():
    dur, errs = MagicMock(), MagicMock()
    with (
        patch.object(MET, "ENRICHMENT_MODEL_DURATION", dur),
        patch.object(MET, "ENRICHMENT_MODEL_ERRORS_TOTAL", errs),
    ):
        yield dur, errs


def _labels(handle):
    return [c.kwargs["model"] for c in handle.labels.call_args_list]


def _obs(handle):
    return [c.args[0] for c in handle.labels.return_value.observe.call_args_list]


# Module-level inference seams (see module docstring for why these are module-scoped).
_SEAM: dict[str, object | None] = {"wx": None, "qual": None}


async def _fake_weather(model_data, image):
    return _SEAM["wx"]


async def _fake_quality(model_data, image, *a, **k):
    return _SEAM["qual"]


@pytest.fixture(scope="module", autouse=True)
def _inference_seams():
    with (
        patch.object(M, "classify_weather", new=_fake_weather),
        patch.object(M, "assess_image_quality", new=_fake_quality),
    ):
        yield


def _det(cls, det_id, conf=0.9):
    return M.DetectionInput(
        id=det_id,
        class_name=cls,
        confidence=conf,
        bbox=M.BoundingBox(x1=1, y1=2, x2=20, y2=30),
    )


def _mm(exc=None):
    """model_manager whose `load(...)` async context raises `exc` on __aenter__."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(side_effect=exc) if exc else AsyncMock(return_value={"k": 1})
    cm.__aexit__ = AsyncMock(return_value=False)
    mm = MagicMock()
    mm.load = MagicMock(return_value=cm)
    return mm


# ------------------------------------------------------- _run_parallel_enrichment seam

_OFF = dict(
    face_detection_enabled=False,
    license_plate_enabled=False,
    ocr_enabled=False,
    vision_extraction_enabled=False,
    violence_detection_enabled=False,
    reid_enabled=False,
    scene_change_enabled=False,
    scene_ocr_enabled=False,
    household_matching_enabled=False,
    smoke_fire_detection_enabled=False,
    yolo_world_enabled=False,
    osnet_reid_enabled=False,
    clothing_segmentation_enabled=False,
    vehicle_damage_detection_enabled=False,
    depth_estimation_enabled=False,
    image_quality_enabled=False,
    weather_classification_enabled=False,
    action_recognition_enabled=False,
    low_light_enhancement_enabled=False,
    pose_estimation_enabled=False,
    clothing_classification_enabled=False,
    vehicle_classification_enabled=False,
    pet_classification_enabled=False,
    age_classification_enabled=False,
    gender_classification_enabled=False,
    redis_client=None,
    use_enrichment_service=False,
)
_SPY = (
    "_safe_classify_vehicle_types",
    "_safe_classify_pets",
    "_safe_classify_person_clothing",
    "_safe_classify_demographics",
    "_safe_estimate_poses",
    "_safe_clip_scene_classify",
    "_safe_clip_threat_match",
    "_safe_detect_faces",
    "_safe_extract_osnet_embeddings",
    "_enrich_persons_via_unified_service",
    "_enrich_vehicles_via_unified_service",
    "_enrich_animals_via_unified_service",
    "_estimate_poses_via_service",
    "_detect_threats_via_service",
    "_compute_reid_via_service",
)


def _rpe_pipeline(over):
    cfg = dict(_OFF)
    quality = over.pop("_quality", "full")
    dets = over.pop("_dets", [])
    florence = over.pop("_florence", False)
    cfg.update(over)
    if florence:
        cfg["vision_extraction_enabled"] = True
    p = M.EnrichmentPipeline(model_manager=MagicMock(), **cfg)
    p._quality_level = quality
    chosen: list[str] = []

    def spy(name):
        async def _s(*a, **k):
            chosen.append(name)
            return None

        return _s

    for n in _SPY:
        setattr(p, n, spy(n))
    p._process_phase1_results = MagicMock()

    async def _flo(*a, **k):
        return None

    if florence:
        cfg["vision_extraction_enabled"] = True
        p.vision_extraction_enabled = True
        p._vision_extractor = MagicMock(extract_batch_attributes=lambda *a, **k: _flo())
    return p, chosen, dets


async def _rpe(**over):
    """Names of the phase-1 workers _run_parallel_enrichment actually scheduled."""
    p, chosen, dets = _rpe_pipeline(over)
    await p._run_parallel_enrichment(
        M.EnrichmentResult(), Image.new("RGB", (8, 8)), list(dets), {}, "cam-1"
    )
    return sorted(chosen)


async def _span_events(**over):
    """{event name -> attributes} for the two super-phase span events."""
    p, _chosen, dets = _rpe_pipeline(over)
    span = MagicMock()
    # Hermeticity: test_batch26_05 installs import-time spies on
    # M.add_span_event (restored only around its own module's tests), so in
    # a combined run our call site would hit THEIR recorder and the span
    # mock would see nothing (KeyError on the event dict). Bind ep's global
    # back to the real telemetry fn for this window — same production path,
    # TEL.get_current_span-patched below is what the real fn reads.
    with (
        patch.object(TEL, "get_current_span", autospec=True, return_value=span),
        patch.object(M, "add_span_event", TEL.add_span_event),
    ):
        await p._run_parallel_enrichment(
            M.EnrichmentResult(), Image.new("RGB", (8, 8)), list(dets), {}, "cam-1"
        )
    out: dict[str, dict] = {}
    for c in span.add_event.call_args_list:
        attrs = c.kwargs.get("attributes") or (c.args[1] if len(c.args) > 1 else {})
        out[c.args[0]] = dict(attrs)
    return out


_START_EV = "enrichment_pipeline.super_phase_start"
_DONE_EV = "enrichment_pipeline.super_phase_complete"


# ----------------------------------------------------------- via-service helper


def _svc_client(**meth_kw):
    c = MagicMock()
    for name in ("classify_vehicle", "classify_pet", "classify_clothing"):
        setattr(c, name, AsyncMock(**meth_kw))
    return c


def _svc_pipe(client):
    p = M.EnrichmentPipeline(model_manager=MagicMock(), use_enrichment_service=True)
    p._enrichment_client = client
    p._crop_to_bbox = AsyncMock(return_value=Image.new("RGB", (4, 4)))
    return p


# ============================================================ g00 (L2436 | L2494)
@pytest.mark.asyncio
async def test_g00_vehicle_gate_requires_flag_and_vehicles():
    """shipped: the vehicle task needs the flag AND vehicles (L2436/L2494)."""
    car = [_det("car", 1)]
    assert await _rpe(use_enrichment_service=True, _dets=car) == []
    assert await _rpe(_dets=car) == []


# ============================================================ g01 (L2446 | L2502)
@pytest.mark.asyncio
async def test_g01_animal_gate_requires_animals():
    """shipped: the animal task needs `animals` — flag + full quality alone is not enough."""
    car = [_det("car", 1)]
    assert await _rpe(use_enrichment_service=True, pet_classification_enabled=True, _dets=car) == []
    assert await _rpe(pet_classification_enabled=True, _dets=car) == []


# ============================================================ g02 (L2446 | L2502)
@pytest.mark.asyncio
async def test_g02_animal_gate_requires_flag():
    """shipped: the animal task needs pet_classification_enabled."""
    dog = [_det("dog", 1)]
    assert await _rpe(use_enrichment_service=True, _dets=dog) == []
    assert await _rpe(_dets=dog) == []


# ============================================================ g03 (L2462 | L2478)
@pytest.mark.asyncio
async def test_g03_pose_gate_requires_flag():
    """shipped: the pose task needs pose_estimation_enabled on both paths (L2462/L2478)."""
    person = [_det("person", 1)]
    assert await _rpe(use_enrichment_service=True, _dets=person) == [
        "_detect_threats_via_service",
        "_enrich_persons_via_unified_service",
    ]
    assert await _rpe(_dets=person) == []


# ============================================================ g04 (L2486 | L2510)
@pytest.mark.asyncio
async def test_g04_person_tier_gates_require_persons():
    """shipped: clothing (L2486) and demographics (L2510) gates need `persons`."""
    assert await _rpe(clothing_classification_enabled=True, age_classification_enabled=True) == []


# ============================================================ g05 (L2563 | L2565)
@pytest.mark.asyncio
async def test_g05_clip_gates_require_reid_flag_and_full_quality():
    """shipped: CLIP scene/threat need reid_enabled AND full quality."""
    assert await _rpe() == []
    assert await _rpe(reid_enabled=True, _quality="minimal") == []
    assert await _rpe(reid_enabled=True) == [
        "_safe_clip_scene_classify",
        "_safe_clip_threat_match",
    ]


# ============================================================ g09 (L2646 | L2745)
@pytest.mark.asyncio
async def test_g09_super_phase_florence_key():
    """shipped: both super-phase span events carry the key "florence_enabled"."""
    off = await _span_events(pose_estimation_enabled=True, _dets=[_det("person", 1)])
    on = await _span_events(_florence=True, _dets=[_det("person", 1, 0.5)])
    for ev in (_START_EV, _DONE_EV):
        assert "florence_enabled" in off[ev], (ev, sorted(off[ev]))
        assert "florence_enabled" in on[ev], (ev, sorted(on[ev]))


# ============================================================ g10 (L2646 | L2745)
@pytest.mark.asyncio
async def test_g10_super_phase_florence_key_is_lowercase():
    """shipped spelling is exactly "florence_enabled" — never FLORENCE_ENABLED."""
    off = await _span_events(pose_estimation_enabled=True, _dets=[_det("person", 1)])
    on = await _span_events(_florence=True, _dets=[_det("person", 1, 0.5)])
    for ev in (_START_EV, _DONE_EV):
        assert "FLORENCE_ENABLED" not in off[ev] and "FLORENCE_ENABLED" not in on[ev]
        assert "florence_enabled" in on[ev]


# ============================================================ g11 (L2646 | L2745)
@pytest.mark.asyncio
async def test_g11_super_phase_florence_enabled_tracks_task_presence():
    """shipped: florence_enabled is True exactly when the Florence task was created."""
    off = await _span_events(pose_estimation_enabled=True, _dets=[_det("person", 1)])
    on = await _span_events(_florence=True, _dets=[_det("person", 1, 0.5)])
    assert off[_START_EV]["florence_enabled"] is False
    assert off[_DONE_EV]["florence_enabled"] is False
    assert on[_START_EV]["florence_enabled"] is True
    assert on[_DONE_EV]["florence_enabled"] is True


# ================================================= g12 _classify_person_clothing (L6629|L6709)
@pytest.mark.asyncio
async def test_g12_clothing_error_category_key():
    """shipped: MODEL_ZOO-miss and parse clothing extras carry "error_category"."""
    p = M.EnrichmentPipeline(model_manager=_mm(KeyError("fashion-clip")))
    with _logs() as recs:
        assert (
            await p._classify_person_clothing([_det("person", 1)], Image.new("RGB", (32, 32))) == {}
        )
    assert (
        _attr(_rec(recs, "fashion-clip model not available in MODEL_ZOO"), "error_category")
        == M.ErrorCategory.PARSE_ERROR.value
    )

    p2 = M.EnrichmentPipeline(model_manager=_mm(TypeError("bad")))
    with _logs() as recs2:
        assert (
            await p2._classify_person_clothing([_det("person", 1)], Image.new("RGB", (32, 32)))
            == {}
        )
    assert (
        _attr(_rec(recs2, "Clothing classification parse error"), "error_category")
        == M.ErrorCategory.PARSE_ERROR.value
    )


# ================================================= g13 _classify_person_clothing (L6629|L6709)
@pytest.mark.asyncio
async def test_g13_clothing_error_category_is_snake_case():
    """shipped key is "error_category", never "ERROR_CATEGORY", at both clothing handlers."""
    p = M.EnrichmentPipeline(model_manager=_mm(KeyError("fashion-clip")))
    with _logs() as recs:
        await p._classify_person_clothing([_det("person", 1)], Image.new("RGB", (32, 32)))
    assert "ERROR_CATEGORY" not in _extras(_rec(recs, "fashion-clip model not available"))

    p2 = M.EnrichmentPipeline(model_manager=_mm(TypeError("bad")))
    with _logs() as recs2:
        await p2._classify_person_clothing([_det("person", 1)], Image.new("RGB", (32, 32)))
    ex2 = _extras(_rec(recs2, "Clothing classification parse error"))
    assert "ERROR_CATEGORY" not in ex2
    assert ex2.get("error_category") == M.ErrorCategory.PARSE_ERROR.value


# ===================================================== g26 _map_unified (L3910 | L4019)
def test_g26_unified_mapping_all_scores_is_empty_dict():
    """shipped: mapped clothing/vehicle results get all_scores={} — never None."""
    p = M.EnrichmentPipeline(model_manager=MagicMock())
    res = M.EnrichmentResult()
    clo = SimpleNamespace(
        categories=[{"category": "jacket", "confidence": 0.7}], is_suspicious=False
    )
    u = SimpleNamespace(
        pose=None,
        clothing=clo,
        demographics=None,
        threat=None,
        reid_embedding=None,
        action=None,
        pet=None,
        depth=None,
        vehicle=None,
    )
    p._map_unified_to_enrichment_result(res, "1", u, "person")
    assert res.clothing_classifications["1"].all_scores == {}

    v = SimpleNamespace(color="red", make="ford", model="focus", type="car", confidence=0.8)
    u2 = SimpleNamespace(
        pose=None,
        clothing=None,
        demographics=None,
        threat=None,
        reid_embedding=None,
        action=None,
        pet=None,
        depth=None,
        vehicle=v,
    )
    p._map_unified_to_enrichment_result(res, "9", u2, "vehicle")
    mapped = res.vehicle_classifications["9"]
    assert mapped.all_scores == {}
    assert mapped.vehicle_type == "car" and mapped.display_name == "red ford focus car"


# ===================================================== g14/g15 _classify_pets (L7170|L7250)
@pytest.mark.asyncio
async def test_g14_pets_error_category_key():
    """shipped: MODEL_ZOO-miss and parse pet extras carry "error_category"."""
    p = M.EnrichmentPipeline(model_manager=_mm(KeyError("pet-classifier")))
    with _logs() as recs:
        assert await p._classify_pets([_det("dog", 1)], Image.new("RGB", (32, 32))) == {}
    assert (
        _attr(_rec(recs, "pet-classifier model not available in MODEL_ZOO"), "error_category")
        == M.ErrorCategory.PARSE_ERROR.value
    )

    p2 = M.EnrichmentPipeline(model_manager=_mm(TypeError("bad")))
    with _logs() as recs2:
        assert await p2._classify_pets([_det("dog", 1)], Image.new("RGB", (32, 32))) == {}
    assert (
        _attr(_rec(recs2, "Pet classification parse error"), "error_category")
        == M.ErrorCategory.PARSE_ERROR.value
    )


@pytest.mark.asyncio
async def test_g15_pets_error_category_is_snake_case():
    """shipped pet handlers use "error_category", never "ERROR_CATEGORY"."""
    p = M.EnrichmentPipeline(model_manager=_mm(KeyError("pet-classifier")))
    with _logs() as recs:
        await p._classify_pets([_det("dog", 1)], Image.new("RGB", (32, 32)))
    assert "ERROR_CATEGORY" not in _extras(_rec(recs, "pet-classifier model not available"))

    p2 = M.EnrichmentPipeline(model_manager=_mm(TypeError("bad")))
    with _logs() as recs2:
        await p2._classify_pets([_det("dog", 1)], Image.new("RGB", (32, 32)))
    ex = _extras(_rec(recs2, "Pet classification parse error"))
    assert "ERROR_CATEGORY" not in ex
    assert ex.get("error_category") == M.ErrorCategory.PARSE_ERROR.value


# ==================================== g16/g17 _classify_pets (L7179 unavailable | L7194 connect)
@pytest.mark.asyncio
async def test_g16_pets_unavailable_extra_payload():
    """shipped: the two transient pet handlers pass detection_type/operation/error_type."""
    p = M.EnrichmentPipeline(model_manager=_mm(M.EnrichmentUnavailableError("down")))
    with _logs() as recs:
        await p._classify_pets([_det("dog", 1)], Image.new("RGB", (32, 32)))
    ex = _extras(_rec(recs, "Pet classification service unavailable"))
    assert ex.get("detection_type") == "animal"
    assert ex.get("operation") == "pet_classification"
    assert ex.get("error_type") == "EnrichmentUnavailableError"

    p2 = M.EnrichmentPipeline(model_manager=_mm(httpx.ConnectError("refused")))
    with _logs() as recs2:
        await p2._classify_pets([_det("dog", 1)], Image.new("RGB", (32, 32)))
    ex2 = _extras(_rec(recs2, "Pet classification connection failed"))
    assert ex2.get("detection_type") == "animal"
    assert ex2.get("operation") == "pet_classification"
    assert ex2.get("error_type") == "ConnectError"


@pytest.mark.asyncio
async def test_g17_pets_unavailable_extra_keyword_present():
    """shipped: both transient pet handlers log WITH an extra= dict (never bare)."""
    p = M.EnrichmentPipeline(model_manager=_mm(M.EnrichmentUnavailableError("down")))
    with _logs() as recs:
        await p._classify_pets([_det("dog", 1)], Image.new("RGB", (32, 32)))
    assert (
        _attr(_rec(recs, "Pet classification service unavailable"), "operation")
        == "pet_classification"
    )

    p2 = M.EnrichmentPipeline(model_manager=_mm(httpx.ConnectError("refused")))
    with _logs() as recs2:
        await p2._classify_pets([_det("dog", 1)], Image.new("RGB", (32, 32)))
    assert _attr(_rec(recs2, "Pet classification connection failed"), "is_transient") is True


# ==================================== g18/g19 _classify_pets (L7179 | L7194 error_category)
@pytest.mark.asyncio
async def test_g18_pets_transient_error_category_key():
    """shipped: both transient pet extras carry "error_category"=service_unavailable."""
    p = M.EnrichmentPipeline(model_manager=_mm(M.EnrichmentUnavailableError("down")))
    with _logs() as recs:
        await p._classify_pets([_det("dog", 1)], Image.new("RGB", (32, 32)))
    assert (
        _attr(_rec(recs, "Pet classification service unavailable"), "error_category")
        == M.ErrorCategory.SERVICE_UNAVAILABLE.value
    )

    p2 = M.EnrichmentPipeline(model_manager=_mm(httpx.ConnectError("refused")))
    with _logs() as recs2:
        await p2._classify_pets([_det("dog", 1)], Image.new("RGB", (32, 32)))
    assert (
        _attr(_rec(recs2, "Pet classification connection failed"), "error_category")
        == M.ErrorCategory.SERVICE_UNAVAILABLE.value
    )


@pytest.mark.asyncio
async def test_g19_pets_transient_error_category_is_snake_case():
    """shipped spelling is "error_category" in both transient pet handlers."""
    p = M.EnrichmentPipeline(model_manager=_mm(M.EnrichmentUnavailableError("down")))
    with _logs() as recs:
        await p._classify_pets([_det("dog", 1)], Image.new("RGB", (32, 32)))
    assert "ERROR_CATEGORY" not in _extras(_rec(recs, "Pet classification service unavailable"))

    p2 = M.EnrichmentPipeline(model_manager=_mm(httpx.ConnectError("refused")))
    with _logs() as recs2:
        await p2._classify_pets([_det("dog", 1)], Image.new("RGB", (32, 32)))
    ex = _extras(_rec(recs2, "Pet classification connection failed"))
    assert "ERROR_CATEGORY" not in ex
    assert ex.get("error_category") == M.ErrorCategory.SERVICE_UNAVAILABLE.value


# ================================= g20-g25 _classify_vehicle_types (L6846/6926/6858/6870)
@pytest.mark.asyncio
async def test_g20_vehicle_error_category_key():
    """shipped: MODEL_ZOO-miss and parse vehicle extras carry "error_category"."""
    p = M.EnrichmentPipeline(model_manager=_mm(KeyError("vehicle-segment-classification")))
    with _logs() as recs:
        assert await p._classify_vehicle_types([_det("car", 1)], Image.new("RGB", (32, 32))) == {}
    assert (
        _attr(
            _rec(recs, "vehicle-segment-classification model not available in MODEL_ZOO"),
            "error_category",
        )
        == M.ErrorCategory.PARSE_ERROR.value
    )

    p2 = M.EnrichmentPipeline(model_manager=_mm(TypeError("bad")))
    with _logs() as recs2:
        assert await p2._classify_vehicle_types([_det("car", 1)], Image.new("RGB", (32, 32))) == {}
    assert (
        _attr(_rec(recs2, "Vehicle classification parse error"), "error_category")
        == M.ErrorCategory.PARSE_ERROR.value
    )


@pytest.mark.asyncio
async def test_g21_vehicle_error_category_is_snake_case():
    """shipped vehicle handlers use "error_category", never "ERROR_CATEGORY"."""
    p = M.EnrichmentPipeline(model_manager=_mm(KeyError("vehicle-segment-classification")))
    with _logs() as recs:
        await p._classify_vehicle_types([_det("car", 1)], Image.new("RGB", (32, 32)))
    assert "ERROR_CATEGORY" not in _extras(
        _rec(recs, "vehicle-segment-classification model not available")
    )

    p2 = M.EnrichmentPipeline(model_manager=_mm(TypeError("bad")))
    with _logs() as recs2:
        await p2._classify_vehicle_types([_det("car", 1)], Image.new("RGB", (32, 32)))
    ex = _extras(_rec(recs2, "Vehicle classification parse error"))
    assert "ERROR_CATEGORY" not in ex
    assert ex.get("error_category") == M.ErrorCategory.PARSE_ERROR.value


@pytest.mark.asyncio
async def test_g22_vehicle_unavailable_extra_payload():
    """shipped: the two transient vehicle handlers pass detection_type/operation/error_type."""
    p = M.EnrichmentPipeline(model_manager=_mm(M.EnrichmentUnavailableError("down")))
    with _logs() as recs:
        await p._classify_vehicle_types([_det("car", 1)], Image.new("RGB", (32, 32)))
    ex = _extras(_rec(recs, "Vehicle classification service unavailable"))
    assert ex.get("detection_type") == "vehicle"
    assert ex.get("operation") == "vehicle_classification"
    assert ex.get("error_type") == "EnrichmentUnavailableError"

    p2 = M.EnrichmentPipeline(model_manager=_mm(httpx.ConnectError("refused")))
    with _logs() as recs2:
        await p2._classify_vehicle_types([_det("car", 1)], Image.new("RGB", (32, 32)))
    ex2 = _extras(_rec(recs2, "Vehicle classification connection failed"))
    assert ex2.get("detection_type") == "vehicle"
    assert ex2.get("operation") == "vehicle_classification"
    assert ex2.get("error_type") == "ConnectError"


@pytest.mark.asyncio
async def test_g23_vehicle_unavailable_extra_keyword_present():
    """shipped: both transient vehicle handlers log WITH an extra= dict (never bare)."""
    p = M.EnrichmentPipeline(model_manager=_mm(M.EnrichmentUnavailableError("down")))
    with _logs() as recs:
        await p._classify_vehicle_types([_det("car", 1)], Image.new("RGB", (32, 32)))
    assert (
        _attr(_rec(recs, "Vehicle classification service unavailable"), "operation")
        == "vehicle_classification"
    )

    p2 = M.EnrichmentPipeline(model_manager=_mm(httpx.ConnectError("refused")))
    with _logs() as recs2:
        await p2._classify_vehicle_types([_det("car", 1)], Image.new("RGB", (32, 32)))
    assert _attr(_rec(recs2, "Vehicle classification connection failed"), "is_transient") is True


@pytest.mark.asyncio
async def test_g24_vehicle_transient_error_category_key():
    """shipped: both transient vehicle extras carry "error_category"."""
    p = M.EnrichmentPipeline(model_manager=_mm(M.EnrichmentUnavailableError("down")))
    with _logs() as recs:
        await p._classify_vehicle_types([_det("car", 1)], Image.new("RGB", (32, 32)))
    assert (
        _attr(_rec(recs, "Vehicle classification service unavailable"), "error_category")
        == M.ErrorCategory.SERVICE_UNAVAILABLE.value
    )

    p2 = M.EnrichmentPipeline(model_manager=_mm(httpx.ConnectError("refused")))
    with _logs() as recs2:
        await p2._classify_vehicle_types([_det("car", 1)], Image.new("RGB", (32, 32)))
    assert (
        _attr(_rec(recs2, "Vehicle classification connection failed"), "error_category")
        == M.ErrorCategory.SERVICE_UNAVAILABLE.value
    )


@pytest.mark.asyncio
async def test_g25_vehicle_transient_error_category_is_snake_case():
    """shipped spelling is "error_category" in both transient vehicle handlers."""
    p = M.EnrichmentPipeline(model_manager=_mm(M.EnrichmentUnavailableError("down")))
    with _logs() as recs:
        await p._classify_vehicle_types([_det("car", 1)], Image.new("RGB", (32, 32)))
    assert "ERROR_CATEGORY" not in _extras(_rec(recs, "Vehicle classification service unavailable"))

    p2 = M.EnrichmentPipeline(model_manager=_mm(httpx.ConnectError("refused")))
    with _logs() as recs2:
        await p2._classify_vehicle_types([_det("car", 1)], Image.new("RGB", (32, 32)))
    ex = _extras(_rec(recs2, "Vehicle classification connection failed"))
    assert "ERROR_CATEGORY" not in ex
    assert ex.get("error_category") == M.ErrorCategory.SERVICE_UNAVAILABLE.value


# =========================================== g27-g37 _classify_clothing_via_service
# two shipped occurrences per shape: L4813 handler (unavailable group) and L4865 handler
# (unexpected). Message needles: "Enrichment service unavailable for person {id}" /
# "Clothing classification unexpected error for {id}: ...".
_CLOTH_RAISES = (M.EnrichmentUnavailableError("down"), RuntimeError("kaboom"))


def _cloth(exc):
    return _svc_pipe(_svc_client(side_effect=exc))


@pytest.mark.asyncio
async def test_g27_clothing_duration_label():
    """shipped: both clothing error handlers observe duration under "clothing-via-service"."""
    for exc in _CLOTH_RAISES:
        with _metrics() as (dur, _e):
            assert (
                await _cloth(exc)._classify_clothing_via_service(
                    [_det("person", 7)], Image.new("RGB", (32, 32))
                )
                == {}
            )
        assert _labels(dur) == ["clothing-via-service"]


@pytest.mark.asyncio
async def test_g28_clothing_duration_label_not_decorated():
    """shipped duration label has no XX-decoration (L4815/L4867)."""
    for exc in _CLOTH_RAISES:
        with _metrics() as (dur, _e):
            await _cloth(exc)._classify_clothing_via_service(
                [_det("person", 7)], Image.new("RGB", (32, 32))
            )
        assert _labels(dur) == ["clothing-via-service"]


@pytest.mark.asyncio
async def test_g29_clothing_duration_label_is_lowercase():
    """shipped duration label is lower-case, never CLOTHING-VIA-SERVICE (L4815/L4867)."""
    for exc in _CLOTH_RAISES:
        with _metrics() as (dur, _e):
            await _cloth(exc)._classify_clothing_via_service(
                [_det("person", 7)], Image.new("RGB", (32, 32))
            )
        assert "CLOTHING-VIA-SERVICE" not in _labels(dur)
        assert _labels(dur) == ["clothing-via-service"]


@pytest.mark.asyncio
async def test_g30_clothing_duration_is_elapsed():
    """shipped: duration = perf_counter() - start_time, a small elapsed span (L4815/L4867)."""
    for exc in _CLOTH_RAISES:
        with _metrics() as (dur, _e):
            await _cloth(exc)._classify_clothing_via_service(
                [_det("person", 7)], Image.new("RGB", (32, 32))
            )
        obs = _obs(dur)
        assert len(obs) == 1 and 0.0 <= obs[0] < 60.0, obs


@pytest.mark.asyncio
async def test_g31_clothing_error_label():
    """shipped: both clothing error handlers bump the error counter for "clothing-via-service"."""
    for exc in _CLOTH_RAISES:
        with _metrics() as (_d, errs):
            await _cloth(exc)._classify_clothing_via_service(
                [_det("person", 7)], Image.new("RGB", (32, 32))
            )
        assert _labels(errs) == ["clothing-via-service"]


@pytest.mark.asyncio
async def test_g32_clothing_error_label_not_decorated():
    """shipped error label has no XX-decoration (L4817/L4869)."""
    for exc in _CLOTH_RAISES:
        with _metrics() as (_d, errs):
            await _cloth(exc)._classify_clothing_via_service(
                [_det("person", 7)], Image.new("RGB", (32, 32))
            )
        assert _labels(errs) == ["clothing-via-service"]


@pytest.mark.asyncio
async def test_g33_clothing_error_label_is_lowercase():
    """shipped error label is lower-case (L4817/L4869)."""
    for exc in _CLOTH_RAISES:
        with _metrics() as (_d, errs):
            await _cloth(exc)._classify_clothing_via_service(
                [_det("person", 7)], Image.new("RGB", (32, 32))
            )
        assert "CLOTHING-VIA-SERVICE" not in _labels(errs)
        assert _labels(errs) == ["clothing-via-service"]


@pytest.mark.asyncio
async def test_g34_clothing_handler_extra_payload():
    """shipped: the two handler log calls pass service/error_type/detection_id (L4820/L4872)."""
    with _logs() as recs:
        await _cloth(M.EnrichmentUnavailableError("down"))._classify_clothing_via_service(
            [_det("person", 7)], Image.new("RGB", (32, 32))
        )
    ex = _extras(_rec(recs, "Enrichment service unavailable for person 7"))
    assert ex.get("service") == "clothing-via-service"
    assert ex.get("detection_id") == "7"
    assert ex.get("error_type") == "EnrichmentUnavailableError"

    with _logs() as recs2:
        await _cloth(RuntimeError("kaboom"))._classify_clothing_via_service(
            [_det("person", 7)], Image.new("RGB", (32, 32))
        )
    ex2 = _extras(_rec(recs2, "Clothing classification unexpected error for 7"))
    assert ex2.get("service") == "clothing-via-service"
    assert ex2.get("detection_id") == "7"
    assert ex2.get("error_type") == "RuntimeError"


@pytest.mark.asyncio
async def test_g35_clothing_error_type_key():
    """shipped: handler extras key is exactly "error_type" (L4822/L4874)."""
    with _logs() as recs:
        await _cloth(M.EnrichmentUnavailableError("down"))._classify_clothing_via_service(
            [_det("person", 7)], Image.new("RGB", (32, 32))
        )
    assert (
        _attr(_rec(recs, "Enrichment service unavailable for person 7"), "error_type")
        == "EnrichmentUnavailableError"
    )

    with _logs() as recs2:
        await _cloth(RuntimeError("kaboom"))._classify_clothing_via_service(
            [_det("person", 7)], Image.new("RGB", (32, 32))
        )
    assert (
        _attr(_rec(recs2, "Clothing classification unexpected error for 7"), "error_type")
        == "RuntimeError"
    )


@pytest.mark.asyncio
async def test_g36_clothing_error_type_is_snake_case():
    """shipped extras key is "error_type", never "ERROR_TYPE" (L4822/L4874)."""
    with _logs() as recs:
        await _cloth(M.EnrichmentUnavailableError("down"))._classify_clothing_via_service(
            [_det("person", 7)], Image.new("RGB", (32, 32))
        )
    assert "ERROR_TYPE" not in _extras(_rec(recs, "Enrichment service unavailable for person 7"))

    with _logs() as recs2:
        await _cloth(RuntimeError("kaboom"))._classify_clothing_via_service(
            [_det("person", 7)], Image.new("RGB", (32, 32))
        )
    ex = _extras(_rec(recs2, "Clothing classification unexpected error for 7"))
    assert "ERROR_TYPE" not in ex
    assert ex.get("error_type") == "RuntimeError"


@pytest.mark.asyncio
async def test_g37_clothing_error_type_names_the_raised_error():
    """shipped: error_type is type(e).__name__ of the caught exception (L4822/L4874)."""
    exc = M.EnrichmentUnavailableError("down")
    with _logs() as recs:
        await _cloth(exc)._classify_clothing_via_service(
            [_det("person", 7)], Image.new("RGB", (32, 32))
        )
    assert (
        _attr(_rec(recs, "Enrichment service unavailable for person 7"), "error_type")
        == type(exc).__name__
    )

    with _logs() as recs2:
        await _cloth(RuntimeError("kaboom"))._classify_clothing_via_service(
            [_det("person", 7)], Image.new("RGB", (32, 32))
        )
    assert (
        _attr(_rec(recs2, "Clothing classification unexpected error for 7"), "error_type")
        == "RuntimeError"
    )


# ============================================= g38-g42 _classify_pets_via_service
# two shipped occurrences per shape: L4400 handler (unavailable group) and L4452 handler.
_PETS_RAISES = (M.EnrichmentUnavailableError("down"), RuntimeError("kaboom"))


def _pets(exc):
    return _svc_pipe(_svc_client(side_effect=exc))


@pytest.mark.asyncio
async def test_g38_pets_svc_duration_label():
    """shipped: both pet error handlers observe duration under "pet-via-service"."""
    for exc in _PETS_RAISES:
        with _metrics() as (dur, _e):
            assert (
                await _pets(exc)._classify_pets_via_service(
                    [_det("dog", 3)], Image.new("RGB", (32, 32))
                )
                == {}
            )
        assert _labels(dur) == ["pet-via-service"]


@pytest.mark.asyncio
async def test_g39_pets_svc_duration_label_not_decorated():
    """shipped duration label has no XX-decoration (L4402/L4454)."""
    for exc in _PETS_RAISES:
        with _metrics() as (dur, _e):
            await _pets(exc)._classify_pets_via_service(
                [_det("dog", 3)], Image.new("RGB", (32, 32))
            )
        assert _labels(dur) == ["pet-via-service"]


@pytest.mark.asyncio
async def test_g40_pets_svc_duration_label_is_lowercase():
    """shipped duration label is lower-case, never PET-VIA-SERVICE (L4402/L4454)."""
    for exc in _PETS_RAISES:
        with _metrics() as (dur, _e):
            await _pets(exc)._classify_pets_via_service(
                [_det("dog", 3)], Image.new("RGB", (32, 32))
            )
        assert "PET-VIA-SERVICE" not in _labels(dur)
        assert _labels(dur) == ["pet-via-service"]


@pytest.mark.asyncio
async def test_g41_pets_svc_duration_is_elapsed():
    """shipped: handler duration = perf_counter() - start_time, not a sum (L4402/L4454)."""
    for exc in _PETS_RAISES:
        with _metrics() as (dur, _e):
            await _pets(exc)._classify_pets_via_service(
                [_det("dog", 3)], Image.new("RGB", (32, 32))
            )
        obs = _obs(dur)
        assert len(obs) == 1 and 0.0 <= obs[0] < 60.0, obs


@pytest.mark.asyncio
async def test_g42_pets_svc_error_label():
    """shipped: both pet error handlers bump the error counter for "pet-via-service"."""
    for exc in _PETS_RAISES:
        with _metrics() as (_d, errs):
            await _pets(exc)._classify_pets_via_service(
                [_det("dog", 3)], Image.new("RGB", (32, 32))
            )
        assert _labels(errs) == ["pet-via-service"]


# ============================================ g43-g45 _classify_vehicle_via_service
# three shipped occurrences per shape: L4266/4267 success debug, L4284/4286 unavailable
# warning, L4336/4338 unexpected error.
_VEH_OK = dict(
    vehicle_type="car", confidence=0.9, display_name="red car", is_commercial=False, all_scores={}
)
_VEH_SITES = (
    (M.EnrichmentUnavailableError("down"), "Enrichment service unavailable for vehicle 4"),
    (RuntimeError("kaboom"), "Vehicle classification unexpected error for 4"),
)


def _veh(exc=None, result=None):
    return _svc_pipe(_svc_client(side_effect=exc, return_value=result))


@pytest.mark.asyncio
async def test_g43_vehicle_service_extra_service_value():
    """shipped: "service" is exactly "vehicle-via-service" at all three log sites."""
    with _logs() as recs:
        out = await _veh(result=MagicMock(**_VEH_OK))._classify_vehicle_via_service(
            [_det("car", 4)], Image.new("RGB", (32, 32))
        )
    assert out["4"].vehicle_type == "car"
    assert _attr(_rec(recs, "Vehicle 4 type (via service)"), "service") == "vehicle-via-service"
    for exc, needle in _VEH_SITES:
        with _logs() as r2:
            await _veh(exc=exc)._classify_vehicle_via_service(
                [_det("car", 4)], Image.new("RGB", (32, 32))
            )
        assert _attr(_rec(r2, needle), "service") == "vehicle-via-service", needle


@pytest.mark.asyncio
async def test_g44_vehicle_service_detection_id_key():
    """shipped: extras key is exactly "detection_id" at all three log sites."""
    with _logs() as recs:
        await _veh(result=MagicMock(**_VEH_OK))._classify_vehicle_via_service(
            [_det("car", 4)], Image.new("RGB", (32, 32))
        )
    assert _attr(_rec(recs, "Vehicle 4 type (via service)"), "detection_id") == "4"
    for exc, needle in _VEH_SITES:
        with _logs() as r2:
            await _veh(exc=exc)._classify_vehicle_via_service(
                [_det("car", 4)], Image.new("RGB", (32, 32))
            )
        assert _attr(_rec(r2, needle), "detection_id") == "4", needle


@pytest.mark.asyncio
async def test_g45_vehicle_service_detection_id_is_snake_case():
    """shipped extras key is "detection_id" — never DETECTION_ID / XXdetection_idXX."""
    with _logs() as recs:
        await _veh(result=MagicMock(**_VEH_OK))._classify_vehicle_via_service(
            [_det("car", 4)], Image.new("RGB", (32, 32))
        )
    assert "DETECTION_ID" not in _extras(_rec(recs, "Vehicle 4 type (via service)"))
    for exc, needle in _VEH_SITES:
        with _logs() as r2:
            await _veh(exc=exc)._classify_vehicle_via_service(
                [_det("car", 4)], Image.new("RGB", (32, 32))
            )
        ex = _extras(_rec(r2, needle))
        assert "DETECTION_ID" not in ex and "XXdetection_idXX" not in ex, needle
        assert ex.get("detection_id") == "4", needle


# ================================================== g46-g49 _assess_image_quality
# three shipped occurrences per shape: try-body L7076/7077, KeyError L7090/7091,
# RuntimeError L7096/7097.
class _QRes:
    is_low_quality = False
    quality_score = 55.0
    quality_issues: list = []


_QUALITY_SCENARIOS = (
    ("try-body", lambda: _mm()),
    ("keyerror", lambda: _mm(KeyError("brisque-quality"))),
    ("runtime", lambda: _mm(RuntimeError("exploded"))),
)


async def _run_quality(mm):
    _SEAM["qual"] = _QRes()
    p = M.EnrichmentPipeline(model_manager=mm, image_quality_enabled=True)
    res = None
    with _metrics() as (dur, errs):
        try:
            res = await p._assess_image_quality(Image.new("RGB", (8, 8)))
        except RuntimeError:
            pass
    return dur, errs, res


@pytest.mark.asyncio
async def test_g46_quality_duration_is_elapsed():
    """shipped: duration = perf_counter() - start_time at all three quality sites."""
    for name, mk in _QUALITY_SCENARIOS:
        dur, _errs, res = await _run_quality(mk())
        if name == "try-body":
            assert res is not None and res.quality_score == 55.0
        obs = _obs(dur)
        assert len(obs) == 1, (name, obs)
        assert 0.0 <= obs[0] < 60.0, (name, obs)


@pytest.mark.asyncio
async def test_g47_quality_label():
    """shipped: all three quality sites observe label "brisque-quality"."""
    for name, mk in _QUALITY_SCENARIOS:
        dur, _errs, _res = await _run_quality(mk())
        assert _labels(dur) == ["brisque-quality"], name


@pytest.mark.asyncio
async def test_g48_quality_label_not_decorated():
    """shipped quality label has no XX-decoration (L7077/7091/7097)."""
    for name, mk in _QUALITY_SCENARIOS:
        dur, _errs, _res = await _run_quality(mk())
        assert _labels(dur) == ["brisque-quality"], (name, _labels(dur))


@pytest.mark.asyncio
async def test_g49_quality_label_is_lowercase():
    """shipped quality label is lower-case, never BRISQUE-QUALITY (L7077/7091/7097)."""
    for name, mk in _QUALITY_SCENARIOS:
        dur, _errs, _res = await _run_quality(mk())
        assert "BRISQUE-QUALITY" not in _labels(dur), name
        assert _labels(dur) == ["brisque-quality"], name


# ==================================================== g50-g53 _classify_weather
# three shipped occurrences per shape: try-body L6555/6556, KeyError L6564/6565,
# generic except L6570/6571.
class _WRes:
    simple_condition = "clear"
    confidence = 0.77


_WEATHER_SCENARIOS = (
    ("try-body", lambda: _mm()),
    ("keyerror", lambda: _mm(KeyError("weather-classification"))),
    ("runtime", lambda: _mm(RuntimeError("exploded"))),
)


async def _run_weather(mm):
    _SEAM["wx"] = _WRes()
    p = M.EnrichmentPipeline(model_manager=mm, weather_classification_enabled=True)
    res = None
    with _metrics() as (dur, errs):
        try:
            res = await p._classify_weather(Image.new("RGB", (8, 8)))
        except RuntimeError:
            pass
    return dur, errs, res


@pytest.mark.asyncio
async def test_g50_weather_duration_is_elapsed():
    """shipped: duration = perf_counter() - start_time at all three weather sites."""
    for name, mk in _WEATHER_SCENARIOS:
        dur, _errs, res = await _run_weather(mk())
        if name == "try-body":
            assert res is not None and res.simple_condition == "clear"
        obs = _obs(dur)
        assert len(obs) == 1, (name, obs)
        assert 0.0 <= obs[0] < 60.0, (name, obs)


@pytest.mark.asyncio
async def test_g51_weather_label():
    """shipped: all three weather sites observe label "weather-classification"."""
    for name, mk in _WEATHER_SCENARIOS:
        dur, _errs, _res = await _run_weather(mk())
        assert _labels(dur) == ["weather-classification"], name


@pytest.mark.asyncio
async def test_g52_weather_label_not_decorated():
    """shipped weather label has no XX-decoration (L6556/6565/6571)."""
    for name, mk in _WEATHER_SCENARIOS:
        dur, _errs, _res = await _run_weather(mk())
        assert _labels(dur) == ["weather-classification"], (name, _labels(dur))


@pytest.mark.asyncio
async def test_g53_weather_label_is_lowercase():
    """shipped weather label is lower-case, never WEATHER-CLASSIFICATION (L6556/6565/6571)."""
    for name, mk in _WEATHER_SCENARIOS:
        dur, _errs, _res = await _run_weather(mk())
        assert "WEATHER-CLASSIFICATION" not in _labels(dur), name
        assert _labels(dur) == ["weather-classification"], name
