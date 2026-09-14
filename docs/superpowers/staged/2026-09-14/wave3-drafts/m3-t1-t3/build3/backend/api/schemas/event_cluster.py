"""Pydantic schemas for event clustering API endpoints (NEM-3620)."""

from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class ClusterRiskLevels(BaseModel):
    """Schema for aggregated risk levels within a cluster."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "critical": 1,
                "high": 2,
                "medium": 2,
                "low": 0,
            }
        }
    )

    critical: int = Field(0, ge=0, description="Number of critical risk events in the cluster")
    high: int = Field(0, ge=0, description="Number of high risk events in the cluster")
    medium: int = Field(0, ge=0, description="Number of medium risk events in the cluster")
    low: int = Field(0, ge=0, description="Number of low risk events in the cluster")


class ClusterEventSummary(BaseModel):
    """Abbreviated event object for cluster response."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "camera_id": "front_door",
                "started_at": "2026-01-25T10:00:00Z",
                "risk_score": 75,
                "risk_level": "high",
                "summary": "Person detected at front entrance",
            }
        },
    )

    id: int = Field(..., description="Event ID")
    camera_id: str = Field(..., description="Camera ID that captured this event")
    started_at: datetime = Field(..., description="Event start timestamp")
    risk_score: int | None = Field(None, description="Risk score (0-100)")
    risk_level: str | None = Field(None, description="Risk level (low, medium, high, critical)")
    summary: str | None = Field(None, description="Brief event summary")


class EventCluster(BaseModel):
    """Schema for an event cluster."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cluster_id": "123e4567-e89b-12d3-a456-426614174000",
                "start_time": "2026-01-25T10:00:00Z",
                "end_time": "2026-01-25T10:05:00Z",
                "event_count": 5,
                "cameras": ["front_door", "back_door"],
                "risk_levels": {
                    "critical": 1,
                    "high": 2,
                    "medium": 2,
                    "low": 0,
                },
                "object_types": {"person": 3, "vehicle": 2},
                "events": [
                    {
                        "id": 1,
                        "camera_id": "front_door",
                        "started_at": "2026-01-25T10:00:00Z",
                        "risk_score": 85,
                        "risk_level": "critical",
                        "summary": "Unknown person at door",
                    }
                ],
            }
        },
    )

    cluster_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the cluster",
    )
    start_time: datetime = Field(..., description="Start time of the first event in the cluster")
    end_time: datetime = Field(..., description="End time of the last event in the cluster")
    event_count: int = Field(..., ge=1, description="Total number of events in the cluster")
    cameras: list[str] = Field(..., description="List of camera IDs with events in this cluster")
    risk_levels: ClusterRiskLevels = Field(
        ..., description="Count of events by risk level in the cluster"
    )
    object_types: dict[str, int] = Field(
        default_factory=dict,
        description="Count of events by detected object type",
    )
    events: list[ClusterEventSummary] = Field(
        ..., description="Abbreviated event objects in the cluster"
    )


class EventClustersResponse(BaseModel):
    """Schema for event clusters API response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "clusters": [
                    {
                        "cluster_id": "123e4567-e89b-12d3-a456-426614174000",
                        "start_time": "2026-01-25T10:00:00Z",
                        "end_time": "2026-01-25T10:05:00Z",
                        "event_count": 5,
                        "cameras": ["front_door", "back_door"],
                        "risk_levels": {
                            "critical": 1,
                            "high": 2,
                            "medium": 2,
                            "low": 0,
                        },
                        "object_types": {"person": 3, "vehicle": 2},
                        "events": [],
                    }
                ],
                "total_clusters": 10,
                "unclustered_events": 15,
            }
        },
    )

    clusters: list[EventCluster] = Field(
        ..., description="List of event clusters matching the query"
    )
    total_clusters: int = Field(..., ge=0, description="Total number of clusters found")
    unclustered_events: int = Field(
        ..., ge=0, description="Number of events not belonging to any cluster"
    )
