"""Unit tests for RFC 8594 Deprecation and Sunset headers middleware.

This module provides comprehensive tests for:
- DeprecationMiddleware: Adds Deprecation and Sunset headers per RFC 8594
- Deprecation configuration system for marking endpoints
- Header format validation (HTTP-date, Unix timestamp)

RFC 8594: https://www.rfc-editor.org/rfc/rfc8594.html
- Deprecation header: `Deprecation: true` or `Deprecation: @<unix-timestamp>`
- Sunset header: `Sunset: <HTTP-date>` per RFC 7231

Tests follow TDD approach - written before implementation.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response

from backend.api.middleware.deprecation import (
    DeprecatedEndpoint,
    DeprecationConfig,
    DeprecationMiddleware,
    format_http_date,
    format_unix_timestamp,
)

# =============================================================================
# Helper Function Tests
# =============================================================================


class TestFormatHttpDate:
    """Tests for HTTP-date formatting per RFC 7231."""

    def test_format_http_date_returns_correct_format(self):
        """Test that HTTP date is formatted per RFC 7231."""
        # Fixed date: Mon, 01 Jan 2024 00:00:00 GMT
        dt = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        result = format_http_date(dt)

        # RFC 7231 HTTP-date format: "day-name, DD Mon YYYY HH:MM:SS GMT"
        assert result == "Mon, 01 Jan 2024 00:00:00 GMT"

    def test_format_http_date_various_dates(self):
        """Test HTTP-date formatting for various dates."""
        test_cases = [
            (datetime(2024, 12, 31, 23, 59, 59, tzinfo=UTC), "Tue, 31 Dec 2024 23:59:59 GMT"),
            (datetime(2025, 6, 15, 12, 30, 45, tzinfo=UTC), "Sun, 15 Jun 2025 12:30:45 GMT"),
            (datetime(2023, 2, 28, 0, 0, 0, tzinfo=UTC), "Tue, 28 Feb 2023 00:00:00 GMT"),
        ]

        for dt, expected in test_cases:
            assert format_http_date(dt) == expected

    def test_format_http_date_naive_datetime_treated_as_utc(self):
        """Test that naive datetime is treated as UTC."""
        dt_naive = datetime(2024, 1, 1, 0, 0, 0)
        dt_utc = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)

        # Both should produce the same result
        assert format_http_date(dt_naive) == format_http_date(dt_utc)


class TestFormatUnixTimestamp:
    """Tests for Unix timestamp formatting for Deprecation header."""

    def test_format_unix_timestamp_returns_at_prefixed_string(self):
        """Test that Unix timestamp is formatted with @ prefix."""
        dt = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        result = format_unix_timestamp(dt)

        # RFC 8594 uses @<unix-timestamp> format
        assert result.startswith("@")
        assert result == "@1704067200"

    def test_format_unix_timestamp_various_dates(self):
        """Test Unix timestamp formatting for various dates."""
        test_cases = [
            (datetime(1970, 1, 1, 0, 0, 0, tzinfo=UTC), "@0"),
            (datetime(2000, 1, 1, 0, 0, 0, tzinfo=UTC), "@946684800"),
            (datetime(2024, 12, 31, 23, 59, 59, tzinfo=UTC), "@1735689599"),
        ]

        for dt, expected in test_cases:
            assert format_unix_timestamp(dt) == expected


# =============================================================================
# DeprecatedEndpoint Tests
# =============================================================================


class TestDeprecatedEndpoint:
    """Tests for DeprecatedEndpoint configuration dataclass."""

    def test_deprecated_endpoint_creation_basic(self):
        """Test basic DeprecatedEndpoint creation."""
        endpoint = DeprecatedEndpoint(
            path="/api/v1/old-endpoint",
            sunset_date=datetime(2025, 6, 1, tzinfo=UTC),
        )

        assert endpoint.path == "/api/v1/old-endpoint"
        assert endpoint.sunset_date == datetime(2025, 6, 1, tzinfo=UTC)
        assert endpoint.deprecated_at is None  # Optional
        assert endpoint.replacement is None  # Optional
        assert endpoint.link is None  # Optional

    def test_deprecated_endpoint_creation_with_all_fields(self):
        """Test DeprecatedEndpoint creation with all optional fields."""
        deprecated_at = datetime(2024, 1, 1, tzinfo=UTC)
        sunset = datetime(2025, 6, 1, tzinfo=UTC)

        endpoint = DeprecatedEndpoint(
            path="/api/v1/users",
            sunset_date=sunset,
            deprecated_at=deprecated_at,
            replacement="/api/v2/users",
            link="https://docs.example.com/migration",
        )

        assert endpoint.path == "/api/v1/users"
        assert endpoint.sunset_date == sunset
        assert endpoint.deprecated_at == deprecated_at
        assert endpoint.replacement == "/api/v2/users"
        assert endpoint.link == "https://docs.example.com/migration"

    def test_deprecated_endpoint_supports_path_patterns(self):
        """Test that DeprecatedEndpoint can use path patterns."""
        # Exact match
        endpoint_exact = DeprecatedEndpoint(
            path="/api/v1/cameras",
            sunset_date=datetime(2025, 6, 1, tzinfo=UTC),
        )

        # Prefix pattern
        endpoint_prefix = DeprecatedEndpoint(
            path="/api/v1/*",
            sunset_date=datetime(2025, 6, 1, tzinfo=UTC),
        )

        assert endpoint_exact.path == "/api/v1/cameras"
        assert endpoint_prefix.path == "/api/v1/*"


# =============================================================================
# DeprecationConfig Tests
# =============================================================================


class TestDeprecationConfig:
    """Tests for DeprecationConfig registry."""

    def test_deprecation_config_empty_by_default(self):
        """Test that DeprecationConfig starts empty."""
        config = DeprecationConfig()
        assert config.get_deprecated_endpoints() == []

    def test_deprecation_config_register_endpoint(self):
        """Test registering a deprecated endpoint."""
        config = DeprecationConfig()
        endpoint = DeprecatedEndpoint(
            path="/api/v1/old",
            sunset_date=datetime(2025, 6, 1, tzinfo=UTC),
        )

        config.register(endpoint)

        endpoints = config.get_deprecated_endpoints()
        assert len(endpoints) == 1
        assert endpoints[0].path == "/api/v1/old"

    def test_deprecation_config_register_multiple_endpoints(self):
        """Test registering multiple deprecated endpoints."""
        config = DeprecationConfig()

        config.register(
            DeprecatedEndpoint(
                path="/api/v1/users",
                sunset_date=datetime(2025, 6, 1, tzinfo=UTC),
            )
        )
        config.register(
            DeprecatedEndpoint(
                path="/api/v1/events",
                sunset_date=datetime(2025, 7, 1, tzinfo=UTC),
            )
        )

        endpoints = config.get_deprecated_endpoints()
        assert len(endpoints) == 2

    def test_deprecation_config_match_exact_path(self):
        """Test matching an exact path."""
        config = DeprecationConfig()
        config.register(
            DeprecatedEndpoint(
                path="/api/v1/cameras",
                sunset_date=datetime(2025, 6, 1, tzinfo=UTC),
            )
        )

        # Exact match
        result = config.match("/api/v1/cameras")
        assert result is not None
        assert result.path == "/api/v1/cameras"

        # No match
        assert config.match("/api/v1/events") is None
        assert config.match("/api/v2/cameras") is None

    def test_deprecation_config_match_path_with_trailing_slash(self):
        """Test path matching normalizes trailing slashes."""
        config = DeprecationConfig()
        config.register(
            DeprecatedEndpoint(
                path="/api/v1/cameras",
                sunset_date=datetime(2025, 6, 1, tzinfo=UTC),
            )
        )

        # Should match with or without trailing slash
        assert config.match("/api/v1/cameras") is not None
        assert config.match("/api/v1/cameras/") is not None

    def test_deprecation_config_match_wildcard_pattern(self):
        """Test matching wildcard patterns."""
        config = DeprecationConfig()
        config.register(
            DeprecatedEndpoint(
                path="/api/v1/*",
                sunset_date=datetime(2025, 6, 1, tzinfo=UTC),
            )
        )

        # Should match any path under /api/v1/
        assert config.match("/api/v1/cameras") is not None
        assert config.match("/api/v1/events") is not None
        assert config.match("/api/v1/cameras/123") is not None

        # Should not match other paths
        assert config.match("/api/v2/cameras") is None
        assert config.match("/api/cameras") is None

    def test_deprecation_config_exact_match_takes_priority(self):
        """Test that exact matches take priority over wildcards."""
        config = DeprecationConfig()

        # Register wildcard first
        config.register(
            DeprecatedEndpoint(
                path="/api/v1/*",
                sunset_date=datetime(2025, 6, 1, tzinfo=UTC),
                replacement="/api/v2/*",
            )
        )
        # Then register exact match
        config.register(
            DeprecatedEndpoint(
                path="/api/v1/special",
                sunset_date=datetime(2025, 12, 31, tzinfo=UTC),
                replacement="/api/v2/special-new",
            )
        )

        # Exact match should be returned for /api/v1/special
        result = config.match("/api/v1/special")
        assert result is not None
        assert result.replacement == "/api/v2/special-new"

        # Wildcard should be used for other paths
        result = config.match("/api/v1/other")
        assert result is not None
        assert result.replacement == "/api/v2/*"

    def test_deprecation_config_clear(self):
        """Test clearing all registered endpoints."""
        config = DeprecationConfig()
        config.register(
            DeprecatedEndpoint(
                path="/api/v1/old",
                sunset_date=datetime(2025, 6, 1, tzinfo=UTC),
            )
        )

        config.clear()

        assert config.get_deprecated_endpoints() == []


# =============================================================================
# DeprecationMiddleware Tests
# =============================================================================


class TestDeprecationMiddleware:
    """Tests for DeprecationMiddleware class."""

    @pytest.fixture
    def deprecation_config(self):
        """Create a test deprecation config with sample endpoints."""
        config = DeprecationConfig()
        config.register(
            DeprecatedEndpoint(
                path="/api/v1/cameras",
                sunset_date=datetime(2025, 6, 1, tzinfo=UTC),
                deprecated_at=datetime(2024, 1, 1, tzinfo=UTC),
                replacement="/api/v2/cameras",
                link="https://docs.example.com/v2-migration",
            )
        )
        config.register(
            DeprecatedEndpoint(
                path="/api/v1/events",
                sunset_date=datetime(2025, 12, 31, tzinfo=UTC),
            )
        )
        return config

    @pytest.fixture
    def app_with_deprecation_middleware(self, deprecation_config):
        """Create a test FastAPI app with DeprecationMiddleware."""
        app = FastAPI()
        app.add_middleware(DeprecationMiddleware, config=deprecation_config)

        @app.get("/api/v1/cameras")
        async def deprecated_cameras():
            return {"cameras": []}

        @app.get("/api/v1/events")
        async def deprecated_events():
            return {"events": []}

        @app.get("/api/v2/cameras")
        async def new_cameras():
            return {"cameras": []}

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        return app

    def test_deprecation_header_added_for_deprecated_endpoint(
        self, app_with_deprecation_middleware
    ):
        """Test that Deprecation header is added for deprecated endpoints."""
        client = TestClient(app_with_deprecation_middleware)
        response = client.get("/api/v1/cameras")

        assert response.status_code == 200
        assert "Deprecation" in response.headers

    def test_deprecation_header_format_with_timestamp(self, app_with_deprecation_middleware):
        """Test that Deprecation header uses @timestamp format when deprecated_at is set."""
        client = TestClient(app_with_deprecation_middleware)
        response = client.get("/api/v1/cameras")

        # /api/v1/cameras has deprecated_at set
        deprecation_header = response.headers["Deprecation"]

        # Should be @<unix-timestamp> format
        assert deprecation_header.startswith("@")
        # @1704067200 is 2024-01-01T00:00:00Z
        assert deprecation_header == "@1704067200"

    def test_deprecation_header_format_true_when_no_timestamp(
        self, app_with_deprecation_middleware
    ):
        """Test that Deprecation header is 'true' when deprecated_at is not set."""
        client = TestClient(app_with_deprecation_middleware)
        response = client.get("/api/v1/events")

        # /api/v1/events does not have deprecated_at set
        deprecation_header = response.headers["Deprecation"]

        # Should be simple "true"
        assert deprecation_header == "true"

    def test_sunset_header_added_for_deprecated_endpoint(self, app_with_deprecation_middleware):
        """Test that Sunset header is added for deprecated endpoints."""
        client = TestClient(app_with_deprecation_middleware)
        response = client.get("/api/v1/cameras")

        assert response.status_code == 200
        assert "Sunset" in response.headers

    def test_sunset_header_http_date_format(self, app_with_deprecation_middleware):
        """Test that Sunset header uses HTTP-date format per RFC 7231."""
        client = TestClient(app_with_deprecation_middleware)
        response = client.get("/api/v1/cameras")

        sunset_header = response.headers["Sunset"]

        # Should be HTTP-date format: "Sun, 01 Jun 2025 00:00:00 GMT"
        assert sunset_header == "Sun, 01 Jun 2025 00:00:00 GMT"

    def test_link_header_added_when_replacement_specified(self, app_with_deprecation_middleware):
        """Test that Link header is added when replacement is specified."""
        client = TestClient(app_with_deprecation_middleware)
        response = client.get("/api/v1/cameras")

        # /api/v1/cameras has link specified
        assert "Link" in response.headers
        link_header = response.headers["Link"]

        # Should contain the documentation link with rel=deprecation
        assert "https://docs.example.com/v2-migration" in link_header
        assert 'rel="deprecation"' in link_header

    def test_no_link_header_when_no_replacement(self, app_with_deprecation_middleware):
        """Test that Link header is not added when no link is specified."""
        client = TestClient(app_with_deprecation_middleware)
        response = client.get("/api/v1/events")

        # /api/v1/events does not have link specified
        # Link header should not be added (or should not contain deprecation rel)
        link_header = response.headers.get("Link", "")
        assert 'rel="deprecation"' not in link_header

    def test_no_headers_for_non_deprecated_endpoint(self, app_with_deprecation_middleware):
        """Test that deprecation headers are not added for non-deprecated endpoints."""
        client = TestClient(app_with_deprecation_middleware)
        response = client.get("/api/v2/cameras")

        assert response.status_code == 200
        assert "Deprecation" not in response.headers
        assert "Sunset" not in response.headers

    def test_no_headers_for_health_endpoint(self, app_with_deprecation_middleware):
        """Test that deprecation headers are not added for health endpoints."""
        client = TestClient(app_with_deprecation_middleware)
        response = client.get("/health")

        assert response.status_code == 200
        assert "Deprecation" not in response.headers
        assert "Sunset" not in response.headers

    def test_middleware_does_not_affect_response_body(self, app_with_deprecation_middleware):
        """Test that middleware does not modify response body."""
        client = TestClient(app_with_deprecation_middleware)
        response = client.get("/api/v1/cameras")

        assert response.status_code == 200
        assert response.json() == {"cameras": []}

    def test_middleware_handles_post_requests(self):
        """Test that middleware adds headers for POST requests."""
        config = DeprecationConfig()
        config.register(
            DeprecatedEndpoint(
                path="/api/v1/cameras",
                sunset_date=datetime(2025, 6, 1, tzinfo=UTC),
            )
        )

        app = FastAPI()
        app.add_middleware(DeprecationMiddleware, config=config)

        @app.post("/api/v1/cameras")
        async def create_camera():
            return {"id": "123"}

        client = TestClient(app)
        response = client.post("/api/v1/cameras")

        assert response.status_code == 200
        assert "Deprecation" in response.headers
        assert "Sunset" in response.headers


class TestDeprecationMiddlewareEdgeCases:
    """Edge case tests for DeprecationMiddleware."""

    def test_handles_error_responses(self):
        """Test that headers are added even for error responses."""
        config = DeprecationConfig()
        config.register(
            DeprecatedEndpoint(
                path="/api/v1/error",
                sunset_date=datetime(2025, 6, 1, tzinfo=UTC),
            )
        )

        app = FastAPI()
        app.add_middleware(DeprecationMiddleware, config=config)

        @app.get("/api/v1/error")
        async def error_endpoint():
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Not found")

        client = TestClient(app)
        response = client.get("/api/v1/error")

        assert response.status_code == 404
        # Headers should still be added
        assert "Deprecation" in response.headers
        assert "Sunset" in response.headers

    def test_handles_empty_config(self):
        """Test middleware works with empty config."""
        config = DeprecationConfig()

        app = FastAPI()
        app.add_middleware(DeprecationMiddleware, config=config)

        @app.get("/test")
        async def test_endpoint():
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        assert "Deprecation" not in response.headers
        assert "Sunset" not in response.headers

    def test_handles_path_with_query_params(self):
        """Test that path matching ignores query parameters."""
        config = DeprecationConfig()
        config.register(
            DeprecatedEndpoint(
                path="/api/v1/cameras",
                sunset_date=datetime(2025, 6, 1, tzinfo=UTC),
            )
        )

        app = FastAPI()
        app.add_middleware(DeprecationMiddleware, config=config)

        @app.get("/api/v1/cameras")
        async def cameras_endpoint():
            return {"cameras": []}

        client = TestClient(app)
        response = client.get("/api/v1/cameras?status=online&limit=10")

        assert response.status_code == 200
        assert "Deprecation" in response.headers
        assert "Sunset" in response.headers

    def test_handles_path_variables(self):
        """Test that path matching works with path variables."""
        config = DeprecationConfig()
        config.register(
            DeprecatedEndpoint(
                path="/api/v1/cameras/*",
                sunset_date=datetime(2025, 6, 1, tzinfo=UTC),
            )
        )

        app = FastAPI()
        app.add_middleware(DeprecationMiddleware, config=config)

        @app.get("/api/v1/cameras/{camera_id}")
        async def get_camera(camera_id: str):
            return {"id": camera_id}

        client = TestClient(app)
        response = client.get("/api/v1/cameras/front-door")

        assert response.status_code == 200
        assert "Deprecation" in response.headers
        assert "Sunset" in response.headers


class TestDeprecationMiddlewareDirectDispatch:
    """Tests for direct dispatch method invocation."""

    @pytest.mark.asyncio
    async def test_dispatch_adds_headers_correctly(self):
        """Test that dispatch method adds headers correctly."""
        config = DeprecationConfig()
        config.register(
            DeprecatedEndpoint(
                path="/api/v1/test",
                sunset_date=datetime(2025, 6, 1, tzinfo=UTC),
                deprecated_at=datetime(2024, 1, 1, tzinfo=UTC),
            )
        )

        app = FastAPI()
        middleware = DeprecationMiddleware(app, config=config)

        mock_request = MagicMock(spec=Request)
        mock_request.url = MagicMock()
        mock_request.url.path = "/api/v1/test"

        mock_response = MagicMock(spec=Response)
        mock_response.headers = {}
        mock_response.status_code = 200

        async def mock_call_next(request):
            return mock_response

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert "Deprecation" in response.headers
        assert "Sunset" in response.headers
        assert response.headers["Deprecation"] == "@1704067200"
        assert response.headers["Sunset"] == "Sun, 01 Jun 2025 00:00:00 GMT"

    @pytest.mark.asyncio
    async def test_dispatch_does_not_add_headers_for_non_deprecated(self):
        """Test that dispatch does not add headers for non-deprecated paths."""
        config = DeprecationConfig()
        config.register(
            DeprecatedEndpoint(
                path="/api/v1/old",
                sunset_date=datetime(2025, 6, 1, tzinfo=UTC),
            )
        )

        app = FastAPI()
        middleware = DeprecationMiddleware(app, config=config)

        mock_request = MagicMock(spec=Request)
        mock_request.url = MagicMock()
        mock_request.url.path = "/api/v2/new"

        mock_response = MagicMock(spec=Response)
        mock_response.headers = {}
        mock_response.status_code = 200

        async def mock_call_next(request):
            return mock_response

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert "Deprecation" not in response.headers
        assert "Sunset" not in response.headers


class TestDeprecationMiddlewareIntegration:
    """Integration tests with other middleware."""

    def test_deprecation_middleware_with_security_headers(self):
        """Test that deprecation middleware works with SecurityHeadersMiddleware."""
        from backend.api.middleware.security_headers import SecurityHeadersMiddleware

        config = DeprecationConfig()
        config.register(
            DeprecatedEndpoint(
                path="/api/v1/test",
                sunset_date=datetime(2025, 6, 1, tzinfo=UTC),
            )
        )

        app = FastAPI()
        app.add_middleware(DeprecationMiddleware, config=config)
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/api/v1/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/api/v1/test")

        assert response.status_code == 200
        # Both deprecation and security headers should be present
        assert "Deprecation" in response.headers
        assert "Sunset" in response.headers
        assert "X-Content-Type-Options" in response.headers

    def test_deprecation_middleware_with_request_id(self):
        """Test that deprecation middleware works with RequestIDMiddleware."""
        from backend.api.middleware.request_id import RequestIDMiddleware

        config = DeprecationConfig()
        config.register(
            DeprecatedEndpoint(
                path="/api/v1/test",
                sunset_date=datetime(2025, 6, 1, tzinfo=UTC),
            )
        )

        app = FastAPI()
        app.add_middleware(DeprecationMiddleware, config=config)
        app.add_middleware(RequestIDMiddleware)

        @app.get("/api/v1/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/api/v1/test")

        assert response.status_code == 200
        # Both deprecation and request ID headers should be present
        assert "Deprecation" in response.headers
        assert "Sunset" in response.headers
        assert "X-Request-ID" in response.headers


class TestDeprecationConfigFromDict:
    """Tests for creating DeprecationConfig from dictionary configuration."""

    def test_from_dict_basic(self):
        """Test creating config from basic dictionary."""
        data = {
            "endpoints": [
                {
                    "path": "/api/v1/old",
                    "sunset_date": "2025-06-01T00:00:00Z",
                }
            ]
        }

        config = DeprecationConfig.from_dict(data)

        endpoints = config.get_deprecated_endpoints()
        assert len(endpoints) == 1
        assert endpoints[0].path == "/api/v1/old"
        assert endpoints[0].sunset_date == datetime(2025, 6, 1, tzinfo=UTC)

    def test_from_dict_with_all_fields(self):
        """Test creating config from dictionary with all fields."""
        data = {
            "endpoints": [
                {
                    "path": "/api/v1/cameras",
                    "sunset_date": "2025-06-01T00:00:00Z",
                    "deprecated_at": "2024-01-01T00:00:00Z",
                    "replacement": "/api/v2/cameras",
                    "link": "https://docs.example.com/migration",
                }
            ]
        }

        config = DeprecationConfig.from_dict(data)

        endpoints = config.get_deprecated_endpoints()
        assert len(endpoints) == 1
        assert endpoints[0].path == "/api/v1/cameras"
        assert endpoints[0].sunset_date == datetime(2025, 6, 1, tzinfo=UTC)
        assert endpoints[0].deprecated_at == datetime(2024, 1, 1, tzinfo=UTC)
        assert endpoints[0].replacement == "/api/v2/cameras"
        assert endpoints[0].link == "https://docs.example.com/migration"

    def test_from_dict_multiple_endpoints(self):
        """Test creating config with multiple endpoints."""
        data = {
            "endpoints": [
                {"path": "/api/v1/a", "sunset_date": "2025-06-01T00:00:00Z"},
                {"path": "/api/v1/b", "sunset_date": "2025-07-01T00:00:00Z"},
                {"path": "/api/v1/c", "sunset_date": "2025-08-01T00:00:00Z"},
            ]
        }

        config = DeprecationConfig.from_dict(data)

        endpoints = config.get_deprecated_endpoints()
        assert len(endpoints) == 3

    def test_from_dict_empty_endpoints(self):
        """Test creating config with empty endpoints list."""
        data = {"endpoints": []}

        config = DeprecationConfig.from_dict(data)

        assert config.get_deprecated_endpoints() == []
