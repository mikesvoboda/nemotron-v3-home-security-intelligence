"""Unit tests for frontend logs API routes.

Tests cover:
- Single log entry ingestion via POST /api/logs/frontend
- Batch log ingestion via POST /api/logs/frontend/batch
- Log level validation
- Context data handling
- Error handling scenarios
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi import Request

from backend.api.routes.logs import (
    _LOG_LEVEL_MAP,
    _log_frontend_entry,
    ingest_frontend_log,
    ingest_frontend_logs_batch,
)
from backend.api.schemas.logs import (
    FrontendLogBatchRequest,
    FrontendLogEntry,
    FrontendLogLevel,
    FrontendLogResponse,
)


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
