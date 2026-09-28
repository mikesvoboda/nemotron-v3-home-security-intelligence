"""Corpus records (spec §2.6; agent-driven design §2): corpus.json, batch.json, index.jsonl."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from synthbench.contract.common import SLUG, ContractModel, Label, Sha256

# Agent-driven design G7: Tier B renders at 1280x720; the camera stage makes the 1920x1080 still.
TIER_B_RENDER_SIZE = (1280, 720)

EventStatus = Literal["sampled", "prompted", "rendered", "failed"]


class CorpusManifest(ContractModel):
    """corpus.json: what a corpus version is built from. Render size is part of its identity."""

    schema_version: Literal[1] = 1
    version: str
    taxonomy_sha256: Sha256
    render_size: tuple[int, int]
    created: str

    @model_validator(mode="after")
    def _valid(self) -> Self:
        if not SLUG.fullmatch(self.version):
            raise ValueError(f"corpus version {self.version!r} must match {SLUG.pattern}")
        if min(self.render_size) < 1:
            raise ValueError(f"render_size must be positive: {self.render_size}")
        return self


class BatchRecord(ContractModel):
    """batch.json: one sample request, with everything needed to regenerate it exactly."""

    schema_version: Literal[1] = 1
    name: str
    version: str
    seed: int = Field(ge=0)
    n: int = Field(ge=1)
    only: tuple[str, ...] = ()
    prior_counts: dict[str, int] = Field(default_factory=dict)
    event_ids: tuple[str, ...]
    created: str

    @model_validator(mode="after")
    def _valid(self) -> Self:
        for name in (self.name, self.version):
            if not SLUG.fullmatch(name):
                raise ValueError(f"{name!r} must match {SLUG.pattern}")
        if len(self.event_ids) != self.n:
            raise ValueError(f"the batch lists {len(self.event_ids)} events but n={self.n}")
        return self


class IndexRow(ContractModel):
    """One index.jsonl row: an event's state change. The latest row per event wins."""

    event_id: str
    batch: str
    scenario: str
    label: Label
    status: EventStatus
    time: str
