"""Pydantic schemas for event search API endpoints."""

from datetime import datetime
from functools import cached_property

from pydantic import BaseModel, ConfigDict, Field, computed_field

from backend.api.schemas.events import _compute_risk_level


class SearchResult(BaseModel):
    """Schema for a single search result."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "camera_id": "front_door",
                "camera_name": "Front Door",
                "started_at": "2025-12-23T12:00:00Z",
                "ended_at": "2025-12-23T12:02:30Z",
                "risk_score": 75,
                "risk_level": "medium",
                "summary": "Suspicious person detected near front entrance",
                "reasoning": "Unknown individual approaching entrance during nighttime hours",
                "reviewed": False,
                "detection_count": 5,
                "detection_ids": [1, 2, 3, 4, 5],
                "object_types": "person, vehicle",
                "relevance_score": 0.85,
            }
        },
    )

    id: int = Field(..., description="Event ID")
    camera_id: str = Field(..., description="Camera ID")
    camera_name: str | None = Field(None, description="Camera display name")
    started_at: datetime = Field(..., description="Event start timestamp")
    ended_at: datetime | None = Field(None, description="Event end timestamp")
    risk_score: int | None = Field(None, description="Risk score (0-100)")
    summary: str | None = Field(None, description="LLM-generated event summary")

    @computed_field(  # type: ignore[prop-decorator]
        description="Risk level (low/medium/high/critical), computed from risk_score using severity thresholds"
    )
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
    reviewed: bool = Field(False, description="Whether event has been reviewed")
    detection_count: int = Field(0, description="Number of detections in this event")
    detection_ids: list[int] = Field(
        default_factory=list, description="List of detection IDs associated with this event"
    )
    object_types: str | None = Field(None, description="Comma-separated detected object types")
    relevance_score: float = Field(
        0.0, description="Full-text search relevance score (higher is more relevant)"
    )
    thumbnail_url: str | None = Field(
        None, description="URL to event thumbnail image (from first detection)"
    )


class SearchResponse(BaseModel):
    """Schema for search response with pagination."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "results": [
                    {
                        "id": 1,
                        "camera_id": "front_door",
                        "camera_name": "Front Door",
                        "started_at": "2025-12-23T12:00:00Z",
                        "ended_at": "2025-12-23T12:02:30Z",
                        "risk_score": 75,
                        "risk_level": "medium",
                        "summary": "Suspicious person detected near front entrance",
                        "reasoning": "Unknown individual approaching entrance during nighttime",
                        "reviewed": False,
                        "detection_count": 5,
                        "detection_ids": [1, 2, 3, 4, 5],
                        "object_types": "person, vehicle",
                        "relevance_score": 0.85,
                    }
                ],
                "total_count": 42,
                "limit": 50,
                "offset": 0,
            }
        }
    )

    results: list[SearchResult] = Field(..., description="List of search results")
    total_count: int = Field(..., description="Total number of matching events")
    limit: int = Field(..., description="Maximum number of results returned")
    offset: int = Field(..., description="Number of results skipped")


class SearchRequest(BaseModel):
    """Schema for search request body (alternative to query params).

    Note: For GET requests, use comma-separated strings for multi-value parameters:
    - severity: "high,critical" (not ["high", "critical"])
    - camera_ids: "front_door,back_door" (not ["front_door", "back_door"])
    - object_types: "person,vehicle" (not ["person", "vehicle"])

    This schema documents the POST request body format if a POST endpoint is added.
    The GET endpoint at /api/events/search uses query parameters with comma-separated values.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "suspicious person near entrance",
                "start_date": "2025-12-01T00:00:00Z",
                "end_date": "2025-12-28T23:59:59Z",
                "camera_ids": "front_door,back_door",
                "severity": "high,critical",
                "object_types": "person",
                "reviewed": False,
                "limit": 50,
                "offset": 0,
            }
        }
    )

    query: str = Field(..., min_length=1, description="Search query string")
    start_date: datetime | None = Field(None, description="Filter by start date (ISO format)")
    end_date: datetime | None = Field(None, description="Filter by end date (ISO format)")
    camera_ids: str | None = Field(
        None, description="Filter by camera IDs (comma-separated for multiple)"
    )
    severity: str | None = Field(
        None, description="Filter by risk levels (comma-separated: low,medium,high,critical)"
    )
    object_types: str | None = Field(
        None, description="Filter by detected object types (comma-separated: person,vehicle,animal)"
    )
    reviewed: bool | None = Field(None, description="Filter by reviewed status")
    limit: int = Field(50, ge=1, le=1000, description="Maximum number of results")
    offset: int = Field(0, ge=0, description="Number of results to skip")
