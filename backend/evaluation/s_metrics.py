"""Wilson interval, computed in-repo, for the report F14 demands.

F14 (owner ruling): S2 and S3 are reported as "rate + n + a 95 % Wilson
interval", because on the corpus that is actually runnable today the
denominators are small (S2's labeled-benign WITH media is 5 items), and a
bare percentage off n=5 reads like a verdict when it is an indication.

Written here rather than imported from scipy on purpose: scipy resolves in
this venv but is TRANSITIVE, not a declared dependency (absent from
pyproject.toml, present in `uv tree`), and a fixed bar's report must not rest
on a package that disappears with someone else's bump. (ab_experiment_runner
already imports scipy directly - that latent break is noted in the Phase 2
plan, not fixed here: declaring a dependency is its own call.)

The interval is checked against HAND-COMPUTED values, not against scipy -
re-checking my arithmetic with the same library that did the arithmetic would
pin the library, not the math.
"""

from __future__ import annotations

import math
from typing import Any

from backend.evaluation.levels import level_at_or_above, score_to_level

VERIFICATION_FAILED = "verification_failed"

# F14's bars, repeated here ONLY as defaults the report prints beside the
# numbers. A change to S2_MAX/S3_MIN is an owner decision; nothing in here
# enforces them - the report shows the rate against the bar.
S2_MAX_PCT = 5.0
S3_MIN_PCT = 90.0


def wilson_interval(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """95 % Wilson score interval for a binomial proportion (k successes of n).

    n = 0 -> (0.0, 1.0): no data is NOT a 0 % rate and NOT a 100 % rate - it
    is a full-width interval, which is the honest thing for a report row over
    an empty denominator (F14 reports n precisely so this row is legible).
    """
    if n == 0:
        return (0.0, 1.0)
    if not 0 <= k <= n:
        raise ValueError(f"k={k} out of range for n={n}")
    p = k / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = p + z2 / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n)
    return ((centre - margin) / denom, (centre + margin) / denom)


def _scored(row: dict[str, Any]) -> bool:
    """A scored verdict: a risk_score present. A `verification_failed` row
    carries NULL by design (S5/spec §6 step 2), and a NULL is never a 0 -
    the harness that folds NULL into 0 has manufactured a benign call out of
    a refusal, which is exactly the null-lie class this repo refuses at every
    reader."""
    return row.get("risk_score") is not None


def s2_false_positive_rate(results: list[dict[str, Any]], labels: dict[str, str]) -> dict[str, Any]:
    """FP rate on LABELED-BENIGN items at level >= medium (score >= 30).

    A refusal (`verification_failed`, NULL score) is not a false positive -
    it contributed no alarming verdict - but it is counted in `refused` and
    reported beside the rate: a model that refuses everything has not passed
    S2, it has escaped it. Items whose label is missing from `labels` (or the
    reverse) are counted in the `skipped` field, never silently dropped.
    """
    denom = fp = refused = skipped = 0
    for row in results:
        item_id = row["item_id"]
        if labels.get(item_id, "") == "benign":
            denom += 1
            if not _scored(row):
                refused += 1
                continue
            if level_at_or_above(score_to_level(row["risk_score"]), "medium"):
                fp += 1
        elif item_id not in labels:
            skipped += 1
    lo, hi = wilson_interval(fp, denom)
    return {
        "fp_rate": (fp / denom) if denom else None,
        "wilson_95": (round(lo, 4), round(hi, 4)),
        "n": denom,
        "fp": fp,
        "refused": refused,
        "skipped": skipped,
        "bar_pct": S2_MAX_PCT,
    }


def s3_recall(results: list[dict[str, Any]], items: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Recall on LABELED incidents: the share whose score reaches the item's
    expected minimum level (D-P2-2: derived from `expected_risk_score`
    through the shipped banding).

    Returned THREE ways, because one number would hide the corpus fact F14
    stands on: `all` is every labeled incident (n=285 on gen-2), `excluding_zero_floor`
    drops the items whose expected floor is `low` - a floor nothing can fail
    - and is the only honest S3 until the owner relabels or supplies media
    (the 8 stock incidents, and any future zero-floor item). F14's own double
    report (with / without the 8 low incidents) is exactly this pair.
    """

    def measure(rows: list[dict[str, Any]]) -> dict[str, Any]:
        hit = miss = refused = 0
        for row in rows:
            item = items[row["item_id"]]
            floor = item["floor"]
            if not _scored(row):
                refused += 1
                continue  # a refusal is not a hit; it is reported as refused
            if level_at_or_above(score_to_level(row["risk_score"]), floor):
                hit += 1
            else:
                miss += 1
        n = hit + miss + refused
        lo, hi = wilson_interval(hit, n)
        return {
            "recall": (hit / n) if n else None,
            "wilson_95": (round(lo, 4), round(hi, 4)),
            "n": n,
            "hit": hit,
            "miss": miss,
            "refused": refused,
        }

    incident_rows = [
        row for row in results if items.get(row["item_id"], {}).get("label") == "incident"
    ]
    zero_floor = [r for r in incident_rows if items[r["item_id"]]["floor"] == "low"]
    nonzero = [r for r in incident_rows if items[r["item_id"]]["floor"] != "low"]
    out: dict[str, Any] = {
        k: measure(rows) for k, rows in (("all", incident_rows), ("excluding_zero_floor", nonzero))
    }
    out["zero_floor_items"] = len(zero_floor)
    out["bar_pct"] = S3_MIN_PCT
    return out


def uncertain_rate(results: list[dict[str, Any]]) -> dict[str, Any]:
    """The hedging rate, and the verdict mix - 1.3b deferred "does the VLM
    hedge when specialist context is present?" to these runs; this is where
    it gets measured. Refusions are reported, never folded into `uncertain`."""
    mix: dict[str, int] = {}
    for row in results:
        mix[row["verdict"]] = mix.get(row["verdict"], 0) + 1
    n = len(results)
    unc = mix.get("uncertain", 0)
    lo, hi = wilson_interval(unc, n)
    return {
        "uncertain_rate": (unc / n) if n else None,
        "wilson_95": (round(lo, 4), round(hi, 4)),
        "n": n,
        "verdict_mix": dict(sorted(mix.items())),
    }


def s5_refusals(results: list[dict[str, Any]]) -> dict[str, Any]:
    """S5's shape at the ROW level: every refusal is verdict
    `verification_failed` WITH a NULL score. A verification_failed row that
    carries a score, or a scored row's NULL, is the ladder broken at the
    harness boundary - counted and loud, never smoothed."""
    broken = [
        row["item_id"]
        for row in results
        if (row["verdict"] == VERIFICATION_FAILED) != (row.get("risk_score") is None)
    ]
    refused = sum(1 for r in results if r["verdict"] == VERIFICATION_FAILED)
    return {
        "refusals": refused,
        "n": len(results),
        "refusal_rate": (refused / len(results)) if results else None,
        "broken_rows": broken,
    }
