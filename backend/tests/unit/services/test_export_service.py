"""Unit tests for the export service (NEM-2088).

Tests verify CSV and Excel export functionality including:
1. Format detection from Accept headers
2. CSV generation with proper escaping
3. Excel generation with formatting
4. CSV injection protection
5. Filename generation
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from backend.services.export_service import (
    ACCEPT_HEADER_MAPPING,
    EXPORT_COLUMNS,
    EXPORT_EXTENSIONS,
    EXPORT_MIME_TYPES,
    EXTENDED_EXPORT_COLUMNS,
    EventExportRow,
    ExportFormat,
    ExportService,
    events_to_csv,
    events_to_csv_streaming,
    events_to_excel,
    format_export_value,
    generate_export_filename,
    get_export_service,
    parse_accept_header,
    reset_export_service,
    sanitize_export_value,
)


class TestSanitizeExportValue:
    """Tests for CSV injection protection in export values."""

    def test_equals_sign_sanitized(self):
        """Test that values starting with = are sanitized."""
        malicious = '=HYPERLINK("http://evil.com","Click")'
        sanitized = sanitize_export_value(malicious)

        assert not sanitized.startswith("=")
        assert sanitized.startswith("'=")

    def test_plus_sign_sanitized(self):
        """Test that values starting with + are sanitized."""
        malicious = "+1+1"
        sanitized = sanitize_export_value(malicious)

        assert not sanitized.startswith("+")
        assert sanitized.startswith("'+")

    def test_minus_sign_sanitized(self):
        """Test that values starting with - are sanitized."""
        malicious = "-1+1"
        sanitized = sanitize_export_value(malicious)

        assert not sanitized.startswith("-")
        assert sanitized.startswith("'-")

    def test_at_sign_sanitized(self):
        """Test that values starting with @ are sanitized."""
        malicious = "@SUM(A1:A10)"
        sanitized = sanitize_export_value(malicious)

        assert not sanitized.startswith("@")
        assert sanitized.startswith("'@")

    def test_tab_sanitized(self):
        """Test that values starting with tab are sanitized."""
        malicious = "\t=cmd|'/C calc'!A0"
        sanitized = sanitize_export_value(malicious)

        assert not sanitized.startswith("\t")
        assert sanitized.startswith("'\t")

    def test_carriage_return_sanitized(self):
        """Test that values starting with carriage return are sanitized."""
        malicious = "\r=cmd|'/C calc'!A0"
        sanitized = sanitize_export_value(malicious)

        assert not sanitized.startswith("\r")
        assert sanitized.startswith("'\r")

    def test_normal_value_unchanged(self):
        """Test that normal values are not modified."""
        normal = "Person detected near entrance"
        sanitized = sanitize_export_value(normal)

        assert sanitized == normal

    def test_empty_string_unchanged(self):
        """Test that empty strings are handled correctly."""
        assert sanitize_export_value("") == ""

    def test_none_returns_empty_string(self):
        """Test that None returns empty string."""
        assert sanitize_export_value(None) == ""

    def test_value_with_special_char_in_middle_unchanged(self):
        """Test that values with special chars in middle are not modified."""
        value = "Person detected - 10:00 AM"
        sanitized = sanitize_export_value(value)

        assert sanitized == value


class TestParseAcceptHeader:
    """Tests for Accept header parsing."""

    def test_csv_text_csv(self):
        """Test text/csv maps to CSV format."""
        assert parse_accept_header("text/csv") == ExportFormat.CSV

    def test_csv_application_csv(self):
        """Test application/csv maps to CSV format."""
        assert parse_accept_header("application/csv") == ExportFormat.CSV

    def test_excel_openxml(self):
        """Test XLSX MIME type maps to Excel format."""
        accept = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert parse_accept_header(accept) == ExportFormat.EXCEL

    def test_excel_ms_excel(self):
        """Test application/vnd.ms-excel maps to Excel format."""
        assert parse_accept_header("application/vnd.ms-excel") == ExportFormat.EXCEL

    def test_excel_xlsx(self):
        """Test application/xlsx maps to Excel format."""
        assert parse_accept_header("application/xlsx") == ExportFormat.EXCEL

    def test_none_defaults_to_csv(self):
        """Test that None Accept header defaults to CSV."""
        assert parse_accept_header(None) == ExportFormat.CSV

    def test_empty_defaults_to_csv(self):
        """Test that empty Accept header defaults to CSV."""
        assert parse_accept_header("") == ExportFormat.CSV

    def test_unknown_defaults_to_csv(self):
        """Test that unknown MIME type defaults to CSV."""
        assert parse_accept_header("text/html") == ExportFormat.CSV
        assert parse_accept_header("application/xml") == ExportFormat.CSV

    def test_json_returns_json(self):
        """Test that application/json returns JSON format (NEM-3611)."""
        assert parse_accept_header("application/json") == ExportFormat.JSON

    def test_wildcard_defaults_to_csv(self):
        """Test that */* defaults to CSV."""
        assert parse_accept_header("*/*") == ExportFormat.CSV

    def test_text_wildcard_defaults_to_csv(self):
        """Test that text/* defaults to CSV."""
        assert parse_accept_header("text/*") == ExportFormat.CSV

    def test_accept_header_with_quality_values(self):
        """Test parsing Accept header with quality values."""
        accept = "text/csv;q=0.9, application/json;q=0.8"
        assert parse_accept_header(accept) == ExportFormat.CSV

    def test_accept_header_multiple_types_prefers_first_match(self):
        """Test that first matching type is used."""
        accept = "text/csv, application/xlsx"
        assert parse_accept_header(accept) == ExportFormat.CSV

    def test_accept_header_excel_first(self):
        """Test Excel format when listed first."""
        accept = "application/xlsx, text/csv"
        assert parse_accept_header(accept) == ExportFormat.EXCEL

    def test_case_insensitive(self):
        """Test that Accept header parsing is case-insensitive."""
        assert parse_accept_header("TEXT/CSV") == ExportFormat.CSV
        assert parse_accept_header("Application/XLSX") == ExportFormat.EXCEL


class TestGenerateExportFilename:
    """Tests for filename generation."""

    def test_csv_extension(self):
        """Test CSV files get .csv extension."""
        filename = generate_export_filename("events_export", ExportFormat.CSV)

        assert filename.startswith("events_export_")
        assert filename.endswith(".csv")

    def test_excel_extension(self):
        """Test Excel files get .xlsx extension."""
        filename = generate_export_filename("events_export", ExportFormat.EXCEL)

        assert filename.startswith("events_export_")
        assert filename.endswith(".xlsx")

    def test_timestamp_format(self):
        """Test filename includes timestamp in expected format."""
        filename = generate_export_filename("test", ExportFormat.CSV)

        # Extract timestamp part: test_YYYYMMDD_HHMMSS.csv
        parts = filename.replace(".csv", "").split("_")
        assert len(parts) >= 3

        # Verify timestamp format
        date_part = parts[1]
        time_part = parts[2]
        assert len(date_part) == 8  # YYYYMMDD
        assert len(time_part) == 6  # HHMMSS


class TestEventExportRow:
    """Tests for EventExportRow dataclass."""

    def test_create_minimal_row(self):
        """Test creating row with required fields only."""
        row = EventExportRow(
            event_id=1,
            camera_name="Front Door",
            started_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
            ended_at=None,
            risk_score=75,
            risk_level="high",
            summary="Person detected",
            detection_count=3,
            reviewed=False,
        )

        assert row.event_id == 1
        assert row.camera_name == "Front Door"
        assert row.detection_count == 3

    def test_create_full_row(self):
        """Test creating row with all fields."""
        row = EventExportRow(
            event_id=1,
            camera_name="Front Door",
            started_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
            ended_at=datetime(2024, 1, 15, 10, 31, 30, tzinfo=UTC),
            risk_score=75,
            risk_level="high",
            summary="Person detected",
            detection_count=3,
            reviewed=True,
            object_types="person,vehicle",
            reasoning="Multiple persons detected near entrance",
        )

        assert row.object_types == "person,vehicle"
        assert row.reasoning == "Multiple persons detected near entrance"


class TestFormatExportValue:
    """Tests for export value formatting."""

    def test_format_datetime(self):
        """Test datetime formatting as ISO string."""
        row = EventExportRow(
            event_id=1,
            camera_name="Test",
            started_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
            ended_at=None,
            risk_score=50,
            risk_level="medium",
            summary="Test",
            detection_count=1,
            reviewed=False,
        )

        value = format_export_value(row, "started_at")
        assert "2024-01-15" in value
        assert "10:30:00" in value

    def test_format_boolean_true(self):
        """Test boolean True formats as Yes."""
        row = EventExportRow(
            event_id=1,
            camera_name="Test",
            started_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
            ended_at=None,
            risk_score=50,
            risk_level="medium",
            summary="Test",
            detection_count=1,
            reviewed=True,
        )

        value = format_export_value(row, "reviewed")
        assert value == "Yes"

    def test_format_boolean_false(self):
        """Test boolean False formats as No."""
        row = EventExportRow(
            event_id=1,
            camera_name="Test",
            started_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
            ended_at=None,
            risk_score=50,
            risk_level="medium",
            summary="Test",
            detection_count=1,
            reviewed=False,
        )

        value = format_export_value(row, "reviewed")
        assert value == "No"

    def test_format_integer(self):
        """Test integer formatting."""
        row = EventExportRow(
            event_id=42,
            camera_name="Test",
            started_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
            ended_at=None,
            risk_score=75,
            risk_level="high",
            summary="Test",
            detection_count=5,
            reviewed=False,
        )

        assert format_export_value(row, "event_id") == "42"
        assert format_export_value(row, "risk_score") == "75"

    def test_format_none(self):
        """Test None formatting as empty string."""
        row = EventExportRow(
            event_id=1,
            camera_name="Test",
            started_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
            ended_at=None,
            risk_score=None,
            risk_level=None,
            summary=None,
            detection_count=1,
            reviewed=False,
        )

        assert format_export_value(row, "ended_at") == ""
        assert format_export_value(row, "risk_score") == ""
        assert format_export_value(row, "summary") == ""

    def test_format_string_with_injection_char(self):
        """Test string with injection character is sanitized."""
        row = EventExportRow(
            event_id=1,
            camera_name="Test",
            started_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
            ended_at=None,
            risk_score=50,
            risk_level="medium",
            summary="=HYPERLINK(...)",
            detection_count=1,
            reviewed=False,
        )

        value = format_export_value(row, "summary")
        assert value.startswith("'=")


class TestEventsToCSV:
    """Tests for CSV generation."""

    @pytest.fixture
    def sample_events(self) -> list[EventExportRow]:
        """Create sample events for testing."""
        return [
            EventExportRow(
                event_id=1,
                camera_name="Front Door",
                started_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
                ended_at=datetime(2024, 1, 15, 10, 31, 30, tzinfo=UTC),
                risk_score=75,
                risk_level="high",
                summary="Person detected at entrance",
                detection_count=3,
                reviewed=False,
            ),
            EventExportRow(
                event_id=2,
                camera_name="Back Yard",
                started_at=datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC),
                ended_at=None,
                risk_score=25,
                risk_level="low",
                summary="Cat in garden",
                detection_count=1,
                reviewed=True,
            ),
        ]

    def test_csv_has_header_row(self, sample_events: list[EventExportRow]):
        """Test CSV output includes header row."""
        csv_content = events_to_csv(sample_events)
        lines = csv_content.strip().split("\n")

        # First line should be header
        header = lines[0]
        assert "Event ID" in header
        assert "Camera" in header
        assert "Started At" in header
        assert "Risk Score" in header

    def test_csv_has_data_rows(self, sample_events: list[EventExportRow]):
        """Test CSV output includes data rows."""
        csv_content = events_to_csv(sample_events)
        lines = csv_content.strip().split("\n")

        # Should have header + 2 data rows
        assert len(lines) == 3

    def test_csv_contains_event_data(self, sample_events: list[EventExportRow]):
        """Test CSV contains expected event data."""
        csv_content = events_to_csv(sample_events)

        assert "Front Door" in csv_content
        assert "Back Yard" in csv_content
        assert "Person detected at entrance" in csv_content
        assert "Cat in garden" in csv_content

    def test_csv_empty_list(self):
        """Test CSV with empty event list."""
        csv_content = events_to_csv([])
        lines = csv_content.strip().split("\n")

        # Should have header only
        assert len(lines) == 1
        assert "Event ID" in lines[0]

    def test_csv_custom_columns(self, sample_events: list[EventExportRow]):
        """Test CSV with custom column selection."""
        columns = [
            ("event_id", "ID"),
            ("camera_name", "Camera"),
            ("risk_score", "Score"),
        ]

        csv_content = events_to_csv(sample_events, columns=columns)
        lines = csv_content.strip().split("\n")

        # Header should only have custom columns
        header = lines[0]
        assert "ID" in header
        assert "Camera" in header
        assert "Score" in header
        assert "Summary" not in header


class TestEventsToExcel:
    """Tests for Excel generation."""

    @pytest.fixture
    def sample_events(self) -> list[EventExportRow]:
        """Create sample events for testing."""
        return [
            EventExportRow(
                event_id=1,
                camera_name="Front Door",
                started_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
                ended_at=datetime(2024, 1, 15, 10, 31, 30, tzinfo=UTC),
                risk_score=75,
                risk_level="high",
                summary="Person detected at entrance",
                detection_count=3,
                reviewed=False,
            ),
            EventExportRow(
                event_id=2,
                camera_name="Back Yard",
                started_at=datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC),
                ended_at=None,
                risk_score=25,
                risk_level="low",
                summary="Cat in garden",
                detection_count=1,
                reviewed=True,
            ),
        ]

    def test_excel_returns_bytes(self, sample_events: list[EventExportRow]):
        """Test Excel export returns bytes."""
        content = events_to_excel(sample_events)

        assert isinstance(content, bytes)
        assert len(content) > 0

    def test_excel_has_xlsx_signature(self, sample_events: list[EventExportRow]):
        """Test Excel file has XLSX signature (ZIP format)."""
        content = events_to_excel(sample_events)

        # XLSX files are ZIP archives, start with PK signature
        assert content[:2] == b"PK"

    def test_excel_can_be_read_by_openpyxl(self, sample_events: list[EventExportRow]):
        """Test Excel file can be read back by openpyxl."""
        import io

        from openpyxl import load_workbook

        content = events_to_excel(sample_events)
        wb = load_workbook(io.BytesIO(content))

        assert wb.active is not None
        ws = wb.active
        assert ws.title == "Events"

    def test_excel_contains_header_row(self, sample_events: list[EventExportRow]):
        """Test Excel file contains header row."""
        import io

        from openpyxl import load_workbook

        content = events_to_excel(sample_events)
        wb = load_workbook(io.BytesIO(content))
        ws = wb.active

        # Check header row (row 1)
        assert ws.cell(row=1, column=1).value == "Event ID"
        assert ws.cell(row=1, column=2).value == "Camera"

    def test_excel_contains_data(self, sample_events: list[EventExportRow]):
        """Test Excel file contains event data."""
        import io

        from openpyxl import load_workbook

        content = events_to_excel(sample_events)
        wb = load_workbook(io.BytesIO(content))
        ws = wb.active

        # Check first data row (row 2)
        assert ws.cell(row=2, column=1).value == 1  # event_id
        assert ws.cell(row=2, column=2).value == "Front Door"  # camera_name

        # Check second data row (row 3)
        assert ws.cell(row=3, column=1).value == 2
        assert ws.cell(row=3, column=2).value == "Back Yard"

    def test_excel_custom_sheet_name(self, sample_events: list[EventExportRow]):
        """Test Excel file with custom sheet name."""
        import io

        from openpyxl import load_workbook

        content = events_to_excel(sample_events, sheet_name="Security Events")
        wb = load_workbook(io.BytesIO(content))
        ws = wb.active

        assert ws.title == "Security Events"

    def test_excel_empty_list(self):
        """Test Excel with empty event list."""
        import io

        from openpyxl import load_workbook

        content = events_to_excel([])
        wb = load_workbook(io.BytesIO(content))
        ws = wb.active

        # Should have header only
        assert ws.cell(row=1, column=1).value == "Event ID"
        assert ws.cell(row=2, column=1).value is None

    def test_excel_handles_none_values(self):
        """Test Excel handles None values correctly."""
        import io

        from openpyxl import load_workbook

        events = [
            EventExportRow(
                event_id=1,
                camera_name="Test",
                started_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
                ended_at=None,
                risk_score=None,
                risk_level=None,
                summary=None,
                detection_count=0,
                reviewed=False,
            ),
        ]

        content = events_to_excel(events)
        wb = load_workbook(io.BytesIO(content))
        ws = wb.active

        # None values should be empty strings
        assert ws.cell(row=2, column=4).value in (None, "")  # ended_at
        assert ws.cell(row=2, column=5).value in (None, "")  # risk_score


class TestExportService:
    """Tests for ExportService class."""

    @pytest.fixture(autouse=True)
    def reset_service(self):
        """Reset service singleton before each test."""
        reset_export_service()
        yield
        reset_export_service()

    def test_get_export_service_singleton(self):
        """Test get_export_service returns singleton."""
        service1 = get_export_service()
        service2 = get_export_service()

        assert service1 is service2

    def test_get_export_format(self):
        """Test format detection from Accept header."""
        service = ExportService()

        assert service.get_export_format("text/csv") == ExportFormat.CSV
        assert service.get_export_format("application/xlsx") == ExportFormat.EXCEL

    def test_get_content_type_csv(self):
        """Test content type for CSV format."""
        service = ExportService()

        content_type = service.get_content_type(ExportFormat.CSV)
        assert content_type == "text/csv"

    def test_get_content_type_excel(self):
        """Test content type for Excel format."""
        service = ExportService()

        content_type = service.get_content_type(ExportFormat.EXCEL)
        assert content_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    def test_get_filename(self):
        """Test filename generation."""
        service = ExportService()

        csv_filename = service.get_filename("events", ExportFormat.CSV)
        excel_filename = service.get_filename("events", ExportFormat.EXCEL)

        assert csv_filename.endswith(".csv")
        assert excel_filename.endswith(".xlsx")

    def test_export_events_csv(self):
        """Test exporting events as CSV."""
        service = ExportService()
        events = [
            EventExportRow(
                event_id=1,
                camera_name="Test",
                started_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
                ended_at=None,
                risk_score=50,
                risk_level="medium",
                summary="Test event",
                detection_count=1,
                reviewed=False,
            ),
        ]

        content = service.export_events(events, ExportFormat.CSV)

        assert isinstance(content, str)
        assert "Test" in content
        assert "Event ID" in content

    def test_export_events_excel(self):
        """Test exporting events as Excel."""
        service = ExportService()
        events = [
            EventExportRow(
                event_id=1,
                camera_name="Test",
                started_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
                ended_at=None,
                risk_score=50,
                risk_level="medium",
                summary="Test event",
                detection_count=1,
                reviewed=False,
            ),
        ]

        content = service.export_events(events, ExportFormat.EXCEL)

        assert isinstance(content, bytes)
        assert content[:2] == b"PK"  # ZIP signature

    def test_content_disposition_attachment(self):
        """Test Content-Disposition header for attachment."""
        service = ExportService()

        header = service.get_content_disposition_header("events.csv")
        assert header == 'attachment; filename="events.csv"'

    def test_content_disposition_inline(self):
        """Test Content-Disposition header for inline."""
        service = ExportService()

        header = service.get_content_disposition_header("events.csv", inline=True)
        assert header == 'inline; filename="events.csv"'


class TestEventsToCSVStreaming:
    """Tests for CSV streaming generation."""

    @pytest.fixture
    def sample_events(self) -> list[EventExportRow]:
        """Create sample events for testing."""
        return [
            EventExportRow(
                event_id=1,
                camera_name="Front Door",
                started_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
                ended_at=datetime(2024, 1, 15, 10, 31, 30, tzinfo=UTC),
                risk_score=75,
                risk_level="high",
                summary="Person detected at entrance",
                detection_count=3,
                reviewed=False,
            ),
            EventExportRow(
                event_id=2,
                camera_name="Back Yard",
                started_at=datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC),
                ended_at=None,
                risk_score=25,
                risk_level="low",
                summary="Cat in garden",
                detection_count=1,
                reviewed=True,
            ),
        ]

    def test_streaming_yields_chunks(self, sample_events: list[EventExportRow]):
        """Test that streaming yields chunks of CSV data."""
        from backend.services.export_service import events_to_csv_streaming

        chunks = list(events_to_csv_streaming(sample_events))

        # Should have at least header + 2 data rows
        assert len(chunks) >= 3

    def test_streaming_first_chunk_is_header(self, sample_events: list[EventExportRow]):
        """Test that first chunk contains header row."""
        from backend.services.export_service import events_to_csv_streaming

        chunks = list(events_to_csv_streaming(sample_events))
        first_chunk = chunks[0]

        assert "Event ID" in first_chunk
        assert "Camera" in first_chunk

    def test_streaming_contains_data(self, sample_events: list[EventExportRow]):
        """Test that streaming contains event data."""
        from backend.services.export_service import events_to_csv_streaming

        chunks = list(events_to_csv_streaming(sample_events))
        all_content = "".join(chunks)

        assert "Front Door" in all_content
        assert "Back Yard" in all_content

    def test_streaming_with_empty_list(self):
        """Test streaming with empty event list."""
        from backend.services.export_service import events_to_csv_streaming

        chunks = list(events_to_csv_streaming([]))

        # Should only yield header
        assert len(chunks) == 1
        assert "Event ID" in chunks[0]

    def test_streaming_with_custom_columns(self, sample_events: list[EventExportRow]):
        """Test streaming with custom columns."""
        from backend.services.export_service import events_to_csv_streaming

        columns = [
            ("event_id", "ID"),
            ("camera_name", "Camera"),
        ]

        chunks = list(events_to_csv_streaming(sample_events, columns=columns))
        first_chunk = chunks[0]

        assert "ID" in first_chunk
        assert "Camera" in first_chunk
        assert "Risk Score" not in first_chunk


@pytest.mark.asyncio
class TestExportServiceWithProgress:
    """Tests for export service with progress tracking."""

    @pytest.fixture
    async def mock_db(self):
        """Create a mock database session."""
        from unittest.mock import AsyncMock

        db = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def mock_job_tracker(self):
        """Create a mock job tracker."""
        from unittest.mock import MagicMock

        tracker = MagicMock()
        tracker.update_progress = MagicMock()
        return tracker

    async def test_export_with_progress_no_db_raises_error(self):
        """Test that export with progress raises error without database."""
        from unittest.mock import MagicMock

        service = ExportService()
        tracker = MagicMock()

        with pytest.raises(ValueError, match="Database session required"):
            await service.export_events_with_progress(
                job_id="test-job",
                job_tracker=tracker,
                export_format="csv",
            )

    async def test_export_with_progress_empty_results(self, mock_db, mock_job_tracker):
        """Test export with progress when no events match filters."""
        from unittest.mock import MagicMock

        # Mock empty count result
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        mock_db.execute.return_value = count_result

        service = ExportService(db=mock_db)

        result = await service.export_events_with_progress(
            job_id="test-job",
            job_tracker=mock_job_tracker,
            export_format="csv",
        )

        # Should create empty export
        assert result["event_count"] == 0
        assert result["format"] == "csv"
        assert "file_path" in result

        # Should update progress
        mock_job_tracker.update_progress.assert_called()

    async def test_export_with_progress_invalid_format(self, mock_db, mock_job_tracker):
        """Test export with progress with invalid format."""
        from unittest.mock import MagicMock

        # Mock empty count
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        mock_db.execute.return_value = count_result

        service = ExportService(db=mock_db)

        with pytest.raises(ValueError, match="Unsupported export format"):
            await service.export_events_with_progress(
                job_id="test-job",
                job_tracker=mock_job_tracker,
                export_format="invalid",
            )

    async def test_export_with_progress_csv_format(self, mock_db, mock_job_tracker):
        """Test export with progress for CSV format."""
        from unittest.mock import AsyncMock, MagicMock

        # Mock event query result using MagicMock
        event = MagicMock()
        event.id = 1
        event.camera_id = "cam-1"
        event.started_at = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        event.ended_at = datetime(2024, 1, 15, 10, 31, 30, tzinfo=UTC)
        event.risk_score = 75
        event.risk_level = "high"
        event.summary = "Test event"
        event.detection_count = 3
        event.reviewed = False
        event.object_types = None
        event.reasoning = None

        event_result = MagicMock()
        event_result.scalars.return_value.all.return_value = [event]

        # Mock camera query result
        camera_result = MagicMock()
        camera_result.scalar.return_value = "Front Door"

        # Mock count result
        count_result = MagicMock()
        count_result.scalar.return_value = 1

        # Setup mock side_effect to return different results per call
        # Order: count query, events query, camera query (for each event)
        mock_db.execute = AsyncMock(side_effect=[count_result, event_result, camera_result])

        service = ExportService(db=mock_db)

        result = await service.export_events_with_progress(
            job_id="test-job",
            job_tracker=mock_job_tracker,
            export_format="csv",
        )

        assert result["format"] == "csv"
        assert result["event_count"] == 1
        assert result["file_path"].endswith(".csv")
        assert result["file_size"] > 0

    async def test_export_with_progress_json_format(self, mock_db, mock_job_tracker):
        """Test export with progress for JSON format."""
        from unittest.mock import AsyncMock, MagicMock

        # Mock event query result
        event = MagicMock()
        event.id = 1
        event.camera_id = "cam-1"
        event.started_at = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        event.ended_at = None
        event.risk_score = 75
        event.risk_level = "high"
        event.summary = "Test"
        event.detection_count = 1
        event.reviewed = False
        event.object_types = None
        event.reasoning = None

        event_result = MagicMock()
        event_result.scalars.return_value.all.return_value = [event]

        # Mock camera query result
        camera_result = MagicMock()
        camera_result.scalar.return_value = "Camera"

        # Mock count result
        count_result = MagicMock()
        count_result.scalar.return_value = 1

        mock_db.execute = AsyncMock(side_effect=[count_result, event_result, camera_result])

        service = ExportService(db=mock_db)

        result = await service.export_events_with_progress(
            job_id="test-job",
            job_tracker=mock_job_tracker,
            export_format="json",
        )

        assert result["format"] == "json"
        assert result["file_path"].endswith(".json")

    async def test_export_with_progress_zip_format(self, mock_db, mock_job_tracker):
        """Test export with progress for ZIP format."""
        from unittest.mock import AsyncMock, MagicMock

        # Mock event query result
        event = MagicMock()
        event.id = 1
        event.camera_id = "cam-1"
        event.started_at = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        event.ended_at = None
        event.risk_score = 50
        event.risk_level = "medium"
        event.summary = "Test"
        event.detection_count = 1
        event.reviewed = False
        event.object_types = None
        event.reasoning = None

        event_result = MagicMock()
        event_result.scalars.return_value.all.return_value = [event]

        # Mock camera query result
        camera_result = MagicMock()
        camera_result.scalar.return_value = "Camera"

        # Mock count result
        count_result = MagicMock()
        count_result.scalar.return_value = 1

        mock_db.execute = AsyncMock(side_effect=[count_result, event_result, camera_result])

        service = ExportService(db=mock_db)

        result = await service.export_events_with_progress(
            job_id="test-job",
            job_tracker=mock_job_tracker,
            export_format="zip",
        )

        assert result["format"] == "zip"
        assert result["file_path"].endswith(".zip")

    async def test_export_with_progress_applies_camera_filter(self, mock_db, mock_job_tracker):
        """Test that camera filter is applied in query."""
        from unittest.mock import MagicMock

        # Mock empty count
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        mock_db.execute.return_value = count_result

        service = ExportService(db=mock_db)

        await service.export_events_with_progress(
            job_id="test-job",
            job_tracker=mock_job_tracker,
            export_format="csv",
            camera_id="cam-123",
        )

        # Should have called execute (filter logic is in SQL)
        assert mock_db.execute.called

    async def test_export_with_progress_applies_risk_level_filter(self, mock_db, mock_job_tracker):
        """Test that risk level filter is applied in query."""
        from unittest.mock import MagicMock

        # Mock empty count
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        mock_db.execute.return_value = count_result

        service = ExportService(db=mock_db)

        await service.export_events_with_progress(
            job_id="test-job",
            job_tracker=mock_job_tracker,
            export_format="csv",
            risk_level="high",
        )

        assert mock_db.execute.called

    async def test_export_with_progress_applies_date_filters(self, mock_db, mock_job_tracker):
        """Test that date filters are applied in query."""
        from unittest.mock import MagicMock

        # Mock empty count
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        mock_db.execute.return_value = count_result

        service = ExportService(db=mock_db)

        await service.export_events_with_progress(
            job_id="test-job",
            job_tracker=mock_job_tracker,
            export_format="csv",
            start_date="2024-01-15T00:00:00Z",
            end_date="2024-01-16T00:00:00Z",
        )

        assert mock_db.execute.called

    async def test_export_with_progress_applies_reviewed_filter(self, mock_db, mock_job_tracker):
        """Test that reviewed filter is applied in query."""
        from unittest.mock import MagicMock

        # Mock empty count
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        mock_db.execute.return_value = count_result

        service = ExportService(db=mock_db)

        await service.export_events_with_progress(
            job_id="test-job",
            job_tracker=mock_job_tracker,
            export_format="csv",
            reviewed=True,
        )

        assert mock_db.execute.called


@pytest.mark.asyncio
class TestCreateEmptyExport:
    """Tests for _create_empty_export method."""

    async def test_create_empty_csv(self):
        """Test creating empty CSV export."""
        service = ExportService()

        result = await service._create_empty_export("csv")

        assert result["format"] == "csv"
        assert result["event_count"] == 0
        assert result["file_path"].endswith(".csv")
        assert result["file_size"] > 0

    async def test_create_empty_json(self):
        """Test creating empty JSON export."""
        service = ExportService()

        result = await service._create_empty_export("json")

        assert result["format"] == "json"
        assert result["event_count"] == 0
        assert result["file_path"].endswith(".json")
        assert result["file_size"] > 0

    async def test_create_empty_zip(self):
        """Test creating empty ZIP export."""
        service = ExportService()

        result = await service._create_empty_export("zip")

        assert result["format"] == "zip"
        assert result["event_count"] == 0
        assert result["file_path"].endswith(".zip")
        assert result["file_size"] > 0

    async def test_create_empty_invalid_format(self):
        """Test creating empty export with invalid format."""
        service = ExportService()

        with pytest.raises(ValueError, match="Unsupported export format"):
            await service._create_empty_export("invalid")


@pytest.mark.asyncio
class TestExportServiceWithWebSocket:
    """Tests for export service with WebSocket progress reporting."""

    @pytest.fixture
    async def mock_db(self):
        """Create a mock database session."""
        from unittest.mock import AsyncMock

        db = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def mock_progress_reporter(self):
        """Create a mock progress reporter."""
        from unittest.mock import AsyncMock, MagicMock

        reporter = MagicMock()
        reporter.start = AsyncMock()
        reporter.report_progress = AsyncMock()
        reporter.complete = AsyncMock()
        reporter.fail = AsyncMock()
        reporter.job_id = "test-job-123"
        reporter.duration_seconds = 1.23
        return reporter

    async def test_export_with_websocket_no_db_raises_error(self, mock_progress_reporter):
        """Test that export with websocket raises error without database."""
        service = ExportService()

        with pytest.raises(ValueError, match="Database session required"):
            await service.export_events_with_websocket(
                progress_reporter=mock_progress_reporter,
                export_format="csv",
            )

    async def test_export_with_websocket_starts_reporter(self, mock_db, mock_progress_reporter):
        """Test that reporter is started with metadata."""
        from unittest.mock import MagicMock

        # Mock empty count
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        mock_db.execute.return_value = count_result

        service = ExportService(db=mock_db)

        await service.export_events_with_websocket(
            progress_reporter=mock_progress_reporter,
            export_format="csv",
        )

        # Verify reporter was started with metadata
        mock_progress_reporter.start.assert_called_once()
        call_args = mock_progress_reporter.start.call_args
        assert "metadata" in call_args[1]
        assert call_args[1]["metadata"]["export_format"] == "csv"

    async def test_export_with_websocket_completes_successfully(
        self, mock_db, mock_progress_reporter
    ):
        """Test that successful export completes the reporter."""
        from unittest.mock import MagicMock

        # Mock empty count
        count_result = MagicMock()
        count_result.scalar.return_value = 0
        mock_db.execute.return_value = count_result

        service = ExportService(db=mock_db)

        result = await service.export_events_with_websocket(
            progress_reporter=mock_progress_reporter,
            export_format="csv",
        )

        # Verify reporter was completed
        mock_progress_reporter.complete.assert_called_once()
        assert result["event_count"] == 0

    async def test_export_with_websocket_reports_progress(self, mock_db, mock_progress_reporter):
        """Test that progress is reported during export."""
        from unittest.mock import AsyncMock, MagicMock

        # Mock event
        event = MagicMock()
        event.id = 1
        event.camera_id = "cam-1"
        event.started_at = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        event.ended_at = None
        event.risk_score = 75
        event.risk_level = "high"
        event.summary = "Test"
        event.detection_count = 1
        event.reviewed = False
        event.object_types = None
        event.reasoning = None

        event_result = MagicMock()
        event_result.scalars.return_value.all.return_value = [event]

        camera_result = MagicMock()
        camera_result.scalar.return_value = "Camera"

        # Mock count result
        count_result = MagicMock()
        count_result.scalar.return_value = 1

        mock_db.execute = AsyncMock(side_effect=[count_result, event_result, camera_result])

        service = ExportService(db=mock_db)

        await service.export_events_with_websocket(
            progress_reporter=mock_progress_reporter,
            export_format="csv",
        )

        # Verify progress was reported
        assert mock_progress_reporter.report_progress.call_count > 0

    async def test_export_with_websocket_handles_exception(self, mock_db, mock_progress_reporter):
        """Test that exceptions are handled and reporter fails."""

        # Mock database to raise exception
        mock_db.execute.side_effect = RuntimeError("Database error")

        service = ExportService(db=mock_db)

        with pytest.raises(RuntimeError, match="Database error"):
            await service.export_events_with_websocket(
                progress_reporter=mock_progress_reporter,
                export_format="csv",
            )

        # Verify reporter was failed
        mock_progress_reporter.fail.assert_called_once()
        call_args = mock_progress_reporter.fail.call_args
        assert isinstance(call_args[0][0], RuntimeError)

    async def test_export_with_websocket_invalid_format(self, mock_db, mock_progress_reporter):
        """Test export with websocket with invalid format."""
        from unittest.mock import AsyncMock, MagicMock

        # Mock event
        event = MagicMock()
        event.id = 1
        event.camera_id = "cam-1"
        event.started_at = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        event.ended_at = None
        event.risk_score = 75
        event.risk_level = "high"
        event.summary = "Test"
        event.detection_count = 1
        event.reviewed = False
        event.object_types = None
        event.reasoning = None

        event_result = MagicMock()
        event_result.scalars.return_value.all.return_value = [event]

        camera_result = MagicMock()
        camera_result.scalar.return_value = "Camera"

        # Mock count result
        count_result = MagicMock()
        count_result.scalar.return_value = 1

        mock_db.execute = AsyncMock(side_effect=[count_result, event_result, camera_result])

        service = ExportService(db=mock_db)

        with pytest.raises(ValueError, match="Unsupported export format"):
            await service.export_events_with_websocket(
                progress_reporter=mock_progress_reporter,
                export_format="invalid",
            )

        # Verify reporter was failed
        mock_progress_reporter.fail.assert_called_once()

    async def test_export_with_websocket_includes_duration(self, mock_db, mock_progress_reporter):
        """Test that result includes duration from reporter when events exist."""
        from unittest.mock import AsyncMock, MagicMock

        # Mock event
        event = MagicMock()
        event.id = 1
        event.camera_id = "cam-1"
        event.started_at = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        event.ended_at = None
        event.risk_score = 75
        event.risk_level = "high"
        event.summary = "Test"
        event.detection_count = 1
        event.reviewed = False
        event.object_types = None
        event.reasoning = None

        event_result = MagicMock()
        event_result.scalars.return_value.all.return_value = [event]

        camera_result = MagicMock()
        camera_result.scalar.return_value = "Camera"

        # Mock count result with 1 event
        count_result = MagicMock()
        count_result.scalar.return_value = 1

        mock_db.execute = AsyncMock(side_effect=[count_result, event_result, camera_result])

        service = ExportService(db=mock_db)

        result = await service.export_events_with_websocket(
            progress_reporter=mock_progress_reporter,
            export_format="csv",
        )

        # Verify duration is included when events exist
        assert "duration_seconds" in result
        assert result["duration_seconds"] == 1.23


class TestExportConstants:
    """Tests for export constant definitions."""

    def test_export_mime_types_defined(self):
        """Test MIME types are defined for all formats."""
        assert ExportFormat.CSV in EXPORT_MIME_TYPES
        assert ExportFormat.EXCEL in EXPORT_MIME_TYPES

    def test_export_extensions_defined(self):
        """Test extensions are defined for all formats."""
        assert ExportFormat.CSV in EXPORT_EXTENSIONS
        assert ExportFormat.EXCEL in EXPORT_EXTENSIONS
        assert EXPORT_EXTENSIONS[ExportFormat.CSV] == ".csv"
        assert EXPORT_EXTENSIONS[ExportFormat.EXCEL] == ".xlsx"

    def test_accept_header_mapping_complete(self):
        """Test Accept header mapping covers common MIME types."""
        assert "text/csv" in ACCEPT_HEADER_MAPPING
        assert "application/csv" in ACCEPT_HEADER_MAPPING
        assert "application/xlsx" in ACCEPT_HEADER_MAPPING
        assert "application/vnd.ms-excel" in ACCEPT_HEADER_MAPPING

    def test_export_columns_defined(self):
        """Test export columns are defined."""
        assert len(EXPORT_COLUMNS) > 0

        # Check required columns exist
        field_names = [col[0] for col in EXPORT_COLUMNS]
        assert "event_id" in field_names
        assert "camera_name" in field_names
        assert "risk_score" in field_names
        assert "reviewed" in field_names

    def test_extended_columns_include_base(self):
        """Test extended columns include base columns."""
        base_fields = {col[0] for col in EXPORT_COLUMNS}
        extended_fields = {col[0] for col in EXTENDED_EXPORT_COLUMNS}

        # All base fields should be in extended
        assert base_fields.issubset(extended_fields)

        # Extended should have additional fields
        assert "object_types" in extended_fields
        assert "reasoning" in extended_fields


class TestExportDeferredColumns:
    """Mechanism lock for R-T9-EXPORTDEFER (deferred Event.reasoning).

    Two sides, both required — each alone is launderable:
    1. The MODEL contract: a bare ``select(Event)`` must still NOT render
       events.reasoning. If someone "fixes" the defect by un-deferring the
       column outright, every query pays the large-text load again (the
       ledger's rejected alternative) — this side goes red on that move.
    2. The FIX contract: the export methods' EVENT query must render
       events.reasoning (undefer at query-build), while its COUNT companion
       stays untouched. Empirical basis (SQLAlchemy 2.0.53): a plain deferred
       select omits the column from compiled text; ``.options(undefer(...))``
       adds it; a count-over-subquery renders all columns EITHER way, so only
       the fetch statement is checked for presence.
    """

    @staticmethod
    def _mock_event():
        from unittest.mock import MagicMock

        event = MagicMock()
        event.id = 1
        event.camera_id = "cam-1"
        event.started_at = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        event.ended_at = None
        event.risk_score = 75
        event.risk_level = "high"
        event.summary = "Test"
        event.detection_count = 1
        event.reviewed = False
        event.object_types = None
        event.reasoning = "why the model thought so"
        return event

    @staticmethod
    def _mock_results(event):
        from unittest.mock import MagicMock

        count_result = MagicMock()
        count_result.scalar.return_value = 1
        event_result = MagicMock()
        event_result.scalars.return_value.all.return_value = [event]
        camera_result = MagicMock()
        camera_result.scalar.return_value = "Camera"
        return [count_result, event_result, camera_result]

    def test_bare_event_select_still_defers_reasoning(self):
        """Side 1: the column stays deferred at the model — the fix belongs
        at the query site, not at mapped_column(deferred(...))."""
        from sqlalchemy import select

        from backend.models.event import Event

        text_ = str(select(Event).compile())
        assert "events.reasoning" not in text_

    async def test_progress_method_fetch_undefers_reasoning(self, tmp_path):
        """Side 2 for export_events_with_progress: the FETCH statement (2nd
        execute; 1st is the count, 3rd the camera-name lookup) must carry
        undefer(Event.reasoning) — reading the deferred column synchronously
        inside the async job is what raised MissingGreenlet."""
        from unittest.mock import AsyncMock

        from backend.services.job_tracker import JobTracker

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=self._mock_results(self._mock_event()))

        tracker = JobTracker()
        tracker.create_job("export", job_id="defer-lock-job")

        service = ExportService(db=mock_db)
        await service.export_events_with_progress(
            job_id="defer-lock-job",
            job_tracker=tracker,
            export_format="csv",
        )

        stmts = [c.args[0] for c in mock_db.execute.call_args_list]
        assert len(stmts) == 3  # count, fetch, camera-name
        assert "events.reasoning" in str(stmts[1].compile())

    async def test_websocket_method_fetch_undefers_reasoning(self):
        """Side 2 for export_events_with_websocket (no production callers —
        fixed same commit as cleanup; locked here identically)."""
        from unittest.mock import AsyncMock, MagicMock

        reporter = MagicMock()
        reporter.start = AsyncMock()
        reporter.report_progress = AsyncMock()
        reporter.complete = AsyncMock()
        reporter.fail = AsyncMock()
        reporter.job_id = "defer-lock-job"
        reporter.duration_seconds = 1.0

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=self._mock_results(self._mock_event()))

        service = ExportService(db=mock_db)
        await service.export_events_with_websocket(
            progress_reporter=reporter,
            export_format="csv",
        )

        stmts = [c.args[0] for c in mock_db.execute.call_args_list]
        assert len(stmts) == 3
        assert "events.reasoning" in str(stmts[1].compile())


# =============================================================================
# WP4.4 kill battery (frozen triage feed archive/wp25-feed/wp44-triage/
# export_service.md, clusters T1-T6 + SQL-COUNT-W/FILENAME-P/WS-RESULT/
# WS-FAIL/SINGLETON/DJ/CSV-SEEK/EMPTY/EE-COLUMNS/GF-PREFIX). Root cause per
# the dossier: every DB-backed method ran through an argument-blind AsyncMock
# asserting only returned-dict shape and execute.called — written file bytes,
# compiled SQL text, progress VALUES and reporter payloads were never read.
# All tests below pin the SHIPPED contract (source read at this commit);
# zero production change. SQL-text precedent: TestExportDeferredColumns.
# =============================================================================


def _two_event_db():
    """count=2 → 2 events → camera hits: the execute side_effect the progress
    and websocket paths consume in order (count, fetch, cam, cam)."""
    from unittest.mock import AsyncMock, MagicMock

    e1 = MagicMock()
    e1.id = 42
    e1.camera_id = "cam-7"
    e1.started_at = datetime(2024, 3, 1, 9, 0, 0, tzinfo=UTC)
    e1.ended_at = datetime(2024, 3, 1, 9, 5, 0, tzinfo=UTC)
    e1.risk_score = 75
    e1.risk_level = "high"
    e1.summary = "Person at door"
    e1.detection_count = None  # `or 0` must render 0
    e1.reviewed = None  # `or False` must render "No"
    e1.object_types = "person, dog"
    e1.reasoning = "why the model thought so"

    e2 = MagicMock()
    e2.id = 43
    e2.camera_id = "cam-missing"
    e2.started_at = datetime(2024, 3, 2, 10, 0, 0, tzinfo=UTC)
    e2.ended_at = None
    e2.risk_score = None
    e2.risk_level = None
    e2.summary = None
    e2.detection_count = 2
    e2.reviewed = True
    e2.object_types = None
    e2.reasoning = None

    count_result = MagicMock()
    count_result.scalar.return_value = 2
    event_result = MagicMock()
    event_result.scalars.return_value.all.return_value = [e1, e2]
    cam1 = MagicMock()
    cam1.scalar.return_value = "Back Gate"
    cam2 = MagicMock()
    cam2.scalar.return_value = None  # miss → "Unknown" fallback

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[count_result, event_result, cam1, cam2])
    return db


def _empty_db():
    from unittest.mock import AsyncMock, MagicMock

    count_result = MagicMock()
    count_result.scalar.return_value = 0
    db = AsyncMock()
    db.execute = AsyncMock(return_value=count_result)
    return db


def _ws_reporter():
    from unittest.mock import AsyncMock, MagicMock

    reporter = MagicMock()
    reporter.start = AsyncMock()
    reporter.report_progress = AsyncMock()
    reporter.complete = AsyncMock()
    reporter.fail = AsyncMock()
    reporter.job_id = "ws-battery"
    reporter.duration_seconds = 1.0
    return reporter


@pytest.mark.asyncio
class TestExportProgressFileContent:
    """T1: export_events_with_progress must write REAL row data to disk.

    ROW-FIELDS-P / FILE-CONTENT-P / COLUMNS / FILENAME-P / PROG-PCT survivors
    existed because the written CSV/JSON was never read back and the tracker
    was asserted as a bare call-count.
    """

    async def test_csv_file_contains_all_event_fields(self, tmp_path, monkeypatch):
        import csv as csv_mod
        import io

        import backend.services.export_service as es

        monkeypatch.setattr(es, "EXPORT_DIR", tmp_path)
        service = es.ExportService(db=_two_event_db())

        result = await service.export_events_with_progress(
            job_id="content-job",
            job_tracker=MagicMock(),
            export_format="csv",
        )

        written = tmp_path / result["file_path"].rsplit("/", 1)[-1]
        rows = list(csv_mod.reader(io.StringIO(written.read_text(encoding="utf-8"))))

        # header = EXTENDED display names in order (kills COLUMNS column-loss)
        assert rows[0] == [display for _, display in es.EXTENDED_EXPORT_COLUMNS]
        # full first row — every field, formatted exactly as shipped
        assert rows[1] == [
            "42",
            "Back Gate",
            "2024-03-01T09:00:00+00:00",
            "2024-03-01T09:05:00+00:00",
            "75",
            "high",
            "Person at door",
            "0",  # detection_count None or 0
            "No",  # reviewed None or False
            "person, dog",
            "why the model thought so",
        ]
        # camera miss → "Unknown" fallback; e2 pass-throughs
        assert rows[2][0] == "43"
        assert rows[2][1] == "Unknown"

    async def test_filename_carries_real_timestamp_digits(self, tmp_path, monkeypatch):
        """FILENAME-P: %Y%m%d_%H%M%S clobbers (XX-wrapped / lowercase
        directives) fail a strict all-digits stem check."""
        import re

        import backend.services.export_service as es

        monkeypatch.setattr(es, "EXPORT_DIR", tmp_path)
        service = es.ExportService(db=_two_event_db())

        result = await service.export_events_with_progress(
            job_id="name-job", job_tracker=MagicMock(), export_format="csv"
        )

        stem = result["file_path"].rsplit("/", 1)[-1][: -len(".csv")]
        assert re.fullmatch(r"events_export_\d{8}_\d{6}", stem)

    async def test_json_file_holds_filtered_row_dicts(self, tmp_path, monkeypatch):
        import json

        import backend.services.export_service as es

        monkeypatch.setattr(es, "EXPORT_DIR", tmp_path)
        service = es.ExportService(db=_two_event_db())

        result = await service.export_events_with_progress(
            job_id="json-job", job_tracker=MagicMock(), export_format="json"
        )

        written = tmp_path / result["file_path"].rsplit("/", 1)[-1]
        dicts = json.loads(written.read_text(encoding="utf-8"))
        assert dicts[0] == {
            "event_id": 42,
            "camera_name": "Back Gate",
            "started_at": "2024-03-01T09:00:00+00:00",
            "ended_at": "2024-03-01T09:05:00+00:00",
            "risk_score": 75,
            "risk_level": "high",
            "summary": "Person at door",
            "detection_count": 0,
            "reviewed": False,
            "object_types": "person, dog",
            "reasoning": "why the model thought so",
        }
        assert dicts[1]["camera_name"] == "Unknown"

    async def test_custom_columns_narrow_csv_and_json(self, tmp_path, monkeypatch):
        """COLUMNS: columns=None fallback hid the custom-columns path —
        get_selected_columns order and filter_row_to_dict keys asserted."""
        import csv as csv_mod
        import io
        import json

        import backend.services.export_service as es

        monkeypatch.setattr(es, "EXPORT_DIR", tmp_path)
        service = es.ExportService(db=_two_event_db())

        result = await service.export_events_with_progress(
            job_id="col-job",
            job_tracker=MagicMock(),
            export_format="csv",
            columns=["summary", "event_id"],
        )
        written = tmp_path / result["file_path"].rsplit("/", 1)[-1]
        rows = list(csv_mod.reader(io.StringIO(written.read_text(encoding="utf-8"))))
        assert rows[0] == ["Summary", "Event ID"]  # requested order preserved
        assert rows[1] == ["Person at door", "42"]

        db2 = _two_event_db()
        service2 = es.ExportService(db=db2)
        result2 = await service2.export_events_with_progress(
            job_id="col-job-2",
            job_tracker=MagicMock(),
            export_format="json",
            columns=["risk_level"],
        )
        written2 = tmp_path / result2["file_path"].rsplit("/", 1)[-1]
        assert json.loads(written2.read_text(encoding="utf-8"))[0] == {"risk_level": "high"}

    async def test_progress_percentages_are_shipped_values(self, tmp_path, monkeypatch):
        """PROG-PCT: tracker VALUES (10/80/95 + message), not call_count."""
        import backend.services.export_service as es

        monkeypatch.setattr(es, "EXPORT_DIR", tmp_path)
        tracker = MagicMock()
        service = es.ExportService(db=_two_event_db())

        await service.export_events_with_progress(
            job_id="pct-job", job_tracker=tracker, export_format="csv"
        )

        calls = [
            (c.args[1], c.kwargs.get("message")) for c in tracker.update_progress.call_args_list
        ]
        assert calls == [
            (10, "Found 2 events to export"),
            (80, "Writing CSV file..."),  # export_format.upper()
            (95, "Finalizing export..."),
        ]


@pytest.mark.asyncio
class TestExportQueryShape:
    """T2: filters must RENDER into compiled SQL. Existing filter tests
    asserted only execute.called — SQLAlchemy 2.x compiles where(None)/!=
    happily, so filter-loss mutants were invisible. Precedent:
    TestExportDeferredColumns."""

    async def test_all_filters_render_into_count_statement(self, tmp_path, monkeypatch):
        from datetime import datetime as dt

        import backend.services.export_service as es

        monkeypatch.setattr(es, "EXPORT_DIR", tmp_path)
        db = _empty_db()
        service = es.ExportService(db=db)
        await service.export_events_with_progress(
            job_id="shape-job",
            job_tracker=MagicMock(),
            export_format="csv",
            camera_id="cam-9",
            risk_level="high",
            start_date="2024-01-15T00:00:00Z",
            end_date="2024-01-16T23:59:59Z",
            reviewed=True,
        )

        # count==0 must SHORT-CIRCUIT to the empty export (kills `or 1`)
        assert db.execute.call_count == 1

        stmt = db.execute.call_args_list[0].args[0]
        text_ = str(stmt.compile())
        assert "events.deleted_at IS NULL" in text_
        assert "events.camera_id = :" in text_
        assert "events.risk_level = :" in text_
        assert "events.started_at >= :" in text_
        assert "events.started_at <= :" in text_
        assert "events.reviewed = true" in text_  # bool renders as literal
        assert "!=" not in text_  # no flipped comparison anywhere
        assert "SELECT count(*)" in text_  # SQL-COUNT: count pipeline intact

        params = stmt.compile().params
        assert "cam-9" in params.values()
        assert "high" in params.values()
        assert dt.fromisoformat("2024-01-15T00:00:00+00:00") in params.values()
        assert dt.fromisoformat("2024-01-16T23:59:59+00:00") in params.values()

    async def test_fetch_statement_orders_desc(self, tmp_path, monkeypatch):
        import backend.services.export_service as es

        monkeypatch.setattr(es, "EXPORT_DIR", tmp_path)
        db = _two_event_db()
        service = es.ExportService(db=db)
        await service.export_events_with_progress(
            job_id="ord-job", job_tracker=MagicMock(), export_format="csv"
        )
        fetch_text = str(db.execute.call_args_list[1].args[0].compile())
        assert "ORDER BY events.started_at DESC" in fetch_text

    async def test_websocket_filters_render_identically(self, tmp_path, monkeypatch):
        """SQL-FILTER-W/SQL-COUNT-W: the ws method builds the SAME statement."""
        from datetime import datetime as dt

        import backend.services.export_service as es

        monkeypatch.setattr(es, "EXPORT_DIR", tmp_path)
        db = _empty_db()
        service = es.ExportService(db=db)
        await service.export_events_with_websocket(
            progress_reporter=_ws_reporter(),
            export_format="csv",
            camera_id="cam-9",
            risk_level="high",
            start_date="2024-01-15T00:00:00Z",
            end_date="2024-01-16T23:59:59Z",
            reviewed=True,
        )

        # count==0 must SHORT-CIRCUIT to the empty export (kills `or 1`)
        assert db.execute.call_count == 1

        stmt = db.execute.call_args_list[0].args[0]
        text_ = str(stmt.compile())
        assert "events.deleted_at IS NULL" in text_
        assert "events.camera_id = :" in text_
        assert "events.risk_level = :" in text_
        assert "events.started_at >= :" in text_
        assert "events.started_at <= :" in text_
        assert "events.reviewed = true" in text_  # bool renders as literal
        assert "!=" not in text_
        assert "SELECT count(*)" in text_
        params = stmt.compile().params
        assert dt.fromisoformat("2024-01-15T00:00:00+00:00") in params.values()


@pytest.mark.asyncio
class TestWebSocketProgressSequence:
    """T3: report_progress call VALUES, not call_count (NEM-2380 contract).
    WS-PROG (32 survivors), WS-RESULT, WS-EMPTY, WS-FAIL."""

    async def test_report_progress_call_sequence(self, tmp_path, monkeypatch):
        import backend.services.export_service as es

        monkeypatch.setattr(es, "EXPORT_DIR", tmp_path)
        reporter = _ws_reporter()
        service = es.ExportService(db=_two_event_db())

        await service.export_events_with_websocket(progress_reporter=reporter, export_format="csv")

        calls = [
            (c.args[0], c.kwargs.get("current_step"), c.kwargs.get("force"))
            for c in reporter.report_progress.call_args_list
        ]
        assert calls == [
            (1, "Found 2 events to export", True),
            (35, "Processing event 1/2", None),  # int(1/2*70)
            (70, "Processing event 2/2", None),  # kills *71, (idx+2)
            (80, "Writing CSV file...", True),
            (95, "Finalizing export...", True),
        ]

    async def test_complete_receives_result_summary(self, tmp_path, monkeypatch):
        """WS-RESULT: complete(result_summary=...) carries the full dict."""
        import backend.services.export_service as es

        monkeypatch.setattr(es, "EXPORT_DIR", tmp_path)
        reporter = _ws_reporter()
        service = es.ExportService(db=_two_event_db())

        result = await service.export_events_with_websocket(
            progress_reporter=reporter, export_format="csv"
        )

        summary = reporter.complete.call_args.kwargs["result_summary"]
        assert summary == result  # same dict shipped to the caller
        assert summary["event_count"] == 2
        assert summary["format"] == "csv"
        assert summary["duration_seconds"] == 1.0
        assert summary["file_path"].startswith("/api/exports/events_export_")
        assert summary["file_size"] > 0

    async def test_empty_path_completes_with_message(self, tmp_path, monkeypatch):
        """WS-EMPTY: empty export still completes with result_summary + msg."""
        import backend.services.export_service as es

        monkeypatch.setattr(es, "EXPORT_DIR", tmp_path)
        reporter = _ws_reporter()
        service = es.ExportService(db=_empty_db())

        result = await service.export_events_with_websocket(
            progress_reporter=reporter, export_format="json"
        )

        summary = reporter.complete.call_args.kwargs["result_summary"]
        assert summary["message"] == "No events to export"
        assert summary["event_count"] == 0
        assert result["event_count"] == 0

    async def test_failure_reports_retryable_false(self):
        """WS-FAIL: fail(e, retryable=False) — the job-retry contract.
        Existing exception test asserts call+type only, never retryable."""
        from unittest.mock import AsyncMock

        reporter = _ws_reporter()
        reporter.start = AsyncMock(side_effect=RuntimeError("boom"))
        service = ExportService(db=_empty_db())

        with pytest.raises(RuntimeError, match="boom"):
            await service.export_events_with_websocket(
                progress_reporter=reporter, export_format="csv"
            )

        reporter.fail.assert_called_once()
        exc_arg = reporter.fail.call_args.args[0]
        assert isinstance(exc_arg, RuntimeError)
        assert reporter.fail.call_args.kwargs["retryable"] is False


@pytest.mark.asyncio
@pytest.mark.asyncio
class TestWebSocketFileContent:
    """WS counterpart of T1: the websocket path writes EXTENDED-columns CSV
    and its fetch statement carries ORDER BY DESC (ROW-FIELDS-W,
    FILE-CONTENT-W, order_by(None) survivors were invisible)."""

    async def test_websocket_csv_file_contains_rows(self, tmp_path, monkeypatch):
        import csv as csv_mod
        import io

        import backend.services.export_service as es

        monkeypatch.setattr(es, "EXPORT_DIR", tmp_path)
        db = _two_event_db()
        reporter = _ws_reporter()
        await es.ExportService(db=db).export_events_with_websocket(
            progress_reporter=reporter, export_format="csv"
        )

        fetch_text = str(db.execute.call_args_list[1].args[0].compile())
        assert "ORDER BY events.started_at DESC" in fetch_text  # kills order_by(None)

        files = list(tmp_path.glob("events_export_*.csv"))
        assert len(files) == 1
        rows = list(csv_mod.reader(io.StringIO(files[0].read_text(encoding="utf-8"))))
        assert rows[0] == [display for _, display in es.EXTENDED_EXPORT_COLUMNS]
        assert rows[1] == [
            "42",
            "Back Gate",
            "2024-03-01T09:00:00+00:00",
            "2024-03-01T09:05:00+00:00",
            "75",
            "high",
            "Person at door",
            "0",
            "No",
            "person, dog",
            "why the model thought so",
        ]
        assert rows[2][1] == "Unknown"


class TestWebSocketStartMetadata:
    """T4: job.started metadata filters dict is the frontend contract
    (WS-META, 12 survivors — key renames/casing all invisible)."""

    async def test_start_metadata_carries_exact_filter_keys(self, tmp_path, monkeypatch):
        import backend.services.export_service as es

        monkeypatch.setattr(es, "EXPORT_DIR", tmp_path)
        reporter = _ws_reporter()
        service = es.ExportService(db=_empty_db())

        await service.export_events_with_websocket(
            progress_reporter=reporter,
            export_format="csv",
            camera_id="cam-1",
            risk_level="high",
            start_date="2024-01-01T00:00:00Z",
            end_date=None,
            reviewed=True,
        )

        meta = reporter.start.call_args.kwargs["metadata"]
        assert meta["export_format"] == "csv"
        assert meta["filters"] == {  # exact dict equality kills every rename
            "camera_id": "cam-1",
            "risk_level": "high",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": None,
            "reviewed": True,
        }


class TestEventsToExcelCellValues:
    """T5: Excel bool/datetime cell VALUES (XL-CELLS, 10 survivors —
    existing tests assert ids/camera names only)."""

    def test_excel_boolean_reviewed_cells_are_yes_no(self):
        import io

        from openpyxl import load_workbook

        events = [
            EventExportRow(
                event_id=1,
                camera_name="Cam",
                started_at=None,
                ended_at=None,
                risk_score=None,
                risk_level=None,
                summary=None,
                detection_count=1,
                reviewed=True,
            ),
            EventExportRow(
                event_id=2,
                camera_name="Cam",
                started_at=None,
                ended_at=None,
                risk_score=None,
                risk_level=None,
                summary=None,
                detection_count=1,
                reviewed=False,
            ),
        ]
        ws = load_workbook(io.BytesIO(events_to_excel(events))).active
        assert ws.cell(row=2, column=9).value == "Yes"
        assert ws.cell(row=3, column=9).value == "No"

    def test_excel_datetime_cells_are_naive_datetimes(self):
        import io

        from openpyxl import load_workbook

        events = [
            EventExportRow(
                event_id=1,
                camera_name="Cam",
                started_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
                ended_at=None,
                risk_score=None,
                risk_level=None,
                summary=None,
                detection_count=1,
                reviewed=False,
            ),
        ]
        ws = load_workbook(io.BytesIO(events_to_excel(events))).active
        value = ws.cell(row=2, column=3).value  # kills tz-strip→None
        assert value == datetime(2024, 1, 15, 10, 30, 0)
        assert value.tzinfo is None  # openpyxl rejects tz-aware cells


class TestAcceptHeaderQualityValue:
    """T6 / ACCEPT-QP: split(';')→split(None) survivors — existing quality
    test used a CSV header whose mutant outcome is ALSO csv; JSON exposes it."""

    def test_accept_header_json_with_quality_value(self):
        assert parse_accept_header("application/json;q=0.9") == ExportFormat.JSON

    def test_accept_header_json_with_space_quality_value(self):
        assert parse_accept_header("application/json ;q=0.9") == ExportFormat.JSON


class TestDetectionsToJsonDefault:
    """DJ-COLS/DJ-CONTENT: sole covering test passes explicit columns, so
    the DEFAULT path (columns=None → DETECTION_EXPORT_COLUMNS) was free."""

    def test_default_columns_produce_full_detection_row(self):
        import json

        from backend.services.export_service import (
            DETECTION_EXPORT_COLUMNS,
            DetectionExportRow,
            detections_to_json,
        )

        d = DetectionExportRow(
            detection_id=7,
            camera_name="Porch",
            detected_at=datetime(2024, 5, 1, 8, 30, tzinfo=UTC),
            object_type="person",
            confidence=0.91,
            bbox_x=1,
            bbox_y=2,
            bbox_width=3,
            bbox_height=4,
            file_path="/f.jpg",
            thumbnail_path="/t.jpg",
            media_type="image",
        )
        out = json.loads(detections_to_json([d]))
        assert list(out[0].keys()) == [f for f, _ in DETECTION_EXPORT_COLUMNS]
        assert out[0]["detection_id"] == 7
        assert out[0]["detected_at"] == "2024-05-01T08:30:00+00:00"
        assert out[0]["object_type"] == "person"


class TestCsvStreamingByteIntegrity:
    """CSV-SEEK: output.seek(1) on either site leaves a stale byte —
    byte-wise corruption of every yielded row. Streaming tests asserted
    substring presence only, which forgives a leading junk byte."""

    def test_joined_streaming_chunks_equal_non_streaming_csv(self):
        events = [
            EventExportRow(
                event_id=1,
                camera_name="Cam A",
                started_at=datetime(2024, 1, 15, 10, 30, tzinfo=UTC),
                ended_at=None,
                risk_score=50,
                risk_level="medium",
                summary="s",
                detection_count=2,
                reviewed=False,
            )
            for _ in range(3)
        ]
        chunks = list(events_to_csv_streaming(events))
        assert "".join(chunks) == events_to_csv(events)


class TestEmptyExportContent:
    """EMPTY-CONTENT/EMPTY-FILENAME: _create_empty_export tests asserted
    size/format only — content never parsed, filename never shaped."""

    @pytest.mark.parametrize("fmt", ["csv", "json"])
    async def test_empty_export_content_is_well_formed(self, tmp_path, monkeypatch, fmt):
        import json
        import re

        import backend.services.export_service as es

        monkeypatch.setattr(es, "EXPORT_DIR", tmp_path)
        service = es.ExportService(db=_empty_db())

        result = await service.export_events_with_progress(
            job_id=f"empty-{fmt}", job_tracker=MagicMock(), export_format=fmt
        )

        written = tmp_path / result["file_path"].rsplit("/", 1)[-1]
        assert re.fullmatch(rf"events_export_\d{{8}}_\d{{6}}\.{fmt}", written.name)
        if fmt == "csv":
            header = written.read_text(encoding="utf-8").splitlines()[0]
            assert header == ",".join(d for _, d in EXTENDED_EXPORT_COLUMNS)
        else:
            assert json.loads(written.read_text(encoding="utf-8")) == []

    async def test_empty_zip_member_is_empty_json(self, tmp_path, monkeypatch):
        import io
        import json
        import zipfile

        import backend.services.export_service as es

        monkeypatch.setattr(es, "EXPORT_DIR", tmp_path)
        service = es.ExportService(db=_empty_db())

        result = await service.export_events_with_progress(
            job_id="empty-zip", job_tracker=MagicMock(), export_format="zip"
        )

        written = tmp_path / result["file_path"].rsplit("/", 1)[-1]
        with zipfile.ZipFile(io.BytesIO(written.read_bytes())) as zf:
            (member,) = zf.namelist()
            assert member.endswith(".json")
            assert json.loads(zf.read(member)) == []


class TestExportServiceDispatchAndSingleton:
    """SINGLETON / GF-PREFIX / EE-COLUMNS: get_export_service memoized both
    mutants (None-identity equality); get_filename asserted endswith-only;
    export_events dispatch never carried custom columns."""

    def test_get_export_service_returns_constructed_instance(self):
        from backend.services.export_service import get_export_service

        reset_export_service()
        try:
            service = get_export_service()
            assert isinstance(service, ExportService)
            assert get_export_service() is service
        finally:
            reset_export_service()

    def test_reset_then_get_returns_new_instance(self):
        from backend.services.export_service import get_export_service

        reset_export_service()
        try:
            first = get_export_service()
            reset_export_service()
            assert get_export_service() is not first
        finally:
            reset_export_service()

    def test_get_filename_carries_prefix_and_extension(self):
        service = ExportService()
        name = service.get_filename("myexports", ExportFormat.EXCEL)
        assert name.startswith("myexports_")
        assert name.endswith(".xlsx")

    def test_export_events_passes_columns_to_csv_and_excel(self):
        import io

        from openpyxl import load_workbook

        events = [
            EventExportRow(
                event_id=1,
                camera_name="Cam",
                started_at=None,
                ended_at=None,
                risk_score=None,
                risk_level=None,
                summary="hi",
                detection_count=1,
                reviewed=False,
            )
        ]
        service = ExportService()
        cols = [("summary", "Summary")]

        csv_out = service.export_events(events, ExportFormat.CSV, columns=cols)
        assert csv_out.splitlines()[0] == "Summary"
        assert csv_out.splitlines()[1] == "hi"  # sanitizer keeps clean strings

        xlsx = service.export_events(events, ExportFormat.EXCEL, columns=cols)
        ws = load_workbook(io.BytesIO(xlsx)).active
        assert ws.cell(row=1, column=1).value == "Summary"
        assert ws.cell(row=2, column=1).value == "hi"
