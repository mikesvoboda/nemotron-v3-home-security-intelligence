"""EventFeedback model for user feedback on security events.

Enhanced with calibration fields for Nemotron prompt improvement (NEM-3330):
- actual_threat_level: User's assessment of true threat level
- suggested_score: What the user thinks the score should have been
- actual_identity: Identity correction for household member learning
- what_was_wrong: Detailed explanation of AI failure
- model_failures: List of specific AI models that failed
"""

from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
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

    Enhanced fields for Nemotron prompt improvement (NEM-3330):
    - actual_threat_level: User's assessment ("no_threat", "minor_concern", "genuine_threat")
    - suggested_score: What the user thinks the risk score should have been (0-100)
    - actual_identity: Identity correction ("That was Mike") for household learning
    - what_was_wrong: Detailed text explanation of what the AI got wrong
    - model_failures: List of specific AI models that failed (e.g., ["florence_vqa", "pose_model"])

    Database constraints:
    - UNIQUE(event_id): One feedback per event maximum
    - Foreign key to events table with CASCADE delete
    - CHECK constraint on expected_severity values
    - CHECK constraint on actual_threat_level values
    - CHECK constraint on suggested_score range (0-100)
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

    # Enhanced feedback fields (NEM-3330: Nemotron prompt improvements)
    # User's assessment of true threat level
    actual_threat_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # What the user thinks the score should have been (0-100)
    suggested_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Identity correction for household member learning (e.g., "Mike (neighbor)")
    actual_identity: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Detailed explanation of what was wrong
    what_was_wrong: Mapped[str | None] = mapped_column(Text, nullable=True)
    # List of specific AI models that failed (e.g., ["florence_vqa", "pose_model"])
    model_failures: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)

    # Relationship
    event: Mapped[Event] = relationship("Event", back_populates="feedback")

    __table_args__ = (
        # Index for querying feedback by event
        Index("idx_event_feedback_event_id", "event_id"),
        # Index for filtering by feedback type
        Index("idx_event_feedback_type", "feedback_type"),
        # Index for time-based queries
        Index("idx_event_feedback_created_at", "created_at"),
        # Index for filtering by actual_threat_level (calibration queries)
        Index("idx_event_feedback_actual_threat_level", "actual_threat_level"),
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
        # CHECK constraint for actual_threat_level values (NEM-3330)
        CheckConstraint(
            "actual_threat_level IS NULL OR actual_threat_level IN ('no_threat', 'minor_concern', 'genuine_threat')",
            name="ck_event_feedback_actual_threat_level",
        ),
        # CHECK constraint for suggested_score range 0-100 (NEM-3330)
        CheckConstraint(
            "suggested_score IS NULL OR (suggested_score >= 0 AND suggested_score <= 100)",
            name="ck_event_feedback_suggested_score",
        ),
    )

    def __repr__(self) -> str:
        """Return string representation of EventFeedback."""
        return (
            f"<EventFeedback(id={self.id}, event_id={self.event_id}, "
            f"feedback_type={self.feedback_type})>"
        )
