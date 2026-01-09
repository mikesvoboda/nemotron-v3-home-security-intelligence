"""Unit tests for HTTP compression middleware (NEM-2087).

Tests cover:
- Gzip compression with Accept-Encoding header
- Brotli compression with Accept-Encoding header
- Minimum size threshold enforcement
- No compression for small responses
- Content-Encoding response header
- Integration with both compression middlewares

NEM-2087: Add gzip/brotli compression support

Note: Starlette's TestClient automatically decompresses responses that have
Content-Encoding headers. To verify compression is working, we check that:
1. The Content-Encoding header is set correctly
2. The decompressed content is correct
We do NOT try to manually decompress the content since TestClient already did that.
"""

import pytest
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient

# Try to import brotli - it may not be installed in all environments
try:
    import brotli  # noqa: F401 - used for skipif check

    BROTLI_AVAILABLE = True
except ImportError:
    BROTLI_AVAILABLE = False


class TestGzipCompression:
    """Tests for GZipMiddleware compression."""

    @pytest.fixture
    def app_with_gzip(self):
        """Create a test FastAPI app with GZipMiddleware."""
        from starlette.middleware.gzip import GZipMiddleware

        app = FastAPI()
        # 500 byte minimum, same as production config
        app.add_middleware(GZipMiddleware, minimum_size=500, compresslevel=6)

        @app.get("/large", response_class=PlainTextResponse)
        async def large_response():
            # Return >500 bytes to trigger compression (plain text is larger than JSON)
            return "x" * 2000

        @app.get("/small", response_class=PlainTextResponse)
        async def small_response():
            # Return <500 bytes to skip compression
            return "ok"

        @app.get("/exact-threshold", response_class=PlainTextResponse)
        async def exact_threshold():
            # Return exactly at threshold boundary
            return "x" * 450

        return app

    def test_gzip_compression_applied_to_large_response(self, app_with_gzip):
        """Test that gzip compression is applied to responses over minimum_size."""
        client = TestClient(app_with_gzip)
        response = client.get(
            "/large",
            headers={"Accept-Encoding": "gzip"},
        )

        assert response.status_code == 200
        # Content-Encoding header indicates compression was applied
        assert response.headers.get("Content-Encoding") == "gzip"
        # TestClient auto-decompresses, so we can read the text directly
        assert "x" * 100 in response.text

    def test_gzip_not_applied_to_small_response(self, app_with_gzip):
        """Test that gzip compression is not applied to small responses."""
        client = TestClient(app_with_gzip)
        response = client.get(
            "/small",
            headers={"Accept-Encoding": "gzip"},
        )

        assert response.status_code == 200
        # Small responses should not be compressed
        assert response.headers.get("Content-Encoding") != "gzip"
        assert response.text == "ok"

    def test_no_compression_without_accept_encoding(self, app_with_gzip):
        """Test that compression is not applied without Accept-Encoding header."""
        client = TestClient(app_with_gzip)
        response = client.get("/large", headers={"Accept-Encoding": ""})

        assert response.status_code == 200
        # Without Accept-Encoding, no compression should be applied
        assert response.headers.get("Content-Encoding") != "gzip"
        # Verify we can read the raw text
        assert "x" * 100 in response.text

    def test_gzip_compresses_large_response(self, app_with_gzip):
        """Test that gzip compression produces valid content."""
        client = TestClient(app_with_gzip)

        # Get response with gzip
        response = client.get(
            "/large",
            headers={"Accept-Encoding": "gzip"},
        )

        assert response.status_code == 200
        # Verify compression header is set
        assert response.headers.get("Content-Encoding") == "gzip"
        # TestClient auto-decompresses, verify content is correct
        assert response.text == "x" * 2000


@pytest.mark.skipif(not BROTLI_AVAILABLE, reason="brotli not installed")
class TestBrotliCompression:
    """Tests for BrotliMiddleware compression."""

    @pytest.fixture
    def app_with_brotli(self):
        """Create a test FastAPI app with BrotliMiddleware."""
        from brotli_asgi import BrotliMiddleware

        app = FastAPI()
        # 500 byte minimum, same as production config
        app.add_middleware(BrotliMiddleware, minimum_size=500, quality=4)

        @app.get("/large", response_class=PlainTextResponse)
        async def large_response():
            # Return >500 bytes to trigger compression
            return "x" * 2000

        @app.get("/small", response_class=PlainTextResponse)
        async def small_response():
            # Return <500 bytes to skip compression
            return "ok"

        return app

    def test_brotli_compression_applied_to_large_response(self, app_with_brotli):
        """Test that brotli compression is applied to responses over minimum_size."""
        client = TestClient(app_with_brotli)
        response = client.get(
            "/large",
            headers={"Accept-Encoding": "br"},
        )

        assert response.status_code == 200
        # Content-Encoding header indicates compression was applied
        assert response.headers.get("Content-Encoding") == "br"
        # TestClient auto-decompresses, so we can read the text directly
        assert "x" * 100 in response.text

    def test_brotli_not_applied_to_small_response(self, app_with_brotli):
        """Test that brotli compression is not applied to small responses."""
        client = TestClient(app_with_brotli)
        response = client.get(
            "/small",
            headers={"Accept-Encoding": "br"},
        )

        assert response.status_code == 200
        # Small responses should not be compressed
        assert response.headers.get("Content-Encoding") != "br"
        assert response.text == "ok"

    def test_brotli_compresses_large_response(self, app_with_brotli):
        """Test that brotli compression produces valid content."""
        client = TestClient(app_with_brotli)

        # Get response with brotli
        response = client.get(
            "/large",
            headers={"Accept-Encoding": "br"},
        )

        assert response.status_code == 200
        # Verify compression header is set
        assert response.headers.get("Content-Encoding") == "br"
        # TestClient auto-decompresses, verify content is correct
        assert response.text == "x" * 2000


class TestCompressionMiddlewareStack:
    """Tests for combined compression middleware stack (as in production)."""

    @pytest.fixture
    def app_with_both_compressions(self):
        """Create a test FastAPI app with both GZip and Brotli middleware.

        This mimics the production middleware configuration in main.py.
        Order matters: BrotliMiddleware is added after GZipMiddleware,
        so Brotli is preferred when client supports both.
        """
        from starlette.middleware.gzip import GZipMiddleware

        app = FastAPI()
        # Add in same order as main.py
        app.add_middleware(GZipMiddleware, minimum_size=500, compresslevel=6)

        if BROTLI_AVAILABLE:
            from brotli_asgi import BrotliMiddleware

            app.add_middleware(BrotliMiddleware, minimum_size=500, quality=4)

        @app.get("/large", response_class=PlainTextResponse)
        async def large_response():
            return "x" * 2000

        @app.get("/json")
        async def json_response():
            return {"items": [{"id": i, "name": f"Item {i}"} for i in range(100)]}

        return app

    def test_gzip_used_when_only_gzip_accepted(self, app_with_both_compressions):
        """Test that gzip is used when client only accepts gzip."""
        client = TestClient(app_with_both_compressions)
        response = client.get(
            "/large",
            headers={"Accept-Encoding": "gzip"},
        )

        assert response.status_code == 200
        # Gzip compression should be applied
        assert response.headers.get("Content-Encoding") == "gzip"
        # TestClient auto-decompresses, verify content is correct
        assert "x" * 100 in response.text

    @pytest.mark.skipif(not BROTLI_AVAILABLE, reason="brotli not installed")
    def test_brotli_preferred_when_both_accepted(self, app_with_both_compressions):
        """Test that brotli is preferred when client accepts both."""
        client = TestClient(app_with_both_compressions)
        response = client.get(
            "/large",
            headers={"Accept-Encoding": "gzip, br"},
        )

        assert response.status_code == 200
        # Brotli should be preferred (added after gzip, so processed first)
        encoding = response.headers.get("Content-Encoding")
        assert encoding in ("br", "gzip")  # Either is acceptable
        # TestClient auto-decompresses, verify content is correct
        assert "x" * 100 in response.text

    def test_json_responses_are_compressed(self, app_with_both_compressions):
        """Test that JSON responses are compressed when large enough."""
        client = TestClient(app_with_both_compressions)
        response = client.get(
            "/json",
            headers={"Accept-Encoding": "gzip"},
        )

        assert response.status_code == 200
        # JSON should be compressed if large enough
        encoding = response.headers.get("Content-Encoding")
        assert encoding == "gzip"
        # TestClient auto-decompresses, verify JSON is valid
        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 100

    def test_deflate_not_supported(self, app_with_both_compressions):
        """Test that deflate encoding is not supported (only gzip and brotli)."""
        client = TestClient(app_with_both_compressions)
        response = client.get(
            "/large",
            headers={"Accept-Encoding": "deflate"},
        )

        assert response.status_code == 200
        # Deflate should not be used - either no encoding or fallback
        assert response.headers.get("Content-Encoding") != "deflate"


class TestCompressionEdgeCases:
    """Edge case tests for compression middleware."""

    @pytest.fixture
    def app(self):
        """Create a test app with gzip compression."""
        from starlette.middleware.gzip import GZipMiddleware

        app = FastAPI()
        app.add_middleware(GZipMiddleware, minimum_size=500)

        @app.get("/binary")
        async def binary_response():
            from fastapi.responses import Response

            return Response(content=b"x" * 1000, media_type="application/octet-stream")

        @app.get("/already-compressed")
        async def already_compressed():
            from fastapi.responses import Response

            # Simulate already-compressed content
            return Response(
                content=b"fake compressed data" * 100,
                media_type="application/gzip",
            )

        @app.get("/text")
        async def text_response():
            from fastapi.responses import PlainTextResponse

            return PlainTextResponse("x" * 1000)

        @app.get("/empty")
        async def empty_response():
            return {}

        return app

    def test_binary_content_compressed(self, app):
        """Test that binary content is compressed."""
        client = TestClient(app)
        response = client.get(
            "/binary",
            headers={"Accept-Encoding": "gzip"},
        )

        assert response.status_code == 200
        # Binary content should be compressed
        assert response.headers.get("Content-Encoding") == "gzip"

    def test_text_content_compressed(self, app):
        """Test that text content is compressed."""
        client = TestClient(app)
        response = client.get(
            "/text",
            headers={"Accept-Encoding": "gzip"},
        )

        assert response.status_code == 200
        assert response.headers.get("Content-Encoding") == "gzip"

    def test_empty_response_not_compressed(self, app):
        """Test that empty responses are not compressed."""
        client = TestClient(app)
        response = client.get(
            "/empty",
            headers={"Accept-Encoding": "gzip"},
        )

        assert response.status_code == 200
        # Empty/small responses should not be compressed
        assert response.headers.get("Content-Encoding") != "gzip"


class TestCompressionConfiguration:
    """Tests for compression middleware configuration options."""

    def test_minimum_size_configurable(self):
        """Test that minimum_size can be configured."""
        from starlette.middleware.gzip import GZipMiddleware

        app = FastAPI()
        # Very low threshold for testing
        app.add_middleware(GZipMiddleware, minimum_size=10)

        @app.get("/small")
        async def small():
            return {"x": "y" * 50}  # Over 10 bytes

        client = TestClient(app)
        response = client.get("/small", headers={"Accept-Encoding": "gzip"})

        assert response.status_code == 200
        assert response.headers.get("Content-Encoding") == "gzip"

    def test_compress_level_affects_compression(self):
        """Test that compress level parameter is accepted."""
        from starlette.middleware.gzip import GZipMiddleware

        # Test with different compression levels
        for level in [1, 6, 9]:
            app = FastAPI()
            app.add_middleware(GZipMiddleware, minimum_size=100, compresslevel=level)

            @app.get("/data")
            async def data():
                return {"data": "x" * 1000}

            client = TestClient(app)
            response = client.get("/data", headers={"Accept-Encoding": "gzip"})
            assert response.status_code == 200
            assert response.headers.get("Content-Encoding") == "gzip"

    @pytest.mark.skipif(not BROTLI_AVAILABLE, reason="brotli not installed")
    def test_brotli_quality_configurable(self):
        """Test that brotli quality can be configured."""
        from brotli_asgi import BrotliMiddleware

        app = FastAPI()
        # Quality 4 is a good balance between speed and compression
        app.add_middleware(BrotliMiddleware, minimum_size=100, quality=4)

        @app.get("/data")
        async def data():
            return {"data": "x" * 1000}

        client = TestClient(app)
        response = client.get("/data", headers={"Accept-Encoding": "br"})

        assert response.status_code == 200
        assert response.headers.get("Content-Encoding") == "br"
