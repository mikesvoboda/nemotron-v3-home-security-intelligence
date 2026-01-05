"""Log model for structured application logging."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .camera import Base


class Log(Base):
    """Log model for storing structured application logs.

    Supports filtering by level, component, camera, and time range.
    Stores additional context in JSON extra field.
    """

    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    level: Mapped[str] = mapped_column(String(10), nullable=False)
    component: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Structured metadata (nullable, for filtering)
    camera_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    event_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    detection_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Performance/debug fields
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extra: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Source tracking
    source: Mapped[str] = mapped_column(String(10), default="backend", nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Indexes for common queries
    __table_args__ = (
        Index("idx_logs_timestamp", "timestamp"),
        Index("idx_logs_level", "level"),
        Index("idx_logs_component", "component"),
        Index("idx_logs_camera_id", "camera_id"),
        Index("idx_logs_source", "source"),
    )

    def __repr__(self) -> str:
        msg_preview = self.message[:50] if self.message else ""
        return (
            f"<Log(id={self.id}, level={self.level!r}, "
            f"component={self.component!r}, message={msg_preview!r}...)>"
        )
