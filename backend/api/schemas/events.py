"""Pydantic schemas for events API endpoints."""

from datetime import datetime
from enum import Enum
from functools import cached_property

from pydantic import BaseModel, ConfigDict, Field, computed_field

from backend.api.schemas.llm_response import (
    ConfidenceFactors,
    RiskEntity,
    RiskFactor,
    RiskFlag,
)
from backend.api.schemas.pagination import PaginationMeta

# Default severity thresholds (matches backend.services.severity)
# These are used for computing risk_level from risk_score
_DEFAULT_LOW_MAX = 29
_DEFAULT_MEDIUM_MAX = 59
_DEFAULT_HIGH_MAX = 84


def _compute_risk_level(risk_score: int | None) -> str | None:
    """Compute risk level from risk score using default thresholds.

    Thresholds (from backend severity taxonomy):
    - LOW: 0-29
    - MEDIUM: 30-59
    - HIGH: 60-84
    - CRITICAL: 85-100

    Args:
        risk_score: Risk score from 0 to 100, or None

    Returns:
        Risk level string ('low', 'medium', 'high', 'critical') or None if score is None
    """
    if risk_score is None:
        return None
    if risk_score <= _DEFAULT_LOW_MAX:
        return "low"
    if risk_score <= _DEFAULT_MEDIUM_MAX:
        return "medium"
    if risk_score <= _DEFAULT_HIGH_MAX:
        return "high"
    return "critical"


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
                "version": 1,
                "risk_factors": [
                    {
                        "factor_name": "daytime_activity",
                        "contribution": -10.0,
                        "description": "Activity during normal hours",
                    },
                    {
                        "factor_name": "front_entrance",
                        "contribution": 5.0,
                        "description": "Activity at primary entrance",
                    },
                ],
                "entities": [
                    {
                        "type": "person",
                        "description": "Individual in casual clothing",
                        "threat_level": "low",
                    }
                ],
                "flags": [],
                "recommended_action": None,
                "confidence_factors": {
                    "detection_quality": "good",
                    "weather_impact": "none",
                    "enrichment_coverage": "full",
                },
            }
        },
    )

    id: int = Field(..., description="Event ID")
    camera_id: str = Field(..., description="Normalized camera ID (e.g., 'front_door')")
    started_at: datetime = Field(..., description="Event start timestamp")
    ended_at: datetime | None = Field(None, description="Event end timestamp")
    risk_score: int | None = Field(None, description="Risk score (0-100)")
    summary: str | None = Field(None, description="LLM-generated event summary")
    version: int = Field(
        1,
        description="Optimistic locking version (NEM-3625). Include in updates to prevent conflicts.",
    )

    @computed_field  # type: ignore[prop-decorator]
    @cached_property
    def risk_level(self) -> str | None:
        """Compute risk level from risk_score (NEM-3398).

        This computed field derives risk_level from risk_score using
        the backend severity taxonomy thresholds:
        - LOW: 0-29
        - MEDIUM: 30-59
        - HIGH: 60-84
        - CRITICAL: 85-100

        Returns:
            Risk level string or None if risk_score is None
        """
        return _compute_risk_level(self.risk_score)

    reasoning: str | None = Field(None, description="LLM reasoning for risk score")
    llm_prompt: str | None = Field(
        None, description="Full prompt sent to Nemotron LLM (for debugging/improvement)"
    )
    reviewed: bool = Field(False, description="Whether event has been reviewed")
    flagged: bool = Field(False, description="Whether event is flagged for follow-up (NEM-3839)")
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
    # Risk factors breakdown (NEM-3603)
    risk_factors: list[RiskFactor] | None = Field(
        default=None,
        description="Individual factors contributing to the risk score (NEM-3603)",
    )
    # Advanced risk analysis fields (NEM-3601)
    entities: list[RiskEntity] = Field(
        default_factory=list,
        description="Entities identified in the analysis (people, vehicles, objects)",
    )
    flags: list[RiskFlag] = Field(
        default_factory=list,
        description="Risk flags raised during analysis",
    )
    recommended_action: str | None = Field(
        None,
        description="Suggested action based on the analysis",
    )
    confidence_factors: ConfidenceFactors | None = Field(
        None,
        description="Factors affecting confidence in the analysis",
    )

    def model_dump_list(self) -> dict:
        """Serialize for list views (exclude detail-only fields).

        Excludes large fields like llm_prompt and reasoning that are only
        needed in detail views. This reduces payload size by 30-50% for
        list responses.

        Returns:
            Dictionary with list view fields only, None values excluded.
        """
        return self.model_dump(
            exclude={"llm_prompt", "reasoning"},
            exclude_none=True,
        )

    def model_dump_detail(self) -> dict:
        """Serialize for detail views (include all fields).

        Includes all fields including large detail-only fields like
        llm_prompt and reasoning.

        Returns:
            Dictionary with all fields, None values excluded.
        """
        return self.model_dump(exclude_none=True)


class EventUpdate(BaseModel):
    """Schema for updating an event (PATCH).

    Supports optimistic locking (NEM-3625): Include the `version` field from the
    event response to prevent concurrent modification conflicts. If the version
    doesn't match, the server returns HTTP 409 Conflict.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reviewed": True,
                "notes": "Verified - delivery person",
                "snooze_until": "2025-12-24T12:00:00Z",
                "version": 1,
            }
        }
    )

    reviewed: bool | None = Field(None, description="Mark event as reviewed or not reviewed")
    flagged: bool | None = Field(None, description="Flag or unflag event for follow-up (NEM-3839)")
    notes: str | None = Field(None, description="User notes for the event")
    snooze_until: datetime | None = Field(
        None, description="Set or clear the alert snooze timestamp (NEM-2359)"
    )
    version: int | None = Field(
        None,
        description=(
            "Optimistic locking version (NEM-3625). "
            "Include the version from the event response to detect concurrent modifications. "
            "If the version doesn't match, returns HTTP 409 Conflict."
        ),
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
