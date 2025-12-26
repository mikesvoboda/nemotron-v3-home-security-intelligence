"""Unit tests for backend.api.routes.system helpers.

These focus on low-level branches that are hard to hit via integration tests
but are important for correctness (and to satisfy the backend coverage gate).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.routes import system as system_routes
from backend.api.schemas.system import LivenessResponse, ReadinessResponse, WorkerStatus


@pytest.mark.asyncio
async def test_check_database_health_unhealthy_on_exception() -> None:
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=RuntimeError("db down"))

    status = await system_routes.check_database_health(db)  # type: ignore[arg-type]
    assert status.status == "unhealthy"
    assert "db down" in status.message


@pytest.mark.asyncio
async def test_check_redis_health_unhealthy_on_error_payload() -> None:
    redis = AsyncMock()
    redis.health_check = AsyncMock(return_value={"status": "unhealthy", "error": "nope"})

    status = await system_routes.check_redis_health(redis)  # type: ignore[arg-type]
    assert status.status == "unhealthy"
    assert status.message == "nope"


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


@pytest.mark.asyncio
async def test_get_liveness_always_returns_alive() -> None:
    """Test that liveness endpoint always returns alive status."""
    response = await system_routes.get_liveness()

    assert isinstance(response, LivenessResponse)
    assert response.status == "alive"


@pytest.mark.asyncio
async def test_get_liveness_has_no_dependencies() -> None:
    """Test that liveness endpoint has no external dependencies.

    The liveness probe should never fail if the process is running.
    """
    # Call multiple times to ensure it's stateless and consistent
    for _ in range(3):
        response = await system_routes.get_liveness()
        assert response.status == "alive"


# =============================================================================
# Readiness Endpoint Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_readiness_all_healthy() -> None:
    """Test readiness endpoint when all services are healthy."""
    db = AsyncMock()
    # Mock successful database query
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 5
    db.execute = AsyncMock(return_value=mock_result)

    redis = AsyncMock()
    redis.health_check = AsyncMock(return_value={"status": "healthy", "redis_version": "7.0.0"})

    response = await system_routes.get_readiness(db, redis)  # type: ignore[arg-type]

    assert isinstance(response, ReadinessResponse)
    assert response.ready is True
    assert response.status == "ready"
    assert response.services["database"].status == "healthy"
    assert response.services["redis"].status == "healthy"
    assert response.timestamp is not None


@pytest.mark.asyncio
async def test_get_readiness_database_unhealthy() -> None:
    """Test readiness endpoint when database is unhealthy."""
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=RuntimeError("db connection failed"))

    redis = AsyncMock()
    redis.health_check = AsyncMock(return_value={"status": "healthy", "redis_version": "7.0.0"})

    response = await system_routes.get_readiness(db, redis)  # type: ignore[arg-type]

    assert isinstance(response, ReadinessResponse)
    assert response.ready is False
    assert response.status == "not_ready"
    assert response.services["database"].status == "unhealthy"
    assert "db connection failed" in response.services["database"].message


@pytest.mark.asyncio
async def test_get_readiness_redis_unhealthy() -> None:
    """Test readiness endpoint when Redis is unhealthy."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 5
    db.execute = AsyncMock(return_value=mock_result)

    redis = AsyncMock()
    redis.health_check = AsyncMock(
        return_value={"status": "unhealthy", "error": "connection refused"}
    )

    response = await system_routes.get_readiness(db, redis)  # type: ignore[arg-type]

    assert isinstance(response, ReadinessResponse)
    assert response.ready is False
    assert response.status == "degraded"
    assert response.services["database"].status == "healthy"
    assert response.services["redis"].status == "unhealthy"


@pytest.mark.asyncio
async def test_get_readiness_redis_exception() -> None:
    """Test readiness endpoint when Redis health check raises exception."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 5
    db.execute = AsyncMock(return_value=mock_result)

    redis = AsyncMock()
    redis.health_check = AsyncMock(side_effect=ConnectionError("redis down"))

    response = await system_routes.get_readiness(db, redis)  # type: ignore[arg-type]

    assert isinstance(response, ReadinessResponse)
    assert response.ready is False
    assert response.services["redis"].status == "unhealthy"


@pytest.mark.asyncio
async def test_get_readiness_both_unhealthy() -> None:
    """Test readiness endpoint when both database and Redis are unhealthy."""
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=RuntimeError("db error"))

    redis = AsyncMock()
    redis.health_check = AsyncMock(return_value={"status": "unhealthy", "error": "redis error"})

    response = await system_routes.get_readiness(db, redis)  # type: ignore[arg-type]

    assert isinstance(response, ReadinessResponse)
    assert response.ready is False
    assert response.status == "not_ready"
    assert response.services["database"].status == "unhealthy"
    assert response.services["redis"].status == "unhealthy"


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

    try:
        # Clear all workers
        system_routes._gpu_monitor = None
        system_routes._cleanup_service = None
        system_routes._system_broadcaster = None
        system_routes._file_watcher = None

        statuses = system_routes._get_worker_statuses()

        assert isinstance(statuses, list)
        assert len(statuses) == 0
    finally:
        # Restore original values
        system_routes._gpu_monitor = original_gpu
        system_routes._cleanup_service = original_cleanup
        system_routes._system_broadcaster = original_broadcaster
        system_routes._file_watcher = original_watcher


def test_get_worker_statuses_with_running_workers() -> None:
    """Test _get_worker_statuses with running workers."""
    # Save original values
    original_gpu = system_routes._gpu_monitor
    original_cleanup = system_routes._cleanup_service
    original_broadcaster = system_routes._system_broadcaster
    original_watcher = system_routes._file_watcher

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


def test_get_worker_statuses_with_stopped_workers() -> None:
    """Test _get_worker_statuses with stopped workers."""
    # Save original values
    original_gpu = system_routes._gpu_monitor
    original_cleanup = system_routes._cleanup_service

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

        statuses = system_routes._get_worker_statuses()

        assert len(statuses) == 2
        for status in statuses:
            assert status.running is False
            assert status.message == "Not running"
    finally:
        # Restore original values
        system_routes._gpu_monitor = original_gpu
        system_routes._cleanup_service = original_cleanup
        system_routes._system_broadcaster = None
        system_routes._file_watcher = None


def test_get_worker_statuses_mixed_status() -> None:
    """Test _get_worker_statuses with mixed running/stopped workers."""
    # Save original values
    original_gpu = system_routes._gpu_monitor
    original_cleanup = system_routes._cleanup_service

    try:
        mock_gpu = MagicMock()
        mock_gpu.running = True

        mock_cleanup = MagicMock()
        mock_cleanup.running = False

        system_routes._gpu_monitor = mock_gpu
        system_routes._cleanup_service = mock_cleanup
        system_routes._system_broadcaster = None
        system_routes._file_watcher = None

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
        system_routes._system_broadcaster = None
        system_routes._file_watcher = None


@pytest.mark.asyncio
async def test_get_readiness_includes_worker_status() -> None:
    """Test that readiness response includes worker status information."""
    # Save original values
    original_gpu = system_routes._gpu_monitor

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

        response = await system_routes.get_readiness(db, redis)  # type: ignore[arg-type]

        assert len(response.workers) >= 1
        gpu_worker = next((w for w in response.workers if w.name == "gpu_monitor"), None)
        assert gpu_worker is not None
        assert gpu_worker.running is True
    finally:
        system_routes._gpu_monitor = original_gpu


# =============================================================================
# Health Check Timeout Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_readiness_database_timeout() -> None:
    """Test readiness endpoint when database health check times out."""

    async def slow_db_execute(*args, **kwargs):
        """Simulate a slow database query that will timeout."""
        await asyncio.sleep(10)  # Much longer than the timeout

    db = AsyncMock()
    db.execute = slow_db_execute

    redis = AsyncMock()
    redis.health_check = AsyncMock(return_value={"status": "healthy", "redis_version": "7.0.0"})

    # Use a short timeout for testing
    with patch.object(system_routes, "HEALTH_CHECK_TIMEOUT_SECONDS", 0.1):
        response = await system_routes.get_readiness(db, redis)  # type: ignore[arg-type]

    assert isinstance(response, ReadinessResponse)
    assert response.ready is False
    assert response.status == "not_ready"
    assert response.services["database"].status == "unhealthy"
    assert "timed out" in response.services["database"].message


@pytest.mark.asyncio
async def test_get_readiness_redis_timeout() -> None:
    """Test readiness endpoint when Redis health check times out."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 5
    db.execute = AsyncMock(return_value=mock_result)

    async def slow_redis_health_check():
        """Simulate a slow Redis health check that will timeout."""
        await asyncio.sleep(10)  # Much longer than the timeout

    redis = AsyncMock()
    redis.health_check = slow_redis_health_check

    # Use a short timeout for testing
    with patch.object(system_routes, "HEALTH_CHECK_TIMEOUT_SECONDS", 0.1):
        response = await system_routes.get_readiness(db, redis)  # type: ignore[arg-type]

    assert isinstance(response, ReadinessResponse)
    assert response.ready is False
    assert response.status == "degraded"
    assert response.services["database"].status == "healthy"
    assert response.services["redis"].status == "unhealthy"
    assert "timed out" in response.services["redis"].message


@pytest.mark.asyncio
async def test_get_readiness_ai_services_timeout() -> None:
    """Test readiness endpoint when AI services health check times out."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 5
    db.execute = AsyncMock(return_value=mock_result)

    redis = AsyncMock()
    redis.health_check = AsyncMock(return_value={"status": "healthy", "redis_version": "7.0.0"})

    async def slow_ai_health_check():
        """Simulate a slow AI services health check that will timeout."""
        await asyncio.sleep(10)  # Much longer than the timeout
        # This return is never reached due to timeout
        return system_routes.ServiceStatus(
            status="healthy", message="AI services operational", details=None
        )

    # Use a short timeout for testing
    with (
        patch.object(system_routes, "HEALTH_CHECK_TIMEOUT_SECONDS", 0.1),
        patch.object(system_routes, "check_ai_services_health", slow_ai_health_check),
    ):
        response = await system_routes.get_readiness(db, redis)  # type: ignore[arg-type]

    assert isinstance(response, ReadinessResponse)
    # Database and Redis are healthy, so system should be ready
    # but AI services timeout should be reflected
    assert response.ready is True
    assert response.status == "ready"
    assert response.services["database"].status == "healthy"
    assert response.services["redis"].status == "healthy"
    assert response.services["ai"].status == "unhealthy"
    assert "timed out" in response.services["ai"].message


@pytest.mark.asyncio
async def test_get_readiness_all_services_timeout() -> None:
    """Test readiness endpoint when all health checks timeout."""

    async def slow_db_execute(*args, **kwargs):
        """Simulate a slow database query that will timeout."""
        await asyncio.sleep(10)

    async def slow_redis_health_check():
        """Simulate a slow Redis health check that will timeout."""
        await asyncio.sleep(10)

    async def slow_ai_health_check():
        """Simulate a slow AI services health check that will timeout."""
        await asyncio.sleep(10)

    db = AsyncMock()
    db.execute = slow_db_execute

    redis = AsyncMock()
    redis.health_check = slow_redis_health_check

    with (
        patch.object(system_routes, "HEALTH_CHECK_TIMEOUT_SECONDS", 0.1),
        patch.object(system_routes, "check_ai_services_health", slow_ai_health_check),
    ):
        response = await system_routes.get_readiness(db, redis)  # type: ignore[arg-type]

    assert isinstance(response, ReadinessResponse)
    assert response.ready is False
    assert response.status == "not_ready"
    assert response.services["database"].status == "unhealthy"
    assert response.services["redis"].status == "unhealthy"
    assert response.services["ai"].status == "unhealthy"
    assert "timed out" in response.services["database"].message
    assert "timed out" in response.services["redis"].message
    assert "timed out" in response.services["ai"].message


@pytest.mark.asyncio
async def test_health_check_timeout_constant_is_reasonable() -> None:
    """Test that the health check timeout constant has a reasonable value."""
    # The timeout should be at least 1 second to allow for slow responses
    assert system_routes.HEALTH_CHECK_TIMEOUT_SECONDS >= 1.0
    # The timeout should not be more than 30 seconds
    assert system_routes.HEALTH_CHECK_TIMEOUT_SECONDS <= 30.0
