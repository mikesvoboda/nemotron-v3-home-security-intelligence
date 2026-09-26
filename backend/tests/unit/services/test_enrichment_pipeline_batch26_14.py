"""Chunk-14 kill-battery: EnrichmentResult.get_summary_flags + EnrichmentPipeline._safe_classify_demographics.

Every assertion was PROBED against pristine shipped code and pins SHIPPED
behaviour (shipped source: /agents/agent-veranda3/workspace
backend/services/enrichment_pipeline.py — get_summary_flags lines 1750-1858,
_safe_classify_demographics lines 3187-3264).

Mutants are swapped in by the ep_plugin pytest plugin via EP_MUT. Both targets
are class methods, so they are reached through the class
(``M.EnrichmentPipeline._safe_classify_demographics(...)`` and
``EnrichmentResult(...).get_summary_flags()``), which is what the plugin
setattr's on the live class.

Two seam details that were MEASURED, not assumed:
* ep_plugin exec's a mutant body in a SNAPSHOT of the live module dict taken at
  bind time — i.e. before any in-test ``patch`` runs. So the module-level names a
  mutated body looks up globally (``classify_ages_batch``,
  ``classify_genders_batch``, ``record_enrichment_model_error``) are installed by
  a MODULE-scoped autouse fixture (module fixtures always set up before function
  fixtures); each test only reconfigures those mock objects, which the snapshot
  observes.
* ``self.has_suspicious_action`` / ``self.action_risk_weight`` resolve through the
  CLASS at call time, so pinning them with ``patch.object(cls, name, new=property(...))``
  is observed by the mutated body too.
"""

from __future__ import annotations

import asyncio
from contextlib import ExitStack
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

import backend.services.enrichment_pipeline as M
from backend.services.age_classifier_loader import AgeClassificationResult
from backend.services.enrichment_pipeline import (
    BoundingBox,
    DetectionInput,
    EnrichmentPipeline,
    EnrichmentResult,
)
from backend.services.gender_classifier_loader import GenderClassificationResult
from backend.services.vitpose_loader import PoseResult
from backend.services.weather_loader import WeatherResult

pytestmark = pytest.mark.timeout(30)

AGE_LABELS = [
    "infant 0-2 years",
    "child 3-12 years",
    "teenager 13-19 years",
    "adult 20-39 years",
    "middle-aged adult 40-59 years",
    "senior citizen 60+ years",
]
_REAL_CROP = object()


# --------------------------------------------------------------------------- #
# shipped-behaviour fixtures (all probe-derived)
# --------------------------------------------------------------------------- #
def _image() -> Image.Image:
    return Image.new("RGB", (640, 480), color=(128, 128, 128))


def _bbox() -> BoundingBox:
    return BoundingBox(x1=10.0, y1=10.0, x2=110.0, y2=210.0)


def _person(det_id: Any) -> DetectionInput:
    return DetectionInput(class_name="person", confidence=0.9, bbox=_bbox(), id=det_id)


def _pose(cls: str, conf: float) -> PoseResult:
    return PoseResult(keypoints={}, pose_class=cls, pose_confidence=conf)


def _weather(simple: str, conf: float) -> WeatherResult:
    return WeatherResult(
        condition=f"{simple}/variant", simple_condition=simple, confidence=conf, all_scores={}
    )


def _age(group: str = "adult") -> AgeClassificationResult:
    return AgeClassificationResult(
        age_group=group, confidence=0.9, display_name="Adult", all_scores={group: 0.9}
    )


def _gender(gender: str = "female") -> GenderClassificationResult:
    return GenderClassificationResult(
        gender=gender, confidence=0.8, male_score=0.2, female_score=0.8
    )


def _flag(flags: list[dict[str, str]], type_: str) -> dict[str, str] | None:
    hits = [f for f in flags if f.get("type") == type_]
    return hits[0] if len(hits) == 1 else None


def _strs(mock: Any) -> list[Any]:
    """First string positional arg of every recorded call (self-tolerant)."""
    out: list[Any] = []
    for call in mock.call_args_list:
        first: Any = None
        for a in call.args:
            if isinstance(a, str):
                first = a
                break
        out.append(first)
    return out


def _action_flags(
    ar: dict[str, Any],
    *,
    suspicious: bool | None = None,
    weight: float | None = None,
) -> list[dict[str, str]]:
    """``get_summary_flags()`` for an action result, with the two action properties
    (which read the module-level ``is_suspicious_action`` / ``get_action_risk_weight``)
    pinned on the class so the mutated body observes them."""
    with ExitStack() as st:
        if suspicious is not None:
            st.enter_context(
                patch.object(
                    EnrichmentResult,
                    "has_suspicious_action",
                    new=property(lambda _self: suspicious),
                )
            )
        if weight is not None:
            st.enter_context(
                patch.object(
                    EnrichmentResult,
                    "action_risk_weight",
                    new=property(lambda _self: weight),
                )
            )
        return EnrichmentResult(action_results=ar).get_summary_flags()


@dataclass
class _AsyncCM:
    """Async context manager whose ``__aenter__`` value is ``payload``."""

    payload: Any = None

    async def __aenter__(self) -> Any:
        return self.payload

    async def __aexit__(self, *exc: Any) -> bool:
        return False


def _mgr(payload: Any = None) -> MagicMock:
    """ModelManager double: ``load(name)`` -> async CM yielding ``payload``."""
    mgr = MagicMock(name="model_manager")
    mgr.load = MagicMock(name="load", side_effect=lambda _name: _AsyncCM(payload))
    return mgr


def _pipeline(mgr: MagicMock) -> EnrichmentPipeline:
    with (
        patch("backend.services.enrichment_pipeline.get_vision_extractor", autospec=True),
        patch("backend.services.enrichment_pipeline.get_reid_service", autospec=True),
        patch("backend.services.enrichment_pipeline.get_scene_change_detector", autospec=True),
    ):
        return EnrichmentPipeline(model_manager=mgr)


@pytest.fixture(scope="module", autouse=True)
def stubs() -> Any:
    """Module-level collaborator doubles, installed for the WHOLE module.

    Required because ep_plugin binds the mutant from a module-dict snapshot taken
    before function-scoped patches run (see module docstring).
    """
    with ExitStack() as st:
        ages = AsyncMock(name="classify_ages_batch")
        genders = AsyncMock(name="classify_genders_batch")
        errors = MagicMock(name="record_enrichment_model_error")
        st.enter_context(patch.object(M, "classify_ages_batch", new=ages))
        st.enter_context(patch.object(M, "classify_genders_batch", new=genders))
        st.enter_context(patch.object(M, "record_enrichment_model_error", new=errors))
        yield SimpleNamespace(ages=ages, genders=genders, errors=errors)


@dataclass
class _Demo:
    """Outcome of one ``_safe_classify_demographics`` probe."""

    out: Any
    mgr: MagicMock
    ages: Any
    genders: Any
    errors: Any
    debug: MagicMock
    seen: dict[str, Any]


def _effect(target: Any) -> Any:
    """list/tuple -> callable returning it; any other value used as side_effect."""
    if isinstance(target, (list, tuple)):
        ret = list(target)
        return lambda *_a, **_k: ret
    return target


def _demographics(
    stubs: Any,
    persons: Any,
    *,
    ages: Any,
    genders: Any,
    crop: Any = _REAL_CROP,
    mgr: MagicMock | None = None,
) -> _Demo:
    """Drive the live ``_safe_classify_demographics`` with every collaborator watched.

    ``ages`` / ``genders``: a list is what that loader returns; any other value
    becomes that loader's side_effect (raise, capture args, ...).
    ``crop``: _REAL_CROP -> shipped ``_crop_to_bbox`` (real PIL crop); any other
    value -> stubbed cropper (list/tuple/callable as side_effect, else constant).
    """
    return asyncio.run(
        _ademographics(stubs, persons, ages=ages, genders=genders, crop=crop, mgr=mgr)
    )


async def _ademographics(
    stubs: Any,
    persons: Any,
    *,
    ages: Any,
    genders: Any,
    crop: Any = _REAL_CROP,
    mgr: MagicMock | None = None,
) -> _Demo:
    for m in (stubs.ages, stubs.genders, stubs.errors):
        m.reset_mock(return_value=True, side_effect=True)
    stubs.ages.side_effect = _effect(ages)
    stubs.genders.side_effect = _effect(genders)
    mgr = _mgr() if mgr is None else mgr
    pipeline = _pipeline(mgr)
    image = _image()
    seen: dict[str, Any] = {}
    with ExitStack() as st:
        if crop is not _REAL_CROP:
            se: Any = crop
            if not (isinstance(crop, (list, tuple)) or callable(crop)):
                se = lambda *_a, **_k: crop  # noqa: E731
                st.enter_context(
                    patch.object(
                        M.EnrichmentPipeline, "_crop_to_bbox", new=AsyncMock(return_value=crop)
                    )
                )
            else:
                st.enter_context(
                    patch.object(
                        M.EnrichmentPipeline, "_crop_to_bbox", new=AsyncMock(side_effect=se)
                    )
                )
        debug = st.enter_context(patch.object(M.logger, "debug", new=MagicMock()))
        out = await M.EnrichmentPipeline._safe_classify_demographics(pipeline, persons, image)
    return _Demo(out, mgr, stubs.ages, stubs.genders, stubs.errors, debug, seen)


# --------------------------------------------------------------------------- #
# A. quality-change flag — shipped lines 1806-1813 ("severity": "alert" @1811)
# --------------------------------------------------------------------------- #
def test_keys_060_061_quality_flag_exact_dict() -> None:
    """60 ("XXseverityXX") / 61 ("SEVERITY") drop or rename the severity key of the
    shipped quality_issue flag."""
    result = EnrichmentResult(
        quality_change_detected=True, quality_change_description="Sudden quality degradation"
    )
    assert result.get_summary_flags() == [
        {
            "type": "quality_issue",
            "description": "Sudden quality degradation",
            "severity": "alert",
        }
    ]


def test_keys_062_063_quality_severity_is_alert() -> None:
    """62 ("XXalertXX") / 63 ("ALERT")."""
    result = EnrichmentResult(
        quality_change_detected=True, quality_change_description="blur detected"
    )
    assert result.get_summary_flags() == [
        {
            "type": "quality_issue",
            "description": "blur detected",
            "severity": "alert",
        }
    ]


# --------------------------------------------------------------------------- #
# B. suspicious poses — shipped lines 1816-1825
# --------------------------------------------------------------------------- #
def test_keys_067_068_running_is_a_suspicious_pose() -> None:
    """67 ("XXrunningXX") / 68 ("RUNNING") remove "running" from the set."""
    result = EnrichmentResult(pose_results={"3": _pose("running", 0.9)})
    assert result.get_summary_flags() == [
        {
            "type": "suspicious_pose",
            "description": "Person 3: running (90% confidence)",
            "severity": "warning",
        }
    ]


def test_keys_069_070_lying_is_a_suspicious_pose() -> None:
    """69 ("XXlyingXX") / 70 ("LYING") remove "lying" from the set."""
    result = EnrichmentResult(pose_results={"3": _pose("lying", 0.9)})
    assert result.get_summary_flags() == [
        {
            "type": "suspicious_pose",
            "description": "Person 3: lying (90% confidence)",
            "severity": "warning",
        }
    ]


def test_key_071_pose_gate_requires_both_clauses() -> None:
    """71 (``and`` -> ``or``) flags a high-confidence NON-suspicious pose."""
    result = EnrichmentResult(pose_results={"3": _pose("standing", 0.99)})
    assert result.get_summary_flags() == []


def test_key_073_pose_gate_is_strictly_above_half() -> None:
    """73 (``>`` -> ``>=``): shipped drops a pose at exactly 0.5 confidence."""
    result = EnrichmentResult(pose_results={"3": _pose("crouching", 0.5)})
    assert result.get_summary_flags() == []


def test_keys_082_084_086_087_088_089_090_crouching_severity_is_alert() -> None:
    """Pose severity, crouching side: 82/83 (severity key), 86/87 ("alert" text),
    88 (``!=``), 89/90 ("crouching" literal), 84 (``and False``)."""
    result = EnrichmentResult(pose_results={"3": _pose("crouching", 0.9)})
    assert result.get_summary_flags() == [
        {
            "type": "suspicious_pose",
            "description": "Person 3: crouching (90% confidence)",
            "severity": "alert",
        }
    ]


def test_guard_pose_set_membership_is_case_sensitive() -> None:
    """Shipped set membership is exact too: an uppercase pose_class is not in
    {"crouching", "running", "lying"} at all, so no flag is emitted (anti-vacuity
    for the pose-set and severity-literal pins)."""
    result = EnrichmentResult(pose_results={"3": _pose("CROUCHING", 0.9)})
    assert result.get_summary_flags() == []


def test_keys_085_091_092_running_severity_is_warning() -> None:
    """Pose severity, non-crouching side: 85 (``or True`` -> alert),
    84 (``and False``), 88 (``!=``), 91 ("XXwarningXX"), 92 ("WARNING")."""
    result = EnrichmentResult(pose_results={"3": _pose("running", 0.9)})
    assert result.get_summary_flags() == [
        {
            "type": "suspicious_pose",
            "description": "Person 3: running (90% confidence)",
            "severity": "warning",
        }
    ]


# --------------------------------------------------------------------------- #
# C. suspicious action — shipped lines 1828-1841
# --------------------------------------------------------------------------- #
def test_key_093_action_gate_requires_suspicious_action() -> None:
    """93 (``and`` -> ``or``) emits a flag even when has_suspicious_action is False."""
    flags = _action_flags(
        {"detected_action": "walking normally", "confidence": 0.9}, suspicious=False
    )
    assert flags == []


def test_keys_096_098_detected_action_default_is_unknown() -> None:
    """96 (default ``None``) / 98 (default arg dropped -> ``None``) render
    ``None (...)`` instead of the shipped ``unknown (...)``."""
    flags = _action_flags({"confidence": 0.4}, suspicious=True, weight=0.5)
    assert flags == [
        {
            "type": "suspicious_action",
            "description": "unknown (40% confidence)",
            "severity": "warning",
        }
    ]


def test_keys_101_102_unknown_default_text() -> None:
    """101 ("XXunknownXX") / 102 ("UNKNOWN")."""
    flags = _action_flags({"confidence": 0.25}, suspicious=True, weight=0.5)
    assert flags[0]["description"] == "unknown (25% confidence)"


def test_key_104_confidence_read_from_confidence_key() -> None:
    """104 (``.get(None, 0.0)``) silently loses the recorded 50%."""
    flags = _action_flags(
        {"detected_action": "loitering", "confidence": 0.5}, suspicious=True, weight=0.7
    )
    assert flags == [
        {
            "type": "suspicious_action",
            "description": "loitering (50% confidence)",
            "severity": "alert",
        }
    ]


def test_keys_105_107_confidence_default_is_zero() -> None:
    """105 (default ``None`` -> ``format(None, ".0%")`` TypeError) / 107 (default
    arg dropped -> ``None``)."""
    flags = _action_flags({"detected_action": "loitering"}, suspicious=True, weight=0.7)
    assert flags == [
        {
            "type": "suspicious_action",
            "description": "loitering (0% confidence)",
            "severity": "alert",
        }
    ]


def test_keys_108_109_confidence_key_literal() -> None:
    """108 ("XXconfidenceXX") / 109 ("CONFIDENCE") miss the key and render 0%."""
    flags = _action_flags(
        {"detected_action": "loitering", "confidence": 0.5}, suspicious=True, weight=0.7
    )
    assert " (50% confidence)" in flags[0]["description"]


def test_key_110_missing_confidence_is_zero_not_one() -> None:
    """110 (default ``0.0`` -> ``1.0``)."""
    flags = _action_flags({"detected_action": "loitering"}, suspicious=True, weight=0.7)
    assert " (0% confidence)" in flags[0]["description"]


def test_keys_112_134_135_action_flag_exact_dict() -> None:
    """112 (``severity = None``), 134 ("XXseverityXX"), 135 ("SEVERITY")."""
    flags = _action_flags(
        {"detected_action": "loitering", "confidence": 0.5}, suspicious=True, weight=0.95
    )
    assert flags == [
        {
            "type": "suspicious_action",
            "description": "loitering (50% confidence)",
            "severity": "critical",
        }
    ]


# --------------------------------------------------------------------------- #
# D. action severity ladder — shipped lines 1832-1834
# --------------------------------------------------------------------------- #
def test_keys_113_117_118_critical_at_exactly_0_9() -> None:
    """113 (``and False``), 117 (``>=`` -> ``>``), 118 (``>= 1.9``) each demote the
    shipped "critical" at the exact 0.9 threshold to "alert"."""
    flags = _action_flags({"detected_action": "loitering"}, suspicious=True, weight=0.9)
    assert flags[0]["severity"] == "critical"


def test_keys_115_116_critical_text() -> None:
    """115 ("XXcriticalXX") / 116 ("CRITICAL")."""
    flags = _action_flags({"detected_action": "loitering"}, suspicious=True, weight=1.0)
    assert flags[0]["severity"] == "critical"


def test_keys_114_119_123_alert_at_exactly_0_7() -> None:
    """114 (``or True`` -> critical), 119 (``and False`` -> warning),
    123 (``>=`` -> ``>`` -> warning)."""
    flags = _action_flags({"detected_action": "loitering"}, suspicious=True, weight=0.7)
    assert flags[0]["severity"] == "alert"


def test_keys_121_122_alert_between_thresholds() -> None:
    """121 ("XXalertXX") / 122 ("ALERT"), and 124 (``>= 1.7`` -> warning)."""
    flags = _action_flags({"detected_action": "loitering"}, suspicious=True, weight=0.75)
    assert flags[0]["severity"] == "alert"


def test_keys_120_124_just_below_0_7_is_warning() -> None:
    """120 (``or True`` -> alert); 124 (``>= 1.7``) also lands here."""
    flags = _action_flags({"detected_action": "loitering"}, suspicious=True, weight=0.69)
    assert flags[0]["severity"] == "warning"


def test_keys_125_126_warning_text() -> None:
    """125 ("XXwarningXX") / 126 ("WARNING")."""
    flags = _action_flags({"detected_action": "loitering"}, suspicious=True, weight=0.1)
    assert flags[0]["severity"] == "warning"


# --------------------------------------------------------------------------- #
# E. weather flags — shipped lines 1844-1856
# --------------------------------------------------------------------------- #
def test_key_137_weather_flag_at_half_confidence() -> None:
    """137 (``>=`` -> ``>``) drops the shipped flag at exactly 0.5 confidence."""
    result = EnrichmentResult(weather_classification=_weather("foggy", 0.5))
    assert result.get_summary_flags() == [
        {
            "type": "weather_low_visibility",
            "description": "Foggy conditions (50% confidence) - reduced visibility",
            "severity": "info",
        }
    ]


def test_guard_weather_below_half_emits_nothing() -> None:
    """Anti-vacuity guard for the threshold pin above."""
    result = EnrichmentResult(weather_classification=_weather("foggy", 0.4))
    assert result.get_summary_flags() == []


def test_guard_foggy_is_low_visibility() -> None:
    """Baseline partner of the snowy pin below."""
    result = EnrichmentResult(weather_classification=_weather("foggy", 0.85))
    f = _flag(result.get_summary_flags(), "weather_low_visibility")
    assert f is not None
    assert f["description"] == "Foggy conditions (85% confidence) - reduced visibility"


def test_keys_144_145_snowy_is_low_visibility() -> None:
    """144 ("XXsnowyXX") / 145 ("SNOWY") drop "snowy" from the tuple."""
    result = EnrichmentResult(weather_classification=_weather("snowy", 0.85))
    assert result.get_summary_flags() == [
        {
            "type": "weather_low_visibility",
            "description": "Snowy conditions (85% confidence) - reduced visibility",
            "severity": "info",
        }
    ]


def test_guard_clear_emits_no_flag() -> None:
    """Anti-vacuity guard for the condition tuple."""
    result = EnrichmentResult(weather_classification=_weather("clear", 0.85))
    assert result.get_summary_flags() == []


def test_keys_149_150_low_visibility_type_literal() -> None:
    """149 ("XXweather_low_visibilityXX") / 150 ("WEATHER_LOW_VISIBILITY")."""
    result = EnrichmentResult(weather_classification=_weather("foggy", 0.5))
    assert [f["type"] for f in result.get_summary_flags()] == ["weather_low_visibility"]


def test_keys_151_152_weather_flag_exact_dict() -> None:
    """151 ("XXdescriptionXX") / 152 ("DESCRIPTION")."""
    result = EnrichmentResult(weather_classification=_weather("snowy", 0.9))
    assert result.get_summary_flags() == [
        {
            "type": "weather_low_visibility",
            "description": "Snowy conditions (90% confidence) - reduced visibility",
            "severity": "info",
        }
    ]


def test_keys_153_154_weather_severity_key() -> None:
    """153 ("XXseverityXX") / 154 ("SEVERITY")."""
    result = EnrichmentResult(weather_classification=_weather("foggy", 0.6))
    assert list(result.get_summary_flags()[0]) == ["type", "description", "severity"]


def test_keys_155_156_weather_severity_is_info() -> None:
    """155 ("XXinfoXX") / 156 ("INFO")."""
    result = EnrichmentResult(weather_classification=_weather("snowy", 0.9))
    f = _flag(result.get_summary_flags(), "weather_low_visibility")
    assert f is not None
    assert f["severity"] == "info"


# --------------------------------------------------------------------------- #
# F. _safe_classify_demographics — empty inputs / det_id derivation
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("empty", [[], None])
def test_keys_001_002_003_no_persons_returns_empty_dicts(stubs: Any, empty: Any) -> None:
    """1/2 (``{}`` -> ``None``) and 3 (``if persons:``): shipped returns a pair of
    distinct EMPTY DICTS for a falsy person list."""
    out = _run_demographics_raw(MagicMock(), empty, _image())
    assert out == ({}, {})
    assert isinstance(out[0], dict) and isinstance(out[1], dict)
    assert out[0] is not out[1]


def _run_demographics_raw(pipeline: Any, persons: Any, image: Any) -> Any:
    return asyncio.run(M.EnrichmentPipeline._safe_classify_demographics(pipeline, persons, image))


def test_keys_004_to_010_det_id_derivation(stubs: Any) -> None:
    """4 (``person_crops = None``), 5 (``enumerate(None)``), 6 (``det_id = None``),
    9 (``str(None)`` true-branch), 10 (``str(None)`` else-branch): a falsy
    detection id falls back to the enumerate index, so shipped keys are 0/1/3."""
    ages = [_age("adult"), _age("child"), _age("senior")]
    genders = [_gender(), _gender("male"), _gender()]
    d = _demographics(stubs, [_person(0), _person(None), _person(3)], ages=ages, genders=genders)
    assert list(d.out[0]) == ["0", "1", "3"]
    assert d.out[0] == {"0": ages[0], "1": ages[1], "3": ages[2]}
    assert d.out[1] == {"0": genders[0], "1": genders[1], "3": genders[2]}
    assert _strs(d.errors) == []


def test_guard_truthy_det_id_wins_over_index(stubs: Any) -> None:
    """Anti-vacuity partner: 7 (``and False``), 8 (``or True``), 9 (``str(None)``)
    all replace a real id with the index."""
    ages = [_age("adult"), _age("child")]
    d = _demographics(
        stubs, [_person(42), _person(None)], ages=ages, genders=[_gender(), _gender()]
    )
    assert list(d.out[0]) == ["42", "1"]


def test_keys_011_to_017_019_to_022_028_to_031_050_to_053_crop_path(stubs: Any) -> None:
    """11 (``crop = None``), 12-15 (mangled ``_crop_to_bbox`` args), 16 (inverted
    gate), 17 (``append(None)``), 19/20 (det_ids), 21/22 (crops), 28-31 and
    50-53 (loader args).

    Runs the SHIPPED cropper against a real image and inspects exactly what each
    batch loader is handed: that stage's model_dict plus the ordered crops.
    """
    seen: dict[str, Any] = {}

    async def _ages(model_dict: Any, images: Any) -> list[Any]:
        seen["age_args"] = (model_dict, images)
        return [_age("adult"), _age("child")]

    async def _genders(model_dict: Any, images: Any) -> list[Any]:
        seen["gender_args"] = (model_dict, images)
        return [_gender(), _gender("male")]

    payload = {"model": "age-model", "processor": "proc", "labels": AGE_LABELS}
    d = _demographics(
        stubs, [_person(5), _person(None)], ages=_ages, genders=_genders, mgr=_mgr(payload)
    )
    assert list(d.out[0]) == ["5", "1"]
    assert seen["age_args"][0] is payload
    assert seen["gender_args"][0] is payload
    crops = seen["age_args"][1]
    assert isinstance(crops, list) and [im.size for im in crops] == [(100, 200), (100, 200)]
    assert seen["gender_args"][1] == crops
    assert d.out[0] == {"5": _age("adult"), "1": _age("child")}
    assert d.out[1] == {"5": _gender(), "1": _gender("male")}
    assert _strs(d.errors) == []


# --------------------------------------------------------------------------- #
# G. crop gating — shipped lines 3212-3219
# --------------------------------------------------------------------------- #
def test_key_018_all_crops_failing_skips_models(stubs: Any) -> None:
    """18 (``if not person_crops:`` -> ``if person_crops:``) loads both models with
    an empty crop list instead of returning early."""
    d = _demographics(stubs, [_person(1)], ages=[], genders=[], crop=None)
    assert d.out == ({}, {})
    assert d.mgr.load.call_args_list == []
    d.ages.assert_not_called()
    d.genders.assert_not_called()
    assert _strs(d.errors) == []


def test_guard_partial_crop_failure(stubs: Any) -> None:
    """Anti-vacuity partner of 16 (``if crop is None:``): a dropped crop removes
    exactly that person, not the whole batch."""
    keep = Image.new("RGB", (40, 40))
    d = _demographics(
        stubs,
        [_person(1), _person(2)],
        ages=[_age("adult")],
        genders=[_gender()],
        crop=[None, keep],
    )
    assert list(d.out[0]) == ["2"]
    assert list(d.out[1]) == ["2"]
    assert _strs(d.errors) == []


# --------------------------------------------------------------------------- #
# H. model names + result wiring
# --------------------------------------------------------------------------- #
def test_keys_024_025_026_046_047_048_model_names(stubs: Any) -> None:
    """24/25/26 (age model name) and 46/47/48 (gender model name): shipped loads
    "vit-age-classifier" then "vit-gender-classifier", in that order."""
    crop = Image.new("RGB", (30, 60))
    d = _demographics(stubs, [_person(1)], ages=[_age("adult")], genders=[_gender()], crop=crop)
    assert [c.args[0] for c in d.mgr.load.call_args_list] == [
        "vit-age-classifier",
        "vit-gender-classifier",
    ]
    assert _strs(d.errors) == []


def test_keys_027_032_033_035_036_age_batch_wiring(stubs: Any) -> None:
    """27 (``age_batch = None``), 32 (``zip(None, ...)``), 33 (``zip(..., None, ...)``),
    35/36 (a zip iterable dropped): age results key onto det_ids positionally."""
    crop0 = Image.new("RGB", (10, 10), color=(1, 1, 1))
    crop1 = Image.new("RGB", (20, 20), color=(2, 2, 2))
    ages = [_age("adult"), _age("senior")]
    d = _demographics(
        stubs,
        [_person(11), _person(22)],
        ages=ages,
        genders=[_gender(), _gender("male")],
        crop=[crop0, crop1],
    )
    assert d.out[0] == {"11": ages[0], "22": ages[1]}
    assert list(d.out[1]) == ["11", "22"]
    assert _strs(d.errors) == []


def test_keys_049_054_055_057_058_gender_batch_wiring(stubs: Any) -> None:
    """49 (``gender_batch = None``), 54 (``zip(None, ...)``), 55
    (``zip(..., None, ...)``), 57/58 (a zip iterable dropped)."""
    crop = Image.new("RGB", (12, 12))
    gender_batch = [_gender("male"), _gender("female")]
    d = _demographics(
        stubs,
        [_person(11), _person(22)],
        ages=[_age("adult"), _age("child")],
        genders=gender_batch,
        crop=crop,
    )
    assert d.out[1] == {"11": gender_batch[0], "22": gender_batch[1]}
    assert _strs(d.errors) == []


def test_keys_050_to_053_gender_loader_args(stubs: Any) -> None:
    """50 (model_dict ``None``), 51 (images ``None``), 52 (model_dict slot
    dropped), 53 (images arg dropped): the gender stage passes its own model_dict
    plus the crops."""
    seen: dict[str, Any] = {}
    crop = Image.new("RGB", (16, 16))
    payload = {"model": "gender-model"}

    async def _genders(model_dict: Any, images: Any) -> list[Any]:
        seen["args"] = (model_dict, images)
        return [_gender("male")]

    d = _demographics(
        stubs,
        [_person(1)],
        ages=[_age("adult")],
        genders=_genders,
        crop=crop,
        mgr=_mgr(payload),
    )
    assert seen["args"][0] is payload
    assert seen["args"][1] == [crop]
    assert d.out[1] == {"1": _gender("male")}
    assert _strs(d.errors) == []


# --------------------------------------------------------------------------- #
# I. strict zip — shipped lines 3230 and 3250
# --------------------------------------------------------------------------- #
def test_keys_034_037_038_age_zip_is_strict(stubs: Any) -> None:
    """34 (``strict=None``), 37 (strict arg dropped), 38 (``strict=False``).

    Shipped: the length mismatch raises mid-loop, so the PARTIAL dict survives,
    the success bookkeeping is skipped, and the except block records the error and
    logs the f-string message.
    """
    crop = Image.new("RGB", (12, 12))
    ages = [_age("adult"), _age("child")]  # 1 det_id vs 2 results
    d = _demographics(stubs, [_person(1)], ages=ages, genders=[_gender()], crop=crop)
    assert d.out[0] == {"1": ages[0]}
    assert d.out[1] == {"1": _gender()}
    assert _strs(d.errors) == ["age_classification"]
    assert any(
        isinstance(m, str) and m.startswith("Age classification skipped: ") for m in _strs(d.debug)
    )


def test_keys_056_059_060_gender_zip_is_strict(stubs: Any) -> None:
    """56 (``strict=None``), 59 (strict arg dropped), 60 (``strict=False``)."""
    crop = Image.new("RGB", (12, 12))
    gender_batch = [_gender("male"), _gender("female")]
    d = _demographics(stubs, [_person(1)], ages=[_age("adult")], genders=gender_batch, crop=crop)
    assert d.out[1] == {"1": gender_batch[0]}
    assert d.out[0] == {"1": _age("adult")}
    assert _strs(d.errors) == ["gender_classification"]
    assert any(
        isinstance(m, str) and m.startswith("Gender classification skipped: ")
        for m in _strs(d.debug)
    )


# --------------------------------------------------------------------------- #
# J. failure containment — shipped lines 3240-3242 and 3260-3262
# --------------------------------------------------------------------------- #
def test_keys_041_to_044_age_load_failure_contained(stubs: Any) -> None:
    """41 (label ``None``), 42 ("XXage_classificationXX"), 43
    ("AGE_CLASSIFICATION"), 44 (``logger.debug(None)``)."""
    crop = Image.new("RGB", (12, 12))
    mgr = _mgr()
    mgr.load = MagicMock(name="load", side_effect=[RuntimeError("boom"), _AsyncCM({})])
    d = _demographics(stubs, [_person(1)], ages=[], genders=[_gender()], crop=crop, mgr=mgr)
    assert d.out == ({}, {"1": _gender()})
    assert _strs(d.errors) == ["age_classification"]
    d.ages.assert_not_called()
    assert "Age classification skipped: boom" in _strs(d.debug)


def test_guard_age_loader_failure_contained(stubs: Any) -> None:
    """Same except block driven by the batch loader (extra pin for 41-44)."""
    crop = Image.new("RGB", (12, 12))

    def _boom(*_a: Any) -> None:
        raise RuntimeError("age down")

    d = _demographics(stubs, [_person(1)], ages=_boom, genders=[_gender()], crop=crop)
    assert d.out == ({}, {"1": _gender()})
    assert _strs(d.errors) == ["age_classification"]
    assert "Age classification skipped: age down" in _strs(d.debug)


def test_keys_063_to_066_gender_failure_contained(stubs: Any) -> None:
    """63 (label ``None``), 64 ("XXgender_classificationXX"), 65
    ("GENDER_CLASSIFICATION"), 66 (``logger.debug(None)``)."""
    crop = Image.new("RGB", (12, 12))
    mgr = _mgr()
    mgr.load = MagicMock(name="load", side_effect=[_AsyncCM({}), RuntimeError("kaboom")])
    d = _demographics(stubs, [_person(1)], ages=[_age("adult")], genders=[], crop=crop, mgr=mgr)
    assert d.out == ({"1": _age("adult")}, {})
    assert _strs(d.errors) == ["gender_classification"]
    d.genders.assert_not_called()
    assert "Gender classification skipped: kaboom" in _strs(d.debug)


def test_guard_age_failure_keeps_gender_stage(stubs: Any) -> None:
    """Anti-vacuity guard: one failed stage must not sink the other stage."""
    crop = Image.new("RGB", (12, 12))

    def _boom(*_a: Any) -> None:
        raise ValueError("nope")

    d = _demographics(stubs, [_person(1)], ages=_boom, genders=[_gender()], crop=crop)
    assert d.out == ({}, {"1": _gender()})
    assert _strs(d.errors) == ["age_classification"]
