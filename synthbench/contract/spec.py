"""spec.json: an event's intent, written by the sampler (spec §2.1).

The sampler fixes every fact that becomes ground truth. The prompt and the camera suffix are
added later, together and once, before rendering (agent-driven design §3.1).
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
    ScenarioGroup,
    Tier,
)

PROMPT_FIELDS = frozenset({"prompt", "camera_suffix"})


class Cell(ContractModel):
    """The taxonomy cell the event was sampled from (spec §1.2)."""

    scenario: str
    group: ScenarioGroup
    property_type: str
    zone: str
    camera: str
    lighting: str
    weather: str
    artifacts: tuple[str, ...] = ()


class Subject(ContractModel):
    """A person, child or animal. Tier B subjects are anonymous (spec §1.1)."""

    id: str
    cls: str = Field(alias="class")
    role: str
    attributes: dict[str, str] = Field(default_factory=dict)


class Prop(ContractModel):
    """An object the image must show; `held_by` names a subject id."""

    id: str
    cls: str = Field(alias="class")
    held_by: str | None = None


class Spec(ContractModel):
    schema_version: Literal[1] = 1
    event_id: str
    tier: Tier
    corpus_version: str
    batch: str
    cell: Cell
    scene_time: HHMM
    label: Label
    risk_band: RiskBand
    subjects: tuple[Subject, ...] = ()
    props: tuple[Prop, ...] = ()
    prompt: str | None = None
    camera_suffix: str | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        for name in (self.corpus_version, self.batch):
            if not SLUG.fullmatch(name):
                raise ValueError(f"{name!r} must match {SLUG.pattern}")
        tier_b_id = rf"B-{re.escape(self.batch)}-\d{{3}}"
        if self.tier == "B" and not re.fullmatch(tier_b_id, self.event_id):
            raise ValueError(f"a Tier B event_id is B-<batch>-NNN, got {self.event_id!r}")
        if not self.event_id.startswith(f"{self.tier}-"):
            raise ValueError(f"event_id {self.event_id!r} must start with {self.tier}-")
        ids = [s.id for s in self.subjects] + [p.id for p in self.props]
        if len(ids) != len(set(ids)):
            raise ValueError(f"subject and prop ids must be unique: {ids}")
        subject_ids = {s.id for s in self.subjects}
        for prop in self.props:
            if prop.held_by is not None and prop.held_by not in subject_ids:
                raise ValueError(f"prop {prop.id} is held by unknown subject {prop.held_by!r}")
        if (self.prompt is None) != (self.camera_suffix is None):
            raise ValueError("prompt and camera_suffix are frozen together")
        return self

    @property
    def frozen(self) -> bool:
        return self.prompt is not None

    def facts(self) -> dict[str, Any]:
        """Everything the sampler fixed: the spec without its frozen prompt (design G4)."""
        return self.model_dump(mode="json", exclude=set(PROMPT_FIELDS))

    def with_prompt(self, prompt: str, camera_suffix: str) -> Spec:
        """Freeze the agent's prompt and the fixed suffix in (design §3.1), validated."""
        if self.frozen:
            raise ValueError(
                f"{self.event_id} already has a frozen prompt; a new prompt is a new event"
            )
        return self.updated(prompt=prompt, camera_suffix=camera_suffix)
