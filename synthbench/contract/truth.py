"""truth.json: the world facts of each still (spec §2.1-§2.3). P4's packager writes it."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from synthbench.contract.common import (
    HHMM,
    Box,
    ContractModel,
    FactStatus,
    Label,
    RiskBand,
    Tier,
)


class Face(ContractModel):
    visible: bool
    height_px: int | None = Field(default=None, ge=1)


class TruthObject(ContractModel):
    id: str | None = None
    cls: str = Field(alias="class")
    bbox: Box
    zone: str | None = None
    face: Face | None = None
    posture: str | None = None
    held_by: str | None = None
    visible: bool | None = None


class Still(ContractModel):
    file: str
    t: float = Field(default=0.0, ge=0.0)
    objects: tuple[TruthObject, ...] = ()
    fact_provenance: dict[str, FactStatus] = Field(default_factory=dict)


class CastEntry(ContractModel):
    role: str
    enrolled: bool = False


class TimelineEntry(ContractModel):
    actor: str
    action: str
    t: tuple[float, float]

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        start, end = self.t
        if not 0.0 <= start <= end:
            raise ValueError(f"timeline t must be [start, end], 0 <= start <= end: {self.t}")
        return self


class Truth(ContractModel):
    schema_version: Literal[1] = 1
    event_id: str
    tier: Tier
    site: str | None = None
    camera: str
    scene_time: HHMM
    conditions: tuple[str, ...] = ()
    label: Label
    risk_band: RiskBand
    scenario: str
    cast: dict[str, CastEntry] = Field(default_factory=dict)
    stills: tuple[Still, ...]
    timeline: tuple[TimelineEntry, ...] = ()
