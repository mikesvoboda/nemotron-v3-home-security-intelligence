"""Pydantic schemas for detections API endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DetectionResponse(BaseModel):
    """Schema for detection response."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "camera_id": "123e4567-e89b-12d3-a456-426614174000",
                "file_path": "/export/foscam/front_door/20251223_120000.jpg",
                "file_type": "image/jpeg",
                "detected_at": "2025-12-23T12:00:00Z",
                "object_type": "person",
                "confidence": 0.95,
                "bbox_x": 100,
                "bbox_y": 150,
                "bbox_width": 200,
                "bbox_height": 400,
                "thumbnail_path": "/data/thumbnails/1_thumb.jpg",
                "media_type": "image",
                "duration": None,
                "video_codec": None,
                "video_width": None,
                "video_height": None,
            }
        },
    )

    id: int = Field(..., description="Detection ID")
    camera_id: str = Field(..., description="Camera UUID")
    file_path: str = Field(..., description="Path to source image or video file")
    file_type: str | None = Field(None, description="MIME type of source file")
    detected_at: datetime = Field(..., description="Timestamp when detection was made")
    object_type: str | None = Field(None, description="Type of detected object (person, car, etc.)")
    confidence: float | None = Field(None, description="Detection confidence score (0-1)")
    bbox_x: int | None = Field(None, description="Bounding box X coordinate")
    bbox_y: int | None = Field(None, description="Bounding box Y coordinate")
    bbox_width: int | None = Field(None, description="Bounding box width")
    bbox_height: int | None = Field(None, description="Bounding box height")
    thumbnail_path: str | None = Field(
        None, description="Path to thumbnail image with bbox overlay"
    )
    # Video-specific fields
    media_type: str | None = Field("image", description="Media type: 'image' or 'video'")
    duration: float | None = Field(None, description="Video duration in seconds (video only)")
    video_codec: str | None = Field(None, description="Video codec (e.g., h264, hevc)")
    video_width: int | None = Field(None, description="Video resolution width")
    video_height: int | None = Field(None, description="Video resolution height")


class DetectionListResponse(BaseModel):
    """Schema for detection list response with pagination."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detections": [
                    {
                        "id": 1,
                        "camera_id": "123e4567-e89b-12d3-a456-426614174000",
                        "file_path": "/export/foscam/front_door/20251223_120000.jpg",
                        "file_type": "image/jpeg",
                        "detected_at": "2025-12-23T12:00:00Z",
                        "object_type": "person",
                        "confidence": 0.95,
                        "bbox_x": 100,
                        "bbox_y": 150,
                        "bbox_width": 200,
                        "bbox_height": 400,
                        "thumbnail_path": "/data/thumbnails/1_thumb.jpg",
                    }
                ],
                "count": 1,
                "limit": 50,
                "offset": 0,
            }
        }
    )

    detections: list[DetectionResponse] = Field(..., description="List of detections")
    count: int = Field(..., description="Total number of detections matching filters")
    limit: int = Field(..., description="Maximum number of results returned")
    offset: int = Field(..., description="Number of results skipped")
