"""Pins for `backend/evaluation/s_metrics.py` (Phase 2, task 2.1.2).

Wilson values are hand-computed from the closed form - matching scipy here
would pin scipy's arithmetic, not the math (and the module deliberately does
not use scipy; see its docstring). n=0 is pinned as the full-width interval:
a bare "0 %" over an empty denominator is the vacuous-green class this repo
refuses everywhere else.
"""

from __future__ import annotations

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
        # Longhand, not a transcription of the code (the previous version of
        # this test re-ran the implementation's own closed form inside the
        # test - a shared formula error passed it, which is the one thing a
        # hand-computed pin exists to prevent). At p=0 the terms collapse:
        #   centre = z²/2n = 3.841459/40      = 0.096036
        #   margin = z·sqrt((z²/4n)/n) = z²/2n = 0.096036  (exactly centre)
        #   lo = (centre-margin)/(1+z²/n) = 0 to float noise
        #   hi = 2·centre/(1+z²/n) = 0.192072/1.192073 = 0.161124
        lo, hi = wilson_interval(0, 20)
        assert lo == pytest.approx(0.0, abs=1e-9)
        assert hi == pytest.approx(0.1611, abs=1e-4)
        assert hi < 0.17, "0-of-20 must not read as 'could be anything up to 1'"

    def test_interval_stays_inside_the_unit_interval(self) -> None:
        """A 95 % interval for a proportion cannot reach 1.0000000000000002
        or -1e-17: the closed form's k=n and k=0 cases land on 1.0 and 0.0
        analytically, and float noise pushes a few n (11, 21, 285, ...) a few
        ulps outside. The report rounds to 4dp so no number CHANGES today -
        this pins the contract for any consumer that reads the raw field."""
        for k, n in [(1, 5), (5, 5), (0, 5), (120, 285), (11, 11), (0, 21), (285, 285), (0, 42)]:
            lo, hi = wilson_interval(k, n)
            assert lo <= k / n <= hi
            assert lo >= 0.0, f"k={k} n={n}: lo={lo} is below 0"
            assert hi <= 1.0, f"k={k} n={n}: hi={hi} is above 1"


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

    def test_a_present_but_empty_label_is_skipped_too(self) -> None:
        """The control freeze stores unlabeled events with `expected_label=""`
        (`control_freeze`: label or "") - the key EXISTS and holds "".
        Keying `skipped` off a missing key made those items invisible to both
        bars at once: not benign (out of S2), not incident (out of S3), and
        `skipped` stayed 0, so a run of 13 measured 9 and no field said so.
        An empty label is exactly as uncountable as a missing one."""
        results = [_row("u", "confirmed", 90), _row("gone", "confirmed", 90)]
        out = s2_false_positive_rate(results, {"u": "", "b1": "benign"})
        assert out["skipped"] == 2  # "" counts like absence
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

    def test_a_bucket_says_how_many_of_its_own_rows_are_unfailable(self) -> None:
        """The stock set's shipped S3 number was recall 0.875 over 8 items
        whose floors were ALL `low` - every scored row hits and the only
        thing that can move the number is a refusal. That is honest only if
        the reader can SEE it from the data, so each bucket carries the
        count of its own unfailable rows beside its recall (finding: the
        prose said the quiet part, no field did)."""
        results = [_row("zero", "confirmed", 0), _row("hi", "confirmed", 90)]
        out = s3_recall(results, self.ITEMS)
        assert out["all"]["unfailable"] == 1
        assert out["excluding_zero_floor"]["unfailable"] == 0

    def test_unlabeled_rows_are_counted_not_invisible(self) -> None:
        """The same null-lie as S2's empty label: a frozen event with
        `expected_label=""` is neither benign nor incident, so it leaves
        BOTH bars' denominators while no field counts it. S3's rows now
        report the count it excluded for that reason."""
        items = {
            **self.ITEMS,
            "blank": {"label": "", "floor": "low"},
        }
        results = [_row("hi", "confirmed", 90), _row("blank", "confirmed", 90)]
        out = s3_recall(results, items)
        assert out["all"]["n"] == 1  # blank never enters the bar
        assert out["unlabeled"] == 1  # ...but it IS counted somewhere


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

    def test_s5_breaks_the_refusals_down_by_error_class(self) -> None:
        """S5's bar is "0 UNPARSEABLE verdicts" (spec :77) - it is a bar on
        the model's output, not on the network. One undifferentiated
        `refusals` count reports all five VlmClientError subclasses (plus
        ConstrainedDecodingNotEnforced) identically, so 13-of-13 schema
        failures and 13-of-13 connection refusals both read as
        `refusals=13` and neither reads as the bar's own quantity.
        `replay_item` already stores the class name in the row's
        `raw_response.error`; this aggregates it. Class NAMES are aggregate
        (D10-safe), never the reply content."""
        rows = [
            {**_row("a", "verification_failed", None), "raw_response": {"error": "VlmSchemaError"}},
            {
                **_row("b", "verification_failed", None),
                "raw_response": {"error": "VlmTruncatedError"},
            },
            {
                **_row("c", "verification_failed", None),
                "raw_response": {"error": "VlmTransportError"},
            },
            _row("d", "confirmed", 60),  # scored, no error field
        ]
        out = s5_refusals(rows)
        assert out["refusals"] == 3
        assert out["by_error_class"] == {
            "VlmSchemaError": 1,
            "VlmTruncatedError": 1,
            "VlmTransportError": 1,
        }
        # The bar's quantity, named: a reply that arrived and could not be
        # parsed. A transport failure is not "unparseable" - it is no reply.
        assert out["unparseable"] == 2
        assert out["unavailable"] == 1

    def test_s5_rows_without_an_error_field_are_their_own_count(self) -> None:
        """A verification_failed row with no `raw_response.error` is the
        ladder broken at the row boundary (verdict says refused, the row
        cannot say why) - counted, never silently classed."""
        rows = [
            _row("a", "verification_failed", None),  # no raw_response at all
            {**_row("b", "verification_failed", None), "raw_response": {"error": "VlmImageError"}},
        ]
        out = s5_refusals(rows)
        assert out["refusals"] == 2
        assert out["by_error_class"] == {"VlmImageError": 1}
        assert out["unclassifiable"] == 1

    def test_empty_results_report_none_rates(self) -> None:
        assert s5_refusals([])["refusal_rate"] is None
        assert uncertain_rate([])["uncertain_rate"] is None
