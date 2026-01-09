"""Pydantic schemas for restore API endpoints.

These schemas define the response format for restoring soft-deleted records.
Restore operations set the `deleted_at` column back to NULL, making the record
active again.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CameraRestoreResponse(BaseModel):
    """Schema for camera restore response.

    Returns the restored camera details after clearing the deleted_at timestamp.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "front_door",
                "name": "Front Door Camera",
                "folder_path": "/export/foscam/front_door",
                "status": "offline",
                "created_at": "2025-12-23T10:00:00Z",
                "last_seen_at": "2025-12-23T12:00:00Z",
                "deleted_at": None,
                "restored": True,
                "message": "Camera restored successfully",
            }
        },
    )

    id: str = Field(
        ..., description="Normalized camera ID derived from folder name (e.g., 'front_door')"
    )
    name: str = Field(..., description="Camera name")
    folder_path: str = Field(..., description="File system path for camera uploads")
    status: str = Field(..., description="Camera status (online, offline, error, unknown)")
    created_at: datetime = Field(..., description="Timestamp when camera was created")
    last_seen_at: datetime | None = Field(None, description="Last time camera was active")
    deleted_at: None = Field(None, description="Deletion timestamp (always None after restore)")
    restored: bool = Field(True, description="Indicates the record was successfully restored")
    message: str = Field(
        default="Camera restored successfully",
        description="Human-readable confirmation message",
    )


class EventRestoreResponse(BaseModel):
    """Schema for event restore response.

    Returns the restored event details after clearing the deleted_at timestamp.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 123,
                "camera_id": "front_door",
                "started_at": "2025-12-23T12:00:00Z",
                "ended_at": "2025-12-23T12:02:30Z",
                "risk_score": 75,
                "risk_level": "medium",
                "summary": "Person detected near front entrance",
                "reviewed": False,
                "deleted_at": None,
                "restored": True,
                "message": "Event restored successfully",
            }
        },
    )

    id: int = Field(..., description="Event ID")
    camera_id: str = Field(..., description="Normalized camera ID (e.g., 'front_door')")
    started_at: datetime = Field(..., description="Event start timestamp")
    ended_at: datetime | None = Field(None, description="Event end timestamp")
    risk_score: int | None = Field(None, description="Risk score (0-100)")
    risk_level: str | None = Field(None, description="Risk level (low, medium, high, critical)")
    summary: str | None = Field(None, description="LLM-generated event summary")
    reviewed: bool = Field(False, description="Whether event has been reviewed")
    deleted_at: None = Field(None, description="Deletion timestamp (always None after restore)")
    restored: bool = Field(True, description="Indicates the record was successfully restored")
    message: str = Field(
        default="Event restored successfully",
        description="Human-readable confirmation message",
    )
