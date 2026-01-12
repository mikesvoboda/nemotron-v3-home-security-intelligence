"""Pydantic schemas for UserCalibration API endpoints.

NEM-2314: Create UserCalibration Pydantic schemas

These schemas support the User Feedback & Calibration System (NEM-1888),
enabling users to customize their risk thresholds and provide feedback
that calibrates the AI's risk assessment.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.api.schemas.feedback import FeedbackType


class UserCalibrationCreate(BaseModel):
    """Schema for creating a user calibration record.

    All threshold fields are optional - if not provided, server defaults
    will be used (low=30, medium=60, high=85, decay_factor=0.1).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "default",
                "low_threshold": 30,
                "medium_threshold": 60,
                "high_threshold": 85,
                "decay_factor": 0.1,
            }
        }
    )

    user_id: str = Field(
        default="default",
        description="User identifier (defaults to 'default' for single-user deployment)",
    )
    low_threshold: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Score threshold for low risk classification (0-100)",
    )
    medium_threshold: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Score threshold for medium risk classification (0-100)",
    )
    high_threshold: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Score threshold for high risk classification (0-100)",
    )
    decay_factor: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Learning rate for threshold adjustment (0.0-1.0)",
    )


class UserCalibrationUpdate(BaseModel):
    """Schema for updating user calibration settings.

    All fields are optional - only provided fields will be updated.
    When all three thresholds are provided, ordering is validated
    (low < medium < high).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "low_threshold": 25,
                "medium_threshold": 55,
                "high_threshold": 80,
                "decay_factor": 0.15,
            }
        }
    )

    low_threshold: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Score threshold for low risk classification (0-100)",
    )
    medium_threshold: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Score threshold for medium risk classification (0-100)",
    )
    high_threshold: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Score threshold for high risk classification (0-100)",
    )
    decay_factor: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Learning rate for threshold adjustment (0.0-1.0)",
    )

    @model_validator(mode="after")
    def validate_threshold_ordering(self) -> UserCalibrationUpdate:
        """Validate threshold ordering when all three thresholds are provided.

        Only validates when all three thresholds are set. Partial updates
        (1 or 2 thresholds) skip ordering validation since they'll be
        combined with existing values on the server.
        """
        low = self.low_threshold
        medium = self.medium_threshold
        high = self.high_threshold

        # Only validate ordering if all three thresholds are provided
        if low is not None and medium is not None and high is not None:
            if low >= medium:
                raise ValueError(
                    f"low_threshold ({low}) must be less than medium_threshold ({medium})"
                )
            if medium >= high:
                raise ValueError(
                    f"medium_threshold ({medium}) must be less than high_threshold ({high})"
                )

        return self


class UserCalibrationResponse(BaseModel):
    """Schema for user calibration response.

    Returned when retrieving or modifying calibration settings.
    Includes feedback counts to show calibration history.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "user_id": "default",
                "low_threshold": 30,
                "medium_threshold": 60,
                "high_threshold": 85,
                "decay_factor": 0.1,
                "false_positive_count": 5,
                "missed_threat_count": 3,
                "created_at": "2025-01-01T12:00:00Z",
                "updated_at": "2025-01-01T12:00:00Z",
            }
        },
    )

    id: int = Field(..., description="Calibration record ID")
    user_id: str = Field(..., description="User identifier")
    low_threshold: int = Field(..., description="Score threshold for low risk (0-100)")
    medium_threshold: int = Field(..., description="Score threshold for medium risk (0-100)")
    high_threshold: int = Field(..., description="Score threshold for high risk (0-100)")
    decay_factor: float = Field(..., description="Learning rate for threshold adjustment (0.0-1.0)")
    false_positive_count: int = Field(
        ..., description="Number of false positive feedbacks received"
    )
    missed_threat_count: int = Field(..., description="Number of missed threat feedbacks received")
    created_at: datetime = Field(..., description="When calibration was created")
    updated_at: datetime = Field(..., description="When calibration was last modified")


class CalibrationAdjustRequest(BaseModel):
    """Schema for requesting calibration adjustment based on feedback.

    Used when submitting feedback to adjust thresholds based on
    the feedback type and the event's original risk score.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "feedback_type": "false_positive",
                "event_risk_score": 75,
            }
        }
    )

    feedback_type: FeedbackType = Field(
        ...,
        description="Type of feedback (false_positive, missed_detection, wrong_severity, correct)",
    )
    event_risk_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Original risk score of the event (0-100)",
    )


class CalibrationDefaultsResponse(BaseModel):
    """Schema for calibration defaults response.

    Returns the system default threshold values.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "low_threshold": 30,
                "medium_threshold": 60,
                "high_threshold": 85,
                "decay_factor": 0.1,
            }
        }
    )

    low_threshold: int = Field(default=30, description="Default low threshold value")
    medium_threshold: int = Field(default=60, description="Default medium threshold value")
    high_threshold: int = Field(default=85, description="Default high threshold value")
    decay_factor: float = Field(default=0.1, description="Default decay factor value")


class CalibrationResetResponse(BaseModel):
    """Schema for calibration reset response.

    Returned after resetting calibration to default values.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Calibration reset to default values",
                "calibration": {
                    "id": 1,
                    "user_id": "default",
                    "low_threshold": 30,
                    "medium_threshold": 60,
                    "high_threshold": 85,
                    "decay_factor": 0.1,
                    "false_positive_count": 5,
                    "missed_threat_count": 3,
                    "created_at": "2025-01-01T12:00:00Z",
                    "updated_at": "2025-01-01T12:00:00Z",
                },
            }
        }
    )

    message: str = Field(..., description="Success message")
    calibration: UserCalibrationResponse = Field(..., description="Reset calibration data")


# Aliases for route compatibility
CalibrationResponse = UserCalibrationResponse
CalibrationUpdate = UserCalibrationUpdate
