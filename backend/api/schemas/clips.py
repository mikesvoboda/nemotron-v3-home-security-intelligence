"""Pydantic schemas for event clip API endpoints."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


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
    """Schema for clip generation request (POST /api/events/{event_id}/clip/generate)."""

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
        ge=-300,
        le=0,
        description="Seconds before event start to include (negative value, max -300)",
    )
    end_offset_seconds: int = Field(
        30,
        ge=0,
        le=300,
        description="Seconds after event end to include (max 300)",
    )
    force: bool = Field(False, description="Force regeneration even if clip already exists")


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
