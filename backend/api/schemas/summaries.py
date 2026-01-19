"""Pydantic schemas for summaries API endpoints.

These schemas define the response models for the dashboard summaries feature,
which provides hourly and daily LLM-generated narrative summaries of security events.
"""

from datetime import datetime

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
