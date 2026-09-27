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
    # The closed form lands on 1.0 and 0.0 analytically at k=n and k=0;
    # float noise pushes a handful of n (11, 21, 285, ...) a few ulps past
    # them, and a "proportion" above 1 is a bug no rounding fully hides.
    return (max(0.0, (centre - margin) / denom), min(1.0, (centre + margin) / denom))


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
        label = labels.get(item_id, "")
        if label == "benign":
            denom += 1
            if not _scored(row):
                refused += 1
                continue
            if level_at_or_above(score_to_level(row["risk_score"]), "medium"):
                fp += 1
        elif label != "incident":
            # Neither label, in either direction: the key missing AND the
            # key present holding "" (the control freeze's unlabeled shape,
            # `label or ""`). Keying this off `not in labels` alone let an
            # empty-label item leave BOTH bars' denominators with nothing
            # counting it - a denominator shrink that read as clean data.
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
        hit = miss = refused = unfailable = 0
        for row in rows:
            item = items[row["item_id"]]
            floor = item["floor"]
            if floor == "low":
                # Any score reaches `low`, so this row cannot move the bar;
                # a bucket that is ALL unfailable reports recall the model
                # cannot lose (the shipped stock set's 0.875 was that number
                # - see the double report). Counted beside the rate, now, so
                # the reader sees it from the data rather than the prose.
                unfailable += 1
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
            "unfailable": unfailable,
        }

    labeled = [
        r for r in results if items.get(r["item_id"], {}).get("label") in ("benign", "incident")
    ]
    unlabeled = len(results) - len(labeled)
    incident_rows = [r for r in labeled if items[r["item_id"]]["label"] == "incident"]
    nonzero = [r for r in incident_rows if items[r["item_id"]]["floor"] != "low"]
    out: dict[str, Any] = {
        k: measure(rows) for k, rows in (("all", incident_rows), ("excluding_zero_floor", nonzero))
    }
    out["zero_floor_items"] = sum(1 for r in incident_rows if items[r["item_id"]]["floor"] == "low")
    out["unlabeled"] = unlabeled  # empty/missing label: out of both bars, counted here
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
    harness boundary - counted and loud, never smoothed.

    The refusals are also broken down by the error class `replay_item`
    stored in `raw_response.error` (class NAMES only - aggregate, D10). The
    bar is "0 **unparseable** verdicts" (spec :77), a statement about the
    model's output; one undifferentiated count made 13-of-13 schema
    failures and 13-of-13 connection refusals report identically, and the
    breaker arm of the 2.1.6 smoke proved a run CAN fail all items on
    plumbing while looking exactly like a model that refused everything.
    Class keys are strings, never imports: this module stays a leaf.
    """
    broken = [
        row["item_id"]
        for row in results
        if (row["verdict"] == VERIFICATION_FAILED) != (row.get("risk_score") is None)
    ]
    refused = sum(1 for r in results if r["verdict"] == VERIFICATION_FAILED)
    by_class: dict[str, int] = {}
    unparseable = unavailable = unclassifiable = 0
    for row in results:
        if row["verdict"] != VERIFICATION_FAILED:
            continue
        error = (row.get("raw_response") or {}).get("error")
        if not error:
            unclassifiable += 1  # refused but the row cannot say why: loud by count
            continue
        by_class[error] = by_class.get(error, 0) + 1
        # "Schema" covers its VlmTruncatedError subclass by name prefix -
        # a truncated reply IS an unparseable one. Image and transport
        # failures produced no model output to call unparseable;
        # enforcement/refusal causes are their own story beside it.
        if error.startswith("VlmSchema") or error.startswith("VlmTruncated"):
            unparseable += 1
        elif error.startswith(("VlmTransport", "VlmUnavailable", "VlmImage")):
            unavailable += 1
    return {
        "refusals": refused,
        "n": len(results),
        "refusal_rate": (refused / len(results)) if results else None,
        "broken_rows": broken,
        "by_error_class": by_class,
        "unparseable": unparseable,  # the bar's own quantity
        "unavailable": unavailable,  # no reply: plumbing, not robustness
        "unclassifiable": unclassifiable,  # refused with no cause on the row
    }
