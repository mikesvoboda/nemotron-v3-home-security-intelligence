"""Pydantic schemas for entity re-identification API endpoints.

Entity re-identification allows tracking the same person or vehicle
across multiple cameras using CLIP embeddings stored in Redis.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EntityAppearance(BaseModel):
    """Schema for a single entity appearance at a specific time and camera.

    Represents one sighting of an entity, including the detection it came from
    and additional attributes extracted from the image.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detection_id": "det_abc123",
                "camera_id": "front_door",
                "camera_name": "Front Door",
                "timestamp": "2025-12-23T14:30:00Z",
                "thumbnail_url": "/api/detections/123/image",
                "similarity_score": 0.92,
                "attributes": {"clothing": "blue jacket", "carrying": "backpack"},
            }
        }
    )

    detection_id: str = Field(..., description="Detection ID from original detection")
    camera_id: str = Field(..., description="Camera ID where entity was seen")
    camera_name: str | None = Field(None, description="Human-readable camera name")
    timestamp: datetime = Field(..., description="When the entity was detected")
    thumbnail_url: str | None = Field(None, description="URL to thumbnail image of this appearance")
    similarity_score: float | None = Field(
        None, ge=0.0, le=1.0, description="Similarity score to the entity's reference embedding"
    )
    attributes: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional attributes extracted from the detection (clothing, carrying, etc.)",
    )


class EntitySummary(BaseModel):
    """Schema for entity summary in list responses.

    Provides an overview of a tracked entity without the full appearance history.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "entity_abc123",
                "entity_type": "person",
                "first_seen": "2025-12-23T10:00:00Z",
                "last_seen": "2025-12-23T14:30:00Z",
                "appearance_count": 5,
                "cameras_seen": ["front_door", "backyard", "driveway"],
                "thumbnail_url": "/api/detections/123/image",
            }
        }
    )

    id: str = Field(..., description="Unique entity identifier")
    entity_type: str = Field(..., description="Type of entity: 'person' or 'vehicle'")
    first_seen: datetime = Field(..., description="Timestamp of first appearance")
    last_seen: datetime = Field(..., description="Timestamp of most recent appearance")
    appearance_count: int = Field(..., ge=0, description="Total number of appearances")
    cameras_seen: list[str] = Field(
        default_factory=list, description="List of camera IDs where entity was detected"
    )
    thumbnail_url: str | None = Field(None, description="URL to the most recent thumbnail image")


class EntityDetail(EntitySummary):
    """Schema for detailed entity information including appearance history.

    Extends EntitySummary with the full list of appearances.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "entity_abc123",
                "entity_type": "person",
                "first_seen": "2025-12-23T10:00:00Z",
                "last_seen": "2025-12-23T14:30:00Z",
                "appearance_count": 3,
                "cameras_seen": ["front_door", "backyard"],
                "thumbnail_url": "/api/detections/123/image",
                "appearances": [
                    {
                        "detection_id": "det_001",
                        "camera_id": "front_door",
                        "camera_name": "Front Door",
                        "timestamp": "2025-12-23T10:00:00Z",
                        "thumbnail_url": "/api/detections/1/image",
                        "similarity_score": 1.0,
                        "attributes": {"clothing": "blue jacket"},
                    },
                    {
                        "detection_id": "det_002",
                        "camera_id": "backyard",
                        "camera_name": "Backyard",
                        "timestamp": "2025-12-23T12:15:00Z",
                        "thumbnail_url": "/api/detections/2/image",
                        "similarity_score": 0.94,
                        "attributes": {"clothing": "blue jacket", "carrying": "bag"},
                    },
                ],
            }
        }
    )

    appearances: list[EntityAppearance] = Field(
        default_factory=list, description="List of all appearances for this entity"
    )


class EntityListResponse(BaseModel):
    """Schema for paginated entity list response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "entities": [
                    {
                        "id": "entity_abc123",
                        "entity_type": "person",
                        "first_seen": "2025-12-23T10:00:00Z",
                        "last_seen": "2025-12-23T14:30:00Z",
                        "appearance_count": 5,
                        "cameras_seen": ["front_door", "backyard"],
                        "thumbnail_url": "/api/detections/123/image",
                    }
                ],
                "count": 1,
                "limit": 50,
                "offset": 0,
            }
        }
    )

    entities: list[EntitySummary] = Field(..., description="List of tracked entities")
    count: int = Field(..., description="Total number of entities matching filters")
    limit: int = Field(..., description="Maximum number of results returned")
    offset: int = Field(..., description="Number of results skipped")


class EntityHistoryResponse(BaseModel):
    """Schema for entity appearance history response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "entity_id": "entity_abc123",
                "entity_type": "person",
                "appearances": [
                    {
                        "detection_id": "det_001",
                        "camera_id": "front_door",
                        "camera_name": "Front Door",
                        "timestamp": "2025-12-23T10:00:00Z",
                        "thumbnail_url": "/api/detections/1/image",
                        "similarity_score": 1.0,
                        "attributes": {},
                    }
                ],
                "count": 1,
            }
        }
    )

    entity_id: str = Field(..., description="Entity identifier")
    entity_type: str = Field(..., description="Type of entity")
    appearances: list[EntityAppearance] = Field(
        ..., description="List of appearances in chronological order"
    )
    count: int = Field(..., description="Total number of appearances")
