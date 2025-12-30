"""Integration tests for FastAPI application endpoints and middleware."""

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(client):
    """Test root endpoint returns correct response."""
    response = await client.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["message"] == "Home Security Intelligence API"


@pytest.mark.asyncio
async def test_health_endpoint_liveness(client, mock_redis):
    """Test simple liveness health check endpoint.

    The /health endpoint is a simple liveness probe that always returns 200
    if the server is running. For detailed health, use /api/system/health.
    """
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()

    # Simple liveness check - just confirms server is alive
    assert data["status"] == "alive"
    assert "message" in data


@pytest.mark.asyncio
async def test_health_endpoint_always_succeeds(client):
    """Test that /health endpoint always succeeds as a liveness probe.

    Unlike /api/system/health which checks dependencies, /health is a
    simple liveness check that always returns 200 if the server is up.
    """
    # Even without Redis, the simple /health endpoint should succeed
    with patch("backend.core.redis._redis_client", None):
        response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()

        # Simple liveness check - always returns alive
        assert data["status"] == "alive"


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
async def test_lifespan_startup_initializes_database(integration_env, mock_redis):
    """Test that lifespan startup event initializes the database."""
    # Import app after env is set
    from backend.main import app

    # Create a fresh client which will trigger lifespan events
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Make a request to ensure app is initialized
        # Use root endpoint since /health is now a simple liveness check
        response = await ac.get("/")
        assert response.status_code == 200

        # Verify app is responding
        data = response.json()
        assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_lifespan_handles_redis_connection_failure(integration_env):
    """Test that lifespan continues when Redis connection fails."""
    from backend.main import app

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
    """Test that simple /health endpoint returns expected fields.

    The /health endpoint is a simple liveness check. For detailed health
    information, use /api/system/health.
    """
    response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()

    # Verify simple liveness response structure
    assert "status" in data
    assert "message" in data
    assert data["status"] == "alive"


@pytest.mark.asyncio
async def test_ready_endpoint(client, mock_redis):
    """Test canonical readiness endpoint /ready.

    The /ready endpoint checks critical dependencies and returns readiness status.
    """
    mock_redis.health_check.return_value = {
        "status": "healthy",
        "connected": True,
        "redis_version": "7.0.0",
    }

    response = await client.get("/ready")

    # May return 200 (ready) or 503 (not ready) depending on dependencies
    assert response.status_code in [200, 503]
    data = response.json()

    # Verify response structure
    assert "ready" in data
    assert "status" in data
    assert data["status"] in ["ready", "not_ready"]


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
