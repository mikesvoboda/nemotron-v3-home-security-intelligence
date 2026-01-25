"""ExportJob model for tracking export progress.

This module defines the data model for tracking background export jobs,
including progress updates, timing information, and results.

Export Types:
    - events: Export security events
    - alerts: Export alert history
    - full_backup: Full system data backup

Job Status Flow:
    pending -> running -> completed
                      -> failed

Compliance Features (NEM-3572):
    - File expiration with configurable retention (default 7 days)
    - Download tracking for audit purposes
    - Data sensitivity acknowledgment

Usage:
    Export jobs are created when users request data exports. The export
    service updates progress as the export runs, and the frontend can
    poll for status updates or receive them via WebSocket.
"""

from datetime import datetime, timedelta
from enum import StrEnum, auto
from uuid import uuid7

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.time_utils import utc_now

from .camera import Base

# Default retention period for export files (days)
DEFAULT_EXPORT_RETENTION_DAYS = 7


class ExportJobStatus(StrEnum):
    """Export job status values."""

    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()


class ExportType(StrEnum):
    """Types of exports available."""

    EVENTS = "events"
    ALERTS = "alerts"
    FULL_BACKUP = "full_backup"


class ExportJob(Base):
    """ExportJob model for tracking export progress.

    Tracks the lifecycle of background export jobs including:
    - Progress percentage and current step
    - Items processed vs total items
    - Timing information (start, end, estimated completion)
    - Result information (output path, file size)
    - Error details for failed exports

    The model supports real-time progress updates and can be used
    by the frontend to display export status to users.
    """

    __tablename__ = "export_jobs"

    # Primary key using UUID
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid7()),
    )

    # Job status
    status: Mapped[ExportJobStatus] = mapped_column(
        Enum(
            ExportJobStatus,
            name="export_job_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ExportJobStatus.PENDING,
    )

    # Export type (events, alerts, full_backup)
    export_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    # Export format (csv, json, zip, excel)
    export_format: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="csv",
    )

    # Progress tracking
    total_items: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_step: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Timing information
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    estimated_completion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Result information
    output_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    output_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Error information
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Filter parameters used for the export (stored as JSON string)
    filter_params: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Compliance fields (NEM-3572)
    # File expiration
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=lambda: utc_now() + timedelta(days=DEFAULT_EXPORT_RETENTION_DAYS),
    )

    # Download tracking
    download_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_downloaded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Data sensitivity acknowledgment
    sensitivity_acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Indexes for common queries
    __table_args__ = (
        Index("idx_export_jobs_status", "status"),
        Index("idx_export_jobs_export_type", "export_type"),
        Index("idx_export_jobs_created_at", "created_at"),
        Index("idx_export_jobs_status_created_at", "status", "created_at"),
        # Index for expired files cleanup (NEM-3572)
        Index("idx_export_jobs_expires_at", "expires_at"),
        # CHECK constraints for business rules
        CheckConstraint(
            "progress_percent >= 0 AND progress_percent <= 100",
            name="ck_export_jobs_progress_range",
        ),
        CheckConstraint(
            "processed_items >= 0",
            name="ck_export_jobs_processed_non_negative",
        ),
        CheckConstraint(
            "total_items IS NULL OR total_items >= 0",
            name="ck_export_jobs_total_non_negative",
        ),
        CheckConstraint(
            "output_size_bytes IS NULL OR output_size_bytes >= 0",
            name="ck_export_jobs_size_non_negative",
        ),
        CheckConstraint(
            "download_count >= 0",
            name="ck_export_jobs_download_count_non_negative",
        ),
    )

    @property
    def is_complete(self) -> bool:
        """Check if the export job has finished (completed or failed).

        Returns:
            True if the job is in a terminal state.
        """
        return self.status in (ExportJobStatus.COMPLETED, ExportJobStatus.FAILED)

    @property
    def is_running(self) -> bool:
        """Check if the export job is currently running.

        Returns:
            True if the job is running.
        """
        return self.status == ExportJobStatus.RUNNING

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
            f"<ExportJob(id={self.id!r}, status={self.status.value!r}, "
            f"export_type={self.export_type!r}, progress={self.progress_percent}%)>"
        )
