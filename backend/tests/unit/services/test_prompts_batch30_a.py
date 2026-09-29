# TARGET-MODULE: backend.services.prompts
"""Batch-30 kill battery A: ``prompts.build_person_analysis_section`` (88 survivors).

Every assert is written against the SHIPPED contract as an exact whole-string
equality, so every representation branch (pose object / pose dict, clothing
object-with-categories / clothing ``raw_description`` / clothing dict /
clothing string, demographics dict, action object / action dict / action
string) is pinned to the character, including the ``.1%`` / ``.0%`` renderings
and the ``"YES"`` / ``"No"`` literals. A comment above each test names the
surviving mutmut key(s) it kills.

Honesty ledger. Two families are provably EQUIVALENT and are not "covered":
the ``getattr``/``.get`` falsy-default swaps (``False`` -> ``None`` -> the
bare-``default``-dropped spelling) sitting on a line whose value only feeds
the ``"YES" if flag else "No"`` truthiness ternary, and the ``hasattr(clothing,
"raw_description")`` dispatch guard, whose reordering cannot be observed on any
value of ``clothing`` because ``raw_description`` never coexists with
``categories`` on the shipped inputs. Each such key is named in the dispatch
report with its one-line reason.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

# This fragment lives OUTSIDE the repo tree (/home/agent/runs/b30-frags), so
# pytest gives it no sys.path entry for the repo. The harness always invokes it
# with the repo root (or the mutant home) as cwd, and the batch-30 sweep helper
# inserts cwd itself — mirror that so the import below resolves in both worlds.
_ROOT = os.getcwd()
if os.path.isfile(os.path.join(_ROOT, "backend", "services", "prompts.py")):
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)

from backend.services.prompts import build_person_analysis_section  # noqa: E402


@dataclass
class FakeEnrichment:
    """Minimal ``OnDemandEnrichmentLike`` stand-in (only the 5 read fields)."""

    pose: Any = None
    clothing: Any = None
    demographics: Any = None
    action: Any = None
    reid_embedding: Any = None


# ---------------------------------------------------------------------------
# Pose & Posture — dict branch defaults (L3784-L3786)
# ---------------------------------------------------------------------------
def test_pose_empty_dict_renders_unknown_and_zero_confidence():
    # kills build_person_analysis_section__mutmut_29 (inner default None ->
    # None.lower() AttributeError), _31 (missing default -> same crash),
    # _34/_35 ("XXunknownXX"/"UNKNOWN" label swaps), _44/_46 (confidence
    # default None -> format crash), _49 (confidence default 1.0 -> 100.0%)
    result = build_person_analysis_section(FakeEnrichment(pose={}))

    assert result == (
        "### Pose & Posture\n- Detected pose: unknown\n- Confidence: 0.0%\n- Suspicious posture: No"
    )


def test_pose_object_lying_is_suspicious():
    # kills __mutmut_19 ("XXlyingXX" in the tuple), __mutmut_20 ("LYING"):
    # the tuple is matched against pose_class.lower(), so the shipped
    # lowercase "lying" must flip the flag to YES.
    enrichment = FakeEnrichment(pose=SimpleNamespace(pose_class="lying", pose_confidence=0.66))

    assert build_person_analysis_section(enrichment) == (
        "### Pose & Posture\n- Detected pose: lying\n- Confidence: 66.0%\n- Suspicious posture: YES"
    )


def test_pose_dict_classification_crawling_is_suspicious():
    # kills __mutmut_55 ("XXcrawlingXX"), __mutmut_56 ("CRAWLING") on the
    # dict branch's own copy of the membership tuple (L3786).
    enrichment = FakeEnrichment(pose={"classification": "crawling", "confidence": 0.72})

    assert build_person_analysis_section(enrichment) == (
        "### Pose & Posture\n"
        "- Detected pose: crawling\n"
        "- Confidence: 72.0%\n"
        "- Suspicious posture: YES"
    )


def test_pose_dict_classification_lying_is_suspicious():
    # kills __mutmut_57 ("XXlyingXX"), __mutmut_58 ("LYING") — dict branch.
    enrichment = FakeEnrichment(pose={"classification": "lying", "confidence": 0.4})

    assert build_person_analysis_section(enrichment) == (
        "### Pose & Posture\n- Detected pose: lying\n- Confidence: 40.0%\n- Suspicious posture: YES"
    )


# ---------------------------------------------------------------------------
# Appearance — object-with-categories branch (L3798-L3805, L3827)
# ---------------------------------------------------------------------------
def test_clothing_object_without_getitem_yields_blank_listing():
    # kills __mutmut_78 (`if hasattr(...) or True`): the guard exists so a
    # non-subscriptable categories attribute degrades to an empty listing;
    # the mutant slices it and dies with TypeError.
    enrichment = FakeEnrichment(clothing=SimpleNamespace(categories=5))

    assert build_person_analysis_section(enrichment) == (
        "### Appearance\n- Clothing: \n- Suspicious attire: No"
    )


def test_clothing_object_categories_truncated_to_three():
    # kills __mutmut_79 (`[:3]` -> `[:4]`): a fourth category must not render.
    enrichment = FakeEnrichment(
        clothing=SimpleNamespace(
            categories=[
                {"category": "a", "confidence": 0.1},
                {"category": "b", "confidence": 0.2},
                {"category": "c", "confidence": 0.3},
                {"category": "d", "confidence": 0.4},
            ]
        )
    )

    assert build_person_analysis_section(enrichment) == (
        "### Appearance\n- Clothing: a (10%), b (20%), c (30%)\n- Suspicious attire: No"
    )


def test_clothing_object_categories_join_and_lookup_keys():
    # kills __mutmut_88 ("XX, XX" joiner), _95 (`get(None, 0)` -> renders "0"),
    # _99/_100 ("XXconfidenceXX"/"CONFIDENCE" key swaps -> "(0%)"), and
    # _111 (getattr default True with is_suspicious absent -> "YES").
    enrichment = FakeEnrichment(
        clothing=SimpleNamespace(
            categories=[
                {"category": "jacket", "confidence": 0.9},
                {"category": "pants", "confidence": 0.85},
            ]
        )
    )

    assert build_person_analysis_section(enrichment) == (
        "### Appearance\n- Clothing: jacket (90%), pants (85%)\n- Suspicious attire: No"
    )


def test_clothing_object_category_without_confidence_renders_zero():
    # kills __mutmut_96/_98 (confidence default None -> format TypeError)
    # and __mutmut_101 (default 1 -> "(100%)").
    enrichment = FakeEnrichment(clothing=SimpleNamespace(categories=[{"category": "hoodie"}]))

    assert build_person_analysis_section(enrichment) == (
        "### Appearance\n- Clothing: hoodie (0%)\n- Suspicious attire: No"
    )


def test_clothing_object_category_without_name_renders_the_mapping():
    # kills __mutmut_90/_92 (`c.get('category', None)` / default dropped):
    # shipped falls back to the category object itself, the mutants print
    # "None (50%)".
    enrichment = FakeEnrichment(clothing=SimpleNamespace(categories=[{"confidence": 0.5}]))

    assert build_person_analysis_section(enrichment) == (
        "### Appearance\n- Clothing: {'confidence': 0.5} (50%)\n- Suspicious attire: No"
    )


def test_clothing_object_is_suspicious_renders_yes():
    # kills __mutmut_102 (= None), _103 (getattr(None, ...)), _109/_110
    # ("XXis_suspiciousXX"/"IS_SUSPICIOUS" attr-name swaps) and the
    # L3827 positive-branch swaps _176 (and False), _178 ("XXYESXX"),
    # _179 ("yes").
    enrichment = FakeEnrichment(
        clothing=SimpleNamespace(
            categories=[{"category": "mask", "confidence": 0.75}], is_suspicious=True
        )
    )

    assert build_person_analysis_section(enrichment) == (
        "### Appearance\n- Clothing: mask (75%)\n- Suspicious attire: YES"
    )


# ---------------------------------------------------------------------------
# Appearance — raw_description branch (L3806-L3808)
# ---------------------------------------------------------------------------
def test_clothing_raw_description_with_suspicious_flag():
    # kills __mutmut_112 (hasattr(None, ...)), _116/_117 (attribute-name
    # swaps -> else branch prints str(clothing) and "No"), and on this
    # input _119 (= None), _120 (getattr(None, ...)), _126/_127
    # (attribute-name swaps) plus _176/_178/_179.
    enrichment = FakeEnrichment(
        clothing=SimpleNamespace(raw_description="blue jeans, white t-shirt", is_suspicious=True)
    )

    assert build_person_analysis_section(enrichment) == (
        "### Appearance\n- Clothing: blue jeans, white t-shirt\n- Suspicious attire: YES"
    )


def test_clothing_raw_description_without_suspicious_flag():
    # kills __mutmut_128 (getattr default True -> "YES") plus the L3827
    # negative-branch swaps _177 (or True), _180 ("XXNoXX"), _181 ("no"),
    # _182 ("NO").
    enrichment = FakeEnrichment(clothing=SimpleNamespace(raw_description="hi-vis vest"))

    assert build_person_analysis_section(enrichment) == (
        "### Appearance\n- Clothing: hi-vis vest\n- Suspicious attire: No"
    )


# ---------------------------------------------------------------------------
# Appearance — dict branch (L3809-L3820)
# ---------------------------------------------------------------------------
def test_clothing_empty_dict_renders_unknown_attire():
    # kills __mutmut_131/_133 (`get("categories", None)` / default dropped ->
    # TypeError on None[:3]), _157 (`or True` -> empty join instead of
    # "unknown"), _161/_162 ("XXunknownXX"/"UNKNOWN") and _170 (get default
    # True) plus _177/_180/_181/_182.
    assert build_person_analysis_section(FakeEnrichment(clothing={})) == (
        "### Appearance\n- Clothing: unknown\n- Suspicious attire: No"
    )


def test_clothing_dict_categories_truncated_to_three():
    # kills __mutmut_136 (`[:3]` -> `[:4]`) on the dict branch.
    enrichment = FakeEnrichment(
        clothing={
            "categories": [
                {"category": "a", "confidence": 0.1},
                {"category": "b", "confidence": 0.2},
                {"category": "c", "confidence": 0.3},
                {"category": "d", "confidence": 0.4},
            ]
        }
    )

    assert build_person_analysis_section(enrichment) == (
        "### Appearance\n- Clothing: a (10%), b (20%), c (30%)\n- Suspicious attire: No"
    )


def test_clothing_dict_categories_join_and_defaults():
    # kills __mutmut_140 ("XX, XX" joiner) and, because is_suspicious is
    # absent, __mutmut_170 (get default True) plus _177/_180/_181/_182.
    enrichment = FakeEnrichment(
        clothing={
            "categories": [
                {"category": "jacket", "confidence": 0.9},
                {"category": "pants", "confidence": 0.85},
            ]
        }
    )

    assert build_person_analysis_section(enrichment) == (
        "### Appearance\n- Clothing: jacket (90%), pants (85%)\n- Suspicious attire: No"
    )


def test_clothing_dict_category_without_name_renders_the_mapping():
    # kills __mutmut_142 (`c.get('category', None)`), _144 (default dropped),
    # _147 (default str(None) -> "None (50%)").
    enrichment = FakeEnrichment(clothing={"categories": [{"confidence": 0.5}]})

    assert build_person_analysis_section(enrichment) == (
        "### Appearance\n- Clothing: {'confidence': 0.5} (50%)\n- Suspicious attire: No"
    )


def test_clothing_dict_category_without_confidence_renders_zero():
    # kills __mutmut_149/_151 (confidence default None -> format TypeError)
    # and __mutmut_154 (default 1 -> "(100%)").
    enrichment = FakeEnrichment(clothing={"categories": [{"category": "hat"}]})

    assert build_person_analysis_section(enrichment) == (
        "### Appearance\n- Clothing: hat (0%)\n- Suspicious attire: No"
    )


def test_clothing_dict_suspicious_true_renders_yes():
    # kills __mutmut_163 (= None), _164 (`get(None, False)`), _166
    # (`get(False)`), _168/_169 (key-name swaps) plus _176/_178/_179.
    enrichment = FakeEnrichment(clothing={"categories": ["mask"], "is_suspicious": True})

    assert build_person_analysis_section(enrichment) == (
        "### Appearance\n- Clothing: mask\n- Suspicious attire: YES"
    )


def test_clothing_string_falls_back_to_str_and_no_flag():
    # kills __mutmut_174 (else-branch `clothing_suspicious = True`) plus
    # _177/_180/_181/_182.
    enrichment = FakeEnrichment(clothing="casual attire")

    assert build_person_analysis_section(enrichment) == (
        "### Appearance\n- Clothing: casual attire\n- Suspicious attire: No"
    )


# ---------------------------------------------------------------------------
# Demographics — dict branch (L3840-L3841)
# ---------------------------------------------------------------------------
def test_demographics_empty_dict_renders_unknowns():
    # kills __mutmut_204/_205 (age fallback "XXunknownXX"/"UNKNOWN") and
    # __mutmut_212/_213 (gender fallback swaps).
    assert build_person_analysis_section(FakeEnrichment(demographics={})) == (
        "### Demographics\n- Estimated age: unknown\n- Gender: unknown"
    )


# ---------------------------------------------------------------------------
# Behavior — branch gate and per-branch defaults (L3858-L3869)
# ---------------------------------------------------------------------------
def test_action_object_without_confidence_takes_string_branch():
    # kills __mutmut_224 (`and` -> `or`): an object exposing only `action`
    # must fall through to str(action)/0.0; the mutant enters the attribute
    # branch and dies on the missing `confidence`.
    enrichment = FakeEnrichment(action=SimpleNamespace(action="loitering"))

    assert build_person_analysis_section(enrichment) == (
        "### Behavior\n"
        "- Detected action: namespace(action='loitering')\n"
        "- Confidence: 0.0%\n"
        "- Suspicious behavior: No"
    )


def test_action_object_without_flag_renders_no():
    # kills __mutmut_251 (getattr default True inside bool(...) -> "YES").
    enrichment = FakeEnrichment(action=SimpleNamespace(action="waving", confidence=0.4))

    assert build_person_analysis_section(enrichment) == (
        "### Behavior\n- Detected action: waving\n- Confidence: 40.0%\n- Suspicious behavior: No"
    )


def test_action_empty_dict_renders_unknown_and_zero():
    # kills __mutmut_262/_263 (name fallback "XXunknownXX"/"UNKNOWN"),
    # _270 (confidence fallback 1.0 -> 100.0%) and _279 (get default True).
    assert build_person_analysis_section(FakeEnrichment(action={})) == (
        "### Behavior\n- Detected action: unknown\n- Confidence: 0.0%\n- Suspicious behavior: No"
    )


def test_action_string_falls_back_with_zero_confidence():
    # kills __mutmut_285 (else-branch `is_suspicious = True`).
    assert build_person_analysis_section(FakeEnrichment(action="standing")) == (
        "### Behavior\n- Detected action: standing\n- Confidence: 0.0%\n- Suspicious behavior: No"
    )


# ---------------------------------------------------------------------------
# Section assembly (L3886)
# ---------------------------------------------------------------------------
def test_two_sections_join_with_double_newline():
    # kills __mutmut_303 ("XX\\n\\nXX" joiner).
    enrichment = FakeEnrichment(
        pose={"pose_class": "standing", "pose_confidence": 0.5},
        demographics={"age_range": "30-40", "gender": "male"},
    )

    assert build_person_analysis_section(enrichment) == (
        "### Pose & Posture\n"
        "- Detected pose: standing\n"
        "- Confidence: 50.0%\n"
        "- Suspicious posture: No\n"
        "\n"
        "### Demographics\n"
        "- Estimated age: 30-40\n"
        "- Gender: male"
    )
