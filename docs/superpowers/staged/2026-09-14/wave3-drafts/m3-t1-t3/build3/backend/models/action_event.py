"""ActionEvent model for storing X-CLIP action recognition results.

This module contains the ActionEvent SQLAlchemy model for storing action
recognition results from the X-CLIP video action recognition model.
The model captures detected actions from video frame sequences, including
confidence scores and security-relevance flags.

X-CLIP analyzes sequences of frames to understand temporal patterns and
classify human actions in security-relevant scenarios.

Reference: ai/enrichment/models/action_recognizer.py
Reference: backend/services/xclip_loader.py
Linear issue: NEM-3714
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .camera import Base

if TYPE_CHECKING:
    from .camera import Camera
    from .track import Track


class ActionEvent(Base):
    """Stores action recognition results from X-CLIP model.

    Each action event represents a detected action from analyzing a sequence
    of video frames. The model is designed to capture security-relevant
    human activities detected by X-CLIP zero-shot classification.

    Attributes:
        id: Primary key
        camera_id: Reference to the camera where action was detected
        track_id: Optional reference to the tracked object (for person tracking)
        action: The detected action label (e.g., "walking normally", "climbing")
        confidence: Confidence score for the action classification (0.0 to 1.0)
        is_suspicious: Flag indicating if the action is security-relevant
        timestamp: When the action was detected
        frame_count: Number of frames analyzed for this action
        all_scores: Dictionary mapping all action classes to their scores
        created_at: Record creation timestamp
    """

    __tablename__ = "action_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    camera_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("cameras.id", ondelete="CASCADE"),
        nullable=False,
        comment="Camera where action was detected",
    )
    track_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("tracks.id", ondelete="SET NULL"),
        nullable=True,
        comment="Optional reference to tracked object",
    )
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Detected action: walking normally, climbing, etc.",
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Action classification confidence (0.0 to 1.0)",
    )
    is_suspicious: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether the action is flagged as security-relevant",
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="When the action was detected",
    )
    frame_count: Mapped[int] = mapped_column(
        Integer,
        default=8,
        nullable=False,
        comment="Number of frames analyzed for this action",
    )
    all_scores: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Dict of action -> score for all candidates",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    camera: Mapped[Camera] = relationship("Camera", back_populates="action_events")
    track: Mapped[Track | None] = relationship("Track", back_populates="action_events")

    __table_args__ = (
        # Indexes for efficient querying
        Index("idx_action_events_camera_id", "camera_id"),
        Index("idx_action_events_track_id", "track_id"),
        Index("idx_action_events_timestamp", "timestamp"),
        Index("idx_action_events_action", "action"),
        Index("idx_action_events_is_suspicious", "is_suspicious"),
        # Composite index for queries like "find all suspicious actions for a camera"
        Index("idx_action_events_camera_suspicious", "camera_id", "is_suspicious"),
        # Composite index for time-range queries per camera
        Index("idx_action_events_camera_time", "camera_id", "timestamp"),
        # BRIN index for time-series queries (efficient for chronological data)
        Index(
            "ix_action_events_timestamp_brin",
            "timestamp",
            postgresql_using="brin",
        ),
        # Check constraints for valid values
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_action_events_confidence_range",
        ),
        CheckConstraint(
            "frame_count > 0",
            name="ck_action_events_frame_count_positive",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ActionEvent(id={self.id}, camera_id={self.camera_id!r}, "
            f"action={self.action!r}, confidence={self.confidence:.2f}, "
            f"is_suspicious={self.is_suspicious})>"
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses.

        Returns:
            Dictionary with all action event fields suitable for JSON serialization.
        """
        return {
            "id": self.id,
            "camera_id": self.camera_id,
            "track_id": self.track_id,
            "action": self.action,
            "confidence": self.confidence,
            "is_suspicious": self.is_suspicious,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "frame_count": self.frame_count,
            "all_scores": self.all_scores,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
