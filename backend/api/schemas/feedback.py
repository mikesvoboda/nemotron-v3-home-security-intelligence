"""Pydantic schemas for EventFeedback API endpoints.

NEM-1908: Create EventFeedback API schemas and routes
NEM-3330: Enhanced feedback fields for Nemotron prompt improvement
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FeedbackType(str, Enum):
    """Types of feedback users can provide on events.

    Values:
        ACCURATE: Event was correctly classified with appropriate severity
        FALSE_POSITIVE: Event was incorrectly flagged as concerning
        MISSED_THREAT: System failed to detect a concerning event
        SEVERITY_WRONG: Event was flagged but with incorrect severity level
    """

    ACCURATE = "accurate"
    FALSE_POSITIVE = "false_positive"
    MISSED_THREAT = "missed_threat"
    SEVERITY_WRONG = "severity_wrong"

    def __str__(self) -> str:
        """Return string representation of feedback type."""
        return self.value


class ActualThreatLevel(str, Enum):
    """User's assessment of the actual threat level.

    Values:
        NO_THREAT: No threat at all (e.g., household member, pet)
        MINOR_CONCERN: Worth noting but not alarming
        GENUINE_THREAT: Real security concern
    """

    NO_THREAT = "no_threat"
    MINOR_CONCERN = "minor_concern"
    GENUINE_THREAT = "genuine_threat"

    def __str__(self) -> str:
        """Return string representation of threat level."""
        return self.value


class EventFeedbackCreate(BaseModel):
    """Schema for creating event feedback.

    Used when submitting user feedback about an event's classification.
    Enhanced with calibration fields for Nemotron prompt improvement (NEM-3330).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_id": 123,
                "feedback_type": "false_positive",
                "notes": "This was my neighbor's car, not a threat.",
                "actual_threat_level": "no_threat",
                "suggested_score": 10,
                "actual_identity": "Mike (neighbor)",
                "what_was_wrong": "Re-ID should have matched this person",
                "model_failures": ["reid_model"],
            }
        }
    )

    event_id: int = Field(
        ...,
        gt=0,
        description="ID of the event this feedback is for",
    )
    feedback_type: FeedbackType = Field(
        ...,
        description="Type of feedback (accurate, false_positive, missed_threat, severity_wrong)",
    )
    notes: str | None = Field(
        None,
        max_length=1000,
        description="Optional notes explaining the feedback",
    )
    # Enhanced feedback fields (NEM-3330)
    actual_threat_level: ActualThreatLevel | None = Field(
        None,
        description="User's assessment of true threat level (no_threat, minor_concern, genuine_threat)",
    )
    suggested_score: int | None = Field(
        None,
        ge=0,
        le=100,
        description="What the user thinks the risk score should have been (0-100)",
    )
    actual_identity: str | None = Field(
        None,
        max_length=100,
        description="Identity correction for household member learning (e.g., 'Mike (neighbor)')",
    )
    what_was_wrong: str | None = Field(
        None,
        max_length=5000,
        description="Detailed explanation of what the AI got wrong",
    )
    model_failures: list[str] | None = Field(
        None,
        description="List of specific AI models that failed (e.g., ['florence_vqa', 'pose_model'])",
    )

    @field_validator("model_failures")
    @classmethod
    def validate_model_failures(cls, v: list[str] | None) -> list[str] | None:
        """Validate model_failures contains known model names."""
        if v is None:
            return v
        known_models = {
            "clothing_model",
            "pose_model",
            "florence_vqa",
            "reid_model",
            "action_model",
            "scene_model",
            "vehicle_model",
        }
        for model in v:
            if model not in known_models:
                # Allow unknown models but could warn in future
                pass
        return v


class EventFeedbackResponse(BaseModel):
    """Schema for event feedback response.

    Returned when retrieving feedback for an event.
    Enhanced with calibration fields for Nemotron prompt improvement (NEM-3330).
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "event_id": 123,
                "feedback_type": "false_positive",
                "notes": "This was my neighbor's car, not a threat.",
                "actual_threat_level": "no_threat",
                "suggested_score": 10,
                "actual_identity": "Mike (neighbor)",
                "what_was_wrong": "Re-ID should have matched this person",
                "model_failures": ["reid_model"],
                "created_at": "2025-01-01T12:00:00Z",
            }
        },
    )

    id: int = Field(..., description="Feedback record ID")
    event_id: int = Field(..., description="Event ID this feedback belongs to")
    feedback_type: FeedbackType | str = Field(..., description="Type of feedback provided")
    notes: str | None = Field(None, description="Optional notes from user")
    # Enhanced feedback fields (NEM-3330)
    actual_threat_level: ActualThreatLevel | str | None = Field(
        None, description="User's assessment of true threat level"
    )
    suggested_score: int | None = Field(
        None, description="What user thinks score should have been (0-100)"
    )
    actual_identity: str | None = Field(
        None, description="Identity correction for household member learning"
    )
    what_was_wrong: str | None = Field(
        None, description="Detailed explanation of what AI got wrong"
    )
    model_failures: list[str] | None = Field(
        None, description="List of specific AI models that failed"
    )
    created_at: datetime = Field(..., description="When feedback was submitted")


class FeedbackStatsResponse(BaseModel):
    """Schema for aggregate feedback statistics.

    Returns counts of feedback by type and by camera to help
    calibrate the AI model's risk assessment.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_feedback": 100,
                "by_type": {
                    "accurate": 10,
                    "false_positive": 40,
                    "missed_threat": 30,
                    "severity_wrong": 20,
                },
                "by_camera": {
                    "front_door": 50,
                    "back_yard": 30,
                    "garage": 20,
                },
            }
        }
    )

    total_feedback: int = Field(
        ...,
        ge=0,
        description="Total number of feedback entries",
    )
    by_type: dict[str, int] = Field(
        ...,
        description="Count of feedback entries grouped by feedback type",
    )
    by_camera: dict[str, int] = Field(
        ...,
        description="Count of feedback entries grouped by camera ID",
    )
