"""Pydantic schemas for summaries API endpoints.

These schemas define the response models for the dashboard summaries feature,
which provides hourly and daily LLM-generated narrative summaries of security events.

Also includes actionable insights that provide prioritized recommendations
based on event analysis (NEM-5418, NEM-5419, NEM-5420, NEM-5421).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BulletPointSchema(BaseModel):
    """Schema for a single bullet point in a structured summary.

    Represents a visual bullet point for display in the dashboard UI,
    with an icon, text content, and optional severity level.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "icon": "camera",
                "text": "Activity at Beach Front Left: person detected",
                "severity": "high",
            }
        }
    )

    icon: str = Field(..., description="Icon identifier (e.g., 'camera', 'alert-triangle')")
    text: str = Field(..., description="Text content of the bullet point")
    severity: str | None = Field(
        None, description="Severity level ('low', 'medium', 'high', 'critical')"
    )


class StructuredSummarySchema(BaseModel):
    """Schema for structured summary data extracted from LLM content.

    Contains categorized information extracted from the narrative summary
    for display in the dashboard UI with visual elements.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "bullet_points": [
                    {
                        "icon": "camera",
                        "text": "Activity at Beach Front Left: person approaching",
                        "severity": "high",
                    },
                    {
                        "icon": "alert-circle",
                        "text": "Loitering behavior detected",
                        "severity": "high",
                    },
                ],
                "focus_areas": ["Beach Front Left", "Dock Right"],
                "dominant_patterns": ["loitering", "obscured face"],
                "max_risk_score": 85,
                "weather_conditions": ["nighttime"],
            }
        }
    )

    bullet_points: list[BulletPointSchema] = Field(
        default_factory=list, description="List of bullet points for visual display"
    )
    focus_areas: list[str] = Field(
        default_factory=list, description="Camera names mentioned in the summary"
    )
    dominant_patterns: list[str] = Field(
        default_factory=list,
        description="Behavior patterns detected (loitering, obscured face, etc.)",
    )
    max_risk_score: int | None = Field(
        None, description="Maximum risk score from events (0-100)", ge=0, le=100
    )
    weather_conditions: list[str] = Field(
        default_factory=list,
        description="Weather/environmental conditions (rainy, nighttime, etc.)",
    )


class InsightSchema(BaseModel):
    """Schema for an actionable insight.

    Represents a prioritized recommendation based on event analysis.
    Insights help users understand what needs attention and provide
    direct links to relevant data.

    Types:
        - camera: Activity on specific cameras that need attention
        - entity: Unknown persons or notable entities detected
        - trend: Activity patterns compared to baseline

    Priority levels (1-10, higher = more urgent):
        - 10: Unknown persons detected (highest)
        - 8-9: Unusual activity trends
        - 6-7: High camera activity
        - 4-5: Known entities
        - 1-3: Informational (lowest)
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "entity",
                "priority": 10,
                "title": "Unknown Persons Detected",
                "description": "2 unknown persons detected at Front Door, Driveway",
                "action_url": "/timeline?entity_type=person&recognized=false",
            }
        }
    )

    type: Literal["camera", "entity", "trend"] = Field(
        ..., description="Insight category (camera, entity, or trend)"
    )
    priority: int = Field(
        ..., description="Urgency level 1-10 (10 = highest priority)", ge=1, le=10
    )
    title: str = Field(..., description="Short title for the insight")
    description: str = Field(..., description="Detailed description with actionable information")
    action_url: str | None = Field(None, description="Optional URL to view related events/data")


class SummaryResponse(BaseModel):
    """Schema for a single summary (hourly or daily).

    Represents an LLM-generated narrative summary of security events within
    a specific time window, with both raw content and structured data.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "content": (
                    "Over the past hour, one critical event occurred at 2:15 PM "
                    "when an unrecognized person approached the front door. "
                    "The individual remained at the door for approximately 45 seconds "
                    "before leaving via the driveway."
                ),
                "event_count": 1,
                "window_start": "2026-01-18T14:00:00Z",
                "window_end": "2026-01-18T15:00:00Z",
                "generated_at": "2026-01-18T14:55:00Z",
                "structured": {
                    "bullet_points": [
                        {
                            "icon": "camera",
                            "text": "Activity at front door: unrecognized person",
                            "severity": "critical",
                        }
                    ],
                    "focus_areas": ["Front Door"],
                    "dominant_patterns": [],
                    "max_risk_score": 85,
                    "weather_conditions": [],
                },
                "insights": [
                    {
                        "type": "entity",
                        "priority": 10,
                        "title": "Unknown Persons Detected",
                        "description": "1 unknown person detected at Front Door",
                        "action_url": "/timeline?entity_type=person&recognized=false",
                    },
                    {
                        "type": "camera",
                        "priority": 6,
                        "title": "Camera Activity",
                        "description": "Review 1 event from Front Door (1 high/critical)",
                        "action_url": "/timeline?camera_id=front_door",
                    },
                ],
            }
        }
    )

    id: int = Field(..., description="Summary ID")
    content: str = Field(..., description="LLM-generated narrative text (2-4 sentences)")
    event_count: int = Field(
        ..., description="Number of high/critical events included in this summary", ge=0
    )
    window_start: datetime = Field(..., description="Start of the time window covered")
    window_end: datetime = Field(..., description="End of the time window covered")
    generated_at: datetime = Field(..., description="When the LLM produced this summary")
    structured: StructuredSummarySchema | None = Field(
        None, description="Structured data extracted from the summary content"
    )
    insights: list[InsightSchema] = Field(
        default_factory=list,
        description="Actionable insights prioritized by urgency (top 3-5 shown)",
    )


class LatestSummariesResponse(BaseModel):
    """Schema for the combined latest summaries response.

    Returns both the latest hourly and daily summaries in a single response.
    Either field can be null if no summary exists for that time period.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "hourly": {
                    "id": 1,
                    "content": (
                        "Over the past hour, one critical event occurred at 2:15 PM "
                        "when an unrecognized person approached the front door."
                    ),
                    "event_count": 1,
                    "window_start": "2026-01-18T14:00:00Z",
                    "window_end": "2026-01-18T15:00:00Z",
                    "generated_at": "2026-01-18T14:55:00Z",
                },
                "daily": {
                    "id": 2,
                    "content": (
                        "Today has seen minimal high-priority activity. "
                        "The only notable event was at 2:15 PM at the front door. "
                        "Morning and evening periods have been quiet with routine traffic only."
                    ),
                    "event_count": 1,
                    "window_start": "2026-01-18T00:00:00Z",
                    "window_end": "2026-01-18T15:00:00Z",
                    "generated_at": "2026-01-18T14:55:00Z",
                },
            }
        }
    )

    hourly: SummaryResponse | None = Field(
        None, description="Latest hourly summary (past 60 minutes), null if none exists"
    )
    daily: SummaryResponse | None = Field(
        None, description="Latest daily summary (since midnight), null if none exists"
    )


class TimelineEventSchema(BaseModel):
    """Schema for an event in the summary timeline.

    Represents a single event in the timeline view of the expandable detail panel.
    Provides key information for quick scanning and links to full event details.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_id": 101,
                "timestamp": "2026-01-21T14:10:00Z",
                "camera_name": "Front Door",
                "summary": "Person detected approaching the front door",
                "risk_score": 75,
                "risk_level": "high",
                "event_url": "/events/101",
            }
        }
    )

    event_id: int = Field(..., description="Event ID")
    timestamp: datetime = Field(..., description="When the event occurred")
    camera_name: str = Field(..., description="Name of the camera that captured the event")
    summary: str = Field(..., description="Brief summary of the event")
    risk_score: int | None = Field(None, description="Risk score (0-100)", ge=0, le=100)
    risk_level: str | None = Field(None, description="Risk level (low, medium, high, critical)")
    event_url: str | None = Field(None, description="URL to view full event details")


class SummaryDetailResponse(BaseModel):
    """Schema for detailed summary response with timeline and export options.

    Used by the expandable detail panel to display full summary information,
    including a timeline of events and export functionality.

    Related Linear issues: NEM-5425, NEM-5426, NEM-5427
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "summary_type": "hourly",
                "content": (
                    "Multiple security events were detected in the past hour. "
                    "A high-risk event occurred at the Front Door when an unrecognized "
                    "person approached. Vehicle activity was also observed in the Driveway."
                ),
                "event_count": 3,
                "window_start": "2026-01-21T14:00:00Z",
                "window_end": "2026-01-21T15:00:00Z",
                "generated_at": "2026-01-21T14:55:00Z",
                "structured": {
                    "bullet_points": [],
                    "focus_areas": ["Front Door", "Driveway"],
                    "dominant_patterns": ["person", "vehicle"],
                    "max_risk_score": 75,
                    "weather_conditions": [],
                },
                "timeline": [
                    {
                        "event_id": 101,
                        "timestamp": "2026-01-21T14:10:00Z",
                        "camera_name": "Front Door",
                        "summary": "Person detected approaching the front door",
                        "risk_score": 75,
                        "risk_level": "high",
                        "event_url": "/events/101",
                    }
                ],
                "export_formats": ["json", "csv", "pdf"],
            }
        }
    )

    id: int = Field(..., description="Summary ID")
    summary_type: str = Field(..., description="Type of summary (hourly or daily)")
    content: str = Field(..., description="Full LLM-generated narrative text")
    event_count: int = Field(
        ..., description="Number of high/critical events included in this summary", ge=0
    )
    window_start: datetime = Field(..., description="Start of the time window covered")
    window_end: datetime = Field(..., description="End of the time window covered")
    generated_at: datetime = Field(..., description="When the LLM produced this summary")
    structured: StructuredSummarySchema | None = Field(
        None, description="Structured data extracted from the summary content"
    )
    timeline: list[TimelineEventSchema] = Field(
        default_factory=list,
        description="Timeline of events included in this summary, sorted chronologically",
    )
    export_formats: list[str] = Field(
        default_factory=lambda: ["json", "csv", "pdf"],
        description="Available export formats for this summary",
    )
