"""Summary model for LLM-generated event summaries."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.models.camera import Base


class SummaryType(str, Enum):
    """Types of summaries that can be generated.

    Attributes:
        HOURLY: Summary covering the past 60 minutes
        DAILY: Summary covering since midnight today
    """

    HOURLY = "hourly"
    DAILY = "daily"


class Summary(Base):
    """LLM-generated narrative summary of security events.

    Summaries are generated every 5 minutes by a background job and provide
    high-level descriptions of high/critical events for the dashboard.

    The summary contains a natural language narrative (2-4 sentences) describing
    notable security activity in the time window, or a reassuring "all clear"
    message when no high-priority events occurred.

    Attributes:
        id: Auto-increment primary key
        summary_type: Type of summary ('hourly' or 'daily')
        content: LLM-generated narrative text
        event_count: Number of high/critical events included
        event_ids: Array of event IDs that were summarized (nullable)
        window_start: Start of the time window
        window_end: End of the time window
        generated_at: When the LLM produced this summary
        created_at: Row creation timestamp (auto-set by database)
    """

    __tablename__ = "summaries"
    __table_args__ = (
        CheckConstraint(
            "summary_type IN ('hourly', 'daily')",
            name="summaries_type_check",
        ),
        Index("idx_summaries_type_created", "summary_type", "created_at"),
        Index("idx_summaries_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    summary_type: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False)
    event_ids: Mapped[list[int] | None] = mapped_column(ARRAY(Integer), nullable=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<Summary(id={self.id}, type={self.summary_type}, events={self.event_count})>"
