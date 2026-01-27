"""Pydantic schemas for detections API endpoints."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.api.schemas.pagination import PaginationMeta

# ============================================================================
# Enrichment Data Schemas (NEM-1067)
# ============================================================================
# These schemas provide type safety and validation for the enrichment_data
# JSONB field stored in Detection records.


class VehicleEnrichmentData(BaseModel):
    """Schema for vehicle enrichment data in detection records.

    Used to validate and type vehicle-related enrichment data extracted
    from the AI pipeline (vehicle classification, damage detection).
    """

    model_config = ConfigDict(
        extra="ignore",  # Ignore extra fields for backward compatibility
        json_schema_extra={
            "example": {
                "vehicle_type": "sedan",
                "vehicle_color": "blue",
                "has_damage": False,
                "is_commercial": False,
            }
        },
    )

    vehicle_type: str | None = Field(
        None, description="Type of vehicle (sedan, suv, truck, van, etc.)"
    )
    vehicle_color: str | None = Field(None, description="Primary color of the vehicle")
    has_damage: bool = Field(False, description="Whether vehicle damage was detected")
    is_commercial: bool = Field(False, description="Whether the vehicle is commercial/delivery")


class PersonEnrichmentData(BaseModel):
    """Schema for person enrichment data in detection records.

    Used to validate and type person-related enrichment data extracted
    from the AI pipeline (clothing classification, action recognition).
    """

    model_config = ConfigDict(
        extra="ignore",  # Ignore extra fields for backward compatibility
        json_schema_extra={
            "example": {
                "clothing_description": "dark jacket, blue jeans",
                "action": "walking",
                "carrying": ["backpack"],
                "is_suspicious": False,
            }
        },
    )

    clothing_description: str | None = Field(
        None, description="Description of clothing (upper, lower)"
    )
    action: str | None = Field(None, description="Detected action (walking, running, standing)")
    carrying: list[str] = Field(
        default_factory=list, description="List of items person is carrying"
    )
    is_suspicious: bool = Field(False, description="Whether appearance is flagged as suspicious")


class PetEnrichmentData(BaseModel):
    """Schema for pet enrichment data in detection records.

    Used to validate and type pet-related enrichment data for
    false positive reduction (distinguishing pets from intruders).
    """

    model_config = ConfigDict(
        extra="ignore",  # Ignore extra fields for backward compatibility
        json_schema_extra={
            "example": {
                "pet_type": "dog",
                "breed": "golden retriever",
            }
        },
    )

    pet_type: str | None = Field(None, description="Type of pet (dog, cat)")
    breed: str | None = Field(None, description="Detected breed if identifiable")


class EnrichmentDataSchema(BaseModel):
    """Schema for the composite enrichment_data JSONB field.

    This schema provides type safety for the enrichment_data field
    on DetectionResponse, ensuring consistent structure and validation
    of AI pipeline results.
    """

    model_config = ConfigDict(
        extra="ignore",  # Ignore extra fields for backward compatibility
        json_schema_extra={
            "example": {
                "vehicle": {
                    "vehicle_type": "sedan",
                    "vehicle_color": "blue",
                    "has_damage": False,
                    "is_commercial": False,
                },
                "person": {
                    "clothing_description": "dark jacket",
                    "action": "walking",
                    "carrying": ["backpack"],
                    "is_suspicious": False,
                },
                "pet": None,
                "weather": "sunny",
                "errors": [],
            }
        },
    )

    vehicle: VehicleEnrichmentData | None = Field(
        None, description="Vehicle classification and damage detection results"
    )
    person: PersonEnrichmentData | None = Field(
        None, description="Person clothing and action recognition results"
    )
    pet: PetEnrichmentData | None = Field(
        None, description="Pet classification results for false positive reduction"
    )
    weather: str | None = Field(
        None, description="Weather condition classification (sunny, cloudy, rainy)"
    )
    errors: list[str] = Field(
        default_factory=list, description="Errors encountered during enrichment"
    )


class DetectionResponse(BaseModel):
    """Schema for detection response."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "camera_id": "front_door",
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
                "enrichment_data": {
                    "vehicle": {
                        "vehicle_type": "sedan",
                        "vehicle_color": "blue",
                        "has_damage": False,
                        "is_commercial": False,
                    },
                    "person": {
                        "clothing_description": "dark jacket",
                        "action": "walking",
                        "carrying": ["backpack"],
                        "is_suspicious": False,
                    },
                    "pet": None,
                    "weather": "sunny",
                    "errors": [],
                },
            }
        },
    )

    id: int = Field(..., description="Detection ID")
    camera_id: str = Field(..., description="Normalized camera ID (e.g., 'front_door')")
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

    # Object tracking fields (for multi-object tracking across frames)
    track_id: int | None = Field(
        None, description="Unique track ID for tracking objects across frames"
    )
    track_confidence: float | None = Field(
        None, description="Confidence score for the track assignment (0-1)"
    )

    # AI enrichment data (vehicle classification, pet identification, etc.)
    # Kept as dict for backward compatibility - use validate_enrichment_data() to get typed data
    enrichment_data: dict[str, Any] | None = Field(
        None,
        description="AI enrichment data including vehicle classification, pet identification, "
        "person attributes, license plates, weather, and image quality scores",
    )

    # Junction table timestamp (NEM-3629)
    # When fetching detections for an event with order_detections_by=created_at,
    # this field contains the timestamp when the detection was associated with the event.
    # Useful for showing detection order within an event (first, second, etc.)
    association_created_at: datetime | None = Field(
        None,
        description="Timestamp when detection was associated with the event (NEM-3629). "
        "Only populated when fetching detections for an event with order_detections_by=created_at.",
    )

    def model_dump_list(self) -> dict:
        """Serialize for list views (exclude detail-only fields).

        Excludes large fields like enrichment_data that are only needed
        in detail views. This reduces payload size for list responses.

        Returns:
            Dictionary with list view fields only, None values excluded.
        """
        return self.model_dump(
            exclude={"enrichment_data"},
            exclude_none=True,
        )

    def model_dump_detail(self) -> dict:
        """Serialize for detail views (include all fields).

        Includes all fields including large detail-only fields like
        enrichment_data.

        Returns:
            Dictionary with all fields, None values excluded.
        """
        return self.model_dump(exclude_none=True)


class DetectionListResponse(BaseModel):
    """Schema for detection list response with standardized pagination envelope.

    Uses the standard pagination envelope: {"items": [...], "pagination": {...}}
    Supports both cursor-based pagination (recommended) and offset pagination (deprecated).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": 1,
                        "camera_id": "front_door",
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
                "pagination": {
                    "total": 1,
                    "limit": 50,
                    "offset": 0,
                    "next_cursor": "eyJpZCI6IDEsICJjcmVhdGVkX2F0IjogIjIwMjUtMTItMjNUMTI6MDA6MDBaIn0=",  # pragma: allowlist secret
                    "has_more": False,
                },
            }
        }
    )

    items: list[DetectionResponse] = Field(..., description="List of detections")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")
    deprecation_warning: str | None = Field(
        default=None,
        description="Warning message when using deprecated offset pagination",
    )


class ObjectClassDistributionItem(BaseModel):
    """Schema for a single object class distribution item (for Grafana compatibility)."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"object_class": "person", "count": 23}}
    )

    object_class: str = Field(..., description="Object class name (e.g., person, car)")
    count: int = Field(..., description="Number of detections of this class")


class DetectionTrendItem(BaseModel):
    """Schema for a single detection trend data point (for Grafana time series).

    Used by the Grafana Analytics dashboard to display detection trends over time.
    The timestamp field is Unix epoch milliseconds for Grafana JSON datasource compatibility.
    """

    model_config = ConfigDict(
        json_schema_extra={"example": {"timestamp": 1737504000000, "detection_count": 50}}
    )

    timestamp: int = Field(
        ..., description="Unix epoch milliseconds for the trend data point (start of day)"
    )
    detection_count: int = Field(..., description="Number of detections on this date")


class DetectionStatsResponse(BaseModel):
    """Schema for detection statistics response.

    Returns aggregate statistics about detections including counts by object class
    and detection trends over time. Used by the AI Performance page and Grafana
    Analytics dashboard.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_detections": 107,
                "detections_by_class": {
                    "person": 23,
                    "car": 20,
                    "truck": 6,
                    "bicycle": 1,
                },
                "object_class_distribution": [
                    {"object_class": "person", "count": 23},
                    {"object_class": "car", "count": 20},
                    {"object_class": "truck", "count": 6},
                    {"object_class": "bicycle", "count": 1},
                ],
                "average_confidence": 0.87,
                "trends": [
                    {"timestamp": "2026-01-16T00:00:00Z", "detection_count": 10},
                    {"timestamp": "2026-01-17T00:00:00Z", "detection_count": 15},
                    {"timestamp": "2026-01-18T00:00:00Z", "detection_count": 12},
                    {"timestamp": "2026-01-19T00:00:00Z", "detection_count": 8},
                    {"timestamp": "2026-01-20T00:00:00Z", "detection_count": 20},
                    {"timestamp": "2026-01-21T00:00:00Z", "detection_count": 25},
                    {"timestamp": "2026-01-22T00:00:00Z", "detection_count": 50},
                ],
            }
        }
    )

    total_detections: int = Field(..., description="Total number of detections")
    detections_by_class: dict[str, int] = Field(
        ..., description="Detection counts grouped by object class (e.g., person, car, truck)"
    )
    object_class_distribution: list[ObjectClassDistributionItem] = Field(
        default_factory=list,
        description="Detections by class as array (for Grafana compatibility)",
    )
    average_confidence: float | None = Field(
        None, description="Average confidence score across all detections"
    )
    trends: list[DetectionTrendItem] = Field(
        default_factory=list,
        description="Detection counts by day for the last 7 days (for Grafana time series)",
    )


# Search Schemas (NEM-1986)


class DetectionSearchResult(BaseModel):
    """Schema for a single detection search result."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Detection ID")
    camera_id: str = Field(..., description="Camera ID")
    object_type: str | None = Field(None, description="Detected object type")
    confidence: float | None = Field(None, description="Detection confidence score")
    detected_at: datetime = Field(..., description="Detection timestamp")
    file_path: str = Field(..., description="Path to source file")
    thumbnail_path: str | None = Field(None, description="Path to thumbnail")
    relevance_score: float = Field(default=0.0, description="Search relevance score")
    labels: list[str] = Field(default_factory=list, description="Searchable labels")
    bbox_x: int | None = Field(None)
    bbox_y: int | None = Field(None)
    bbox_width: int | None = Field(None)
    bbox_height: int | None = Field(None)
    enrichment_data: dict[str, Any] | None = Field(None)
    track_id: int | None = Field(
        None, description="Unique track ID for tracking objects across frames"
    )
    track_confidence: float | None = Field(
        None, description="Confidence score for the track assignment (0-1)"
    )


class DetectionSearchResponse(BaseModel):
    """Schema for detection search response."""

    results: list[DetectionSearchResult] = Field(..., description="Search results")
    total_count: int = Field(..., description="Total matching detections")
    limit: int = Field(...)
    offset: int = Field(...)


class DetectionLabelCount(BaseModel):
    """Schema for a label with count."""

    label: str = Field(...)
    count: int = Field(...)


class DetectionLabelsResponse(BaseModel):
    """Schema for detection labels response."""

    labels: list[DetectionLabelCount] = Field(...)
