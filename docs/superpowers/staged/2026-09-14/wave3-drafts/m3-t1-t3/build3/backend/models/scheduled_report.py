"""ScheduledReport model for scheduled reports and exports.

This module defines the data model for scheduled reports including:
- Report frequency (daily, weekly, monthly)
- Schedule configuration (hour, minute, day of week, day of month, timezone)
- Output format (pdf, csv, json)
- Email recipients for delivery
- Report content options (charts, event details)
- Tracking of last and next run times

Scheduled reports are executed by a background scheduler that checks
next_run_at to determine when reports should be generated and sent.
"""

from datetime import datetime
from enum import StrEnum, auto

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from backend.core.time_utils import utc_now

from .camera import Base


class ReportFrequency(StrEnum):
    """Frequency options for scheduled reports.

    Attributes:
        DAILY: Report runs every day at specified time
        WEEKLY: Report runs on specified day of week
        MONTHLY: Report runs on specified day of month
    """

    DAILY = auto()
    WEEKLY = auto()
    MONTHLY = auto()


class ReportFormat(StrEnum):
    """Output format options for scheduled reports.

    Attributes:
        PDF: Portable Document Format with charts and summaries
        CSV: Comma-separated values for data analysis
        JSON: Machine-readable JSON format
    """

    PDF = auto()
    CSV = auto()
    JSON = auto()


class ScheduledReport(Base):
    """ScheduledReport model for managing scheduled reports.

    Represents a scheduled report configuration that defines when and how
    reports should be generated and who should receive them.

    Schedule Configuration:
        - hour: Hour of day to run (0-23)
        - minute: Minute of hour to run (0-59)
        - day_of_week: Day of week (0=Monday to 6=Sunday) for weekly reports
        - day_of_month: Day of month (1-31) for monthly reports
        - timezone: Timezone for scheduling (e.g., 'America/New_York')

    Recipients:
        Stored as PostgreSQL array of email addresses in email_recipients field.

    Content Options:
        - include_charts: Whether to include visual charts
        - include_event_details: Whether to include detailed event breakdowns

    Tracking:
        - last_run_at: When the report was last generated
        - next_run_at: When the report should next be generated
    """

    __tablename__ = "scheduled_reports"

    # Primary key using auto-increment integer
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Report configuration
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    frequency: Mapped[str] = mapped_column(
        Enum(
            ReportFrequency,
            name="report_frequency",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Schedule configuration
    day_of_week: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )  # 0-6 for weekly (0=Monday)
    day_of_month: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-31 for monthly
    hour: Mapped[int] = mapped_column(Integer, nullable=False, default=8)  # 0-23
    minute: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0-59
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="UTC")

    # Output format
    format: Mapped[str] = mapped_column(
        Enum(
            ReportFormat,
            name="report_format",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ReportFormat.PDF.value,
    )

    # Email recipients (PostgreSQL array of strings)
    email_recipients: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    # Report content options
    include_charts: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    include_event_details: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Run tracking
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    # Indexes and constraints
    __table_args__ = (
        Index("idx_scheduled_reports_enabled", "enabled"),
        Index("idx_scheduled_reports_frequency", "frequency"),
        Index("idx_scheduled_reports_next_run_at", "next_run_at"),
        Index("idx_scheduled_reports_enabled_next_run", "enabled", "next_run_at"),
        # CHECK constraints for business rules
        CheckConstraint(
            "day_of_week IS NULL OR (day_of_week >= 0 AND day_of_week <= 6)",
            name="ck_scheduled_reports_day_of_week_range",
        ),
        CheckConstraint(
            "day_of_month IS NULL OR (day_of_month >= 1 AND day_of_month <= 31)",
            name="ck_scheduled_reports_day_of_month_range",
        ),
        CheckConstraint(
            "hour >= 0 AND hour <= 23",
            name="ck_scheduled_reports_hour_range",
        ),
        CheckConstraint(
            "minute >= 0 AND minute <= 59",
            name="ck_scheduled_reports_minute_range",
        ),
    )

    @property
    def is_due(self) -> bool:
        """Check if the report is due to run.

        Returns:
            True if enabled and next_run_at is in the past.
        """
        if not self.enabled or self.next_run_at is None:
            return False
        return utc_now() >= self.next_run_at

    def __repr__(self) -> str:
        return (
            f"<ScheduledReport(id={self.id!r}, name={self.name!r}, "
            f"frequency={self.frequency!r}, enabled={self.enabled})>"
        )
