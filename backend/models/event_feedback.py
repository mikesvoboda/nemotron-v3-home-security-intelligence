"""EventFeedback model for user feedback on security events."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .camera import Base

if TYPE_CHECKING:
    from .event import Event


class FeedbackType(str, Enum):
    """Types of feedback users can provide on events.

    - FALSE_POSITIVE: Event was incorrectly flagged as concerning
    - MISSED_DETECTION: System failed to detect a concerning event
    """

    FALSE_POSITIVE = "false_positive"
    MISSED_DETECTION = "missed_detection"

    def __str__(self) -> str:
        """Return string representation of feedback type."""
        return self.value


class EventFeedback(Base):
    """EventFeedback model for tracking user feedback on security events.

    Users can mark events as false positives or missed detections,
    which is used to calibrate personalized risk thresholds.

    Database constraints:
    - UNIQUE(event_id): One feedback per event maximum
    - Foreign key to events table with CASCADE delete
    """

    __tablename__ = "event_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    feedback_type: Mapped[FeedbackType] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    # Relationship
    event: Mapped[Event] = relationship("Event", back_populates="feedback")

    __table_args__ = (
        # Index for querying feedback by event
        Index("idx_event_feedback_event_id", "event_id"),
        # Index for filtering by feedback type
        Index("idx_event_feedback_type", "feedback_type"),
        # Index for time-based queries
        Index("idx_event_feedback_created_at", "created_at"),
        # CHECK constraint for valid feedback types
        CheckConstraint(
            "feedback_type IN ('false_positive', 'missed_detection')",
            name="ck_event_feedback_type",
        ),
    )

    def __repr__(self) -> str:
        """Return string representation of EventFeedback."""
        return (
            f"<EventFeedback(id={self.id}, event_id={self.event_id}, "
            f"feedback_type={self.feedback_type.value})>"
        )
