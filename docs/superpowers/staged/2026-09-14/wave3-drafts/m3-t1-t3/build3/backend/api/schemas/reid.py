"""Pydantic schemas for Re-ID similarity search API endpoints (NEM-4932).

These schemas define the request and response models for the Re-ID
similarity search functionality, allowing users to find similar entities
based on embedding vectors.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SimilaritySearchRequest(BaseModel):
    """Request schema for similarity search.

    Allows searching for entities similar to a given embedding vector
    or detection ID.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "embedding": [0.1, 0.2, 0.3],
                "entity_type": "person",
                "threshold": 0.85,
                "limit": 10,
                "include_historical": True,
            }
        }
    )

    embedding: list[float] = Field(
        ...,
        min_length=1,
        description="Embedding vector to search for (typically 768-dimensional CLIP embedding)",
    )
    entity_type: str = Field(
        default="person",
        pattern="^(person|vehicle)$",
        description="Type of entity to search for: 'person' or 'vehicle'",
    )
    threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity threshold for matches (default: 0.85)",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of results to return (default: 10, max: 100)",
    )
    include_historical: bool = Field(
        default=True,
        description="If True, search both Redis (hot cache) and PostgreSQL (historical). "
        "If False, only search Redis hot cache (24h window).",
    )
    exclude_detection_id: str | None = Field(
        default=None,
        description="Optional detection ID to exclude from results (e.g., to exclude self-matches)",
    )


class SimilarityMatch(BaseModel):
    """Schema for a single similarity match result."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "entity_id": "550e8400-e29b-41d4-a716-446655440000",
                "entity_type": "person",
                "camera_id": "front_door",
                "timestamp": "2025-12-23T10:00:00Z",
                "detection_id": "123",
                "similarity": 0.92,
                "time_gap_seconds": 3600.0,
                "source": "redis",
                "thumbnail_url": "/api/detections/123/image",
                "attributes": {"clothing": "blue jacket"},
            }
        }
    )

    entity_id: str = Field(..., description="Entity or detection ID")
    entity_type: str = Field(..., description="Type of entity: 'person' or 'vehicle'")
    camera_id: str = Field(..., description="Camera ID where entity was detected")
    timestamp: datetime = Field(..., description="When the entity was detected")
    detection_id: str | None = Field(None, description="Detection ID if available")
    similarity: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity score (0-1)")
    time_gap_seconds: float = Field(
        ..., description="Time difference in seconds from query timestamp"
    )
    source: str = Field(
        ...,
        pattern="^(redis|postgresql)$",
        description="Data source: 'redis' (hot cache) or 'postgresql' (historical)",
    )
    thumbnail_url: str | None = Field(None, description="URL to thumbnail image")
    attributes: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional attributes from the detection (clothing, color, etc.)",
    )


class SimilaritySearchResponse(BaseModel):
    """Response schema for similarity search."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "matches": [
                    {
                        "entity_id": "det_001",
                        "entity_type": "person",
                        "camera_id": "front_door",
                        "timestamp": "2025-12-23T10:00:00Z",
                        "detection_id": "123",
                        "similarity": 0.92,
                        "time_gap_seconds": 3600.0,
                        "source": "redis",
                        "thumbnail_url": "/api/detections/123/image",
                        "attributes": {"clothing": "blue jacket"},
                    }
                ],
                "total_matches": 1,
                "threshold": 0.85,
                "entity_type": "person",
                "include_historical": True,
            }
        }
    )

    matches: list[SimilarityMatch] = Field(
        default_factory=list,
        description="List of matching entities sorted by similarity (highest first)",
    )
    total_matches: int = Field(..., ge=0, description="Total number of matches found")
    threshold: float = Field(..., description="Similarity threshold used for the search")
    entity_type: str = Field(..., description="Entity type that was searched")
    include_historical: bool = Field(
        ..., description="Whether historical (PostgreSQL) data was included"
    )


class DetectionSimilarityRequest(BaseModel):
    """Request schema for finding similar entities to a detection.

    Alternative to embedding-based search that uses a detection ID
    to automatically retrieve the embedding and find similar entities.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detection_id": "123",
                "entity_type": "person",
                "threshold": 0.85,
                "limit": 10,
                "include_historical": True,
            }
        }
    )

    detection_id: str = Field(..., description="Detection ID to find similar entities for")
    entity_type: str = Field(
        default="person",
        pattern="^(person|vehicle)$",
        description="Type of entity to search for: 'person' or 'vehicle'",
    )
    threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity threshold for matches",
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of results to return",
    )
    include_historical: bool = Field(
        default=True,
        description="If True, search both Redis and PostgreSQL",
    )
