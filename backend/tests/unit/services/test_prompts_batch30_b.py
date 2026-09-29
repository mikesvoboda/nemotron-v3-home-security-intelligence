# TARGET-MODULE: backend.services.prompts
"""Batch-30 kill battery (fragment B): prompts.py confidence-quality renderers.

Scope — the 90 surviving mutant keys triaged for
``format_confidence_quality_summary`` (63), ``_compute_confidence_quality`` (4),
``format_detections_with_quality`` (15), ``format_scene_context`` (3),
``format_trajectory_context`` (3) and ``format_depth_context`` (2).

Every assert is an exact whole-string equality against the SHIPPED contract, so
the label/range/suffix/header/guidance text swaps die on the rendered text
(``"EXCELLENT"`` -> ``"XXEXCELLENTXX"`` / ``"excellent"``,
``">=0.90"`` -> ``"XX>=0.90XX"``, ``" - trust fully"`` -> ``" - TRUST FULLY"``,
the ``"\\n".join`` -> ``"XX\\nXX".join`` family, ...), while the
``.get("confidence")`` key mutants die on inputs crafted so the key is PRESENT
(the wrong key surfaces ``None`` -> the detection vanishes) and the
``None``-of-expression mutants die on the crash their own edit produces
(``counts = None`` -> ``TypeError`` inside the tier-count loop).

Equivalence honesty (the diff shape lies, so each claim below was constructed):
* ``format_confidence_quality_summary__mutmut_49/_50`` (``suffix = ""`` ->
  ``None`` / ``"XXXX"``) are TRUE EQUIVALENTS: the following
  ``if tier in (EXCELLENT, GOOD) / elif MODERATE / elif MARGINAL`` chain covers
  all four members of ``_ConfidenceQuality``, so ``suffix`` is ALWAYS rebound
  before the f-string reads it and the initialiser value is unobservable. (Only
  the sibling ``tier not in (...)`` flip ``_51`` makes it live, and that flip is
  itself killed by the all-four-tiers fixture.)
* ``format_detections_with_quality__mutmut_15/16/17/18/25/26/27`` mutate
  ``quality_counts``, which the shipped body only ever WRITES — there is no
  read of that dict anywhere in the function, so seeding a tier to ``1`` and the
  ``= 1`` / ``-= 1`` / ``+= 2`` arithmetic flips have no observable effect.
* ``format_scene_context__mutmut_12/19/20`` (``rfind(" ", 0, ...)`` -> start
  ``None`` / ``1``, and ``last_space > 0`` -> ``>= 0``) are unreachable: the
  shipped body ``caption = caption.strip()`` runs first, so a
  whitespace-stripped caption can never hold a space at index 0 — the value
  ``0`` is therefore impossible, which makes ``rfind`` start ``0``/``None``/``1``
  identical on every reachable input and collapses ``> 0`` onto ``>= 0``. The
  last test pins that truncation contract (and the fuzz-verified invariant)
  without pretending to kill them.
"""

from __future__ import annotations

import sys
from pathlib import Path

# This fragment lives OUTSIDE the repo tree (/home/agent/runs/b30-frags), so
# pytest gives it no sys.path entry for the repo. The harness always invokes it
# with the repo root (or the mutant home) as cwd, and the batch-30 sweep helper
# inserts cwd itself — mirror that so the import below resolves in both worlds.
_ROOT = str(Path.cwd())
if (Path(_ROOT) / "backend" / "services" / "prompts.py").is_file() and _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from backend.services.prompts import (  # noqa: E402
    _compute_confidence_quality,
    _ConfidenceQuality,
    format_confidence_quality_summary,
    format_depth_context,
    format_detections_with_quality,
    format_scene_context,
    format_trajectory_context,
)

# The closing guidance paragraph, verbatim from the shipped contract. Mutating
# any of its three source segments (_59/_60/_61, plus _58 = append(None)) has to
# change the assembled output to survive an equality assert against this.
GUIDANCE = (
    "Confidence guidance: EXCELLENT/GOOD detections are reliable. "
    "MODERATE detections should be corroborated with other signals. "
    "MARGINAL detections are uncertain — do not base risk score primarily on them."
)


class _Depth:
    """Minimal DepthAnalysisResult stand-in (only ``has_detections`` is read)."""

    def __init__(self, has_detections: bool) -> None:
        self.has_detections = has_detections

    def to_context_string(self) -> str:  # pragma: no cover - never reached here
        return "detailed depth context"


# ---------------------------------------------------------------------------
# format_confidence_quality_summary — empty guard, confidence-key gate,
# tier counting, tier table, MARGINAL class listing, guidance tail
# ---------------------------------------------------------------------------
def test_summary_empty_input_returns_empty_string():
    # kills _format_confidence_quality_summary__mutmut_2
    # (`return ""` -> `return "XXXX"` on the `if not detections` guard). The
    # sibling `if not detections:` -> `if detections:` flip (_1) is NOT killed
    # here — both return "" for an empty list — it dies in the all-tiers test.
    assert format_confidence_quality_summary([]) == ""


def test_summary_zero_and_missing_confidence_produce_no_report():
    # kills the whole `.get("confidence")` gate family: _9 (`conf = None`),
    # _10 (`det.get(None)`), _11 (`"XXconfidenceXX"`), _12 (`"CONFIDENCE"`) —
    # all four drop the key lookup, so total stays 0 and the report vanishes;
    # _13 (`is None and` -> conf 0.0 falls THROUGH into MARGINAL, so a report
    # is rendered instead of ""), _14 (`is not None or` -> conf None reaches
    # `conf <= 0` -> TypeError), _15 (`< 0` -> conf 0.0 becomes MARGINAL),
    # _16 (`<= 1` -> every legal confidence is skipped); _23 (`total = None`,
    # so `total == 0` never fires and a header-only report is rendered), _24
    # (`sum(None)` -> TypeError) and _26 (`total == 1` -> the total==0 guard
    # never fires for these two detections).
    assert format_confidence_quality_summary([{"confidence": 0.0, "class_name": "car"}]) == ""
    assert format_confidence_quality_summary([{"class_name": "ghost"}]) == ""
    assert format_confidence_quality_summary([{"confidence": -0.5, "class_name": "cat"}]) == ""


def test_summary_single_excellent_detection_is_not_early_returned():
    # kills _format_confidence_quality_summary__mutmut_26 (`if total == 1:` ->
    # the single-detection report would early-return "") and anchors the header
    # (_41/_42/_43), EXCELLENT label/range (_28/_29/_30), " - trust fully"
    # suffix (_52/_53/_54), blank line (_56/_57), guidance (_58/_59/_60/_61)
    # and the "\n".join (_62/_63) contracts at the smallest possible render.
    result = format_confidence_quality_summary([{"confidence": 0.95, "class_name": "person"}])

    assert result == "\n".join(
        [
            "## Detection Confidence Quality",
            "- 1 detection(s) at EXCELLENT confidence (>=0.90) - trust fully",
            "",
            GUIDANCE,
        ]
    )


def test_summary_all_four_tiers_exact_render():
    # kills _1 (`if detections:` -> the whole report early-returns ""),
    # _4/_5/_6/_7 (seeding a tier counter at 1 inflates 2->3 / 1->2 in every
    # tier line), _17 (`tier = None` -> KeyError on counts[None]), _18
    # (`_compute_confidence_quality(None)` -> TypeError), _19 (`counts[tier]
    # = 1` collapses the two EXCELLENT detections to 1), _20 (`-= 1` renders
    # "- -2 detection(s)"), _21 (`+= 2` inflates EXCELLENT to 4), _22
    # (`tier != MARGINAL` moves person/car/dog/chair into the MARGINAL class
    # list), _25 (`total != 0` -> ""), _28.._39 (every tier label/range swap),
    # _40 (`lines = None` -> append on None), _44 (`count = None` renders
    # "- None detection(s)"), _45 (`count != 0` skips every populated tier),
    # _46 (`count == 1` skips the GOOD/MODERATE/MARGINAL singles), _48
    # (`= None` unpack TypeError), _51 (`tier not in (EXCELLENT, GOOD)` drops
    # both " - trust fully" suffixes), _52.._54, _55 (`append(None)`),
    # _56/_57 (blank-line swaps), _58.._61 (guidance swaps) and _62/_63
    # (join swaps).
    detections = [
        {"confidence": 0.95, "class_name": "person"},
        {"confidence": 0.91, "class_name": "car"},
        {"confidence": 0.82, "class_name": "dog"},
        {"confidence": 0.65, "class_name": "chair"},
        {"confidence": 0.45, "class_name": "cat"},
    ]
    result = format_confidence_quality_summary(detections)

    assert result == "\n".join(
        [
            "## Detection Confidence Quality",
            "- 2 detection(s) at EXCELLENT confidence (>=0.90) - trust fully",
            "- 1 detection(s) at GOOD confidence (0.75-0.89) - trust fully",
            "- 1 detection(s) at MODERATE confidence (0.60-0.74) - verify with other signals",
            "- 1 detection(s) at MARGINAL confidence (<0.60) - treat with caution",
            "  MARGINAL detections: cat",
            "",
            GUIDANCE,
        ]
    )


def test_summary_leading_empty_tiers_still_render_later_tiers():
    # EXCELLENT and GOOD are EMPTY here and come FIRST in the render order, so
    # this is the input that kills _47 (`continue` -> `break`: the first zero
    # count abandons the loop and the MODERATE/MARGINAL lines never render) and
    # _3 (`counts = None` -> TypeError in the counting loop). It re-kills the
    # tier-seed mutants _4/_5 (a seeded EXCELLENT/GOOD counter PRINTS the two
    # tiers this fixture must not print) and _27 (`tier_labels = None` ->
    # TypeError on the label lookup). It also proves the `object_type` fallback
    # of the MARGINAL label (a wrong/None fallback key would print "unknown"
    # instead of "vehicle").
    detections = [
        {"confidence": 0.65, "class_name": "chair"},
        {"confidence": 0.55, "object_type": "vehicle"},
        {"confidence": 0.45, "class_name": "cat"},
    ]
    result = format_confidence_quality_summary(detections)

    assert result == "\n".join(
        [
            "## Detection Confidence Quality",
            "- 1 detection(s) at MODERATE confidence (0.60-0.74) - verify with other signals",
            "- 2 detection(s) at MARGINAL confidence (<0.60) - treat with caution",
            "  MARGINAL detections: vehicle, cat",
            "",
            GUIDANCE,
        ]
    )


def test_summary_two_marginal_classes_join_with_comma_space():
    # the MARGINAL listing join needs >=2 members to make ", " observable: kills
    # _format_confidence_quality_summary__mutmut_8 (`marginal_classes = None` ->
    # TypeError on .append) and re-kills _22 (`!= MARGINAL` empties the list so
    # the whole "  MARGINAL detections:" line disappears).
    detections = [
        {"confidence": 0.30, "class_name": "cat"},
        {"confidence": 0.20, "object_type": "dog"},
    ]
    result = format_confidence_quality_summary(detections)

    assert result == "\n".join(
        [
            "## Detection Confidence Quality",
            "- 2 detection(s) at MARGINAL confidence (<0.60) - treat with caution",
            "  MARGINAL detections: cat, dog",
            "",
            GUIDANCE,
        ]
    )


# ---------------------------------------------------------------------------
# _compute_confidence_quality — inclusive tier boundaries
# ---------------------------------------------------------------------------
def test_compute_confidence_quality_boundaries_are_inclusive():
    # kills _compute_confidence_quality__mutmut_1 (`>= 0.90` -> `> 0.90` puts
    # exactly 0.90 in GOOD), _3 (`>= 0.75` -> `> 0.75` puts 0.75 in MODERATE),
    # _5 (`>= 0.60` -> `> 0.60` puts 0.60 in MARGINAL) and _6 (`>= 0.60` ->
    # `>= 1.60` sends every 0.60-0.74 value to MARGINAL). The 0.899/0.749/0.599
    # anchors keep the test from passing on a shifted-everything tier map.
    assert _compute_confidence_quality(0.95) is _ConfidenceQuality.EXCELLENT
    assert _compute_confidence_quality(0.90) is _ConfidenceQuality.EXCELLENT
    assert _compute_confidence_quality(0.899) is _ConfidenceQuality.GOOD
    assert _compute_confidence_quality(0.82) is _ConfidenceQuality.GOOD
    assert _compute_confidence_quality(0.75) is _ConfidenceQuality.GOOD
    assert _compute_confidence_quality(0.749) is _ConfidenceQuality.MODERATE
    assert _compute_confidence_quality(0.65) is _ConfidenceQuality.MODERATE
    assert _compute_confidence_quality(0.60) is _ConfidenceQuality.MODERATE
    assert _compute_confidence_quality(0.599) is _ConfidenceQuality.MARGINAL
    assert _compute_confidence_quality(0.45) is _ConfidenceQuality.MARGINAL


# ---------------------------------------------------------------------------
# format_detections_with_quality — header, per-detection render, quality summary
# ---------------------------------------------------------------------------
def test_detections_with_quality_mixed_fixture_exact_render():
    # one EXCELLENT centred detection, one MARGINAL detection AT the frame edge
    # (so both summary lists are non-empty) and a second MARGINAL one (so the
    # ", ".join of the marginal class list is observable). Kills
    # _format_detections_with_quality__mutmut_11 (header XX-wrap), _13 (the
    # blank line after the header -> "XXXX"), _20 (`boundary_detections = None`
    # -> TypeError on .append for the edge detection), _28 (`!= MARGINAL`
    # swaps which detections land in the marginal list: PERSON alone instead of
    # car+dog), _32 (the blank line before the summary -> "XXXX"), _34 (summary
    # header XX-wrap), _39 (`", "` join -> `"XX, XX"`) and _41
    # (`"\n".join` -> `"XX\nXX".join`).
    detections = [
        {
            "class": "person",
            "confidence": 0.95,
            "bbox": {"x": 700, "y": 400, "width": 500, "height": 500},
        },
        {
            "class": "car",
            "confidence": 0.55,
            "bbox": {"x": 0, "y": 400, "width": 300, "height": 400},
        },
        {
            "class": "dog",
            "confidence": 0.50,
            "bbox": {"x": 900, "y": 900, "width": 200, "height": 150},
        },
    ]
    result = format_detections_with_quality(detections, 1920, 1080)

    assert result == "\n".join(
        [
            "## DETECTIONS WITH QUALITY INDICATORS",
            "",
            "- PERSON: Very high confidence (95%) - highly reliable detection",
            "  Position: large object in center of frame",
            "- CAR: MARGINAL confidence (55%) - treat with caution, may be false positive",
            "  Position: medium object in left of frame (at frame edge)",
            "  WARNING: Low confidence detection - verify before acting",
            "  NOTE: Object at frame boundary - may be partially visible",
            "- DOG: MARGINAL confidence (50%) - treat with caution, may be false positive",
            "  Position: small object in bottom of frame",
            "  WARNING: Low confidence detection - verify before acting",
            "",
            "## DETECTION QUALITY SUMMARY",
            "- 2 MARGINAL confidence detection(s): car, dog - verify before acting",
            "- 1 detection(s) at frame boundary: car - may be partially visible",
        ]
    )


def test_detections_with_quality_all_reliable_omits_the_summary_block():
    # the summary block is gated on `marginal_detections or
    # boundary_detections`; this reliable/centred fixture has NEITHER, so the
    # `== MARGINAL` -> `!= MARGINAL` flip (_28) makes it GROW a summary block
    # (and the `boundary_detections = None` flip _20 crashes on .append). Also
    # pins the two "No detections in this frame." sentinel paths.
    detections = [
        {
            "class": "person",
            "confidence": 0.95,
            "bbox": {"x": 700, "y": 400, "width": 500, "height": 500},
        },
    ]
    result = format_detections_with_quality(detections, 1920, 1080)

    assert result == "\n".join(
        [
            "## DETECTIONS WITH QUALITY INDICATORS",
            "",
            "- PERSON: Very high confidence (95%) - highly reliable detection",
            "  Position: large object in center of frame",
        ]
    )
    assert format_detections_with_quality([], 1920, 1080) == "No detections in this frame."


# ---------------------------------------------------------------------------
# format_trajectory_context — "not available" sentinel
# ---------------------------------------------------------------------------
def test_trajectory_context_missing_data_sentinel_exact():
    # kills _format_trajectory_context__mutmut_2 (XX-wrap), _3 (lower-case) and
    # _4 (upper-case) — the sentinel is the only reachable text for a falsy
    # argument, and both falsy spellings (None and {}) are asserted so a
    # truthiness flip on the guard cannot hide behind the other.
    assert format_trajectory_context(None) == "Trajectory analysis: No track data available"
    assert format_trajectory_context({}) == "Trajectory analysis: No track data available"


# ---------------------------------------------------------------------------
# format_depth_context — None guard and no-detections sentinel
# ---------------------------------------------------------------------------
def test_depth_context_none_returns_empty_string():
    # kills _format_depth_context__mutmut_2 (`return ""` -> `return "XXXX"` on
    # the `depth_results is None` guard).
    assert format_depth_context(None) == ""


def test_depth_context_no_detections_sentinel_exact():
    # kills _format_depth_context__mutmut_4 (XX-wrap of the no-detections
    # sentinel); the truthy-has_detections path delegates to
    # DepthAnalysisResult.to_context_string() and owns no survivors.
    assert (
        format_depth_context(_Depth(has_detections=False))
        == "Depth analysis: No detections analyzed"
    )
    assert format_depth_context() == ""


# ---------------------------------------------------------------------------
# format_scene_context — equivalence anchor for the rfind-window mutants
# ---------------------------------------------------------------------------
def test_scene_context_truncation_contract_pins_the_equivalent_rfind_window():
    # _format_scene_context__mutmut_12/19/20 are UNREACHABLE-EQUIVALENT, not
    # covered here: `caption = caption.strip()` runs before the rfind, so no
    # reachable caption has a space at index 0 -> the sentinel 0 is impossible,
    # which (a) makes the search-start 0 / None / 1 spellings identical (an
    # out-of-range start is clamped, and index 0 can never be the match) and
    # (b) collapses `last_space > 0` onto `>= 0`. What IS pinned is the shipped
    # truncation contract those three edits all leave untouched: truncate_at =
    # max_length - 3, word-boundary cut, literal "..." suffix, the
    # len(caption) <= max_length identity path and the whitespace-only guard.
    assert format_scene_context("A residential driveway at night.") == (
        "A residential driveway at night."
    )
    assert format_scene_context(None) == ""
    assert format_scene_context("") == ""
    assert format_scene_context("   \t  ") == ""
    assert format_scene_context("x" * 10, max_length=10) == "x" * 10
    # word boundary: the last space before index 37 sits at 35 -> "alpha" x6
    assert format_scene_context("alpha " * 60, max_length=40) == (
        "alpha alpha alpha alpha alpha alpha..."
    )
    # single long word: rfind finds no space in the [0, 7) window -> hard truncate
    assert format_scene_context("abcdefghijk l", max_length=10) == "abcdefg..."
    # a leading space is stripped before the rfind, so the space that WOULD sit
    # at index 0 disappears entirely — exactly the situation the three mutants
    # claim to change, and the render below is identical for all of them.
    assert format_scene_context(" leading space caption here x", max_length=20) == (
        "leading space..."
    )
