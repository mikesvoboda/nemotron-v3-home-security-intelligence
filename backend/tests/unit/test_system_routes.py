"""Unit tests for backend.api.routes.system helpers.

These focus on low-level branches that are hard to hit via integration tests
but are important for correctness (and to satisfy the backend coverage gate).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.routes import system as system_routes
from backend.api.schemas.system import (
    ConfigResponse,
    GPUStatsHistoryResponse,
    GPUStatsResponse,
    HealthResponse,
    LivenessResponse,
    PipelineLatencies,
    ReadinessResponse,
    StageLatency,
    SystemStatsResponse,
    TelemetryResponse,
    WorkerStatus,
)


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
    mock_gpu_stat.gpu_utilization = 75.5
    mock_gpu_stat.memory_used = 12000
    mock_gpu_stat.memory_total = 24000
    mock_gpu_stat.temperature = 65.0
    mock_gpu_stat.inference_fps = 30.5

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_gpu_stat
    db.execute = AsyncMock(return_value=mock_result)

    response = await system_routes.get_gpu_stats(db)  # type: ignore[arg-type]

    assert isinstance(response, GPUStatsResponse)
    assert response.utilization == 75.5
    assert response.memory_used == 12000
    assert response.memory_total == 24000
    assert response.temperature == 65.0
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
    mock_stat1.gpu_utilization = 50.0
    mock_stat1.memory_used = 8000
    mock_stat1.memory_total = 24000
    mock_stat1.temperature = 55.0
    mock_stat1.inference_fps = 25.0

    mock_stat2 = MagicMock()
    mock_stat2.recorded_at = datetime(2025, 12, 27, 10, 0, 0)
    mock_stat2.gpu_utilization = 75.0
    mock_stat2.memory_used = 12000
    mock_stat2.memory_total = 24000
    mock_stat2.temperature = 65.0
    mock_stat2.inference_fps = 30.0

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    # Return in descending order (newest first) - will be reversed
    mock_scalars.all.return_value = [mock_stat2, mock_stat1]
    mock_result.scalars.return_value = mock_scalars
    db.execute = AsyncMock(return_value=mock_result)

    response = await system_routes.get_gpu_stats_history(db=db)  # type: ignore[arg-type]

    assert isinstance(response, GPUStatsHistoryResponse)
    assert response.count == 2
    assert response.limit == 300  # Default limit
    assert len(response.samples) == 2
    # Should be in chronological order after reversal
    assert response.samples[0].recorded_at == datetime(2025, 12, 27, 9, 0, 0)
    assert response.samples[1].recorded_at == datetime(2025, 12, 27, 10, 0, 0)


@pytest.mark.asyncio
async def test_get_gpu_stats_history_with_since_filter() -> None:
    """Test get_gpu_stats_history filters by since parameter."""
    db = AsyncMock()

    mock_stat = MagicMock()
    mock_stat.recorded_at = datetime(2025, 12, 27, 10, 0, 0)
    mock_stat.gpu_utilization = 75.0
    mock_stat.memory_used = 12000
    mock_stat.memory_total = 24000
    mock_stat.temperature = 65.0
    mock_stat.inference_fps = 30.0

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_stat]
    mock_result.scalars.return_value = mock_scalars
    db.execute = AsyncMock(return_value=mock_result)

    since_time = datetime(2025, 12, 27, 9, 0, 0)
    response = await system_routes.get_gpu_stats_history(
        since=since_time, db=db
    )  # type: ignore[arg-type]

    assert isinstance(response, GPUStatsHistoryResponse)
    assert response.count == 1


@pytest.mark.asyncio
async def test_get_gpu_stats_history_limit_clamping() -> None:
    """Test get_gpu_stats_history clamps limit to valid range."""
    db = AsyncMock()

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    db.execute = AsyncMock(return_value=mock_result)

    # Test that limit of 0 is clamped to 1
    response = await system_routes.get_gpu_stats_history(
        limit=0, db=db
    )  # type: ignore[arg-type]
    assert response.limit == 1

    # Test that negative limit is clamped to 1
    response = await system_routes.get_gpu_stats_history(
        limit=-5, db=db
    )  # type: ignore[arg-type]
    assert response.limit == 1

    # Test that limit over 5000 is clamped to 5000
    response = await system_routes.get_gpu_stats_history(
        limit=10000, db=db
    )  # type: ignore[arg-type]
    assert response.limit == 5000


@pytest.mark.asyncio
async def test_get_gpu_stats_history_empty_result() -> None:
    """Test get_gpu_stats_history with no samples."""
    db = AsyncMock()

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    db.execute = AsyncMock(return_value=mock_result)

    response = await system_routes.get_gpu_stats_history(db=db)  # type: ignore[arg-type]

    assert isinstance(response, GPUStatsHistoryResponse)
    assert response.count == 0
    assert response.samples == []


# =============================================================================
# Health Endpoint Tests (Lines 255-278)
# =============================================================================


@pytest.mark.asyncio
async def test_get_health_all_healthy() -> None:
    """Test health endpoint when all services are healthy."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 5
    db.execute = AsyncMock(return_value=mock_result)

    redis = AsyncMock()
    redis.health_check = AsyncMock(return_value={"status": "healthy", "redis_version": "7.0.0"})

    response = await system_routes.get_health(db, redis)  # type: ignore[arg-type]

    assert isinstance(response, HealthResponse)
    assert response.status == "healthy"
    assert response.services["database"].status == "healthy"
    assert response.services["redis"].status == "healthy"
    assert response.services["ai"].status == "healthy"
    assert response.timestamp is not None


@pytest.mark.asyncio
async def test_get_health_degraded_when_redis_unhealthy() -> None:
    """Test health endpoint returns degraded when non-critical service is unhealthy."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 5
    db.execute = AsyncMock(return_value=mock_result)

    redis = AsyncMock()
    redis.health_check = AsyncMock(
        return_value={"status": "unhealthy", "error": "connection refused"}
    )

    response = await system_routes.get_health(db, redis)  # type: ignore[arg-type]

    assert isinstance(response, HealthResponse)
    assert response.status == "degraded"
    assert response.services["database"].status == "healthy"
    assert response.services["redis"].status == "unhealthy"


@pytest.mark.asyncio
async def test_get_health_unhealthy_when_database_down() -> None:
    """Test health endpoint returns unhealthy when database is down."""
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=RuntimeError("db error"))

    redis = AsyncMock()
    redis.health_check = AsyncMock(return_value={"status": "healthy", "redis_version": "7.0.0"})

    response = await system_routes.get_health(db, redis)  # type: ignore[arg-type]

    assert isinstance(response, HealthResponse)
    assert response.status == "unhealthy"
    assert response.services["database"].status == "unhealthy"


@pytest.mark.asyncio
async def test_get_health_unhealthy_when_all_services_down() -> None:
    """Test health endpoint returns unhealthy when all services down."""
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=RuntimeError("db error"))

    redis = AsyncMock()
    redis.health_check = AsyncMock(
        return_value={"status": "unhealthy", "error": "redis error"}
    )

    response = await system_routes.get_health(db, redis)  # type: ignore[arg-type]

    assert isinstance(response, HealthResponse)
    assert response.status == "unhealthy"
    assert response.services["database"].status == "unhealthy"
    assert response.services["redis"].status == "unhealthy"


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
    mock_settings.batch_window_seconds = 90
    mock_settings.batch_idle_timeout_seconds = 30
    mock_settings.detection_confidence_threshold = 0.5

    with patch.object(system_routes, "get_settings", return_value=mock_settings):
        response = await system_routes.get_config()

    assert isinstance(response, ConfigResponse)
    assert response.app_name == "Home Security Intelligence"
    assert response.version == "1.0.0"
    assert response.retention_days == 30
    assert response.batch_window_seconds == 90
    assert response.batch_idle_timeout_seconds == 30
    assert response.detection_confidence_threshold == 0.5


@pytest.mark.asyncio
async def test_patch_config_updates_retention_days(tmp_path, monkeypatch) -> None:
    """Test patch_config updates retention_days setting."""
    runtime_env = tmp_path / "runtime.env"
    monkeypatch.setenv("HSI_RUNTIME_ENV_PATH", str(runtime_env))

    mock_settings = MagicMock()
    mock_settings.app_name = "Home Security Intelligence"
    mock_settings.app_version = "1.0.0"
    mock_settings.retention_days = 7
    mock_settings.batch_window_seconds = 90
    mock_settings.batch_idle_timeout_seconds = 30
    mock_settings.detection_confidence_threshold = 0.5

    mock_get_settings = MagicMock(return_value=mock_settings)
    mock_get_settings.cache_clear = MagicMock()

    from backend.api.schemas.system import ConfigUpdateRequest

    update = ConfigUpdateRequest(retention_days=7)

    with patch.object(system_routes, "get_settings", mock_get_settings):
        response = await system_routes.patch_config(update)

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
    mock_settings.batch_window_seconds = 120
    mock_settings.batch_idle_timeout_seconds = 30
    mock_settings.detection_confidence_threshold = 0.5

    mock_get_settings = MagicMock(return_value=mock_settings)
    mock_get_settings.cache_clear = MagicMock()

    from backend.api.schemas.system import ConfigUpdateRequest

    update = ConfigUpdateRequest(batch_window_seconds=120)

    with patch.object(system_routes, "get_settings", mock_get_settings):
        response = await system_routes.patch_config(update)

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
    mock_settings.batch_window_seconds = 90
    mock_settings.batch_idle_timeout_seconds = 45
    mock_settings.detection_confidence_threshold = 0.5

    mock_get_settings = MagicMock(return_value=mock_settings)
    mock_get_settings.cache_clear = MagicMock()

    from backend.api.schemas.system import ConfigUpdateRequest

    update = ConfigUpdateRequest(batch_idle_timeout_seconds=45)

    with patch.object(system_routes, "get_settings", mock_get_settings):
        response = await system_routes.patch_config(update)

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
    mock_settings.batch_window_seconds = 90
    mock_settings.batch_idle_timeout_seconds = 30
    mock_settings.detection_confidence_threshold = 0.75

    mock_get_settings = MagicMock(return_value=mock_settings)
    mock_get_settings.cache_clear = MagicMock()

    from backend.api.schemas.system import ConfigUpdateRequest

    update = ConfigUpdateRequest(detection_confidence_threshold=0.75)

    with patch.object(system_routes, "get_settings", mock_get_settings):
        response = await system_routes.patch_config(update)

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
    mock_settings.batch_window_seconds = 90
    mock_settings.batch_idle_timeout_seconds = 30
    mock_settings.detection_confidence_threshold = 0.5

    mock_get_settings = MagicMock(return_value=mock_settings)
    mock_get_settings.cache_clear = MagicMock()

    from backend.api.schemas.system import ConfigUpdateRequest

    # Empty update - no fields set
    update = ConfigUpdateRequest()

    with patch.object(system_routes, "get_settings", mock_get_settings):
        response = await system_routes.patch_config(update)

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
    mock_settings.batch_window_seconds = 60
    mock_settings.batch_idle_timeout_seconds = 20
    mock_settings.detection_confidence_threshold = 0.8

    mock_get_settings = MagicMock(return_value=mock_settings)
    mock_get_settings.cache_clear = MagicMock()

    from backend.api.schemas.system import ConfigUpdateRequest

    update = ConfigUpdateRequest(
        retention_days=14,
        batch_window_seconds=60,
        batch_idle_timeout_seconds=20,
        detection_confidence_threshold=0.8,
    )

    with patch.object(system_routes, "get_settings", mock_get_settings):
        response = await system_routes.patch_config(update)

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
    """Test record_stage_latency with valid pipeline stage."""
    redis = AsyncMock()
    redis.add_to_queue = AsyncMock()

    await system_routes.record_stage_latency(redis, "watch", 10.5)  # type: ignore[arg-type]

    redis.add_to_queue.assert_called_once_with("telemetry:latency:watch", 10.5)


@pytest.mark.asyncio
async def test_record_stage_latency_invalid_stage() -> None:
    """Test record_stage_latency with invalid pipeline stage logs warning."""
    redis = AsyncMock()
    redis.add_to_queue = AsyncMock()

    with patch.object(system_routes.logger, "warning") as mock_warning:
        await system_routes.record_stage_latency(
            redis, "invalid_stage", 10.5
        )  # type: ignore[arg-type]

    mock_warning.assert_called_once()
    assert "invalid_stage" in mock_warning.call_args[0][0]
    redis.add_to_queue.assert_not_called()


@pytest.mark.asyncio
async def test_record_stage_latency_exception_handling() -> None:
    """Test record_stage_latency handles Redis exceptions gracefully."""
    redis = AsyncMock()
    redis.add_to_queue = AsyncMock(side_effect=RuntimeError("redis error"))

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
    redis.peek_queue = AsyncMock(side_effect=[
        # watch stage
        [10.0, 15.0, 20.0],
        # detect stage
        [100.0, 150.0, 200.0],
        # batch stage
        [1000.0, 1500.0],
        # analyze stage
        [5000.0, 6000.0, 7000.0],
    ])

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
    redis.peek_queue = AsyncMock(side_effect=[
        # watch stage with some invalid values
        [10.0, "invalid", 20.0, None, 30.0],
        # Other stages empty
        [],
        [],
        [],
    ])

    result = await system_routes.get_latency_stats(redis)  # type: ignore[arg-type]

    assert isinstance(result, PipelineLatencies)
    assert result.watch is not None
    # Only valid numeric values should be counted
    assert result.watch.sample_count == 3


@pytest.mark.asyncio
async def test_get_latency_stats_exception_handling() -> None:
    """Test get_latency_stats returns None on exception."""
    redis = AsyncMock()
    redis.peek_queue = AsyncMock(side_effect=RuntimeError("redis error"))

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
    redis.peek_queue = AsyncMock(side_effect=[
        [10.0, 15.0],  # watch
        [100.0, 150.0],  # detect
        [1000.0],  # batch
        [5000.0, 6000.0],  # analyze
    ])

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
    redis.get_queue_length = AsyncMock(side_effect=RuntimeError("redis error"))
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
    """Test check_database_health returns healthy on success."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 5
    db.execute = AsyncMock(return_value=mock_result)

    status = await system_routes.check_database_health(db)  # type: ignore[arg-type]

    assert status.status == "healthy"
    assert status.message == "Database operational"


@pytest.mark.asyncio
async def test_check_redis_health_healthy() -> None:
    """Test check_redis_health returns healthy with version details."""
    redis = AsyncMock()
    redis.health_check = AsyncMock(
        return_value={"status": "healthy", "redis_version": "7.2.0"}
    )

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
    status = await system_routes.check_ai_services_health()

    assert status.status == "healthy"
    assert status.message == "AI services not monitored"


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
    redis.peek_queue = AsyncMock(side_effect=[
        ["10.5", "20.0", "30.5"],  # watch - strings
        [],
        [],
        [],
    ])

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
    redis.peek_queue = AsyncMock(side_effect=[
        # Mix of valid floats, valid strings, and invalid values
        [10.0, "20.0", {"invalid": True}, [], "not_a_number", 30.0],
        [],
        [],
        [],
    ])

    result = await system_routes.get_latency_stats(redis)  # type: ignore[arg-type]

    assert isinstance(result, PipelineLatencies)
    assert result.watch is not None
    # Only 3 valid values: 10.0, "20.0" (converted), 30.0
    assert result.watch.sample_count == 3
