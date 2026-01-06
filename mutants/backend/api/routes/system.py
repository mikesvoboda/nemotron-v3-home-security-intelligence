"""System monitoring and configuration API endpoints."""

from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.baseline import (
    AnomalyConfig,
    AnomalyConfigUpdate,
)
from backend.api.schemas.system import (
    BatchAggregatorStatusResponse,
    BatchInfoResponse,
    CircuitBreakerConfigResponse,
    CircuitBreakerResetResponse,
    CircuitBreakersResponse,
    CircuitBreakerStateEnum,
    CircuitBreakerStatusResponse,
    CleanupResponse,
    CleanupStatusResponse,
    ConfigResponse,
    ConfigUpdateRequest,
    DegradationModeEnum,
    DegradationStatusResponse,
    FileWatcherStatusResponse,
    GPUStatsHistoryResponse,
    GPUStatsResponse,
    HealthResponse,
    LatencyHistorySnapshot,
    LatencyHistoryStageStats,
    ModelLatencyHistoryResponse,
    ModelLatencyHistorySnapshot,
    ModelLatencyStageStats,
    ModelRegistryResponse,
    ModelStatusEnum,
    ModelStatusResponse,
    ModelZooStatusItem,
    ModelZooStatusResponse,
    PipelineLatencies,
    PipelineLatencyHistoryResponse,
    PipelineLatencyResponse,
    PipelineStageLatency,
    PipelineStatusResponse,
    QueueDepths,
    ReadinessResponse,
    ServiceHealthStatusResponse,
    ServiceStatus,
    SeverityDefinitionResponse,
    SeverityMetadataResponse,
    SeverityThresholds,
    SeverityThresholdsUpdateRequest,
    StageLatency,
    StorageCategoryStats,
    StorageStatsResponse,
    SystemStatsResponse,
    TelemetryResponse,
    WebSocketBroadcasterStatus,
    WebSocketHealthResponse,
    WorkerStatus,
)
from backend.core import get_db, get_settings
from backend.core.config import Settings
from backend.core.constants import ANALYSIS_QUEUE, DETECTION_QUEUE
from backend.core.logging import get_logger
from backend.core.redis import (
    QueueOverflowPolicy,
    RedisClient,
    get_redis,
    get_redis_optional,
)
from backend.models import Camera, Detection, Event, GPUStats, Log
from backend.models.audit import AuditAction
from backend.services.audit import AuditService
from backend.services.model_zoo import (
    get_model_config,
    get_model_manager,
    get_model_zoo,
)

logger = get_logger(__name__)

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
_batch_aggregator: BatchAggregator | None = None
_degradation_manager: DegradationManager | None = None


def register_workers(
    gpu_monitor: GPUMonitor | None = None,
    cleanup_service: CleanupService | None = None,
    system_broadcaster: SystemBroadcaster | None = None,
    file_watcher: FileWatcher | None = None,
    pipeline_manager: PipelineWorkerManager | None = None,
    batch_aggregator: BatchAggregator | None = None,
    degradation_manager: DegradationManager | None = None,
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
        batch_aggregator: BatchAggregator instance for pipeline status
        degradation_manager: DegradationManager instance for degradation status
    """
    global _gpu_monitor, _cleanup_service, _system_broadcaster, _file_watcher, _pipeline_manager, _batch_aggregator, _degradation_manager  # noqa: PLW0603
    _gpu_monitor = gpu_monitor
    _cleanup_service = cleanup_service
    _system_broadcaster = system_broadcaster
    _file_watcher = file_watcher
    _pipeline_manager = pipeline_manager
    _batch_aggregator = batch_aggregator
    _degradation_manager = degradation_manager


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
    from backend.services.batch_aggregator import BatchAggregator
    from backend.services.cleanup_service import CleanupService
    from backend.services.degradation_manager import DegradationManager
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

# Maximum concurrent health checks across all requests
# Prevents thundering herd when multiple clients check health simultaneously
MAX_CONCURRENT_HEALTH_CHECKS = 10
_health_check_semaphore = asyncio.Semaphore(MAX_CONCURRENT_HEALTH_CHECKS)


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


async def _bounded_health_check(
    check_func: Any,
    *args: Any,
    timeout_seconds: float = 30.0,
) -> tuple[bool, str | None]:
    """Run a health check with semaphore-bounded concurrency and timeout.

    Limits concurrent health checks across all requests to prevent
    thundering herd when multiple clients check health simultaneously.
    Uses a timeout to prevent indefinite queuing under high load.

    Args:
        check_func: Async function to call for health check
        *args: Arguments to pass to the check function
        timeout_seconds: Maximum time to wait for semaphore acquisition
            and health check execution (default: 30 seconds)

    Returns:
        Tuple of (is_healthy, error_message)
    """
    try:
        async with asyncio.timeout(timeout_seconds):
            async with _health_check_semaphore:
                result: tuple[bool, str | None] = await check_func(*args)
                return result
    except TimeoutError:
        return (False, "Health check timed out waiting for available slot")


async def check_ai_services_health() -> ServiceStatus:
    """Check AI services health by pinging RT-DETR and Nemotron endpoints.

    Performs concurrent health checks on both AI services:
    - RT-DETR (object detection): GET {rtdetr_url}/health
    - Nemotron (LLM reasoning): GET {nemotron_url}/health

    Health checks are bounded by MAX_CONCURRENT_HEALTH_CHECKS semaphore
    to prevent thundering herd when multiple clients check simultaneously.

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
    # Each check is bounded by the semaphore to limit total concurrent checks
    rtdetr_result, nemotron_result = await asyncio.gather(
        _bounded_health_check(
            _check_rtdetr_health_with_circuit_breaker, rtdetr_url, AI_HEALTH_CHECK_TIMEOUT_SECONDS
        ),
        _bounded_health_check(
            _check_nemotron_health_with_circuit_breaker,
            nemotron_url,
            AI_HEALTH_CHECK_TIMEOUT_SECONDS,
        ),
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


# NOTE: /api/system/health/live has been removed to consolidate duplicate endpoints.
# Use GET /health (root level) for liveness probes. It provides the same functionality.


@router.get("/health/ready", response_model=ReadinessResponse)
async def get_readiness(
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient | None = Depends(get_redis_optional),
) -> ReadinessResponse:
    """Kubernetes-style readiness probe endpoint with detailed information.

    This endpoint indicates whether the application is ready to receive
    traffic and process uploads. It checks all critical dependencies:
    - Database connectivity (critical)
    - Redis connectivity (required for queue processing)
    - AI services availability
    - Background worker status

    Note: The canonical readiness probe is GET /ready at the root level.
    This endpoint provides the same readiness check but with detailed
    service and worker status information.

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


@router.get("/health/websocket", response_model=WebSocketHealthResponse)
async def get_websocket_health() -> WebSocketHealthResponse:
    """Get health status of WebSocket broadcasters and their circuit breakers.

    Returns the current state of circuit breakers for:
    - Event broadcaster: Handles real-time security event distribution
    - System broadcaster: Handles system status updates (GPU, cameras, queues)

    Circuit breakers protect the system from cascading failures by:
    - Opening after repeated connection failures
    - Blocking recovery attempts while open to allow stabilization
    - Gradually testing recovery in half-open state

    Circuit breaker states:
    - closed: Normal operation, WebSocket events flowing normally
    - open: Failures detected, events may be delayed or unavailable
    - half_open: Testing recovery, limited operations allowed

    Returns:
        WebSocketHealthResponse with circuit breaker status for both broadcasters
    """
    from backend.services.event_broadcaster import _broadcaster as event_broadcaster
    from backend.services.system_broadcaster import (
        _system_broadcaster as system_broadcaster,
    )

    event_status: WebSocketBroadcasterStatus | None = None
    system_status: WebSocketBroadcasterStatus | None = None

    # Get event broadcaster status
    if event_broadcaster is not None:
        circuit_state = event_broadcaster.get_circuit_state()
        event_status = WebSocketBroadcasterStatus(
            state=CircuitBreakerStateEnum(circuit_state.value),
            failure_count=event_broadcaster.circuit_breaker.failure_count,
            is_degraded=event_broadcaster.is_degraded(),
        )

    # Get system broadcaster status
    if system_broadcaster is not None:
        circuit_state = system_broadcaster.get_circuit_state()
        system_status = WebSocketBroadcasterStatus(
            state=CircuitBreakerStateEnum(circuit_state.value),
            failure_count=system_broadcaster.circuit_breaker.failure_count,
            is_degraded=not system_broadcaster._pubsub_listening,
        )

    return WebSocketHealthResponse(
        event_broadcaster=event_status,
        system_broadcaster=system_status,
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
        grafana_url=settings.grafana_url,
    )


def _runtime_env_path() -> Path:
    """Return the configured runtime override env file path."""
    return Path(os.getenv("HSI_RUNTIME_ENV_PATH", "./data/runtime.env"))


def _write_runtime_env(overrides: dict[str, str]) -> None:
    """Write/merge settings overrides into the runtime env file.

    Uses fsync to guarantee data is written to disk before returning,
    ensuring settings survive process restarts and page refreshes.

    Args:
        overrides: Dictionary of environment variable names to values.
    """
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

    # Write with explicit flush and fsync to ensure persistence
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    logger.info(f"Wrote runtime env to {path}: {overrides}")


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
    logger.info(f"patch_config called with: {update.model_dump()}")
    logger.info(f"Runtime env path: {_runtime_env_path()}")

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

    logger.info(
        f"Settings after update: retention_days={settings.retention_days}, "
        f"batch_window_seconds={settings.batch_window_seconds}, "
        f"detection_confidence_threshold={settings.detection_confidence_threshold}"
    )

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
        grafana_url=settings.grafana_url,
    )


@router.get("/anomaly-config", response_model=AnomalyConfig)
async def get_anomaly_config() -> AnomalyConfig:
    """Get current anomaly detection configuration.

    Returns the current settings for the baseline service including:
    - threshold_stdev: Number of standard deviations for anomaly detection
    - min_samples: Minimum samples required before anomaly detection is reliable
    - decay_factor: Exponential decay factor for EWMA (weights recent observations)
    - window_days: Rolling window size in days for baseline calculations

    Returns:
        AnomalyConfig with current anomaly detection settings
    """
    from backend.services.baseline import get_baseline_service

    service = get_baseline_service()

    return AnomalyConfig(
        threshold_stdev=service.anomaly_threshold_std,
        min_samples=service.min_samples,
        decay_factor=service.decay_factor,
        window_days=service.window_days,
    )


@router.patch(
    "/anomaly-config", response_model=AnomalyConfig, dependencies=[Depends(verify_api_key)]
)
async def update_anomaly_config(
    config_update: AnomalyConfigUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AnomalyConfig:
    """Update anomaly detection configuration.

    Allows updating the anomaly detection thresholds:
    - threshold_stdev: Number of standard deviations for anomaly detection
    - min_samples: Minimum samples required before anomaly detection is reliable

    Note: decay_factor and window_days are not configurable at runtime
    as they affect historical data calculations.

    Requires API key authentication.

    Args:
        config_update: Configuration values to update (only provided values are changed)
        request: HTTP request for audit logging
        db: Database session

    Returns:
        AnomalyConfig with updated settings
    """
    from backend.services.baseline import get_baseline_service

    service = get_baseline_service()

    # Track old values for audit
    old_values: dict[str, Any] = {
        "threshold_stdev": service.anomaly_threshold_std,
        "min_samples": service.min_samples,
    }

    # Update configuration
    try:
        service.update_config(
            threshold_stdev=config_update.threshold_stdev,
            min_samples=config_update.min_samples,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e

    # Track changes
    new_values: dict[str, Any] = {
        "threshold_stdev": service.anomaly_threshold_std,
        "min_samples": service.min_samples,
    }

    changes: dict[str, Any] = {}
    for key, old_value in old_values.items():
        new_value = new_values[key]
        if old_value != new_value:
            changes[key] = {"old": old_value, "new": new_value}

    # Log audit entry
    if changes:
        await AuditService.log_action(
            db=db,
            action=AuditAction.CONFIG_UPDATED,
            resource_type="anomaly_config",
            resource_id="system",
            actor="anonymous",
            details={"changes": changes},
            request=request,
        )
        await db.commit()

    return AnomalyConfig(
        threshold_stdev=service.anomaly_threshold_std,
        min_samples=service.min_samples,
        decay_factor=service.decay_factor,
        window_days=service.window_days,
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
        # Using DROP_OLDEST policy since telemetry data can tolerate data loss
        # while keeping the newest samples is more valuable for monitoring
        result = await redis.add_to_queue_safe(
            key,
            latency_ms,
            max_size=MAX_LATENCY_SAMPLES,
            overflow_policy=QueueOverflowPolicy.DROP_OLDEST,
        )
        if not result.success:
            logger.warning(f"Failed to record latency for stage {stage}: {result.error}")
            return
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
        detection_depth = await redis.get_queue_length(DETECTION_QUEUE)
        analysis_depth = await redis.get_queue_length(ANALYSIS_QUEUE)
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


@router.get("/pipeline-latency/history", response_model=PipelineLatencyHistoryResponse)
async def get_pipeline_latency_history(
    since: int = Query(
        default=60,
        ge=1,
        le=1440,
        description="Number of minutes of history to return (1-1440, i.e., 1 minute to 24 hours)",
    ),
    bucket_seconds: int = Query(
        default=60,
        ge=10,
        le=3600,
        description="Size of each time bucket in seconds (10-3600, i.e., 10 seconds to 1 hour)",
    ),
) -> PipelineLatencyHistoryResponse:
    """Get pipeline latency history for time-series visualization.

    Returns latency data grouped into time buckets for charting.
    Each bucket contains aggregated statistics for all pipeline stages.

    Args:
        since: Number of minutes of history to return (1-1440, default 60)
        bucket_seconds: Size of each time bucket in seconds (10-3600, default 60)

    Returns:
        PipelineLatencyHistoryResponse with chronologically ordered snapshots
    """
    from backend.core.metrics import get_pipeline_latency_tracker

    tracker = get_pipeline_latency_tracker()
    history_data = tracker.get_latency_history(
        window_minutes=since,
        bucket_seconds=bucket_seconds,
    )

    # Convert raw history data to schema format
    snapshots = []
    for snapshot in history_data:
        stages: dict[str, LatencyHistoryStageStats | None] = {}
        for stage_name, stage_stats in snapshot["stages"].items():
            if stage_stats is not None:
                stages[stage_name] = LatencyHistoryStageStats(
                    avg_ms=stage_stats["avg_ms"],
                    p50_ms=stage_stats["p50_ms"],
                    p95_ms=stage_stats["p95_ms"],
                    p99_ms=stage_stats["p99_ms"],
                    sample_count=stage_stats["sample_count"],
                )
            else:
                stages[stage_name] = None

        snapshots.append(
            LatencyHistorySnapshot(
                timestamp=snapshot["timestamp"],
                stages=stages,
            )
        )

    return PipelineLatencyHistoryResponse(
        snapshots=snapshots,
        window_minutes=since,
        bucket_seconds=bucket_seconds,
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


@router.put(
    "/severity", response_model=SeverityMetadataResponse, dependencies=[Depends(verify_api_key)]
)
async def update_severity_thresholds(
    request: Request,
    update: SeverityThresholdsUpdateRequest = Body(...),
    db: AsyncSession = Depends(get_db),
) -> SeverityMetadataResponse:
    """Update severity threshold configuration.

    Updates the risk score thresholds for severity levels. The thresholds
    define how risk scores (0-100) are mapped to severity levels:
    - LOW: 0 to low_max
    - MEDIUM: low_max+1 to medium_max
    - HIGH: medium_max+1 to high_max
    - CRITICAL: high_max+1 to 100

    Requires API key authentication when api_key_enabled is True in settings.
    Provide the API key via X-API-Key header.

    Validation:
    - Thresholds must be strictly ordered: low_max < medium_max < high_max
    - All thresholds must be between 1 and 99
    - This ensures contiguous, non-overlapping ranges covering 0-100

    Note: Changes only affect new events. Existing events retain their
    original severity assignment.

    Args:
        update: New threshold values

    Returns:
        SeverityMetadataResponse with updated definitions and thresholds

    Raises:
        HTTPException 400: If thresholds are not strictly ordered
    """
    from backend.services.severity import get_severity_service, reset_severity_service

    # Validate threshold ordering (must be strictly increasing)
    if not (update.low_max < update.medium_max < update.high_max):
        raise HTTPException(
            status_code=400,
            detail=f"Thresholds must be strictly ordered: low_max ({update.low_max}) < "
            f"medium_max ({update.medium_max}) < high_max ({update.high_max})",
        )

    # Capture old thresholds for audit log
    old_service = get_severity_service()
    old_thresholds = old_service.get_thresholds()

    # Write new thresholds to runtime env file
    overrides = {
        "SEVERITY_LOW_MAX": str(update.low_max),
        "SEVERITY_MEDIUM_MAX": str(update.medium_max),
        "SEVERITY_HIGH_MAX": str(update.high_max),
    }
    _write_runtime_env(overrides)

    # Clear settings cache to pick up new values
    get_settings.cache_clear()

    # Clear severity service cache to create new service with updated thresholds
    reset_severity_service()

    # Get the updated service
    service = get_severity_service()

    # Build audit log changes
    new_thresholds = service.get_thresholds()
    changes: dict[str, dict[str, int]] = {}
    for key in ["low_max", "medium_max", "high_max"]:
        if old_thresholds[key] != new_thresholds[key]:
            changes[key] = {"old": old_thresholds[key], "new": new_thresholds[key]}

    # Log the audit entry
    if changes:
        await AuditService.log_action(
            db=db,
            action=AuditAction.SETTINGS_CHANGED,
            resource_type="severity_thresholds",
            actor="anonymous",
            details={"changes": changes},
            request=request,
        )
        await db.commit()

    logger.info(
        f"Severity thresholds updated: low_max={new_thresholds['low_max']}, "
        f"medium_max={new_thresholds['medium_max']}, high_max={new_thresholds['high_max']}"
    )

    # Get updated severity definitions
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

    return SeverityMetadataResponse(
        definitions=definition_responses,
        thresholds=SeverityThresholds(
            low_max=new_thresholds["low_max"],
            medium_max=new_thresholds["medium_max"],
            high_max=new_thresholds["high_max"],
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


# =============================================================================
# Circuit Breaker Endpoints
# =============================================================================


@router.get("/circuit-breakers", response_model=CircuitBreakersResponse)
async def get_circuit_breakers() -> CircuitBreakersResponse:
    """Get status of all circuit breakers in the system.

    Returns the current state and metrics for each circuit breaker,
    which protect external services from cascading failures.

    Circuit breakers can be in one of three states:
    - CLOSED: Normal operation, calls pass through
    - OPEN: Service failing, calls rejected immediately
    - HALF_OPEN: Testing recovery, limited calls allowed

    Returns:
        CircuitBreakersResponse with status of all circuit breakers
    """
    from backend.services.circuit_breaker import _get_registry

    registry = _get_registry()
    all_status = registry.get_all_status()

    # Convert to response format
    circuit_breakers: dict[str, CircuitBreakerStatusResponse] = {}
    open_count = 0

    for name, status in all_status.items():
        state_value = status.get("state", "closed")
        state = CircuitBreakerStateEnum(state_value)

        if state == CircuitBreakerStateEnum.OPEN:
            open_count += 1

        config = status.get("config", {})
        circuit_breakers[name] = CircuitBreakerStatusResponse(
            name=name,
            state=state,
            failure_count=status.get("failure_count", 0),
            success_count=status.get("success_count", 0),
            total_calls=status.get("total_calls", 0),
            rejected_calls=status.get("rejected_calls", 0),
            last_failure_time=status.get("last_failure_time"),
            opened_at=status.get("opened_at"),
            config=CircuitBreakerConfigResponse(
                failure_threshold=config.get("failure_threshold", 5),
                recovery_timeout=config.get("recovery_timeout", 30.0),
                half_open_max_calls=config.get("half_open_max_calls", 3),
                success_threshold=config.get("success_threshold", 2),
            ),
        )

    return CircuitBreakersResponse(
        circuit_breakers=circuit_breakers,
        total_count=len(circuit_breakers),
        open_count=open_count,
        timestamp=datetime.now(UTC),
    )


@router.post(
    "/circuit-breakers/{name}/reset",
    response_model=CircuitBreakerResetResponse,
    dependencies=[Depends(verify_api_key)],
)
async def reset_circuit_breaker(name: str) -> CircuitBreakerResetResponse:
    """Reset a specific circuit breaker to CLOSED state.

    This manually resets a circuit breaker, clearing failure counts
    and returning it to normal operation. Use this to recover from
    transient failures or after fixing an underlying issue.

    Requires API key authentication when api_key_enabled is True.

    Args:
        name: Name of the circuit breaker to reset

    Returns:
        CircuitBreakerResetResponse with reset confirmation

    Raises:
        HTTPException 400: If name is invalid (empty, too long, or contains invalid characters)
        HTTPException 404: If circuit breaker not found
    """
    from backend.services.circuit_breaker import _get_registry

    # Validate name parameter: must be non-empty and reasonable length
    if not name or len(name) > 64:
        raise HTTPException(
            status_code=400,
            detail="Invalid circuit breaker name: must be 1-64 characters",
        )

    # Only allow alphanumeric characters, underscores, and hyphens (defense in depth)
    if not all(c.isalnum() or c in "_-" for c in name):
        raise HTTPException(
            status_code=400,
            detail="Invalid circuit breaker name: must contain only alphanumeric characters, underscores, or hyphens",
        )

    registry = _get_registry()

    # Validate against registered circuit breaker names
    valid_names = registry.list_names()
    if name not in valid_names:
        if not valid_names:
            raise HTTPException(
                status_code=404,
                detail=f"Circuit breaker '{name}' not found. No circuit breakers are currently registered.",
            )
        raise HTTPException(
            status_code=404,
            detail=f"Circuit breaker '{name}' not found. Valid names: {', '.join(sorted(valid_names))}",
        )

    breaker = registry.get(name)

    # This should never be None due to the validation above, but check for safety
    if breaker is None:
        raise HTTPException(
            status_code=404,
            detail=f"Circuit breaker '{name}' not found",
        )

    previous_state = CircuitBreakerStateEnum(breaker.state.value)
    breaker.reset()
    new_state = CircuitBreakerStateEnum(breaker.state.value)

    logger.info(
        f"Circuit breaker '{name}' manually reset: {previous_state.value} -> {new_state.value}"
    )

    return CircuitBreakerResetResponse(
        name=name,
        previous_state=previous_state,
        new_state=new_state,
        message=f"Circuit breaker '{name}' reset successfully from {previous_state.value} to {new_state.value}",
    )


# =============================================================================
# Cleanup Service Status Endpoint
# =============================================================================


@router.get("/cleanup/status", response_model=CleanupStatusResponse)
async def get_cleanup_status() -> CleanupStatusResponse:
    """Get current status of the cleanup service.

    Returns information about the automated cleanup service including:
    - Whether the service is running
    - Current retention settings
    - Next scheduled cleanup time

    Returns:
        CleanupStatusResponse with cleanup service status
    """
    if _cleanup_service is not None:
        stats = _cleanup_service.get_cleanup_stats()
        return CleanupStatusResponse(
            running=stats.get("running", False),
            retention_days=stats.get("retention_days", 30),
            cleanup_time=stats.get("cleanup_time", "03:00"),
            delete_images=stats.get("delete_images", False),
            next_cleanup=stats.get("next_cleanup"),
            timestamp=datetime.now(UTC),
        )
    else:
        # Return default status if cleanup service is not registered
        settings = get_settings()
        return CleanupStatusResponse(
            running=False,
            retention_days=settings.retention_days,
            cleanup_time="03:00",
            delete_images=False,
            next_cleanup=None,
            timestamp=datetime.now(UTC),
        )


# =============================================================================
# Pipeline Status Endpoint
# =============================================================================


def _decode_redis_value(value: bytes | str | None) -> str | None:
    """Decode a Redis value from bytes or string to string."""
    if value is None:
        return None
    return value.decode() if isinstance(value, bytes) else value


def _parse_detections(detections_data_raw: bytes | str | None) -> list[dict[str, Any]]:
    """Parse detections from raw Redis value."""
    import json

    if not detections_data_raw:
        return []
    detections_data = _decode_redis_value(detections_data_raw)
    if isinstance(detections_data, str):
        parsed: list[dict[str, Any]] = json.loads(detections_data)
        return parsed
    return []


def _build_empty_batch_response(settings: Settings) -> BatchAggregatorStatusResponse:
    """Build an empty batch aggregator status response."""
    return BatchAggregatorStatusResponse(
        active_batches=0,
        batches=[],
        batch_window_seconds=settings.batch_window_seconds,
        idle_timeout_seconds=settings.batch_idle_timeout_seconds,
    )


async def _get_batch_aggregator_status(
    redis: RedisClient | None,
) -> BatchAggregatorStatusResponse | None:
    """Get status of batch aggregator service by querying Redis.

    Uses Redis pipelining to efficiently batch all metadata fetches,
    reducing round-trip overhead when multiple batches are active.

    Args:
        redis: Redis client for batch state queries

    Returns:
        BatchAggregatorStatusResponse or None if service unavailable
    """
    if redis is None or redis._client is None:
        return None

    settings = get_settings()
    current_time = time.time()
    redis_client = redis._client

    try:
        # First pass: collect all batch IDs using scan
        batch_keys: list[str] = []
        async for key in redis_client.scan_iter(match="batch:*:current", count=100):
            batch_keys.append(key)

        if not batch_keys:
            return _build_empty_batch_response(settings)

        # Pipeline batch ID fetches
        pipe = redis_client.pipeline()
        for key in batch_keys:
            pipe.get(key)
        batch_id_results = await pipe.execute()

        # Collect valid batch IDs (filter None and decode)
        batch_ids = [_decode_redis_value(result) for result in batch_id_results if result]
        batch_ids = [bid for bid in batch_ids if bid]  # Filter None values

        if not batch_ids:
            return _build_empty_batch_response(settings)

        # Second pass: pipeline all metadata fetches (4 keys per batch)
        pipe = redis_client.pipeline()
        for batch_id in batch_ids:
            pipe.get(f"batch:{batch_id}:camera_id")
            pipe.get(f"batch:{batch_id}:detections")
            pipe.get(f"batch:{batch_id}:started_at")
            pipe.get(f"batch:{batch_id}:last_activity")
        metadata_results = await pipe.execute()

        # Process results in groups of 4
        active_batches: list[BatchInfoResponse] = []
        for i, batch_id in enumerate(batch_ids):
            try:
                camera_id = _decode_redis_value(metadata_results[i * 4])
                if not camera_id:
                    continue

                detections = _parse_detections(metadata_results[i * 4 + 1])
                started_at_str = _decode_redis_value(metadata_results[i * 4 + 2])
                last_activity_str = _decode_redis_value(metadata_results[i * 4 + 3])

                started_at = float(started_at_str) if started_at_str else current_time
                last_activity = float(last_activity_str) if last_activity_str else started_at

                active_batches.append(
                    BatchInfoResponse(
                        batch_id=batch_id,
                        camera_id=camera_id,
                        detection_count=len(detections),
                        started_at=started_at,
                        age_seconds=round(current_time - started_at, 1),
                        last_activity_seconds=round(current_time - last_activity, 1),
                    )
                )
            except Exception as e:
                logger.warning(f"Error processing batch {batch_id}: {e}", exc_info=True)
                continue

        return BatchAggregatorStatusResponse(
            active_batches=len(active_batches),
            batches=active_batches,
            batch_window_seconds=settings.batch_window_seconds,
            idle_timeout_seconds=settings.batch_idle_timeout_seconds,
        )
    except Exception as e:
        logger.error(f"Error getting batch aggregator status: {e}", exc_info=True)
        return None


def _get_degradation_status() -> DegradationStatusResponse | None:
    """Get status from the global degradation manager.

    Returns:
        DegradationStatusResponse or None if manager not initialized
    """
    if _degradation_manager is None:
        # Try to get the global manager
        from backend.services.degradation_manager import get_degradation_manager

        try:
            manager = get_degradation_manager()
        except Exception:
            return None
    else:
        manager = _degradation_manager

    try:
        status = manager.get_status()

        # Convert services to response format
        services_list: list[ServiceHealthStatusResponse] = []
        services_dict = status.get("services", {})
        for name, health in services_dict.items():
            services_list.append(
                ServiceHealthStatusResponse(
                    name=name,
                    status=health.get("status", "unknown"),
                    last_check=health.get("last_check"),
                    consecutive_failures=health.get("consecutive_failures", 0),
                    error_message=health.get("error_message"),
                )
            )

        return DegradationStatusResponse(
            mode=DegradationModeEnum(status.get("mode", "normal")),
            is_degraded=status.get("is_degraded", False),
            redis_healthy=status.get("redis_healthy", False),
            memory_queue_size=status.get("memory_queue_size", 0),
            fallback_queues=status.get("fallback_queues", {}),
            services=services_list,
            available_features=status.get("available_features", []),
        )
    except Exception as e:
        logger.error(f"Error getting degradation status: {e}", exc_info=True)
        return None


@router.get("/pipeline", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    redis: RedisClient | None = Depends(get_redis_optional),
) -> PipelineStatusResponse:
    """Get combined status of all pipeline operations.

    Returns real-time visibility into the AI processing pipeline:

    **FileWatcher**: Monitors camera directories for new uploads
    - running: Whether the watcher is active
    - camera_root: Directory being watched
    - pending_tasks: Files waiting for debounce completion
    - observer_type: Filesystem observer type (native/polling)

    **BatchAggregator**: Groups detections into time-based batches
    - active_batches: Number of batches being aggregated
    - batches: Details of each active batch
    - batch_window_seconds: Configured window timeout
    - idle_timeout_seconds: Configured idle timeout

    **DegradationManager**: Handles graceful degradation
    - mode: Current degradation mode (normal/degraded/minimal/offline)
    - is_degraded: Whether system is in any degraded state
    - services: Health status of registered services
    - available_features: Features available in current mode

    Returns:
        PipelineStatusResponse with status of all pipeline services
    """
    # Get FileWatcher status
    file_watcher_status: FileWatcherStatusResponse | None = None
    if _file_watcher is not None:
        observer_type = "polling" if getattr(_file_watcher, "_use_polling", False) else "native"
        file_watcher_status = FileWatcherStatusResponse(
            running=getattr(_file_watcher, "running", False),
            camera_root=getattr(_file_watcher, "camera_root", ""),
            pending_tasks=len(getattr(_file_watcher, "_pending_tasks", {})),
            observer_type=observer_type,
        )

    # Get BatchAggregator status from Redis
    batch_aggregator_status = await _get_batch_aggregator_status(redis)

    # Get DegradationManager status
    degradation_status = _get_degradation_status()

    return PipelineStatusResponse(
        file_watcher=file_watcher_status,
        batch_aggregator=batch_aggregator_status,
        degradation=degradation_status,
        timestamp=datetime.now(UTC),
    )


# =============================================================================
# Model Zoo Endpoints
# =============================================================================

# VRAM budget for Model Zoo (excludes RT-DETRv2 and Nemotron allocations)
MODEL_ZOO_VRAM_BUDGET_MB = 1650


def _get_model_display_name(name: str) -> str:
    """Generate a human-readable display name from model identifier.

    Args:
        name: Model identifier (e.g., 'yolo11-license-plate')

    Returns:
        Human-readable name (e.g., 'YOLO11 License Plate')
    """
    # Mapping of known models to display names
    display_names: dict[str, str] = {
        "yolo11-license-plate": "YOLO11 License Plate",
        "yolo11-face": "YOLO11 Face Detection",
        "paddleocr": "PaddleOCR",
        "yolo26-general": "YOLO26 General Detection",
        "clip_embedder": "CLIP ViT-L/14",
        "yolo-world-s": "YOLO-World Small",
        "depth-anything-v2-small": "Depth Anything V2 Small",
        "vitpose-small": "ViTPose Small",
    }

    if name in display_names:
        return display_names[name]

    # Generate display name from identifier
    # Replace hyphens with spaces and capitalize
    return name.replace("-", " ").replace("_", " ").title()


def _model_config_to_status(
    name: str,
    manager_loaded_models: list[str],
    manager_load_counts: dict[str, int],
) -> ModelStatusResponse:
    """Convert a ModelConfig to ModelStatusResponse.

    Args:
        name: Model name
        manager_loaded_models: List of currently loaded model names
        manager_load_counts: Dictionary of model load counts

    Returns:
        ModelStatusResponse with current status
    """
    config = get_model_config(name)
    if config is None:
        raise ValueError(f"Model '{name}' not found in registry")

    # Determine status
    if not config.enabled:
        status = ModelStatusEnum.DISABLED
    elif name in manager_loaded_models:
        status = ModelStatusEnum.LOADED
    else:
        status = ModelStatusEnum.UNLOADED

    return ModelStatusResponse(
        name=config.name,
        display_name=_get_model_display_name(config.name),
        vram_mb=config.vram_mb,
        status=status,
        category=config.category,
        enabled=config.enabled,
        available=config.available,
        path=config.path,
        load_count=manager_load_counts.get(name, 0),
    )


@router.get(
    "/models",
    response_model=ModelRegistryResponse,
    summary="Get Model Zoo Registry",
)
async def get_models() -> ModelRegistryResponse:
    """Get the current status of all models in the Model Zoo.

    Returns comprehensive information about all AI models available in the system,
    including their VRAM requirements, loading status, and configuration.

    **VRAM Budget**: The Model Zoo has a dedicated VRAM budget of 1650 MB,
    separate from the RT-DETRv2 detector and Nemotron LLM allocations.

    **Loading Strategy**: Models are loaded sequentially (one at a time) to
    prevent VRAM fragmentation and ensure stable operation.

    **Model Categories**:
    - detection: Object detection models (YOLO variants)
    - recognition: Face and license plate recognition
    - ocr: Optical character recognition
    - embedding: Visual embedding models (CLIP)
    - depth-estimation: Depth estimation models
    - pose: Human pose estimation

    Returns:
        ModelRegistryResponse with VRAM stats and all model statuses
    """
    manager = get_model_manager()
    zoo = get_model_zoo()

    # Get current VRAM usage
    vram_used = manager.total_loaded_vram

    # Build model status list
    models: list[ModelStatusResponse] = []
    for model_name in zoo:
        try:
            status = _model_config_to_status(
                model_name,
                manager.loaded_models,
                manager._load_counts,
            )
            models.append(status)
        except ValueError:
            # Skip invalid models
            continue

    return ModelRegistryResponse(
        vram_budget_mb=MODEL_ZOO_VRAM_BUDGET_MB,
        vram_used_mb=vram_used,
        vram_available_mb=MODEL_ZOO_VRAM_BUDGET_MB - vram_used,
        models=models,
        loading_strategy="sequential",
        max_concurrent_models=1,
    )


@router.get(
    "/models/{model_name}",
    response_model=ModelStatusResponse,
    summary="Get Model Status",
)
async def get_model(model_name: str) -> ModelStatusResponse:
    """Get detailed status information for a specific model.

    Args:
        model_name: Unique identifier of the model (e.g., 'yolo11-license-plate')

    Returns:
        ModelStatusResponse with detailed model information

    Raises:
        HTTPException: 404 if model not found in registry
    """
    config = get_model_config(model_name)
    if config is None:
        raise HTTPException(
            status_code=404,
            detail=f"Model '{model_name}' not found in registry",
        )

    manager = get_model_manager()

    return _model_config_to_status(
        model_name,
        manager.loaded_models,
        manager._load_counts,
    )


# =============================================================================
# Model Zoo Status and Latency Endpoints
# =============================================================================

# Model category mapping for dropdown grouping
MODEL_CATEGORIES: dict[str, list[str]] = {
    "Detection": [
        "yolo11-license-plate",
        "yolo11-face",
        "yolo-world-s",
        "vehicle-damage-detection",
    ],
    "Classification": [
        "violence-detection",
        "weather-classification",
        "fashion-clip",
        "vehicle-segment-classification",
        "pet-classifier",
    ],
    "Segmentation": ["segformer-b2-clothes"],
    "Pose": ["vitpose-small"],
    "Depth": ["depth-anything-v2-small"],
    "Embedding": ["clip-vit-l"],
    "OCR": ["paddleocr"],
    "Action Recognition": ["xclip-base"],
}

# Disabled models that should appear at the bottom of the dropdown
DISABLED_MODELS = ["florence-2-large", "brisque-quality", "yolo26-general"]

# Redis key prefix for model zoo latency data
MODEL_ZOO_LATENCY_KEY_PREFIX = "model_zoo:latency:"
MODEL_ZOO_LATENCY_TTL_SECONDS = 86400  # Keep data for 24 hours


def _get_model_category(model_name: str) -> str:
    """Get the category for a model.

    Args:
        model_name: Model identifier

    Returns:
        Category name (e.g., 'Detection', 'Classification')
    """
    for category, models in MODEL_CATEGORIES.items():
        if model_name in models:
            return category
    return "Other"


@router.get(
    "/model-zoo/status",
    response_model=ModelZooStatusResponse,
    summary="Get Model Zoo Status",
)
async def get_model_zoo_status() -> ModelZooStatusResponse:
    """Get status information for all Model Zoo models.

    Returns status information for all 18 Model Zoo models, including:
    - Current status (loaded, unloaded, disabled)
    - VRAM usage when loaded
    - Last usage timestamp
    - Category grouping for UI display

    This endpoint is optimized for the compact status card display
    in the AI Performance page.

    Returns:
        ModelZooStatusResponse with all model statuses
    """
    manager = get_model_manager()
    zoo = get_model_zoo()

    models: list[ModelZooStatusItem] = []
    loaded_count = 0
    disabled_count = 0

    for model_name, config in zoo.items():
        # Determine status
        if not config.enabled:
            status = ModelStatusEnum.DISABLED
            disabled_count += 1
        elif model_name in manager.loaded_models:
            status = ModelStatusEnum.LOADED
            loaded_count += 1
        else:
            status = ModelStatusEnum.UNLOADED

        # Get category
        category = _get_model_category(model_name)

        models.append(
            ModelZooStatusItem(
                name=config.name,
                display_name=_get_model_display_name(config.name),
                category=category,
                status=status,
                vram_mb=config.vram_mb,
                last_used_at=None,  # TODO: Track last usage time
                enabled=config.enabled,
            )
        )

    # Sort models: enabled first (by category), then disabled
    enabled_models = [m for m in models if m.enabled]
    disabled_models_list = [m for m in models if not m.enabled]

    # Sort enabled by category, then by name
    category_order = [*list(MODEL_CATEGORIES.keys()), "Other"]
    enabled_models.sort(
        key=lambda m: (
            category_order.index(m.category) if m.category in category_order else 999,
            m.name,
        )
    )

    sorted_models = enabled_models + disabled_models_list

    return ModelZooStatusResponse(
        models=sorted_models,
        total_models=len(models),
        loaded_count=loaded_count,
        disabled_count=disabled_count,
        vram_budget_mb=MODEL_ZOO_VRAM_BUDGET_MB,
        vram_used_mb=manager.total_loaded_vram,
        timestamp=datetime.now(UTC),
    )


@router.get(
    "/model-zoo/latency/history",
    response_model=ModelLatencyHistoryResponse,
    summary="Get Model Zoo Latency History",
)
async def get_model_zoo_latency_history(
    model: str = Query(
        ...,
        description="Model name to get latency history for (e.g., 'yolo11-license-plate')",
    ),
    since: int = Query(
        default=60,
        ge=1,
        le=1440,
        description="Number of minutes of history to return (1-1440, i.e., 1 minute to 24 hours)",
    ),
    bucket_seconds: int = Query(
        default=60,
        ge=10,
        le=3600,
        description="Size of each time bucket in seconds (10-3600, i.e., 10 seconds to 1 hour)",
    ),
) -> ModelLatencyHistoryResponse:
    """Get latency history for a specific Model Zoo model.

    Returns time-series latency data for the dropdown-controlled chart.
    Each bucket contains aggregated statistics (avg, p50, p95).

    Args:
        model: Model name to get history for
        since: Number of minutes of history to return (default 60)
        bucket_seconds: Size of each time bucket in seconds (default 60)

    Returns:
        ModelLatencyHistoryResponse with chronologically ordered snapshots

    Raises:
        HTTPException: 404 if model not found in registry
    """
    config = get_model_config(model)
    if config is None:
        raise HTTPException(
            status_code=404,
            detail=f"Model '{model}' not found in registry",
        )

    # Get latency history from the metrics tracker if available
    from backend.core.metrics import get_model_latency_tracker

    tracker = get_model_latency_tracker()
    if tracker is not None:
        history_data = tracker.get_model_latency_history(
            model_name=model,
            window_minutes=since,
            bucket_seconds=bucket_seconds,
        )
    else:
        # Return empty history if tracker not available
        history_data = []

    # Build snapshots
    snapshots: list[ModelLatencyHistorySnapshot] = []
    has_data = False

    for snapshot in history_data:
        stats = snapshot.get("stats")
        if stats is not None:
            has_data = True
            snapshots.append(
                ModelLatencyHistorySnapshot(
                    timestamp=snapshot["timestamp"],
                    stats=ModelLatencyStageStats(
                        avg_ms=stats["avg_ms"],
                        p50_ms=stats["p50_ms"],
                        p95_ms=stats["p95_ms"],
                        sample_count=stats["sample_count"],
                    ),
                )
            )
        else:
            snapshots.append(
                ModelLatencyHistorySnapshot(
                    timestamp=snapshot["timestamp"],
                    stats=None,
                )
            )

    return ModelLatencyHistoryResponse(
        model_name=model,
        display_name=_get_model_display_name(model),
        snapshots=snapshots,
        window_minutes=since,
        bucket_seconds=bucket_seconds,
        has_data=has_data,
        timestamp=datetime.now(UTC),
    )
