"""The pilot gate (clips design §5.2): status/clip-gate.json.

Only the owner's `audit --clips` writes it, on the host; the agent's sandbox mounts status/
read-only, so the agent can read the gate but never write it. One file holds the latest gate
(ruling H3-R10): a gate for other settings means there is no gate for these.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from synthbench.contract.clip import ClipSettings, RoundRecord
from synthbench.contract.common import ContractModel
from synthbench.status import read_status, status_dir

BAR = 0.8  # at least 80% of a pilot's clips pass all three audit questions (C10)
PILOT_MAX_N = 20


def meets_bar(passed_all: int, n: int) -> bool:
    """passed_all / n >= 80%, in integers so no float rounding decides a gate."""
    return 5 * passed_all >= 4 * n


class ClipGate(ContractModel):
    schema_version: Literal[1] = 1
    round: str
    n: int = Field(ge=1)
    passed_all: int = Field(ge=0)
    rate: float = Field(ge=0.0, le=1.0)
    bar: float = BAR
    passed: bool
    settings: ClipSettings
    time: AwareDatetime

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.passed_all > self.n:
            raise ValueError(f"passed_all {self.passed_all} is more than n {self.n}")
        if abs(self.rate - self.passed_all / self.n) > 1e-9:
            raise ValueError(f"rate {self.rate} is not passed_all / n")
        if self.bar != BAR or self.passed != meets_bar(self.passed_all, self.n):
            raise ValueError("passed must say whether passed_all / n meets the 80% bar")
        return self


class GateRefused(Exception):
    """A new round would get past the owner's pilot gate (exit 2)."""


def gate_file(env: Mapping[str, str] | None = None) -> Path:
    return status_dir(env) / "clip-gate.json"


def read_gate(path: Path) -> ClipGate | None:
    """The gate, or None before any pilot was rated. Read and validation errors propagate."""
    if not path.exists():
        return None
    return read_status(path, ClipGate)


def round_kind(
    settings: ClipSettings, gate: ClipGate | None, rounds: Sequence[RoundRecord]
) -> Literal["pilot", "volume"]:
    """What a new round with these settings may be (clips design §3.1)."""
    if gate is not None and gate.settings == settings:
        if gate.passed:
            return "volume"
        raise GateRefused(
            f"pilot round {gate.round} failed the owner's audit ({gate.passed_all} of {gate.n} "
            f"clips passed, the bar is {BAR:.0%}); what changes before the next pilot is the "
            "owner's decision."
        )
    for record in rounds:
        rated = gate is not None and gate.round == record.name
        if record.pilot and record.settings == settings and not rated:
            raise GateRefused(
                f"pilot round {record.name} awaits the owner's audit "
                f"(`python -m synthbench audit --clips --round {record.name}` on the host)."
            )
    return "pilot"
