"""Unit tests for GZipMiddleware integration (NEM-3741).

Tests cover:
- GZip middleware is properly configured
- Response data integrity is preserved
- Small responses are not affected
- Integration with other middleware

Note: TestClient automatically handles gzip decompression, so these tests
verify data integrity and correct middleware configuration rather than
testing the raw gzip bytes (which is already tested by Starlette).
"""

import pytest
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.testclient import TestClient


class TestGZipMiddlewareConfiguration:
    """Tests for GZipMiddleware configuration as used in main.py."""

    @pytest.fixture
    def app_with_gzip(self):
        """Create a test FastAPI app with GZipMiddleware."""
        app = FastAPI()
        # Same configuration as in main.py (NEM-3741)
        app.add_middleware(
            GZipMiddleware,
            minimum_size=1000,  # Only compress responses > 1KB
            compresslevel=5,  # Balance between CPU and compression ratio
        )

        @app.get("/small")
        async def small_endpoint():
            """Return a small response (under compression threshold)."""
            return {"message": "hello"}

        @app.get("/large")
        async def large_endpoint():
            """Return a large response (over compression threshold)."""
            # Generate a response larger than 1000 bytes
            return {"data": "x" * 2000}

        @app.get("/json-list")
        async def json_list_endpoint():
            """Return a list of items that would compress well."""
            return {"items": [{"id": i, "name": f"Item {i}"} for i in range(100)]}

        return app

    def test_small_response_data_integrity(self, app_with_gzip):
        """Test that small responses return correct data."""
        client = TestClient(app_with_gzip)
        response = client.get(
            "/small",
            headers={"Accept-Encoding": "gzip"},
        )

        assert response.status_code == 200
        assert response.json() == {"message": "hello"}

    def test_large_response_data_integrity(self, app_with_gzip):
        """Test that large responses return correct data after compression/decompression."""
        client = TestClient(app_with_gzip)
        response = client.get(
            "/large",
            headers={"Accept-Encoding": "gzip"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"]) == 2000
        assert data["data"] == "x" * 2000

    def test_json_list_response_data_integrity(self, app_with_gzip):
        """Test that JSON list responses maintain data integrity."""
        client = TestClient(app_with_gzip)
        response = client.get(
            "/json-list",
            headers={"Accept-Encoding": "gzip"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 100
        assert data["items"][0] == {"id": 0, "name": "Item 0"}
        assert data["items"][99] == {"id": 99, "name": "Item 99"}

    def test_works_without_accept_encoding(self, app_with_gzip):
        """Test that endpoints work without Accept-Encoding header."""
        client = TestClient(app_with_gzip)
        response = client.get("/large")

        assert response.status_code == 200
        data = response.json()
        assert data["data"] == "x" * 2000


class TestGZipMiddlewareEdgeCases:
    """Edge case tests for GZip middleware."""

    @pytest.fixture
    def app(self):
        """Create test app with GZip middleware."""
        app = FastAPI()
        app.add_middleware(GZipMiddleware, minimum_size=100)

        @app.get("/binary")
        async def binary_endpoint():
            from starlette.responses import Response

            return Response(
                content=b"x" * 2000,
                media_type="application/octet-stream",
            )

        @app.get("/empty")
        async def empty_endpoint():
            return {}

        @app.get("/unicode")
        async def unicode_endpoint():
            return {"message": "Hello, World! Emoji: \U0001f600"}

        return app

    def test_binary_content_data_integrity(self, app):
        """Test that binary content is handled correctly."""
        client = TestClient(app)
        response = client.get(
            "/binary",
            headers={"Accept-Encoding": "gzip"},
        )

        assert response.status_code == 200
        assert len(response.content) == 2000
        assert response.content == b"x" * 2000

    def test_empty_response_works(self, app):
        """Test that empty responses work correctly."""
        client = TestClient(app)
        response = client.get(
            "/empty",
            headers={"Accept-Encoding": "gzip"},
        )

        assert response.status_code == 200
        assert response.json() == {}

    def test_unicode_content_preserved(self, app):
        """Test that Unicode content is preserved correctly."""
        client = TestClient(app)
        response = client.get(
            "/unicode",
            headers={"Accept-Encoding": "gzip"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Hello, World! Emoji: \U0001f600"


class TestGZipMiddlewareIntegration:
    """Integration tests for GZip with other middleware."""

    def test_gzip_works_with_cors(self):
        """Test that GZip works alongside CORS middleware."""
        from fastapi.middleware.cors import CORSMiddleware

        app = FastAPI()
        app.add_middleware(GZipMiddleware, minimum_size=100)
        # nosemgrep: python.fastapi.security.wildcard-cors.wildcard-cors
        app.add_middleware(CORSMiddleware, allow_origins=["*"])

        @app.get("/data")
        async def data_endpoint():
            return {"data": "x" * 500}

        client = TestClient(app)
        response = client.get(
            "/data",
            headers={"Accept-Encoding": "gzip", "Origin": "http://localhost:3000"},
        )

        assert response.status_code == 200
        # CORS headers should be present
        assert "access-control-allow-origin" in response.headers
        # Data should be intact
        assert response.json()["data"] == "x" * 500

    def test_gzip_preserves_response_headers(self):
        """Test that custom response headers are preserved with compression."""
        app = FastAPI()
        app.add_middleware(GZipMiddleware, minimum_size=100)

        @app.get("/custom-headers")
        async def custom_headers_endpoint():
            from starlette.responses import JSONResponse

            response = JSONResponse(
                content={"data": "x" * 500},
                headers={"X-Custom-Header": "custom-value"},
            )
            return response

        client = TestClient(app)
        response = client.get(
            "/custom-headers",
            headers={"Accept-Encoding": "gzip"},
        )

        assert response.status_code == 200
        assert response.headers.get("x-custom-header") == "custom-value"
        assert response.json()["data"] == "x" * 500

    def test_gzip_with_body_limit_middleware(self):
        """Test GZip works with BodySizeLimitMiddleware (as in main.py)."""
        from backend.api.middleware.body_limit import BodySizeLimitMiddleware

        app = FastAPI()
        # Order matters - body limit first, then gzip
        app.add_middleware(BodySizeLimitMiddleware, max_body_size=10 * 1024 * 1024)
        app.add_middleware(GZipMiddleware, minimum_size=1000)

        @app.get("/data")
        async def data_endpoint():
            return {"data": "x" * 2000}

        @app.post("/upload")
        async def upload_endpoint():
            return {"received": True}

        client = TestClient(app)

        # GET should work with compression
        get_response = client.get("/data", headers={"Accept-Encoding": "gzip"})
        assert get_response.status_code == 200
        assert get_response.json()["data"] == "x" * 2000

        # POST should also work
        post_response = client.post("/upload", json={"test": "data"})
        assert post_response.status_code == 200
        assert post_response.json()["received"] is True


class TestGZipMiddlewareMinimumSizeConfiguration:
    """Tests for minimum_size threshold behavior."""

    def test_minimum_size_threshold_boundary(self):
        """Test behavior at exact minimum_size boundary."""
        app = FastAPI()
        # Set threshold to exactly 100 bytes
        app.add_middleware(GZipMiddleware, minimum_size=100)

        @app.get("/at-threshold")
        async def at_threshold():
            # Return content that is close to 100 bytes when serialized
            # JSON: {"d": "xxx...x"} = ~100 bytes with enough x's
            return {"d": "x" * 90}  # ~97 bytes serialized

        @app.get("/above-threshold")
        async def above_threshold():
            return {"d": "x" * 200}  # ~207 bytes serialized

        client = TestClient(app)

        # Both should return correct data
        response_at = client.get("/at-threshold", headers={"Accept-Encoding": "gzip"})
        response_above = client.get("/above-threshold", headers={"Accept-Encoding": "gzip"})

        assert response_at.status_code == 200
        assert response_above.status_code == 200
        assert response_at.json()["d"] == "x" * 90
        assert response_above.json()["d"] == "x" * 200

    def test_compression_level_5_is_used(self):
        """Test that the middleware is configured with compression level 5."""
        app = FastAPI()
        middleware = GZipMiddleware(app, minimum_size=1000, compresslevel=5)

        # Verify middleware configuration
        assert middleware.minimum_size == 1000
        assert middleware.compresslevel == 5
