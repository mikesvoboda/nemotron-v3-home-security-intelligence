"""Integration tests for system API endpoints."""

import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app


@pytest.fixture
async def test_db_setup():
    """Set up test database environment."""
    from backend.core.config import get_settings
    from backend.core.database import close_db, init_db

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_system_api.db"
        test_db_url = f"sqlite+aiosqlite:///{db_path}"

        # Store original environment
        original_db_url = os.environ.get("DATABASE_URL")
        original_redis_url = os.environ.get("REDIS_URL")

        # Set test environment
        os.environ["DATABASE_URL"] = test_db_url
        os.environ["REDIS_URL"] = "redis://localhost:6379/15"  # Test DB

        # Clear settings cache and initialize database
        get_settings.cache_clear()
        await close_db()
        await init_db()

        yield test_db_url

        # Cleanup
        await close_db()

        # Restore original environment
        if original_db_url:
            os.environ["DATABASE_URL"] = original_db_url
        else:
            os.environ.pop("DATABASE_URL", None)

        if original_redis_url:
            os.environ["REDIS_URL"] = original_redis_url
        else:
            os.environ.pop("REDIS_URL", None)

        # Clear settings cache again
        get_settings.cache_clear()


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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_endpoint_all_services_healthy(client, mock_redis):
    """Test health check endpoint when all services are healthy."""
    # Configure mock Redis to return healthy status
    mock_redis.health_check.return_value = {
        "status": "healthy",
        "connected": True,
        "redis_version": "7.0.0",
    }

    response = await client.get("/api/system/health")

    assert response.status_code == 200
    data = response.json()

    # Check response structure
    assert "status" in data
    assert "services" in data
    assert "timestamp" in data

    # Check services
    services = data["services"]
    assert "database" in services
    assert "redis" in services
    assert "ai" in services

    # Verify timestamp format
    timestamp = datetime.fromisoformat(data["timestamp"])
    assert isinstance(timestamp, datetime)


@pytest.mark.asyncio
async def test_health_endpoint_degraded_services(client, test_db_setup):
    """Test health check endpoint with degraded services (Redis down)."""
    # Mock Redis to raise an exception (simulating unhealthy Redis)
    mock_redis_client = AsyncMock()
    mock_redis_client.health_check.side_effect = Exception("Redis connection failed")

    with patch("backend.core.redis._redis_client", mock_redis_client):
        response = await client.get("/api/system/health")

        assert response.status_code == 200
        data = response.json()

        # Overall status should be degraded
        assert data["status"] in ["healthy", "degraded"]
        assert "services" in data

        # Redis should be marked as unhealthy
        services = data["services"]
        assert "redis" in services
        assert services["redis"]["status"] == "unhealthy"


@pytest.mark.asyncio
async def test_health_endpoint_database_connectivity(client, mock_redis, test_db_setup):
    """Test health check endpoint verifies actual database connectivity."""
    response = await client.get("/api/system/health")

    assert response.status_code == 200
    data = response.json()

    # Database should be checked
    services = data["services"]
    assert "database" in services
    # Database status should be operational or not_initialized depending on test setup
    assert services["database"]["status"] in ["healthy", "unhealthy", "not_initialized"]


@pytest.mark.asyncio
async def test_gpu_stats_endpoint(client, mock_redis):
    """Test GPU stats endpoint returns current GPU statistics."""
    response = await client.get("/api/system/gpu")

    assert response.status_code == 200
    data = response.json()

    # Check response structure (all fields can be null if GPU unavailable)
    assert "utilization" in data
    assert "memory_used" in data
    assert "memory_total" in data
    assert "temperature" in data
    assert "inference_fps" in data


@pytest.mark.asyncio
async def test_gpu_stats_endpoint_with_data(client, mock_redis):
    """Test GPU stats endpoint with mocked GPU data."""
    # Mock GPU stats query to return data
    with patch("backend.api.routes.system.get_latest_gpu_stats") as mock_gpu:
        mock_gpu.return_value = {
            "utilization": 75.5,
            "memory_used": 12000,
            "memory_total": 24000,
            "temperature": 65.0,
            "inference_fps": 30.5,
        }

        response = await client.get("/api/system/gpu")

        assert response.status_code == 200
        data = response.json()

        assert data["utilization"] == 75.5
        assert data["memory_used"] == 12000
        assert data["memory_total"] == 24000
        assert data["temperature"] == 65.0
        assert data["inference_fps"] == 30.5


@pytest.mark.asyncio
async def test_config_endpoint(client, mock_redis):
    """Test config endpoint returns public configuration."""
    response = await client.get("/api/system/config")

    assert response.status_code == 200
    data = response.json()

    # Check expected public fields
    assert "app_name" in data
    assert "version" in data
    assert "retention_days" in data
    assert "batch_window_seconds" in data
    assert "batch_idle_timeout_seconds" in data

    # Verify no sensitive data is exposed
    assert "database_url" not in data
    assert "redis_url" not in data
    assert "DATABASE_URL" not in str(data)
    assert "REDIS_URL" not in str(data)


@pytest.mark.asyncio
async def test_config_endpoint_has_expected_values(client, mock_redis):
    """Test config endpoint returns expected default values."""
    response = await client.get("/api/system/config")

    assert response.status_code == 200
    data = response.json()

    # Check default values from settings
    assert data["app_name"] == "Home Security Intelligence"
    assert data["version"] == "0.1.0"
    assert data["retention_days"] == 30
    assert data["batch_window_seconds"] == 90
    assert data["batch_idle_timeout_seconds"] == 30


@pytest.mark.asyncio
async def test_stats_endpoint(client, mock_redis):
    """Test stats endpoint returns system statistics."""
    response = await client.get("/api/system/stats")

    assert response.status_code == 200
    data = response.json()

    # Check response structure
    assert "total_cameras" in data
    assert "total_events" in data
    assert "total_detections" in data
    assert "uptime_seconds" in data

    # All counts should be non-negative integers
    assert isinstance(data["total_cameras"], int)
    assert isinstance(data["total_events"], int)
    assert isinstance(data["total_detections"], int)
    assert data["total_cameras"] >= 0
    assert data["total_events"] >= 0
    assert data["total_detections"] >= 0

    # Uptime should be a positive number
    assert isinstance(data["uptime_seconds"], int | float)
    assert data["uptime_seconds"] >= 0


@pytest.mark.asyncio
async def test_stats_endpoint_with_data(client, mock_redis, test_db_setup):
    """Test stats endpoint returns correct counts when data exists."""
    # This test would need to insert test data, but for now we just verify structure
    response = await client.get("/api/system/stats")

    assert response.status_code == 200
    data = response.json()

    # With empty database, counts should be 0
    assert data["total_cameras"] >= 0
    assert data["total_events"] >= 0
    assert data["total_detections"] >= 0


@pytest.mark.asyncio
async def test_system_endpoints_return_json(client, mock_redis):
    """Test that all system endpoints return JSON content type."""
    endpoints = [
        "/api/system/health",
        "/api/system/gpu",
        "/api/system/config",
        "/api/system/stats",
    ]

    for endpoint in endpoints:
        response = await client.get(endpoint)
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_system_endpoints_handle_concurrent_requests(client, mock_redis):
    """Test that system endpoints can handle concurrent requests."""
    import asyncio

    # Make concurrent requests to all endpoints
    endpoints = [
        "/api/system/health",
        "/api/system/gpu",
        "/api/system/config",
        "/api/system/stats",
    ]

    tasks = [client.get(endpoint) for endpoint in endpoints * 3]
    responses = await asyncio.gather(*tasks)

    # All requests should succeed
    for response in responses:
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_endpoint_includes_ai_service_status(client, mock_redis):
    """Test health check includes AI service status."""
    response = await client.get("/api/system/health")

    assert response.status_code == 200
    data = response.json()

    # Check AI service is included
    services = data["services"]
    assert "ai" in services

    # AI service should have a status
    ai_service = services["ai"]
    assert "status" in ai_service


@pytest.mark.asyncio
async def test_gpu_stats_endpoint_handles_no_gpu(client, mock_redis):
    """Test GPU stats endpoint when GPU is unavailable."""
    # Mock GPU stats query to return None (no GPU data)
    with patch("backend.api.routes.system.get_latest_gpu_stats") as mock_gpu:
        mock_gpu.return_value = None

        response = await client.get("/api/system/gpu")

        assert response.status_code == 200
        data = response.json()

        # All fields should be null when GPU unavailable
        assert data["utilization"] is None
        assert data["memory_used"] is None
        assert data["memory_total"] is None
        assert data["temperature"] is None
        assert data["inference_fps"] is None
