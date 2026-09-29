# TARGET-MODULE: backend.services.prompts
"""Batch-30 lane F kill-battery: ``prompts.py`` clip/clothing/threat/violence renderers.

Functions (triage dumps ``/home/agent/runs/b30-triage/<fn>.txt``):
``format_clip_analysis_context`` (31 keys), ``format_clothing_analysis_context``
(24), ``build_threat_section`` (22), ``_format_violence_section`` (21).

Every expected value below was MEASURED on the pristine shipped module (no
source edit is applied anywhere: the kill is delivered by the mutmut
trampoline via ``MUTANT_UNDER_TEST``). Assertions are whole-string equality
against the SHIPPED contract, so header XX/case swaps, join-separator swaps,
``is not None`` polarity flips and ``getattr`` default swaps all die on the
same assert.

Equivalence honesty (banked rule — diff-shape lies): polarity mutants are
attacked from BOTH sides (attribute absent AND attribute populated) and
``getattr``-default mutants require the attribute to be ABSENT, so the bare
fixtures are load-bearing. Six keys are provably unbreakable and are named
in the ledger at the bottom of this file (they are NOT silently skipped):
``format_clothing_analysis_context__mutmut_29``,
``build_threat_section__mutmut_30/-32/-64/-91`` and
``_format_violence_section__mutmut_5``.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest import mock

from backend.services.prompts import (
    _format_violence_section,
    build_threat_section,
    format_clip_analysis_context,
    format_clothing_analysis_context,
)

# ---------------------------------------------------------------------------
# fixtures (plain attribute bags — the shipped code only reads attributes;
# SimpleNamespace factories are used instead of @dataclass because the sweep
# harness execs this file via importlib WITHOUT registering it in sys.modules,
# and dataclasses processing needs sys.modules[cls.__module__] on 3.14)
# ---------------------------------------------------------------------------


def _cls(
    raw_description: str,
    confidence: float,
    top_category: str = "casual",
    is_suspicious: bool = False,
    is_service_uniform: bool = False,
) -> Any:
    """Stand-in for fashion_clip_loader.ClothingClassification."""
    return SimpleNamespace(
        raw_description=raw_description,
        confidence=confidence,
        top_category=top_category,
        is_suspicious=is_suspicious,
        is_service_uniform=is_service_uniform,
    )


def _seg(
    clothing_items: Any = (),
    has_face_covered: bool = False,
    has_bag: bool = False,
    coverage_percentages: Any = None,
) -> Any:
    """Stand-in for segformer_loader.ClothingSegmentationResult.

    ``clothing_items`` is deliberately an ORDERED list: the shipped renderer
    feeds ``validate_clothing_items`` and sorts the RESULT, but a mutual-
    exclusion tie is broken by ``max(matches, key=confidences.get)`` — with a
    set-backed fixture the (mutated) empty-confidence path would return a
    process-random winner. An ordered list keeps the shipped-vs-mutated
    divergence deterministic.
    """
    return SimpleNamespace(
        clothing_items=list(clothing_items),
        has_face_covered=has_face_covered,
        has_bag=has_bag,
        coverage_percentages=coverage_percentages if coverage_percentages is not None else {},
    )


def _clip(**attrs: Any) -> Any:
    """Attribute-less-by-default enrichment stand-in."""
    return mock.MagicMock(spec=(), **attrs)


# ---------------------------------------------------------------------------
# format_clip_analysis_context — three guarded getattr sections + join
# ---------------------------------------------------------------------------

_CLIP_ALL = "\n".join(
    [
        "CLIP Scene Classification: 'normal activity' (0.82)",
        "  Top-3: 'normal activity' (0.82), 'person loitering' (0.12), 'trespassing' (0.06)",
        "CLIP Threat Pattern Matches:",
        "  'a person checking door handles' (0.78)",
        "  'a delivery person leaving a package' (0.65)",
        "CLIP Visual Anomaly Score: 0.73 (major deviation from baseline - investigate)",
        "  Baseline similarity: 0.27",
    ]
)

_SCENE = {"normal activity": 0.82, "person loitering": 0.12, "trespassing": 0.06}
_THREATS = {
    "a person checking door handles": 0.78,
    "a delivery person leaving a package": 0.65,
}


def test_clip_analysis_all_three_sections_exact():
    # kills mutmut_1 (sections=None -> AttributeError on .append), _2/_3/_8/_9
    # (scene_scores dead -> scene block vanishes), _10/_11/_16/_17 (scene_top
    # dead -> "Not performed"), _19/_20/_25/_26 (threats dead),
    # _28/_29/_34/_35 (anomaly_score dead), _36/_37/_42/_43 (similarity dead),
    # _18/_27/_44 (is-not-None polarity: block dropped on the populated side),
    # _45 (`if sections:` returns "" here instead of the join)
    result = format_clip_analysis_context(
        _clip(
            clip_scene_classification=_SCENE,
            clip_scene_top_label="normal activity",
            clip_threat_matches=_THREATS,
            clip_anomaly_score=0.73,
            clip_anomaly_similarity=0.27,
        )
    )
    assert result == _CLIP_ALL


def test_clip_analysis_no_clip_attributes_returns_empty_string():
    # kills _7/_15/_24/_33/_41 (2-arg getattr -> AttributeError on an absent
    # attribute), _18/_27/_44 (polarity emits a "Not performed" block on the
    # empty side) and _46 (`return "XXXX"` instead of "")
    assert format_clip_analysis_context(_clip()) == ""
    assert format_clip_analysis_context(None) == ""


def test_clip_analysis_scene_section_only_exact():
    # second (singleton) attack on every scene-line key: with ONLY the scene
    # attributes set, a dead scene_scores/scene_top collapses the whole return
    # value to "" or "Not performed" instead of the two-line block
    assert (
        format_clip_analysis_context(
            _clip(clip_scene_classification={"a": 0.5}, clip_scene_top_label="a")
        )
        == "CLIP Scene Classification: 'a' (0.50)\n  Top-3: 'a' (0.50)"
    )


def test_clip_analysis_scene_scores_without_top_label_is_not_performed():
    # shipped keeps a non-empty section ("Not performed") because the scores
    # guard passes while format_clip_scene_classification() sees top_label=None;
    # also re-kills _15 (2-arg getattr on the absent label)
    assert format_clip_analysis_context(_clip(clip_scene_classification={"a": 1.0})) == (
        "CLIP Scene Classification: Not performed"
    )


def test_clip_analysis_threat_section_only_exact():
    # singleton attack on _19/_20/_25/_26 + _27: a dead threat_matches leaves ""
    assert format_clip_analysis_context(_clip(clip_threat_matches=_THREATS)) == (
        "CLIP Threat Pattern Matches:\n"
        "  'a person checking door handles' (0.78)\n"
        "  'a delivery person leaving a package' (0.65)"
    )


def test_clip_analysis_empty_threat_dict_is_no_patterns_matched():
    # `is not None` guard passes for {}: an EMPTY threat dict must still render
    # its own sentinel line, which _27 (`if threat_matches is None:`) drops
    assert format_clip_analysis_context(_clip(clip_threat_matches={})) == (
        "CLIP Threat Pattern Matches: No patterns matched"
    )


def test_clip_analysis_anomaly_without_similarity_exact():
    # singleton attack on _28/_29/_34/_35 + _44: a dead anomaly_score returns ""
    assert format_clip_analysis_context(_clip(clip_anomaly_score=0.73)) == (
        "CLIP Visual Anomaly Score: 0.73 (major deviation from baseline - investigate)"
    )


def test_clip_analysis_anomaly_with_similarity_exact():
    # kills _36/_37/_42/_43: a dead similarity drops the "Baseline similarity"
    # tail line while the score line stays identical
    assert format_clip_analysis_context(
        _clip(clip_anomaly_score=0.73, clip_anomaly_similarity=0.27)
    ) == (
        "CLIP Visual Anomaly Score: 0.73 (major deviation from baseline - investigate)\n"
        "  Baseline similarity: 0.27"
    )


# ---------------------------------------------------------------------------
# format_clothing_analysis_context — entry guard, alert lines, joins
# ---------------------------------------------------------------------------

_SUSPICIOUS = _cls(
    raw_description="dark hoodie + face mask",
    confidence=0.825,
    top_category="mask",
    is_suspicious=True,
)
_SERVICE = _cls(
    raw_description="branded delivery jacket",
    confidence=0.64,
    top_category="delivery",
    is_service_uniform=True,
)
_PLAIN = _cls(raw_description="t-shirt and jeans", confidence=0.5)
# ordered list + coverage that makes "pants" the shipped winner
_SEG = _seg(
    clothing_items=["skirt", "pants", "hat", "bag"],
    has_face_covered=True,
    has_bag=True,
    coverage_percentages={"pants": 0.9, "skirt": 0.4},
)


def test_clothing_both_inputs_empty_returns_sentinel():
    # kills mutmut_2 (`if cc and not cs:` -> falls through to "No results"),
    # _3 (`and cs` -> same fall-through), and the sentinel string swaps
    # _4 (XX), _5 (lowercase), _6 (uppercase)
    assert format_clothing_analysis_context({}, None) == (
        "Clothing analysis: No person detections analyzed"
    )
    assert format_clothing_analysis_context({}, {}) == (
        "Clothing analysis: No person detections analyzed"
    )


def test_clothing_suspicious_attire_exact():
    # populated classifications with segmentation=None kill _1 (`and`->`or`
    # returns the no-detections sentinel because clothing_segmentation is
    # falsy) and _2; the exact body kills _12/_14 (attire ALERT XX/case swaps)
    # and _55 (person_lines join -> "XX\nXX")
    assert format_clothing_analysis_context({"det-1": _SUSPICIOUS}, None) == "\n".join(
        [
            "Person det-1:",
            "  Clothing: dark hoodie + face mask",
            "  Confidence: 82.5%",
            "  **ALERT**: Potentially suspicious attire detected",
            "    Category: mask",
        ]
    )


def test_clothing_service_uniform_exact():
    # kills _17 (service-uniform line XX swap) — also re-kills _1/_55
    assert format_clothing_analysis_context({"det-2": _SERVICE}, None) == "\n".join(
        [
            "Person det-2:",
            "  Clothing: branded delivery jacket",
            "  Confidence: 64.0%",
            "  [Service/delivery worker uniform detected - lower risk]",
        ]
    )


def test_clothing_two_persons_joined_by_blank_line():
    # kills _59 ("\n\n".join -> "XX\n\nXX") — a single person never exercises
    # the outer join separator
    out = format_clothing_analysis_context({"det-1": _SUSPICIOUS, "det-2": _SERVICE}, None)
    assert out == "\n\n".join(
        [
            "\n".join(
                [
                    "Person det-1:",
                    "  Clothing: dark hoodie + face mask",
                    "  Confidence: 82.5%",
                    "  **ALERT**: Potentially suspicious attire detected",
                    "    Category: mask",
                ]
            ),
            "\n".join(
                [
                    "Person det-2:",
                    "  Clothing: branded delivery jacket",
                    "  Confidence: 64.0%",
                    "  [Service/delivery worker uniform detected - lower risk]",
                ]
            ),
        ]
    )


def test_clothing_segmentation_without_classifications_returns_no_results():
    # classifications empty but segmentation truthy: the shipped guard falls
    # through and the loop never runs, so the EMPTY-list sentinel is returned.
    # kills _3 (guard enters on `and cs` -> "No person detections analyzed"),
    # _57 (`if (lines) or True` -> "") and the "No results" swaps _60/_61/_62
    assert format_clothing_analysis_context({}, {"det-1": _SEG}) == (
        "Clothing analysis: No results"
    )


def test_clothing_segmentation_block_and_conflict_resolution_exact():
    # exact 5-line block kills _46 (face-covering ALERT XX swap), _50/_51/_52
    # ("Carrying bag detected" XX/lower/upper swaps) and _55. The conflict line
    # is the confidence probe: shipped coverage picks "pants" (0.9 over skirt's
    # 0.4); _26 (`or {}` -> `and {}`), _27 (getattr(None, ...)), _33/_34
    # (coverage_percentages renamed) all hand validate_clothing_items an empty
    # confidence dict, where the ordered items list makes "skirt" win.
    assert format_clothing_analysis_context({"det-1": _PLAIN}, {"det-1": _SEG}) == "\n".join(
        [
            "Person det-1:",
            "  Clothing: t-shirt and jeans",
            "  Confidence: 50.0%",
            "  Clothing items: bag, hat, pants",
            "  **ALERT**: Face covering detected (hat/sunglasses/scarf)",
            "  Carrying bag detected",
        ]
    )


def test_clothing_segmentation_for_unmatched_detection_id_is_skipped():
    # guard `if clothing_segmentation and det_id in clothing_segmentation`:
    # segmentation exists but the id does not -> no segmentation lines at all
    assert format_clothing_analysis_context({"det-9": _PLAIN}, {"det-1": _SEG}) == "\n".join(
        ["Person det-9:", "  Clothing: t-shirt and jeans", "  Confidence: 50.0%"]
    )


def test_clothing_blank_segmentation_adds_no_lines():
    # a SegFormer result with no items/flags contributes nothing (pins that the
    # three seg sub-guards are all falsy, so the conflict probe above is the
    # only path that can move the confidence dict)
    assert format_clothing_analysis_context({"det-1": _PLAIN}, {"det-1": _seg()}) == "\n".join(
        ["Person det-1:", "  Clothing: t-shirt and jeans", "  Confidence: 50.0%"]
    )


# ---------------------------------------------------------------------------
# build_threat_section — protocol/dict dispatch, defaults, join
# ---------------------------------------------------------------------------

_NO_THREATS = "No threats detected."


def test_threat_none_threat_field_returns_sentinel():
    assert build_threat_section(_clip(threat=None)) == _NO_THREATS


def test_threat_dict_with_one_threat_exact():
    # exact 2-line block kills _51 (header XX swap) and _118 ("\n" -> "XX\nXX")
    assert (
        build_threat_section(
            _clip(
                threat={
                    "has_threat": True,
                    "threats": [{"threat_type": "knife", "severity": "high", "confidence": 0.88}],
                }
            )
        )
        == "**THREATS DETECTED:**\n- KNIFE (severity: high, confidence: 88%)"
    )


def test_threat_dict_threats_detected_flag_path_exact():
    # the `or threat.get("threats_detected", False)` fallback branch (pin the
    # shipped 88%-style line through the alternate truth source)
    assert (
        build_threat_section(
            _clip(
                threat={
                    "threats_detected": True,
                    "threats": [{"type": "fire", "severity": "critical", "confidence": 1.0}],
                }
            )
        )
        == "**THREATS DETECTED:**\n- FIRE (severity: critical, confidence: 100%)"
    )


def test_threat_dict_missing_threats_key_renders_header_only():
    # "threats" ABSENT while has_threat is truthy: shipped default [] yields a
    # header-only block; _38 (default None) and _40 (2-arg .get -> None) both
    # crash on `for t in None`
    assert build_threat_section(_clip(threat={"has_threat": True})) == "**THREATS DETECTED:**"


def test_threat_dict_threats_only_without_has_threat_returns_sentinel():
    # has_threat AND threats_detected both ABSENT: shipped default False keeps
    # the sentinel; _35 (default True) reports a threat out of nothing
    assert build_threat_section(_clip(threat={"threats": [{"threat_type": "knife"}]})) == (
        _NO_THREATS
    )


def test_threat_dict_empty_returns_sentinel():
    # second (fully-empty) attack on _35/_30/_32: {} has neither flag key
    assert build_threat_section(_clip(threat={})) == _NO_THREATS


def test_threat_dict_falsy_entries_use_defaults_exact():
    # every key falsy/absent in a dict entry -> the dict-branch defaults:
    # "unknown" (then .upper()-ed), severity "high", confidence 0.0.
    # kills _63 ("XXunknownXX" survives .upper()), _79 (`or 1.0` prints 100%),
    # _51/_118 (header + "\n" join). _64 ("unknown" -> "UNKNOWN") is NOT
    # killable here — see the ledger below.
    assert build_threat_section(
        _clip(
            threat={
                "has_threat": True,
                "threats": [{}, {"type": "", "severity": "", "confidence": ""}],
            }
        )
    ) == "\n".join(
        [
            "**THREATS DETECTED:**",
            "- UNKNOWN (severity: high, confidence: 0%)",
            "- UNKNOWN (severity: high, confidence: 0%)",
        ]
    )


def test_threat_object_without_threats_attribute_renders_header_only():
    # "threats" ABSENT on the protocol object: the shipped
    # `threat.threats if hasattr(threat, "threats") else []` yields []; _16
    # (`or True`) drops the guard and raises AttributeError
    assert build_threat_section(_clip(threat=_clip(has_threat=True))) == "**THREATS DETECTED:**"


def test_threat_object_bare_entry_defaults_exact():
    # non-dict entry with ALL THREE attributes absent -> getattr defaults:
    # "unknown" / "high" / 0.0. Kills _84/_96 (default None -> "None"),
    # _87/_99/_108/_111 (2-arg getattr -> AttributeError), _90 ("XXunknownXX"
    # survives .upper()), _102/_103 (severity default XX/uppercase — severity is
    # interpolated RAW, not upper-cased), _114 (default 1.0 -> "100%"), plus
    # _51/_118. _91 ("unknown" -> "UNKNOWN") is NOT killable — ledger.
    assert (
        build_threat_section(_clip(threat=_clip(has_threat=True, threats=[_clip()])))
        == "**THREATS DETECTED:**\n- UNKNOWN (severity: high, confidence: 0%)"
    )


def test_threat_object_populated_entry_exact():
    # the object-branch happy path (pins the attribute names the renames would
    # break, and that an explicit severity is NOT upper-cased)
    assert (
        build_threat_section(
            _clip(
                threat=_clip(
                    has_threat=True,
                    threats=[_clip(threat_type="gun", severity="critical", confidence=0.92)],
                )
            )
        )
        == "**THREATS DETECTED:**\n- GUN (severity: critical, confidence: 92%)"
    )


def test_threat_object_has_threat_false_returns_sentinel():
    # the opposite polarity side of `if not has_threat`: threats exist but the
    # flag is false -> no section
    assert (
        build_threat_section(
            _clip(threat=_clip(has_threat=False, threats=[_clip(threat_type="gun")]))
        )
        == _NO_THREATS
    )


def test_threat_unsupported_threat_type_returns_sentinel():
    # neither protocol nor dict (a bare str) falls to the else branch
    assert build_threat_section(_clip(threat="knife")) == _NO_THREATS


# ---------------------------------------------------------------------------
# _format_violence_section — gated renderer + three score defaults
# ---------------------------------------------------------------------------

_VIOLENCE_ALL_ZERO = (
    "**VIOLENCE DETECTED** (confidence: 0%)\n"
    "  Violent score: 0%\n"
    "  Non-violent score: 0%\n"
    "  ACTION REQUIRED: Immediate review recommended"
)


def test_violence_none_input_returns_none():
    assert _format_violence_section(None) is None


def test_violence_missing_is_violent_returns_none():
    # is_violent ABSENT: shipped default False -> None. _8 (2-arg getattr)
    # raises AttributeError here; _11 (default True) returns the alert string
    # instead. (_5, default None, is equivalent to False — ledger.)
    assert _format_violence_section(_clip()) is None


def test_violence_is_violent_false_returns_none():
    # populated-false side of the same gate
    assert _format_violence_section(_clip(is_violent=False, confidence=0.9)) is None


def test_violence_flags_violent_without_scores_uses_zero_defaults():
    # all three score attributes ABSENT: shipped defaults 0.0 render "0%".
    # Kills _15/_25/_35 (default None -> TypeError in f"{None:.0%}"),
    # _18/_28/_38 (2-arg getattr -> AttributeError) and _21/_31/_41
    # (default 1.0 -> "100%")
    assert _format_violence_section(_clip(is_violent=True)) == _VIOLENCE_ALL_ZERO


def test_violence_populated_exact():
    # populated scores pin the attribute NAMES (kills the XX/UPPER renames
    # _19/_20/_29/_30/_39/_40) and the getattr(None, ...) rebindings
    # _13/_23/_33, which silently collapse every number to 0%
    assert (
        _format_violence_section(
            _clip(is_violent=True, confidence=0.91, violent_score=0.78, non_violent_score=0.22)
        )
        == "**VIOLENCE DETECTED** (confidence: 91%)\n"
        "  Violent score: 78%\n"
        "  Non-violent score: 22%\n"
        "  ACTION REQUIRED: Immediate review recommended"
    )


# ---------------------------------------------------------------------------
# LEDGER — keys in the triage dumps that NO test can kill (proven equivalent),
# i.e. keys_covered = every other key in the four dumps.
#   format_clothing_analysis_context__mutmut_29
#       getattr(seg, ..., None) or {} -> `None or {}` == shipped `{} or {}`
#   build_threat_section__mutmut_30 / -32
#       threats_detected default False -> None (and 2-arg .get -> None): both
#       falsy, so bool(has_threat or <falsy>) is unchanged
#   build_threat_section__mutmut_64 / -91
#       "unknown" -> "UNKNOWN" is erased by the f-string's .upper()
#   _format_violence_section__mutmut_5
#       is_violent default False -> None: `not None` == `not False`
# ---------------------------------------------------------------------------
