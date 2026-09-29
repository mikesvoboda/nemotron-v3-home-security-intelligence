"""provenance.json: every attempt at an event (spec §2.1; agent-driven design §2 and §4).

Schema version 2 (P3): each attempt records its failed render jobs and the timestamp the camera
stage drew. No version-1 file was ever written.
"""

from __future__ import annotations

import hashlib
import re
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

# A render failure's kind. Three failed `job`s fail the event; an `unreachable` renderer does
# not count, since it already stops the run for the owner.
FailureKind = Literal["job", "unreachable"]

_OVERLAY_TIME = re.compile(
    r"\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01]) ([01]\d|2[0-3]):[0-5]\d:[0-5]\d"
)


def attempt_seed(event_id: str, k: int) -> int:
    """Attempt k's seed, from the event id and k, so a rerun renders the same image (§3)."""
    return int(hashlib.sha256(f"{event_id}:{k}".encode()).hexdigest()[:8], 16)


def render_name(k: int, seed: int) -> str:
    """The raw 1280x720 render of attempt k, relative to the event directory (design §2)."""
    return f"renders/a{k}-s{seed}.png"


def still_name(k: int, seed: int) -> str:
    """The 1920x1080 camera still of attempt k, relative to the event directory (design §2)."""
    return f"stills/a{k}-s{seed}.jpg"


class OutputFile(ContractModel):
    """A file an attempt produced, relative to the event directory, with its sha256."""

    path: str
    sha256: Sha256

    @model_validator(mode="after")
    def _relative(self) -> Self:
        pure = PurePosixPath(self.path)
        if not pure.parts or pure.is_absolute() or str(pure) != self.path or ".." in pure.parts:
            raise ValueError(
                f"path must be a normalized path relative to the event directory: {self.path!r}"
            )
        return self


class Triage(ContractModel):
    verdict: Literal["ok", "reroll"]
    reason: TriageReason | None = None

    @model_validator(mode="after")
    def _reason_matches_verdict(self) -> Self:
        if (self.verdict == "reroll") != (self.reason is not None):
            raise ValueError("a reroll needs a reason from the list; an ok verdict has none")
        return self


class RenderFailure(ContractModel):
    """A render job that failed; `render` retries the same seed on its next run."""

    time: str
    error: str = Field(min_length=1, max_length=500)
    kind: FailureKind = "job"


class Attempt(ContractModel):
    k: int = Field(ge=1)
    seed: int = Field(ge=0)
    prompt_sha256: Sha256
    models: dict[str, Sha256] = Field(default_factory=dict)
    render: OutputFile | None = None
    render_seconds: float | None = Field(default=None, ge=0.0)
    render_failures: tuple[RenderFailure, ...] = ()
    still: OutputFile | None = None
    camera_params: str | None = None
    overlay_time: str | None = None
    triage: Triage | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.overlay_time is not None and not _OVERLAY_TIME.fullmatch(self.overlay_time):
            raise ValueError(f"overlay_time must be YYYY-MM-DD HH:MM:SS, got {self.overlay_time!r}")
        if self.still is not None and (
            self.render is None or self.camera_params is None or self.overlay_time is None
        ):
            raise ValueError("a still needs its render, camera_params and overlay_time")
        if self.triage is not None and self.still is None:
            raise ValueError("triage needs a still: the agent triages what it looked at")
        return self


class Provenance(ContractModel):
    schema_version: Literal[2] = 2
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
