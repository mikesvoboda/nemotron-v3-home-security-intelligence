"""Unit tests for Accept header content negotiation middleware (NEM-2086).

This module provides comprehensive tests for:
- AcceptHeaderMiddleware: HTTP Accept header content negotiation
- Support for application/json and application/problem+json (errors)
- 406 Not Acceptable when requested format isn't supported
- Default to application/json when no Accept header provided
- Quality value (q=) parsing and prioritization
"""

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from backend.api.middleware.accept_header import (
    SUPPORTED_MEDIA_TYPES,
    AcceptHeaderMiddleware,
    parse_accept_header,
    select_best_media_type,
)


class TestParseAcceptHeader:
    """Tests for the parse_accept_header utility function."""

    def test_parse_simple_accept_header(self):
        """Test parsing a simple Accept header without quality values."""
        result = parse_accept_header("application/json")
        assert result == [("application/json", 1.0)]

    def test_parse_accept_header_with_quality(self):
        """Test parsing Accept header with quality value."""
        result = parse_accept_header("application/json;q=0.8")
        assert result == [("application/json", 0.8)]

    def test_parse_accept_header_with_space_around_quality(self):
        """Test parsing Accept header with spaces around quality value."""
        result = parse_accept_header("application/json; q=0.8")
        assert result == [("application/json", 0.8)]

    def test_parse_multiple_media_types(self):
        """Test parsing Accept header with multiple media types."""
        result = parse_accept_header("application/json, text/html")
        assert len(result) == 2
        assert ("application/json", 1.0) in result
        assert ("text/html", 1.0) in result

    def test_parse_multiple_media_types_with_quality(self):
        """Test parsing multiple media types with quality values."""
        result = parse_accept_header("text/html;q=0.9, application/json;q=0.8")
        assert len(result) == 2
        # Should be sorted by quality (highest first)
        assert result[0] == ("text/html", 0.9)
        assert result[1] == ("application/json", 0.8)

    def test_parse_wildcard_media_type(self):
        """Test parsing wildcard media type."""
        result = parse_accept_header("*/*")
        assert result == [("*/*", 1.0)]

    def test_parse_type_wildcard(self):
        """Test parsing type with subtype wildcard."""
        result = parse_accept_header("application/*")
        assert result == [("application/*", 1.0)]

    def test_parse_empty_accept_header(self):
        """Test parsing empty Accept header."""
        result = parse_accept_header("")
        assert result == []

    def test_parse_none_accept_header(self):
        """Test parsing None Accept header."""
        result = parse_accept_header(None)
        assert result == []

    def test_parse_invalid_quality_defaults_to_one(self):
        """Test that invalid quality values default to 1.0."""
        result = parse_accept_header("application/json;q=invalid")
        assert result == [("application/json", 1.0)]

    def test_parse_quality_out_of_range_clamped(self):
        """Test that quality values are clamped to [0, 1]."""
        result = parse_accept_header("application/json;q=1.5")
        assert result == [("application/json", 1.0)]

        result = parse_accept_header("application/json;q=-0.5")
        assert result == [("application/json", 0.0)]

    def test_parse_case_insensitive_media_type(self):
        """Test that media type parsing is case insensitive."""
        result = parse_accept_header("APPLICATION/JSON")
        assert result == [("application/json", 1.0)]

    def test_parse_with_other_parameters(self):
        """Test parsing Accept header with other parameters besides q."""
        result = parse_accept_header("application/json; charset=utf-8; q=0.9")
        assert result == [("application/json", 0.9)]


class TestSelectBestMediaType:
    """Tests for the select_best_media_type utility function."""

    def test_select_exact_match(self):
        """Test selecting an exact media type match."""
        result = select_best_media_type(
            [("application/json", 1.0)],
            SUPPORTED_MEDIA_TYPES,
        )
        assert result == "application/json"

    def test_select_problem_json_exact_match(self):
        """Test selecting application/problem+json exact match."""
        result = select_best_media_type(
            [("application/problem+json", 1.0)],
            SUPPORTED_MEDIA_TYPES,
        )
        assert result == "application/problem+json"

    def test_select_highest_quality_match(self):
        """Test selecting the supported type with highest quality."""
        result = select_best_media_type(
            [("text/html", 1.0), ("application/json", 0.9)],
            SUPPORTED_MEDIA_TYPES,
        )
        # text/html is not supported, so should return application/json
        assert result == "application/json"

    def test_select_wildcard_returns_default(self):
        """Test that wildcard returns the default (application/json)."""
        result = select_best_media_type(
            [("*/*", 1.0)],
            SUPPORTED_MEDIA_TYPES,
        )
        assert result == "application/json"

    def test_select_application_wildcard_returns_json(self):
        """Test that application/* wildcard matches application/json."""
        result = select_best_media_type(
            [("application/*", 1.0)],
            SUPPORTED_MEDIA_TYPES,
        )
        assert result == "application/json"

    def test_select_no_supported_type_returns_none(self):
        """Test that unsupported types return None."""
        result = select_best_media_type(
            [("text/html", 1.0), ("text/plain", 0.9)],
            SUPPORTED_MEDIA_TYPES,
        )
        assert result is None

    def test_select_empty_accept_returns_default(self):
        """Test that empty accept list returns default (application/json)."""
        result = select_best_media_type([], SUPPORTED_MEDIA_TYPES)
        assert result == "application/json"

    def test_select_respects_quality_order(self):
        """Test that selection respects quality order."""
        # When both types are supported, the one with higher quality is selected
        # Note: parse_accept_header sorts by quality, so we provide them pre-sorted
        result = select_best_media_type(
            [("application/problem+json", 0.9), ("application/json", 0.5)],
            SUPPORTED_MEDIA_TYPES,
        )
        # application/problem+json has higher quality and is checked first
        assert result == "application/problem+json"


class TestAcceptHeaderMiddleware:
    """Tests for AcceptHeaderMiddleware class."""

    @pytest.fixture
    def app_with_middleware(self):
        """Create a test FastAPI app with AcceptHeaderMiddleware."""
        app = FastAPI()
        app.add_middleware(AcceptHeaderMiddleware)

        @app.get("/test")
        async def get_endpoint():
            return {"message": "ok"}

        @app.get("/error")
        async def error_endpoint():
            raise HTTPException(status_code=404, detail="Not found")

        @app.post("/create")
        async def create_endpoint():
            return {"id": 123}

        @app.get("/health")
        async def health_endpoint():
            return {"status": "ok"}

        return app

    def test_accept_json_returns_json_response(self, app_with_middleware):
        """Test that Accept: application/json returns JSON response."""
        client = TestClient(app_with_middleware)
        response = client.get("/test", headers={"Accept": "application/json"})

        assert response.status_code == 200
        assert response.json() == {"message": "ok"}
        # Content-Type should be application/json
        assert "application/json" in response.headers.get("content-type", "")

    def test_no_accept_header_returns_json_default(self, app_with_middleware):
        """Test that missing Accept header defaults to application/json."""
        client = TestClient(app_with_middleware)
        # TestClient adds default Accept header, so we need to override
        response = client.get("/test", headers={"Accept": "*/*"})

        assert response.status_code == 200
        assert response.json() == {"message": "ok"}

    def test_accept_wildcard_returns_json(self, app_with_middleware):
        """Test that Accept: */* returns application/json."""
        client = TestClient(app_with_middleware)
        response = client.get("/test", headers={"Accept": "*/*"})

        assert response.status_code == 200
        assert response.json() == {"message": "ok"}

    def test_unsupported_accept_returns_406(self, app_with_middleware):
        """Test that unsupported Accept type returns 406 Not Acceptable."""
        client = TestClient(app_with_middleware)
        response = client.get("/test", headers={"Accept": "text/xml"})

        assert response.status_code == 406
        # The detail message contains info about unsupported type
        assert "not supported" in response.json().get("detail", "").lower()

    def test_unsupported_accept_returns_supported_types_in_response(self, app_with_middleware):
        """Test that 406 response includes list of supported types."""
        client = TestClient(app_with_middleware)
        response = client.get("/test", headers={"Accept": "text/xml"})

        assert response.status_code == 406
        data = response.json()
        assert "application/json" in str(data)
        assert "application/problem+json" in str(data)

    def test_post_with_unsupported_accept_returns_406(self, app_with_middleware):
        """Test that POST with unsupported Accept returns 406."""
        client = TestClient(app_with_middleware)
        response = client.post(
            "/create",
            json={"name": "test"},
            headers={"Accept": "text/html"},
        )

        assert response.status_code == 406

    def test_accept_application_wildcard_returns_json(self, app_with_middleware):
        """Test that Accept: application/* returns application/json."""
        client = TestClient(app_with_middleware)
        response = client.get("/test", headers={"Accept": "application/*"})

        assert response.status_code == 200
        assert response.json() == {"message": "ok"}

    def test_accept_with_quality_respects_preference(self, app_with_middleware):
        """Test that quality values are respected in content negotiation."""
        client = TestClient(app_with_middleware)
        # text/html has higher quality but unsupported, json is fallback
        response = client.get(
            "/test",
            headers={"Accept": "text/html;q=1.0, application/json;q=0.9"},
        )

        assert response.status_code == 200
        assert response.json() == {"message": "ok"}


class TestAcceptHeaderMiddlewareConfiguration:
    """Tests for middleware configuration options."""

    def test_custom_supported_types(self):
        """Test custom supported media types configuration."""
        app = FastAPI()
        app.add_middleware(
            AcceptHeaderMiddleware,
            supported_types={"application/json", "application/xml"},
        )

        @app.get("/test")
        async def test_endpoint():
            return {"ok": True}

        client = TestClient(app)

        # JSON should work
        response = client.get("/test", headers={"Accept": "application/json"})
        assert response.status_code == 200

        # XML Accept should pass middleware (even though FastAPI returns JSON)
        response = client.get("/test", headers={"Accept": "application/xml"})
        assert response.status_code == 200

        # Text/plain should fail
        response = client.get("/test", headers={"Accept": "text/plain"})
        assert response.status_code == 406

    def test_custom_exempt_paths(self):
        """Test custom exempt paths configuration."""
        app = FastAPI()
        app.add_middleware(
            AcceptHeaderMiddleware,
            exempt_paths={"/custom-exempt"},
        )

        @app.get("/custom-exempt")
        async def exempt_endpoint():
            return {"exempt": True}

        @app.get("/api/data")
        async def data_endpoint():
            return {"data": "ok"}

        client = TestClient(app)

        # Exempt path should pass with any Accept header
        response = client.get(
            "/custom-exempt",
            headers={"Accept": "text/xml"},
        )
        assert response.status_code == 200

        # Non-exempt path should validate Accept
        response = client.get(
            "/api/data",
            headers={"Accept": "text/xml"},
        )
        assert response.status_code == 406


class TestAcceptHeaderMiddlewareExemptPaths:
    """Tests for default exempt paths."""

    @pytest.fixture
    def app_with_middleware(self):
        """Create a test FastAPI app with AcceptHeaderMiddleware."""
        app = FastAPI()
        app.add_middleware(AcceptHeaderMiddleware)

        @app.get("/")
        async def root():
            return {"status": "ok"}

        @app.get("/health")
        async def health():
            return {"status": "alive"}

        @app.get("/ready")
        async def ready():
            return {"ready": True}

        @app.get("/api/system/health")
        async def system_health():
            return {"healthy": True}

        @app.get("/api/system/health/ready")
        async def system_ready():
            return {"ready": True}

        @app.get("/api/metrics")
        async def metrics():
            return "# prometheus metrics"

        return app

    def test_root_path_exempt(self, app_with_middleware):
        """Test that / is exempt from Accept validation."""
        client = TestClient(app_with_middleware)
        response = client.get("/", headers={"Accept": "text/xml"})
        assert response.status_code == 200

    def test_health_path_exempt(self, app_with_middleware):
        """Test that /health is exempt from Accept validation."""
        client = TestClient(app_with_middleware)
        response = client.get("/health", headers={"Accept": "text/xml"})
        assert response.status_code == 200

    def test_ready_path_exempt(self, app_with_middleware):
        """Test that /ready is exempt from Accept validation."""
        client = TestClient(app_with_middleware)
        response = client.get("/ready", headers={"Accept": "text/xml"})
        assert response.status_code == 200

    def test_api_system_health_exempt(self, app_with_middleware):
        """Test that /api/system/health is exempt from Accept validation."""
        client = TestClient(app_with_middleware)
        response = client.get("/api/system/health", headers={"Accept": "text/xml"})
        assert response.status_code == 200

    def test_api_metrics_exempt(self, app_with_middleware):
        """Test that /api/metrics is exempt from Accept validation."""
        client = TestClient(app_with_middleware)
        response = client.get("/api/metrics", headers={"Accept": "text/xml"})
        assert response.status_code == 200


class TestAcceptHeaderMiddlewareEdgeCases:
    """Edge case tests for Accept header validation."""

    @pytest.fixture
    def app_with_middleware(self):
        """Create a test FastAPI app with AcceptHeaderMiddleware."""
        app = FastAPI()
        app.add_middleware(AcceptHeaderMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"ok": True}

        return app

    def test_malformed_accept_header_treated_as_wildcard(self, app_with_middleware):
        """Test that malformed Accept header is treated as wildcard."""
        client = TestClient(app_with_middleware)
        # Malformed header should be handled gracefully
        response = client.get("/test", headers={"Accept": ";;;;"})
        # Should default to allowing the request (permissive)
        assert response.status_code == 200

    def test_accept_with_zero_quality_is_rejected(self, app_with_middleware):
        """Test that media type with q=0 is treated as not acceptable."""
        client = TestClient(app_with_middleware)
        # q=0 means "not acceptable"
        response = client.get("/test", headers={"Accept": "application/json;q=0, text/html;q=1.0"})
        # json is q=0, html is not supported, should be 406
        assert response.status_code == 406

    def test_complex_accept_header_parsed_correctly(self, app_with_middleware):
        """Test complex Accept header with multiple types and qualities."""
        client = TestClient(app_with_middleware)
        response = client.get(
            "/test",
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7"
            },
        )
        # application/json is acceptable with q=0.8, */* allows anything with q=0.7
        # Should succeed since json is supported
        assert response.status_code == 200

    def test_accept_header_with_charset_parameter(self, app_with_middleware):
        """Test Accept header with charset parameter is handled."""
        client = TestClient(app_with_middleware)
        response = client.get(
            "/test",
            headers={"Accept": "application/json; charset=utf-8"},
        )
        assert response.status_code == 200

    def test_multiple_wildcards_handled(self, app_with_middleware):
        """Test handling of multiple wildcard patterns."""
        client = TestClient(app_with_middleware)
        response = client.get(
            "/test",
            headers={"Accept": "*/*;q=0.1, application/*;q=0.5"},
        )
        assert response.status_code == 200


class TestAcceptHeaderMiddlewareWithWebSocket:
    """Tests for middleware behavior with WebSocket paths."""

    def test_websocket_paths_exempt(self):
        """Test that WebSocket paths are exempt from Accept validation."""
        app = FastAPI()
        app.add_middleware(AcceptHeaderMiddleware)

        @app.get("/ws/events")
        async def ws_events():
            # Simulating the path structure
            return {"ws": "events"}

        @app.get("/ws/system")
        async def ws_system():
            return {"ws": "system"}

        client = TestClient(app)

        # WebSocket paths should be exempt
        response = client.get("/ws/events", headers={"Accept": "text/xml"})
        assert response.status_code == 200

        response = client.get("/ws/system", headers={"Accept": "text/xml"})
        assert response.status_code == 200
