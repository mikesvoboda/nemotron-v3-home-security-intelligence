"""Pydantic schemas for face recognition API endpoints.

Implements NEM-3716: Face detection with InsightFace
Implements NEM-3717: Face quality assessment for recognition

These schemas enable face recognition features including:
- Known person management
- Face embedding storage and matching
- Face detection event tracking
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# Known Person Schemas
# =============================================================================


class KnownPersonCreate(BaseModel):
    """Schema for creating a new known person."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "John Doe",
                "is_household_member": True,
                "notes": "Family member - always trusted",
            }
        }
    )

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Display name of the person",
    )
    is_household_member: bool = Field(
        default=False,
        description="Whether person is a trusted household member",
    )
    notes: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional notes about the person",
    )


class KnownPersonUpdate(BaseModel):
    """Schema for updating an existing known person."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "John Smith",
                "is_household_member": True,
                "notes": "Updated notes",
            }
        }
    )

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Display name of the person",
    )
    is_household_member: bool | None = Field(
        default=None,
        description="Whether person is a trusted household member",
    )
    notes: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional notes about the person",
    )


class KnownPersonResponse(BaseModel):
    """Schema for known person response."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "name": "John Doe",
                "is_household_member": True,
                "notes": "Family member",
                "embedding_count": 3,
                "created_at": "2025-01-01T10:00:00Z",
                "updated_at": "2025-01-01T12:00:00Z",
            }
        },
    )

    id: int = Field(..., description="Unique identifier for the person")
    name: str = Field(..., description="Display name of the person")
    is_household_member: bool = Field(..., description="Whether person is a household member")
    notes: str | None = Field(None, description="Notes about the person")
    embedding_count: int = Field(
        default=0,
        description="Number of face embeddings stored for this person",
    )
    created_at: datetime = Field(..., description="When the person was registered")
    updated_at: datetime = Field(..., description="When the record was last updated")


class KnownPersonListResponse(BaseModel):
    """Schema for list of known persons."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": 1,
                        "name": "John Doe",
                        "is_household_member": True,
                        "notes": "Family member",
                        "embedding_count": 3,
                        "created_at": "2025-01-01T10:00:00Z",
                        "updated_at": "2025-01-01T12:00:00Z",
                    }
                ],
                "total": 1,
            }
        }
    )

    items: list[KnownPersonResponse] = Field(..., description="List of known persons")
    total: int = Field(..., description="Total number of known persons")


# =============================================================================
# Face Embedding Schemas
# =============================================================================


class FaceEmbeddingCreate(BaseModel):
    """Schema for adding a face embedding."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "embedding": [0.1] * 512,  # 512-dim vector
                "quality_score": 0.85,
                "source_image_path": "/data/images/john_doe_1.jpg",
            }
        }
    )

    embedding: list[float] = Field(
        ...,
        min_length=512,
        max_length=512,
        description="512-dimensional ArcFace embedding vector",
    )
    quality_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Face quality score when embedding was captured",
    )
    source_image_path: str | None = Field(
        default=None,
        max_length=500,
        description="Path to the source image",
    )


class FaceEmbeddingResponse(BaseModel):
    """Schema for face embedding response."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "person_id": 1,
                "quality_score": 0.85,
                "source_image_path": "/data/images/john_doe_1.jpg",
                "created_at": "2025-01-01T10:00:00Z",
            }
        },
    )

    id: int = Field(..., description="Unique identifier for the embedding")
    person_id: int = Field(..., description="ID of the associated person")
    quality_score: float = Field(..., description="Face quality score")
    source_image_path: str | None = Field(None, description="Path to source image")
    created_at: datetime = Field(..., description="When the embedding was created")


# =============================================================================
# Face Detection Event Schemas
# =============================================================================


class FaceDetectionEventResponse(BaseModel):
    """Schema for face detection event response."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "camera_id": "front_door",
                "timestamp": "2025-01-01T10:00:00Z",
                "bbox": [100, 150, 200, 300],
                "matched_person_id": 1,
                "matched_person_name": "John Doe",
                "match_confidence": 0.92,
                "is_unknown": False,
                "quality_score": 0.85,
                "age_estimate": 35,
                "gender_estimate": "M",
                "created_at": "2025-01-01T10:00:00Z",
            }
        },
    )

    id: int = Field(..., description="Unique identifier for the event")
    camera_id: str = Field(..., description="ID of the camera that detected the face")
    timestamp: datetime = Field(..., description="When the face was detected")
    bbox: list[float] = Field(..., description="Bounding box [x1, y1, x2, y2]")
    matched_person_id: int | None = Field(None, description="ID of matched person")
    matched_person_name: str | None = Field(None, description="Name of matched person")
    match_confidence: float | None = Field(None, description="Match confidence score")
    is_unknown: bool = Field(..., description="Whether face is unknown")
    quality_score: float = Field(..., description="Face quality score")
    age_estimate: int | None = Field(None, description="Estimated age")
    gender_estimate: str | None = Field(None, description="Estimated gender (M/F)")
    created_at: datetime = Field(..., description="When the event was recorded")


class FaceDetectionEventListResponse(BaseModel):
    """Schema for list of face detection events."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": 1,
                        "camera_id": "front_door",
                        "timestamp": "2025-01-01T10:00:00Z",
                        "bbox": [100, 150, 200, 300],
                        "matched_person_id": None,
                        "matched_person_name": None,
                        "match_confidence": None,
                        "is_unknown": True,
                        "quality_score": 0.75,
                        "age_estimate": 40,
                        "gender_estimate": "M",
                        "created_at": "2025-01-01T10:00:00Z",
                    }
                ],
                "total": 1,
            }
        }
    )

    items: list[FaceDetectionEventResponse] = Field(
        ..., description="List of face detection events"
    )
    total: int = Field(..., description="Total number of events")


# =============================================================================
# Face Matching Schemas
# =============================================================================


class FaceMatchRequest(BaseModel):
    """Schema for face matching request."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "embedding": [0.1] * 512,  # 512-dim vector
                "threshold": 0.68,
            }
        }
    )

    embedding: list[float] = Field(
        ...,
        min_length=512,
        max_length=512,
        description="512-dimensional face embedding to match",
    )
    threshold: float = Field(
        default=0.68,
        ge=0.0,
        le=1.0,
        description="Minimum similarity threshold for a match",
    )


class FaceMatchResponse(BaseModel):
    """Schema for face matching response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "matched": True,
                "person_id": 1,
                "person_name": "John Doe",
                "similarity": 0.92,
                "is_unknown": False,
                "is_household_member": True,
            }
        }
    )

    matched: bool = Field(..., description="Whether a match was found")
    person_id: int | None = Field(None, description="ID of matched person")
    person_name: str | None = Field(None, description="Name of matched person")
    similarity: float = Field(..., description="Best similarity score")
    is_unknown: bool = Field(..., description="Whether face is unknown")
    is_household_member: bool | None = Field(
        None, description="Whether matched person is a household member"
    )


# =============================================================================
# Unknown Stranger Alert Schemas
# =============================================================================


class UnknownStrangerAlert(BaseModel):
    """Schema for unknown stranger alert."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_id": 1,
                "camera_id": "front_door",
                "timestamp": "2025-01-01T10:00:00Z",
                "bbox": [100, 150, 200, 300],
                "quality_score": 0.85,
                "age_estimate": 35,
                "gender_estimate": "M",
                "thumbnail_path": "/data/thumbnails/stranger_1.jpg",
            }
        }
    )

    event_id: int = Field(..., description="ID of the face detection event")
    camera_id: str = Field(..., description="ID of the camera")
    timestamp: datetime = Field(..., description="When the stranger was detected")
    bbox: list[float] = Field(..., description="Bounding box coordinates")
    quality_score: float = Field(..., description="Face quality score")
    age_estimate: int | None = Field(None, description="Estimated age")
    gender_estimate: str | None = Field(None, description="Estimated gender")
    thumbnail_path: str | None = Field(None, description="Path to face thumbnail")


class UnknownStrangerListResponse(BaseModel):
    """Schema for list of unknown stranger alerts."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "event_id": 1,
                        "camera_id": "front_door",
                        "timestamp": "2025-01-01T10:00:00Z",
                        "bbox": [100, 150, 200, 300],
                        "quality_score": 0.85,
                        "age_estimate": 35,
                        "gender_estimate": "M",
                        "thumbnail_path": None,
                    }
                ],
                "total": 1,
            }
        }
    )

    items: list[UnknownStrangerAlert] = Field(..., description="List of unknown strangers")
    total: int = Field(..., description="Total number of unknown strangers")
