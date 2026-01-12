"""Job log model for storing job execution logs.

This model stores log entries generated during job execution, allowing
for detailed debugging and audit trails. Logs are associated with specific
job attempts and include log level, timestamps, and optional context.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum, auto
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from .camera import Base


class LogLevel(StrEnum):
    """Log level enumeration for job logs."""

    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()


class JobLog(Base):
    """Job log model for storing job execution logs.

    Each log entry is associated with a specific job and optionally an attempt.
    Logs include level, message, timestamp, and optional context data.

    Attributes:
        id: Unique identifier for this log entry.
        job_id: Reference to the parent job UUID.
        attempt_number: Which attempt generated this log (for correlation).
        timestamp: When the log entry was created.
        level: Log level (DEBUG, INFO, WARNING, ERROR).
        message: The log message.
        context: Optional structured context data (e.g., metrics, metadata).
    """

    __tablename__ = "job_logs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    job_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    level: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default=str(LogLevel.INFO),
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    context: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    __table_args__ = (
        # Composite index for job_id + attempt_number queries
        Index("idx_job_logs_job_attempt", "job_id", "attempt_number"),
        # Index for level filtering
        Index("idx_job_logs_level", "level"),
        # Composite index for job_id + timestamp (for time range queries)
        Index("idx_job_logs_job_timestamp", "job_id", "timestamp"),
        # BRIN index for time-series queries on timestamp
        Index(
            "ix_job_logs_timestamp_brin",
            "timestamp",
            postgresql_using="brin",
        ),
        # CHECK constraint for valid log levels
        CheckConstraint(
            "level IN ('debug', 'info', 'warning', 'error')",
            name="ck_job_logs_level",
        ),
        # CHECK constraint for attempt_number >= 1
        CheckConstraint(
            "attempt_number >= 1",
            name="ck_job_logs_attempt_number",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<JobLog(id={self.id}, job_id={self.job_id}, "
            f"level={self.level!r}, message={self.message[:50]!r}...)>"
        )
