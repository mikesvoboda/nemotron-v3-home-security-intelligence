"""Batch-25 kill battery — part 13, chunk "NemotronAnalyzer._build_prompt#chunk2" (62 keys).

All 62 chunk keys are singleton occurrence-twin shape groups (verified against
/tmp/wp-batch25/feed.json: no shape group carries a second key, and no group
straddles chunk-12). Kill families:

A. format-arg-deleted mutants (124-142, 152-154, 168-169, 174-175): a real
   argument (and sometimes the keyword name itself) is removed from the
   MODEL_ZOO template .format(...) call -> missing keyword -> KeyError against
   the real shipped template, or a formatter called with the shipped arg list
   shortened -> wrong call shape.
B. value-substitution mutants (145, 149-151, 156-161, 163-164, 166, 170,
   172-173, 176, 178, 180-181, 183-184, 188): the formatter still runs but
   receives None / {} / [] / the ternary's else value instead of the shipped
   enrichment field.
C. truthiness mutants whose condition flips ONLY on the false-but-not-None
   side of the shipped `if enrichment_result is not None` guard (162, 165,
   171, 177, 179, 182, 185): `cond or True` always takes the attribute-read
   branch, so with enrichment_result None (enriched branch entered via an
   EnrichedContext with baselines) they raise AttributeError on None.
D. basic-path =None mutants (192, 193, 194): RISK_ANALYSIS_PROMPT.format
   keyword values replaced by None -> "None" renders into the Time/DETECTIONS
   lines.
E. household-injection mutants (200, 201, 202): the "## EVENT CONTEXT" marker
   literal (or its containment test) is mutated, so the household block lands
   at the after-SCORING-REFERENCE fallback position (or nowhere) instead of
   immediately before "## EVENT CONTEXT".

Nothing here is killed_by_draft: the draft battery
(/tmp/wp-batch25/test_nemotron_analyzer_batch25.py) covers only
_parse_llm_response / _validate_risk_data / _extract_json_objects, and the
repo suite's only real _build_prompt call (test_nemotron_analyzer.py::
test_build_prompt_basic) stays on the basic branch while its household tests
go through _call_llm and assert substring presence only — which the mutants'
fallback branch also satisfies.

Production is pinned AS SHIPPED (probe: /tmp/wp-batch25/probes/probe_c13.py).
No source changes proposed.

Ratchet note: patch sites with an explicit ``new`` cannot also carry
autospec=True (mock raises TypeError), so those use patch(target, new=...) —
the other accepted ratchet form. Mocks that must enforce the shipped call
signature use autospec=True with no ``new``.
"""

from __future__ import annotations

import os
import string
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# Mirror the minimum env vars the repo conftest sets before any
# settings-instantiating import (values copied, not invented).
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("PYROSCOPE_ENABLED", "false")
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://security:security_dev_password@localhost:5432/security",  # pragma: allowlist secret
)
os.environ.setdefault("OTEL_ENABLED", "false")

import pytest

pytestmark = pytest.mark.unit

from backend.services import nemotron_analyzer as NA_MOD
from backend.services.nemotron_analyzer import NemotronAnalyzer
from backend.services.prompts import (
    MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT,
)

KEY_PREFIX = "backend.services.nemotron_analyzer.xǁNemotronAnalyzerǁ_build_prompt__mutmut_"

# Module-level formatters consumed by _build_prompt's enriched branch.
MODULE_FORMATTERS = [
    "format_weather_context",
    "format_image_quality_context",
    "format_confidence_quality_summary",
    "format_violence_context",
    "format_pose_analysis_context",
    "format_action_recognition_context",
    "format_trajectory_context",
    "format_vehicle_classification_context",
    "format_vehicle_damage_context",
    "format_clothing_analysis_context",
    "format_pet_classification_context",
    "format_depth_context",
    "format_clip_analysis_context",
    "format_cross_camera_person_tracking",
]

SENT = {
    "format_weather_context": "WXSENT",
    "format_image_quality_context": "IQCTXSENT",
    "format_confidence_quality_summary": "CQSENT",
    "format_violence_context": "VIOLSENT",
    "format_pose_analysis_context": "POSESENT",
    "format_action_recognition_context": "ACTSENT",
    "format_trajectory_context": "TRAJCTXSENT",
    "format_vehicle_classification_context": "VEHCLASSENT",
    "format_vehicle_damage_context": "VEHDAMSENT",
    "format_clothing_analysis_context": "CLOTHSENT",
    "format_pet_classification_context": "PETSENT",
    "format_depth_context": "DEPTHCTXSENT",
    "format_clip_analysis_context": "CLIPSENT",
    "format_cross_camera_person_tracking": "XCPTRKSENT",
}


def _analyzer() -> NemotronAnalyzer:
    # __new__ skips the heavy __init__; _build_prompt touches only its
    # arguments plus _get_context_enricher / _build_ondemand_enrichment_context.
    a = NemotronAnalyzer.__new__(NemotronAnalyzer)
    enricher = MagicMock(name="enricher")
    enricher.format_zone_analysis.return_value = "ZONESENT"
    enricher.format_baseline_comparison.return_value = "BASESENT"
    enricher.format_cross_camera_summary.return_value = "XCAMSENT"
    a._get_context_enricher = MagicMock(name="get_enricher")
    a._get_context_enricher.return_value = enricher
    a._build_ondemand_enrichment_context = MagicMock(name="ondemand_method")
    a._build_ondemand_enrichment_context.return_value = "ONDSENT"
    return a


def _enrichment_result() -> MagicMock:
    """EnrichmentResult stand-in: consumed fields set explicitly."""
    er = MagicMock(name="EnrichmentResult")
    for attr in (
        "vision_extraction",
        "person_reid_matches",
        "vehicle_reid_matches",
        "pose_results",
        "action_results",
        "violence_detection",
        "weather_classification",
        "image_quality",
        "quality_change_detected",
        "quality_change_description",
        "trajectory_analyses",
        "vehicle_classifications",
        "vehicle_damage",
        "clothing_classifications",
        "clothing_segmentation",
        "pet_classifications",
        "depth_analysis",
    ):
        setattr(er, attr, None)
    er.to_context_string.return_value = "TOCTXSENT"
    return er


def _patched_formatters() -> list:
    ps = []
    for name in MODULE_FORMATTERS:
        ps.append(patch.object(NA_MOD, name, autospec=True, return_value=SENT[name]))
    # Imported lazily INSIDE the enriched branch:
    ps.append(
        patch(
            "backend.services.reid_service.format_full_reid_context",
            autospec=True,
            return_value="REIDSENT",
        )
    )
    return ps


def _all_sentinels() -> list:
    return [
        "WXSENT",
        "IQCTXSENT",
        "CQSENT",
        "VIOLSENT",
        "POSESENT",
        "ACTSENT",
        "TRAJCTXSENT",
        "VEHCLASSENT",
        "VEHDAMSENT",
        "CLOTHSENT",
        "PETSENT",
        "DEPTHCTXSENT",
        "XCPTRKSENT",
        "REIDSENT",
        "TOCTXSENT",
        "ONDSENT",
        "CLIPSENT",
    ]


# ---------------------------------------------------------------------------
# Families A + B: enriched branch with every consumed field unique, real
# shipped template, spec'd formatter mocks.
# ---------------------------------------------------------------------------


def test_enriched_prompt_golden_renders_every_slot_with_shipped_args():
    """Kills keys 124-142, 145, 149-154, 156-161, 163-164, 166, 169-170,
    172-173, 174-176, 178, 180-181, 183-184, 188 of
    backend.services.nemotron_analyzer.
    xǁNemotronAnalyzerǁ_build_prompt__mutmut_<N>  (prefix KEY_PREFIX).

    Shipped behavior (probe /tmp/wp-batch25/probes/probe_c13.py): the enriched
    branch fills ALL 27 MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT slots — every
    context sentinel appears exactly once — and each module formatter receives
    exactly the shipped positional/keyword arguments from the enrichment
    fields. Arg-deletion mutants (family A) raise KeyError on the real
    template (missing keyword) before any assertion runs; value-substitution
    mutants (family B) reach a formatter with None/{}/else-value instead of
    the shipped field, breaking the call-args pins below."""
    er = _enrichment_result()
    er.weather_classification = "WXOBS"
    er.image_quality = "IQOBS"
    er.quality_change_detected = True
    er.quality_change_description = "QDESCOBS"
    er.violence_detection = "VIOLOBS"
    er.pose_results = {"0": SimpleNamespace(pose_class="crouching", pose_confidence=0.8)}
    er.action_results = {"0": ["loitering"]}
    er.trajectory_analyses = {"7": "TRAJOBS"}
    er.vehicle_classifications = {"0": "VEHCOBS"}
    er.vehicle_damage = {"0": "VDMOBS"}
    er.clothing_classifications = {"0": "CLTHOBS"}
    er.clothing_segmentation = {"0": "SEGBOBS"}
    er.pet_classifications = {"0": "PETOBS"}
    er.depth_analysis = "DEPOBS"
    dicts = [{"confidence": 0.95, "class_name": "person"}]

    ps = _patched_formatters()
    started = [p.start() for p in ps]
    m = dict(zip(MODULE_FORMATTERS, started, strict=False))
    try:
        prompt = _analyzer()._build_prompt(
            camera_name="CAMNAME",
            start_time="STARTISO",
            end_time="ENDISO",
            detections_list="DETLISTSENT",
            enriched_context=None,
            enrichment_result=er,
            camera_health_context="HEALTHSENT",
            detection_dicts=dicts,
        )
    finally:
        for p in reversed(ps):
            p.stop()

    # (A) every enriched-section slot rendered exactly once
    for tok in _all_sentinels():
        assert prompt.count(tok) == 1, f"slot token {tok} count != 1"

    # (A/B) shipped literal values on the no-EnrichedContext enriched path
    assert "CAMNAME" in prompt
    assert "STARTISO to ENDISO" in prompt
    assert "Day: Unknown" in prompt
    assert "Lighting: day" in prompt
    assert "HEALTHSENT" in prompt
    assert "Zone analysis: Not available" in prompt
    assert "Baseline comparison: Not available" in prompt
    assert "0.00" in prompt
    assert "Cross-camera activity: Not available" in prompt
    assert "No scene analysis available." in prompt

    # (B) shipped arguments reaching each formatter
    m["format_weather_context"].assert_called_once_with("WXOBS")
    m["format_image_quality_context"].assert_called_once_with("IQOBS", True, "QDESCOBS")
    m["format_confidence_quality_summary"].assert_called_once_with(dicts)
    m["format_violence_context"].assert_called_once_with("VIOLOBS")
    m["format_pose_analysis_context"].assert_called_once_with(
        {"0": {"classification": "crouching", "confidence": 0.8}}
    )
    # shipped wraps: action_data = {"0": enrichment_result.action_results}
    m["format_action_recognition_context"].assert_called_once_with({"0": {"0": ["loitering"]}})
    m["format_trajectory_context"].assert_called_once_with({"7": "TRAJOBS"})
    m["format_vehicle_classification_context"].assert_called_once_with({"0": "VEHCOBS"})
    m["format_vehicle_damage_context"].assert_called_once_with({"0": "VDMOBS"}, time_of_day="day")
    m["format_clothing_analysis_context"].assert_called_once_with(
        {"0": "CLTHOBS"}, {"0": "SEGBOBS"}
    )
    m["format_pet_classification_context"].assert_called_once_with({"0": "PETOBS"})
    m["format_depth_context"].assert_called_once_with("DEPOBS")
    assert m["format_clip_analysis_context"].call_args.args[0] is er
    assert m["format_clip_analysis_context"].call_count == 1
    m["format_cross_camera_person_tracking"].assert_called_once_with(
        person_reid_matches=None,
        vehicle_reid_matches=None,
        current_camera_id=None,
        zone_context=None,
    )


def test_enhanced_template_receives_full_shipped_kwargs():
    """Kills mutmut keys 124-142, 168, 188 (second, focused pin) of
    backend.services.nemotron_analyzer.
    xǁNemotronAnalyzerǁ_build_prompt__mutmut_<N>  (prefix KEY_PREFIX; full
    observed kill set of THIS test per redcheck_c13_result.json).

    Shipped behavior: the enriched branch passes the template exactly the 27
    placeholder keywords with the shipped values (recording template stand-in
    patched with ``new=``, so a deleted keyword is observable as a missing
    entry rather than as a KeyError)."""
    fields = set()
    for _, fld, _, _ in string.Formatter().parse(MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT):
        if fld:
            fields.add(fld)
    assert len(fields) == 27

    recorder = MagicMock(name="template")
    recorder.format.return_value = "PROMPTRECORD"
    er = _enrichment_result()
    dicts = [{"confidence": 0.95}]
    ps = _patched_formatters()
    mocks = [p.start() for p in ps]
    clip_mock = mocks[MODULE_FORMATTERS.index("format_clip_analysis_context")]
    try:
        with patch.object(NA_MOD, "MODEL_ZOO_ENHANCED_RISK_ANALYSIS_PROMPT", new=recorder):
            out = _analyzer()._build_prompt(
                camera_name="CAMNAME",
                start_time="STARTISO",
                end_time="ENDISO",
                detections_list="DETLISTSENT",
                enriched_context=None,
                enrichment_result=er,
                camera_health_context="HEALTHSENT",
                detection_dicts=dicts,
            )
    finally:
        for p in reversed(ps):
            p.stop()

    assert out == "PROMPTRECORD"
    recorder.format.assert_called_once()
    kw = recorder.format.call_args.kwargs
    assert set(kw) == fields
    assert kw["camera_name"] == "CAMNAME"
    assert kw["timestamp"] == "STARTISO to ENDISO"
    assert kw["detections_with_all_attributes"] == "TOCTXSENT"
    assert kw["confidence_quality_summary"] == SENT["format_confidence_quality_summary"]
    assert kw["violence_context"] == SENT["format_violence_context"]
    assert kw["pose_analysis"] == SENT["format_pose_analysis_context"]
    assert kw["action_recognition"] == SENT["format_action_recognition_context"]
    assert kw["trajectory_context"] == SENT["format_trajectory_context"]
    assert kw["vehicle_classification_context"] == SENT["format_vehicle_classification_context"]
    assert kw["vehicle_damage_context"] == SENT["format_vehicle_damage_context"]
    assert kw["clothing_analysis_context"] == SENT["format_clothing_analysis_context"]
    assert kw["pet_classification_context"] == SENT["format_pet_classification_context"]
    assert kw["depth_context"] == SENT["format_depth_context"]
    assert kw["reid_context"] == "REIDSENT"
    assert kw["cross_camera_person_tracking"] == SENT["format_cross_camera_person_tracking"]
    assert kw["scene_analysis"] == "No scene analysis available."
    assert kw["ondemand_enrichment_context"] == "ONDSENT"
    assert kw["clip_analysis_context"] == SENT["format_clip_analysis_context"]
    assert clip_mock.call_args.args[0] is er


# ---------------------------------------------------------------------------
# Family C: enriched branch entered via EnrichedContext WITH baselines while
# enrichment_result is None — the only input class where the shipped guard
# (is not None -> True branch not taken) and plain truthiness diverge.
# ---------------------------------------------------------------------------


def test_enriched_branch_via_context_with_er_none_passes_defaults():
    """Kills mutmut keys 124-142, 156-157, 162-163, 165-166, 168-169,
    171-172, 174-175, 177, 179-180, 182, 185 of
    backend.services.nemotron_analyzer.
    xǁNemotronAnalyzerǁ_build_prompt__mutmut_<N>  (prefix KEY_PREFIX; full
    observed kill set of THIS test per redcheck_c13_result.json — the
    truthiness family 162/165/171/177/179/182/185 is killed ONLY here).

    Shipped behavior: with enrichment_result None but a baselines-bearing
    EnrichedContext, the enriched branch is still taken (`is not None` on the
    context), and every `field if enrichment_result else <default>` ternary
    takes its DEFAULT branch — formatters receive ({}, {}, {}, None, None,
    {}, None, {}, None) — while the enricher formats zone/baseline/cross-camera
    text and the shipped weather/quality/clip else-strings render. The
    `... if (enrichment_result) or True else <default>` mutants instead read
    attributes off None and raise AttributeError."""
    ec = MagicMock(name="EnrichedContext")
    ec.baselines = SimpleNamespace(deviation_score=0.42, day_of_week="Thursday")
    ec.camera_id = "CAMIDSENT"
    ec.zones = ["ZONE_A"]
    ec.cross_camera = ["XCROW"]
    dicts = [{"confidence": 0.95, "class_name": "person"}]

    ps = _patched_formatters()
    m = dict(zip(MODULE_FORMATTERS, [p.start() for p in ps], strict=False))
    try:
        prompt = _analyzer()._build_prompt(
            camera_name="CAMNAME",
            start_time="STARTISO",
            end_time="ENDISO",
            detections_list="DETLISTSENT",
            enriched_context=ec,
            enrichment_result=None,
            camera_health_context="HEALTHSENT",
            detection_dicts=dicts,
        )
    finally:
        for p in reversed(ps):
            p.stop()

    m["format_confidence_quality_summary"].assert_called_once_with(dicts)
    m["format_pose_analysis_context"].assert_called_once_with(None)
    m["format_action_recognition_context"].assert_called_once_with(None)
    m["format_trajectory_context"].assert_called_once_with(None)
    m["format_vehicle_classification_context"].assert_called_once_with({})
    m["format_vehicle_damage_context"].assert_called_once_with({}, time_of_day="day")
    m["format_clothing_analysis_context"].assert_called_once_with({}, None)
    m["format_pet_classification_context"].assert_called_once_with({})
    m["format_depth_context"].assert_called_once_with(None)
    m["format_weather_context"].assert_not_called()
    m["format_image_quality_context"].assert_not_called()
    m["format_clip_analysis_context"].assert_not_called()

    # shipped enricher path + else-strings
    assert "ZONESENT" in prompt and "BASESENT" in prompt and "XCAMSENT" in prompt
    assert "Thursday" in prompt
    assert "0.42" in prompt
    assert "Violence analysis: Not performed" in prompt
    assert "Weather: Unknown (classification unavailable)" in prompt
    assert "Image quality: Not assessed" in prompt
    assert "DETLISTSENT" in prompt
    assert "CLIPSENT" not in prompt


# ---------------------------------------------------------------------------
# Family D: basic fallback path.
# ---------------------------------------------------------------------------


def test_basic_prompt_renders_times_and_detections_verbatim():
    """Kills mutmut keys 192, 193, 194 of backend.services.nemotron_analyzer.
    xǁNemotronAnalyzerǁ_build_prompt__mutmut_<N>  (prefix KEY_PREFIX; also the
    sole observed killer together with the household fallback test).

    Shipped behavior on the no-enrichment fallback: the basic template renders
    "Time: {start_time} to {end_time}" and "DETECTIONS\\n{detections_list}"
    with the caller's values verbatim, and no "None" token appears anywhere in
    the prompt. The =None mutants print "None" for the start/end timestamp or
    the detections block, failing both the exact-line and the no-None pins."""
    prompt = _analyzer()._build_prompt(
        camera_name="CAMNAME",
        start_time="STARTISO",
        end_time="ENDISO",
        detections_list="DETLISTSENT",
    )
    assert "Time: STARTISO to ENDISO" in prompt
    assert "DETECTIONS\nDETLISTSENT" in prompt
    assert "None" not in prompt


# ---------------------------------------------------------------------------
# Family E: household-context injection geometry.
# ---------------------------------------------------------------------------

_HH = "HHLINE-SENTINEL"


def test_household_context_basic_prompt_inserted_directly_before_event_context():
    """Kills mutmut keys 200, 201, 202 of backend.services.nemotron_analyzer.
    xǁNemotronAnalyzerǁ_build_prompt__mutmut_<N>  (prefix KEY_PREFIX; full
    observed kill set of THIS test per redcheck_c13_result.json).

    Shipped behavior (NEM-3315): with the basic prompt and household_context
    set, the block is spliced via str.replace on the literal "## EVENT
    CONTEXT", so it ends exactly 2 characters (the "\\n\\n" separator) before
    the EVENT CONTEXT heading. Mutants 200/201 (mutated marker literals) and
    202 (`not in`) fall through to the after-SCORING-REFERENCE fallback, which
    on this template lands ~1000 chars earlier — adjacency fails."""
    base = _analyzer()._build_prompt(
        camera_name="CAMNAME",
        start_time="STARTISO",
        end_time="ENDISO",
        detections_list="DETLISTSENT",
    )
    prompt = _analyzer()._build_prompt(
        camera_name="CAMNAME",
        start_time="STARTISO",
        end_time="ENDISO",
        detections_list="DETLISTSENT",
        household_context=_HH,
    )
    assert base.count("## EVENT CONTEXT") == 1
    ev = prompt.index("## EVENT CONTEXT")
    assert prompt == base.replace("## EVENT CONTEXT", f"{_HH}\n\n## EVENT CONTEXT", 1)
    assert prompt[ev - len(_HH) - 2 : ev - 2] == _HH


def test_household_context_enriched_prompt_inserted_directly_before_event_context():
    """Kills mutmut keys 124-142, 168, 200, 201, 202 of
    backend.services.nemotron_analyzer.
    xǁNemotronAnalyzerǁ_build_prompt__mutmut_<N>  (prefix KEY_PREFIX; full
    observed kill set of THIS test per redcheck_c13_result.json).

    Same shipped splice geometry pinned on the enriched prompt (the one the
    streaming path actually sends): household block immediately precedes
    "## EVENT CONTEXT", and lands far after the SCORING REFERENCE fallback
    position (~10k chars in) where the mutants insert instead."""
    ps = _patched_formatters()
    started = [p.start() for p in ps]
    try:
        prompt = _analyzer()._build_prompt(
            camera_name="CAMNAME",
            start_time="STARTISO",
            end_time="ENDISO",
            detections_list="DETLISTSENT",
            enriched_context=None,
            enrichment_result=_enrichment_result(),
            camera_health_context="HEALTHSENT",
            household_context=_HH,
        )
    finally:
        for p in reversed(ps):
            p.stop()
    ev = prompt.index("## EVENT CONTEXT")
    sc = prompt.index("## SCORING REFERENCE")
    assert prompt[ev - len(_HH) - 2 : ev - 2] == _HH
    # the shipped prompt did NOT take the fallback branch (which would put HH
    # right after the scoring table, thousands of chars earlier)
    assert ev - len(_HH) - 2 > sc + 5000


class _FmtTemplate:
    """Plain stand-in template (patched with ``new=``): .format returns a
    fixed string so the household-injection branches can be steered."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = []

    def format(self, **kwargs):
        self.calls.append(kwargs)
        return self.text.format(**kwargs)


def test_household_context_falls_back_after_scoring_table_when_marker_absent():
    """Kills mutmut keys 192, 193, 194, 202 of
    backend.services.nemotron_analyzer.
    xǁNemotronAnalyzerǁ_build_prompt__mutmut_<N>  (prefix KEY_PREFIX; full
    observed kill set of THIS test per redcheck_c13_result.json).

    Shipped fallback behavior when the rendered prompt has SCORING REFERENCE
    but no EVENT CONTEXT and no assistant marker: the household block is
    inserted immediately after the table's first "\\n\\n" terminator. Mutant
    202 inverts the containment test, so on this marker-free prompt the
    replace branch runs (replacing a marker that isn't there = no-op) and the
    household text never reaches the prompt — the insertion pins fail."""
    text = (
        "## SCORING REFERENCE\n| a | b |\n|---|---|\n| row |\n"
        "\n"
        "## TAIL SECTION {camera_name} {start_time} {end_time}\n"
        "DETECTIONS\n{detections_list}\n"
    )
    tpl = _FmtTemplate(text)
    with patch.object(NA_MOD, "RISK_ANALYSIS_PROMPT", new=tpl):
        prompt = _analyzer()._build_prompt(
            camera_name="CAM",
            start_time="S",
            end_time="E",
            detections_list="D",
            household_context=_HH,
        )
    idx = text.format(camera_name="CAM", start_time="S", end_time="E", detections_list="D")
    insert = idx.index("\n\n", idx.index("## SCORING REFERENCE") + len("## SCORING REFERENCE"))
    assert prompt == idx[: insert + 2] + _HH + "\n\n" + idx[insert + 2 :]
    assert tpl.calls == [
        {
            "camera_name": "CAM",
            "start_time": "S",
            "end_time": "E",
            "detections_list": "D",
        }
    ]
