"""Pydantic schemas for camera API endpoints.

NEM-2569: Enhanced Pydantic validation with explicit validators and field constraints
for comprehensive server-side input validation.
"""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.api.schemas.pagination import PaginationMeta
from backend.models.enums import CameraStatus

# Re-export CameraStatus for convenient imports from this module
__all__ = [
    "CameraCreate",
    "CameraListResponse",
    "CameraPathValidationResponse",
    "CameraResponse",
    "CameraStatus",
    "CameraUpdate",
    "CameraValidationInfo",
    "DeletedCamerasListResponse",
]

# Regex pattern for forbidden path characters (beyond path traversal)
# Allow alphanumeric, underscore, hyphen, slash, and dots (but not ..)
_FORBIDDEN_PATH_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')

# Regex pattern for forbidden name characters
# Reject control characters (0x00-0x1f, 0x7f), including null, tab, newline, etc.
_FORBIDDEN_NAME_CHARS = re.compile(r"[\x00-\x1f\x7f]")


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


def _validate_camera_name(v: str) -> str:
    """Validate and sanitize camera name.

    NEM-2569: Added explicit name validation for security and data quality.

    Args:
        v: The camera name string to validate

    Returns:
        The validated and sanitized camera name (with leading/trailing whitespace stripped)

    Raises:
        ValueError: If name contains control characters or is whitespace-only
    """
    # Strip leading/trailing whitespace
    stripped = v.strip()

    # Check if name is effectively empty after stripping
    if not stripped:
        raise ValueError("Camera name cannot be empty or whitespace-only")

    # Check for forbidden control characters (including null, tab, newline, etc.)
    if _FORBIDDEN_NAME_CHARS.search(v):
        raise ValueError(
            "Camera name contains forbidden characters (control characters like null, tab, or newline)"
        )

    return stripped


class CameraCreate(BaseModel):
    """Schema for creating a new camera.

    NEM-2569: Enhanced with explicit Pydantic validators for:
    - Name: Control character rejection, whitespace stripping, empty validation
    - Folder path: Path traversal prevention, forbidden character rejection
    """

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

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate and sanitize camera name.

        NEM-2569: Rejects control characters, strips whitespace.
        """
        return _validate_camera_name(v)

    @field_validator("folder_path")
    @classmethod
    def validate_folder_path(cls, v: str) -> str:
        """Validate folder_path for security."""
        return _validate_folder_path(v)


class CameraUpdate(BaseModel):
    """Schema for updating an existing camera.

    NEM-2569: Enhanced with explicit Pydantic validators for partial updates.
    All fields are optional; only provided fields are validated.
    """

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

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        """Validate and sanitize camera name for updates.

        NEM-2569: Rejects control characters, strips whitespace.
        Returns None unchanged for partial updates.
        """
        if v is None:
            return v
        return _validate_camera_name(v)

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


class CameraValidationInfo(BaseModel):
    """Schema for individual camera validation result.

    NEM-2063: Response model for camera path validation details.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "front_door",
                "name": "Front Door Camera",
                "folder_path": "/export/foscam/front_door",
                "status": "online",
                "resolved_path": "/export/foscam/front_door",
                "issues": ["directory does not exist"],
            }
        }
    )

    id: str = Field(..., description="Camera ID")
    name: str = Field(..., description="Camera name")
    folder_path: str = Field(..., description="Configured folder path")
    status: CameraStatus = Field(..., description="Camera status")
    resolved_path: str | None = Field(
        None, description="Resolved absolute path (included if path is outside base_path)"
    )
    issues: list[str] | None = Field(
        None, description="List of validation issues (only for invalid cameras)"
    )


class CameraPathValidationResponse(BaseModel):
    """Schema for camera path validation response.

    NEM-2063: Response model for the /api/cameras/validation/paths endpoint.
    Validates all camera folder paths against the configured base path.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "base_path": "/export/foscam",
                "total_cameras": 6,
                "valid_count": 4,
                "invalid_count": 2,
                "valid_cameras": [
                    {
                        "id": "front_door",
                        "name": "Front Door Camera",
                        "folder_path": "/export/foscam/front_door",
                        "status": "online",
                    }
                ],
                "invalid_cameras": [
                    {
                        "id": "garage",
                        "name": "Garage Camera",
                        "folder_path": "/export/foscam/garage",
                        "status": "offline",
                        "issues": ["directory does not exist"],
                    }
                ],
            }
        }
    )

    base_path: str = Field(..., description="Configured base path for camera folders")
    total_cameras: int = Field(..., description="Total number of cameras validated")
    valid_count: int = Field(..., description="Number of cameras with valid paths")
    invalid_count: int = Field(..., description="Number of cameras with invalid paths")
    valid_cameras: list[CameraValidationInfo] = Field(..., description="Cameras with valid paths")
    invalid_cameras: list[CameraValidationInfo] = Field(
        ..., description="Cameras with validation issues"
    )
