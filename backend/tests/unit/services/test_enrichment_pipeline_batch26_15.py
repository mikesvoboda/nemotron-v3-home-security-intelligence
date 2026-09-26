"""Chunk-15 kill battery: enrichment_pipeline mutation survivors.

Targets (shipped source, PRISTINE workspace copy):
  - EnrichmentResult.to_dict               (shipped lines 1398-1490)
  - EnrichmentPipeline._process_phase1_results (shipped lines 2869-3078)
  - EnrichmentPipeline._run_reid           (shipped lines 5733-5870)

Every assertion below was PROBE-derived from shipped behaviour (probes/c15/probe1.py,
probe2.py) - including the shipped oddities:
  * to_dict serializes plate/face bboxes with ``to_tuple()`` (a TUPLE, not the
    5-key dict that LicensePlateResult.to_dict()/FaceResult.to_dict() produce),
  * ``smoke_fire_detection`` uses ``if value`` (not ``is not None``) so an empty
    result object is emitted as null,
  * ``_process_phase1_results`` skips the image-quality "disabled" error by a
    case-insensitive substring test on str(exc),
  * ``EnrichmentResult.add_error`` (reached by every _handle_enrichment_error call)
    stamps operation + reason f"{sanitized exc}" + legacy errors[] string.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from PIL import Image

import backend.services.enrichment_pipeline as M
from backend.services.enrichment_pipeline import (
    BoundingBox,
    DetectionInput,
    EnrichmentResult,
    EnrichmentPipeline,
)
from backend.services.household_matcher import HouseholdMatch
from backend.services.pet_classifier_loader import PetClassificationResult
from backend.services.vision_extractor import BatchExtractionResult
from backend.services.vitpose_loader import Keypoint, PoseResult

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_PIPELINE: EnrichmentPipeline | None = None


def pipeline() -> EnrichmentPipeline:
    """Cheap, deterministic EnrichmentPipeline (no models loaded)."""
    global _PIPELINE
    if _PIPELINE is None:
        mm = MagicMock()
        mm.load = MagicMock()
        mm.load.return_value.__aenter__ = AsyncMock(return_value=None)
        mm.load.return_value.__aexit__ = AsyncMock(return_value=None)
        _PIPELINE = EnrichmentPipeline(model_manager=mm, redis_client=AsyncMock())
    return _PIPELINE


def phase1(key: object, value: object) -> EnrichmentResult:
    """Run shipped _process_phase1_results on a single-key phase1 dict."""
    result = EnrichmentResult()
    pipeline()._process_phase1_results(result, {key: value})
    return result


def err_op(result: EnrichmentResult, index: int = 0) -> str:
    return result.structured_errors[index].operation


def plate_result() -> EnrichmentResult:
    r = EnrichmentResult()
    r.license_plates.append(
        M.LicensePlateResult(
            bbox=BoundingBox(x1=1.5, y1=2.5, x2=3.5, y2=4.5),
            text="ABC123",
            confidence=0.9,
            ocr_confidence=0.8,
            source_detection_id=7,
        )
    )
    return r


def face_result() -> EnrichmentResult:
    r = EnrichmentResult()
    r.faces.append(
        M.FaceResult(
            bbox=BoundingBox(x1=5.5, y1=6.5, x2=7.5, y2=8.5),
            confidence=0.4,
            source_detection_id=9,
        )
    )
    return r


class _Dictable:
    """Sentinel with a real to_dict()."""

    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def to_dict(self) -> dict:
        return dict(self.payload)


class _NoDict:
    """Sentinel WITHOUT to_dict() (threat_detection field is ``Any``)."""


class _RolelessMatch:
    """Household-match-shaped object lacking member_role / schedule_status."""

    member_id = 77
    member_name = "Roleless"
    vehicle_id = None
    vehicle_description = None
    similarity = 0.31
    match_type = "person"


def _model_manager_with(calls: list) -> MagicMock:
    mm = MagicMock()

    class _Ctx:
        async def __aenter__(self) -> None:
            return None

        async def __aexit__(self, *exc: object) -> None:
            return None

    mm.load = MagicMock(side_effect=lambda name: calls.append(name) or _Ctx())
    return mm


def _reid_pipeline(calls: list) -> tuple[EnrichmentPipeline, AsyncMock]:
    svc = AsyncMock()
    svc.generate_embedding = AsyncMock(return_value=[0.1, 0.2])
    svc.find_matching_entities = AsyncMock(return_value=[])
    svc.store_embedding = AsyncMock()
    p = EnrichmentPipeline(
        model_manager=_model_manager_with(calls),
        redis_client=AsyncMock(),
        reid_enabled=True,
    )
    p._reid_service = svc
    return p, svc


def _stored_entity(svc: AsyncMock, index: int = 0):
    return svc.store_embedding.call_args_list[index][0][1]


# ===========================================================================
# EnrichmentResult.to_dict  --  key names
# ===========================================================================


def test_plate_entry_uses_bbox_and_source_detection_id_keys():
    """mutmut_3/4 (bbox key), mutmut_11/12 (source_detection_id key)."""
    entry = plate_result().to_dict()["license_plates"][0]
    assert entry["bbox"] == (1.5, 2.5, 3.5, 4.5)  # tuple, not dict
    assert entry["source_detection_id"] == 7
    assert set(entry) == {
        "bbox",
        "text",
        "confidence",
        "ocr_confidence",
        "source_detection_id",
    }


def test_face_entry_uses_bbox_and_source_detection_id_keys():
    """mutmut_15/16 (bbox key)."""
    entry = face_result().to_dict()["faces"][0]
    assert entry["bbox"] == (5.5, 6.5, 7.5, 8.5)
    assert entry["source_detection_id"] == 9
    assert set(entry) == {"bbox", "confidence", "source_detection_id"}


def test_pose_results_key_present_and_empty_by_default():
    """mutmut_29/30."""
    assert EnrichmentResult().to_dict()["pose_results"] == {}
    r = EnrichmentResult()
    r.pose_results["1"] = PoseResult(
        keypoints={"nose": Keypoint(x=1.0, y=2.0, confidence=0.9, name="nose")},
        pose_class="crouching",
        pose_confidence=0.95,
    )
    d = r.to_dict()
    assert d["pose_results"]["1"]["posture"] == "crouching"
    assert d["pose_results"]["1"]["alerts"] == ["person_crouching"]


def test_depth_analysis_key_present_and_null_by_default():
    """mutmut_35/36."""
    assert EnrichmentResult().to_dict()["depth_analysis"] is None
    r = EnrichmentResult()
    r.depth_analysis = _Dictable({"closest_detection_id": "3"})
    assert r.to_dict()["depth_analysis"] == {"closest_detection_id": "3"}


def test_threat_detection_key_present():
    """mutmut_43/44."""
    assert EnrichmentResult().to_dict()["threat_detection"] is None
    r = EnrichmentResult()
    r.threat_detection = _Dictable({"has_threats": True})
    assert r.to_dict()["threat_detection"] == {"has_threats": True}


def test_age_gender_embeddings_keys_present_and_empty():
    """mutmut_52/53 (age_classifications), 54/55 (gender_classifications),
    56/57 (person_embeddings)."""
    d = EnrichmentResult().to_dict()
    assert d["age_classifications"] == {}
    assert d["gender_classifications"] == {}
    assert d["person_embeddings"] == {}


def test_yolo_world_detections_key_list_identity():
    """mutmut_62/63."""
    r = EnrichmentResult()
    assert r.to_dict()["yolo_world_detections"] == []
    items = [{"class_name": "ladder", "confidence": 0.42}]
    r.yolo_world_detections = items
    assert r.to_dict()["yolo_world_detections"] is items


def test_person_household_match_member_id_key():
    """mutmut_69/70."""
    r = EnrichmentResult()
    r.person_household_matches[3] = HouseholdMatch(
        member_id=42, member_name="Ann", similarity=0.91, match_type="person"
    )
    entry = r.to_dict()["person_household_matches"]["3"]
    assert entry["member_id"] == 42
    assert entry["member_name"] == "Ann"
    assert entry["similarity"] == 0.91
    assert entry["match_type"] == "person"


def test_vehicle_household_match_vehicle_id_key():
    """mutmut_100/101."""
    r = EnrichmentResult()
    r.vehicle_household_matches[5] = HouseholdMatch(
        vehicle_id=11,
        vehicle_description="blue van",
        similarity=0.7,
        match_type="license_plate",
    )
    entry = r.to_dict()["vehicle_household_matches"]["5"]
    assert entry["vehicle_id"] == 11
    assert entry["vehicle_description"] == "blue van"
    assert entry["similarity"] == 0.7
    assert entry["match_type"] == "license_plate"
    assert set(entry) == {
        "detection_id",
        "vehicle_id",
        "vehicle_description",
        "similarity",
        "match_type",
    }


def test_vision_extraction_key_and_passthrough():
    """mutmut_108/109 (key) + 110 (truthiness)."""
    assert EnrichmentResult().to_dict()["vision_extraction"] is None
    r = EnrichmentResult()
    r.vision_extraction = BatchExtractionResult()
    d = r.to_dict()
    assert d["vision_extraction"] == {
        "vehicle_attributes": {},
        "person_attributes": {},
        "scene_analysis": None,
        "environment_context": None,
        "florence_enhanced": None,
    }
    # truthiness guard, not ``is not None``: an empty-but-present result still
    # serializes (BatchExtractionResult() is truthy as a dataclass instance).
    assert d["vision_extraction"] is not None


# ===========================================================================
# EnrichmentResult.to_dict  --  conditional expressions
# ===========================================================================


def test_depth_analysis_emits_payload_when_present():
    """mutmut_37 (``and False`` -> always None)."""
    r = EnrichmentResult()
    r.depth_analysis = _Dictable({"average_depth": 0.25})
    assert r.to_dict()["depth_analysis"] == {"average_depth": 0.25}


def test_threat_detection_dictable_serializes_dictless_is_none():
    """mutmut_45 (and->or), 46-51 (hasright arg)."""
    r = EnrichmentResult()
    r.threat_detection = _Dictable({"threats": []})
    assert r.to_dict()["threat_detection"] == {"threats": []}

    r2 = EnrichmentResult()
    r2.threat_detection = _NoDict()
    assert r2.to_dict()["threat_detection"] is None
    # shipped guard is a plain ``and``: a falsy value with to_dict() is None
    r3 = EnrichmentResult()
    r3.threat_detection = []
    assert r3.to_dict()["threat_detection"] is None


def test_smoke_fire_truthiness_and_value():
    """mutmut_58/59 (key) + 60 (``and False`` -> always None)."""
    assert EnrichmentResult().to_dict()["smoke_fire_detection"] is None
    r = EnrichmentResult()
    r.smoke_fire_detection = _Dictable({"has_detections": True})
    assert r.to_dict()["smoke_fire_detection"] == {"has_detections": True}


# ===========================================================================
# EnrichmentResult.to_dict  --  household getattr members
# ===========================================================================


def test_person_household_match_member_role_and_schedule_status():
    """mutmut_77/78 (key), 84/85 (attr name), 86/87 (key), 93/94 (attr name)."""
    r = EnrichmentResult()
    r.person_household_matches[1] = HouseholdMatch(
        member_id=42,
        member_name="Ann",
        similarity=0.5,
        match_type="person",
        member_role="service_worker",
        schedule_status=True,
    )
    entry = r.to_dict()["person_household_matches"]["1"]
    assert entry["member_role"] == "service_worker"
    assert entry["schedule_status"] is True
    assert set(entry) == {
        "detection_id",
        "member_id",
        "member_name",
        "similarity",
        "match_type",
        "member_role",
        "schedule_status",
    }


def test_person_household_match_missing_optional_attrs_default_none():
    """mutmut_79, 83, 88, 92 (getattr target/2-arg forms -> AttributeError)."""
    r = EnrichmentResult()
    r.person_household_matches[2] = _RolelessMatch()
    entry = r.to_dict()["person_household_matches"]["2"]
    assert entry["member_role"] is None
    assert entry["schedule_status"] is None
    assert entry["member_id"] == 77


# ===========================================================================
# _process_phase1_results  --  exception paths record the operation
# ===========================================================================


def test_face_detection_exception_recorded():
    """mutmut_8 (exc arg -> None)."""
    r = phase1("face_detection", RuntimeError("face-boom"))
    assert len(r.structured_errors) == 1
    assert err_op(r) == "face_detection"
    assert r.structured_errors[0].reason == "Unexpected error: face-boom"
    assert r.errors == ["face_detection failed: Unexpected error: face-boom"]


def test_license_plate_detection_exception_recorded():
    """mutmut_23."""
    r = phase1("license_plate_detection", RuntimeError("plate-boom"))
    assert len(r.structured_errors) == 1
    assert err_op(r) == "license_plate_detection"
    assert r.structured_errors[0].reason == "Unexpected error: plate-boom"


def test_weather_classification_exception_recorded():
    """mutmut_65 (exc arg), 70/71 (operation name)."""
    r = phase1("weather_classification", RuntimeError("weather-boom"))
    assert len(r.structured_errors) == 1
    assert err_op(r) == "weather_classification"
    assert r.structured_errors[0].reason == "Unexpected error: weather-boom"


def test_pose_estimation_exception_recorded():
    """mutmut_87 (exc arg), 92/93 (operation name)."""
    r = phase1("pose_estimation", RuntimeError("pose-boom"))
    assert len(r.structured_errors) == 1
    assert err_op(r) == "pose_estimation"
    assert r.structured_errors[0].reason == "Unexpected error: pose-boom"


def test_depth_estimation_exception_recorded():
    """mutmut_102 (exc arg), 107/108 (operation name)."""
    r = phase1("depth_estimation", RuntimeError("depth-boom"))
    assert len(r.structured_errors) == 1
    assert err_op(r) == "depth_estimation"
    assert r.structured_errors[0].reason == "Unexpected error: depth-boom"


def test_image_quality_non_disabled_exception_recorded_under_assessment_name():
    """mutmut_50 (exc arg), 55 (operation name)."""
    r = phase1("image_quality", RuntimeError("brisque exploded"))
    assert len(r.structured_errors) == 1
    assert err_op(r) == "image_quality_assessment"
    assert r.structured_errors[0].reason == "Unexpected error: brisque exploded"


# ===========================================================================
# _process_phase1_results  --  the image-quality "disabled" skip
# ===========================================================================


def test_image_quality_disabled_exception_is_skipped():
    """mutmut_44, 45, 47, 48 (the substring test loses the match)."""
    for message in ("quality model disabled by config", "MODEL DISABLED", "Disabled here"):
        r = phase1("image_quality", RuntimeError(message))
        assert r.structured_errors == [], message
        assert r.errors == [], message


# ===========================================================================
# _process_phase1_results  --  membership guards on phase1_dict keys
# ===========================================================================


def test_depth_estimation_key_gates_the_block():
    """mutmut_95/96."""
    sentinel = _Dictable({"average_depth": 0.4})
    r = EnrichmentResult()
    pipeline()._process_phase1_results(r, {"depth_estimation": sentinel})
    assert r.depth_analysis is sentinel
    r2 = phase1("depth_estimationX", sentinel)
    assert r2.depth_analysis is None
    assert r2.structured_errors == []


def test_action_recognition_key_gates_the_block():
    """mutmut_110/111."""
    actions = {"detected_action": "loitering", "confidence": 0.8}
    r = EnrichmentResult()
    pipeline()._process_phase1_results(r, {"action_recognition": actions})
    assert r.action_results == actions
    r2 = phase1("action_recognitionX", actions)
    assert r2.action_results is None


def test_scene_ocr_frame_key_gates_the_block():
    """mutmut_145/146."""
    ocr = _Dictable({"texts": ["EXIT"]})
    r = EnrichmentResult()
    pipeline()._process_phase1_results(r, {"scene_ocr_frame": ocr})
    assert r.scene_ocr is ocr
    r2 = phase1("scene_ocr_frameX", ocr)
    assert r2.scene_ocr is None
    assert r2.structured_errors == []


def test_threat_detection_key_gates_the_block():
    """mutmut_152/153."""
    threat = _Dictable({"has_threats": True})
    r = EnrichmentResult()
    pipeline()._process_phase1_results(r, {"threat_detection": threat})
    assert r.threat_detection is threat
    r2 = phase1("threat_detectionX", threat)
    assert r2.threat_detection is None
    assert r2.structured_errors == []


def test_demographics_key_gates_the_block():
    """mutmut_158/159."""
    r = EnrichmentResult()
    pipeline()._process_phase1_results(r, {"demographics": ({"1": "adult"}, {"1": "female"})})
    assert r.age_classifications == {"1": "adult"}
    assert r.gender_classifications == {"1": "female"}
    r2 = phase1("demographicsX", ({"1": "adult"}, {"1": "female"}))
    assert r2.age_classifications == {}
    assert r2.gender_classifications == {}
    assert r2.structured_errors == []


def test_smoke_fire_detection_key_gates_the_block():
    """mutmut_165/166/167."""
    sentinel = _Dictable({"has_detections": True})
    r = EnrichmentResult()
    pipeline()._process_phase1_results(r, {"smoke_fire_detection": sentinel})
    assert r.smoke_fire_detection is sentinel
    r2 = phase1("smoke_fire_detectionX", sentinel)
    assert r2.smoke_fire_detection is None
    assert r2.structured_errors == []
    # shipped truthiness guard: a falsy (but present) value IS stored
    r3 = phase1("smoke_fire_detection", [])
    assert r3.smoke_fire_detection == []


def test_yolo_world_detection_key_gates_the_block():
    """mutmut_172/173/174."""
    dets = [{"class_name": "knife", "confidence": 0.6}]
    r = EnrichmentResult()
    pipeline()._process_phase1_results(r, {"yolo_world_detection": dets})
    assert r.yolo_world_detections == dets
    r2 = phase1("yolo_world_detectionX", dets)
    assert r2.yolo_world_detections == []
    assert r2.structured_errors == []


def test_osnet_reid_key_gates_the_block():
    """mutmut_178/179."""
    r = EnrichmentResult()
    pipeline()._process_phase1_results(r, {"osnet_reid": {"5": [0.5, 0.6]}})
    assert r.person_embeddings == {"5": [0.5, 0.6]}
    r2 = phase1("osnet_reidX", {"5": [0.5, 0.6]})
    assert r2.person_embeddings == {}
    assert r2.structured_errors == []


def test_clip_scene_classification_key_gates_the_block():
    """mutmut_184/185."""
    r = EnrichmentResult()
    pipeline()._process_phase1_results(
        r, {"clip_scene_classification": ({"driveway": 0.9}, "driveway")}
    )
    assert r.clip_scene_classification == {"driveway": 0.9}
    assert r.clip_scene_top_label == "driveway"
    r2 = phase1("clip_scene_classificationX", ({"driveway": 0.9}, "driveway"))
    assert r2.clip_scene_classification is None
    assert r2.clip_scene_top_label is None
    assert r2.structured_errors == []


def test_clip_threat_matching_key_gates_the_block():
    """mutmut_190/191."""
    scores = {"weapon": 0.77}
    r = EnrichmentResult()
    pipeline()._process_phase1_results(r, {"clip_threat_matching": scores})
    assert r.clip_threat_matches == scores
    r2 = phase1("clip_threat_matchingX", scores)
    assert r2.clip_threat_matches is None
    assert r2.structured_errors == []


def test_reid_via_service_key_gates_the_block():
    """mutmut_196/197."""
    r = phase1("reid_via_service", RuntimeError("reid-boom"))
    assert len(r.structured_errors) == 1
    assert err_op(r) == "reid_via_service"
    r2 = phase1("reid_via_serviceX", RuntimeError("reid-boom"))
    assert r2.structured_errors == []


def test_unified_task_keys_gate_the_exception_loop():
    """mutmut_200 (unified_result -> None kills 3 of 9 keys, not the group)."""
    for unified_key in (
        "unified_person_enrichment",
        "unified_vehicle_enrichment",
        "unified_animal_enrichment",
    ):
        r = phase1(unified_key, RuntimeError("unified-boom"))
        assert len(r.structured_errors) == 1, unified_key
        assert err_op(r) == unified_key, unified_key
        assert r.structured_errors[0].reason == "Unexpected error: unified-boom", unified_key
    r2 = phase1("unified_person_enrichmentX", RuntimeError("unified-boom"))
    assert r2.structured_errors == []


# ===========================================================================
# _process_phase1_results  --  pet-only log line
# ===========================================================================


def test_pet_only_event_log_line_emitted():
    """mutmut_134 (arg->None), 135 (XX..XX), 136 (lower), 137 (upper).

    The logger is reached through the module global ``logger`` (shipped line
    2979).  The ep_plugin mutant's ``__globals__`` is a COPY of the module dict,
    so rebinding ``M.logger`` would be invisible to the mutant; instead the
    ``info`` method of the shared Logger object is wrapped, which both shipped
    and mutant calls land on.  ``pet_only_event`` is True here (probe-measured)
    so the line is on the executed path.
    """
    pet = PetClassificationResult(
        animal_type="dog",
        confidence=0.95,
        cat_score=0.02,
        dog_score=0.95,
        is_household_pet=True,
    )
    messages: list[object] = []

    def _spy(self: object, msg: object, *args: object, **kw: object) -> None:
        messages.append(msg)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(type(M.logger), "info", _spy)
        r = phase1("pet_classification", {"3": pet})
    assert r.pet_only_event is True
    assert "Pet-only event detected - can skip Nemotron risk analysis" in messages, messages


# ===========================================================================
# _run_reid
# ===========================================================================


def test_run_reid_asserts_redis_client_present():
    """mutmut_2/3 (assert message text)."""
    p, _svc = _reid_pipeline([])
    p.redis_client = None
    result = EnrichmentResult()
    det = DetectionInput(id=1, class_name="person", confidence=0.9, bbox=BoundingBox(1, 2, 3, 4))
    with pytest.raises(AssertionError) as excinfo:
        asyncio.run(p._run_reid([det], Image.new("RGB", (64, 64)), "cam", result))
    assert str(excinfo.value) == "redis_client required for re-id"


def test_run_reid_loads_siglip2_model_and_uses_live_redis():
    """mutmut_4 (redis local -> None), 5/6/7 (model name)."""
    calls: list = []
    p, svc = _reid_pipeline(calls)
    result = EnrichmentResult()
    det = DetectionInput(id=1, class_name="person", confidence=0.9, bbox=BoundingBox(1, 2, 3, 4))
    asyncio.run(p._run_reid([det], Image.new("RGB", (64, 64)), "cam", result))
    assert calls == ["siglip2-base-patch16-224"]
    assert svc.generate_embedding.await_count == 1
    assert svc.find_matching_entities.await_args[0][0] is p.redis_client
    assert svc.store_embedding.await_args[0][0] is p.redis_client
    assert result.clip_embeddings == {"1": [0.1, 0.2]}


def test_run_reid_det_id_falls_back_to_index_string():
    """mutmut_11 (``or True`` -> str(None)), 13 (else -> str(None))."""
    calls: list = []
    p, svc = _reid_pipeline(calls)
    result = EnrichmentResult()
    # id=None -> str(i) == "0"; under the mutants this becomes str(None) == "None"
    det = DetectionInput(id=None, class_name="person", confidence=0.9, bbox=BoundingBox(1, 2, 3, 4))
    asyncio.run(p._run_reid([det], Image.new("RGB", (64, 64)), "cam", result))
    assert list(result.clip_embeddings) == ["0"]
    assert _stored_entity(svc).detection_id == "0"
    # id truthy -> str(det.id)
    p2, svc2 = _reid_pipeline([])
    result2 = EnrichmentResult()
    det2 = DetectionInput(id=9, class_name="person", confidence=0.9, bbox=BoundingBox(1, 2, 3, 4))
    asyncio.run(p2._run_reid([det2], Image.new("RGB", (64, 64)), "cam", result2))
    assert list(result2.clip_embeddings) == ["9"]
    assert _stored_entity(svc2).detection_id == "9"


def test_run_reid_skips_non_person_vehicle_detections():
    """mutmut_16 (``case _: continue`` deleted -> UnboundLocalError)."""
    calls: list = []
    p, svc = _reid_pipeline(calls)
    result = EnrichmentResult()
    dets = [
        DetectionInput(id=1, class_name="dog", confidence=0.9, bbox=BoundingBox(1, 2, 3, 4)),
        DetectionInput(id=2, class_name="person", confidence=0.9, bbox=BoundingBox(1, 2, 3, 4)),
    ]
    asyncio.run(p._run_reid(dets, Image.new("RGB", (64, 64)), "cam", result))
    assert list(result.clip_embeddings) == ["2"]
    assert svc.store_embedding.await_count == 1
    assert _stored_entity(svc).entity_type == "person"


def test_run_reid_person_routes_to_person_reid_matches_with_person_type():
    """mutmut_18 (None), 19 (XXpersonXX), 20 (PERSON)."""
    calls: list = []
    p, svc = _reid_pipeline(calls)
    matches = [_Dictable({"member_id": 42})]
    svc.find_matching_entities = AsyncMock(return_value=matches)
    result = EnrichmentResult()
    det = DetectionInput(id=1, class_name="person", confidence=0.9, bbox=BoundingBox(1, 2, 3, 4))
    asyncio.run(p._run_reid([det], Image.new("RGB", (64, 64)), "cam", result))
    assert result.person_reid_matches == {"1": matches}
    assert result.vehicle_reid_matches == {}
    assert svc.find_matching_entities.await_args.kwargs["entity_type"] == "person"
    assert _stored_entity(svc).entity_type == "person"
