"""System monitoring and configuration API endpoints."""

import os
import time
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Body, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.system import (
    ConfigResponse,
    ConfigUpdateRequest,
    GPUStatsHistoryResponse,
    GPUStatsResponse,
    HealthResponse,
    ServiceStatus,
    SystemStatsResponse,
)
from backend.core import get_db, get_settings
from backend.core.redis import RedisClient, get_redis
from backend.models import Camera, Detection, Event, GPUStats

router = APIRouter(prefix="/api/system", tags=["system"])

# Track application start time for uptime calculation
_app_start_time = time.time()


async def get_latest_gpu_stats(db: AsyncSession) -> dict[str, float | int | datetime | None] | None:
    """Get the latest GPU statistics from the database.

    Args:
        db: Database session

    Returns:
        Dictionary with GPU stats or None if no data available
    """
    stmt = select(GPUStats).order_by(GPUStats.recorded_at.desc()).limit(1)
    result = await db.execute(stmt)
    gpu_stat = result.scalar_one_or_none()

    if gpu_stat is None:
        return None

    return {
        "recorded_at": gpu_stat.recorded_at,
        "utilization": gpu_stat.gpu_utilization,
        "memory_used": gpu_stat.memory_used,
        "memory_total": gpu_stat.memory_total,
        "temperature": gpu_stat.temperature,
        "inference_fps": gpu_stat.inference_fps,
    }


async def check_database_health(db: AsyncSession) -> ServiceStatus:
    """Check database connectivity and health.

    Args:
        db: Database session

    Returns:
        ServiceStatus with database health information
    """
    try:
        # Execute a simple query to verify database connectivity
        result = await db.execute(select(func.count()).select_from(Camera))
        result.scalar_one()
        return ServiceStatus(
            status="healthy",
            message="Database operational",
            details=None,
        )
    except Exception as e:
        return ServiceStatus(
            status="unhealthy",
            message=f"Database error: {e!s}",
            details=None,
        )


async def check_redis_health(redis: RedisClient) -> ServiceStatus:
    """Check Redis connectivity and health.

    Args:
        redis: Redis client

    Returns:
        ServiceStatus with Redis health information
    """
    try:
        health = await redis.health_check()
        if health.get("status") == "healthy":
            return ServiceStatus(
                status="healthy",
                message="Redis connected",
                details={"redis_version": health.get("redis_version", "unknown")},
            )
        else:
            return ServiceStatus(
                status="unhealthy",
                message=health.get("error", "Redis connection error"),
                details=None,
            )
    except Exception as e:
        return ServiceStatus(
            status="unhealthy",
            message=f"Redis error: {e!s}",
            details=None,
        )


async def check_ai_services_health() -> ServiceStatus:
    """Check AI services health.

    This is a placeholder that can be expanded to check RT-DETR and Nemotron services.

    Returns:
        ServiceStatus with AI services health information
    """
    # For now, return a basic status
    # In the future, this could ping the RT-DETR and Nemotron endpoints
    return ServiceStatus(
        status="healthy",
        message="AI services not monitored",
        details=None,
    )


@router.get("/health", response_model=HealthResponse)
async def get_health(
    db: AsyncSession = Depends(get_db),
    redis: RedisClient = Depends(get_redis),
) -> HealthResponse:
    """Get detailed system health check.

    Checks the health of all system components:
    - Database connectivity
    - Redis connectivity
    - AI services status

    Returns:
        HealthResponse with overall status and individual service statuses
    """
    # Check all services
    db_status = await check_database_health(db)
    redis_status = await check_redis_health(redis)
    ai_status = await check_ai_services_health()

    # Determine overall status
    services = {
        "database": db_status,
        "redis": redis_status,
        "ai": ai_status,
    }

    # Overall status is healthy if all services are healthy
    # Degraded if some services are unhealthy
    # Unhealthy if critical services (database) are down
    unhealthy_count = sum(1 for s in services.values() if s.status == "unhealthy")

    if unhealthy_count == 0:
        overall_status = "healthy"
    elif db_status.status == "unhealthy":
        overall_status = "unhealthy"
    else:
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        services=services,
        timestamp=datetime.now(UTC),
    )


@router.get("/gpu", response_model=GPUStatsResponse)
async def get_gpu_stats(db: AsyncSession = Depends(get_db)) -> GPUStatsResponse:
    """Get current GPU statistics.

    Returns the most recent GPU statistics including:
    - GPU utilization percentage
    - Memory usage (used/total)
    - Temperature
    - Inference FPS

    Returns:
        GPUStatsResponse with GPU statistics (null values if unavailable)
    """
    stats = await get_latest_gpu_stats(db)

    if stats is None:
        # Return all null values if no GPU data available
        return GPUStatsResponse(
            utilization=None,
            memory_used=None,
            memory_total=None,
            temperature=None,
            inference_fps=None,
        )

    return GPUStatsResponse(
        utilization=stats["utilization"],
        memory_used=stats["memory_used"],
        memory_total=stats["memory_total"],
        temperature=stats["temperature"],
        inference_fps=stats["inference_fps"],
    )


@router.get("/gpu/history", response_model=GPUStatsHistoryResponse)
async def get_gpu_stats_history(
    since: datetime | None = None,
    limit: int = 300,
    db: AsyncSession = Depends(get_db),
) -> GPUStatsHistoryResponse:
    """Get recent GPU stats samples as a time-series.

    Args:
        since: Optional lower bound for recorded_at (ISO datetime)
        limit: Maximum number of samples to return (default 300)
        db: Database session
    """
    limit = max(limit, 1)
    limit = min(limit, 5000)

    stmt = select(GPUStats)
    if since is not None:
        stmt = stmt.where(GPUStats.recorded_at >= since)

    # Fetch newest first, then reverse to chronological order for charting.
    stmt = stmt.order_by(GPUStats.recorded_at.desc()).limit(limit)
    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    rows.reverse()

    samples = [
        {
            "recorded_at": r.recorded_at,
            "utilization": r.gpu_utilization,
            "memory_used": r.memory_used,
            "memory_total": r.memory_total,
            "temperature": r.temperature,
            "inference_fps": r.inference_fps,
        }
        for r in rows
    ]

    return GPUStatsHistoryResponse(samples=samples, count=len(samples), limit=limit)


@router.get("/config", response_model=ConfigResponse)
async def get_config() -> ConfigResponse:
    """Get public configuration settings.

    Returns non-sensitive application configuration values.
    Does NOT expose database URLs, API keys, or other secrets.

    Returns:
        ConfigResponse with public configuration settings
    """
    settings = get_settings()

    return ConfigResponse(
        app_name=settings.app_name,
        version=settings.app_version,
        retention_days=settings.retention_days,
        batch_window_seconds=settings.batch_window_seconds,
        batch_idle_timeout_seconds=settings.batch_idle_timeout_seconds,
        detection_confidence_threshold=settings.detection_confidence_threshold,
    )


def _runtime_env_path() -> Path:
    """Return the configured runtime override env file path."""
    return Path(os.getenv("HSI_RUNTIME_ENV_PATH", "./data/runtime.env"))


def _write_runtime_env(overrides: dict[str, str]) -> None:
    """Write/merge settings overrides into the runtime env file."""
    path = _runtime_env_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    existing: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            k, v = stripped.split("=", 1)
            existing[k.strip()] = v.strip()

    existing.update(overrides)

    content = "\n".join(f"{k}={v}" for k, v in sorted(existing.items())) + "\n"
    path.write_text(content, encoding="utf-8")


@router.patch("/config", response_model=ConfigResponse)
async def patch_config(update: ConfigUpdateRequest = Body(...)) -> ConfigResponse:
    """Patch processing-related configuration and persist runtime overrides.

    Notes:
    - This updates a runtime override env file (see `HSI_RUNTIME_ENV_PATH`) and clears the
      settings cache so subsequent `get_settings()` calls observe the new values.
    """
    overrides: dict[str, str] = {}

    if update.retention_days is not None:
        overrides["RETENTION_DAYS"] = str(update.retention_days)
    if update.batch_window_seconds is not None:
        overrides["BATCH_WINDOW_SECONDS"] = str(update.batch_window_seconds)
    if update.batch_idle_timeout_seconds is not None:
        overrides["BATCH_IDLE_TIMEOUT_SECONDS"] = str(update.batch_idle_timeout_seconds)
    if update.detection_confidence_threshold is not None:
        overrides["DETECTION_CONFIDENCE_THRESHOLD"] = str(update.detection_confidence_threshold)

    if overrides:
        _write_runtime_env(overrides)

    # Make new values visible to the app immediately.
    get_settings.cache_clear()
    settings = get_settings()

    return ConfigResponse(
        app_name=settings.app_name,
        version=settings.app_version,
        retention_days=settings.retention_days,
        batch_window_seconds=settings.batch_window_seconds,
        batch_idle_timeout_seconds=settings.batch_idle_timeout_seconds,
        detection_confidence_threshold=settings.detection_confidence_threshold,
    )


@router.get("/stats", response_model=SystemStatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db)) -> SystemStatsResponse:
    """Get system statistics.

    Returns aggregate statistics about the system:
    - Total number of cameras
    - Total number of events
    - Total number of detections
    - Application uptime

    Returns:
        SystemStatsResponse with system statistics
    """
    # Count cameras
    camera_count_stmt = select(func.count()).select_from(Camera)
    camera_result = await db.execute(camera_count_stmt)
    total_cameras = camera_result.scalar_one()

    # Count events
    event_count_stmt = select(func.count()).select_from(Event)
    event_result = await db.execute(event_count_stmt)
    total_events = event_result.scalar_one()

    # Count detections
    detection_count_stmt = select(func.count()).select_from(Detection)
    detection_result = await db.execute(detection_count_stmt)
    total_detections = detection_result.scalar_one()

    # Calculate uptime
    uptime = time.time() - _app_start_time

    return SystemStatsResponse(
        total_cameras=total_cameras,
        total_events=total_events,
        total_detections=total_detections,
        uptime_seconds=uptime,
    )
