"""Pydantic schemas for EventFeedback API endpoints.

NEM-1908: Create EventFeedback API schemas and routes
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class FeedbackType(str, Enum):
    """Types of feedback users can provide on events.

    Values:
        FALSE_POSITIVE: Event was incorrectly flagged as concerning
        MISSED_DETECTION: System failed to detect a concerning event
        WRONG_SEVERITY: Event was flagged but with wrong severity level
        CORRECT: Event was correctly classified and scored
    """

    FALSE_POSITIVE = "false_positive"
    MISSED_DETECTION = "missed_detection"
    WRONG_SEVERITY = "wrong_severity"
    CORRECT = "correct"

    def __str__(self) -> str:
        """Return string representation of feedback type."""
        return self.value


class EventFeedbackCreate(BaseModel):
    """Schema for creating event feedback.

    Used when submitting user feedback about an event's classification.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_id": 123,
                "feedback_type": "false_positive",
                "notes": "This was my neighbor's car, not a threat.",
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
        description="Type of feedback (false_positive, missed_detection, wrong_severity, correct)",
    )
    notes: str | None = Field(
        None,
        max_length=1000,
        description="Optional notes explaining the feedback",
    )


class EventFeedbackResponse(BaseModel):
    """Schema for event feedback response.

    Returned when retrieving feedback for an event.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "event_id": 123,
                "feedback_type": "false_positive",
                "notes": "This was my neighbor's car, not a threat.",
                "created_at": "2025-01-01T12:00:00Z",
            }
        },
    )

    id: int = Field(..., description="Feedback record ID")
    event_id: int = Field(..., description="Event ID this feedback belongs to")
    feedback_type: FeedbackType | str = Field(..., description="Type of feedback provided")
    notes: str | None = Field(None, description="Optional notes from user")
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
                    "false_positive": 40,
                    "missed_detection": 30,
                    "wrong_severity": 20,
                    "correct": 10,
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
