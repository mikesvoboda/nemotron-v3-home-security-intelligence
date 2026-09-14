"""Pydantic schemas for scene change API endpoints.

These schemas define the request/response models for scene change
detection and acknowledgement endpoints.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class SceneChangeType(str, Enum):
    """Type of scene change detected."""

    VIEW_BLOCKED = "view_blocked"
    ANGLE_CHANGED = "angle_changed"
    VIEW_TAMPERED = "view_tampered"
    UNKNOWN = "unknown"


class SceneChangeResponse(BaseModel):
    """Response schema for a single scene change.

    Represents a detected camera view change that may indicate
    tampering, angle changes, or blocked views.
    """

    id: int = Field(..., description="Unique scene change ID")
    detected_at: datetime = Field(..., description="When the scene change was detected")
    change_type: str = Field(
        ..., description="Type of change: view_blocked, angle_changed, view_tampered, unknown"
    )
    similarity_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="SSIM similarity score (0-1, lower means more different)",
    )
    acknowledged: bool = Field(
        default=False, description="Whether the change has been acknowledged"
    )
    acknowledged_at: datetime | None = Field(
        default=None, description="When the change was acknowledged"
    )
    file_path: str | None = Field(
        default=None, description="Path to the image that triggered detection"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "detected_at": "2026-01-03T10:30:00Z",
                "change_type": "view_blocked",
                "similarity_score": 0.23,
                "acknowledged": False,
                "acknowledged_at": None,
                "file_path": "/export/foscam/front_door/image.jpg",
            }
        },
    )


class SceneChangeListResponse(BaseModel):
    """Response schema for listing scene changes.

    Returns a list of scene changes for a camera with cursor-based pagination.
    """

    camera_id: str = Field(..., description="Camera ID")
    scene_changes: list[SceneChangeResponse] = Field(
        default_factory=list, description="List of scene changes"
    )
    total_changes: int = Field(default=0, ge=0, description="Number of scene changes returned")
    next_cursor: str | None = Field(
        default=None,
        description="Cursor for fetching the next page (ISO 8601 timestamp)",
    )
    has_more: bool = Field(
        default=False,
        description="Whether there are more results available",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "camera_id": "front_door",
                "scene_changes": [
                    {
                        "id": 1,
                        "detected_at": "2026-01-03T10:30:00Z",
                        "change_type": "view_blocked",
                        "similarity_score": 0.23,
                        "acknowledged": False,
                        "acknowledged_at": None,
                        "file_path": None,
                    }
                ],
                "total_changes": 1,
                "next_cursor": "2026-01-03T09:30:00Z",
                "has_more": True,
            }
        },
    )


class SceneChangeAcknowledgeResponse(BaseModel):
    """Response schema for acknowledging a scene change.

    Confirms that a scene change has been acknowledged.
    """

    id: int = Field(..., description="Scene change ID")
    acknowledged: bool = Field(default=True, description="Acknowledgement status (always True)")
    acknowledged_at: datetime = Field(..., description="When the change was acknowledged")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "acknowledged": True,
                "acknowledged_at": "2026-01-03T11:00:00Z",
            }
        },
    )
