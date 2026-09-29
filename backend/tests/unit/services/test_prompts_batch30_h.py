# TARGET-MODULE: backend.services.prompts
"""Batch-30 mutation-kill battery (lane H): prompts.py context formatters.

Scope — the 82 surviving mutant keys triaged for ``format_violence_context``
(12), ``format_class_anomaly_context`` (14), ``format_enhanced_clothing_context``
(12), ``format_image_quality_context`` (12), ``format_camera_health_context``
(13), ``build_summary_prompt`` (9), ``format_gender_classification_context`` (5)
and ``format_person_reid_context`` (5). The mutant-home red-check sweep of this
battery reports 75 RED / 7 GREEN; the 7 GREEN are provably equivalent mutants
(the sentinel/default of a value that is only ever compared, never rendered —
each is named in a comment on the test that reaches its line) and are listed
with one-line reasons in the lane report rather than tested vacuously.

Every assert is an exact whole-string (or whole-result) equality written
against the SHIPPED contract, so a text-swap mutant (XX wrap / lowercase /
UPPERCASE / join-separator) dies on the rendered bytes and a threshold mutant
must move a deliberately boundary-pinned input across its edge. The
``getattr(obj, "confidence", DEFAULT)`` family in
``format_enhanced_clothing_context`` is reached exclusively with NON-dict
payloads, because the dict arm of the ``isinstance`` ternary never consults the
third ``getattr`` argument — with a string payload the shipped ``0.0`` default
is the only value that leaves the section line absent.

The two ``call:arg_drop`` keys on ``ClassAnomalyResult`` (dropped
``risk_modifier=15``) are killed at the CALL SITE: the dataclass default is
also 15, so the built instance is attribute-for-attribute equal to shipped and
no field assert can see the deletion. ``unittest.mock.patch`` of the module
global, delegating through ``side_effect``, observes the argument list itself.

Those seven: the violence marginal-tier sentinel (32/33/34) and the camera
health ``recent`` sentinel (3) and ``change_type`` default (24/30/31). Each is
written into a value that the shipped code only ever tests for falseness or
equality against a branch literal — it is never interpolated or formatted — so
no reachable input separates shipped from mutant. Their tests are kept (they
pin the shipped contract and carry other keys) but they are NOT claimed as
kills.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from backend.services import prompts as prompts_module
from backend.services.prompts import (
    build_summary_prompt,
    format_camera_health_context,
    format_class_anomaly_context,
    format_enhanced_clothing_context,
    format_gender_classification_context,
    format_image_quality_context,
    format_person_reid_context,
    format_violence_context,
)


def _baseline(frequency, sample_count):
    """ClassBaselineProtocol stand-in (only these two attrs are read)."""
    return SimpleNamespace(frequency=frequency, sample_count=sample_count)


def _quality(**kw):
    """ImageQualityResult stand-in with neutral defaults."""
    base = {
        "is_good_quality": True,
        "quality_score": 90.0,
        "quality_issues": [],
        "is_blurry": False,
        "is_noisy": False,
    }
    base.update(kw)
    return SimpleNamespace(**base)


def _event(ts, camera, level, score, summary, objects):
    return {
        "timestamp": ts,
        "camera_name": camera,
        "risk_level": level,
        "risk_score": score,
        "summary": summary,
        "object_types": objects,
    }


# ---------------------------------------------------------------------------
# format_violence_context — None guard, tier attribute, score fallback tiers
# ---------------------------------------------------------------------------
def test_violence_none_returns_empty_string():
    # mutmut_2 (`return "XXXX"`): a whitespace blob is not the "" contract
    assert format_violence_context(None) == ""


def test_violence_is_none_identity():
    # mutmut_1 (`is None` -> `is not None`) is NOT killed by this assert: None
    # still reaches the tier block, recomputes from a 0.0 score and returns "".
    # The discriminator is the NON-None side — the flip short-circuits every
    # real payload to "", so the rendering tests below are what turn it red.
    assert format_violence_context(None) == ""


def test_violence_declared_suspected_tier_overrides_high_score():
    # mutmut_3 (`tier = None`), mutmut_4 (`getattr(None, ...)`), mutmut_9
    # ("XXconfidence_tierXX") and mutmut_10 ("CONFIDENCE_TIER") all IGNORE the
    # declared tier and recompute from the 0.95 score -> "definitive" block.
    result = SimpleNamespace(
        confidence_tier="suspected",
        confidence=0.95,
        violent_score=0.95,
        non_violent_score=0.05,
    )
    assert format_violence_context(result) == "\n".join(
        [
            "Possible violence detected (confidence: 95%)",
            "  Violent score: 95%",
            "  Non-violent score: 5%",
            "  Note: Moderate confidence - consider with other context for review",
        ]
    )


def test_violence_declared_definitive_tier_overrides_low_score():
    # mirror sample for mutmut_3/4/9/10: recomputing from the 0.10 score would
    # classify "marginal" and return "", so the tier attribute read is live here
    result = SimpleNamespace(
        confidence_tier="definitive",
        confidence=0.10,
        violent_score=0.10,
        non_violent_score=0.90,
    )
    assert format_violence_context(result) == "\n".join(
        [
            "**VIOLENCE DETECTED** (confidence: 10%)",
            "  Violent score: 10%",
            "  Non-violent score: 90%",
            "  Tier: definitive (confirmed)",
            "  ACTION REQUIRED: Immediate review recommended",
        ]
    )


def test_violence_score_0_70_is_definitive():
    # Anchor: pins the exact bytes of the definitive block (no in-scope survivor
    # sits on `>= 0.70`, so this row exists to make the declared-tier and
    # missing-score kills meaningful rather than vacuously empty).
    result = SimpleNamespace(
        confidence_tier=None,
        confidence=0.70,
        violent_score=0.70,
        non_violent_score=0.30,
    )
    assert format_violence_context(result) == "\n".join(
        [
            "**VIOLENCE DETECTED** (confidence: 70%)",
            "  Violent score: 70%",
            "  Non-violent score: 30%",
            "  Tier: definitive (confirmed)",
            "  ACTION REQUIRED: Immediate review recommended",
        ]
    )


def test_violence_score_0_55_is_suspected():
    # mutmut_27 (`>= 0.55` -> `> 0.55`) drops the exact 0.55 edge into
    # "marginal" -> ""; mutmut_21 (fallback 1.0) would land "definitive"
    result = SimpleNamespace(
        confidence_tier=None,
        confidence=None,
        violent_score=0.55,
        non_violent_score=0.45,
    )
    assert format_violence_context(result) == "\n".join(
        [
            "Possible violence detected (confidence: 55%)",
            "  Violent score: 55%",
            "  Non-violent score: 45%",
            "  Note: Moderate confidence - consider with other context for review",
        ]
    )


def test_violence_score_0_54_is_marginal_and_excluded():
    # Anchor for the 0.55 boundary test above. NOTE: mutmut_32 (`tier = None`),
    # mutmut_33 (`tier = "XXmarginalXX"`) and mutmut_34 (`tier = "MARGINAL"`)
    # are EQUIVALENT here — the sentinel value is only ever compared against
    # "definitive"/"suspected" and never interpolated, so all four values take
    # the else arm and return "". No input separates them (see the ledger).
    result = SimpleNamespace(
        confidence_tier=None,
        confidence=None,
        violent_score=0.54,
        non_violent_score=0.46,
    )
    assert format_violence_context(result) == ""


def test_violence_score_0_40_is_marginal_and_excluded():
    # Second marginal sample, far from every threshold, so the exclusion is not
    # an artefact of the 0.54 edge. violent_score is PRESENT here, so the
    # getattr fallback is not consulted — the mutmut_21 kill lives in the
    # missing-attribute test below.
    result = SimpleNamespace(
        confidence_tier=None,
        confidence=None,
        violent_score=0.40,
        non_violent_score=0.60,
    )
    assert format_violence_context(result) == ""


def test_violence_missing_score_uses_zero_default():
    # Shipped fallback 0.0 -> "marginal" -> "". Kill for mutmut_21, whose 1.0
    # fallback classifies "definitive" and renders the whole alert block, so the
    # difference here is a VALUE difference (the other attributes are supplied
    # precisely so nothing fails incidentally). It also kills mutmut_18, whose
    # trailing comma leaves a TWO-argument getattr and therefore raises
    # AttributeError on the absent attribute.
    result = SimpleNamespace(confidence_tier=None, confidence=1.0, non_violent_score=0.0)
    assert format_violence_context(result) == ""


# ---------------------------------------------------------------------------
# format_camera_health_context — acknowledgement scan and branch text
# ---------------------------------------------------------------------------
def test_camera_health_missing_acknowledged_attr_is_acked():
    # shipped default True -> `not True` is False, so the entry is skipped and
    # "" is returned. mutmut_7 (None) and mutmut_13 (False) both make it live
    # and render the else-branch alert.
    change = SimpleNamespace(change_type="unknown", similarity_score=0.5)
    assert format_camera_health_context("cam1", [change]) == ""


def test_camera_health_all_acknowledged_returns_empty():
    # Shipped `recent = None` + `if not recent:`. NOTE: mutmut_3 (`recent = ""`)
    # is EQUIVALENT — the sentinel is only ever read through that falseness
    # guard and never interpolated, so "" and None are indistinguishable. This
    # row documents the shipped "all acknowledged" contract instead.
    changes = [
        SimpleNamespace(change_type="view_blocked", similarity_score=0.10, acknowledged=True),
        SimpleNamespace(change_type="view_tampered", similarity_score=0.20, acknowledged=True),
    ]
    assert format_camera_health_context("cam1", changes) == ""


def test_camera_health_only_first_unacknowledged_is_rendered():
    # shipped breaks at the first unacknowledged entry, so entry three
    # ("view_tampered", 5%) must NOT appear
    changes = [
        SimpleNamespace(change_type="angle_changed", similarity_score=0.25, acknowledged=True),
        SimpleNamespace(change_type="view_blocked", similarity_score=0.30, acknowledged=False),
        SimpleNamespace(change_type="view_tampered", similarity_score=0.05, acknowledged=False),
    ]
    assert format_camera_health_context("cam1", changes) == "\n".join(
        [
            "## CAMERA HEALTH ALERT",
            "Camera view may be BLOCKED (similarity: 30%)",
            "Detection confidence is DEGRADED",
            "RISK MODIFIER: +30 points if intrusion detected during blocked view",
        ]
    )


def test_camera_health_none_and_empty_inputs():
    assert format_camera_health_context("cam1", None) == ""
    assert format_camera_health_context("cam1", []) == ""


def test_camera_health_missing_change_type_attribute_raises_on_deleted_default():
    # Kill for mutmut_27: its trailing comma leaves a TWO-argument getattr, so
    # the missing attribute raises AttributeError where shipped falls back to
    # "unknown" and takes the else block.
    # NOTE: mutmut_24 (None), mutmut_30 ("XXunknownXX") and mutmut_31
    # ("UNKNOWN") are EQUIVALENT — change_type is only ever compared against
    # the three branch literals and never interpolated, so every alternative
    # default still lands in the same else block with identical bytes.
    change = SimpleNamespace(similarity_score=0.42, acknowledged=False)
    assert (
        format_camera_health_context("cam1", [change]) == "## CAMERA HEALTH ALERT\n"
        "Scene change detected (similarity: 42%)\n"
        "Detection accuracy may be affected"
    )


def test_camera_health_unknown_change_type_exact():
    assert (
        format_camera_health_context(
            "cam1",
            [SimpleNamespace(change_type="unknown", similarity_score=0.42, acknowledged=False)],
        )
        == "## CAMERA HEALTH ALERT\n"
        "Scene change detected (similarity: 42%)\n"
        "Detection accuracy may be affected"
    )


def test_camera_health_unlisted_change_type_else_branch_exact():
    # mutmut_76 (XX wrap), mutmut_77 (lowercase) and mutmut_78 (UPPERCASE) of
    # the else-branch tail line all die on this whole-string equality
    assert (
        format_camera_health_context(
            "cam1",
            [SimpleNamespace(change_type="lens_fogged", similarity_score=1.0, acknowledged=False)],
        )
        == "## CAMERA HEALTH ALERT\n"
        "Scene change detected (similarity: 100%)\n"
        "Detection accuracy may be affected"
    )


def test_camera_health_angle_changed_branch_exact():
    assert (
        format_camera_health_context(
            "cam1",
            [
                SimpleNamespace(
                    change_type="angle_changed", similarity_score=0.80, acknowledged=False
                )
            ],
        )
        == "## CAMERA HEALTH ALERT\n"
        "Camera angle has CHANGED (similarity: 80%)\n"
        "Baseline patterns may not apply"
    )


def test_camera_health_view_tampered_branch_exact():
    assert (
        format_camera_health_context(
            "cam1",
            [
                SimpleNamespace(
                    change_type="view_tampered", similarity_score=0.05, acknowledged=False
                )
            ],
        )
        == "## CAMERA HEALTH ALERT\n"
        "Possible TAMPERING detected (similarity: 5%)\n"
        "CRITICAL: Verify camera integrity\n"
        "ESCALATION: If unknown person detected, escalate to CRITICAL priority"
    )


def test_camera_health_missing_similarity_uses_zero_default():
    # shipped default 0.0 renders "0%"; mutmut_41 (1.0) renders "100%";
    # mutmut_35 (None) raises TypeError on the percent format
    change = SimpleNamespace(change_type="angle_changed", acknowledged=False)
    assert (
        format_camera_health_context("cam1", [change]) == "## CAMERA HEALTH ALERT\n"
        "Camera angle has CHANGED (similarity: 0%)\n"
        "Baseline patterns may not apply"
    )


# ---------------------------------------------------------------------------
# format_image_quality_context — not-assessed, good, issues, change alert
# ---------------------------------------------------------------------------
def test_image_quality_none_returns_not_assessed():
    # mutmut_2 (XX wrap), mutmut_3 (lowercase), mutmut_4 (UPPERCASE)
    assert format_image_quality_context(None) == "Image quality: Not assessed"


def test_image_quality_none_with_explicit_flags_still_not_assessed():
    # Redundant byte-pinned sample of the same contract (mutmut_2/3/4 already
    # die on the plain None call; this one shows the guard runs before the
    # quality_change branch, so a None result is never decorated).
    assert format_image_quality_context(None, False, "") == "Image quality: Not assessed"


def test_image_quality_good_path_single_line():
    # is_good_quality True skips the issues/blur/noise block entirely
    assert format_image_quality_context(_quality(quality_score=87.0)) == (
        "Image quality: Good (score: 87/100)"
    )


def test_image_quality_good_score_is_rounded():
    # `{:.0f}` — a stray precision mutant would show "87.4"
    q = _quality(quality_score=87.4)
    assert format_image_quality_context(q) == "Image quality: Good (score: 87/100)"


def test_image_quality_issue_join_separator_is_comma_space():
    # mutmut_11 (`", "` -> `"XX, XX"`)
    q = _quality(is_good_quality=False, quality_score=42.0, quality_issues=["dark", "noisy"])
    assert format_image_quality_context(q) == (
        "Image quality: Issues detected - dark, noisy (score: 42/100)"
    )


def test_image_quality_single_issue_has_no_separator():
    # pairs with the two-item case so mutmut_11 cannot survive a one-item join
    q = _quality(is_good_quality=False, quality_score=33.0, quality_issues=["dark"])
    assert format_image_quality_context(q) == (
        "Image quality: Issues detected - dark (score: 33/100)"
    )


def test_image_quality_empty_issues_fall_back_to_general_degradation():
    # mutmut_12 (XX wrap of the fallback literal)
    q = _quality(is_good_quality=False, quality_score=15.0, quality_issues=[])
    assert format_image_quality_context(q) == (
        "Image quality: Issues detected - general degradation (score: 15/100)"
    )


def test_image_quality_blur_line_exact():
    # mutmut_16 (XX wrap) and mutmut_17 (lowercase swap) of the blur line
    q = _quality(
        is_good_quality=False,
        quality_score=42.0,
        quality_issues=["blurry"],
        is_blurry=True,
    )
    assert format_image_quality_context(q) == "\n".join(
        [
            "Image quality: Issues detected - blurry (score: 42/100)",
            "  - Blur detected: May indicate fast movement or camera issue",
        ]
    )


def test_image_quality_noise_line_exact():
    # mutmut_20 (XX wrap of the noise line)
    q = _quality(
        is_good_quality=False,
        quality_score=42.0,
        quality_issues=["grainy"],
        is_noisy=True,
    )
    assert format_image_quality_context(q) == "\n".join(
        [
            "Image quality: Issues detected - grainy (score: 42/100)",
            "  - Noise/artifacts detected: May affect detection accuracy",
        ]
    )


def test_image_quality_change_alert_block_exact():
    # mutmut_24 (`lines.append("")` -> `"XXXX"`) and mutmut_27 (XX wrap) /
    # mutmut_28 (lowercase) of the investigate line
    q = _quality(quality_score=90.0)
    assert format_image_quality_context(q, True, "Brightness dropped 40%") == (
        "Image quality: Good (score: 90/100)\n"
        "\n"
        "**QUALITY ALERT**: Brightness dropped 40%\n"
        "  Possible camera obstruction or tampering - investigate"
    )


def test_image_quality_change_alert_on_issues_path_keeps_newline_join():
    # mutmut_31 (`"\n".join` -> `"XX\nXX".join`): five real newlines separate
    # the six lines, none of which carry the mutant's "XX" padding
    q = _quality(
        is_good_quality=False,
        quality_score=20.0,
        quality_issues=[],
        is_blurry=True,
        is_noisy=True,
    )
    assert format_image_quality_context(q, True, "lens covered") == "\n".join(
        [
            "Image quality: Issues detected - general degradation (score: 20/100)",
            "  - Blur detected: May indicate fast movement or camera issue",
            "  - Noise/artifacts detected: May affect detection accuracy",
            "",
            "**QUALITY ALERT**: lens covered",
            "  Possible camera obstruction or tampering - investigate",
        ]
    )


# ---------------------------------------------------------------------------
# format_gender_classification_context — low-confidence note and boundary
# ---------------------------------------------------------------------------
def test_gender_empty_mapping_message():
    assert format_gender_classification_context({}) == "Gender estimation: No persons analyzed"


def test_gender_at_0_60_has_no_low_confidence_note():
    # mutmut_8 (`< 0.6` -> `<= 0.6`) appends the note at exactly 0.6
    genders = {"det-1": SimpleNamespace(gender="male", confidence=0.60)}
    assert format_gender_classification_context(genders) == (
        "Gender estimation (1 persons):\n  Person det-1: male (60%)"
    )


def test_gender_below_0_6_gets_the_note():
    # mutmut_6 (note -> None raises inside the f-string), mutmut_7 (`"XXXX"`),
    # mutmut_11 (XX wrap of the note) and mutmut_15 (`"XX\nXX"` join)
    genders = {"det-2": SimpleNamespace(gender="female", confidence=0.59)}
    assert format_gender_classification_context(genders) == (
        "Gender estimation (1 persons):\n  Person det-2: female (59%) [low confidence]"
    )


def test_gender_two_persons_mixed_confidences_exact():
    # one string pins the header count, the newline join and both note states
    genders = {
        "a1": SimpleNamespace(gender="male", confidence=0.85),
        "b2": SimpleNamespace(gender="female", confidence=0.32),
    }
    assert format_gender_classification_context(genders) == "\n".join(
        [
            "Gender estimation (2 persons):",
            "  Person a1: male (85%)",
            "  Person b2: female (32%) [low confidence]",
        ]
    )


# ---------------------------------------------------------------------------
# format_person_reid_context — header, thresholds, alternatives, join
# ---------------------------------------------------------------------------
def test_reid_none_means_not_performed():
    assert format_person_reid_context(None) == "Person re-identification: Not performed"


def test_reid_empty_mapping_means_all_new_individuals():
    assert (
        format_person_reid_context({})
        == "Person re-identification: No matches found (all new individuals)"
    )


def test_reid_high_confidence_boundary_at_0_9():
    # shipped `top_sim >= 0.9` wins ahead of the 0.8 arm; mutmut_10 (XX-wrapped
    # header) and mutmut_37 (`"XX\nXX"` join) die on the same equality
    matches = {"d1": [(SimpleNamespace(detection_id="alice"), 0.90)]}
    assert format_person_reid_context(matches) == "\n".join(
        [
            "Person re-identification:",
            "  Person d1: HIGH CONFIDENCE match to alice (90%)",
        ]
    )


def test_reid_likely_boundary_at_exactly_0_8():
    # mutmut_25 (`>= 0.8` -> `> 0.8`) sends exactly 0.8 into "Possible match"
    matches = {"d2": [(SimpleNamespace(detection_id="bob"), 0.80)]}
    assert format_person_reid_context(matches) == "\n".join(
        [
            "Person re-identification:",
            "  Person d2: Likely same person as bob (80%)",
        ]
    )


def test_reid_below_0_8_is_possible_match():
    matches = {"d3": [(SimpleNamespace(detection_id="carol"), 0.75)]}
    assert format_person_reid_context(matches) == "\n".join(
        [
            "Person re-identification:",
            "  Person d3: Possible match to carol (75%)",
        ]
    )


def test_reid_empty_match_list_renders_new_individual():
    # The `continue` arm: header plus one line, no match or alternative lines.
    # Also carries the mutmut_10 header and mutmut_37 join kills.
    assert format_person_reid_context({"d4": []}) == "\n".join(
        [
            "Person re-identification:",
            "  Person d4: New individual (no prior matches)",
        ]
    )


def test_reid_falsy_alt_detection_id_uses_unknown_literal():
    # mutmut_33 (`"XXunknownXX"`) and mutmut_34 (`"UNKNOWN"`) surface in the
    # alternative line; mutmut_37 (join) and mutmut_10 (header) in the first
    matches = {
        "d5": [
            (SimpleNamespace(detection_id="alice"), 0.95),
            (SimpleNamespace(detection_id=""), 0.70),
        ]
    }
    assert format_person_reid_context(matches) == "\n".join(
        [
            "Person re-identification:",
            "  Person d5: HIGH CONFIDENCE match to alice (95%)",
            "    Alternative: unknown (70%)",
        ]
    )


def test_reid_only_two_alternatives_are_rendered():
    # the `matches[1:3]` slice: the fourth match must not appear
    matches = {
        "d6": [
            (SimpleNamespace(detection_id="alice"), 0.95),
            (SimpleNamespace(detection_id="bob"), 0.85),
            (SimpleNamespace(detection_id="carol"), 0.80),
            (SimpleNamespace(detection_id="dave"), 0.60),
        ]
    }
    assert format_person_reid_context(matches) == "\n".join(
        [
            "Person re-identification:",
            "  Person d6: HIGH CONFIDENCE match to alice (95%)",
            "    Alternative: bob (85%)",
            "    Alternative: carol (80%)",
        ]
    )


# ---------------------------------------------------------------------------
# format_class_anomaly_context — sample floor, rarity bound, icons, kwargs
# ---------------------------------------------------------------------------
def test_anomaly_exactly_ten_samples_is_enough_data():
    # shipped `sample_count < 10` skips only BELOW ten. mutmut_19 (`<= 10`) and
    # mutmut_20 (`< 11`) both skip this class and return ("", [])
    context, anomalies = format_class_anomaly_context(
        "cam1", 2, {"dog": 1}, {"cam1:2:dog": _baseline(0.0, 10)}
    )
    assert context == "\n".join(
        [
            "## CLASS-SPECIFIC ANOMALIES",
            "[MEDIUM] dog RARE at this hour (expected: 0.0/hr, actual: 1)",
        ]
    )
    assert anomalies[0].class_name == "dog"
    assert anomalies[0].severity == "medium"
    assert anomalies[0].risk_modifier == 15


def test_anomaly_nine_samples_is_insufficient():
    # other side of the floor, so 19/20 cannot survive by moving the edge
    assert format_class_anomaly_context(
        "cam1", 2, {"dog": 1}, {"cam1:2:dog": _baseline(0.0, 9)}
    ) == (
        "",
        [],
    )


def test_anomaly_missing_baseline_is_skipped_not_fatal():
    assert format_class_anomaly_context("cam1", 2, {"dog": 1}, {}) == ("", [])


def test_anomaly_frequency_exactly_0_1_takes_the_volume_branch():
    # shipped `expected < 0.1` is FALSE at exactly 0.1, so the class falls to
    # the volume arm (1 > 3x0.1). mutmut_23 (`<= 0.1`) and mutmut_24 (`< 1.1`)
    # both route it to the RARE message instead — a different whole string.
    context, _anomalies = format_class_anomaly_context(
        "cam1", 3, {"bicycle": 1}, {"cam1:3:bicycle": _baseline(0.1, 40)}
    )
    assert context == (
        "## CLASS-SPECIFIC ANOMALIES\n[MEDIUM] bicycle UNUSUAL volume (1 vs expected 0.1)"
    )


def test_anomaly_frequency_0_5_count_1_is_not_anomalous():
    # shipped: 0.5 is not rare and 1 is not above 3x0.5 -> silent. mutmut_24
    # (`< 1.1`) makes 0.5 "rare" and emits an anomaly out of nothing.
    assert format_class_anomaly_context(
        "cam1", 3, {"bicycle": 1}, {"cam1:3:bicycle": _baseline(0.5, 40)}
    ) == ("", [])


def test_anomaly_frequency_0_05_is_rare():
    # 0.05 renders as "0.1" under `{:.1f}`, so the RARE message differs from the
    # 0.1-frequency volume message above. Also the [MEDIUM]/RARE line bytes used
    # by the icon and join keys (68/73/77) are anchored here.
    context, _anomalies = format_class_anomaly_context(
        "cam1", 3, {"bicycle": 1}, {"cam1:3:bicycle": _baseline(0.05, 40)}
    )
    assert context == (
        "## CLASS-SPECIFIC ANOMALIES\n"
        "[MEDIUM] bicycle RARE at this hour (expected: 0.1/hr, actual: 1)"
    )


def test_anomaly_security_class_uses_high_icon():
    # mutmut_68 (XX wrap of "[HIGH]"); the whole-string form is what makes the
    # XX wrap of the OTHER arm (mutmut_73) visible in the next test
    context, anomalies = format_class_anomaly_context(
        "cam1", 3, {"person": 1}, {"cam1:3:person": _baseline(0.0, 40)}
    )
    assert context == (
        "## CLASS-SPECIFIC ANOMALIES\n[HIGH] person RARE at this hour (expected: 0.0/hr, actual: 1)"
    )
    assert anomalies[0].severity == "high"


def test_anomaly_non_security_class_uses_medium_icon():
    # mutmut_73 (`else "XX[MEDIUM]XX"`)
    context, anomalies = format_class_anomaly_context(
        "cam1", 3, {"cat": 1}, {"cam1:3:cat": _baseline(0.0, 40)}
    )
    assert context == (
        "## CLASS-SPECIFIC ANOMALIES\n[MEDIUM] cat RARE at this hour (expected: 0.0/hr, actual: 1)"
    )
    assert anomalies[0].severity == "medium"


def test_anomaly_unusual_volume_line_and_fields():
    # frequency 2.0 keeps mutmut_24 out of the rare path; mutmut_49
    # (class_name=None), mutmut_52 (risk_modifier=None) and mutmut_59
    # (risk_modifier=16) die on the field asserts
    context, anomalies = format_class_anomaly_context(
        "cam1", 5, {"car": 7}, {"cam1:5:car": _baseline(2.0, 30)}
    )
    assert context == (
        "## CLASS-SPECIFIC ANOMALIES\n[MEDIUM] car UNUSUAL volume (7 vs expected 2.0)"
    )
    assert anomalies[0].class_name == "car"
    assert anomalies[0].severity == "medium"
    assert anomalies[0].risk_modifier == 15


def test_anomaly_three_times_expected_is_not_unusual():
    # shipped `count > expected * 3`: 6 IS 3x 2.0, so it is not "greater than"
    assert format_class_anomaly_context(
        "cam1", 5, {"car": 6}, {"cam1:5:car": _baseline(2.0, 30)}
    ) == (
        "",
        [],
    )


def test_anomaly_class_without_baseline_does_not_end_the_scan():
    # mutmut_21 (`continue` -> `break`) abandons the loop at "unknown" and
    # returns ("", []); shipped keeps iterating and still reports "dog"
    baselines = {"cam1:2:dog": _baseline(0.0, 40)}
    context, _anomalies = format_class_anomaly_context(
        "cam1", 2, {"unknown": 1, "dog": 1}, baselines
    )
    assert context == (
        "## CLASS-SPECIFIC ANOMALIES\n[MEDIUM] dog RARE at this hour (expected: 0.0/hr, actual: 1)"
    )


def test_anomaly_two_entries_join_on_real_newlines():
    # mutmut_63 (XX-wrapped "## CLASS-SPECIFIC ANOMALIES") and mutmut_77
    # (`"\n".join` -> `"XX\nXX".join`)
    baselines = {
        "cam1:8:dog": _baseline(0.0, 40),
        "cam1:8:car": _baseline(2.0, 30),
    }
    context, anomalies = format_class_anomaly_context("cam1", 8, {"dog": 1, "car": 7}, baselines)
    assert context == "\n".join(
        [
            "## CLASS-SPECIFIC ANOMALIES",
            "[MEDIUM] dog RARE at this hour (expected: 0.0/hr, actual: 1)",
            "[MEDIUM] car UNUSUAL volume (7 vs expected 2.0)",
        ]
    )
    assert [a.class_name for a in anomalies] == ["dog", "car"]


def test_anomaly_rare_branch_passes_risk_modifier_kwarg():
    # mutmut_43 deletes `risk_modifier=15,` from the RARE-branch constructor.
    # ClassAnomalyResult defaults risk_modifier to 15, so the built instance is
    # attribute-equal to shipped — only the call itself can show the deletion.
    real = prompts_module.ClassAnomalyResult
    with patch.object(prompts_module, "ClassAnomalyResult", autospec=True, side_effect=real) as spy:
        format_class_anomaly_context("cam1", 2, {"dog": 1}, {"cam1:2:dog": _baseline(0.0, 40)})
    assert spy.call_count == 1
    assert "risk_modifier" in spy.call_args.kwargs
    assert spy.call_args.kwargs["risk_modifier"] == 15


def test_anomaly_volume_branch_passes_risk_modifier_kwarg():
    # mutmut_56 deletes `risk_modifier=15,` from the VOLUME-branch constructor;
    # same call-site reasoning as the rare-branch test above
    real = prompts_module.ClassAnomalyResult
    with patch.object(prompts_module, "ClassAnomalyResult", autospec=True, side_effect=real) as spy:
        format_class_anomaly_context("cam1", 5, {"car": 7}, {"cam1:5:car": _baseline(2.0, 30)})
    assert spy.call_count == 1
    assert "risk_modifier" in spy.call_args.kwargs
    assert spy.call_args.kwargs["risk_modifier"] == 15


# ---------------------------------------------------------------------------
# build_summary_prompt — section wiring around SUMMARY_PROMPT_TEMPLATE
# ---------------------------------------------------------------------------
def test_summary_system_prompt_is_the_module_constant():
    # the system prompt is returned verbatim; every survivor sits on the
    # user-prompt assembly side, so this pins the untouched half
    system, _user = build_summary_prompt("2:00 PM", "3:00 PM", "hour", [], 0)
    assert system == prompts_module.SUMMARY_SYSTEM_PROMPT


def test_summary_two_events_user_prompt_exact():
    # mutmut_3 (XX wrap), mutmut_4 (lowercase) and mutmut_5 (UPPERCASE) all
    # rewrite the "**Event Details:**\n" heading that leads this block, as well
    # as the event_count / period slots
    events = [
        _event("2:05 PM", "Driveway", "HIGH", 72, "Unknown person on driveway", "person"),
        _event("2:40 PM", "Backyard", "CRITICAL", 91, "Glass break detected", "person, vehicle"),
    ]
    _system, user = build_summary_prompt("2:00 PM", "3:00 PM", "hour", events, 5)
    assert user == "\n".join(
        [
            "Summarize the following security events for the homeowner.",
            "",
            "**Time Window:** 2:00 PM to 3:00 PM",
            "**Period:** hour",
            "**High/Critical Events:** 2",
            "",
            "**Event Details:**",
            "",
            "Event 1:",
            "- Time: 2:05 PM",
            "- Camera: Driveway",
            "- Risk Level: HIGH (72/100)",
            "- Summary: Unknown person on driveway",
            "- Objects Detected: person",
            "",
            "Event 2:",
            "- Time: 2:40 PM",
            "- Camera: Backyard",
            "- Risk Level: CRITICAL (91/100)",
            "- Summary: Glass break detected",
            "- Objects Detected: person, vehicle",
            "",
            "",
            "**Instructions:**",
            "1. Write a concise narrative summary (2-4 sentences maximum)",
            "2. Highlight what happened and when",
            "3. Note any patterns (e.g., person and vehicle arriving together, repeated activity)",
            "4. Mention which areas of the property were affected",
            "5. Use a calm, informative tone - avoid alarmist language",
            "",
            "",
            "",
            "**Response Format:**",
            "Write only the summary paragraph. No headers, bullets, or formatting. Just natural prose.",
        ]
    )


def test_summary_events_suppress_routine_count_and_empty_instruction():
    # mutmut_51 (`empty_instruction = None` -> the literal "None" renders into
    # the prompt), mutmut_52 (`= "XXXX"`) and the no-events routine-count tail
    # would all change this string
    events = [_event("9:15 AM", "Porch", "HIGH", 61, "Stranger at porch", "person")]
    _system, user = build_summary_prompt("9:00 AM", "10:00 AM", "day", events, 7)
    assert user == "\n".join(
        [
            "Summarize the following security events for the homeowner.",
            "",
            "**Time Window:** 9:00 AM to 10:00 AM",
            "**Period:** day",
            "**High/Critical Events:** 1",
            "",
            "**Event Details:**",
            "",
            "Event 1:",
            "- Time: 9:15 AM",
            "- Camera: Porch",
            "- Risk Level: HIGH (61/100)",
            "- Summary: Stranger at porch",
            "- Objects Detected: person",
            "",
            "",
            "**Instructions:**",
            "1. Write a concise narrative summary (2-4 sentences maximum)",
            "2. Highlight what happened and when",
            "3. Note any patterns (e.g., person and vehicle arriving together, repeated activity)",
            "4. Mention which areas of the property were affected",
            "5. Use a calm, informative tone - avoid alarmist language",
            "",
            "",
            "",
            "**Response Format:**",
            "Write only the summary paragraph. No headers, bullets, or formatting. Just natural prose.",
        ]
    )


def test_summary_zero_events_no_routine_count_exact():
    # mutmut_40 (XX wrap of the whole no-events detail string) and mutmut_50
    # (`period=None` puts the literal "None" into the empty-state instruction
    # instead of "hour")
    _system, user = build_summary_prompt("3:00 PM", "4:00 PM", "hour", [], 0)
    assert user == "\n".join(
        [
            "Summarize the following security events for the homeowner.",
            "",
            "**Time Window:** 3:00 PM to 4:00 PM",
            "**Period:** hour",
            "**High/Critical Events:** 0",
            "",
            "**Event Details:**",
            "No high or critical events in this period.",
            "",
            "**Instructions:**",
            "1. Write a concise narrative summary (2-4 sentences maximum)",
            "2. Highlight what happened and when",
            "3. Note any patterns (e.g., person and vehicle arriving together, repeated activity)",
            "4. Mention which areas of the property were affected",
            "5. Use a calm, informative tone - avoid alarmist language",
            "",
            "IMPORTANT: There are ZERO events in this period. The event list above is empty.",
            'You MUST respond with ONLY a brief reassuring "all clear" message such as:',
            '"No high-priority security events detected in the past hour. The property has been quiet."',
            "Do NOT invent, fabricate, or describe any activity. There were no events — say so directly.",
            "You may mention the count of lower-priority detections if provided, but do NOT describe what those detections were.",
            "",
            "**Response Format:**",
            "Write only the summary paragraph. No headers, bullets, or formatting. Just natural prose.",
        ]
    )


def test_summary_routine_count_of_one_is_rendered():
    # mutmut_44 (`routine_count > 0` -> `> 1`) drops the parenthetical at 1;
    # mutmut_40 (XX wrap of the detail string) also dies here
    _system, user = build_summary_prompt("3:00 PM", "4:00 PM", "day", [], 1)
    assert user == "\n".join(
        [
            "Summarize the following security events for the homeowner.",
            "",
            "**Time Window:** 3:00 PM to 4:00 PM",
            "**Period:** day",
            "**High/Critical Events:** 0",
            "",
            "**Event Details:**",
            "No high or critical events in this period.",
            "(1 routine/low-priority detections occurred)",
            "",
            "**Instructions:**",
            "1. Write a concise narrative summary (2-4 sentences maximum)",
            "2. Highlight what happened and when",
            "3. Note any patterns (e.g., person and vehicle arriving together, repeated activity)",
            "4. Mention which areas of the property were affected",
            "5. Use a calm, informative tone - avoid alarmist language",
            "",
            "IMPORTANT: There are ZERO events in this period. The event list above is empty.",
            'You MUST respond with ONLY a brief reassuring "all clear" message such as:',
            '"No high-priority security events detected in the past day. The property has been quiet."',
            "Do NOT invent, fabricate, or describe any activity. There were no events — say so directly.",
            "You may mention the count of lower-priority detections if provided, but do NOT describe what those detections were.",
            "",
            "**Response Format:**",
            "Write only the summary paragraph. No headers, bullets, or formatting. Just natural prose.",
        ]
    )


def test_summary_routine_count_of_three_is_rendered():
    # second parenthetical sample so mutmut_44 is not a single-point claim
    _system, user = build_summary_prompt("3:00 PM", "4:00 PM", "day", [], 3)
    assert "(3 routine/low-priority detections occurred)" in user.split("\n")


def test_summary_period_reaches_both_slots():
    # mutmut_56 (`period_type=None` -> "**Period:** None") and mutmut_50
    # (`period=None` -> "... in the past None.") are killed by these two slots;
    # "week" is unused elsewhere so a swapped slot cannot silently re-match
    _system, user = build_summary_prompt("3:00 PM", "4:00 PM", "week", [], 0)
    assert "**Period:** week" in user.split("\n")
    assert (
        '"No high-priority security events detected in the past week. '
        'The property has been quiet."' in user.split("\n")
    )


# ---------------------------------------------------------------------------
# format_enhanced_clothing_context — non-dict confidence defaults per section
# ---------------------------------------------------------------------------
def test_clothing_none_and_empty_return_empty_string():
    assert format_enhanced_clothing_context(None) == ""
    assert format_enhanced_clothing_context({}) == ""


def test_clothing_suspicious_string_uses_zero_confidence_default():
    # shipped non-dict default 0.0 fails `confidence > 0.6`, so no section line
    # is appended and the `len(lines) == 1` guard collapses the header to "".
    # mutmut_25 (None) raises on `None > 0.6`; mutmut_28, whose trailing comma
    # leaves a TWO-argument getattr, raises AttributeError on the string payload;
    # mutmut_31 (1.0) renders the ALERT line instead of "".
    assert format_enhanced_clothing_context({"suspicious": "mask and hood"}) == ""


def test_clothing_suspicious_object_without_confidence_uses_zero_default():
    # same ledge from the other non-dict shape: getattr falls back to 0.0 and
    # the header-only guard returns "". 25/28/31 behave as in the string case.
    payload = SimpleNamespace(label="balaclava")
    assert format_enhanced_clothing_context({"suspicious": payload}) == ""


def test_clothing_suspicious_string_above_threshold_still_alerts():
    # proves the zero-default test above is not vacuous: with a real
    # confidence on the same payload shape the ALERT line IS rendered
    payload = SimpleNamespace(confidence=0.82)
    assert format_enhanced_clothing_context({"suspicious": payload}) == (
        "### Person Appearance Analysis\n- **ALERT**: namespace(confidence=0.82) (confidence: 82%)"
    )


def test_clothing_delivery_string_uses_zero_confidence_default():
    # mutmut_65 (None) raises on `None > 0.5`, mutmut_68 (two-argument getattr)
    # raises AttributeError on the string, and mutmut_71 (1.0) emits the
    # service-worker line where shipped renders nothing at all.
    assert format_enhanced_clothing_context({"delivery": "courier uniform"}) == ""


def test_clothing_delivery_object_without_confidence_uses_zero_default():
    payload = SimpleNamespace(label="postal shirt")
    assert format_enhanced_clothing_context({"delivery": payload}) == ""


def test_clothing_delivery_object_with_confidence_renders_percent():
    # non-vacuity anchor for the delivery default family
    payload = SimpleNamespace(confidence=0.77)
    assert format_enhanced_clothing_context({"delivery": payload}) == (
        "### Person Appearance Analysis\n"
        "- Service worker identified: namespace(confidence=0.77) (77%)"
    )


def test_clothing_utility_string_uses_zero_confidence_default():
    # mutmut_105 (None) raises on `None > 0.5`, mutmut_108 (two-argument
    # getattr) raises AttributeError, mutmut_111 (1.0) emits the line.
    assert format_enhanced_clothing_context({"utility": "hi-vis vest"}) == ""


def test_clothing_utility_object_without_confidence_uses_zero_default():
    payload = SimpleNamespace(label="lineman gear")
    assert format_enhanced_clothing_context({"utility": payload}) == ""


def test_clothing_utility_object_with_confidence_renders_percent():
    # non-vacuity anchor for the utility default family
    payload = SimpleNamespace(confidence=0.66)
    assert format_enhanced_clothing_context({"utility": payload}) == (
        "### Person Appearance Analysis\n"
        "- Utility worker identified: namespace(confidence=0.66) (66%)"
    )


def test_clothing_carrying_string_renders_zero_percent():
    # the carrying section has no threshold, so the shipped 0.0 default shows
    # up as "(0%)". mutmut_143 (`getattr(None, ...)` -> TypeError on the
    # missing attribute read of a str) and the name swaps (mutmut_149/150,
    # which also fall back to 0.0 — killed by the anchor below)
    assert format_enhanced_clothing_context({"carrying": "cardboard box"}) == (
        "### Person Appearance Analysis\n- Carrying: cardboard box (0%)"
    )


def test_clothing_carrying_object_with_confidence_attribute_renders_percent():
    # the discriminating input for the carrying default family: shipped reads
    # 0.88 -> "(88%)" while mutmut_143 (getattr off None) always yields 0.0 and
    # mutmut_149 ("XXconfidenceXX") / mutmut_150 ("CONFIDENCE") read a missing
    # attribute and fall back to 0.0 -> "(0%)"
    payload = SimpleNamespace(confidence=0.88)
    assert format_enhanced_clothing_context({"carrying": payload}) == (
        "### Person Appearance Analysis\n- Carrying: namespace(confidence=0.88) (88%)"
    )


def test_clothing_carrying_object_without_confidence_renders_zero_percent():
    # shipped 0.0 default -> "(0%)"
    payload = SimpleNamespace(item="backpack")
    assert format_enhanced_clothing_context({"carrying": payload}) == (
        "### Person Appearance Analysis\n- Carrying: namespace(item='backpack') (0%)"
    )


def test_clothing_casual_string_renders_without_confidence():
    assert format_enhanced_clothing_context({"casual": "hoodie and jeans"}) == (
        "### Person Appearance Analysis\n- General attire: hoodie and jeans"
    )


def test_clothing_sections_keep_declaration_order():
    # Header + delivery + utility + carrying + casual in shipped order. No
    # in-scope survivor reorders blocks; this row anchors the multi-line join
    # and the dict arm (which never reaches the non-dict getattr defaults).
    result = format_enhanced_clothing_context(
        {
            "delivery": {"confidence": 0.70, "top_match": "delivery uniform"},
            "utility": {"confidence": 0.70, "top_match": "utility worker"},
            "carrying": {"confidence": 0.40, "top_match": "cardboard box"},
            "casual": {"top_match": "hoodie and jeans"},
        }
    )
    assert result == "\n".join(
        [
            "### Person Appearance Analysis",
            "- Service worker identified: delivery uniform (70%)",
            "- Utility worker identified: utility worker (70%)",
            "- Carrying: cardboard box (40%)",
            "- General attire: hoodie and jeans",
        ]
    )
