"""Batch-24 mutation-kill battery: llm_reasoning pure parser functions.

Targets the WP4.4 dossier module llm_reasoning (archive/wp25-feed/
wp44-triage/llm_reasoning.md: 210 survivors, 32 clusters, 100% TEST-GAP
share at dossier time). The cache has since been invalidated (meta today
reads 420 keys ALL null), so this battery is adjudicated by a fresh
full-module red-check feed, not by the dossier's key numbers.

Every expected value MEASURED against shipped production this session
(/tmp/lr-probes.json + boundary re-probes; production NOT bent):
- _parse_json_response: dict -> dict, list/invalid -> None (C1).
- _extract_think_block: plain '...' tags, content .strip()ped, absent
  -> None; <THINK> uppercase matches via IGNORECASE (C8: pattern-literal
  case mutants are EQUIVALENT BY CONSTRUCTION -- search is IGNORECASE).
- _extract_key_observations: cap EXACTLY 10 of 11 (C4), len>5 filter
  (6-char kept, 5-char dropped), dedup, ANCHORED '(?:^|nl)The detected'
  (mid-line -> []), IGNORECASE drives uppercase capture (C2/C3). The
  MULTILINE-alone removal is EQUIVALENT by construction: '^' OR 'nl'
  already matches at 0 and after every newline either way.
- _extract_key_factors: cap 5 of 6, len>3 boundary (abcd in, abc out),
  dedup across patterns ('due to X'/'because of X') (C5).
- _extract_confidence: ALL 14 shipped keywords pinned level-by-level
  (5 low / 5 high / 4 medium) and low-first precedence kills C6's 22
  untested-keyword mutants by value-coverage.
- _extract_risk_factors: dedup, keyword 'loitering' appended LOWERCASE
  from 'LOITERING' text, pattern-matches-before-keywords order (C7).
- _parse_reasoning_steps: key_factors/confidence_indicator NON-NULL on
  BOTH numbered and paragraph branches (C9 kwargs removal/None).
- _parse_enrichment_sources: ALL 14 display labels EXACT (C10/C11),
  dict field_count=len + sample_keys cap EXACTLY 5 of 6 (C13), list
  field_count=len(data) (item count, not key count), scalar populated
  with field_count 0 (C12 init->1 dies), unknown-dict name
  key.replace('_',' ').title() (C17), unknown-LIST ships sample_fields
  [] while known-list ships data[0] keys (kills C13/C14/C15/C16 legs).
- _parse_truncation_info: None/{} -> was_truncated False + nulls + [];
  full log surfaces 'reason' -> truncation_reason (C18/C19).
- _parse_household_matches: THREE branches (list / dict-of-lists /
  dict) each pinned field-by-field: defaults ('unknown', 0.0), fallback
  chains (entity_name|name, similarity|similarity_score,
  method|match_method) both spellings, every element is a HouseholdMatch
  (kills C24 append(None) which len() could not see).
"""

from __future__ import annotations

from typing import ClassVar

import pytest

from backend.api.routes.llm_reasoning import (
    _extract_confidence,
    _extract_key_factors,
    _extract_key_observations,
    _extract_risk_factors,
    _extract_think_block,
    _parse_enrichment_sources,
    _parse_household_matches,
    _parse_json_response,
    _parse_reasoning_steps,
    _parse_truncation_info,
)
from backend.api.schemas.llm_reasoning import HouseholdMatch

pytestmark = pytest.mark.unit


class TestParseJsonResponseAndThinkBlock:
    def test_json_shapes(self):
        # MEASURED: dict passthrough; list and invalid BOTH None.
        assert _parse_json_response('{"a": 1}') == {"a": 1}
        assert _parse_json_response("[1, 2]") is None
        assert _parse_json_response("not json") is None

    def test_think_block_strip_and_absence(self):
        a = _extract_think_block("pre <think>  NOTE me  </think> post")
        assert a == "NOTE me"  # MEASURED strip()
        assert _extract_think_block("no block here") is None

    def test_think_block_uppercase_matches(self):
        # MEASURED: search flags carry IGNORECASE (C8 EQUIVALENT note:
        # mutating the pattern literal's case cannot change matches).
        assert _extract_think_block("<THINK>Shout</THINK>") == "Shout"


class TestKeyObservations:
    def test_cap_is_exactly_ten(self):
        text = "\n".join(f"The detected thing number {i}." for i in range(11))
        assert len(_extract_key_observations(text)) == 10  # kills [:10]->[:11]

    def test_length_filter_boundary(self):
        # MEASURED: 6-char capture kept, 5-char dropped (len > 5).
        assert _extract_key_observations("I observe that abcde.") == []
        assert _extract_key_observations("I observe that abcdef.") == ["abcdef"]

    def test_dedup_across_patterns(self):
        out = _extract_key_observations("I observe that same thing. observation: same thing.")
        assert out == ["same thing"]

    def test_detected_anchor_is_line_start(self):
        # MEASURED: mid-line 'The detected' does NOT match ((?:^|nl)).
        assert _extract_key_observations("prefix text The detected mid-line item.") == []
        assert _extract_key_observations("The detected line start item.") == ["line start item"]

    def test_ignorecase_drives_capture(self):
        # Kills the IGNORECASE-removal legs of the flags mutants.
        assert _extract_key_observations("I OBSERVE THAT uppercase works.") == ["uppercase works"]


class TestKeyFactors:
    def test_cap_is_exactly_five(self):
        text = (
            "due to alpha one, due to beta two, due to gamma three, "
            "due to delta four, due to epsilon five, due to zeta six"
        )
        assert _extract_key_factors(text) == [
            "alpha one",
            "beta two",
            "gamma three",
            "delta four",
            "epsilon five",
        ]

    def test_length_boundary_gt3(self):
        # MEASURED: 'abc' (3) dropped, 'abcd' (4) kept.
        assert _extract_key_factors("factor: abc. factor: abcd") == ["abcd"]

    def test_dedup_across_patterns(self):
        assert _extract_key_factors("due to same thing. because of same thing.") == ["same thing"]

    def test_all_seven_patterns(self):
        # MEASURED: every capture needs len>3 ([^,.]+ stops at commas), and
        # output order is the SHIPPED pattern-loop order, capped 5 of 7.
        text = (
            "due to alpha. because of beta. considering gamma. factor: delta. "
            "based on epsilon. given that zeta. it indicates eta four"
        )
        assert _extract_key_factors(text) == ["alpha", "beta", "gamma", "delta", "epsilon"]


class TestConfidenceKeywords:
    # MEASURED full shipped keyword tables; pinning each keyword's LEVEL
    # kills every XX-pad / case mutant across all 14 indicators.
    LOW: ClassVar[list[str]] = ["low confidence", "uncertain", "unclear", "possibly", "might be"]
    HIGH: ClassVar[list[str]] = ["high confidence", "confident", "certain", "clearly", "definitely"]
    MED: ClassVar[list[str]] = ["moderate confidence", "likely", "probably", "suggests"]

    @pytest.mark.parametrize("kw", LOW)
    def test_low_keywords(self, kw):
        assert _extract_confidence(f"saying X {kw} Y") == "low"

    @pytest.mark.parametrize("kw", HIGH)
    def test_high_keywords(self, kw):
        assert _extract_confidence(f"saying X {kw} Y") == "high"

    @pytest.mark.parametrize("kw", MED)
    def test_medium_keywords(self, kw):
        assert _extract_confidence(f"saying X {kw} Y") == "medium"

    def test_none_without_indicator(self):
        assert _extract_confidence("nothing indicative") is None

    def test_low_checked_before_high(self):
        # MEASURED precedence: 'confident but uncertain' -> low.
        assert _extract_confidence("I am confident but uncertain") == "low"
        assert _extract_confidence("certain, but possibly") == "low"


class TestRiskFactors:
    def test_pattern_dedup_and_keyword_order(self):
        # MEASURED: pattern capture first, keywords appended after.
        out = _extract_risk_factors(
            "risk factor: wet floor because slippery. Also wet floor mentioned. "
            "someone was loitering and an unknown person stayed."
        )
        assert out == ["wet floor because slippery", "unknown person", "loitering"]

    def test_keyword_appended_lowercase(self):
        # MEASURED: 'LOITERING' in text appends the shipped lowercase kw.
        assert _extract_risk_factors("there was LOITERING outside") == ["loitering"]

    def test_all_risk_patterns_capture(self):
        out = _extract_risk_factors(
            "suspicious because he ran. concerning due to noise. "
            "threat from the dog. increases the risk because darkness"
        )
        assert out == ["darkness", "he ran", "noise", "the dog"]

    def test_full_keyword_table(self):
        text = (
            "late night unusual time unknown person unrecognized "
            "suspicious behavior loitering approaching multiple attempts "
            "concealed obscured face"
        )
        assert _extract_risk_factors(text) == [
            "late night",
            "unusual time",
            "unknown person",
            "unrecognized",
            "suspicious behavior",
            "loitering",
            "approaching",
            "multiple attempts",
            "concealed",
            "obscured face",
        ]  # EXACT order: 10 shipped keywords, cap [:10]


class TestReasoningStepsForwardSubParses:
    def test_numbered_branch_carves_subfields(self):
        steps = _parse_reasoning_steps(
            "1. The camera indicates motion due to shadow. Uncertain.\n2. Second step clearly fine"
        )
        assert [s.step_number for s in steps] == [1, 2]
        # MEASURED: BOTH sub-parsers forwarded (kwargs removal/None dies).
        assert steps[0].key_factors == ["shadow", "motion due to shadow"]
        assert steps[0].confidence_indicator == "low"
        assert steps[1].key_factors == []
        assert steps[1].confidence_indicator == "high"

    def test_paragraph_branch_carves_subfields(self):
        steps = _parse_reasoning_steps("First para due to rain.\n\nSecond para likely ok.")
        assert [(s.step_number, s.content) for s in steps] == [
            (1, "First para due to rain."),
            (2, "Second para likely ok."),
        ]
        assert steps[0].key_factors == ["rain"]
        assert steps[1].confidence_indicator == "medium"

    def test_single_step_fallback(self):
        steps = _parse_reasoning_steps("one single line")
        assert [(s.step_number, s.content) for s in steps] == [(1, "one single line")]


class TestEnrichmentSources:
    def test_all_fourteen_known_labels_exact(self):
        snap = {
            k: {"f": 1}
            for k in [
                "florence",
                "clip",
                "weather",
                "violence",
                "clothing",
                "vehicle",
                "pet",
                "pose",
                "demographics",
                "image_quality",
                "zones",
                "baseline",
                "cross_camera",
                "detections",
            ]
        }
        assert [s.name for s in _parse_enrichment_sources(snap)] == [
            "Florence-2 Vision Analysis",
            "CLIP Embeddings",
            "Weather Analysis",
            "Violence Detection",
            "Clothing Analysis",
            "Vehicle Classification",
            "Pet Detection",
            "Pose Estimation",
            "Demographics Analysis",
            "Image Quality Assessment",
            "Zone Analysis",
            "Baseline Comparison",
            "Cross-Camera Correlation",
            "Object Detections",
        ]

    def test_known_legs_dict_list_scalar_empty(self):
        snap = {
            "florence": {"desc": "d", "tags": ["a"], "x": 1},
            "clip": [{"label": "cat", "score": 0.9, "z": 1, "y": 2, "w": 3, "v": 4}],
            "weather": [],
            "pose": 42,  # scalar: MEASURED populated=True, field_count 0
        }
        got = [
            (s.name, s.populated, s.field_count, s.sample_fields)
            for s in _parse_enrichment_sources(snap)
        ]
        assert got == [
            ("Florence-2 Vision Analysis", True, 3, ["desc", "tags", "x"]),
            # list: field_count = ITEM count (1), sample = data[0] keys, cap 5 of 6
            ("CLIP Embeddings", True, 1, ["label", "score", "z", "y", "w"]),
            ("Weather Analysis", False, 0, []),
            ("Pose Estimation", True, 0, []),
        ]

    def test_unknown_legs_dict_and_list(self):
        snap = {"mystery_box": {"k1": 1, "k2": 2}, "mystery_list": [{"a": 1}, {"b": 2}]}
        got = [
            (s.name, s.populated, s.field_count, s.sample_fields)
            for s in _parse_enrichment_sources(snap)
        ]
        # MEASURED: unknown name = key.replace('_',' ').title(); unknown
        # LIST ships sample_fields [] (known-list leg does NOT).
        assert got == [
            ("Mystery Box", True, 2, ["k1", "k2"]),
            ("Mystery List", True, 2, []),
        ]

    def test_empty_known_is_not_populated(self):
        got = _parse_enrichment_sources({"empty_known": {}})
        assert [(s.name, s.populated, s.field_count, s.sample_fields) for s in got] == [
            ("Empty Known", False, 0, [])
        ]

    def test_dict_sample_cap_five_of_six(self):
        snap = {"florence": dict.fromkeys("abcdef", 1)}
        assert _parse_enrichment_sources(snap)[0].sample_fields == ["a", "b", "c", "d", "e"]


class TestTruncationInfo:
    def test_none_and_empty_default_legs(self):
        for log in (None, {}):
            t = _parse_truncation_info(log)
            assert (t.was_truncated, t.original_length, t.truncated_length) == (
                False,
                None,
                None,
            )
            assert (t.dropped_sections, t.truncation_reason) == ([], None)

    def test_full_log_surfaces_reason(self):
        t = _parse_truncation_info(
            {
                "was_truncated": True,
                "original_length": 100,
                "truncated_length": 60,
                "dropped_sections": ["s1"],
                "reason": "budget",
            }
        )
        assert (t.was_truncated, t.original_length, t.truncated_length) == (True, 100, 60)
        assert (t.dropped_sections, t.truncation_reason) == (["s1"], "budget")


class TestHouseholdMatchesAllBranches:
    def test_list_branch_fields_and_defaults(self):
        out = _parse_household_matches(
            [
                {
                    "entity_type": "person",
                    "entity_name": "Ann",
                    "similarity_score": 0.9,
                    "match_method": "face",
                },
                {"name": "Bob"},
            ]
        )
        assert all(isinstance(m, HouseholdMatch) for m in out)  # kills append(None)
        assert [
            (m.entity_type, m.entity_name, m.similarity_score, m.match_method) for m in out
        ] == [
            ("person", "Ann", 0.9, "face"),
            ("unknown", "Bob", 0.0, None),  # MEASURED defaults + name fallback
        ]

    def test_dict_of_lists_branch_both_spellings(self):
        out = _parse_household_matches(
            {
                "pet": [
                    {"name": "Rex", "similarity": 0.7, "method": "gait"},
                    {"entity_name": "Max", "similarity_score": 0.4, "match_method": "tag"},
                ]
            }
        )
        assert all(isinstance(m, HouseholdMatch) for m in out)
        assert [
            (m.entity_type, m.entity_name, m.similarity_score, m.match_method) for m in out
        ] == [
            ("pet", "Rex", 0.7, "gait"),
            ("pet", "Max", 0.4, "tag"),
        ]

    def test_dict_branch_and_missing_fields(self):
        out = _parse_household_matches({"vehicle": {"name": "Van", "similarity": 0.55}})
        assert [
            (m.entity_type, m.entity_name, m.similarity_score, m.match_method) for m in out
        ] == [("vehicle", "Van", 0.55, None)]
        # MEASURED: empty match_data yields one match with name None.
        out2 = _parse_household_matches({"vehicle": {}})
        assert [
            (m.entity_type, m.entity_name, m.similarity_score, m.match_method) for m in out2
        ] == [("vehicle", None, 0.0, None)]

    def test_empty_and_none_input(self):
        assert _parse_household_matches(None) == []
        assert _parse_household_matches({}) == []
