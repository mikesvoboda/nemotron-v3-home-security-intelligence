"""Unit tests for exception handlers including RFC 7807 Problem Details.

Tests cover:
- http_exception_handler returns RFC 7807 Problem Details format
- Various HTTP status codes return correct Problem Details
- Media type is application/problem+json
- Custom HTTPException detail messages are preserved
- Edge cases and error scenarios

NEM-1425: Standardize error response format with RFC 7807 Problem Details
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.testclient import TestClient

from backend.api.exception_handlers import (
    build_error_response,
    get_request_id,
    problem_details_exception_handler,
    register_exception_handlers,
)

# Mark as unit tests - no database required
pytestmark = pytest.mark.unit


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_request() -> MagicMock:
    """Create a mock Request object."""
    # Don't use spec=Request as it makes MagicMock return False in boolean context
    request = MagicMock()
    request.url.path = "/api/test/resource"
    request.method = "GET"
    # Create state with explicit request_id attribute
    state = MagicMock()
    state.request_id = "test-request-id-123"
    request.state = state
    request.headers = {}
    return request


@pytest.fixture
def mock_request_no_id() -> MagicMock:
    """Create a mock Request object without request ID."""
    # Don't use spec=Request as it makes MagicMock return False in boolean context
    request = MagicMock()
    request.url.path = "/api/test/resource"
    request.method = "GET"
    # Simulate missing request_id attribute
    request.state = MagicMock(spec=[])
    request.headers = {}
    return request


@pytest.fixture
def test_app() -> FastAPI:
    """Create a test FastAPI app with exception handlers registered."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/test/404")
    async def raise_404():
        raise HTTPException(status_code=404, detail="Resource not found")

    @app.get("/test/400")
    async def raise_400():
        raise HTTPException(status_code=400, detail="Bad request data")

    @app.get("/test/500")
    async def raise_500():
        raise HTTPException(status_code=500, detail="Internal error")

    @app.get("/test/422")
    async def raise_422():
        raise HTTPException(status_code=422, detail="Validation failed")

    @app.get("/test/503")
    async def raise_503():
        raise HTTPException(status_code=503, detail="Service unavailable")

    @app.get("/test/429")
    async def raise_429():
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    @app.get("/test/no-detail")
    async def raise_no_detail():
        raise HTTPException(status_code=404)

    return app


@pytest.fixture
def client(test_app: FastAPI) -> TestClient:
    """Create a test client with exception handlers."""
    return TestClient(test_app)


# =============================================================================
# problem_details_exception_handler Tests
# =============================================================================


class TestProblemDetailsExceptionHandler:
    """Tests for problem_details_exception_handler function."""

    @pytest.mark.asyncio
    async def test_returns_problem_details_format(self, mock_request: MagicMock):
        """Test that handler returns RFC 7807 Problem Details format."""
        exc = StarletteHTTPException(status_code=404, detail="Camera not found")

        response = await problem_details_exception_handler(mock_request, exc)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 404
        assert response.media_type == "application/problem+json"

        # Verify response body structure
        import json

        body = json.loads(response.body.decode())

        assert body["type"] == "about:blank"
        assert body["title"] == "Not Found"
        assert body["status"] == 404
        assert body["detail"] == "Camera not found"
        assert body["instance"] == "/api/test/resource"

    @pytest.mark.asyncio
    async def test_400_bad_request(self, mock_request: MagicMock):
        """Test 400 Bad Request returns correct Problem Details."""
        exc = StarletteHTTPException(status_code=400, detail="Invalid JSON")

        response = await problem_details_exception_handler(mock_request, exc)

        import json

        body = json.loads(response.body.decode())

        assert response.status_code == 400
        assert body["title"] == "Bad Request"
        assert body["status"] == 400
        assert body["detail"] == "Invalid JSON"

    @pytest.mark.asyncio
    async def test_401_unauthorized(self, mock_request: MagicMock):
        """Test 401 Unauthorized returns correct Problem Details."""
        exc = StarletteHTTPException(status_code=401, detail="Missing API key")

        response = await problem_details_exception_handler(mock_request, exc)

        import json

        body = json.loads(response.body.decode())

        assert response.status_code == 401
        assert body["title"] == "Unauthorized"
        assert body["detail"] == "Missing API key"

    @pytest.mark.asyncio
    async def test_403_forbidden(self, mock_request: MagicMock):
        """Test 403 Forbidden returns correct Problem Details."""
        exc = StarletteHTTPException(status_code=403, detail="Access denied")

        response = await problem_details_exception_handler(mock_request, exc)

        import json

        body = json.loads(response.body.decode())

        assert response.status_code == 403
        assert body["title"] == "Forbidden"
        assert body["detail"] == "Access denied"

    @pytest.mark.asyncio
    async def test_404_not_found(self, mock_request: MagicMock):
        """Test 404 Not Found returns correct Problem Details."""
        exc = StarletteHTTPException(status_code=404, detail="User not found")

        response = await problem_details_exception_handler(mock_request, exc)

        import json

        body = json.loads(response.body.decode())

        assert response.status_code == 404
        assert body["title"] == "Not Found"
        assert body["detail"] == "User not found"

    @pytest.mark.asyncio
    async def test_409_conflict(self, mock_request: MagicMock):
        """Test 409 Conflict returns correct Problem Details."""
        exc = StarletteHTTPException(status_code=409, detail="Resource already exists")

        response = await problem_details_exception_handler(mock_request, exc)

        import json

        body = json.loads(response.body.decode())

        assert response.status_code == 409
        assert body["title"] == "Conflict"
        assert body["detail"] == "Resource already exists"

    @pytest.mark.asyncio
    async def test_422_unprocessable_content(self, mock_request: MagicMock):
        """Test 422 Unprocessable Content returns correct Problem Details."""
        exc = StarletteHTTPException(status_code=422, detail="Validation failed")

        response = await problem_details_exception_handler(mock_request, exc)

        import json

        body = json.loads(response.body.decode())

        assert response.status_code == 422
        assert body["title"] == "Unprocessable Content"
        assert body["detail"] == "Validation failed"

    @pytest.mark.asyncio
    async def test_429_too_many_requests(self, mock_request: MagicMock):
        """Test 429 Too Many Requests returns correct Problem Details."""
        exc = StarletteHTTPException(status_code=429, detail="Rate limit exceeded")

        response = await problem_details_exception_handler(mock_request, exc)

        import json

        body = json.loads(response.body.decode())

        assert response.status_code == 429
        assert body["title"] == "Too Many Requests"
        assert body["detail"] == "Rate limit exceeded"

    @pytest.mark.asyncio
    async def test_500_internal_server_error(self, mock_request: MagicMock):
        """Test 500 Internal Server Error returns correct Problem Details."""
        exc = StarletteHTTPException(status_code=500, detail="Database error")

        response = await problem_details_exception_handler(mock_request, exc)

        import json

        body = json.loads(response.body.decode())

        assert response.status_code == 500
        assert body["title"] == "Internal Server Error"
        assert body["detail"] == "Database error"

    @pytest.mark.asyncio
    async def test_502_bad_gateway(self, mock_request: MagicMock):
        """Test 502 Bad Gateway returns correct Problem Details."""
        exc = StarletteHTTPException(status_code=502, detail="Upstream error")

        response = await problem_details_exception_handler(mock_request, exc)

        import json

        body = json.loads(response.body.decode())

        assert response.status_code == 502
        assert body["title"] == "Bad Gateway"
        assert body["detail"] == "Upstream error"

    @pytest.mark.asyncio
    async def test_503_service_unavailable(self, mock_request: MagicMock):
        """Test 503 Service Unavailable returns correct Problem Details."""
        exc = StarletteHTTPException(status_code=503, detail="AI service down")

        response = await problem_details_exception_handler(mock_request, exc)

        import json

        body = json.loads(response.body.decode())

        assert response.status_code == 503
        assert body["title"] == "Service Unavailable"
        assert body["detail"] == "AI service down"

    @pytest.mark.asyncio
    async def test_504_gateway_timeout(self, mock_request: MagicMock):
        """Test 504 Gateway Timeout returns correct Problem Details."""
        exc = StarletteHTTPException(status_code=504, detail="Request timed out")

        response = await problem_details_exception_handler(mock_request, exc)

        import json

        body = json.loads(response.body.decode())

        assert response.status_code == 504
        assert body["title"] == "Gateway Timeout"
        assert body["detail"] == "Request timed out"

    @pytest.mark.asyncio
    async def test_missing_detail_uses_status_phrase(self, mock_request: MagicMock):
        """Test that missing detail falls back to status phrase."""
        exc = StarletteHTTPException(status_code=404, detail=None)

        response = await problem_details_exception_handler(mock_request, exc)

        import json

        body = json.loads(response.body.decode())

        assert body["detail"] == "Not Found"

    @pytest.mark.asyncio
    async def test_empty_detail_uses_status_phrase(self, mock_request: MagicMock):
        """Test that empty detail falls back to status phrase."""
        exc = StarletteHTTPException(status_code=500, detail="")

        response = await problem_details_exception_handler(mock_request, exc)

        import json

        body = json.loads(response.body.decode())

        # Empty string should use status phrase as fallback
        assert body["detail"] == "Internal Server Error"

    @pytest.mark.asyncio
    async def test_instance_is_request_path(self, mock_request: MagicMock):
        """Test that instance is set to request path."""
        mock_request.url.path = "/api/cameras/front_door"
        exc = StarletteHTTPException(status_code=404, detail="Camera not found")

        response = await problem_details_exception_handler(mock_request, exc)

        import json

        body = json.loads(response.body.decode())

        assert body["instance"] == "/api/cameras/front_door"

    @pytest.mark.asyncio
    async def test_type_is_about_blank(self, mock_request: MagicMock):
        """Test that type is 'about:blank' per RFC 7807."""
        exc = StarletteHTTPException(status_code=404, detail="Not found")

        response = await problem_details_exception_handler(mock_request, exc)

        import json

        body = json.loads(response.body.decode())

        assert body["type"] == "about:blank"

    @pytest.mark.asyncio
    async def test_media_type_is_application_problem_json(self, mock_request: MagicMock):
        """Test that media type is application/problem+json."""
        exc = StarletteHTTPException(status_code=404, detail="Not found")

        response = await problem_details_exception_handler(mock_request, exc)

        assert response.media_type == "application/problem+json"


# =============================================================================
# Integration Tests via TestClient
# =============================================================================


class TestProblemDetailsIntegration:
    """Integration tests for Problem Details via HTTP."""

    def test_404_via_http(self, client: TestClient):
        """Test 404 returns Problem Details via HTTP."""
        response = client.get("/test/404")

        assert response.status_code == 404
        assert response.headers["content-type"] == "application/problem+json"

        body = response.json()
        assert body["type"] == "about:blank"
        assert body["title"] == "Not Found"
        assert body["status"] == 404
        assert body["detail"] == "Resource not found"
        assert "instance" in body

    def test_400_via_http(self, client: TestClient):
        """Test 400 returns Problem Details via HTTP."""
        response = client.get("/test/400")

        assert response.status_code == 400
        assert response.headers["content-type"] == "application/problem+json"

        body = response.json()
        assert body["title"] == "Bad Request"
        assert body["status"] == 400

    def test_500_via_http(self, client: TestClient):
        """Test 500 returns Problem Details via HTTP."""
        response = client.get("/test/500")

        assert response.status_code == 500
        assert response.headers["content-type"] == "application/problem+json"

        body = response.json()
        assert body["title"] == "Internal Server Error"
        assert body["status"] == 500

    def test_422_via_http(self, client: TestClient):
        """Test 422 returns Problem Details via HTTP."""
        response = client.get("/test/422")

        assert response.status_code == 422
        # Note: Pydantic validation errors might override this handler
        # This test is for explicit HTTPException(422)
        body = response.json()
        assert body["status"] == 422

    def test_503_via_http(self, client: TestClient):
        """Test 503 returns Problem Details via HTTP."""
        response = client.get("/test/503")

        assert response.status_code == 503
        assert response.headers["content-type"] == "application/problem+json"

        body = response.json()
        assert body["title"] == "Service Unavailable"
        assert body["status"] == 503

    def test_429_via_http(self, client: TestClient):
        """Test 429 returns Problem Details via HTTP."""
        response = client.get("/test/429")

        assert response.status_code == 429
        assert response.headers["content-type"] == "application/problem+json"

        body = response.json()
        assert body["title"] == "Too Many Requests"
        assert body["status"] == 429

    def test_no_detail_via_http(self, client: TestClient):
        """Test HTTPException without detail via HTTP."""
        response = client.get("/test/no-detail")

        assert response.status_code == 404
        assert response.headers["content-type"] == "application/problem+json"

        body = response.json()
        # Should fall back to status phrase
        assert body["detail"] == "Not Found"


# =============================================================================
# get_request_id Tests
# =============================================================================


class TestGetRequestId:
    """Tests for get_request_id helper function."""

    def test_gets_request_id_from_state(self, mock_request: MagicMock):
        """Test getting request ID from request state."""
        mock_request.state.request_id = "state-request-id"

        result = get_request_id(mock_request)

        assert result == "state-request-id"

    def test_falls_back_to_header(self, mock_request_no_id: MagicMock):
        """Test falling back to X-Request-ID header."""
        mock_request_no_id.headers = {"X-Request-ID": "header-request-id"}

        result = get_request_id(mock_request_no_id)

        assert result == "header-request-id"

    def test_returns_none_when_no_id(self, mock_request_no_id: MagicMock):
        """Test returns None when no request ID available."""
        mock_request_no_id.headers = {}

        result = get_request_id(mock_request_no_id)

        assert result is None


# =============================================================================
# build_error_response Tests (Legacy Format)
# =============================================================================


class TestBuildErrorResponse:
    """Tests for build_error_response helper function (legacy format)."""

    def test_builds_basic_error_response(self):
        """Test building a basic error response."""
        response = build_error_response(
            error_code="NOT_FOUND",
            message="Resource not found",
            status_code=404,
        )

        assert response.status_code == 404

        import json

        body = json.loads(response.body.decode())

        assert body["error"]["code"] == "NOT_FOUND"
        assert body["error"]["message"] == "Resource not found"
        assert "timestamp" in body["error"]

    def test_includes_request_id(self, mock_request: MagicMock):
        """Test that request ID is included when available."""
        response = build_error_response(
            error_code="NOT_FOUND",
            message="Resource not found",
            status_code=404,
            request=mock_request,
        )

        import json

        body = json.loads(response.body.decode())

        assert body["error"]["request_id"] == "test-request-id-123"

    def test_includes_details(self):
        """Test that details are included when provided."""
        response = build_error_response(
            error_code="VALIDATION_ERROR",
            message="Validation failed",
            status_code=400,
            details={"field": "email", "reason": "invalid format"},
        )

        import json

        body = json.loads(response.body.decode())

        assert body["error"]["details"]["field"] == "email"
        assert body["error"]["details"]["reason"] == "invalid format"

    def test_includes_custom_headers(self):
        """Test that custom headers are included."""
        response = build_error_response(
            error_code="RATE_LIMIT_EXCEEDED",
            message="Too many requests",
            status_code=429,
            headers={"Retry-After": "60"},
        )

        assert response.headers.get("Retry-After") == "60"
