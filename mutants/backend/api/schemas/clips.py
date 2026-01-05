"""Pydantic schemas for event clip API endpoints."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ClipStatus(str, Enum):
    """Status of clip generation."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class ClipInfoResponse(BaseModel):
    """Schema for clip info response (GET /api/events/{event_id}/clip)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_id": 123,
                "clip_available": True,
                "clip_url": "/api/media/clips/123_clip.mp4",
                "duration_seconds": 30,
                "generated_at": "2026-01-03T10:30:00Z",
                "file_size_bytes": 5242880,
            }
        }
    )

    event_id: int = Field(..., description="Event ID")
    clip_available: bool = Field(..., description="Whether a clip is available for this event")
    clip_url: str | None = Field(None, description="URL to access the clip (if available)")
    duration_seconds: int | None = Field(None, description="Duration of the clip in seconds")
    generated_at: datetime | None = Field(None, description="Timestamp when the clip was generated")
    file_size_bytes: int | None = Field(None, description="File size of the clip in bytes")


class ClipGenerateRequest(BaseModel):
    """Schema for clip generation request (POST /api/events/{event_id}/clip/generate).

    Offset validation (NEM-1355):
    - start_offset_seconds: -30 to 3600 seconds
    - end_offset_seconds: -30 to 3600 seconds
    - end_offset_seconds must be >= start_offset_seconds
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "start_offset_seconds": -15,
                "end_offset_seconds": 30,
                "force": False,
            }
        }
    )

    start_offset_seconds: int = Field(
        -15,
        ge=-30,
        le=3600,
        description="Seconds relative to event start to begin clip "
        "(negative = before event, range: -30 to 3600)",
    )
    end_offset_seconds: int = Field(
        30,
        ge=-30,
        le=3600,
        description="Seconds relative to event start to end clip "
        "(range: -30 to 3600, must be >= start_offset_seconds)",
    )
    force: bool = Field(False, description="Force regeneration even if clip already exists")

    @model_validator(mode="after")
    def validate_offset_order(self) -> ClipGenerateRequest:
        """Validate that end_offset_seconds >= start_offset_seconds (NEM-1355).

        This ensures the clip has a non-negative duration.

        Returns:
            Self if validation passes

        Raises:
            ValueError: If end_offset_seconds < start_offset_seconds
        """
        if self.end_offset_seconds < self.start_offset_seconds:
            raise ValueError(
                f"end_offset_seconds ({self.end_offset_seconds}) must be greater than or equal to "
                f"start_offset_seconds ({self.start_offset_seconds}). "
                "The end of the clip cannot be before the start."
            )
        return self


class ClipGenerateResponse(BaseModel):
    """Schema for clip generation response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_id": 123,
                "status": "completed",
                "clip_url": "/api/media/clips/123_clip.mp4",
                "generated_at": "2026-01-03T10:30:00Z",
                "message": "Clip generated successfully",
            }
        }
    )

    event_id: int = Field(..., description="Event ID")
    status: ClipStatus = Field(..., description="Status of clip generation")
    clip_url: str | None = Field(None, description="URL to access the clip (if completed)")
    generated_at: datetime | None = Field(None, description="Timestamp when the clip was generated")
    message: str | None = Field(None, description="Status message or error details")
