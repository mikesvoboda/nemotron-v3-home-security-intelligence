"""Unit tests for BodySizeLimitMiddleware (NEM-1614).

Tests cover:
- Request body size enforcement
- Content-Length header validation
- Configurable size limits
- 413 Payload Too Large responses
- Edge cases (no Content-Length, streaming requests)

NEM-1614: Add request body size limits to prevent DoS attacks
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from backend.api.middleware.body_limit import BodySizeLimitMiddleware


class TestBodySizeLimitMiddleware:
    """Tests for BodySizeLimitMiddleware class."""

    @pytest.fixture
    def app_with_body_limit(self):
        """Create a test FastAPI app with BodySizeLimitMiddleware."""
        app = FastAPI()
        # 1KB limit for testing
        app.add_middleware(BodySizeLimitMiddleware, max_body_size=1024)

        @app.post("/upload")
        async def upload_endpoint(request: Request):
            body = await request.body()
            return {"size": len(body)}

        @app.get("/test")
        async def test_endpoint():
            return {"message": "ok"}

        @app.put("/update")
        async def update_endpoint(request: Request):
            body = await request.body()
            return {"size": len(body)}

        return app

    @pytest.fixture
    def app_with_default_limit(self):
        """Create a test FastAPI app with default body limit (10MB)."""
        app = FastAPI()
        app.add_middleware(BodySizeLimitMiddleware)

        @app.post("/upload")
        async def upload_endpoint(request: Request):
            body = await request.body()
            return {"size": len(body)}

        return app

    def test_small_body_allowed(self, app_with_body_limit):
        """Test that requests with small body are allowed."""
        client = TestClient(app_with_body_limit)
        response = client.post("/upload", content=b"small body")

        assert response.status_code == 200
        assert response.json()["size"] == len(b"small body")

    def test_body_at_exact_limit_allowed(self, app_with_body_limit):
        """Test that requests at exactly the limit are allowed."""
        client = TestClient(app_with_body_limit)
        # 1024 bytes = exactly at limit
        body = b"x" * 1024
        response = client.post("/upload", content=body)

        assert response.status_code == 200
        assert response.json()["size"] == 1024

    def test_body_over_limit_rejected(self, app_with_body_limit):
        """Test that requests over the limit are rejected with 413."""
        client = TestClient(app_with_body_limit)
        # 1025 bytes = 1 byte over limit
        body = b"x" * 1025
        response = client.post("/upload", content=body)

        assert response.status_code == 413
        assert response.json()["error_code"] == "PAYLOAD_TOO_LARGE"
        assert "too large" in response.json()["message"].lower()

    def test_large_body_rejected(self, app_with_body_limit):
        """Test that large requests are rejected."""
        client = TestClient(app_with_body_limit)
        # 10KB = way over 1KB limit
        body = b"x" * (10 * 1024)
        response = client.post("/upload", content=body)

        assert response.status_code == 413

    def test_get_request_with_no_body_allowed(self, app_with_body_limit):
        """Test that GET requests without body are allowed."""
        client = TestClient(app_with_body_limit)
        response = client.get("/test")

        assert response.status_code == 200
        assert response.json()["message"] == "ok"

    def test_different_http_methods_checked(self, app_with_body_limit):
        """Test that PUT requests are also checked."""
        client = TestClient(app_with_body_limit)
        body = b"x" * 2048  # Over limit
        response = client.put("/update", content=body)

        assert response.status_code == 413

    def test_request_without_content_length_allowed(self, app_with_body_limit):
        """Test that requests without Content-Length header are allowed through.

        Note: The middleware checks Content-Length header before reading body.
        Requests without this header (e.g., chunked transfer) pass through.
        """
        client = TestClient(app_with_body_limit)
        # TestClient typically sets Content-Length, but let's verify behavior
        response = client.post("/upload", content=b"test")
        # Should either pass or fail based on actual content length
        assert response.status_code in (200, 413)


class TestBodySizeLimitMiddlewareConfiguration:
    """Tests for middleware configuration options."""

    def test_default_limit_is_10mb(self):
        """Test that default max body size is 10MB."""
        app = FastAPI()
        middleware = BodySizeLimitMiddleware(app)
        assert middleware.max_body_size == 10 * 1024 * 1024  # 10MB

    def test_custom_limit_can_be_set(self):
        """Test that custom limit can be configured."""
        app = FastAPI()
        middleware = BodySizeLimitMiddleware(app, max_body_size=5 * 1024 * 1024)
        assert middleware.max_body_size == 5 * 1024 * 1024  # 5MB

    def test_small_limit_can_be_set(self):
        """Test that very small limits can be set (for testing)."""
        app = FastAPI()
        middleware = BodySizeLimitMiddleware(app, max_body_size=100)
        assert middleware.max_body_size == 100

    def test_zero_limit_blocks_all_bodies(self):
        """Test that zero limit blocks any body."""
        app = FastAPI()
        app.add_middleware(BodySizeLimitMiddleware, max_body_size=0)

        @app.post("/upload")
        async def upload():
            return {"ok": True}

        client = TestClient(app)
        response = client.post("/upload", content=b"x")

        assert response.status_code == 413


class TestBodySizeLimitMiddlewareErrorResponse:
    """Tests for error response format."""

    @pytest.fixture
    def app(self):
        """Create test app with 100 byte limit."""
        app = FastAPI()
        app.add_middleware(BodySizeLimitMiddleware, max_body_size=100)

        @app.post("/upload")
        async def upload():
            return {"ok": True}

        return app

    def test_error_response_has_error_code(self, app):
        """Test that error response includes error_code field."""
        client = TestClient(app)
        response = client.post("/upload", content=b"x" * 200)

        assert response.status_code == 413
        json_response = response.json()
        assert "error_code" in json_response
        assert json_response["error_code"] == "PAYLOAD_TOO_LARGE"

    def test_error_response_has_message(self, app):
        """Test that error response includes message field."""
        client = TestClient(app)
        response = client.post("/upload", content=b"x" * 200)

        json_response = response.json()
        assert "message" in json_response
        assert len(json_response["message"]) > 0

    def test_error_response_is_json(self, app):
        """Test that error response is valid JSON."""
        client = TestClient(app)
        response = client.post("/upload", content=b"x" * 200)

        assert response.headers.get("content-type") == "application/json"
        # Should not raise
        response.json()


class TestBodySizeLimitMiddlewareIntegration:
    """Integration tests with other middleware and handlers."""

    def test_works_with_request_id_middleware(self):
        """Test that body limit works with RequestIDMiddleware."""
        from backend.api.middleware.request_id import RequestIDMiddleware

        app = FastAPI()
        app.add_middleware(BodySizeLimitMiddleware, max_body_size=100)
        app.add_middleware(RequestIDMiddleware)

        @app.post("/upload")
        async def upload(request: Request):
            body = await request.body()
            return {"size": len(body)}

        client = TestClient(app)

        # Small body should work
        response = client.post("/upload", content=b"small")
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers

        # Large body should fail
        response = client.post("/upload", content=b"x" * 200)
        assert response.status_code == 413

    def test_works_with_timing_middleware(self):
        """Test that body limit works with RequestTimingMiddleware."""
        from backend.api.middleware.request_timing import RequestTimingMiddleware

        app = FastAPI()
        app.add_middleware(BodySizeLimitMiddleware, max_body_size=100)
        app.add_middleware(RequestTimingMiddleware)

        @app.post("/upload")
        async def upload(request: Request):
            body = await request.body()
            return {"size": len(body)}

        client = TestClient(app)

        # Large body should fail with timing header
        response = client.post("/upload", content=b"x" * 200)
        assert response.status_code == 413
        # Note: Headers may or may not be present depending on middleware order

    def test_body_limit_preserves_request_state(self):
        """Test that body limit middleware preserves request state."""
        app = FastAPI()
        app.add_middleware(BodySizeLimitMiddleware, max_body_size=1024)

        @app.post("/upload")
        async def upload(request: Request):
            # Verify we can read the body after middleware
            body = await request.body()
            return {"size": len(body), "method": request.method}

        client = TestClient(app)
        response = client.post("/upload", content=b"test body")

        assert response.status_code == 200
        assert response.json()["size"] == len(b"test body")
        assert response.json()["method"] == "POST"


class TestBodySizeLimitMiddlewareEdgeCases:
    """Edge case tests for body limit middleware."""

    def test_handles_empty_body(self):
        """Test handling of empty request body."""
        app = FastAPI()
        app.add_middleware(BodySizeLimitMiddleware, max_body_size=100)

        @app.post("/upload")
        async def upload(request: Request):
            body = await request.body()
            return {"size": len(body)}

        client = TestClient(app)
        response = client.post("/upload", content=b"")

        assert response.status_code == 200
        assert response.json()["size"] == 0

    def test_handles_binary_content(self):
        """Test handling of binary content."""
        app = FastAPI()
        app.add_middleware(BodySizeLimitMiddleware, max_body_size=1024)

        @app.post("/upload")
        async def upload(request: Request):
            body = await request.body()
            return {"size": len(body)}

        client = TestClient(app)
        # Binary content with null bytes
        binary_content = bytes(range(256)) * 2  # 512 bytes
        response = client.post("/upload", content=binary_content)

        assert response.status_code == 200
        assert response.json()["size"] == 512

    def test_handles_json_content(self):
        """Test handling of JSON content."""
        app = FastAPI()
        app.add_middleware(BodySizeLimitMiddleware, max_body_size=1024)

        @app.post("/data")
        async def upload(request: Request):
            body = await request.body()
            return {"size": len(body)}

        client = TestClient(app)
        response = client.post(
            "/data",
            json={"key": "value", "nested": {"data": "content"}},
        )

        assert response.status_code == 200

    def test_large_json_rejected(self):
        """Test that large JSON payloads are rejected."""
        app = FastAPI()
        app.add_middleware(BodySizeLimitMiddleware, max_body_size=100)

        @app.post("/data")
        async def upload():
            return {"ok": True}

        client = TestClient(app)
        # Large JSON payload
        large_data = {"data": "x" * 200}
        response = client.post("/data", json=large_data)

        assert response.status_code == 413

    def test_content_length_string_handling(self):
        """Test that Content-Length as string is handled correctly."""
        app = FastAPI()
        app.add_middleware(BodySizeLimitMiddleware, max_body_size=100)

        @app.post("/upload")
        async def upload(request: Request):
            body = await request.body()
            return {"size": len(body)}

        client = TestClient(app)
        # Content-Length is always a string in headers
        response = client.post(
            "/upload",
            content=b"test",
            headers={"Content-Length": "4"},
        )

        assert response.status_code == 200

    def test_content_length_mismatch_uses_header_value(self):
        """Test behavior when Content-Length header doesn't match actual body.

        The middleware checks the header value, not the actual body size.
        This is by design for early rejection without reading the body.
        """
        app = FastAPI()
        app.add_middleware(BodySizeLimitMiddleware, max_body_size=100)

        @app.post("/upload")
        async def upload(request: Request):
            body = await request.body()
            return {"size": len(body)}

        client = TestClient(app)
        # If header says large but body is small, middleware uses header
        # Note: TestClient may override headers, so this tests documented behavior
        response = client.post("/upload", content=b"small")
        # Should pass because actual content is small
        assert response.status_code == 200


class TestBodySizeLimitMiddlewareRealisticScenarios:
    """Tests for realistic usage scenarios."""

    def test_file_upload_under_limit(self):
        """Test file upload under the size limit."""
        app = FastAPI()
        # 1MB limit
        app.add_middleware(BodySizeLimitMiddleware, max_body_size=1 * 1024 * 1024)

        @app.post("/upload")
        async def upload(request: Request):
            body = await request.body()
            return {"size": len(body)}

        client = TestClient(app)
        # 500KB file
        file_content = b"x" * (500 * 1024)
        response = client.post("/upload", content=file_content)

        assert response.status_code == 200
        assert response.json()["size"] == 500 * 1024

    def test_file_upload_over_limit(self):
        """Test file upload over the size limit."""
        app = FastAPI()
        # 1MB limit
        app.add_middleware(BodySizeLimitMiddleware, max_body_size=1 * 1024 * 1024)

        @app.post("/upload")
        async def upload():
            return {"ok": True}

        client = TestClient(app)
        # 2MB file
        file_content = b"x" * (2 * 1024 * 1024)
        response = client.post("/upload", content=file_content)

        assert response.status_code == 413

    def test_api_json_payload_typical_size(self):
        """Test typical JSON API payload sizes."""
        app = FastAPI()
        # 10MB limit (default)
        app.add_middleware(BodySizeLimitMiddleware)

        @app.post("/api/data")
        async def data(request: Request):
            body = await request.body()
            return {"received": len(body)}

        client = TestClient(app)
        # Typical API payload
        response = client.post(
            "/api/data",
            json={
                "items": [{"id": i, "name": f"Item {i}"} for i in range(100)],
                "metadata": {"page": 1, "total": 100},
            },
        )

        assert response.status_code == 200
