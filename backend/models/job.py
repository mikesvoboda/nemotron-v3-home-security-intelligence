"""Job model for background job tracking.

This model provides persistent storage for background jobs in PostgreSQL,
enabling job tracking, filtering, and historical job data retention.

Jobs go through states: QUEUED -> RUNNING -> COMPLETED/FAILED/CANCELLED
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.camera import Base


class JobStatus(str, Enum):
    """Status of a background job.

    Represents the lifecycle states of a job:
    - QUEUED: Job is waiting to be processed
    - RUNNING: Job is currently executing
    - COMPLETED: Job finished successfully
    - FAILED: Job encountered an error
    - CANCELLED: Job was cancelled by user request
    """

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    def __str__(self) -> str:
        """Return string representation of job status."""
        return self.value


class Job(Base):
    """Job model representing a background job.

    Jobs are created for long-running background operations such as exports,
    imports, cleanup tasks, and backups. This model provides persistent
    storage for job tracking with progress updates, results, and error handling.

    Attributes:
        id: Unique job identifier (UUID string)
        job_type: Type of job (e.g., 'export', 'cleanup', 'backup', 'import')
        status: Current job status (queued, running, completed, failed, cancelled)
        queue_name: Name of the queue this job is assigned to
        priority: Job priority (0 = highest, 4 = lowest)
        created_at: Timestamp when job was created
        started_at: Timestamp when job started running
        completed_at: Timestamp when job finished (success or failure)
        progress_percent: Progress percentage (0-100)
        current_step: Description of current processing step
        result: JSON result data for completed jobs
        error_message: Error message for failed jobs
        error_traceback: Full error traceback for debugging
        attempt_number: Current attempt number (for retries)
        max_attempts: Maximum number of retry attempts
        next_retry_at: Timestamp for next retry attempt
    """

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=JobStatus.QUEUED.value,
    )
    queue_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=2)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Progress tracking
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_step: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Result and error handling
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_traceback: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Retry handling
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Indexes for common queries
    __table_args__ = (
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_job_type", "job_type"),
        Index("idx_jobs_created_at", "created_at"),
        Index("idx_jobs_queue_name", "queue_name"),
        Index("idx_jobs_priority", "priority"),
        # Composite index for filtered listing queries
        Index("idx_jobs_status_created_at", "status", "created_at"),
        Index("idx_jobs_job_type_status", "job_type", "status"),
        # BRIN index for time-series queries on created_at (append-only data)
        Index(
            "ix_jobs_created_at_brin",
            "created_at",
            postgresql_using="brin",
        ),
        # CHECK constraints
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_jobs_status",
        ),
        CheckConstraint(
            "progress_percent >= 0 AND progress_percent <= 100",
            name="ck_jobs_progress_range",
        ),
        CheckConstraint(
            "priority >= 0 AND priority <= 4",
            name="ck_jobs_priority_range",
        ),
        CheckConstraint(
            "attempt_number >= 1",
            name="ck_jobs_attempt_number_min",
        ),
        CheckConstraint(
            "max_attempts >= 1",
            name="ck_jobs_max_attempts_min",
        ),
        CheckConstraint(
            "completed_at IS NULL OR completed_at >= created_at",
            name="ck_jobs_completed_after_created",
        ),
        CheckConstraint(
            "started_at IS NULL OR started_at >= created_at",
            name="ck_jobs_started_after_created",
        ),
    )

    @property
    def is_active(self) -> bool:
        """Check if the job is still active (queued or running).

        Returns:
            True if the job is queued or running, False otherwise.
        """
        return self.status in (JobStatus.QUEUED.value, JobStatus.RUNNING.value)

    @property
    def is_finished(self) -> bool:
        """Check if the job has finished (completed, failed, or cancelled).

        Returns:
            True if the job has finished, False otherwise.
        """
        return self.status in (
            JobStatus.COMPLETED.value,
            JobStatus.FAILED.value,
            JobStatus.CANCELLED.value,
        )

    @property
    def can_retry(self) -> bool:
        """Check if the job can be retried.

        A job can be retried if it has failed and has remaining attempts.

        Returns:
            True if the job can be retried, False otherwise.
        """
        return self.status == JobStatus.FAILED.value and self.attempt_number < self.max_attempts

    @property
    def duration_seconds(self) -> float | None:
        """Calculate the duration of the job in seconds.

        Returns:
            Duration in seconds if both started_at and completed_at are set,
            None otherwise.
        """
        if self.started_at is None or self.completed_at is None:
            return None
        return (self.completed_at - self.started_at).total_seconds()

    def start(self) -> None:
        """Mark the job as started/running.

        Sets the status to RUNNING and records the start timestamp.
        """
        self.status = JobStatus.RUNNING.value
        self.started_at = datetime.now(UTC)

    def complete(self, result: dict[str, Any] | None = None) -> None:
        """Mark the job as completed.

        Sets the status to COMPLETED, progress to 100%, and records
        the completion timestamp and optional result.

        Args:
            result: Optional result data to store with the job.
        """
        self.status = JobStatus.COMPLETED.value
        self.progress_percent = 100
        self.completed_at = datetime.now(UTC)
        self.current_step = "Completed"
        if result is not None:
            self.result = result

    def fail(self, error_message: str, error_traceback: str | None = None) -> None:
        """Mark the job as failed.

        Sets the status to FAILED and records the error information.

        Args:
            error_message: Human-readable error message.
            error_traceback: Optional full error traceback for debugging.
        """
        self.status = JobStatus.FAILED.value
        self.completed_at = datetime.now(UTC)
        self.error_message = error_message
        self.error_traceback = error_traceback
        self.current_step = (
            f"Failed: {error_message[:50]}..."
            if len(error_message) > 50
            else f"Failed: {error_message}"
        )

    def cancel(self) -> None:
        """Mark the job as cancelled.

        Can only cancel jobs that are queued or running.
        """
        if self.is_active:
            self.status = JobStatus.CANCELLED.value
            self.completed_at = datetime.now(UTC)
            self.current_step = "Cancelled by user"
            self.error_message = "Job cancelled by user request"

    def update_progress(self, progress_percent: int, current_step: str | None = None) -> None:
        """Update the job progress.

        Args:
            progress_percent: New progress value (clamped to 0-100).
            current_step: Optional description of current processing step.
        """
        self.progress_percent = max(0, min(100, progress_percent))
        if current_step is not None:
            self.current_step = current_step

    def prepare_retry(self) -> None:
        """Prepare the job for a retry attempt.

        Increments the attempt number and resets the status to QUEUED.
        Should only be called when can_retry is True.
        """
        if self.can_retry:
            self.attempt_number += 1
            self.status = JobStatus.QUEUED.value
            self.started_at = None
            self.completed_at = None
            self.error_message = None
            self.error_traceback = None
            self.progress_percent = 0
            self.current_step = None

    def __repr__(self) -> str:
        return (
            f"<Job(id={self.id!r}, job_type={self.job_type!r}, "
            f"status={self.status!r}, progress={self.progress_percent}%)>"
        )
