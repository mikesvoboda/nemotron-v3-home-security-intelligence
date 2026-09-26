"""Chunk-21 kill-battery for enrichment_pipeline mutation survivors (120 keys).

Every assertion pins behaviour MEASURED on the pristine shipped module
(/agents/agent-veranda3/workspace/backend/services/enrichment_pipeline.py).

Harness constraint discovered while measuring: the ep_plugin swap EXECs the
mutant body in a *snapshot copy* of the module dict, therefore any patch of a
module global (``patch.object(M, "record_enrichment_model_call")`` etc.) is
INVISIBLE to a mutated body.  Every method-level test below therefore derives
its signal only from objects the mutant body reaches through ``self`` or
through runtime imports (prompt formatters are imported INSIDE
``to_prompt_context``; the real ``yolo_world_loader`` and the real Prometheus
registry in ``backend.core.metrics``), or through the logging handler attached
to ``M.logger`` (the snapshot holds the same logger object).

Shape families covered:

A) ``get_action_risk_weight`` (module level, shipped L282-314) — the three
   keyword-tier loops (high L295-298 -> 1.0, medium L301-305 -> 0.7, benign
   L308-311 -> 0.2, neutral floor L314 -> 0.5) and the ``kw in action_lower``
   membership predicate.
B) ``EnrichmentResult.get_risk_modifiers`` (L1649-1735) — the 15 hard-coded
   modifier constants, the action-weight threshold cascade (L1700-1709) and the
   weather confidence gate (L1716).
C) ``EnrichmentResult.to_prompt_context`` (L1575-1647) — the pose payload
   (L1628-1638), the action payload ``{"0": ...}`` (L1641) and the depth
   argument (L1645).
D) ``EnrichmentPipeline._enrich_persons_via_unified_service`` (L4050-4102) —
   metric labels, per-detection task signature, ``det_id`` derivation (L4078),
   ``asyncio.gather(..., return_exceptions=True)`` (L4082), map-site det_id
   (L4098), elapsed duration (L4084) and completion debug line (L4100).
E) ``EnrichmentPipeline._enrich_animals_via_unified_service`` (L4151-4203) —
   same family plus the map-site det_id (L4189) and pet-only INFO branch
   (L4191-4194).
F) ``EnrichmentPipeline._detect_plates_fast_alpr`` (L6012-6069) — the
   ``results`` accumulator (L6032) and the ``"fast-alpr"`` model key (L6035).
G) ``EnrichmentPipeline._safe_detect_yolo_world`` (L3335-3392) — the suspicious
   class vocabulary (L3353-3362), the low-confidence-person trigger
   (L3363-3365), the ``not A and not B`` skip gate (L3367), the monotonic start
   (L3371), the ``"yolo-world-s"`` model key (L3373), the error counter (L3391)
   and the skip debug message (L3392).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from typing import Any
from unittest.mock import AsyncMock, MagicMock, call, patch

from backend.core.metrics import (
    ENRICHMENT_MODEL_CALLS_TOTAL,
    ENRICHMENT_MODEL_DURATION,
    ENRICHMENT_MODEL_ERRORS_TOTAL,
)
from backend.services.enrichment_pipeline import (
    BoundingBox,
    DetectionInput,
    EnrichmentPipeline,
    EnrichmentResult,
)
from backend.services.pet_classifier_loader import PetClassificationResult

import backend.services.enrichment_pipeline as M

MODULE = "backend.services.enrichment_pipeline"
PROMPTS = "backend.services.prompts"
EXTRA_KEYS = ("service", "detection_id")

PET_ONLY_MSG = "Pet-only event detected via unified enrichment - can skip Nemotron risk analysis"


def run(coro: Any) -> Any:
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------
def mm_ctx() -> MagicMock:
    """Model manager whose ``load(...)`` yields an async-context model stub."""
    mm = MagicMock(name="model_manager")
    mm.load.return_value.__aenter__ = AsyncMock(return_value=MagicMock(name="model"))
    mm.load.return_value.__aexit__ = AsyncMock(return_value=False)
    return mm


def pipeline(**kw: Any) -> EnrichmentPipeline:
    return EnrichmentPipeline(model_manager=mm_ctx(), redis_client=AsyncMock(), **kw)


def det(cls: str, conf: float, id: int | None = None) -> DetectionInput:
    return DetectionInput(
        class_name=cls,
        confidence=conf,
        bbox=BoundingBox(x1=0.0, y1=0.0, x2=10.0, y2=10.0),
        id=id,
    )


def image() -> MagicMock:
    return MagicMock(name="frame")


def pet(confidence: float = 0.95) -> PetClassificationResult:
    return PetClassificationResult(
        animal_type="dog", confidence=confidence, cat_score=0.05, dog_score=confidence
    )


class _Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@contextlib.contextmanager
def capture_logs(level: int = logging.DEBUG) -> Any:
    """Attach a handler to the module logger object itself.

    The plugin's snapshot dict holds the *same* logger object, so mutated
    bodies are captured too.
    """
    handler = _Capture()
    previous = M.logger.level
    M.logger.addHandler(handler)
    M.logger.setLevel(level)
    try:
        yield handler
    finally:
        M.logger.setLevel(previous)
        M.logger.removeHandler(handler)


def messages(records: Any, level: int | None = None) -> list[str]:
    return [r.getMessage() for r in records if level is None or r.levelno == level]


def extra_of(record: logging.LogRecord) -> dict[str, Any]:
    return {k: getattr(record, k, None) for k in EXTRA_KEYS if hasattr(record, k)}


def counter_value(counter: Any, model: Any) -> float:
    """Read (and lazily create) a Prometheus child value from the real registry."""
    return float(counter.labels(model=model)._value.get())


def duration_sum(model: Any) -> float:
    return float(ENRICHMENT_MODEL_DURATION.labels(model=model)._sum._value)


def error_value(model: Any) -> float:
    return counter_value(ENRICHMENT_MODEL_ERRORS_TOTAL, model)


def stub_tasks(p: EnrichmentPipeline, results: list[Any]) -> MagicMock:
    """Async task factory + recording mapper bound ON THE INSTANCE.

    Instance attributes are reached through ``self`` and therefore observed by
    mutated bodies regardless of how their globals were snapshotted.
    """
    single = AsyncMock(name="_enrich_single_detection_unified")
    single.side_effect = list(results)
    p._enrich_single_detection_unified = single
    p._map_unified_to_enrichment_result = MagicMock(name="_map")
    return single


def stub_raising(p: EnrichmentPipeline, exc: BaseException) -> MagicMock:
    single = AsyncMock(name="_enrich_single_detection_unified", side_effect=exc)
    p._enrich_single_detection_unified = single
    p._map_unified_to_enrichment_result = MagicMock(name="_map")
    return single


# ---------------------------------------------------------------------------
# yolo-world drives: the REAL ``detect_with_prompts`` from yolo_world_loader
# runs against a fake ultralytics model, because ``detect_with_prompts`` is a
# module-level import that a mutated body resolves from the plugin snapshot
# (a patch of M.detect_with_prompts would be ignored).
# ---------------------------------------------------------------------------
NAMES = {0: "backpack", 1: "mystery-object"}


class _Tensor:
    def __init__(self, value: Any) -> None:
        import numpy as np

        self._array = np.array(value, dtype=float)

    def cpu(self) -> "_Tensor":
        return self

    def numpy(self) -> Any:
        return self._array


class _Boxes:
    def __init__(self, rows: list[tuple[float, float, float, float, float, int]]) -> None:
        self._rows = rows

    def __len__(self) -> int:
        return len(self._rows)

    @property
    def xyxy(self) -> list[_Tensor]:
        return [_Tensor(row[:4]) for row in self._rows]

    @property
    def conf(self) -> list[_Tensor]:
        return [_Tensor(row[4]) for row in self._rows]

    @property
    def cls(self) -> list[_Tensor]:
        return [_Tensor(row[5]) for row in self._rows]


class _Result:
    def __init__(self, rows: list[tuple[float, float, float, float, float, int]]) -> None:
        self.boxes = _Boxes(rows) if rows else None
        self.names = {int(row[5]): NAMES[int(row[5])] for row in rows}


def yolo_model(
    rows: list[tuple[float, float, float, float, float, int]] | None = None,
) -> MagicMock:
    model = MagicMock(name="yolo-world-model")
    model.set_classes.return_value = None
    model.predict.return_value = [_Result(rows or [])]
    return model


# ===========================================================================
# A) get_action_risk_weight — shipped L282-314
# ===========================================================================
def test_action_risk_weight_high_risk_vocabulary() -> None:
    """Shipped high tier (L295-298) returns exactly 1.0 for its four keywords."""
    for action in (
        "someone is breaking in through the window",
        "vandalizing the mailbox",
        "a person is trying door handle on the front door",
        "hiding behind the shed",
    ):
        assert M.get_action_risk_weight(action) == 1.0, action
    # nothing else may match, so a dropped keyword sends the matching action
    # all the way down to the neutral floor instead of 1.0
    assert M.get_action_risk_weight("standing on the porch") == 0.5
    assert M.get_action_risk_weight("trying the doorknob") == 0.5


def test_action_risk_weight_medium_risk_vocabulary() -> None:
    """Shipped medium tier (L301-305) returns exactly 0.7 for its five keywords."""
    for action in (
        "loitering near the garage",
        "acting suspiciously by the fence",
        "running away from the porch",
        "taking photos of the windows",
        "checking the parked cars",
    ):
        assert M.get_action_risk_weight(action) == 0.7, action
    assert M.get_action_risk_weight("watering the lawn") == 0.5


def test_action_risk_weight_benign_vocabulary_and_tier_order() -> None:
    """Shipped benign tier (L308-311) returns exactly 0.2 for its five keywords.

    The membership predicate is affirmative (``kw in action_lower``): the first
    *absent* keyword only continues the loop, it never triggers the tier (an
    inverted predicate returns 0.2 for the very first non-matching word).  The
    tiers are also ordered high -> medium -> benign, so an action matching both
    the medium and benign vocabularies yields 0.7, never 0.2.
    """
    for action in (
        "delivering a package",
        "knocking on the front door",
        "ringing the doorbell",
        "leaving package at the door",
        "walking normally on the sidewalk",
    ):
        assert M.get_action_risk_weight(action) == 0.2, action
    assert M.get_action_risk_weight("watering the lawn") == 0.5
    # medium tier is evaluated first, so a mixed string yields 0.7 ...
    assert M.get_action_risk_weight("loitering, not knocking") == 0.7
    # ... and the high tier is evaluated before both
    assert M.get_action_risk_weight("breaking in") == 1.0
    assert M.get_action_risk_weight("delivering a package") == 0.2


# ===========================================================================
# B) EnrichmentResult.get_risk_modifiers — shipped L1649-1735
# ===========================================================================
def test_risk_modifiers_violence_formula() -> None:
    """Shipped L1660: ``modifiers["violence"] = 0.5 + (0.5 * confidence)``."""
    r = EnrichmentResult()
    r.violence_detection = types_simple(is_violent=True, confidence=0.5)
    assert r.get_risk_modifiers()["violence"] == 0.75
    r2 = EnrichmentResult()
    r2.violence_detection = types_simple(is_violent=True, confidence=0.6)
    assert r2.get_risk_modifiers()["violence"] == 0.5 + 0.5 * 0.6
    r3 = EnrichmentResult()
    r3.violence_detection = types_simple(is_violent=False, confidence=0.99)
    assert "violence" not in r3.get_risk_modifiers()


def types_simple(**kw: Any) -> Any:
    import types as _types

    return _types.SimpleNamespace(**kw)


def test_risk_modifiers_pet_and_clothing_values() -> None:
    """Shipped constants: pet_only -0.7, confirmed_pet -0.3, suspicious_attire
    0.3, service_uniform -0.2 (L1663-1681)."""
    # a high-confidence household pet with no clothing context is a pet-only
    # event under the shipped ``is_likely_pet_false_positive`` predicate
    only = EnrichmentResult(pet_classifications={"0": pet()})
    assert only.pet_only_event is True
    assert only.get_risk_modifiers()["pet_only"] == -0.7

    # clothing context kills pet-only, so the elif contributes confirmed_pet
    clothed = EnrichmentResult(
        pet_classifications={"0": pet()},
        clothing_classifications={"1": types_simple(is_suspicious=False, is_service_uniform=False)},
    )
    assert clothed.pet_only_event is False
    mods = clothed.get_risk_modifiers()
    assert "pet_only" not in mods
    assert mods["confirmed_pet"] == -0.3

    sus = EnrichmentResult(
        clothing_classifications={"1": types_simple(is_suspicious=True, is_service_uniform=False)}
    )
    assert sus.get_risk_modifiers()["suspicious_attire"] == 0.3

    uni = EnrichmentResult(
        clothing_classifications={"2": types_simple(is_suspicious=False, is_service_uniform=True)}
    )
    assert uni.get_risk_modifiers()["service_uniform"] == -0.2


def test_risk_modifiers_damage_quality_pose_values() -> None:
    """Shipped constants: vehicle_damage_high 0.4 / vehicle_damage 0.15
    (elif), commercial_vehicle -0.1, quality_issues 0.1, quality_change 0.2,
    suspicious_pose 0.25 (L1684-1701)."""
    high = EnrichmentResult(
        vehicle_damage={"v1": types_simple(has_high_security_damage=True, has_damage=True)},
        vehicle_classifications={"v1": types_simple(is_commercial=True)},
        image_quality=types_simple(is_good_quality=False, is_blurry=False),
        quality_change_detected=True,
        pose_results={"0": types_simple(pose_class="crouching", pose_confidence=0.9)},
    )
    mods = high.get_risk_modifiers()
    assert mods["vehicle_damage_high"] == 0.4
    assert "vehicle_damage" not in mods  # elif: high damage wins
    assert mods["commercial_vehicle"] == -0.1
    assert mods["quality_issues"] == 0.1
    assert mods["quality_change"] == 0.2
    assert mods["suspicious_pose"] == 0.25

    low = EnrichmentResult(
        vehicle_damage={"v1": types_simple(has_high_security_damage=False, has_damage=True)}
    )
    lmods = low.get_risk_modifiers()
    assert lmods["vehicle_damage"] == 0.15
    assert "vehicle_damage_high" not in lmods


def test_risk_modifiers_action_weight_thresholds() -> None:
    """Shipped cascade L1700-1709: >=0.7 -> suspicious_action 0.4,
    >=0.5 -> moderate_action 0.2, <=0.3 -> benign_action -0.15.

    ``action_risk_weight`` is patched ON THE CLASS, which the method body reads
    through ``self`` (an instance attribute cannot shadow a dataclass property).
    """

    def mods_for(weight: float) -> dict[str, float]:
        r = EnrichmentResult(action_results={"detected_action": "x", "confidence": 0.9})
        with patch.object(EnrichmentResult, "action_risk_weight", property(lambda self: weight)):
            return r.get_risk_modifiers()

    high = mods_for(0.7)
    assert high["suspicious_action"] == 0.4
    assert "moderate_action" not in high
    at_zero5 = mods_for(0.5)
    assert at_zero5["moderate_action"] == 0.2
    assert "suspicious_action" not in at_zero5 and "benign_action" not in at_zero5
    mid = mods_for(0.6)
    assert mid["moderate_action"] == 0.2
    at_zero3 = mods_for(0.3)
    assert at_zero3["benign_action"] == -0.15
    assert "moderate_action" not in at_zero3
    # 0.3 < w < 0.5 is the shipped dead band: no action modifier at all
    gap = mods_for(0.4)
    assert "benign_action" not in gap
    assert "moderate_action" not in gap
    assert "suspicious_action" not in gap
    # weights above 1.0 still take the first branch (no 1.5-threshold exists)
    assert mods_for(2.0)["suspicious_action"] == 0.4


def test_risk_modifiers_weather_confidence_boundary() -> None:
    """Shipped L1716 gate is inclusive: ``weather.confidence >= 0.5``."""

    def weather_mods(conf: float, condition: str = "rainy", night: bool = False) -> dict:
        r = EnrichmentResult(
            weather_classification=types_simple(confidence=conf, simple_condition=condition),
            is_nighttime=night,
        )
        return r.get_risk_modifiers()

    assert weather_mods(0.5)["weather_rainy"] == -0.15
    assert "weather_rainy" not in weather_mods(0.4)
    assert weather_mods(0.5, "foggy")["weather_low_visibility"] == 0.1
    assert weather_mods(0.5, "clear", night=True)["weather_clear_night"] == 0.25


# ===========================================================================
# C) EnrichmentResult.to_prompt_context — shipped L1575-1647
# The formatters are imported INSIDE the method (L1589), so patching the
# prompts module is observed at call time by shipped code and mutants alike.
# ===========================================================================
def test_prompt_context_pose_payload_shape() -> None:
    """Shipped L1628-1638 builds ``{det_id: {"classification", "confidence"}}``
    from ``pose_results`` and passes ``None`` when it is empty."""
    pose = types_simple(pose_class="crouching", pose_confidence=0.77)
    r = EnrichmentResult(pose_results={"7": pose})
    with patch(f"{PROMPTS}.format_pose_analysis_context", return_value="POSE-SENT") as fmt:
        ctx = r.to_prompt_context()
    assert ctx["pose_analysis"] == "POSE-SENT"
    assert fmt.call_args_list == [call({"7": {"classification": "crouching", "confidence": 0.77}})]

    empty = EnrichmentResult()
    with patch(f"{PROMPTS}.format_pose_analysis_context", return_value="NONE-SENT") as fmt2:
        ctx2 = empty.to_prompt_context()
    assert ctx2["pose_analysis"] == "NONE-SENT"
    assert fmt2.call_args_list == [call(None)]


def test_prompt_context_action_payload_shape() -> None:
    """Shipped L1641 wraps ``action_results`` as ``{"0": action_results}`` and
    passes ``None`` when there is none."""
    actions = {"detected_action": "running", "confidence": 0.9}
    r = EnrichmentResult(action_results=actions)
    with patch(f"{PROMPTS}.format_action_recognition_context", return_value="ACT-SENT") as fmt:
        ctx = r.to_prompt_context()
    assert ctx["action_recognition"] == "ACT-SENT"
    assert fmt.call_args_list == [call({"0": actions})]

    empty = EnrichmentResult()
    with patch(f"{PROMPTS}.format_action_recognition_context", return_value="NONE-SENT") as fmt2:
        ctx2 = empty.to_prompt_context()
    assert ctx2["action_recognition"] == "NONE-SENT"
    assert fmt2.call_args_list == [call(None)]


def test_prompt_context_depth_argument() -> None:
    """Shipped L1645 forwards ``self.depth_analysis`` itself (not ``None``)."""
    depth = types_simple(marker="depth-analysis-object")
    r = EnrichmentResult(depth_analysis=depth)
    with patch(f"{PROMPTS}.format_depth_context", return_value="DEPTH-SENT") as fmt:
        ctx = r.to_prompt_context()
    assert ctx["depth_context"] == "DEPTH-SENT"
    assert fmt.call_args_list == [call(depth)]


# ===========================================================================
# D) EnrichmentPipeline._enrich_persons_via_unified_service — L4050-4102
# ===========================================================================
def test_enrich_persons_task_signature() -> None:
    """Shipped L4077-4079 builds one task per person via
    ``_enrich_single_detection_unified(person, image, "person", camera_id)``."""
    p = pipeline()
    single = stub_tasks(p, [("5", {"k": 0}), ("1", {"k": 1})])
    img = image()
    persons = [det("person", 0.95, id=5), det("person", 0.85, id=None)]
    with capture_logs():
        run(p._enrich_persons_via_unified_service(persons, img, "cam-1", EnrichmentResult()))
    assert [c.args for c in single.call_args_list] == [
        (persons[0], img, "person", "cam-1"),
        (persons[1], img, "person", "cam-1"),
    ]


def test_enrich_persons_metric_labels() -> None:
    """Shipped L4073/L4084: exactly one call counter and one duration sample
    under the label ``unified-enrich-person``, nothing under look-alike labels,
    and the duration is the *elapsed* counter difference (small, non-negative)."""
    p = pipeline()
    stub_tasks(p, [("5", {"k": 0})])
    calls_before = counter_value(ENRICHMENT_MODEL_CALLS_TOTAL, "unified-enrich-person")
    duration_before = duration_sum("unified-enrich-person")
    wrong_calls = {
        label: counter_value(ENRICHMENT_MODEL_CALLS_TOTAL, label)
        for label in (None, "XXunified-enrich-personXX", "UNIFIED-ENRICH-PERSON")
    }
    wrong_durations = {
        label: duration_sum(label)
        for label in (None, "XXunified-enrich-personXX", "UNIFIED-ENRICH-PERSON")
    }
    with capture_logs():
        run(
            p._enrich_persons_via_unified_service(
                [det("person", 0.9, id=5)], image(), "c", EnrichmentResult()
            )
        )
    assert counter_value(ENRICHMENT_MODEL_CALLS_TOTAL, "unified-enrich-person") == calls_before + 1
    observed = duration_sum("unified-enrich-person") - duration_before
    assert 0 <= observed < 10.0, f"duration is not an elapsed time: {observed}"
    for label, before in wrong_calls.items():
        assert counter_value(ENRICHMENT_MODEL_CALLS_TOTAL, label) == before, label
    for label, before in wrong_durations.items():
        assert duration_sum(label) == before, label


def test_enrich_persons_map_receives_task_det_id() -> None:
    """Shipped L4097-4098 unpacks ``(det_id, unified)`` from the task result and
    passes that det_id (never ``None``) to the mapper."""
    p = pipeline()
    stub_tasks(p, [("7", {"pose": "stand"})])
    r = EnrichmentResult()
    with capture_logs():
        run(p._enrich_persons_via_unified_service([det("person", 0.9, id=7)], image(), "c", r))
    assert p._map_unified_to_enrichment_result.call_args_list == [
        call(r, "7", {"pose": "stand"}, "person")
    ]


def test_enrich_persons_failure_is_collected_not_raised() -> None:
    """Shipped ``asyncio.gather(..., return_exceptions=True)`` (L4082) collects a
    failed person task instead of re-raising: the failure is logged with
    ``extra={"service": "unified-enrich", "detection_id": det_id}`` (L4086-4091),
    counted via ``record_enrichment_model_error``, and nothing is mapped."""
    p = pipeline()
    stub_raising(p, RuntimeError("person-service-down"))
    r = EnrichmentResult()
    errors_before = error_value("unified-enrich-person")
    raised: BaseException | None = None
    with capture_logs(logging.WARNING) as logs:
        try:
            run(p._enrich_persons_via_unified_service([det("person", 0.9, id=4)], image(), "c", r))
        except BaseException as exc:  # noqa: BLE001 - shipped never raises
            raised = exc
    assert raised is None, f"shipped collects the failure; mutant re-raised {raised!r}"
    assert p._map_unified_to_enrichment_result.call_args_list == []
    noisy = [x for x in logs.records if x.levelno >= logging.WARNING]
    assert len(noisy) == 1, messages(logs.records)
    assert "Unified enrichment failed for person 4" in noisy[0].getMessage()
    assert extra_of(noisy[0]) == {"service": "unified-enrich", "detection_id": "4"}
    assert error_value("unified-enrich-person") == errors_before + 1


def test_enrich_persons_completion_debug_log() -> None:
    """Shipped L4100 emits exactly
    ``Unified person enrichment complete: {N} persons in {duration:.2f}s``."""
    p = pipeline()
    stub_tasks(p, [("1", {"k": 0}), ("2", {"k": 1})])
    with capture_logs() as logs:
        run(
            p._enrich_persons_via_unified_service(
                [det("person", 0.9, id=1), det("person", 0.8, id=2)],
                image(),
                "c",
                EnrichmentResult(),
            )
        )
    completion = [m for m in messages(logs.records, logging.DEBUG) if "enrichment complete" in m]
    assert len(completion) == 1, messages(logs.records)
    assert re.fullmatch(
        r"Unified person enrichment complete: 2 persons in \d+\.\d{2}s", completion[0]
    ), completion


# ===========================================================================
# E) EnrichmentPipeline._enrich_animals_via_unified_service — L4151-4203
# ===========================================================================
def test_enrich_animals_task_signature() -> None:
    """Shipped L4178-4179 builds one task per animal via
    ``_enrich_single_detection_unified(animal, image, "animal")`` (no camera)."""
    p = pipeline()
    single = stub_tasks(p, [("3", {"k": 0})])
    img = image()
    animals = [det("dog", 0.9, id=3)]
    with capture_logs():
        run(p._enrich_animals_via_unified_service(animals, img, EnrichmentResult()))
    assert [c.args for c in single.call_args_list] == [(animals[0], img, "animal")]


def test_enrich_animals_metric_labels() -> None:
    """Shipped L4174/L4184: one call counter and one *elapsed* duration sample
    under ``unified-enrich-animal``, nothing under look-alike labels."""
    p = pipeline()
    stub_tasks(p, [("3", {"k": 0})])
    calls_before = counter_value(ENRICHMENT_MODEL_CALLS_TOTAL, "unified-enrich-animal")
    duration_before = duration_sum("unified-enrich-animal")
    wrong_calls = {
        label: counter_value(ENRICHMENT_MODEL_CALLS_TOTAL, label)
        for label in (None, "XXunified-enrich-animalXX", "UNIFIED-ENRICH-ANIMAL")
    }
    wrong_durations = {
        label: duration_sum(label)
        for label in (None, "XXunified-enrich-animalXX", "UNIFIED-ENRICH-ANIMAL")
    }
    with capture_logs():
        run(
            p._enrich_animals_via_unified_service(
                [det("dog", 0.9, id=3)], image(), EnrichmentResult()
            )
        )
    assert counter_value(ENRICHMENT_MODEL_CALLS_TOTAL, "unified-enrich-animal") == calls_before + 1
    observed = duration_sum("unified-enrich-animal") - duration_before
    assert 0 <= observed < 10.0, f"duration is not an elapsed time: {observed}"
    for label, before in wrong_calls.items():
        assert counter_value(ENRICHMENT_MODEL_CALLS_TOTAL, label) == before, label
    for label, before in wrong_durations.items():
        assert duration_sum(label) == before, label


def test_enrich_animals_map_receives_task_det_id() -> None:
    """Shipped L4188-4189 unpacks ``(det_id, unified)`` and passes that det_id
    (never ``None``) to the mapper."""
    p = pipeline()
    stub_tasks(p, [("7", {"pet": "dog"})])
    r = EnrichmentResult()
    with (
        patch.object(EnrichmentResult, "pet_only_event", property(lambda self: False)),
        capture_logs(),
    ):
        run(p._enrich_animals_via_unified_service([det("dog", 0.9, id=7)], image(), r))
    assert p._map_unified_to_enrichment_result.call_args_list == [
        call(r, "7", {"pet": "dog"}, "animal")
    ]


def test_enrich_animals_failure_is_collected_not_raised() -> None:
    """Shipped ``return_exceptions=True`` (L4182) collects a failed animal task:
    logged with structured extras, error-counted, nothing mapped, no raise."""
    p = pipeline()
    stub_raising(p, RuntimeError("animal-service-down"))
    r = EnrichmentResult()
    errors_before = error_value("unified-enrich-animal")
    raised: BaseException | None = None
    with capture_logs(logging.WARNING) as logs:
        try:
            run(p._enrich_animals_via_unified_service([det("dog", 0.9, id=3)], image(), r))
        except BaseException as exc:  # noqa: BLE001 - shipped never raises
            raised = exc
    assert raised is None, f"shipped collects the failure; mutant re-raised {raised!r}"
    assert p._map_unified_to_enrichment_result.call_args_list == []
    noisy = [x for x in logs.records if x.levelno >= logging.WARNING]
    assert len(noisy) == 1, messages(logs.records)
    assert "Unified enrichment failed for animal 3" in noisy[0].getMessage()
    assert extra_of(noisy[0]) == {"service": "unified-enrich", "detection_id": "3"}
    assert error_value("unified-enrich-animal") == errors_before + 1


def test_enrich_animals_completion_debug_log() -> None:
    """Shipped L4201 emits exactly
    ``Unified animal enrichment complete: {N} animals in {duration:.2f}s``."""
    p = pipeline()
    stub_tasks(p, [("1", {"k": 0})])
    with capture_logs() as logs:
        run(
            p._enrich_animals_via_unified_service(
                [det("dog", 0.9, id=1)], image(), EnrichmentResult()
            )
        )
    completion = [m for m in messages(logs.records, logging.DEBUG) if "enrichment complete" in m]
    assert len(completion) == 1, messages(logs.records)
    assert re.fullmatch(
        r"Unified animal enrichment complete: 1 animals in \d+\.\d{2}s", completion[0]
    ), completion


def test_enrich_animals_pet_only_log_requires_both_conditions() -> None:
    """Shipped L4191 logs the exact INFO line only when the result has BOTH
    ``pet_classifications`` AND ``pet_only_event`` (conjunction, not disjunction):
    each condition on its own logs nothing."""
    # classifications present, pet_only_event False -> no INFO
    p = pipeline()
    stub_tasks(p, [("7", {"pet": "dog"})])
    r = EnrichmentResult(pet_classifications={"7": pet()})
    with (
        patch.object(EnrichmentResult, "pet_only_event", property(lambda self: False)),
        capture_logs() as logs,
    ):
        run(p._enrich_animals_via_unified_service([det("dog", 0.9, id=7)], image(), r))
    assert messages(logs.records, logging.INFO) == []

    # pet_only_event True but no classifications -> no INFO
    p2 = pipeline()
    stub_tasks(p2, [("7", {"pet": "dog"})])
    r2 = EnrichmentResult()
    with (
        patch.object(EnrichmentResult, "pet_only_event", property(lambda self: True)),
        capture_logs() as logs2,
    ):
        run(p2._enrich_animals_via_unified_service([det("dog", 0.9, id=7)], image(), r2))
    assert messages(logs2.records, logging.INFO) == []

    # both -> exactly the shipped INFO sentence
    p3 = pipeline()
    stub_tasks(p3, [("7", {"pet": "dog"})])
    r3 = EnrichmentResult(pet_classifications={"7": pet()})
    with (
        patch.object(EnrichmentResult, "pet_only_event", property(lambda self: True)),
        capture_logs() as logs3,
    ):
        run(p3._enrich_animals_via_unified_service([det("dog", 0.9, id=7)], image(), r3))
    assert messages(logs3.records, logging.INFO) == [PET_ONLY_MSG]


# ===========================================================================
# F) EnrichmentPipeline._detect_plates_fast_alpr — L6012-6069
# ===========================================================================
def test_fast_alpr_plate_accumulation_and_model_key() -> None:
    """Shipped L6032 starts from a fresh list and appends one
    ``LicensePlateResult`` per plate; L6035 loads ``"fast-alpr"``.  The OCR
    entry point is imported INSIDE the method, so the patch is observed."""
    import backend.services.fast_alpr_loader as F

    p = pipeline()
    p._get_image_for_detection = MagicMock(return_value=image())
    p._crop_to_bbox = AsyncMock(return_value=image())
    vehicles = [det("car", 0.95, id=11)]
    with patch.object(
        F, "run_fast_alpr", new=AsyncMock(return_value=[plate("AAA111"), plate("BBB222")])
    ) as rf:
        out = run(p._detect_plates_fast_alpr(vehicles, {11: image()}))
    assert rf.await_count == 1
    assert p.model_manager.load.call_args_list == [call("fast-alpr")]
    assert isinstance(out, list) and len(out) == 2
    assert [x.text for x in out] == ["AAA111", "BBB222"]
    assert [x.bbox.to_dict() for x in out] == [
        {"x1": 1, "y1": 2, "x2": 3, "y2": 4, "confidence": 0.0}
    ] * 2
    assert [x.confidence for x in out] == [0.91, 0.91]
    assert [x.ocr_confidence for x in out] == [0.82, 0.82]
    assert [x.source_detection_id for x in out] == [11, 11]

    p2 = pipeline()
    assert run(p2._detect_plates_fast_alpr([], {})) == []


def plate(text: str) -> MagicMock:
    handle = MagicMock(name="alpr-plate")
    handle.bbox = [1, 2, 3, 4]
    handle.detection_confidence = 0.91
    handle.text = text
    handle.confidence = 0.82
    return handle


# ===========================================================================
# G) EnrichmentPipeline._safe_detect_yolo_world — L3335-3392
# ===========================================================================
def _drive_yolo(
    detections: list[DetectionInput],
    rows: list[tuple[float, float, float, float, float, int]] | None = None,
    load_effect: BaseException | None = None,
) -> tuple[MagicMock, list[dict[str, Any]], list[logging.LogRecord]]:
    """Run the shipped method with the REAL loader pipeline over a fake model."""
    p = pipeline()
    model = yolo_model(rows)
    p.model_manager.load.return_value.__aenter__ = AsyncMock(return_value=model)
    if load_effect is not None:
        p.model_manager.load.side_effect = load_effect
    with capture_logs() as logs:
        out = run(p._safe_detect_yolo_world(image(), detections))
    return p, out, logs.records


def test_yolo_world_suspicious_class_vocabulary() -> None:
    """Shipped trigger set L3353-3362 is matched against ``d.class_name.lower()``:
    every member class (any case) opens the gate and reaches ``load("yolo-world-s")``;
    a single non-member class keeps the model unloaded."""
    for cls in (
        "backpack",
        "suitcase",
        "handbag",
        "umbrella",
        "knife",
        "scissors",
        "baseball bat",
        "unknown",
    ):
        p, out, _ = _drive_yolo([det(cls, 0.95)])
        assert out == [], cls
        assert p.model_manager.load.call_args_list == [call("yolo-world-s")], cls

    # mixed-case spellings still trigger (``.lower()`` normalisation)
    p, out, _ = _drive_yolo([det("SCISSORS", 0.7)])
    assert p.model_manager.load.call_count == 1
    p, out, _ = _drive_yolo([det("Baseball Bat", 0.7)])
    assert p.model_manager.load.call_count == 1

    # a single non-member class (confident) opens neither gate -> skip entirely
    p2, out2, _ = _drive_yolo([det("car", 0.95)])
    assert out2 == []
    assert p2.model_manager.load.call_args_list == []


def test_yolo_world_person_low_confidence_and_gate() -> None:
    """Shipped L3363-3367: only a ``person`` with ``confidence < 0.6`` sets the
    second trigger, and the skip gate is ``not A and not B`` — the model runs
    whenever EITHER trigger is true."""
    cases: list[tuple[list[DetectionInput], int]] = [
        ([det("person", 0.42)], 1),  # low-confidence person alone triggers
        ([det("person", 0.95)], 0),  # confident person does not
        ([det("person", 0.6)], 0),  # 0.6 is not < 0.6
        ([det("car", 0.1)], 0),  # non-person low confidence is irrelevant
        ([det("knife", 0.95), det("person", 0.95)], 1),  # one true flag suffices
        ([det("car", 0.95), det("dog", 0.95)], 0),  # neither flag -> skip
    ]
    for detections, expected_loads in cases:
        p, out, _ = _drive_yolo(detections)
        assert out == [], detections
        assert p.model_manager.load.call_count == expected_loads, detections


def test_yolo_world_happy_path_metrics_and_priority() -> None:
    """Shipped L3371-3389: monotonic start so the observed duration is elapsed
    time, both metric calls labelled ``yolo_world_detection``, and ``priority``
    annotated on every returned detection."""
    rows = [(1.0, 2.0, 3.0, 4.0, 0.5, 0), (5.0, 6.0, 7.0, 8.0, 0.4, 1)]
    calls_before = counter_value(ENRICHMENT_MODEL_CALLS_TOTAL, "yolo_world_detection")
    errors_before = error_value("yolo_world_detection")
    duration_before = duration_sum("yolo_world_detection")
    wrong_calls = {
        label: counter_value(ENRICHMENT_MODEL_CALLS_TOTAL, label)
        for label in (None, "XXyolo_world_detectionXX", "YOLO_WORLD_DETECTION")
    }
    p, out, records = _drive_yolo([det("knife", 0.9)], rows)
    assert p.model_manager.load.call_args_list == [call("yolo-world-s")]
    assert [x["class_name"] for x in out] == ["backpack", "mystery-object"]
    assert [x["priority"] for x in out] == ["medium", "low"]
    assert counter_value(ENRICHMENT_MODEL_CALLS_TOTAL, "yolo_world_detection") == calls_before + 1
    assert error_value("yolo_world_detection") == errors_before
    observed = duration_sum("yolo_world_detection") - duration_before
    assert 0 <= observed < 10.0, f"duration is not an elapsed time: {observed}"
    for label, before in wrong_calls.items():
        assert counter_value(ENRICHMENT_MODEL_CALLS_TOTAL, label) == before, label
    assert any(
        m.startswith("YOLO-World detected 2 objects in ") for m in messages(records, logging.DEBUG)
    ), messages(records)


def test_yolo_world_error_path_metrics_and_log() -> None:
    """Shipped L3390-3392: a load failure records
    ``record_enrichment_model_error("yolo_world_detection")`` and logs the
    f-string ``YOLO-World detection skipped: <exc>``, returning ``[]``."""
    errors_before = error_value("yolo_world_detection")
    wrong = {
        label: error_value(label)
        for label in (None, "XXyolo_world_detectionXX", "YOLO_WORLD_DETECTION")
    }
    p, out, records = _drive_yolo([det("knife", 0.9)], load_effect=RuntimeError("boom-boom"))
    assert out == []
    assert error_value("yolo_world_detection") == errors_before + 1
    for label, before in wrong.items():
        assert error_value(label) == before, label
    assert "YOLO-World detection skipped: boom-boom" in messages(records)
