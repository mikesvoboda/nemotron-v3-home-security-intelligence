"""G0.4 eval-item schema.

`AssessInput` is the frozen snapshot the VLM verifier sees; it is also Phase 1's
`vlm_assess` input contract, so its shape is pinned for owner review BEFORE any
real item is frozen (a wrong shape means re-freezing the corpus). Fields mirror
what the pipeline can record at detection time (spec §5): camera, detections,
zone state, household context, timestamp.

Privacy (D10): items may only reference media by path; the bytes never enter
this object or the repo.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AssessInput(BaseModel):
    """The self-contained snapshot a verdict is scored against (spec §5)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    camera_id: str
    detections: list[dict[str, Any]] = Field(default_factory=list)
    zones: list[str] = Field(default_factory=list)
    zone_crossing: bool = False
    household: dict[str, Any] = Field(default_factory=dict)
    timestamp: str


class EvalItem(BaseModel):
    """A frozen replay unit: the snapshot, the control label, and where the
    media lives (never the media itself)."""

    model_config = ConfigDict(frozen=True)

    item_id: str
    media_paths: list[str] = Field(default_factory=list)
    expected_label: str  # "incident" | "benign"
    expected_risk_score: int = 0
    snapshot: AssessInput
    source: str = "synthetic"
