"""Batch-25 chunk-12 kill battery: NemotronAnalyzer._build_prompt (130 keys).

Adjudication basis: /tmp/wp-batch25/feed.json shape groups (occurrence twins fully
contained in chunk-12) and shipped source backend/services/nemotron_analyzer.py
L4603-4870. Every assertion pins SHIPPED behavior, probed before authoring
(/tmp/wp-batch25/probes/p12_probe*.py). No production code is changed by this file.

Scenario vocabulary used in docstrings (arguments to _build_prompt):
  A = enriched_context WITH baselines, enrichment_result None
  B = enrichment_result only, every enrichment attribute falsy
  E = enriched_context WITHOUT baselines + enrichment_result
  C = enriched_context + enrichment_result with vision_extraction / reid matches
The _harness fixture autospec-mocks every formatting helper _build_prompt reaches
to a unique sentinel, so a None-ified or dropped .format() keyword argument — or a
flipped ternary operand — is directly observable in the rendered prompt.
"""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

NA = "backend.services.nemotron_analyzer"

# module-level format helpers imported by backend.services.nemotron_analyzer
NA_FORMATS = {
    "format_weather_context": "WX-M",
    "format_image_quality_context": "IQ-M",
    "format_pose_analysis_context": "POSE-M",
    "format_action_recognition_context": "ACT-M",
    "format_trajectory_context": "TRJ-M",
    "format_vehicle_classification_context": "VCLS-M",
    "format_vehicle_damage_context": "VDM-M",
    "format_clothing_analysis_context": "CLO-M",
    "format_pet_classification_context": "PET-M",
    "format_depth_context": "DEPTH-M",
    "format_clip_analysis_context": "CLIP-M",
    "format_violence_context": "VIOL-M",
    "format_confidence_quality_summary": "CQS-M",
    "format_cross_camera_person_tracking": "CCPT-M",
    "format_detections_with_all_enrichment": "DWE-M",
}
# sentinels of helpers imported LAZILY inside the function body (module-local import)
REID_S, SCENE_S = "REID-M", "SCENE-M"
ALL_S = sorted([*NA_FORMATS.values(), REID_S, SCENE_S])

# section headers present ONLY in MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT
ENHANCED_ONLY = (
    "## Zone Analysis",
    "## Baseline Comparison",
    "## Scene Analysis",
    "## CLIP Scene Intelligence",
    "## Behavioral Analysis",
)


class _Harness:
    """Records every mocked collaborator _build_prompt uses."""

    def __init__(self, mocks, enricher, ondemand):
        self.mocks = mocks
        self.enricher = enricher
        self.ondemand = ondemand


def _mk_enricher():
    enricher = MagicMock(name="ContextEnricher")
    enricher.format_zone_analysis.return_value = "ZONE-M"
    enricher.format_baseline_comparison.return_value = "BL-M"
    enricher.format_cross_camera_summary.return_value = "CCS-M"
    return enricher


def _mk_ctx(with_baselines):
    ctx = SimpleNamespace(camera_id="CAMID-M", zones=["ZONES-M"])
    if with_baselines:
        ctx.baselines = SimpleNamespace(day_of_week="DOW-M", deviation_score=0.42)
    else:
        ctx.baselines = None
    ctx.cross_camera = "XXCROSS-M"  # shipped must never render this object
    return ctx


def _mk_result(**over):
    res = MagicMock(name="EnrichmentResult")
    attrs = dict(
        vision_extraction=None,
        person_reid_matches=None,
        vehicle_reid_matches=None,
        violence_detection=None,
        pose_results=None,
        action_results=None,
        weather_classification=None,
        image_quality=None,
        quality_change_detected=False,
        quality_change_description="",
        trajectory_analyses=None,
        vehicle_classifications=None,
        vehicle_damage=None,
        clothing_classifications=None,
        clothing_segmentation=None,
        pet_classifications=None,
        depth_analysis=None,
    )
    attrs.update(over)
    for name, value in attrs.items():
        setattr(res, name, value)
    res.to_context_string.return_value = "TCS-M"
    return res


def _call(an, enriched_context=None, enrichment_result=None, detection_dicts=None):
    return an._build_prompt(
        "CAM-M",
        "TSTART",
        "TEND",
        "DETLIST-M",
        enriched_context=enriched_context,
        enrichment_result=enrichment_result,
        camera_health_context="HEALTH-M",
        detection_dicts=detection_dicts,
    )


@contextmanager
def _harness(analyzer):
    with ExitStack() as stack:
        mocks = {}
        for name, value in NA_FORMATS.items():
            mocks[name] = stack.enter_context(
                patch(f"{NA}.{name}", autospec=True, return_value=value)
            )
        mocks["format_full_reid_context"] = stack.enter_context(
            patch(
                "backend.services.reid_service.format_full_reid_context",
                autospec=True,
                return_value=REID_S,
            )
        )
        mocks["format_scene_analysis"] = stack.enter_context(
            patch(
                "backend.services.vision_extractor.format_scene_analysis",
                autospec=True,
                return_value=SCENE_S,
            )
        )
        enricher = _mk_enricher()
        stack.enter_context(
            patch.object(
                type(analyzer), "_get_context_enricher", autospec=True, return_value=enricher
            )
        )
        ondemand = stack.enter_context(
            patch.object(
                type(analyzer),
                "_build_ondemand_enrichment_context",
                autospec=True,
                return_value="OND-M",
            )
        )
        yield _Harness(mocks, enricher, ondemand)


@pytest.fixture()
def analyzer():
    # __new__ skips the heavy __init__ (model/client wiring); _build_prompt uses
    # only its arguments plus the two instance-method seams mocked by _harness.
    from backend.services.nemotron_analyzer import NemotronAnalyzer

    return NemotronAnalyzer.__new__(NemotronAnalyzer)


class TestEnhancedBranchGuard:
    """has_enriched_context computation and the enhanced/fallback branch guard."""

    def test_single_input_builds_enhanced(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        """
        with _harness(analyzer):
            p_ctx = _call(analyzer, enriched_context=_mk_ctx(True))
            p_res = _call(analyzer, enrichment_result=_mk_result())
        for prompt in (p_ctx, p_res):
            for token in ENHANCED_ONLY:
                assert token in prompt, token

    def test_no_inputs_falls_back(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        """
        prompt = _call(analyzer)
        assert "## Zone Analysis" not in prompt
        assert "## CLIP Scene Intelligence" not in prompt
        assert "Camera: CAM-M" in prompt
        assert "Time: TSTART to TEND" in prompt
        assert "DETLIST-M" in prompt

    def test_no_baselines_context_takes_else(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_7
        - mutmut_74
        - mutmut_76
        - mutmut_77
        - mutmut_109
        """
        with _harness(analyzer):
            p_no = _call(analyzer, enriched_context=_mk_ctx(False), enrichment_result=_mk_result())
            p_with = _call(analyzer, enriched_context=_mk_ctx(True), enrichment_result=_mk_result())
        assert "Zone analysis: Not available" in p_no
        assert "Zone analysis: Not available" not in p_with
        assert "ZONE-M" in p_with
        assert "XXCROSS-M" not in p_with


class TestEnricherSeam:
    def test_enricher_formatters_run(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        """
        ctx = _mk_ctx(True)
        with _harness(analyzer) as h:
            prompt = _call(analyzer, enriched_context=ctx)
        assert h.enricher.format_zone_analysis.call_args.args == (ctx.zones,)
        assert h.enricher.format_baseline_comparison.call_args.args == (ctx.baselines,)
        assert h.enricher.format_cross_camera_summary.call_args.args == (ctx.cross_camera,)
        assert "ZONE-M" in prompt and "BL-M" in prompt and "CCS-M" in prompt


class TestTimeOfDay:
    def test_default_value(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        """
        with _harness(analyzer):
            prompt = _call(analyzer, enrichment_result=_mk_result())
        assert "Lighting: day\n" in prompt
        assert "XXday" not in prompt
        assert "DAY" not in prompt

    def test_environment_context_guard_second_operand(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_8
        - mutmut_9
        - mutmut_10
        """
        res = _mk_result(
            vision_extraction=SimpleNamespace(environment_context=None, scene_analysis=None)
        )
        with _harness(analyzer):
            prompt = _call(analyzer, enrichment_result=res)
        assert "Lighting: day\n" in prompt

    def test_vision_extraction_guard_operand(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        """
        with _harness(analyzer):
            p = _call(analyzer, enriched_context=_mk_ctx(True))
            assert "Lighting: day\n" in p
            _call(analyzer, enriched_context=_mk_ctx(True), enrichment_result=_mk_result())

    def test_is_not_none_guard_operand(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_5
        - mutmut_13
        - mutmut_40
        - mutmut_55
        - mutmut_64
        - mutmut_66
        - mutmut_67
        - mutmut_68
        - mutmut_88
        - mutmut_92
        - mutmut_116
        - mutmut_117
        - mutmut_118
        - mutmut_119
        - mutmut_120
        - mutmut_121
        - mutmut_122
        - mutmut_123
        """
        res = _mk_result(
            vision_extraction=SimpleNamespace(
                environment_context=SimpleNamespace(time_of_day="night"), scene_analysis=None
            )
        )
        with _harness(analyzer):
            prompt = _call(analyzer, enrichment_result=res)
        assert "Lighting: night\n" in prompt
        assert "Lighting: day\n" not in prompt


class TestSceneText:
    def test_default_line_exact(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_14
        - mutmut_15
        - mutmut_16
        - mutmut_17
        - mutmut_69
        """
        with _harness(analyzer):
            prompt = _call(
                analyzer, enriched_context=_mk_ctx(False), enrichment_result=_mk_result()
            )
        lines = [
            ln for ln in prompt.splitlines() if ln.strip().lower() == "no scene analysis available."
        ]
        assert len(lines) == 1
        assert lines[0].strip() == "No scene analysis available."

    def test_scene_guard_or_operand_keeps_default(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        """
        res = _mk_result(
            vision_extraction=SimpleNamespace(environment_context=None, scene_analysis=None)
        )
        with _harness(analyzer):
            prompt = _call(analyzer, enrichment_result=res)
        assert "No scene analysis available." in prompt
        assert SCENE_S not in prompt

    def test_formatter_output_replaces_default(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        """
        res = _mk_result(
            vision_extraction=SimpleNamespace(
                environment_context=None, scene_analysis=SimpleNamespace(name="scene")
            )
        )
        with _harness(analyzer):
            prompt = _call(analyzer, enrichment_result=res)
        assert SCENE_S in prompt
        assert "No scene analysis available." not in prompt


class TestReidText:
    def test_output_and_positional_arguments(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_22
        - mutmut_23
        - mutmut_26
        - mutmut_28
        """
        res = _mk_result(person_reid_matches=["PM"], vehicle_reid_matches=["VM"])
        with _harness(analyzer) as h:
            prompt = _call(analyzer, enrichment_result=res)
        assert REID_S in prompt
        assert list(h.mocks["format_full_reid_context"].call_args.args) == [["PM"], ["VM"]]

    def test_none_arguments_when_no_matches(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_24
        - mutmut_25
        """
        res = _mk_result()
        with _harness(analyzer) as h:
            prompt = _call(analyzer, enrichment_result=res)
        assert list(h.mocks["format_full_reid_context"].call_args.args) == [None, None]
        assert REID_S in prompt


class TestDetectionsText:
    def test_three_branch_selection(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_33
        """
        ve = SimpleNamespace(environment_context=None, scene_analysis=None)
        with _harness(analyzer):
            p_a = _call(analyzer, enriched_context=_mk_ctx(True))
            p_b = _call(analyzer, enrichment_result=_mk_result())
            p_c = _call(
                analyzer,
                enriched_context=_mk_ctx(True),
                enrichment_result=_mk_result(vision_extraction=ve),
            )
        assert "DETLIST-M" in p_a and "TCS-M" not in p_a and "DWE-M" not in p_a
        assert "TCS-M" in p_b and "DETLIST-M" not in p_b and "DWE-M" not in p_b
        assert "DWE-M" in p_c and "TCS-M" not in p_c and "DETLIST-M" not in p_c


class TestViolenceText:
    def test_else_string_when_no_result(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        """
        with _harness(analyzer):
            prompt = _call(analyzer, enriched_context=_mk_ctx(True))
        assert "Violence analysis: Not performed" in prompt
        assert "VIOL-M" not in prompt

    def test_formatter_used_when_result(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        """
        with _harness(analyzer):
            prompt = _call(analyzer, enrichment_result=_mk_result())
        assert "VIOL-M" in prompt
        assert "Violence analysis: Not performed" not in prompt

    def test_formatter_receives_violence_detection(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_34
        - mutmut_35
        - mutmut_37
        - mutmut_38
        """
        with _harness(analyzer) as h:
            _call(analyzer, enrichment_result=_mk_result(violence_detection="VD-M"))
        assert h.mocks["format_violence_context"].call_args.args == ("VD-M",)


class TestPoseActionData:
    def test_falsy_results_keep_none(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_39
        - mutmut_42
        - mutmut_43
        """
        res = _mk_result(pose_results={}, action_results={})
        with _harness(analyzer) as h:
            _call(analyzer, enrichment_result=res)
        assert h.mocks["format_pose_analysis_context"].call_args.args == (None,)
        assert h.mocks["format_action_recognition_context"].call_args.args == (None,)

    def test_populated_results_build_payloads(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_41
        - mutmut_44
        """
        pose = SimpleNamespace(pose_class="sitting", pose_confidence=0.66)
        res = _mk_result(pose_results={"7": pose}, action_results={"action": "walking"})
        with _harness(analyzer) as h:
            h.mocks["format_pose_analysis_context"].return_value = "POSE-P"
            h.mocks["format_action_recognition_context"].return_value = "ACT-P"
            prompt = _call(analyzer, enrichment_result=res)
        assert h.mocks["format_pose_analysis_context"].call_args.args == (
            {"7": {"classification": "sitting", "confidence": 0.66}},
        )
        assert h.mocks["format_action_recognition_context"].call_args.args == (
            {"0": {"action": "walking"}},
        )
        assert "POSE-P" in prompt and "ACT-P" in prompt


class TestOndemandText:
    def test_empty_when_no_result(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_47
        """
        with _harness(analyzer) as h:
            prompt = _call(analyzer, enriched_context=_mk_ctx(True))
        assert h.ondemand.call_count == 0
        assert "OND-M" not in prompt
        assert "## On-Demand Analysis Results" in prompt
        assert "None" not in prompt

    def test_seam_receives_result(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_48
        """
        res = _mk_result()
        with _harness(analyzer) as h:
            h.ondemand.return_value = "OND-R"
            prompt = _call(analyzer, enrichment_result=res)
        # (the seam is a @staticmethod, so autospec records no self argument)
        assert h.ondemand.call_args.args[0] is res
        assert "OND-R" in prompt


class TestCrossCameraTrackingCall:
    def test_arguments_populated_inputs(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_53
        - mutmut_54
        - mutmut_63
        - mutmut_65
        """
        ctx = _mk_ctx(False)
        res = _mk_result(person_reid_matches=["PM"], vehicle_reid_matches=["VM"])
        with _harness(analyzer) as h:
            prompt = _call(analyzer, enriched_context=ctx, enrichment_result=res)
        assert h.mocks["format_cross_camera_person_tracking"].call_args.kwargs == {
            "person_reid_matches": ["PM"],
            "vehicle_reid_matches": ["VM"],
            "current_camera_id": "CAMID-M",
            "zone_context": ctx.zones,
        }
        assert "CCPT-M" in prompt

    def test_arguments_when_no_result(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        """
        ctx = _mk_ctx(True)
        with _harness(analyzer) as h:
            _call(analyzer, enriched_context=ctx, enrichment_result=None)
        assert h.mocks["format_cross_camera_person_tracking"].call_args.kwargs == {
            "person_reid_matches": None,
            "vehicle_reid_matches": None,
            "current_camera_id": "CAMID-M",
            "zone_context": ctx.zones,
        }

    def test_arguments_when_no_context(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_51
        - mutmut_52
        - mutmut_56
        - mutmut_57
        - mutmut_58
        - mutmut_59
        - mutmut_61
        """
        res = _mk_result(person_reid_matches=["PM"], vehicle_reid_matches=["VM"])
        with _harness(analyzer) as h:
            _call(analyzer, enriched_context=None, enrichment_result=res)
        assert h.mocks["format_cross_camera_person_tracking"].call_args.kwargs == {
            "person_reid_matches": ["PM"],
            "vehicle_reid_matches": ["VM"],
            "current_camera_id": None,
            "zone_context": None,
        }


class TestBaselinesGuardAndDefaults:
    def test_no_baselines_defaults_render(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_75
        - mutmut_79
        - mutmut_85
        """
        with _harness(analyzer):
            prompt = _call(
                analyzer, enriched_context=_mk_ctx(False), enrichment_result=_mk_result()
            )
        assert "Day: Unknown\nLighting: day" in prompt
        assert "## Zone Analysis\nZone analysis: Not available\n" in prompt
        assert "## Baseline Comparison\nBaseline comparison: Not available\n" in prompt
        assert "Deviation score: 0.00\n" in prompt
        assert "## Cross-Camera Activity\nCross-camera activity: Not available" in prompt

    def test_default_strings_are_case_exact(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_70
        - mutmut_71
        - mutmut_72
        - mutmut_73
        - mutmut_78
        - mutmut_80
        - mutmut_81
        - mutmut_82
        - mutmut_83
        - mutmut_84
        - mutmut_86
        - mutmut_87
        - mutmut_91
        - mutmut_110
        - mutmut_111
        - mutmut_112
        """
        with _harness(analyzer):
            prompt = _call(
                analyzer, enriched_context=_mk_ctx(False), enrichment_result=_mk_result()
            )
        assert "Zone analysis: Not available" in prompt
        assert "Zone analysis: not available" not in prompt
        assert "ZONE ANALYSIS: NOT AVAILABLE" not in prompt
        assert "Baseline comparison: Not available" in prompt
        assert "baseline comparison: not available" not in prompt
        assert "BASELINE COMPARISON: NOT AVAILABLE" not in prompt
        assert "Deviation score: 0.00\n" in prompt
        assert "XX0.00XX" not in prompt
        assert "Deviation score: None" not in prompt
        assert "Cross-camera activity: Not available" in prompt
        assert "cross-camera activity: not available" not in prompt
        assert "CROSS-CAMERA ACTIVITY: NOT AVAILABLE" not in prompt
        assert "Day: Unknown\n" in prompt
        assert "XXUnknown" not in prompt
        assert "Day: UNKNOWN" not in prompt
        assert "Day: unknown" not in prompt
        assert "Day: None" not in prompt


class TestTernaryOperandsInFormatArgs:
    def test_fallback_strings_when_no_result(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_187
        """
        with _harness(analyzer):
            prompt = _call(analyzer, enriched_context=_mk_ctx(True))
        assert "Weather: Unknown (classification unavailable)" in prompt
        assert "Image quality: Not assessed" in prompt
        assert "## CLIP Scene Intelligence" in prompt
        for token in ["WX-M", "IQ-M", "CLIP-M"]:
            assert token not in prompt
        assert "None" not in prompt

    def test_formatter_calls_when_result(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        """
        res = _mk_result()
        with _harness(analyzer) as h:
            prompt = _call(analyzer, enrichment_result=res)
        assert h.mocks["format_weather_context"].call_args.args == (res.weather_classification,)
        assert h.mocks["format_image_quality_context"].call_args.args == (None, False, "")
        assert h.mocks["format_clip_analysis_context"].call_args.args == (res,)
        for token in ["WX-M", "IQ-M", "CLIP-M"]:
            assert token in prompt


class TestFormatKeywordBattery:
    """Each .format() keyword argument must reach the template verbatim."""

    def _a(self, analyzer):
        with _harness(analyzer):
            return _call(analyzer, enriched_context=_mk_ctx(True))

    def _b(self, analyzer):
        with _harness(analyzer):
            return _call(analyzer, enrichment_result=_mk_result())

    def test_prompt_rendered_not_none(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        """
        prompt = self._a(analyzer)
        assert isinstance(prompt, str)
        assert "## Risk Interpretation Guide" in prompt
        assert "None" not in prompt

    def test_camera_name(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_27
        - mutmut_29
        - mutmut_30
        - mutmut_31
        - mutmut_32
        - mutmut_36
        - mutmut_60
        - mutmut_62
        - mutmut_89
        - mutmut_144
        - mutmut_148
        """
        assert "Camera: CAM-M" in self._a(analyzer)

    def test_timestamp(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_90
        """
        assert "Time: TSTART to TEND" in self._a(analyzer)

    def test_day_of_week(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        """
        assert "Day: DOW-M" in self._a(analyzer)

    def test_time_of_day(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        """
        assert "Lighting: day" in self._a(analyzer)

    def test_weather_context(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_93
        - mutmut_143
        - mutmut_146
        """
        assert "WX-M" in self._b(analyzer)

    def test_image_quality_context(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_94
        - mutmut_147
        - mutmut_155
        """
        assert "IQ-M" in self._b(analyzer)

    def test_camera_health_context(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_1
        - mutmut_4
        - mutmut_95
        """
        assert "HEALTH-M" in self._a(analyzer)

    def test_detections_with_all_attributes(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_96
        """
        assert "DETLIST-M" in self._a(analyzer)

    def test_confidence_quality_summary(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_97
        """
        assert "CQS-M" in self._a(analyzer)

    def test_violence_context(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_98
        """
        assert "VIOL-M" in self._b(analyzer)

    def test_pose_analysis(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_99
        """
        assert "POSE-M" in self._b(analyzer)

    def test_action_recognition(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_18
        - mutmut_19
        - mutmut_100
        """
        assert "ACT-M" in self._b(analyzer)

    def test_trajectory_context(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_101
        """
        assert "TRJ-M" in self._b(analyzer)

    def test_vehicle_classification_context(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_102
        """
        assert "VCLS-M" in self._b(analyzer)

    def test_vehicle_damage_context(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_103
        """
        assert "VDM-M" in self._b(analyzer)

    def test_clothing_analysis_context(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_104
        """
        assert "CLO-M" in self._b(analyzer)

    def test_pet_classification_context(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_105
        """
        assert "PET-M" in self._b(analyzer)

    def test_depth_context(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_106
        """
        assert "DEPTH-M" in self._b(analyzer)

    def test_reid_context(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_21
        - mutmut_107
        """
        assert REID_S in self._b(analyzer)

    def test_cross_camera_person_tracking(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_50
        - mutmut_108
        """
        assert "CCPT-M" in self._b(analyzer)

    def test_zone_analysis(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        """
        assert "ZONE-M" in self._a(analyzer)

    def test_baseline_comparison(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        """
        assert "BL-M" in self._a(analyzer)

    def test_deviation_score(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        """
        assert "Deviation score: 0.42" in self._a(analyzer)

    def test_cross_camera_summary(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        """
        assert "CCS-M" in self._a(analyzer)

    def test_scene_analysis_kwarg(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_11
        - mutmut_12
        - mutmut_20
        - mutmut_113
        """
        res = _mk_result(
            vision_extraction=SimpleNamespace(
                environment_context=None, scene_analysis=SimpleNamespace(name="s")
            )
        )
        with _harness(analyzer):
            prompt = _call(analyzer, enrichment_result=res)
        assert SCENE_S in prompt

    def test_ondemand_enrichment_context(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_45
        - mutmut_46
        - mutmut_49
        - mutmut_114
        """
        assert "OND-M" in self._b(analyzer)

    def test_clip_analysis_context(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_115
        - mutmut_186
        - mutmut_189
        """
        assert "CLIP-M" in self._b(analyzer)


class TestFormatterArgumentForwarding:
    def test_confidence_summary_receives_detection_dicts(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        """
        dicts = [{"class": "person", "confidence": 0.9}]
        with _harness(analyzer) as h:
            _call(analyzer, enriched_context=_mk_ctx(True), detection_dicts=dicts)
        assert h.mocks["format_confidence_quality_summary"].call_args.args == (dicts,)

    def test_trajectory_and_vehicle_formatters_receive_fields(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        - mutmut_167
        """
        res = _mk_result()
        with _harness(analyzer) as h:
            _call(analyzer, enrichment_result=res)
        assert h.mocks["format_trajectory_context"].call_args.args == (None,)
        assert h.mocks["format_vehicle_classification_context"].call_args.args == (None,)
        assert h.mocks["format_vehicle_damage_context"].call_args.kwargs == {"time_of_day": "day"}
        assert h.mocks["format_clothing_analysis_context"].call_args.args == (None, None)
        assert h.mocks["format_pet_classification_context"].call_args.args == (None,)
        assert h.mocks["format_depth_context"].call_args.args == (None,)

    def test_populated_field_values_forwarded(self, analyzer):
        """Kill-battery assignment: mutant keys in chunk
        NemotronAnalyzer._build_prompt#chunk1 that fail THIS test when the
        mutant is applied (each key verified by a mutant-apply run; the
        shipped code passes all 59 tests in this file).

        """
        res = _mk_result(
            trajectory_analyses=["TRJ"],
            vehicle_classifications={"car": 1},
            vehicle_damage={"d": 1},
            clothing_classifications={"c": 1},
            clothing_segmentation=["SEG"],
            pet_classifications={"dog": 1},
            depth_analysis={"depth": 1},
        )
        with _harness(analyzer) as h:
            _call(analyzer, enrichment_result=res)
        assert h.mocks["format_trajectory_context"].call_args.args == (["TRJ"],)
        assert h.mocks["format_vehicle_classification_context"].call_args.args == ({"car": 1},)
        assert h.mocks["format_vehicle_damage_context"].call_args.args == ({"d": 1},)
        assert h.mocks["format_clothing_analysis_context"].call_args.args == ({"c": 1}, ["SEG"])
        assert h.mocks["format_pet_classification_context"].call_args.args == ({"dog": 1},)
        assert h.mocks["format_depth_context"].call_args.args == ({"depth": 1},)
