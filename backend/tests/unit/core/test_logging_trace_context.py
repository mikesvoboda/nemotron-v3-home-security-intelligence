"""Unit tests for trace context injection in structured logging.

NEM-1638: Tests for enhanced structured logging with trace context and log aggregation.

This module tests:
1. Trace context (trace_id, span_id) injection into log records
2. OpenTelemetry trace context extraction
3. Correlation ID to trace context mapping
4. Log aggregation-friendly structured output

Tests follow TDD methodology - written before implementation.
"""

import json
import logging
from unittest.mock import MagicMock, patch

import pytest

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


class TestTraceContextInLogs:
    """Test trace context injection into log records."""

    def test_context_filter_adds_trace_id_when_otel_enabled(self):
        """Test that ContextFilter adds trace_id from active OpenTelemetry span."""
        from backend.core.logging import ContextFilter

        # Mock OpenTelemetry span context
        mock_span = MagicMock()
        mock_span.get_span_context.return_value.trace_id = 0x1234567890ABCDEF1234567890ABCDEF
        mock_span.get_span_context.return_value.span_id = 0xFEDCBA0987654321
        mock_span.get_span_context.return_value.is_valid = True

        with patch("backend.core.logging.get_current_trace_context") as mock_get_trace:
            mock_get_trace.return_value = {
                "trace_id": "1234567890abcdef1234567890abcdef",
                "span_id": "fedcba0987654321",
            }

            filter_obj = ContextFilter()
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="test message",
                args=(),
                exc_info=None,
            )

            result = filter_obj.filter(record)

            assert result is True
            assert hasattr(record, "trace_id")
            assert record.trace_id == "1234567890abcdef1234567890abcdef"
            assert hasattr(record, "span_id")
            assert record.span_id == "fedcba0987654321"

    def test_context_filter_no_trace_when_otel_disabled(self):
        """Test that ContextFilter sets None trace_id when OpenTelemetry is disabled."""
        from backend.core.logging import ContextFilter

        with patch("backend.core.logging.get_current_trace_context") as mock_get_trace:
            mock_get_trace.return_value = {"trace_id": None, "span_id": None}

            filter_obj = ContextFilter()
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="test message",
                args=(),
                exc_info=None,
            )

            result = filter_obj.filter(record)

            assert result is True
            assert hasattr(record, "trace_id")
            assert record.trace_id is None
            assert hasattr(record, "span_id")
            assert record.span_id is None

    def test_context_filter_preserves_explicit_trace_id(self):
        """Test that explicit trace_id in extra= takes precedence."""
        from backend.core.logging import ContextFilter

        with patch("backend.core.logging.get_current_trace_context") as mock_get_trace:
            mock_get_trace.return_value = {
                "trace_id": "context-trace-id",
                "span_id": "context-span-id",
            }

            filter_obj = ContextFilter()
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="test message",
                args=(),
                exc_info=None,
            )
            # Pre-set trace_id (as if passed via extra=)
            record.trace_id = "explicit-trace-id"

            result = filter_obj.filter(record)

            assert result is True
            # Explicit value should be preserved
            assert record.trace_id == "explicit-trace-id"


class TestCustomJsonFormatterTraceContext:
    """Test CustomJsonFormatter includes trace context in JSON output."""

    def test_formatter_includes_trace_id_when_present(self):
        """Test that JSON formatter includes trace_id in output."""
        from backend.core.logging import CustomJsonFormatter

        formatter = CustomJsonFormatter()
        record = logging.LogRecord(
            name="test.component",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )
        record.trace_id = "abc123def456"
        record.span_id = "789xyz"

        formatted = formatter.format(record)

        assert "abc123def456" in formatted  # pragma: allowlist secret
        assert "789xyz" in formatted
        # Verify it's valid JSON
        parsed = json.loads(formatted)
        assert parsed["trace_id"] == "abc123def456"
        assert parsed["span_id"] == "789xyz"

    def test_formatter_excludes_none_trace_id(self):
        """Test that JSON formatter excludes trace_id when None."""
        from backend.core.logging import CustomJsonFormatter

        formatter = CustomJsonFormatter()
        record = logging.LogRecord(
            name="test.component",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )
        record.trace_id = None
        record.span_id = None

        formatted = formatter.format(record)

        # Verify it's valid JSON
        parsed = json.loads(formatted)
        # None values should not be included (or should be null)
        assert "trace_id" not in parsed or parsed.get("trace_id") is None
        assert "span_id" not in parsed or parsed.get("span_id") is None

    def test_formatter_includes_correlation_id(self):
        """Test that JSON formatter includes correlation_id for log aggregation."""
        from backend.core.logging import CustomJsonFormatter

        formatter = CustomJsonFormatter()
        record = logging.LogRecord(
            name="test.component",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )
        record.correlation_id = "corr-123-456"
        record.request_id = "req-abc"

        formatted = formatter.format(record)
        parsed = json.loads(formatted)

        assert parsed["correlation_id"] == "corr-123-456"
        assert parsed["request_id"] == "req-abc"


class TestGetCurrentTraceContext:
    """Test the get_current_trace_context helper function."""

    def test_returns_trace_context_when_otel_active(self):
        """Test that function returns trace context from active span."""
        from backend.core.logging import get_current_trace_context

        # Mock OpenTelemetry trace module
        mock_span_context = MagicMock()
        mock_span_context.trace_id = 0x1234567890ABCDEF1234567890ABCDEF
        mock_span_context.span_id = 0xFEDCBA0987654321
        mock_span_context.is_valid = True

        mock_span = MagicMock()
        mock_span.get_span_context.return_value = mock_span_context

        with patch("backend.core.logging._get_otel_current_span", return_value=mock_span):
            result = get_current_trace_context()

        assert result["trace_id"] == "1234567890abcdef1234567890abcdef"
        assert result["span_id"] == "fedcba0987654321"

    def test_returns_none_when_otel_not_available(self):
        """Test that function returns None values when OpenTelemetry unavailable."""
        from backend.core.logging import get_current_trace_context

        with patch("backend.core.logging._get_otel_current_span", return_value=None):
            result = get_current_trace_context()

        assert result["trace_id"] is None
        assert result["span_id"] is None

    def test_returns_none_when_span_invalid(self):
        """Test that function returns None when span context is invalid."""
        from backend.core.logging import get_current_trace_context

        mock_span_context = MagicMock()
        mock_span_context.is_valid = False

        mock_span = MagicMock()
        mock_span.get_span_context.return_value = mock_span_context

        with patch("backend.core.logging._get_otel_current_span", return_value=mock_span):
            result = get_current_trace_context()

        assert result["trace_id"] is None
        assert result["span_id"] is None

    def test_handles_otel_import_error(self):
        """Test graceful handling when OpenTelemetry is not installed."""
        from backend.core.logging import get_current_trace_context

        with patch(
            "backend.core.logging._get_otel_current_span",
            side_effect=ImportError("No module named 'opentelemetry'"),
        ):
            result = get_current_trace_context()

        assert result["trace_id"] is None
        assert result["span_id"] is None


class TestLogAggregationFields:
    """Test log fields required for log aggregation (Loki, ELK)."""

    def test_formatter_includes_service_name(self):
        """Test that logs include service name for aggregation filtering."""
        from backend.core.logging import CustomJsonFormatter

        formatter = CustomJsonFormatter()
        record = logging.LogRecord(
            name="backend.services.detector",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Detection completed",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)
        parsed = json.loads(formatted)

        # Should include service/component name
        assert "component" in parsed
        assert parsed["component"] == "backend.services.detector"

    def test_formatter_includes_timestamp_iso8601(self):
        """Test that timestamp is ISO 8601 format for log aggregation."""
        from backend.core.logging import CustomJsonFormatter

        formatter = CustomJsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)
        parsed = json.loads(formatted)

        # Should include ISO 8601 timestamp
        assert "timestamp" in parsed
        # ISO 8601 format includes 'T' separator and timezone
        assert "T" in parsed["timestamp"]

    def test_formatter_includes_log_level(self):
        """Test that log level is included for filtering."""
        from backend.core.logging import CustomJsonFormatter

        formatter = CustomJsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="warning message",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)
        parsed = json.loads(formatted)

        assert "level" in parsed
        assert parsed["level"] == "WARNING"

    def test_formatter_includes_structured_context_fields(self):
        """Test that structured context fields are included."""
        from backend.core.logging import CustomJsonFormatter

        formatter = CustomJsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Processing camera",
            args=(),
            exc_info=None,
        )
        # Add structured context
        record.camera_id = "front_door"
        record.event_id = 123
        record.detection_count = 5

        formatted = formatter.format(record)
        parsed = json.loads(formatted)

        assert parsed.get("camera_id") == "front_door"
        assert parsed.get("event_id") == 123
        assert parsed.get("detection_count") == 5


class TestCorrelationIdIntegration:
    """Test integration between correlation_id and trace context."""

    @pytest.fixture(autouse=True)
    def setup_context(self):
        """Setup and cleanup context variables."""
        from backend.api.middleware.request_id import set_correlation_id
        from backend.core.logging import set_request_id

        yield

        # Cleanup
        set_correlation_id(None)
        set_request_id(None)

    def test_context_filter_adds_correlation_id(self):
        """Test that ContextFilter adds correlation_id from context."""
        from backend.api.middleware.request_id import set_correlation_id
        from backend.core.logging import ContextFilter

        set_correlation_id("test-correlation-uuid")

        filter_obj = ContextFilter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="test message",
            args=(),
            exc_info=None,
        )

        with patch("backend.core.logging.get_current_trace_context") as mock_get_trace:
            mock_get_trace.return_value = {"trace_id": None, "span_id": None}
            result = filter_obj.filter(record)

        assert result is True
        assert hasattr(record, "correlation_id")
        assert record.correlation_id == "test-correlation-uuid"

    def test_both_trace_and_correlation_ids_present(self):
        """Test that both trace_id and correlation_id can coexist in logs."""
        from backend.api.middleware.request_id import set_correlation_id
        from backend.core.logging import ContextFilter, CustomJsonFormatter, set_request_id

        set_correlation_id("corr-uuid-12345")
        set_request_id("req-abc")

        with patch("backend.core.logging.get_current_trace_context") as mock_get_trace:
            mock_get_trace.return_value = {
                "trace_id": "trace-id-xyz",
                "span_id": "span-id-123",
            }

            filter_obj = ContextFilter()
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=0,
                msg="test message",
                args=(),
                exc_info=None,
            )

            filter_obj.filter(record)

        formatter = CustomJsonFormatter()
        formatted = formatter.format(record)
        parsed = json.loads(formatted)

        # Both should be present
        assert parsed.get("trace_id") == "trace-id-xyz"
        assert parsed.get("span_id") == "span-id-123"
        assert parsed.get("correlation_id") == "corr-uuid-12345"
        assert parsed.get("request_id") == "req-abc"
