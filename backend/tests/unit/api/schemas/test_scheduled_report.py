"""Unit tests for scheduled report API schemas.

NEM-3621: Create Scheduled Reports API Schemas and Routes

Tests cover:
- ReportFrequency enum validation
- ReportFormat enum validation
- ScheduledReportCreate validation (required fields, schedule fields)
- ScheduledReportUpdate partial update validation
- ScheduledReportResponse serialization
- ScheduledReportListResponse structure
- ScheduledReportRunResponse structure
"""

import pytest
from pydantic import ValidationError

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# ReportFrequency Enum Tests
# =============================================================================


class TestReportFrequency:
    """Tests for ReportFrequency enum."""

    def test_frequency_daily(self) -> None:
        """Test ReportFrequency.DAILY value."""
        from backend.api.schemas.scheduled_report import ReportFrequency

        assert ReportFrequency.DAILY == "daily"
        assert ReportFrequency.DAILY.value == "daily"

    def test_frequency_weekly(self) -> None:
        """Test ReportFrequency.WEEKLY value."""
        from backend.api.schemas.scheduled_report import ReportFrequency

        assert ReportFrequency.WEEKLY == "weekly"
        assert ReportFrequency.WEEKLY.value == "weekly"

    def test_frequency_monthly(self) -> None:
        """Test ReportFrequency.MONTHLY value."""
        from backend.api.schemas.scheduled_report import ReportFrequency

        assert ReportFrequency.MONTHLY == "monthly"
        assert ReportFrequency.MONTHLY.value == "monthly"

    def test_frequency_is_string_enum(self) -> None:
        """Test ReportFrequency inherits from str."""
        from backend.api.schemas.scheduled_report import ReportFrequency

        freq = ReportFrequency.DAILY
        assert isinstance(freq, str)
        assert freq == "daily"

    def test_frequency_str_representation(self) -> None:
        """Test ReportFrequency __str__ method."""
        from backend.api.schemas.scheduled_report import ReportFrequency

        assert str(ReportFrequency.DAILY) == "daily"
        assert str(ReportFrequency.WEEKLY) == "weekly"
        assert str(ReportFrequency.MONTHLY) == "monthly"


# =============================================================================
# ReportFormat Enum Tests
# =============================================================================


class TestReportFormat:
    """Tests for ReportFormat enum."""

    def test_format_pdf(self) -> None:
        """Test ReportFormat.PDF value."""
        from backend.api.schemas.scheduled_report import ReportFormat

        assert ReportFormat.PDF == "pdf"
        assert ReportFormat.PDF.value == "pdf"

    def test_format_csv(self) -> None:
        """Test ReportFormat.CSV value."""
        from backend.api.schemas.scheduled_report import ReportFormat

        assert ReportFormat.CSV == "csv"
        assert ReportFormat.CSV.value == "csv"

    def test_format_json(self) -> None:
        """Test ReportFormat.JSON value."""
        from backend.api.schemas.scheduled_report import ReportFormat

        assert ReportFormat.JSON == "json"
        assert ReportFormat.JSON.value == "json"

    def test_format_is_string_enum(self) -> None:
        """Test ReportFormat inherits from str."""
        from backend.api.schemas.scheduled_report import ReportFormat

        fmt = ReportFormat.PDF
        assert isinstance(fmt, str)
        assert fmt == "pdf"


# =============================================================================
# ScheduledReportCreate Tests
# =============================================================================


class TestScheduledReportCreate:
    """Tests for ScheduledReportCreate schema."""

    def test_create_daily_report(self) -> None:
        """Test creating a daily scheduled report."""
        from backend.api.schemas.scheduled_report import (
            ReportFormat,
            ReportFrequency,
            ScheduledReportCreate,
        )

        report = ScheduledReportCreate(
            name="Daily Summary",
            frequency=ReportFrequency.DAILY,
            hour=8,
            minute=0,
        )

        assert report.name == "Daily Summary"
        assert report.frequency == ReportFrequency.DAILY
        assert report.hour == 8
        assert report.minute == 0
        assert report.day_of_week is None
        assert report.day_of_month is None
        assert report.format == ReportFormat.PDF  # default
        assert report.enabled is True  # default
        assert report.timezone == "UTC"  # default

    def test_create_weekly_report_with_day_of_week(self) -> None:
        """Test creating a weekly report requires day_of_week."""
        from backend.api.schemas.scheduled_report import (
            ReportFrequency,
            ScheduledReportCreate,
        )

        report = ScheduledReportCreate(
            name="Weekly Report",
            frequency=ReportFrequency.WEEKLY,
            day_of_week=1,  # Tuesday
            hour=9,
        )

        assert report.frequency == ReportFrequency.WEEKLY
        assert report.day_of_week == 1

    def test_create_weekly_report_missing_day_of_week_fails(self) -> None:
        """Test weekly report without day_of_week raises error."""
        from backend.api.schemas.scheduled_report import (
            ReportFrequency,
            ScheduledReportCreate,
        )

        with pytest.raises(ValidationError) as exc_info:
            ScheduledReportCreate(
                name="Weekly Report",
                frequency=ReportFrequency.WEEKLY,
                hour=9,
            )

        errors = exc_info.value.errors()
        assert any("day_of_week" in str(e) for e in errors)

    def test_create_monthly_report_with_day_of_month(self) -> None:
        """Test creating a monthly report requires day_of_month."""
        from backend.api.schemas.scheduled_report import (
            ReportFrequency,
            ScheduledReportCreate,
        )

        report = ScheduledReportCreate(
            name="Monthly Report",
            frequency=ReportFrequency.MONTHLY,
            day_of_month=15,
            hour=10,
        )

        assert report.frequency == ReportFrequency.MONTHLY
        assert report.day_of_month == 15

    def test_create_monthly_report_missing_day_of_month_fails(self) -> None:
        """Test monthly report without day_of_month raises error."""
        from backend.api.schemas.scheduled_report import (
            ReportFrequency,
            ScheduledReportCreate,
        )

        with pytest.raises(ValidationError) as exc_info:
            ScheduledReportCreate(
                name="Monthly Report",
                frequency=ReportFrequency.MONTHLY,
                hour=10,
            )

        errors = exc_info.value.errors()
        assert any("day_of_month" in str(e) for e in errors)

    def test_day_of_week_validation_min(self) -> None:
        """Test day_of_week minimum is 0 (Monday)."""
        from backend.api.schemas.scheduled_report import (
            ReportFrequency,
            ScheduledReportCreate,
        )

        report = ScheduledReportCreate(
            name="Monday Report",
            frequency=ReportFrequency.WEEKLY,
            day_of_week=0,
        )

        assert report.day_of_week == 0

    def test_day_of_week_validation_max(self) -> None:
        """Test day_of_week maximum is 6 (Sunday)."""
        from backend.api.schemas.scheduled_report import (
            ReportFrequency,
            ScheduledReportCreate,
        )

        report = ScheduledReportCreate(
            name="Sunday Report",
            frequency=ReportFrequency.WEEKLY,
            day_of_week=6,
        )

        assert report.day_of_week == 6

    def test_day_of_week_validation_invalid_negative(self) -> None:
        """Test day_of_week rejects negative values."""
        from backend.api.schemas.scheduled_report import (
            ReportFrequency,
            ScheduledReportCreate,
        )

        with pytest.raises(ValidationError) as exc_info:
            ScheduledReportCreate(
                name="Invalid Report",
                frequency=ReportFrequency.WEEKLY,
                day_of_week=-1,
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("day_of_week",) for e in errors)

    def test_day_of_week_validation_invalid_over_6(self) -> None:
        """Test day_of_week rejects values over 6."""
        from backend.api.schemas.scheduled_report import (
            ReportFrequency,
            ScheduledReportCreate,
        )

        with pytest.raises(ValidationError) as exc_info:
            ScheduledReportCreate(
                name="Invalid Report",
                frequency=ReportFrequency.WEEKLY,
                day_of_week=7,
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("day_of_week",) for e in errors)

    def test_day_of_month_validation_min(self) -> None:
        """Test day_of_month minimum is 1."""
        from backend.api.schemas.scheduled_report import (
            ReportFrequency,
            ScheduledReportCreate,
        )

        report = ScheduledReportCreate(
            name="First Day Report",
            frequency=ReportFrequency.MONTHLY,
            day_of_month=1,
        )

        assert report.day_of_month == 1

    def test_day_of_month_validation_max(self) -> None:
        """Test day_of_month maximum is 31."""
        from backend.api.schemas.scheduled_report import (
            ReportFrequency,
            ScheduledReportCreate,
        )

        report = ScheduledReportCreate(
            name="End of Month Report",
            frequency=ReportFrequency.MONTHLY,
            day_of_month=31,
        )

        assert report.day_of_month == 31

    def test_day_of_month_validation_invalid_zero(self) -> None:
        """Test day_of_month rejects 0."""
        from backend.api.schemas.scheduled_report import (
            ReportFrequency,
            ScheduledReportCreate,
        )

        with pytest.raises(ValidationError) as exc_info:
            ScheduledReportCreate(
                name="Invalid Report",
                frequency=ReportFrequency.MONTHLY,
                day_of_month=0,
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("day_of_month",) for e in errors)

    def test_day_of_month_validation_invalid_over_31(self) -> None:
        """Test day_of_month rejects values over 31."""
        from backend.api.schemas.scheduled_report import (
            ReportFrequency,
            ScheduledReportCreate,
        )

        with pytest.raises(ValidationError) as exc_info:
            ScheduledReportCreate(
                name="Invalid Report",
                frequency=ReportFrequency.MONTHLY,
                day_of_month=32,
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("day_of_month",) for e in errors)

    def test_hour_validation_min(self) -> None:
        """Test hour minimum is 0."""
        from backend.api.schemas.scheduled_report import (
            ReportFrequency,
            ScheduledReportCreate,
        )

        report = ScheduledReportCreate(
            name="Midnight Report",
            frequency=ReportFrequency.DAILY,
            hour=0,
        )

        assert report.hour == 0

    def test_hour_validation_max(self) -> None:
        """Test hour maximum is 23."""
        from backend.api.schemas.scheduled_report import (
            ReportFrequency,
            ScheduledReportCreate,
        )

        report = ScheduledReportCreate(
            name="Late Night Report",
            frequency=ReportFrequency.DAILY,
            hour=23,
        )

        assert report.hour == 23

    def test_hour_validation_invalid(self) -> None:
        """Test hour rejects values outside 0-23."""
        from backend.api.schemas.scheduled_report import (
            ReportFrequency,
            ScheduledReportCreate,
        )

        with pytest.raises(ValidationError) as exc_info:
            ScheduledReportCreate(
                name="Invalid Report",
                frequency=ReportFrequency.DAILY,
                hour=24,
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("hour",) for e in errors)

    def test_minute_validation_min(self) -> None:
        """Test minute minimum is 0."""
        from backend.api.schemas.scheduled_report import (
            ReportFrequency,
            ScheduledReportCreate,
        )

        report = ScheduledReportCreate(
            name="On the Hour Report",
            frequency=ReportFrequency.DAILY,
            minute=0,
        )

        assert report.minute == 0

    def test_minute_validation_max(self) -> None:
        """Test minute maximum is 59."""
        from backend.api.schemas.scheduled_report import (
            ReportFrequency,
            ScheduledReportCreate,
        )

        report = ScheduledReportCreate(
            name="End of Hour Report",
            frequency=ReportFrequency.DAILY,
            minute=59,
        )

        assert report.minute == 59

    def test_minute_validation_invalid(self) -> None:
        """Test minute rejects values outside 0-59."""
        from backend.api.schemas.scheduled_report import (
            ReportFrequency,
            ScheduledReportCreate,
        )

        with pytest.raises(ValidationError) as exc_info:
            ScheduledReportCreate(
                name="Invalid Report",
                frequency=ReportFrequency.DAILY,
                minute=60,
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("minute",) for e in errors)

    def test_create_with_email_recipients(self) -> None:
        """Test creating report with email recipients."""
        from backend.api.schemas.scheduled_report import (
            ReportFrequency,
            ScheduledReportCreate,
        )

        report = ScheduledReportCreate(
            name="Email Report",
            frequency=ReportFrequency.DAILY,
            email_recipients=["admin@example.com", "user@example.com"],
        )

        assert report.email_recipients == ["admin@example.com", "user@example.com"]

    def test_email_recipients_max_count(self) -> None:
        """Test email recipients limited to 10."""
        from backend.api.schemas.scheduled_report import (
            ReportFrequency,
            ScheduledReportCreate,
        )

        emails = [f"user{i}@example.com" for i in range(11)]

        with pytest.raises(ValidationError) as exc_info:
            ScheduledReportCreate(
                name="Too Many Emails",
                frequency=ReportFrequency.DAILY,
                email_recipients=emails,
            )

        errors = exc_info.value.errors()
        assert any("10" in str(e) for e in errors)

    def test_email_recipients_invalid_format(self) -> None:
        """Test invalid email format is rejected."""
        from backend.api.schemas.scheduled_report import (
            ReportFrequency,
            ScheduledReportCreate,
        )

        with pytest.raises(ValidationError) as exc_info:
            ScheduledReportCreate(
                name="Bad Email Report",
                frequency=ReportFrequency.DAILY,
                email_recipients=["not-an-email"],
            )

        errors = exc_info.value.errors()
        assert any("email" in str(e).lower() for e in errors)

    def test_create_missing_name_fails(self) -> None:
        """Test name is required."""
        from backend.api.schemas.scheduled_report import (
            ReportFrequency,
            ScheduledReportCreate,
        )

        with pytest.raises(ValidationError) as exc_info:
            ScheduledReportCreate(
                frequency=ReportFrequency.DAILY,
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("name",) for e in errors)

    def test_create_missing_frequency_fails(self) -> None:
        """Test frequency is required."""
        from backend.api.schemas.scheduled_report import ScheduledReportCreate

        with pytest.raises(ValidationError) as exc_info:
            ScheduledReportCreate(
                name="No Frequency Report",
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("frequency",) for e in errors)

    def test_name_max_length(self) -> None:
        """Test name respects max_length of 255."""
        from backend.api.schemas.scheduled_report import (
            ReportFrequency,
            ScheduledReportCreate,
        )

        # Valid at max length
        report = ScheduledReportCreate(
            name="A" * 255,
            frequency=ReportFrequency.DAILY,
        )
        assert len(report.name) == 255

        # Invalid over max length
        with pytest.raises(ValidationError) as exc_info:
            ScheduledReportCreate(
                name="A" * 256,
                frequency=ReportFrequency.DAILY,
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("name",) for e in errors)

    def test_create_with_string_frequency(self) -> None:
        """Test creating report with string frequency value."""
        from backend.api.schemas.scheduled_report import (
            ReportFrequency,
            ScheduledReportCreate,
        )

        report = ScheduledReportCreate(
            name="String Frequency Report",
            frequency="daily",
        )

        assert report.frequency == ReportFrequency.DAILY

    def test_create_with_all_optional_fields(self) -> None:
        """Test creating report with all optional fields."""
        from backend.api.schemas.scheduled_report import (
            ReportFormat,
            ReportFrequency,
            ScheduledReportCreate,
        )

        report = ScheduledReportCreate(
            name="Full Report",
            frequency=ReportFrequency.WEEKLY,
            day_of_week=4,  # Friday
            hour=17,
            minute=30,
            timezone="America/New_York",
            format=ReportFormat.CSV,
            enabled=False,
            email_recipients=["admin@example.com"],
            include_charts=False,
            include_event_details=False,
        )

        assert report.name == "Full Report"
        assert report.frequency == ReportFrequency.WEEKLY
        assert report.day_of_week == 4
        assert report.hour == 17
        assert report.minute == 30
        assert report.timezone == "America/New_York"
        assert report.format == ReportFormat.CSV
        assert report.enabled is False
        assert report.email_recipients == ["admin@example.com"]
        assert report.include_charts is False
        assert report.include_event_details is False


# =============================================================================
# ScheduledReportUpdate Tests
# =============================================================================


class TestScheduledReportUpdate:
    """Tests for ScheduledReportUpdate schema."""

    def test_update_all_fields_optional(self) -> None:
        """Test all fields are optional for update."""
        from backend.api.schemas.scheduled_report import ScheduledReportUpdate

        # Empty update is valid
        update = ScheduledReportUpdate()

        assert update.name is None
        assert update.frequency is None
        assert update.day_of_week is None
        assert update.day_of_month is None
        assert update.hour is None
        assert update.minute is None
        assert update.timezone is None
        assert update.format is None
        assert update.enabled is None

    def test_update_single_field(self) -> None:
        """Test updating a single field."""
        from backend.api.schemas.scheduled_report import ScheduledReportUpdate

        update = ScheduledReportUpdate(name="Updated Name")

        assert update.name == "Updated Name"
        assert update.frequency is None

    def test_update_enabled_only(self) -> None:
        """Test updating enabled status only."""
        from backend.api.schemas.scheduled_report import ScheduledReportUpdate

        update = ScheduledReportUpdate(enabled=False)

        assert update.enabled is False
        assert update.name is None

    def test_update_day_of_week_validation(self) -> None:
        """Test day_of_week validation in update."""
        from backend.api.schemas.scheduled_report import ScheduledReportUpdate

        # Valid values
        for day in range(7):
            update = ScheduledReportUpdate(day_of_week=day)
            assert update.day_of_week == day

        # Invalid value
        with pytest.raises(ValidationError):
            ScheduledReportUpdate(day_of_week=7)

    def test_update_day_of_month_validation(self) -> None:
        """Test day_of_month validation in update."""
        from backend.api.schemas.scheduled_report import ScheduledReportUpdate

        # Valid values
        for day in range(1, 32):
            update = ScheduledReportUpdate(day_of_month=day)
            assert update.day_of_month == day

        # Invalid values
        with pytest.raises(ValidationError):
            ScheduledReportUpdate(day_of_month=0)

        with pytest.raises(ValidationError):
            ScheduledReportUpdate(day_of_month=32)

    def test_update_email_recipients_validation(self) -> None:
        """Test email validation in update."""
        from backend.api.schemas.scheduled_report import ScheduledReportUpdate

        # Valid emails
        update = ScheduledReportUpdate(email_recipients=["test@example.com"])
        assert update.email_recipients == ["test@example.com"]

        # Invalid email
        with pytest.raises(ValidationError):
            ScheduledReportUpdate(email_recipients=["invalid"])


# =============================================================================
# ScheduledReportResponse Tests
# =============================================================================


class TestScheduledReportResponse:
    """Tests for ScheduledReportResponse schema."""

    def test_response_contains_all_fields(self) -> None:
        """Test response schema has all expected fields."""
        from datetime import UTC, datetime

        from backend.api.schemas.scheduled_report import (
            ReportFormat,
            ReportFrequency,
            ScheduledReportResponse,
        )

        now = datetime.now(UTC)
        response = ScheduledReportResponse(
            id=1,
            name="Test Report",
            frequency=ReportFrequency.DAILY,
            day_of_week=None,
            day_of_month=None,
            hour=8,
            minute=0,
            timezone="UTC",
            format=ReportFormat.PDF,
            enabled=True,
            email_recipients=None,
            include_charts=True,
            include_event_details=True,
            last_run_at=None,
            next_run_at=now,
            created_at=now,
            updated_at=now,
        )

        assert response.id == 1
        assert response.name == "Test Report"
        assert response.frequency == ReportFrequency.DAILY
        assert response.hour == 8
        assert response.enabled is True

    def test_response_with_weekly_schedule(self) -> None:
        """Test response with weekly schedule fields."""
        from datetime import UTC, datetime

        from backend.api.schemas.scheduled_report import (
            ReportFormat,
            ReportFrequency,
            ScheduledReportResponse,
        )

        now = datetime.now(UTC)
        response = ScheduledReportResponse(
            id=2,
            name="Weekly Report",
            frequency=ReportFrequency.WEEKLY,
            day_of_week=3,  # Thursday
            day_of_month=None,
            hour=9,
            minute=30,
            timezone="America/New_York",
            format=ReportFormat.CSV,
            enabled=True,
            email_recipients=["admin@example.com"],
            include_charts=False,
            include_event_details=True,
            last_run_at=now,
            next_run_at=now,
            created_at=now,
            updated_at=now,
        )

        assert response.day_of_week == 3
        assert response.day_of_month is None

    def test_response_from_orm_attributes(self) -> None:
        """Test response can be created from ORM model attributes."""
        from datetime import UTC, datetime
        from unittest.mock import MagicMock

        from backend.api.schemas.scheduled_report import ScheduledReportResponse

        # Simulate ORM model
        mock_model = MagicMock()
        mock_model.id = 10
        mock_model.name = "ORM Report"
        mock_model.frequency = "daily"
        mock_model.day_of_week = None
        mock_model.day_of_month = None
        mock_model.hour = 8
        mock_model.minute = 0
        mock_model.timezone = "UTC"
        mock_model.format = "pdf"
        mock_model.enabled = True
        mock_model.email_recipients = ["test@example.com"]
        mock_model.include_charts = True
        mock_model.include_event_details = True
        mock_model.last_run_at = None
        mock_model.next_run_at = datetime.now(UTC)
        mock_model.created_at = datetime.now(UTC)
        mock_model.updated_at = datetime.now(UTC)

        response = ScheduledReportResponse.model_validate(mock_model)

        assert response.id == 10
        assert response.name == "ORM Report"
        assert response.frequency == "daily"

    def test_response_serialization(self) -> None:
        """Test response serializes correctly to JSON-compatible dict."""
        from datetime import UTC, datetime

        from backend.api.schemas.scheduled_report import (
            ReportFormat,
            ReportFrequency,
            ScheduledReportResponse,
        )

        response = ScheduledReportResponse(
            id=5,
            name="JSON Test",
            frequency=ReportFrequency.MONTHLY,
            day_of_week=None,
            day_of_month=15,
            hour=10,
            minute=0,
            timezone="UTC",
            format=ReportFormat.JSON,
            enabled=True,
            email_recipients=None,
            include_charts=True,
            include_event_details=True,
            last_run_at=None,
            next_run_at=None,
            created_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
            updated_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
        )

        data = response.model_dump(mode="json")

        assert data["id"] == 5
        assert data["name"] == "JSON Test"
        assert data["frequency"] == "monthly"
        assert data["day_of_month"] == 15
        assert data["format"] == "json"
        assert "created_at" in data


# =============================================================================
# ScheduledReportListResponse Tests
# =============================================================================


class TestScheduledReportListResponse:
    """Tests for ScheduledReportListResponse schema."""

    def test_list_response_structure(self) -> None:
        """Test list response has items and total."""
        from datetime import UTC, datetime

        from backend.api.schemas.scheduled_report import (
            ReportFormat,
            ReportFrequency,
            ScheduledReportListResponse,
            ScheduledReportResponse,
        )

        now = datetime.now(UTC)
        reports = [
            ScheduledReportResponse(
                id=1,
                name="Report 1",
                frequency=ReportFrequency.DAILY,
                day_of_week=None,
                day_of_month=None,
                hour=8,
                minute=0,
                timezone="UTC",
                format=ReportFormat.PDF,
                enabled=True,
                email_recipients=None,
                include_charts=True,
                include_event_details=True,
                last_run_at=None,
                next_run_at=now,
                created_at=now,
                updated_at=now,
            ),
            ScheduledReportResponse(
                id=2,
                name="Report 2",
                frequency=ReportFrequency.WEEKLY,
                day_of_week=1,
                day_of_month=None,
                hour=9,
                minute=0,
                timezone="UTC",
                format=ReportFormat.CSV,
                enabled=False,
                email_recipients=["admin@example.com"],
                include_charts=False,
                include_event_details=True,
                last_run_at=now,
                next_run_at=now,
                created_at=now,
                updated_at=now,
            ),
        ]

        list_response = ScheduledReportListResponse(
            items=reports,
            total=2,
        )

        assert len(list_response.items) == 2
        assert list_response.total == 2
        assert list_response.items[0].name == "Report 1"
        assert list_response.items[1].name == "Report 2"

    def test_list_response_empty(self) -> None:
        """Test list response handles empty data."""
        from backend.api.schemas.scheduled_report import ScheduledReportListResponse

        list_response = ScheduledReportListResponse(
            items=[],
            total=0,
        )

        assert list_response.items == []
        assert list_response.total == 0

    def test_list_response_total_non_negative(self) -> None:
        """Test total must be >= 0."""
        from backend.api.schemas.scheduled_report import ScheduledReportListResponse

        with pytest.raises(ValidationError) as exc_info:
            ScheduledReportListResponse(
                items=[],
                total=-1,
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("total",) for e in errors)


# =============================================================================
# ScheduledReportRunResponse Tests
# =============================================================================


class TestScheduledReportRunResponse:
    """Tests for ScheduledReportRunResponse schema."""

    def test_run_response_structure(self) -> None:
        """Test run response has expected fields."""
        from datetime import UTC, datetime

        from backend.api.schemas.scheduled_report import ScheduledReportRunResponse

        now = datetime.now(UTC)
        response = ScheduledReportRunResponse(
            report_id=1,
            status="running",
            message="Report generation started",
            started_at=now,
        )

        assert response.report_id == 1
        assert response.status == "running"
        assert response.message == "Report generation started"
        assert response.started_at == now

    def test_run_response_queued_status(self) -> None:
        """Test run response with queued status."""
        from datetime import UTC, datetime

        from backend.api.schemas.scheduled_report import ScheduledReportRunResponse

        response = ScheduledReportRunResponse(
            report_id=5,
            status="queued",
            message="Report has been queued for generation",
            started_at=datetime.now(UTC),
        )

        assert response.status == "queued"

    def test_run_response_serialization(self) -> None:
        """Test run response serializes correctly."""
        from datetime import UTC, datetime

        from backend.api.schemas.scheduled_report import ScheduledReportRunResponse

        response = ScheduledReportRunResponse(
            report_id=10,
            status="failed",
            message="Report generation failed: timeout",
            started_at=datetime(2025, 1, 25, 10, 30, 0, tzinfo=UTC),
        )

        data = response.model_dump(mode="json")

        assert data["report_id"] == 10
        assert data["status"] == "failed"
        assert "timeout" in data["message"]
        assert "started_at" in data
