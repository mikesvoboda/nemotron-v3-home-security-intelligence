"""Score -> risk level, the one helper the evaluation harness is allowed to use.

PHASE 2 / D-P2-3. S2 is stated as "the rate at `risk_level >= medium`" and S3
as "at or above their expected minimum level", but `VlmVerdict` deliberately
carries NO level field (spec §3 - the model never emits a level;
`vlm_verdict.py:11`). So a harness that scores S2/S3 must derive the level
itself, and the moment it spells its own 30/60/85 table it has created a
second definition of the bar.

The definition of record is the frontend's `RISK_THRESHOLDS`
(`frontend/src/utils/risk.ts:80-85`) - low 0-29, medium 30-59, high 60-84,
critical 85-100 - which is also exactly the severity floor map the label
import uses (`_SEVERITY_FLOORS`, `label_import.py:96`: low 0 / medium 30 /
high 60 / critical 85). Three places, one truth; `test_levels.py` pins this
module against the TS source so the harness's S2 and the dashboard's gauge
can never disagree quietly.
"""

from __future__ import annotations

# The band edges, inclusive-upper, matching RISK_THRESHOLDS verbatim.
LOW_MAX = 29
MEDIUM_MAX = 59
HIGH_MAX = 84

# The order that makes ">= medium" arithmetic possible without string compare.
LEVEL_ORDER: tuple[str, ...] = ("low", "medium", "high", "critical")


def score_to_level(score: int) -> str:
    """The shipped banding. `VlmVerdict.risk_score` is constrained 0..100, so
    no clamping happens here on purpose: an out-of-range score is a bug and
    should read as one, not get folded into a band."""
    if score <= LOW_MAX:
        return "low"
    if score <= MEDIUM_MAX:
        return "medium"
    if score <= HIGH_MAX:
        return "high"
    return "critical"


def level_at_or_above(level: str, floor: str) -> bool:
    """`level >= floor` by rank, not lexicographically ("critical" < "high"
    as strings - the bug this helper exists to prevent)."""
    return LEVEL_ORDER.index(level) >= LEVEL_ORDER.index(floor)


def floor_for_expected_score(expected_risk_score: int) -> str:
    """S3's per-item expected MINIMUM level, derived from the frozen
    `expected_risk_score` (the label set's band midpoint) through the shipped
    banding.

    D-P2-2, and the honesty that comes with it: `EvalItem` carries no
    expected-severity field, so this is a DERIVATION, and an item expected at
    0 floors at `low` - meaning nothing a model scores can fail it. That is
    correct arithmetic, not a loophole, and it is precisely why the 13
    media-bearing stock items (whose `expected_risk_score` is 0, because a
    still frame carries no risk band) cannot carry S3 today. The report says
    so beside the number.
    """
    return score_to_level(expected_risk_score)
