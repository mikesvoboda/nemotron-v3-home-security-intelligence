"""Pydantic schemas for entity re-identification API endpoints.

Entity re-identification allows tracking the same person or vehicle
across multiple cameras using CLIP embeddings stored in Redis.

This module provides two sets of schemas:
1. Database-aligned schemas (EntityBase, EntityCreate, EntityRead, EntityUpdate)
   - Match the SQLAlchemy Entity model in backend/models/entity.py
   - Used for database CRUD operations

2. Redis/API schemas (EntityAppearance, EntitySummary, EntityDetail, etc.)
   - Used for real-time entity tracking via Redis
   - Used by the current /api/entities endpoints
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.api.schemas.logs import PaginationInfo

# =============================================================================
# Database Entity Type Enum (matches backend/models/enums.py)
# =============================================================================


class EntityTypeEnum(str, Enum):
    """Entity types for re-identification tracking.

    Matches the EntityType enum in backend/models/enums.py and
    the CHECK constraint on the entities table.
    """

    PERSON = "person"
    VEHICLE = "vehicle"
    ANIMAL = "animal"
    PACKAGE = "package"
    OTHER = "other"


class EntityTypeFilter(str, Enum):
    """Entity types for API query filtering.

    A subset of EntityTypeEnum used for filtering in API endpoints.
    Currently only person and vehicle are supported for re-identification.
    """

    person = "person"
    vehicle = "vehicle"


# =============================================================================
# Database-Aligned Entity Schemas (match SQLAlchemy Entity model)
# =============================================================================


class EmbeddingVectorData(BaseModel):
    """Schema for embedding vector storage (matches JSONB structure in Entity model).

    The embedding_vector column stores a JSONB object with these fields.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "vector": [0.1, 0.2, 0.3],
                "model": "clip",
                "dimension": 768,
            }
        }
    )

    vector: list[float] = Field(..., description="The embedding vector as a list of floats")
    model: str = Field(default="clip", description="The model used to generate the embedding")
    dimension: int = Field(..., description="Dimension of the embedding vector")


class EntityBase(BaseModel):
    """Base schema for Entity with common fields.

    Field names and types match the SQLAlchemy Entity model exactly.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "entity_type": "person",
                "entity_metadata": {"clothing_color": "blue", "height_estimate": "tall"},
            }
        }
    )

    entity_type: EntityTypeEnum = Field(
        default=EntityTypeEnum.PERSON,
        description="Type of entity: person, vehicle, animal, package, or other",
    )
    entity_metadata: dict[str, Any] | None = Field(
        default=None,
        description="Flexible metadata for attributes like clothing color, vehicle make/model, etc.",
    )


class EntityCreate(EntityBase):
    """Schema for creating a new Entity.

    Includes optional fields for initial detection linkage and embedding.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "entity_type": "person",
                "embedding_vector": {
                    "vector": [0.1, 0.2, 0.3],
                    "model": "clip",
                    "dimension": 768,
                },
                "primary_detection_id": 123,
                "entity_metadata": {"clothing_color": "blue"},
            }
        }
    )

    embedding_vector: EmbeddingVectorData | None = Field(
        default=None,
        description="Optional embedding vector for re-identification",
    )
    primary_detection_id: int | None = Field(
        default=None,
        description="Optional reference to the primary/best detection for this entity",
    )


class EntityUpdate(BaseModel):
    """Schema for updating an existing Entity.

    All fields are optional - only provided fields will be updated.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "entity_type": "vehicle",
                "entity_metadata": {"make": "Toyota", "color": "silver"},
                "primary_detection_id": 456,
            }
        }
    )

    entity_type: EntityTypeEnum | None = Field(
        default=None,
        description="Updated entity type",
    )
    embedding_vector: EmbeddingVectorData | None = Field(
        default=None,
        description="Updated embedding vector",
    )
    entity_metadata: dict[str, Any] | None = Field(
        default=None,
        description="Updated metadata (replaces existing metadata)",
    )
    primary_detection_id: int | None = Field(
        default=None,
        description="Updated primary detection reference",
    )


class EntityRead(EntityBase):
    """Schema for reading an Entity from the database.

    Includes all fields from the SQLAlchemy model with proper types.
    Field names match the database model exactly.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "entity_type": "person",
                "embedding_vector": {
                    "vector": [0.1, 0.2, 0.3],
                    "model": "clip",
                    "dimension": 768,
                },
                "first_seen_at": "2025-12-23T10:00:00Z",
                "last_seen_at": "2025-12-23T14:30:00Z",
                "detection_count": 5,
                "entity_metadata": {"clothing_color": "blue"},
                "primary_detection_id": 123,
            }
        },
    )

    id: UUID = Field(..., description="Unique entity identifier (UUID)")
    embedding_vector: dict[str, Any] | None = Field(
        default=None,
        description="Feature vector for re-identification (JSONB)",
    )
    first_seen_at: datetime = Field(..., description="Timestamp of first detection")
    last_seen_at: datetime = Field(..., description="Timestamp of most recent detection")
    detection_count: int = Field(
        default=0,
        ge=0,
        description="Total number of detections linked to this entity",
    )
    primary_detection_id: int | None = Field(
        default=None,
        description="Reference to the primary/best detection for this entity",
    )


class EntityReadWithDetection(EntityRead):
    """Schema for Entity with expanded primary detection relationship.

    Extends EntityRead to include the primary detection details when needed.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "entity_type": "person",
                "embedding_vector": None,
                "first_seen_at": "2025-12-23T10:00:00Z",
                "last_seen_at": "2025-12-23T14:30:00Z",
                "detection_count": 5,
                "entity_metadata": {"clothing_color": "blue"},
                "primary_detection_id": 123,
                "primary_detection": {
                    "id": 123,
                    "label": "person",
                    "confidence": 0.95,
                },
            }
        },
    )

    # Note: Using Any here to avoid circular import with detection schema
    # The actual type would be DetectionRead from backend.api.schemas.detections
    primary_detection: dict[str, Any] | None = Field(
        default=None,
        description="The primary detection associated with this entity",
    )


# =============================================================================
# Redis/API Entity Schemas (for real-time entity tracking)
# =============================================================================


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
    """Schema for paginated entity list response (NEM-2075 pagination envelope).

    Uses standardized pagination envelope with 'items' and 'pagination' fields.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
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
                "pagination": {
                    "total": 1,
                    "limit": 50,
                    "offset": 0,
                    "has_more": False,
                },
            }
        }
    )

    items: list[EntitySummary] = Field(..., description="List of tracked entities")
    pagination: PaginationInfo = Field(..., description="Pagination metadata")


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


class EntityMatchItem(BaseModel):
    """Schema for a single entity match result.

    Represents a matching entity found through re-identification,
    including similarity score and time gap.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "entity_id": "det_abc123",
                "entity_type": "person",
                "camera_id": "backyard",
                "camera_name": "Backyard",
                "timestamp": "2025-12-23T10:00:00Z",
                "thumbnail_url": "/api/detections/123/image",
                "similarity_score": 0.92,
                "time_gap_seconds": 3600.0,
                "attributes": {"clothing": "blue jacket"},
            }
        }
    )

    entity_id: str = Field(..., description="Detection ID of the matched entity")
    entity_type: str = Field(..., description="Type of entity: 'person' or 'vehicle'")
    camera_id: str = Field(..., description="Camera ID where entity was seen")
    camera_name: str | None = Field(None, description="Human-readable camera name")
    timestamp: datetime = Field(..., description="When the entity was detected")
    thumbnail_url: str | None = Field(None, description="URL to thumbnail image")
    similarity_score: float = Field(
        ..., ge=0.0, le=1.0, description="Cosine similarity score (0-1)"
    )
    time_gap_seconds: float = Field(..., description="Time gap in seconds between query and match")
    attributes: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional attributes extracted from the detection",
    )


class EntityMatchResponse(BaseModel):
    """Schema for entity match query response.

    Returns entities matching a specific detection's embedding,
    used for showing re-ID matches in the EventDetailModal.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query_detection_id": "det_001",
                "entity_type": "person",
                "matches": [
                    {
                        "entity_id": "det_002",
                        "entity_type": "person",
                        "camera_id": "backyard",
                        "camera_name": "Backyard",
                        "timestamp": "2025-12-23T09:00:00Z",
                        "thumbnail_url": "/api/detections/2/image",
                        "similarity_score": 0.92,
                        "time_gap_seconds": 3600.0,
                        "attributes": {"clothing": "blue jacket"},
                    }
                ],
                "total_matches": 1,
                "threshold": 0.85,
            }
        }
    )

    query_detection_id: str = Field(..., description="Detection ID used for the query")
    entity_type: str = Field(..., description="Type of entity searched")
    matches: list[EntityMatchItem] = Field(
        default_factory=list, description="List of matching entities sorted by similarity"
    )
    total_matches: int = Field(..., description="Total number of matches found")
    threshold: float = Field(..., description="Similarity threshold used for matching")
