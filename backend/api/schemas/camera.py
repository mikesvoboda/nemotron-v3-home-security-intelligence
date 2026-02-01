"""Pydantic schemas for camera API endpoints.

NEM-2569: Enhanced Pydantic validation with explicit validators and field constraints
for comprehensive server-side input validation.
"""

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.api.schemas.pagination import PaginationMeta
from backend.models.enums import CameraStatus

# Re-export CameraStatus for convenient imports from this module
__all__ = [
    "AreaBasic",
    "BaselineConfigUpdate",
    "CameraCreate",
    "CameraListResponse",
    "CameraPathValidationResponse",
    "CameraResponse",
    "CameraStatus",
    "CameraUpdate",
    "CameraValidationInfo",
    "DeletedCamerasListResponse",
    "PreviewStartRequest",
    "PreviewStartResponse",
    "RTSPCapabilitiesResponse",
    "RTSPTestRequest",
    "RTSPTestResponse",
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


class AreaBasic(BaseModel):
    """Minimal area schema for embedding in CameraResponse.

    NEM-3597: Basic area information for API responses that include
    camera-area relationships without full area details.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "name": "Front Yard",
            }
        },
    )

    id: int = Field(..., description="Unique area identifier")
    name: str = Field(..., description="Area name")


def _validate_rtsp_url(v: str | None) -> str | None:
    """Validate RTSP URL format.

    Validates that RTSP URLs use rtsp:// or rtsps:// scheme and have a valid host.
    """
    if v is None:
        return v

    if not v.startswith(("rtsp://", "rtsps://")):
        raise ValueError("rtsp_url must use rtsp:// or rtsps:// scheme")

    import urllib.parse

    parsed = urllib.parse.urlparse(v)
    if not parsed.netloc:
        raise ValueError("rtsp_url must have a valid host")

    return v


def _validate_motion_sensitivity(v: float) -> float:
    """Validate motion_sensitivity is between 0.0 and 1.0."""
    if not 0.0 <= v <= 1.0:
        raise ValueError("motion_sensitivity must be between 0.0 and 1.0")
    return v


# Valid ingestion modes
VALID_INGESTION_MODES = ("ftp", "rtsp", "onvif")

# Valid stream profiles
VALID_STREAM_PROFILES = ("main", "sub", "both")


class CameraCreate(BaseModel):
    """Schema for creating a new camera.

    NEM-2569: Enhanced with explicit Pydantic validators for:
    - Name: Control character rejection, whitespace stripping, empty validation
    - Folder path: Path traversal prevention, forbidden character rejection

    NEM-4191: Added RTSP/ONVIF streaming fields:
    - ingestion_mode: How images are acquired (ftp, rtsp, onvif)
    - rtsp_url: RTSP stream URL
    - rtsp_username/rtsp_password: RTSP credentials
    - stream_profile: Which stream profile to use (main, sub, both)
    - motion_sensitivity: Motion detection sensitivity (0.0-1.0)
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Front Door Camera",
                "folder_path": "/export/foscam/front_door",
                "status": "online",
                "ingestion_mode": "ftp",
                "motion_sensitivity": 0.5,
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

    # RTSP/ONVIF streaming fields (NEM-4191)
    ingestion_mode: Literal["ftp", "rtsp", "onvif"] = Field(
        default="ftp",
        description="Camera ingestion mode (ftp, rtsp, onvif)",
    )
    rtsp_url: str | None = Field(
        default=None,
        description="RTSP stream URL (rtsp:// or rtsps://)",
    )
    rtsp_username: str | None = Field(
        default=None,
        description="RTSP authentication username",
    )
    rtsp_password: str | None = Field(
        default=None,
        description="RTSP authentication password",
    )
    stream_profile: Literal["main", "sub", "both"] | None = Field(
        default=None,
        description="Stream profile to use (main, sub, both)",
    )
    motion_sensitivity: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Motion detection sensitivity (0.0-1.0)",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate and sanitize camera name."""
        return _validate_camera_name(v)

    @field_validator("folder_path")
    @classmethod
    def validate_folder_path(cls, v: str) -> str:
        """Validate folder_path for security."""
        return _validate_folder_path(v)

    @field_validator("rtsp_url")
    @classmethod
    def validate_rtsp_url(cls, v: str | None) -> str | None:
        """Validate RTSP URL format."""
        return _validate_rtsp_url(v)

    @model_validator(mode="after")
    def validate_rtsp_url_required_for_streaming_modes(self) -> CameraCreate:
        """Validate rtsp_url is required when ingestion_mode is rtsp or onvif."""
        if "rtsp_url" in self.model_fields_set:
            if self.ingestion_mode in ("rtsp", "onvif") and self.rtsp_url is None:
                raise ValueError("rtsp_url is required when ingestion_mode is 'rtsp' or 'onvif'")
        return self


class CameraUpdate(BaseModel):
    """Schema for updating an existing camera.

    NEM-2569: Enhanced with explicit Pydantic validators for partial updates.
    All fields are optional; only provided fields are validated.

    NEM-4191: Added RTSP/ONVIF streaming fields for partial updates.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Front Door Camera - Updated",
                "status": "offline",
                "ingestion_mode": "rtsp",
                "rtsp_url": "rtsp://192.168.1.100:554/stream1",
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

    # RTSP/ONVIF streaming fields (NEM-4191)
    ingestion_mode: Literal["ftp", "rtsp", "onvif"] | None = Field(
        default=None,
        description="Camera ingestion mode (ftp, rtsp, onvif)",
    )
    rtsp_url: str | None = Field(
        default=None,
        description="RTSP stream URL (rtsp:// or rtsps://)",
    )
    rtsp_username: str | None = Field(
        default=None,
        description="RTSP authentication username",
    )
    rtsp_password: str | None = Field(
        default=None,
        description="RTSP authentication password",
    )
    stream_profile: Literal["main", "sub", "both"] | None = Field(
        default=None,
        description="Stream profile to use (main, sub, both)",
    )
    motion_sensitivity: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Motion detection sensitivity (0.0-1.0)",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        """Validate and sanitize camera name for updates."""
        return _validate_camera_name(v) if v is not None else v

    @field_validator("folder_path")
    @classmethod
    def validate_folder_path(cls, v: str | None) -> str | None:
        """Validate folder_path for security."""
        return _validate_folder_path(v) if v is not None else v

    @field_validator("rtsp_url")
    @classmethod
    def validate_rtsp_url(cls, v: str | None) -> str | None:
        """Validate RTSP URL format for updates."""
        return _validate_rtsp_url(v)


class CameraResponse(BaseModel):
    """Schema for camera response.

    NEM-3597: Added property_id and areas fields to expose camera relationships.
    NEM-4191: Added RTSP/ONVIF streaming fields.
    """

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
                "property_id": 1,
                "areas": [{"id": 1, "name": "Front Yard"}],
                "ingestion_mode": "ftp",
                "rtsp_url": None,
                "rtsp_username": None,
                "rtsp_password": None,
                "stream_profile": None,
                "motion_sensitivity": 0.5,
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
    property_id: int | None = Field(None, description="ID of the property this camera belongs to")
    areas: list[AreaBasic] | None = Field(
        None, description="List of areas this camera is assigned to"
    )

    # RTSP/ONVIF streaming fields (NEM-4191)
    ingestion_mode: str = Field(
        default="ftp",
        description="Camera ingestion mode (ftp, rtsp, onvif)",
    )
    rtsp_url: str | None = Field(
        default=None,
        description="RTSP stream URL (rtsp:// or rtsps://)",
    )
    rtsp_username: str | None = Field(
        default=None,
        description="RTSP authentication username",
    )
    rtsp_password: str | None = Field(
        default=None,
        description="RTSP authentication password",
    )
    stream_profile: str | None = Field(
        default=None,
        description="Stream profile to use (main, sub, both)",
    )
    motion_sensitivity: float = Field(
        default=0.5,
        description="Motion detection sensitivity (0.0-1.0)",
    )


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


# =============================================================================
# RTSP Connection Testing Schemas (NEM-4748)
# =============================================================================


class RTSPTestRequest(BaseModel):
    """Request schema for testing an RTSP connection.

    NEM-4748: Schema for POST /api/cameras/rtsp/test endpoint.
    Validates RTSP URL format and accepts optional credentials.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "rtsp_url": "rtsp://192.168.1.100:554/stream1",
                "username": "admin",
                "password": "password123",  # pragma: allowlist secret
            }
        }
    )

    rtsp_url: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="RTSP URL to test (rtsp:// or rtsps://)",
    )
    username: str | None = Field(
        default=None,
        max_length=100,
        description="Optional username for RTSP authentication",
    )
    password: str | None = Field(
        default=None,
        max_length=100,
        description="Optional password for RTSP authentication",
    )

    @field_validator("rtsp_url")
    @classmethod
    def validate_rtsp_url(cls, v: str) -> str:
        """Validate RTSP URL format."""
        result = _validate_rtsp_url(v)
        if result is None:
            raise ValueError("rtsp_url is required")
        return result


class RTSPCapabilitiesResponse(BaseModel):
    """Response schema for RTSP stream capabilities.

    NEM-4748: Detected capabilities of an RTSP stream including
    video/audio support, resolution, codec, and framerate.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "video": True,
                "audio": True,
                "ptz": False,
                "resolution": "1920x1080",
                "codec": "H.264",
                "fps": 30,
            }
        }
    )

    video: bool = Field(..., description="Whether the stream supports video")
    audio: bool = Field(..., description="Whether the stream supports audio")
    ptz: bool = Field(..., description="Whether PTZ control is available")
    resolution: str | None = Field(None, description="Stream resolution (e.g., '1920x1080')")
    codec: str = Field(..., description="Video codec (e.g., 'H.264', 'H.265')")
    fps: int | None = Field(None, description="Stream framerate")


class RTSPTestResponse(BaseModel):
    """Response schema for RTSP connection test result.

    NEM-4748: Result of testing an RTSP connection including
    success status, latency, capabilities, or error details.
    Note: Never includes password in response for security.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "latency_ms": 245,
                "capabilities": {
                    "video": True,
                    "audio": True,
                    "ptz": False,
                    "resolution": "1920x1080",
                    "codec": "H.264",
                    "fps": 30,
                },
                "error_message": None,
            }
        }
    )

    success: bool = Field(..., description="Whether the connection test succeeded")
    latency_ms: int | None = Field(None, description="Connection latency in milliseconds")
    capabilities: RTSPCapabilitiesResponse | None = Field(
        None, description="Stream capabilities (only present on success)"
    )
    error_message: str | None = Field(None, description="Error message (only present on failure)")


# =============================================================================
# RTSP Live Preview Schemas (NEM-4762)
# =============================================================================


class PreviewStartRequest(BaseModel):
    """Request schema for starting an RTSP preview.

    NEM-4762: Schema for POST /api/cameras/preview/start endpoint.
    Initiates WebRTC signaling with go2rtc for live preview.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "rtsp_url": "rtsp://192.168.1.100:554/stream1",
                "username": "admin",
                "password": "password123",  # pragma: allowlist secret
                "offer": "v=0\r\no=- ...",  # SDP offer
            }
        }
    )

    rtsp_url: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="RTSP URL for preview stream",
    )
    username: str | None = Field(
        default=None,
        max_length=100,
        description="Optional username for RTSP authentication",
    )
    password: str | None = Field(
        default=None,
        max_length=100,
        description="Optional password for RTSP authentication",
    )
    offer: str | None = Field(
        default=None,
        description="WebRTC SDP offer (optional, for direct signaling)",
    )

    @field_validator("rtsp_url")
    @classmethod
    def validate_rtsp_url(cls, v: str) -> str:
        """Validate RTSP URL format."""
        result = _validate_rtsp_url(v)
        if result is None:
            raise ValueError("rtsp_url is required")
        return result


class PreviewStartResponse(BaseModel):
    """Response schema for starting an RTSP preview.

    NEM-4762: Response from POST /api/cameras/preview/start endpoint.
    Contains WebRTC connection details and session info.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "webrtc_url": "ws://localhost:1984/api/ws?src=camera_front_door_abc123",
                "stream_id": "camera_front_door_abc123",
                "expires_in": 300,
                "sdp": "v=0\r\no=- ...",  # SDP answer
            }
        }
    )

    webrtc_url: str = Field(
        ...,
        description="WebRTC WebSocket URL for connecting to go2rtc",
    )
    stream_id: str = Field(
        ...,
        description="Unique stream identifier for cleanup",
    )
    expires_in: int = Field(
        ...,
        description="Session expiry time in seconds (default 300)",
    )
    sdp: str | None = Field(
        default=None,
        description="WebRTC SDP answer (if offer was provided)",
    )


# =============================================================================
# Baseline Configuration Schemas (NEM-4921)
# =============================================================================


class BaselineConfigUpdate(BaseModel):
    """Request schema for updating per-camera baseline configuration.

    NEM-4921: Schema for PUT /api/cameras/{camera_id}/baseline/config endpoint.
    All fields are optional; only provided fields are updated.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "threshold_stdev": 3.0,
                "min_samples": 15,
                "override_global_config": True,
            }
        }
    )

    threshold_stdev: float | None = Field(
        default=None,
        description="Anomaly detection threshold in standard deviations (minimum 0.5)",
    )
    min_samples: int | None = Field(
        default=None,
        description="Minimum samples required for reliable anomaly detection (minimum 1)",
    )
    override_global_config: bool | None = Field(
        default=None,
        description="Whether to use per-camera overrides instead of global defaults",
    )
