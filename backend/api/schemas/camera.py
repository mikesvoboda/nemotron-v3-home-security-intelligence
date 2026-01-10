"""Pydantic schemas for camera API endpoints."""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.api.schemas.pagination import PaginationMeta
from backend.models.enums import CameraStatus

# Re-export CameraStatus for convenient imports from this module
__all__ = [
    "CameraCreate",
    "CameraListResponse",
    "CameraResponse",
    "CameraStatus",
    "CameraUpdate",
    "DeletedCamerasListResponse",
]

# Regex pattern for forbidden path characters (beyond path traversal)
# Allow alphanumeric, underscore, hyphen, slash, and dots (but not ..)
_FORBIDDEN_PATH_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')


def _validate_folder_path(v: str) -> str:
    """Validate folder_path for security and correctness.

    Args:
        v: The folder path string to validate

    Returns:
        The validated folder path

    Raises:
        ValueError: If path traversal is detected, path is empty/too long,
                   or contains forbidden characters
    """
    # Check for path traversal attempts
    if ".." in v:
        raise ValueError("Path traversal (..) not allowed in folder_path")

    # Check path length (already enforced by Field max_length, but explicit check)
    if not v or len(v) > 500:
        raise ValueError("folder_path must be between 1 and 500 characters")

    # Check for forbidden characters
    if _FORBIDDEN_PATH_CHARS.search(v):
        raise ValueError(
            'folder_path contains forbidden characters (< > : " | ? * or control characters)'
        )

    return v


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

    @field_validator("folder_path")
    @classmethod
    def validate_folder_path(cls, v: str) -> str:
        """Validate folder_path for security."""
        return _validate_folder_path(v)


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

    @field_validator("folder_path")
    @classmethod
    def validate_folder_path(cls, v: str | None) -> str | None:
        """Validate folder_path for security."""
        if v is None:
            return v
        return _validate_folder_path(v)


class CameraResponse(BaseModel):
    """Schema for camera response."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "front_door",
                "name": "Front Door Camera",
                "folder_path": "/export/foscam/front_door",
                "status": "online",
                "created_at": "2025-12-23T10:00:00Z",
                "last_seen_at": "2025-12-23T12:00:00Z",
            }
        },
    )

    id: str = Field(
        ..., description="Normalized camera ID derived from folder name (e.g., 'front_door')"
    )
    name: str = Field(..., description="Camera name")
    folder_path: str = Field(..., description="File system path for camera uploads")
    status: CameraStatus = Field(..., description="Camera status (online, offline, error, unknown)")
    created_at: datetime = Field(..., description="Timestamp when camera was created")
    last_seen_at: datetime | None = Field(None, description="Last time camera was active")


class CameraListResponse(BaseModel):
    """Schema for camera list response.

    NEM-2075: Standardized pagination envelope with items + pagination structure.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "front_door",
                        "name": "Front Door Camera",
                        "folder_path": "/export/foscam/front_door",
                        "status": "online",
                        "created_at": "2025-12-23T10:00:00Z",
                        "last_seen_at": "2025-12-23T12:00:00Z",
                    }
                ],
                "pagination": {
                    "total": 1,
                    "limit": 50,
                    "offset": 0,
                    "cursor": None,
                    "next_cursor": None,
                    "has_more": False,
                },
            }
        }
    )

    items: list[CameraResponse] = Field(..., description="List of cameras")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")


class DeletedCamerasListResponse(BaseModel):
    """Schema for listing soft-deleted cameras (trash view).

    NEM-1955: Provides a trash view of soft-deleted cameras that can be restored.
    Cameras are ordered by deleted_at descending (most recently deleted first).
    NEM-2075: Standardized pagination envelope with items + pagination structure.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "front_door",
                        "name": "Front Door Camera",
                        "folder_path": "/export/foscam/front_door",
                        "status": "offline",
                        "created_at": "2025-12-23T10:00:00Z",
                        "last_seen_at": "2025-12-23T12:00:00Z",
                    }
                ],
                "pagination": {
                    "total": 1,
                    "limit": 50,
                    "offset": 0,
                    "cursor": None,
                    "next_cursor": None,
                    "has_more": False,
                },
            }
        }
    )

    items: list[CameraResponse] = Field(..., description="List of soft-deleted cameras")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")
