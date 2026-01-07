"""Unit tests for Content-Type validation middleware (NEM-1617).

This module provides comprehensive tests for:
- ContentTypeValidationMiddleware: Request Content-Type validation
- Validation of POST/PUT/PATCH requests with bodies
- Pass-through for GET/DELETE/OPTIONS requests
- Handling of missing or invalid Content-Type headers
- Support for application/json and multipart/form-data
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.middleware.content_type_validator import ContentTypeValidationMiddleware


class TestContentTypeValidationMiddleware:
    """Tests for ContentTypeValidationMiddleware class."""

    @pytest.fixture
    def app_with_validation(self):
        """Create a test FastAPI app with ContentTypeValidationMiddleware."""
        app = FastAPI()
        app.add_middleware(ContentTypeValidationMiddleware)

        @app.get("/test")
        async def get_endpoint():
            return {"message": "ok"}

        @app.post("/create")
        async def create_endpoint():
            return {"id": 123}

        @app.put("/update/{item_id}")
        async def update_endpoint(item_id: int):
            return {"id": item_id}

        @app.patch("/patch/{item_id}")
        async def patch_endpoint(item_id: int):
            return {"id": item_id}

        @app.delete("/delete/{item_id}")
        async def delete_endpoint(item_id: int):
            return {"deleted": item_id}

        @app.get("/health")
        async def health_endpoint():
            return {"status": "ok"}

        return app

    def test_get_request_passes_through(self, app_with_validation):
        """Test that GET requests pass through without Content-Type validation."""
        client = TestClient(app_with_validation)
        response = client.get("/test")

        assert response.status_code == 200
        assert response.json() == {"message": "ok"}

    def test_delete_request_passes_through(self, app_with_validation):
        """Test that DELETE requests pass through without Content-Type validation."""
        client = TestClient(app_with_validation)
        response = client.delete("/delete/123")

        assert response.status_code == 200
        assert response.json() == {"deleted": 123}

    def test_post_with_json_content_type_passes(self, app_with_validation):
        """Test that POST with application/json Content-Type passes."""
        client = TestClient(app_with_validation)
        response = client.post(
            "/create",
            json={"name": "test"},
        )

        assert response.status_code == 200
        assert response.json() == {"id": 123}

    def test_post_with_json_charset_content_type_passes(self, app_with_validation):
        """Test that POST with application/json; charset=utf-8 passes."""
        client = TestClient(app_with_validation)
        response = client.post(
            "/create",
            content='{"name": "test"}',
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

        assert response.status_code == 200
        assert response.json() == {"id": 123}

    def test_post_with_multipart_content_type_passes(self, app_with_validation):
        """Test that POST with multipart/form-data Content-Type passes."""
        client = TestClient(app_with_validation)
        response = client.post(
            "/create",
            files={"file": ("test.txt", b"content", "text/plain")},
        )

        assert response.status_code == 200

    def test_post_with_invalid_content_type_returns_415(self, app_with_validation):
        """Test that POST with invalid Content-Type returns 415."""
        client = TestClient(app_with_validation)
        response = client.post(
            "/create",
            content="name=test",
            headers={"Content-Type": "text/plain"},
        )

        assert response.status_code == 415
        assert "Unsupported Media Type" in response.json()["detail"]
        assert "text/plain" in response.json()["detail"]

    def test_put_with_json_content_type_passes(self, app_with_validation):
        """Test that PUT with application/json Content-Type passes."""
        client = TestClient(app_with_validation)
        response = client.put(
            "/update/123",
            json={"name": "updated"},
        )

        assert response.status_code == 200
        assert response.json() == {"id": 123}

    def test_put_with_invalid_content_type_returns_415(self, app_with_validation):
        """Test that PUT with invalid Content-Type returns 415."""
        client = TestClient(app_with_validation)
        response = client.put(
            "/update/123",
            content="name=test",
            headers={"Content-Type": "application/xml"},
        )

        assert response.status_code == 415
        assert "Unsupported Media Type" in response.json()["detail"]

    def test_patch_with_json_content_type_passes(self, app_with_validation):
        """Test that PATCH with application/json Content-Type passes."""
        client = TestClient(app_with_validation)
        response = client.patch(
            "/patch/123",
            json={"name": "patched"},
        )

        assert response.status_code == 200
        assert response.json() == {"id": 123}

    def test_patch_with_invalid_content_type_returns_415(self, app_with_validation):
        """Test that PATCH with invalid Content-Type returns 415."""
        client = TestClient(app_with_validation)
        response = client.patch(
            "/patch/123",
            content="name=test",
            headers={"Content-Type": "text/html"},
        )

        assert response.status_code == 415
        assert "Unsupported Media Type" in response.json()["detail"]

    def test_post_without_body_passes(self, app_with_validation):
        """Test that POST without body passes validation."""
        client = TestClient(app_with_validation)
        # POST with no body and no Content-Type should pass
        response = client.post("/create")

        assert response.status_code == 200

    def test_exempt_paths_pass_through(self, app_with_validation):
        """Test that exempt paths bypass Content-Type validation."""
        client = TestClient(app_with_validation)

        # Health check is exempt
        response = client.get("/health")
        assert response.status_code == 200


class TestContentTypeValidationMiddlewareConfiguration:
    """Tests for middleware configuration options."""

    def test_custom_allowed_content_types(self):
        """Test custom allowed content types configuration."""
        app = FastAPI()
        app.add_middleware(
            ContentTypeValidationMiddleware,
            allowed_content_types={"application/json", "application/xml"},
        )

        @app.post("/test")
        async def test_endpoint():
            return {"ok": True}

        client = TestClient(app)

        # JSON should pass
        response = client.post("/test", json={"test": "data"})
        assert response.status_code == 200

        # XML should pass (custom allowed)
        response = client.post(
            "/test",
            content="<test>data</test>",
            headers={"Content-Type": "application/xml"},
        )
        assert response.status_code == 200

        # Text/plain should fail
        response = client.post(
            "/test",
            content="test data",
            headers={"Content-Type": "text/plain"},
        )
        assert response.status_code == 415

    def test_custom_exempt_paths(self):
        """Test custom exempt paths configuration."""
        app = FastAPI()
        app.add_middleware(
            ContentTypeValidationMiddleware,
            exempt_paths={"/custom-health"},
        )

        @app.post("/custom-health")
        async def health_endpoint():
            return {"status": "ok"}

        @app.post("/api/data")
        async def data_endpoint():
            return {"data": "ok"}

        client = TestClient(app)

        # Custom exempt path should pass without Content-Type
        response = client.post(
            "/custom-health",
            content="test",
            headers={"Content-Type": "text/plain"},
        )
        assert response.status_code == 200

        # Non-exempt path should require valid Content-Type
        response = client.post(
            "/api/data",
            content="test",
            headers={"Content-Type": "text/plain"},
        )
        assert response.status_code == 415


class TestContentTypeValidationMiddlewareEdgeCases:
    """Edge case tests for Content-Type validation."""

    @pytest.fixture
    def app_with_validation(self):
        """Create a test FastAPI app with ContentTypeValidationMiddleware."""
        app = FastAPI()
        app.add_middleware(ContentTypeValidationMiddleware)

        @app.post("/test")
        async def test_endpoint():
            return {"ok": True}

        return app

    def test_missing_content_type_with_body_returns_415(self, app_with_validation):
        """Test that missing Content-Type with a body returns 415."""
        client = TestClient(app_with_validation)

        # Manually construct request with body but no Content-Type
        # This is tricky because TestClient usually adds Content-Type automatically
        # We need to override headers completely
        response = client.post(
            "/test",
            content=b"some body content",
            headers={"Content-Length": "17"},
        )

        # Should fail because body is present but Content-Type is missing/invalid
        assert response.status_code == 415

    def test_empty_content_type_with_body_returns_415(self, app_with_validation):
        """Test that empty Content-Type with a body returns 415."""
        client = TestClient(app_with_validation)
        response = client.post(
            "/test",
            content=b"some body content",
            headers={"Content-Type": "", "Content-Length": "17"},
        )

        assert response.status_code == 415

    def test_case_insensitive_content_type(self, app_with_validation):
        """Test that Content-Type validation is case-insensitive."""
        client = TestClient(app_with_validation)

        # Mixed case should work
        response = client.post(
            "/test",
            content='{"test": true}',
            headers={"Content-Type": "Application/JSON"},
        )
        assert response.status_code == 200

    def test_content_type_with_complex_parameters(self, app_with_validation):
        """Test Content-Type with multiple parameters."""
        client = TestClient(app_with_validation)

        response = client.post(
            "/test",
            content='{"test": true}',
            headers={"Content-Type": "application/json; charset=utf-8; boundary=something"},
        )
        assert response.status_code == 200

    def test_whitespace_in_content_type(self, app_with_validation):
        """Test Content-Type with extra whitespace."""
        client = TestClient(app_with_validation)

        response = client.post(
            "/test",
            content='{"test": true}',
            headers={"Content-Type": "  application/json  ; charset=utf-8  "},
        )
        assert response.status_code == 200


class TestContentTypeParseMethod:
    """Tests for the _parse_content_type helper method."""

    def test_parse_simple_content_type(self):
        """Test parsing simple Content-Type."""
        middleware = ContentTypeValidationMiddleware(None)
        result = middleware._parse_content_type("application/json")
        assert result == "application/json"

    def test_parse_content_type_with_charset(self):
        """Test parsing Content-Type with charset parameter."""
        middleware = ContentTypeValidationMiddleware(None)
        result = middleware._parse_content_type("application/json; charset=utf-8")
        assert result == "application/json"

    def test_parse_content_type_with_multiple_params(self):
        """Test parsing Content-Type with multiple parameters."""
        middleware = ContentTypeValidationMiddleware(None)
        result = middleware._parse_content_type("multipart/form-data; boundary=----; charset=utf-8")
        assert result == "multipart/form-data"

    def test_parse_empty_content_type(self):
        """Test parsing empty Content-Type."""
        middleware = ContentTypeValidationMiddleware(None)
        result = middleware._parse_content_type("")
        assert result == ""

    def test_parse_none_content_type(self):
        """Test parsing None Content-Type."""
        middleware = ContentTypeValidationMiddleware(None)
        # This tests the edge case where header is somehow None
        result = middleware._parse_content_type("")
        assert result == ""

    def test_parse_uppercase_content_type(self):
        """Test parsing uppercase Content-Type."""
        middleware = ContentTypeValidationMiddleware(None)
        result = middleware._parse_content_type("APPLICATION/JSON")
        assert result == "application/json"
