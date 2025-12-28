"""Event model for security event tracking."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .camera import Base

if TYPE_CHECKING:
    from .camera import Camera


class Event(Base):
    """Event model representing a security event.

    Events are aggregated from multiple detections within a time window,
    analyzed by the LLM to determine risk level and generate summaries.
    """

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String, nullable=False)
    camera_id: Mapped[str] = mapped_column(
        String, ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    detection_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_fast_path: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    camera: Mapped[Camera] = relationship("Camera", back_populates="events")

    # Indexes for common queries
    __table_args__ = (
        Index("idx_events_camera_id", "camera_id"),
        Index("idx_events_started_at", "started_at"),
        Index("idx_events_risk_score", "risk_score"),
        Index("idx_events_reviewed", "reviewed"),
        Index("idx_events_batch_id", "batch_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<Event(id={self.id}, batch_id={self.batch_id!r}, "
            f"camera_id={self.camera_id!r}, risk_score={self.risk_score})>"
        )
