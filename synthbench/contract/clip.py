"""Clip events (clips design §2): a clip's spec, provenance, round record and index rows.

A clip animates one ready Tier B still with MiniMax-H3 turbo. It is its own event,
`C-<round>-NNN`: its facts are copied from the source still's spec, and the source render's
sha256 pins frame 0 (design C4-C6). Clip events live under events/C/, with their own
clip-index.jsonl and rounds/<r>/round.json, so no still command ever reads them.
"""

from __future__ import annotations

import re
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from synthbench.contract.common import (
    HHMM,
    SLUG,
    ContractModel,
    Label,
    RiskBand,
    Sha256,
    Tier,
)
from synthbench.contract.corpus import EventStatus
from synthbench.contract.provenance import MAX_ATTEMPTS, OutputFile, RenderFailure
from synthbench.contract.spec import Cell, Prop, Spec, Subject

# The source spec's fields a clip copies: its truth, the still's facts held throughout (C5).
FACT_FIELDS = frozenset(
    {"tier", "corpus_version", "cell", "scene_time", "label", "risk_band", "subjects", "props"}
)

# Clips design §3.3: the only reasons the agent may reroll a clip. All are mechanical.
ClipTriageReason = Literal[
    "camera_moved",
    "subject_lost",
    "subject_duplicated",
    "prop_lost",
    "morphing",
    "scene_cut",
]

_SOURCE_ID = re.compile(r"B-[a-z0-9][a-z0-9-]{0,39}-\d{3}")


def clip_id(round_name: str, number: int) -> str:
    """The id of a round's clip `number`, counted from 0 like B-<batch>-NNN."""
    return f"C-{round_name}-{number:03d}"


def clip_name(k: int, seed: int) -> str:
    """Attempt k's clip, relative to the event directory."""
    return f"clips/a{k}-s{seed}.mp4"


def strip_name(k: int, seed: int) -> str:
    """Attempt k's frame strip, the image the agent triages, relative to the event directory."""
    return f"strips/a{k}-s{seed}.jpg"


def source_facts(spec: Spec) -> dict[str, Any]:
    """The still's facts a clip copies, as JSON."""
    return spec.model_dump(mode="json", include=set(FACT_FIELDS))


class ClipSource(ContractModel):
    """The still a clip animates: its ready attempt and that attempt's render (frame 0)."""

    event_id: str
    k: int = Field(ge=1)
    render_sha256: Sha256

    @model_validator(mode="after")
    def _tier_b(self) -> Self:
        if not _SOURCE_ID.fullmatch(self.event_id):
            raise ValueError(
                f"a clip's source is a Tier B still, B-<batch>-NNN, got {self.event_id!r}"
            )
        return self


class ClipSettings(ContractModel):
    """What makes two rounds the same generator; the pilot gate approves one of these (C10)."""

    frames: int = Field(ge=5)
    fps: int = Field(ge=1)
    size: tuple[int, int]
    weights: Sha256
    clip_suffix_sha256: Sha256


class ClipSpec(ContractModel):
    schema_version: Literal[1] = 1
    event_id: str
    tier: Tier
    corpus_version: str
    round: str
    source: ClipSource
    cell: Cell
    scene_time: HHMM
    label: Label
    risk_band: RiskBand
    subjects: tuple[Subject, ...] = ()
    props: tuple[Prop, ...] = ()
    prompt: str | None = None
    clip_suffix: str | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        for name in (self.corpus_version, self.round):
            if not SLUG.fullmatch(name):
                raise ValueError(f"{name!r} must match {SLUG.pattern}")
        if not re.fullmatch(rf"C-{re.escape(self.round)}-\d{{3}}", self.event_id):
            raise ValueError(f"a clip event_id is C-<round>-NNN, got {self.event_id!r}")
        if (self.prompt is None) != (self.clip_suffix is None):
            raise ValueError("prompt and clip_suffix are frozen together")
        return self

    @property
    def frozen(self) -> bool:
        return self.prompt is not None

    def facts(self) -> dict[str, Any]:
        """The fields copied from the source still, as JSON: compare with source_facts()."""
        return self.model_dump(mode="json", include=set(FACT_FIELDS))

    def with_prompt(self, prompt: str, clip_suffix: str) -> ClipSpec:
        """Freeze the agent's motion and the fixed clip suffix in, validated."""
        if self.frozen:
            raise ValueError(
                f"{self.event_id} already has a frozen motion; a new motion is a new clip event"
            )
        return self.updated(prompt=prompt, clip_suffix=clip_suffix)

    @classmethod
    def from_source(
        cls, spec: Spec, *, round_name: str, number: int, k: int, render_sha256: str
    ) -> ClipSpec:
        """Clip `number` of a round, animating attempt k of the still `spec`."""
        return cls.model_validate(
            {
                "event_id": clip_id(round_name, number),
                "round": round_name,
                "source": {"event_id": spec.event_id, "k": k, "render_sha256": render_sha256},
                **source_facts(spec),
            }
        )


class ClipTriage(ContractModel):
    verdict: Literal["ok", "reroll"]
    reason: ClipTriageReason | None = None

    @model_validator(mode="after")
    def _reason_matches_verdict(self) -> Self:
        if (self.verdict == "reroll") != (self.reason is not None):
            raise ValueError("a reroll needs a reason from the list; an ok verdict has none")
        return self


class ClipAttempt(ContractModel):
    k: int = Field(ge=1)
    seed: int = Field(ge=0)
    prompt_sha256: Sha256
    models: dict[str, Sha256] = Field(default_factory=dict)
    input_sha256: Sha256 | None = None
    clip: OutputFile | None = None
    strip: OutputFile | None = None
    render_seconds: float | None = Field(default=None, ge=0.0)
    render_failures: tuple[RenderFailure, ...] = ()
    triage: ClipTriage | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        recorded = (self.input_sha256 is not None, self.clip is not None, self.strip is not None)
        if any(recorded) and not all(recorded):
            raise ValueError("an attempt records its input, clip and strip together")
        if self.triage is not None and self.clip is None:
            raise ValueError("triage needs a clip: the agent triages the strip it looked at")
        return self


class ClipProvenance(ContractModel):
    schema_version: Literal[1] = 1
    event_id: str
    attempts: tuple[ClipAttempt, ...] = ()

    @model_validator(mode="after")
    def _attempts(self) -> Self:
        ks = [attempt.k for attempt in self.attempts]
        if ks != list(range(1, len(ks) + 1)):
            raise ValueError(f"attempts must be numbered 1..n in order, got {ks}")
        if len(ks) > MAX_ATTEMPTS:
            raise ValueError(f"at most {MAX_ATTEMPTS} attempts per clip, got {len(ks)}")
        return self


class RoundRecord(ContractModel):
    """round.json: one clip sample request and its draw (clips design §2.3)."""

    schema_version: Literal[1] = 1
    name: str
    version: str
    seed: int = Field(ge=0)
    n: int = Field(ge=1, le=500)
    pilot: bool
    settings: ClipSettings
    allocation: dict[str, dict[str, int]]  # group -> lighting -> clips drawn
    event_ids: tuple[str, ...]
    source_event_ids: tuple[str, ...]
    created: str

    @model_validator(mode="after")
    def _valid(self) -> Self:
        for name in (self.name, self.version):
            if not SLUG.fullmatch(name):
                raise ValueError(f"{name!r} must match {SLUG.pattern}")
        if self.event_ids != tuple(clip_id(self.name, i) for i in range(self.n)):
            raise ValueError(f"a round lists its clips C-{self.name}-000.. in order, n={self.n}")
        if len(self.source_event_ids) != self.n or len(set(self.source_event_ids)) != self.n:
            raise ValueError("a round lists one distinct source still per clip")
        if sum(c for lights in self.allocation.values() for c in lights.values()) != self.n:
            raise ValueError("the allocation must add up to n")
        return self


class ClipIndexRow(ContractModel):
    """One clip-index.jsonl row: a clip's state change. The latest row per clip wins."""

    event_id: str
    round: str
    source: str
    scenario: str
    label: Label
    status: EventStatus
    time: str


class ClipTriageRow(ContractModel):
    """One rounds/<r>/triage.jsonl row: the agent's verdict on attempt k's strip."""

    event_id: str
    k: int = Field(ge=1)
    verdict: Literal["ok", "reroll"]
    reason: ClipTriageReason | None = None

    @model_validator(mode="after")
    def _reason_matches_verdict(self) -> Self:
        if (self.verdict == "reroll") != (self.reason is not None):
            raise ValueError("a reroll needs a reason from the list; an ok verdict has none")
        return self

    def triage(self) -> ClipTriage:
        return ClipTriage(verdict=self.verdict, reason=self.reason)


class SwitchRow(ContractModel):
    """One rounds/<r>/switches.jsonl row: `clip render` switched the renderer to H3 (§4.1)."""

    time: str
    previous: Literal["flux2", "other", "none"]
    free_gib: float = Field(ge=0.0)
    warmup_seconds: float = Field(ge=0.0)
