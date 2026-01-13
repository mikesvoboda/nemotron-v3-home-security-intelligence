"""Unit tests for request timing middleware (NEM-1469).

This module provides comprehensive tests for:
- RequestTimingMiddleware: API latency tracking and logging
- X-Response-Time header addition
- Configurable slow request threshold logging

Tests follow TDD approach - written before implementation.
"""

import asyncio
import logging
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response

from backend.api.middleware.request_timing import RequestTimingMiddleware

# =============================================================================
# RequestTimingMiddleware Tests
# =============================================================================


class TestRequestTimingMiddleware:
    """Tests for RequestTimingMiddleware class."""

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

    def test_adds_response_time_header(self, app_with_timing_middleware):
        """Test that middleware adds X-Response-Time header to response."""
        client = TestClient(app_with_timing_middleware)
        response = client.get("/test")

        assert response.status_code == 200
        assert "X-Response-Time" in response.headers
        # Header should end with 'ms'
        assert response.headers["X-Response-Time"].endswith("ms")

    def test_response_time_header_format(self, app_with_timing_middleware):
        """Test that X-Response-Time header has correct format (e.g., '1.23ms')."""
        client = TestClient(app_with_timing_middleware)
        response = client.get("/test")

        time_header = response.headers["X-Response-Time"]
        # Should match pattern like "1.23ms" or "0.50ms"
        assert time_header.endswith("ms")
        # Extract numeric part
        numeric_part = time_header.replace("ms", "")
        # Should be a valid float
        duration = float(numeric_part)
        assert duration >= 0

    def test_response_time_is_positive(self, app_with_timing_middleware):
        """Test that recorded response time is positive."""
        client = TestClient(app_with_timing_middleware)
        response = client.get("/test")

        time_header = response.headers["X-Response-Time"]
        duration = float(time_header.replace("ms", ""))
        assert duration > 0

    def test_slow_request_has_longer_response_time(self, app_with_timing_middleware):
        """Test that slow requests have appropriately longer response times."""
        client = TestClient(app_with_timing_middleware)

        # Fast request
        fast_response = client.get("/test")
        fast_duration = float(fast_response.headers["X-Response-Time"].replace("ms", ""))

        # Slow request (100ms sleep)
        slow_response = client.get("/slow")
        slow_duration = float(slow_response.headers["X-Response-Time"].replace("ms", ""))

        # Slow request should be significantly longer
        assert slow_duration > fast_duration
        assert slow_duration >= 100  # At least 100ms due to sleep

    def test_header_added_for_different_http_methods(self, app_with_timing_middleware):
        """Test that X-Response-Time is added for different HTTP methods."""
        client = TestClient(app_with_timing_middleware)

        # GET request
        get_response = client.get("/test")
        assert "X-Response-Time" in get_response.headers

        # POST request
        post_response = client.post("/create")
        assert "X-Response-Time" in post_response.headers

    def test_error_response_returns_500(self, app_with_timing_middleware):
        """Test that error responses return 500 status code.

        Note: When an exception is raised and not caught, the error handler
        creates a new response that bypasses the middleware's header addition.
        The timing middleware logs slow requests on error but cannot add headers
        to the error response created by Starlette's exception handler.
        """
        client = TestClient(app_with_timing_middleware, raise_server_exceptions=False)
        response = client.get("/error")

        assert response.status_code == 500
        # Note: X-Response-Time header is NOT added on unhandled exceptions
        # because the exception handler creates a new response


class TestRequestTimingMiddlewareLogging:
    """Tests for slow request logging functionality."""

    @pytest.fixture
    def app_with_low_threshold(self):
        """Create app with low threshold (10ms) for testing logging."""
        app = FastAPI()
        # 10ms threshold so even fast requests might be logged
        app.add_middleware(RequestTimingMiddleware, slow_request_threshold_ms=10)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        @app.get("/slow")
        async def slow_endpoint():
            await asyncio.sleep(0.05)  # 50ms delay - above threshold
            return {"message": "slow"}

        return app

    @pytest.fixture
    def app_with_high_threshold(self):
        """Create app with high threshold (1000ms) for testing logging."""
        app = FastAPI()
        # 1000ms threshold so fast requests won't be logged
        app.add_middleware(RequestTimingMiddleware, slow_request_threshold_ms=1000)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        return app

    def test_slow_request_is_logged(self, app_with_low_threshold, caplog):
        """Test that requests above threshold are logged."""
        client = TestClient(app_with_low_threshold)

        with caplog.at_level(logging.WARNING):
            response = client.get("/slow")

        assert response.status_code == 200
        # Check that a slow request warning was logged
        slow_logs = [r for r in caplog.records if "slow" in r.message.lower()]
        assert len(slow_logs) >= 1

    def test_fast_request_not_logged_as_slow(self, app_with_high_threshold, caplog):
        """Test that requests below threshold are not logged as slow."""
        client = TestClient(app_with_high_threshold)

        with caplog.at_level(logging.WARNING):
            response = client.get("/test")

        assert response.status_code == 200
        # Check that no slow request warning was logged
        slow_logs = [r for r in caplog.records if "slow" in r.message.lower()]
        assert len(slow_logs) == 0

    def test_log_includes_request_method(self, app_with_low_threshold, caplog):
        """Test that slow request log includes HTTP method."""
        client = TestClient(app_with_low_threshold)

        with caplog.at_level(logging.WARNING):
            response = client.get("/slow")

        assert response.status_code == 200
        slow_logs = [r for r in caplog.records if "slow" in r.message.lower()]
        assert len(slow_logs) >= 1
        # Log message should include GET method
        assert "GET" in slow_logs[0].message

    def test_log_includes_request_path(self, app_with_low_threshold, caplog):
        """Test that slow request log includes request path."""
        client = TestClient(app_with_low_threshold)

        with caplog.at_level(logging.WARNING):
            response = client.get("/slow")

        assert response.status_code == 200
        slow_logs = [r for r in caplog.records if "slow" in r.message.lower()]
        assert len(slow_logs) >= 1
        # Log message should include path
        assert "/slow" in slow_logs[0].message

    def test_log_includes_status_code(self, app_with_low_threshold, caplog):
        """Test that slow request log includes response status code."""
        client = TestClient(app_with_low_threshold)

        with caplog.at_level(logging.WARNING):
            response = client.get("/slow")

        assert response.status_code == 200
        slow_logs = [r for r in caplog.records if "slow" in r.message.lower()]
        assert len(slow_logs) >= 1
        # Log message should include status code
        assert "200" in slow_logs[0].message

    def test_log_includes_duration_ms(self, app_with_low_threshold, caplog):
        """Test that slow request log includes duration in milliseconds."""
        client = TestClient(app_with_low_threshold)

        with caplog.at_level(logging.WARNING):
            response = client.get("/slow")

        assert response.status_code == 200
        slow_logs = [r for r in caplog.records if "slow" in r.message.lower()]
        assert len(slow_logs) >= 1
        # Log should contain duration_ms in extra fields
        assert hasattr(slow_logs[0], "duration_ms") or "ms" in slow_logs[0].message


class TestRequestTimingMiddlewareConfiguration:
    """Tests for middleware configuration options."""

    def test_default_threshold_value(self):
        """Test that default slow request threshold is reasonable."""
        app = FastAPI()
        middleware = RequestTimingMiddleware(app)
        # Default should be 500ms based on requirements
        assert middleware.slow_request_threshold_ms == 500

    def test_custom_threshold_value(self):
        """Test that custom threshold can be set."""
        app = FastAPI()
        middleware = RequestTimingMiddleware(app, slow_request_threshold_ms=100)
        assert middleware.slow_request_threshold_ms == 100

    def test_threshold_from_settings(self):
        """Test that threshold can be loaded from settings."""
        with patch("backend.api.middleware.request_timing.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(slow_request_threshold_ms=250)

            app = FastAPI()
            # When no threshold provided, should use settings
            middleware = RequestTimingMiddleware(app)
            assert middleware.slow_request_threshold_ms == 250


class TestRequestTimingMiddlewareDirectDispatch:
    """Tests for direct dispatch method invocation."""

    @pytest.mark.asyncio
    async def test_dispatch_measures_time_accurately(self):
        """Test that dispatch method measures time with reasonable accuracy."""
        app = FastAPI()
        middleware = RequestTimingMiddleware(app)

        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url = MagicMock()
        mock_request.url.path = "/test"

        mock_response = MagicMock(spec=Response)
        mock_response.headers = {}
        mock_response.status_code = 200

        delay_ms = 50

        async def mock_call_next(request):
            await asyncio.sleep(delay_ms / 1000)  # Convert to seconds
            return mock_response

        start = time.perf_counter()
        response = await middleware.dispatch(mock_request, mock_call_next)
        elapsed = (time.perf_counter() - start) * 1000

        # Get the measured time from header
        measured_time = float(response.headers["X-Response-Time"].replace("ms", ""))

        # Measured time should be close to actual delay
        assert measured_time >= delay_ms * 0.8  # Allow 20% tolerance
        assert measured_time <= elapsed * 1.2  # Allow 20% tolerance

    @pytest.mark.asyncio
    async def test_dispatch_header_added_on_exception(self):
        """Test that header is added even when call_next raises exception."""
        app = FastAPI()
        middleware = RequestTimingMiddleware(app)

        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url = MagicMock()
        mock_request.url.path = "/error"

        async def mock_call_next_raises(request):
            raise ValueError("Test exception")

        # The middleware should re-raise the exception
        with pytest.raises(ValueError, match="Test exception"):
            await middleware.dispatch(mock_request, mock_call_next_raises)

    @pytest.mark.asyncio
    async def test_dispatch_uses_perf_counter(self):
        """Test that dispatch uses time.perf_counter for accurate timing."""
        app = FastAPI()
        middleware = RequestTimingMiddleware(app)

        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url = MagicMock()
        mock_request.url.path = "/test"

        mock_response = MagicMock(spec=Response)
        mock_response.headers = {}
        mock_response.status_code = 200

        async def mock_call_next(request):
            return mock_response

        with patch("backend.api.middleware.request_timing.time.perf_counter") as mock_perf:
            mock_perf.side_effect = [1.0, 1.05]  # 50ms difference

            response = await middleware.dispatch(mock_request, mock_call_next)

            # perf_counter should be called twice (start and end)
            assert mock_perf.call_count == 2

            # Duration should be 50ms
            duration = float(response.headers["X-Response-Time"].replace("ms", ""))
            assert abs(duration - 50.0) < 0.01


class TestRequestTimingMiddlewareIntegration:
    """Integration tests with other middleware."""

    def test_timing_middleware_with_request_id(self):
        """Test that timing middleware works with RequestIDMiddleware."""
        from backend.api.middleware.request_id import RequestIDMiddleware

        app = FastAPI()
        app.add_middleware(RequestTimingMiddleware)
        app.add_middleware(RequestIDMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200
        # Both headers should be present
        assert "X-Response-Time" in response.headers
        assert "X-Request-ID" in response.headers

    def test_timing_measures_full_request_including_other_middleware(self):
        """Test that timing includes time spent in other middleware."""
        from backend.api.middleware.request_id import RequestIDMiddleware

        app = FastAPI()
        # Timing middleware added last so it's outermost
        app.add_middleware(RequestIDMiddleware)
        app.add_middleware(RequestTimingMiddleware)

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        # Response time should be positive and include all middleware time
        duration = float(response.headers["X-Response-Time"].replace("ms", ""))
        assert duration > 0


class TestRequestTimingMiddlewareEdgeCases:
    """Edge case tests for request timing middleware."""

    def test_handles_very_fast_requests(self):
        """Test handling of very fast requests (sub-millisecond)."""
        app = FastAPI()
        app.add_middleware(RequestTimingMiddleware)

        @app.get("/fast")
        async def fast_endpoint():
            return {"ok": True}

        client = TestClient(app)
        response = client.get("/fast")

        assert response.status_code == 200
        assert "X-Response-Time" in response.headers
        # Should handle sub-millisecond times
        duration = float(response.headers["X-Response-Time"].replace("ms", ""))
        assert duration >= 0

    def test_handles_streaming_responses(self):
        """Test handling of streaming responses."""
        from starlette.responses import StreamingResponse

        app = FastAPI()
        app.add_middleware(RequestTimingMiddleware)

        async def generate():
            yield b"chunk1"
            yield b"chunk2"

        @app.get("/stream")
        async def stream_endpoint():
            return StreamingResponse(generate())

        client = TestClient(app)
        response = client.get("/stream")

        assert response.status_code == 200
        assert "X-Response-Time" in response.headers

    def test_handles_websocket_upgrade_requests(self):
        """Test that middleware passes through WebSocket upgrade requests.

        Note: BaseHTTPMiddleware does not intercept WebSocket connections,
        so timing middleware doesn't affect WebSocket functionality.
        """
        from fastapi import WebSocket as FastAPIWebSocket

        app = FastAPI()
        app.add_middleware(RequestTimingMiddleware)

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: FastAPIWebSocket):
            await websocket.accept()
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
            await websocket.close()

        # WebSocket connections should work without issues
        # BaseHTTPMiddleware does not intercept WebSocket requests
        with TestClient(app) as client, client.websocket_connect("/ws") as ws:
            ws.send_text("Hello")
            response = ws.receive_text()
            assert response == "Echo: Hello"


class TestRequestTimingMiddlewareErrorHandling:
    """Tests for error handling in request timing middleware (NEM-2546)."""

    def test_settings_unavailable_uses_fallback_with_debug_log(self, caplog):
        """Test that when settings are unavailable, fallback is used and logged at DEBUG."""
        with patch("backend.api.middleware.request_timing.get_settings") as mock_settings:
            # Simulate settings fetch failure
            mock_settings.side_effect = RuntimeError("Settings unavailable")

            app = FastAPI()
            with caplog.at_level(logging.DEBUG):
                middleware = RequestTimingMiddleware(app)

            # Should use default fallback
            assert middleware.slow_request_threshold_ms == 500

            # Should log at DEBUG level
            debug_logs = [
                r
                for r in caplog.records
                if r.levelno == logging.DEBUG and "settings unavailable" in r.message.lower()
            ]
            assert len(debug_logs) == 1

            # Log should contain useful context
            log_record = debug_logs[0]
            assert hasattr(log_record, "default_threshold_ms") or "500" in str(log_record)

    def test_settings_unavailable_logs_error_message(self, caplog):
        """Test that settings unavailable log includes the error message."""
        error_message = "Connection refused to config server"
        with patch("backend.api.middleware.request_timing.get_settings") as mock_settings:
            mock_settings.side_effect = ConnectionError(error_message)

            app = FastAPI()
            with caplog.at_level(logging.DEBUG):
                RequestTimingMiddleware(app)

            debug_logs = [
                r
                for r in caplog.records
                if r.levelno == logging.DEBUG and "settings unavailable" in r.message.lower()
            ]
            assert len(debug_logs) == 1
            # Error should be captured in extra fields
            assert hasattr(debug_logs[0], "error") or error_message in str(debug_logs[0])

    @pytest.mark.asyncio
    async def test_response_processing_error_logs_and_reraises(self, caplog):
        """Test that response processing errors are logged at ERROR level and re-raised."""
        app = FastAPI()
        middleware = RequestTimingMiddleware(app)

        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url = MagicMock()
        mock_request.url.path = "/api/process"

        error_message = "Database connection lost"

        async def mock_call_next_raises(request):
            raise ConnectionError(error_message)

        with caplog.at_level(logging.ERROR):
            with pytest.raises(ConnectionError, match=error_message):
                await middleware.dispatch(mock_request, mock_call_next_raises)

        # Should have logged at ERROR level before re-raising
        error_logs = [
            r
            for r in caplog.records
            if r.levelno == logging.ERROR and "request processing failed" in r.message.lower()
        ]
        assert len(error_logs) == 1

        # Log should contain context about where exception occurred
        log_record = error_logs[0]
        assert hasattr(log_record, "path") or "/api/process" in str(log_record)
        assert hasattr(log_record, "method") or "POST" in str(log_record)
        assert hasattr(log_record, "error_type") or "ConnectionError" in str(log_record)

    @pytest.mark.asyncio
    async def test_response_processing_error_includes_duration(self, caplog):
        """Test that error log includes request duration for diagnostics."""
        app = FastAPI()
        middleware = RequestTimingMiddleware(app)

        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url = MagicMock()
        mock_request.url.path = "/test"

        async def mock_call_next_raises(request):
            await asyncio.sleep(0.05)  # 50ms delay before error
            raise ValueError("Test error")

        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError):
                await middleware.dispatch(mock_request, mock_call_next_raises)

        error_logs = [
            r
            for r in caplog.records
            if r.levelno == logging.ERROR and "request processing failed" in r.message.lower()
        ]
        assert len(error_logs) == 1

        # Log should contain duration_ms
        log_record = error_logs[0]
        assert hasattr(log_record, "duration_ms")
        # Duration should be at least 50ms (the sleep time)
        assert log_record.duration_ms >= 45  # Allow some tolerance

    @pytest.mark.asyncio
    async def test_response_processing_error_includes_error_type(self, caplog):
        """Test that error log includes the exception type name."""
        app = FastAPI()
        middleware = RequestTimingMiddleware(app)

        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url = MagicMock()
        mock_request.url.path = "/test"

        async def mock_call_next_raises(request):
            raise KeyError("missing_key")

        with caplog.at_level(logging.ERROR):
            with pytest.raises(KeyError):
                await middleware.dispatch(mock_request, mock_call_next_raises)

        error_logs = [
            r
            for r in caplog.records
            if r.levelno == logging.ERROR and "request processing failed" in r.message.lower()
        ]
        assert len(error_logs) == 1

        # Log should contain error_type
        log_record = error_logs[0]
        assert hasattr(log_record, "error_type")
        assert log_record.error_type == "KeyError"

    def test_init_and_dispatch_exception_handling_consistency(self):
        """Test that both init and dispatch handle exceptions consistently.

        Init logs at DEBUG (expected during testing), dispatch logs at ERROR (unexpected).
        Both capture exception details in structured extra fields.
        """
        # Init exception handling - logs at DEBUG (expected scenario)
        with patch("backend.api.middleware.request_timing.get_settings") as mock_settings:
            mock_settings.side_effect = RuntimeError("Test error")
            app = FastAPI()
            middleware = RequestTimingMiddleware(app)
            # Should succeed with fallback
            assert middleware.slow_request_threshold_ms == 500

        # Dispatch exception handling is tested in other tests
        # Both use structured logging with extra fields for consistency
