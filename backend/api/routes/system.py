"""System monitoring and configuration API endpoints."""

import time
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.system import (
    ConfigResponse,
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


async def get_latest_gpu_stats(db: AsyncSession) -> dict[str, float | int | None] | None:
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
