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


# =============================================================================
# Person Appearances Schemas (NEM-4688)
# =============================================================================


class PersonAppearance(BaseModel):
    """Schema for a single person appearance in the timeline."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2025-01-31T10:32:00Z",
                "camera_id": "front_door",
                "camera_name": "Front Door",
                "detection_id": 1,
                "confidence": 0.95,
                "thumbnail_url": "/api/thumbnails/face_1.jpg",
            }
        }
    )

    timestamp: datetime = Field(..., description="When the person was detected")
    camera_id: str = Field(..., description="ID of the camera that detected the person")
    camera_name: str = Field(..., description="Human-readable name of the camera")
    detection_id: int = Field(..., description="ID of the face detection event")
    confidence: float = Field(..., description="Match confidence score (0-1)")
    thumbnail_url: str | None = Field(None, description="URL to face thumbnail image")


class PersonAppearancesResponse(BaseModel):
    """Schema for person appearances timeline response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "appearances": [
                    {
                        "timestamp": "2025-01-31T10:32:00Z",
                        "camera_id": "front_door",
                        "camera_name": "Front Door",
                        "detection_id": 1,
                        "confidence": 0.95,
                        "thumbnail_url": "/api/thumbnails/face_1.jpg",
                    },
                    {
                        "timestamp": "2025-01-31T08:15:00Z",
                        "camera_id": "driveway",
                        "camera_name": "Driveway",
                        "detection_id": 2,
                        "confidence": 0.92,
                        "thumbnail_url": None,
                    },
                ],
                "total_count": 2,
            }
        }
    )

    appearances: list[PersonAppearance] = Field(
        ..., description="List of person appearances ordered by timestamp descending"
    )
    total_count: int = Field(..., description="Total number of appearances matching filters")


# =============================================================================
# Face Events Statistics Schemas (NEM-4688 Phase 2)
# =============================================================================


class CameraFaceStats(BaseModel):
    """Schema for face detection statistics per camera."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total": 50,
                "known": 40,
                "unknown": 10,
            }
        }
    )

    total: int = Field(..., ge=0, description="Total face detections from this camera today")
    known: int = Field(..., ge=0, description="Number of known (matched) faces")
    unknown: int = Field(..., ge=0, description="Number of unknown (unmatched) faces")


class FaceEventsStatsResponse(BaseModel):
    """Schema for face events statistics response.

    Returns aggregated face detection statistics for today,
    broken down by camera and known/unknown status.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_today": 100,
                "known_count": 70,
                "unknown_count": 30,
                "by_camera": {
                    "front_door": {"total": 60, "known": 45, "unknown": 15},
                    "back_door": {"total": 40, "known": 25, "unknown": 15},
                },
            }
        }
    )

    total_today: int = Field(..., ge=0, description="Total face detection events today")
    known_count: int = Field(..., ge=0, description="Number of known (matched person) faces today")
    unknown_count: int = Field(..., ge=0, description="Number of unknown (no match) faces today")
    by_camera: dict[str, CameraFaceStats] = Field(
        default_factory=dict,
        description="Face detection counts broken down by camera ID",
    )


# =============================================================================
# Enroll From Detection Schemas (NEM-4688 Phase 1)
# =============================================================================


class EnrollFromDetectionRequest(BaseModel):
    """Schema for enrolling a face from an existing detection.

    Used to create a face embedding for a known person from a detection
    that contains a person with a visible face.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detection_id": "123",
            }
        }
    )

    detection_id: str = Field(
        ...,
        description="ID of the detection to extract face embedding from",
    )


class EnrollFromDetectionResponse(BaseModel):
    """Schema for enroll-from-detection response.

    Returns the result of face enrollment including:
    - success: Whether the embedding was created
    - embedding_id: ID of the created face embedding
    - quality_score: Quality score of the extracted face (0-1)
    - warning: Optional warning message for moderate quality faces (0.7-0.8)
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "embedding_id": 1,
                "quality_score": 0.92,
                "warning": None,
            }
        }
    )

    success: bool = Field(..., description="Whether the face was successfully enrolled")
    embedding_id: int = Field(..., description="ID of the created face embedding")
    quality_score: float = Field(
        ..., ge=0.0, le=1.0, description="Quality score of the extracted face"
    )
    warning: str | None = Field(
        None,
        description="Warning message for moderate quality faces (0.7-0.8)",
    )


# =============================================================================
# Identify Face Event Schemas (NEM-4688 Phase 2)
# =============================================================================


class IdentifyFaceEventRequest(BaseModel):
    """Schema for manually identifying an unknown face as a known person.

    Used when a user manually identifies an unknown face detection event
    as belonging to a known person in the system.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "known_person_id": 1,
            }
        }
    )

    known_person_id: int = Field(
        ...,
        description="ID of the known person to associate with this face event",
    )


class IdentifyFaceEventResponse(BaseModel):
    """Schema for identify face event response.

    Returns the result of manually identifying an unknown face:
    - success: Whether the identification was successful
    - created_embedding: Whether a new face embedding was created
      (only happens when quality_score >= 0.7)
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "created_embedding": True,
            }
        }
    )

    success: bool = Field(..., description="Whether the face was successfully identified")
    created_embedding: bool = Field(
        ...,
        description="Whether a new face embedding was created (quality >= 0.7)",
    )


# =============================================================================
# Face Similarity Comparison Schemas (NEM-4955)
# =============================================================================


class FaceSimilarityCompareResponse(BaseModel):
    """Schema for face similarity comparison response.

    Returns the result of comparing two face images:
    - similarity_score: Cosine similarity between embeddings (0-1)
    - is_match: Whether similarity exceeds the threshold
    - threshold: The threshold used for matching
    - embedding_dimension: Dimension of the embeddings used (768 for CLIP)
    - processing_time_ms: Time taken to process both images

    Note: This debug tool uses CLIP embeddings (768-dim) for visual similarity,
    not ArcFace embeddings (512-dim) used in production face recognition.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "similarity_score": 0.85,
                "is_match": True,
                "threshold": 0.7,
                "embedding_dimension": 768,
                "processing_time_ms": 245,
                "error": None,
            }
        }
    )

    similarity_score: float = Field(
        ..., ge=0.0, le=1.0, description="Cosine similarity score between the two faces"
    )
    is_match: bool = Field(
        ..., description="Whether the similarity exceeds the threshold (same person)"
    )
    threshold: float = Field(..., ge=0.0, le=1.0, description="The threshold used for matching")
    embedding_dimension: int = Field(..., description="Dimension of the embeddings (768 for CLIP)")
    processing_time_ms: int = Field(
        ..., ge=0, description="Time taken to process both images in milliseconds"
    )
    error: str | None = Field(None, description="Error message if comparison failed")


# =============================================================================
# Bulk Enrollment Schemas (NEM-4954)
# =============================================================================


class BulkEnrollmentImageResult(BaseModel):
    """Schema for individual image result in bulk enrollment.

    Each image in a bulk enrollment request produces a result with:
    - filename: Original filename of the uploaded image
    - success: Whether enrollment succeeded
    - embedding_id: ID of created embedding (if successful)
    - quality_score: Quality score of the face (if detected)
    - error: Error message if enrollment failed
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "filename": "face_001.jpg",
                "success": True,
                "embedding_id": 1,
                "quality_score": 0.92,
                "error": None,
            }
        }
    )

    filename: str = Field(..., description="Original filename of the uploaded image")
    success: bool = Field(..., description="Whether enrollment succeeded for this image")
    embedding_id: int | None = Field(None, description="ID of created embedding if successful")
    quality_score: float | None = Field(
        None, ge=0.0, le=1.0, description="Quality score of detected face"
    )
    error: str | None = Field(None, description="Error message if enrollment failed")


class BulkEnrollmentResponse(BaseModel):
    """Schema for bulk enrollment response.

    Returns summary of bulk face enrollment:
    - total_images: Number of images submitted
    - successful: Number of successful enrollments
    - failed: Number of failed enrollments
    - results: Per-image results with details
    - person_id: ID of the person images were enrolled to
    - person_name: Name of the person
    - created_new_person: Whether a new person was created
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_images": 5,
                "successful": 4,
                "failed": 1,
                "results": [
                    {
                        "filename": "face_001.jpg",
                        "success": True,
                        "embedding_id": 1,
                        "quality_score": 0.92,
                        "error": None,
                    },
                    {
                        "filename": "face_002.jpg",
                        "success": False,
                        "embedding_id": None,
                        "quality_score": 0.55,
                        "error": "Quality score below threshold (0.7)",
                    },
                ],
                "person_id": 1,
                "person_name": "John Doe",
                "created_new_person": False,
            }
        }
    )

    total_images: int = Field(..., ge=0, description="Total number of images submitted")
    successful: int = Field(..., ge=0, description="Number of successful enrollments")
    failed: int = Field(..., ge=0, description="Number of failed enrollments")
    results: list[BulkEnrollmentImageResult] = Field(
        ..., description="Per-image enrollment results"
    )
    person_id: int = Field(..., description="ID of the person images were enrolled to")
    person_name: str = Field(..., description="Name of the person")
    created_new_person: bool = Field(
        ..., description="Whether a new person was created for this enrollment"
    )


# =============================================================================
# Auto-Enrollment Schemas (NEM-4941)
# =============================================================================


class EnrollmentCandidateResponse(BaseModel):
    """Schema for enrollment candidate response.

    Represents a face detection that meets quality thresholds and is
    pending review for enrollment as a known person.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "face_event_id": 100,
                "quality_score": 0.92,
                "status": "pending",
                "suggested_name": None,
                "enrolled_person_id": None,
                "camera_id": "front_door",
                "timestamp": "2025-01-31T10:30:00Z",
                "created_at": "2025-01-31T10:31:00Z",
            }
        },
    )

    id: int = Field(..., description="Unique identifier for the enrollment candidate")
    face_event_id: int = Field(..., description="ID of the source face detection event")
    quality_score: float = Field(..., ge=0.0, le=1.0, description="Face quality score")
    status: str = Field(
        ..., description="Enrollment status: pending/approved/rejected/auto_enrolled"
    )
    suggested_name: str | None = Field(None, description="Auto-generated or suggested name")
    enrolled_person_id: int | None = Field(None, description="ID of enrolled person if approved")
    camera_id: str | None = Field(None, description="Camera ID where face was detected")
    timestamp: datetime | None = Field(None, description="When the face was detected")
    created_at: datetime = Field(..., description="When the candidate was added to queue")


class EnrollmentCandidateListResponse(BaseModel):
    """Schema for list of enrollment candidates."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": 1,
                        "face_event_id": 100,
                        "quality_score": 0.92,
                        "status": "pending",
                        "suggested_name": None,
                        "enrolled_person_id": None,
                        "camera_id": "front_door",
                        "timestamp": "2025-01-31T10:30:00Z",
                        "created_at": "2025-01-31T10:31:00Z",
                    }
                ],
                "total": 1,
            }
        }
    )

    items: list[EnrollmentCandidateResponse] = Field(
        ..., description="List of enrollment candidates"
    )
    total: int = Field(..., description="Total number of candidates")


class ApproveEnrollmentRequest(BaseModel):
    """Schema for approving an enrollment candidate.

    Either provide a name for a new person, or provide an existing
    person_id to link the face to an existing known person.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "John Doe",
                "is_household_member": True,
            }
        }
    )

    name: str | None = Field(
        None,
        min_length=1,
        max_length=100,
        description="Name for new person (required if person_id not provided)",
    )
    person_id: int | None = Field(
        None,
        description="ID of existing person to link to (optional)",
    )
    is_household_member: bool = Field(
        default=False,
        description="Whether to mark as household member",
    )


class ApproveEnrollmentResponse(BaseModel):
    """Schema for approve enrollment response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "person_id": 1,
                "person_name": "John Doe",
                "embedding_id": 5,
            }
        }
    )

    success: bool = Field(..., description="Whether approval was successful")
    person_id: int | None = Field(None, description="ID of the person")
    person_name: str | None = Field(None, description="Name of the person")
    embedding_id: int | None = Field(None, description="ID of created embedding")
    error: str | None = Field(None, description="Error message if failed")


class RejectEnrollmentRequest(BaseModel):
    """Schema for rejecting an enrollment candidate."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reason": "Not a household member",
            }
        }
    )

    reason: str | None = Field(
        None,
        max_length=500,
        description="Optional reason for rejection",
    )


class RejectEnrollmentResponse(BaseModel):
    """Schema for reject enrollment response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
            }
        }
    )

    success: bool = Field(..., description="Whether rejection was successful")


class AutoEnrollmentSettingsResponse(BaseModel):
    """Schema for auto-enrollment settings response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "enabled": True,
                "quality_threshold": 0.8,
                "similarity_threshold": 0.85,
                "auto_approve": False,
            }
        }
    )

    enabled: bool = Field(..., description="Whether auto-enrollment is enabled")
    quality_threshold: float = Field(
        ..., ge=0.0, le=1.0, description="Minimum quality score for enrollment"
    )
    similarity_threshold: float = Field(
        ..., ge=0.0, le=1.0, description="Similarity threshold for duplicate detection"
    )
    auto_approve: bool = Field(..., description="Whether to auto-approve without review queue")
