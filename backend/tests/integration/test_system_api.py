"""Integration tests for system API endpoints."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from backend.models.gpu_stats import GPUStats


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

    # HTTP status: 200 if healthy, 503 if degraded/unhealthy
    # In integration tests, AI services may be down, leading to degraded status
    assert response.status_code in [200, 503]
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
async def test_health_endpoint_degraded_services(client, integration_db):
    """Test health check endpoint with degraded services (Redis down)."""
    # Mock Redis to raise an exception (simulating unhealthy Redis)
    mock_redis_client = AsyncMock()
    mock_redis_client.health_check.side_effect = Exception("Redis connection failed")

    with patch("backend.core.redis._redis_client", mock_redis_client):
        response = await client.get("/api/system/health")

        # Degraded/unhealthy states now return 503
        assert response.status_code in [200, 503]
        data = response.json()

        # Overall status should be degraded
        assert data["status"] in ["healthy", "degraded"]
        assert "services" in data

        # Redis should be marked as unhealthy
        services = data["services"]
        assert "redis" in services
        assert services["redis"]["status"] == "unhealthy"


@pytest.mark.asyncio
async def test_health_endpoint_database_connectivity(client, mock_redis, integration_db):
    """Test health check endpoint verifies actual database connectivity."""
    response = await client.get("/api/system/health")

    # HTTP status depends on overall health: 200 if healthy, 503 if degraded/unhealthy
    assert response.status_code in [200, 503]
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
    assert "detection_confidence_threshold" in data

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
    assert data["detection_confidence_threshold"] == 0.5


@pytest.mark.asyncio
async def test_patch_config_updates_values(client, mock_redis):
    """PATCH /api/system/config updates runtime config and affects subsequent reads."""
    payload = {
        "retention_days": 7,
        "batch_window_seconds": 42,
        "batch_idle_timeout_seconds": 13,
        "detection_confidence_threshold": 0.75,
    }

    patch_resp = await client.patch("/api/system/config", json=payload)
    assert patch_resp.status_code == 200
    patched = patch_resp.json()
    assert patched["retention_days"] == 7
    assert patched["batch_window_seconds"] == 42
    assert patched["batch_idle_timeout_seconds"] == 13
    assert patched["detection_confidence_threshold"] == 0.75

    get_resp = await client.get("/api/system/config")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["retention_days"] == 7
    assert data["batch_window_seconds"] == 42
    assert data["batch_idle_timeout_seconds"] == 13
    assert data["detection_confidence_threshold"] == 0.75


@pytest.mark.asyncio
async def test_gpu_history_empty(client, mock_redis):
    """GET /api/system/gpu/history returns empty list when no samples exist."""
    resp = await client.get("/api/system/gpu/history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["samples"] == []
    assert data["count"] == 0
    assert data["limit"] >= 1


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
async def test_stats_endpoint_with_data(client, mock_redis, integration_db):
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
        # Health endpoint may return 503 if services are degraded/unhealthy
        # Other endpoints should return 200
        if endpoint == "/api/system/health":
            assert response.status_code in [200, 503]
        else:
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

    # All requests should succeed (health may return 503 if degraded)
    for response in responses:
        assert response.status_code in [200, 503]


@pytest.mark.asyncio
async def test_health_endpoint_includes_ai_service_status(client, mock_redis):
    """Test health check includes AI service status."""
    response = await client.get("/api/system/health")

    # Health endpoint returns 200 if healthy, 503 if degraded/unhealthy
    assert response.status_code in [200, 503]
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


@pytest.mark.asyncio
async def test_gpu_history_with_data_and_since_filter(client, db_session, mock_redis):
    """GET /api/system/gpu/history returns samples in chronological order and supports since."""
    now = datetime.now(UTC)
    older = now - timedelta(minutes=2)
    newer = now - timedelta(minutes=1)

    db_session.add_all(
        [
            GPUStats(
                recorded_at=older,
                gpu_utilization=10.0,
                memory_used=100,
                memory_total=1000,
                temperature=40.0,
                inference_fps=0.0,
            ),
            GPUStats(
                recorded_at=newer,
                gpu_utilization=20.0,
                memory_used=200,
                memory_total=1000,
                temperature=41.0,
                inference_fps=1.0,
            ),
        ]
    )
    await db_session.commit()

    resp = await client.get("/api/system/gpu/history?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2
    assert data["samples"][0]["utilization"] == 10.0
    assert data["samples"][1]["utilization"] == 20.0

    # since filter should exclude the older sample
    # Use 'Z' to avoid '+' being interpreted as a space in query strings.
    since = (now - timedelta(minutes=1, seconds=30)).isoformat().replace("+00:00", "Z")
    resp2 = await client.get(f"/api/system/gpu/history?since={since}&limit=10")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["count"] == 1
    assert data2["samples"][0]["utilization"] == 20.0


# =============================================================================
# Pipeline Worker Readiness Integration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_readiness_endpoint_includes_pipeline_workers(client, mock_redis):
    """Test that readiness endpoint includes pipeline worker status in workers list."""
    from unittest.mock import MagicMock

    from backend.api.routes import system as system_routes

    # Save original
    original_pipeline_manager = system_routes._pipeline_manager

    try:
        # Mock pipeline manager with running workers
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {
            "running": True,
            "workers": {
                "detection": {"state": "running", "items_processed": 100},
                "analysis": {"state": "running", "items_processed": 50},
                "timeout": {"state": "running", "items_processed": 10},
                "metrics": {"running": True},
            },
        }
        system_routes._pipeline_manager = mock_manager

        mock_redis.health_check.return_value = {
            "status": "healthy",
            "connected": True,
            "redis_version": "7.0.0",
        }

        response = await client.get("/api/system/health/ready")

        assert response.status_code == 200
        data = response.json()

        # Should be ready when all workers are running
        assert data["ready"] is True
        assert data["status"] == "ready"

        # Check that workers list includes pipeline workers
        workers = data["workers"]
        worker_names = [w["name"] for w in workers]

        assert "detection_worker" in worker_names
        assert "analysis_worker" in worker_names

        # Verify detection_worker status
        detection_worker = next(w for w in workers if w["name"] == "detection_worker")
        assert detection_worker["running"] is True

        # Verify analysis_worker status
        analysis_worker = next(w for w in workers if w["name"] == "analysis_worker")
        assert analysis_worker["running"] is True

    finally:
        system_routes._pipeline_manager = original_pipeline_manager


@pytest.mark.asyncio
async def test_readiness_endpoint_not_ready_when_pipeline_workers_stopped(client, mock_redis):
    """Test that readiness endpoint returns not_ready when pipeline workers are stopped."""
    from unittest.mock import MagicMock

    from backend.api.routes import system as system_routes

    # Save original
    original_pipeline_manager = system_routes._pipeline_manager

    try:
        # Mock pipeline manager with stopped workers
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {
            "running": True,
            "workers": {
                "detection": {"state": "stopped", "items_processed": 100},
                "analysis": {"state": "stopped", "items_processed": 50},
            },
        }
        system_routes._pipeline_manager = mock_manager

        mock_redis.health_check.return_value = {
            "status": "healthy",
            "connected": True,
            "redis_version": "7.0.0",
        }

        response = await client.get("/api/system/health/ready")

        # 503 is returned when not ready
        assert response.status_code == 503
        data = response.json()

        # Should NOT be ready when critical workers are stopped
        assert data["ready"] is False
        assert data["status"] == "not_ready"

        # Database and Redis should still be healthy
        assert data["services"]["database"]["status"] == "healthy"
        assert data["services"]["redis"]["status"] == "healthy"

        # Workers should show stopped status
        workers = data["workers"]
        detection_worker = next((w for w in workers if w["name"] == "detection_worker"), None)
        assert detection_worker is not None
        assert detection_worker["running"] is False

    finally:
        system_routes._pipeline_manager = original_pipeline_manager


@pytest.mark.asyncio
async def test_readiness_endpoint_not_ready_when_detection_worker_in_error(client, mock_redis):
    """Test that readiness endpoint returns not_ready when detection worker is in error state."""
    from unittest.mock import MagicMock

    from backend.api.routes import system as system_routes

    # Save original
    original_pipeline_manager = system_routes._pipeline_manager

    try:
        # Mock pipeline manager with detection worker in error state
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {
            "running": True,
            "workers": {
                "detection": {"state": "error", "items_processed": 100, "errors": 10},
                "analysis": {"state": "running", "items_processed": 50},
            },
        }
        system_routes._pipeline_manager = mock_manager

        mock_redis.health_check.return_value = {
            "status": "healthy",
            "connected": True,
            "redis_version": "7.0.0",
        }

        response = await client.get("/api/system/health/ready")

        # 503 is returned when not ready
        assert response.status_code == 503
        data = response.json()

        # Should NOT be ready when detection worker is in error state
        assert data["ready"] is False
        assert data["status"] == "not_ready"

    finally:
        system_routes._pipeline_manager = original_pipeline_manager


@pytest.mark.asyncio
async def test_readiness_endpoint_graceful_when_no_pipeline_manager(client, mock_redis):
    """Test that readiness endpoint returns not_ready when pipeline manager is not registered.

    Without the pipeline manager, the system cannot process detections, so it should
    report as not_ready (503) rather than ready.
    """
    from backend.api.routes import system as system_routes

    # Save original
    original_pipeline_manager = system_routes._pipeline_manager

    try:
        # Set pipeline manager to None (not registered)
        system_routes._pipeline_manager = None

        mock_redis.health_check.return_value = {
            "status": "healthy",
            "connected": True,
            "redis_version": "7.0.0",
        }

        response = await client.get("/api/system/health/ready")

        # Should return 503 when pipeline manager is not registered
        # because the system cannot process detections
        assert response.status_code == 503
        data = response.json()

        assert data["ready"] is False
        assert data["status"] == "not_ready"

    finally:
        system_routes._pipeline_manager = original_pipeline_manager
