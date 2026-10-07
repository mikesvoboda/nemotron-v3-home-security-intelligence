"""The clip audit's files (ISS-038 acceptance, method per ISS-044 v2/OD-15).

Three row kinds, each with the shape its writer needs:

  * `ClipAuditDrawRow`  - one round's `audit-draw.jsonl`: the fixed sample, created once by
    `clip audit sample` and read by everything after it. Write-once like every corpus file:
    a page serves the manifest, never a re-draw, so an audit interrupted by a render window
    resumes the same set (a growing ready set must not reshuffle half-audited clips).
  * `ClipAuditAnswerRow` - the owner's answers, appended to
    `$SYNTHBENCH_ROOT/audits/<version>/clip-<round>.jsonl`. Latest per (event, question)
    wins, exactly like the stills audit's log. `pick` carries a choice from a list (a
    scenario id, a threat level); `answer` the y/n/u marks.
  * `ClipAuditFlagRow`  - a machine pre-screen's output (OD-15 item 1), which the owner
    hands to `clip audit sample --flagged`. The instrument never runs a screen; it only
    pins the row so a future screen and this sampler agree without a conversation.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import model_validator

from synthbench.contract.common import ContractModel

# The page's question keys. motion and threat are forced choices; scene is the blind
# scenario pick recorded as a pick; prop and conditions are y/n/u about the AUDITOR's own
# scenario pick - blind to the declaration, since after the pick that item's truth is what
# the auditor believes is there (ISS-044 v2 keeps v1's no-declared-text clause verbatim).
ClipAuditQuestion = Literal["motion", "scene", "prop", "conditions", "threat"]

# The motion choices (the page asks them in this order). The vocabulary is
# docs/synthbench/h3-prompt-notes.md's: crossing motion is what fails to render, so the
# realized class of a READY clip is the measurement's survivor-bias variable (ISS-038).
MOTION_CHOICES: tuple[str, ...] = (
    "crossing",
    "line-of-sight",
    "in-place",
    "barely-moving",
    "unclear",
)

# The blind threat-level choices (ISS-044's "threat level" read against the taxonomy's
# bands: benign scenarios carry [0,10]-[0,20] bands, suspicious [40,70], threat [60,100]).
THREAT_CHOICES: tuple[str, ...] = ("none", "record", "threat")


class ClipAuditDrawRow(ContractModel):
    """One clip in a round's audit draw. `basis` says why it is here: a census of ready
    incidents (F4: the audited subset IS the measurement corpus, so every incident clip
    must be audited), a stratified draw for the benign mirror (Freeze F2), or an OD-15
    flagged residue."""

    event_id: str
    side: Literal["incident", "benign"]
    group: str
    scenario: str
    lighting: str
    weather: str
    intended_motion: str
    basis: Literal["ready-census", "benign-stratified", "flagged"]


class ClipAuditAnswerRow(ContractModel):
    """One answer line. Exactly one of `answer` / `pick` is set - the model, not the
    writer, keeps the log from holding an answer that answers no question kind."""

    event_id: str
    question: ClipAuditQuestion
    answer: Literal["y", "n", "u"] | None = None
    pick: str | None = None
    time: str

    @model_validator(mode="after")
    def _shape_matches_question(self) -> Self:
        # Checked first: both/neither is a writer bug about the ROW, not about the
        # question, and naming the question's choice list would bury the real fault.
        if (self.answer is None) == (self.pick is None):
            raise ValueError("an answer row carries one y/n/u answer or one pick, never both")
        if self.question in ("prop", "conditions"):
            if self.answer is None or self.pick is not None:
                raise ValueError(f"{self.question} is answered y/n/u, not picked")
            return self
        # The three blind choices: a pick from their own list, never a y/n/u.
        allowed = MOTION_CHOICES if self.question == "motion" else THREAT_CHOICES
        if self.question == "scene":
            if self.pick is None or self.answer is not None:
                raise ValueError("scene is the blind scenario pick, not a y/n/u")
        elif self.pick not in allowed or self.answer is not None:
            raise ValueError(
                f"{self.question} is picked from {', '.join(allowed)}, got {self.pick!r}"
            )
        return self


class ClipAuditFlagRow(ContractModel):
    """One row of a machine pre-screen's flagged-residue file (OD-15 item 1's output
    format, pinned now so the screen lands without touching the instrument)."""

    event_id: str
    flagged_by: str
    note: str = ""
