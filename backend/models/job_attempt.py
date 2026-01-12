"""Job attempt model for tracking individual job execution attempts.

This model stores detailed information about each attempt to execute a job,
including timing, worker information, and failure details. It supports the
job history API by recording the retry history and execution timeline.
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


class JobAttemptStatus(StrEnum):
    """Status of a job attempt."""

    STARTED = auto()
    SUCCEEDED = auto()
    FAILED = auto()
    CANCELLED = auto()


class JobAttempt(Base):
    """Job attempt model for tracking individual job execution attempts.

    Each job can have multiple attempts due to retries. This model stores
    information about each attempt including timing, worker assignment,
    and error details.

    Attributes:
        id: Unique identifier for this attempt record.
        job_id: Reference to the parent job UUID.
        attempt_number: Sequential attempt number (1-based).
        started_at: When this attempt started.
        ended_at: When this attempt ended (succeeded, failed, or cancelled).
        status: Current status of this attempt.
        worker_id: Identifier of the worker that processed this attempt.
        error_message: Human-readable error message if failed.
        error_traceback: Full traceback if failed.
        result: Result data if successful.
    """

    __tablename__ = "job_attempts"

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
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=str(JobAttemptStatus.STARTED),
    )
    worker_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    error_traceback: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    result: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    __table_args__ = (
        # Composite index for job_id + attempt_number queries
        Index("idx_job_attempts_job_attempt", "job_id", "attempt_number"),
        # Index for status filtering
        Index("idx_job_attempts_status", "status"),
        # BRIN index for time-series queries on started_at
        Index(
            "ix_job_attempts_started_at_brin",
            "started_at",
            postgresql_using="brin",
        ),
        # CHECK constraint for valid status values
        CheckConstraint(
            "status IN ('started', 'succeeded', 'failed', 'cancelled')",
            name="ck_job_attempts_status",
        ),
        # CHECK constraint for attempt_number >= 1
        CheckConstraint(
            "attempt_number >= 1",
            name="ck_job_attempts_attempt_number",
        ),
        # CHECK constraint for ended_at >= started_at
        CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name="ck_job_attempts_time_order",
        ),
    )

    @property
    def duration_seconds(self) -> float | None:
        """Calculate the duration of this attempt in seconds.

        Returns:
            Duration in seconds if ended_at is set, None otherwise.
        """
        if self.ended_at is None:
            return None
        return (self.ended_at - self.started_at).total_seconds()

    def __repr__(self) -> str:
        return (
            f"<JobAttempt(id={self.id}, job_id={self.job_id}, "
            f"attempt_number={self.attempt_number}, status={self.status!r})>"
        )
