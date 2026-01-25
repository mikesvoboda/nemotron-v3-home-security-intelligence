"""Pydantic schemas for scheduled report API endpoints.

NEM-3621: Create Scheduled Reports API Schemas and Routes

Provides schemas for:
- Creating scheduled reports (daily, weekly, monthly)
- Updating scheduled report configurations
- Response schemas with report metadata
- List response with pagination
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

__all__ = [
    "ReportFormat",
    "ReportFrequency",
    "ScheduledReportCreate",
    "ScheduledReportListResponse",
    "ScheduledReportResponse",
    "ScheduledReportRunResponse",
    "ScheduledReportUpdate",
]


class ReportFrequency(str, Enum):
    """Frequency options for scheduled reports.

    Values:
        DAILY: Report runs every day at specified time
        WEEKLY: Report runs on specified day of week
        MONTHLY: Report runs on specified day of month
    """

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

    def __str__(self) -> str:
        """Return string representation of frequency."""
        return self.value


class ReportFormat(str, Enum):
    """Output format options for scheduled reports.

    Values:
        PDF: Portable Document Format with charts and summaries
        CSV: Comma-separated values for data analysis
        JSON: Machine-readable JSON format
    """

    PDF = "pdf"
    CSV = "csv"
    JSON = "json"

    def __str__(self) -> str:
        """Return string representation of format."""
        return self.value


class ScheduledReportCreate(BaseModel):
    """Schema for creating a new scheduled report.

    Used when setting up a new automated report schedule.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Weekly Security Summary",
                "frequency": "weekly",
                "day_of_week": 1,
                "hour": 8,
                "minute": 0,
                "timezone": "America/New_York",
                "format": "pdf",
                "enabled": True,
                "email_recipients": ["admin@example.com"],
                "include_charts": True,
                "include_event_details": True,
            }
        }
    )

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name/title of the scheduled report",
    )
    frequency: ReportFrequency = Field(
        ...,
        description="How often the report should run (daily, weekly, monthly)",
    )
    day_of_week: int | None = Field(
        None,
        ge=0,
        le=6,
        description="Day of week (0=Monday, 6=Sunday) for weekly reports",
    )
    day_of_month: int | None = Field(
        None,
        ge=1,
        le=31,
        description="Day of month (1-31) for monthly reports",
    )
    hour: int = Field(
        8,
        ge=0,
        le=23,
        description="Hour of day to run report (0-23, default 8)",
    )
    minute: int = Field(
        0,
        ge=0,
        le=59,
        description="Minute of hour to run report (0-59, default 0)",
    )
    timezone: str = Field(
        "UTC",
        max_length=50,
        description="Timezone for schedule (e.g., 'America/New_York', 'UTC')",
    )
    format: ReportFormat = Field(
        ReportFormat.PDF,
        description="Output format for the report (pdf, csv, json)",
    )
    enabled: bool = Field(
        True,
        description="Whether the scheduled report is active",
    )
    email_recipients: list[str] | None = Field(
        None,
        max_length=10,
        description="Email addresses to send report to (max 10)",
    )
    include_charts: bool = Field(
        True,
        description="Include visual charts in the report",
    )
    include_event_details: bool = Field(
        True,
        description="Include detailed event breakdowns",
    )

    @field_validator("email_recipients")
    @classmethod
    def validate_email_recipients(cls, v: list[str] | None) -> list[str] | None:
        """Validate email recipients are properly formatted."""
        if v is None:
            return v
        if len(v) > 10:
            raise ValueError("Maximum of 10 email recipients allowed")
        for email in v:
            if "@" not in email or len(email) > 254:
                raise ValueError(f"Invalid email format: {email}")
        return v

    @model_validator(mode="after")
    def validate_schedule_fields(self) -> ScheduledReportCreate:
        """Validate that schedule fields match the frequency.

        - Weekly reports require day_of_week
        - Monthly reports require day_of_month
        - Daily reports should not have day_of_week or day_of_month
        """
        if self.frequency == ReportFrequency.WEEKLY:
            if self.day_of_week is None:
                raise ValueError("day_of_week is required for weekly reports")
        elif self.frequency == ReportFrequency.MONTHLY:
            if self.day_of_month is None:
                raise ValueError("day_of_month is required for monthly reports")

        return self


class ScheduledReportUpdate(BaseModel):
    """Schema for updating an existing scheduled report.

    All fields are optional for partial updates.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Updated Weekly Report",
                "enabled": False,
            }
        }
    )

    name: str | None = Field(
        None,
        min_length=1,
        max_length=255,
        description="Name/title of the scheduled report",
    )
    frequency: ReportFrequency | None = Field(
        None,
        description="How often the report should run (daily, weekly, monthly)",
    )
    day_of_week: int | None = Field(
        None,
        ge=0,
        le=6,
        description="Day of week (0=Monday, 6=Sunday) for weekly reports",
    )
    day_of_month: int | None = Field(
        None,
        ge=1,
        le=31,
        description="Day of month (1-31) for monthly reports",
    )
    hour: int | None = Field(
        None,
        ge=0,
        le=23,
        description="Hour of day to run report (0-23)",
    )
    minute: int | None = Field(
        None,
        ge=0,
        le=59,
        description="Minute of hour to run report (0-59)",
    )
    timezone: str | None = Field(
        None,
        max_length=50,
        description="Timezone for schedule (e.g., 'America/New_York', 'UTC')",
    )
    format: ReportFormat | None = Field(
        None,
        description="Output format for the report (pdf, csv, json)",
    )
    enabled: bool | None = Field(
        None,
        description="Whether the scheduled report is active",
    )
    email_recipients: list[str] | None = Field(
        None,
        max_length=10,
        description="Email addresses to send report to (max 10)",
    )
    include_charts: bool | None = Field(
        None,
        description="Include visual charts in the report",
    )
    include_event_details: bool | None = Field(
        None,
        description="Include detailed event breakdowns",
    )

    @field_validator("email_recipients")
    @classmethod
    def validate_email_recipients(cls, v: list[str] | None) -> list[str] | None:
        """Validate email recipients are properly formatted."""
        if v is None:
            return v
        if len(v) > 10:
            raise ValueError("Maximum of 10 email recipients allowed")
        for email in v:
            if "@" not in email or len(email) > 254:
                raise ValueError(f"Invalid email format: {email}")
        return v


class ScheduledReportResponse(BaseModel):
    """Schema for scheduled report response.

    Returned when retrieving or creating a scheduled report.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "name": "Weekly Security Summary",
                "frequency": "weekly",
                "day_of_week": 1,
                "day_of_month": None,
                "hour": 8,
                "minute": 0,
                "timezone": "America/New_York",
                "format": "pdf",
                "enabled": True,
                "email_recipients": ["admin@example.com"],
                "include_charts": True,
                "include_event_details": True,
                "last_run_at": "2025-01-20T08:00:00Z",
                "next_run_at": "2025-01-27T08:00:00Z",
                "created_at": "2025-01-01T12:00:00Z",
                "updated_at": "2025-01-15T09:30:00Z",
            }
        },
    )

    id: int = Field(..., description="Scheduled report ID")
    name: str = Field(..., description="Name/title of the scheduled report")
    frequency: ReportFrequency | str = Field(..., description="How often the report runs")
    day_of_week: int | None = Field(
        None, description="Day of week (0=Monday, 6=Sunday) for weekly reports"
    )
    day_of_month: int | None = Field(None, description="Day of month (1-31) for monthly reports")
    hour: int = Field(..., description="Hour of day to run report (0-23)")
    minute: int = Field(..., description="Minute of hour to run report (0-59)")
    timezone: str = Field(..., description="Timezone for schedule")
    format: ReportFormat | str = Field(..., description="Output format for the report")
    enabled: bool = Field(..., description="Whether the scheduled report is active")
    email_recipients: list[str] | None = Field(
        None, description="Email addresses to send report to"
    )
    include_charts: bool = Field(..., description="Include visual charts in the report")
    include_event_details: bool = Field(..., description="Include detailed event breakdowns")
    last_run_at: datetime | None = Field(None, description="When the report last ran successfully")
    next_run_at: datetime | None = Field(
        None, description="When the report is scheduled to run next"
    )
    created_at: datetime = Field(..., description="When the report was created")
    updated_at: datetime = Field(..., description="When the report was last updated")


class ScheduledReportListResponse(BaseModel):
    """Schema for scheduled report list response.

    Returns a list of scheduled reports with total count.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": 1,
                        "name": "Weekly Security Summary",
                        "frequency": "weekly",
                        "day_of_week": 1,
                        "day_of_month": None,
                        "hour": 8,
                        "minute": 0,
                        "timezone": "America/New_York",
                        "format": "pdf",
                        "enabled": True,
                        "email_recipients": ["admin@example.com"],
                        "include_charts": True,
                        "include_event_details": True,
                        "last_run_at": "2025-01-20T08:00:00Z",
                        "next_run_at": "2025-01-27T08:00:00Z",
                        "created_at": "2025-01-01T12:00:00Z",
                        "updated_at": "2025-01-15T09:30:00Z",
                    }
                ],
                "total": 1,
            }
        }
    )

    items: list[ScheduledReportResponse] = Field(..., description="List of scheduled reports")
    total: int = Field(..., ge=0, description="Total number of scheduled reports")


class ScheduledReportRunResponse(BaseModel):
    """Schema for manual report run response.

    Returned when a report is manually triggered.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "report_id": 1,
                "status": "running",
                "message": "Report generation started",
                "started_at": "2025-01-25T10:30:00Z",
            }
        }
    )

    report_id: int = Field(..., description="ID of the report being run")
    status: str = Field(..., description="Status of the run (running, queued, failed)")
    message: str = Field(..., description="Status message")
    started_at: datetime = Field(..., description="When the run was initiated")
