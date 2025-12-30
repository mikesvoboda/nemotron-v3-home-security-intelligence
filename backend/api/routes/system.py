"""System monitoring and configuration API endpoints."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
from fastapi import APIRouter, Body, Depends, Header, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.system import (
    CleanupResponse,
    ConfigResponse,
    ConfigUpdateRequest,
    GPUStatsHistoryResponse,
    GPUStatsResponse,
    HealthResponse,
    LivenessResponse,
    PipelineLatencies,
    PipelineLatencyResponse,
    PipelineStageLatency,
    QueueDepths,
    ReadinessResponse,
    ServiceStatus,
    SeverityDefinitionResponse,
    SeverityMetadataResponse,
    SeverityThresholds,
    StageLatency,
    StorageCategoryStats,
    StorageStatsResponse,
    SystemStatsResponse,
    TelemetryResponse,
    WorkerStatus,
)
from backend.core import get_db, get_settings
from backend.core.redis import RedisClient, get_redis, get_redis_optional
from backend.models import Camera, Detection, Event, GPUStats, Log
from backend.models.audit import AuditAction
from backend.services.audit import AuditService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/system", tags=["system"])


# =============================================================================
# Circuit Breaker for Health Checks
# =============================================================================


@dataclass
class CircuitBreaker:
    """Simple circuit breaker for health checks.

    Tracks failures for external services and temporarily skips health checks
    for services that are repeatedly failing. This prevents health checks from
    blocking on slow/unavailable services.

    States:
    - CLOSED: Normal operation, health checks are executed
    - OPEN: Service is failing, health checks are skipped (returns cached failure)

    After reset_timeout expires, the circuit transitions back to CLOSED
    and allows the next health check to proceed (half-open state implicit).

    Attributes:
        failure_threshold: Number of consecutive failures before opening circuit
        reset_timeout: Time to wait before allowing health checks again
    """

    failure_threshold: int = 3
    reset_timeout: timedelta = field(default_factory=lambda: timedelta(seconds=30))
    _failures: dict[str, int] = field(default_factory=dict)
    _open_until: dict[str, datetime] = field(default_factory=dict)
    _last_error: dict[str, str] = field(default_factory=dict)

    def is_open(self, service: str) -> bool:
        """Check if circuit is open (service should be skipped).

        Args:
            service: Name of the service to check

        Returns:
            True if circuit is open and service should be skipped,
            False if circuit is closed and health check should proceed
        """
        if service in self._open_until:
            if datetime.now(UTC) < self._open_until[service]:
                return True
            # Reset after timeout (transition to half-open/closed)
            del self._open_until[service]
            self._failures[service] = 0
        return False

    def get_cached_error(self, service: str) -> str | None:
        """Get the last error message for a service with open circuit.

        Args:
            service: Name of the service

        Returns:
            Last error message or None if no cached error
        """
        return self._last_error.get(service)

    def record_failure(self, service: str, error_msg: str | None = None) -> None:
        """Record a health check failure for a service.

        Increments failure count and opens circuit if threshold is reached.

        Args:
            service: Name of the service that failed
            error_msg: Optional error message to cache
        """
        self._failures[service] = self._failures.get(service, 0) + 1
        if error_msg:
            self._last_error[service] = error_msg
        if self._failures[service] >= self.failure_threshold:
            self._open_until[service] = datetime.now(UTC) + self.reset_timeout
            logger.warning(
                f"Circuit breaker opened for {service} after "
                f"{self._failures[service]} failures. "
                f"Will retry after {self.reset_timeout.total_seconds()}s"
            )

    def record_success(self, service: str) -> None:
        """Record a successful health check for a service.

        Resets failure count and clears any cached error.

        Args:
            service: Name of the service that succeeded
        """
        self._failures[service] = 0
        if service in self._last_error:
            del self._last_error[service]

    def get_state(self, service: str) -> str:
        """Get the current circuit breaker state for a service.

        Args:
            service: Name of the service

        Returns:
            'open' if circuit is open, 'closed' otherwise
        """
        return "open" if self.is_open(service) else "closed"


# Global circuit breaker instance for health checks
_health_circuit_breaker = CircuitBreaker()


async def verify_api_key(x_api_key: str | None = Header(None)) -> None:
    """Verify API key for protected endpoints.

    This dependency checks if API key authentication is enabled in settings,
    and if so, validates the provided API key against the configured keys.

    Args:
        x_api_key: API key from X-API-Key header

    Raises:
        HTTPException: 401 if API key is required but missing or invalid
    """
    settings = get_settings()

    # Skip authentication if disabled
    if not settings.api_key_enabled:
        return

    # Require API key if authentication is enabled
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Provide via X-API-Key header.",
        )

    # Hash and validate the API key
    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    valid_hashes = {hashlib.sha256(k.encode()).hexdigest() for k in settings.api_keys}

    if key_hash not in valid_hashes:
        raise HTTPException(status_code=401, detail="Invalid API key")


# Track application start time for uptime calculation
_app_start_time = time.time()

# Timeout for health check operations (in seconds)
HEALTH_CHECK_TIMEOUT_SECONDS = 5.0

# Global references for worker status tracking (set by main.py at startup)
_gpu_monitor: GPUMonitor | None = None
_cleanup_service: CleanupService | None = None
_system_broadcaster: SystemBroadcaster | None = None
_file_watcher: FileWatcher | None = None
_pipeline_manager: PipelineWorkerManager | None = None


def register_workers(
    gpu_monitor: GPUMonitor | None = None,
    cleanup_service: CleanupService | None = None,
    system_broadcaster: SystemBroadcaster | None = None,
    file_watcher: FileWatcher | None = None,
    pipeline_manager: PipelineWorkerManager | None = None,
) -> None:
    """Register worker instances for readiness monitoring.

    This function should be called from main.py after workers are initialized
    to enable readiness probes to check worker status.

    Args:
        gpu_monitor: GPUMonitor instance
        cleanup_service: CleanupService instance
        system_broadcaster: SystemBroadcaster instance
        file_watcher: FileWatcher instance
        pipeline_manager: PipelineWorkerManager instance (critical for readiness)
    """
    global _gpu_monitor, _cleanup_service, _system_broadcaster, _file_watcher, _pipeline_manager  # noqa: PLW0603
    _gpu_monitor = gpu_monitor
    _cleanup_service = cleanup_service
    _system_broadcaster = system_broadcaster
    _file_watcher = file_watcher
    _pipeline_manager = pipeline_manager


def _get_worker_statuses() -> list[WorkerStatus]:
    """Get status of all registered background workers.

    Returns:
        List of WorkerStatus objects for each registered worker
    """
    statuses: list[WorkerStatus] = []

    # Check GPU monitor
    if _gpu_monitor is not None:
        is_running = getattr(_gpu_monitor, "running", False)
        statuses.append(
            WorkerStatus(
                name="gpu_monitor",
                running=is_running,
                message=None if is_running else "Not running",
            )
        )

    # Check cleanup service
    if _cleanup_service is not None:
        is_running = getattr(_cleanup_service, "running", False)
        statuses.append(
            WorkerStatus(
                name="cleanup_service",
                running=is_running,
                message=None if is_running else "Not running",
            )
        )

    # Check system broadcaster
    if _system_broadcaster is not None:
        is_running = getattr(_system_broadcaster, "_running", False)
        statuses.append(
            WorkerStatus(
                name="system_broadcaster",
                running=is_running,
                message=None if is_running else "Not running",
            )
        )

    # Check file watcher
    if _file_watcher is not None:
        is_running = getattr(_file_watcher, "running", False)
        statuses.append(
            WorkerStatus(
                name="file_watcher",
                running=is_running,
                message=None if is_running else "Not running",
            )
        )

    # Check pipeline workers (detection and analysis workers are critical)
    if _pipeline_manager is not None:
        manager_status = _pipeline_manager.get_status()
        workers_dict = manager_status.get("workers", {})

        # Detection worker (critical)
        if "detection" in workers_dict:
            detection_state = workers_dict["detection"].get("state", "stopped")
            is_running = detection_state == "running"
            statuses.append(
                WorkerStatus(
                    name="detection_worker",
                    running=is_running,
                    message=None if is_running else f"State: {detection_state}",
                )
            )

        # Analysis worker (critical)
        if "analysis" in workers_dict:
            analysis_state = workers_dict["analysis"].get("state", "stopped")
            is_running = analysis_state == "running"
            statuses.append(
                WorkerStatus(
                    name="analysis_worker",
                    running=is_running,
                    message=None if is_running else f"State: {analysis_state}",
                )
            )

        # Batch timeout worker
        if "timeout" in workers_dict:
            timeout_state = workers_dict["timeout"].get("state", "stopped")
            is_running = timeout_state == "running"
            statuses.append(
                WorkerStatus(
                    name="batch_timeout_worker",
                    running=is_running,
                    message=None if is_running else f"State: {timeout_state}",
                )
            )

        # Metrics worker
        if "metrics" in workers_dict:
            metrics_running = workers_dict["metrics"].get("running", False)
            statuses.append(
                WorkerStatus(
                    name="metrics_worker",
                    running=metrics_running,
                    message=None if metrics_running else "Not running",
                )
            )

    return statuses


def _are_critical_pipeline_workers_healthy() -> bool:
    """Check if critical pipeline workers (detection and analysis) are running.

    Returns:
        True if both detection and analysis workers are running, False otherwise.
        Returns False if pipeline_manager is not registered (system cannot process detections).
    """
    if _pipeline_manager is None:
        # Pipeline manager not registered - system cannot process detections
        logger.warning("Pipeline manager not registered - marking as not ready")
        return False

    manager_status = _pipeline_manager.get_status()

    # Manager itself must be running
    if not manager_status.get("running", False):
        return False

    workers_dict = manager_status.get("workers", {})

    # Check detection worker (critical)
    if "detection" in workers_dict:
        detection_state = workers_dict["detection"].get("state", "stopped")
        if detection_state != "running":
            return False

    # Check analysis worker (critical)
    if "analysis" in workers_dict:
        analysis_state = workers_dict["analysis"].get("state", "stopped")
        if analysis_state != "running":
            return False

    return True


# Type hints for worker imports (avoid circular imports)
if TYPE_CHECKING:
    from backend.services.cleanup_service import CleanupService
    from backend.services.file_watcher import FileWatcher
    from backend.services.gpu_monitor import GPUMonitor
    from backend.services.pipeline_workers import PipelineWorkerManager
    from backend.services.system_broadcaster import SystemBroadcaster


async def get_latest_gpu_stats(
    db: AsyncSession,
) -> dict[str, float | int | str | datetime | None] | None:
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
        "gpu_name": gpu_stat.gpu_name,
        "utilization": gpu_stat.gpu_utilization,
        "memory_used": gpu_stat.memory_used,
        "memory_total": gpu_stat.memory_total,
        "temperature": gpu_stat.temperature,
        "power_usage": gpu_stat.power_usage,
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


async def check_redis_health(redis: RedisClient | None) -> ServiceStatus:
    """Check Redis connectivity and health.

    Args:
        redis: Redis client (may be None if connection failed during dependency injection)

    Returns:
        ServiceStatus with Redis health information
    """
    # Handle case where Redis client is None (connection failed during DI)
    if redis is None:
        return ServiceStatus(
            status="unhealthy",
            message="Redis unavailable: connection failed",
            details=None,
        )

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


async def _check_rtdetr_health(rtdetr_url: str, timeout: float) -> tuple[bool, str | None]:
    """Check RT-DETR object detection service health.

    Args:
        rtdetr_url: Base URL for RT-DETR service
        timeout: Request timeout in seconds

    Returns:
        Tuple of (is_healthy, error_message)
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{rtdetr_url}/health")
            response.raise_for_status()
            return True, None
    except httpx.ConnectError:
        return False, "RT-DETR service connection refused"
    except httpx.TimeoutException:
        return False, "RT-DETR service request timed out"
    except httpx.HTTPStatusError as e:
        return False, f"RT-DETR service returned HTTP {e.response.status_code}"
    except Exception as e:
        return False, f"RT-DETR service error: {e!s}"


async def _check_nemotron_health(nemotron_url: str, timeout: float) -> tuple[bool, str | None]:
    """Check Nemotron LLM service health.

    Args:
        nemotron_url: Base URL for Nemotron service (llama.cpp server)
        timeout: Request timeout in seconds

    Returns:
        Tuple of (is_healthy, error_message)
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{nemotron_url}/health")
            response.raise_for_status()
            return True, None
    except httpx.ConnectError:
        return False, "Nemotron service connection refused"
    except httpx.TimeoutException:
        return False, "Nemotron service request timed out"
    except httpx.HTTPStatusError as e:
        return False, f"Nemotron service returned HTTP {e.response.status_code}"
    except Exception as e:
        return False, f"Nemotron service error: {e!s}"


# Timeout for individual AI service health checks (in seconds)
AI_HEALTH_CHECK_TIMEOUT_SECONDS = 3.0


async def _check_rtdetr_health_with_circuit_breaker(
    rtdetr_url: str, timeout: float
) -> tuple[bool, str | None]:
    """Check RT-DETR health with circuit breaker protection.

    If the circuit is open (service repeatedly failing), returns cached error
    immediately without making network call. Otherwise performs health check
    and records result in circuit breaker.

    Args:
        rtdetr_url: Base URL for RT-DETR service
        timeout: Request timeout in seconds

    Returns:
        Tuple of (is_healthy, error_message)
    """
    service_name = "rtdetr"

    # Check if circuit is open (service is down, skip the check)
    if _health_circuit_breaker.is_open(service_name):
        cached_error = _health_circuit_breaker.get_cached_error(service_name)
        return False, cached_error or "RT-DETR service unavailable (circuit open)"

    # Circuit is closed, perform actual health check
    is_healthy, error_msg = await _check_rtdetr_health(rtdetr_url, timeout)

    # Record result in circuit breaker
    if is_healthy:
        _health_circuit_breaker.record_success(service_name)
    else:
        _health_circuit_breaker.record_failure(service_name, error_msg)

    return is_healthy, error_msg


async def _check_nemotron_health_with_circuit_breaker(
    nemotron_url: str, timeout: float
) -> tuple[bool, str | None]:
    """Check Nemotron health with circuit breaker protection.

    If the circuit is open (service repeatedly failing), returns cached error
    immediately without making network call. Otherwise performs health check
    and records result in circuit breaker.

    Args:
        nemotron_url: Base URL for Nemotron service
        timeout: Request timeout in seconds

    Returns:
        Tuple of (is_healthy, error_message)
    """
    service_name = "nemotron"

    # Check if circuit is open (service is down, skip the check)
    if _health_circuit_breaker.is_open(service_name):
        cached_error = _health_circuit_breaker.get_cached_error(service_name)
        return False, cached_error or "Nemotron service unavailable (circuit open)"

    # Circuit is closed, perform actual health check
    is_healthy, error_msg = await _check_nemotron_health(nemotron_url, timeout)

    # Record result in circuit breaker
    if is_healthy:
        _health_circuit_breaker.record_success(service_name)
    else:
        _health_circuit_breaker.record_failure(service_name, error_msg)

    return is_healthy, error_msg


async def check_ai_services_health() -> ServiceStatus:
    """Check AI services health by pinging RT-DETR and Nemotron endpoints.

    Performs concurrent health checks on both AI services:
    - RT-DETR (object detection): GET {rtdetr_url}/health
    - Nemotron (LLM reasoning): GET {nemotron_url}/health

    Returns:
        ServiceStatus with AI services health information:
        - healthy: Both services are responding
        - degraded: At least one service is down but some AI capability remains
        - unhealthy: Both services are down (no AI capability)
    """
    settings = get_settings()
    rtdetr_url = settings.rtdetr_url
    nemotron_url = settings.nemotron_url

    # Check both services concurrently with circuit breaker protection
    rtdetr_result, nemotron_result = await asyncio.gather(
        _check_rtdetr_health_with_circuit_breaker(rtdetr_url, AI_HEALTH_CHECK_TIMEOUT_SECONDS),
        _check_nemotron_health_with_circuit_breaker(nemotron_url, AI_HEALTH_CHECK_TIMEOUT_SECONDS),
    )

    rtdetr_healthy, rtdetr_error = rtdetr_result
    nemotron_healthy, nemotron_error = nemotron_result

    # Build details dict with individual service status
    details: dict[str, str] = {
        "rtdetr": "healthy" if rtdetr_healthy else (rtdetr_error or "unknown error"),
        "nemotron": "healthy" if nemotron_healthy else (nemotron_error or "unknown error"),
    }

    # Determine overall AI status
    if rtdetr_healthy and nemotron_healthy:
        return ServiceStatus(
            status="healthy",
            message="AI services operational",
            details=details,
        )
    elif rtdetr_healthy or nemotron_healthy:
        # At least one service is up - degraded but partially functional
        working_service = "RT-DETR" if rtdetr_healthy else "Nemotron"
        failed_service = "Nemotron" if rtdetr_healthy else "RT-DETR"
        return ServiceStatus(
            status="degraded",
            message=f"{failed_service} service unavailable, {working_service} operational",
            details=details,
        )
    else:
        # Both services are down
        return ServiceStatus(
            status="unhealthy",
            message="All AI services unavailable",
            details=details,
        )


@router.get("/health", response_model=HealthResponse)
async def get_health(
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient | None = Depends(get_redis_optional),
) -> HealthResponse:
    """Get detailed system health check.

    Checks the health of all system components:
    - Database connectivity
    - Redis connectivity
    - AI services status

    Health checks have a timeout of HEALTH_CHECK_TIMEOUT_SECONDS (default 5 seconds).
    If a health check times out, the service is marked as unhealthy.

    Returns:
        HealthResponse with overall status and individual service statuses.
        HTTP 200 if healthy, 503 if degraded or unhealthy.
    """
    # Check all services with timeout protection
    try:
        db_status = await asyncio.wait_for(
            check_database_health(db),
            timeout=HEALTH_CHECK_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        db_status = ServiceStatus(
            status="unhealthy",
            message="Database health check timed out",
            details=None,
        )

    try:
        redis_status = await asyncio.wait_for(
            check_redis_health(redis),
            timeout=HEALTH_CHECK_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        redis_status = ServiceStatus(
            status="unhealthy",
            message="Redis health check timed out",
            details=None,
        )

    try:
        ai_status = await asyncio.wait_for(
            check_ai_services_health(),
            timeout=HEALTH_CHECK_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        ai_status = ServiceStatus(
            status="unhealthy",
            message="AI services health check timed out",
            details=None,
        )

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

    # Set appropriate HTTP status code
    # 200 for healthy, 503 for degraded or unhealthy
    if overall_status != "healthy":
        response.status_code = 503

    return HealthResponse(
        status=overall_status,
        services=services,
        timestamp=datetime.now(UTC),
    )


@router.get("/health/live", response_model=LivenessResponse)
async def get_liveness() -> LivenessResponse:
    """Liveness probe endpoint.

    This endpoint indicates whether the process is running and able to
    respond to HTTP requests. It always returns 200 with status "alive"
    if the process is up. This is a minimal check with no dependencies.

    Used by Kubernetes/Docker to determine if the container should be restarted.
    If this endpoint fails, the process is considered dead and should be restarted.

    Returns:
        LivenessResponse with status "alive"
    """
    return LivenessResponse(status="alive")


@router.get("/health/ready", response_model=ReadinessResponse)
async def get_readiness(
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient | None = Depends(get_redis_optional),
) -> ReadinessResponse:
    """Readiness probe endpoint.

    This endpoint indicates whether the application is ready to receive
    traffic and process uploads. It checks all critical dependencies:
    - Database connectivity (critical)
    - Redis connectivity (required for queue processing)
    - AI services availability
    - Background worker status

    Used by Kubernetes/Docker to determine if traffic should be routed to this instance.
    If this endpoint returns not_ready, the instance should not receive new requests.

    Health checks have a timeout of HEALTH_CHECK_TIMEOUT_SECONDS (default 5 seconds).
    If a health check times out, the service is marked as unhealthy.

    Returns:
        ReadinessResponse with overall readiness status and detailed checks.
        HTTP 200 if ready, 503 if degraded or not ready.
    """
    # Check all infrastructure services with timeout protection
    try:
        db_status = await asyncio.wait_for(
            check_database_health(db),
            timeout=HEALTH_CHECK_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        db_status = ServiceStatus(
            status="unhealthy",
            message="Database health check timed out",
            details=None,
        )

    try:
        redis_status = await asyncio.wait_for(
            check_redis_health(redis),
            timeout=HEALTH_CHECK_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        redis_status = ServiceStatus(
            status="unhealthy",
            message="Redis health check timed out",
            details=None,
        )

    try:
        ai_status = await asyncio.wait_for(
            check_ai_services_health(),
            timeout=HEALTH_CHECK_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        ai_status = ServiceStatus(
            status="unhealthy",
            message="AI services health check timed out",
            details=None,
        )

    services = {
        "database": db_status,
        "redis": redis_status,
        "ai": ai_status,
    }

    # Get worker statuses
    workers = _get_worker_statuses()

    # Check critical pipeline workers (detection and analysis workers)
    pipeline_workers_healthy = _are_critical_pipeline_workers_healthy()

    # Determine overall readiness
    # Ready: All critical services healthy (database, redis, and pipeline workers are required)
    # Degraded: Database healthy but some other services unhealthy
    # Not Ready: Database unhealthy OR Redis unhealthy OR critical pipeline workers down

    db_healthy = db_status.status == "healthy"
    redis_healthy = redis_status.status == "healthy"

    # Both database and redis are required to process camera uploads
    # Critical pipeline workers (detection, analysis) are also required for full functionality
    if db_healthy and redis_healthy and pipeline_workers_healthy:
        ready = True
        status = "ready"
    elif db_healthy and redis_healthy:
        # Database and Redis healthy but pipeline workers down - not ready
        # (can't process images even if infrastructure is up)
        ready = False
        status = "not_ready"
    elif db_healthy:
        # Database up but Redis down - degraded (can't process queues)
        ready = False
        status = "degraded"
    else:
        # Database down - not ready
        ready = False
        status = "not_ready"

    # Set appropriate HTTP status code
    # 200 if ready, 503 if not ready or degraded
    if not ready:
        response.status_code = 503

    return ReadinessResponse(
        ready=ready,
        status=status,
        services=services,
        workers=workers,
        timestamp=datetime.now(UTC),
    )


@router.get("/gpu", response_model=GPUStatsResponse)
async def get_gpu_stats(db: AsyncSession = Depends(get_db)) -> GPUStatsResponse:
    """Get current GPU statistics.

    Returns the most recent GPU statistics including:
    - GPU name
    - GPU utilization percentage
    - Memory usage (used/total)
    - Temperature
    - Power usage
    - Inference FPS

    Returns:
        GPUStatsResponse with GPU statistics (null values if unavailable)
    """
    stats = await get_latest_gpu_stats(db)

    if stats is None:
        # Return all null values if no GPU data available
        return GPUStatsResponse(
            gpu_name=None,
            utilization=None,
            memory_used=None,
            memory_total=None,
            temperature=None,
            power_usage=None,
            inference_fps=None,
        )

    return GPUStatsResponse(
        gpu_name=stats["gpu_name"],
        utilization=stats["utilization"],
        memory_used=stats["memory_used"],
        memory_total=stats["memory_total"],
        temperature=stats["temperature"],
        power_usage=stats["power_usage"],
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
            "gpu_name": r.gpu_name,
            "utilization": r.gpu_utilization,
            "memory_used": r.memory_used,
            "memory_total": r.memory_total,
            "temperature": r.temperature,
            "power_usage": r.power_usage,
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


@router.patch("/config", response_model=ConfigResponse, dependencies=[Depends(verify_api_key)])
async def patch_config(
    request: Request,
    update: ConfigUpdateRequest = Body(...),
    db: AsyncSession = Depends(get_db),
) -> ConfigResponse:
    """Patch processing-related configuration and persist runtime overrides.

    Requires API key authentication when api_key_enabled is True in settings.
    Provide the API key via X-API-Key header.

    Notes:
    - This updates a runtime override env file (see `HSI_RUNTIME_ENV_PATH`) and clears the
      settings cache so subsequent `get_settings()` calls observe the new values.
    """
    # Capture old settings for audit log
    old_settings = get_settings()
    old_values = {
        "retention_days": old_settings.retention_days,
        "batch_window_seconds": old_settings.batch_window_seconds,
        "batch_idle_timeout_seconds": old_settings.batch_idle_timeout_seconds,
        "detection_confidence_threshold": old_settings.detection_confidence_threshold,
    }

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

    # Build changes for audit log
    new_values = {
        "retention_days": settings.retention_days,
        "batch_window_seconds": settings.batch_window_seconds,
        "batch_idle_timeout_seconds": settings.batch_idle_timeout_seconds,
        "detection_confidence_threshold": settings.detection_confidence_threshold,
    }
    changes: dict[str, dict[str, Any]] = {}
    for key, old_value in old_values.items():
        new_value = new_values[key]
        if old_value != new_value:
            changes[key] = {"old": old_value, "new": new_value}

    # Log the audit entry
    if changes:
        await AuditService.log_action(
            db=db,
            action=AuditAction.SETTINGS_CHANGED,
            resource_type="settings",
            actor="anonymous",
            details={"changes": changes},
            request=request,
        )
        await db.commit()

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


# =============================================================================
# Telemetry Endpoint and Helpers
# =============================================================================

# Redis keys for latency tracking
LATENCY_KEY_PREFIX = "telemetry:latency:"
LATENCY_TTL_SECONDS = 3600  # Keep latency samples for 1 hour
MAX_LATENCY_SAMPLES = 1000  # Maximum samples to keep per stage

# Valid pipeline stages
PIPELINE_STAGES = ("watch", "detect", "batch", "analyze")


async def record_stage_latency(
    redis: RedisClient,
    stage: str,
    latency_ms: float,
) -> None:
    """Record a latency sample for a pipeline stage.

    Stores latency samples in Redis lists for later statistical analysis.
    Samples are automatically trimmed to MAX_LATENCY_SAMPLES (keeping newest)
    and the key TTL is refreshed to LATENCY_TTL_SECONDS on each write.

    The list uses RPUSH (append to end), so newer samples are at the end.
    When trimmed, we keep the last MAX_LATENCY_SAMPLES items (newest).

    Args:
        redis: Redis client
        stage: Pipeline stage name (watch, detect, batch, analyze)
        latency_ms: Latency in milliseconds
    """
    if stage not in PIPELINE_STAGES:
        logger.warning(f"Invalid pipeline stage: {stage}")
        return

    key = f"{LATENCY_KEY_PREFIX}{stage}"
    try:
        # Add to list (appends to end, so newest samples are last)
        # max_size trims to keep only the last MAX_LATENCY_SAMPLES items
        await redis.add_to_queue(key, latency_ms, max_size=MAX_LATENCY_SAMPLES)
        # Refresh TTL so inactive stages eventually expire
        await redis.expire(key, LATENCY_TTL_SECONDS)
    except Exception as e:
        logger.warning(f"Failed to record latency for stage {stage}: {e}")


def _calculate_percentile(samples: list[float], percentile: float) -> float:
    """Calculate a percentile from a sorted list of samples.

    Args:
        samples: Sorted list of latency samples
        percentile: Percentile to calculate (0-100)

    Returns:
        Value at the given percentile
    """
    if not samples:
        return 0.0
    index = int(len(samples) * percentile / 100)
    index = min(index, len(samples) - 1)
    return samples[index]


def _calculate_stage_latency(samples: list[float]) -> StageLatency | None:
    """Calculate latency statistics for a single stage.

    Args:
        samples: List of latency samples in milliseconds

    Returns:
        StageLatency with calculated statistics, or None if no samples
    """
    if not samples:
        return None

    sorted_samples = sorted(samples)
    count = len(sorted_samples)

    return StageLatency(
        avg_ms=sum(sorted_samples) / count,
        min_ms=sorted_samples[0],
        max_ms=sorted_samples[-1],
        p50_ms=_calculate_percentile(sorted_samples, 50),
        p95_ms=_calculate_percentile(sorted_samples, 95),
        p99_ms=_calculate_percentile(sorted_samples, 99),
        sample_count=count,
    )


async def get_latency_stats(redis: RedisClient) -> PipelineLatencies | None:
    """Get latency statistics for all pipeline stages.

    Retrieves latency samples from Redis and calculates statistics.

    Args:
        redis: Redis client

    Returns:
        PipelineLatencies with statistics for each stage, or None on error
    """
    try:
        latencies: dict[str, StageLatency | None] = {}

        for stage in PIPELINE_STAGES:
            key = f"{LATENCY_KEY_PREFIX}{stage}"
            # Get samples from Redis list
            samples_data = await redis.peek_queue(key, 0, MAX_LATENCY_SAMPLES - 1)

            if samples_data:
                # Convert to floats, filtering out invalid values
                samples = []
                for s in samples_data:
                    try:
                        samples.append(float(s))
                    except (TypeError, ValueError):
                        continue
                latencies[stage] = _calculate_stage_latency(samples)
            else:
                latencies[stage] = None

        return PipelineLatencies(
            watch=latencies.get("watch"),
            detect=latencies.get("detect"),
            batch=latencies.get("batch"),
            analyze=latencies.get("analyze"),
        )
    except Exception as e:
        logger.warning(f"Failed to get latency stats: {e}")
        return None


@router.get("/telemetry", response_model=TelemetryResponse)
async def get_telemetry(
    redis: RedisClient = Depends(get_redis),
) -> TelemetryResponse:
    """Get pipeline telemetry data.

    Returns real-time metrics about the AI processing pipeline:
    - Queue depths: Items waiting in detection and analysis queues
    - Stage latencies: Processing time statistics for each pipeline stage

    This endpoint helps operators:
    - Monitor pipeline health and throughput
    - Identify bottlenecks and backlogs
    - Debug pipeline stalls
    - Track performance trends

    Returns:
        TelemetryResponse with queue depths and latency statistics
    """
    # Get queue depths
    detection_depth = 0
    analysis_depth = 0

    try:
        detection_depth = await redis.get_queue_length("detection_queue")
        analysis_depth = await redis.get_queue_length("analysis_queue")
    except Exception as e:
        logger.warning(f"Failed to get queue depths: {e}")
        # Return zeros on error - endpoint should still work

    queues = QueueDepths(
        detection_queue=detection_depth,
        analysis_queue=analysis_depth,
    )

    # Get latency statistics
    latencies = await get_latency_stats(redis)

    return TelemetryResponse(
        queues=queues,
        latencies=latencies,
        timestamp=datetime.now(UTC),
    )


# =============================================================================
# Pipeline Latency Endpoint
# =============================================================================


def _stats_to_schema(stats: dict[str, float | int | None]) -> PipelineStageLatency | None:
    """Convert latency stats dict to PipelineStageLatency schema.

    Args:
        stats: Dictionary with latency statistics from PipelineLatencyTracker

    Returns:
        PipelineStageLatency schema or None if no samples
    """
    if stats.get("sample_count", 0) == 0:
        return None

    return PipelineStageLatency(
        avg_ms=stats.get("avg_ms"),
        min_ms=stats.get("min_ms"),
        max_ms=stats.get("max_ms"),
        p50_ms=stats.get("p50_ms"),
        p95_ms=stats.get("p95_ms"),
        p99_ms=stats.get("p99_ms"),
        sample_count=stats.get("sample_count", 0),
    )


@router.get("/pipeline-latency", response_model=PipelineLatencyResponse)
async def get_pipeline_latency(
    window_minutes: int = 60,
) -> PipelineLatencyResponse:
    """Get pipeline latency metrics with percentiles.

    Returns latency statistics for each stage transition in the AI pipeline:
    - watch_to_detect: Time from file watcher detecting image to RT-DETR processing start
    - detect_to_batch: Time from detection completion to batch aggregation
    - batch_to_analyze: Time from batch completion to Nemotron analysis start
    - total_pipeline: Total end-to-end processing time

    Each stage includes:
    - avg_ms: Average latency in milliseconds
    - min_ms: Minimum latency
    - max_ms: Maximum latency
    - p50_ms: 50th percentile (median)
    - p95_ms: 95th percentile
    - p99_ms: 99th percentile
    - sample_count: Number of samples used

    Args:
        window_minutes: Time window for statistics calculation (default 60 minutes)

    Returns:
        PipelineLatencyResponse with latency statistics for each stage
    """
    from backend.core.metrics import get_pipeline_latency_tracker

    tracker = get_pipeline_latency_tracker()
    summary = tracker.get_pipeline_summary(window_minutes=window_minutes)

    return PipelineLatencyResponse(
        watch_to_detect=_stats_to_schema(summary.get("watch_to_detect", {})),
        detect_to_batch=_stats_to_schema(summary.get("detect_to_batch", {})),
        batch_to_analyze=_stats_to_schema(summary.get("batch_to_analyze", {})),
        total_pipeline=_stats_to_schema(summary.get("total_pipeline", {})),
        window_minutes=window_minutes,
        timestamp=datetime.now(UTC),
    )


# =============================================================================
# Cleanup Endpoint
# =============================================================================


@router.post("/cleanup", response_model=CleanupResponse, dependencies=[Depends(verify_api_key)])
async def trigger_cleanup(dry_run: bool = False) -> CleanupResponse:
    """Trigger manual data cleanup based on retention settings.

    Requires API key authentication when api_key_enabled is True in settings.
    Provide the API key via X-API-Key header.

    This endpoint runs the CleanupService to delete old data according to
    the configured retention period. It deletes:
    - Events older than retention period
    - Detections older than retention period
    - GPU stats older than retention period
    - Logs older than log retention period
    - Associated thumbnail files
    - Optionally original image files (if delete_images is enabled)

    The cleanup respects the current retention_days setting from the system
    configuration. To change the retention period before running cleanup,
    use PATCH /api/system/config first.

    Args:
        dry_run: If True, calculate and return what would be deleted without
                 actually performing the deletion. Useful for verification
                 before destructive operations.

    Returns:
        CleanupResponse with statistics about the cleanup operation.
        When dry_run=True, the counts represent what would be deleted.
    """
    from backend.services.cleanup_service import CleanupService

    settings = get_settings()

    if dry_run:
        logger.info(
            f"Manual cleanup dry run triggered with retention_days={settings.retention_days}"
        )

        # Create a CleanupService instance to use for dry run calculations
        cleanup_service = CleanupService(
            retention_days=settings.retention_days,
            thumbnail_dir="backend/data/thumbnails",
            delete_images=False,
        )

        try:
            # Run the dry run to calculate what would be deleted
            stats = await cleanup_service.dry_run_cleanup()

            logger.info(f"Manual cleanup dry run completed: {stats}")

            return CleanupResponse(
                events_deleted=stats.events_deleted,
                detections_deleted=stats.detections_deleted,
                gpu_stats_deleted=stats.gpu_stats_deleted,
                logs_deleted=stats.logs_deleted,
                thumbnails_deleted=stats.thumbnails_deleted,
                images_deleted=stats.images_deleted,
                space_reclaimed=stats.space_reclaimed,
                retention_days=settings.retention_days,
                dry_run=True,
                timestamp=datetime.now(UTC),
            )
        except Exception as e:
            logger.error(f"Manual cleanup dry run failed: {e}", exc_info=True)
            raise
    else:
        logger.info(f"Manual cleanup triggered with retention_days={settings.retention_days}")

        # Create a CleanupService instance with current settings
        cleanup_service = CleanupService(
            retention_days=settings.retention_days,
            thumbnail_dir="backend/data/thumbnails",
            delete_images=False,  # Keep original images by default for safety
        )

        try:
            # Run the cleanup operation
            stats = await cleanup_service.run_cleanup()

            logger.info(f"Manual cleanup completed: {stats}")

            return CleanupResponse(
                events_deleted=stats.events_deleted,
                detections_deleted=stats.detections_deleted,
                gpu_stats_deleted=stats.gpu_stats_deleted,
                logs_deleted=stats.logs_deleted,
                thumbnails_deleted=stats.thumbnails_deleted,
                images_deleted=stats.images_deleted,
                space_reclaimed=stats.space_reclaimed,
                retention_days=settings.retention_days,
                dry_run=False,
                timestamp=datetime.now(UTC),
            )
        except Exception as e:
            logger.error(f"Manual cleanup failed: {e}", exc_info=True)
            raise


# =============================================================================
# Severity Endpoint
# =============================================================================


@router.get("/severity", response_model=SeverityMetadataResponse)
async def get_severity_metadata() -> SeverityMetadataResponse:
    """Get severity level definitions and thresholds.

    Returns complete information about the severity taxonomy including:
    - All severity level definitions (LOW, MEDIUM, HIGH, CRITICAL)
    - Risk score thresholds for each level
    - Color codes for UI display
    - Human-readable labels and descriptions

    This endpoint is useful for frontends to:
    - Display severity information consistently
    - Show severity legends in the UI
    - Validate severity-related user inputs
    - Map risk scores to severity levels client-side

    Returns:
        SeverityMetadataResponse with all severity definitions and current thresholds
    """
    from backend.services.severity import get_severity_service

    service = get_severity_service()

    # Get severity definitions
    definitions = service.get_severity_definitions()

    # Convert to response format
    definition_responses = [
        SeverityDefinitionResponse(
            severity=defn.severity.value,
            label=defn.label,
            description=defn.description,
            color=defn.color,
            priority=defn.priority,
            min_score=defn.min_score,
            max_score=defn.max_score,
        )
        for defn in definitions
    ]

    thresholds = service.get_thresholds()

    return SeverityMetadataResponse(
        definitions=definition_responses,
        thresholds=SeverityThresholds(
            low_max=thresholds["low_max"],
            medium_max=thresholds["medium_max"],
            high_max=thresholds["high_max"],
        ),
    )


# =============================================================================
# Storage Endpoint
# =============================================================================


def _get_directory_stats(directory: Path) -> tuple[int, int]:
    """Calculate total size and file count for a directory.

    Args:
        directory: Path to the directory to scan

    Returns:
        Tuple of (total_size_bytes, file_count)
    """
    total_size = 0
    file_count = 0

    if not directory.exists():
        return 0, 0

    try:
        for entry in directory.rglob("*"):
            if entry.is_file():
                try:
                    total_size += entry.stat().st_size
                    file_count += 1
                except (OSError, PermissionError):
                    # Skip files we can't access
                    pass
    except (OSError, PermissionError):
        # Return zeros if we can't access the directory
        pass

    return total_size, file_count


@router.get("/storage", response_model=StorageStatsResponse)
async def get_storage_stats(db: AsyncSession = Depends(get_db)) -> StorageStatsResponse:
    """Get storage statistics and disk usage metrics.

    Returns detailed storage usage information including:
    - Overall disk usage (used/total/free)
    - Storage breakdown by category (thumbnails, images, clips)
    - Database record counts (events, detections, GPU stats, logs)

    This endpoint helps operators:
    - Monitor available storage space
    - Understand storage distribution across data types
    - Plan cleanup operations
    - Track database growth

    Returns:
        StorageStatsResponse with comprehensive storage metrics
    """
    settings = get_settings()

    # Get disk usage for the data directory
    # Use the thumbnail directory's parent as a reference point for data storage
    thumbnail_dir = Path(settings.video_thumbnails_dir)
    data_dir = thumbnail_dir.parent if thumbnail_dir.parent.exists() else Path("data")

    # Fall back to current directory if data directory doesn't exist
    if not data_dir.exists():
        data_dir = Path()

    try:
        disk_usage = shutil.disk_usage(data_dir)
        disk_total = disk_usage.total
        disk_used = disk_usage.used
        disk_free = disk_usage.free
        disk_percent = (disk_used / disk_total * 100) if disk_total > 0 else 0.0
    except (OSError, PermissionError):
        # Return zeros if we can't access disk stats
        disk_total = 0
        disk_used = 0
        disk_free = 0
        disk_percent = 0.0

    # Get storage breakdown by category
    # Thumbnails directory
    thumbnails_size, thumbnails_count = _get_directory_stats(thumbnail_dir)

    # Images directory (Foscam uploads)
    foscam_path = Path(settings.foscam_base_path)
    images_size, images_count = _get_directory_stats(foscam_path)

    # Clips directory
    clips_dir = Path(settings.clips_directory)
    clips_size, clips_count = _get_directory_stats(clips_dir)

    # Get database record counts
    # Count events
    event_count_stmt = select(func.count()).select_from(Event)
    event_result = await db.execute(event_count_stmt)
    events_count = event_result.scalar_one()

    # Count detections
    detection_count_stmt = select(func.count()).select_from(Detection)
    detection_result = await db.execute(detection_count_stmt)
    detections_count = detection_result.scalar_one()

    # Count GPU stats
    gpu_stats_count_stmt = select(func.count()).select_from(GPUStats)
    gpu_stats_result = await db.execute(gpu_stats_count_stmt)
    gpu_stats_count = gpu_stats_result.scalar_one()

    # Count logs
    logs_count_stmt = select(func.count()).select_from(Log)
    logs_result = await db.execute(logs_count_stmt)
    logs_count = logs_result.scalar_one()

    return StorageStatsResponse(
        disk_used_bytes=disk_used,
        disk_total_bytes=disk_total,
        disk_free_bytes=disk_free,
        disk_usage_percent=round(disk_percent, 2),
        thumbnails=StorageCategoryStats(
            file_count=thumbnails_count,
            size_bytes=thumbnails_size,
        ),
        images=StorageCategoryStats(
            file_count=images_count,
            size_bytes=images_size,
        ),
        clips=StorageCategoryStats(
            file_count=clips_count,
            size_bytes=clips_size,
        ),
        events_count=events_count,
        detections_count=detections_count,
        gpu_stats_count=gpu_stats_count,
        logs_count=logs_count,
        timestamp=datetime.now(UTC),
    )
