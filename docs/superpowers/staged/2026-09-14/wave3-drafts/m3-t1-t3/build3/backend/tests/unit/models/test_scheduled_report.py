"""Unit tests for ScheduledReport model.

Tests cover:
- ReportFrequency enum values and behavior
- ReportFormat enum values and behavior
- ScheduledReport model initialization and fields
- ScheduledReport model __repr__ method
- ScheduledReport table configuration (name, indexes, constraints)
- ScheduledReport is_due property
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import inspect

from backend.models.scheduled_report import (
    ReportFormat,
    ReportFrequency,
    ScheduledReport,
)

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# ReportFrequency Enum Tests
# =============================================================================


class TestReportFrequency:
    """Tests for ReportFrequency enum."""

    def test_daily_value(self) -> None:
        """Test DAILY enum has correct string value."""
        assert ReportFrequency.DAILY.value == "daily"

    def test_weekly_value(self) -> None:
        """Test WEEKLY enum has correct string value."""
        assert ReportFrequency.WEEKLY.value == "weekly"

    def test_monthly_value(self) -> None:
        """Test MONTHLY enum has correct string value."""
        assert ReportFrequency.MONTHLY.value == "monthly"

    def test_is_string_enum(self) -> None:
        """Test ReportFrequency inherits from str for JSON serialization."""
        assert isinstance(ReportFrequency.DAILY, str)
        assert isinstance(ReportFrequency.WEEKLY, str)
        assert isinstance(ReportFrequency.MONTHLY, str)

    def test_enum_comparison_with_string(self) -> None:
        """Test enum values can be compared directly with strings."""
        assert ReportFrequency.DAILY == "daily"
        assert ReportFrequency.WEEKLY == "weekly"
        assert ReportFrequency.MONTHLY == "monthly"

    def test_enum_count(self) -> None:
        """Test ReportFrequency has exactly three values."""
        assert len(ReportFrequency) == 3


# =============================================================================
# ReportFormat Enum Tests
# =============================================================================


class TestReportFormat:
    """Tests for ReportFormat enum."""

    def test_pdf_value(self) -> None:
        """Test PDF enum has correct string value."""
        assert ReportFormat.PDF.value == "pdf"

    def test_csv_value(self) -> None:
        """Test CSV enum has correct string value."""
        assert ReportFormat.CSV.value == "csv"

    def test_json_value(self) -> None:
        """Test JSON enum has correct string value."""
        assert ReportFormat.JSON.value == "json"

    def test_is_string_enum(self) -> None:
        """Test ReportFormat inherits from str for JSON serialization."""
        assert isinstance(ReportFormat.PDF, str)
        assert isinstance(ReportFormat.CSV, str)
        assert isinstance(ReportFormat.JSON, str)

    def test_enum_comparison_with_string(self) -> None:
        """Test enum values can be compared directly with strings."""
        assert ReportFormat.PDF == "pdf"
        assert ReportFormat.CSV == "csv"
        assert ReportFormat.JSON == "json"

    def test_enum_count(self) -> None:
        """Test ReportFormat has exactly three values."""
        assert len(ReportFormat) == 3


# =============================================================================
# ScheduledReport Model Initialization Tests
# =============================================================================


class TestScheduledReportModelInitialization:
    """Tests for ScheduledReport model initialization and fields."""

    def test_create_scheduled_report_minimal(self) -> None:
        """Test creating a scheduled report with required fields."""
        report = ScheduledReport(
            name="Daily Security Summary",
            frequency=ReportFrequency.DAILY.value,
        )

        assert report.name == "Daily Security Summary"
        assert report.frequency == "daily"
        # Check defaults
        assert report.day_of_week is None
        assert report.day_of_month is None
        assert report.last_run_at is None
        assert report.next_run_at is None

    def test_create_daily_report(self) -> None:
        """Test creating a daily report."""
        report = ScheduledReport(
            name="Daily Summary",
            frequency=ReportFrequency.DAILY.value,
            hour=9,
            minute=0,
            timezone="UTC",
            format=ReportFormat.PDF.value,
            enabled=True,
            email_recipients=["admin@example.com"],
            include_charts=True,
            include_event_details=True,
        )

        assert report.frequency == "daily"
        assert report.hour == 9
        assert report.minute == 0
        assert report.timezone == "UTC"
        assert report.format == "pdf"
        assert report.email_recipients == ["admin@example.com"]
        assert report.include_charts is True
        assert report.include_event_details is True

    def test_create_weekly_report(self) -> None:
        """Test creating a weekly report with day of week."""
        report = ScheduledReport(
            name="Weekly Security Report",
            frequency=ReportFrequency.WEEKLY.value,
            day_of_week=0,  # Monday
            hour=8,
            minute=30,
        )

        assert report.frequency == "weekly"
        assert report.day_of_week == 0
        assert report.day_of_month is None

    def test_create_monthly_report(self) -> None:
        """Test creating a monthly report with day of month."""
        report = ScheduledReport(
            name="Monthly Security Report",
            frequency=ReportFrequency.MONTHLY.value,
            day_of_month=1,  # First of month
            hour=6,
            minute=0,
        )

        assert report.frequency == "monthly"
        assert report.day_of_month == 1
        assert report.day_of_week is None

    def test_create_report_with_csv_format(self) -> None:
        """Test creating a report with CSV format."""
        report = ScheduledReport(
            name="CSV Export",
            frequency=ReportFrequency.DAILY.value,
            format=ReportFormat.CSV.value,
        )

        assert report.format == "csv"

    def test_create_report_with_json_format(self) -> None:
        """Test creating a report with JSON format."""
        report = ScheduledReport(
            name="JSON Export",
            frequency=ReportFrequency.DAILY.value,
            format=ReportFormat.JSON.value,
        )

        assert report.format == "json"

    def test_create_report_with_all_fields(self) -> None:
        """Test creating a report with all fields populated."""
        now = datetime.now(UTC)
        next_run = now + timedelta(days=1)

        report = ScheduledReport(
            id=1,
            name="Full Report",
            frequency=ReportFrequency.WEEKLY.value,
            enabled=True,
            day_of_week=4,  # Friday
            day_of_month=None,
            hour=10,
            minute=30,
            timezone="America/New_York",
            format=ReportFormat.PDF.value,
            email_recipients=["user1@example.com", "user2@example.com"],
            include_charts=True,
            include_event_details=False,
            last_run_at=now,
            next_run_at=next_run,
            created_at=now,
            updated_at=now,
        )

        assert report.id == 1
        assert report.name == "Full Report"
        assert report.frequency == "weekly"
        assert report.enabled is True
        assert report.day_of_week == 4
        assert report.day_of_month is None
        assert report.hour == 10
        assert report.minute == 30
        assert report.timezone == "America/New_York"
        assert report.format == "pdf"
        assert report.email_recipients == ["user1@example.com", "user2@example.com"]
        assert report.include_charts is True
        assert report.include_event_details is False
        assert report.last_run_at == now
        assert report.next_run_at == next_run
        assert report.created_at == now
        assert report.updated_at == now

    def test_create_disabled_report(self) -> None:
        """Test creating a disabled report."""
        report = ScheduledReport(
            name="Disabled Report",
            frequency=ReportFrequency.DAILY.value,
            enabled=False,
        )

        assert report.enabled is False

    def test_create_report_with_multiple_recipients(self) -> None:
        """Test creating a report with multiple email recipients."""
        recipients = [
            "admin@example.com",
            "security@example.com",
            "manager@example.com",
        ]
        report = ScheduledReport(
            name="Multi-recipient Report",
            frequency=ReportFrequency.DAILY.value,
            email_recipients=recipients,
        )

        assert report.email_recipients == recipients
        assert len(report.email_recipients) == 3


# =============================================================================
# ScheduledReport is_due Property Tests
# =============================================================================


class TestScheduledReportIsDue:
    """Tests for ScheduledReport is_due property."""

    def test_is_due_when_next_run_in_past(self) -> None:
        """Test is_due returns True when next_run_at is in the past."""
        past = datetime.now(UTC) - timedelta(minutes=5)
        report = ScheduledReport(
            name="Test Report",
            frequency=ReportFrequency.DAILY.value,
            enabled=True,
            next_run_at=past,
        )

        assert report.is_due is True

    def test_is_due_when_next_run_in_future(self) -> None:
        """Test is_due returns False when next_run_at is in the future."""
        future = datetime.now(UTC) + timedelta(hours=1)
        report = ScheduledReport(
            name="Test Report",
            frequency=ReportFrequency.DAILY.value,
            enabled=True,
            next_run_at=future,
        )

        assert report.is_due is False

    def test_is_due_when_disabled(self) -> None:
        """Test is_due returns False when report is disabled."""
        past = datetime.now(UTC) - timedelta(minutes=5)
        report = ScheduledReport(
            name="Test Report",
            frequency=ReportFrequency.DAILY.value,
            enabled=False,
            next_run_at=past,
        )

        assert report.is_due is False

    def test_is_due_when_next_run_is_none(self) -> None:
        """Test is_due returns False when next_run_at is None."""
        report = ScheduledReport(
            name="Test Report",
            frequency=ReportFrequency.DAILY.value,
            enabled=True,
            next_run_at=None,
        )

        assert report.is_due is False

    def test_is_due_at_exact_time(self) -> None:
        """Test is_due returns True when current time equals next_run_at."""
        now = datetime.now(UTC)
        with patch("backend.models.scheduled_report.utc_now", return_value=now):
            report = ScheduledReport(
                name="Test Report",
                frequency=ReportFrequency.DAILY.value,
                enabled=True,
                next_run_at=now,
            )

            assert report.is_due is True


# =============================================================================
# ScheduledReport Repr Tests
# =============================================================================


class TestScheduledReportRepr:
    """Tests for ScheduledReport __repr__ method."""

    def test_repr_contains_class_name(self) -> None:
        """Test repr contains 'ScheduledReport'."""
        report = ScheduledReport(
            id=1,
            name="Test Report",
            frequency=ReportFrequency.DAILY.value,
        )
        repr_str = repr(report)
        assert "ScheduledReport" in repr_str

    def test_repr_contains_id(self) -> None:
        """Test repr contains the id value."""
        report = ScheduledReport(
            id=42,
            name="Test Report",
            frequency=ReportFrequency.DAILY.value,
        )
        repr_str = repr(report)
        assert "42" in repr_str

    def test_repr_contains_name(self) -> None:
        """Test repr contains the name."""
        report = ScheduledReport(
            id=1,
            name="My Daily Report",
            frequency=ReportFrequency.DAILY.value,
        )
        repr_str = repr(report)
        assert "My Daily Report" in repr_str

    def test_repr_contains_frequency(self) -> None:
        """Test repr contains the frequency."""
        report = ScheduledReport(
            id=1,
            name="Test Report",
            frequency=ReportFrequency.WEEKLY.value,
        )
        repr_str = repr(report)
        assert "weekly" in repr_str

    def test_repr_contains_enabled_status(self) -> None:
        """Test repr contains the enabled status."""
        report = ScheduledReport(
            id=1,
            name="Test Report",
            frequency=ReportFrequency.DAILY.value,
            enabled=False,
        )
        repr_str = repr(report)
        assert "enabled=False" in repr_str

    def test_repr_format(self) -> None:
        """Test repr has expected format."""
        report = ScheduledReport(
            id=1,
            name="Test Report",
            frequency=ReportFrequency.DAILY.value,
            enabled=True,
        )
        repr_str = repr(report)
        assert repr_str.startswith("<ScheduledReport(")
        assert repr_str.endswith(")>")


# =============================================================================
# ScheduledReport Table Configuration Tests
# =============================================================================


class TestScheduledReportTableConfiguration:
    """Tests for ScheduledReport table name, indexes, and constraints."""

    def test_tablename(self) -> None:
        """Test ScheduledReport has correct table name."""
        assert ScheduledReport.__tablename__ == "scheduled_reports"

    def test_has_table_args(self) -> None:
        """Test ScheduledReport model has __table_args__."""
        assert hasattr(ScheduledReport, "__table_args__")

    def test_indexes_defined(self) -> None:
        """Test ScheduledReport has expected indexes."""
        mapper = inspect(ScheduledReport)
        table = mapper.local_table
        index_names = [idx.name for idx in table.indexes]

        assert "idx_scheduled_reports_enabled" in index_names
        assert "idx_scheduled_reports_frequency" in index_names
        assert "idx_scheduled_reports_next_run_at" in index_names
        assert "idx_scheduled_reports_enabled_next_run" in index_names

    def test_check_constraints_defined(self) -> None:
        """Test ScheduledReport has check constraints."""
        mapper = inspect(ScheduledReport)
        table = mapper.local_table
        constraint_names = [c.name for c in table.constraints if c.name]

        assert "ck_scheduled_reports_day_of_week_range" in constraint_names
        assert "ck_scheduled_reports_day_of_month_range" in constraint_names
        assert "ck_scheduled_reports_hour_range" in constraint_names
        assert "ck_scheduled_reports_minute_range" in constraint_names

    def test_primary_key_column(self) -> None:
        """Test id is the primary key."""
        mapper = inspect(ScheduledReport)
        pk_columns = [col.name for col in mapper.primary_key]
        assert pk_columns == ["id"]

    def test_column_types(self) -> None:
        """Test columns have correct nullable settings."""
        mapper = inspect(ScheduledReport)
        columns = {col.name: col for col in mapper.columns}

        # Check nullable settings
        assert columns["id"].primary_key is True
        assert columns["name"].nullable is False
        assert columns["frequency"].nullable is False
        assert columns["enabled"].nullable is False
        assert columns["day_of_week"].nullable is True
        assert columns["day_of_month"].nullable is True
        assert columns["hour"].nullable is False
        assert columns["minute"].nullable is False
        assert columns["timezone"].nullable is False
        assert columns["format"].nullable is False
        assert columns["email_recipients"].nullable is True
        assert columns["include_charts"].nullable is False
        assert columns["include_event_details"].nullable is False
        assert columns["last_run_at"].nullable is True
        assert columns["next_run_at"].nullable is True
        assert columns["created_at"].nullable is False
        assert columns["updated_at"].nullable is False

    def test_default_column_definitions(self) -> None:
        """Test that columns have correct default definitions."""
        mapper = inspect(ScheduledReport)

        enabled_col = mapper.columns["enabled"]
        assert enabled_col.default is not None
        assert enabled_col.default.arg is True

        hour_col = mapper.columns["hour"]
        assert hour_col.default is not None
        assert hour_col.default.arg == 8

        minute_col = mapper.columns["minute"]
        assert minute_col.default is not None
        assert minute_col.default.arg == 0

        include_charts_col = mapper.columns["include_charts"]
        assert include_charts_col.default is not None
        assert include_charts_col.default.arg is True

        include_event_details_col = mapper.columns["include_event_details"]
        assert include_event_details_col.default is not None
        assert include_event_details_col.default.arg is True


# =============================================================================
# ScheduledReport Schedule Configuration Tests
# =============================================================================


class TestScheduledReportScheduleConfiguration:
    """Tests for ScheduledReport schedule configuration."""

    def test_valid_day_of_week_monday(self) -> None:
        """Test day_of_week accepts Monday (0)."""
        report = ScheduledReport(
            name="Test Report",
            frequency=ReportFrequency.WEEKLY.value,
            day_of_week=0,
        )
        assert report.day_of_week == 0

    def test_valid_day_of_week_sunday(self) -> None:
        """Test day_of_week accepts Sunday (6)."""
        report = ScheduledReport(
            name="Test Report",
            frequency=ReportFrequency.WEEKLY.value,
            day_of_week=6,
        )
        assert report.day_of_week == 6

    def test_valid_day_of_month_first(self) -> None:
        """Test day_of_month accepts 1."""
        report = ScheduledReport(
            name="Test Report",
            frequency=ReportFrequency.MONTHLY.value,
            day_of_month=1,
        )
        assert report.day_of_month == 1

    def test_valid_day_of_month_last(self) -> None:
        """Test day_of_month accepts 31."""
        report = ScheduledReport(
            name="Test Report",
            frequency=ReportFrequency.MONTHLY.value,
            day_of_month=31,
        )
        assert report.day_of_month == 31

    def test_valid_hour_values(self) -> None:
        """Test various hour values work correctly."""
        for hour in [0, 6, 12, 18, 23]:
            report = ScheduledReport(
                name="Test Report",
                frequency=ReportFrequency.DAILY.value,
                hour=hour,
            )
            assert report.hour == hour

    def test_valid_minute_values(self) -> None:
        """Test various minute values work correctly."""
        for minute in [0, 15, 30, 45, 59]:
            report = ScheduledReport(
                name="Test Report",
                frequency=ReportFrequency.DAILY.value,
                minute=minute,
            )
            assert report.minute == minute

    def test_timezone_values(self) -> None:
        """Test various timezone values work correctly."""
        timezones = ["UTC", "America/New_York", "Europe/London", "Asia/Tokyo"]

        for tz in timezones:
            report = ScheduledReport(
                name="Test Report",
                frequency=ReportFrequency.DAILY.value,
                timezone=tz,
            )
            assert report.timezone == tz


# =============================================================================
# Import Tests
# =============================================================================


class TestScheduledReportImports:
    """Tests for ScheduledReport model imports from models package."""

    def test_import_from_models_package(self) -> None:
        """Test ScheduledReport can be imported from backend.models."""
        from backend.models import ReportFormat as ImportedReportFormat
        from backend.models import ReportFrequency as ImportedReportFrequency
        from backend.models import ScheduledReport as ImportedScheduledReport

        assert ImportedScheduledReport is ScheduledReport
        assert ImportedReportFrequency is ReportFrequency
        assert ImportedReportFormat is ReportFormat

    def test_in_models_all(self) -> None:
        """Test ScheduledReport and enums are in __all__."""
        from backend import models

        assert "ScheduledReport" in models.__all__
        assert "ReportFrequency" in models.__all__
        assert "ReportFormat" in models.__all__
