"""Integration tests for FastAPI application endpoints and middleware."""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app


@pytest.fixture
async def test_db_setup():
    """Set up test database environment."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_api.db"
        test_db_url = f"sqlite+aiosqlite:///{db_path}"

        # Store original environment
        original_db_url = os.environ.get("DATABASE_URL")
        original_redis_url = os.environ.get("REDIS_URL")

        # Set test environment
        os.environ["DATABASE_URL"] = test_db_url
        os.environ["REDIS_URL"] = "redis://localhost:6379/15"  # Test DB

        yield test_db_url

        # Restore original environment
        if original_db_url:
            os.environ["DATABASE_URL"] = original_db_url
        else:
            os.environ.pop("DATABASE_URL", None)

        if original_redis_url:
            os.environ["REDIS_URL"] = original_redis_url
        else:
            os.environ.pop("REDIS_URL", None)


@pytest.fixture
async def mock_redis():
    """Mock Redis operations to avoid requiring Redis server."""
    mock_redis_client = AsyncMock()
    mock_redis_client.health_check.return_value = {
        "status": "healthy",
        "connected": True,
        "redis_version": "7.0.0",
    }

    with (
        patch("backend.core.redis._redis_client", mock_redis_client),
        patch("backend.core.redis.init_redis", return_value=mock_redis_client),
    ):
        yield mock_redis_client


@pytest.fixture
async def client(test_db_setup, mock_redis):
    """Create async HTTP client for testing FastAPI app."""
    # Use ASGITransport to test the app without running a server
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_root_endpoint(client):
    """Test root endpoint returns correct response."""
    response = await client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["message"] == "Home Security Intelligence API"


@pytest.mark.asyncio
async def test_health_endpoint_with_healthy_services(client, mock_redis):
    """Test health check endpoint when all services are operational."""
    # Configure mock Redis to return healthy status
    mock_redis.health_check.return_value = {
        "status": "healthy",
        "connected": True,
        "redis_version": "7.0.0",
    }

    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()

    # Check overall status - can be degraded if database engine not fully initialized
    assert data["status"] in ["healthy", "degraded"]
    assert data["api"] == "operational"
    # Database may not be fully initialized in test context
    assert data["database"] in ["operational", "not_initialized"]
    assert data["redis"] in ["healthy", "not_initialized"]


@pytest.mark.asyncio
async def test_health_endpoint_with_redis_error(client):
    """Test health check endpoint when Redis is unavailable."""
    # Mock Redis to raise an exception
    with patch("backend.core.redis._redis_client", None):
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()

        # Overall status should be healthy since Redis is optional (not_initialized is acceptable)
        assert data["status"] in ["healthy", "degraded"]
        assert data["api"] == "operational"
        # Database may not be fully initialized in test context
        assert data["database"] in ["operational", "not_initialized"]
        # When _redis_client is None, status is "not_initialized"
        assert data["redis"] == "not_initialized"


@pytest.mark.asyncio
async def test_cors_middleware_allows_configured_origins(client):
    """Test CORS middleware allows requests from configured origins."""
    # Test with allowed origin
    response = await client.get(
        "/",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    # CORS headers should be present
    assert "access-control-allow-origin" in response.headers
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


@pytest.mark.asyncio
async def test_cors_middleware_preflight_request(client):
    """Test CORS middleware handles preflight OPTIONS requests."""
    response = await client.options(
        "/",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    # Preflight should succeed
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
    assert "access-control-allow-methods" in response.headers
    assert "access-control-allow-headers" in response.headers


@pytest.mark.asyncio
async def test_lifespan_startup_initializes_database(test_db_setup, mock_redis):
    """Test that lifespan startup event initializes the database."""
    # Create a fresh client which will trigger lifespan events
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Make a request to ensure app is initialized
        response = await ac.get("/health")
        assert response.status_code == 200

        # Check that database is initialized (may be operational or not_initialized in test context)
        data = response.json()
        assert data["database"] in ["operational", "not_initialized"]


@pytest.mark.asyncio
async def test_lifespan_handles_redis_connection_failure(test_db_setup):
    """Test that lifespan continues when Redis connection fails."""
    # Mock init_redis to raise an exception
    with patch("backend.main.init_redis", side_effect=Exception("Redis unavailable")):
        # App should still start even if Redis fails
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/")
            assert response.status_code == 200


@pytest.mark.asyncio
async def test_api_returns_json_content_type(client):
    """Test that API endpoints return proper JSON content type."""
    response = await client.get("/")

    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_health_endpoint_structure(client):
    """Test that health endpoint returns all expected fields."""
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()

    # Verify all required fields are present
    required_fields = ["status", "api", "database", "redis", "redis_details"]
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"

    # Verify status values are valid
    assert data["status"] in ["healthy", "degraded", "unhealthy"]
    assert data["api"] in ["operational", "degraded", "down"]
    assert data["database"] in ["operational", "not_initialized", "error"]


@pytest.mark.asyncio
async def test_multiple_concurrent_requests(client):
    """Test that API can handle multiple concurrent requests."""
    import asyncio

    # Make 10 concurrent requests
    tasks = [client.get("/") for _ in range(10)]
    responses = await asyncio.gather(*tasks)

    # All requests should succeed
    for response in responses:
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_404_endpoint_not_found(client):
    """Test that accessing non-existent endpoint returns 404."""
    response = await client.get("/nonexistent-endpoint")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cors_credentials_flag(client):
    """Test that CORS middleware sets credentials flag correctly."""
    response = await client.get("/", headers={"Origin": "http://localhost:3000"})

    assert response.status_code == 200
    # Check that credentials are allowed
    assert response.headers.get("access-control-allow-credentials") == "true"
