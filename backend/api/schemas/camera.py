"""Pydantic schemas for camera API endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.models.enums import CameraStatus

# Re-export CameraStatus for convenient imports from this module
__all__ = ["CameraCreate", "CameraListResponse", "CameraResponse", "CameraStatus", "CameraUpdate"]


class CameraCreate(BaseModel):
    """Schema for creating a new camera."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Front Door Camera",
                "folder_path": "/export/foscam/front_door",
                "status": "online",
            }
        }
    )

    name: str = Field(..., min_length=1, max_length=255, description="Camera name")
    folder_path: str = Field(
        ..., min_length=1, max_length=500, description="File system path for camera uploads"
    )
    status: CameraStatus = Field(
        default=CameraStatus.ONLINE,
        description="Camera status (online, offline, error, unknown)",
    )


class CameraUpdate(BaseModel):
    """Schema for updating an existing camera."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Front Door Camera - Updated",
                "status": "offline",
            }
        }
    )

    name: str | None = Field(None, min_length=1, max_length=255, description="Camera name")
    folder_path: str | None = Field(
        None, min_length=1, max_length=500, description="File system path for camera uploads"
    )
    status: CameraStatus | None = Field(
        None, description="Camera status (online, offline, error, unknown)"
    )


class CameraResponse(BaseModel):
    """Schema for camera response."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Front Door Camera",
                "folder_path": "/export/foscam/front_door",
                "status": "online",
                "created_at": "2025-12-23T10:00:00Z",
                "last_seen_at": "2025-12-23T12:00:00Z",
            }
        },
    )

    id: str = Field(..., description="Camera UUID")
    name: str = Field(..., description="Camera name")
    folder_path: str = Field(..., description="File system path for camera uploads")
    status: CameraStatus = Field(..., description="Camera status (online, offline, error, unknown)")
    created_at: datetime = Field(..., description="Timestamp when camera was created")
    last_seen_at: datetime | None = Field(None, description="Last time camera was active")


class CameraListResponse(BaseModel):
    """Schema for camera list response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cameras": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "name": "Front Door Camera",
                        "folder_path": "/export/foscam/front_door",
                        "status": "online",
                        "created_at": "2025-12-23T10:00:00Z",
                        "last_seen_at": "2025-12-23T12:00:00Z",
                    }
                ],
                "count": 1,
            }
        }
    )

    cameras: list[CameraResponse] = Field(..., description="List of cameras")
    count: int = Field(..., description="Total number of cameras")
