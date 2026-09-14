"""Unit tests for SummaryDetailService.

Tests cover:
- Generating detailed summary data with full narrative
- Building timeline of events
- Export functionality (JSON, CSV, PDF)
- Edge cases (no events, partial data)

Related Linear issues: NEM-5425, NEM-5426, NEM-5427
"""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from backend.services.summary_detail_service import (
    ExportFormat,
    SummaryDetailService,
)

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


# Fixtures


@pytest.fixture
def mock_summary() -> MagicMock:
    """Create a mock Summary object with typical values."""
    summary = MagicMock()
    summary.id = 1
    summary.summary_type = "hourly"
    summary.content = "Multiple security events were detected."
    summary.event_count = 3
    summary.event_ids = [101, 102, 103]
    summary.window_start = datetime(2026, 1, 21, 14, 0, tzinfo=UTC)
    summary.window_end = datetime(2026, 1, 21, 15, 0, tzinfo=UTC)
    summary.generated_at = datetime(2026, 1, 21, 14, 55, tzinfo=UTC)
    return summary


@pytest.fixture
def mock_events() -> list[MagicMock]:
    """Create mock Event objects."""
    events: list[MagicMock] = []

    event1 = MagicMock()
    event1.id = 101
    event1.started_at = datetime(2026, 1, 21, 14, 10, tzinfo=UTC)
    event1.ended_at = datetime(2026, 1, 21, 14, 12, tzinfo=UTC)
    event1.camera_id = "front_door"
    event1.camera = MagicMock()
    event1.camera.name = "Front Door"
    event1.summary = "Person detected approaching the front door"
    event1.risk_score = 75
    event1.risk_level = "high"
    event1.object_types = "person"
    event1.entities = [{"type": "person", "recognized": False}]
    events.append(event1)

    event2 = MagicMock()
    event2.id = 102
    event2.started_at = datetime(2026, 1, 21, 14, 30, tzinfo=UTC)
    event2.ended_at = datetime(2026, 1, 21, 14, 32, tzinfo=UTC)
    event2.camera_id = "driveway"
    event2.camera = MagicMock()
    event2.camera.name = "Driveway"
    event2.summary = "Vehicle detected in driveway"
    event2.risk_score = 50
    event2.risk_level = "medium"
    event2.object_types = "vehicle"
    event2.entities = [{"type": "vehicle"}]
    events.append(event2)

    event3 = MagicMock()
    event3.id = 103
    event3.started_at = datetime(2026, 1, 21, 14, 45, tzinfo=UTC)
    event3.ended_at = None  # Ongoing event
    event3.camera_id = "backyard"
    event3.camera = MagicMock()
    event3.camera.name = "Backyard"
    event3.summary = "Motion detected in backyard"
    event3.risk_score = 30
    event3.risk_level = "low"
    event3.object_types = "motion"
    event3.entities = None
    events.append(event3)

    return events


@pytest.fixture
def detail_service() -> SummaryDetailService:
    """Create a SummaryDetailService instance."""
    return SummaryDetailService()


# Tests: Timeline Building


class TestTimelineBuilding:
    """Tests for building timeline from events."""

    def test_build_timeline_from_events(
        self,
        detail_service: SummaryDetailService,
        mock_events: list[MagicMock],
    ) -> None:
        """Test building a timeline from events."""
        timeline = detail_service.build_timeline(mock_events)

        assert len(timeline) == 3
        # Events should be sorted by timestamp (earliest first)
        assert timeline[0].event_id == 101
        assert timeline[1].event_id == 102
        assert timeline[2].event_id == 103

    def test_timeline_event_structure(
        self,
        detail_service: SummaryDetailService,
        mock_events: list[MagicMock],
    ) -> None:
        """Test TimelineEvent has correct structure."""
        timeline = detail_service.build_timeline(mock_events)

        event = timeline[0]
        assert event.event_id == 101
        assert event.timestamp == datetime(2026, 1, 21, 14, 10, tzinfo=UTC)
        assert event.camera_name == "Front Door"
        assert event.summary == "Person detected approaching the front door"
        assert event.risk_score == 75
        assert event.risk_level == "high"
        assert event.event_url is not None
        assert "/events/101" in event.event_url

    def test_build_timeline_empty_events(
        self,
        detail_service: SummaryDetailService,
    ) -> None:
        """Test building timeline with no events returns empty list."""
        timeline = detail_service.build_timeline([])

        assert timeline == []

    def test_timeline_sorts_by_timestamp(
        self,
        detail_service: SummaryDetailService,
    ) -> None:
        """Test timeline events are sorted chronologically."""
        # Create events in reverse order
        events: list[MagicMock] = []

        event_late = MagicMock()
        event_late.id = 2
        event_late.started_at = datetime(2026, 1, 21, 15, 0, tzinfo=UTC)
        event_late.camera = MagicMock()
        event_late.camera.name = "Camera"
        event_late.summary = "Late event"
        event_late.risk_score = 50
        event_late.risk_level = "medium"
        events.append(event_late)

        event_early = MagicMock()
        event_early.id = 1
        event_early.started_at = datetime(2026, 1, 21, 14, 0, tzinfo=UTC)
        event_early.camera = MagicMock()
        event_early.camera.name = "Camera"
        event_early.summary = "Early event"
        event_early.risk_score = 50
        event_early.risk_level = "medium"
        events.append(event_early)

        timeline = detail_service.build_timeline(events)

        assert timeline[0].event_id == 1  # Early event first
        assert timeline[1].event_id == 2  # Late event second

    def test_timeline_handles_missing_camera_relationship(
        self,
        detail_service: SummaryDetailService,
    ) -> None:
        """Test timeline uses camera_id when camera relationship is None."""
        event = MagicMock()
        event.id = 1
        event.started_at = datetime(2026, 1, 21, 14, 0, tzinfo=UTC)
        event.camera_id = "unknown_camera"
        event.camera = None  # No camera relationship
        event.summary = "Event summary"
        event.risk_score = 50
        event.risk_level = "medium"

        timeline = detail_service.build_timeline([event])

        assert len(timeline) == 1
        assert timeline[0].camera_name == "unknown_camera"


# Tests: Export Functionality


class TestExportJSON:
    """Tests for JSON export functionality."""

    def test_export_json_structure(
        self,
        detail_service: SummaryDetailService,
        mock_summary: MagicMock,
        mock_events: list[MagicMock],
    ) -> None:
        """Test JSON export has correct structure."""
        result = detail_service.export_json(mock_summary, mock_events)

        # Should be valid JSON
        data = json.loads(result)

        assert "summary" in data
        assert "events" in data
        assert "metadata" in data

    def test_export_json_summary_fields(
        self,
        detail_service: SummaryDetailService,
        mock_summary: MagicMock,
        mock_events: list[MagicMock],
    ) -> None:
        """Test JSON export includes all summary fields."""
        result = detail_service.export_json(mock_summary, mock_events)
        data = json.loads(result)

        summary_data = data["summary"]
        assert summary_data["id"] == 1
        assert summary_data["type"] == "hourly"
        assert "content" in summary_data
        assert summary_data["event_count"] == 3
        assert "window_start" in summary_data
        assert "window_end" in summary_data
        assert "generated_at" in summary_data

    def test_export_json_events(
        self,
        detail_service: SummaryDetailService,
        mock_summary: MagicMock,
        mock_events: list[MagicMock],
    ) -> None:
        """Test JSON export includes all events."""
        result = detail_service.export_json(mock_summary, mock_events)
        data = json.loads(result)

        events_data = data["events"]
        assert len(events_data) == 3

        event = events_data[0]
        assert "id" in event
        assert "timestamp" in event
        assert "camera" in event
        assert "summary" in event
        assert "risk_score" in event
        assert "risk_level" in event

    def test_export_json_no_events(
        self,
        detail_service: SummaryDetailService,
        mock_summary: MagicMock,
    ) -> None:
        """Test JSON export with no events."""
        mock_summary.event_ids = None
        mock_summary.event_count = 0

        result = detail_service.export_json(mock_summary, [])
        data = json.loads(result)

        assert data["events"] == []
        assert data["metadata"]["event_count"] == 0


class TestExportCSV:
    """Tests for CSV export functionality."""

    def test_export_csv_headers(
        self,
        detail_service: SummaryDetailService,
        mock_summary: MagicMock,
        mock_events: list[MagicMock],
    ) -> None:
        """Test CSV export has correct headers."""
        result = detail_service.export_csv(mock_summary, mock_events)

        reader = csv.reader(io.StringIO(result))
        headers = next(reader)

        assert "Event ID" in headers
        assert "Timestamp" in headers
        assert "Camera" in headers
        assert "Summary" in headers
        assert "Risk Score" in headers
        assert "Risk Level" in headers

    def test_export_csv_rows(
        self,
        detail_service: SummaryDetailService,
        mock_summary: MagicMock,
        mock_events: list[MagicMock],
    ) -> None:
        """Test CSV export includes all event rows."""
        result = detail_service.export_csv(mock_summary, mock_events)

        reader = csv.reader(io.StringIO(result))
        rows = list(reader)

        # Header + 3 event rows
        assert len(rows) == 4

        # Check first data row
        assert rows[1][0] == "101"  # Event ID
        assert "Front Door" in rows[1][2]  # Camera

    def test_export_csv_no_events(
        self,
        detail_service: SummaryDetailService,
        mock_summary: MagicMock,
    ) -> None:
        """Test CSV export with no events."""
        result = detail_service.export_csv(mock_summary, [])

        reader = csv.reader(io.StringIO(result))
        rows = list(reader)

        # Only header row
        assert len(rows) == 1

    def test_export_csv_escapes_special_characters(
        self,
        detail_service: SummaryDetailService,
        mock_summary: MagicMock,
    ) -> None:
        """Test CSV properly escapes special characters."""
        event = MagicMock()
        event.id = 1
        event.started_at = datetime(2026, 1, 21, 14, 0, tzinfo=UTC)
        event.camera = MagicMock()
        event.camera.name = "Camera, with comma"
        event.summary = 'Summary with "quotes"'
        event.risk_score = 50
        event.risk_level = "medium"

        result = detail_service.export_csv(mock_summary, [event])

        # Should be parseable
        reader = csv.reader(io.StringIO(result))
        rows = list(reader)
        assert len(rows) == 2
        assert "Camera, with comma" in rows[1][2]


class TestExportPDF:
    """Tests for PDF export functionality."""

    def test_export_pdf_returns_bytes(
        self,
        detail_service: SummaryDetailService,
        mock_summary: MagicMock,
        mock_events: list[MagicMock],
    ) -> None:
        """Test PDF export returns bytes."""
        result = detail_service.export_pdf(mock_summary, mock_events)

        assert isinstance(result, bytes)
        # PDF magic bytes
        assert result.startswith(b"%PDF") or len(result) > 0

    def test_export_pdf_no_events(
        self,
        detail_service: SummaryDetailService,
        mock_summary: MagicMock,
    ) -> None:
        """Test PDF export with no events."""
        result = detail_service.export_pdf(mock_summary, [])

        assert isinstance(result, bytes)


class TestExportFormat:
    """Tests for ExportFormat enum."""

    def test_export_format_values(self) -> None:
        """Test ExportFormat enum has expected values."""
        assert ExportFormat.JSON.value == "json"
        assert ExportFormat.CSV.value == "csv"
        assert ExportFormat.PDF.value == "pdf"

    def test_export_format_from_string(self) -> None:
        """Test creating ExportFormat from string."""
        assert ExportFormat("json") == ExportFormat.JSON
        assert ExportFormat("csv") == ExportFormat.CSV
        assert ExportFormat("pdf") == ExportFormat.PDF

    def test_export_format_invalid(self) -> None:
        """Test invalid format raises ValueError."""
        with pytest.raises(ValueError):
            ExportFormat("xml")


# Tests: Full Detail Generation


class TestGenerateDetail:
    """Tests for full detail generation."""

    def test_generate_detail_structure(
        self,
        detail_service: SummaryDetailService,
        mock_summary: MagicMock,
        mock_events: list[MagicMock],
    ) -> None:
        """Test generate_detail returns correct structure."""
        result = detail_service.generate_detail(mock_summary, mock_events)

        assert result.id == mock_summary.id
        assert result.summary_type == "hourly"
        assert result.content == mock_summary.content
        assert result.event_count == 3
        assert len(result.timeline) == 3
        assert result.export_formats == ["json", "csv", "pdf"]

    def test_generate_detail_includes_structured_data(
        self,
        detail_service: SummaryDetailService,
        mock_summary: MagicMock,
        mock_events: list[MagicMock],
    ) -> None:
        """Test generate_detail includes structured summary data."""
        result = detail_service.generate_detail(mock_summary, mock_events)

        assert result.window_start is not None
        assert result.window_end is not None
        assert result.generated_at is not None

    def test_generate_detail_no_events(
        self,
        detail_service: SummaryDetailService,
        mock_summary: MagicMock,
    ) -> None:
        """Test generate_detail with no events."""
        mock_summary.event_count = 0
        mock_summary.event_ids = None

        result = detail_service.generate_detail(mock_summary, [])

        assert result.event_count == 0
        assert result.timeline == []
        assert result.export_formats is not None


# Tests: Edge Cases


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_timeline_event_to_dict(
        self,
        detail_service: SummaryDetailService,
        mock_events: list[MagicMock],
    ) -> None:
        """Test TimelineEvent to_dict method."""
        timeline = detail_service.build_timeline(mock_events)
        event_dict = timeline[0].to_dict()

        assert isinstance(event_dict, dict)
        assert "event_id" in event_dict
        assert "timestamp" in event_dict
        assert "camera_name" in event_dict

    def test_event_with_none_values(
        self,
        detail_service: SummaryDetailService,
    ) -> None:
        """Test handling events with None values."""
        event = MagicMock()
        event.id = 1
        event.started_at = datetime(2026, 1, 21, 14, 0, tzinfo=UTC)
        event.camera = MagicMock()
        event.camera.name = "Camera"
        event.summary = None  # No summary
        event.risk_score = None  # No risk score
        event.risk_level = None  # No risk level

        timeline = detail_service.build_timeline([event])

        assert len(timeline) == 1
        assert timeline[0].summary is None or timeline[0].summary == ""
        assert timeline[0].risk_score is None

    def test_export_handles_unicode(
        self,
        detail_service: SummaryDetailService,
        mock_summary: MagicMock,
    ) -> None:
        """Test export handles unicode characters."""
        event = MagicMock()
        event.id = 1
        event.started_at = datetime(2026, 1, 21, 14, 0, tzinfo=UTC)
        event.camera = MagicMock()
        event.camera.name = "Camera"
        event.summary = "Summary with unicode: \u4e2d\u6587 \ud83d\ude00"
        event.risk_score = 50
        event.risk_level = "medium"

        # JSON export
        json_result = detail_service.export_json(mock_summary, [event])
        data = json.loads(json_result)
        assert "\u4e2d\u6587" in data["events"][0]["summary"]

        # CSV export
        csv_result = detail_service.export_csv(mock_summary, [event])
        assert "\u4e2d\u6587" in csv_result
