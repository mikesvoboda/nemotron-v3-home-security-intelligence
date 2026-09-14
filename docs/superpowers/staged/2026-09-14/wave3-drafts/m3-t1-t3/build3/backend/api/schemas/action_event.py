"""Pydantic schemas for action events API endpoints.

This module provides schemas for X-CLIP action recognition results,
including request/response validation for action event CRUD operations
and action analysis endpoints.

Linear issue: NEM-3714
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from backend.api.schemas.pagination import PaginationMeta


class ActionEventBase(BaseModel):
    """Base schema for action event fields.

    Contains common fields shared between create and response schemas.
    """

    camera_id: str = Field(..., description="Camera ID where the action was detected")
    track_id: int | None = Field(None, description="Optional track ID for the detected person")
    action: str = Field(
        ..., description="Detected action label (e.g., 'walking normally', 'climbing')"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Action classification confidence (0.0 to 1.0)"
    )
    is_suspicious: bool = Field(
        False, description="Whether the action is flagged as security-relevant"
    )
    frame_count: int = Field(8, ge=1, description="Number of frames analyzed for this action")
    all_scores: dict[str, float] | None = Field(
        None, description="Dictionary mapping all action classes to their confidence scores"
    )


class ActionEventCreate(ActionEventBase):
    """Schema for creating a new action event.

    Inherits all fields from ActionEventBase. The timestamp will be
    auto-generated if not provided.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "camera_id": "front_door",
                "track_id": 42,
                "action": "walking normally",
                "confidence": 0.89,
                "is_suspicious": False,
                "frame_count": 8,
                "all_scores": {
                    "walking normally": 0.89,
                    "running": 0.05,
                    "climbing": 0.02,
                    "loitering": 0.04,
                },
            }
        }
    )

    timestamp: datetime | None = Field(
        None, description="When the action was detected (auto-generated if not provided)"
    )


class ActionEventResponse(ActionEventBase):
    """Schema for action event response.

    Includes all base fields plus server-generated fields like id and timestamps.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "camera_id": "front_door",
                "track_id": 42,
                "action": "walking normally",
                "confidence": 0.89,
                "is_suspicious": False,
                "timestamp": "2026-01-26T12:00:00Z",
                "frame_count": 8,
                "all_scores": {
                    "walking normally": 0.89,
                    "running": 0.05,
                    "climbing": 0.02,
                    "loitering": 0.04,
                },
                "created_at": "2026-01-26T12:00:00Z",
            }
        },
    )

    id: int = Field(..., description="Action event ID")
    timestamp: datetime = Field(..., description="When the action was detected")
    created_at: datetime = Field(..., description="Record creation timestamp")


class ActionEventListResponse(BaseModel):
    """Schema for action event list response with pagination.

    Uses the standard pagination envelope pattern.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": 1,
                        "camera_id": "front_door",
                        "track_id": 42,
                        "action": "walking normally",
                        "confidence": 0.89,
                        "is_suspicious": False,
                        "timestamp": "2026-01-26T12:00:00Z",
                        "frame_count": 8,
                        "all_scores": None,
                        "created_at": "2026-01-26T12:00:00Z",
                    }
                ],
                "pagination": {
                    "total": 1,
                    "limit": 50,
                    "offset": 0,
                    "has_more": False,
                },
            }
        }
    )

    items: list[ActionEventResponse] = Field(..., description="List of action events")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")


class ActionAnalyzeRequest(BaseModel):
    """Schema for action analysis request.

    Used to trigger action recognition on a set of frames.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "camera_id": "front_door",
                "frame_paths": [
                    "/export/foscam/front_door/frame_001.jpg",
                    "/export/foscam/front_door/frame_002.jpg",
                    "/export/foscam/front_door/frame_003.jpg",
                    "/export/foscam/front_door/frame_004.jpg",
                    "/export/foscam/front_door/frame_005.jpg",
                    "/export/foscam/front_door/frame_006.jpg",
                    "/export/foscam/front_door/frame_007.jpg",
                    "/export/foscam/front_door/frame_008.jpg",
                ],
                "track_id": 42,
                "confidence_threshold": 0.5,
            }
        }
    )

    camera_id: str = Field(..., description="Camera ID for the frames")
    frame_paths: list[str] = Field(
        ...,
        min_length=1,
        max_length=32,
        description="List of frame file paths to analyze (1-32 frames)",
    )
    track_id: int | None = Field(None, description="Optional track ID to associate with the action")
    confidence_threshold: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for creating an action event",
    )
    save_event: bool = Field(
        True,
        description="Whether to save the action event to the database",
    )


class ActionAnalyzeResponse(BaseModel):
    """Schema for action analysis response.

    Returns the detected action along with all scores and optional saved event.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "action": "walking normally",
                "confidence": 0.89,
                "is_suspicious": False,
                "all_scores": {
                    "walking normally": 0.89,
                    "running": 0.05,
                    "climbing": 0.02,
                    "loitering": 0.04,
                },
                "frame_count": 8,
                "event_id": 1,
                "saved": True,
            }
        }
    )

    action: str = Field(..., description="Detected action label")
    confidence: float = Field(..., description="Action classification confidence")
    is_suspicious: bool = Field(..., description="Whether the action is security-relevant")
    all_scores: dict[str, float] = Field(..., description="All action scores")
    frame_count: int = Field(..., description="Number of frames analyzed")
    event_id: int | None = Field(None, description="Saved action event ID (if save_event=True)")
    saved: bool = Field(..., description="Whether the event was saved to the database")


class SuspiciousActionsResponse(BaseModel):
    """Schema for suspicious actions summary response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": 5,
                        "camera_id": "back_yard",
                        "track_id": 17,
                        "action": "climbing",
                        "confidence": 0.92,
                        "is_suspicious": True,
                        "timestamp": "2026-01-26T14:30:00Z",
                        "frame_count": 8,
                        "all_scores": {"climbing": 0.92, "walking normally": 0.05},
                        "created_at": "2026-01-26T14:30:00Z",
                    }
                ],
                "pagination": {
                    "total": 1,
                    "limit": 50,
                    "offset": 0,
                    "has_more": False,
                },
                "suspicious_count": 1,
                "total_count": 25,
            }
        }
    )

    items: list[ActionEventResponse] = Field(..., description="List of suspicious action events")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")
    suspicious_count: int = Field(..., description="Total count of suspicious actions")
    total_count: int = Field(..., description="Total count of all action events")


# List of suspicious action types for reference (from ai/enrichment/models/action_recognizer.py)
SUSPICIOUS_ACTIONS = [
    "fighting",
    "climbing",
    "breaking window",
    "picking lock",
    "hiding",
    "loitering",
    "looking around suspiciously",
]
