"""Pins for `backend/evaluation/s_metrics.py` (Phase 2, task 2.1.2).

Wilson values are hand-computed from the closed form - matching scipy here
would pin scipy's arithmetic, not the math (and the module deliberately does
not use scipy; see its docstring). n=0 is pinned as the full-width interval:
a bare "0 %" over an empty denominator is the vacuous-green class this repo
refuses everywhere else.
"""

from __future__ import annotations

import math
from typing import ClassVar

import pytest

from backend.evaluation.s_metrics import (
    s2_false_positive_rate,
    s3_recall,
    s5_refusals,
    uncertain_rate,
    wilson_interval,
)


class TestWilson:
    def test_zero_events_is_full_width_not_zero(self) -> None:
        assert wilson_interval(0, 0) == (0.0, 1.0)

    def test_k_out_of_range_refuses(self) -> None:
        with pytest.raises(ValueError):
            wilson_interval(6, 5)

    def test_hand_computed_half_of_four(self) -> None:
        # k=2, n=4, by the closed form worked longhand:
        #   z=1.959964, z²=3.841459
        #   denom  = 1 + z²/n  = 1.960365
        #   centre = p + z²/2n = 0.980182
        #   margin = z*sqrt((pq + z²/4n)/n) = 1.959964*sqrt((0.25+0.240091)/4) = 0.68609
        #   lo = (0.980182-0.68609)/1.960365 = 0.1500
        #   hi = (0.980182+0.68609)/1.960365 = 0.8500
        lo, hi = wilson_interval(2, 4)
        assert lo == pytest.approx(0.1500, abs=1e-3)
        assert hi == pytest.approx(0.8500, abs=1e-3)

    def test_hand_computed_zero_of_twenty(self) -> None:
        # k=0, n=20: centre = z²/2n/(1+z²/n) = .0862; upper = z*sqrt(p(1-p)+z²/4n)/...
        z = 1.959963984540054
        n = 20
        p = 0.0
        denom = 1 + z * z / n
        centre = p + z * z / (2 * n)
        margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
        lo, hi = wilson_interval(0, n)
        assert lo == pytest.approx((centre - margin) / denom, abs=1e-9)
        assert hi == pytest.approx((centre + margin) / denom, abs=1e-9)
        # and the honest reading of the row: 0 events is still bounded below
        # by 0 and strictly below 1 - the bound is (0, 0.1611) for n=20.
        assert lo == pytest.approx(0.0, abs=1e-9)
        assert hi < 0.17, "0-of-20 must not read as 'could be anything up to 1'"

    def test_interval_brackets_point_estimate(self) -> None:
        for k, n in [(1, 5), (5, 5), (0, 5), (120, 285)]:
            lo, hi = wilson_interval(k, n)
            assert lo <= k / n <= hi


def _row(item_id: str, verdict: str, score: int | None) -> dict:
    return {"item_id": item_id, "verdict": verdict, "risk_score": score}


class TestS2:
    def test_medium_bar_is_30_and_only_scored_rows_count(self) -> None:
        labels = {"b1": "benign", "b2": "benign", "b3": "benign", "b4": "benign", "b5": "benign"}
        results = [
            _row("b1", "confirmed", 30),  # exactly medium -> FP
            _row("b2", "confirmed", 29),  # low -> clean
            _row("b3", "verification_failed", None),  # refusal, not an FP
            _row("b4", "rejected", 0),
            _row("b5", "confirmed", 55),  # medium -> FP
        ]
        out = s2_false_positive_rate(results, labels)
        assert out["fp"] == 2
        assert out["n"] == 5
        assert out["fp_rate"] == pytest.approx(0.4)
        assert out["refused"] == 1
        # hand-check: Wilson(2,5) ~ (0.1176, 0.7693)
        assert out["wilson_95"][0] == pytest.approx(0.1176, abs=1e-3)
        assert out["wilson_95"][1] == pytest.approx(0.7693, abs=1e-3)

    def test_refusals_never_fold_into_benign_quietly(self) -> None:
        """The count is reported, not smoothed: five refusals produce an
        fp_rate of 0 AND refused=5 - the reader must see the model escaped
        the bar rather than passed it."""
        labels = {f"b{i}": "benign" for i in range(5)}
        results = [_row(f"b{i}", "verification_failed", None) for i in range(5)]
        out = s2_false_positive_rate(results, labels)
        assert out["fp_rate"] == 0.0
        assert out["refused"] == 5
        assert out["n"] == 5  # refusals stay IN the denominator

    def test_empty_denominator_is_none_not_zero(self) -> None:
        out = s2_false_positive_rate([], {})
        assert out["fp_rate"] is None
        assert out["n"] == 0
        assert out["wilson_95"] == (0.0, 1.0)

    def test_unlabeled_result_is_counted_skipped_not_dropped_silently(self) -> None:
        out = s2_false_positive_rate([_row("x", "confirmed", 90)], {"b1": "benign"})
        assert out["skipped"] == 1
        assert out["n"] == 0

    def test_incidents_never_enter_s2(self) -> None:
        labels = {"i1": "incident", "b1": "benign"}
        out = s2_false_positive_rate(
            [_row("i1", "confirmed", 95), _row("b1", "confirmed", 10)], labels
        )
        assert out["n"] == 1
        assert out["fp"] == 0


class TestS3:
    ITEMS: ClassVar[dict[str, dict[str, str]]] = {
        # high-floor incident (expected 80), zero-floor stock incident (0),
        # medium-floor incident (47), a benign (never in S3)
        "hi": {"label": "incident", "floor": "high"},
        "zero": {"label": "incident", "floor": "low"},
        "med": {"label": "incident", "floor": "medium"},
        "b": {"label": "benign", "floor": "low"},
    }

    def test_score_must_reach_the_items_own_floor(self) -> None:
        results = [
            _row("hi", "confirmed", 84),  # high -> hit
            _row("med", "confirmed", 59),  # medium floor, medium score -> hit
            _row("zero", "confirmed", 0),  # vacuous by D-P2-2: floors at low
            _row("b", "confirmed", 0),  # not an incident
        ]
        out = s3_recall(results, self.ITEMS)
        assert out["all"]["n"] == 3
        assert out["all"]["hit"] == 3
        assert out["excluding_zero_floor"]["n"] == 2
        assert out["excluding_zero_floor"]["hit"] == 2
        assert out["zero_floor_items"] == 1

    def test_below_floor_is_a_miss(self) -> None:
        results = [_row("hi", "confirmed", 60 - 1)]  # high floor, medium score
        out = s3_recall(results, self.ITEMS)
        assert out["all"]["hit"] == 0
        assert out["all"]["miss"] == 1
        assert out["all"]["n"] == 1

    def test_refusal_is_never_a_hit_and_stays_in_n(self) -> None:
        results = [_row("hi", "verification_failed", None)]
        out = s3_recall(results, self.ITEMS)
        assert out["all"]["hit"] == 0
        assert out["all"]["refused"] == 1
        assert out["all"]["n"] == 1
        assert out["all"]["recall"] == 0.0

    def test_the_double_report_is_the_pair_f14_demands(self) -> None:
        results = [
            _row("hi", "confirmed", 90),
            _row("zero", "confirmed", 0),
        ]
        out = s3_recall(results, self.ITEMS)
        assert out["all"]["n"] == 2
        assert out["excluding_zero_floor"]["n"] == 1


class TestUncertainAndS5:
    def test_verdict_mix_counts_every_verdict_and_refused_is_its_own_line(self) -> None:
        results = [
            _row("a", "confirmed", 90),
            _row("b", "uncertain", 45),
            _row("c", "verification_failed", None),
            _row("d", "rejected", 5),
        ]
        out = uncertain_rate(results)
        assert out["verdict_mix"] == {
            "confirmed": 1,
            "rejected": 1,
            "uncertain": 1,
            "verification_failed": 1,
        }
        assert out["n"] == 4
        assert out["uncertain_rate"] == pytest.approx(0.25)

    def test_s5_shape_a_refusal_row_with_a_score_is_loud(self) -> None:
        good = _row("a", "verification_failed", None)
        broken_scored = _row("b", "verification_failed", 50)  # the null-lie
        broken_null = _row("c", "confirmed", None)  # a scored NULL
        out = s5_refusals([good, broken_scored, broken_null])
        assert out["refusals"] == 2  # by verdict, the shipped shape
        assert sorted(out["broken_rows"]) == ["b", "c"]
        assert out["refusal_rate"] == pytest.approx(2 / 3)

    def test_empty_results_report_none_rates(self) -> None:
        assert s5_refusals([])["refusal_rate"] is None
        assert uncertain_rate([])["uncertain_rate"] is None
