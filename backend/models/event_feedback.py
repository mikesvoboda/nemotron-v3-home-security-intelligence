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

    Four feedback types support comprehensive calibration:
    - ACCURATE/CORRECT: The alert was accurate and appropriately flagged
    - FALSE_POSITIVE: Event was incorrectly flagged as concerning (no real threat)
    - MISSED_THREAT: A real threat was not detected (missed detection)
    - SEVERITY_WRONG: Threat detected but severity level was incorrect
    """

    ACCURATE = "accurate"
    CORRECT = "correct"
    FALSE_POSITIVE = "false_positive"
    MISSED_THREAT = "missed_threat"
    SEVERITY_WRONG = "severity_wrong"

    def __str__(self) -> str:
        """Return string representation of feedback type."""
        return self.value


class EventFeedback(Base):
    """EventFeedback model for tracking user feedback on security events.

    Users can provide feedback on events to calibrate personalized risk thresholds.
    Four feedback types are supported:
    - correct: Alert was accurate
    - false_positive: Alert was wrong (no real threat)
    - missed_threat: A real threat was not detected
    - severity_wrong: Threat detected but severity was incorrect

    For severity_wrong feedback, the expected_severity field stores what the
    user believes the correct severity should have been.

    Database constraints:
    - UNIQUE(event_id): One feedback per event maximum
    - Foreign key to events table with CASCADE delete
    - CHECK constraint on expected_severity values
    """

    __tablename__ = "event_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    feedback_type: Mapped[FeedbackType] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # For severity_wrong feedback: what severity the user expected
    expected_severity: Mapped[str | None] = mapped_column(String, nullable=True)
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
            "feedback_type IN ('accurate', 'correct', 'false_positive', 'missed_threat', 'severity_wrong')",
            name="ck_event_feedback_type",
        ),
        # CHECK constraint for expected_severity values (must be valid severity or NULL)
        CheckConstraint(
            "expected_severity IS NULL OR expected_severity IN ('low', 'medium', 'high', 'critical')",
            name="ck_event_feedback_expected_severity",
        ),
    )

    def __repr__(self) -> str:
        """Return string representation of EventFeedback."""
        return (
            f"<EventFeedback(id={self.id}, event_id={self.event_id}, "
            f"feedback_type={self.feedback_type})>"
        )
