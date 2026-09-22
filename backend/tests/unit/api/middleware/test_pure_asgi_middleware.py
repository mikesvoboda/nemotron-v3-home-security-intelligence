"""Unit tests for pure ASGI middleware implementations (NEM-3348).

This module tests the pure ASGI middleware implementations of:
- SecurityHeadersMiddleware

These tests specifically verify the ASGI interface (__call__) and the
send_wrapper pattern used in pure ASGI middleware.
"""

import time

import pytest
from fastapi import FastAPI
from fastapi import WebSocket as FastAPIWebSocket
from fastapi.testclient import TestClient

from backend.api.middleware.security_headers import SecurityHeadersMiddleware
from backend.tests.unit.conftest import get_auth_headers

# =============================================================================
# Pure ASGI SecurityHeadersMiddleware Tests
# =============================================================================


class TestSecurityHeadersMiddlewareASGI:
    """Tests for pure ASGI SecurityHeadersMiddleware implementation."""

    @pytest.fixture
    def app_with_security_headers(self):
        """Create a test FastAPI app with SecurityHeadersMiddleware."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        @app.get("/health")
        async def health():
            return {"status": "healthy"}

        return app

    def test_all_security_headers_present_asgi(self, app_with_security_headers):
        """Test that all security headers are present in pure ASGI implementation."""
        client = TestClient(app_with_security_headers)
        response = client.get("/test")

        assert response.status_code == 200

        required_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Referrer-Policy",
            "Content-Security-Policy",
            "Permissions-Policy",
            "Cross-Origin-Opener-Policy",
            "Cross-Origin-Resource-Policy",
        ]

        for header in required_headers:
            assert header in response.headers, f"Missing security header: {header}"

    def test_header_values_asgi(self, app_with_security_headers):
        """Test that security headers have correct values in pure ASGI implementation."""
        client = TestClient(app_with_security_headers)
        response = client.get("/test")

        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_csp_header_asgi(self, app_with_security_headers):
        """Test CSP header in pure ASGI implementation."""
        client = TestClient(app_with_security_headers)
        response = client.get("/test")

        csp = response.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp

    def test_websocket_passthrough_asgi(self, app_with_security_headers):
        """Test that security headers middleware passes through WebSocket connections."""

        @app_with_security_headers.websocket("/ws")
        async def websocket_endpoint(websocket: FastAPIWebSocket):
            await websocket.accept()
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
            await websocket.close()

        with TestClient(app_with_security_headers) as client, client.websocket_connect("/ws") as ws:
            ws.send_text("Hello")
            response = ws.receive_text()
            assert response == "Echo: Hello"

    def test_headers_on_different_endpoints_asgi(self, app_with_security_headers):
        """Test that security headers are applied to all endpoints."""
        client = TestClient(app_with_security_headers)

        for path in ["/test", "/health"]:
            response = client.get(path)
            assert "X-Content-Type-Options" in response.headers
            assert "X-Frame-Options" in response.headers
            assert "Content-Security-Policy" in response.headers


class TestSecurityHeadersMiddlewareHSTSASGI:
    """Tests for HSTS header functionality in pure ASGI middleware."""

    @pytest.fixture
    def https_app(self):
        """Create a test app with HSTS enabled."""
        app = FastAPI()
        app.add_middleware(
            SecurityHeadersMiddleware,
            hsts_enabled=True,
            hsts_max_age=31536000,
            hsts_include_subdomains=True,
        )

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        return app

    def test_hsts_not_added_on_http_asgi(self, https_app):
        """Test that HSTS header is NOT added for plain HTTP requests."""
        client = TestClient(https_app)
        response = client.get("/test")

        assert response.status_code == 200
        assert "Strict-Transport-Security" not in response.headers

    def test_hsts_added_on_https_asgi(self, https_app):
        """Test that HSTS header IS added when X-Forwarded-Proto is https."""
        client = TestClient(https_app)
        response = client.get("/test", headers={"X-Forwarded-Proto": "https"})

        assert response.status_code == 200
        assert "Strict-Transport-Security" in response.headers
        hsts = response.headers["Strict-Transport-Security"]
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts

    def test_hsts_preload_asgi(self):
        """Test HSTS preload directive in pure ASGI implementation."""
        app = FastAPI()
        app.add_middleware(
            SecurityHeadersMiddleware,
            hsts_enabled=True,
            hsts_max_age=31536000,
            hsts_include_subdomains=True,
            hsts_preload=True,
        )

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app, headers=get_auth_headers())
        response = client.get("/test", headers={"X-Forwarded-Proto": "https"})

        assert response.status_code == 200
        hsts = response.headers["Strict-Transport-Security"]
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts
        assert "preload" in hsts


class TestSecurityHeadersMiddlewareCustomConfigASGI:
    """Tests for custom configuration in pure ASGI middleware."""

    def test_custom_frame_options_asgi(self):
        """Test custom X-Frame-Options value in pure ASGI implementation."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware, frame_options="SAMEORIGIN")

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app, headers=get_auth_headers())
        response = client.get("/test")

        assert response.headers["X-Frame-Options"] == "SAMEORIGIN"

    def test_custom_csp_asgi(self):
        """Test custom CSP value in pure ASGI implementation."""
        app = FastAPI()
        custom_csp = "default-src 'none'; script-src 'self'"
        app.add_middleware(SecurityHeadersMiddleware, content_security_policy=custom_csp)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app, headers=get_auth_headers())
        response = client.get("/test")

        assert response.headers["Content-Security-Policy"] == custom_csp

    def test_csp_report_only_mode_asgi(self):
        """Test CSP report-only mode in pure ASGI implementation."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware, csp_report_only=True)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app, headers=get_auth_headers())
        response = client.get("/test")

        assert "Content-Security-Policy-Report-Only" in response.headers
        assert "Content-Security-Policy" not in response.headers


# =============================================================================
# Performance Tests
# =============================================================================


class TestMiddlewarePerformance:
    """Basic performance tests for pure ASGI middleware."""

    def test_security_headers_overhead(self):
        """Test that security headers middleware has minimal overhead."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"ok": True}

        client = TestClient(app, headers=get_auth_headers())

        # Warm up
        client.get("/test")

        # Measure multiple requests
        durations = []
        for _ in range(10):
            start = time.perf_counter()
            response = client.get("/test")
            elapsed = (time.perf_counter() - start) * 1000
            durations.append(elapsed)
            assert response.status_code == 200

        avg_duration = sum(durations) / len(durations)
        # Pure ASGI middleware should be fast (< 50ms overhead)
        assert avg_duration < 50, f"Average duration {avg_duration:.2f}ms is too high"
