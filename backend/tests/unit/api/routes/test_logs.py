"""Unit tests for logs API routes.

Tests cover:
- Single log entry ingestion via POST /api/logs/frontend
- Batch log ingestion via POST /api/logs/frontend/batch
- Log level validation
- Context data handling
- Error handling scenarios
- Log query via GET /api/logs
- Log statistics via GET /api/logs/stats
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.api.routes.logs import (
    _LOG_LEVEL_MAP,
    _log_frontend_entry,
    ingest_frontend_log,
    ingest_frontend_logs_batch,
    router,
)
from backend.api.schemas.logs import (
    FrontendLogBatchRequest,
    FrontendLogEntry,
    FrontendLogLevel,
    FrontendLogResponse,
    LogEntryResponse,
    LogStats,
)
from backend.core.database import get_db


class TestLogLevelMapping:
    """Tests for log level mapping."""

    def test_log_level_map_has_all_levels(self):
        """Test that log level map contains all expected levels."""
        import logging

        assert _LOG_LEVEL_MAP["DEBUG"] == logging.DEBUG
        assert _LOG_LEVEL_MAP["INFO"] == logging.INFO
        assert _LOG_LEVEL_MAP["WARNING"] == logging.WARNING
        assert _LOG_LEVEL_MAP["ERROR"] == logging.ERROR
        assert _LOG_LEVEL_MAP["CRITICAL"] == logging.CRITICAL


class TestLogFrontendEntryHelper:
    """Tests for _log_frontend_entry helper function."""

    def test_log_entry_with_minimal_fields(self):
        """Test logging entry with only required fields."""
        entry = FrontendLogEntry(
            level=FrontendLogLevel.INFO,
            message="Test message",
        )

        with patch("backend.api.routes.logs.frontend_logger") as mock_logger:
            result = _log_frontend_entry(entry)

            assert result is True
            mock_logger.log.assert_called_once()
            call_args = mock_logger.log.call_args
            assert call_args[0][0] == 20  # logging.INFO
            assert "Test message" in call_args[0][1]

    def test_log_entry_with_all_fields(self):
        """Test logging entry with all fields populated."""
        entry = FrontendLogEntry(
            level=FrontendLogLevel.ERROR,
            message="Full test message",
            timestamp=datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC),
            component="TestComponent",
            context={"key1": "value1", "key2": 123},
            url="https://example.com/test",
            user_agent="TestBrowser/1.0",
        )

        with patch("backend.api.routes.logs.frontend_logger") as mock_logger:
            result = _log_frontend_entry(entry)

            assert result is True
            mock_logger.log.assert_called_once()
            call_args = mock_logger.log.call_args
            assert call_args[0][0] == 40  # logging.ERROR
            assert "TestComponent" in call_args[0][1]
            assert "Full test message" in call_args[0][1]

    def test_log_entry_extracts_context_fields(self):
        """Test that context fields are extracted and prefixed."""
        entry = FrontendLogEntry(
            level=FrontendLogLevel.INFO,
            message="Test",
            context={"action": "click", "element": "button"},
        )

        with patch("backend.api.routes.logs.frontend_logger") as mock_logger:
            _log_frontend_entry(entry)

            call_args = mock_logger.log.call_args
            extra = call_args[1]["extra"]
            assert "ctx_action" in extra
            assert "ctx_element" in extra

    def test_log_entry_handles_request_user_agent(self):
        """Test that user-agent from request is captured when not in entry."""
        entry = FrontendLogEntry(
            level=FrontendLogLevel.INFO,
            message="Test",
        )

        mock_request = MagicMock()
        mock_headers = MagicMock()
        mock_headers.get.return_value = "RequestBrowser/1.0"
        mock_request.headers = mock_headers

        with patch("backend.api.routes.logs.frontend_logger") as mock_logger:
            result = _log_frontend_entry(entry, mock_request)

            assert result is True
            mock_headers.get.assert_called_with("user-agent")
            # Verify user agent was captured in extra
            call_args = mock_logger.log.call_args
            extra = call_args[1]["extra"]
            assert extra["frontend_user_agent"] == "RequestBrowser/1.0"

    def test_log_entry_payload_user_agent_takes_precedence(self):
        """Test that entry user_agent takes precedence over header."""
        entry = FrontendLogEntry(
            level=FrontendLogLevel.INFO,
            message="Test",
            user_agent="PayloadBrowser/2.0",
        )

        mock_request = MagicMock(spec=Request)
        mock_request.headers.get.return_value = "HeaderBrowser/1.0"

        with patch("backend.api.routes.logs.frontend_logger") as mock_logger:
            _log_frontend_entry(entry, mock_request)

            call_args = mock_logger.log.call_args
            extra = call_args[1]["extra"]
            assert extra["frontend_user_agent"] == "PayloadBrowser/2.0"

    def test_log_entry_returns_false_on_exception(self):
        """Test that logging errors return False without raising."""
        entry = FrontendLogEntry(
            level=FrontendLogLevel.INFO,
            message="Test",
        )

        with (
            patch("backend.api.routes.logs.frontend_logger") as mock_logger,
            patch("backend.api.routes.logs.logger") as mock_route_logger,
        ):
            mock_logger.log.side_effect = Exception("Logging failed")

            result = _log_frontend_entry(entry)

            assert result is False
            mock_route_logger.warning.assert_called_once()


class TestIngestFrontendLog:
    """Tests for ingest_frontend_log endpoint."""

    @pytest.mark.asyncio
    async def test_ingest_single_log_success(self):
        """Test successful single log ingestion."""
        entry = FrontendLogEntry(
            level=FrontendLogLevel.INFO,
            message="Test message",
        )
        mock_request = MagicMock(spec=Request)
        mock_request.headers.get.return_value = None

        with patch("backend.api.routes.logs._log_frontend_entry", return_value=True):
            response = await ingest_frontend_log(entry, mock_request)

            assert isinstance(response, FrontendLogResponse)
            assert response.success is True
            assert response.count == 1
            assert "Successfully ingested 1 log entry" in response.message

    @pytest.mark.asyncio
    async def test_ingest_single_log_failure(self):
        """Test single log ingestion when logging fails."""
        entry = FrontendLogEntry(
            level=FrontendLogLevel.ERROR,
            message="Test error",
        )
        mock_request = MagicMock(spec=Request)

        with patch("backend.api.routes.logs._log_frontend_entry", return_value=False):
            response = await ingest_frontend_log(entry, mock_request)

            assert response.success is False
            assert response.count == 0
            assert "Failed to ingest" in response.message


class TestIngestFrontendLogsBatch:
    """Tests for ingest_frontend_logs_batch endpoint."""

    @pytest.mark.asyncio
    async def test_ingest_batch_all_success(self):
        """Test successful batch log ingestion."""
        batch = FrontendLogBatchRequest(
            entries=[
                FrontendLogEntry(level=FrontendLogLevel.INFO, message="Entry 1"),
                FrontendLogEntry(level=FrontendLogLevel.WARNING, message="Entry 2"),
                FrontendLogEntry(level=FrontendLogLevel.ERROR, message="Entry 3"),
            ]
        )
        mock_request = MagicMock(spec=Request)

        with patch("backend.api.routes.logs._log_frontend_entry", return_value=True):
            response = await ingest_frontend_logs_batch(batch, mock_request)

            assert response.success is True
            assert response.count == 3
            assert "Successfully ingested 3 log entry" in response.message

    @pytest.mark.asyncio
    async def test_ingest_batch_partial_success(self):
        """Test batch ingestion with partial failures."""
        batch = FrontendLogBatchRequest(
            entries=[
                FrontendLogEntry(level=FrontendLogLevel.INFO, message="Entry 1"),
                FrontendLogEntry(level=FrontendLogLevel.WARNING, message="Entry 2"),
                FrontendLogEntry(level=FrontendLogLevel.ERROR, message="Entry 3"),
            ]
        )
        mock_request = MagicMock(spec=Request)

        # First and third succeed, second fails
        with (
            patch(
                "backend.api.routes.logs._log_frontend_entry",
                side_effect=[True, False, True],
            ),
            patch("backend.api.routes.logs.logger"),
        ):
            response = await ingest_frontend_logs_batch(batch, mock_request)

            assert response.success is True
            assert response.count == 2

    @pytest.mark.asyncio
    async def test_ingest_batch_all_fail(self):
        """Test batch ingestion when all entries fail."""
        batch = FrontendLogBatchRequest(
            entries=[
                FrontendLogEntry(level=FrontendLogLevel.INFO, message="Entry 1"),
                FrontendLogEntry(level=FrontendLogLevel.WARNING, message="Entry 2"),
            ]
        )
        mock_request = MagicMock(spec=Request)

        with (
            patch("backend.api.routes.logs._log_frontend_entry", return_value=False),
            patch("backend.api.routes.logs.logger"),
        ):
            response = await ingest_frontend_logs_batch(batch, mock_request)

            assert response.success is False
            assert response.count == 0
            assert "No log entries were ingested" in response.message


class TestFrontendLogSchemas:
    """Tests for frontend log schemas."""

    def test_log_entry_with_alias_extra(self):
        """Test that 'extra' field alias works for context."""
        entry = FrontendLogEntry(
            level=FrontendLogLevel.INFO,
            message="Test",
            extra={"key": "value"},
        )
        assert entry.context == {"key": "value"}

    def test_log_entry_rejects_empty_message(self):
        """Test that empty messages are rejected."""
        with pytest.raises(ValueError):
            FrontendLogEntry(
                level=FrontendLogLevel.INFO,
                message="",
            )

    def test_log_entry_rejects_too_long_message(self):
        """Test that overly long messages are rejected."""
        with pytest.raises(ValueError):
            FrontendLogEntry(
                level=FrontendLogLevel.INFO,
                message="A" * 10001,
            )

    def test_batch_request_rejects_empty_entries(self):
        """Test that empty entries list is rejected."""
        with pytest.raises(ValueError):
            FrontendLogBatchRequest(entries=[])

    def test_batch_request_rejects_too_many_entries(self):
        """Test that too many entries are rejected."""
        with pytest.raises(ValueError):
            entries = [
                FrontendLogEntry(level=FrontendLogLevel.INFO, message=f"Entry {i}")
                for i in range(101)
            ]
            FrontendLogBatchRequest(entries=entries)

    def test_response_model_serialization(self):
        """Test that response model serializes correctly."""
        response = FrontendLogResponse(
            success=True,
            count=5,
            message="Test message",
        )
        data = response.model_dump()
        assert data["success"] is True
        assert data["count"] == 5
        assert data["message"] == "Test message"


# =============================================================================
# Fixtures for Log Query Tests
# =============================================================================


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def client(mock_db_session: AsyncMock) -> TestClient:
    """Create a test client with mocked dependencies."""
    app = FastAPI()
    app.include_router(router)

    async def override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client


# =============================================================================
# GET /api/logs Tests
# =============================================================================


class TestListLogs:
    """Tests for GET /api/logs endpoint."""

    def test_list_logs_returns_expected_structure(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that list logs returns expected response structure."""
        # Mock empty result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        response = client.get("/api/logs")

        assert response.status_code == 200
        data = response.json()

        # Verify expected fields
        assert "items" in data
        assert "pagination" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["pagination"], dict)
        assert "total" in data["pagination"]
        assert "limit" in data["pagination"]
        assert "has_more" in data["pagination"]

    def test_list_logs_with_level_filter(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test filtering logs by level."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        response = client.get("/api/logs?level=ERROR")

        assert response.status_code == 200

    def test_list_logs_with_component_filter(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test filtering logs by component."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        response = client.get("/api/logs?component=backend")

        assert response.status_code == 200

    def test_list_logs_with_source_filter(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test filtering logs by source."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        response = client.get("/api/logs?source=backend")

        assert response.status_code == 200

    def test_list_logs_with_date_range_filter(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test filtering logs by date range."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        response = client.get(
            "/api/logs?start_date=2026-01-01T00:00:00Z&end_date=2026-01-31T23:59:59Z"
        )

        assert response.status_code == 200

    def test_list_logs_invalid_date_range(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that invalid date range returns 400."""
        response = client.get(
            "/api/logs?start_date=2026-01-31T00:00:00Z&end_date=2026-01-01T23:59:59Z"
        )

        assert response.status_code == 400
        assert "start_date cannot be after end_date" in response.json()["detail"]

    def test_list_logs_with_limit(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test pagination limit parameter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        response = client.get("/api/logs?limit=50")

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["limit"] == 50

    def test_list_logs_with_include_total_count(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test including total count in response."""
        # Mock count result
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 150

        # Mock logs result
        mock_logs_result = MagicMock()
        mock_logs_result.scalars.return_value.all.return_value = []

        mock_db_session.execute.side_effect = [mock_count_result, mock_logs_result]

        response = client.get("/api/logs?include_total_count=true")

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total"] == 150

    def test_list_logs_returns_log_entries(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that log entries are returned correctly."""
        # Create a mock log entry
        mock_log = MagicMock()
        mock_log.id = 12345
        mock_log.timestamp = datetime(2026, 1, 15, 10, 30, 0, tzinfo=UTC)
        mock_log.level = "ERROR"
        mock_log.component = "backend.services.detector"
        mock_log.message = "Detection failed"
        mock_log.camera_id = "front_door"
        mock_log.event_id = None
        mock_log.request_id = "req-abc123"
        mock_log.detection_id = None
        mock_log.duration_ms = None
        mock_log.extra = None
        mock_log.source = "backend"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_log]
        mock_db_session.execute.return_value = mock_result

        response = client.get("/api/logs")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == 12345
        assert data["items"][0]["level"] == "ERROR"
        assert data["items"][0]["component"] == "backend.services.detector"
        assert data["items"][0]["message"] == "Detection failed"
        assert data["items"][0]["camera_id"] == "front_door"
        assert data["items"][0]["source"] == "backend"

    def test_list_logs_has_more_pagination(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test has_more is True when there are more results."""
        # Create mock logs (return limit+1 to indicate more results)
        mock_logs = []
        for i in range(101):  # Default limit is 100, so 101 indicates more
            mock_log = MagicMock()
            mock_log.id = i + 1
            mock_log.timestamp = datetime(2026, 1, 15, 10, 30, i, tzinfo=UTC)
            mock_log.level = "INFO"
            mock_log.component = "test"
            mock_log.message = f"Log {i}"
            mock_log.camera_id = None
            mock_log.event_id = None
            mock_log.request_id = None
            mock_log.detection_id = None
            mock_log.duration_ms = None
            mock_log.extra = None
            mock_log.source = "backend"
            mock_logs.append(mock_log)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_logs
        mock_db_session.execute.return_value = mock_result

        response = client.get("/api/logs")

        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["has_more"] is True
        assert data["pagination"]["next_cursor"] is not None
        # Should trim to limit
        assert len(data["items"]) == 100


# =============================================================================
# GET /api/logs/stats Tests
# =============================================================================


class TestGetLogStats:
    """Tests for GET /api/logs/stats endpoint."""

    def test_log_stats_returns_expected_structure(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that log stats returns all expected fields."""
        # Mock UNION ALL result (category, key, count) tuples
        union_result = MagicMock()
        union_result.fetchall.return_value = [
            ("total", "all", 1500),
            ("errors", "all", 15),
            ("warnings", "all", 42),
            ("component", "backend.services.detector", 350),
            ("component", "backend.api.routes.events", 280),
        ]

        mock_db_session.execute.return_value = union_result

        response = client.get("/api/logs/stats")

        assert response.status_code == 200
        data = response.json()

        # Verify all expected fields are present
        assert "errors_today" in data
        assert "warnings_today" in data
        assert "total_today" in data
        assert "top_component" in data
        assert "by_component" in data

        # Verify data types
        assert isinstance(data["errors_today"], int)
        assert isinstance(data["warnings_today"], int)
        assert isinstance(data["total_today"], int)
        assert isinstance(data["by_component"], dict)

    def test_log_stats_values_correctly_aggregated(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that aggregated values are correctly parsed and returned."""
        # Mock UNION ALL result (category, key, count) tuples
        union_result = MagicMock()
        union_result.fetchall.return_value = [
            ("total", "all", 1500),
            ("errors", "all", 15),
            ("warnings", "all", 42),
            ("component", "backend.services.detector", 350),
            ("component", "backend.api.routes.events", 280),
            ("component", "frontend", 200),
        ]

        mock_db_session.execute.return_value = union_result

        response = client.get("/api/logs/stats")

        assert response.status_code == 200
        data = response.json()

        # Verify counts
        assert data["total_today"] == 1500
        assert data["errors_today"] == 15
        assert data["warnings_today"] == 42

        # Verify by_component breakdown
        assert data["by_component"]["backend.services.detector"] == 350
        assert data["by_component"]["backend.api.routes.events"] == 280
        assert data["by_component"]["frontend"] == 200

        # Verify top_component
        assert data["top_component"] == "backend.services.detector"

    def test_log_stats_empty_database(self, client: TestClient, mock_db_session: AsyncMock) -> None:
        """Test log stats with no logs in database."""
        # Mock empty result
        union_result = MagicMock()
        union_result.fetchall.return_value = [
            ("total", "all", 0),
            ("errors", "all", 0),
            ("warnings", "all", 0),
        ]

        mock_db_session.execute.return_value = union_result

        response = client.get("/api/logs/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_today"] == 0
        assert data["errors_today"] == 0
        assert data["warnings_today"] == 0
        assert data["top_component"] is None
        assert data["by_component"] == {}

    def test_log_stats_one_query_execution(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that the endpoint uses only 1 database query.

        The optimized endpoint should make only 1 query using UNION ALL.
        """
        union_result = MagicMock()
        union_result.fetchall.return_value = [
            ("total", "all", 100),
            ("errors", "all", 5),
            ("warnings", "all", 10),
        ]

        mock_db_session.execute.return_value = union_result

        response = client.get("/api/logs/stats")

        assert response.status_code == 200
        # Verify only 1 query was executed
        assert mock_db_session.execute.call_count == 1

    def test_log_stats_backwards_compatible_response(
        self, client: TestClient, mock_db_session: AsyncMock
    ) -> None:
        """Test that response matches LogStats schema for backwards compatibility."""
        union_result = MagicMock()
        union_result.fetchall.return_value = [
            ("total", "all", 1500),
            ("errors", "all", 15),
            ("warnings", "all", 42),
            ("component", "backend", 500),
        ]

        mock_db_session.execute.return_value = union_result

        response = client.get("/api/logs/stats")

        assert response.status_code == 200
        data = response.json()

        # Validate against expected schema structure
        validated = LogStats(**data)
        assert validated.total_today == 1500
        assert validated.errors_today == 15
        assert validated.warnings_today == 42
        assert validated.by_component == {"backend": 500}
        assert validated.top_component == "backend"


# =============================================================================
# Log Entry Response Schema Tests
# =============================================================================


class TestLogEntryResponseSchema:
    """Tests for LogEntryResponse schema."""

    def test_log_entry_response_from_attributes(self):
        """Test that LogEntryResponse can be created from ORM model."""
        mock_log = MagicMock()
        mock_log.id = 1
        mock_log.timestamp = datetime(2026, 1, 15, 10, 30, 0, tzinfo=UTC)
        mock_log.level = "INFO"
        mock_log.component = "test"
        mock_log.message = "Test message"
        mock_log.camera_id = None
        mock_log.event_id = None
        mock_log.request_id = None
        mock_log.detection_id = None
        mock_log.duration_ms = None
        mock_log.extra = None
        mock_log.source = "backend"

        # This should not raise
        entry = LogEntryResponse.model_validate(mock_log)
        assert entry.id == 1
        assert entry.level == "INFO"
        assert entry.message == "Test message"

    def test_log_entry_response_with_all_fields(self):
        """Test LogEntryResponse with all optional fields populated."""
        entry = LogEntryResponse(
            id=1,
            timestamp=datetime(2026, 1, 15, 10, 30, 0, tzinfo=UTC),
            level="ERROR",
            component="backend.services.detector",
            message="Detection failed",
            camera_id="front_door",
            event_id=123,
            request_id="req-abc",
            detection_id=456,
            duration_ms=5000,
            extra={"key": "value"},
            source="backend",
        )

        data = entry.model_dump()
        assert data["id"] == 1
        assert data["level"] == "ERROR"
        assert data["camera_id"] == "front_door"
        assert data["event_id"] == 123
        assert data["duration_ms"] == 5000
        assert data["extra"] == {"key": "value"}


class TestLogStatsSchema:
    """Tests for LogStats schema."""

    def test_log_stats_with_defaults(self):
        """Test LogStats with minimal fields."""
        stats = LogStats(
            errors_today=0,
            warnings_today=0,
            total_today=0,
        )
        assert stats.top_component is None
        assert stats.by_component == {}

    def test_log_stats_with_all_fields(self):
        """Test LogStats with all fields populated."""
        stats = LogStats(
            errors_today=15,
            warnings_today=42,
            total_today=1500,
            top_component="backend",
            by_component={"backend": 500, "frontend": 200},
        )
        data = stats.model_dump()
        assert data["errors_today"] == 15
        assert data["warnings_today"] == 42
        assert data["total_today"] == 1500
        assert data["top_component"] == "backend"
        assert data["by_component"] == {"backend": 500, "frontend": 200}
