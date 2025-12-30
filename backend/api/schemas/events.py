"""Pydantic schemas for events API endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EventResponse(BaseModel):
    """Schema for event response."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "camera_id": "123e4567-e89b-12d3-a456-426614174000",
                "started_at": "2025-12-23T12:00:00Z",
                "ended_at": "2025-12-23T12:02:30Z",
                "risk_score": 75,
                "risk_level": "medium",
                "summary": "Person detected near front entrance",
                "reasoning": "Person approaching entrance during daytime, no suspicious behavior",
                "reviewed": False,
                "notes": None,
                "detection_count": 5,
                "detection_ids": [1, 2, 3, 4, 5],
            }
        },
    )

    id: int = Field(..., description="Event ID")
    camera_id: str = Field(..., description="Camera UUID")
    started_at: datetime = Field(..., description="Event start timestamp")
    ended_at: datetime | None = Field(None, description="Event end timestamp")
    risk_score: int | None = Field(None, description="Risk score (0-100)")
    risk_level: str | None = Field(None, description="Risk level (low, medium, high, critical)")
    summary: str | None = Field(None, description="LLM-generated event summary")
    reasoning: str | None = Field(None, description="LLM reasoning for risk score")
    reviewed: bool = Field(False, description="Whether event has been reviewed")
    notes: str | None = Field(None, description="User notes for the event")
    detection_count: int = Field(0, description="Number of detections in this event")
    detection_ids: list[int] = Field(
        default_factory=list, description="List of detection IDs associated with this event"
    )


class EventUpdate(BaseModel):
    """Schema for updating an event (PATCH)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reviewed": True,
                "notes": "Verified - delivery person",
            }
        }
    )

    reviewed: bool | None = Field(None, description="Mark event as reviewed or not reviewed")
    notes: str | None = Field(None, description="User notes for the event")


class EventListResponse(BaseModel):
    """Schema for event list response with pagination."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "events": [
                    {
                        "id": 1,
                        "camera_id": "123e4567-e89b-12d3-a456-426614174000",
                        "started_at": "2025-12-23T12:00:00Z",
                        "ended_at": "2025-12-23T12:02:30Z",
                        "risk_score": 75,
                        "risk_level": "medium",
                        "summary": "Person detected near front entrance",
                        "reasoning": "Person approaching entrance during daytime, no suspicious behavior",
                        "reviewed": False,
                        "notes": None,
                        "detection_count": 5,
                        "detection_ids": [1, 2, 3, 4, 5],
                    }
                ],
                "count": 1,
                "limit": 50,
                "offset": 0,
            }
        }
    )

    events: list[EventResponse] = Field(..., description="List of events")
    count: int = Field(..., description="Total number of events matching filters")
    limit: int = Field(..., description="Maximum number of results returned")
    offset: int = Field(..., description="Number of results skipped")


class EventsByRiskLevel(BaseModel):
    """Schema for events count by risk level."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "critical": 2,
                "high": 5,
                "medium": 12,
                "low": 25,
            }
        }
    )

    critical: int = Field(0, description="Number of critical risk events")
    high: int = Field(0, description="Number of high risk events")
    medium: int = Field(0, description="Number of medium risk events")
    low: int = Field(0, description="Number of low risk events")


class EventsByCamera(BaseModel):
    """Schema for events count by camera."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "camera_id": "123e4567-e89b-12d3-a456-426614174000",
                "camera_name": "Front Door",
                "event_count": 15,
            }
        }
    )

    camera_id: str = Field(..., description="Camera UUID")
    camera_name: str = Field(..., description="Camera name")
    event_count: int = Field(..., description="Number of events for this camera")


class EventStatsResponse(BaseModel):
    """Schema for aggregated event statistics."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_events": 44,
                "events_by_risk_level": {
                    "critical": 2,
                    "high": 5,
                    "medium": 12,
                    "low": 25,
                },
                "events_by_camera": [
                    {
                        "camera_id": "123e4567-e89b-12d3-a456-426614174000",
                        "camera_name": "Front Door",
                        "event_count": 30,
                    },
                    {
                        "camera_id": "456e7890-e89b-12d3-a456-426614174001",
                        "camera_name": "Back Door",
                        "event_count": 14,
                    },
                ],
            }
        }
    )

    total_events: int = Field(..., description="Total number of events")
    events_by_risk_level: EventsByRiskLevel = Field(..., description="Events grouped by risk level")
    events_by_camera: list[EventsByCamera] = Field(..., description="Events grouped by camera")
