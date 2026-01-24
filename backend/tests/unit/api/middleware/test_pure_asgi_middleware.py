"""Unit tests for pure ASGI middleware implementations (NEM-3348).

This module tests the pure ASGI middleware implementations of:
- RequestTimingMiddleware
- SecurityHeadersMiddleware

These tests specifically verify the ASGI interface (__call__) and the
send_wrapper pattern used in pure ASGI middleware.
"""

import asyncio
import logging
import time

import pytest
from fastapi import FastAPI
from fastapi import WebSocket as FastAPIWebSocket
from fastapi.testclient import TestClient
from starlette.responses import StreamingResponse

from backend.api.middleware.request_timing import RequestTimingMiddleware
from backend.api.middleware.security_headers import SecurityHeadersMiddleware

# =============================================================================
# Pure ASGI RequestTimingMiddleware Tests
# =============================================================================


class TestRequestTimingMiddlewareASGI:
    """Tests for pure ASGI RequestTimingMiddleware implementation."""

    @pytest.fixture
    def app_with_timing_middleware(self):
        """Create a test FastAPI app with RequestTimingMiddleware."""
        app = FastAPI()
        app.add_middleware(RequestTimingMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        @app.get("/slow")
        async def slow_endpoint():
            """Endpoint that simulates a slow response."""
            await asyncio.sleep(0.1)  # 100ms delay
            return {"message": "slow"}

        @app.post("/create")
        async def create_endpoint():
            return {"id": 123}

        @app.get("/error")
        async def error_endpoint():
            raise ValueError("Test error")

        return app

    def test_adds_response_time_header_asgi(self, app_with_timing_middleware):
        """Test that pure ASGI middleware adds X-Response-Time header."""
        client = TestClient(app_with_timing_middleware)
        response = client.get("/test")

        assert response.status_code == 200
        assert "X-Response-Time" in response.headers
        assert response.headers["X-Response-Time"].endswith("ms")

    def test_response_time_header_format_asgi(self, app_with_timing_middleware):
        """Test X-Response-Time header format from pure ASGI implementation."""
        client = TestClient(app_with_timing_middleware)
        response = client.get("/test")

        time_header = response.headers["X-Response-Time"]
        assert time_header.endswith("ms")
        numeric_part = time_header.replace("ms", "")
        duration = float(numeric_part)
        assert duration >= 0

    def test_slow_request_timing_asgi(self, app_with_timing_middleware):
        """Test that slow requests have appropriately longer response times."""
        client = TestClient(app_with_timing_middleware)

        fast_response = client.get("/test")
        fast_duration = float(fast_response.headers["X-Response-Time"].replace("ms", ""))

        slow_response = client.get("/slow")
        slow_duration = float(slow_response.headers["X-Response-Time"].replace("ms", ""))

        assert slow_duration > fast_duration
        assert slow_duration >= 100  # At least 100ms due to sleep

    def test_websocket_passthrough_asgi(self, app_with_timing_middleware):
        """Test that pure ASGI middleware passes through WebSocket connections."""

        @app_with_timing_middleware.websocket("/ws")
        async def websocket_endpoint(websocket: FastAPIWebSocket):
            await websocket.accept()
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
            await websocket.close()

        with (
            TestClient(app_with_timing_middleware) as client,
            client.websocket_connect("/ws") as ws,
        ):
            ws.send_text("Hello")
            response = ws.receive_text()
            assert response == "Echo: Hello"

    def test_streaming_response_asgi(self, app_with_timing_middleware):
        """Test that pure ASGI middleware handles streaming responses."""

        async def generate():
            yield b"chunk1"
            yield b"chunk2"

        @app_with_timing_middleware.get("/stream")
        async def stream_endpoint():
            return StreamingResponse(generate())

        client = TestClient(app_with_timing_middleware)
        response = client.get("/stream")

        assert response.status_code == 200
        assert "X-Response-Time" in response.headers

    def test_multiple_http_methods_asgi(self, app_with_timing_middleware):
        """Test that timing works for different HTTP methods."""
        client = TestClient(app_with_timing_middleware)

        get_response = client.get("/test")
        assert "X-Response-Time" in get_response.headers

        post_response = client.post("/create")
        assert "X-Response-Time" in post_response.headers


class TestRequestTimingMiddlewareASGILogging:
    """Tests for slow request logging in pure ASGI middleware."""

    @pytest.fixture
    def app_with_low_threshold(self):
        """Create app with low threshold (10ms) for testing logging."""
        app = FastAPI()
        app.add_middleware(RequestTimingMiddleware, slow_request_threshold_ms=10)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        @app.get("/slow")
        async def slow_endpoint():
            await asyncio.sleep(0.05)  # 50ms delay - above threshold
            return {"message": "slow"}

        return app

    def test_slow_request_logged_asgi(self, app_with_low_threshold, caplog):
        """Test that slow requests are logged in pure ASGI middleware."""
        client = TestClient(app_with_low_threshold)

        with caplog.at_level(logging.WARNING):
            response = client.get("/slow")

        assert response.status_code == 200
        slow_logs = [r for r in caplog.records if "slow" in r.message.lower()]
        assert len(slow_logs) >= 1
        assert "GET" in slow_logs[0].message
        assert "/slow" in slow_logs[0].message


class TestRequestTimingMiddlewareASGIErrorHandling:
    """Tests for error handling in pure ASGI middleware."""

    @pytest.fixture
    def app_with_timing(self):
        """Create app with timing middleware."""
        app = FastAPI()
        app.add_middleware(RequestTimingMiddleware)

        @app.get("/error")
        async def error_endpoint():
            raise ValueError("Test error")

        return app

    def test_error_logged_asgi(self, app_with_timing, caplog):
        """Test that errors are logged with request context in pure ASGI middleware."""
        client = TestClient(app_with_timing, raise_server_exceptions=False)

        with caplog.at_level(logging.ERROR):
            response = client.get("/error")

        assert response.status_code == 500
        error_logs = [
            r
            for r in caplog.records
            if r.levelno == logging.ERROR and "request processing failed" in r.message.lower()
        ]
        assert len(error_logs) >= 1


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

        client = TestClient(app)
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

        client = TestClient(app)
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

        client = TestClient(app)
        response = client.get("/test")

        assert response.headers["Content-Security-Policy"] == custom_csp

    def test_csp_report_only_mode_asgi(self):
        """Test CSP report-only mode in pure ASGI implementation."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware, csp_report_only=True)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        assert "Content-Security-Policy-Report-Only" in response.headers
        assert "Content-Security-Policy" not in response.headers


# =============================================================================
# Combined Middleware Tests
# =============================================================================


class TestCombinedMiddlewareASGI:
    """Tests for multiple pure ASGI middleware working together."""

    @pytest.fixture
    def app_with_both_middleware(self):
        """Create app with both timing and security headers middleware."""
        app = FastAPI()
        app.add_middleware(RequestTimingMiddleware)
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        return app

    def test_both_middlewares_work_together_asgi(self, app_with_both_middleware):
        """Test that both pure ASGI middleware work together correctly."""
        client = TestClient(app_with_both_middleware)
        response = client.get("/test")

        assert response.status_code == 200

        # Timing header should be present
        assert "X-Response-Time" in response.headers

        # Security headers should be present
        assert "X-Content-Type-Options" in response.headers
        assert "X-Frame-Options" in response.headers
        assert "Content-Security-Policy" in response.headers

    def test_websocket_with_both_middlewares_asgi(self, app_with_both_middleware):
        """Test WebSocket passthrough works with both middleware."""

        @app_with_both_middleware.websocket("/ws")
        async def websocket_endpoint(websocket: FastAPIWebSocket):
            await websocket.accept()
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
            await websocket.close()

        with TestClient(app_with_both_middleware) as client, client.websocket_connect("/ws") as ws:
            ws.send_text("Test")
            response = ws.receive_text()
            assert response == "Echo: Test"


# =============================================================================
# Performance Tests
# =============================================================================


class TestMiddlewarePerformance:
    """Basic performance tests for pure ASGI middleware."""

    def test_timing_middleware_overhead(self):
        """Test that timing middleware has minimal overhead."""
        app = FastAPI()
        app.add_middleware(RequestTimingMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"ok": True}

        client = TestClient(app)

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

    def test_security_headers_overhead(self):
        """Test that security headers middleware has minimal overhead."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"ok": True}

        client = TestClient(app)

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
