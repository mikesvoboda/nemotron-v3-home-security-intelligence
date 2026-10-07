"""Pins for `backend/evaluation/cluster_stats.py` (ISS-043).

The cluster bootstrap is pinned where its answer is hand-computable whatever the
seed draws - a population of identical clusters must return that cluster's rate
with zero width, whatever gets resampled - and pinned against a hand-answered
question where it is not: heterogeneous clusters must be WIDER than Wilson, the
whole point of the module. McNemar's exact p is small enough to answer by hand.
Matching a reference implementation would pin the reference, not the math (the
same reason `s_metrics` does not use scipy).
"""

from __future__ import annotations

import pytest

from backend.evaluation.cluster_stats import (
    cluster_bootstrap,
    cluster_bootstrap_diff,
    mcnemar_exact,
    noise_floor,
)

# A cluster is (n, k): n eligible items in the scenario, k of them "events"
# (a false alarm for S2, a hit for S3). The shapes below say the rate in words:
# ten items, of which the model flagged k.
HOMOGENEOUS = [(10, 5), (10, 5), (10, 5), (10, 5)]
HETEROGENEOUS = [(10, 0), (10, 0), (10, 10), (10, 10)]


class TestClusterBootstrap:
    def test_identical_clusters_return_their_rate_at_zero_width(self) -> None:
        """Every resample of identical clusters holds n=40, k=20 whatever the
        draws: 50.0%, [50.0, 50.0]. Hand-computed, seed-independent."""
        out = cluster_bootstrap(HOMOGENEOUS, resamples=2_000, seed=20261006)
        assert out["point_pct"] == pytest.approx(50.0)
        assert out["ci_pct"] == pytest.approx([50.0, 50.0])
        assert out["n"] == 40 and out["k"] == 20
        assert out["clusters"] == 4

    def test_heterogeneous_clusters_are_wider_than_wilson(self) -> None:
        """Half the clusters run at 0%, half at 100%. Wilson treats the 40
        items as independent; the bootstrap resamples the 4 scenarios, and a
        draw of two 0% clusters and two 100% ones (the likeliest shape) still
        gives 50%, while a lopsided draw moves it hard - so the interval must
        strictly contain Wilson's. This direction IS the ISS-043 claim."""
        from backend.evaluation.s_metrics import wilson_interval

        out = cluster_bootstrap(HETEROGENEOUS, resamples=4_000, seed=20261006)
        lo, hi = wilson_interval(20, 40)
        assert out["point_pct"] == pytest.approx(50.0)
        assert out["ci_pct"][0] < 100 * lo, "cluster CI must be wider than Wilson below"
        assert out["ci_pct"][1] > 100 * hi, "cluster CI must be wider than Wilson above"

    def test_the_same_seed_replays_the_same_interval(self) -> None:
        a = cluster_bootstrap(HETEROGENEOUS, resamples=1_000, seed=7)
        b = cluster_bootstrap(HETEROGENEOUS, resamples=1_000, seed=7)
        assert a == b

    def test_a_single_cluster_reports_the_point_rate_at_zero_width(self) -> None:
        """One scenario: every resample IS that scenario. Zero width is honest
        here (there is no between-cluster variance to estimate) and the caller
        reports the cluster count so the reader sees n_clusters=1."""
        out = cluster_bootstrap([(8, 2)], resamples=500, seed=1)
        assert out["point_pct"] == pytest.approx(25.0)
        assert out["ci_pct"] == pytest.approx([25.0, 25.0])

    def test_an_empty_population_is_full_width_not_a_pass(self) -> None:
        out = cluster_bootstrap([], resamples=100, seed=1)
        assert out["n"] == 0
        assert out["point_pct"] is None
        assert out["ci_pct"] == [0.0, 100.0]

    def test_every_eligible_item_counted_even_when_a_resample_sheds_a_label(self) -> None:
        """Clusters may hold items of both labels (benign and incident); the
        caller splits by label and passes one list per bar. A cluster with 0
        eligible items contributes 0/0 and must not disturb the point rate."""
        out = cluster_bootstrap([(10, 3), (0, 0), (10, 1)], resamples=100, seed=3)
        assert out["n"] == 20 and out["k"] == 4
        assert out["point_pct"] == pytest.approx(20.0)


class TestClusterBootstrapDiff:
    def test_identical_arms_are_exactly_zero(self) -> None:
        """a == b cluster by cluster: every resample's difference is 0, so the
        CI is [0.0, 0.0] whatever the draws. Hand-computed, seed-independent."""
        pairs = [(4, 2, 2, 1, 1, 1), (4, 2, 2, 1, 1, 1)]  # n,k same in both arms
        out = cluster_bootstrap_diff(pairs, resamples=500, seed=11)
        assert out["point_pts"] == pytest.approx(0.0)
        assert out["ci_pts"] == pytest.approx([0.0, 0.0])

    def test_a_constant_gap_returns_that_gap_at_zero_width(self) -> None:
        """Every cluster: arm A 2-of-4 false alarms, arm B 1-of-4. Any
        resample holds dS2 = (2-1)/4 = +25.0 points; the incident legs are
        equal so dS3 = 0.0. Both intervals collapse to their constant - and
        those constants are hand-computed from the table."""
        pairs = [(4, 2, 1, 2, 1, 1)] * 3
        out = cluster_bootstrap_diff(pairs, resamples=800, seed=5)
        assert out["point_pts"] == pytest.approx(25.0)
        assert out["ci_pts"] == pytest.approx([25.0, 25.0])
        assert out["point3_pts"] == pytest.approx(0.0)

    def test_the_pooled_point_is_the_pooled_difference(self) -> None:
        """Pooled: A's false alarms 3+1 of 4+4 = 4/8, B's 1+1 of 8 = 2/8 ->
        25.0 points, the same reading the report prints beside it."""
        pairs = [(4, 3, 1, 2, 1, 1), (4, 1, 1, 2, 1, 2)]
        out = cluster_bootstrap_diff(pairs, resamples=100, seed=9)
        assert out["point_pts"] == pytest.approx(25.0)


class TestMcnemarExact:
    def test_zero_discordants_is_not_significant(self) -> None:
        assert mcnemar_exact(0, 0) == 1.0

    def test_two_one_split_by_hand(self) -> None:
        """b=2, c=1: discordants n=3; P(one side wins >= 2 of 3 fair-coin
        draws) = (C(3,0)+C(3,1))/2^3 = 4/8; two-sided = 2*0.5 = 1.0."""
        assert mcnemar_exact(2, 1) == pytest.approx(1.0)

    def test_five_zero_by_hand(self) -> None:
        """b=5, c=0: the tails are each (1/2)^5, so p = 2/32 = 0.0625 - the
        classic 'looks decisive, is not quite' reading the paired test exists
        to state honestly."""
        assert mcnemar_exact(5, 0) == pytest.approx(0.0625)

    def test_six_zero_by_hand(self) -> None:
        """b=6, c=0: p = 2/64 = 0.03125."""
        assert mcnemar_exact(6, 0) == pytest.approx(0.03125)

    def test_negative_discordants_refuse(self) -> None:
        with pytest.raises(ValueError):
            mcnemar_exact(-1, 2)


class TestNoiseFloor:
    def test_the_measured_triple_by_hand(self) -> None:
        """The three identical reruns ISS-043 quotes (S2 false alarms 14/19/18
        of 209): range 5 items, sample sd 2.6 items, 1.3 points of a 209-item
        denominator per sd unit."""
        out = noise_floor([14, 19, 18], n=209)
        assert out["runs"] == 3
        assert out["values"] == [14, 19, 18]
        assert out["min"] == 14 and out["max"] == 19
        assert out["range"] == 5
        assert out["sd_items"] == pytest.approx(2.6, abs=0.05)
        assert out["sd_points"] == pytest.approx(1.3, abs=0.05)

    def test_fewer_than_two_runs_refuses(self) -> None:
        """A single run has no spread to report; reporting zero would call an
        unmeasured floor a measured one."""
        with pytest.raises(ValueError):
            noise_floor([17], n=209)

    def test_identical_reruns_measure_a_zero_floor(self) -> None:
        out = noise_floor([450, 450, 450], n=450)
        assert out["range"] == 0
        assert out["sd_items"] == pytest.approx(0.0)
