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


class SourceFilter(str, Enum):
    """Data source for entity queries.

    Controls which storage backend to query for entities:
    - redis: Only query Redis hot cache (24h window)
    - postgres: Only query PostgreSQL (30d retention)
    - both: Query both and merge results (default)
    """

    redis = "redis"
    postgres = "postgres"
    both = "both"


class TrustStatusEnum(str, Enum):
    """Trust status for tracked entities.

    Matches the TrustStatus enum in backend/models/enums.py and
    the CHECK constraint on the entities table.

    - TRUSTED: Known/recognized entity (alerts may be skipped or reduced)
    - UNTRUSTED: Explicitly flagged as suspicious (alerts may be increased)
    - UNKNOWN: Not yet classified (normal alert processing)
    """

    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"
    UNKNOWN = "unknown"


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
    trust_status: TrustStatusEnum = Field(
        default=TrustStatusEnum.UNKNOWN,
        description="Trust level: trusted (known/safe), untrusted (suspicious), or unknown (default)",
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
    trust_status: TrustStatusEnum | None = Field(
        default=None,
        description="Updated trust status (trusted, untrusted, or unknown)",
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


# =============================================================================
# Historical Query Response Schemas (NEM-2500)
# =============================================================================


class DetectionSummary(BaseModel):
    """Summary of a detection linked to an entity.

    Represents a single detection occurrence for an entity, used in
    the entity detections list endpoint.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "detection_id": 123,
                "camera_id": "front_door",
                "camera_name": "Front Door",
                "timestamp": "2025-12-23T10:00:00Z",
                "confidence": 0.95,
                "thumbnail_url": "/api/detections/123/image",
                "object_type": "person",
            }
        },
    )

    detection_id: int = Field(..., description="Detection database ID")
    camera_id: str = Field(..., description="Camera ID where detection occurred")
    camera_name: str | None = Field(None, description="Human-readable camera name")
    timestamp: datetime = Field(..., description="When the detection occurred")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="Detection confidence score")
    thumbnail_url: str | None = Field(None, description="URL to detection thumbnail")
    object_type: str | None = Field(None, description="Detected object type")


class EntityDetectionsResponse(BaseModel):
    """Response for entity detections list endpoint.

    Returns all detections linked to a specific entity with pagination.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "entity_id": "550e8400-e29b-41d4-a716-446655440000",
                "entity_type": "person",
                "detections": [
                    {
                        "detection_id": 123,
                        "camera_id": "front_door",
                        "camera_name": "Front Door",
                        "timestamp": "2025-12-23T10:00:00Z",
                        "confidence": 0.95,
                        "thumbnail_url": "/api/detections/123/image",
                        "object_type": "person",
                    }
                ],
                "pagination": {
                    "total": 5,
                    "limit": 50,
                    "offset": 0,
                    "has_more": False,
                },
            }
        }
    )

    entity_id: str = Field(..., description="UUID of the entity")
    entity_type: str = Field(..., description="Type of entity")
    detections: list[DetectionSummary] = Field(
        default_factory=list, description="List of detections for this entity"
    )
    pagination: PaginationInfo = Field(..., description="Pagination metadata")


class EntityTypeCounts(BaseModel):
    """Entity counts by type."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "person": 150,
                "vehicle": 45,
                "animal": 12,
            }
        }
    )

    person: int = Field(default=0, ge=0, description="Count of person entities")
    vehicle: int = Field(default=0, ge=0, description="Count of vehicle entities")
    animal: int = Field(default=0, ge=0, description="Count of animal entities")
    package: int = Field(default=0, ge=0, description="Count of package entities")
    other: int = Field(default=0, ge=0, description="Count of other entities")


class CameraCounts(BaseModel):
    """Entity counts by camera."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "front_door": 85,
                "backyard": 42,
                "driveway": 68,
            }
        }
    )

    # Dynamic camera counts stored in a dict
    counts: dict[str, int] = Field(default_factory=dict, description="Entity counts per camera")


class EntityStatsResponse(BaseModel):
    """Response for entity statistics endpoint.

    Returns aggregated statistics about tracked entities.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_entities": 207,
                "total_appearances": 1523,
                "by_type": {
                    "person": 150,
                    "vehicle": 45,
                    "animal": 12,
                    "package": 0,
                    "other": 0,
                },
                "by_camera": {
                    "front_door": 85,
                    "backyard": 42,
                    "driveway": 68,
                    "garage": 12,
                },
                "repeat_visitors": 89,
                "time_range": {
                    "since": "2025-12-23T00:00:00Z",
                    "until": "2025-12-23T23:59:59Z",
                },
            }
        }
    )

    total_entities: int = Field(..., ge=0, description="Count of unique entities")
    total_appearances: int = Field(
        ..., ge=0, description="Sum of all detection counts across entities"
    )
    by_type: dict[str, int] = Field(
        default_factory=dict, description="Entity counts grouped by entity type"
    )
    by_camera: dict[str, int] = Field(
        default_factory=dict, description="Entity counts grouped by camera"
    )
    repeat_visitors: int = Field(..., ge=0, description="Count of entities seen more than once")
    time_range: dict[str, datetime | None] | None = Field(
        None, description="Time range for the statistics query"
    )


# =============================================================================
# Entity Trust Classification Schemas (NEM-2671)
# =============================================================================


class TrustStatus(str, Enum):
    """Trust classification status for entities.

    Entities can be classified as trusted (known/safe), untrusted (unknown/suspicious),
    or unclassified (no classification assigned yet).
    """

    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"
    UNCLASSIFIED = "unclassified"


class EntityTrustUpdate(BaseModel):
    """Schema for updating an entity's trust status.

    Request body for PATCH /api/entities/{entity_id}/trust endpoint.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "trust_status": "trusted",
                "notes": "Regular mail carrier, verified by homeowner",
            }
        }
    )

    trust_status: TrustStatus = Field(
        ...,
        description="The trust classification to assign to the entity",
    )
    notes: str | None = Field(
        default=None,
        max_length=500,
        description="Optional notes explaining the trust classification decision",
    )


class EntityTrustResponse(BaseModel):
    """Schema for entity trust status response.

    Response from PATCH /api/entities/{entity_id}/trust endpoint and list endpoints.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "entity_type": "person",
                "trust_status": "trusted",
                "trust_notes": "Regular mail carrier, verified by homeowner",
                "trust_updated_at": "2025-12-23T14:30:00Z",
                "first_seen": "2025-12-23T10:00:00Z",
                "last_seen": "2025-12-23T14:30:00Z",
                "appearance_count": 5,
                "thumbnail_url": "/api/detections/123/image",
            }
        }
    )

    id: str = Field(..., description="Unique entity identifier (UUID)")
    entity_type: str = Field(..., description="Type of entity: person, vehicle, etc.")
    trust_status: TrustStatus = Field(..., description="Current trust classification status")
    trust_notes: str | None = Field(None, description="Notes about the trust classification")
    trust_updated_at: datetime | None = Field(
        None, description="When the trust status was last updated"
    )
    first_seen: datetime | None = Field(None, description="Timestamp of first appearance")
    last_seen: datetime | None = Field(None, description="Timestamp of most recent appearance")
    appearance_count: int | None = Field(None, ge=0, description="Total number of appearances")
    thumbnail_url: str | None = Field(None, description="URL to thumbnail image")


class TrustedEntityListResponse(BaseModel):
    """Schema for paginated list of trusted or untrusted entities.

    Response from GET /api/entities/trusted and GET /api/entities/untrusted endpoints.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "entity_type": "person",
                        "trust_status": "trusted",
                        "trust_notes": "Mail carrier",
                        "trust_updated_at": "2025-12-23T14:30:00Z",
                        "first_seen": "2025-12-23T10:00:00Z",
                        "last_seen": "2025-12-23T14:30:00Z",
                        "appearance_count": 5,
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

    items: list[EntityTrustResponse] = Field(
        ..., description="List of entities with their trust status"
    )
    pagination: PaginationInfo = Field(..., description="Pagination metadata")
