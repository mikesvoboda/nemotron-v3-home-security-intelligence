"""Unit tests for backend.api.routes.system helpers.

These focus on low-level branches that are hard to hit via integration tests
but are important for correctness (and to satisfy the backend coverage gate).
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response
from starlette.testclient import TestClient

from backend.api.routes import system as system_routes
from backend.api.schemas.system import (
    CleanupResponse,
    ConfigResponse,
    GPUStatsHistoryResponse,
    GPUStatsResponse,
    HealthCheckServiceStatus,
    HealthResponse,
    PipelineLatencies,
    ReadinessResponse,
    StageLatency,
    SystemStatsResponse,
    TelemetryResponse,
    WorkerStatus,
)
from backend.core.redis import RedisClient


@pytest.fixture(autouse=True)
def clear_health_caches_fixture() -> None:
    """Clear health caches before each test to ensure test isolation.

    The health endpoints cache results for 5 seconds to reduce load.
    Without clearing, tests may see cached results from previous tests.
    """
    system_routes.clear_health_cache()


@pytest.fixture(autouse=True)
def mock_ai_health_settings():
    """Mock get_settings for AI health checks to prevent environment validation issues.

    Tests that call check_ai_services_health() will fail if the environment
    has ENVIRONMENT=production with weak passwords. This fixture mocks
    get_settings() to return valid settings without environment validation.
    """
    mock_settings = MagicMock()
    mock_settings.yolo26_url = "http://localhost:8001"
    mock_settings.nemotron_url = "http://localhost:8002"

    with patch.object(system_routes, "get_settings", return_value=mock_settings):
        yield mock_settings


@pytest.mark.asyncio
async def test_check_database_health_unhealthy_on_exception() -> None:
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock(side_effect=RuntimeError("db down"))

    status = await system_routes.check_database_health(db)  # type: ignore[arg-type]
    assert status.status == "unhealthy"
    assert "db down" in status.message


@pytest.mark.asyncio
async def test_check_redis_health_unhealthy_on_error_payload() -> None:
    redis = AsyncMock(spec=RedisClient)
    redis.health_check = AsyncMock(return_value={"status": "unhealthy", "error": "nope"})

    status = await system_routes.check_redis_health(redis)  # type: ignore[arg-type]
    assert status.status == "unhealthy"
    assert status.message == "nope"


@pytest.mark.asyncio
async def test_check_redis_health_unhealthy_when_redis_is_none() -> None:
    """Test that check_redis_health returns unhealthy status when redis is None.

    This handles the case where the Redis connection failed during dependency injection.
    """
    status = await system_routes.check_redis_health(None)
    assert status.status == "unhealthy"
    assert "unavailable" in status.message.lower()
    assert "connection failed" in status.message.lower()


def test_write_runtime_env_merges_existing_lines(tmp_path, monkeypatch) -> None:
    # Point runtime env path at a tmp file
    runtime_env = tmp_path / "runtime.env"
    monkeypatch.setenv("HSI_RUNTIME_ENV_PATH", str(runtime_env))

    runtime_env.write_text(
        "\n".join(
            [
                "# comment",
                "RETENTION_DAYS=30",
                "INVALID_LINE",
                "BATCH_WINDOW_SECONDS=90",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    system_routes._write_runtime_env(
        {"RETENTION_DAYS": "7", "DETECTION_CONFIDENCE_THRESHOLD": "0.75"}
    )

    content = runtime_env.read_text(encoding="utf-8").splitlines()
    # Should be sorted keys and include merged values
    assert content == [
        "BATCH_WINDOW_SECONDS=90",
        "DETECTION_CONFIDENCE_THRESHOLD=0.75",
        "RETENTION_DAYS=7",
    ]


def test_runtime_env_path_default_is_under_data() -> None:
    # Just sanity-check the default (do not touch filesystem)
    p = system_routes._runtime_env_path()
    assert isinstance(p, Path)


# =============================================================================
# Liveness Endpoint Tests
# =============================================================================
# NOTE: The liveness endpoint (/api/system/health/live) was removed to consolidate
# duplicate endpoints. Liveness probes should use GET /health at the root level.
# See main.py::health() for the canonical liveness probe implementation.


# =============================================================================
# Readiness Endpoint Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_readiness_all_healthy() -> None:
    """Test readiness endpoint when all services are healthy."""
    original_pipeline_manager = system_routes._pipeline_manager
    mock_response = Response()

    try:
        # Mock pipeline manager with running workers (required for ready status)
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {
            "running": True,
            "workers": {
                "detection": {"state": "running"},
                "analysis": {"state": "running"},
            },
        }
        system_routes._pipeline_manager = mock_manager

        db = AsyncMock()
        # Mock successful database query
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 5
        db.execute = AsyncMock(return_value=mock_result)

        redis = AsyncMock()
        redis.health_check = AsyncMock(return_value={"status": "healthy", "redis_version": "7.0.0"})

        response = await system_routes.get_readiness(mock_response, db, redis)  # type: ignore[arg-type]

        assert isinstance(response, ReadinessResponse)
        assert response.ready is True
        assert response.status == "ready"
        assert response.services["database"].status == "healthy"
        assert response.services["redis"].status == "healthy"
        assert response.timestamp is not None
        assert mock_response.status_code == 200
    finally:
        system_routes._pipeline_manager = original_pipeline_manager


@pytest.mark.asyncio
async def test_get_readiness_database_unhealthy() -> None:
    """Test readiness endpoint when database is unhealthy."""
    mock_response = Response()

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=RuntimeError("db connection failed"))

    redis = AsyncMock()
    redis.health_check = AsyncMock(return_value={"status": "healthy", "redis_version": "7.0.0"})

    response = await system_routes.get_readiness(mock_response, db, redis)  # type: ignore[arg-type]

    assert isinstance(response, ReadinessResponse)
    assert response.ready is False
    assert response.status == "not_ready"
    assert response.services["database"].status == "unhealthy"
    assert "db connection failed" in response.services["database"].message
    assert mock_response.status_code == 503


@pytest.mark.asyncio
async def test_get_readiness_redis_unhealthy() -> None:
    """Test readiness endpoint when Redis is unhealthy."""
    mock_response = Response()

    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 5
    db.execute = AsyncMock(return_value=mock_result)

    redis = AsyncMock()
    redis.health_check = AsyncMock(
        return_value={"status": "unhealthy", "error": "connection refused"}
    )

    response = await system_routes.get_readiness(mock_response, db, redis)  # type: ignore[arg-type]

    assert isinstance(response, ReadinessResponse)
    assert response.ready is False
    assert response.status == "degraded"
    assert response.services["database"].status == "healthy"
    assert response.services["redis"].status == "unhealthy"
    assert mock_response.status_code == 503


@pytest.mark.asyncio
async def test_get_readiness_redis_exception() -> None:
    """Test readiness endpoint when Redis health check raises exception."""
    mock_response = Response()

    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 5
    db.execute = AsyncMock(return_value=mock_result)

    redis = AsyncMock()
    redis.health_check = AsyncMock(side_effect=ConnectionError("redis down"))

    response = await system_routes.get_readiness(mock_response, db, redis)  # type: ignore[arg-type]

    assert isinstance(response, ReadinessResponse)
    assert response.ready is False
    assert response.services["redis"].status == "unhealthy"
    assert mock_response.status_code == 503


@pytest.mark.asyncio
async def test_get_readiness_redis_none() -> None:
    """Test readiness endpoint when Redis client is None (connection failed during DI).

    This tests the scenario where Redis connection fails during dependency injection
    and the endpoint receives None instead of a connected RedisClient.
    """
    mock_response = Response()

    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 5
    db.execute = AsyncMock(return_value=mock_result)

    # Pass None as redis to simulate connection failure during DI
    response = await system_routes.get_readiness(mock_response, db, None)

    assert isinstance(response, ReadinessResponse)
    assert response.ready is False
    assert response.status == "degraded"
    assert response.services["database"].status == "healthy"
    assert response.services["redis"].status == "unhealthy"
    assert "unavailable" in response.services["redis"].message.lower()
    assert mock_response.status_code == 503


@pytest.mark.asyncio
async def test_get_readiness_both_unhealthy() -> None:
    """Test readiness endpoint when both database and Redis are unhealthy."""
    mock_response = Response()

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=RuntimeError("db error"))

    redis = AsyncMock()
    redis.health_check = AsyncMock(return_value={"status": "unhealthy", "error": "redis error"})

    response = await system_routes.get_readiness(mock_response, db, redis)  # type: ignore[arg-type]

    assert isinstance(response, ReadinessResponse)
    assert response.ready is False
    assert response.status == "not_ready"
    assert response.services["database"].status == "unhealthy"
    assert response.services["redis"].status == "unhealthy"
    assert mock_response.status_code == 503


# =============================================================================
# Worker Registration Tests
# =============================================================================


def test_register_workers_sets_global_references() -> None:
    """Test that register_workers correctly sets global worker references."""
    # Save original values
    original_gpu = system_routes._gpu_monitor
    original_cleanup = system_routes._cleanup_service
    original_broadcaster = system_routes._system_broadcaster
    original_watcher = system_routes._file_watcher

    try:
        # Create mock workers
        mock_gpu = MagicMock()
        mock_cleanup = MagicMock()
        mock_broadcaster = MagicMock()
        mock_watcher = MagicMock()

        # Register workers
        system_routes.register_workers(
            gpu_monitor=mock_gpu,
            cleanup_service=mock_cleanup,
            system_broadcaster=mock_broadcaster,
            file_watcher=mock_watcher,
        )

        # Verify globals are set
        assert system_routes._gpu_monitor is mock_gpu
        assert system_routes._cleanup_service is mock_cleanup
        assert system_routes._system_broadcaster is mock_broadcaster
        assert system_routes._file_watcher is mock_watcher
    finally:
        # Restore original values
        system_routes._gpu_monitor = original_gpu
        system_routes._cleanup_service = original_cleanup
        system_routes._system_broadcaster = original_broadcaster
        system_routes._file_watcher = original_watcher


def test_get_worker_statuses_no_workers_registered() -> None:
    """Test _get_worker_statuses when no workers are registered."""
    # Save original values
    original_gpu = system_routes._gpu_monitor
    original_cleanup = system_routes._cleanup_service
    original_broadcaster = system_routes._system_broadcaster
    original_watcher = system_routes._file_watcher
    original_pipeline = system_routes._pipeline_manager

    try:
        # Clear all workers
        system_routes._gpu_monitor = None
        system_routes._cleanup_service = None
        system_routes._system_broadcaster = None
        system_routes._file_watcher = None
        system_routes._pipeline_manager = None

        statuses = system_routes._get_worker_statuses()

        assert isinstance(statuses, list)
        assert len(statuses) == 0
    finally:
        # Restore original values
        system_routes._gpu_monitor = original_gpu
        system_routes._cleanup_service = original_cleanup
        system_routes._system_broadcaster = original_broadcaster
        system_routes._file_watcher = original_watcher
        system_routes._pipeline_manager = original_pipeline


def test_get_worker_statuses_with_running_workers() -> None:
    """Test _get_worker_statuses with running workers."""
    # Save original values
    original_gpu = system_routes._gpu_monitor
    original_cleanup = system_routes._cleanup_service
    original_broadcaster = system_routes._system_broadcaster
    original_watcher = system_routes._file_watcher
    original_pipeline = system_routes._pipeline_manager

    try:
        # Create running mock workers
        mock_gpu = MagicMock()
        mock_gpu.running = True

        mock_cleanup = MagicMock()
        mock_cleanup.running = True

        mock_broadcaster = MagicMock()
        mock_broadcaster._running = True

        mock_watcher = MagicMock()
        mock_watcher.running = True

        system_routes._gpu_monitor = mock_gpu
        system_routes._cleanup_service = mock_cleanup
        system_routes._system_broadcaster = mock_broadcaster
        system_routes._file_watcher = mock_watcher
        system_routes._pipeline_manager = None  # Exclude pipeline workers from count

        statuses = system_routes._get_worker_statuses()

        assert len(statuses) == 4
        for status in statuses:
            assert isinstance(status, WorkerStatus)
            assert status.running is True
            assert status.message is None
    finally:
        # Restore original values
        system_routes._gpu_monitor = original_gpu
        system_routes._cleanup_service = original_cleanup
        system_routes._system_broadcaster = original_broadcaster
        system_routes._file_watcher = original_watcher
        system_routes._pipeline_manager = original_pipeline


def test_get_worker_statuses_with_stopped_workers() -> None:
    """Test _get_worker_statuses with stopped workers."""
    # Save original values
    original_gpu = system_routes._gpu_monitor
    original_cleanup = system_routes._cleanup_service
    original_broadcaster = system_routes._system_broadcaster
    original_watcher = system_routes._file_watcher
    original_pipeline = system_routes._pipeline_manager

    try:
        # Create stopped mock workers
        mock_gpu = MagicMock()
        mock_gpu.running = False

        mock_cleanup = MagicMock()
        mock_cleanup.running = False

        system_routes._gpu_monitor = mock_gpu
        system_routes._cleanup_service = mock_cleanup
        system_routes._system_broadcaster = None
        system_routes._file_watcher = None
        system_routes._pipeline_manager = None  # Exclude pipeline workers from count

        statuses = system_routes._get_worker_statuses()

        assert len(statuses) == 2
        for status in statuses:
            assert status.running is False
            assert status.message == "Not running"
    finally:
        # Restore original values
        system_routes._gpu_monitor = original_gpu
        system_routes._cleanup_service = original_cleanup
        system_routes._system_broadcaster = original_broadcaster
        system_routes._file_watcher = original_watcher
        system_routes._pipeline_manager = original_pipeline


def test_get_worker_statuses_mixed_status() -> None:
    """Test _get_worker_statuses with mixed running/stopped workers."""
    # Save original values
    original_gpu = system_routes._gpu_monitor
    original_cleanup = system_routes._cleanup_service
    original_broadcaster = system_routes._system_broadcaster
    original_watcher = system_routes._file_watcher
    original_pipeline = system_routes._pipeline_manager

    try:
        mock_gpu = MagicMock()
        mock_gpu.running = True

        mock_cleanup = MagicMock()
        mock_cleanup.running = False

        system_routes._gpu_monitor = mock_gpu
        system_routes._cleanup_service = mock_cleanup
        system_routes._system_broadcaster = None
        system_routes._file_watcher = None
        system_routes._pipeline_manager = None  # Exclude pipeline workers from count

        statuses = system_routes._get_worker_statuses()

        assert len(statuses) == 2
        gpu_status = next(s for s in statuses if s.name == "gpu_monitor")
        cleanup_status = next(s for s in statuses if s.name == "cleanup_service")

        assert gpu_status.running is True
        assert gpu_status.message is None

        assert cleanup_status.running is False
        assert cleanup_status.message == "Not running"
    finally:
        # Restore original values
        system_routes._gpu_monitor = original_gpu
        system_routes._cleanup_service = original_cleanup
        system_routes._system_broadcaster = original_broadcaster
        system_routes._file_watcher = original_watcher
        system_routes._pipeline_manager = original_pipeline


# =============================================================================
# Pipeline Worker Readiness Tests
# =============================================================================


def test_get_worker_statuses_includes_pipeline_workers() -> None:
    """Test _get_worker_statuses includes pipeline worker status when registered."""
    original_pipeline_manager = system_routes._pipeline_manager
    original_gpu = system_routes._gpu_monitor

    try:
        # Clear other workers
        system_routes._gpu_monitor = None
        system_routes._cleanup_service = None
        system_routes._system_broadcaster = None
        system_routes._file_watcher = None

        # Mock pipeline manager with running workers
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {
            "running": True,
            "workers": {
                "detection": {"state": "running", "items_processed": 100, "errors": 0},
                "analysis": {"state": "running", "items_processed": 50, "errors": 1},
                "timeout": {"state": "running", "items_processed": 10, "errors": 0},
                "metrics": {"running": True},
            },
        }
        system_routes._pipeline_manager = mock_manager

        statuses = system_routes._get_worker_statuses()

        # Should have 5 workers from pipeline manager
        # (detection, analysis, batch_timeout_worker, batch_aggregator, metrics)
        # Note: timeout worker creates both batch_timeout_worker and batch_aggregator for frontend compat
        assert len(statuses) == 5

        detection_status = next(s for s in statuses if s.name == "detection_worker")
        assert detection_status.running is True
        assert detection_status.message is None

        analysis_status = next(s for s in statuses if s.name == "analysis_worker")
        assert analysis_status.running is True
        assert analysis_status.message is None

        timeout_status = next(s for s in statuses if s.name == "batch_timeout_worker")
        assert timeout_status.running is True
        assert timeout_status.message is None

        # batch_aggregator is also added for frontend compatibility
        aggregator_status = next(s for s in statuses if s.name == "batch_aggregator")
        assert aggregator_status.running is True
        assert aggregator_status.message is None

        metrics_status = next(s for s in statuses if s.name == "metrics_worker")
        assert metrics_status.running is True
        assert metrics_status.message is None

    finally:
        system_routes._pipeline_manager = original_pipeline_manager
        system_routes._gpu_monitor = original_gpu


def test_get_worker_statuses_pipeline_workers_stopped() -> None:
    """Test _get_worker_statuses shows stopped pipeline workers."""
    original_pipeline_manager = system_routes._pipeline_manager
    original_gpu = system_routes._gpu_monitor

    try:
        # Clear other workers
        system_routes._gpu_monitor = None
        system_routes._cleanup_service = None
        system_routes._system_broadcaster = None
        system_routes._file_watcher = None

        # Mock pipeline manager with stopped workers
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {
            "running": False,
            "workers": {
                "detection": {"state": "stopped", "items_processed": 100, "errors": 0},
                "analysis": {"state": "error", "items_processed": 50, "errors": 5},
                "timeout": {"state": "stopped", "items_processed": 10, "errors": 0},
                "metrics": {"running": False},
            },
        }
        system_routes._pipeline_manager = mock_manager

        statuses = system_routes._get_worker_statuses()

        detection_status = next(s for s in statuses if s.name == "detection_worker")
        assert detection_status.running is False
        assert "stopped" in detection_status.message.lower()

        analysis_status = next(s for s in statuses if s.name == "analysis_worker")
        assert analysis_status.running is False
        assert "error" in analysis_status.message.lower()

    finally:
        system_routes._pipeline_manager = original_pipeline_manager
        system_routes._gpu_monitor = original_gpu


def test_are_critical_pipeline_workers_healthy_all_running() -> None:
    """Test _are_critical_pipeline_workers_healthy returns True when workers are running."""
    original_pipeline_manager = system_routes._pipeline_manager

    try:
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {
            "running": True,
            "workers": {
                "detection": {"state": "running"},
                "analysis": {"state": "running"},
            },
        }
        system_routes._pipeline_manager = mock_manager

        assert system_routes._are_critical_pipeline_workers_healthy() is True

    finally:
        system_routes._pipeline_manager = original_pipeline_manager


def test_are_critical_pipeline_workers_healthy_detection_stopped() -> None:
    """Test _are_critical_pipeline_workers_healthy returns False when detection worker stopped."""
    original_pipeline_manager = system_routes._pipeline_manager

    try:
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {
            "running": True,
            "workers": {
                "detection": {"state": "stopped"},
                "analysis": {"state": "running"},
            },
        }
        system_routes._pipeline_manager = mock_manager

        assert system_routes._are_critical_pipeline_workers_healthy() is False

    finally:
        system_routes._pipeline_manager = original_pipeline_manager


def test_are_critical_pipeline_workers_healthy_analysis_stopped() -> None:
    """Test _are_critical_pipeline_workers_healthy returns False when analysis worker stopped."""
    original_pipeline_manager = system_routes._pipeline_manager

    try:
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {
            "running": True,
            "workers": {
                "detection": {"state": "running"},
                "analysis": {"state": "stopped"},
            },
        }
        system_routes._pipeline_manager = mock_manager

        assert system_routes._are_critical_pipeline_workers_healthy() is False

    finally:
        system_routes._pipeline_manager = original_pipeline_manager


def test_are_critical_pipeline_workers_healthy_manager_not_running() -> None:
    """Test _are_critical_pipeline_workers_healthy returns False when manager not running."""
    original_pipeline_manager = system_routes._pipeline_manager

    try:
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {
            "running": False,
            "workers": {
                "detection": {"state": "running"},
                "analysis": {"state": "running"},
            },
        }
        system_routes._pipeline_manager = mock_manager

        assert system_routes._are_critical_pipeline_workers_healthy() is False

    finally:
        system_routes._pipeline_manager = original_pipeline_manager


def test_are_critical_pipeline_workers_healthy_no_manager() -> None:
    """Test _are_critical_pipeline_workers_healthy returns False when no manager registered.

    If the pipeline manager failed to initialize, the system cannot process detections,
    so it should report as not healthy. This prevents the container from accepting
    traffic when it can't actually process images.
    """
    original_pipeline_manager = system_routes._pipeline_manager

    try:
        system_routes._pipeline_manager = None

        # Should return False - system cannot process detections without pipeline manager
        assert system_routes._are_critical_pipeline_workers_healthy() is False

    finally:
        system_routes._pipeline_manager = original_pipeline_manager


@pytest.mark.asyncio
async def test_get_readiness_not_ready_when_pipeline_workers_down() -> None:
    """Test readiness returns not_ready when critical pipeline workers are stopped."""
    original_pipeline_manager = system_routes._pipeline_manager
    mock_response = Response()

    try:
        # Mock pipeline manager with stopped workers
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {
            "running": True,
            "workers": {
                "detection": {"state": "stopped"},
                "analysis": {"state": "stopped"},
            },
        }
        system_routes._pipeline_manager = mock_manager

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 5
        db.execute = AsyncMock(return_value=mock_result)

        redis = AsyncMock()
        redis.health_check = AsyncMock(return_value={"status": "healthy", "redis_version": "7.0.0"})

        # Mock AI services health check to avoid calling get_settings() which requires env vars
        async def mock_ai_health_check():
            return HealthCheckServiceStatus(
                status="healthy", message="AI services operational", details=None
            )

        with patch.object(system_routes, "check_ai_services_health", mock_ai_health_check):
            response = await system_routes.get_readiness(mock_response, db, redis)  # type: ignore[arg-type]

        assert isinstance(response, ReadinessResponse)
        # Database and Redis are healthy but pipeline workers are down
        assert response.ready is False
        assert response.status == "not_ready"
        assert response.services["database"].status == "healthy"
        assert response.services["redis"].status == "healthy"
        assert mock_response.status_code == 503

    finally:
        system_routes._pipeline_manager = original_pipeline_manager


@pytest.mark.asyncio
async def test_get_readiness_ready_when_pipeline_workers_running() -> None:
    """Test readiness returns ready when critical pipeline workers are running."""
    original_pipeline_manager = system_routes._pipeline_manager
    mock_response = Response()

    try:
        # Mock pipeline manager with running workers
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {
            "running": True,
            "workers": {
                "detection": {"state": "running"},
                "analysis": {"state": "running"},
            },
        }
        system_routes._pipeline_manager = mock_manager

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 5
        db.execute = AsyncMock(return_value=mock_result)

        redis = AsyncMock()
        redis.health_check = AsyncMock(return_value={"status": "healthy", "redis_version": "7.0.0"})

        # Mock AI services health check to avoid calling get_settings() which requires env vars
        async def mock_ai_health_check():
            return HealthCheckServiceStatus(
                status="healthy", message="AI services operational", details=None
            )

        with patch.object(system_routes, "check_ai_services_health", mock_ai_health_check):
            response = await system_routes.get_readiness(mock_response, db, redis)  # type: ignore[arg-type]

        assert isinstance(response, ReadinessResponse)
        assert response.ready is True
        assert response.status == "ready"
        assert mock_response.status_code == 200

    finally:
        system_routes._pipeline_manager = original_pipeline_manager


@pytest.mark.asyncio
async def test_get_readiness_includes_pipeline_worker_status() -> None:
    """Test readiness response includes pipeline worker status in workers list."""
    original_pipeline_manager = system_routes._pipeline_manager
    original_gpu = system_routes._gpu_monitor

    try:
        # Clear other workers
        system_routes._gpu_monitor = None
        system_routes._cleanup_service = None
        system_routes._system_broadcaster = None
        system_routes._file_watcher = None

        # Mock pipeline manager with running workers
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {
            "running": True,
            "workers": {
                "detection": {"state": "running", "items_processed": 100},
                "analysis": {"state": "running", "items_processed": 50},
            },
        }
        system_routes._pipeline_manager = mock_manager

        mock_response = Response()

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 5
        db.execute = AsyncMock(return_value=mock_result)

        redis = AsyncMock()
        redis.health_check = AsyncMock(return_value={"status": "healthy", "redis_version": "7.0.0"})

        # Mock AI services health check to avoid calling get_settings() which requires env vars
        async def mock_ai_health_check():
            return HealthCheckServiceStatus(
                status="healthy", message="AI services operational", details=None
            )

        with patch.object(system_routes, "check_ai_services_health", mock_ai_health_check):
            response = await system_routes.get_readiness(mock_response, db, redis)  # type: ignore[arg-type]

        # Should include detection_worker and analysis_worker in workers list
        detection_worker = next((w for w in response.workers if w.name == "detection_worker"), None)
        analysis_worker = next((w for w in response.workers if w.name == "analysis_worker"), None)

        assert detection_worker is not None
        assert detection_worker.running is True

        assert analysis_worker is not None
        assert analysis_worker.running is True

    finally:
        system_routes._pipeline_manager = original_pipeline_manager
        system_routes._gpu_monitor = original_gpu


@pytest.mark.asyncio
async def test_get_readiness_includes_worker_status() -> None:
    """Test that readiness response includes worker status information."""
    # Save original values
    original_gpu = system_routes._gpu_monitor
    mock_response = Response()

    try:
        mock_gpu = MagicMock()
        mock_gpu.running = True
        system_routes._gpu_monitor = mock_gpu

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 5
        db.execute = AsyncMock(return_value=mock_result)

        redis = AsyncMock()
        redis.health_check = AsyncMock(return_value={"status": "healthy", "redis_version": "7.0.0"})

        response = await system_routes.get_readiness(mock_response, db, redis)  # type: ignore[arg-type]

        assert len(response.workers) >= 1
        gpu_worker = next((w for w in response.workers if w.name == "gpu_monitor"), None)
        assert gpu_worker is not None
        assert gpu_worker.running is True
    finally:
        system_routes._gpu_monitor = original_gpu


@pytest.mark.asyncio
async def test_get_readiness_not_ready_when_pipeline_manager_is_none() -> None:
    """Test readiness returns not_ready when pipeline_manager is None.

    If the pipeline manager failed to initialize (e.g., due to startup error),
    the system cannot process detections and should not accept traffic.
    This is a P0 critical fix to prevent containers from accepting traffic
    when they cannot actually process images.
    """
    original_pipeline_manager = system_routes._pipeline_manager
    original_gpu = system_routes._gpu_monitor
    mock_response = Response()

    try:
        # Set pipeline manager to None (simulating failed initialization)
        system_routes._pipeline_manager = None
        system_routes._gpu_monitor = None
        system_routes._cleanup_service = None
        system_routes._system_broadcaster = None
        system_routes._file_watcher = None

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 5
        db.execute = AsyncMock(return_value=mock_result)

        redis = AsyncMock()
        redis.health_check = AsyncMock(return_value={"status": "healthy", "redis_version": "7.0.0"})

        # Mock AI services health check to avoid calling get_settings() which requires env vars
        async def mock_ai_health_check():
            return HealthCheckServiceStatus(
                status="healthy", message="AI services operational", details=None
            )

        with patch.object(system_routes, "check_ai_services_health", mock_ai_health_check):
            response = await system_routes.get_readiness(mock_response, db, redis)  # type: ignore[arg-type]

        assert isinstance(response, ReadinessResponse)
        # Even though database and Redis are healthy, system should NOT be ready
        # because pipeline manager is None (can't process images)
        assert response.ready is False
        assert response.status == "not_ready"
        assert response.services["database"].status == "healthy"
        assert response.services["redis"].status == "healthy"
        assert mock_response.status_code == 503

    finally:
        system_routes._pipeline_manager = original_pipeline_manager
        system_routes._gpu_monitor = original_gpu


# =============================================================================
# Health Check Timeout Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_readiness_database_timeout() -> None:
    """Test readiness endpoint when database health check times out."""
    mock_response = Response()

    async def slow_db_execute(*args, **kwargs):
        """Simulate a slow database query that will timeout."""
        await asyncio.sleep(0.5)  # Longer than 0.1s timeout, but not excessive

    db = AsyncMock()
    db.execute = slow_db_execute

    redis = AsyncMock()
    redis.health_check = AsyncMock(return_value={"status": "healthy", "redis_version": "7.0.0"})

    # Use a short timeout for testing
    with patch.object(system_routes, "HEALTH_CHECK_TIMEOUT_SECONDS", 0.1):
        response = await system_routes.get_readiness(mock_response, db, redis)  # type: ignore[arg-type]

    assert isinstance(response, ReadinessResponse)
    assert response.ready is False
    assert response.status == "not_ready"
    assert response.services["database"].status == "unhealthy"
    assert "timed out" in response.services["database"].message
    assert mock_response.status_code == 503


@pytest.mark.asyncio
async def test_get_readiness_redis_timeout() -> None:
    """Test readiness endpoint when Redis health check times out."""
    mock_response = Response()

    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 5
    db.execute = AsyncMock(return_value=mock_result)

    async def slow_redis_health_check():
        """Simulate a slow Redis health check that will timeout."""
        await asyncio.sleep(0.5)  # Longer than 0.1s timeout, but not excessive

    redis = AsyncMock()
    redis.health_check = slow_redis_health_check

    # Use a short timeout for testing
    with patch.object(system_routes, "HEALTH_CHECK_TIMEOUT_SECONDS", 0.1):
        response = await system_routes.get_readiness(mock_response, db, redis)  # type: ignore[arg-type]

    assert isinstance(response, ReadinessResponse)
    assert response.ready is False
    assert response.status == "degraded"
    assert response.services["database"].status == "healthy"
    assert response.services["redis"].status == "unhealthy"
    assert "timed out" in response.services["redis"].message
    assert mock_response.status_code == 503


@pytest.mark.asyncio
async def test_get_readiness_ai_services_timeout() -> None:
    """Test readiness endpoint when AI services health check times out."""
    original_pipeline_manager = system_routes._pipeline_manager
    mock_response = Response()

    try:
        # Mock pipeline manager with running workers (required for ready status)
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = {
            "running": True,
            "workers": {
                "detection": {"state": "running"},
                "analysis": {"state": "running"},
            },
        }
        system_routes._pipeline_manager = mock_manager

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 5
        db.execute = AsyncMock(return_value=mock_result)

        redis = AsyncMock()
        redis.health_check = AsyncMock(return_value={"status": "healthy", "redis_version": "7.0.0"})

        async def slow_ai_health_check():
            """Simulate a slow AI services health check that will timeout."""
            await asyncio.sleep(0.5)  # Longer than 0.1s timeout, but not excessive
            # This return is never reached due to timeout
            return HealthCheckServiceStatus(
                status="healthy", message="AI services operational", details=None
            )

        # Use a short timeout for testing
        with (
            patch.object(system_routes, "HEALTH_CHECK_TIMEOUT_SECONDS", 0.1),
            patch.object(system_routes, "check_ai_services_health", slow_ai_health_check),
        ):
            response = await system_routes.get_readiness(mock_response, db, redis)  # type: ignore[arg-type]

        assert isinstance(response, ReadinessResponse)
        # Database and Redis are healthy, so system should be ready
        # but AI services timeout should be reflected
        assert response.ready is True
        assert response.status == "ready"
        assert response.services["database"].status == "healthy"
        assert response.services["redis"].status == "healthy"
        assert response.services["ai"].status == "unhealthy"
        assert "timed out" in response.services["ai"].message
        assert mock_response.status_code == 200
    finally:
        system_routes._pipeline_manager = original_pipeline_manager


@pytest.mark.asyncio
async def test_get_readiness_all_services_timeout() -> None:
    """Test readiness endpoint when all health checks timeout."""
    mock_response = Response()

    async def slow_db_execute(*args, **kwargs):
        """Simulate a slow database query that will timeout."""
        await asyncio.sleep(0.5)  # Longer than 0.1s timeout, but not excessive

    async def slow_redis_health_check():
        """Simulate a slow Redis health check that will timeout."""
        await asyncio.sleep(0.5)  # Longer than 0.1s timeout, but not excessive

    async def slow_ai_health_check():
        """Simulate a slow AI services health check that will timeout."""
        await asyncio.sleep(0.5)  # Longer than 0.1s timeout, but not excessive

    db = AsyncMock()
    db.execute = slow_db_execute

    redis = AsyncMock()
    redis.health_check = slow_redis_health_check

    with (
        patch.object(system_routes, "HEALTH_CHECK_TIMEOUT_SECONDS", 0.1),
        patch.object(system_routes, "check_ai_services_health", slow_ai_health_check),
    ):
        response = await system_routes.get_readiness(mock_response, db, redis)  # type: ignore[arg-type]

    assert isinstance(response, ReadinessResponse)
    assert response.ready is False
    assert response.status == "not_ready"
    assert response.services["database"].status == "unhealthy"
    assert response.services["redis"].status == "unhealthy"
    assert response.services["ai"].status == "unhealthy"
    assert "timed out" in response.services["database"].message
    assert "timed out" in response.services["redis"].message
    assert "timed out" in response.services["ai"].message
    assert mock_response.status_code == 503


@pytest.mark.asyncio
async def test_health_check_timeout_constant_is_reasonable() -> None:
    """Test that the health check timeout constant has a reasonable value."""
    # The timeout should be at least 1 second to allow for slow responses
    assert system_routes.HEALTH_CHECK_TIMEOUT_SECONDS >= 1.0
    # The timeout should not be more than 30 seconds
    assert system_routes.HEALTH_CHECK_TIMEOUT_SECONDS <= 30.0


# =============================================================================
# GPU Stats Tests (Lines 148-155, 415-427)
# =============================================================================


@pytest.mark.asyncio
async def test_get_latest_gpu_stats_returns_data() -> None:
    """Test get_latest_gpu_stats returns stats from database."""
    db = AsyncMock()
    mock_gpu_stat = MagicMock()
    mock_gpu_stat.recorded_at = datetime(2025, 12, 27, 10, 0, 0)
    mock_gpu_stat.gpu_utilization = 75.5
    mock_gpu_stat.memory_used = 12000
    mock_gpu_stat.memory_total = 24000
    mock_gpu_stat.temperature = 65.0
    mock_gpu_stat.inference_fps = 30.5

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_gpu_stat
    db.execute = AsyncMock(return_value=mock_result)

    stats = await system_routes.get_latest_gpu_stats(db)  # type: ignore[arg-type]

    assert stats is not None
    assert stats["utilization"] == 75.5
    assert stats["memory_used"] == 12000
    assert stats["memory_total"] == 24000
    assert stats["temperature"] == 65.0
    assert stats["inference_fps"] == 30.5
    assert stats["recorded_at"] == datetime(2025, 12, 27, 10, 0, 0)


@pytest.mark.asyncio
async def test_get_latest_gpu_stats_returns_none_when_no_data() -> None:
    """Test get_latest_gpu_stats returns None when no GPU stats exist."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)

    stats = await system_routes.get_latest_gpu_stats(db)  # type: ignore[arg-type]

    assert stats is None


@pytest.mark.asyncio
async def test_get_gpu_stats_with_data() -> None:
    """Test get_gpu_stats returns GPU stats when data available."""
    db = AsyncMock()
    mock_gpu_stat = MagicMock()
    mock_gpu_stat.recorded_at = datetime(2025, 12, 27, 10, 0, 0)
    mock_gpu_stat.gpu_name = "NVIDIA RTX A5500"
    mock_gpu_stat.gpu_utilization = 75.5
    mock_gpu_stat.memory_used = 12000
    mock_gpu_stat.memory_total = 24000
    mock_gpu_stat.temperature = 65.0
    mock_gpu_stat.power_usage = 150.0
    mock_gpu_stat.inference_fps = 30.5

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_gpu_stat
    db.execute = AsyncMock(return_value=mock_result)

    response = await system_routes.get_gpu_stats(db)  # type: ignore[arg-type]

    assert isinstance(response, GPUStatsResponse)
    assert response.gpu_name == "NVIDIA RTX A5500"
    assert response.utilization == 75.5
    assert response.memory_used == 12000
    assert response.memory_total == 24000
    assert response.temperature == 65.0
    assert response.power_usage == 150.0
    assert response.inference_fps == 30.5


@pytest.mark.asyncio
async def test_get_gpu_stats_no_data_returns_nulls() -> None:
    """Test get_gpu_stats returns null values when no GPU data available."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mock_result)

    response = await system_routes.get_gpu_stats(db)  # type: ignore[arg-type]

    assert isinstance(response, GPUStatsResponse)
    assert response.utilization is None
    assert response.memory_used is None
    assert response.memory_total is None
    assert response.temperature is None
    assert response.inference_fps is None


# =============================================================================
# GPU Stats History Tests (Lines 449-474)
# =============================================================================


@pytest.mark.asyncio
async def test_get_gpu_stats_history_returns_samples() -> None:
    """Test get_gpu_stats_history returns time-series samples."""
    db = AsyncMock()

    # Create mock GPU stat rows
    mock_stat1 = MagicMock()
    mock_stat1.recorded_at = datetime(2025, 12, 27, 9, 0, 0)
    mock_stat1.gpu_name = "NVIDIA RTX A5500"
    mock_stat1.gpu_utilization = 50.0
    mock_stat1.memory_used = 8000
    mock_stat1.memory_total = 24000
    mock_stat1.temperature = 55.0
    mock_stat1.power_usage = 120.0
    mock_stat1.inference_fps = 25.0

    mock_stat2 = MagicMock()
    mock_stat2.recorded_at = datetime(2025, 12, 27, 10, 0, 0)
    mock_stat2.gpu_name = "NVIDIA RTX A5500"
    mock_stat2.gpu_utilization = 75.0
    mock_stat2.memory_used = 12000
    mock_stat2.memory_total = 24000
    mock_stat2.temperature = 65.0
    mock_stat2.power_usage = 150.0
    mock_stat2.inference_fps = 30.0

    # Mock for count query
    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 2

    # Mock for data query
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    # Return in descending order (newest first) - will be reversed
    mock_scalars.all.return_value = [mock_stat2, mock_stat1]
    mock_result.scalars.return_value = mock_scalars

    # Execute returns count result first, then data result
    db.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

    response = await system_routes.get_gpu_stats_history(db=db)  # type: ignore[arg-type]

    assert isinstance(response, GPUStatsHistoryResponse)
    assert response.pagination.total == 2
    assert response.pagination.limit == 300  # Default limit
    assert len(response.items) == 2
    # Should be in chronological order after reversal
    assert response.items[0].recorded_at == datetime(2025, 12, 27, 9, 0, 0)
    assert response.items[1].recorded_at == datetime(2025, 12, 27, 10, 0, 0)


@pytest.mark.asyncio
async def test_get_gpu_stats_history_with_since_filter() -> None:
    """Test get_gpu_stats_history filters by since parameter."""
    db = AsyncMock()

    mock_stat = MagicMock()
    mock_stat.recorded_at = datetime(2025, 12, 27, 10, 0, 0)
    mock_stat.gpu_name = "NVIDIA RTX A5500"
    mock_stat.gpu_utilization = 75.0
    mock_stat.memory_used = 12000
    mock_stat.memory_total = 24000
    mock_stat.temperature = 65.0
    mock_stat.power_usage = 150.0
    mock_stat.inference_fps = 30.0

    # Mock for count query
    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 1

    # Mock for data query
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_stat]
    mock_result.scalars.return_value = mock_scalars

    db.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

    since_time = datetime(2025, 12, 27, 9, 0, 0)
    response = await system_routes.get_gpu_stats_history(since=since_time, db=db)  # type: ignore[arg-type]

    assert isinstance(response, GPUStatsHistoryResponse)
    assert response.pagination.total == 1


@pytest.mark.asyncio
async def test_get_gpu_stats_history_limit_clamping() -> None:
    """Test get_gpu_stats_history clamps limit to valid range."""
    db = AsyncMock()

    def create_mock_db() -> AsyncMock:
        """Create a fresh mock db for each test."""
        mock_db = AsyncMock()
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 0
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute = AsyncMock(side_effect=[mock_count_result, mock_result])
        return mock_db

    # Test that limit of 0 is clamped to 1
    response = await system_routes.get_gpu_stats_history(limit=0, db=create_mock_db())  # type: ignore[arg-type]
    assert response.pagination.limit == 1

    # Test that negative limit is clamped to 1
    response = await system_routes.get_gpu_stats_history(limit=-5, db=create_mock_db())  # type: ignore[arg-type]
    assert response.pagination.limit == 1

    # Test that limit over 5000 is clamped to 5000
    response = await system_routes.get_gpu_stats_history(limit=10000, db=create_mock_db())  # type: ignore[arg-type]
    assert response.pagination.limit == 5000


@pytest.mark.asyncio
async def test_get_gpu_stats_history_empty_result() -> None:
    """Test get_gpu_stats_history with no samples."""
    db = AsyncMock()

    # Mock for count query
    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 0

    # Mock for data query
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars

    db.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

    response = await system_routes.get_gpu_stats_history(db=db)  # type: ignore[arg-type]

    assert isinstance(response, GPUStatsHistoryResponse)
    assert response.pagination.total == 0
    assert response.items == []


# =============================================================================
# Health Endpoint Tests (Lines 255-278)
# =============================================================================


@pytest.mark.asyncio
async def test_get_health_all_healthy() -> None:
    """Test health endpoint when all services are healthy."""
    # Clear health cache to ensure fresh result
    system_routes.clear_health_cache()
    mock_response = Response()

    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 5
    db.execute = AsyncMock(return_value=mock_result)

    redis = AsyncMock()
    redis.health_check = AsyncMock(return_value={"status": "healthy", "redis_version": "7.0.0"})

    # Mock settings to avoid environment validation issues
    mock_settings = MagicMock()
    mock_settings.yolo26_url = "http://localhost:8001"
    mock_settings.nemotron_url = "http://localhost:8002"

    # Patch AI health check to avoid network calls
    with (
        patch.object(system_routes, "get_settings", return_value=mock_settings),
        patch.object(
            system_routes,
            "_check_yolo26_health_with_circuit_breaker",
            return_value=(True, None),
        ),
        patch.object(
            system_routes,
            "_check_nemotron_health_with_circuit_breaker",
            return_value=(True, None),
        ),
    ):
        response = await system_routes.get_health(mock_response, db, redis)  # type: ignore[arg-type]

    assert isinstance(response, HealthResponse)
    assert response.status == "healthy"
    assert response.services["database"].status == "healthy"
    assert response.services["redis"].status == "healthy"
    assert response.services["ai"].status == "healthy"
    assert response.timestamp is not None
    assert mock_response.status_code == 200


@pytest.mark.asyncio
async def test_get_health_degraded_when_redis_unhealthy() -> None:
    """Test health endpoint returns degraded when non-critical service is unhealthy."""
    # Clear health cache to ensure fresh result
    system_routes.clear_health_cache()
    mock_response = Response()

    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 5
    db.execute = AsyncMock(return_value=mock_result)

    redis = AsyncMock()
    redis.health_check = AsyncMock(
        return_value={"status": "unhealthy", "error": "connection refused"}
    )

    # Mock settings to avoid environment validation issues
    mock_settings = MagicMock()
    mock_settings.yolo26_url = "http://localhost:8001"
    mock_settings.nemotron_url = "http://localhost:8002"

    # Patch AI health check to avoid network calls
    with (
        patch.object(system_routes, "get_settings", return_value=mock_settings),
        patch.object(
            system_routes,
            "_check_yolo26_health_with_circuit_breaker",
            return_value=(True, None),
        ),
        patch.object(
            system_routes,
            "_check_nemotron_health_with_circuit_breaker",
            return_value=(True, None),
        ),
    ):
        response = await system_routes.get_health(mock_response, db, redis)  # type: ignore[arg-type]

    assert isinstance(response, HealthResponse)
    assert response.status == "degraded"
    assert response.services["database"].status == "healthy"
    assert response.services["redis"].status == "unhealthy"
    assert mock_response.status_code == 503


@pytest.mark.asyncio
async def test_get_health_unhealthy_when_database_down() -> None:
    """Test health endpoint returns unhealthy when database is down."""
    # Clear health cache to ensure fresh result
    system_routes.clear_health_cache()
    mock_response = Response()

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=RuntimeError("db error"))

    redis = AsyncMock()
    redis.health_check = AsyncMock(return_value={"status": "healthy", "redis_version": "7.0.0"})

    # Mock settings to avoid environment validation issues
    mock_settings = MagicMock()
    mock_settings.yolo26_url = "http://localhost:8001"
    mock_settings.nemotron_url = "http://localhost:8002"

    # Patch AI health check to avoid network calls
    with (
        patch.object(system_routes, "get_settings", return_value=mock_settings),
        patch.object(
            system_routes,
            "_check_yolo26_health_with_circuit_breaker",
            return_value=(True, None),
        ),
        patch.object(
            system_routes,
            "_check_nemotron_health_with_circuit_breaker",
            return_value=(True, None),
        ),
    ):
        response = await system_routes.get_health(mock_response, db, redis)  # type: ignore[arg-type]

    assert isinstance(response, HealthResponse)
    assert response.status == "unhealthy"
    assert response.services["database"].status == "unhealthy"
    assert mock_response.status_code == 503


@pytest.mark.asyncio
async def test_get_health_unhealthy_when_all_services_down() -> None:
    """Test health endpoint returns unhealthy when all services down."""
    # Clear health cache to ensure fresh result
    system_routes.clear_health_cache()
    mock_response = Response()

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=RuntimeError("db error"))

    redis = AsyncMock()
    redis.health_check = AsyncMock(return_value={"status": "unhealthy", "error": "redis error"})

    # Mock settings to avoid environment validation issues
    mock_settings = MagicMock()
    mock_settings.yolo26_url = "http://localhost:8001"
    mock_settings.nemotron_url = "http://localhost:8002"

    # Patch AI health check to avoid network calls
    with (
        patch.object(system_routes, "get_settings", return_value=mock_settings),
        patch.object(
            system_routes,
            "_check_yolo26_health_with_circuit_breaker",
            return_value=(True, None),
        ),
        patch.object(
            system_routes,
            "_check_nemotron_health_with_circuit_breaker",
            return_value=(True, None),
        ),
    ):
        response = await system_routes.get_health(mock_response, db, redis)  # type: ignore[arg-type]

    assert isinstance(response, HealthResponse)
    assert response.status == "unhealthy"
    assert response.services["database"].status == "unhealthy"
    assert response.services["redis"].status == "unhealthy"
    assert mock_response.status_code == 503


@pytest.mark.asyncio
async def test_get_health_redis_none() -> None:
    """Test health endpoint when Redis client is None (connection failed during DI)."""
    # Clear health cache to ensure fresh result
    system_routes.clear_health_cache()
    mock_response = Response()

    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 5
    db.execute = AsyncMock(return_value=mock_result)

    # Mock settings to avoid environment validation issues
    mock_settings = MagicMock()
    mock_settings.yolo26_url = "http://localhost:8001"
    mock_settings.nemotron_url = "http://localhost:8002"

    # Patch AI health check to avoid network calls
    with (
        patch.object(system_routes, "get_settings", return_value=mock_settings),
        patch.object(
            system_routes,
            "_check_yolo26_health_with_circuit_breaker",
            return_value=(True, None),
        ),
        patch.object(
            system_routes,
            "_check_nemotron_health_with_circuit_breaker",
            return_value=(True, None),
        ),
    ):
        response = await system_routes.get_health(mock_response, db, None)

    assert isinstance(response, HealthResponse)
    assert response.status == "degraded"
    assert response.services["database"].status == "healthy"
    assert response.services["redis"].status == "unhealthy"
    assert "unavailable" in response.services["redis"].message.lower()
    assert mock_response.status_code == 503


# =============================================================================
# Config Tests (Lines 487-489, 532-550)
# =============================================================================


@pytest.mark.asyncio
async def test_get_config_returns_settings() -> None:
    """Test get_config returns application settings."""
    mock_settings = MagicMock()
    mock_settings.app_name = "Home Security Intelligence"
    mock_settings.app_version = "1.0.0"
    mock_settings.retention_days = 30
    mock_settings.log_retention_days = 7
    mock_settings.batch_window_seconds = 90
    mock_settings.batch_idle_timeout_seconds = 30
    mock_settings.detection_confidence_threshold = 0.5
    mock_settings.fast_path_confidence_threshold = 0.9
    mock_settings.grafana_url = "http://localhost:3002"
    mock_settings.debug = False

    mock_response = Response()

    with patch.object(system_routes, "get_settings", return_value=mock_settings):
        response = await system_routes.get_config(response=mock_response)

    assert isinstance(response, ConfigResponse)
    assert response.app_name == "Home Security Intelligence"
    assert response.version == "1.0.0"
    assert response.retention_days == 30
    assert response.log_retention_days == 7
    assert response.batch_window_seconds == 90
    assert response.batch_idle_timeout_seconds == 30
    assert response.detection_confidence_threshold == 0.5
    assert response.fast_path_confidence_threshold == 0.9


@pytest.mark.asyncio
async def test_patch_config_updates_retention_days(tmp_path, monkeypatch) -> None:
    """Test patch_config updates retention_days setting."""
    runtime_env = tmp_path / "runtime.env"
    monkeypatch.setenv("HSI_RUNTIME_ENV_PATH", str(runtime_env))

    mock_settings = MagicMock()
    mock_settings.app_name = "Home Security Intelligence"
    mock_settings.app_version = "1.0.0"
    mock_settings.retention_days = 7
    mock_settings.log_retention_days = 7
    mock_settings.batch_window_seconds = 90
    mock_settings.batch_idle_timeout_seconds = 30
    mock_settings.detection_confidence_threshold = 0.5
    mock_settings.fast_path_confidence_threshold = 0.9
    mock_settings.grafana_url = "http://localhost:3002"
    mock_settings.debug = False

    mock_get_settings = MagicMock(return_value=mock_settings)
    mock_get_settings.cache_clear = MagicMock()

    from backend.api.schemas.system import ConfigUpdateRequest

    update = ConfigUpdateRequest(retention_days=7)
    mock_request = MagicMock()
    mock_response = Response()
    mock_db = AsyncMock()

    with (
        patch.object(system_routes, "get_settings", mock_get_settings),
        patch.object(system_routes, "AuditService") as mock_audit,
    ):
        mock_audit.log_action = AsyncMock()
        response = await system_routes.patch_config(
            request=mock_request, response=mock_response, update=update, db=mock_db
        )

    assert isinstance(response, ConfigResponse)
    assert response.retention_days == 7
    mock_get_settings.cache_clear.assert_called_once()


@pytest.mark.asyncio
async def test_patch_config_updates_batch_window_seconds(tmp_path, monkeypatch) -> None:
    """Test patch_config updates batch_window_seconds setting."""
    runtime_env = tmp_path / "runtime.env"
    monkeypatch.setenv("HSI_RUNTIME_ENV_PATH", str(runtime_env))

    mock_settings = MagicMock()
    mock_settings.app_name = "Home Security Intelligence"
    mock_settings.app_version = "1.0.0"
    mock_settings.retention_days = 30
    mock_settings.log_retention_days = 7
    mock_settings.batch_window_seconds = 120
    mock_settings.batch_idle_timeout_seconds = 30
    mock_settings.detection_confidence_threshold = 0.5
    mock_settings.fast_path_confidence_threshold = 0.9
    mock_settings.grafana_url = "http://localhost:3002"
    mock_settings.debug = False

    mock_get_settings = MagicMock(return_value=mock_settings)
    mock_get_settings.cache_clear = MagicMock()

    from backend.api.schemas.system import ConfigUpdateRequest

    update = ConfigUpdateRequest(batch_window_seconds=120)
    mock_request = MagicMock()
    mock_response = Response()
    mock_db = AsyncMock()

    with (
        patch.object(system_routes, "get_settings", mock_get_settings),
        patch.object(system_routes, "AuditService") as mock_audit,
    ):
        mock_audit.log_action = AsyncMock()
        response = await system_routes.patch_config(
            request=mock_request, response=mock_response, update=update, db=mock_db
        )

    assert isinstance(response, ConfigResponse)
    assert response.batch_window_seconds == 120


@pytest.mark.asyncio
async def test_patch_config_updates_batch_idle_timeout(tmp_path, monkeypatch) -> None:
    """Test patch_config updates batch_idle_timeout_seconds setting."""
    runtime_env = tmp_path / "runtime.env"
    monkeypatch.setenv("HSI_RUNTIME_ENV_PATH", str(runtime_env))

    mock_settings = MagicMock()
    mock_settings.app_name = "Home Security Intelligence"
    mock_settings.app_version = "1.0.0"
    mock_settings.retention_days = 30
    mock_settings.log_retention_days = 7
    mock_settings.batch_window_seconds = 90
    mock_settings.batch_idle_timeout_seconds = 45
    mock_settings.detection_confidence_threshold = 0.5
    mock_settings.fast_path_confidence_threshold = 0.9
    mock_settings.grafana_url = "http://localhost:3002"
    mock_settings.debug = False

    mock_get_settings = MagicMock(return_value=mock_settings)
    mock_get_settings.cache_clear = MagicMock()

    from backend.api.schemas.system import ConfigUpdateRequest

    update = ConfigUpdateRequest(batch_idle_timeout_seconds=45)
    mock_request = MagicMock()
    mock_response = Response()
    mock_db = AsyncMock()

    with (
        patch.object(system_routes, "get_settings", mock_get_settings),
        patch.object(system_routes, "AuditService") as mock_audit,
    ):
        mock_audit.log_action = AsyncMock()
        response = await system_routes.patch_config(
            request=mock_request, response=mock_response, update=update, db=mock_db
        )

    assert isinstance(response, ConfigResponse)
    assert response.batch_idle_timeout_seconds == 45


@pytest.mark.asyncio
async def test_patch_config_updates_detection_threshold(tmp_path, monkeypatch) -> None:
    """Test patch_config updates detection_confidence_threshold setting."""
    runtime_env = tmp_path / "runtime.env"
    monkeypatch.setenv("HSI_RUNTIME_ENV_PATH", str(runtime_env))

    mock_settings = MagicMock()
    mock_settings.app_name = "Home Security Intelligence"
    mock_settings.app_version = "1.0.0"
    mock_settings.retention_days = 30
    mock_settings.log_retention_days = 7
    mock_settings.batch_window_seconds = 90
    mock_settings.batch_idle_timeout_seconds = 30
    mock_settings.detection_confidence_threshold = 0.75
    mock_settings.fast_path_confidence_threshold = 0.9
    mock_settings.grafana_url = "http://localhost:3002"
    mock_settings.debug = False

    mock_get_settings = MagicMock(return_value=mock_settings)
    mock_get_settings.cache_clear = MagicMock()

    from backend.api.schemas.system import ConfigUpdateRequest

    update = ConfigUpdateRequest(detection_confidence_threshold=0.75)
    mock_request = MagicMock()
    mock_response = Response()
    mock_db = AsyncMock()

    with (
        patch.object(system_routes, "get_settings", mock_get_settings),
        patch.object(system_routes, "AuditService") as mock_audit,
    ):
        mock_audit.log_action = AsyncMock()
        response = await system_routes.patch_config(
            request=mock_request, response=mock_response, update=update, db=mock_db
        )

    assert isinstance(response, ConfigResponse)
    assert response.detection_confidence_threshold == 0.75


@pytest.mark.asyncio
async def test_patch_config_no_changes(tmp_path, monkeypatch) -> None:
    """Test patch_config with no changes still returns current settings."""
    runtime_env = tmp_path / "runtime.env"
    monkeypatch.setenv("HSI_RUNTIME_ENV_PATH", str(runtime_env))

    mock_settings = MagicMock()
    mock_settings.app_name = "Home Security Intelligence"
    mock_settings.app_version = "1.0.0"
    mock_settings.retention_days = 30
    mock_settings.log_retention_days = 7
    mock_settings.batch_window_seconds = 90
    mock_settings.batch_idle_timeout_seconds = 30
    mock_settings.detection_confidence_threshold = 0.5
    mock_settings.fast_path_confidence_threshold = 0.9
    mock_settings.grafana_url = "http://localhost:3002"
    mock_settings.debug = False

    mock_get_settings = MagicMock(return_value=mock_settings)
    mock_get_settings.cache_clear = MagicMock()

    from backend.api.schemas.system import ConfigUpdateRequest

    # Empty update - no fields set
    update = ConfigUpdateRequest()
    mock_request = MagicMock()
    mock_response = Response()
    mock_db = AsyncMock()

    with (
        patch.object(system_routes, "get_settings", mock_get_settings),
        patch.object(system_routes, "AuditService") as mock_audit,
    ):
        mock_audit.log_action = AsyncMock()
        response = await system_routes.patch_config(
            request=mock_request, response=mock_response, update=update, db=mock_db
        )

    assert isinstance(response, ConfigResponse)
    # Cache clear is always called
    mock_get_settings.cache_clear.assert_called_once()


@pytest.mark.asyncio
async def test_patch_config_multiple_fields(tmp_path, monkeypatch) -> None:
    """Test patch_config updates multiple fields at once."""
    runtime_env = tmp_path / "runtime.env"
    monkeypatch.setenv("HSI_RUNTIME_ENV_PATH", str(runtime_env))

    mock_settings = MagicMock()
    mock_settings.app_name = "Home Security Intelligence"
    mock_settings.app_version = "1.0.0"
    mock_settings.retention_days = 14
    mock_settings.log_retention_days = 7
    mock_settings.batch_window_seconds = 60
    mock_settings.batch_idle_timeout_seconds = 20
    mock_settings.detection_confidence_threshold = 0.8
    mock_settings.fast_path_confidence_threshold = 0.9
    mock_settings.grafana_url = "http://localhost:3002"
    mock_settings.debug = False

    mock_get_settings = MagicMock(return_value=mock_settings)
    mock_get_settings.cache_clear = MagicMock()

    from backend.api.schemas.system import ConfigUpdateRequest

    update = ConfigUpdateRequest(
        retention_days=14,
        batch_window_seconds=60,
        batch_idle_timeout_seconds=20,
        detection_confidence_threshold=0.8,
    )
    mock_request = MagicMock()
    mock_response = Response()
    mock_db = AsyncMock()

    with (
        patch.object(system_routes, "get_settings", mock_get_settings),
        patch.object(system_routes, "AuditService") as mock_audit,
    ):
        mock_audit.log_action = AsyncMock()
        response = await system_routes.patch_config(
            request=mock_request, response=mock_response, update=update, db=mock_db
        )

    assert isinstance(response, ConfigResponse)
    assert response.retention_days == 14
    assert response.batch_window_seconds == 60
    assert response.batch_idle_timeout_seconds == 20
    assert response.detection_confidence_threshold == 0.8

    # Check the runtime env file was written correctly
    content = runtime_env.read_text(encoding="utf-8").splitlines()
    assert "BATCH_IDLE_TIMEOUT_SECONDS=20" in content
    assert "BATCH_WINDOW_SECONDS=60" in content
    assert "DETECTION_CONFIDENCE_THRESHOLD=0.8" in content
    assert "RETENTION_DAYS=14" in content


# =============================================================================
# System Stats Tests (Lines 574-591)
# =============================================================================


@pytest.mark.asyncio
async def test_get_stats_returns_counts() -> None:
    """Test get_stats returns camera, event, and detection counts."""
    db = AsyncMock()

    # Mock camera count
    camera_mock_result = MagicMock()
    camera_mock_result.scalar_one.return_value = 4

    # Mock event count
    event_mock_result = MagicMock()
    event_mock_result.scalar_one.return_value = 156

    # Mock detection count
    detection_mock_result = MagicMock()
    detection_mock_result.scalar_one.return_value = 892

    db.execute = AsyncMock(
        side_effect=[camera_mock_result, event_mock_result, detection_mock_result]
    )

    response = await system_routes.get_stats(db)  # type: ignore[arg-type]

    assert isinstance(response, SystemStatsResponse)
    assert response.total_cameras == 4
    assert response.total_events == 156
    assert response.total_detections == 892
    assert response.uptime_seconds > 0


@pytest.mark.asyncio
async def test_get_stats_zero_counts() -> None:
    """Test get_stats with zero counts."""
    db = AsyncMock()

    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 0
    db.execute = AsyncMock(return_value=mock_result)

    response = await system_routes.get_stats(db)  # type: ignore[arg-type]

    assert isinstance(response, SystemStatsResponse)
    assert response.total_cameras == 0
    assert response.total_events == 0
    assert response.total_detections == 0
    assert response.uptime_seconds > 0


# =============================================================================
# Telemetry / Latency Tests (Lines 628-629, 637-638, 651-655, 670-673, 707-710, 713, 721-723)
# =============================================================================


@pytest.mark.asyncio
async def test_record_stage_latency_valid_stage() -> None:
    """Test record_stage_latency with valid pipeline stage.

    Verifies that:
    - add_to_queue_safe is called with correct key and overflow policy
    - expire is called to set TTL on the key
    """
    from backend.core.redis import QueueAddResult, QueueOverflowPolicy

    redis = AsyncMock()
    redis.add_to_queue_safe = AsyncMock(return_value=QueueAddResult(success=True, queue_length=1))
    redis.expire = AsyncMock()

    await system_routes.record_stage_latency(redis, "watch", 10.5)  # type: ignore[arg-type]

    # Verify add_to_queue_safe called with correct parameters
    redis.add_to_queue_safe.assert_called_once_with(
        "telemetry:latency:watch",
        10.5,
        max_size=system_routes.MAX_LATENCY_SAMPLES,
        overflow_policy=QueueOverflowPolicy.DROP_OLDEST,
    )
    # Verify TTL is set
    redis.expire.assert_called_once_with(
        "telemetry:latency:watch",
        system_routes.LATENCY_TTL_SECONDS,
    )


@pytest.mark.asyncio
async def test_record_stage_latency_invalid_stage() -> None:
    """Test record_stage_latency with invalid pipeline stage logs warning."""
    redis = AsyncMock()
    redis.add_to_queue_safe = AsyncMock()

    with patch.object(system_routes.logger, "warning") as mock_warning:
        await system_routes.record_stage_latency(redis, "invalid_stage", 10.5)  # type: ignore[arg-type]

    mock_warning.assert_called_once()
    assert "invalid_stage" in mock_warning.call_args[0][0]
    redis.add_to_queue_safe.assert_not_called()


@pytest.mark.asyncio
async def test_record_stage_latency_exception_handling() -> None:
    """Test record_stage_latency handles Redis exceptions gracefully."""
    redis = AsyncMock()
    redis.add_to_queue_safe = AsyncMock(side_effect=ConnectionError("redis error"))

    with patch.object(system_routes.logger, "warning") as mock_warning:
        await system_routes.record_stage_latency(redis, "detect", 15.0)  # type: ignore[arg-type]

    mock_warning.assert_called_once()
    assert "Failed to record latency" in mock_warning.call_args[0][0]


def test_calculate_percentile_empty_list() -> None:
    """Test _calculate_percentile with empty list returns 0.0."""
    result = system_routes._calculate_percentile([], 50)
    assert result == 0.0


def test_calculate_percentile_single_value() -> None:
    """Test _calculate_percentile with single value."""
    result = system_routes._calculate_percentile([100.0], 50)
    assert result == 100.0


def test_calculate_percentile_multiple_values() -> None:
    """Test _calculate_percentile calculates correct percentile."""
    samples = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    p50 = system_routes._calculate_percentile(samples, 50)
    p95 = system_routes._calculate_percentile(samples, 95)
    p99 = system_routes._calculate_percentile(samples, 99)

    # For 10 samples:
    # p50: index = 5 -> 60.0
    # p95: index = 9 (clamped) -> 100.0
    # p99: index = 9 (clamped) -> 100.0
    assert p50 == 60.0
    assert p95 == 100.0
    assert p99 == 100.0


def test_calculate_percentile_clamping() -> None:
    """Test _calculate_percentile clamps index to valid range."""
    samples = [10.0, 20.0, 30.0]
    # 100th percentile should clamp to last element
    result = system_routes._calculate_percentile(samples, 100)
    assert result == 30.0


def test_calculate_stage_latency_empty_samples() -> None:
    """Test _calculate_stage_latency returns None for empty samples."""
    result = system_routes._calculate_stage_latency([])
    assert result is None


def test_calculate_stage_latency_single_sample() -> None:
    """Test _calculate_stage_latency with single sample."""
    result = system_routes._calculate_stage_latency([50.0])

    assert isinstance(result, StageLatency)
    assert result.avg_ms == 50.0
    assert result.min_ms == 50.0
    assert result.max_ms == 50.0
    assert result.p50_ms == 50.0
    assert result.p95_ms == 50.0
    assert result.p99_ms == 50.0
    assert result.sample_count == 1


def test_calculate_stage_latency_multiple_samples() -> None:
    """Test _calculate_stage_latency with multiple samples."""
    samples = [10.0, 20.0, 30.0, 40.0, 50.0]
    result = system_routes._calculate_stage_latency(samples)

    assert isinstance(result, StageLatency)
    assert result.avg_ms == 30.0  # (10+20+30+40+50)/5 = 30
    assert result.min_ms == 10.0
    assert result.max_ms == 50.0
    assert result.sample_count == 5


def test_calculate_stage_latency_unsorted_samples() -> None:
    """Test _calculate_stage_latency sorts samples correctly."""
    samples = [50.0, 10.0, 30.0, 20.0, 40.0]
    result = system_routes._calculate_stage_latency(samples)

    assert isinstance(result, StageLatency)
    assert result.min_ms == 10.0
    assert result.max_ms == 50.0


@pytest.mark.asyncio
async def test_get_latency_stats_with_data() -> None:
    """Test get_latency_stats returns latency statistics for all stages."""
    redis = AsyncMock()
    redis.peek_queue = AsyncMock(
        side_effect=[
            # watch stage
            [10.0, 15.0, 20.0],
            # detect stage
            [100.0, 150.0, 200.0],
            # batch stage
            [1000.0, 1500.0],
            # analyze stage
            [5000.0, 6000.0, 7000.0],
        ]
    )

    result = await system_routes.get_latency_stats(redis)  # type: ignore[arg-type]

    assert isinstance(result, PipelineLatencies)
    assert result.watch is not None
    assert result.watch.sample_count == 3
    assert result.detect is not None
    assert result.detect.sample_count == 3
    assert result.batch is not None
    assert result.batch.sample_count == 2
    assert result.analyze is not None
    assert result.analyze.sample_count == 3


@pytest.mark.asyncio
async def test_get_latency_stats_empty_queues() -> None:
    """Test get_latency_stats handles empty queues."""
    redis = AsyncMock()
    redis.peek_queue = AsyncMock(return_value=[])

    result = await system_routes.get_latency_stats(redis)  # type: ignore[arg-type]

    assert isinstance(result, PipelineLatencies)
    assert result.watch is None
    assert result.detect is None
    assert result.batch is None
    assert result.analyze is None


@pytest.mark.asyncio
async def test_get_latency_stats_invalid_values_filtered() -> None:
    """Test get_latency_stats filters out invalid sample values."""
    redis = AsyncMock()
    redis.peek_queue = AsyncMock(
        side_effect=[
            # watch stage with some invalid values
            [10.0, "invalid", 20.0, None, 30.0],
            # Other stages empty
            [],
            [],
            [],
        ]
    )

    result = await system_routes.get_latency_stats(redis)  # type: ignore[arg-type]

    assert isinstance(result, PipelineLatencies)
    assert result.watch is not None
    # Only valid numeric values should be counted
    assert result.watch.sample_count == 3


@pytest.mark.asyncio
async def test_get_latency_stats_exception_handling() -> None:
    """Test get_latency_stats returns None on exception."""
    redis = AsyncMock()
    redis.peek_queue = AsyncMock(side_effect=ConnectionError("redis error"))

    with patch.object(system_routes.logger, "warning") as mock_warning:
        result = await system_routes.get_latency_stats(redis)  # type: ignore[arg-type]

    assert result is None
    mock_warning.assert_called_once()
    assert "Failed to get latency stats" in mock_warning.call_args[0][0]


@pytest.mark.asyncio
async def test_get_telemetry_returns_queue_depths_and_latencies() -> None:
    """Test get_telemetry returns queue depths and latency statistics."""
    redis = AsyncMock()
    redis.get_queue_length = AsyncMock(side_effect=[5, 2])
    redis.peek_queue = AsyncMock(
        side_effect=[
            [10.0, 15.0],  # watch
            [100.0, 150.0],  # detect
            [1000.0],  # batch
            [5000.0, 6000.0],  # analyze
        ]
    )

    response = await system_routes.get_telemetry(redis)  # type: ignore[arg-type]

    assert isinstance(response, TelemetryResponse)
    assert response.queues.detection_queue == 5
    assert response.queues.analysis_queue == 2
    assert response.latencies is not None
    assert response.timestamp is not None


@pytest.mark.asyncio
async def test_get_telemetry_queue_depth_exception() -> None:
    """Test get_telemetry handles queue depth errors gracefully."""
    redis = AsyncMock()
    redis.get_queue_length = AsyncMock(side_effect=ConnectionError("redis error"))
    redis.peek_queue = AsyncMock(return_value=[])

    with patch.object(system_routes.logger, "warning"):
        response = await system_routes.get_telemetry(redis)  # type: ignore[arg-type]

    assert isinstance(response, TelemetryResponse)
    # Should return zeros on error
    assert response.queues.detection_queue == 0
    assert response.queues.analysis_queue == 0


# =============================================================================
# Additional Edge Case Tests
# =============================================================================


@pytest.mark.asyncio
async def test_check_database_health_healthy() -> None:
    """Test check_database_health returns healthy on success with pool status."""
    from unittest.mock import patch

    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 5
    db.execute = AsyncMock(return_value=mock_result)

    # Mock get_pool_status to return realistic pool metrics
    mock_pool_status = {
        "pool_size": 20,
        "overflow": 5,
        "checkedin": 15,
        "checkedout": 10,
        "total_connections": 25,
    }

    with patch(
        "backend.core.database.get_pool_status",
        AsyncMock(return_value=mock_pool_status),
    ):
        status = await system_routes.check_database_health(db)  # type: ignore[arg-type]

    assert status.status == "healthy"
    assert status.message == "Database operational"
    assert status.details is not None
    assert "pool" in status.details
    assert status.details["pool"]["size"] == 20
    assert status.details["pool"]["checkedout"] == 10


@pytest.mark.asyncio
async def test_check_redis_health_healthy() -> None:
    """Test check_redis_health returns healthy with version details."""
    redis = AsyncMock()
    redis.health_check = AsyncMock(return_value={"status": "healthy", "redis_version": "7.2.0"})

    status = await system_routes.check_redis_health(redis)  # type: ignore[arg-type]

    assert status.status == "healthy"
    assert status.message == "Redis connected"
    assert status.details == {"redis_version": "7.2.0"}


@pytest.mark.asyncio
async def test_check_redis_health_exception() -> None:
    """Test check_redis_health returns unhealthy on exception."""
    redis = AsyncMock()
    redis.health_check = AsyncMock(side_effect=ConnectionError("connection refused"))

    status = await system_routes.check_redis_health(redis)  # type: ignore[arg-type]

    assert status.status == "unhealthy"
    assert "connection refused" in status.message


@pytest.mark.asyncio
async def test_check_ai_services_health() -> None:
    """Test check_ai_services_health returns expected status."""
    # Patch to avoid network calls and test the happy path
    with (
        patch.object(
            system_routes,
            "_check_yolo26_health_with_circuit_breaker",
            return_value=(True, None),
        ),
        patch.object(
            system_routes,
            "_check_nemotron_health_with_circuit_breaker",
            return_value=(True, None),
        ),
    ):
        status = await system_routes.check_ai_services_health()

    assert status.status == "healthy"
    assert status.message == "AI services operational"


def test_write_runtime_env_creates_directory(tmp_path, monkeypatch) -> None:
    """Test _write_runtime_env creates parent directory if needed."""
    nested_path = tmp_path / "nested" / "dir" / "runtime.env"
    monkeypatch.setenv("HSI_RUNTIME_ENV_PATH", str(nested_path))

    system_routes._write_runtime_env({"TEST_KEY": "value"})

    assert nested_path.exists()
    content = nested_path.read_text(encoding="utf-8")
    assert "TEST_KEY=value" in content


def test_write_runtime_env_creates_new_file(tmp_path, monkeypatch) -> None:
    """Test _write_runtime_env creates file if it doesn't exist."""
    runtime_env = tmp_path / "runtime.env"
    monkeypatch.setenv("HSI_RUNTIME_ENV_PATH", str(runtime_env))

    assert not runtime_env.exists()

    system_routes._write_runtime_env({"NEW_KEY": "new_value"})

    assert runtime_env.exists()
    content = runtime_env.read_text(encoding="utf-8")
    assert "NEW_KEY=new_value" in content


def test_pipeline_stages_constant() -> None:
    """Test PIPELINE_STAGES contains expected stages."""
    assert system_routes.PIPELINE_STAGES == ("watch", "detect", "batch", "analyze")


def test_latency_constants() -> None:
    """Test telemetry constants have reasonable values."""
    assert system_routes.LATENCY_TTL_SECONDS == 3600
    assert system_routes.MAX_LATENCY_SAMPLES == 1000
    assert system_routes.LATENCY_KEY_PREFIX == "telemetry:latency:"


@pytest.mark.asyncio
async def test_get_latency_stats_string_conversion() -> None:
    """Test get_latency_stats correctly converts string values to floats."""
    redis = AsyncMock()
    # Return string values that should be converted to floats
    redis.peek_queue = AsyncMock(
        side_effect=[
            ["10.5", "20.0", "30.5"],  # watch - strings
            [],
            [],
            [],
        ]
    )

    result = await system_routes.get_latency_stats(redis)  # type: ignore[arg-type]

    assert isinstance(result, PipelineLatencies)
    assert result.watch is not None
    assert result.watch.sample_count == 3
    # Verify values were converted correctly
    assert result.watch.min_ms == 10.5
    assert result.watch.max_ms == 30.5


@pytest.mark.asyncio
async def test_get_latency_stats_mixed_valid_invalid() -> None:
    """Test get_latency_stats handles mix of valid and invalid values."""
    redis = AsyncMock()
    redis.peek_queue = AsyncMock(
        side_effect=[
            # Mix of valid floats, valid strings, and invalid values
            [10.0, "20.0", {"invalid": True}, [], "not_a_number", 30.0],
            [],
            [],
            [],
        ]
    )

    result = await system_routes.get_latency_stats(redis)  # type: ignore[arg-type]

    assert isinstance(result, PipelineLatencies)
    assert result.watch is not None
    # Only 3 valid values: 10.0, "20.0" (converted), 30.0
    assert result.watch.sample_count == 3


# =============================================================================
# TTL and Max-Sample Behavior Tests
# =============================================================================


@pytest.mark.asyncio
async def test_record_stage_latency_sets_ttl() -> None:
    """Test record_stage_latency sets TTL on the latency key.

    The TTL should be refreshed on each write to ensure active stages
    don't expire while inactive stages eventually do.
    """
    redis = AsyncMock()
    redis.expire = AsyncMock(return_value=True)

    await system_routes.record_stage_latency(redis, "detect", 100.0)  # type: ignore[arg-type]

    # Verify expire was called with correct TTL
    redis.expire.assert_called_once_with(
        "telemetry:latency:detect",
        system_routes.LATENCY_TTL_SECONDS,
    )


@pytest.mark.asyncio
async def test_record_stage_latency_uses_max_samples() -> None:
    """Test record_stage_latency passes max_size to limit stored samples.

    This ensures memory usage is bounded by trimming old samples
    when the list exceeds MAX_LATENCY_SAMPLES.
    """
    from backend.core.redis import QueueAddResult

    redis = AsyncMock()
    redis.add_to_queue_safe = AsyncMock(return_value=QueueAddResult(success=True, queue_length=1))
    redis.expire = AsyncMock()

    await system_routes.record_stage_latency(redis, "batch", 5000.0)  # type: ignore[arg-type]

    # Verify add_to_queue_safe called with max_size parameter
    redis.add_to_queue_safe.assert_called_once()
    call_args = redis.add_to_queue_safe.call_args
    assert call_args.kwargs.get("max_size") == system_routes.MAX_LATENCY_SAMPLES


@pytest.mark.asyncio
async def test_record_stage_latency_all_stages_use_correct_keys() -> None:
    """Test record_stage_latency uses correct Redis keys for all stages."""
    from backend.core.redis import QueueAddResult

    redis = AsyncMock()
    redis.add_to_queue_safe = AsyncMock(return_value=QueueAddResult(success=True, queue_length=1))
    redis.expire = AsyncMock()

    for stage in system_routes.PIPELINE_STAGES:
        redis.add_to_queue_safe.reset_mock()
        redis.expire.reset_mock()

        await system_routes.record_stage_latency(redis, stage, 50.0)  # type: ignore[arg-type]

        expected_key = f"{system_routes.LATENCY_KEY_PREFIX}{stage}"
        redis.add_to_queue_safe.assert_called_once()
        assert redis.add_to_queue_safe.call_args[0][0] == expected_key
        redis.expire.assert_called_once()
        assert redis.expire.call_args[0][0] == expected_key


@pytest.mark.asyncio
async def test_record_stage_latency_expire_failure_logs_warning() -> None:
    """Test record_stage_latency logs warning if expire fails."""
    from backend.core.redis import QueueAddResult

    redis = AsyncMock()
    redis.add_to_queue_safe = AsyncMock(return_value=QueueAddResult(success=True, queue_length=1))
    redis.expire = AsyncMock(side_effect=ConnectionError("redis expire error"))

    with patch.object(system_routes.logger, "warning") as mock_warning:
        await system_routes.record_stage_latency(redis, "analyze", 200.0)  # type: ignore[arg-type]

    # Should have logged a warning about the failure
    mock_warning.assert_called_once()
    assert "Failed to record latency" in mock_warning.call_args[0][0]


@pytest.mark.asyncio
async def test_record_stage_latency_ttl_refreshes_on_each_write() -> None:
    """Test that TTL is refreshed on each write to keep active stages alive.

    This simulates multiple writes and verifies expire is called each time.
    """
    from backend.core.redis import QueueAddResult

    redis = AsyncMock()
    redis.add_to_queue_safe = AsyncMock(return_value=QueueAddResult(success=True, queue_length=1))
    redis.expire = AsyncMock(return_value=True)

    # Record multiple samples
    for i in range(5):
        await system_routes.record_stage_latency(redis, "watch", float(i * 10))  # type: ignore[arg-type]

    # expire should be called once per write
    assert redis.expire.call_count == 5


def test_max_latency_samples_is_reasonable() -> None:
    """Test MAX_LATENCY_SAMPLES is set to a reasonable value.

    1000 samples is enough for statistical analysis while keeping
    memory usage bounded.
    """
    assert system_routes.MAX_LATENCY_SAMPLES == 1000
    assert system_routes.MAX_LATENCY_SAMPLES > 100  # Enough for percentiles
    assert system_routes.MAX_LATENCY_SAMPLES < 10000  # Not excessive


def test_latency_ttl_is_reasonable() -> None:
    """Test LATENCY_TTL_SECONDS is set to a reasonable value.

    1 hour (3600 seconds) allows capturing latency trends while
    ensuring inactive stages eventually expire.
    """
    assert system_routes.LATENCY_TTL_SECONDS == 3600
    assert system_routes.LATENCY_TTL_SECONDS >= 60  # At least 1 minute
    assert system_routes.LATENCY_TTL_SECONDS <= 86400  # At most 1 day


# =============================================================================
# Cleanup Endpoint Tests
# =============================================================================


@pytest.mark.asyncio
async def test_trigger_cleanup_success() -> None:
    """Test trigger_cleanup successfully runs cleanup and returns stats."""
    mock_stats = MagicMock()
    mock_stats.events_deleted = 10
    mock_stats.detections_deleted = 50
    mock_stats.gpu_stats_deleted = 100
    mock_stats.logs_deleted = 25
    mock_stats.thumbnails_deleted = 50
    mock_stats.images_deleted = 0
    mock_stats.space_reclaimed = 1024000

    mock_settings = MagicMock()
    mock_settings.retention_days = 30

    mock_cleanup_service = MagicMock()
    mock_cleanup_service.run_cleanup = AsyncMock(return_value=mock_stats)

    with (
        patch.object(system_routes, "get_settings", return_value=mock_settings),
        patch(
            "backend.services.cleanup_service.CleanupService",
            return_value=mock_cleanup_service,
        ),
    ):
        response = await system_routes.trigger_cleanup()

    assert isinstance(response, CleanupResponse)
    assert response.events_deleted == 10
    assert response.detections_deleted == 50
    assert response.gpu_stats_deleted == 100
    assert response.logs_deleted == 25
    assert response.thumbnails_deleted == 50
    assert response.images_deleted == 0
    assert response.space_reclaimed == 1024000
    assert response.retention_days == 30
    assert response.timestamp is not None


@pytest.mark.asyncio
async def test_trigger_cleanup_uses_retention_from_settings() -> None:
    """Test trigger_cleanup uses retention_days from current settings."""
    mock_stats = MagicMock()
    mock_stats.events_deleted = 0
    mock_stats.detections_deleted = 0
    mock_stats.gpu_stats_deleted = 0
    mock_stats.logs_deleted = 0
    mock_stats.thumbnails_deleted = 0
    mock_stats.images_deleted = 0
    mock_stats.space_reclaimed = 0

    mock_settings = MagicMock()
    mock_settings.retention_days = 7  # Custom retention

    mock_cleanup_service = MagicMock()
    mock_cleanup_service.run_cleanup = AsyncMock(return_value=mock_stats)

    with (
        patch.object(system_routes, "get_settings", return_value=mock_settings),
        patch(
            "backend.services.cleanup_service.CleanupService",
            return_value=mock_cleanup_service,
        ) as mock_cleanup_class,
    ):
        response = await system_routes.trigger_cleanup()

    # Verify CleanupService was instantiated with correct retention_days
    mock_cleanup_class.assert_called_once_with(
        retention_days=7,
        thumbnail_dir="backend/data/thumbnails",
        delete_images=False,
    )
    assert response.retention_days == 7


@pytest.mark.asyncio
async def test_trigger_cleanup_zero_deletions() -> None:
    """Test trigger_cleanup when nothing needs to be cleaned up."""
    mock_stats = MagicMock()
    mock_stats.events_deleted = 0
    mock_stats.detections_deleted = 0
    mock_stats.gpu_stats_deleted = 0
    mock_stats.logs_deleted = 0
    mock_stats.thumbnails_deleted = 0
    mock_stats.images_deleted = 0
    mock_stats.space_reclaimed = 0

    mock_settings = MagicMock()
    mock_settings.retention_days = 30

    mock_cleanup_service = MagicMock()
    mock_cleanup_service.run_cleanup = AsyncMock(return_value=mock_stats)

    with (
        patch.object(system_routes, "get_settings", return_value=mock_settings),
        patch(
            "backend.services.cleanup_service.CleanupService",
            return_value=mock_cleanup_service,
        ),
    ):
        response = await system_routes.trigger_cleanup()

    assert isinstance(response, CleanupResponse)
    assert response.events_deleted == 0
    assert response.detections_deleted == 0
    assert response.gpu_stats_deleted == 0
    assert response.logs_deleted == 0
    assert response.thumbnails_deleted == 0


@pytest.mark.asyncio
async def test_trigger_cleanup_exception_propagates() -> None:
    """Test trigger_cleanup propagates exception from CleanupService."""
    mock_settings = MagicMock()
    mock_settings.retention_days = 30

    mock_cleanup_service = MagicMock()
    mock_cleanup_service.run_cleanup = AsyncMock(
        side_effect=RuntimeError("Database connection failed")
    )

    with (
        patch.object(system_routes, "get_settings", return_value=mock_settings),
        patch(
            "backend.services.cleanup_service.CleanupService",
            return_value=mock_cleanup_service,
        ),
        pytest.raises(RuntimeError, match="Database connection failed"),
    ):
        await system_routes.trigger_cleanup()


@pytest.mark.asyncio
async def test_trigger_cleanup_does_not_delete_images_by_default() -> None:
    """Test trigger_cleanup does not delete original images by default."""
    mock_stats = MagicMock()
    mock_stats.events_deleted = 5
    mock_stats.detections_deleted = 20
    mock_stats.gpu_stats_deleted = 50
    mock_stats.logs_deleted = 10
    mock_stats.thumbnails_deleted = 20
    mock_stats.images_deleted = 0  # Should be 0 when delete_images=False
    mock_stats.space_reclaimed = 512000

    mock_settings = MagicMock()
    mock_settings.retention_days = 30

    mock_cleanup_service = MagicMock()
    mock_cleanup_service.run_cleanup = AsyncMock(return_value=mock_stats)

    with (
        patch.object(system_routes, "get_settings", return_value=mock_settings),
        patch(
            "backend.services.cleanup_service.CleanupService",
            return_value=mock_cleanup_service,
        ) as mock_cleanup_class,
    ):
        response = await system_routes.trigger_cleanup()

    # Verify delete_images=False
    mock_cleanup_class.assert_called_once()
    call_kwargs = mock_cleanup_class.call_args[1]
    assert call_kwargs["delete_images"] is False
    assert response.images_deleted == 0


@pytest.mark.asyncio
async def test_trigger_cleanup_logs_operation() -> None:
    """Test trigger_cleanup logs the cleanup operation."""
    mock_stats = MagicMock()
    mock_stats.events_deleted = 10
    mock_stats.detections_deleted = 50
    mock_stats.gpu_stats_deleted = 100
    mock_stats.logs_deleted = 25
    mock_stats.thumbnails_deleted = 50
    mock_stats.images_deleted = 0
    mock_stats.space_reclaimed = 1024000

    mock_settings = MagicMock()
    mock_settings.retention_days = 30

    mock_cleanup_service = MagicMock()
    mock_cleanup_service.run_cleanup = AsyncMock(return_value=mock_stats)

    with (
        patch.object(system_routes, "get_settings", return_value=mock_settings),
        patch(
            "backend.services.cleanup_service.CleanupService",
            return_value=mock_cleanup_service,
        ),
        patch.object(system_routes.logger, "info") as mock_logger,
    ):
        await system_routes.trigger_cleanup()

    # Verify logging calls
    log_messages = [call[0][0] for call in mock_logger.call_args_list]
    assert any("Manual cleanup triggered" in msg for msg in log_messages)
    assert any("Manual cleanup completed" in msg for msg in log_messages)


# =============================================================================
# AI Services Health Check Tests
# =============================================================================


@pytest.mark.asyncio
async def test_check_yolo26_health_success() -> None:
    """Test YOLO26 health check returns healthy when service responds."""
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        is_healthy, error = await system_routes._check_yolo26_health("http://localhost:8090", 3.0)

        assert is_healthy is True
        assert error is None


@pytest.mark.asyncio
async def test_check_yolo26_health_connection_refused() -> None:
    """Test YOLO26 health check handles connection refused error."""
    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Connection refused")):
        is_healthy, error = await system_routes._check_yolo26_health("http://localhost:8090", 3.0)

        assert is_healthy is False
        assert error is not None
        assert "connection refused" in error.lower()


@pytest.mark.asyncio
async def test_check_yolo26_health_timeout() -> None:
    """Test YOLO26 health check handles timeout error."""
    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Timeout")):
        is_healthy, error = await system_routes._check_yolo26_health("http://localhost:8090", 3.0)

        assert is_healthy is False
        assert error is not None
        assert "timed out" in error.lower()


@pytest.mark.asyncio
async def test_check_yolo26_health_http_error() -> None:
    """Test YOLO26 health check handles HTTP error status."""
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(), response=mock_response
        )
        mock_get.return_value = mock_response

        is_healthy, error = await system_routes._check_yolo26_health("http://localhost:8090", 3.0)

        assert is_healthy is False
        assert error is not None
        assert "500" in error


@pytest.mark.asyncio
async def test_check_yolo26_health_unexpected_error() -> None:
    """Test YOLO26 health check handles unexpected error."""
    with patch("httpx.AsyncClient.get", side_effect=OSError("Unexpected network error")):
        is_healthy, error = await system_routes._check_yolo26_health("http://localhost:8090", 3.0)

        assert is_healthy is False
        assert error is not None
        assert "error" in error.lower()


@pytest.mark.asyncio
async def test_check_nemotron_health_success() -> None:
    """Test Nemotron health check returns healthy when service responds."""
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        is_healthy, error = await system_routes._check_nemotron_health("http://localhost:8091", 3.0)

        assert is_healthy is True
        assert error is None


@pytest.mark.asyncio
async def test_check_nemotron_health_connection_refused() -> None:
    """Test Nemotron health check handles connection refused error."""
    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Connection refused")):
        is_healthy, error = await system_routes._check_nemotron_health("http://localhost:8091", 3.0)

        assert is_healthy is False
        assert error is not None
        assert "connection refused" in error.lower()


@pytest.mark.asyncio
async def test_check_nemotron_health_timeout() -> None:
    """Test Nemotron health check handles timeout error."""
    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Timeout")):
        is_healthy, error = await system_routes._check_nemotron_health("http://localhost:8091", 3.0)

        assert is_healthy is False
        assert error is not None
        assert "timed out" in error.lower()


@pytest.mark.asyncio
async def test_check_nemotron_health_http_error() -> None:
    """Test Nemotron health check handles HTTP error status."""
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Service Unavailable", request=MagicMock(), response=mock_response
        )
        mock_get.return_value = mock_response

        is_healthy, error = await system_routes._check_nemotron_health("http://localhost:8091", 3.0)

        assert is_healthy is False
        assert error is not None
        assert "503" in error


@pytest.mark.asyncio
async def test_check_nemotron_health_unexpected_error() -> None:
    """Test Nemotron health check handles unexpected error."""
    with patch("httpx.AsyncClient.get", side_effect=RuntimeError("Unexpected")):
        is_healthy, error = await system_routes._check_nemotron_health("http://localhost:8091", 3.0)

        assert is_healthy is False
        assert error is not None
        assert "error" in error.lower()


@pytest.mark.asyncio
async def test_check_ai_services_health_both_healthy() -> None:
    """Test AI services health check when both services are healthy."""
    # Mock settings to avoid environment validation issues
    mock_settings = MagicMock()
    mock_settings.yolo26_url = "http://localhost:8001"
    mock_settings.nemotron_url = "http://localhost:8002"

    with (
        patch.object(system_routes, "get_settings", return_value=mock_settings),
        patch.object(
            system_routes,
            "_check_yolo26_health_with_circuit_breaker",
            return_value=(True, None),
        ),
        patch.object(
            system_routes,
            "_check_nemotron_health_with_circuit_breaker",
            return_value=(True, None),
        ),
    ):
        status = await system_routes.check_ai_services_health()

        assert status.status == "healthy"
        assert status.message == "AI services operational"
        assert status.details is not None
        assert status.details["yolo26"] == "healthy"
        assert status.details["nemotron"] == "healthy"


@pytest.mark.asyncio
async def test_check_ai_services_health_yolo26_down() -> None:
    """Test AI services health check when YOLO26 is down but Nemotron is up."""
    # Mock settings to avoid environment validation issues
    mock_settings = MagicMock()
    mock_settings.yolo26_url = "http://localhost:8001"
    mock_settings.nemotron_url = "http://localhost:8002"

    with (
        patch.object(system_routes, "get_settings", return_value=mock_settings),
        patch.object(
            system_routes,
            "_check_yolo26_health_with_circuit_breaker",
            return_value=(False, "YOLO26 service returned HTTP 500"),
        ),
        patch.object(
            system_routes,
            "_check_nemotron_health_with_circuit_breaker",
            return_value=(True, None),
        ),
    ):
        status = await system_routes.check_ai_services_health()

        assert status.status == "degraded"
        assert "YOLO26" in status.message
        assert "unavailable" in status.message
        assert "Nemotron" in status.message
        assert "operational" in status.message
        assert status.details is not None
        assert "500" in status.details["yolo26"]
        assert status.details["nemotron"] == "healthy"


@pytest.mark.asyncio
async def test_check_ai_services_health_nemotron_down() -> None:
    """Test AI services health check when Nemotron is down but YOLO26 is up."""
    # Mock settings to avoid environment validation issues
    mock_settings = MagicMock()
    mock_settings.yolo26_url = "http://localhost:8001"
    mock_settings.nemotron_url = "http://localhost:8002"

    with (
        patch.object(system_routes, "get_settings", return_value=mock_settings),
        patch.object(
            system_routes,
            "_check_yolo26_health_with_circuit_breaker",
            return_value=(True, None),
        ),
        patch.object(
            system_routes,
            "_check_nemotron_health_with_circuit_breaker",
            return_value=(False, "Nemotron service returned HTTP 500"),
        ),
    ):
        status = await system_routes.check_ai_services_health()

        assert status.status == "degraded"
        assert "Nemotron" in status.message
        assert "unavailable" in status.message
        assert "YOLO26" in status.message
        assert "operational" in status.message
        assert status.details is not None
        assert status.details["yolo26"] == "healthy"
        assert "500" in status.details["nemotron"]


@pytest.mark.asyncio
async def test_check_ai_services_health_both_down() -> None:
    """Test AI services health check when both services are down."""
    # Mock settings to avoid environment validation issues
    mock_settings = MagicMock()
    mock_settings.yolo26_url = "http://localhost:8001"
    mock_settings.nemotron_url = "http://localhost:8002"

    with (
        patch.object(system_routes, "get_settings", return_value=mock_settings),
        patch.object(
            system_routes,
            "_check_yolo26_health_with_circuit_breaker",
            return_value=(False, "YOLO26 service returned HTTP 500"),
        ),
        patch.object(
            system_routes,
            "_check_nemotron_health_with_circuit_breaker",
            return_value=(False, "Nemotron service returned HTTP 503"),
        ),
    ):
        status = await system_routes.check_ai_services_health()

        assert status.status == "unhealthy"
        assert status.message == "All AI services unavailable"
        assert status.details is not None
        assert "500" in status.details["yolo26"]
        assert "503" in status.details["nemotron"]


@pytest.mark.asyncio
async def test_ai_health_check_timeout_constant_is_reasonable() -> None:
    """Test that the AI health check timeout constant has a reasonable value."""
    # The timeout should be at least 1 second to allow for slow responses
    assert system_routes.AI_HEALTH_CHECK_TIMEOUT_SECONDS >= 1.0
    # The timeout should not be more than 10 seconds to avoid blocking
    assert system_routes.AI_HEALTH_CHECK_TIMEOUT_SECONDS <= 10.0


@pytest.mark.asyncio
async def test_check_ai_services_health_returns_details() -> None:
    """Test that AI services health check always returns details dict."""
    # Mock settings to avoid environment validation issues
    mock_settings = MagicMock()
    mock_settings.yolo26_url = "http://localhost:8001"
    mock_settings.nemotron_url = "http://localhost:8002"

    # Both services down should still populate details
    with (
        patch.object(system_routes, "get_settings", return_value=mock_settings),
        patch.object(
            system_routes,
            "_check_yolo26_health_with_circuit_breaker",
            return_value=(False, "YOLO26 connection refused"),
        ),
        patch.object(
            system_routes,
            "_check_nemotron_health_with_circuit_breaker",
            return_value=(False, "Nemotron connection refused"),
        ),
    ):
        status = await system_routes.check_ai_services_health()

        assert status.details is not None
        assert "yolo26" in status.details
        assert "nemotron" in status.details


@pytest.mark.asyncio
async def test_check_ai_services_health_uses_config_urls() -> None:
    """Test that AI services health check uses config URLs."""
    with (
        patch.object(system_routes, "get_settings") as mock_settings,
        patch.object(
            system_routes,
            "_check_yolo26_health_with_circuit_breaker",
            return_value=(True, None),
        ) as mock_yolo26,
        patch.object(
            system_routes,
            "_check_nemotron_health_with_circuit_breaker",
            return_value=(True, None),
        ) as mock_nemotron,
    ):
        mock_settings.return_value.yolo26_url = "http://custom-yolo26:9000"
        mock_settings.return_value.nemotron_url = "http://custom-nemotron:9001"

        await system_routes.check_ai_services_health()

        # Verify the circuit breaker health check functions were called
        mock_yolo26.assert_called_once()
        mock_nemotron.assert_called_once()
        # Verify the config URLs were passed
        assert mock_yolo26.call_args[0][0] == "http://custom-yolo26:9000"
        assert mock_nemotron.call_args[0][0] == "http://custom-nemotron:9001"


# =============================================================================
# Circuit Breaker Tests
# =============================================================================


class TestCircuitBreaker:
    """Tests for the CircuitBreaker class."""

    def test_circuit_breaker_starts_closed(self) -> None:
        """Test that circuit starts in closed state."""
        cb = system_routes.CircuitBreaker()
        assert cb.is_open("service1") is False
        assert cb.get_state("service1") == "closed"

    def test_circuit_breaker_records_failures(self) -> None:
        """Test that circuit breaker tracks failure count."""
        cb = system_routes.CircuitBreaker(failure_threshold=3)

        cb.record_failure("service1", "error 1")
        assert cb.is_open("service1") is False  # Not yet at threshold

        cb.record_failure("service1", "error 2")
        assert cb.is_open("service1") is False  # Still not at threshold

        cb.record_failure("service1", "error 3")
        assert cb.is_open("service1") is True  # Now open after 3 failures

    def test_circuit_breaker_opens_after_threshold(self) -> None:
        """Test that circuit opens after failure threshold is reached."""
        cb = system_routes.CircuitBreaker(failure_threshold=2)

        cb.record_failure("yolo26", "Connection refused")
        cb.record_failure("yolo26", "Connection refused")

        assert cb.is_open("yolo26") is True
        assert cb.get_state("yolo26") == "open"

    def test_circuit_breaker_caches_last_error(self) -> None:
        """Test that circuit breaker caches the last error message."""
        cb = system_routes.CircuitBreaker(failure_threshold=2)

        cb.record_failure("service1", "first error")
        cb.record_failure("service1", "second error")

        assert cb.get_cached_error("service1") == "second error"

    def test_circuit_breaker_success_resets_failures(self) -> None:
        """Test that recording success resets the failure count."""
        cb = system_routes.CircuitBreaker(failure_threshold=3)

        cb.record_failure("service1", "error 1")
        cb.record_failure("service1", "error 2")
        cb.record_success("service1")  # Reset

        cb.record_failure("service1", "error 3")
        assert cb.is_open("service1") is False  # Only 1 failure after reset

    def test_circuit_breaker_success_clears_cached_error(self) -> None:
        """Test that recording success clears the cached error."""
        cb = system_routes.CircuitBreaker(failure_threshold=2)

        cb.record_failure("service1", "some error")
        assert cb.get_cached_error("service1") == "some error"

        cb.record_success("service1")
        assert cb.get_cached_error("service1") is None

    def test_circuit_breaker_isolates_services(self) -> None:
        """Test that circuit breaker tracks services independently."""
        cb = system_routes.CircuitBreaker(failure_threshold=2)

        cb.record_failure("yolo26", "error")
        cb.record_failure("yolo26", "error")
        cb.record_failure("nemotron", "error")

        assert cb.is_open("yolo26") is True
        assert cb.is_open("nemotron") is False  # Only 1 failure

    def test_circuit_breaker_get_cached_error_returns_none_for_unknown(self) -> None:
        """Test that get_cached_error returns None for unknown service."""
        cb = system_routes.CircuitBreaker()
        assert cb.get_cached_error("unknown_service") is None


@pytest.mark.asyncio
async def test_check_yolo26_health_with_circuit_breaker_skips_when_open() -> None:
    """Test that circuit breaker skips health check when circuit is open."""
    # Reset the global circuit breaker state
    system_routes._health_circuit_breaker = system_routes.CircuitBreaker(failure_threshold=2)

    # Open the circuit by recording failures
    system_routes._health_circuit_breaker.record_failure("yolo26", "Connection refused")
    system_routes._health_circuit_breaker.record_failure("yolo26", "Connection refused")

    # Health check should return cached error without making HTTP call
    is_healthy, error = await system_routes._check_yolo26_health_with_circuit_breaker(
        "http://localhost:8090", 3.0
    )

    assert is_healthy is False
    assert error == "Connection refused"


@pytest.mark.asyncio
async def test_check_yolo26_health_with_circuit_breaker_makes_call_when_closed() -> None:
    """Test that circuit breaker performs health check when circuit is closed."""
    # Reset the global circuit breaker state
    system_routes._health_circuit_breaker = system_routes.CircuitBreaker(failure_threshold=3)

    with patch.object(
        system_routes, "_check_yolo26_health", return_value=(True, None)
    ) as mock_check:
        is_healthy, error = await system_routes._check_yolo26_health_with_circuit_breaker(
            "http://localhost:8090", 3.0
        )

        assert is_healthy is True
        assert error is None
        mock_check.assert_called_once()


@pytest.mark.asyncio
async def test_check_nemotron_health_with_circuit_breaker_skips_when_open() -> None:
    """Test that circuit breaker skips Nemotron health check when circuit is open."""
    # Reset the global circuit breaker state
    system_routes._health_circuit_breaker = system_routes.CircuitBreaker(failure_threshold=2)

    # Open the circuit
    system_routes._health_circuit_breaker.record_failure("nemotron", "Service timeout")
    system_routes._health_circuit_breaker.record_failure("nemotron", "Service timeout")

    # Health check should return cached error without making HTTP call
    is_healthy, error = await system_routes._check_nemotron_health_with_circuit_breaker(
        "http://localhost:8091", 3.0
    )

    assert is_healthy is False
    assert error == "Service timeout"


@pytest.mark.asyncio
async def test_circuit_breaker_records_failure_on_health_check_error() -> None:
    """Test that circuit breaker records failure when health check fails."""
    # Reset the global circuit breaker state
    system_routes._health_circuit_breaker = system_routes.CircuitBreaker(failure_threshold=3)

    with patch.object(
        system_routes, "_check_yolo26_health", return_value=(False, "Connection refused")
    ):
        await system_routes._check_yolo26_health_with_circuit_breaker("http://localhost:8090", 3.0)
        await system_routes._check_yolo26_health_with_circuit_breaker("http://localhost:8090", 3.0)
        await system_routes._check_yolo26_health_with_circuit_breaker("http://localhost:8090", 3.0)

    # Circuit should now be open after 3 failures
    assert system_routes._health_circuit_breaker.is_open("yolo26") is True


@pytest.mark.asyncio
async def test_circuit_breaker_records_success_on_health_check_success() -> None:
    """Test that circuit breaker records success when health check succeeds."""
    # Reset with 1 failure already recorded
    system_routes._health_circuit_breaker = system_routes.CircuitBreaker(failure_threshold=3)
    system_routes._health_circuit_breaker.record_failure("yolo26", "Previous error")

    with patch.object(system_routes, "_check_yolo26_health", return_value=(True, None)):
        await system_routes._check_yolo26_health_with_circuit_breaker("http://localhost:8090", 3.0)

    # Failure count should be reset to 0
    assert system_routes._health_circuit_breaker._failures.get("yolo26", 0) == 0


# =============================================================================
# API Key Authentication Tests
# =============================================================================


@pytest.mark.asyncio
async def test_verify_api_key_skips_when_disabled() -> None:
    """Test that API key verification is skipped when api_key_enabled is False."""
    mock_settings = MagicMock()
    mock_settings.api_key_enabled = False

    with patch.object(system_routes, "get_settings", return_value=mock_settings):
        # Should not raise any exception
        await system_routes.verify_api_key(x_api_key=None)


@pytest.mark.asyncio
async def test_verify_api_key_returns_401_when_missing() -> None:
    """Test that API key verification returns 401 when key is missing but required."""
    mock_settings = MagicMock()
    mock_settings.api_key_enabled = True

    with (
        patch.object(system_routes, "get_settings", return_value=mock_settings),
        pytest.raises(HTTPException) as exc_info,
    ):
        await system_routes.verify_api_key(x_api_key=None)

    assert exc_info.value.status_code == 401
    assert "API key required" in exc_info.value.detail


@pytest.mark.asyncio
async def test_verify_api_key_returns_401_for_invalid_key() -> None:
    """Test that API key verification returns 401 for invalid key."""
    mock_settings = MagicMock()
    mock_settings.api_key_enabled = True
    mock_settings.api_keys = ["valid-api-key-123"]

    with (
        patch.object(system_routes, "get_settings", return_value=mock_settings),
        pytest.raises(HTTPException) as exc_info,
    ):
        await system_routes.verify_api_key(x_api_key="invalid-key")  # pragma: allowlist secret

    assert exc_info.value.status_code == 401
    assert "Invalid API key" in exc_info.value.detail


@pytest.mark.asyncio
async def test_verify_api_key_accepts_valid_key() -> None:
    """Test that API key verification accepts valid key."""
    mock_settings = MagicMock()
    mock_settings.api_key_enabled = True
    mock_settings.api_keys = ["valid-api-key-123", "another-valid-key"]

    with patch.object(system_routes, "get_settings", return_value=mock_settings):
        # Should not raise any exception
        await system_routes.verify_api_key(
            x_api_key="valid-api-key-123"  # pragma: allowlist secret
        )


@pytest.mark.asyncio
async def test_verify_api_key_accepts_any_valid_key_from_list() -> None:
    """Test that API key verification accepts any valid key from the list."""
    mock_settings = MagicMock()
    mock_settings.api_key_enabled = True
    mock_settings.api_keys = ["key-one", "key-two", "key-three"]

    with patch.object(system_routes, "get_settings", return_value=mock_settings):
        # Should accept any key from the list
        await system_routes.verify_api_key(x_api_key="key-one")  # pragma: allowlist secret
        await system_routes.verify_api_key(x_api_key="key-two")  # pragma: allowlist secret
        await system_routes.verify_api_key(x_api_key="key-three")  # pragma: allowlist secret


# =============================================================================
# Cleanup Endpoint Authentication Tests
# =============================================================================


@pytest.mark.asyncio
async def test_cleanup_endpoint_requires_api_key_when_enabled() -> None:
    """Test that cleanup endpoint requires API key when authentication is enabled.

    This test verifies that the POST /cleanup endpoint has the verify_api_key
    dependency applied, matching the behavior of PATCH /config.
    """
    # Verify the dependency is in the endpoint's dependencies
    # by checking the route's dependencies list
    cleanup_route = None
    for route in system_routes.router.routes:
        # Routes have the full path including prefix when accessed from router.routes
        if hasattr(route, "path") and route.path == "/api/system/cleanup":
            cleanup_route = route
            break

    assert cleanup_route is not None, "Cleanup route not found"
    assert cleanup_route.dependencies is not None, "Cleanup route has no dependencies"
    assert len(cleanup_route.dependencies) > 0, "Cleanup route has empty dependencies"

    # Check that verify_api_key is in the dependencies
    dependency_names = []
    for dep in cleanup_route.dependencies:
        if hasattr(dep, "dependency"):
            dep_name = getattr(dep.dependency, "__name__", str(dep.dependency))
            dependency_names.append(dep_name)

    assert "verify_api_key" in dependency_names, (
        f"verify_api_key dependency not found in cleanup route. "
        f"Found dependencies: {dependency_names}"
    )


@pytest.mark.asyncio
async def test_cleanup_endpoint_has_same_auth_as_patch_config() -> None:
    """Test that cleanup endpoint uses the same auth pattern as patch_config.

    Both endpoints should use the verify_api_key dependency for authentication.
    """
    cleanup_route = None
    config_route = None

    for route in system_routes.router.routes:
        if hasattr(route, "path"):
            path = route.path
            # Routes have full path with prefix
            if (
                path == "/api/system/cleanup"
                and hasattr(route, "methods")
                and "POST" in route.methods
            ):
                cleanup_route = route
            if (
                path == "/api/system/config"
                and hasattr(route, "methods")
                and "PATCH" in route.methods
            ):
                config_route = route

    assert cleanup_route is not None, "Cleanup route not found"
    assert config_route is not None, "Config PATCH route not found"

    # Both should have dependencies
    assert cleanup_route.dependencies is not None
    assert config_route.dependencies is not None

    # Extract dependency function names
    def get_dep_names(route):
        names = []
        for dep in route.dependencies:
            if hasattr(dep, "dependency"):
                dep_name = getattr(dep.dependency, "__name__", str(dep.dependency))
                names.append(dep_name)
        return names

    cleanup_deps = get_dep_names(cleanup_route)
    config_deps = get_dep_names(config_route)

    # Both should have verify_api_key
    assert "verify_api_key" in cleanup_deps, "verify_api_key not in cleanup dependencies"
    assert "verify_api_key" in config_deps, "verify_api_key not in config dependencies"


# =============================================================================
# Cleanup Endpoint Dry Run Tests
# =============================================================================


@pytest.mark.asyncio
async def test_trigger_cleanup_dry_run_returns_stats_without_deleting() -> None:
    """Test trigger_cleanup with dry_run=True returns stats without deleting."""
    mock_stats = MagicMock()
    mock_stats.events_deleted = 15
    mock_stats.detections_deleted = 75
    mock_stats.gpu_stats_deleted = 200
    mock_stats.logs_deleted = 50
    mock_stats.thumbnails_deleted = 75
    mock_stats.images_deleted = 0
    mock_stats.space_reclaimed = 2048000

    mock_settings = MagicMock()
    mock_settings.retention_days = 30

    mock_cleanup_service = MagicMock()
    mock_cleanup_service.dry_run_cleanup = AsyncMock(return_value=mock_stats)

    with (
        patch.object(system_routes, "get_settings", return_value=mock_settings),
        patch(
            "backend.services.cleanup_service.CleanupService",
            return_value=mock_cleanup_service,
        ),
    ):
        response = await system_routes.trigger_cleanup(dry_run=True)

    assert isinstance(response, CleanupResponse)
    assert response.events_deleted == 15
    assert response.detections_deleted == 75
    assert response.gpu_stats_deleted == 200
    assert response.logs_deleted == 50
    assert response.thumbnails_deleted == 75
    assert response.images_deleted == 0
    assert response.space_reclaimed == 2048000
    assert response.retention_days == 30
    assert response.dry_run is True
    assert response.timestamp is not None

    # Verify dry_run_cleanup was called, NOT run_cleanup
    mock_cleanup_service.dry_run_cleanup.assert_called_once()
    mock_cleanup_service.run_cleanup.assert_not_called()


@pytest.mark.asyncio
async def test_trigger_cleanup_dry_run_false_performs_actual_deletion() -> None:
    """Test trigger_cleanup with dry_run=False performs actual deletion."""
    mock_stats = MagicMock()
    mock_stats.events_deleted = 10
    mock_stats.detections_deleted = 50
    mock_stats.gpu_stats_deleted = 100
    mock_stats.logs_deleted = 25
    mock_stats.thumbnails_deleted = 50
    mock_stats.images_deleted = 0
    mock_stats.space_reclaimed = 1024000

    mock_settings = MagicMock()
    mock_settings.retention_days = 30

    mock_cleanup_service = MagicMock()
    mock_cleanup_service.run_cleanup = AsyncMock(return_value=mock_stats)

    with (
        patch.object(system_routes, "get_settings", return_value=mock_settings),
        patch(
            "backend.services.cleanup_service.CleanupService",
            return_value=mock_cleanup_service,
        ),
    ):
        response = await system_routes.trigger_cleanup(dry_run=False)

    assert isinstance(response, CleanupResponse)
    assert response.dry_run is False

    # Verify run_cleanup was called, NOT dry_run_cleanup
    mock_cleanup_service.run_cleanup.assert_called_once()
    mock_cleanup_service.dry_run_cleanup.assert_not_called()


@pytest.mark.asyncio
async def test_trigger_cleanup_default_dry_run_is_false() -> None:
    """Test trigger_cleanup defaults dry_run to False."""
    mock_stats = MagicMock()
    mock_stats.events_deleted = 5
    mock_stats.detections_deleted = 20
    mock_stats.gpu_stats_deleted = 50
    mock_stats.logs_deleted = 10
    mock_stats.thumbnails_deleted = 20
    mock_stats.images_deleted = 0
    mock_stats.space_reclaimed = 512000

    mock_settings = MagicMock()
    mock_settings.retention_days = 30

    mock_cleanup_service = MagicMock()
    mock_cleanup_service.run_cleanup = AsyncMock(return_value=mock_stats)

    with (
        patch.object(system_routes, "get_settings", return_value=mock_settings),
        patch(
            "backend.services.cleanup_service.CleanupService",
            return_value=mock_cleanup_service,
        ),
    ):
        # Call without specifying dry_run
        response = await system_routes.trigger_cleanup()

    assert response.dry_run is False
    # Verify run_cleanup was called (actual deletion)
    mock_cleanup_service.run_cleanup.assert_called_once()


@pytest.mark.asyncio
async def test_trigger_cleanup_dry_run_exception_propagates() -> None:
    """Test trigger_cleanup dry_run propagates exception from CleanupService."""
    mock_settings = MagicMock()
    mock_settings.retention_days = 30

    mock_cleanup_service = MagicMock()
    mock_cleanup_service.dry_run_cleanup = AsyncMock(
        side_effect=RuntimeError("Database query failed")
    )

    with (
        patch.object(system_routes, "get_settings", return_value=mock_settings),
        patch(
            "backend.services.cleanup_service.CleanupService",
            return_value=mock_cleanup_service,
        ),
        pytest.raises(RuntimeError, match="Database query failed"),
    ):
        await system_routes.trigger_cleanup(dry_run=True)


@pytest.mark.asyncio
async def test_trigger_cleanup_dry_run_logs_operation() -> None:
    """Test trigger_cleanup dry_run logs the operation."""
    mock_stats = MagicMock()
    mock_stats.events_deleted = 10
    mock_stats.detections_deleted = 50
    mock_stats.gpu_stats_deleted = 100
    mock_stats.logs_deleted = 25
    mock_stats.thumbnails_deleted = 50
    mock_stats.images_deleted = 0
    mock_stats.space_reclaimed = 1024000

    mock_settings = MagicMock()
    mock_settings.retention_days = 30

    mock_cleanup_service = MagicMock()
    mock_cleanup_service.dry_run_cleanup = AsyncMock(return_value=mock_stats)

    with (
        patch.object(system_routes, "get_settings", return_value=mock_settings),
        patch(
            "backend.services.cleanup_service.CleanupService",
            return_value=mock_cleanup_service,
        ),
        patch.object(system_routes.logger, "info") as mock_logger,
    ):
        await system_routes.trigger_cleanup(dry_run=True)

    # Verify logging calls
    log_messages = [call[0][0] for call in mock_logger.call_args_list]
    assert any("dry run triggered" in msg for msg in log_messages)
    assert any("dry run completed" in msg for msg in log_messages)


@pytest.mark.asyncio
async def test_trigger_cleanup_dry_run_uses_retention_from_settings() -> None:
    """Test trigger_cleanup dry_run uses retention_days from settings."""
    mock_stats = MagicMock()
    mock_stats.events_deleted = 0
    mock_stats.detections_deleted = 0
    mock_stats.gpu_stats_deleted = 0
    mock_stats.logs_deleted = 0
    mock_stats.thumbnails_deleted = 0
    mock_stats.images_deleted = 0
    mock_stats.space_reclaimed = 0

    mock_settings = MagicMock()
    mock_settings.retention_days = 14  # Custom retention

    mock_cleanup_service = MagicMock()
    mock_cleanup_service.dry_run_cleanup = AsyncMock(return_value=mock_stats)

    with (
        patch.object(system_routes, "get_settings", return_value=mock_settings),
        patch(
            "backend.services.cleanup_service.CleanupService",
            return_value=mock_cleanup_service,
        ) as mock_cleanup_class,
    ):
        response = await system_routes.trigger_cleanup(dry_run=True)

    # Verify CleanupService was instantiated with correct retention_days
    mock_cleanup_class.assert_called_once_with(
        retention_days=14,
        thumbnail_dir="backend/data/thumbnails",
        delete_images=False,
    )
    assert response.retention_days == 14
    assert response.dry_run is True


@pytest.mark.asyncio
async def test_trigger_cleanup_dry_run_zero_counts() -> None:
    """Test trigger_cleanup dry_run when nothing would be deleted."""
    mock_stats = MagicMock()
    mock_stats.events_deleted = 0
    mock_stats.detections_deleted = 0
    mock_stats.gpu_stats_deleted = 0
    mock_stats.logs_deleted = 0
    mock_stats.thumbnails_deleted = 0
    mock_stats.images_deleted = 0
    mock_stats.space_reclaimed = 0

    mock_settings = MagicMock()
    mock_settings.retention_days = 30

    mock_cleanup_service = MagicMock()
    mock_cleanup_service.dry_run_cleanup = AsyncMock(return_value=mock_stats)

    with (
        patch.object(system_routes, "get_settings", return_value=mock_settings),
        patch(
            "backend.services.cleanup_service.CleanupService",
            return_value=mock_cleanup_service,
        ),
    ):
        response = await system_routes.trigger_cleanup(dry_run=True)

    assert isinstance(response, CleanupResponse)
    assert response.events_deleted == 0
    assert response.detections_deleted == 0
    assert response.gpu_stats_deleted == 0
    assert response.logs_deleted == 0
    assert response.thumbnails_deleted == 0
    assert response.images_deleted == 0
    assert response.space_reclaimed == 0
    assert response.dry_run is True


# =============================================================================
# Circuit Breaker Endpoint Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_circuit_breakers_empty_registry() -> None:
    """Test get_circuit_breakers when no circuit breakers are registered."""
    mock_registry = MagicMock()
    mock_registry.get_all_status.return_value = {}

    with patch("backend.services.circuit_breaker._get_registry", return_value=mock_registry):
        response = await system_routes.get_circuit_breakers()

    assert response.total_count == 0
    assert response.open_count == 0
    assert len(response.circuit_breakers) == 0
    assert response.timestamp is not None


@pytest.mark.asyncio
async def test_get_circuit_breakers_with_closed_breakers() -> None:
    """Test get_circuit_breakers with circuit breakers in closed state."""
    mock_registry = MagicMock()
    mock_registry.get_all_status.return_value = {
        "yolo26": {
            "state": "closed",
            "failure_count": 0,
            "success_count": 0,
            "total_calls": 100,
            "rejected_calls": 0,
            "last_failure_time": None,
            "opened_at": None,
            "config": {
                "failure_threshold": 5,
                "recovery_timeout": 30.0,
                "half_open_max_calls": 3,
                "success_threshold": 2,
            },
        },
        "nemotron": {
            "state": "closed",
            "failure_count": 1,
            "success_count": 0,
            "total_calls": 50,
            "rejected_calls": 0,
            "last_failure_time": 12345.0,
            "opened_at": None,
            "config": {
                "failure_threshold": 5,
                "recovery_timeout": 30.0,
                "half_open_max_calls": 3,
                "success_threshold": 2,
            },
        },
    }

    with patch("backend.services.circuit_breaker._get_registry", return_value=mock_registry):
        response = await system_routes.get_circuit_breakers()

    assert response.total_count == 2
    assert response.open_count == 0
    assert "yolo26" in response.circuit_breakers
    assert "nemotron" in response.circuit_breakers
    assert response.circuit_breakers["yolo26"].state.value == "closed"
    assert response.circuit_breakers["nemotron"].failure_count == 1


@pytest.mark.asyncio
async def test_get_circuit_breakers_with_open_breaker() -> None:
    """Test get_circuit_breakers when a circuit breaker is open."""
    mock_registry = MagicMock()
    mock_registry.get_all_status.return_value = {
        "yolo26": {
            "state": "open",
            "failure_count": 5,
            "success_count": 0,
            "total_calls": 100,
            "rejected_calls": 25,
            "last_failure_time": 12345.0,
            "opened_at": 12340.0,
            "config": {
                "failure_threshold": 5,
                "recovery_timeout": 30.0,
                "half_open_max_calls": 3,
                "success_threshold": 2,
            },
        },
    }

    with patch("backend.services.circuit_breaker._get_registry", return_value=mock_registry):
        response = await system_routes.get_circuit_breakers()

    assert response.total_count == 1
    assert response.open_count == 1
    assert response.circuit_breakers["yolo26"].state.value == "open"
    assert response.circuit_breakers["yolo26"].rejected_calls == 25


@pytest.mark.asyncio
async def test_get_circuit_breakers_with_half_open_breaker() -> None:
    """Test get_circuit_breakers when a circuit breaker is in half-open state."""
    mock_registry = MagicMock()
    mock_registry.get_all_status.return_value = {
        "yolo26": {
            "state": "half_open",
            "failure_count": 0,
            "success_count": 1,
            "total_calls": 101,
            "rejected_calls": 25,
            "last_failure_time": 12345.0,
            "opened_at": 12340.0,
            "config": {
                "failure_threshold": 5,
                "recovery_timeout": 30.0,
                "half_open_max_calls": 3,
                "success_threshold": 2,
            },
        },
    }

    with patch("backend.services.circuit_breaker._get_registry", return_value=mock_registry):
        response = await system_routes.get_circuit_breakers()

    assert response.total_count == 1
    assert response.open_count == 0  # half_open is not counted as open
    assert response.circuit_breakers["yolo26"].state.value == "half_open"
    assert response.circuit_breakers["yolo26"].success_count == 1


@pytest.mark.asyncio
async def test_reset_circuit_breaker_success() -> None:
    """Test resetting a circuit breaker successfully."""
    mock_breaker = MagicMock()
    mock_breaker.state.value = "open"

    mock_registry = MagicMock()
    mock_registry.get.return_value = mock_breaker
    mock_registry.list_names.return_value = ["yolo26", "nemotron"]

    # After reset, state should be closed
    def reset_side_effect():
        mock_breaker.state.value = "closed"

    mock_breaker.reset.side_effect = reset_side_effect

    with patch("backend.services.circuit_breaker._get_registry", return_value=mock_registry):
        response = await system_routes.reset_circuit_breaker("yolo26")

    assert response.name == "yolo26"
    assert response.previous_state.value == "open"
    assert response.new_state.value == "closed"
    assert "reset successfully" in response.message
    mock_breaker.reset.assert_called_once()


@pytest.mark.asyncio
async def test_reset_circuit_breaker_not_found() -> None:
    """Test resetting a circuit breaker that doesn't exist."""
    mock_registry = MagicMock()
    mock_registry.list_names.return_value = ["yolo26", "nemotron"]

    with (
        patch("backend.services.circuit_breaker._get_registry", return_value=mock_registry),
        pytest.raises(HTTPException) as exc_info,
    ):
        await system_routes.reset_circuit_breaker("nonexistent")

    assert exc_info.value.status_code == 404
    assert "not found" in str(exc_info.value.detail)
    assert "Valid names:" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_reset_circuit_breaker_empty_name() -> None:
    """Test resetting a circuit breaker with empty name returns 400."""
    with pytest.raises(HTTPException) as exc_info:
        await system_routes.reset_circuit_breaker("")

    assert exc_info.value.status_code == 400
    assert "must be 1-64 characters" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_reset_circuit_breaker_name_too_long() -> None:
    """Test resetting a circuit breaker with name longer than 64 characters returns 400."""
    long_name = "a" * 65

    with pytest.raises(HTTPException) as exc_info:
        await system_routes.reset_circuit_breaker(long_name)

    assert exc_info.value.status_code == 400
    assert "must be 1-64 characters" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_reset_circuit_breaker_invalid_characters() -> None:
    """Test resetting a circuit breaker with invalid characters returns 400."""
    invalid_names = [
        "test@name",
        "test/name",
        "test name",
        "test.name",
        "test<script>",
        "../etc/passwd",
    ]

    for name in invalid_names:
        with pytest.raises(HTTPException) as exc_info:
            await system_routes.reset_circuit_breaker(name)

        assert exc_info.value.status_code == 400
        assert "alphanumeric characters, underscores, or hyphens" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_reset_circuit_breaker_valid_name_formats() -> None:
    """Test that valid name formats are accepted."""
    mock_breaker = MagicMock()
    mock_breaker.state.value = "closed"

    mock_registry = MagicMock()
    mock_registry.get.return_value = mock_breaker

    valid_names = [
        "yolo26",
        "nemotron",
        "ai_detector",
        "service-1",
        "test_service_name",
        "Service123",
        "TEST-SERVICE-01",
    ]

    for name in valid_names:
        mock_registry.list_names.return_value = [name]
        mock_breaker.reset.reset_mock()

        with patch("backend.services.circuit_breaker._get_registry", return_value=mock_registry):
            response = await system_routes.reset_circuit_breaker(name)

        assert response.name == name
        mock_breaker.reset.assert_called_once()


@pytest.mark.asyncio
async def test_reset_circuit_breaker_no_registered_breakers() -> None:
    """Test resetting when no circuit breakers are registered."""
    mock_registry = MagicMock()
    mock_registry.list_names.return_value = []

    with (
        patch("backend.services.circuit_breaker._get_registry", return_value=mock_registry),
        pytest.raises(HTTPException) as exc_info,
    ):
        await system_routes.reset_circuit_breaker("yolo26")

    assert exc_info.value.status_code == 404
    assert "No circuit breakers are currently registered" in str(exc_info.value.detail)


# =============================================================================
# Cleanup Status Endpoint Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_cleanup_status_with_running_service() -> None:
    """Test get_cleanup_status when cleanup service is running."""
    original_cleanup_service = system_routes._cleanup_service

    try:
        mock_cleanup_service = MagicMock()
        mock_cleanup_service.get_cleanup_stats.return_value = {
            "running": True,
            "retention_days": 30,
            "cleanup_time": "03:00",
            "delete_images": False,
            "next_cleanup": "2025-12-31T03:00:00Z",
        }
        system_routes._cleanup_service = mock_cleanup_service

        response = await system_routes.get_cleanup_status()

        assert response.running is True
        assert response.retention_days == 30
        assert response.cleanup_time == "03:00"
        assert response.delete_images is False
        assert response.next_cleanup == "2025-12-31T03:00:00Z"
        assert response.timestamp is not None

    finally:
        system_routes._cleanup_service = original_cleanup_service


@pytest.mark.asyncio
async def test_get_cleanup_status_with_stopped_service() -> None:
    """Test get_cleanup_status when cleanup service is stopped."""
    original_cleanup_service = system_routes._cleanup_service

    try:
        mock_cleanup_service = MagicMock()
        mock_cleanup_service.get_cleanup_stats.return_value = {
            "running": False,
            "retention_days": 14,
            "cleanup_time": "02:00",
            "delete_images": True,
            "next_cleanup": None,
        }
        system_routes._cleanup_service = mock_cleanup_service

        response = await system_routes.get_cleanup_status()

        assert response.running is False
        assert response.retention_days == 14
        assert response.cleanup_time == "02:00"
        assert response.delete_images is True
        assert response.next_cleanup is None

    finally:
        system_routes._cleanup_service = original_cleanup_service


@pytest.mark.asyncio
async def test_get_cleanup_status_without_service() -> None:
    """Test get_cleanup_status when cleanup service is not registered."""
    original_cleanup_service = system_routes._cleanup_service

    try:
        system_routes._cleanup_service = None

        mock_settings = MagicMock()
        mock_settings.retention_days = 30

        with patch.object(system_routes, "get_settings", return_value=mock_settings):
            response = await system_routes.get_cleanup_status()

        assert response.running is False
        assert response.retention_days == 30
        assert response.cleanup_time == "03:00"
        assert response.delete_images is False
        assert response.next_cleanup is None

    finally:
        system_routes._cleanup_service = original_cleanup_service


# =============================================================================
# Bounded Health Check Concurrency Tests
# =============================================================================


@pytest.mark.asyncio
async def test_bounded_health_check_respects_semaphore_limit() -> None:
    """Test that _bounded_health_check uses the semaphore to limit concurrency."""

    # Track concurrent executions
    max_concurrent = 0
    current_concurrent = 0
    lock = asyncio.Lock()

    async def slow_check(*args):
        nonlocal max_concurrent, current_concurrent
        async with lock:
            current_concurrent += 1
            max_concurrent = max(max_concurrent, current_concurrent)
        await asyncio.sleep(0.1)
        async with lock:
            current_concurrent -= 1
        return (True, None)

    # Run more tasks than the semaphore allows (MAX_CONCURRENT_HEALTH_CHECKS=10)
    tasks = [system_routes._bounded_health_check(slow_check, "arg1", "arg2") for _ in range(15)]

    await asyncio.gather(*tasks)

    # max_concurrent should not exceed the semaphore limit (10)
    assert max_concurrent <= system_routes.MAX_CONCURRENT_HEALTH_CHECKS


@pytest.mark.asyncio
async def test_bounded_health_check_passes_args_correctly() -> None:
    """Test that _bounded_health_check passes arguments to the check function."""
    received_args = []

    async def mock_check(*args):
        received_args.extend(args)
        return (True, None)

    await system_routes._bounded_health_check(mock_check, "url", 3.0)

    assert received_args == ["url", 3.0]


@pytest.mark.asyncio
async def test_bounded_health_check_returns_result() -> None:
    """Test that _bounded_health_check returns the result from the check function."""

    async def mock_check(*args):
        return (False, "Test error message")

    is_healthy, error = await system_routes._bounded_health_check(mock_check)

    assert is_healthy is False
    assert error == "Test error message"


@pytest.mark.asyncio
async def test_check_ai_services_health_uses_bounded_checks() -> None:
    """Test that check_ai_services_health uses bounded health checks."""
    # Verify the semaphore is being used by checking that both checks complete
    mock_settings = MagicMock()
    mock_settings.yolo26_url = "http://localhost:8090"
    mock_settings.nemotron_url = "http://localhost:8091"

    with (
        patch.object(system_routes, "get_settings", return_value=mock_settings),
        patch.object(
            system_routes,
            "_check_yolo26_health_with_circuit_breaker",
            return_value=(True, None),
        ),
        patch.object(
            system_routes,
            "_check_nemotron_health_with_circuit_breaker",
            return_value=(True, None),
        ),
    ):
        status = await system_routes.check_ai_services_health()

    assert status.status == "healthy"
    assert status.message == "AI services operational"


@pytest.mark.asyncio
async def test_max_concurrent_health_checks_constant_exists() -> None:
    """Test that MAX_CONCURRENT_HEALTH_CHECKS constant is defined."""
    assert hasattr(system_routes, "MAX_CONCURRENT_HEALTH_CHECKS")
    assert system_routes.MAX_CONCURRENT_HEALTH_CHECKS == 10


@pytest.mark.asyncio
async def test_health_check_semaphore_exists() -> None:
    """Test that _health_check_semaphore is defined."""
    assert hasattr(system_routes, "_health_check_semaphore")
    assert isinstance(system_routes._health_check_semaphore, asyncio.Semaphore)


# =============================================================================
# Bounded Health Check Timeout Tests
# =============================================================================


@pytest.mark.asyncio
async def test_bounded_health_check_timeout_returns_degraded_status() -> None:
    """Test that _bounded_health_check returns degraded status on timeout."""

    async def slow_check(*args):
        # This check takes longer than the timeout (0.1s)
        await asyncio.sleep(0.5)  # Longer than 0.1s timeout, but not excessive
        return (True, None)

    # Use a very short timeout to trigger timeout behavior
    is_healthy, error = await system_routes._bounded_health_check(slow_check, timeout_seconds=0.1)

    assert is_healthy is False
    assert error == "Health check timed out waiting for available slot"


@pytest.mark.asyncio
async def test_bounded_health_check_timeout_under_high_load() -> None:
    """Test that _bounded_health_check times out when semaphore is exhausted."""

    # Create a semaphore that allows only 1 concurrent check for testing
    original_semaphore = system_routes._health_check_semaphore
    system_routes._health_check_semaphore = asyncio.Semaphore(1)

    try:
        blocking_event = asyncio.Event()

        async def blocking_check(*args):
            # Wait until we tell it to complete
            await blocking_event.wait()
            return (True, None)

        async def fast_check(*args):
            return (True, None)

        # Start a blocking task that holds the semaphore
        blocking_task = asyncio.create_task(
            system_routes._bounded_health_check(blocking_check, timeout_seconds=5.0)
        )

        # Give the blocking task time to acquire the semaphore
        await asyncio.sleep(0.05)

        # Try to run another check with a short timeout - should timeout waiting for semaphore
        is_healthy, error = await system_routes._bounded_health_check(
            fast_check, timeout_seconds=0.1
        )

        # Release the blocking task
        blocking_event.set()
        await blocking_task

        assert is_healthy is False
        assert error == "Health check timed out waiting for available slot"

    finally:
        # Restore original semaphore
        system_routes._health_check_semaphore = original_semaphore


@pytest.mark.asyncio
async def test_bounded_health_check_completes_within_timeout() -> None:
    """Test that _bounded_health_check completes normally when within timeout."""

    async def quick_check(*args):
        await asyncio.sleep(0.01)
        return (True, None)

    is_healthy, error = await system_routes._bounded_health_check(quick_check, timeout_seconds=1.0)

    assert is_healthy is True
    assert error is None


@pytest.mark.asyncio
async def test_bounded_health_check_default_timeout_is_30_seconds() -> None:
    """Test that the default timeout is 30 seconds."""
    import inspect

    sig = inspect.signature(system_routes._bounded_health_check)
    timeout_param = sig.parameters.get("timeout_seconds")

    assert timeout_param is not None
    assert timeout_param.default == 30.0


@pytest.mark.asyncio
async def test_bounded_health_check_timeout_with_custom_value() -> None:
    """Test that custom timeout values are respected."""

    async def check_with_delay(*args):
        await asyncio.sleep(0.5)
        return (True, None)

    # Test with 0.2 second timeout (should timeout)
    is_healthy, error = await system_routes._bounded_health_check(
        check_with_delay, timeout_seconds=0.2
    )

    assert is_healthy is False
    assert "timed out" in error.lower()

    # Test with 1.0 second timeout (should succeed)
    is_healthy, error = await system_routes._bounded_health_check(
        check_with_delay, timeout_seconds=1.0
    )

    assert is_healthy is True
    assert error is None


# =============================================================================
# Pipeline Latency History Tests (NEM-249)
# =============================================================================


@pytest.mark.asyncio
async def test_get_pipeline_latency_history_empty() -> None:
    """Test pipeline latency history returns empty snapshots when no data."""
    from backend.api.schemas.system import PipelineLatencyHistoryResponse
    from backend.core.metrics import PipelineLatencyTracker

    # Create a fresh tracker with no data
    tracker = PipelineLatencyTracker()

    with patch("backend.core.metrics.get_pipeline_latency_tracker", return_value=tracker):
        # Pass explicit values since Query defaults don't resolve when calling directly
        response = await system_routes.get_pipeline_latency_history(since=60, bucket_seconds=60)

    assert isinstance(response, PipelineLatencyHistoryResponse)
    assert response.snapshots == []
    assert response.window_minutes == 60
    assert response.bucket_seconds == 60


@pytest.mark.asyncio
async def test_get_pipeline_latency_history_with_data() -> None:
    """Test pipeline latency history returns data when samples exist."""
    import time

    from backend.api.schemas.system import PipelineLatencyHistoryResponse
    from backend.core.metrics import PipelineLatencyTracker

    tracker = PipelineLatencyTracker()

    # Mock time to control bucket placement
    current_time = time.time()

    with patch.object(tracker, "_time") as mock_time:
        mock_time.time.return_value = current_time

        # Add some samples
        tracker.record_stage_latency("watch_to_detect", 100.0)
        tracker.record_stage_latency("watch_to_detect", 150.0)
        tracker.record_stage_latency("detect_to_batch", 200.0)

        with patch("backend.core.metrics.get_pipeline_latency_tracker", return_value=tracker):
            response = await system_routes.get_pipeline_latency_history(
                since=60,
                bucket_seconds=60,
            )

    assert isinstance(response, PipelineLatencyHistoryResponse)
    assert len(response.snapshots) >= 1
    assert response.window_minutes == 60
    assert response.bucket_seconds == 60


@pytest.mark.asyncio
async def test_get_pipeline_latency_history_custom_params() -> None:
    """Test pipeline latency history with custom parameters."""
    from backend.api.schemas.system import PipelineLatencyHistoryResponse
    from backend.core.metrics import PipelineLatencyTracker

    tracker = PipelineLatencyTracker()

    with patch("backend.core.metrics.get_pipeline_latency_tracker", return_value=tracker):
        response = await system_routes.get_pipeline_latency_history(
            since=30,
            bucket_seconds=120,
        )

    assert isinstance(response, PipelineLatencyHistoryResponse)
    assert response.window_minutes == 30
    assert response.bucket_seconds == 120


@pytest.mark.asyncio
async def test_get_pipeline_latency_history_stage_stats_format() -> None:
    """Test that stage stats have correct format in history."""
    import time

    from backend.api.schemas.system import (
        LatencyHistoryStageStats,
    )
    from backend.core.metrics import PipelineLatencyTracker

    tracker = PipelineLatencyTracker()

    current_time = time.time()

    with patch.object(tracker, "_time") as mock_time:
        mock_time.time.return_value = current_time

        # Add multiple samples to get meaningful stats
        for latency in [100.0, 110.0, 120.0, 130.0, 140.0]:
            tracker.record_stage_latency("watch_to_detect", latency)

        with patch("backend.core.metrics.get_pipeline_latency_tracker", return_value=tracker):
            response = await system_routes.get_pipeline_latency_history(
                since=60,
                bucket_seconds=60,
            )

    assert len(response.snapshots) >= 1
    snapshot = response.snapshots[-1]  # Most recent

    # Check that watch_to_detect has valid stats
    watch_stats = snapshot.stages.get("watch_to_detect")
    assert watch_stats is not None
    assert isinstance(watch_stats, LatencyHistoryStageStats)
    assert watch_stats.avg_ms > 0
    assert watch_stats.p50_ms > 0
    assert watch_stats.p95_ms > 0
    assert watch_stats.p99_ms > 0
    assert watch_stats.sample_count == 5


# =============================================================================
# Pipeline Latency History Parameter Validation Tests (NEM-1063)
# =============================================================================


class TestPipelineLatencyHistoryParameterValidation:
    """Tests for parameter validation bounds on pipeline-latency-history endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create a test client."""
        from backend.main import app

        return TestClient(app)

    # === since parameter validation ===

    def test_since_below_minimum_returns_422(self, client: TestClient) -> None:
        """Test that since=0 returns 422 validation error."""
        response = client.get("/api/system/pipeline-latency/history?since=0")
        assert response.status_code == 422  # Validation error

    def test_since_negative_returns_422(self, client: TestClient) -> None:
        """Test that since=-1 returns 422 validation error."""
        response = client.get("/api/system/pipeline-latency/history?since=-1")
        assert response.status_code == 422  # Validation error

    def test_since_above_maximum_returns_422(self, client: TestClient) -> None:
        """Test that since=1441 (above 1440 max) returns 422 validation error."""
        response = client.get("/api/system/pipeline-latency/history?since=1441")
        assert response.status_code == 422  # Validation error

    def test_since_way_above_maximum_returns_422(self, client: TestClient) -> None:
        """Test that extremely large since value returns 422 validation error."""
        response = client.get("/api/system/pipeline-latency/history?since=999999999")
        assert response.status_code == 422  # Validation error

    def test_since_at_minimum_boundary_returns_200(self, client: TestClient) -> None:
        """Test that since=1 (minimum valid) returns 200."""
        response = client.get("/api/system/pipeline-latency/history?since=1")
        assert response.status_code == 200

    def test_since_at_maximum_boundary_returns_200(self, client: TestClient) -> None:
        """Test that since=1440 (maximum valid) returns 200."""
        response = client.get("/api/system/pipeline-latency/history?since=1440")
        assert response.status_code == 200

    def test_since_default_returns_200(self, client: TestClient) -> None:
        """Test that default since parameter returns 200."""
        response = client.get("/api/system/pipeline-latency/history")
        assert response.status_code == 200

    # === bucket_seconds parameter validation ===

    def test_bucket_seconds_below_minimum_returns_422(self, client: TestClient) -> None:
        """Test that bucket_seconds=9 (below 10 min) returns 422 validation error."""
        response = client.get("/api/system/pipeline-latency/history?bucket_seconds=9")
        assert response.status_code == 422  # Validation error

    def test_bucket_seconds_at_one_returns_422(self, client: TestClient) -> None:
        """Test that bucket_seconds=1 returns 422 validation error."""
        response = client.get("/api/system/pipeline-latency/history?bucket_seconds=1")
        assert response.status_code == 422  # Validation error

    def test_bucket_seconds_negative_returns_422(self, client: TestClient) -> None:
        """Test that bucket_seconds=-1 returns 422 validation error."""
        response = client.get("/api/system/pipeline-latency/history?bucket_seconds=-1")
        assert response.status_code == 422  # Validation error

    def test_bucket_seconds_above_maximum_returns_422(self, client: TestClient) -> None:
        """Test that bucket_seconds=3601 (above 3600 max) returns 422 validation error."""
        response = client.get("/api/system/pipeline-latency/history?bucket_seconds=3601")
        assert response.status_code == 422  # Validation error

    def test_bucket_seconds_way_above_maximum_returns_422(self, client: TestClient) -> None:
        """Test that extremely large bucket_seconds value returns 422 validation error."""
        response = client.get("/api/system/pipeline-latency/history?bucket_seconds=999999999")
        assert response.status_code == 422  # Validation error

    def test_bucket_seconds_at_minimum_boundary_returns_200(self, client: TestClient) -> None:
        """Test that bucket_seconds=10 (minimum valid) returns 200."""
        response = client.get("/api/system/pipeline-latency/history?bucket_seconds=10")
        assert response.status_code == 200

    def test_bucket_seconds_at_maximum_boundary_returns_200(self, client: TestClient) -> None:
        """Test that bucket_seconds=3600 (maximum valid) returns 200."""
        response = client.get("/api/system/pipeline-latency/history?bucket_seconds=3600")
        assert response.status_code == 200

    # === Combined parameter validation ===

    def test_both_parameters_invalid_returns_422(self, client: TestClient) -> None:
        """Test that both invalid since and bucket_seconds returns 422."""
        response = client.get("/api/system/pipeline-latency/history?since=0&bucket_seconds=1")
        assert response.status_code == 422  # Validation error

    def test_both_parameters_valid_returns_200(self, client: TestClient) -> None:
        """Test that valid since and bucket_seconds returns 200."""
        response = client.get("/api/system/pipeline-latency/history?since=60&bucket_seconds=60")
        assert response.status_code == 200

    def test_valid_since_invalid_bucket_seconds_returns_422(self, client: TestClient) -> None:
        """Test that valid since with invalid bucket_seconds returns 422."""
        response = client.get("/api/system/pipeline-latency/history?since=60&bucket_seconds=1")
        assert response.status_code == 422  # Validation error

    def test_invalid_since_valid_bucket_seconds_returns_422(self, client: TestClient) -> None:
        """Test that invalid since with valid bucket_seconds returns 422."""
        response = client.get("/api/system/pipeline-latency/history?since=0&bucket_seconds=60")
        assert response.status_code == 422  # Validation error
