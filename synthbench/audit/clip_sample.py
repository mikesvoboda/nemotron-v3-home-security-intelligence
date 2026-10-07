"""The clip audit's sample and its blind questions (ISS-038 acceptance, method per OD-15).

The incident half of the draw is a **census of ready incidents**, not a sample: the
pre-registered measurement runs on the audited clips alone (prereg Freeze F4), so every
incident clip that could enter the corpus must be audited, and a census stays correct as a
render window grows the ready set - a new ready clip joins the draw; nothing already
audited moves. The benign half is a seeded stratified draw (Freeze F2) sized to mirror the
incident half, over (group x intended motion) strata. Flagged residue - the output of an
OD-15 machine pre-screen, whenever the owner authorizes one - is unioned in.

"Blind" (ISS-044 v2, v1's clause unamended) binds the questions: the auditor sees only the
clip and picks the scenario and threat level from lists; nothing declared is shown. The
prop question is therefore asked AFTER the scenario pick, of the auditor's own pick - after
the pick, the declared truth is not the item's truth anyway (a mislabelled clip is exactly
what the audit finds). The page never reads a clip's prompt or source still: frame 0 of the
clip IS the still, and the motion prompt names the scenario's props.

The intended-motion classifier is the survivor-bias stratifier (ISS-038): H3 fails crossing
motion at elevated rates (docs/synthbench/h3-prompt-notes.md: the hooded_jogger runners 0/13
ready), so an audit stratified only on scenario and lighting would silently over-weight
in-place clips. Keywords are that note's own counted wordings, ordered crossing >
line-of-sight > in-place (a note counts "crosses... toward the house" as crossing).
"""

from __future__ import annotations

import random
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from synthbench.audit.sample import allocate
from synthbench.contract.clip_audit import (
    MOTION_CHOICES,
    THREAT_CHOICES,
    ClipAuditDrawRow,
    ClipAuditFlagRow,
)
from synthbench.taxonomy.model import ScenarioDef, Taxonomy

SEED = 20261007

# Ordered, most-specific first; whole words, so "past" never matches "pastime" and an
# object called "the past" is a clip nobody wrote.
_CLASSIFIERS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "crossing",
        re.compile(
            r"\bacross\b|\bcross(?:es|ed|ing)?\b|\bpast\b"
            r"|\balong the \w*(?:pav|path|walk|sidewalk|street|drivew)"
            r"|\bfrom (?:the )?(?:left|right)\b|\b(?:left|right) to (?:right|left)\b"
            r"|\bexits? (?:the )?(?:frame|shot)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "line-of-sight",
        re.compile(
            r"\btoward(?:s)? (?:the )?(?:house|door|camera|porch|drive|patio|pool|steps?"
            r"|window|gate|car)\b|\bup the drive\b|\bapproach(?:es|ing|ed)?\b|\bcloser\b"
            r"|\bwalks? (?:up|to)\b|\bsteps? (?:up|to)\b|\bretreat(?:s|ing|ed)?\b"
            r"|\bbacks? away\b|\bfurther into\b",
            re.IGNORECASE,
        ),
    ),
    (
        "in-place",
        re.compile(
            r"\bin place\b|\bstay(?:s|s)?\b|\bstays?\b|\bremain(?:s|ed|ing)?\b"
            r"|\bcontinu(?:es|ed|ing)?\b|\bkeeps?\b|\bworks?\b|\bwaits?\b|\bsweeps?\b"
            r"|\brak(?:es|ing)?\b|\bmow(?:s|ing|ed)?\b|\bstands?\b|\bpauses?\b|\bpause[sd]?\b"
            r"|\bstops?\b|\bcircles?\b|\bshifts? (?:his|her|its|their) weight\b"
            r"|\bturn(?:s|s)? (?:his|her|its|their) head\b",
            re.IGNORECASE,
        ),
    ),
)

MOTION_CLASSES: tuple[str, ...] = ("crossing", "line-of-sight", "in-place", "other")

# One row's reason for being in the draw, exactly the contract's closed set - so the
# literal below the row() call site is checked, not just cast.
DrawBasis = Literal["ready-census", "benign-stratified", "flagged"]


def classify_intended_motion(motion: str) -> str:
    """The intended-motion class of one frozen motion text, by keyword family.

    'other' is an honest third answer for a motion in no family (the mounted round's 459
    classify exhaustively into the three real classes - computed 2026-10-07, outside git);
    the bias disclosure prints its count instead of hiding it in a named class.
    """
    for name, pattern in _CLASSIFIERS:
        if pattern.search(motion):
            return name
    return "other"


@dataclass(frozen=True)
class ClipQuestion:
    """One audit question. `choices` empty means the page takes a y/n/u mark; otherwise the
    auditor picks one of `choices` and the pick itself is the answer."""

    key: str
    text: str
    choices: tuple[str, ...] = ()


def motion_question() -> ClipQuestion:
    return ClipQuestion(
        key="motion",
        text=(
            "What does the subject do over the clip? Cross the frame, move toward or away "
            "along the camera's line of sight, work or move in place, or barely move?"
        ),
        choices=MOTION_CHOICES,
    )


def scene_choices(tax: Taxonomy) -> tuple[ScenarioDef, ...]:
    """The blind scenario list: the whole taxonomy, one entry per scenario, in id order -
    the same list for every clip, so nothing about the clip is in the list."""
    return tuple(sorted(tax.scenarios, key=lambda scenario: scenario.id))


def scene_question() -> ClipQuestion:
    return ClipQuestion(
        key="scene",
        text=(
            "Which scenario is this clip showing? Pick from the taxonomy list; there is no "
            "declared answer on screen."
        ),
    )  # choices arrive per-request from scene_choices, not from this static text


def prop_question(picked: ScenarioDef) -> ClipQuestion | None:
    """The prop question of the AUDITOR'S pick (None when that scenario declares no props):
    asked after the scene pick so the question never names a declared prop before the pick,
    and asks about the scenario the auditor believes is there - their pick is this item's
    truth, which is the point of a blind audit."""
    names = sorted({term for prop in picked.props for term in prop.one_of})
    if not names:
        return None
    things = " and the ".join(name.replace("_", " ") for name in names)
    return ClipQuestion(
        key="prop",
        text=f"Is the {things} visible?",
    )


def threat_question() -> ClipQuestion:
    return ClipQuestion(
        key="threat",
        text=(
            "What threat level does the clip show? none (ordinary activity), record (an "
            "event worth a log, not a danger), threat (a danger to people or property)?"
        ),
        choices=THREAT_CHOICES,
    )


def conditions_question(lighting: str, weather: str) -> ClipQuestion:
    """The one declared fact the page DOES show: lighting and weather carry through from
    the source still's cell unchanged (clips design C5), so a wrong reading here is a clip
    defect, not a label leak - and a clip that contradicts them has scene trouble anyway."""
    return ClipQuestion(
        key="conditions",
        text=f"{lighting.replace('_', ' ')} light and {weather.replace('_', ' ')} weather?",
    )


def audit_draw(
    specs: Sequence[object],
    motions: Mapping[str, str],
    status: Mapping[str, str],
    *,
    round_name: str,
    benign_target: int | None = None,
    flagged: Sequence[ClipAuditFlagRow] = (),
    seed: int = SEED,
) -> list[ClipAuditDrawRow]:
    """The round's audit draw: ready-incident census, then the benign mirror sized to it,
    then flagged residue not already listed. Deterministic; ordered incident, benign,
    flagged, each side by event id, so the page order survives a re-run.

    `specs` are the round's ClipSpecs (read through their attributes: event_id, label,
    cell.group/.scenario/.lighting); `status` is the latest clip-index status per event
    id; `motions` maps event id to the frozen motion text. The taxonomy is deliberately
    absent: every fact a draw row carries is already on the clip's spec.
    """
    facts = {
        spec.event_id: spec  # type: ignore[attr-defined]
        for spec in specs
    }

    def row(event_id: str, basis: DrawBasis) -> ClipAuditDrawRow:
        spec = facts[event_id]
        return ClipAuditDrawRow(
            event_id=event_id,
            side="incident" if spec.label == "incident" else "benign",  # type: ignore[attr-defined]
            group=str(spec.cell.group),  # type: ignore[attr-defined]
            scenario=str(spec.cell.scenario),  # type: ignore[attr-defined]
            lighting=str(spec.cell.lighting),  # type: ignore[attr-defined]
            weather=str(spec.cell.weather),  # type: ignore[attr-defined]
            intended_motion=classify_intended_motion(motions[event_id]),
            basis=basis,
        )

    ready = [eid for eid in sorted(facts) if status.get(eid) == "ready"]
    incidents = sorted(
        eid
        for eid in ready
        if facts[eid].label == "incident"  # type: ignore[attr-defined]
    )
    drawn: list[ClipAuditDrawRow] = [row(eid, "ready-census") for eid in incidents]

    # Freeze F2's mirror: as many benign clips as incidents, one stratum at a time.
    # Strata are (group, intended motion) so both the group axis (benign vs hard_negative)
    # and the motion axis the bias lives on get spread; a stratum never takes two slots
    # while another starves while k allows.
    target = len(incidents) if benign_target is None else benign_target
    by_stratum: dict[tuple[str, str], list[str]] = defaultdict(list)
    for eid in ready:
        if facts[eid].label != "benign":  # type: ignore[attr-defined]
            continue  # ambiguous clips are not S2 material and not incidents
        spec = facts[eid]
        by_stratum[
            (str(spec.cell.group), classify_intended_motion(motions[eid]))  # type: ignore[attr-defined]
        ].append(eid)
    counts = {f"{group}\x1f{motion}": len(ids) for (group, motion), ids in by_stratum.items()}
    alloc = allocate(counts, min(target, sum(counts.values())))
    rng = random.Random(f"{seed}:{round_name}")  # noqa: S311  # reproducible draw
    chosen: list[str] = []
    for stratum in sorted(alloc):
        group, motion = stratum.split("\x1f", 1)  # strata are exactly two names
        ids = sorted(by_stratum[(group, motion)])
        n = alloc[stratum]
        if n:
            chosen.extend(sorted(rng.sample(ids, n)))
    drawn.extend(row(eid, "benign-stratified") for eid in chosen)

    listed = {r.event_id for r in drawn}
    for flag in flagged:
        if flag.event_id in listed or flag.event_id not in facts:
            continue  # a flag on a censused clip adds nothing; on a foreign clip, nowhere
        drawn.append(row(flag.event_id, "flagged"))
    return drawn
