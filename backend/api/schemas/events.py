"""Pydantic schemas for events API endpoints."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class EnrichmentStatusEnum(str, Enum):
    """Status of enrichment pipeline execution for an event.

    Values:
        full: All enrichment models succeeded
        partial: Some models succeeded, some failed
        failed: All models failed (no enrichment data)
        skipped: Enrichment was not attempted
    """

    FULL = "full"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


class EnrichmentStatusResponse(BaseModel):
    """Schema for enrichment status in event responses (NEM-1672).

    Provides visibility into which enrichment models succeeded/failed
    for a given event, instead of silently degrading.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "partial",
                "successful_models": ["violence", "weather", "face"],
                "failed_models": ["clothing"],
                "errors": {"clothing": "Model not loaded"},
                "success_rate": 0.75,
            }
        }
    )

    status: EnrichmentStatusEnum = Field(
        ..., description="Overall enrichment status (full, partial, failed, skipped)"
    )
    successful_models: list[str] = Field(
        default_factory=list, description="List of enrichment models that succeeded"
    )
    failed_models: list[str] = Field(
        default_factory=list, description="List of enrichment models that failed"
    )
    errors: dict[str, str] = Field(
        default_factory=dict, description="Model name to error message mapping"
    )
    success_rate: float = Field(..., ge=0.0, le=1.0, description="Success rate (0.0 to 1.0)")


class EventResponse(BaseModel):
    """Schema for event response."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "camera_id": "front_door",
                "started_at": "2025-12-23T12:00:00Z",
                "ended_at": "2025-12-23T12:02:30Z",
                "risk_score": 75,
                "risk_level": "medium",
                "summary": "Person detected near front entrance",
                "reasoning": "Person approaching entrance during daytime, no suspicious behavior",
                "llm_prompt": "<|im_start|>system\nYou are a home security risk analyzer...",
                "reviewed": False,
                "notes": None,
                "detection_count": 5,
                "detection_ids": [1, 2, 3, 4, 5],
                "thumbnail_url": "/api/media/detections/1",
                "enrichment_status": {
                    "status": "full",
                    "successful_models": ["violence", "weather", "face", "clothing"],
                    "failed_models": [],
                    "errors": {},
                    "success_rate": 1.0,
                },
            }
        },
    )

    id: int = Field(..., description="Event ID")
    camera_id: str = Field(..., description="Normalized camera ID (e.g., 'front_door')")
    started_at: datetime = Field(..., description="Event start timestamp")
    ended_at: datetime | None = Field(None, description="Event end timestamp")
    risk_score: int | None = Field(None, description="Risk score (0-100)")
    risk_level: str | None = Field(None, description="Risk level (low, medium, high, critical)")
    summary: str | None = Field(None, description="LLM-generated event summary")
    reasoning: str | None = Field(None, description="LLM reasoning for risk score")
    llm_prompt: str | None = Field(
        None, description="Full prompt sent to Nemotron LLM (for debugging/improvement)"
    )
    reviewed: bool = Field(False, description="Whether event has been reviewed")
    notes: str | None = Field(None, description="User notes for the event")
    detection_count: int = Field(0, description="Number of detections in this event")
    detection_ids: list[int] = Field(
        default_factory=list, description="List of detection IDs associated with this event"
    )
    thumbnail_url: str | None = Field(
        None, description="URL to thumbnail image (first detection's media)"
    )
    enrichment_status: EnrichmentStatusResponse | None = Field(
        None,
        description="Enrichment pipeline status (NEM-1672) - shows which models succeeded/failed",
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
    """Schema for event list response with pagination.

    Supports both cursor-based pagination (recommended) and offset pagination (deprecated).
    Use cursor-based pagination for better performance with large datasets.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "events": [
                    {
                        "id": 1,
                        "camera_id": "front_door",
                        "started_at": "2025-12-23T12:00:00Z",
                        "ended_at": "2025-12-23T12:02:30Z",
                        "risk_score": 75,
                        "risk_level": "medium",
                        "summary": "Person detected near front entrance",
                        "reasoning": "Person approaching entrance during daytime, no suspicious behavior",
                        "llm_prompt": "<|im_start|>system\nYou are a home security risk analyzer...",
                        "reviewed": False,
                        "notes": None,
                        "detection_count": 5,
                        "detection_ids": [1, 2, 3, 4, 5],
                        "thumbnail_url": "/api/media/detections/1",
                    }
                ],
                "count": 1,
                "limit": 50,
                "offset": 0,
                "next_cursor": "eyJpZCI6IDEsICJjcmVhdGVkX2F0IjogIjIwMjUtMTItMjNUMTI6MDA6MDBaIn0=",  # pragma: allowlist secret
                "has_more": False,
            }
        }
    )

    events: list[EventResponse] = Field(..., description="List of events")
    count: int = Field(..., description="Total number of events matching filters")
    limit: int = Field(..., description="Maximum number of results returned")
    offset: int = Field(..., description="Number of results skipped (deprecated, use cursor)")
    next_cursor: str | None = Field(
        default=None,
        description="Cursor for fetching the next page. Pass this as the 'cursor' parameter.",
    )
    has_more: bool = Field(
        default=False, description="Whether there are more results available after this page"
    )
    deprecation_warning: str | None = Field(
        default=None,
        description="Warning message when using deprecated offset pagination",
    )


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
                "camera_id": "front_door",
                "camera_name": "Front Door",
                "event_count": 15,
            }
        }
    )

    camera_id: str = Field(..., description="Normalized camera ID (e.g., 'front_door')")
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
                        "camera_id": "front_door",
                        "camera_name": "Front Door",
                        "event_count": 30,
                    },
                    {
                        "camera_id": "back_door",
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


class DeletedEventsListResponse(BaseModel):
    """Schema for listing soft-deleted events (trash view).

    NEM-1955: Provides a trash view of soft-deleted events that can be restored.
    Events are ordered by deleted_at descending (most recently deleted first).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "events": [
                    {
                        "id": 1,
                        "camera_id": "front_door",
                        "started_at": "2025-12-23T12:00:00Z",
                        "ended_at": "2025-12-23T12:02:30Z",
                        "risk_score": 75,
                        "risk_level": "medium",
                        "summary": "Person detected near front entrance",
                        "reasoning": "Analysis details",
                        "reviewed": False,
                        "notes": None,
                        "detection_count": 5,
                        "detection_ids": [1, 2, 3, 4, 5],
                        "thumbnail_url": "/api/media/detections/1",
                    }
                ],
                "count": 1,
            }
        }
    )

    events: list[EventResponse] = Field(..., description="List of soft-deleted events")
    count: int = Field(..., description="Total number of deleted events")
