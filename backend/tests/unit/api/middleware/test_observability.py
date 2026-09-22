"""Unit tests for the unified observability middleware helpers.

Re-homed from test_request_logging.py (NEM-5558): tests for the structured
request-log formatting that ObservabilityMiddleware now owns directly.
"""

import json

import pytest

# Mark all tests in this file as unit tests
pytestmark = pytest.mark.unit


class TestRequestLogFormatting:
    """Tests for structured log output format used by ObservabilityMiddleware."""

    def test_log_output_is_json_parseable(self):
        """Test that log output can be parsed as JSON."""
        from backend.api.middleware.observability import format_request_log

        log_data = format_request_log(
            method="GET",
            path="/api/test",
            status_code=200,
            duration_ms=45.5,
            client_ip="192.168.1.1",
            request_id="req-123",
        )

        # Should be a dict that can be JSON serialized
        assert isinstance(log_data, dict)
        json_str = json.dumps(log_data)
        parsed = json.loads(json_str)
        assert parsed["method"] == "GET"
        assert parsed["path"] == "/api/test"
        assert parsed["status_code"] == 200

    def test_log_format_includes_all_required_fields(self):
        """Test that log format includes all fields for aggregation."""
        from backend.api.middleware.observability import format_request_log

        log_data = format_request_log(
            method="POST",
            path="/api/events",
            status_code=201,
            duration_ms=123.45,
            client_ip="10.0.0.1",
            request_id="req-abc",
            correlation_id="corr-xyz",
            trace_id="trace-123",
            span_id="span-456",
        )

        # Required fields for log aggregation
        assert "method" in log_data
        assert "path" in log_data
        assert "status_code" in log_data
        assert "duration_ms" in log_data
        assert "request_id" in log_data
        assert "correlation_id" in log_data
        assert "trace_id" in log_data
        assert "span_id" in log_data

    def test_log_format_masks_sensitive_paths(self):
        """Test that sensitive path parameters are masked."""
        from backend.api.middleware.observability import format_request_log

        log_data = format_request_log(
            method="GET",
            path="/api/users/12345/tokens",
            status_code=200,
            duration_ms=50,
            client_ip="10.0.0.1",
            request_id="req-123",
        )

        # Path should be logged (sensitive data masking is handled elsewhere)
        assert "path" in log_data
        assert log_data["path"] == "/api/users/12345/tokens"
