"""provenance.json: every attempt at an event (spec §2.1; agent-driven design §2 and §4)."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Literal, Self

from pydantic import Field, model_validator

from synthbench.contract.common import ContractModel, Sha256

# Parent spec §4.2: at most 3 seeds per event, shared by the agent's triage and the verifier.
MAX_ATTEMPTS = 3

# Agent-driven design §4: the only reasons the agent may reroll an event.
TriageReason = Literal[
    "blank",
    "refusal_card",
    "wrong_scene",
    "no_person",
    "broken_anatomy",
    "not_security_camera",
    "text_overlay",
]


class OutputFile(ContractModel):
    """A file an attempt produced, relative to the event directory, with its sha256."""

    path: str
    sha256: Sha256

    @model_validator(mode="after")
    def _relative(self) -> Self:
        pure = PurePosixPath(self.path)
        if not self.path or pure.is_absolute() or ".." in pure.parts:
            raise ValueError(f"path must be relative to the event directory: {self.path!r}")
        return self


class Triage(ContractModel):
    verdict: Literal["ok", "reroll"]
    reason: TriageReason | None = None

    @model_validator(mode="after")
    def _reason_matches_verdict(self) -> Self:
        if (self.verdict == "reroll") != (self.reason is not None):
            raise ValueError("a reroll needs a reason from the list; an ok verdict has none")
        return self


class Attempt(ContractModel):
    k: int = Field(ge=1)
    seed: int = Field(ge=0)
    prompt_sha256: Sha256
    models: dict[str, Sha256] = Field(default_factory=dict)
    render: OutputFile | None = None
    render_seconds: float | None = Field(default=None, ge=0.0)
    still: OutputFile | None = None
    camera_params: str | None = None
    triage: Triage | None = None


class Provenance(ContractModel):
    schema_version: Literal[1] = 1
    event_id: str
    attempts: tuple[Attempt, ...] = ()

    @model_validator(mode="after")
    def _attempts(self) -> Self:
        ks = [attempt.k for attempt in self.attempts]
        if ks != list(range(1, len(ks) + 1)):
            raise ValueError(f"attempts must be numbered 1..n in order, got {ks}")
        if len(ks) > MAX_ATTEMPTS:
            raise ValueError(
                f"at most {MAX_ATTEMPTS} attempts per event (spec §4.2), got {len(ks)}"
            )
        return self
