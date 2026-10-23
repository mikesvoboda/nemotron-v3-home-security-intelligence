"""Pydantic schemas for the Arming API (`/api/arming`, B4.7 / 4n-arming.md)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NextScheduledTransitionResponse(BaseModel):
    """Next scheduled mode transition."""

    at: datetime = Field(..., description="UTC timestamp of the next scheduled transition")
    mode: str = Field(..., description="Target arming mode (home, away, night, disarmed)")


class ArmingStatusResponse(BaseModel):
    """Response for GET /api/arming."""

    mode: str = Field(
        ..., description="Current household arming mode (home, away, night, disarmed)"
    )
    since: datetime = Field(..., description="UTC timestamp when the current mode was set")
    source_kind: str = Field(..., description="Source kind (user, webhook, mqtt, schedule, system)")
    source_name: str = Field(..., description="Source identifier")
    by_whom: str = Field(..., description="Who or what set the current mode")
    next_scheduled: NextScheduledTransitionResponse | None = Field(
        default=None, description="Next scheduled transition if a schedule is configured"
    )


class ArmingSetModeRequest(BaseModel):
    """Request for PUT /api/arming/mode."""

    mode: str = Field(..., description="Target arming mode: home, away, night, or disarmed")


class ArmingModeCamerasResponse(BaseModel):
    """Response for GET/PUT /api/arming/modes/{mode}/cameras."""

    mode: str = Field(..., description="Arming mode")
    excluded_camera_ids: list[str] = Field(
        default_factory=list,
        description="Camera IDs excluded from alerting in this mode",
    )


class ArmingModeCamerasUpdateRequest(BaseModel):
    """Request for PUT /api/arming/modes/{mode}/cameras."""

    excluded_camera_ids: list[str] = Field(
        default_factory=list,
        description="Camera IDs to leave out of alerting in this mode",
    )


class ArmingScheduleEntrySchema(BaseModel):
    """A single weekly schedule entry."""

    id: int | None = Field(default=None, description="Schedule entry ID")
    days: list[str] = Field(..., min_length=1, description="Weekdays (monday..sunday)")
    time: str = Field(..., description="Local time in HH:MM (24-hour)")
    mode: str = Field(..., description="Target arming mode: home, away, night, or disarmed")


class ArmingScheduleResponse(BaseModel):
    """Response for GET/PUT /api/arming/schedule."""

    items: list[ArmingScheduleEntrySchema] = Field(default_factory=list)


class ArmingScheduleUpdateRequest(BaseModel):
    """Request for PUT /api/arming/schedule."""

    items: list[ArmingScheduleEntrySchema] = Field(default_factory=list)


class ArmingChangeItemResponse(BaseModel):
    """A single entry in the arming change history."""

    id: int
    kind: str
    from_value: Any | None = None
    to_value: Any
    mode_after: str
    exclusions_after: dict[str, list[str]] = Field(default_factory=dict)
    source_kind: str
    source_name: str
    changed_at: datetime


class ArmingChangesListResponse(BaseModel):
    """Response for GET /api/arming/changes."""

    items: list[ArmingChangeItemResponse] = Field(default_factory=list)


class ArmingEventDecisionResponse(BaseModel):
    """Response for GET /api/arming/events/{event_id}/decision."""

    event_id: int
    notify: bool
    decided_by: str
