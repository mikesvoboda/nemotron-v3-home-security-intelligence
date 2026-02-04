"""Unit tests for /api/zones redirect to /api/analytics-zones.

Tests the redirect endpoints:
- GET /api/zones -> 308 redirect to /api/analytics-zones/
- GET /api/zones/{path} -> 308 redirect to /api/analytics-zones/{path}
- All HTTP methods supported (GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS)
- Query string preservation

NEM-5377: Add backward compatibility redirect from /api/zones to /api/analytics-zones.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import status


class TestZonesRedirect:
    """Tests for /api/zones redirect endpoints."""

    @pytest.mark.asyncio
    async def test_redirect_root_path(self) -> None:
        """Test /api/zones redirects to /api/analytics-zones/."""
        from backend.api.routes.analytics_zones import zones_redirect

        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/api/zones"
        mock_request.url.query = ""

        response = await zones_redirect(request=mock_request, path="")

        assert response.status_code == status.HTTP_308_PERMANENT_REDIRECT
        assert response.headers["location"] == "/api/analytics-zones/"

    @pytest.mark.asyncio
    async def test_redirect_with_path(self) -> None:
        """Test /api/zones/line-zones redirects to /api/analytics-zones/line-zones."""
        from backend.api.routes.analytics_zones import zones_redirect

        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/api/zones/line-zones"
        mock_request.url.query = ""

        response = await zones_redirect(request=mock_request, path="line-zones")

        assert response.status_code == status.HTTP_308_PERMANENT_REDIRECT
        assert response.headers["location"] == "/api/analytics-zones/line-zones"

    @pytest.mark.asyncio
    async def test_redirect_preserves_query_string(self) -> None:
        """Test redirect preserves query string parameters."""
        from backend.api.routes.analytics_zones import zones_redirect

        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/api/zones/polygon-zones"
        mock_request.url.query = "camera_id=front_door&active_only=true"

        response = await zones_redirect(request=mock_request, path="polygon-zones")

        assert response.status_code == status.HTTP_308_PERMANENT_REDIRECT
        expected_location = (
            "/api/analytics-zones/polygon-zones?camera_id=front_door&active_only=true"
        )
        assert response.headers["location"] == expected_location

    @pytest.mark.asyncio
    async def test_redirect_with_nested_path(self) -> None:
        """Test redirect works with nested paths."""
        from backend.api.routes.analytics_zones import zones_redirect

        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/api/zones/polygon-zones/123/dwellers"
        mock_request.url.query = ""

        response = await zones_redirect(request=mock_request, path="polygon-zones/123/dwellers")

        assert response.status_code == status.HTTP_308_PERMANENT_REDIRECT
        assert response.headers["location"] == "/api/analytics-zones/polygon-zones/123/dwellers"

    @pytest.mark.asyncio
    async def test_redirect_uses_308_status(self) -> None:
        """Test redirect uses HTTP 308 Permanent Redirect to preserve method."""
        from backend.api.routes.analytics_zones import zones_redirect

        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_request.url.path = "/api/zones/line-zones"
        mock_request.url.query = ""

        response = await zones_redirect(request=mock_request, path="line-zones")

        # HTTP 308 preserves the request method (unlike 301/302 which may convert to GET)
        assert response.status_code == status.HTTP_308_PERMANENT_REDIRECT

    @pytest.mark.asyncio
    async def test_redirect_router_exists(self) -> None:
        """Test that zones_redirect_router is properly exported."""
        from backend.api.routes.analytics_zones import zones_redirect_router

        assert zones_redirect_router is not None
        assert zones_redirect_router.prefix == "/api/zones"

    @pytest.mark.asyncio
    async def test_redirect_router_not_in_schema(self) -> None:
        """Test that zones_redirect_router is excluded from OpenAPI schema."""
        from backend.api.routes.analytics_zones import zones_redirect_router

        # The router has include_in_schema=False
        # We can verify this by checking the routes
        for route in zones_redirect_router.routes:
            # All routes in this router should have include_in_schema=False
            assert getattr(route, "include_in_schema", True) is False


class TestZonesRedirectIntegration:
    """Integration-style tests using FastAPI TestClient."""

    def test_redirect_via_test_client(self) -> None:
        """Test redirect works via TestClient (without following redirects)."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from backend.api.routes.analytics_zones import zones_redirect_router

        # Create minimal app with just the redirect router
        app = FastAPI()
        app.include_router(zones_redirect_router)

        client = TestClient(app, follow_redirects=False)

        # Test root redirect
        response = client.get("/api/zones")
        assert response.status_code == status.HTTP_308_PERMANENT_REDIRECT
        assert response.headers["location"] == "/api/analytics-zones/"

    def test_redirect_with_path_via_test_client(self) -> None:
        """Test redirect with path via TestClient."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from backend.api.routes.analytics_zones import zones_redirect_router

        app = FastAPI()
        app.include_router(zones_redirect_router)

        client = TestClient(app, follow_redirects=False)

        response = client.get("/api/zones/line-zones/123")
        assert response.status_code == status.HTTP_308_PERMANENT_REDIRECT
        assert response.headers["location"] == "/api/analytics-zones/line-zones/123"

    def test_redirect_post_method(self) -> None:
        """Test POST requests are redirected correctly."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from backend.api.routes.analytics_zones import zones_redirect_router

        app = FastAPI()
        app.include_router(zones_redirect_router)

        client = TestClient(app, follow_redirects=False)

        response = client.post("/api/zones/line-zones", json={"name": "test"})
        assert response.status_code == status.HTTP_308_PERMANENT_REDIRECT
        assert response.headers["location"] == "/api/analytics-zones/line-zones"

    def test_redirect_with_query_params(self) -> None:
        """Test redirect preserves query parameters."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from backend.api.routes.analytics_zones import zones_redirect_router

        app = FastAPI()
        app.include_router(zones_redirect_router)

        client = TestClient(app, follow_redirects=False)

        response = client.get("/api/zones/polygon-zones?camera_id=cam1&active=true")
        assert response.status_code == status.HTTP_308_PERMANENT_REDIRECT
        assert "camera_id=cam1" in response.headers["location"]
        assert "active=true" in response.headers["location"]
