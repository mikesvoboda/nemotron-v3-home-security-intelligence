"""Unit tests for the export service (NEM-2088).

Tests verify CSV and Excel export functionality including:
1. Format detection from Accept headers
2. CSV generation with proper escaping
3. Excel generation with formatting
4. CSV injection protection
5. Filename generation
"""

from datetime import UTC, datetime

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
        assert parse_accept_header("application/json") == ExportFormat.CSV

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
