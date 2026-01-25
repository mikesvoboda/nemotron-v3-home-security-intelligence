"""BackupJob and RestoreJob models for tracking backup/restore operations.

This module defines the data models for tracking background backup and
restore jobs, including progress updates, timing information, and results.

Backup Job Status Flow:
    pending -> running -> completed
                      -> failed

Restore Job Status Flow:
    pending -> validating -> restoring -> completed
                         -> failed

Usage:
    Backup jobs are created when users request full system backups.
    Restore jobs are created when users upload backup files for restoration.
    Both job types support progress tracking and can be polled for status.
"""

from datetime import datetime
from enum import StrEnum, auto
from uuid import uuid7

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.time_utils import utc_now

from .camera import Base


class BackupJobStatus(StrEnum):
    """Backup job status values."""

    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()


class RestoreJobStatus(StrEnum):
    """Restore job status values."""

    PENDING = auto()
    VALIDATING = auto()
    RESTORING = auto()
    COMPLETED = auto()
    FAILED = auto()


class BackupJob(Base):
    """Model for tracking backup job progress.

    Tracks the lifecycle of background backup jobs including:
    - Progress percentage and current step
    - Tables exported vs total tables
    - Timing information (start, end)
    - Result information (output path, file size, manifest)
    - Error details for failed backups

    The model supports real-time progress updates and can be used
    by the frontend to display backup status to users.
    """

    __tablename__ = "backup_jobs"

    # Primary key using UUID
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid7()),
    )

    # Job status
    status: Mapped[BackupJobStatus] = mapped_column(
        Enum(
            BackupJobStatus,
            name="backup_job_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=BackupJobStatus.PENDING,
    )

    # Progress tracking
    total_tables: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    completed_tables: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_step: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Timing
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Result
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    manifest_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Error
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Indexes for common queries
    __table_args__ = (
        Index("idx_backup_jobs_status", "status"),
        Index("idx_backup_jobs_created_at", "created_at"),
        # CHECK constraints for business rules
        CheckConstraint(
            "progress_percent >= 0 AND progress_percent <= 100",
            name="ck_backup_progress_range",
        ),
    )

    @property
    def is_complete(self) -> bool:
        """Check if the backup job has finished (completed or failed).

        Returns:
            True if the job is in a terminal state.
        """
        return self.status in (BackupJobStatus.COMPLETED, BackupJobStatus.FAILED)

    @property
    def is_running(self) -> bool:
        """Check if the backup job is currently running.

        Returns:
            True if the job is running.
        """
        return self.status == BackupJobStatus.RUNNING

    @property
    def duration_seconds(self) -> float | None:
        """Calculate the job duration in seconds.

        Returns:
            Duration in seconds if started, None otherwise.
        """
        if self.started_at is None:
            return None

        end_time = self.completed_at if self.completed_at else utc_now()
        return (end_time - self.started_at).total_seconds()

    def __repr__(self) -> str:
        return (
            f"<BackupJob(id={self.id!r}, status={self.status.value!r}, "
            f"progress={self.progress_percent}%)>"
        )


class RestoreJob(Base):
    """Model for tracking restore job progress.

    Tracks the lifecycle of background restore jobs including:
    - Progress percentage and current step
    - Tables restored vs total tables
    - Source backup information
    - Timing information (start, end)
    - Result information (items restored per table)
    - Error details for failed restores

    The model supports real-time progress updates and can be used
    by the frontend to display restore status to users.
    """

    __tablename__ = "restore_jobs"

    # Primary key using UUID
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid7()),
    )

    # Job status
    status: Mapped[RestoreJobStatus] = mapped_column(
        Enum(
            RestoreJobStatus,
            name="restore_job_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=RestoreJobStatus.PENDING,
    )

    # Source backup info
    backup_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    backup_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Progress tracking
    total_tables: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    completed_tables: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_step: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Timing
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Result
    items_restored: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Error
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Indexes for common queries
    __table_args__ = (
        Index("idx_restore_jobs_status", "status"),
        Index("idx_restore_jobs_created_at", "created_at"),
        # CHECK constraints for business rules
        CheckConstraint(
            "progress_percent >= 0 AND progress_percent <= 100",
            name="ck_restore_progress_range",
        ),
    )

    @property
    def is_complete(self) -> bool:
        """Check if the restore job has finished (completed or failed).

        Returns:
            True if the job is in a terminal state.
        """
        return self.status in (RestoreJobStatus.COMPLETED, RestoreJobStatus.FAILED)

    @property
    def is_running(self) -> bool:
        """Check if the restore job is currently running.

        Returns:
            True if the job is validating or restoring.
        """
        return self.status in (RestoreJobStatus.VALIDATING, RestoreJobStatus.RESTORING)

    @property
    def duration_seconds(self) -> float | None:
        """Calculate the job duration in seconds.

        Returns:
            Duration in seconds if started, None otherwise.
        """
        if self.started_at is None:
            return None

        end_time = self.completed_at if self.completed_at else utc_now()
        return (end_time - self.started_at).total_seconds()

    def __repr__(self) -> str:
        return (
            f"<RestoreJob(id={self.id!r}, status={self.status.value!r}, "
            f"progress={self.progress_percent}%)>"
        )
