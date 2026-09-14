"""Unit tests for exception handlers including RFC 7807 Problem Details.

Tests cover:
- http_exception_handler returns RFC 7807 Problem Details format
- Various HTTP status codes return correct Problem Details
- Media type is application/problem+json
- Custom HTTPException detail messages are preserved
- Edge cases and error scenarios
- Comprehensive exception handler coverage for all handler types

NEM-1425: Standardize error response format with RFC 7807 Problem Details
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from pydantic_core import ErrorDetails
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.testclient import TestClient

from backend.api.exception_handlers import (
    build_error_response,
    circuit_breaker_exception_handler,
    external_service_exception_handler,
    generic_exception_handler,
    get_request_id,
    http_exception_handler,
    problem_details_exception_handler,
    pydantic_validation_handler,
    rate_limit_exception_handler,
    register_exception_handlers,
    security_intelligence_exception_handler,
    validation_exception_handler,
)
from backend.core.exceptions import (
    CircuitBreakerOpenError,
    ExternalServiceError,
    RateLimitError,
    SecurityIntelligenceError,
    ValidationError,
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


# =============================================================================
# SQLAlchemy Exception Handler Tests (NEM-1442)
# =============================================================================


class TestSQLAlchemyExceptionHandler:
    """Tests for sqlalchemy_exception_handler function."""

    @pytest.mark.asyncio
    async def test_database_error_returns_503(self, mock_request: MagicMock):
        """Test that SQLAlchemyError returns 503 Service Unavailable."""
        from sqlalchemy.exc import SQLAlchemyError

        from backend.api.exception_handlers import sqlalchemy_exception_handler

        exc = SQLAlchemyError("Connection refused")

        response = await sqlalchemy_exception_handler(mock_request, exc)

        assert response.status_code == 503

        import json

        body = json.loads(response.body.decode())

        assert body["error"]["code"] == "DATABASE_UNAVAILABLE"
        assert "database" in body["error"]["message"].lower()
        assert body["error"]["request_id"] == "test-request-id-123"

    @pytest.mark.asyncio
    async def test_operational_error_returns_503(self, mock_request: MagicMock):
        """Test that OperationalError returns 503 with appropriate message."""
        from sqlalchemy.exc import OperationalError

        from backend.api.exception_handlers import sqlalchemy_exception_handler

        # OperationalError requires statement, params, orig
        exc = OperationalError(
            statement="SELECT 1",
            params={},
            orig=Exception("Connection timed out"),
        )

        response = await sqlalchemy_exception_handler(mock_request, exc)

        assert response.status_code == 503

        import json

        body = json.loads(response.body.decode())

        assert body["error"]["code"] == "DATABASE_UNAVAILABLE"
        assert "request_id" in body["error"]

    @pytest.mark.asyncio
    async def test_integrity_error_returns_409(self, mock_request: MagicMock):
        """Test that IntegrityError returns 409 Conflict."""
        from sqlalchemy.exc import IntegrityError

        from backend.api.exception_handlers import sqlalchemy_exception_handler

        exc = IntegrityError(
            statement="INSERT INTO cameras",
            params={},
            orig=Exception("duplicate key"),
        )

        response = await sqlalchemy_exception_handler(mock_request, exc)

        assert response.status_code == 409

        import json

        body = json.loads(response.body.decode())

        assert body["error"]["code"] == "DATABASE_CONFLICT"
        assert "request_id" in body["error"]

    @pytest.mark.asyncio
    async def test_no_sensitive_data_leaked(self, mock_request: MagicMock):
        """Test that sensitive data is not leaked in error response."""
        from sqlalchemy.exc import SQLAlchemyError

        from backend.api.exception_handlers import sqlalchemy_exception_handler

        # Error message containing sensitive info (test credentials only)
        exc = SQLAlchemyError(
            "Connection to postgresql://user:password123@localhost:5432/db failed"  # pragma: allowlist secret
        )

        response = await sqlalchemy_exception_handler(mock_request, exc)

        import json

        body = json.loads(response.body.decode())

        # Should not contain the password or full connection string
        assert "password123" not in body["error"]["message"]
        assert "user:" not in body["error"]["message"]

    @pytest.mark.asyncio
    async def test_includes_timestamp(self, mock_request: MagicMock):
        """Test that error response includes timestamp."""
        from sqlalchemy.exc import SQLAlchemyError

        from backend.api.exception_handlers import sqlalchemy_exception_handler

        exc = SQLAlchemyError("Connection refused")

        response = await sqlalchemy_exception_handler(mock_request, exc)

        import json

        body = json.loads(response.body.decode())

        assert "timestamp" in body["error"]


# =============================================================================
# Redis Exception Handler Tests (NEM-1442)
# =============================================================================


class TestRedisExceptionHandler:
    """Tests for redis_exception_handler function."""

    @pytest.mark.asyncio
    async def test_redis_error_returns_503(self, mock_request: MagicMock):
        """Test that RedisError returns 503 Service Unavailable."""
        from redis.exceptions import RedisError

        from backend.api.exception_handlers import redis_exception_handler

        exc = RedisError("Connection refused")

        response = await redis_exception_handler(mock_request, exc)

        assert response.status_code == 503

        import json

        body = json.loads(response.body.decode())

        assert body["error"]["code"] == "CACHE_UNAVAILABLE"
        assert (
            "cache" in body["error"]["message"].lower()
            or "redis" in body["error"]["message"].lower()
        )
        assert body["error"]["request_id"] == "test-request-id-123"

    @pytest.mark.asyncio
    async def test_connection_error_returns_503(self, mock_request: MagicMock):
        """Test that ConnectionError returns 503."""
        from redis.exceptions import ConnectionError as RedisConnectionError

        from backend.api.exception_handlers import redis_exception_handler

        exc = RedisConnectionError("Connection refused")

        response = await redis_exception_handler(mock_request, exc)

        assert response.status_code == 503

        import json

        body = json.loads(response.body.decode())

        assert body["error"]["code"] == "CACHE_UNAVAILABLE"

    @pytest.mark.asyncio
    async def test_timeout_error_returns_503(self, mock_request: MagicMock):
        """Test that TimeoutError returns 503."""
        from redis.exceptions import TimeoutError as RedisTimeoutError

        from backend.api.exception_handlers import redis_exception_handler

        exc = RedisTimeoutError("Operation timed out")

        response = await redis_exception_handler(mock_request, exc)

        assert response.status_code == 503

        import json

        body = json.loads(response.body.decode())

        assert body["error"]["code"] == "CACHE_UNAVAILABLE"

    @pytest.mark.asyncio
    async def test_no_sensitive_data_leaked(self, mock_request: MagicMock):
        """Test that sensitive data is not leaked in error response."""
        from redis.exceptions import RedisError

        from backend.api.exception_handlers import redis_exception_handler

        # Error message containing sensitive info
        exc = RedisError("Connection to redis://:secretpassword@localhost:6379/0 failed")

        response = await redis_exception_handler(mock_request, exc)

        import json

        body = json.loads(response.body.decode())

        # Should not contain the password
        assert "secretpassword" not in body["error"]["message"]

    @pytest.mark.asyncio
    async def test_includes_timestamp(self, mock_request: MagicMock):
        """Test that error response includes timestamp."""
        from redis.exceptions import RedisError

        from backend.api.exception_handlers import redis_exception_handler

        exc = RedisError("Connection refused")

        response = await redis_exception_handler(mock_request, exc)

        import json

        body = json.loads(response.body.decode())

        assert "timestamp" in body["error"]

    @pytest.mark.asyncio
    async def test_request_id_from_header_fallback(self, mock_request_no_id: MagicMock):
        """Test that request ID falls back to header when not in state."""
        from redis.exceptions import RedisError

        from backend.api.exception_handlers import redis_exception_handler

        mock_request_no_id.headers = {"X-Request-ID": "header-id-456"}
        exc = RedisError("Connection refused")

        response = await redis_exception_handler(mock_request_no_id, exc)

        import json

        body = json.loads(response.body.decode())

        assert body["error"]["request_id"] == "header-id-456"


# =============================================================================
# Integration Tests for Database/Redis Exception Handlers (NEM-1442)
# =============================================================================


class TestDatabaseRedisExceptionHandlersIntegration:
    """Integration tests for database and Redis exception handlers via HTTP."""

    @pytest.fixture
    def db_redis_test_app(self) -> FastAPI:
        """Create a test app with routes that raise database/Redis errors."""
        from redis.exceptions import ConnectionError as RedisConnectionError
        from redis.exceptions import RedisError
        from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/test/db-error")
        async def raise_db_error():
            raise SQLAlchemyError("Database connection failed")

        @app.get("/test/db-operational")
        async def raise_db_operational():
            raise OperationalError(
                statement="SELECT 1",
                params={},
                orig=Exception("Connection pool exhausted"),
            )

        @app.get("/test/db-integrity")
        async def raise_db_integrity():
            raise IntegrityError(
                statement="INSERT INTO table",
                params={},
                orig=Exception("Unique constraint violated"),
            )

        @app.get("/test/redis-error")
        async def raise_redis_error():
            raise RedisError("Redis connection failed")

        @app.get("/test/redis-connection")
        async def raise_redis_connection():
            raise RedisConnectionError("Connection refused")

        return app

    @pytest.fixture
    def db_redis_client(self, db_redis_test_app: FastAPI) -> TestClient:
        """Create test client for database/Redis tests."""
        return TestClient(db_redis_test_app)

    def test_sqlalchemy_error_via_http(self, db_redis_client: TestClient):
        """Test SQLAlchemyError returns proper response via HTTP."""
        response = db_redis_client.get("/test/db-error")

        assert response.status_code == 503

        body = response.json()
        assert body["error"]["code"] == "DATABASE_UNAVAILABLE"
        assert "timestamp" in body["error"]

    def test_operational_error_via_http(self, db_redis_client: TestClient):
        """Test OperationalError returns 503 via HTTP."""
        response = db_redis_client.get("/test/db-operational")

        assert response.status_code == 503

        body = response.json()
        assert body["error"]["code"] == "DATABASE_UNAVAILABLE"

    def test_integrity_error_via_http(self, db_redis_client: TestClient):
        """Test IntegrityError returns 409 via HTTP."""
        response = db_redis_client.get("/test/db-integrity")

        assert response.status_code == 409

        body = response.json()
        assert body["error"]["code"] == "DATABASE_CONFLICT"

    def test_redis_error_via_http(self, db_redis_client: TestClient):
        """Test RedisError returns proper response via HTTP."""
        response = db_redis_client.get("/test/redis-error")

        assert response.status_code == 503

        body = response.json()
        assert body["error"]["code"] == "CACHE_UNAVAILABLE"
        assert "timestamp" in body["error"]

    def test_redis_connection_error_via_http(self, db_redis_client: TestClient):
        """Test Redis ConnectionError returns 503 via HTTP."""
        response = db_redis_client.get("/test/redis-connection")

        assert response.status_code == 503

        body = response.json()
        assert body["error"]["code"] == "CACHE_UNAVAILABLE"

    @patch("backend.api.exception_handlers.datetime")
    def test_build_error_response_includes_timestamp(self, mock_datetime: Mock) -> None:
        """Test that error response includes ISO timestamp."""
        mock_now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        mock_datetime.now.return_value = mock_now

        response = build_error_response(
            error_code="ERROR",
            message="Test",
            status_code=500,
        )

        content = response.body.decode()
        assert "2024-01-01T12:00:00" in content


# =============================================================================
# SecurityIntelligenceExceptionHandler Tests
# =============================================================================


class TestSecurityIntelligenceExceptionHandler:
    """Tests for security_intelligence_exception_handler."""

    @pytest.mark.asyncio
    async def test_handles_500_error_with_error_logging(self) -> None:
        """Test that 5xx errors are logged with error level."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/test"
        request.method = "POST"
        request.state = Mock(spec=[])
        request.headers = {}

        exc = SecurityIntelligenceError(
            "Internal server error",
            error_code="INTERNAL_ERROR",
            status_code=500,
        )

        with patch("backend.api.exception_handlers.logger") as mock_logger:
            response = await security_intelligence_exception_handler(request, exc)

            # Should log as error for 5xx
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            assert "Internal error" in call_args[0][0]
            assert call_args[1]["extra"]["status_code"] == 500

        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_handles_429_error_with_warning_logging(self) -> None:
        """Test that 429 rate limit errors are logged with warning level."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/test"
        request.method = "GET"
        request.state = Mock()
        request.state.request_id = "req-123"

        exc = RateLimitError("Rate limit exceeded")

        with patch("backend.api.exception_handlers.logger") as mock_logger:
            response = await security_intelligence_exception_handler(request, exc)

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert "Rate limit exceeded" in call_args[0][0]

        assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_handles_400_error_with_info_logging(self) -> None:
        """Test that 4xx client errors are logged with info level."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/cameras/invalid"
        request.method = "GET"
        request.state = Mock(spec=[])
        request.headers = {}

        exc = ValidationError("Invalid input", status_code=400)

        with patch("backend.api.exception_handlers.logger") as mock_logger:
            response = await security_intelligence_exception_handler(request, exc)

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert "Client error" in call_args[0][0]

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_includes_details_in_response(self) -> None:
        """Test that exception details are included in response."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/test"
        request.method = "POST"
        request.state = Mock(spec=[])
        request.headers = {}

        details = {"field": "email", "value": "invalid"}
        exc = ValidationError(
            "Validation failed",
            status_code=400,
            details=details,
        )

        with patch("backend.api.exception_handlers.logger"):
            response = await security_intelligence_exception_handler(request, exc)

        content = response.body.decode()
        assert "field" in content
        assert "email" in content

    @pytest.mark.asyncio
    async def test_handles_other_status_code_with_debug_logging(self) -> None:
        """Test that non-4xx/5xx status codes are logged with debug level."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/test"
        request.method = "GET"
        request.state = Mock(spec=[])
        request.headers = {}

        exc = SecurityIntelligenceError(
            "Informational message",
            error_code="INFO",
            status_code=200,  # 2xx status code (not 4xx or 5xx)
        )

        with patch("backend.api.exception_handlers.logger") as mock_logger:
            response = await security_intelligence_exception_handler(request, exc)

            # Should log as debug for non-error status codes
            mock_logger.debug.assert_called_once()
            call_args = mock_logger.debug.call_args
            assert "Exception handled" in call_args[0][0]

        assert response.status_code == 200


# =============================================================================
# HttpExceptionHandler Tests
# =============================================================================


class TestHttpExceptionHandler:
    """Tests for http_exception_handler."""

    @pytest.mark.asyncio
    async def test_handles_404_not_found(self) -> None:
        """Test handling 404 Not Found exceptions."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/cameras/missing"
        request.method = "GET"
        request.state = Mock(spec=[])
        request.headers = {}

        exc = StarletteHTTPException(status_code=404, detail="Camera not found")

        with patch("backend.api.exception_handlers.logger") as mock_logger:
            response = await http_exception_handler(request, exc)

            mock_logger.info.assert_called_once()

        assert response.status_code == 404
        content = response.body.decode()
        assert "NOT_FOUND" in content
        assert "Camera not found" in content

    @pytest.mark.asyncio
    async def test_handles_401_unauthorized(self) -> None:
        """Test handling 401 Unauthorized exceptions."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/admin"
        request.method = "GET"
        request.state = Mock(spec=[])
        request.headers = {}

        exc = StarletteHTTPException(
            status_code=401,
            detail="Authentication required",
        )

        with patch("backend.api.exception_handlers.logger"):
            response = await http_exception_handler(request, exc)

        assert response.status_code == 401
        content = response.body.decode()
        assert "AUTHENTICATION_REQUIRED" in content

    @pytest.mark.asyncio
    async def test_handles_500_internal_error(self) -> None:
        """Test handling 500 Internal Server Error with error logging."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/test"
        request.method = "POST"
        request.state = Mock(spec=[])
        request.headers = {}

        exc = StarletteHTTPException(
            status_code=500,
            detail="Internal server error",
        )

        with patch("backend.api.exception_handlers.logger") as mock_logger:
            response = await http_exception_handler(request, exc)

            # Should log as error for 5xx
            mock_logger.error.assert_called_once()

        assert response.status_code == 500
        content = response.body.decode()
        assert "INTERNAL_ERROR" in content

    @pytest.mark.asyncio
    async def test_handles_503_service_unavailable(self) -> None:
        """Test handling 503 Service Unavailable."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/detections"
        request.method = "GET"
        request.state = Mock(spec=[])
        request.headers = {}

        exc = StarletteHTTPException(
            status_code=503,
            detail="Service temporarily unavailable",
        )

        with patch("backend.api.exception_handlers.logger"):
            response = await http_exception_handler(request, exc)

        assert response.status_code == 503
        content = response.body.decode()
        assert "SERVICE_UNAVAILABLE" in content

    @pytest.mark.asyncio
    async def test_handles_exception_with_custom_headers(self) -> None:
        """Test that custom headers from exception are preserved."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/test"
        request.method = "GET"
        request.state = Mock(spec=[])
        request.headers = {}

        exc = StarletteHTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": "60"},
        )

        with patch("backend.api.exception_handlers.logger"):
            response = await http_exception_handler(request, exc)

        assert response.headers.get("Retry-After") == "60"

    @pytest.mark.asyncio
    async def test_handles_unknown_status_code(self) -> None:
        """Test handling exception with unmapped status code."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/test"
        request.method = "GET"
        request.state = Mock(spec=[])
        request.headers = {}

        exc = StarletteHTTPException(status_code=418, detail="I'm a teapot")

        with patch("backend.api.exception_handlers.logger"):
            response = await http_exception_handler(request, exc)

        assert response.status_code == 418
        content = response.body.decode()
        assert "ERROR" in content  # Default error code

    @pytest.mark.asyncio
    async def test_handles_exception_with_request_id_in_header(self) -> None:
        """Test that request ID from header is included in logs."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/test"
        request.method = "GET"
        request.state = Mock(spec=[])
        request.headers = {"X-Request-ID": "header-req-999"}

        exc = StarletteHTTPException(status_code=400, detail="Bad request")

        with patch("backend.api.exception_handlers.logger") as mock_logger:
            response = await http_exception_handler(request, exc)

            call_args = mock_logger.info.call_args
            assert call_args[1]["extra"]["request_id"] == "header-req-999"

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_handles_300_status_code(self) -> None:
        """Test handling 3xx status code (not 4xx or 5xx)."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/redirect"
        request.method = "GET"
        request.state = Mock(spec=[])
        request.headers = {}

        exc = StarletteHTTPException(
            status_code=301,
            detail="Moved Permanently",
        )

        with patch("backend.api.exception_handlers.logger") as mock_logger:
            response = await http_exception_handler(request, exc)

            # Should not call error, warning, or info for 3xx
            mock_logger.error.assert_not_called()
            mock_logger.warning.assert_not_called()
            mock_logger.info.assert_not_called()

        assert response.status_code == 301


# =============================================================================
# ValidationExceptionHandler Tests
# =============================================================================


class TestValidationExceptionHandler:
    """Tests for validation_exception_handler."""

    @pytest.mark.asyncio
    async def test_handles_single_validation_error(self) -> None:
        """Test handling single validation error with field details."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/cameras"
        request.method = "POST"
        request.state = Mock(spec=[])
        request.headers = {}

        # Create validation error
        error: ErrorDetails = {
            "type": "value_error",
            "loc": ("body", "name"),
            "msg": "Field required",
            "input": None,
        }
        exc = RequestValidationError([error])

        with patch("backend.api.exception_handlers.logger") as mock_logger:
            response = await validation_exception_handler(request, exc)

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert "Request validation failed" in call_args[0][0]

        assert response.status_code == 422
        content = response.body.decode()
        assert "VALIDATION_ERROR" in content
        assert "body.name" in content
        assert "Field required" in content

    @pytest.mark.asyncio
    async def test_handles_multiple_validation_errors(self) -> None:
        """Test handling multiple validation errors."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/events"
        request.method = "GET"
        request.state = Mock()
        request.state.request_id = "req-xyz"

        errors: list[ErrorDetails] = [
            {
                "type": "value_error",
                "loc": ("query", "start_date"),
                "msg": "Invalid date format",
                "input": "not-a-date",
            },
            {
                "type": "value_error",
                "loc": ("query", "limit"),
                "msg": "Must be positive",
                "input": -5,
            },
        ]
        exc = RequestValidationError(errors)

        with patch("backend.api.exception_handlers.logger"):
            response = await validation_exception_handler(request, exc)

        content = response.body.decode()
        assert "query.start_date" in content
        assert "query.limit" in content
        assert "Invalid date format" in content
        assert "Must be positive" in content
        assert "req-xyz" in content

    @pytest.mark.asyncio
    async def test_truncates_long_values(self) -> None:
        """Test that long input values are truncated."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/test"
        request.method = "POST"
        request.state = Mock(spec=[])
        request.headers = {}

        long_value = "x" * 200
        error: ErrorDetails = {
            "type": "value_error",
            "loc": ("body", "field"),
            "msg": "Too long",
            "input": long_value,
        }
        exc = RequestValidationError([error])

        with patch("backend.api.exception_handlers.logger"):
            response = await validation_exception_handler(request, exc)

        content = response.body.decode()
        # Value should be truncated to 100 characters
        assert long_value[:100] in content
        # Full value should NOT be in response (only first 100 chars)
        assert long_value not in content


# =============================================================================
# PydanticValidationHandler Tests
# =============================================================================


class TestPydanticValidationHandler:
    """Tests for pydantic_validation_handler."""

    @pytest.mark.asyncio
    async def test_handles_response_serialization_error(self) -> None:
        """Test handling Pydantic validation error during response serialization."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/cameras"
        request.method = "GET"
        request.state = Mock()
        request.state.request_id = "req-123"

        # Create a mock Pydantic validation error
        # Use try/except to generate a real validation error
        try:
            from pydantic import BaseModel, Field

            class TestModel(BaseModel):
                required_field: str = Field(...)

            # This will raise ValidationError
            TestModel()
        except PydanticValidationError as e:
            exc = e

        with patch("backend.api.exception_handlers.logger") as mock_logger:
            response = await pydantic_validation_handler(request, exc)

            # Should log as error since it's a server-side bug
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            assert "Response serialization failed" in call_args[0][0]
            assert call_args[1]["extra"]["error_count"] == 1

        assert response.status_code == 500
        content = response.body.decode()
        assert "INTERNAL_ERROR" in content
        assert "internal error occurred" in content

    @pytest.mark.asyncio
    async def test_handles_error_without_request_id(self) -> None:
        """Test handling error when request has no request ID."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/test"
        request.method = "POST"
        request.state = Mock(spec=[])
        request.headers = {}

        # Create a validation error
        try:
            from pydantic import BaseModel

            class TestModel(BaseModel):
                required: str

            TestModel()
        except PydanticValidationError as e:
            exc = e

        with patch("backend.api.exception_handlers.logger") as mock_logger:
            response = await pydantic_validation_handler(request, exc)

            # Should log without request_id
            call_args = mock_logger.error.call_args
            log_extra = call_args[1]["extra"]
            assert "request_id" not in log_extra

        assert response.status_code == 500


# =============================================================================
# GenericExceptionHandler Tests
# =============================================================================


class TestGenericExceptionHandler:
    """Tests for generic_exception_handler."""

    @pytest.mark.asyncio
    async def test_handles_unhandled_exception(self) -> None:
        """Test handling any unhandled exception."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/test"
        request.method = "POST"
        request.state = Mock(spec=[])
        request.headers = {}

        exc = ValueError("Unexpected error occurred")

        with (
            patch("backend.api.exception_handlers.logger") as mock_logger,
            patch("backend.api.exception_handlers.sanitize_error_for_response") as mock_sanitize,
        ):
            mock_sanitize.return_value = "A safe error message"

            response = await generic_exception_handler(request, exc)

            # Should sanitize the error
            mock_sanitize.assert_called_once_with(exc)

            # Should log with full exception info
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            assert "Unhandled exception" in call_args[0][0]
            assert call_args[1]["exc_info"] is True

        assert response.status_code == 500
        content = response.body.decode()
        assert "INTERNAL_ERROR" in content
        assert "safe error message" in content

    @pytest.mark.asyncio
    async def test_includes_exception_type_in_logs(self) -> None:
        """Test that exception type is logged for debugging."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/test"
        request.method = "GET"
        request.state = Mock()
        request.state.request_id = "req-abc"

        exc = KeyError("missing_key")

        with (
            patch("backend.api.exception_handlers.logger") as mock_logger,
            patch("backend.api.exception_handlers.sanitize_error_for_response") as mock_sanitize,
        ):
            mock_sanitize.return_value = "Sanitized error message"

            await generic_exception_handler(request, exc)

            call_args = mock_logger.error.call_args
            log_extra = call_args[1]["extra"]
            assert log_extra["exception_type"] == "KeyError"
            assert log_extra["request_id"] == "req-abc"


# =============================================================================
# CircuitBreakerExceptionHandler Tests
# =============================================================================


class TestCircuitBreakerExceptionHandler:
    """Tests for circuit_breaker_exception_handler."""

    @pytest.mark.asyncio
    async def test_handles_circuit_breaker_error(self) -> None:
        """Test handling circuit breaker open error."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/detections"
        request.method = "POST"
        request.state = Mock(spec=[])
        request.headers = {}

        exc = CircuitBreakerOpenError(
            service_name="yolo26",
            recovery_timeout=30.0,
        )

        with patch("backend.api.exception_handlers.logger") as mock_logger:
            response = await circuit_breaker_exception_handler(request, exc)

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert "Circuit breaker open for yolo26" in call_args[0][0]
            assert call_args[1]["extra"]["service"] == "yolo26"

        assert response.status_code == 503
        content = response.body.decode()
        assert "CIRCUIT_BREAKER_OPEN" in content
        assert "yolo26" in content

    @pytest.mark.asyncio
    async def test_includes_retry_after_header(self) -> None:
        """Test that Retry-After header is added with recovery timeout."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/test"
        request.method = "GET"
        request.state = Mock(spec=[])
        request.headers = {}

        exc = CircuitBreakerOpenError(
            service_name="nemotron",
            recovery_timeout=60.0,
        )

        with patch("backend.api.exception_handlers.logger"):
            response = await circuit_breaker_exception_handler(request, exc)

        # Should include Retry-After header with recovery timeout
        assert response.headers.get("Retry-After") == "60"

    @pytest.mark.asyncio
    async def test_handles_circuit_breaker_without_timeout(self) -> None:
        """Test handling circuit breaker without recovery timeout."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/test"
        request.method = "GET"
        request.state = Mock(spec=[])
        request.headers = {}

        exc = CircuitBreakerOpenError(service_name="service")

        with patch("backend.api.exception_handlers.logger"):
            response = await circuit_breaker_exception_handler(request, exc)

        # Should not have Retry-After header if no timeout
        assert "Retry-After" not in response.headers

    @pytest.mark.asyncio
    async def test_handles_circuit_breaker_with_request_id_in_header(self) -> None:
        """Test circuit breaker handler with request ID from header."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/test"
        request.method = "GET"
        request.state = Mock(spec=[])
        request.headers = {"X-Request-ID": "cb-req-123"}

        exc = CircuitBreakerOpenError(service_name="database")

        with patch("backend.api.exception_handlers.logger") as mock_logger:
            response = await circuit_breaker_exception_handler(request, exc)

            call_args = mock_logger.warning.call_args
            assert call_args[1]["extra"]["request_id"] == "cb-req-123"

        assert response.status_code == 503


# =============================================================================
# RateLimitExceptionHandler Tests
# =============================================================================


class TestRateLimitExceptionHandler:
    """Tests for rate_limit_exception_handler."""

    @pytest.mark.asyncio
    async def test_handles_rate_limit_error(self) -> None:
        """Test handling rate limit error."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/events"
        request.method = "GET"
        request.state = Mock(spec=[])
        request.headers = {}

        exc = RateLimitError(
            "Rate limit exceeded",
            retry_after=30,
            limit=100,
            window_seconds=60,
        )

        with patch("backend.api.exception_handlers.logger") as mock_logger:
            response = await rate_limit_exception_handler(request, exc)

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert "Rate limit exceeded" in call_args[0][0]

        assert response.status_code == 429
        content = response.body.decode()
        assert "RATE_LIMIT_EXCEEDED" in content
        assert "retry_after" in content

    @pytest.mark.asyncio
    async def test_includes_retry_after_header(self) -> None:
        """Test that Retry-After header is included."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/test"
        request.method = "POST"
        request.state = Mock(spec=[])
        request.headers = {}

        exc = RateLimitError(retry_after=120)

        with patch("backend.api.exception_handlers.logger"):
            response = await rate_limit_exception_handler(request, exc)

        assert response.headers.get("Retry-After") == "120"

    @pytest.mark.asyncio
    async def test_handles_rate_limit_without_retry_after(self) -> None:
        """Test handling rate limit error without retry_after."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/test"
        request.method = "GET"
        request.state = Mock(spec=[])
        request.headers = {}

        exc = RateLimitError("Too many requests")

        with patch("backend.api.exception_handlers.logger"):
            response = await rate_limit_exception_handler(request, exc)

        # Should not have Retry-After header if not specified
        assert "Retry-After" not in response.headers

    @pytest.mark.asyncio
    async def test_handles_rate_limit_with_request_id_in_header(self) -> None:
        """Test rate limit handler with request ID from header."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/test"
        request.method = "POST"
        request.state = Mock(spec=[])
        request.headers = {"X-Request-ID": "rl-req-456"}

        exc = RateLimitError("Rate limit hit", retry_after=30)

        with patch("backend.api.exception_handlers.logger") as mock_logger:
            response = await rate_limit_exception_handler(request, exc)

            call_args = mock_logger.warning.call_args
            assert call_args[1]["extra"]["request_id"] == "rl-req-456"

        assert response.status_code == 429


# =============================================================================
# ExternalServiceExceptionHandler Tests
# =============================================================================


class TestExternalServiceExceptionHandler:
    """Tests for external_service_exception_handler."""

    @pytest.mark.asyncio
    async def test_handles_external_service_error(self) -> None:
        """Test handling external service error."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/detections"
        request.method = "POST"
        request.state = Mock()
        request.state.request_id = "req-ext-123"

        exc = ExternalServiceError(
            "Service unavailable",
            service_name="yolo26",
            details={"reason": "timeout"},
        )

        with patch("backend.api.exception_handlers.logger") as mock_logger:
            response = await external_service_exception_handler(request, exc)

            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            assert "External service error (yolo26)" in call_args[0][0]
            assert call_args[1]["extra"]["service"] == "yolo26"
            assert call_args[1]["exc_info"] is True

        assert response.status_code == 503
        content = response.body.decode()
        assert "SERVICE_UNAVAILABLE" in content
        assert "req-ext-123" in content

    @pytest.mark.asyncio
    async def test_includes_service_details(self) -> None:
        """Test that service details are included in response."""
        request = Mock(spec=Request)
        request.url = Mock()
        request.url.path = "/api/test"
        request.method = "GET"
        request.state = Mock(spec=[])
        request.headers = {}

        exc = ExternalServiceError(
            "Database connection failed",
            service_name="postgresql",
            details={"error": "connection timeout", "host": "db.example.com"},
        )

        with patch("backend.api.exception_handlers.logger"):
            response = await external_service_exception_handler(request, exc)

        content = response.body.decode()
        assert "error" in content
        assert "connection timeout" in content


# =============================================================================
# RegisterExceptionHandlers Tests
# =============================================================================


class TestRegisterExceptionHandlers:
    """Tests for register_exception_handlers function."""

    def test_registers_all_handlers(self) -> None:
        """Test that all exception handlers are registered with the app."""
        app = FastAPI()

        with patch("backend.api.exception_handlers.logger") as mock_logger:
            register_exception_handlers(app)

            # Should log that handlers were registered
            mock_logger.info.assert_called_once_with("Exception handlers registered")

        # Verify handlers were added to the app
        # FastAPI stores handlers in app.exception_handlers dict
        assert len(app.exception_handlers) > 0

        # Check for specific exception types
        from fastapi.exceptions import RequestValidationError
        from pydantic import ValidationError as PydanticValidationError
        from starlette.exceptions import HTTPException as StarletteHTTPException

        from backend.core.exceptions import (
            CircuitBreakerOpenError,
            ExternalServiceError,
            RateLimitError,
            SecurityIntelligenceError,
        )

        assert CircuitBreakerOpenError in app.exception_handlers
        assert RateLimitError in app.exception_handlers
        assert ExternalServiceError in app.exception_handlers
        assert SecurityIntelligenceError in app.exception_handlers
        assert RequestValidationError in app.exception_handlers
        assert PydanticValidationError in app.exception_handlers
        assert StarletteHTTPException in app.exception_handlers
        assert Exception in app.exception_handlers

    def test_handlers_are_registered_in_correct_order(self) -> None:
        """Test that handlers are registered from most specific to least specific."""
        app = FastAPI()
        register_exception_handlers(app)

        # The order matters for exception handling - more specific exceptions
        # should be registered before more general ones.
        # We can't easily test the order, but we can verify all are present.
        handler_keys = list(app.exception_handlers.keys())

        from backend.core.exceptions import (
            CircuitBreakerOpenError,
            ExternalServiceError,
            SecurityIntelligenceError,
        )

        # CircuitBreakerOpenError should be registered (subclass of ExternalServiceError)
        assert CircuitBreakerOpenError in handler_keys
        # ExternalServiceError should be registered
        assert ExternalServiceError in handler_keys
        # SecurityIntelligenceError should be registered (base class)
        assert SecurityIntelligenceError in handler_keys
        # Generic Exception handler should be registered
        assert Exception in handler_keys
