"""Face recognition database models.

This module provides database models for face recognition:
- KnownPerson: Registered persons for face recognition
- FaceEmbedding: ArcFace embeddings for known persons
- FaceDetectionEvent: Face detection events from cameras
- EnrollmentCandidate: Queue for auto-enrollment review

Implements NEM-3716: Face detection with InsightFace
Implements NEM-3717: Face quality assessment for recognition
Implements NEM-4941: Face Auto-Enrollment from High-Confidence Detections
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .camera import Base

if TYPE_CHECKING:
    from .camera import Camera
    from .household import HouseholdMember


class EnrollmentStatus(str, Enum):
    """Status of an enrollment candidate.

    Attributes:
        PENDING: Candidate is waiting for review
        APPROVED: Candidate was approved and enrolled
        REJECTED: Candidate was rejected by user
        AUTO_ENROLLED: Candidate was automatically enrolled (no review)
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_ENROLLED = "auto_enrolled"


class KnownPerson(Base):
    """Known persons for face recognition.

    This model stores information about persons who have been registered
    for face recognition. When a face is detected, it can be matched
    against embeddings associated with known persons.

    Attributes:
        id: Unique identifier for the person
        name: Display name of the person
        is_household_member: Whether person is a household member (trusted)
        notes: Optional notes about the person
        created_at: When the person was registered
        updated_at: When the record was last updated
        embeddings: Associated face embeddings for this person
    """

    __tablename__ = "known_persons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_household_member: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    # Relationships
    embeddings: Mapped[list[FaceEmbedding]] = relationship(
        "FaceEmbedding",
        back_populates="person",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    detection_events: Mapped[list[FaceDetectionEvent]] = relationship(
        "FaceDetectionEvent",
        back_populates="matched_person",
        foreign_keys="FaceDetectionEvent.matched_person_id",
    )
    household_member: Mapped[HouseholdMember | None] = relationship(
        "HouseholdMember",
        back_populates="known_person",
    )

    __table_args__ = (
        # Index for name searches
        Index("idx_known_persons_name", "name"),
        # Index for filtering household members
        Index("idx_known_persons_household", "is_household_member"),
    )

    def __repr__(self) -> str:
        return (
            f"<KnownPerson(id={self.id}, name={self.name!r}, "
            f"is_household_member={self.is_household_member})>"
        )


class FaceEmbedding(Base):
    """Face embeddings for known persons.

    Stores 512-dimensional ArcFace embeddings that can be used to match
    detected faces against known persons. Multiple embeddings can be stored
    per person to improve recognition across different angles and conditions.

    Attributes:
        id: Unique identifier for the embedding
        person_id: Foreign key to the associated KnownPerson
        embedding: Serialized 512-dim float32 embedding vector
        quality_score: Face quality score when embedding was captured (0-1)
        source_image_path: Optional path to the source image
        created_at: When the embedding was created
        person: Relationship to the parent KnownPerson
    """

    __tablename__ = "face_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    person_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("known_persons.id", ondelete="CASCADE"),
        nullable=False,
    )
    embedding: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    source_image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    person: Mapped[KnownPerson] = relationship(
        "KnownPerson",
        back_populates="embeddings",
    )

    __table_args__ = (
        # Index for querying embeddings by person
        Index("idx_face_embeddings_person_id", "person_id"),
        # Index for filtering by quality
        Index("idx_face_embeddings_quality", "quality_score"),
    )

    def __repr__(self) -> str:
        return (
            f"<FaceEmbedding(id={self.id}, person_id={self.person_id}, "
            f"quality_score={self.quality_score})>"
        )


class FaceDetectionEvent(Base):
    """Face detection events from security cameras.

    Records each face detection with its embedding, match results,
    and quality metrics. This enables tracking of known and unknown
    persons over time and supports stranger detection alerts.

    Attributes:
        id: Unique identifier for the event
        camera_id: Foreign key to the camera that detected the face
        timestamp: When the face was detected
        bbox: Bounding box coordinates [x1, y1, x2, y2]
        embedding: Serialized 512-dim float32 embedding vector
        matched_person_id: FK to matched KnownPerson (None if unknown)
        match_confidence: Cosine similarity with matched person
        is_unknown: True if face is unknown (no match found)
        quality_score: Face quality score (0-1)
        age_estimate: Estimated age (optional)
        gender_estimate: Estimated gender 'M' or 'F' (optional)
        created_at: When the event was recorded
    """

    __tablename__ = "face_detection_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("cameras.id", ondelete="CASCADE"),
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(nullable=False)
    bbox: Mapped[dict] = mapped_column(JSONB, nullable=False)
    embedding: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    matched_person_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("known_persons.id", ondelete="SET NULL"),
        nullable=True,
    )
    match_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_unknown: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    age_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender_estimate: Mapped[str | None] = mapped_column(String(1), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    camera: Mapped[Camera] = relationship("Camera")
    matched_person: Mapped[KnownPerson | None] = relationship(
        "KnownPerson",
        back_populates="detection_events",
        foreign_keys=[matched_person_id],
    )

    __table_args__ = (
        # Index for querying by camera
        Index("idx_face_events_camera_id", "camera_id"),
        # Index for time-range queries
        Index("idx_face_events_timestamp", "timestamp"),
        # Index for finding unknown faces
        Index("idx_face_events_is_unknown", "is_unknown"),
        # Index for querying by matched person
        Index("idx_face_events_matched_person_id", "matched_person_id"),
        # Composite index for camera + time queries
        Index("idx_face_events_camera_timestamp", "camera_id", "timestamp"),
        # BRIN index for time-series queries
        Index(
            "idx_face_events_timestamp_brin",
            "timestamp",
            postgresql_using="brin",
        ),
        # NEM-5054: Index for match_confidence queries (filtering/sorting by confidence)
        Index("idx_face_events_confidence", "match_confidence"),
        # NEM-5054: Composite index for matched_person_id + match_confidence
        # Enables efficient queries like "all matches for person X sorted by confidence"
        Index("idx_face_events_matched_confidence", "matched_person_id", "match_confidence"),
    )

    def __repr__(self) -> str:
        match_info = f"matched={self.matched_person_id}" if self.matched_person_id else "unknown"
        return (
            f"<FaceDetectionEvent(id={self.id}, camera_id={self.camera_id!r}, "
            f"{match_info}, quality={self.quality_score:.2f})>"
        )


class EnrollmentCandidate(Base):
    """Candidates for face auto-enrollment.

    High-confidence face detections that meet quality thresholds are
    added to this queue for review or automatic enrollment. This allows
    users to approve or reject candidates before they become known persons.

    Implements NEM-4941: Face Auto-Enrollment from High-Confidence Detections

    Attributes:
        id: Unique identifier for the candidate
        face_event_id: FK to the source FaceDetectionEvent
        embedding: Copy of the face embedding (for comparison)
        quality_score: Face quality score when captured (0-1)
        status: Current enrollment status (pending/approved/rejected/auto_enrolled)
        suggested_name: Auto-generated or user-suggested name
        enrolled_person_id: FK to KnownPerson if approved
        rejection_reason: User-provided reason if rejected
        reviewed_at: When the candidate was reviewed
        created_at: When the candidate was added to queue
    """

    __tablename__ = "enrollment_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    face_event_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("face_detection_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    embedding: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        default=EnrollmentStatus.PENDING.value,
        nullable=False,
    )
    suggested_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    enrolled_person_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("known_persons.id", ondelete="SET NULL"),
        nullable=True,
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    face_event: Mapped[FaceDetectionEvent] = relationship(
        "FaceDetectionEvent",
        foreign_keys=[face_event_id],
    )
    enrolled_person: Mapped[KnownPerson | None] = relationship(
        "KnownPerson",
        foreign_keys=[enrolled_person_id],
    )

    __table_args__ = (
        # Index for querying by status
        Index("idx_enrollment_candidates_status", "status"),
        # Index for querying by face event
        Index("idx_enrollment_candidates_face_event", "face_event_id"),
        # Index for time-based queries
        Index("idx_enrollment_candidates_created_at", "created_at"),
        # Index for filtering pending candidates
        Index(
            "idx_enrollment_candidates_pending",
            "status",
            postgresql_where=(status == EnrollmentStatus.PENDING.value),
        ),
    )

    def __repr__(self) -> str:
        quality = f"{self.quality_score:.2f}" if self.quality_score is not None else "None"
        return (
            f"<EnrollmentCandidate(id={self.id}, face_event_id={self.face_event_id}, "
            f"status={self.status}, quality={quality})>"
        )
