"""Event model for security event tracking."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .camera import Base
from .enums import Severity

if TYPE_CHECKING:
    from .alert import Alert
    from .camera import Camera


class Event(Base):
    """Event model representing a security event.

    Events are aggregated from multiple detections within a time window,
    analyzed by the LLM to determine risk level and generate summaries.

    The search_vector column is a PostgreSQL TSVECTOR that enables full-text search
    across summary, reasoning, and object types. It is populated via a database trigger.
    """

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String, nullable=False)
    camera_id: Mapped[str] = mapped_column(
        String, ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    detection_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_fast_path: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Cached object types from related detections (comma-separated string)
    # Populated by the batch aggregator when events are created
    object_types: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Full-text search vector (PostgreSQL TSVECTOR)
    # This column is auto-populated by a database trigger on INSERT/UPDATE
    # Combines: summary, reasoning, object_types, and camera_name (via join)
    search_vector: Mapped[Any] = mapped_column(TSVECTOR, nullable=True)

    # Relationships
    camera: Mapped[Camera] = relationship("Camera", back_populates="events")
    alerts: Mapped[list[Alert]] = relationship(
        "Alert", back_populates="event", cascade="all, delete-orphan"
    )

    # Indexes for common queries
    __table_args__ = (
        Index("idx_events_camera_id", "camera_id"),
        Index("idx_events_started_at", "started_at"),
        Index("idx_events_risk_score", "risk_score"),
        Index("idx_events_reviewed", "reviewed"),
        Index("idx_events_batch_id", "batch_id"),
        # GIN index for full-text search
        Index("idx_events_search_vector", "search_vector", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        return (
            f"<Event(id={self.id}, batch_id={self.batch_id!r}, "
            f"camera_id={self.camera_id!r}, risk_score={self.risk_score})>"
        )

    def get_severity(self) -> Severity | None:
        """Get the severity level for this event based on risk score.

        Uses the SeverityService to map the risk_score to a Severity enum.
        Returns None if no risk_score is set.

        Returns:
            Severity enum value or None if risk_score is not set
        """
        if self.risk_score is None:
            return None

        # Import here to avoid circular dependency
        from backend.services.severity import get_severity_service

        service = get_severity_service()
        return service.risk_score_to_severity(self.risk_score)
