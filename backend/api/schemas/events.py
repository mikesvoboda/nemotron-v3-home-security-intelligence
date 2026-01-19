"""Pydantic schemas for events API endpoints."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from backend.api.schemas.pagination import PaginationMeta


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
                "snooze_until": None,
                "detection_count": 5,
                "detection_ids": [1, 2, 3, 4, 5],
                "thumbnail_url": "/api/detections/1/image",
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
    snooze_until: datetime | None = Field(
        None, description="Timestamp until which alerts for this event are snoozed (NEM-2359)"
    )
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
    deleted_at: datetime | None = Field(
        None,
        description="Timestamp when the event was soft-deleted (null if not deleted)",
    )


class EventUpdate(BaseModel):
    """Schema for updating an event (PATCH)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reviewed": True,
                "notes": "Verified - delivery person",
                "snooze_until": "2025-12-24T12:00:00Z",
            }
        }
    )

    reviewed: bool | None = Field(None, description="Mark event as reviewed or not reviewed")
    notes: str | None = Field(None, description="User notes for the event")
    snooze_until: datetime | None = Field(
        None, description="Set or clear the alert snooze timestamp (NEM-2359)"
    )


class EventListResponse(BaseModel):
    """Schema for event list response with pagination.

    NEM-2075: Standardized pagination envelope with items + pagination structure.
    Supports both cursor-based pagination (recommended) and offset pagination (deprecated).
    Use cursor-based pagination for better performance with large datasets.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": 1,
                        "camera_id": "front_door",
                        "started_at": "2025-12-23T12:00:00Z",
                        "ended_at": "2025-12-23T12:02:30Z",
                        "risk_score": 75,
                        "risk_level": "medium",
                        "summary": "Person detected near front entrance",
                        "reasoning": "Person approaching entrance during daytime",
                        "reviewed": False,
                        "notes": None,
                        "detection_count": 5,
                        "detection_ids": [1, 2, 3, 4, 5],
                        "thumbnail_url": "/api/detections/1/image",
                    }
                ],
                "pagination": {
                    "total": 1,
                    "limit": 50,
                    "offset": 0,
                    "cursor": None,
                    "next_cursor": "eyJpZCI6IDEsICJjcmVhdGVkX2F0IjogIjIwMjUtMTItMjNUMTI6MDA6MDBaIn0=",  # pragma: allowlist secret
                    "has_more": False,
                },
                "deprecation_warning": None,
            }
        }
    )

    items: list[EventResponse] = Field(..., description="List of events")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")
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


class RiskDistributionItem(BaseModel):
    """Schema for a single risk distribution item (for Grafana compatibility)."""

    model_config = ConfigDict(json_schema_extra={"example": {"risk_level": "high", "count": 5}})

    risk_level: str = Field(..., description="Risk level name (critical, high, medium, low)")
    count: int = Field(..., description="Number of events with this risk level")


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
                "risk_distribution": [
                    {"risk_level": "critical", "count": 2},
                    {"risk_level": "high", "count": 5},
                    {"risk_level": "medium", "count": 12},
                    {"risk_level": "low", "count": 25},
                ],
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
    risk_distribution: list[RiskDistributionItem] = Field(
        default_factory=list,
        description="Events by risk level as array (for Grafana compatibility)",
    )
    events_by_camera: list[EventsByCamera] = Field(..., description="Events grouped by camera")


class TimelineBucketResponse(BaseModel):
    """Schema for a single time bucket in the timeline summary (NEM-2932).

    Each bucket represents a time period with aggregated event data.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2026-01-15T12:00:00Z",
                "event_count": 15,
                "max_risk_score": 85,
            }
        }
    )

    timestamp: datetime = Field(..., description="Start timestamp of this bucket")
    event_count: int = Field(..., ge=0, description="Number of events in this bucket")
    max_risk_score: int = Field(
        0, ge=0, le=100, description="Maximum risk score of events in this bucket"
    )


class TimelineSummaryResponse(BaseModel):
    """Schema for timeline summary response (NEM-2932).

    Returns bucketed event data for timeline visualization.
    Supports different zoom levels with varying bucket sizes.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "buckets": [
                    {
                        "timestamp": "2026-01-15T06:00:00Z",
                        "event_count": 5,
                        "max_risk_score": 45,
                    },
                    {
                        "timestamp": "2026-01-15T07:00:00Z",
                        "event_count": 12,
                        "max_risk_score": 85,
                    },
                    {
                        "timestamp": "2026-01-15T08:00:00Z",
                        "event_count": 3,
                        "max_risk_score": 25,
                    },
                ],
                "total_events": 20,
                "start_date": "2026-01-15T06:00:00Z",
                "end_date": "2026-01-15T09:00:00Z",
            }
        }
    )

    buckets: list[TimelineBucketResponse] = Field(
        ..., description="List of time buckets with aggregated event data"
    )
    total_events: int = Field(..., ge=0, description="Total events in the time range")
    start_date: datetime = Field(..., description="Start of the timeline range")
    end_date: datetime = Field(..., description="End of the timeline range")


class DeletedEventsListResponse(BaseModel):
    """Schema for listing soft-deleted events (trash view).

    NEM-1955: Provides a trash view of soft-deleted events that can be restored.
    Events are ordered by deleted_at descending (most recently deleted first).
    NEM-2075: Standardized pagination envelope with items + pagination structure.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
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
                        "thumbnail_url": "/api/detections/1/image",
                    }
                ],
                "pagination": {
                    "total": 1,
                    "limit": 50,
                    "offset": 0,
                    "cursor": None,
                    "next_cursor": None,
                    "has_more": False,
                },
            }
        }
    )

    items: list[EventResponse] = Field(..., description="List of soft-deleted events")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")
