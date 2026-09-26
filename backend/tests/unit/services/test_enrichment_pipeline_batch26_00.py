"""Chunk-00 kill-battery for enrichment_pipeline mutation survivors (115 keys).

Every assertion below pins behaviour MEASURED on the pristine shipped module.
Shape families covered (15 shape groups):

A) ``EnrichmentError.from_exception`` — ``error_type=type(exc).__name__`` at the
   7 return sites shipped L445 / L456 / L467 / L484 / L495 / L506 / L516
     shape#8 -> ``error_type=None``
     shape#9 -> ``error_type=type(None).__name__`` (the literal "NoneType")

B) ``EnrichmentPipeline._classify_person_clothing`` — structured ``extra={...}``
   of the except-branch log calls (L6627/6628, L6642/6643, L6655, L6666/6667,
   L6680/6681, L6706/6707, L6719/6720)
     shape#21 "detection_type" key -> "XXdetection_typeXX"
     shape#22 "detection_type" key -> "DETECTION_TYPE"
     shape#25 "operation" key       -> "XXoperationXX"
     shape#26 "operation" key       -> "OPERATION"
     shape#27 operation value       -> "XXclothing_classificationXX"
     shape#28 operation value       -> "CLOTHING_CLASSIFICATION"

C) ``EnrichmentPipeline._classify_pets`` — the same shapes on
   ``"operation": "pet_classification"`` (L7169, L7184, L7196, L7208, L7222,
   L7248, L7261) -> shapes #25-#28.

D) ``EnrichmentPipeline._run_parallel_enrichment`` — the
   ``and self._should_run_for_quality("standard")`` cascade gate at 11 sites
   (L2438, L2448, L2488, L2496, L2504, L2512, L2531, L2543, L2552, L2577, L2795)
     shape#46 -> ``None``,  shape#47 -> ``"XXstandardXX"``,  shape#48 -> ``"STANDARD"``
   Shipped ``_should_run_for_quality`` (L2331-2343) resolves an unknown/None tier
   via ``level_order.get(tier, 2) == 2`` (i.e. "full").  With the shipped default
   quality ("full") all three mutants are value-identical to shipped, so the
   discriminating state is ``pipeline._quality_level == "standard"``: shipped
   schedules the gated task (1 >= 1), the mutants do not (1 >= 2 is False).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from PIL import Image

import backend.services.enrichment_pipeline as M

MODULE = "backend.services.enrichment_pipeline"
CLOTHING_OP = "clothing_classification"
PET_OP = "pet_classification"
EXTRA_KEYS = (
    "detection_type",
    "operation",
    "error_type",
    "error_category",
    "is_transient",
    "status_code",
)


def asyncio_run(coro: Any) -> Any:
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# log capture: ``logger.warning(msg, extra={...})`` copies the extra mapping onto
# the LogRecord, so a Handler attached to the module logger sees it verbatim.
# ---------------------------------------------------------------------------
class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@contextlib.contextmanager
def capture_extra() -> Any:
    handler = _Capture()
    previous_level = M.logger.level
    M.logger.addHandler(handler)
    M.logger.setLevel(logging.DEBUG)
    try:
        yield handler
    finally:
        M.logger.setLevel(previous_level)
        M.logger.removeHandler(handler)


def extra_of(record: logging.LogRecord) -> dict[str, Any]:
    return {k: record.__dict__[k] for k in EXTRA_KEYS if k in record.__dict__}


def single_noisy_payload(records: Any) -> dict[str, Any]:
    """Shipped emits exactly one WARNING-or-worse record per except branch."""
    noisy = [r for r in records if r.levelno >= logging.WARNING]
    assert len(noisy) == 1, [(r.levelname, r.getMessage()) for r in noisy]
    record = noisy[0]
    return {"level": record.levelname, "extra": extra_of(record)}


# ---------------------------------------------------------------------------
# exception drivers, one per except-branch of the classification helpers
# ---------------------------------------------------------------------------
def http_status_error(code: int) -> httpx.HTTPStatusError:
    response = MagicMock()
    response.status_code = code
    return httpx.HTTPStatusError("status", request=MagicMock(), response=response)


def named_exception(name: str, message: str = "boom") -> Exception:
    """Exception instance whose ``type(exc).__name__`` is exactly *name*."""
    return type(name, (Exception,), {})(message)


BRANCH_DRIVER: dict[str, Any] = {
    "zoo_missing": lambda: KeyError("model-not-in-zoo"),
    "service_unavailable": lambda: M.EnrichmentUnavailableError("svc down"),
    "connect": lambda: httpx.ConnectError("conn refused"),
    "timeout": lambda: httpx.TimeoutException("too slow"),
    "http_5xx": lambda: http_status_error(503),
    "parse": lambda: ValueError("bad payload"),
    "unexpected": lambda: named_exception("UnexpectedBoom"),
}

# shipped (level, error_type-or-absent, error_category, is_transient-or-absent,
# status_code-or-absent) per branch, measured from the shipped module
BRANCH_SHAPE: dict[str, tuple[str, Any, str, Any, Any]] = {
    "zoo_missing": ("WARNING", None, "parse_error", None, None),
    "service_unavailable": (
        "WARNING",
        "EnrichmentUnavailableError",
        "service_unavailable",
        True,
        None,
    ),
    "connect": ("WARNING", "ConnectError", "service_unavailable", True, None),
    "timeout": ("WARNING", "TimeoutException", "timeout", True, None),
    "http_5xx": ("WARNING", "HTTPStatusError", "server_error", True, 503),
    "parse": ("ERROR", "ValueError", "parse_error", False, None),
    "unexpected": ("ERROR", None, "unexpected", True, None),
}


def expected_extra(method: str, branch: str) -> dict[str, Any]:
    """Shipped ``extra=`` payload for one except branch of one classifier."""
    level, error_type, category, transient, status_code = BRANCH_SHAPE[branch]
    detection_type = "person" if method == "_classify_person_clothing" else "animal"
    operation = CLOTHING_OP if method == "_classify_person_clothing" else PET_OP
    payload: dict[str, Any] = {
        "detection_type": detection_type,
        "operation": operation,
        "error_category": category,
    }
    if error_type is not None:
        payload["error_type"] = error_type
    if transient is not None:
        payload["is_transient"] = transient
    if status_code is not None:
        payload["status_code"] = status_code
    return payload


def make_manager_raising(exc: Exception) -> MagicMock:
    manager = MagicMock()

    @contextlib.asynccontextmanager
    async def _load(_model_name: str) -> Any:
        raise exc
        yield None  # pragma: no cover - makes _load an async context manager

    manager.load = _load
    return manager


def classify_once(method: str, branch: str, class_name: str) -> dict[str, Any]:
    """Drive one except-branch of a private classification helper."""
    pipeline = M.EnrichmentPipeline.__new__(M.EnrichmentPipeline)
    pipeline.model_manager = make_manager_raising(BRANCH_DRIVER[branch]())
    detections = [
        M.DetectionInput(
            id=7,
            class_name=class_name,
            confidence=0.9,
            bbox=M.BoundingBox(x1=1, y1=1, x2=8, y2=8),
        )
    ]
    with capture_extra() as handler:
        outcome = asyncio_run(
            getattr(pipeline, method)(detections, Image.new("RGB", (16, 16), "gray"))
        )
    assert outcome == {}, outcome  # shipped: every branch swallows, returns {}
    return single_noisy_payload(handler.records)


# ---------------------------------------------------------------------------
# A) from_exception  ->  error_type=type(exc).__name__
# ---------------------------------------------------------------------------
def call_from_exception(operation: str, exc: Exception, **kw: Any) -> Any:
    """Call ``EnrichmentError.from_exception`` whether it is shipped (a real
    ``classmethod``) or a plugin-bound plain function (mutmut's extracted body
    drops the decorator), so assertions measure the body, not the binding."""
    raw = M.EnrichmentError.__dict__["from_exception"]
    fn = raw.__func__ if isinstance(raw, classmethod) else raw
    return fn(M.EnrichmentError, operation, exc, **kw)


# (branch, exception factory, shipped category, shipped is_transient,
#  shipped reason, shipped details, shipped error_type)
FROM_EXCEPTION_BRANCHES: list[tuple[str, Any, Any, bool, str, dict[str, Any], str]] = [
    (
        "http_429",
        lambda: http_status_error(429),
        M.ErrorCategory.RATE_LIMITED,
        True,
        "Rate limited (HTTP 429)",
        {"status_code": 429},
        "HTTPStatusError",
    ),
    (
        "http_5xx",
        lambda: http_status_error(503),
        M.ErrorCategory.SERVER_ERROR,
        True,
        "Server error (HTTP 503)",
        {"status_code": 503},
        "HTTPStatusError",
    ),
    (
        "http_4xx",
        lambda: http_status_error(404),
        M.ErrorCategory.CLIENT_ERROR,
        False,
        "Client error (HTTP 404)",
        {"status_code": 404},
        "HTTPStatusError",
    ),
    (
        "ai_unavailable",
        lambda: M.AIServiceError("ai is down"),
        M.ErrorCategory.SERVICE_UNAVAILABLE,
        True,
        "ai is down",
        {},
        "AIServiceError",
    ),
    (
        "parse",
        lambda: ValueError("bad payload"),
        M.ErrorCategory.PARSE_ERROR,
        False,
        "Response parsing failed: bad payload",
        {},
        "ValueError",
    ),
    (
        "validation",
        lambda: AttributeError("missing attr"),
        M.ErrorCategory.VALIDATION_ERROR,
        False,
        "Validation failed: missing attr",
        {},
        "AttributeError",
    ),
    (
        "unexpected",
        lambda: named_exception("UnexpectedBoom"),
        M.ErrorCategory.UNEXPECTED,
        True,
        "Unexpected error: boom",
        {},
        "UnexpectedBoom",
    ),
]


def from_exception_at(label: str) -> tuple[Any, Exception]:
    for name, factory, *_rest in FROM_EXCEPTION_BRANCHES:
        if name == label:
            exc = factory()
            return call_from_exception("battery_op", exc), exc
    raise AssertionError(f"unknown branch {label}")


def test_from_exception_error_type_is_the_raised_class_name() -> None:
    """Pins ``error_type=type(exc).__name__`` at all 7 in-chunk return sites;
    kills the ``type(None).__name__`` shape (which yields "NoneType")."""
    for label, _f, _c, _t, _r, _d, expected_type in FROM_EXCEPTION_BRANCHES:
        error, exc = from_exception_at(label)
        assert error.error_type == type(exc).__name__, label
        assert error.error_type == expected_type, label
        assert error.error_type != "NoneType", label
        assert error.to_dict()["error_type"] == expected_type, label


def test_from_exception_error_type_is_never_none() -> None:
    """Pins that no return site leaves ``error_type`` None/unset; kills the
    ``error_type=None`` shape."""
    for label, _f, _c, _t, _r, _d, expected_type in FROM_EXCEPTION_BRANCHES:
        error, _exc = from_exception_at(label)
        assert error.error_type is not None, label
        assert isinstance(error.error_type, str), label
        assert error.error_type == expected_type, label


def test_from_exception_full_shipped_shape() -> None:
    """Reference pin: every public field of the shipped EnrichmentError per branch."""
    for label, _f, category, transient, reason, details, expected_type in FROM_EXCEPTION_BRANCHES:
        error, _exc = from_exception_at(label)
        assert error.operation == "battery_op", label
        assert error.category is category, label
        assert error.reason == reason, label
        assert error.is_transient is transient, label
        assert error.details == details, label
        assert error.error_type == expected_type, label
    connect = call_from_exception("battery_op", httpx.ConnectError("conn down"))
    assert (connect.error_type, connect.category, connect.reason, connect.is_transient) == (
        "ConnectError",
        M.ErrorCategory.SERVICE_UNAVAILABLE,
        "Service connection failed: conn down",
        True,
    )
    timed = call_from_exception("battery_op", httpx.ConnectTimeout("slow"))
    assert (timed.error_type, timed.category, timed.reason) == (
        "ConnectTimeout",
        M.ErrorCategory.TIMEOUT,
        "Request timed out: slow",
    )
    assert call_from_exception("battery_op", TimeoutError("t")).error_type == "TimeoutError"


def test_from_exception_details_passthrough_and_mutation() -> None:
    """Reference pin (shipped quirk included): ``error_details = details or {}``
    means a *non-empty* caller dict is passed through as the same object and gets
    ``status_code`` added at the HTTP-status sites, while an *empty* dict is
    replaced by a fresh one and the caller's dict is left untouched."""
    details = {"camera": "front-door"}
    error = call_from_exception("battery_op", httpx.ConnectError("x"), details=details)
    assert error.details == {"camera": "front-door"}
    assert error.details is details
    status_details: dict[str, Any] = {"crop": 1}
    status_error = call_from_exception("battery_op", http_status_error(429), details=status_details)
    assert status_details == {"crop": 1, "status_code": 429}
    assert status_error.details is status_details
    # shipped quirk: falsy (empty) details is replaced, not mutated
    empty: dict[str, Any] = {}
    replaced = call_from_exception("battery_op", http_status_error(503), details=empty)
    assert empty == {}
    assert replaced.details == {"status_code": 503}
    assert replaced.details is not empty
    assert call_from_exception("battery_op", RuntimeError("y")).details == {}


# ---------------------------------------------------------------------------
# B) _classify_person_clothing  ->  structured-log key/value pins
# ---------------------------------------------------------------------------
# branches whose shipped extra carries a "detection_type" entry (6 sites)
CLOTHING_DT_BRANCHES = (
    "zoo_missing",
    "service_unavailable",
    "timeout",
    "http_5xx",
    "parse",
    "unexpected",
)
# branches whose shipped extra carries an "operation" entry (7 sites; the
# httpx.ConnectError branch logs "operation" but no "detection_type")
CLOTHING_OP_BRANCHES = CLOTHING_DT_BRANCHES + ("connect",)


def test_classify_person_clothing_shipped_extra_baseline() -> None:
    """Reference pin of the shipped ``extra=`` payload + level of each in-chunk branch."""
    for branch in CLOTHING_OP_BRANCHES:
        payload = classify_once("_classify_person_clothing", branch, "person")
        assert payload["level"] == BRANCH_SHAPE[branch][0], branch
        assert payload["extra"] == expected_extra("_classify_person_clothing", branch), branch


def test_classify_person_clothing_extra_detection_type_key_survives() -> None:
    """shape#21: the key stays literally ``detection_type`` (not "XXdetection_typeXX")."""
    for branch in CLOTHING_DT_BRANCHES:
        payload = classify_once("_classify_person_clothing", branch, "person")
        assert "detection_type" in payload["extra"], branch
        assert "XXdetection_typeXX" not in payload["extra"], branch


def test_classify_person_clothing_extra_detection_type_key_is_lowercase() -> None:
    """shape#22: the key is not upper-cased to ``DETECTION_TYPE``."""
    for branch in CLOTHING_DT_BRANCHES:
        payload = classify_once("_classify_person_clothing", branch, "person")
        assert payload["extra"].get("detection_type") == "person", branch
        assert "DETECTION_TYPE" not in payload["extra"], branch


def test_classify_person_clothing_extra_operation_key_survives() -> None:
    """shape#25: the key stays literally ``operation`` (not "XXoperationXX")."""
    for branch in CLOTHING_OP_BRANCHES:
        payload = classify_once("_classify_person_clothing", branch, "person")
        assert "operation" in payload["extra"], branch
        assert "XXoperationXX" not in payload["extra"], branch


def test_classify_person_clothing_extra_operation_key_is_lowercase() -> None:
    """shape#26: the key is not upper-cased to ``OPERATION``."""
    for branch in CLOTHING_OP_BRANCHES:
        payload = classify_once("_classify_person_clothing", branch, "person")
        assert payload["extra"].get("operation") == CLOTHING_OP, branch
        assert "OPERATION" not in payload["extra"], branch


def test_classify_person_clothing_extra_operation_value_sentinel_free() -> None:
    """shape#27: the value is not the "XXclothing_classificationXX" sentinel."""
    for branch in CLOTHING_OP_BRANCHES:
        payload = classify_once("_classify_person_clothing", branch, "person")
        assert payload["extra"].get("operation") != "XXclothing_classificationXX", branch
        assert payload["extra"].get("operation") == CLOTHING_OP, branch


def test_classify_person_clothing_extra_operation_value_is_snake_case() -> None:
    """shape#28: the value is not "CLOTHING_CLASSIFICATION"."""
    for branch in CLOTHING_OP_BRANCHES:
        payload = classify_once("_classify_person_clothing", branch, "person")
        value = payload["extra"].get("operation")
        assert value != "CLOTHING_CLASSIFICATION", branch
        assert value.islower(), branch
        assert value == CLOTHING_OP, branch


# ---------------------------------------------------------------------------
# C) _classify_pets  ->  structured-log pins (operation key + value)
# ---------------------------------------------------------------------------
PETS_OP_BRANCHES = CLOTHING_OP_BRANCHES


def test_classify_pets_shipped_extra_baseline() -> None:
    """Reference pin of the shipped ``extra=`` payload + level of each pet branch."""
    for branch in PETS_OP_BRANCHES:
        payload = classify_once("_classify_pets", branch, "dog")
        assert payload["level"] == BRANCH_SHAPE[branch][0], branch
        assert payload["extra"] == expected_extra("_classify_pets", branch), branch


def test_classify_pets_extra_operation_key_survives() -> None:
    """shape#25: pet log key stays literally ``operation`` (not "XXoperationXX")."""
    for branch in PETS_OP_BRANCHES:
        payload = classify_once("_classify_pets", branch, "dog")
        assert "operation" in payload["extra"], branch
        assert "XXoperationXX" not in payload["extra"], branch


def test_classify_pets_extra_operation_key_is_lowercase() -> None:
    """shape#26: pet log key is not upper-cased to ``OPERATION``."""
    for branch in PETS_OP_BRANCHES:
        payload = classify_once("_classify_pets", branch, "dog")
        assert payload["extra"].get("operation") == PET_OP, branch
        assert "OPERATION" not in payload["extra"], branch


def test_classify_pets_extra_operation_value_sentinel_free() -> None:
    """shape#27: pet operation value is not "XXpet_classificationXX"."""
    for branch in PETS_OP_BRANCHES:
        payload = classify_once("_classify_pets", branch, "dog")
        assert payload["extra"].get("operation") != "XXpet_classificationXX", branch
        assert payload["extra"].get("operation") == PET_OP, branch


def test_classify_pets_extra_operation_value_is_snake_case() -> None:
    """shape#28: pet operation value is not "PET_CLASSIFICATION"."""
    for branch in PETS_OP_BRANCHES:
        payload = classify_once("_classify_pets", branch, "dog")
        value = payload["extra"].get("operation")
        assert value != "PET_CLASSIFICATION", branch
        assert value.islower(), branch
        assert value == PET_OP, branch


# ---------------------------------------------------------------------------
# D) _run_parallel_enrichment  ->  _should_run_for_quality("standard") gates
# ---------------------------------------------------------------------------
# the 11 in-chunk gated sites, identified by the worker they schedule
GATED_WORKERS: dict[str, str] = {
    # L2438 (service path)
    "unified_vehicle_enrichment": "_enrich_vehicles_via_unified_service",
    # L2448 (service path)
    "unified_animal_enrichment": "_enrich_animals_via_unified_service",
    # L2488
    "clothing_classification": "_safe_classify_person_clothing",
    # L2496
    "vehicle_classification": "_safe_classify_vehicle_types",
    # L2504
    "pet_classification": "_safe_classify_pets",
    # L2512
    "demographics": "_safe_classify_demographics",
    # L2531
    "yolo_world_detection": "_safe_detect_yolo_world",
    # L2543
    "depth_estimation": "_safe_analyze_depth",
    # L2552
    "vehicle_damage": "_safe_detect_vehicle_damage",
    # L2577 (Florence-2 super-phase task)
    "florence_vision_extraction": "_vision_extractor.extract_batch_attributes",
    # L2795 (phase 2, runs in both modes)
    "scene_ocr_crop": "_safe_run_scene_ocr_crops",
}

# every worker _run_parallel_enrichment can reach, so nothing real executes and no
# result-processing branch sees an unexpected shape
STUBBED_WORKERS = (
    "_compute_reid_via_service",
    "_detect_threats_via_service",
    "_enrich_animals_via_unified_service",
    "_enrich_persons_via_unified_service",
    "_enrich_vehicles_via_unified_service",
    "_estimate_poses_via_service",
    "_read_plates",
    "_recognize_actions_from_skeleton",
    "_run_clip_anomaly_detection",
    "_run_household_matching",
    "_run_reid",
    "_safe_analyze_depth",
    "_safe_assess_image_quality",
    "_safe_classify_demographics",
    "_safe_classify_person_clothing",
    "_safe_classify_pets",
    "_safe_classify_vehicle_types",
    "_safe_classify_weather",
    "_safe_clip_scene_classify",
    "_safe_clip_threat_match",
    "_safe_detect_faces",
    "_safe_detect_license_plates",
    "_safe_detect_plates_fast_alpr",
    "_safe_detect_smoke_fire",
    "_safe_detect_vehicle_damage",
    "_safe_detect_violence",
    "_safe_detect_yolo_world",
    "_safe_estimate_poses",
    "_safe_extract_osnet_embeddings",
    "_safe_run_scene_ocr_crops",
    "_safe_run_scene_ocr_frame",
    "_safe_segment_person_clothing",
)


def build_gate_pipeline(*, use_enrichment_service: bool) -> tuple[Any, dict[str, Any]]:
    """Real pipeline with every worker stubbed; ``_quality_level`` = "standard"."""
    with (
        patch(f"{MODULE}.get_vision_extractor", autospec=True) as vision_get,
        patch(f"{MODULE}.get_reid_service", autospec=True),
        patch(f"{MODULE}.get_scene_change_detector", autospec=True),
        patch(f"{MODULE}.get_scene_ocr_service", autospec=True),
    ):
        vision_get.return_value = MagicMock()
        pipeline = M.EnrichmentPipeline(
            model_manager=MagicMock(),
            use_enrichment_service=use_enrichment_service,
            # every gated feature enabled so only the quality gate decides:
            clothing_classification_enabled=True,
            vehicle_classification_enabled=True,
            pet_classification_enabled=True,
            age_classification_enabled=True,
            gender_classification_enabled=True,
            yolo_world_enabled=True,
            depth_estimation_enabled=True,
            vehicle_damage_detection_enabled=True,
            scene_ocr_enabled=True,
            vision_extraction_enabled=True,
            # ungated work switched off so the sweep stays minimal:
            face_detection_enabled=False,
            license_plate_enabled=False,
            ocr_enabled=False,
            violence_detection_enabled=False,
            smoke_fire_detection_enabled=False,
            pose_estimation_enabled=False,
            image_quality_enabled=False,
            weather_classification_enabled=False,
            clothing_segmentation_enabled=False,
            reid_enabled=False,
            osnet_reid_enabled=False,
            scene_change_enabled=False,
            household_matching_enabled=False,
            action_recognition_enabled=False,
            redis_client=None,
        )
    pipeline._quality_level = "standard"
    florence = AsyncMock(return_value=None)
    pipeline._vision_extractor = MagicMock()
    pipeline._vision_extractor.extract_batch_attributes = florence
    spies: dict[str, Any] = {"_vision_extractor.extract_batch_attributes": florence}
    for attr in STUBBED_WORKERS:
        spy = AsyncMock(return_value=None)
        setattr(pipeline, attr, spy)
        spies[attr] = spy
    pipeline._process_phase1_results = MagicMock()
    pipeline._handle_enrichment_error = MagicMock()
    return pipeline, spies


def gate_detections() -> list[Any]:
    return [
        M.DetectionInput(
            id=1, class_name="person", confidence=0.9, bbox=M.BoundingBox(x1=1, y1=1, x2=9, y2=9)
        ),
        # below the 0.7 cascade threshold so the Florence-2 gate actually runs
        M.DetectionInput(
            id=2, class_name="person", confidence=0.4, bbox=M.BoundingBox(x1=2, y1=2, x2=8, y2=8)
        ),
        M.DetectionInput(
            id=3, class_name="car", confidence=0.9, bbox=M.BoundingBox(x1=0, y1=0, x2=5, y2=5)
        ),
        M.DetectionInput(
            id=4, class_name="dog", confidence=0.9, bbox=M.BoundingBox(x1=3, y1=3, x2=7, y2=7)
        ),
    ]


def sweep(quality: str = "standard") -> dict[str, bool]:
    """Run both enrichment-service modes and report which gated workers ran."""
    fired: dict[str, bool] = {}
    for use_service in (False, True):
        pipeline, spies = build_gate_pipeline(use_enrichment_service=use_service)
        pipeline._quality_level = quality
        result = M.EnrichmentResult()
        image = Image.new("RGB", (16, 16), "gray")
        asyncio_run(
            pipeline._run_parallel_enrichment(
                result, image, gate_detections(), {1: image}, "cam-front"
            )
        )
        assert pipeline._handle_enrichment_error.call_count == 0, [
            repr(c.args[1]) for c in pipeline._handle_enrichment_error.call_args_list
        ]
        for label, spy in spies.items():
            fired[label] = fired.get(label, False) or spy.call_count > 0
    return fired


_SWEEP: dict[str, dict[str, bool]] = {}


def gate_fired() -> dict[str, bool]:
    if "standard" not in _SWEEP:
        _SWEEP.update(
            {"standard": sweep("standard"), "full": sweep("full"), "minimal": sweep("minimal")}
        )
    return _SWEEP["standard"]


def gated_attrs() -> list[str]:
    """The 11 worker attributes scheduled behind an in-chunk quality gate."""
    return sorted(set(GATED_WORKERS.values()))


def starved_at_standard() -> list[str]:
    fired = gate_fired()
    return [attr for attr in gated_attrs() if not fired[attr]]


def test_gate_cascade_tasks_scheduled_at_standard_quality() -> None:
    """shape#46 (tier=None): shipped passes the literal "standard" tier, so all 11
    gated workers run at ``_quality_level == "standard"``; None maps to tier 2
    ("full") and starves them."""
    assert starved_at_standard() == [], (
        f"quality-gated workers not scheduled at 'standard': {starved_at_standard()}"
    )


def test_gate_tier_string_is_recognised_by_level_order() -> None:
    """shape#47 (tier="XXstandardXX"): an unrecognised tier resolves to 2 == "full"
    in shipped ``_should_run_for_quality`` and starves the same 11 workers."""
    assert starved_at_standard() == [], (
        f"quality-gated workers not scheduled at 'standard': {starved_at_standard()}"
    )


def test_gate_tier_string_is_case_exact() -> None:
    """shape#48 (tier="STANDARD"): not a ``level_order`` key, so it resolves to 2
    == "full" and starves the same 11 workers."""
    assert starved_at_standard() == [], (
        f"quality-gated workers not scheduled at 'standard': {starved_at_standard()}"
    )


def test_gate_reference_shipped_tier_arithmetic() -> None:
    """Reference pin of shipped ``_should_run_for_quality`` (L2331-2343): unknown
    and None tiers both resolve to 2, which is why "standard" discriminates."""
    pipeline = M.EnrichmentPipeline.__new__(M.EnrichmentPipeline)
    for level, expected in (
        ("minimal", {"minimal": True, "standard": False, "full": False}),
        ("standard", {"minimal": True, "standard": True, "full": False}),
        ("full", {"minimal": True, "standard": True, "full": True}),
    ):
        pipeline._quality_level = level
        for tier, want in expected.items():
            assert pipeline._should_run_for_quality(tier) is want, (level, tier)
        for unknown in (None, "XXstandardXX", "STANDARD", "bogus"):
            assert pipeline._should_run_for_quality(unknown) is (level == "full"), (
                level,
                unknown,
            )
    # shipped default quality level is "full", where all three shapes are inert
    with (
        patch(f"{MODULE}.get_vision_extractor", autospec=True),
        patch(f"{MODULE}.get_reid_service", autospec=True),
        patch(f"{MODULE}.get_scene_change_detector", autospec=True),
        patch(f"{MODULE}.get_scene_ocr_service", autospec=True),
    ):
        default_pipeline = M.EnrichmentPipeline(model_manager=MagicMock())
    assert default_pipeline._quality_level == "full"
    assert default_pipeline._should_run_for_quality("standard") is True
    assert default_pipeline._should_run_for_quality(None) is True


def test_gate_reference_full_and_minimal_sweeps() -> None:
    """Reference pin: at quality "full" every gated worker runs, at "minimal" none
    does (so the "standard" sweep is the discriminating measurement)."""
    gate_fired()  # populates the cache for all three qualities
    for quality, want in (("full", True), ("minimal", False)):
        fired = _SWEEP[quality]
        assert {attr: fired[attr] for attr in gated_attrs()} == {
            attr: want for attr in gated_attrs()
        }, (quality, {a: fired[a] for a in gated_attrs()})
    # ungated workers must run at every quality level (sanity that the sweep
    # actually reached the scheduler rather than short-circuiting)
    for quality in ("standard", "full", "minimal"):
        fired = _SWEEP[quality]
        assert fired["_safe_detect_smoke_fire"] is False  # feature disabled
        assert fired["_enrich_persons_via_unified_service"] is True  # persons gate
