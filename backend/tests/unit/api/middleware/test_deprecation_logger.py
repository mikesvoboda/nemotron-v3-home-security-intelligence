"""Unit tests for deprecation logging middleware (NEM-2090).

This module provides comprehensive tests for:
- DeprecationLoggerMiddleware: Tracks calls to deprecated API endpoints
- Prometheus metrics for deprecation tracking
- Warning header addition to responses
- Client identification for migration progress tracking

Tests follow TDD approach and cover:
- Deprecated endpoint detection via Deprecation header
- Logging behavior with client info
- Prometheus counter increments
- Warning header formatting (RFC 7234)
- Non-deprecated endpoint passthrough
- Sunset date inclusion in warnings
"""

import logging
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient
from starlette.requests import Request

from backend.api.middleware.deprecation_logger import (
    DEPRECATED_CALLS_TOTAL,
    DeprecationLoggerMiddleware,
    record_deprecated_call,
)

# =============================================================================
# DeprecationLoggerMiddleware Tests
# =============================================================================


class TestDeprecationLoggerMiddleware:
    """Tests for DeprecationLoggerMiddleware class."""

    @pytest.fixture
    def app_with_deprecation_middleware(self):
        """Create a test FastAPI app with DeprecationLoggerMiddleware."""
        app = FastAPI()
        app.add_middleware(DeprecationLoggerMiddleware)

        @app.get("/test")
        async def test_endpoint():
            """Non-deprecated endpoint."""
            return {"message": "ok"}

        @app.get("/deprecated")
        async def deprecated_endpoint(response: Response):
            """Deprecated endpoint - sets Deprecation header."""
            response.headers["Deprecation"] = "true"
            return {"message": "deprecated"}

        @app.get("/deprecated-with-sunset")
        async def deprecated_with_sunset(response: Response):
            """Deprecated endpoint with sunset date."""
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = "2025-12-31"
            return {"message": "deprecated with sunset"}

        @app.post("/deprecated-post")
        async def deprecated_post(response: Response):
            """Deprecated POST endpoint."""
            response.headers["Deprecation"] = "true"
            return {"created": True}

        return app

    def test_non_deprecated_endpoint_passes_through(self, app_with_deprecation_middleware):
        """Test that non-deprecated endpoints pass through without modification."""
        client = TestClient(app_with_deprecation_middleware)
        response = client.get("/test")

        assert response.status_code == 200
        assert response.json() == {"message": "ok"}
        # No Warning header should be added
        assert "Warning" not in response.headers

    def test_deprecated_endpoint_adds_warning_header(self, app_with_deprecation_middleware):
        """Test that deprecated endpoints get Warning header added."""
        client = TestClient(app_with_deprecation_middleware)
        response = client.get("/deprecated")

        assert response.status_code == 200
        assert "Warning" in response.headers
        warning = response.headers["Warning"]
        assert "299" in warning
        assert "deprecated" in warning.lower()

    def test_warning_header_format_rfc_7234(self, app_with_deprecation_middleware):
        """Test that Warning header follows RFC 7234 format."""
        client = TestClient(app_with_deprecation_middleware)
        response = client.get("/deprecated")

        warning = response.headers["Warning"]
        # RFC 7234 format: warn-code warn-agent warn-text
        # Example: 299 - "This endpoint is deprecated."
        assert warning.startswith("299")
        assert '"' in warning  # Quoted text

    def test_sunset_date_included_in_warning(self, app_with_deprecation_middleware):
        """Test that Sunset header date is included in Warning message."""
        client = TestClient(app_with_deprecation_middleware)
        response = client.get("/deprecated-with-sunset")

        warning = response.headers["Warning"]
        assert "2025-12-31" in warning
        assert "removed" in warning.lower()

    def test_deprecated_post_endpoint(self, app_with_deprecation_middleware):
        """Test that POST endpoints also get deprecation handling."""
        client = TestClient(app_with_deprecation_middleware)
        response = client.post("/deprecated-post")

        assert response.status_code == 200
        assert "Warning" in response.headers

    def test_custom_warn_code(self):
        """Test that custom warning code can be configured."""
        app = FastAPI()
        app.add_middleware(DeprecationLoggerMiddleware, warn_code=110)

        @app.get("/deprecated")
        async def deprecated(response: Response):
            response.headers["Deprecation"] = "true"
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/deprecated")

        warning = response.headers["Warning"]
        assert warning.startswith("110")


class TestDeprecationLogging:
    """Tests for deprecation logging functionality."""

    @pytest.fixture
    def app_with_logging(self):
        """Create app for testing logging behavior."""
        app = FastAPI()
        app.add_middleware(DeprecationLoggerMiddleware)

        @app.get("/deprecated")
        async def deprecated(response: Response):
            response.headers["Deprecation"] = "true"
            return {"ok": True}

        return app

    def test_deprecated_call_is_logged(self, app_with_logging, caplog):
        """Test that deprecated calls are logged as warnings."""
        client = TestClient(app_with_logging)

        with caplog.at_level(logging.WARNING):
            response = client.get("/deprecated")

        assert response.status_code == 200

        # Check that a deprecation warning was logged
        deprecation_logs = [
            r for r in caplog.records
            if "deprecated" in r.message.lower() and r.levelno == logging.WARNING
        ]
        assert len(deprecation_logs) >= 1

    def test_log_includes_endpoint_path(self, app_with_logging, caplog):
        """Test that log includes the endpoint path."""
        client = TestClient(app_with_logging)

        with caplog.at_level(logging.WARNING):
            client.get("/deprecated")

        deprecation_logs = [
            r for r in caplog.records
            if "deprecated" in r.message.lower()
        ]
        assert len(deprecation_logs) >= 1
        assert "/deprecated" in deprecation_logs[0].message

    def test_log_includes_http_method(self, app_with_logging, caplog):
        """Test that log includes the HTTP method."""
        client = TestClient(app_with_logging)

        with caplog.at_level(logging.WARNING):
            client.get("/deprecated")

        deprecation_logs = [
            r for r in caplog.records
            if "deprecated" in r.message.lower()
        ]
        assert len(deprecation_logs) >= 1
        assert "GET" in deprecation_logs[0].message

    def test_log_includes_client_id_header(self, app_with_logging, caplog):
        """Test that log includes X-Client-ID if provided."""
        client = TestClient(app_with_logging)

        with caplog.at_level(logging.WARNING):
            client.get("/deprecated", headers={"X-Client-ID": "test-client-v2"})

        deprecation_logs = [
            r for r in caplog.records
            if "deprecated" in r.message.lower()
        ]
        assert len(deprecation_logs) >= 1
        # Check extra fields contain client_id
        assert hasattr(deprecation_logs[0], "client_id")
        assert deprecation_logs[0].client_id == "test-client-v2"

    def test_log_includes_user_agent(self, app_with_logging, caplog):
        """Test that log includes User-Agent header."""
        client = TestClient(app_with_logging)

        with caplog.at_level(logging.WARNING):
            client.get("/deprecated", headers={"User-Agent": "TestClient/1.0"})

        deprecation_logs = [
            r for r in caplog.records
            if "deprecated" in r.message.lower()
        ]
        assert len(deprecation_logs) >= 1
        assert hasattr(deprecation_logs[0], "user_agent")
        assert "TestClient" in deprecation_logs[0].user_agent

    def test_non_deprecated_endpoint_not_logged(self, caplog):
        """Test that non-deprecated endpoints are not logged as deprecated."""
        app = FastAPI()
        app.add_middleware(DeprecationLoggerMiddleware)

        @app.get("/normal")
        async def normal():
            return {"ok": True}

        client = TestClient(app)

        with caplog.at_level(logging.WARNING):
            response = client.get("/normal")

        assert response.status_code == 200
        deprecation_logs = [
            r for r in caplog.records
            if "deprecated" in r.message.lower()
        ]
        assert len(deprecation_logs) == 0


class TestDeprecationMetrics:
    """Tests for Prometheus metrics tracking."""

    @pytest.fixture
    def app_with_metrics(self):
        """Create app for testing metrics."""
        app = FastAPI()
        app.add_middleware(DeprecationLoggerMiddleware)

        @app.get("/deprecated")
        async def deprecated(response: Response):
            response.headers["Deprecation"] = "true"
            return {"ok": True}

        @app.get("/normal")
        async def normal():
            return {"ok": True}

        return app

    def test_deprecated_call_increments_counter(self, app_with_metrics):
        """Test that deprecated calls increment Prometheus counter."""
        client = TestClient(app_with_metrics)

        # Get counter value before
        before_value = DEPRECATED_CALLS_TOTAL.labels(
            endpoint="/deprecated",
            client_id="unknown",
        )._value.get()

        # Make deprecated call
        client.get("/deprecated")

        # Get counter value after
        after_value = DEPRECATED_CALLS_TOTAL.labels(
            endpoint="/deprecated",
            client_id="unknown",
        )._value.get()

        assert after_value > before_value

    def test_counter_includes_client_id_label(self, app_with_metrics):
        """Test that counter includes client_id label when provided."""
        client = TestClient(app_with_metrics)

        # Get counter value before
        before_value = DEPRECATED_CALLS_TOTAL.labels(
            endpoint="/deprecated",
            client_id="my-client",
        )._value.get()

        # Make deprecated call with client ID
        client.get("/deprecated", headers={"X-Client-ID": "my-client"})

        # Get counter value after
        after_value = DEPRECATED_CALLS_TOTAL.labels(
            endpoint="/deprecated",
            client_id="my-client",
        )._value.get()

        assert after_value == before_value + 1

    def test_non_deprecated_call_does_not_increment_counter(self, app_with_metrics):
        """Test that non-deprecated calls don't increment counter."""
        client = TestClient(app_with_metrics)

        # Get counter value before
        before_value = DEPRECATED_CALLS_TOTAL.labels(
            endpoint="/normal",
            client_id="unknown",
        )._value.get()

        # Make non-deprecated call
        client.get("/normal")

        # Get counter value after - should be same
        after_value = DEPRECATED_CALLS_TOTAL.labels(
            endpoint="/normal",
            client_id="unknown",
        )._value.get()

        assert after_value == before_value


class TestRecordDeprecatedCallHelper:
    """Tests for the record_deprecated_call helper function."""

    def test_records_call_with_defaults(self):
        """Test recording a deprecated call with default client_id."""
        before_value = DEPRECATED_CALLS_TOTAL.labels(
            endpoint="/v1/legacy",
            client_id="unknown",
        )._value.get()

        record_deprecated_call("/v1/legacy")

        after_value = DEPRECATED_CALLS_TOTAL.labels(
            endpoint="/v1/legacy",
            client_id="unknown",
        )._value.get()

        assert after_value == before_value + 1

    def test_records_call_with_client_id(self):
        """Test recording a deprecated call with specific client_id."""
        before_value = DEPRECATED_CALLS_TOTAL.labels(
            endpoint="/v1/old-api",
            client_id="client-xyz",
        )._value.get()

        record_deprecated_call("/v1/old-api", "client-xyz")

        after_value = DEPRECATED_CALLS_TOTAL.labels(
            endpoint="/v1/old-api",
            client_id="client-xyz",
        )._value.get()

        assert after_value == before_value + 1


class TestDeprecationMiddlewareEdgeCases:
    """Edge case tests for deprecation middleware."""

    def test_handles_empty_deprecation_header(self):
        """Test handling of empty Deprecation header value."""
        app = FastAPI()
        app.add_middleware(DeprecationLoggerMiddleware)

        @app.get("/test")
        async def test_endpoint(response: Response):
            response.headers["Deprecation"] = ""
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/test")

        # Empty string is falsy, so no Warning should be added
        assert response.status_code == 200
        assert "Warning" not in response.headers

    def test_handles_various_deprecation_header_values(self):
        """Test that various Deprecation header values are detected."""
        app = FastAPI()
        app.add_middleware(DeprecationLoggerMiddleware)

        @app.get("/v1")
        async def v1(response: Response):
            response.headers["Deprecation"] = "true"
            return {"ok": True}

        @app.get("/v2")
        async def v2(response: Response):
            response.headers["Deprecation"] = "1"
            return {"ok": True}

        @app.get("/v3")
        async def v3(response: Response):
            response.headers["Deprecation"] = "Mon, 01 Jan 2024 00:00:00 GMT"
            return {"ok": True}

        client = TestClient(app)

        # All should add Warning header since Deprecation header is present
        for path in ["/v1", "/v2", "/v3"]:
            response = client.get(path)
            assert "Warning" in response.headers, f"Expected Warning header for {path}"

    def test_existing_warning_header_not_overwritten(self):
        """Test that existing Warning header is preserved."""
        app = FastAPI()
        app.add_middleware(DeprecationLoggerMiddleware)

        @app.get("/deprecated")
        async def deprecated(response: Response):
            response.headers["Deprecation"] = "true"
            response.headers["Warning"] = '110 - "Custom warning"'
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/deprecated")

        # Existing Warning should be preserved
        assert response.headers["Warning"] == '110 - "Custom warning"'

    def test_long_endpoint_path_sanitized(self):
        """Test that very long endpoint paths are sanitized in metrics."""
        app = FastAPI()
        app.add_middleware(DeprecationLoggerMiddleware)

        long_path = "/deprecated/" + "a" * 200

        @app.get(long_path)
        async def deprecated(response: Response):
            response.headers["Deprecation"] = "true"
            return {"ok": True}

        client = TestClient(app)
        response = client.get(long_path)

        # Should complete without error
        assert response.status_code == 200

    def test_special_characters_in_client_id_sanitized(self):
        """Test that special characters in client_id are handled."""
        app = FastAPI()
        app.add_middleware(DeprecationLoggerMiddleware)

        @app.get("/deprecated")
        async def deprecated(response: Response):
            response.headers["Deprecation"] = "true"
            return {"ok": True}

        client = TestClient(app)

        # Client ID with special characters
        response = client.get(
            "/deprecated",
            headers={"X-Client-ID": "test<script>alert(1)</script>client"}
        )

        # Should complete without error
        assert response.status_code == 200


class TestDeprecationMiddlewareIntegration:
    """Integration tests with other middleware."""

    def test_works_with_request_timing_middleware(self):
        """Test that deprecation middleware works with RequestTimingMiddleware."""
        from backend.api.middleware.request_timing import RequestTimingMiddleware

        app = FastAPI()
        app.add_middleware(DeprecationLoggerMiddleware)
        app.add_middleware(RequestTimingMiddleware)

        @app.get("/deprecated")
        async def deprecated(response: Response):
            response.headers["Deprecation"] = "true"
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/deprecated")

        assert response.status_code == 200
        # Both middleware should add their headers
        assert "Warning" in response.headers
        assert "X-Response-Time" in response.headers

    def test_works_with_request_id_middleware(self):
        """Test that deprecation middleware works with RequestIDMiddleware."""
        from backend.api.middleware.request_id import RequestIDMiddleware

        app = FastAPI()
        app.add_middleware(DeprecationLoggerMiddleware)
        app.add_middleware(RequestIDMiddleware)

        @app.get("/deprecated")
        async def deprecated(response: Response):
            response.headers["Deprecation"] = "true"
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/deprecated")

        assert response.status_code == 200
        assert "Warning" in response.headers
        assert "X-Request-ID" in response.headers
