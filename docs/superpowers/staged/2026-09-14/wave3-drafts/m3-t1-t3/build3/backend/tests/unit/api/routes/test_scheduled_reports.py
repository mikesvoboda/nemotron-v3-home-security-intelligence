"""Unit tests for scheduled reports API routes.

NEM-3621: Create Scheduled Reports API Schemas and Routes

Tests cover:
- POST /api/scheduled-reports - Create scheduled report
- GET /api/scheduled-reports - List all scheduled reports
- GET /api/scheduled-reports/{report_id} - Get single report
- PUT /api/scheduled-reports/{report_id} - Update report
- DELETE /api/scheduled-reports/{report_id} - Delete report
- POST /api/scheduled-reports/{report_id}/run - Manually trigger report

These tests follow TDD methodology with mocking for database operations.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# CreateScheduledReport Tests
# =============================================================================


class TestCreateScheduledReport:
    """Tests for POST /api/scheduled-reports endpoint."""

    @pytest.mark.asyncio
    async def test_create_scheduled_report_success(self) -> None:
        """Test successfully creating a scheduled report."""
        from backend.api.routes.scheduled_reports import create_scheduled_report
        from backend.api.schemas.scheduled_report import (
            ReportFrequency,
            ScheduledReportCreate,
        )

        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        report_data = ScheduledReportCreate(
            name="Daily Security Report",
            frequency=ReportFrequency.DAILY,
            hour=8,
            minute=0,
        )

        # Mock the model class
        # Note: Use configure_mock for 'name' to avoid LogRecord conflict
        mock_report = MagicMock()
        mock_report.configure_mock(name="Daily Security Report")
        mock_report.id = 1
        mock_report.frequency = "daily"
        mock_report.day_of_week = None
        mock_report.day_of_month = None
        mock_report.hour = 8
        mock_report.minute = 0
        mock_report.timezone = "UTC"
        mock_report.format = "pdf"
        mock_report.enabled = True
        mock_report.email_recipients = None
        mock_report.include_charts = True
        mock_report.include_event_details = True
        mock_report.last_run_at = None
        mock_report.next_run_at = None
        mock_report.created_at = datetime.now(UTC)
        mock_report.updated_at = datetime.now(UTC)

        with patch(
            "backend.api.routes.scheduled_reports.ScheduledReport",
            return_value=mock_report,
        ):
            result = await create_scheduled_report(
                report_data=report_data,
                db=mock_db,
            )

        assert result.name == "Daily Security Report"
        assert result.frequency == "daily"
        assert result.hour == 8
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_scheduled_report_weekly(self) -> None:
        """Test creating a weekly scheduled report with day_of_week."""
        from backend.api.routes.scheduled_reports import create_scheduled_report
        from backend.api.schemas.scheduled_report import (
            ReportFrequency,
            ScheduledReportCreate,
        )

        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        report_data = ScheduledReportCreate(
            name="Weekly Summary",
            frequency=ReportFrequency.WEEKLY,
            day_of_week=1,  # Tuesday
            hour=9,
        )

        # Note: Use configure_mock for 'name' to avoid LogRecord conflict
        mock_report = MagicMock()
        mock_report.configure_mock(name="Weekly Summary")
        mock_report.id = 2
        mock_report.frequency = "weekly"
        mock_report.day_of_week = 1
        mock_report.day_of_month = None
        mock_report.hour = 9
        mock_report.minute = 0
        mock_report.timezone = "UTC"
        mock_report.format = "pdf"
        mock_report.enabled = True
        mock_report.email_recipients = None
        mock_report.include_charts = True
        mock_report.include_event_details = True
        mock_report.last_run_at = None
        mock_report.next_run_at = None
        mock_report.created_at = datetime.now(UTC)
        mock_report.updated_at = datetime.now(UTC)

        with patch(
            "backend.api.routes.scheduled_reports.ScheduledReport",
            return_value=mock_report,
        ):
            result = await create_scheduled_report(
                report_data=report_data,
                db=mock_db,
            )

        assert result.frequency == "weekly"
        assert result.day_of_week == 1


# =============================================================================
# ListScheduledReports Tests
# =============================================================================


class TestListScheduledReports:
    """Tests for GET /api/scheduled-reports endpoint."""

    @pytest.mark.asyncio
    async def test_list_scheduled_reports_success(self) -> None:
        """Test listing all scheduled reports."""
        from backend.api.routes.scheduled_reports import list_scheduled_reports

        mock_db = AsyncMock()

        mock_report1 = MagicMock()
        mock_report1.id = 1
        mock_report1.name = "Report 1"
        mock_report1.frequency = "daily"
        mock_report1.day_of_week = None
        mock_report1.day_of_month = None
        mock_report1.hour = 8
        mock_report1.minute = 0
        mock_report1.timezone = "UTC"
        mock_report1.format = "pdf"
        mock_report1.enabled = True
        mock_report1.email_recipients = None
        mock_report1.include_charts = True
        mock_report1.include_event_details = True
        mock_report1.last_run_at = None
        mock_report1.next_run_at = None
        mock_report1.created_at = datetime.now(UTC)
        mock_report1.updated_at = datetime.now(UTC)

        mock_report2 = MagicMock()
        mock_report2.id = 2
        mock_report2.name = "Report 2"
        mock_report2.frequency = "weekly"
        mock_report2.day_of_week = 1
        mock_report2.day_of_month = None
        mock_report2.hour = 9
        mock_report2.minute = 30
        mock_report2.timezone = "America/New_York"
        mock_report2.format = "csv"
        mock_report2.enabled = False
        mock_report2.email_recipients = ["admin@example.com"]
        mock_report2.include_charts = False
        mock_report2.include_event_details = True
        mock_report2.last_run_at = datetime.now(UTC)
        mock_report2.next_run_at = datetime.now(UTC)
        mock_report2.created_at = datetime.now(UTC)
        mock_report2.updated_at = datetime.now(UTC)

        # Mock query execution - first for list, second for count
        mock_result_list = MagicMock()
        mock_result_list.scalars.return_value.all.return_value = [
            mock_report1,
            mock_report2,
        ]

        mock_result_count = MagicMock()
        mock_result_count.scalar.return_value = 2

        mock_db.execute.side_effect = [mock_result_list, mock_result_count]

        with patch("backend.api.routes.scheduled_reports.select") as mock_select:
            # Configure mock_select to return a mock query
            mock_query = MagicMock()
            mock_query.order_by.return_value = mock_query
            mock_query.where.return_value = mock_query
            mock_select.return_value = mock_query

            with patch("backend.api.routes.scheduled_reports.func"):
                result = await list_scheduled_reports(
                    enabled=None,
                    db=mock_db,
                )

        assert result.total == 2
        assert len(result.items) == 2
        assert result.items[0].name == "Report 1"
        assert result.items[1].name == "Report 2"

    @pytest.mark.asyncio
    async def test_list_scheduled_reports_filter_enabled(self) -> None:
        """Test listing reports filtered by enabled status."""
        from backend.api.routes.scheduled_reports import list_scheduled_reports

        mock_db = AsyncMock()

        mock_report = MagicMock()
        mock_report.id = 1
        mock_report.name = "Enabled Report"
        mock_report.frequency = "daily"
        mock_report.day_of_week = None
        mock_report.day_of_month = None
        mock_report.hour = 8
        mock_report.minute = 0
        mock_report.timezone = "UTC"
        mock_report.format = "pdf"
        mock_report.enabled = True
        mock_report.email_recipients = None
        mock_report.include_charts = True
        mock_report.include_event_details = True
        mock_report.last_run_at = None
        mock_report.next_run_at = None
        mock_report.created_at = datetime.now(UTC)
        mock_report.updated_at = datetime.now(UTC)

        mock_result_list = MagicMock()
        mock_result_list.scalars.return_value.all.return_value = [mock_report]

        mock_result_count = MagicMock()
        mock_result_count.scalar.return_value = 1

        mock_db.execute.side_effect = [mock_result_list, mock_result_count]

        with patch("backend.api.routes.scheduled_reports.select") as mock_select:
            mock_query = MagicMock()
            mock_query.order_by.return_value = mock_query
            mock_query.where.return_value = mock_query
            mock_select.return_value = mock_query

            with patch("backend.api.routes.scheduled_reports.func"):
                result = await list_scheduled_reports(
                    enabled=True,
                    db=mock_db,
                )

        assert result.total == 1
        assert result.items[0].enabled is True

    @pytest.mark.asyncio
    async def test_list_scheduled_reports_empty(self) -> None:
        """Test listing reports when none exist."""
        from backend.api.routes.scheduled_reports import list_scheduled_reports

        mock_db = AsyncMock()

        mock_result_list = MagicMock()
        mock_result_list.scalars.return_value.all.return_value = []

        mock_result_count = MagicMock()
        mock_result_count.scalar.return_value = 0

        mock_db.execute.side_effect = [mock_result_list, mock_result_count]

        with patch("backend.api.routes.scheduled_reports.select") as mock_select:
            mock_query = MagicMock()
            mock_query.order_by.return_value = mock_query
            mock_query.where.return_value = mock_query
            mock_select.return_value = mock_query

            with patch("backend.api.routes.scheduled_reports.func"):
                result = await list_scheduled_reports(
                    enabled=None,
                    db=mock_db,
                )

        assert result.total == 0
        assert result.items == []


# =============================================================================
# GetScheduledReport Tests
# =============================================================================


class TestGetScheduledReport:
    """Tests for GET /api/scheduled-reports/{report_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_scheduled_report_success(self) -> None:
        """Test getting a specific scheduled report by ID."""
        from backend.api.routes.scheduled_reports import get_scheduled_report

        mock_db = AsyncMock()

        mock_report = MagicMock()
        mock_report.id = 1
        mock_report.name = "Test Report"
        mock_report.frequency = "daily"
        mock_report.day_of_week = None
        mock_report.day_of_month = None
        mock_report.hour = 8
        mock_report.minute = 0
        mock_report.timezone = "UTC"
        mock_report.format = "pdf"
        mock_report.enabled = True
        mock_report.email_recipients = None
        mock_report.include_charts = True
        mock_report.include_event_details = True
        mock_report.last_run_at = None
        mock_report.next_run_at = None
        mock_report.created_at = datetime.now(UTC)
        mock_report.updated_at = datetime.now(UTC)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_report
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.scheduled_reports.select") as mock_select:
            mock_query = MagicMock()
            mock_query.where.return_value = mock_query
            mock_select.return_value = mock_query

            result = await get_scheduled_report(
                report_id=1,
                db=mock_db,
            )

        assert result.id == 1
        assert result.name == "Test Report"

    @pytest.mark.asyncio
    async def test_get_scheduled_report_not_found(self) -> None:
        """Test getting a non-existent report returns 404."""
        from fastapi import HTTPException

        from backend.api.routes.scheduled_reports import get_scheduled_report

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.scheduled_reports.select") as mock_select:
            mock_query = MagicMock()
            mock_query.where.return_value = mock_query
            mock_select.return_value = mock_query

            with pytest.raises(HTTPException) as exc_info:
                await get_scheduled_report(
                    report_id=999,
                    db=mock_db,
                )

            assert exc_info.value.status_code == 404
            assert "999" in exc_info.value.detail


# =============================================================================
# UpdateScheduledReport Tests
# =============================================================================


class TestUpdateScheduledReport:
    """Tests for PUT /api/scheduled-reports/{report_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_scheduled_report_success(self) -> None:
        """Test successfully updating a scheduled report."""
        from backend.api.routes.scheduled_reports import update_scheduled_report
        from backend.api.schemas.scheduled_report import ScheduledReportUpdate

        mock_db = AsyncMock()

        mock_report = MagicMock()
        mock_report.id = 1
        mock_report.name = "Original Name"
        mock_report.frequency = "daily"
        mock_report.day_of_week = None
        mock_report.day_of_month = None
        mock_report.hour = 8
        mock_report.minute = 0
        mock_report.timezone = "UTC"
        mock_report.format = "pdf"
        mock_report.enabled = True
        mock_report.email_recipients = None
        mock_report.include_charts = True
        mock_report.include_event_details = True
        mock_report.last_run_at = None
        mock_report.next_run_at = None
        mock_report.created_at = datetime.now(UTC)
        mock_report.updated_at = datetime.now(UTC)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_report
        mock_db.execute.return_value = mock_result

        update_data = ScheduledReportUpdate(name="Updated Name", enabled=False)

        with patch("backend.api.routes.scheduled_reports.select") as mock_select:
            mock_query = MagicMock()
            mock_query.where.return_value = mock_query
            mock_select.return_value = mock_query

            result = await update_scheduled_report(
                report_id=1,
                report_data=update_data,
                db=mock_db,
            )

        # Verify the name was updated on the mock
        assert mock_report.name == "Updated Name"
        assert mock_report.enabled is False
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_scheduled_report_not_found(self) -> None:
        """Test updating a non-existent report returns 404."""
        from fastapi import HTTPException

        from backend.api.routes.scheduled_reports import update_scheduled_report
        from backend.api.schemas.scheduled_report import ScheduledReportUpdate

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        update_data = ScheduledReportUpdate(name="Updated Name")

        with patch("backend.api.routes.scheduled_reports.select") as mock_select:
            mock_query = MagicMock()
            mock_query.where.return_value = mock_query
            mock_select.return_value = mock_query

            with pytest.raises(HTTPException) as exc_info:
                await update_scheduled_report(
                    report_id=999,
                    report_data=update_data,
                    db=mock_db,
                )

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_scheduled_report_partial(self) -> None:
        """Test partial update only changes specified fields."""
        from backend.api.routes.scheduled_reports import update_scheduled_report
        from backend.api.schemas.scheduled_report import ScheduledReportUpdate

        mock_db = AsyncMock()

        mock_report = MagicMock()
        mock_report.id = 1
        mock_report.name = "Original Name"
        mock_report.frequency = "daily"
        mock_report.day_of_week = None
        mock_report.day_of_month = None
        mock_report.hour = 8
        mock_report.minute = 0
        mock_report.timezone = "UTC"
        mock_report.format = "pdf"
        mock_report.enabled = True
        mock_report.email_recipients = None
        mock_report.include_charts = True
        mock_report.include_event_details = True
        mock_report.last_run_at = None
        mock_report.next_run_at = None
        mock_report.created_at = datetime.now(UTC)
        mock_report.updated_at = datetime.now(UTC)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_report
        mock_db.execute.return_value = mock_result

        # Only update hour
        update_data = ScheduledReportUpdate(hour=10)

        with patch("backend.api.routes.scheduled_reports.select") as mock_select:
            mock_query = MagicMock()
            mock_query.where.return_value = mock_query
            mock_select.return_value = mock_query

            await update_scheduled_report(
                report_id=1,
                report_data=update_data,
                db=mock_db,
            )

        # Only hour should be updated
        assert mock_report.hour == 10
        # Name should remain unchanged
        assert mock_report.name == "Original Name"


# =============================================================================
# DeleteScheduledReport Tests
# =============================================================================


class TestDeleteScheduledReport:
    """Tests for DELETE /api/scheduled-reports/{report_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_scheduled_report_success(self) -> None:
        """Test successfully deleting a scheduled report."""
        from backend.api.routes.scheduled_reports import delete_scheduled_report

        mock_db = AsyncMock()

        mock_report = MagicMock()
        mock_report.id = 1

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_report
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.scheduled_reports.select") as mock_select:
            mock_query = MagicMock()
            mock_query.where.return_value = mock_query
            mock_select.return_value = mock_query

            result = await delete_scheduled_report(
                report_id=1,
                db=mock_db,
            )

        assert result is None
        mock_db.delete.assert_called_once_with(mock_report)
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_scheduled_report_not_found(self) -> None:
        """Test deleting a non-existent report returns 404."""
        from fastapi import HTTPException

        from backend.api.routes.scheduled_reports import delete_scheduled_report

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.scheduled_reports.select") as mock_select:
            mock_query = MagicMock()
            mock_query.where.return_value = mock_query
            mock_select.return_value = mock_query

            with pytest.raises(HTTPException) as exc_info:
                await delete_scheduled_report(
                    report_id=999,
                    db=mock_db,
                )

            assert exc_info.value.status_code == 404


# =============================================================================
# RunScheduledReport Tests
# =============================================================================


class TestRunScheduledReport:
    """Tests for POST /api/scheduled-reports/{report_id}/run endpoint."""

    @pytest.mark.asyncio
    async def test_run_scheduled_report_success(self) -> None:
        """Test manually triggering a scheduled report."""
        from backend.api.routes.scheduled_reports import run_scheduled_report

        mock_db = AsyncMock()

        mock_report = MagicMock()
        mock_report.id = 1
        mock_report.name = "Test Report"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_report
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.scheduled_reports.select") as mock_select:
            mock_query = MagicMock()
            mock_query.where.return_value = mock_query
            mock_select.return_value = mock_query

            result = await run_scheduled_report(
                report_id=1,
                db=mock_db,
            )

        assert result.report_id == 1
        assert result.status == "queued"
        assert "Test Report" in result.message
        assert result.started_at is not None

    @pytest.mark.asyncio
    async def test_run_scheduled_report_not_found(self) -> None:
        """Test running a non-existent report returns 404."""
        from fastapi import HTTPException

        from backend.api.routes.scheduled_reports import run_scheduled_report

        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with patch("backend.api.routes.scheduled_reports.select") as mock_select:
            mock_query = MagicMock()
            mock_query.where.return_value = mock_query
            mock_select.return_value = mock_query

            with pytest.raises(HTTPException) as exc_info:
                await run_scheduled_report(
                    report_id=999,
                    db=mock_db,
                )

            assert exc_info.value.status_code == 404
