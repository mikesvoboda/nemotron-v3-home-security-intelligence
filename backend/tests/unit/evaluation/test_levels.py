"""Pins for `backend/evaluation/levels.py` (Phase 2, D-P2-3).

The interesting test here is `test_matches_the_shipped_frontend_table`: the
harness may not own its own copy of the banding, so this parses the TS
constant out of the frontend source and asserts the SAME three edges. A
banding change that lands in `risk.ts` without landing here turns this red -
which is the point: S2's bar and the gauge a human reads must move together
or the eval verdict stops describing the product.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from backend.evaluation.levels import (
    HIGH_MAX,
    LOW_MAX,
    MEDIUM_MAX,
    floor_for_expected_score,
    level_at_or_above,
    score_to_level,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
RISK_TS = REPO_ROOT / "frontend" / "src" / "utils" / "risk.ts"


class TestScoreToLevel:
    @pytest.mark.parametrize(
        ("score", "level"),
        [
            (0, "low"),
            (29, "low"),  # inclusive upper edge
            (30, "medium"),
            (59, "medium"),
            (60, "high"),
            (84, "high"),
            (85, "critical"),
            (100, "critical"),
        ],
    )
    def test_bands_and_inclusive_edges(self, score: int, level: str) -> None:
        assert score_to_level(score) == level

    def test_matches_the_shipped_frontend_table(self) -> None:
        src = RISK_TS.read_text(encoding="utf-8")
        m = re.search(r"RISK_THRESHOLDS\s*=\s*\{(.*?)\}\s*as const", src, re.DOTALL)
        assert m, "RISK_THRESHOLDS not found in risk.ts - did the banding move?"
        edges = {
            k: int(v) for k, v in re.findall(r"(LOW_MAX|MEDIUM_MAX|HIGH_MAX):\s*(\d+)", m.group(1))
        }
        assert (
            edges["LOW_MAX"],
            edges["MEDIUM_MAX"],
            edges["HIGH_MAX"],
        ) == (LOW_MAX, MEDIUM_MAX, HIGH_MAX), (
            "the eval banding and the UI banding diverged (D-P2-3)"
        )

    def test_matches_the_import_side_floor_map(self) -> None:
        """The THIRD spelling of the same truth: label_import's severity
        floors must be the same lines the banding draws."""
        from backend.evaluation.label_import import _SEVERITY_FLOORS

        assert _SEVERITY_FLOORS["medium"] == LOW_MAX + 1
        assert _SEVERITY_FLOORS["high"] == MEDIUM_MAX + 1
        assert _SEVERITY_FLOORS["critical"] == HIGH_MAX + 1


class TestLevelOrder:
    def test_at_or_above_is_rank_not_lexicographic(self) -> None:
        # The trap this helper exists for: as STRINGS "critical" sorts BELOW
        # "high", so a naive `>=` gets this exact pair backwards. (Bound to
        # names rather than compared literal-to-literal - ruff's PLR0133 is
        # right that a bare literal pair proves nothing on its own.)
        probe, floor = "critical", "high"
        assert not probe >= floor, 'lexicographically "critical" < "high"'
        assert level_at_or_above(probe, floor) is True
        assert level_at_or_above("high", "high") is True
        assert level_at_or_above("medium", "high") is False
        assert level_at_or_above("medium", "medium") is True
        assert level_at_or_above("low", "medium") is False

    def test_s2_medium_bar_is_score_30(self) -> None:
        """S2 = rate at level >= medium on labeled-benign. The bar in score
        terms is 30, and that must be true here rather than remembered."""
        assert level_at_or_above(score_to_level(29), "medium") is False
        assert level_at_or_above(score_to_level(30), "medium") is True


class TestExpectedFloor:
    def test_band_midpoints_floor_at_their_own_band(self) -> None:
        # the corpus's real expected_risk_score values (measured on gen-2):
        assert floor_for_expected_score(20) == "low"
        assert floor_for_expected_score(47) == "medium"
        assert floor_for_expected_score(80) == "high"
        assert floor_for_expected_score(91) == "critical"

    def test_zero_expected_floors_at_low_and_is_honest_about_it(self) -> None:
        """The stock items' expected_risk_score is 0 (a still carries no
        band), so their S3 floor is `low` and nothing can fail it. The pin
        documents the vacuity instead of hiding it: S3-on-media-bearing is
        reported with that sentence beside the number."""
        assert floor_for_expected_score(0) == "low"
        assert level_at_or_above("low", floor_for_expected_score(0)) is True
        assert level_at_or_above("critical", floor_for_expected_score(0)) is True
