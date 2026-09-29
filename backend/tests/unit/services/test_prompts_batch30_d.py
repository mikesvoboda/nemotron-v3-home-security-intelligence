# TARGET-MODULE: backend.services.prompts
"""Batch-30 kill battery (fragment D): prompts.py pose + action renderers.

Scope — the surviving mutant keys triaged for
``format_pose_analysis_context`` (52), ``format_action_recognition_context``
(42 in the dossier excerpt + the 5 risk-frozenset members 11/12/13/14/18 the
bank sweep added to the key file), ``_format_pose_section`` (1) and
``resolve_pose_scene_conflict`` (2) — 102 keys total. The frozenset family
(``high_risk_actions = None``, member swaps like ``"hiding"`` ->
``"XXhidingXX"``) dies to the same "hiding"/"loitering" inputs used for the
risk-level ladder.

Every assert is an exact whole-string equality against the SHIPPED contract, so
each string-swap mutant (``"Detected poses:"`` -> ``"DETECTED POSES:"``,
``" [SUSPICIOUS: ...]"`` -> ``"XX [SUSPICIOUS: ...]XX"``, join-separator swaps,
...) dies on the rendered text, while the ``.get(key, default)`` families die on
inputs crafted so the key is PRESENT (key-string mutants fall off the map and a
wrong key surfaces ``unknown``/the dict repr) or ABSENT (a default mutant
surfaces ``None``/``1.0``/``"UNKNOWN"``). ``confidence > 0.7`` is attacked with
the EXACT boundary value 0.7 plus a 0.75 inclusion anchor so the boundary test
cannot pass vacuously.

The only keys in scope that are NOT killed are the two ``resolve_pose_scene_
conflict`` else-arm string swaps: ``resolved_winner`` is compared exclusively
against ``"pose"``, so ``"scene"``/``"XXsceneXX"``/``"SCENE"`` are observably
identical (see the comment on the last test).
"""

from __future__ import annotations

import os
import sys

# This fragment lives OUTSIDE the repo tree (/home/agent/runs/b30-frags), so
# pytest gives it no sys.path entry for the repo. The harness always invokes it
# with the repo root (or the mutant home) as cwd, and the batch-30 sweep helper
# inserts cwd itself — mirror that so the import below resolves in both worlds.
_ROOT = os.getcwd()
if os.path.isfile(os.path.join(_ROOT, "backend", "services", "prompts.py")):
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)

from backend.services.prompts import (  # noqa: E402
    _format_pose_section,
    format_action_recognition_context,
    format_pose_analysis_context,
    resolve_pose_scene_conflict,
)


# ---------------------------------------------------------------------------
# format_pose_analysis_context — entry guards (mutmut_1..6)
# ---------------------------------------------------------------------------
def test_pose_analysis_none_returns_empty_string():
    # mutmut_1 (`is None` -> `is not None` falls through to the empty-dict
    # sentinel) and mutmut_2 (`return ""` -> `return "XXXX"`)
    assert format_pose_analysis_context(None) == ""
    assert format_pose_analysis_context() == ""


def test_pose_analysis_empty_dict_sentinel():
    # mutmut_3 (`if not pose_results` -> `if pose_results` renders a bare
    # "Detected poses:" header) and mutmut_4/5/6 (sentinel case/XX swaps)
    assert format_pose_analysis_context({}) == "Pose analysis: No poses detected"


# ---------------------------------------------------------------------------
# format_pose_analysis_context — non-dict entries (mutmut_13/22/25/33)
# ---------------------------------------------------------------------------
def test_pose_analysis_scalar_entry_string_value():
    # A str value is the ONLY way to reach the `else str(pose)` arm:
    # mutmut_13/25 (`or True` calls .get() on a str -> AttributeError),
    # mutmut_22 (`else str(None)` -> "None"), mutmut_33 (`else 1.0` -> "100%").
    # Also kills mutmut_11 (pose_class = None), mutmut_23 (confidence = None),
    # mutmut_34/35 (risk_note "" -> None/"XXXX") and the `not in`/`!=` flips
    # mutmut_37/47 that light up a plain pose with a risk note.
    assert format_pose_analysis_context({"p1": "standing"}) == (
        "Detected poses:\n  Person p1: standing (0%)"
    )


def test_pose_analysis_multi_entry_join_and_header():
    # mutmut_7 (lines = None), mutmut_8/9/10 (header swaps), mutmut_64
    # ("\\n" -> "XX\\nXX" — only observable with two or more rendered lines).
    # The dict entry additionally kills mutmut_12/34/35/37/47.
    result = format_pose_analysis_context(
        {
            "p1": "standing",
            "p2": {"classification": "crouching", "confidence": 0.95},
            "p3": ["x"],
        }
    )
    assert result == (
        "Detected poses:\n"
        "  Person p1: standing (0%)\n"
        "  Person p2: crouching (95%) [SUSPICIOUS: Low posture near ground]\n"
        "  Person p3: ['x'] (0%)"
    )


def test_pose_analysis_full_dict_entry():
    # key-present input: mutmut_14 (`get(None, ...)` -> "unknown"),
    # mutmut_18/19 ("XXclassificationXX"/"CLASSIFICATION" -> "unknown"),
    # mutmut_24/26/30/31 (confidence key mutants -> "0%"),
    # mutmut_12 (`and False` renders the dict repr), mutmut_16/17
    # (`get("unknown")`/`get("classification",)` -> None -> AttributeError),
    # mutmut_28 (`get(0.0)` -> None -> format TypeError).
    assert format_pose_analysis_context(
        {"p1": {"classification": "standing", "confidence": 0.873}}
    ) == ("Detected poses:\n  Person p1: standing (87%)")


def test_pose_analysis_missing_classification_uses_unknown():
    # key-ABSENT input: mutmut_15 (`default None` -> AttributeError),
    # mutmut_20/21 ("XXunknownXX"/"UNKNOWN" surface in the line),
    # mutmut_16/17/28 (None-valued lookups crash the .lower()/format).
    assert format_pose_analysis_context({"p1": {"confidence": 0.42}}) == (
        "Detected poses:\n  Person p1: unknown (42%)"
    )


def test_pose_analysis_missing_confidence_defaults_zero():
    # key-ABSENT confidence: mutmut_27/29 (default None -> format TypeError)
    # and mutmut_32 (default 1.0 -> "100%" instead of "0%").
    assert format_pose_analysis_context({"p1": {"classification": "standing"}}) == (
        "Detected poses:\n  Person p1: standing (0%)"
    )


# ---------------------------------------------------------------------------
# format_pose_analysis_context — risk-note ladder (mutmut_36..59)
# ---------------------------------------------------------------------------
def test_pose_analysis_crouching_suspicious_note():
    # mutmut_36 (`upper()` never matches), mutmut_38/39 (tuple member swaps),
    # mutmut_37 (`not in`), mutmut_42..45 (note -> None/lower/upper/XX).
    assert format_pose_analysis_context(
        {"p1": {"classification": "crouching", "confidence": 0.95}}
    ) == ("Detected poses:\n  Person p1: crouching (95%) [SUSPICIOUS: Low posture near ground]")


def test_pose_analysis_crawling_is_case_insensitive():
    # "Crawling" reaches the branch only through `.lower()`: kills mutmut_40/41
    # ("XXcrawlingXX"/"CRAWLING" in the membership tuple) and mutmut_36/38/39.
    assert format_pose_analysis_context(
        {"p1": {"classification": "Crawling", "confidence": 0.5}}
    ) == ("Detected poses:\n  Person p1: Crawling (50%) [SUSPICIOUS: Low posture near ground]")


def test_pose_analysis_running_note():
    # mutmut_46 (`upper()`), mutmut_47 (`!=`), mutmut_48/49 ("XXrunningXX"/
    # "RUNNING"), mutmut_51 (note text XX-wrapped).
    assert format_pose_analysis_context(
        {"p1": {"classification": "running", "confidence": 1.0}}
    ) == ("Detected poses:\n  Person p1: running (100%) [NOTE: Fast movement detected]")


def test_pose_analysis_lying_note():
    # mutmut_59 (person-on-ground note XX-wrapped) — the `elif` chain's last
    # arm needs its own input, no other pose reaches it.
    assert format_pose_analysis_context(
        {"p1": {"classification": "lying", "confidence": 0.33}}
    ) == ("Detected poses:\n  Person p1: lying (33%) [NOTE: Person on ground - may need attention]")


# ---------------------------------------------------------------------------
# format_action_recognition_context — entry guards (mutmut_1..6)
# ---------------------------------------------------------------------------
def test_action_recognition_none_returns_empty_string():
    # mutmut_1 (`is None` -> `is not None`), mutmut_2 (`return ""` -> "XXXX")
    assert format_action_recognition_context(None) == ""
    assert format_action_recognition_context() == ""


def test_action_recognition_empty_dict_sentinel():
    # mutmut_3 (`if not action_results` flip renders a bare "Detected
    # actions:"), mutmut_4/5/6 (sentinel case/XX swaps)
    assert format_action_recognition_context({}) == "Action recognition: No actions detected"


# ---------------------------------------------------------------------------
# format_action_recognition_context — scalar entry + high-risk ladder
# ---------------------------------------------------------------------------
def test_action_recognition_scalar_string_high_risk():
    # A bare str value is the ONLY way to reach `else [actions]` and
    # `else str(action)`: mutmut_17/20/31 (`or True` -> .get() on a str ->
    # AttributeError), mutmut_28 (`else str(None)` -> "None"), mutmut_39
    # (`else 1.0` -> "100%"). Header guards mutmut_7..10 and mutmut_15
    # (`action_list = None`) / mutmut_29 (`confidence = None`) die here too,
    # and "hiding" is a HIGH-risk member so mutmut_42/43/44/45 die on the tag.
    assert format_action_recognition_context({"p1": "hiding"}) == (
        "Detected actions:\n  Person p1: hiding (0%) **HIGH RISK**"
    )


def test_action_recognition_list_of_strings_and_join():
    # mutmut_16 (`and False` wraps the list -> "['hiding', 'walking']"),
    # mutmut_55 ("\\n" -> "XX\\nXX", needs two rendered lines), and the
    # non-risk "walking" line kills mutmut_40/41 (risk_level "" -> None/"XXXX")
    # plus mutmut_43 (`not in high_risk_actions` tags walking HIGH RISK).
    result = format_action_recognition_context({"p1": ["hiding", "walking"]})
    assert result == (
        "Detected actions:\n  Person p1: hiding (0%) **HIGH RISK**\n  Person p1: walking (0%)"
    )


def test_action_recognition_medium_risk_dict():
    # key-present dict: mutmut_21/25/26 (action key mutants surface the dict
    # repr instead of "loitering"), mutmut_19 (`and False` -> dict repr),
    # mutmut_30/32/34/36/37 (confidence key mutants -> "0%" or a TypeError on
    # None), mutmut_50 (" [Suspicious]" -> "XX [Suspicious]XX").
    assert format_action_recognition_context(
        {"p1": {"action": "loitering", "confidence": 0.62}}
    ) == ("Detected actions:\n  Person p1: loitering (62%) [Suspicious]")


def test_action_recognition_dict_without_action_key():
    # key-ABSENT "action": the shipped default is `str(action)`, i.e. the dict
    # repr — so mutmut_22/23/24 (default None -> AttributeError on .lower())
    # and mutmut_27 (`str(None)` -> "None") all surface here.
    assert format_action_recognition_context({"p1": {"confidence": 0.5}}) == (
        "Detected actions:\n  Person p1: {'confidence': 0.5} (50%)"
    )


def test_action_recognition_dict_without_confidence_key():
    # key-ABSENT "confidence": mutmut_33/35 (default None -> format
    # TypeError) and mutmut_38 (default 1.0 -> "100%" instead of "0%").
    assert format_action_recognition_context({"p1": {"action": "walking"}}) == (
        "Detected actions:\n  Person p1: walking (0%)"
    )


# ---------------------------------------------------------------------------
# _format_pose_section — confidence threshold boundary (mutmut_11)
# ---------------------------------------------------------------------------
def test_format_pose_section_excludes_confidence_at_exact_boundary():
    # mutmut_11 (`confidence > 0.7` -> `>= 0.7`) admits 0.7 verbatim, so the
    # shipped contract at the boundary is None — no section at all.
    assert _format_pose_section({"p1": {"classification": "standing", "confidence": 0.7}}) is None


def test_format_pose_section_includes_confidence_above_boundary():
    # Inclusion anchor proving the boundary test is not vacuous (a "always
    # None" body would pass the test above): 0.75 is a high-confidence pose.
    assert _format_pose_section({"p1": {"classification": "standing", "confidence": 0.75}}) == (
        "Detected poses:\n  Person p1: standing (75%)"
    )


# ---------------------------------------------------------------------------
# resolve_pose_scene_conflict — conditional (motion-blur) rule
# ---------------------------------------------------------------------------
def test_resolve_pose_scene_conflict_conditional_motion_blur():
    # Pins both arms of the "conditional" rule for ("running", "standing").
    # NOTE (equivalence honesty): surviving keys x_resolve_pose_scene_conflict__
    # mutmut_21 ("scene" -> "XXsceneXX") and __mutmut_22 ("scene" -> "SCENE")
    # are NOT killable — `resolved_winner` is only ever compared to "pose", so
    # every non-"pose" string takes the identical else arm and returns the same
    # dict. This test still pins the shipped observable contract for the arm.
    assert resolve_pose_scene_conflict("Running", 0.85, "person standing still", False) == {
        "resolved_pose": "unknown",
        "conflict_detected": True,
        "resolution": "Preferred scene interpretation",
    }
    assert resolve_pose_scene_conflict("running", 0.85, "a standing figure", True) == {
        "resolved_pose": "running",
        "conflict_detected": True,
        "resolution": "Preferred pose interpretation",
    }
