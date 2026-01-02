"""EventAudit model for AI pipeline performance tracking."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .camera import Base

if TYPE_CHECKING:
    from .event import Event


def _utc_now() -> datetime:
    """Return current UTC time as a timezone-aware datetime."""
    return datetime.now(UTC)


class EventAudit(Base):
    """Audit record for AI pipeline performance on an event.

    Tracks which models contributed to an event's analysis, quality scores
    from Nemotron self-evaluation, and prompt improvement suggestions.
    """

    __tablename__ = "event_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    audited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utc_now
    )

    # Model contribution flags (captured real-time)
    has_rtdetr: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_florence: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_clip: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_violence: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_clothing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_vehicle: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_pet: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_weather: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_image_quality: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_zones: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_baseline: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_cross_camera: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Prompt metrics
    prompt_length: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    prompt_token_estimate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    enrichment_utilization: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Self-evaluation scores (1-5 scale, NULL if not yet evaluated)
    context_usage_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reasoning_coherence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_justification_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    consistency_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    overall_quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Consistency check data
    consistency_risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    consistency_diff: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Self-evaluation text
    self_eval_critique: Mapped[str | None] = mapped_column(Text, nullable=True)
    self_eval_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    self_eval_response: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Prompt improvement suggestions (JSON arrays stored as text)
    missing_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    confusing_sections: Mapped[str | None] = mapped_column(Text, nullable=True)
    unused_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    format_suggestions: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_gaps: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationship
    event: Mapped[Event] = relationship("Event", back_populates="audit")

    # Indexes
    __table_args__ = (
        Index("idx_event_audits_event_id", "event_id"),
        Index("idx_event_audits_audited_at", "audited_at"),
        Index("idx_event_audits_overall_score", "overall_quality_score"),
    )

    @property
    def is_fully_evaluated(self) -> bool:
        """Check if full self-evaluation has been run."""
        return self.overall_quality_score is not None

    def __repr__(self) -> str:
        return (
            f"<EventAudit(id={self.id}, event_id={self.event_id}, "
            f"overall_score={self.overall_quality_score})>"
        )
