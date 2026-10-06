"""Scenario-clustered statistics for S2/S3 (ISS-043).

Wilson treats every item as an independent draw. It is not: the corpus's items
share scenarios (8 to 29 per scenario), and the model's behavior correlates
inside a scenario - a lighting or framing artifact misread once tends to be
misread on every still of that scenario. A rate's honest interval therefore
resamples the SCENARIOS, not the items (cluster bootstrap), and a comparison of
two arms on the same items uses the PAIRED test (McNemar), whose exact form
needs no asymptotic assumption on the small discordant counts a 450-item corpus
actually produces.

Provenance: the sweep's analysis script (`docs/benchmarks/synthbench/sweep-2026-
10-03/analysis.py`) computed both, correctly, in throwaway form; ISS-043 is
their promotion to a tested module the report path uses, so a future report
cannot quietly drop the clustering. Stdlib only, like `s_metrics`: a fixed
bar's statistics must not rest on an undeclared transitive dependency.

Conventions shared with `s_metrics` (do not drift):
  - a refusal is a non-event in the numerator and stays in the denominator, so
    an S3 leg counts m = hit + miss + refused (see `s3_recall`);
  - an empty population is never a 0% rate: it is a full-width interval;
  - "events" here means the bar's own flagged set - false alarms for S2, floor
    hits for S3 - and the caller splits items by label before calling.
"""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Sequence
from typing import Any

# The sweep fixed 10,000 resamples and a recorded seed; the same numbers here
# keep a report reproducible and its interval as stable as its seed allows.
DEFAULT_RESAMPLES = 10_000
DEFAULT_SEED = 20261006


def _percentile(sorted_values: Sequence[float], q: float) -> float:
    """The sweep's percentile (nearest-rank on the sorted list), kept identical
    so a re-run of the sweep's figures matches."""
    return sorted_values[int(q * (len(sorted_values) - 1))]


def cluster_bootstrap(
    clusters: Sequence[tuple[int, int]],
    *,
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    """A 95% scenario-cluster bootstrap interval for one bar's rate.

    `clusters` is one (n, k) per scenario: n eligible items (the bar's
    denominator - for S3 that includes refusals), k of them the bar's event. A
    resample draws len(clusters) scenarios WITH replacement and recomputes
    sum(k)/sum(n); the interval is the 2.5/97.5 percentiles of those rates, in
    percentage points. n = 0 everywhere is full width: no data is not a 0%
    rate (same rule as `wilson_interval`).
    """
    bad = [(n, k) for n, k in clusters if not 0 <= k <= n]
    if bad:
        raise ValueError(f"cluster k out of range for n: {bad[:3]}")
    n_total = sum(n for n, _ in clusters)
    k_total = sum(k for _, k in clusters)
    out: dict[str, Any] = {
        "n": n_total,
        "k": k_total,
        "clusters": len(clusters),
        "resamples": resamples,
        "seed": seed,
    }
    if n_total == 0:
        out["point_pct"] = None
        out["ci_pct"] = [0.0, 100.0]
        return out
    out["point_pct"] = round(100 * k_total / n_total, 4)
    rng = random.Random(seed)  # noqa: S311  # seeded resampling, reproducibility not secrecy
    m = len(clusters)
    rates = []
    for _ in range(resamples):
        n = k = 0
        for _ in range(m):
            cn, ck = clusters[rng.randrange(m)]
            n += cn
            k += ck
        if n:  # a draw can land on only 0-eligible clusters; that draw is skipped
            rates.append(100 * k / n)
    rates.sort()
    if not rates:  # every draw empty although the pooled n > 0: no bound to claim
        out["ci_pct"] = [0.0, 100.0]
        return out
    out["ci_pct"] = [round(_percentile(rates, 0.025), 4), round(_percentile(rates, 0.975), 4)]
    return out


def cluster_bootstrap_diff(
    cluster_pairs: Sequence[tuple[int, int, int, int, int, int]],
    *,
    resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
) -> dict[str, Any]:
    """Paired dS2 and dS3 (arm A minus control, percentage points) with 95%
    scenario-cluster CIs - OD-26's paired test, promoted from the sweep script.

    Each tuple is one scenario's (nb, fa_a, fa_b, ni, hit_a, hit_b): benign
    items and false alarms per arm, incident-leg items (m, refusals included)
    and floor hits per arm. Resampling draws whole scenarios, so the pairing
    survives: both arms see the same clusters in every resample, which is what
    makes the interval on the DIFFERENCE narrower and more honest than intervals
    on the two rates minus each other. A leg whose denominator is empty in a
    draw is skipped for that leg (the point estimate uses the pooled rates,
    which are defined whenever the total denominators are).
    """
    bad = [
        t
        for t in cluster_pairs
        if not (0 <= t[1] <= t[0] and 0 <= t[2] <= t[0] and 0 <= t[4] <= t[3] and 0 <= t[5] <= t[3])
    ]
    if bad:
        raise ValueError(f"cluster pair k out of range for n: {bad[:3]}")
    nb = sum(t[0] for t in cluster_pairs)
    ni = sum(t[3] for t in cluster_pairs)
    fa_a = sum(t[1] for t in cluster_pairs)
    fa_b = sum(t[2] for t in cluster_pairs)
    hit_a = sum(t[4] for t in cluster_pairs)
    hit_b = sum(t[5] for t in cluster_pairs)
    out: dict[str, Any] = {
        "clusters": len(cluster_pairs),
        "benign": {"a": [fa_a, nb], "b": [fa_b, nb]},
        "incident": {"a": [hit_a, ni], "b": [hit_b, ni]},
        "resamples": resamples,
        "seed": seed,
    }
    out["point_pts"] = round(100 * (fa_a - fa_b) / nb, 4) if nb else None
    out["point3_pts"] = round(100 * (hit_a - hit_b) / ni, 4) if ni else None
    rng = random.Random(seed)  # noqa: S311  # seeded resampling, reproducibility not secrecy
    m = len(cluster_pairs)
    d2: list[float] = []
    d3: list[float] = []
    for _ in range(resamples):
        b_n = a2 = b2 = i_n = a3 = b3 = 0
        for _ in range(m):
            t = cluster_pairs[rng.randrange(m)]
            b_n += t[0]
            a2 += t[1]
            b2 += t[2]
            i_n += t[3]
            a3 += t[4]
            b3 += t[5]
        if b_n:
            d2.append(100 * (a2 - b2) / b_n)
        if i_n:
            d3.append(100 * (a3 - b3) / i_n)
    for key, samples in (("ci_pts", d2), ("ci3_pts", d3)):
        if not samples:
            out[key] = None  # this leg has no defined denominator in any draw
            continue
        samples.sort()
        out[key] = [round(_percentile(samples, 0.025), 4), round(_percentile(samples, 0.975), 4)]
    return out


def mcnemar_exact(only_a: int, only_b: int) -> float:
    """Exact two-sided McNemar p for the discordant counts (H0: each discordant
    pair is a fair coin). Items are the unit; for the SCENARIO-clustered
    version of the same comparison use `cluster_bootstrap_diff`, which is the
    form OD-26 gated on. Reported beside it, never instead of it."""
    if only_a < 0 or only_b < 0:
        raise ValueError(f"discordant counts must be >= 0, got {only_a}, {only_b}")
    n = only_a + only_b
    if n == 0:
        return 1.0
    k = min(only_a, only_b)
    tail: float = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * tail)


def noise_floor(values: Sequence[int], n: int) -> dict[str, Any]:
    """The run-to-run spread of one reading over >= 2 identical reruns: the
    noise floor a before/after comparison must clear before the word
    'improvement' is allowed. Two identical reruns measure a zero floor only
    for the axis they actually reran (same server, same build); the conditions
    line that makes a rerun mean what it says is ISS-045's, not this file's."""
    if len(values) < 2:
        raise ValueError("a noise floor needs at least two runs; one run measures no spread")
    if n <= 0:
        raise ValueError(f"denominator must be positive, got {n}")
    return {
        "runs": len(values),
        "values": list(values),
        "n": n,
        "min": min(values),
        "max": max(values),
        "range": max(values) - min(values),
        "sd_items": round(statistics.stdev(values), 4),
        "sd_points": round(100 * statistics.stdev(values) / n, 4),
    }
