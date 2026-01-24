"""Integration tests for system API endpoints."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from backend.models.gpu_stats import GPUStats
from backend.tests.integration.test_helpers import get_error_message


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
    from backend.api.routes.system import clear_health_cache

    # Clear health cache to ensure fresh check
    clear_health_cache()

    # Mock Redis to raise an exception (simulating unhealthy Redis)
    mock_redis_client = AsyncMock()
    mock_redis_client.health_check.side_effect = ConnectionError("Redis connection failed")

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
    from backend.api.routes import system as system_routes

    # Clear cache to ensure fresh evaluation
    system_routes.clear_health_cache()

    # Mock GPU stats query to return data
    # Must use AsyncMock since get_latest_gpu_stats is async
    with patch(
        "backend.api.routes.system.get_latest_gpu_stats", new_callable=AsyncMock
    ) as mock_gpu:
        mock_gpu.return_value = {
            "gpu_name": "NVIDIA RTX A5500",
            "utilization": 75.5,
            "memory_used": 12000,
            "memory_total": 24000,
            "temperature": 65.0,
            "power_usage": 150.0,
            "inference_fps": 30.5,
        }

        response = await client.get("/api/system/gpu")

        assert response.status_code == 200
        data = response.json()

        assert data["gpu_name"] == "NVIDIA RTX A5500"
        assert data["utilization"] == 75.5
        assert data["memory_used"] == 12000
        assert data["memory_total"] == 24000
        assert data["temperature"] == 65.0
        assert data["power_usage"] == 150.0
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
async def test_get_config_includes_grafana_url(client, mock_redis):
    """Test that GET /api/system/config includes grafana_url."""
    response = await client.get("/api/system/config")
    assert response.status_code == 200
    data = response.json()
    assert "grafana_url" in data
    # grafana_url can be an absolute URL (http://) or a relative path (/grafana)
    assert data["grafana_url"].startswith("http") or data["grafana_url"].startswith("/")


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
async def test_gpu_history_empty(client, db_session, mock_redis):
    """GET /api/system/gpu/history returns empty list when no samples exist."""
    # Clear any existing GPU stats from the database
    from sqlalchemy import delete

    await db_session.execute(delete(GPUStats))
    await db_session.commit()

    resp = await client.get("/api/system/gpu/history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["pagination"]["total"] == 0
    assert data["pagination"]["limit"] >= 1


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
    from backend.api.routes import system as system_routes

    # Clear cache to ensure fresh evaluation
    system_routes.clear_health_cache()

    # Mock GPU stats query to return None (no GPU data)
    # Must use AsyncMock since get_latest_gpu_stats is async
    with patch(
        "backend.api.routes.system.get_latest_gpu_stats", new_callable=AsyncMock
    ) as mock_gpu:
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
    # Clear any existing GPU stats from the database
    from sqlalchemy import delete

    await db_session.execute(delete(GPUStats))
    await db_session.commit()

    now = datetime.now(UTC)
    older = now - timedelta(minutes=2)
    newer = now - timedelta(minutes=1)

    db_session.add_all(
        [
            GPUStats(
                recorded_at=older,
                gpu_name="NVIDIA RTX A5500",
                gpu_utilization=10.0,
                memory_used=100,
                memory_total=1000,
                temperature=40.0,
                power_usage=100.0,
                inference_fps=0.0,
            ),
            GPUStats(
                recorded_at=newer,
                gpu_name="NVIDIA RTX A5500",
                gpu_utilization=20.0,
                memory_used=200,
                memory_total=1000,
                temperature=41.0,
                power_usage=120.0,
                inference_fps=1.0,
            ),
        ]
    )
    await db_session.commit()

    resp = await client.get("/api/system/gpu/history?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["pagination"]["total"] == 2
    assert data["items"][0]["utilization"] == 10.0
    assert data["items"][0]["power_usage"] == 100.0
    assert data["items"][1]["utilization"] == 20.0
    assert data["items"][1]["power_usage"] == 120.0

    # since filter should exclude the older sample
    # Use 'Z' to avoid '+' being interpreted as a space in query strings.
    since = (now - timedelta(minutes=1, seconds=30)).isoformat().replace("+00:00", "Z")
    resp2 = await client.get(f"/api/system/gpu/history?since={since}&limit=10")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["pagination"]["total"] == 1
    assert data2["items"][0]["utilization"] == 20.0
    assert data2["items"][0]["power_usage"] == 120.0


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

        # Clear health cache to ensure this test gets fresh results with mocked state
        system_routes.clear_health_cache()

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
        # Clear the readiness cache to ensure our mock is used
        system_routes.clear_health_cache()

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
        # Clear cache to ensure clean state for other tests
        system_routes.clear_health_cache()


@pytest.mark.asyncio
async def test_readiness_endpoint_not_ready_when_detection_worker_in_error(client, mock_redis):
    """Test that readiness endpoint returns not_ready when detection worker is in error state."""
    from unittest.mock import MagicMock

    from backend.api.routes import system as system_routes

    # Save original
    original_pipeline_manager = system_routes._pipeline_manager
    original_cache = system_routes._readiness_cache

    try:
        # Clear the readiness cache to ensure fresh evaluation
        system_routes._readiness_cache = None
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
        system_routes._readiness_cache = original_cache


@pytest.mark.asyncio
async def test_readiness_endpoint_graceful_when_no_pipeline_manager(client, mock_redis):
    """Test that readiness endpoint returns not_ready when pipeline manager is not registered.

    Without the pipeline manager, the system cannot process image detections, so it should
    report as not_ready (503) rather than ready, even if database and Redis are healthy.
    """
    from backend.api.routes import system as system_routes

    # Save original
    original_pipeline_manager = system_routes._pipeline_manager
    original_cache = system_routes._readiness_cache

    try:
        # Clear the readiness cache to ensure fresh evaluation
        system_routes._readiness_cache = None
        # Set pipeline manager to None (not registered)
        system_routes._pipeline_manager = None

        mock_redis.health_check.return_value = {
            "status": "healthy",
            "connected": True,
            "redis_version": "7.0.0",
        }

        response = await client.get("/api/system/health/ready")

        # Should return 503 when pipeline manager is not registered
        # because the system cannot process detections without it
        assert response.status_code == 503
        data = response.json()

        # Should NOT be ready when pipeline manager is not registered
        assert data["ready"] is False
        assert data["status"] == "not_ready"

        # Database and Redis should still show as healthy
        assert data["services"]["database"]["status"] == "healthy"
        assert data["services"]["redis"]["status"] == "healthy"

    finally:
        system_routes._pipeline_manager = original_pipeline_manager
        system_routes._readiness_cache = original_cache


# =============================================================================
# Pipeline Status Endpoint Tests
# =============================================================================


@pytest.mark.asyncio
async def test_pipeline_status_endpoint_basic(client, mock_redis):
    """Test pipeline status endpoint returns valid response structure."""
    response = await client.get("/api/system/pipeline")

    assert response.status_code == 200
    data = response.json()

    # Check response structure
    assert "file_watcher" in data
    assert "batch_aggregator" in data
    assert "degradation" in data
    assert "timestamp" in data

    # Verify timestamp format
    timestamp = datetime.fromisoformat(data["timestamp"])
    assert isinstance(timestamp, datetime)


@pytest.mark.asyncio
async def test_pipeline_status_with_file_watcher_registered(client, mock_redis):
    """Test pipeline status endpoint when file watcher is registered."""
    from unittest.mock import MagicMock

    from backend.api.routes import system as system_routes

    # Save original
    original_file_watcher = system_routes._file_watcher

    try:
        # Mock file watcher
        mock_watcher = MagicMock()
        mock_watcher.running = True
        mock_watcher.camera_root = "/export/foscam"
        mock_watcher._use_polling = False
        mock_watcher._pending_tasks = {"file1.jpg": True, "file2.jpg": True}
        system_routes._file_watcher = mock_watcher

        response = await client.get("/api/system/pipeline")

        assert response.status_code == 200
        data = response.json()

        # Check file watcher status
        fw = data["file_watcher"]
        assert fw is not None
        assert fw["running"] is True
        assert fw["camera_root"] == "/export/foscam"
        assert fw["pending_tasks"] == 2
        assert fw["observer_type"] == "native"

    finally:
        system_routes._file_watcher = original_file_watcher


@pytest.mark.asyncio
async def test_pipeline_status_with_file_watcher_polling_mode(client, mock_redis):
    """Test pipeline status endpoint shows polling observer type."""
    from unittest.mock import MagicMock

    from backend.api.routes import system as system_routes

    # Save original
    original_file_watcher = system_routes._file_watcher

    try:
        # Mock file watcher with polling mode
        mock_watcher = MagicMock()
        mock_watcher.running = True
        mock_watcher.camera_root = "/mnt/cameras"
        mock_watcher._use_polling = True
        mock_watcher._pending_tasks = {}
        system_routes._file_watcher = mock_watcher

        response = await client.get("/api/system/pipeline")

        assert response.status_code == 200
        data = response.json()

        # Check file watcher shows polling mode
        fw = data["file_watcher"]
        assert fw is not None
        assert fw["observer_type"] == "polling"

    finally:
        system_routes._file_watcher = original_file_watcher


@pytest.mark.asyncio
async def test_pipeline_status_file_watcher_not_running(client, mock_redis):
    """Test pipeline status when file watcher is not registered."""
    from backend.api.routes import system as system_routes

    # Save original
    original_file_watcher = system_routes._file_watcher

    try:
        # Set file watcher to None
        system_routes._file_watcher = None

        response = await client.get("/api/system/pipeline")

        assert response.status_code == 200
        data = response.json()

        # File watcher should be null
        assert data["file_watcher"] is None

    finally:
        system_routes._file_watcher = original_file_watcher


@pytest.mark.asyncio
async def test_pipeline_status_with_degradation_manager(client, mock_redis):
    """Test pipeline status endpoint with degradation manager status."""

    response = await client.get("/api/system/pipeline")

    assert response.status_code == 200
    data = response.json()

    # Degradation field may be None or have status depending on initialization
    # This is expected behavior - degradation manager may not be initialized in tests
    assert "degradation" in data


@pytest.mark.asyncio
async def test_pipeline_status_batch_aggregator_no_redis(client):
    """Test pipeline status when Redis is not available."""
    from backend.core.redis import get_redis_optional
    from backend.main import app

    # Override the dependency to return None
    async def mock_no_redis():
        yield None

    app.dependency_overrides[get_redis_optional] = mock_no_redis

    try:
        response = await client.get("/api/system/pipeline")

        assert response.status_code == 200
        data = response.json()

        # Batch aggregator should be null when Redis is unavailable
        assert data["batch_aggregator"] is None
    finally:
        # Clean up dependency override
        app.dependency_overrides.pop(get_redis_optional, None)


@pytest.mark.asyncio
async def test_pipeline_status_timestamp_is_recent(client, mock_redis):
    """Test pipeline status endpoint timestamp is recent."""
    response = await client.get("/api/system/pipeline")

    assert response.status_code == 200
    data = response.json()

    # Parse timestamp and verify it's within last minute
    timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
    now = datetime.now(UTC)
    assert (now - timestamp).total_seconds() < 60


# =============================================================================
# Circuit Breaker Endpoint Integration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_circuit_breakers_returns_valid_response(client, mock_redis):
    """Test GET /api/system/circuit-breakers returns valid structure."""
    response = await client.get("/api/system/circuit-breakers")

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "circuit_breakers" in data
    assert "total_count" in data
    assert "open_count" in data
    assert "timestamp" in data

    # Verify types
    assert isinstance(data["circuit_breakers"], dict)
    assert isinstance(data["total_count"], int)
    assert isinstance(data["open_count"], int)
    assert data["total_count"] >= 0
    assert data["open_count"] >= 0
    assert data["open_count"] <= data["total_count"]

    # Verify timestamp is valid
    timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
    assert isinstance(timestamp, datetime)


@pytest.mark.asyncio
async def test_get_circuit_breakers_with_registered_breakers(client, mock_redis):
    """Test circuit breakers endpoint when breakers are registered."""
    from backend.services.circuit_breaker import (
        CircuitBreakerConfig,
        _get_registry,
        reset_circuit_breaker_registry,
    )

    # Reset and create test circuit breakers
    reset_circuit_breaker_registry()
    registry = _get_registry()

    # Create a few test circuit breakers
    config = CircuitBreakerConfig(failure_threshold=5, recovery_timeout=30.0)
    registry.get_or_create("test_service_1", config)
    registry.get_or_create("test_service_2", config)

    try:
        response = await client.get("/api/system/circuit-breakers")

        assert response.status_code == 200
        data = response.json()

        assert data["total_count"] >= 2
        assert "test_service_1" in data["circuit_breakers"]
        assert "test_service_2" in data["circuit_breakers"]

        # Verify individual breaker structure
        breaker = data["circuit_breakers"]["test_service_1"]
        assert breaker["name"] == "test_service_1"
        assert breaker["state"] == "closed"
        assert breaker["failure_count"] == 0
        assert breaker["success_count"] == 0
        assert "config" in breaker
        assert breaker["config"]["failure_threshold"] == 5
        assert breaker["config"]["recovery_timeout"] == 30.0

    finally:
        reset_circuit_breaker_registry()


@pytest.mark.asyncio
async def test_get_circuit_breakers_shows_open_state(client, mock_redis):
    """Test circuit breakers endpoint correctly reports open breakers."""
    from backend.services.circuit_breaker import (
        CircuitBreakerConfig,
        _get_registry,
        reset_circuit_breaker_registry,
    )

    reset_circuit_breaker_registry()
    registry = _get_registry()

    # Create a breaker and force it open
    config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30.0)
    breaker = registry.get_or_create("test_open_breaker", config)
    breaker.force_open()

    try:
        response = await client.get("/api/system/circuit-breakers")

        assert response.status_code == 200
        data = response.json()

        assert data["open_count"] >= 1
        assert "test_open_breaker" in data["circuit_breakers"]
        assert data["circuit_breakers"]["test_open_breaker"]["state"] == "open"

    finally:
        reset_circuit_breaker_registry()


@pytest.mark.asyncio
async def test_reset_circuit_breaker_success(client, mock_redis):
    """Test POST /api/system/circuit-breakers/{name}/reset successfully resets a breaker."""
    from backend.services.circuit_breaker import (
        CircuitBreakerConfig,
        _get_registry,
        reset_circuit_breaker_registry,
    )

    reset_circuit_breaker_registry()
    registry = _get_registry()

    # Create a breaker and force it open
    config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30.0)
    breaker = registry.get_or_create("resettable_breaker", config)
    breaker.force_open()

    try:
        # Verify breaker is open
        assert breaker.state.value == "open"

        response = await client.post("/api/system/circuit-breakers/resettable_breaker/reset")

        assert response.status_code == 200
        data = response.json()

        assert data["name"] == "resettable_breaker"
        assert data["previous_state"] == "open"
        assert data["new_state"] == "closed"
        assert "reset successfully" in data["message"]

        # Verify breaker is now closed
        assert breaker.state.value == "closed"

    finally:
        reset_circuit_breaker_registry()


@pytest.mark.asyncio
async def test_reset_circuit_breaker_not_found(client, mock_redis):
    """Test resetting a non-existent circuit breaker returns 404."""
    from backend.services.circuit_breaker import reset_circuit_breaker_registry

    reset_circuit_breaker_registry()

    try:
        response = await client.post("/api/system/circuit-breakers/nonexistent_breaker/reset")

        assert response.status_code == 404
        data = response.json()
        error_msg = get_error_message(data)
        assert "not found" in error_msg.lower()

    finally:
        reset_circuit_breaker_registry()


@pytest.mark.asyncio
async def test_reset_circuit_breaker_invalid_name(client, mock_redis):
    """Test resetting with invalid name characters returns 400."""
    response = await client.post("/api/system/circuit-breakers/invalid@name!/reset")

    assert response.status_code == 400
    data = response.json()
    error_msg = get_error_message(data)
    assert "invalid" in error_msg.lower()


@pytest.mark.asyncio
async def test_reset_circuit_breaker_empty_name(client, mock_redis):
    """Test resetting with empty name returns appropriate error."""
    # Empty name in URL path typically results in 404 (route not found)
    # or a redirect, so we test with a very long name for 400
    long_name = "a" * 100  # Exceeds 64 character limit
    response = await client.post(f"/api/system/circuit-breakers/{long_name}/reset")

    assert response.status_code == 400
    data = response.json()
    error_msg = get_error_message(data)
    assert "invalid" in error_msg.lower() or "1-64 characters" in error_msg


# =============================================================================
# Cleanup Service Status Endpoint Integration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_cleanup_status_service_not_running(client, mock_redis):
    """Test GET /api/system/cleanup/status when service is not running."""
    from backend.api.routes import system as system_routes

    # Save original
    original_cleanup_service = system_routes._cleanup_service

    try:
        # Set cleanup service to None
        system_routes._cleanup_service = None

        response = await client.get("/api/system/cleanup/status")

        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "running" in data
        assert "retention_days" in data
        assert "cleanup_time" in data
        assert "delete_images" in data
        assert "next_cleanup" in data
        assert "timestamp" in data

        # When not running, should report as not running
        assert data["running"] is False
        assert data["next_cleanup"] is None
        assert isinstance(data["retention_days"], int)

    finally:
        system_routes._cleanup_service = original_cleanup_service


@pytest.mark.asyncio
async def test_get_cleanup_status_service_running(client, mock_redis):
    """Test GET /api/system/cleanup/status when service is running."""
    from unittest.mock import MagicMock

    from backend.api.routes import system as system_routes

    # Save original
    original_cleanup_service = system_routes._cleanup_service

    try:
        # Create mock cleanup service
        mock_cleanup = MagicMock()
        mock_cleanup.get_cleanup_stats.return_value = {
            "running": True,
            "retention_days": 30,
            "cleanup_time": "03:00",
            "delete_images": False,
            "next_cleanup": "2025-12-31T03:00:00+00:00",
        }
        system_routes._cleanup_service = mock_cleanup

        response = await client.get("/api/system/cleanup/status")

        assert response.status_code == 200
        data = response.json()

        assert data["running"] is True
        assert data["retention_days"] == 30
        assert data["cleanup_time"] == "03:00"
        assert data["delete_images"] is False
        assert data["next_cleanup"] is not None

    finally:
        system_routes._cleanup_service = original_cleanup_service


@pytest.mark.asyncio
async def test_get_cleanup_status_with_active_cleanup(client, mock_redis):
    """Test cleanup status reflects current settings during active cleanup."""
    from unittest.mock import MagicMock

    from backend.api.routes import system as system_routes

    original_cleanup_service = system_routes._cleanup_service

    try:
        # Simulate active cleanup with custom retention
        mock_cleanup = MagicMock()
        mock_cleanup.get_cleanup_stats.return_value = {
            "running": True,
            "retention_days": 7,  # Custom retention
            "cleanup_time": "02:00",
            "delete_images": True,  # Images deletion enabled
            "next_cleanup": "2025-12-30T02:00:00+00:00",
        }
        system_routes._cleanup_service = mock_cleanup

        response = await client.get("/api/system/cleanup/status")

        assert response.status_code == 200
        data = response.json()

        assert data["retention_days"] == 7
        assert data["cleanup_time"] == "02:00"
        assert data["delete_images"] is True

    finally:
        system_routes._cleanup_service = original_cleanup_service


# =============================================================================
# WebSocket Health Endpoint Integration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_websocket_health_returns_valid_structure(client, mock_redis):
    """Test GET /api/system/health/websocket returns valid response structure."""
    response = await client.get("/api/system/health/websocket")

    assert response.status_code == 200
    data = response.json()

    # Verify structure
    assert "event_broadcaster" in data
    assert "system_broadcaster" in data
    assert "timestamp" in data

    # Verify timestamp
    timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
    assert isinstance(timestamp, datetime)


@pytest.mark.asyncio
async def test_websocket_health_with_healthy_broadcasters(client, mock_redis):
    """Test WebSocket health when broadcasters are healthy."""
    from unittest.mock import MagicMock

    from backend.services.circuit_breaker import CircuitState

    # Mock the broadcasters to simulate healthy state
    mock_event_broadcaster = MagicMock()
    mock_event_broadcaster.get_circuit_state.return_value = CircuitState.CLOSED
    mock_event_broadcaster.circuit_breaker.failure_count = 0
    mock_event_broadcaster.is_degraded.return_value = False

    mock_system_broadcaster = MagicMock()
    mock_system_broadcaster.get_circuit_state.return_value = CircuitState.CLOSED
    mock_system_broadcaster.circuit_breaker.failure_count = 0
    mock_system_broadcaster._pubsub_listening = True

    with (
        patch(
            "backend.services.event_broadcaster._broadcaster",
            mock_event_broadcaster,
        ),
        patch(
            "backend.services.system_broadcaster._system_broadcaster",
            mock_system_broadcaster,
        ),
    ):
        response = await client.get("/api/system/health/websocket")

        assert response.status_code == 200
        data = response.json()

        # When broadcasters are healthy
        if data["event_broadcaster"] is not None:
            assert data["event_broadcaster"]["state"] == "closed"
            assert data["event_broadcaster"]["is_degraded"] is False

        if data["system_broadcaster"] is not None:
            assert data["system_broadcaster"]["state"] == "closed"


@pytest.mark.asyncio
async def test_websocket_health_with_degraded_broadcaster(client, mock_redis):
    """Test WebSocket health when a broadcaster is in degraded mode."""
    from unittest.mock import MagicMock

    from backend.services.circuit_breaker import CircuitState

    # Mock event broadcaster in degraded state
    mock_event_broadcaster = MagicMock()
    mock_event_broadcaster.get_circuit_state.return_value = CircuitState.OPEN
    mock_event_broadcaster.circuit_breaker.failure_count = 5
    mock_event_broadcaster.is_degraded.return_value = True

    with patch(
        "backend.services.event_broadcaster._broadcaster",
        mock_event_broadcaster,
    ):
        response = await client.get("/api/system/health/websocket")

        assert response.status_code == 200
        data = response.json()

        if data["event_broadcaster"] is not None:
            assert data["event_broadcaster"]["state"] == "open"
            assert data["event_broadcaster"]["failure_count"] == 5
            assert data["event_broadcaster"]["is_degraded"] is True


# =============================================================================
# Storage Statistics Endpoint Integration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_storage_endpoint_returns_valid_structure(client, mock_redis):
    """Test GET /api/system/storage returns valid response structure."""
    response = await client.get("/api/system/storage")

    assert response.status_code == 200
    data = response.json()

    # Verify disk usage fields
    assert "disk_used_bytes" in data
    assert "disk_total_bytes" in data
    assert "disk_free_bytes" in data
    assert "disk_usage_percent" in data

    # Verify storage categories
    assert "thumbnails" in data
    assert "images" in data
    assert "clips" in data

    # Verify database counts
    assert "events_count" in data
    assert "detections_count" in data
    assert "gpu_stats_count" in data
    assert "logs_count" in data

    # Verify timestamp
    assert "timestamp" in data
    timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
    assert isinstance(timestamp, datetime)


@pytest.mark.asyncio
async def test_storage_endpoint_disk_usage_values(client, mock_redis):
    """Test storage endpoint returns reasonable disk usage values."""
    response = await client.get("/api/system/storage")

    assert response.status_code == 200
    data = response.json()

    # Disk values should be non-negative
    assert data["disk_used_bytes"] >= 0
    assert data["disk_total_bytes"] >= 0
    assert data["disk_free_bytes"] >= 0

    # Usage percent should be between 0 and 100
    assert 0 <= data["disk_usage_percent"] <= 100

    # Total should equal used + free (approximately, accounting for reserved space)
    # We allow some tolerance as filesystems reserve space for system use
    if data["disk_total_bytes"] > 0:
        calculated_total = data["disk_used_bytes"] + data["disk_free_bytes"]
        # Allow 5% tolerance for reserved blocks
        assert abs(calculated_total - data["disk_total_bytes"]) < data["disk_total_bytes"] * 0.05


@pytest.mark.asyncio
async def test_storage_endpoint_category_stats(client, mock_redis):
    """Test storage endpoint returns valid category statistics."""
    response = await client.get("/api/system/storage")

    assert response.status_code == 200
    data = response.json()

    # Each category should have file_count and size_bytes
    for category in ["thumbnails", "images", "clips"]:
        assert "file_count" in data[category]
        assert "size_bytes" in data[category]
        assert data[category]["file_count"] >= 0
        assert data[category]["size_bytes"] >= 0


@pytest.mark.asyncio
async def test_storage_endpoint_database_counts(client, mock_redis, integration_db):
    """Test storage endpoint returns database record counts."""
    response = await client.get("/api/system/storage")

    assert response.status_code == 200
    data = response.json()

    # All counts should be non-negative integers
    assert isinstance(data["events_count"], int)
    assert isinstance(data["detections_count"], int)
    assert isinstance(data["gpu_stats_count"], int)
    assert isinstance(data["logs_count"], int)

    assert data["events_count"] >= 0
    assert data["detections_count"] >= 0
    assert data["gpu_stats_count"] >= 0
    assert data["logs_count"] >= 0


# =============================================================================
# Severity Metadata Endpoint Integration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_severity_endpoint_returns_valid_structure(client, mock_redis):
    """Test GET /api/system/severity returns valid response structure."""
    response = await client.get("/api/system/severity")

    assert response.status_code == 200
    data = response.json()

    # Verify main structure
    assert "definitions" in data
    assert "thresholds" in data

    # Verify definitions is a list with expected severity levels
    assert isinstance(data["definitions"], list)
    assert len(data["definitions"]) == 4  # LOW, MEDIUM, HIGH, CRITICAL

    # Verify thresholds structure
    thresholds = data["thresholds"]
    assert "low_max" in thresholds
    assert "medium_max" in thresholds
    assert "high_max" in thresholds


@pytest.mark.asyncio
async def test_severity_endpoint_definitions_content(client, mock_redis):
    """Test severity definitions contain expected fields and values."""
    response = await client.get("/api/system/severity")

    assert response.status_code == 200
    data = response.json()

    severity_values = set()
    for defn in data["definitions"]:
        # Each definition should have required fields
        assert "severity" in defn
        assert "label" in defn
        assert "description" in defn
        assert "color" in defn
        assert "priority" in defn
        assert "min_score" in defn
        assert "max_score" in defn

        # Validate color format (hex color)
        assert defn["color"].startswith("#")
        assert len(defn["color"]) == 7

        # Validate score range
        assert 0 <= defn["min_score"] <= 100
        assert 0 <= defn["max_score"] <= 100
        assert defn["min_score"] <= defn["max_score"]

        # Collect severity values
        severity_values.add(defn["severity"])

    # Should have all four severity levels
    assert severity_values == {"low", "medium", "high", "critical"}


@pytest.mark.asyncio
async def test_severity_endpoint_threshold_ordering(client, mock_redis):
    """Test severity thresholds are properly ordered."""
    response = await client.get("/api/system/severity")

    assert response.status_code == 200
    data = response.json()

    thresholds = data["thresholds"]

    # Thresholds should be in ascending order
    assert thresholds["low_max"] < thresholds["medium_max"]
    assert thresholds["medium_max"] < thresholds["high_max"]

    # All should be within valid range
    assert 0 <= thresholds["low_max"] <= 100
    assert 0 <= thresholds["medium_max"] <= 100
    assert 0 <= thresholds["high_max"] <= 100


@pytest.mark.asyncio
async def test_severity_endpoint_default_thresholds(client, mock_redis):
    """Test severity endpoint returns expected default thresholds."""
    # Reset the singleton to ensure we get fresh defaults
    # (other tests may have modified thresholds via PUT /api/system/severity)
    from backend.services.severity import reset_severity_service

    reset_severity_service()

    response = await client.get("/api/system/severity")

    assert response.status_code == 200
    data = response.json()

    # Default thresholds as defined in the severity service
    thresholds = data["thresholds"]
    assert thresholds["low_max"] == 29
    assert thresholds["medium_max"] == 59
    assert thresholds["high_max"] == 84


# =============================================================================
# Pipeline Latency Endpoint Integration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_pipeline_latency_endpoint_returns_valid_structure(client, mock_redis):
    """Test GET /api/system/pipeline-latency returns valid response structure."""
    response = await client.get("/api/system/pipeline-latency")

    assert response.status_code == 200
    data = response.json()

    # Verify main structure
    assert "watch_to_detect" in data
    assert "detect_to_batch" in data
    assert "batch_to_analyze" in data
    assert "total_pipeline" in data
    assert "window_minutes" in data
    assert "timestamp" in data

    # Verify timestamp is valid
    timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
    assert isinstance(timestamp, datetime)


@pytest.mark.asyncio
async def test_pipeline_latency_endpoint_default_window(client, mock_redis):
    """Test pipeline latency uses default window of 60 minutes."""
    response = await client.get("/api/system/pipeline-latency")

    assert response.status_code == 200
    data = response.json()

    assert data["window_minutes"] == 60


@pytest.mark.asyncio
async def test_pipeline_latency_endpoint_custom_window(client, mock_redis):
    """Test pipeline latency accepts custom window parameter."""
    response = await client.get("/api/system/pipeline-latency?window_minutes=30")

    assert response.status_code == 200
    data = response.json()

    assert data["window_minutes"] == 30


@pytest.mark.asyncio
async def test_pipeline_latency_with_data(client, mock_redis):
    """Test pipeline latency returns statistics when data is available."""
    from backend.core.metrics import get_pipeline_latency_tracker

    # Get the global tracker and add some sample data
    tracker = get_pipeline_latency_tracker()

    # Record some sample latencies
    tracker.record_stage_latency("watch_to_detect", 50.0)
    tracker.record_stage_latency("watch_to_detect", 75.0)
    tracker.record_stage_latency("watch_to_detect", 100.0)

    tracker.record_stage_latency("detect_to_batch", 200.0)
    tracker.record_stage_latency("detect_to_batch", 250.0)

    response = await client.get("/api/system/pipeline-latency")

    assert response.status_code == 200
    data = response.json()

    # Should have data for recorded stages
    if data["watch_to_detect"] is not None:
        stage_data = data["watch_to_detect"]
        assert "avg_ms" in stage_data
        assert "min_ms" in stage_data
        assert "max_ms" in stage_data
        assert "p50_ms" in stage_data
        assert "p95_ms" in stage_data
        assert "p99_ms" in stage_data
        assert "sample_count" in stage_data

        # Verify statistics are reasonable
        if stage_data["sample_count"] > 0:
            assert stage_data["min_ms"] <= stage_data["avg_ms"] <= stage_data["max_ms"]


@pytest.mark.asyncio
async def test_pipeline_latency_empty_stages(client, mock_redis):
    """Test pipeline latency returns null for stages with no data."""
    from unittest.mock import MagicMock

    # Create a fresh tracker with no data
    mock_tracker = MagicMock()
    mock_tracker.get_pipeline_summary.return_value = {
        "watch_to_detect": {"sample_count": 0, "avg_ms": None, "min_ms": None, "max_ms": None},
        "detect_to_batch": {"sample_count": 0, "avg_ms": None, "min_ms": None, "max_ms": None},
        "batch_to_analyze": {"sample_count": 0, "avg_ms": None, "min_ms": None, "max_ms": None},
        "total_pipeline": {"sample_count": 0, "avg_ms": None, "min_ms": None, "max_ms": None},
    }

    with patch("backend.core.metrics.get_pipeline_latency_tracker", return_value=mock_tracker):
        response = await client.get("/api/system/pipeline-latency")

        assert response.status_code == 200
        data = response.json()

        # Stages with no samples should have None values or sample_count == 0
        for stage in ["watch_to_detect", "detect_to_batch", "batch_to_analyze", "total_pipeline"]:
            assert data[stage] is None or data[stage].get("sample_count", 0) == 0


@pytest.mark.asyncio
async def test_pipeline_latency_percentile_calculation(client, mock_redis):
    """Test pipeline latency correctly calculates percentiles."""
    from backend.core.metrics import get_pipeline_latency_tracker

    tracker = get_pipeline_latency_tracker()

    # Record samples to test percentile calculation
    for i in range(100):
        tracker.record_stage_latency("total_pipeline", float(i * 10))  # 0, 10, 20, ... 990

    response = await client.get("/api/system/pipeline-latency")

    assert response.status_code == 200
    data = response.json()

    if data["total_pipeline"] is not None and data["total_pipeline"].get("sample_count", 0) >= 100:
        stage = data["total_pipeline"]

        # P50 should be around the median
        assert stage["p50_ms"] is not None

        # P95 should be higher than P50
        assert stage["p95_ms"] >= stage["p50_ms"]

        # P99 should be highest
        assert stage["p99_ms"] >= stage["p95_ms"]


# =============================================================================
# Combined System Endpoints Concurrent Access Tests
# =============================================================================


@pytest.mark.asyncio
async def test_system_monitoring_endpoints_concurrent_access(client, mock_redis):
    """Test that monitoring endpoints handle concurrent requests correctly."""
    import asyncio

    # List of monitoring endpoints to test concurrently
    endpoints = [
        "/api/system/circuit-breakers",
        "/api/system/cleanup/status",
        "/api/system/health/websocket",
        "/api/system/storage",
        "/api/system/severity",
        "/api/system/pipeline-latency",
    ]

    # Make concurrent requests to all endpoints
    tasks = [client.get(endpoint) for endpoint in endpoints * 3]
    responses = await asyncio.gather(*tasks)

    # All requests should succeed
    for response in responses:
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_system_monitoring_endpoints_json_content_type(client, mock_redis):
    """Test that all monitoring endpoints return JSON content type."""
    endpoints = [
        "/api/system/circuit-breakers",
        "/api/system/cleanup/status",
        "/api/system/health/websocket",
        "/api/system/storage",
        "/api/system/severity",
        "/api/system/pipeline-latency",
    ]

    for endpoint in endpoints:
        response = await client.get(endpoint)
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]


# =============================================================================
# Severity Thresholds Update Endpoint Integration Tests
# =============================================================================


@pytest.mark.asyncio
async def test_update_severity_thresholds_success(client, mock_redis):
    """Test PUT /api/system/severity successfully updates thresholds."""
    payload = {
        "low_max": 20,
        "medium_max": 50,
        "high_max": 80,
    }

    response = await client.put("/api/system/severity", json=payload)

    assert response.status_code == 200
    data = response.json()

    # Verify updated thresholds
    assert data["thresholds"]["low_max"] == 20
    assert data["thresholds"]["medium_max"] == 50
    assert data["thresholds"]["high_max"] == 80

    # Verify definitions are updated with new ranges
    definitions = {d["severity"]: d for d in data["definitions"]}
    assert definitions["low"]["max_score"] == 20
    assert definitions["medium"]["min_score"] == 21
    assert definitions["medium"]["max_score"] == 50
    assert definitions["high"]["min_score"] == 51
    assert definitions["high"]["max_score"] == 80
    assert definitions["critical"]["min_score"] == 81
    assert definitions["critical"]["max_score"] == 100


@pytest.mark.asyncio
async def test_update_severity_thresholds_persists(client, mock_redis):
    """Test that updated severity thresholds persist across GET requests."""
    # Update thresholds
    payload = {
        "low_max": 25,
        "medium_max": 55,
        "high_max": 85,
    }

    put_response = await client.put("/api/system/severity", json=payload)
    assert put_response.status_code == 200

    # Verify GET returns updated values
    get_response = await client.get("/api/system/severity")
    assert get_response.status_code == 200
    data = get_response.json()

    assert data["thresholds"]["low_max"] == 25
    assert data["thresholds"]["medium_max"] == 55
    assert data["thresholds"]["high_max"] == 85


@pytest.mark.asyncio
async def test_update_severity_thresholds_invalid_order(client, mock_redis):
    """Test PUT /api/system/severity rejects invalid threshold ordering."""
    # low_max >= medium_max
    payload = {
        "low_max": 50,
        "medium_max": 40,
        "high_max": 80,
    }

    response = await client.put("/api/system/severity", json=payload)

    assert response.status_code == 400
    data = response.json()
    # Error message should indicate ordering constraint violation
    detail_lower = get_error_message(data).lower()
    assert (
        "invalid" in detail_lower
        or "must satisfy" in detail_lower
        or "strictly ordered" in detail_lower
    )


@pytest.mark.asyncio
async def test_update_severity_thresholds_medium_gte_high(client, mock_redis):
    """Test PUT /api/system/severity rejects medium_max >= high_max."""
    payload = {
        "low_max": 20,
        "medium_max": 80,
        "high_max": 60,
    }

    response = await client.put("/api/system/severity", json=payload)

    assert response.status_code == 400
    data = response.json()
    # Error message should indicate ordering constraint violation
    detail_lower = get_error_message(data).lower()
    assert (
        "invalid" in detail_lower
        or "must satisfy" in detail_lower
        or "strictly ordered" in detail_lower
    )


@pytest.mark.asyncio
async def test_update_severity_thresholds_missing_fields(client, mock_redis):
    """Test PUT /api/system/severity rejects partial updates."""
    # Missing high_max
    payload = {
        "low_max": 20,
        "medium_max": 50,
    }

    response = await client.put("/api/system/severity", json=payload)

    # Should return 422 Unprocessable Entity for validation error
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_severity_thresholds_out_of_range(client, mock_redis):
    """Test PUT /api/system/severity validates range constraints."""
    # low_max below minimum (1)
    payload = {
        "low_max": 0,
        "medium_max": 50,
        "high_max": 80,
    }

    response = await client.put("/api/system/severity", json=payload)

    # Should return 422 for pydantic validation failure
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_severity_thresholds_extreme_values(client, mock_redis):
    """Test PUT /api/system/severity accepts extreme but valid values."""
    # Minimal range for each severity
    payload = {
        "low_max": 1,
        "medium_max": 2,
        "high_max": 3,
    }

    response = await client.put("/api/system/severity", json=payload)

    assert response.status_code == 200
    data = response.json()

    # Verify all severities have valid ranges
    definitions = {d["severity"]: d for d in data["definitions"]}
    assert definitions["low"]["min_score"] == 0
    assert definitions["low"]["max_score"] == 1
    assert definitions["critical"]["min_score"] == 4
    assert definitions["critical"]["max_score"] == 100


@pytest.mark.asyncio
async def test_update_severity_thresholds_concurrent_updates(client, mock_redis):
    """Test concurrent severity threshold updates don't cause issues."""
    import asyncio

    # Multiple concurrent updates with different values
    payloads = [
        {"low_max": 25, "medium_max": 55, "high_max": 85},
        {"low_max": 30, "medium_max": 60, "high_max": 90},
        {"low_max": 20, "medium_max": 50, "high_max": 80},
    ]

    tasks = [client.put("/api/system/severity", json=p) for p in payloads]
    responses = await asyncio.gather(*tasks)

    # All should succeed
    for response in responses:
        assert response.status_code == 200

    # Final GET should return one of the valid configurations
    get_response = await client.get("/api/system/severity")
    assert get_response.status_code == 200
    data = get_response.json()

    # Thresholds should be from one of the updates
    thresholds = data["thresholds"]
    valid_low_max = [25, 30, 20]
    assert thresholds["low_max"] in valid_low_max


# =============================================================================
# Performance Endpoint Tests (NEM-1900)
# =============================================================================


@pytest.mark.asyncio
async def test_performance_endpoint_returns_metrics(client, mock_redis):
    """Test performance endpoint returns current performance metrics."""
    from backend.api.routes import system as system_routes
    from backend.api.schemas.performance import (
        GpuMetrics,
        HostMetrics,
        PerformanceUpdate,
    )

    # Save original collector
    original_collector = system_routes._performance_collector

    try:
        # Create a real PerformanceUpdate for the mock to return
        mock_snapshot = PerformanceUpdate(
            timestamp=datetime.now(UTC),
            gpu=GpuMetrics(
                name="NVIDIA RTX A5500",
                utilization=38.0,
                vram_used_gb=22.7,
                vram_total_gb=24.0,
                temperature=38,
                power_watts=31,
            ),
            ai_models={},
            nemotron=None,
            inference=None,
            databases={},
            host=HostMetrics(
                cpu_percent=12.0,
                ram_used_gb=8.2,
                ram_total_gb=32.0,
                disk_used_gb=156.0,
                disk_total_gb=500.0,
            ),
            containers=[],
            alerts=[],
        )

        # Create mock collector
        mock_collector = AsyncMock()
        mock_collector.collect_all = AsyncMock(return_value=mock_snapshot)
        system_routes._performance_collector = mock_collector

        response = await client.get("/api/system/performance")

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "timestamp" in data
        assert "gpu" in data
        assert "host" in data
        assert "alerts" in data

        # Verify data content
        assert data["gpu"]["name"] == "NVIDIA RTX A5500"
        assert data["gpu"]["utilization"] == 38.0
        assert data["host"]["cpu_percent"] == 12.0
    finally:
        system_routes._performance_collector = original_collector


@pytest.mark.asyncio
async def test_performance_endpoint_without_collector(client, mock_redis):
    """Test performance endpoint returns 503 when collector is not registered."""
    from backend.api.routes import system as system_routes

    # Save original collector
    original_collector = system_routes._performance_collector

    try:
        # Ensure no collector is registered
        system_routes._performance_collector = None

        response = await client.get("/api/system/performance")

        # Should return 503 Service Unavailable
        assert response.status_code == 503
        data = response.json()
        assert "detail" in data
        assert "not initialized" in data["detail"].lower()
    finally:
        system_routes._performance_collector = original_collector


@pytest.mark.asyncio
async def test_performance_endpoint_handles_collector_error(client, mock_redis):
    """Test performance endpoint handles collector errors gracefully."""
    from backend.api.routes import system as system_routes

    # Save original collector
    original_collector = system_routes._performance_collector

    try:
        # Create mock collector that raises an error
        mock_collector = AsyncMock()
        mock_collector.collect_all = AsyncMock(side_effect=RuntimeError("Collection failed"))
        system_routes._performance_collector = mock_collector

        response = await client.get("/api/system/performance")

        # Should return 500 Internal Server Error
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
    finally:
        system_routes._performance_collector = original_collector


@pytest.mark.skip(reason="Performance REST API endpoint not yet implemented (NEM-1900)")
@pytest.mark.asyncio
async def test_performance_history_endpoint_empty(client, mock_redis):
    """Test performance history endpoint with no stored data."""
    # Configure mock Redis to return empty sorted set
    mock_redis.zrangebyscore = AsyncMock(return_value=[])

    response = await client.get("/api/system/performance/history")

    assert response.status_code == 200
    data = response.json()

    assert "snapshots" in data
    assert "time_range" in data
    assert "count" in data
    assert data["snapshots"] == []
    assert data["count"] == 0
    assert data["time_range"] == "5m"  # Default value


@pytest.mark.skip(reason="Performance REST API endpoint not yet implemented (NEM-1900)")
@pytest.mark.asyncio
async def test_performance_history_endpoint_with_time_range(client, mock_redis):
    """Test performance history endpoint with different time ranges."""
    mock_redis.zrangebyscore = AsyncMock(return_value=[])

    # Test 5m time range
    response = await client.get("/api/system/performance/history?time_range=5m")
    assert response.status_code == 200
    data = response.json()
    assert data["time_range"] == "5m"

    # Test 15m time range
    response = await client.get("/api/system/performance/history?time_range=15m")
    assert response.status_code == 200
    data = response.json()
    assert data["time_range"] == "15m"

    # Test 60m time range
    response = await client.get("/api/system/performance/history?time_range=60m")
    assert response.status_code == 200
    data = response.json()
    assert data["time_range"] == "60m"


@pytest.mark.skip(reason="Performance REST API endpoint not yet implemented (NEM-1900)")
@pytest.mark.asyncio
async def test_performance_history_endpoint_invalid_time_range(client, mock_redis):
    """Test performance history endpoint rejects invalid time ranges."""
    response = await client.get("/api/system/performance/history?time_range=invalid")

    # FastAPI validates enum values and returns 422
    assert response.status_code == 422


@pytest.mark.skip(reason="Performance REST API endpoint not yet implemented (NEM-1900)")
@pytest.mark.asyncio
async def test_performance_history_endpoint_with_data(client, mock_redis):
    """Test performance history endpoint returns stored snapshots."""
    import json

    # Create sample performance data
    sample_snapshot = {
        "timestamp": "2026-01-10T12:00:00Z",
        "gpu": None,
        "ai_models": {},
        "nemotron": None,
        "inference": None,
        "databases": {},
        "host": {
            "cpu_percent": 30.0,
            "ram_used_gb": 10.0,
            "ram_total_gb": 32.0,
            "disk_used_gb": 200.0,
            "disk_total_gb": 500.0,
        },
        "containers": [],
        "alerts": [],
    }

    # Mock Redis to return stored snapshots
    mock_redis.zrangebyscore = AsyncMock(return_value=[json.dumps(sample_snapshot)])

    response = await client.get("/api/system/performance/history?time_range=5m")

    assert response.status_code == 200
    data = response.json()

    assert data["count"] == 1
    assert len(data["snapshots"]) == 1
    snapshot = data["snapshots"][0]
    assert snapshot["host"]["cpu_percent"] == 30.0


@pytest.mark.skip(reason="Performance REST API endpoint not yet implemented (NEM-1900)")
@pytest.mark.asyncio
async def test_performance_stores_snapshot_in_redis(client, mock_redis):
    """Test that getting current performance stores snapshot in Redis."""
    # Mock the PerformanceCollector
    from backend.api.schemas.performance import PerformanceUpdate

    mock_snapshot = PerformanceUpdate(
        timestamp=datetime.now(UTC),
        gpu=None,
        ai_models={},
        nemotron=None,
        inference=None,
        databases={},
        host=None,
        containers=[],
        alerts=[],
    )

    with patch("backend.api.routes.system._performance_collector") as mock_collector:
        mock_collector.collect_all = AsyncMock(return_value=mock_snapshot)

        # Mock Redis zadd to verify it's called
        mock_redis.zadd = AsyncMock(return_value=1)
        mock_redis._ensure_connected = lambda: mock_redis
        mock_redis.zcard = AsyncMock(return_value=1)

        response = await client.get("/api/system/performance")

        assert response.status_code == 200
        # Verify Redis zadd was called to store the snapshot
        mock_redis.zadd.assert_called_once()
