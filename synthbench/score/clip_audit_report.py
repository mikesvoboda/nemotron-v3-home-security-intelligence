"""`clip audit bias`'s report (ISS-038's survivor-bias disclosure; OD-15's audit output).

The statistics live here, in `synthbench/score/`, because the intervals reuse the shared
`wilson_interval` - spec §7.1 lets only this package and `run/` import `backend`, so the
command reaches this module lazily and the generation-side commands never load it.

Three printings. The survivor rates are the round's ready-over-decided fraction per
intended-motion class: H3 fails crossing motion at elevated rates
(docs/synthbench/h3-prompt-notes.md - the hooded_jogger runners 0/13 ready), so a corpus
of READY clips over-weights in-place motion, and a clip number measured on it inherits the
skew; the rates are how big the correction is. The matrices are the blind audit itself -
declared scenario and band versus what the owner picked. And the disclosures print whether
or not anything has been answered, because they bind every number this round produces.

`report` is a pure function over already-read files (the caller loads them), so the
statistics are testable without a corpus or a server.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence

from backend.evaluation.s_metrics import wilson_interval

from synthbench.audit.clip_sample import MOTION_CLASSES
from synthbench.contract.clip_audit import ClipAuditDrawRow
from synthbench.taxonomy.model import Taxonomy

# The always-asked questions; prop opens only behind a scene pick whose scenario declares
# one, so whether a clip is answered depends on the owner's own pick, exactly on the page.
ALWAYS = ("motion", "scene", "conditions", "threat")

# The declared group's threat level, the taxonomy's band reading the contract documents:
# threat groups are a danger, suspicious ones worth a log, everything benign (hard
# negatives included) ordinary activity.
BAND = {"threat": "threat", "suspicious": "record"}

OTHER = "other"  # the classifier's "no keyword family matched", counted out loud, never folded in


def report(
    tax: Taxonomy,
    name: str,
    version: str,
    draw: Sequence[ClipAuditDrawRow],
    answers: Mapping[tuple[str, str], str],
    population: Mapping[str, tuple[str, str]],
    generated: str,
) -> str:
    """The report text. `answers` is the audit log replayed to its latest per
    (event, question); `population` maps every clip of the round (drawn or not) to its
    intended-motion class and outcome - `ready`, `failed`, or `open` for anything still
    mid-flight, which is counted out of the denominator and printed beside it."""
    with_props = frozenset(s.id for s in tax.scenarios if s.props)
    lines = [
        f"clip audit bias {name} (corpus {version})",
        f"Generated {generated} by `python -m synthbench clip audit bias`.",
        "",
        "## Survivor rates by intended motion",
        "",
        *_survivors(population),
        "",
        "H3 fails crossing motion at elevated rates, so a ready-only corpus over-weights",
        "in-place clips; any clip number measured on this round carries this skew with it.",
        "",
        "## Declared versus picked",
        "",
        *_matrices(draw, answers),
        "",
        "## Answers so far",
        "",
        _progress(draw, answers, with_props),
        "",
        "## Disclosures",
        "",
        "- The triplet corpus is frame-sampled from rendered clips, not scripted triplets:",
        "  it measures multi-frame input the model is handed, not a filmed event.",
        "- The clips are H3 rendered from real corpus stills, not filmed; a correct verdict",
        "  here is evidence about the model's reading of motion, not about any real scene.",
        "- No clip number from this round is publishable before the blind audit is complete",
        "  (ISS-038); this report exists to show what the audit has found so far.",
    ]
    return "\n".join(lines) + "\n"


def _survivors(population: Mapping[str, tuple[str, str]]) -> list[str]:
    """One line per intended-motion class the round holds, in the classifier's order. The
    denominator is decided clips only - ready or failed - because an open clip has survived
    nothing yet; its count rides at the end of the line instead. A class no clip fell into
    is skipped; a class with nothing decided prints a plain note, never a 0-over-0 rate."""
    ready: Counter[str] = Counter()
    decided: Counter[str] = Counter()
    open_: Counter[str] = Counter()
    for motion, outcome in population.values():
        if outcome == "ready":
            ready[motion] += 1
            decided[motion] += 1
        elif outcome == "failed":
            decided[motion] += 1
        else:
            open_[motion] += 1
    held = set(ready) | set(decided) | set(open_)
    ordered = [c for c in MOTION_CLASSES if c in held] + sorted(held - set(MOTION_CLASSES))
    lines: list[str] = []
    for cls in ordered:
        n, k = decided[cls], ready[cls]
        if n == 0:
            lines.append(f"{cls}: no decided clip ({open_[cls]} open)")
            continue
        lo, hi = wilson_interval(k, n)
        suffix = f", {open_[cls]} open" if open_[cls] else ""
        lines.append(
            f"{cls}: {k}/{n} ready ({k / n * 100:.1f} %, Wilson 95 % CI "
            f"{lo * 100:.1f}-{hi * 100:.1f} %){suffix}"
        )
    if not lines:
        return ["No clip in the round yet."]
    other = sum(1 for motion, _ in population.values() if motion == OTHER)
    if other:
        lines.append(f"classified other: {other} (no keyword family named its motion)")
    return lines


def _matrices(
    draw: Sequence[ClipAuditDrawRow], answers: Mapping[tuple[str, str], str]
) -> list[str]:
    """Scene (declared scenario -> picked scenario) and threat (declared band -> picked
    level). Only an answered clip is a cell: a clip the owner has not picked is absent, not
    a disagreement, and never counted against agreement. Only the off-diagonal pairs print
    - the agreed count is the headline, the specific confusions are the audit's whole point."""
    scene_total = sum(1 for row in draw if (row.event_id, "scene") in answers)
    threat_total = sum(1 for row in draw if (row.event_id, "threat") in answers)
    if not scene_total and not threat_total:
        return ["The matrices fill in as the owner picks; nothing answered yet."]
    scene_agreed, scene_wrong = 0, Counter[tuple[str, str]]()
    for row in draw:
        picked = answers.get((row.event_id, "scene"))
        if picked is None:
            continue
        if picked == row.scenario:
            scene_agreed += 1
        else:
            scene_wrong[(row.scenario, picked)] += 1
    threat_agreed, threat_wrong = 0, Counter[tuple[str, str]]()
    for row in draw:
        picked = answers.get((row.event_id, "threat"))
        if picked is None:
            continue
        expect = BAND.get(row.group, "none")
        if picked == expect:
            threat_agreed += 1
        else:
            threat_wrong[(expect, picked)] += 1
    return [
        _agreement("scene", scene_agreed, scene_total),
        *_pairs(scene_wrong),
        _agreement("threat", threat_agreed, threat_total),
        *_pairs(threat_wrong),
    ]


def _agreement(what: str, agreed: int, total: int) -> str:
    if total == 0:
        return f"{what} agreement: nothing picked yet."
    lo, hi = wilson_interval(agreed, total)
    return (
        f"{what} agreement {agreed}/{total} ({agreed / total * 100:.1f} %, Wilson 95 % CI "
        f"{lo * 100:.1f}-{hi * 100:.1f} %)"
    )


def _pairs(wrong: Mapping[tuple[str, str], int]) -> list[str]:
    return [f"  {from_} -> {to}: {n}" for (from_, to), n in sorted(wrong.items())]


def _progress(
    draw: Sequence[ClipAuditDrawRow],
    answers: Mapping[tuple[str, str], str],
    with_props: frozenset[str],
) -> str:
    """How far the audit has got: clips complete under the page's own rule (the four
    always-asked keys, plus a prop answer when the owner's pick opened one), and every
    prop mark the log holds. Prop marks count over the log, not the draw, so a mark on a
    clip outside a re-drawn manifest is still told."""
    marks = Counter(
        value for (event_id, key), value in answers.items() if key == "prop" and event_id
    )
    complete = sum(1 for row in draw if _complete(row, answers, with_props))
    return (
        f"answered {complete} of {len(draw)} drawn clips; prop marks: y {marks['y']}, "
        f"n {marks['n']}, u {marks['u']}"
    )


def _complete(
    row: ClipAuditDrawRow, answers: Mapping[tuple[str, str], str], with_props: frozenset[str]
) -> bool:
    if any((row.event_id, key) not in answers for key in ALWAYS):
        return False
    # The prop question belongs to the pick, not the clip: it is asked iff the owner's
    # picked scenario declares a prop, and then the clip is complete iff that prop is marked.
    picked = answers[(row.event_id, "scene")]
    return (row.event_id, "prop") in answers if picked in with_props else True
