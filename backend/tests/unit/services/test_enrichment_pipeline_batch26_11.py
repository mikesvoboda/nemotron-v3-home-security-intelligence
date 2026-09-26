"""Chunk-11 kill battery: enrichment_pipeline vehicle-classification + unified mapper.

Two targets, all keys measured against pristine HEAD source (see
/tmp/wp-ep/probes/c11/probe*.py, outputs quoted in verdicts_11.json):

A) ``EnrichmentPipeline._classify_vehicle_types`` (shipped lines 6790-6943)
   - happy path: ``record_enrichment_model_call("vehicle")`` once, then
     ``"vehicle-segment-classification"`` once per classified vehicle;
     ``classify_vehicle(model_data, crop)`` positional; result value IS the
     object returned by ``classify_vehicle``; ``det_id`` = ``str(vehicle.id)``
     for truthy ids else ``str(loop_index)``;
     debug line ``"Vehicle {det_id} type: {vehicle_type} ({conf:.0%})"``.
   - one log record per exception handler with an exact message + exact
     ``extra`` payload (all values measured, e.g. the KeyError handler emits
     ``error_category="parse_error"`` and no ``error_type``/``is_transient``).
   - MEASURED shipped quirk: the ValueError/TypeError handler reports
     ``error_category="parse_error"`` (not validation_error) and
     ``is_transient=False``, while the catch-all Exception handler reports
     ``is_transient=True`` — pinned as shipped, not as "sensible".

B) ``EnrichmentPipeline._map_unified_to_enrichment_result`` (3850-4048)
   a pure in-memory mapper. Every ``detection_type`` gate and every
   ``dict.get`` default is pinned with the shipped value: clothing defaults
   ``("" , 0.0, "")`` when ``categories`` is empty, ``raw_description``
   falls back to ``top_cat``, ``display_name`` is a single-space join,
   ``is_commercial`` is the 5-name membership test, pet scores are 0.0 and
   ``is_household_pet`` defaults True.

Calls go through the LIVE class attribute (``M.EnrichmentPipeline._fn``) so the
ep_plugin mutant swap is observed — a ``from ... import`` would freeze shipped
and mask kills.
"""

from __future__ import annotations

import contextlib
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import backend.services.enrichment_pipeline as M
import httpx
import pytest
from backend.core.exceptions import EnrichmentUnavailableError
from backend.services.enrichment_client import (
    UnifiedClothingResult,
    UnifiedDemographicsResult,
    UnifiedEnrichmentResult,
    UnifiedPoseResult,
    UnifiedThreatResult,
    UnifiedVehicleResult,
)
from backend.services.enrichment_pipeline import (
    BoundingBox,
    DetectionInput,
    EnrichmentResult,
)
from PIL import Image

MODLOG = "backend.services.enrichment_pipeline"
CVT = "_classify_vehicle_types"
MAP = "_map_unified_to_enrichment_result"

# ------------------------------------------------------------------ helpers #

MODEL = object()  # sentinel returned by model_manager.load(...) as async CM
CROP = object()  # sentinel returned by _crop_to_bbox(...)
IMAGE = Image.new("RGB", (32, 32), "grey")


class _LoadCM:
    """Stand-in for ``async with model_manager.load(name) as model_data``."""

    def __init__(self, result=MODEL, exc: BaseException | None = None) -> None:
        self.result = result
        self.exc = exc

    async def __aenter__(self):
        if self.exc is not None:
            raise self.exc
        return self.result

    async def __aexit__(self, *exc_info) -> bool:
        return False


def bbox() -> BoundingBox:
    return BoundingBox(x1=10, y1=10, x2=50, y2=50)


def det(det_id: int | None = 7, cls: str = "car") -> DetectionInput:
    return DetectionInput(class_name=cls, confidence=0.9, bbox=bbox(), id=det_id)


def vehicle_result(vtype: str = "pickup_truck", conf: float = 0.77):
    """MEASURED ctor arity: vehicle_classifier_loader.VehicleClassificationResult
    has exactly (vehicle_type, confidence, display_name, is_commercial, all_scores)."""
    return M.VehicleClassificationResult(
        vehicle_type=vtype,
        confidence=conf,
        display_name="Pickup Truck",
        is_commercial=True,
        all_scores={},
    )


def pipeline(exc: BaseException | None = None) -> M.EnrichmentPipeline:
    mm = MagicMock()
    mm.load = MagicMock(return_value=_LoadCM(exc=exc))
    return M.EnrichmentPipeline(model_manager=mm)


def target_globals(method: str) -> dict:
    """The name-resolution dict of the LIVE function object.

    MEASURED harness fact: the ep_plugin swap exec's the variant body in a COPY
    of the module dict, so a swapped mutant's ``__globals__`` is NOT
    ``M.__dict__`` and ``patch.object(M, name, ...)`` is invisible to it (the
    real loader function runs).  Under pristine shipped code
    ``fn.__globals__ is M.__dict__``, so patching through the function's own
    globals is exactly equivalent there and additionally observed by mutants.
    """
    return getattr(M.EnrichmentPipeline, method).__globals__


@contextlib.contextmanager
def cvt_collaborators(classification=None, allow_call=True):
    """Patch the two module-level collaborators _classify_vehicle_types calls.

    Yields the caller-owned mapping of the replacements (NOT the dict
    patch.dict returns, which is the target globals dict and therefore holds the
    RESTORED originals once the context exits).
    """
    subs: dict = {"record_enrichment_model_call": MagicMock()}
    if classification is not None or allow_call:
        subs["classify_vehicle"] = AsyncMock(return_value=classification)
    with patch.dict(target_globals(CVT), subs):
        yield subs


async def run_cvt(vehicles, cls_ret=None, exc=None):
    """Drive the live _classify_vehicle_types with patched collaborators."""
    p = pipeline(exc)
    p._crop_to_bbox = AsyncMock(return_value=CROP)
    classification = cls_ret if cls_ret is not None else vehicle_result()
    with cvt_collaborators(classification) as subs:
        out = await getattr(M.EnrichmentPipeline, CVT)(p, vehicles, IMAGE)
    return out, subs["record_enrichment_model_call"], subs["classify_vehicle"], p


def payload_of(record) -> dict:
    keys = ("detection_type", "operation", "error_type", "error_category", "is_transient")
    return {k: getattr(record, k) for k in keys if hasattr(record, k)}


async def scenario(caplog, exc):
    """One exception-handler scenario: returns the single record emitted."""
    caplog.clear()
    p = pipeline(exc)
    p._crop_to_bbox = AsyncMock(return_value=CROP)
    with (
        caplog.at_level(logging.DEBUG, logger=MODLOG),
        cvt_collaborators(vehicle_result()),
    ):
        out = await getattr(M.EnrichmentPipeline, CVT)(p, [det(7)], IMAGE)
    assert out == {}, "shipped: every top-level handler returns the empty dict"
    # every handler emits exactly one WARNING/ERROR record for this scenario
    records = [r for r in caplog.records if r.name == MODLOG and r.levelno >= logging.WARNING]
    assert len(records) == 1, [(r.levelno, r.getMessage()) for r in caplog.records]
    return records[0]


def mapper(result: EnrichmentResult, unified, detection_type: str):
    """Call the live mapper through the live class attribute."""
    p = M.EnrichmentPipeline(model_manager=MagicMock())
    return getattr(M.EnrichmentPipeline, MAP)(p, result, "D1", unified, detection_type)


def full_person() -> UnifiedEnrichmentResult:
    return UnifiedEnrichmentResult(
        pose=UnifiedPoseResult(
            keypoints=[
                {"name": "nose", "x": 1.0, "y": 2.0, "confidence": 0.5},
                {"name": "left_shoulder", "x": 3.0, "y": 4.0, "confidence": 0.7},
            ],
            pose_class="standing",
            confidence=0.6,
            is_suspicious=False,
        ),
        clothing=UnifiedClothingResult(
            categories=[{"category": "jacket", "confidence": 0.42, "description": "dark jacket"}],
            is_suspicious=True,
        ),
        demographics=UnifiedDemographicsResult(
            age_range="child", age_confidence=0.3, gender="female", gender_confidence=0.4
        ),
        threat=UnifiedThreatResult(
            threats=[{"type": "knife", "confidence": 0.9, "bbox": [0.1, 0.2, 0.3, 0.4]}],
            has_threat=True,
            max_severity="high",
        ),
        reid_embedding=[0.1, 0.2, 0.3],
        action={"top_action": "loitering", "confidence": 0.55, "all_scores": {"a": 0.1, "b": 0.9}},
    )


# ========================================================================== #
# A) _classify_vehicle_types — happy path pins                               #
# ========================================================================== #


@pytest.mark.asyncio
async def test_cvt_model_call_labels_are_recorded():
    """MEASURED: metric labels are exactly ("vehicle",) then ("vehicle-segment-
    classification",) — the shipped strings are pinned verbatim."""
    out, rec, _cv, _p = await run_cvt([det(7)])
    assert [c.args for c in rec.call_args_list] == [
        ("vehicle",),
        ("vehicle-segment-classification",),
    ]
    assert list(out) == ["7"]


@pytest.mark.asyncio
async def test_cvt_det_id_uses_loop_index_when_id_falsy():
    """MEASURED: ids [None, 0, 7] -> keys {'0','1','7'} — falsy ids fall back to
    str(enumerate index), never str(None)."""
    out, _rec, _cv, _p = await run_cvt([det(None), det(0), det(7)])
    assert sorted(out) == ["0", "1", "7"]


@pytest.mark.asyncio
async def test_cvt_classify_vehicle_receives_model_data_and_crop():
    """MEASURED: classify_vehicle(model_data, vehicle_crop) positionally, where
    model_data is the object yielded by model_manager.load(...) and vehicle_crop
    is the _crop_to_bbox result."""
    _out, _rec, cv, p = await run_cvt([det(7)])
    assert [c.args for c in cv.call_args_list] == [(MODEL, CROP)]
    assert p._crop_to_bbox.await_count == 1


@pytest.mark.asyncio
async def test_cvt_stores_classification_object_keyed_by_det_id():
    """MEASURED: results[det_id] IS the object classify_vehicle returned."""
    cls = vehicle_result()
    out, _rec, _cv, _p = await run_cvt([det(7)], cls_ret=cls)
    assert out == {"7": cls}
    assert out["7"] is cls


@pytest.mark.asyncio
async def test_cvt_debug_line_reports_type_and_confidence(caplog):
    """MEASURED debug record: 'Vehicle 7 type: pickup_truck (77%)'."""
    caplog.clear()
    p = pipeline()
    p._crop_to_bbox = AsyncMock(return_value=CROP)
    with (
        caplog.at_level(logging.DEBUG, logger=MODLOG),
        cvt_collaborators(vehicle_result()),
    ):
        out = await getattr(M.EnrichmentPipeline, CVT)(p, [det(7)], IMAGE)
    assert list(out) == ["7"]
    debugs = [
        r.getMessage() for r in caplog.records if r.name == MODLOG and r.levelno == logging.DEBUG
    ]
    assert debugs == ["Vehicle 7 type: pickup_truck (77%)"]


@pytest.mark.asyncio
async def test_cvt_empty_vehicle_list_returns_empty_dict():
    """MEASURED guard: no detections -> {} and no metric call at all."""
    p = pipeline()
    with cvt_collaborators(allow_call=False) as subs:
        out = await getattr(M.EnrichmentPipeline, CVT)(p, [], IMAGE)
    assert out == {}
    assert subs["record_enrichment_model_call"].call_args_list == []


# ========================================================================== #
# A2) _classify_vehicle_types — one pin per exception handler                 #
# ========================================================================== #


@pytest.mark.asyncio
async def test_cvt_keyerror_handler_message_and_payload(caplog):
    """MEASURED warning: MODEL_ZOO miss text + payload {detection_type,
    operation, error_category='parse_error'} (no error_type, no is_transient)."""
    r = await scenario(caplog, KeyError("vehicle-segment-classification"))
    assert r.levelno == logging.WARNING
    assert r.getMessage() == "vehicle-segment-classification model not available in MODEL_ZOO"
    assert payload_of(r) == {
        "detection_type": "vehicle",
        "operation": "vehicle_classification",
        "error_category": "parse_error",
    }


@pytest.mark.asyncio
async def test_cvt_service_unavailable_handler_message_and_payload(caplog):
    """MEASURED warning text embeds sanitize_error(e) verbatim; payload pins
    error_type=EnrichmentUnavailableError, transient True."""
    r = await scenario(caplog, EnrichmentUnavailableError("service down"))
    assert r.levelno == logging.WARNING
    assert r.getMessage() == "Vehicle classification service unavailable: service down"
    assert payload_of(r) == {
        "detection_type": "vehicle",
        "operation": "vehicle_classification",
        "error_type": "EnrichmentUnavailableError",
        "error_category": "service_unavailable",
        "is_transient": True,
    }


@pytest.mark.asyncio
async def test_cvt_connect_error_handler_message_and_payload(caplog):
    """MEASURED connect-failure warning + payload."""
    r = await scenario(caplog, httpx.ConnectError("connect refused"))
    assert r.levelno == logging.WARNING
    assert r.getMessage() == "Vehicle classification connection failed: connect refused"
    assert payload_of(r) == {
        "detection_type": "vehicle",
        "operation": "vehicle_classification",
        "error_type": "ConnectError",
        "error_category": "service_unavailable",
        "is_transient": True,
    }


@pytest.mark.asyncio
async def test_cvt_timeout_handler_message_and_payload(caplog):
    """MEASURED timeout warning + payload (error_category='timeout')."""
    r = await scenario(caplog, httpx.TimeoutException("tick tick"))
    assert r.levelno == logging.WARNING
    assert r.getMessage() == "Vehicle classification timed out: tick tick"
    assert payload_of(r) == {
        "detection_type": "vehicle",
        "operation": "vehicle_classification",
        "error_type": "TimeoutException",
        "error_category": "timeout",
        "is_transient": True,
    }


@pytest.mark.asyncio
async def test_cvt_parse_error_handler_message_and_payload(caplog):
    """MEASURED SHIPPED QUIRK: ValueError -> logger.error('Vehicle classification
    parse error: bad json payload') with error_category='parse_error' and
    is_transient=False."""
    r = await scenario(caplog, ValueError("bad json payload"))
    assert r.levelno == logging.ERROR
    assert r.getMessage() == "Vehicle classification parse error: bad json payload"
    assert payload_of(r) == {
        "detection_type": "vehicle",
        "operation": "vehicle_classification",
        "error_type": "ValueError",
        "error_category": "parse_error",
        "is_transient": False,
    }


@pytest.mark.asyncio
async def test_cvt_unexpected_handler_message_and_payload(caplog):
    """MEASURED SHIPPED QUIRK: catch-all -> logger.error('Vehicle classification
    error', exc_info=True) with error_category='unexpected' and is_transient=True."""
    r = await scenario(caplog, RuntimeError("kaboom"))
    assert r.levelno == logging.ERROR
    assert r.getMessage() == "Vehicle classification error"
    assert r.exc_info is not None and r.exc_info[0] is RuntimeError
    assert payload_of(r) == {
        "detection_type": "vehicle",
        "operation": "vehicle_classification",
        "error_category": "unexpected",
        "is_transient": True,
    }


# ========================================================================== #
# B) _map_unified_to_enrichment_result — gates                               #
# ========================================================================== #


def test_map_pose_populated_for_person_only():
    """MEASURED: pose_results is written iff pose is not None AND
    detection_type == 'person' (case-sensitive), with avg keypoint confidence."""
    r = EnrichmentResult()
    mapper(r, full_person(), "person")
    pose = r.pose_results["D1"]
    assert pose.pose_class == "standing"
    assert pose.pose_confidence == pytest.approx(0.6)
    assert sorted(pose.keypoints) == ["left_shoulder", "nose"]
    assert (pose.keypoints["nose"].x, pose.keypoints["nose"].confidence) == (1.0, 0.5)
    assert pose.bbox is None
    # negative half: the same payload mapped as a vehicle writes nothing
    r2 = EnrichmentResult()
    mapper(r2, full_person(), "vehicle")
    assert dict(r2.pose_results) == {}


def test_map_clothing_gate_requires_person_detection_type():
    """MEASURED: clothing populated for 'person'; for detection_type='vehicle'
    the shipped AND-gate skips the whole block ({} written)."""
    r = EnrichmentResult()
    mapper(r, full_person(), "vehicle")
    assert dict(r.clothing_classifications) == {}


def test_map_demographics_gate_requires_person_detection_type():
    """MEASURED: demographics populated for 'person' only; mapped as 'vehicle'
    both age_classifications and gender_classifications stay empty."""
    r = EnrichmentResult()
    mapper(r, full_person(), "vehicle")
    assert dict(r.age_classifications) == {}
    assert dict(r.gender_classifications) == {}


def test_map_demographics_populated_for_person():
    """MEASURED: age_group/display_name = age_range, confidence = age_confidence,
    is_minor True for 'child', gender block from demographics."""
    r = EnrichmentResult()
    mapper(r, full_person(), "person")
    age = r.age_classifications["D1"]
    assert (age.age_group, age.display_name, age.confidence, age.is_minor) == (
        "child",
        "child",
        0.3,
        True,
    )
    gen = r.gender_classifications["D1"]
    assert (gen.gender, gen.confidence) == ("female", 0.4)


def test_map_threat_requires_has_threat_true():
    """MEASURED: threat present but has_threat=False + detection_type='person'
    writes NO threat_detection (the shipped guard includes has_threat)."""
    u = UnifiedEnrichmentResult(
        threat=UnifiedThreatResult(threats=[], has_threat=False, max_severity="none")
    )
    r = EnrichmentResult()
    mapper(r, u, "person")
    assert r.threat_detection is None


def test_map_threat_populated_for_person_with_threat():
    """MEASURED: threat_detection.threats == [ThreatDetection('knife', 0.9,
    (0.1,0.2,0.3,0.4), is_high_priority=True)]."""
    r = EnrichmentResult()
    mapper(r, full_person(), "person")
    threats = r.threat_detection.threats
    assert [(t.class_name, t.confidence, t.bbox, t.is_high_priority) for t in threats] == [
        ("knife", 0.9, (0.1, 0.2, 0.3, 0.4), True)
    ]
    # shipped does not overwrite a pre-existing threat_detection
    r2 = EnrichmentResult()
    r2.threat_detection = "PRESET"
    mapper(r2, full_person(), "person")
    assert r2.threat_detection == "PRESET"


def test_map_reid_gate_requires_person_detection_type():
    """MEASURED: reid_embedding populated for 'person' only."""
    r = EnrichmentResult()
    mapper(r, full_person(), "vehicle")
    assert dict(r.person_embeddings) == {}


def test_map_reid_populated_for_person():
    """MEASURED: person_embeddings[det_id] = {embedding, embedding_dim, detection_id}."""
    r = EnrichmentResult()
    mapper(r, full_person(), "person")
    assert r.person_embeddings["D1"] == {
        "embedding": [0.1, 0.2, 0.3],
        "embedding_dim": 3,
        "detection_id": "D1",
    }


def test_map_action_gate_requires_person_detection_type():
    """MEASURED: action populated for 'person' only; action_results stays None."""
    r = EnrichmentResult()
    mapper(r, full_person(), "vehicle")
    assert r.action_results is None


def test_map_action_populated_for_person():
    """MEASURED: detected_action=top_action, confidence passthrough, top_actions
    = all_scores sorted desc truncated to 5."""
    r = EnrichmentResult()
    mapper(r, full_person(), "person")
    assert r.action_results["D1"] == {
        "detected_action": "loitering",
        "confidence": 0.55,
        "top_actions": [("b", 0.9), ("a", 0.1)],
        "all_scores": {"a": 0.1, "b": 0.9},
    }


def test_map_vehicle_gate_requires_vehicle_detection_type():
    """MEASURED: unified.vehicle mapped only when detection_type == 'vehicle'."""
    u = UnifiedEnrichmentResult(
        vehicle=UnifiedVehicleResult(
            make=None, model=None, color="red", type="sedan", confidence=0.5
        )
    )
    r = EnrichmentResult()
    mapper(r, u, "person")
    assert dict(r.vehicle_classifications) == {}


def test_map_pet_gate_requires_animal_detection_type():
    """MEASURED: unified.pet mapped only when detection_type == 'animal'."""
    u = UnifiedEnrichmentResult(pet={"pet_type": "dog", "confidence": 0.9})
    r = EnrichmentResult()
    mapper(r, u, "vehicle")
    assert dict(r.pet_classifications) == {}


# ========================================================================== #
# B2) clothing field pins                                                    #
# ========================================================================== #


def test_map_clothing_defaults_when_categories_empty():
    """MEASURED: empty categories list -> ClothingClassification('', 0.0, {},
    is_suspicious=payload, False, '') — the three locals keep their shipped
    '' / 0.0 / '' initialisers."""
    u = UnifiedEnrichmentResult(clothing=UnifiedClothingResult(categories=[], is_suspicious=False))
    r = EnrichmentResult()
    mapper(r, u, "person")
    c = r.clothing_classifications["D1"]
    assert c.top_category == ""
    assert c.confidence == 0.0
    assert c.raw_description == ""
    assert c.is_suspicious is False


def test_map_clothing_category_absent_gives_empty_string():
    """MEASURED: categories=[{}] (no 'category' key) -> top_category == '' and
    confidence == 0.0 and raw_description == '' (the .get defaults)."""
    u = UnifiedEnrichmentResult(clothing=UnifiedClothingResult(categories=[{}], is_suspicious=True))
    r = EnrichmentResult()
    mapper(r, u, "person")
    c = r.clothing_classifications["D1"]
    assert c.top_category == ""
    assert c.confidence == 0.0
    assert c.raw_description == ""


def test_map_clothing_reads_the_category_key():
    """MEASURED: top_category == top['category'] read with .get('category', '')."""
    u = UnifiedEnrichmentResult(
        clothing=UnifiedClothingResult(categories=[{"category": "jacket"}], is_suspicious=False)
    )
    r = EnrichmentResult()
    mapper(r, u, "person")
    assert r.clothing_classifications["D1"].top_category == "jacket"


def test_map_clothing_reads_the_confidence_key():
    """MEASURED: confidence == top['confidence'] read with .get('confidence', 0.0)."""
    u = UnifiedEnrichmentResult(
        clothing=UnifiedClothingResult(
            categories=[{"category": "jacket", "confidence": 0.42}], is_suspicious=False
        )
    )
    r = EnrichmentResult()
    mapper(r, u, "person")
    assert r.clothing_classifications["D1"].confidence == 0.42


def test_map_clothing_reads_the_description_key():
    """MEASURED: raw_description == top['description'] when present."""
    u = UnifiedEnrichmentResult(
        clothing=UnifiedClothingResult(
            categories=[{"category": "jacket", "description": "dark jacket"}], is_suspicious=False
        )
    )
    r = EnrichmentResult()
    mapper(r, u, "person")
    assert r.clothing_classifications["D1"].raw_description == "dark jacket"


def test_map_clothing_description_falls_back_to_category():
    """MEASURED: no 'description' key -> raw_description == top_cat ('hoodie'),
    i.e. the shipped .get('description', top_cat) default."""
    u = UnifiedEnrichmentResult(
        clothing=UnifiedClothingResult(
            categories=[{"category": "hoodie", "confidence": 0.1}], is_suspicious=True
        )
    )
    r = EnrichmentResult()
    mapper(r, u, "person")
    c = r.clothing_classifications["D1"]
    assert c.raw_description == "hoodie"
    assert c.top_category == "hoodie"


def test_map_clothing_record_fields():
    """MEASURED full ClothingClassification record for the populated case."""
    r = EnrichmentResult()
    mapper(r, full_person(), "person")
    c = r.clothing_classifications["D1"]
    assert isinstance(c, M.ClothingClassification)
    assert c.top_category == "jacket"
    assert c.confidence == 0.42
    assert c.all_scores == {}
    assert c.is_suspicious is True
    assert c.is_service_uniform is False
    assert c.raw_description == "dark jacket"


def test_map_clothing_all_scores_is_an_empty_dict():
    """MEASURED pin: all_scores is always a fresh empty dict."""
    r = EnrichmentResult()
    mapper(r, full_person(), "person")
    assert r.clothing_classifications["D1"].all_scores == {}
    assert isinstance(r.clothing_classifications["D1"].all_scores, dict)


def test_map_clothing_is_service_uniform_is_hardcoded_false():
    """MEASURED pin: is_service_uniform is False regardless of payload."""
    u = UnifiedEnrichmentResult(
        clothing=UnifiedClothingResult(
            categories=[{"category": "police_uniform", "confidence": 0.99}], is_suspicious=True
        )
    )
    r = EnrichmentResult()
    mapper(r, u, "person")
    assert r.clothing_classifications["D1"].is_service_uniform is False


# ========================================================================== #
# B3) vehicle / pet record pins                                              #
# ========================================================================== #


def test_map_vehicle_display_name_is_space_join():
    """MEASURED: display_name == ' '.join([color, make, model, type]) with
    falsy parts dropped ('' type -> '')."""
    u = UnifiedEnrichmentResult(
        vehicle=UnifiedVehicleResult(
            make="Ford", model="F-150", color="red", type="pickup_truck", confidence=0.6
        )
    )
    r = EnrichmentResult()
    mapper(r, u, "vehicle")
    assert r.vehicle_classifications["D1"].display_name == "red Ford F-150 pickup_truck"
    u2 = UnifiedEnrichmentResult(
        vehicle=UnifiedVehicleResult(make=None, model=None, color=None, type="", confidence=0.5)
    )
    r2 = EnrichmentResult()
    mapper(r2, u2, "vehicle")
    assert r2.vehicle_classifications["D1"].display_name == ""


def test_map_vehicle_record_fields():
    """MEASURED full VehicleClassificationResult record."""
    u = UnifiedEnrichmentResult(
        vehicle=UnifiedVehicleResult(
            make="Ford", model="F-150", color="red", type="pickup_truck", confidence=0.6
        )
    )
    r = EnrichmentResult()
    mapper(r, u, "vehicle")
    v = r.vehicle_classifications["D1"]
    assert isinstance(v, M.VehicleClassificationResult)
    assert v.vehicle_type == "pickup_truck"
    assert v.confidence == 0.6
    assert v.display_name == "red Ford F-150 pickup_truck"
    assert v.is_commercial is True
    assert v.all_scores == {}


def test_map_vehicle_is_commercial_membership_set():
    """MEASURED membership table: the five commercial names -> True, others
    (including the empty string) -> False."""
    p = M.EnrichmentPipeline(model_manager=MagicMock())
    table = {
        "delivery_van": True,
        "box_truck": True,
        "semi_truck": True,
        "cargo_van": True,
        "pickup_truck": True,
        "sedan": False,
        "car": False,
        "unknown": False,
    }
    for vtype, expected in table.items():
        u = UnifiedEnrichmentResult(
            vehicle=UnifiedVehicleResult(
                make=None, model=None, color=None, type=vtype, confidence=0.5
            )
        )
        r = EnrichmentResult()
        getattr(M.EnrichmentPipeline, MAP)(p, r, "D1", u, "vehicle")
        assert r.vehicle_classifications["D1"].is_commercial is expected, vtype


def test_map_pet_record_fields():
    """MEASURED full PetClassificationResult record: pet_type wins over 'type',
    cat/dog scores are hardcoded 0.0, is_household_pet defaults True."""
    p = M.EnrichmentPipeline(model_manager=MagicMock())
    u = UnifiedEnrichmentResult(pet={"pet_type": "dog", "type": "canine", "confidence": 0.9})
    r = EnrichmentResult()
    getattr(M.EnrichmentPipeline, MAP)(p, r, "D1", u, "animal")
    pet = r.pet_classifications["D1"]
    assert isinstance(pet, M.PetClassificationResult)
    assert pet.animal_type == "dog"
    assert pet.confidence == 0.9
    assert pet.cat_score == 0.0
    assert pet.dog_score == 0.0
    assert pet.is_household_pet is True


def test_map_pet_type_fallback_chain():
    """MEASURED: no 'pet_type' -> falls back to 'type'; empty dict -> 'unknown'
    with confidence 0.0 and is_household_pet True."""
    p = M.EnrichmentPipeline(model_manager=MagicMock())
    for payload, expected in (
        ({"type": "cat", "confidence": 0.25}, ("cat", 0.25, True)),
        ({}, ("unknown", 0.0, True)),
    ):
        r = EnrichmentResult()
        getattr(M.EnrichmentPipeline, MAP)(
            p, r, "D1", UnifiedEnrichmentResult(pet=payload), "animal"
        )
        pet = r.pet_classifications["D1"]
        assert (pet.animal_type, pet.confidence, pet.is_household_pet) == expected, payload


def test_map_pet_is_household_pet_honours_false():
    """MEASURED: an explicit is_household_pet=False in the payload is kept."""
    p = M.EnrichmentPipeline(model_manager=MagicMock())
    r = EnrichmentResult()
    getattr(M.EnrichmentPipeline, MAP)(
        p,
        r,
        "D1",
        UnifiedEnrichmentResult(pet={"pet_type": "dog", "is_household_pet": False}),
        "animal",
    )
    assert r.pet_classifications["D1"].is_household_pet is False
