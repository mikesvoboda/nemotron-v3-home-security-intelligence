"""System monitoring and configuration API endpoints."""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import shutil
import tempfile
import time
from collections.abc import AsyncGenerator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
from fastapi import (
    APIRouter,
    Body,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import ORJSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_baseline_service_dep
from backend.api.middleware import RateLimiter, RateLimitTier
from backend.api.schemas.baseline import (
    AnomalyConfig,
    AnomalyConfigUpdate,
)
from backend.api.schemas.health import (
    AIServiceHealthStatus,
    CircuitBreakerSummary,
    CircuitState,
    FullHealthResponse,
    InfrastructureHealthStatus,
    ServiceHealthState,
    WorkerHealthStatus,
)
from backend.api.schemas.pagination import create_pagination_meta
from backend.api.schemas.performance import (
    PerformanceHistoryResponse,
    PerformanceUpdate,
    TimeRange,
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
    ExporterStatus,
    ExporterStatusEnum,
    FileWatcherStatusResponse,
    GPUStatsHistoryResponse,
    GPUStatsResponse,
    HealthCheckServiceStatus,
    HealthEventResponse,
    HealthResponse,
    JobTargetSummary,
    LatencyHistorySnapshot,
    LatencyHistoryStageStats,
    MetricsCollectionStatus,
    ModelLatencyHistoryResponse,
    ModelLatencyHistorySnapshot,
    ModelLatencyStageStats,
    ModelRegistryResponse,
    ModelStatusEnum,
    ModelStatusResponse,
    ModelZooStatusItem,
    ModelZooStatusResponse,
    MonitoringHealthResponse,
    MonitoringTargetsResponse,
    OrphanedFileCleanupResponse,
    PipelineLatencies,
    PipelineLatencyHistoryResponse,
    PipelineLatencyResponse,
    PipelineStageLatency,
    PipelineStatusResponse,
    QueueDepths,
    ReadinessResponse,
    RestartHistoryEvent,
    RestartHistoryResponse,
    ServiceHealthStatusResponse,
    SeverityDefinitionResponse,
    SeverityMetadataResponse,
    SeverityThresholds,
    SeverityThresholdsUpdateRequest,
    StageLatency,
    StorageCategoryStats,
    StorageStatsResponse,
    SupervisedWorkerInfo,
    SupervisedWorkerStatusEnum,
    SystemStatsResponse,
    TargetHealth,
    TelemetryResponse,
    WebSocketBroadcasterStatus,
    WebSocketHealthResponse,
    WorkerControlResponse,
    WorkerStatus,
    WorkerSupervisorStatusResponse,
)
from backend.api.schemas.websocket import (
    EventRegistryResponse,
    get_event_registry_response,
)
from backend.core import get_db, get_settings
from backend.core.config import Settings
from backend.core.constants import ANALYSIS_QUEUE, DETECTION_QUEUE
from backend.core.logging import get_logger, sanitize_log_value
from backend.core.redis import (
    QueueOverflowPolicy,
    RedisClient,
    get_redis,
    get_redis_optional,
)
from backend.models import Camera, Detection, Event, GPUStats, Log
from backend.models.audit import AuditAction
from backend.models.event_audit import EventAudit
from backend.services.audit import AuditService
from backend.services.baseline import BaselineService
from backend.services.health_event_emitter import get_health_event_emitter
from backend.services.model_zoo import (
    get_model_config,
    get_model_manager,
    get_model_zoo,
)

# Type alias for dependency injection
BaselineServiceDep = BaselineService

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/system",
    tags=["system"],
    default_response_class=ORJSONResponse,
)


# =============================================================================
# Circuit Breaker for Health Checks
# =============================================================================


@dataclass(slots=True)
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
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Provide via X-API-Key header.",
        )

    # Hash and validate the API key
    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
    # Support SecretStr for api_keys
    valid_hashes = set()
    for k in settings.api_keys:
        key_value: str = k.get_secret_value() if hasattr(k, "get_secret_value") else str(k)
        valid_hashes.add(hashlib.sha256(key_value.encode()).hexdigest())

    if key_hash not in valid_hashes:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


# Track application start time for uptime calculation
_app_start_time = time.time()

# =============================================================================
# Health Check Timeouts (NEM-3892)
# =============================================================================
# Optimized timeouts to ensure health endpoints respond under 500ms SLO.
# Individual component timeouts allow parallel checks to fail fast.

# Overall timeout for the entire health check (must be under 500ms)
HEALTH_CHECK_OVERALL_TIMEOUT_SECONDS = 0.4  # 400ms allows 100ms buffer

# Individual component timeouts (run in parallel)
# These should be shorter than overall timeout since they run concurrently
HEALTH_CHECK_DB_TIMEOUT_SECONDS = 0.3  # Database ping should be fast
HEALTH_CHECK_REDIS_TIMEOUT_SECONDS = 0.3  # Redis ping should be fast
HEALTH_CHECK_AI_TIMEOUT_SECONDS = 0.3  # AI service health check

# Legacy timeout (kept for backwards compatibility with existing code)
HEALTH_CHECK_TIMEOUT_SECONDS = 5.0

# =============================================================================
# Health Check Response Cache
# =============================================================================
# Cache health check results to reduce load from frequent health probes.
# With caching, most requests return instantly from cache, and only cache
# misses trigger the parallel health checks.

HEALTH_CACHE_TTL_SECONDS = 10.0  # Increased from 5s to reduce check frequency


@dataclass(slots=True)
class HealthCacheEntry:
    """Cached health check response with TTL tracking.

    Attributes:
        response: The cached HealthResponse
        cached_at: Timestamp when the response was cached
        http_status: The HTTP status code to return (200 or 503)
    """

    response: HealthResponse
    cached_at: float
    http_status: int

    def is_valid(self) -> bool:
        """Check if the cached entry is still within TTL."""
        return (time.time() - self.cached_at) < HEALTH_CACHE_TTL_SECONDS


# Global cache for health check responses
_health_cache: HealthCacheEntry | None = None


@dataclass(slots=True)
class ReadinessCacheEntry:
    """Cached readiness check response with TTL tracking."""

    response: ReadinessResponse
    cached_at: float
    http_status: int

    def is_valid(self) -> bool:
        """Check if the cached entry is still within TTL."""
        return (time.time() - self.cached_at) < HEALTH_CACHE_TTL_SECONDS


@dataclass(slots=True)
class GPUStatsCacheEntry:
    """Cached GPU stats response with TTL tracking."""

    response: GPUStatsResponse
    cached_at: float

    def is_valid(self) -> bool:
        """Check if the cached entry is still within TTL (use 5s for GPU stats)."""
        return (time.time() - self.cached_at) < HEALTH_CACHE_TTL_SECONDS


@dataclass(slots=True)
class SystemStatsCacheEntry:
    """Cached system stats response with TTL tracking."""

    response: SystemStatsResponse
    cached_at: float

    def is_valid(self) -> bool:
        """Check if the cached entry is still within TTL (use 5s for stats)."""
        return (time.time() - self.cached_at) < HEALTH_CACHE_TTL_SECONDS


# Global caches for various endpoints
_readiness_cache: ReadinessCacheEntry | None = None
_gpu_stats_cache: GPUStatsCacheEntry | None = None
_system_stats_cache: SystemStatsCacheEntry | None = None


def clear_health_cache() -> None:
    """Clear all health check caches.

    This is primarily for testing purposes to ensure tests don't see
    stale cached results from previous test runs.
    """
    global _health_cache, _readiness_cache, _gpu_stats_cache, _system_stats_cache  # noqa: PLW0603
    _health_cache = None
    _readiness_cache = None
    _gpu_stats_cache = None
    _system_stats_cache = None


# Global references for worker status tracking (set by main.py at startup)
_gpu_monitor: GPUMonitor | None = None
_cleanup_service: CleanupService | None = None
_system_broadcaster: SystemBroadcaster | None = None
_file_watcher: FileWatcher | None = None
_pipeline_manager: PipelineWorkerManager | None = None
_batch_aggregator: BatchAggregator | None = None
_degradation_manager: DegradationManager | None = None
_service_health_monitor: ServiceHealthMonitor | None = None
_performance_collector: PerformanceCollector | None = None
_worker_supervisor: WorkerSupervisor | None = None  # NEM-2457


def register_workers(
    gpu_monitor: GPUMonitor | None = None,
    cleanup_service: CleanupService | None = None,
    system_broadcaster: SystemBroadcaster | None = None,
    file_watcher: FileWatcher | None = None,
    pipeline_manager: PipelineWorkerManager | None = None,
    batch_aggregator: BatchAggregator | None = None,
    degradation_manager: DegradationManager | None = None,
    service_health_monitor: ServiceHealthMonitor | None = None,
    performance_collector: PerformanceCollector | None = None,
    worker_supervisor: WorkerSupervisor | None = None,
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
        service_health_monitor: ServiceHealthMonitor instance for health event history
        performance_collector: PerformanceCollector instance for performance metrics
        worker_supervisor: WorkerSupervisor instance for worker auto-recovery (NEM-2457)
    """
    global _gpu_monitor, _cleanup_service, _system_broadcaster, _file_watcher, _pipeline_manager, _batch_aggregator, _degradation_manager, _service_health_monitor, _performance_collector, _worker_supervisor  # noqa: PLW0603
    _gpu_monitor = gpu_monitor
    _cleanup_service = cleanup_service
    _system_broadcaster = system_broadcaster
    _file_watcher = file_watcher
    _pipeline_manager = pipeline_manager
    _batch_aggregator = batch_aggregator
    _degradation_manager = degradation_manager
    _service_health_monitor = service_health_monitor
    _performance_collector = performance_collector
    _worker_supervisor = worker_supervisor


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

        # Batch timeout worker (also report as batch_aggregator for frontend compatibility)
        if "timeout" in workers_dict:
            timeout_state = workers_dict["timeout"].get("state", "stopped")
            is_running = timeout_state == "running"
            message = None if is_running else f"State: {timeout_state}"

            # Add as batch_timeout_worker
            statuses.append(
                WorkerStatus(
                    name="batch_timeout_worker",
                    running=is_running,
                    message=message,
                )
            )

            # Also add as batch_aggregator (frontend expects this name)
            statuses.append(
                WorkerStatus(
                    name="batch_aggregator",
                    running=is_running,
                    message=message,
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


def _get_supervisor_health() -> bool:
    """Check if the worker supervisor is healthy.

    Returns:
        True if supervisor is healthy (running with no failed workers),
        or if no supervisor is registered (not required for basic operation).
    """
    if _worker_supervisor is None:
        return True

    if not _worker_supervisor.is_running:
        return False

    # Check if any workers have exceeded restart limit
    for worker_info in _worker_supervisor.get_all_workers().values():
        if worker_info.status.value == "failed":
            return False

    return True


# Type hints for worker imports (avoid circular imports)
if TYPE_CHECKING:
    from backend.services.batch_aggregator import BatchAggregator
    from backend.services.cleanup_service import CleanupService
    from backend.services.degradation_manager import DegradationManager
    from backend.services.file_watcher import FileWatcher
    from backend.services.gpu_monitor import GPUMonitor
    from backend.services.health_monitor import ServiceHealthMonitor
    from backend.services.performance_collector import PerformanceCollector
    from backend.services.pipeline_workers import PipelineWorkerManager
    from backend.services.system_broadcaster import SystemBroadcaster
    from backend.services.worker_supervisor import WorkerSupervisor


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
        # Extended metrics
        "fan_speed": gpu_stat.fan_speed,
        "sm_clock": gpu_stat.sm_clock,
        "memory_bandwidth_utilization": gpu_stat.memory_bandwidth_utilization,
        "pstate": gpu_stat.pstate,
        # High-value metrics
        "throttle_reasons": gpu_stat.throttle_reasons,
        "power_limit": gpu_stat.power_limit,
        "sm_clock_max": gpu_stat.sm_clock_max,
        "compute_processes_count": gpu_stat.compute_processes_count,
        "pcie_replay_counter": gpu_stat.pcie_replay_counter,
        "temp_slowdown_threshold": gpu_stat.temp_slowdown_threshold,
        # Medium-value metrics
        "memory_clock": gpu_stat.memory_clock,
        "memory_clock_max": gpu_stat.memory_clock_max,
        "pcie_link_gen": gpu_stat.pcie_link_gen,
        "pcie_link_width": gpu_stat.pcie_link_width,
        "pcie_tx_throughput": gpu_stat.pcie_tx_throughput,
        "pcie_rx_throughput": gpu_stat.pcie_rx_throughput,
        "encoder_utilization": gpu_stat.encoder_utilization,
        "decoder_utilization": gpu_stat.decoder_utilization,
        "bar1_used": gpu_stat.bar1_used,
    }


async def check_database_health(db: AsyncSession) -> HealthCheckServiceStatus:
    """Check database connectivity and health.

    Args:
        db: Database session

    Returns:
        HealthCheckServiceStatus with database health information including pool status
    """
    from backend.core.database import get_pool_status

    try:
        # Execute a simple query to verify database connectivity
        result = await db.execute(select(func.count()).select_from(Camera))
        result.scalar_one()

        # Get connection pool status for monitoring
        pool_status = await get_pool_status()

        return HealthCheckServiceStatus(
            status="healthy",
            message="Database operational",
            details={
                "pool": {
                    "size": pool_status.get("pool_size", 0),
                    "overflow": pool_status.get("overflow", 0),
                    "checkedin": pool_status.get("checkedin", 0),
                    "checkedout": pool_status.get("checkedout", 0),
                    "total_connections": pool_status.get("total_connections", 0),
                }
            },
        )
    except (ConnectionError, TimeoutError, OSError, RuntimeError) as e:
        # Database connection and query failures
        return HealthCheckServiceStatus(
            status="unhealthy",
            message=f"Database error: {e!s}",
            details=None,
        )


async def check_redis_health(redis: RedisClient | None) -> HealthCheckServiceStatus:
    """Check Redis connectivity and health.

    Args:
        redis: Redis client (may be None if connection failed during dependency injection)

    Returns:
        HealthCheckServiceStatus with Redis health information
    """
    # Handle case where Redis client is None (connection failed during DI)
    if redis is None:
        return HealthCheckServiceStatus(
            status="unhealthy",
            message="Redis unavailable: connection failed",
            details=None,
        )

    try:
        health = await redis.health_check()
        if health.get("status") == "healthy":
            return HealthCheckServiceStatus(
                status="healthy",
                message="Redis connected",
                details={"redis_version": health.get("redis_version", "unknown")},
            )
        else:
            return HealthCheckServiceStatus(
                status="unhealthy",
                message=health.get("error", "Redis connection error"),
                details=None,
            )
    except (ConnectionError, TimeoutError, OSError) as e:
        # Redis connection failures
        return HealthCheckServiceStatus(
            status="unhealthy",
            message=f"Redis error: {e!s}",
            details=None,
        )


async def _check_yolo26_health(yolo26_url: str, timeout: float) -> tuple[bool, str | None]:
    """Check YOLO26 object detection service health.

    Args:
        yolo26_url: Base URL for YOLO26 service
        timeout: Request timeout in seconds

    Returns:
        Tuple of (is_healthy, error_message)
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{yolo26_url}/health")
            response.raise_for_status()
            return True, None
    except httpx.ConnectError:
        return False, "YOLO26 service connection refused"
    except httpx.TimeoutException:
        return False, "YOLO26 service request timed out"
    except httpx.HTTPStatusError as e:
        return False, f"YOLO26 service returned HTTP {e.response.status_code}"
    except (OSError, RuntimeError) as e:
        # Network-level failures
        return False, f"YOLO26 service error: {e!s}"


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
    except (OSError, RuntimeError) as e:
        # Network-level failures
        return False, f"Nemotron service error: {e!s}"


# Timeout for individual AI service health checks (in seconds)
AI_HEALTH_CHECK_TIMEOUT_SECONDS = 3.0

# Maximum concurrent health checks across all requests
# Prevents thundering herd when multiple clients check health simultaneously
MAX_CONCURRENT_HEALTH_CHECKS = 10
_health_check_semaphore = asyncio.Semaphore(MAX_CONCURRENT_HEALTH_CHECKS)


async def _check_yolo26_health_with_circuit_breaker(
    yolo26_url: str, timeout: float
) -> tuple[bool, str | None]:
    """Check YOLO26 health with circuit breaker protection.

    If the circuit is open (service repeatedly failing), returns cached error
    immediately without making network call. Otherwise performs health check
    and records result in circuit breaker.

    Args:
        yolo26_url: Base URL for YOLO26 service
        timeout: Request timeout in seconds

    Returns:
        Tuple of (is_healthy, error_message)
    """
    service_name = "yolo26"

    # Check if circuit is open (service is down, skip the check)
    if _health_circuit_breaker.is_open(service_name):
        cached_error = _health_circuit_breaker.get_cached_error(service_name)
        return False, cached_error or "YOLO26 service unavailable (circuit open)"

    # Circuit is closed, perform actual health check
    is_healthy, error_msg = await _check_yolo26_health(yolo26_url, timeout)

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


async def check_ai_services_health() -> HealthCheckServiceStatus:
    """Check AI services health by pinging YOLO26 and Nemotron endpoints.

    Performs concurrent health checks on both AI services:
    - YOLO26 (object detection): GET {yolo26_url}/health
    - Nemotron (LLM reasoning): GET {nemotron_url}/health

    Health checks are bounded by MAX_CONCURRENT_HEALTH_CHECKS semaphore
    to prevent thundering herd when multiple clients check simultaneously.

    Returns:
        HealthCheckServiceStatus with AI services health information:
        - healthy: Both services are responding
        - degraded: At least one service is down but some AI capability remains
        - unhealthy: Both services are down (no AI capability)
    """
    settings = get_settings()
    yolo26_url = settings.yolo26_url
    nemotron_url = settings.nemotron_url

    # Check both services concurrently with circuit breaker protection
    # Each check is bounded by the semaphore to limit total concurrent checks
    yolo26_result, nemotron_result = await asyncio.gather(
        _bounded_health_check(
            _check_yolo26_health_with_circuit_breaker, yolo26_url, AI_HEALTH_CHECK_TIMEOUT_SECONDS
        ),
        _bounded_health_check(
            _check_nemotron_health_with_circuit_breaker,
            nemotron_url,
            AI_HEALTH_CHECK_TIMEOUT_SECONDS,
        ),
    )

    yolo26_healthy, yolo26_error = yolo26_result
    nemotron_healthy, nemotron_error = nemotron_result

    # Build details dict with individual service status
    details: dict[str, str] = {
        "yolo26": "healthy" if yolo26_healthy else (yolo26_error or "unknown error"),
        "nemotron": "healthy" if nemotron_healthy else (nemotron_error or "unknown error"),
    }

    # Determine overall AI status
    if yolo26_healthy and nemotron_healthy:
        return HealthCheckServiceStatus(
            status="healthy",
            message="AI services operational",
            details=details,
        )
    elif yolo26_healthy or nemotron_healthy:
        # At least one service is up - degraded but partially functional
        working_service = "YOLO26" if yolo26_healthy else "Nemotron"
        failed_service = "Nemotron" if yolo26_healthy else "YOLO26"
        return HealthCheckServiceStatus(
            status="degraded",
            message=f"{failed_service} service unavailable, {working_service} operational",
            details=details,
        )
    else:
        # Both services are down
        return HealthCheckServiceStatus(
            status="unhealthy",
            message="All AI services unavailable",
            details=details,
        )


async def _emit_health_status_changes(
    db_status: str,
    redis_status: str,
    ai_status: str,
    db_details: dict[str, Any] | None = None,
    redis_details: dict[str, Any] | None = None,
    ai_details: dict[str, Any] | None = None,
) -> None:
    """Emit WebSocket events for health status changes.

    This helper function tracks health state transitions and only emits
    WebSocket events when status actually changes. This prevents flooding
    clients with duplicate events on each health check.

    The health event emitter maintains previous state and handles the
    logic for detecting transitions.

    Args:
        db_status: Current database health status
        redis_status: Current Redis health status
        ai_status: Current AI services health status
        db_details: Optional database health details
        redis_details: Optional Redis health details
        ai_details: Optional AI services health details
    """
    try:
        health_emitter = get_health_event_emitter()

        # Try to set up the WebSocket emitter if not already configured
        if health_emitter._emitter is None:
            from backend.services.websocket_emitter import get_websocket_emitter_sync

            ws_emitter = get_websocket_emitter_sync()
            if ws_emitter is not None:
                health_emitter.set_emitter(ws_emitter)

        # Update all component statuses (emits events only on changes)
        await health_emitter.update_all_components(
            statuses={
                "database": db_status,
                "redis": redis_status,
                "ai_service": ai_status,
            },
            details={
                "database": db_details or {},
                "redis": redis_details or {},
                "ai_service": ai_details or {},
            },
        )

    except Exception as e:
        # Don't let health event emission failures break health checks
        logger.warning(f"Failed to emit health status change events: {e}", exc_info=True)


async def _check_db_health_with_timeout(
    db: AsyncSession,
) -> HealthCheckServiceStatus:
    """Check database health with timeout and metrics.

    Args:
        db: Database session

    Returns:
        HealthCheckServiceStatus for the database
    """
    from backend.core.metrics import observe_health_check_component_latency

    start_time = time.time()
    try:
        result = await asyncio.wait_for(
            check_database_health(db),
            timeout=HEALTH_CHECK_DB_TIMEOUT_SECONDS,
        )
        duration = time.time() - start_time
        observe_health_check_component_latency("database", duration)
        return result
    except TimeoutError:
        duration = time.time() - start_time
        observe_health_check_component_latency("database", duration)
        return HealthCheckServiceStatus(
            status="unhealthy",
            message=f"Database health check timed out after {HEALTH_CHECK_DB_TIMEOUT_SECONDS}s",
            details=None,
        )


async def _check_redis_health_with_timeout(
    redis: RedisClient | None,
) -> HealthCheckServiceStatus:
    """Check Redis health with timeout and metrics.

    Args:
        redis: Redis client or None

    Returns:
        HealthCheckServiceStatus for Redis
    """
    from backend.core.metrics import observe_health_check_component_latency

    start_time = time.time()
    try:
        result = await asyncio.wait_for(
            check_redis_health(redis),
            timeout=HEALTH_CHECK_REDIS_TIMEOUT_SECONDS,
        )
        duration = time.time() - start_time
        observe_health_check_component_latency("redis", duration)
        return result
    except TimeoutError:
        duration = time.time() - start_time
        observe_health_check_component_latency("redis", duration)
        return HealthCheckServiceStatus(
            status="unhealthy",
            message=f"Redis health check timed out after {HEALTH_CHECK_REDIS_TIMEOUT_SECONDS}s",
            details=None,
        )


async def _check_ai_health_with_timeout() -> HealthCheckServiceStatus:
    """Check AI services health with timeout and metrics.

    Returns:
        HealthCheckServiceStatus for AI services
    """
    from backend.core.metrics import observe_health_check_component_latency

    start_time = time.time()
    try:
        result = await asyncio.wait_for(
            check_ai_services_health(),
            timeout=HEALTH_CHECK_AI_TIMEOUT_SECONDS,
        )
        duration = time.time() - start_time
        observe_health_check_component_latency("ai_services", duration)
        return result
    except TimeoutError:
        duration = time.time() - start_time
        observe_health_check_component_latency("ai_services", duration)
        return HealthCheckServiceStatus(
            status="unhealthy",
            message=f"AI services health check timed out after {HEALTH_CHECK_AI_TIMEOUT_SECONDS}s",
            details=None,
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

    NEM-3892: Health checks run in PARALLEL with short individual timeouts
    to ensure the endpoint responds under 500ms SLO. Each component has a
    300ms timeout and all checks run concurrently via asyncio.gather.

    Results are cached for HEALTH_CACHE_TTL_SECONDS (default 10 seconds) to reduce
    load from frequent health probes. Cached responses are returned immediately
    without re-checking services.

    Returns:
        HealthResponse with overall status and individual service statuses.
        HTTP 200 if healthy, 503 if degraded or unhealthy.
    """
    from backend.core.metrics import (
        observe_health_check_latency,
        record_health_check_cache_hit,
        record_health_check_cache_miss,
    )

    global _health_cache  # noqa: PLW0603
    start_time = time.time()

    # Check if we have a valid cached response
    if _health_cache is not None and _health_cache.is_valid():
        # Return cached response with appropriate HTTP status
        response.status_code = _health_cache.http_status
        duration = time.time() - start_time
        observe_health_check_latency("health", "cached", duration)
        record_health_check_cache_hit("health")
        return _health_cache.response

    # Cache miss - record it
    record_health_check_cache_miss("health")

    # NEM-3892: Run all health checks in PARALLEL for faster response
    # Each check has its own timeout, and they all run concurrently
    db_status, redis_status, ai_status = await asyncio.gather(
        _check_db_health_with_timeout(db),
        _check_redis_health_with_timeout(redis),
        _check_ai_health_with_timeout(),
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

    # Determine HTTP status code (200 for healthy, 503 for degraded or unhealthy)
    http_status = 200 if overall_status == "healthy" else 503
    response.status_code = http_status

    # Emit WebSocket events for health status changes
    # This only emits when status actually transitions (not on every check)
    await _emit_health_status_changes(
        db_status=db_status.status,
        redis_status=redis_status.status,
        ai_status=ai_status.status,
        db_details=db_status.details,
        redis_details=redis_status.details,
        ai_details=ai_status.details,
    )

    # Collect recent health events for debugging intermittent issues
    recent_events: list[HealthEventResponse] = []
    if _service_health_monitor is not None:
        events = _service_health_monitor.get_recent_events(limit=20)
        recent_events = [
            HealthEventResponse(
                timestamp=event.timestamp,
                service=event.service,
                event_type=event.event_type,
                message=event.message,
            )
            for event in events
        ]

    health_response = HealthResponse(
        status=overall_status,
        services=services,
        timestamp=datetime.now(UTC),
        recent_events=recent_events,
    )

    # Cache the response for future requests
    _health_cache = HealthCacheEntry(
        response=health_response,
        cached_at=time.time(),
        http_status=http_status,
    )

    # Record total latency for the health check
    duration = time.time() - start_time
    observe_health_check_latency("health", "full", duration)

    return health_response


@router.get("/health/live")
async def get_liveness() -> dict[str, str]:
    """Fast liveness probe endpoint - responds in under 100ms.

    NEM-3892: This endpoint performs NO external checks. It immediately returns
    a simple "alive" status to indicate the process is running and can handle
    HTTP requests. This is critical for Kubernetes liveness probes which need
    to detect hung processes quickly without waiting for dependency checks.

    For detailed health information, use:
    - GET /api/system/health - Full health check with service status
    - GET /api/system/health/ready - Readiness check with dependency status

    Returns:
        Dict with status "alive" and timestamp.
    """
    from backend.core.metrics import observe_health_check_latency

    start_time = time.time()

    response = {
        "status": "alive",
        "timestamp": datetime.now(UTC).isoformat(),
    }

    # Record liveness latency (should be <10ms)
    duration = time.time() - start_time
    observe_health_check_latency("health_live", "liveness", duration)

    return response


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

    NEM-3892: Health checks run in PARALLEL with short individual timeouts
    to ensure the endpoint responds under 500ms SLO.

    Results are cached for HEALTH_CACHE_TTL_SECONDS (default 10 seconds) to reduce
    load from frequent readiness probes.

    Returns:
        ReadinessResponse with overall readiness status and detailed checks.
        HTTP 200 if ready, 503 if degraded or not ready.
    """
    from backend.core.metrics import (
        observe_health_check_latency,
        record_health_check_cache_hit,
        record_health_check_cache_miss,
    )

    global _readiness_cache  # noqa: PLW0603
    start_time = time.time()

    # Check if we have a valid cached response
    if _readiness_cache is not None and _readiness_cache.is_valid():
        response.status_code = _readiness_cache.http_status
        duration = time.time() - start_time
        observe_health_check_latency("health_ready", "cached", duration)
        record_health_check_cache_hit("health_ready")
        return _readiness_cache.response

    # Cache miss - record it
    record_health_check_cache_miss("health_ready")

    # NEM-3892: Run all health checks in PARALLEL for faster response
    db_status, redis_status, ai_status = await asyncio.gather(
        _check_db_health_with_timeout(db),
        _check_redis_health_with_timeout(redis),
        _check_ai_health_with_timeout(),
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
    http_status = 200 if ready else 503
    response.status_code = http_status

    # Check supervisor health (NEM-2462)
    supervisor_healthy = _get_supervisor_health()

    readiness_response = ReadinessResponse(
        ready=ready,
        status=status,
        services=services,
        workers=workers,
        timestamp=datetime.now(UTC),
        supervisor_healthy=supervisor_healthy,
    )

    # Cache the response for future requests
    _readiness_cache = ReadinessCacheEntry(
        response=readiness_response,
        cached_at=time.time(),
        http_status=http_status,
    )

    # Record total latency for the readiness check
    duration = time.time() - start_time
    observe_health_check_latency("health_ready", "full", duration)

    return readiness_response


@router.get("/health/websocket", response_model=WebSocketHealthResponse)
async def get_websocket_health(
    _rate_limit: None = Depends(RateLimiter(tier=RateLimitTier.DEFAULT)),
) -> WebSocketHealthResponse:
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

    # Helper function to create unavailable status for uninitialized broadcasters
    def get_unavailable_status(broadcaster_name: str) -> WebSocketBroadcasterStatus:
        return WebSocketBroadcasterStatus(
            state=CircuitBreakerStateEnum.UNAVAILABLE,
            is_degraded=True,
            failure_count=0,
            message=f"{broadcaster_name} not initialized",
        )

    # Get event broadcaster status
    if event_broadcaster is not None:
        circuit_state = event_broadcaster.get_circuit_state()
        event_status = WebSocketBroadcasterStatus(
            state=CircuitBreakerStateEnum(circuit_state.value),
            failure_count=event_broadcaster.circuit_breaker.failure_count,
            is_degraded=event_broadcaster.is_degraded(),
        )
    else:
        event_status = get_unavailable_status("Event broadcaster")

    # Get system broadcaster status
    if system_broadcaster is not None:
        circuit_state = system_broadcaster.get_circuit_state()
        system_status = WebSocketBroadcasterStatus(
            state=CircuitBreakerStateEnum(circuit_state.value),
            failure_count=system_broadcaster.circuit_breaker.failure_count,
            is_degraded=not system_broadcaster._pubsub_listening,
        )
    else:
        system_status = get_unavailable_status("System broadcaster")

    return WebSocketHealthResponse(
        event_broadcaster=event_status,
        system_broadcaster=system_status,
        timestamp=datetime.now(UTC),
    )


# =============================================================================
# Monitoring Stack Health Endpoints (NEM-2470)
# =============================================================================

# Timeout for Prometheus API requests (in seconds)
PROMETHEUS_API_TIMEOUT_SECONDS = 5.0

# Known exporters with their default endpoints
KNOWN_EXPORTERS = {
    "redis-exporter": "http://redis-exporter:9121",
    "json-exporter": "http://json-exporter:7979",
    "blackbox-exporter": "http://blackbox-exporter:9115",
}


async def _check_prometheus_reachability(prometheus_url: str) -> tuple[bool, dict | None]:
    """Check if Prometheus server is reachable and get status.

    Args:
        prometheus_url: Base URL for Prometheus server

    Returns:
        Tuple of (is_reachable, status_data)
    """
    try:
        async with httpx.AsyncClient(timeout=PROMETHEUS_API_TIMEOUT_SECONDS) as client:
            # Check ready endpoint for Prometheus health
            response = await client.get(f"{prometheus_url}/-/ready")
            if response.status_code == 200:
                return True, {"status": "ready"}
            return False, {"status": "not_ready", "status_code": response.status_code}
    except httpx.ConnectError:
        return False, {"error": "Connection refused"}
    except httpx.TimeoutException:
        return False, {"error": "Request timed out"}
    except Exception as e:
        return False, {"error": str(e)}


async def _get_prometheus_targets(prometheus_url: str) -> list[dict]:
    """Get all scrape targets from Prometheus API.

    Args:
        prometheus_url: Base URL for Prometheus server

    Returns:
        List of target dictionaries with health status
    """
    try:
        async with httpx.AsyncClient(timeout=PROMETHEUS_API_TIMEOUT_SECONDS) as client:
            response = await client.get(f"{prometheus_url}/api/v1/targets")
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    targets = []
                    active_targets = data.get("data", {}).get("activeTargets", [])
                    for target in active_targets:
                        targets.append(
                            {
                                "job": target.get("labels", {}).get("job", "unknown"),
                                "instance": target.get("labels", {}).get("instance", "unknown"),
                                "health": target.get("health", "unknown"),
                                "labels": target.get("labels", {}),
                                "lastScrape": target.get("lastScrape"),
                                "lastError": target.get("lastError", ""),
                                "scrapeInterval": target.get("scrapeInterval"),
                                "scrapeDuration": target.get("lastScrapeDuration"),
                            }
                        )
                    return targets
    except Exception as e:
        logger.warning(f"Failed to fetch Prometheus targets: {e}")
    return []


async def _get_prometheus_tsdb_status(prometheus_url: str) -> dict | None:
    """Get TSDB status from Prometheus (for series count).

    Args:
        prometheus_url: Base URL for Prometheus server

    Returns:
        TSDB status dict or None if unavailable
    """
    try:
        async with httpx.AsyncClient(timeout=PROMETHEUS_API_TIMEOUT_SECONDS) as client:
            response = await client.get(f"{prometheus_url}/api/v1/status/tsdb")
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    result: dict = data.get("data", {})
                    return result
    except Exception as e:
        logger.debug(f"Failed to fetch Prometheus TSDB status: {e}")
    return None


def _parse_prometheus_timestamp(ts_str: str | None) -> datetime | None:
    """Parse a Prometheus timestamp string to datetime.

    Args:
        ts_str: Timestamp string in ISO format

    Returns:
        datetime object or None if parsing fails
    """
    if not ts_str:
        return None
    try:
        # Prometheus returns ISO 8601 format timestamps
        # Handle both "2024-01-13T10:30:00Z" and "2024-01-13T10:30:00.123456789Z"
        if "." in ts_str:
            # Truncate nanoseconds to microseconds
            parts = ts_str.split(".")
            if len(parts) == 2:
                fraction = parts[1].rstrip("Z")[:6]  # Keep only 6 digits
                ts_str = f"{parts[0]}.{fraction}Z"
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _build_targets_summary(targets: list[dict]) -> list[JobTargetSummary]:
    """Build a summary of target health by job.

    Args:
        targets: List of target dictionaries

    Returns:
        List of JobTargetSummary objects
    """
    job_stats: dict[str, dict[str, int]] = {}

    for target in targets:
        job = target.get("job", "unknown")
        if job not in job_stats:
            job_stats[job] = {"total": 0, "up": 0, "down": 0, "unknown": 0}

        job_stats[job]["total"] += 1
        health = target.get("health", "unknown").lower()
        if health == "up":
            job_stats[job]["up"] += 1
        elif health == "down":
            job_stats[job]["down"] += 1
        else:
            job_stats[job]["unknown"] += 1

    return [
        JobTargetSummary(
            job=job,
            total=stats["total"],
            up=stats["up"],
            down=stats["down"],
            unknown=stats["unknown"],
        )
        for job, stats in sorted(job_stats.items())
    ]


def _build_exporter_status(targets: list[dict]) -> list[ExporterStatus]:
    """Build exporter status from target data.

    Args:
        targets: List of target dictionaries

    Returns:
        List of ExporterStatus objects for known exporters
    """
    exporters: list[ExporterStatus] = []

    for exporter_name, default_endpoint in KNOWN_EXPORTERS.items():
        # Find matching targets for this exporter
        exporter_targets = [
            t
            for t in targets
            if exporter_name.replace("-", "_") in t.get("job", "").lower()
            or exporter_name.replace("-", "") in t.get("instance", "").lower()
            or exporter_name in t.get("instance", "").lower()
        ]

        if exporter_targets:
            # Use the first matching target
            target = exporter_targets[0]
            health = target.get("health", "unknown").lower()
            exporter_status = (
                ExporterStatusEnum.UP
                if health == "up"
                else (ExporterStatusEnum.DOWN if health == "down" else ExporterStatusEnum.UNKNOWN)
            )
            last_scrape = _parse_prometheus_timestamp(target.get("lastScrape"))
            error = target.get("lastError") if target.get("lastError") else None

            exporters.append(
                ExporterStatus(
                    name=exporter_name,
                    status=exporter_status,
                    endpoint=target.get("instance") or default_endpoint,
                    last_scrape=last_scrape,
                    error=error,
                )
            )
        else:
            # Exporter not found in targets - mark as unknown
            exporters.append(
                ExporterStatus(
                    name=exporter_name,
                    status=ExporterStatusEnum.UNKNOWN,
                    endpoint=default_endpoint,
                    last_scrape=None,
                    error="Exporter not found in Prometheus targets",
                )
            )

    return exporters


def _identify_monitoring_issues(
    prometheus_reachable: bool,
    targets_summary: list[JobTargetSummary],
    exporters: list[ExporterStatus],
) -> list[str]:
    """Identify issues with the monitoring stack.

    Args:
        prometheus_reachable: Whether Prometheus is reachable
        targets_summary: Summary of target health by job
        exporters: List of exporter statuses

    Returns:
        List of issue descriptions
    """
    issues: list[str] = []

    if not prometheus_reachable:
        issues.append("Prometheus server is not reachable")
        return issues  # No point checking further

    # Check for jobs with all targets down
    for summary in targets_summary:
        if summary.total > 0 and summary.down == summary.total:
            issues.append(f"All targets in job '{summary.job}' are down")
        elif summary.down > 0:
            issues.append(f"{summary.down}/{summary.total} targets in job '{summary.job}' are down")

    # Check exporters
    for exporter in exporters:
        if exporter.status == ExporterStatusEnum.DOWN:
            issues.append(
                f"Exporter '{exporter.name}' is down: {exporter.error or 'unknown error'}"
            )
        elif exporter.status == ExporterStatusEnum.UNKNOWN:
            issues.append(f"Exporter '{exporter.name}' status unknown (not in Prometheus targets)")

    return issues


@router.get("/monitoring/health", response_model=MonitoringHealthResponse)
async def get_monitoring_health(
    _rate_limit: None = Depends(RateLimiter(tier=RateLimitTier.DEFAULT)),
) -> MonitoringHealthResponse:
    """Get comprehensive monitoring stack health status.

    Checks the health of the monitoring infrastructure including:
    - Prometheus server reachability
    - Scrape target status (UP/DOWN counts by job)
    - Exporter status (redis-exporter, json-exporter, blackbox-exporter)
    - Metrics collection status

    This endpoint provides operators with a quick view of monitoring
    stack health without needing to access the Prometheus UI directly.

    Returns:
        MonitoringHealthResponse with full monitoring stack status.
        The 'healthy' field is True if Prometheus is reachable and
        the majority of critical targets are up.
    """
    settings = get_settings()
    prometheus_url = settings.prometheus_url

    # Check Prometheus reachability
    prometheus_reachable, _ = await _check_prometheus_reachability(prometheus_url)

    if not prometheus_reachable:
        # Return minimal response when Prometheus is unreachable
        return MonitoringHealthResponse(
            healthy=False,
            prometheus_reachable=False,
            prometheus_url=prometheus_url,
            targets_summary=[],
            exporters=[
                ExporterStatus(
                    name=name,
                    status=ExporterStatusEnum.UNKNOWN,
                    endpoint=endpoint,
                    error="Prometheus unreachable - cannot determine exporter status",
                )
                for name, endpoint in KNOWN_EXPORTERS.items()
            ],
            metrics_collection=MetricsCollectionStatus(
                collecting=False,
                last_successful_scrape=None,
                scrape_interval_seconds=15,
                total_series=None,
            ),
            issues=["Prometheus server is not reachable"],
            timestamp=datetime.now(UTC),
        )

    # Get targets and build summaries
    targets = await _get_prometheus_targets(prometheus_url)
    targets_summary = _build_targets_summary(targets)
    exporters = _build_exporter_status(targets)

    # Get TSDB status for series count
    tsdb_status = await _get_prometheus_tsdb_status(prometheus_url)
    total_series = None
    if tsdb_status:
        head_stats = tsdb_status.get("headStats", {})
        total_series = head_stats.get("numSeries")

    # Find most recent successful scrape
    last_successful_scrape = None
    for target in targets:
        if target.get("health", "").lower() == "up":
            target_scrape = _parse_prometheus_timestamp(target.get("lastScrape"))
            if target_scrape and (
                last_successful_scrape is None or target_scrape > last_successful_scrape
            ):
                last_successful_scrape = target_scrape

    # Identify issues
    issues = _identify_monitoring_issues(prometheus_reachable, targets_summary, exporters)

    # Determine overall health
    # Healthy if: Prometheus reachable AND no critical jobs fully down
    total_up = sum(s.up for s in targets_summary)
    total_down = sum(s.down for s in targets_summary)
    healthy = prometheus_reachable and (total_down == 0 or total_up > total_down)

    return MonitoringHealthResponse(
        healthy=healthy,
        prometheus_reachable=prometheus_reachable,
        prometheus_url=prometheus_url,
        targets_summary=targets_summary,
        exporters=exporters,
        metrics_collection=MetricsCollectionStatus(
            collecting=total_up > 0,
            last_successful_scrape=last_successful_scrape,
            scrape_interval_seconds=15,  # Default from prometheus.yml
            total_series=total_series,
        ),
        issues=issues,
        timestamp=datetime.now(UTC),
    )


@router.get("/monitoring/targets", response_model=MonitoringTargetsResponse)
async def get_monitoring_targets(
    _rate_limit: None = Depends(RateLimiter(tier=RateLimitTier.DEFAULT)),
) -> MonitoringTargetsResponse:
    """Get detailed status of all Prometheus scrape targets.

    Returns complete information about every target Prometheus is
    configured to scrape, including:
    - Job and instance identifiers
    - Health status (up/down)
    - All labels associated with the target
    - Last scrape timestamp and duration
    - Any scrape errors

    This endpoint is useful for debugging specific target issues
    or getting a comprehensive view of all monitored endpoints.

    Returns:
        MonitoringTargetsResponse with detailed target information.

    Raises:
        HTTPException: 503 if Prometheus is unreachable
    """
    settings = get_settings()
    prometheus_url = settings.prometheus_url

    # Check Prometheus reachability
    prometheus_reachable, status_data = await _check_prometheus_reachability(prometheus_url)

    if not prometheus_reachable:
        error_msg = status_data.get("error", "Unknown error") if status_data else "Unknown error"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Prometheus server is not reachable: {error_msg}",
        )

    # Get targets
    raw_targets = await _get_prometheus_targets(prometheus_url)

    # Convert to TargetHealth objects
    targets: list[TargetHealth] = []
    jobs: set[str] = set()
    up_count = 0
    down_count = 0

    for raw in raw_targets:
        job = raw.get("job", "unknown")
        jobs.add(job)

        health = raw.get("health", "unknown").lower()
        if health == "up":
            up_count += 1
        elif health == "down":
            down_count += 1

        # Parse scrape duration
        scrape_duration = None
        duration_str = raw.get("scrapeDuration")
        if duration_str:
            try:
                # Duration is in seconds as a float string
                scrape_duration = float(duration_str)
            except (ValueError, TypeError):
                # Scrape duration is optional metadata - if parsing fails,
                # we continue with None rather than failing the entire response.
                # See: NEM-2540 for rationale
                pass

        targets.append(
            TargetHealth(
                job=job,
                instance=raw.get("instance", "unknown"),
                health=health,
                labels=raw.get("labels", {}),
                last_scrape=_parse_prometheus_timestamp(raw.get("lastScrape")),
                last_error=raw.get("lastError") if raw.get("lastError") else None,
                scrape_duration_seconds=scrape_duration,
            )
        )

    return MonitoringTargetsResponse(
        targets=targets,
        total=len(targets),
        up=up_count,
        down=down_count,
        jobs=sorted(jobs),
        timestamp=datetime.now(UTC),
    )


@router.get("/performance", response_model=PerformanceUpdate)
async def get_performance_metrics(
    _rate_limit: None = Depends(RateLimiter(tier=RateLimitTier.DEFAULT)),
) -> PerformanceUpdate:
    """Get current system performance metrics.

    Collects and returns real-time metrics from all system components:
    - GPU: Utilization, VRAM usage, temperature, power consumption
    - AI Models: YOLO26v2 and Nemotron status and resource usage
    - Inference: Latency percentiles and throughput metrics
    - Databases: PostgreSQL and Redis connection status and performance
    - Host: CPU, RAM, and disk usage
    - Containers: Health status of all running containers
    - Alerts: Active performance alerts when thresholds are exceeded

    This endpoint powers the System Performance Dashboard and provides
    a comprehensive snapshot of system health at the time of the request.

    Returns:
        PerformanceUpdate with all available metrics. Fields may be None
        if a particular metric source is unavailable.

    Raises:
        HTTPException: 503 if performance collector is not initialized
        HTTPException: 500 if metric collection fails
    """
    if _performance_collector is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Performance collector not initialized",
        )

    try:
        return await _performance_collector.collect_all()
    except Exception as e:
        logger.error(f"Failed to collect performance metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to collect performance metrics: {e!s}",
        ) from e


@router.get("/performance/history", response_model=PerformanceHistoryResponse)
async def get_performance_history(
    time_range: TimeRange = Query(default=TimeRange.FIVE_MIN),
    _rate_limit: None = Depends(RateLimiter(tier=RateLimitTier.DEFAULT)),
) -> PerformanceHistoryResponse:
    """Get historical system performance metrics.

    Returns historical performance snapshots for time-series visualization.
    The data is sampled based on the requested time range to provide
    approximately 60 data points for each range:

    - 5m: All snapshots from the last 5 minutes (every 5s = 60 points max)
    - 15m: Sampled snapshots from last 15 minutes (every 15s = 60 points max)
    - 60m: Sampled snapshots from last 60 minutes (every 60s = 60 points max)

    This endpoint enables the System Performance Dashboard to display
    historical trends and patterns in system metrics.

    Args:
        time_range: Time range for history (5m, 15m, or 60m). Defaults to 5m.

    Returns:
        PerformanceHistoryResponse containing:
        - snapshots: List of PerformanceUpdate objects in chronological order
        - time_range: The requested time range
        - count: Number of snapshots returned
    """
    if _system_broadcaster is None:
        # Return empty response if broadcaster not initialized
        return PerformanceHistoryResponse(
            snapshots=[],
            time_range=time_range,
            count=0,
        )

    snapshots = _system_broadcaster.get_performance_history(time_range)
    return PerformanceHistoryResponse(
        snapshots=snapshots,
        time_range=time_range,
        count=len(snapshots),
    )


@router.get("/websocket/events", response_model=EventRegistryResponse)
async def list_websocket_event_types(
    _rate_limit: None = Depends(RateLimiter(tier=RateLimitTier.DEFAULT)),
) -> EventRegistryResponse:
    """List all available WebSocket event types with schemas.

    Returns the complete registry of WebSocket event types supported by the system,
    including their descriptions, payload schemas, and example payloads. This
    endpoint enables frontend developers and API consumers to discover and
    understand all available real-time event types.

    Event types follow a hierarchical naming convention: {domain}.{action}
    For example: detection.new, event.created, camera.status_changed

    Channels group related events:
    - detections: AI detection pipeline events
    - events: Security event lifecycle events
    - alerts: Alert notifications and state changes
    - cameras: Camera status and configuration changes
    - jobs: Background job lifecycle events
    - system: System health and status events

    Note: Some event types are marked as deprecated with suggested replacements.
    These remain available for backward compatibility but should be avoided in
    new implementations.

    Returns:
        EventRegistryResponse containing:
        - event_types: List of all event types with schemas and examples
        - channels: List of available WebSocket channels
        - total_count: Total number of event types
        - deprecated_count: Number of deprecated event types
    """
    return get_event_registry_response()


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

    Results are cached for HEALTH_CACHE_TTL_SECONDS (default 5 seconds) to reduce
    database load from frequent polling. GPU stats only update every 5 seconds anyway.

    Returns:
        GPUStatsResponse with GPU statistics (null values if unavailable)
    """
    global _gpu_stats_cache  # noqa: PLW0603

    # Check if we have a valid cached response
    if _gpu_stats_cache is not None and _gpu_stats_cache.is_valid():
        return _gpu_stats_cache.response

    # Cache miss or expired - query database
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
            fan_speed=None,
            sm_clock=None,
            memory_bandwidth_utilization=None,
            pstate=None,
            throttle_reasons=None,
            power_limit=None,
            sm_clock_max=None,
            compute_processes_count=None,
            pcie_replay_counter=None,
            temp_slowdown_threshold=None,
            memory_clock=None,
            memory_clock_max=None,
            pcie_link_gen=None,
            pcie_link_width=None,
            pcie_tx_throughput=None,
            pcie_rx_throughput=None,
            encoder_utilization=None,
            decoder_utilization=None,
            bar1_used=None,
        )

    gpu_response = GPUStatsResponse(
        gpu_name=stats["gpu_name"],
        utilization=stats["utilization"],
        memory_used=stats["memory_used"],
        memory_total=stats["memory_total"],
        temperature=stats["temperature"],
        power_usage=stats["power_usage"],
        inference_fps=stats["inference_fps"],
        fan_speed=stats.get("fan_speed"),
        sm_clock=stats.get("sm_clock"),
        memory_bandwidth_utilization=stats.get("memory_bandwidth_utilization"),
        pstate=stats.get("pstate"),
        throttle_reasons=stats.get("throttle_reasons"),
        power_limit=stats.get("power_limit"),
        sm_clock_max=stats.get("sm_clock_max"),
        compute_processes_count=stats.get("compute_processes_count"),
        pcie_replay_counter=stats.get("pcie_replay_counter"),
        temp_slowdown_threshold=stats.get("temp_slowdown_threshold"),
        memory_clock=stats.get("memory_clock"),
        memory_clock_max=stats.get("memory_clock_max"),
        pcie_link_gen=stats.get("pcie_link_gen"),
        pcie_link_width=stats.get("pcie_link_width"),
        pcie_tx_throughput=stats.get("pcie_tx_throughput"),
        pcie_rx_throughput=stats.get("pcie_rx_throughput"),
        encoder_utilization=stats.get("encoder_utilization"),
        decoder_utilization=stats.get("decoder_utilization"),
        bar1_used=stats.get("bar1_used"),
    )

    # Cache the response for future requests
    _gpu_stats_cache = GPUStatsCacheEntry(
        response=gpu_response,
        cached_at=time.time(),
    )

    return gpu_response


@router.get("/gpu/history", response_model=GPUStatsHistoryResponse)
async def get_gpu_stats_history(
    since: datetime | None = None,
    limit: int = 300,
    db: AsyncSession = Depends(get_db),
) -> GPUStatsHistoryResponse:
    """Get recent GPU stats samples as a time-series.

    Returns GPU stats in standard pagination envelope format (NEM-2178):
    - items: GPU stats samples (renamed from 'samples')
    - pagination: Standard pagination metadata

    Args:
        since: Optional lower bound for recorded_at (ISO datetime)
        limit: Maximum number of samples to return (default 300, max 5000)
        db: Database session
    """
    limit = max(limit, 1)
    limit = min(limit, 5000)

    stmt = select(GPUStats)
    if since is not None:
        stmt = stmt.where(GPUStats.recorded_at >= since)

    # Get total count for pagination
    count_stmt = select(func.count(GPUStats.id))
    if since is not None:
        count_stmt = count_stmt.where(GPUStats.recorded_at >= since)
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    # Fetch newest first, then reverse to chronological order for charting.
    stmt = stmt.order_by(GPUStats.recorded_at.desc()).limit(limit)
    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    rows.reverse()

    items = [
        {
            "recorded_at": r.recorded_at,
            "gpu_name": r.gpu_name,
            "utilization": r.gpu_utilization,
            "memory_used": r.memory_used,
            "memory_total": r.memory_total,
            "temperature": r.temperature,
            "power_usage": r.power_usage,
            "inference_fps": r.inference_fps,
            # Extended metrics
            "fan_speed": r.fan_speed,
            "sm_clock": r.sm_clock,
            "memory_bandwidth_utilization": r.memory_bandwidth_utilization,
            "pstate": r.pstate,
            # High-value metrics
            "throttle_reasons": r.throttle_reasons,
            "power_limit": r.power_limit,
            "sm_clock_max": r.sm_clock_max,
            "compute_processes_count": r.compute_processes_count,
            "pcie_replay_counter": r.pcie_replay_counter,
            "temp_slowdown_threshold": r.temp_slowdown_threshold,
            # Medium-value metrics
            "memory_clock": r.memory_clock,
            "memory_clock_max": r.memory_clock_max,
            "pcie_link_gen": r.pcie_link_gen,
            "pcie_link_width": r.pcie_link_width,
            "pcie_tx_throughput": r.pcie_tx_throughput,
            "pcie_rx_throughput": r.pcie_rx_throughput,
            "encoder_utilization": r.encoder_utilization,
            "decoder_utilization": r.decoder_utilization,
            "bar1_used": r.bar1_used,
        }
        for r in rows
    ]

    return GPUStatsHistoryResponse(
        items=items,
        pagination=create_pagination_meta(
            total=total,
            limit=limit,
            items_count=len(items),
        ),
    )


@router.get("/config", response_model=ConfigResponse)
async def get_config(response: Response) -> ConfigResponse:
    """Get public configuration settings.

    Returns non-sensitive application configuration values.
    Does NOT expose database URLs, API keys, or other secrets.

    Note: The detection_confidence_threshold field is deprecated.
    Use /api/v1/settings detection.confidence_threshold instead.

    Returns:
        ConfigResponse with public configuration settings
    """
    settings = get_settings()

    # Add deprecation headers (RFC 8594)
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "2026-07-01T00:00:00Z"
    response.headers["Link"] = (
        '</api/v1/settings>; rel="successor-version"; '
        'title="Use /api/v1/settings for detection settings"'
    )
    response.headers["X-Deprecated-Message"] = (
        "detection_confidence_threshold is deprecated. "
        "Use /api/v1/settings detection.confidence_threshold instead."
    )

    return ConfigResponse(
        app_name=settings.app_name,
        version=settings.app_version,
        retention_days=settings.retention_days,
        log_retention_days=settings.log_retention_days,
        batch_window_seconds=settings.batch_window_seconds,
        batch_idle_timeout_seconds=settings.batch_idle_timeout_seconds,
        detection_confidence_threshold=settings.detection_confidence_threshold,
        fast_path_confidence_threshold=settings.fast_path_confidence_threshold,
        grafana_url=settings.grafana_url,
        debug=settings.debug,
    )


def _runtime_env_path() -> Path:
    """Return the configured runtime override env file path.

    The path is validated to be within expected directories to prevent
    path traversal vulnerabilities via HSI_RUNTIME_ENV_PATH.
    """
    raw_path = os.getenv("HSI_RUNTIME_ENV_PATH", "./data/runtime.env")
    path = Path(raw_path).resolve()

    # Allowed directories: data dirs, system temp dir, or current working directory
    allowed_bases = [
        Path("./data").resolve(),
        Path("/data").resolve(),
        Path(tempfile.gettempdir()).resolve(),
        Path.cwd().resolve(),
    ]
    if not any(str(path).startswith(str(base)) for base in allowed_bases):
        logger.warning(
            f"Runtime env path {path} is outside allowed directories, "
            f"using default ./data/runtime.env"
        )
        path = Path("./data/runtime.env").resolve()

    return path


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
    # nosemgrep: path-traversal-open -- path is from env var/hardcoded default, not user input
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    logger.info(f"Wrote runtime env to {path}: {sanitize_log_value(overrides)}")


@router.patch(
    "/config",
    response_model=ConfigResponse,
    dependencies=[Depends(verify_api_key)],
    responses={
        401: {"description": "Unauthorized - API key required"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def patch_config(
    request: Request,
    response: Response,
    update: ConfigUpdateRequest = Body(...),
    db: AsyncSession = Depends(get_db),
) -> ConfigResponse:
    """Patch processing-related configuration and persist runtime overrides.

    Requires API key authentication when api_key_enabled is True in settings.
    Provide the API key via X-API-Key header.

    Note: The detection_confidence_threshold field is deprecated.
    Use PATCH /api/v1/settings with detection.confidence_threshold instead.

    Notes:
    - This updates a runtime override env file (see `HSI_RUNTIME_ENV_PATH`) and clears the
      settings cache so subsequent `get_settings()` calls observe the new values.
    """
    # Add deprecation headers (RFC 8594)
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "2026-07-01T00:00:00Z"
    response.headers["Link"] = (
        '</api/v1/settings>; rel="successor-version"; '
        'title="Use /api/v1/settings for detection settings"'
    )
    response.headers["X-Deprecated-Message"] = (
        "detection_confidence_threshold is deprecated. "
        "Use /api/v1/settings detection.confidence_threshold instead."
    )
    logger.info(f"patch_config called with: {update.model_dump()}")
    logger.info(f"Runtime env path: {_runtime_env_path()}")

    # Capture old settings for audit log
    old_settings = get_settings()
    old_values = {
        "retention_days": old_settings.retention_days,
        "log_retention_days": old_settings.log_retention_days,
        "batch_window_seconds": old_settings.batch_window_seconds,
        "batch_idle_timeout_seconds": old_settings.batch_idle_timeout_seconds,
        "detection_confidence_threshold": old_settings.detection_confidence_threshold,
        "fast_path_confidence_threshold": old_settings.fast_path_confidence_threshold,
    }

    overrides: dict[str, str] = {}

    if update.retention_days is not None:
        overrides["RETENTION_DAYS"] = str(update.retention_days)
    if update.log_retention_days is not None:
        overrides["LOG_RETENTION_DAYS"] = str(update.log_retention_days)
    if update.batch_window_seconds is not None:
        overrides["BATCH_WINDOW_SECONDS"] = str(update.batch_window_seconds)
    if update.batch_idle_timeout_seconds is not None:
        overrides["BATCH_IDLE_TIMEOUT_SECONDS"] = str(update.batch_idle_timeout_seconds)
    if update.detection_confidence_threshold is not None:
        overrides["DETECTION_CONFIDENCE_THRESHOLD"] = str(update.detection_confidence_threshold)
    if update.fast_path_confidence_threshold is not None:
        overrides["FAST_PATH_CONFIDENCE_THRESHOLD"] = str(update.fast_path_confidence_threshold)

    if overrides:
        _write_runtime_env(overrides)

    # Make new values visible to the app immediately.
    get_settings.cache_clear()
    settings = get_settings()

    logger.info(
        f"Settings after update: retention_days={settings.retention_days}, "
        f"log_retention_days={settings.log_retention_days}, "
        f"batch_window_seconds={settings.batch_window_seconds}, "
        f"detection_confidence_threshold={settings.detection_confidence_threshold}, "
        f"fast_path_confidence_threshold={settings.fast_path_confidence_threshold}"
    )

    # Build changes for audit log
    new_values = {
        "retention_days": settings.retention_days,
        "log_retention_days": settings.log_retention_days,
        "batch_window_seconds": settings.batch_window_seconds,
        "batch_idle_timeout_seconds": settings.batch_idle_timeout_seconds,
        "detection_confidence_threshold": settings.detection_confidence_threshold,
        "fast_path_confidence_threshold": settings.fast_path_confidence_threshold,
    }
    changes: dict[str, dict[str, Any]] = {}
    for key, old_value in old_values.items():
        new_value = new_values[key]
        if old_value != new_value:
            changes[key] = {"old": old_value, "new": new_value}

    # Log the audit entry
    if changes:
        try:
            await AuditService.log_action(
                db=db,
                action=AuditAction.SETTINGS_CHANGED,
                resource_type="settings",
                actor="anonymous",
                details={"changes": changes},
                request=request,
            )
            await db.commit()
        except (ConnectionError, TimeoutError, OSError, RuntimeError) as e:
            # Database transaction failures
            logger.error(
                f"Failed to commit audit log: {e}",
                exc_info=True,
                extra={"action": "settings_changed"},
            )
            await db.rollback()
            # Don't fail the main operation - audit is non-critical

    return ConfigResponse(
        app_name=settings.app_name,
        version=settings.app_version,
        retention_days=settings.retention_days,
        log_retention_days=settings.log_retention_days,
        batch_window_seconds=settings.batch_window_seconds,
        batch_idle_timeout_seconds=settings.batch_idle_timeout_seconds,
        detection_confidence_threshold=settings.detection_confidence_threshold,
        fast_path_confidence_threshold=settings.fast_path_confidence_threshold,
        grafana_url=settings.grafana_url,
        debug=settings.debug,
    )


@router.get(
    "/anomaly-config",
    response_model=AnomalyConfig,
    responses={
        500: {"description": "Internal server error"},
    },
)
async def get_anomaly_config(
    service: BaselineServiceDep = Depends(get_baseline_service_dep),
) -> AnomalyConfig:
    """Get current anomaly detection configuration.

    Returns the current settings for the baseline service including:
    - threshold_stdev: Number of standard deviations for anomaly detection
    - min_samples: Minimum samples required before anomaly detection is reliable
    - decay_factor: Exponential decay factor for EWMA (weights recent observations)
    - window_days: Rolling window size in days for baseline calculations

    Args:
        service: BaselineService injected via Depends()

    Returns:
        AnomalyConfig with current anomaly detection settings
    """
    return AnomalyConfig(
        threshold_stdev=service.anomaly_threshold_std,
        min_samples=service.min_samples,
        decay_factor=service.decay_factor,
        window_days=service.window_days,
    )


@router.patch(
    "/anomaly-config",
    response_model=AnomalyConfig,
    dependencies=[Depends(verify_api_key)],
    responses={
        401: {"description": "Unauthorized - API key required"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def update_anomaly_config(
    config_update: AnomalyConfigUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    service: BaselineServiceDep = Depends(get_baseline_service_dep),
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
        service: BaselineService injected via Depends()

    Returns:
        AnomalyConfig with updated settings
    """
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
            status_code=status.HTTP_400_BAD_REQUEST,
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
        try:
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
        except (ConnectionError, TimeoutError, OSError, RuntimeError) as e:
            # Database transaction failures
            logger.error(
                f"Failed to commit audit log: {e}",
                exc_info=True,
                extra={"action": "anomaly_config_updated"},
            )
            await db.rollback()
            # Don't fail the main operation - audit is non-critical

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

    Results are cached for HEALTH_CACHE_TTL_SECONDS (default 5 seconds) to reduce
    database load from three sequential COUNT queries.

    Returns:
        SystemStatsResponse with system statistics
    """
    global _system_stats_cache  # noqa: PLW0603

    # Check if we have a valid cached response
    if _system_stats_cache is not None and _system_stats_cache.is_valid():
        return _system_stats_cache.response

    # Cache miss or expired - query database
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

    stats_response = SystemStatsResponse(
        total_cameras=total_cameras,
        total_events=total_events,
        total_detections=total_detections,
        uptime_seconds=uptime,
    )

    # Cache the response for future requests
    _system_stats_cache = SystemStatsCacheEntry(
        response=stats_response,
        cached_at=time.time(),
    )

    return stats_response


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
    except (ConnectionError, TimeoutError, OSError) as e:
        # Redis connection failures
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
    except (ConnectionError, TimeoutError, OSError, ValueError) as e:
        # Redis failures or parsing errors
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
    except (ConnectionError, TimeoutError, OSError) as e:
        # Redis connection failures
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


def _stats_to_schema(stats: Mapping[str, Any]) -> PipelineStageLatency | None:
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
    - watch_to_detect: Time from file watcher detecting image to YOLO26 processing start
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
        except (OSError, RuntimeError, ConnectionError) as e:
            # File system and database cleanup failures
            logger.error(
                f"Manual cleanup dry run failed: {e}",
                exc_info=True,
                extra={"retention_days": settings.retention_days},
            )
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
        except (OSError, RuntimeError, ConnectionError) as e:
            # File system and database cleanup failures
            logger.error(
                f"Manual cleanup failed: {e}",
                exc_info=True,
                extra={"retention_days": settings.retention_days},
            )
            raise


# =============================================================================
# Orphaned File Cleanup Endpoint
# =============================================================================


@router.post(
    "/cleanup/orphaned-files",
    response_model=OrphanedFileCleanupResponse,
    dependencies=[Depends(verify_api_key)],
)
async def run_orphaned_file_cleanup(
    dry_run: bool = Query(
        default=True,
        description="If True, only report what would be deleted without deleting. Default is True for safety.",
    ),
) -> OrphanedFileCleanupResponse:
    """Find and clean up orphaned files (files on disk not referenced in database).

    Requires API key authentication when api_key_enabled is True in settings.
    Provide the API key via X-API-Key header.

    This endpoint scans storage directories for files that are not referenced
    in the database and optionally deletes them to reclaim disk space.

    Storage directories scanned:
    - Thumbnails directory (video_thumbnails_dir setting)
    - Clips directory (clips_directory setting)

    Database tables checked for file references:
    - Detection.file_path (source images)
    - Detection.thumbnail_path (thumbnails)
    - Event.clip_path (generated clips)

    **Safety Features:**
    - dry_run=True by default to prevent accidental deletion
    - Progress tracking via job system
    - Detailed reporting of orphaned files

    Args:
        dry_run: If True, calculate and return what would be deleted without
                 actually performing the deletion. Default is True for safety.
                 Set to False to actually delete orphaned files.

    Returns:
        OrphanedFileCleanupResponse with statistics about orphaned files.
        When dry_run=True, shows what would be deleted.
        When dry_run=False, shows what was deleted.
    """
    from backend.services.cleanup_service import OrphanedFileCleanup, format_bytes
    from backend.services.job_tracker import get_job_tracker

    job_tracker = get_job_tracker()

    if dry_run:
        logger.info("Orphaned file cleanup dry run triggered")
    else:
        logger.info("Orphaned file cleanup triggered (will delete files)")

    # Create cleanup service with job tracker for progress reporting
    cleanup_service = OrphanedFileCleanup(job_tracker=job_tracker)

    try:
        # Run cleanup (blocking in this implementation)
        stats = await cleanup_service.run_cleanup(dry_run=dry_run)

        logger.info(f"Orphaned file cleanup completed: {stats}")

        return OrphanedFileCleanupResponse(
            orphaned_count=stats.orphaned_count,
            total_size=stats.total_size,
            total_size_formatted=format_bytes(stats.total_size),
            dry_run=stats.dry_run,
            orphaned_files=stats.orphaned_files[:100],  # Limit to 100 files
            job_id=None,  # Job already completed
            timestamp=datetime.now(UTC),
        )

    except (OSError, RuntimeError, ConnectionError) as e:
        logger.error(f"Orphaned file cleanup failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Orphaned file cleanup failed: {e}",
        ) from e


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
            status_code=status.HTTP_400_BAD_REQUEST,
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
        try:
            await AuditService.log_action(
                db=db,
                action=AuditAction.SETTINGS_CHANGED,
                resource_type="severity_thresholds",
                actor="anonymous",
                details={"changes": changes},
                request=request,
            )
            await db.commit()
        except (ConnectionError, TimeoutError, OSError, RuntimeError) as e:
            # Database transaction failures
            logger.error(
                f"Failed to commit audit log: {e}",
                exc_info=True,
                extra={"action": "severity_thresholds_updated"},
            )
            await db.rollback()
            # Don't fail the main operation - audit is non-critical

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
                    # Skip files we can't access - partial results are better than failure.
                    # See: NEM-2540 for rationale
                    pass
    except (OSError, PermissionError):
        # Return zeros if we can't access the directory - caller handles empty results.
        # See: NEM-2540 for rationale
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

    for name, cb_status in all_status.items():
        state_value = cb_status.get("state", "closed")
        state = CircuitBreakerStateEnum(state_value)

        if state == CircuitBreakerStateEnum.OPEN:
            open_count += 1

        config = cb_status.get("config", {})
        circuit_breakers[name] = CircuitBreakerStatusResponse(
            name=name,
            state=state,
            failure_count=cb_status.get("failure_count", 0),
            success_count=cb_status.get("success_count", 0),
            total_calls=cb_status.get("total_calls", 0),
            rejected_calls=cb_status.get("rejected_calls", 0),
            last_failure_time=cb_status.get("last_failure_time"),
            opened_at=cb_status.get("opened_at"),
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
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid circuit breaker name: must be 1-64 characters",
        )

    # Only allow alphanumeric characters, underscores, and hyphens (defense in depth)
    if not all(c.isalnum() or c in "_-" for c in name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid circuit breaker name: must contain only alphanumeric characters, underscores, or hyphens",
        )

    registry = _get_registry()

    # Validate against registered circuit breaker names
    valid_names = registry.list_names()
    if name not in valid_names:
        if not valid_names:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Circuit breaker '{name}' not found. No circuit breakers are currently registered.",
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Circuit breaker '{name}' not found. Valid names: {', '.join(sorted(valid_names))}",
        )

    breaker = registry.get(name)

    # This should never be None due to the validation above, but check for safety
    if breaker is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
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
            except (ValueError, TypeError, KeyError) as e:
                # Data parsing failures for individual batches
                logger.warning(f"Error processing batch {batch_id}: {e}", exc_info=True)
                continue

        return BatchAggregatorStatusResponse(
            active_batches=len(active_batches),
            batches=active_batches,
            batch_window_seconds=settings.batch_window_seconds,
            idle_timeout_seconds=settings.batch_idle_timeout_seconds,
        )
    except (ConnectionError, TimeoutError, OSError) as e:
        # Redis connection failures
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
        except (RuntimeError, ValueError) as e:
            # Manager not initialized or invalid state
            logger.debug(f"Degradation manager not available: {e}")
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
    except (KeyError, ValueError, AttributeError) as e:
        # Status data parsing failures
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
# Worker Supervisor Endpoints (NEM-2457)
# =============================================================================


@router.get("/supervisor", response_model=WorkerSupervisorStatusResponse)
async def get_supervisor_status() -> WorkerSupervisorStatusResponse:
    """Get status of the Worker Supervisor and all supervised workers.

    The Worker Supervisor monitors pipeline worker tasks and automatically
    restarts them with exponential backoff when they crash.

    Returns:
        WorkerSupervisorStatusResponse with:
        - running: Whether the supervisor is active
        - worker_count: Number of registered workers
        - workers: Detailed status of each supervised worker including:
          - status: running/stopped/crashed/restarting/failed
          - restart_count: Number of restart attempts
          - last_started_at/last_crashed_at: Timestamps
          - error: Last error message if crashed

    Use this endpoint to monitor worker health and identify workers that
    are repeatedly crashing or have exceeded their restart limit.
    """
    if _worker_supervisor is None:
        return WorkerSupervisorStatusResponse(
            running=False,
            worker_count=0,
            workers=[],
            timestamp=datetime.now(UTC),
        )

    all_workers = _worker_supervisor.get_all_workers()
    worker_infos: list[SupervisedWorkerInfo] = []

    for name, info in all_workers.items():
        worker_infos.append(
            SupervisedWorkerInfo(
                name=name,
                status=SupervisedWorkerStatusEnum(info.status.value),
                restart_count=info.restart_count,
                max_restarts=info.max_restarts,
                last_started_at=info.last_started_at,
                last_crashed_at=info.last_crashed_at,
                error=info.error,
            )
        )

    return WorkerSupervisorStatusResponse(
        running=_worker_supervisor.is_running,
        worker_count=_worker_supervisor.worker_count,
        workers=worker_infos,
        timestamp=datetime.now(UTC),
    )


@router.post("/supervisor/reset/{worker_name}")
async def reset_worker(worker_name: str) -> dict[str, str | bool]:
    """Reset a failed worker's restart count to allow new restart attempts.

    When a worker exceeds its max restart limit, it enters FAILED status
    and won't be restarted. Use this endpoint to reset the worker's
    restart count and transition it back to STOPPED status, allowing
    the supervisor to attempt restarts again.

    Args:
        worker_name: Name of the worker to reset

    Returns:
        Dictionary with success status and message

    Raises:
        HTTPException 404: Worker not found
        HTTPException 503: Supervisor not initialized
    """
    if _worker_supervisor is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Worker supervisor not initialized",
        )

    success = _worker_supervisor.reset_worker(worker_name)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Worker '{worker_name}' not found",
        )

    logger.info(f"Reset worker '{worker_name}' restart count")
    return {
        "success": True,
        "message": f"Worker '{worker_name}' restart count reset",
    }


# Valid worker name pattern (alphanumeric and underscores only)
VALID_WORKER_NAME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")


def _validate_worker_name(name: str) -> None:
    """Validate worker name format.

    Args:
        name: Worker name to validate.

    Raises:
        HTTPException: 400 if name is invalid.
    """
    if not VALID_WORKER_NAME_PATTERN.match(name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid worker name: '{name}'. Must start with a letter and contain only alphanumeric characters and underscores.",
        )


@router.get("/supervisor/status", response_model=WorkerSupervisorStatusResponse)
async def get_supervisor_full_status() -> WorkerSupervisorStatusResponse:
    """Get full status of the Worker Supervisor and all supervised workers.

    This endpoint is an alias for GET /supervisor but with a clearer path
    that matches the API convention for status endpoints.

    Returns:
        WorkerSupervisorStatusResponse with:
        - running: Whether the supervisor is active
        - worker_count: Number of registered workers
        - workers: Detailed status of each supervised worker
        - timestamp: When the status was queried
    """
    if _worker_supervisor is None:
        return WorkerSupervisorStatusResponse(
            running=False,
            worker_count=0,
            workers=[],
            timestamp=datetime.now(UTC),
        )

    all_workers = _worker_supervisor.get_all_workers()
    worker_infos: list[SupervisedWorkerInfo] = []

    for name, info in all_workers.items():
        worker_infos.append(
            SupervisedWorkerInfo(
                name=name,
                status=SupervisedWorkerStatusEnum(info.status.value),
                restart_count=info.restart_count,
                max_restarts=info.max_restarts,
                last_started_at=info.last_started_at,
                last_crashed_at=info.last_crashed_at,
                error=info.error,
            )
        )

    return WorkerSupervisorStatusResponse(
        running=_worker_supervisor.is_running,
        worker_count=_worker_supervisor.worker_count,
        workers=worker_infos,
        timestamp=datetime.now(UTC),
    )


@router.post(
    "/supervisor/workers/{worker_name}/restart",
    response_model=WorkerControlResponse,
)
async def restart_supervisor_worker(worker_name: str) -> WorkerControlResponse:
    """Manually restart a supervised worker.

    This stops the worker if running and starts it again with reset state.

    Args:
        worker_name: Name of the worker to restart (e.g., file_watcher, detector)

    Returns:
        WorkerControlResponse with success status and message

    Raises:
        HTTPException 400: Invalid worker name format
        HTTPException 404: Worker not found
        HTTPException 503: Supervisor not initialized
    """
    _validate_worker_name(worker_name)

    if _worker_supervisor is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Worker supervisor not initialized",
        )

    # Check worker exists
    if _worker_supervisor.get_worker_info(worker_name) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Worker '{worker_name}' not found",
        )

    success = await _worker_supervisor.restart_worker_task(worker_name)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Worker '{worker_name}' not found",
        )

    logger.info(f"Manually restarted worker '{worker_name}'")
    return WorkerControlResponse(
        success=True,
        message=f"Worker '{worker_name}' restarted successfully",
        worker_name=worker_name,
    )


@router.post(
    "/supervisor/workers/{worker_name}/stop",
    response_model=WorkerControlResponse,
)
async def stop_supervisor_worker(worker_name: str) -> WorkerControlResponse:
    """Manually stop a supervised worker.

    This stops the worker's task. The worker will remain registered
    but will not be automatically restarted by the supervisor.

    Args:
        worker_name: Name of the worker to stop

    Returns:
        WorkerControlResponse with success status and message

    Raises:
        HTTPException 400: Invalid worker name format
        HTTPException 404: Worker not found
        HTTPException 503: Supervisor not initialized
    """
    _validate_worker_name(worker_name)

    if _worker_supervisor is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Worker supervisor not initialized",
        )

    # Check worker exists
    if _worker_supervisor.get_worker_info(worker_name) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Worker '{worker_name}' not found",
        )

    success = await _worker_supervisor.stop_worker(worker_name)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Worker '{worker_name}' not found",
        )

    logger.info(f"Manually stopped worker '{worker_name}'")
    return WorkerControlResponse(
        success=True,
        message=f"Worker '{worker_name}' stopped successfully",
        worker_name=worker_name,
    )


@router.post(
    "/supervisor/workers/{worker_name}/start",
    response_model=WorkerControlResponse,
)
async def start_supervisor_worker(worker_name: str) -> WorkerControlResponse:
    """Manually start a stopped supervised worker.

    This starts a worker that was previously stopped. If the worker
    is already running, this is a no-op and returns success.

    Args:
        worker_name: Name of the worker to start

    Returns:
        WorkerControlResponse with success status and message

    Raises:
        HTTPException 400: Invalid worker name format
        HTTPException 404: Worker not found
        HTTPException 503: Supervisor not initialized
    """
    _validate_worker_name(worker_name)

    if _worker_supervisor is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Worker supervisor not initialized",
        )

    # Check worker exists
    if _worker_supervisor.get_worker_info(worker_name) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Worker '{worker_name}' not found",
        )

    success = await _worker_supervisor.start_worker(worker_name)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Worker '{worker_name}' not found",
        )

    logger.info(f"Manually started worker '{worker_name}'")
    return WorkerControlResponse(
        success=True,
        message=f"Worker '{worker_name}' started successfully",
        worker_name=worker_name,
    )


@router.get("/supervisor/restart-history", response_model=RestartHistoryResponse)
async def get_restart_history(
    worker_name: str | None = Query(
        None,
        description="Filter by worker name",
    ),
    limit: int = Query(
        50,
        ge=1,
        le=100,
        description="Maximum number of events to return",
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Number of events to skip",
    ),
) -> RestartHistoryResponse:
    """Get paginated history of worker restart events.

    Returns a list of restart events including both automatic restarts
    (triggered by crashes) and manual restarts.

    Args:
        worker_name: Optional filter by worker name
        limit: Maximum number of events to return (default 50, max 100)
        offset: Number of events to skip for pagination

    Returns:
        RestartHistoryResponse with events and pagination metadata
    """
    from backend.api.schemas.pagination import create_pagination_meta

    if _worker_supervisor is None:
        # Return empty response when supervisor not initialized
        return RestartHistoryResponse(
            items=[],
            pagination=create_pagination_meta(
                total=0,
                limit=limit,
                offset=offset,
                items_count=0,
            ),
        )

    # Get history from supervisor
    history = _worker_supervisor.get_restart_history(
        worker_name=worker_name,
        limit=limit,
        offset=offset,
    )

    total = _worker_supervisor.get_restart_history_count(worker_name=worker_name)

    # Convert to schema objects
    items = [
        RestartHistoryEvent(
            worker_name=event["worker_name"],
            timestamp=datetime.fromisoformat(event["timestamp"]),
            attempt=event["attempt"],
            status=event["status"],
            error=event.get("error"),
        )
        for event in history
    ]

    return RestartHistoryResponse(
        items=items,
        pagination=create_pagination_meta(
            total=total,
            limit=limit,
            offset=offset,
            items_count=len(items),
        ),
    )


# =============================================================================
# Model Zoo Endpoints
# =============================================================================

# VRAM budget for Model Zoo (excludes YOLO26v2 and Nemotron allocations)
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
    separate from the YOLO26v2 detector and Nemotron LLM allocations.

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
            status_code=status.HTTP_404_NOT_FOUND,
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
        "threat-detection-yolov8n",
    ],
    "Classification": [
        "violence-detection",
        "weather-classification",
        "fashion-clip",
        "vehicle-segment-classification",
        "pet-classifier",
        "vit-age-classifier",
        "vit-gender-classifier",
    ],
    "Segmentation": ["segformer-b2-clothes"],
    "Pose": ["vitpose-small", "yolov8n-pose"],
    "Depth": ["depth-anything-v2-small"],
    "Embedding": ["clip-vit-l", "osnet-x0-25"],
    "OCR": ["paddleocr"],
    "Action Recognition": ["xclip-base"],
}

# Disabled models that should appear at the bottom of the dropdown
DISABLED_MODELS = ["florence-2-large", "brisque-quality", "yolo26-general"]

# Redis key prefix for model zoo latency data
MODEL_ZOO_LATENCY_KEY_PREFIX = "model_zoo:latency:"
MODEL_ZOO_LATENCY_TTL_SECONDS = 86400  # Keep data for 24 hours

# Mapping from EventAudit model flags to Model Zoo model names
# EventAudit tracks which models contributed to each event analysis
# This mapping allows us to derive "last used" timestamps from audit data
AUDIT_MODEL_TO_ZOO_MODELS: dict[str, list[str]] = {
    "yolo26": [],  # YOLO26v2 is not in Model Zoo (always loaded separately)
    "florence": ["florence-2-large"],
    "clip": ["clip-vit-l", "osnet-x0-25"],  # CLIP embeddings and OSNet re-id
    "violence": ["violence-detection"],
    "clothing": ["segformer-b2-clothes", "fashion-clip"],
    "vehicle": ["vehicle-segment-classification", "vehicle-damage-detection"],
    "pet": ["pet-classifier"],
    "weather": ["weather-classification"],
    "image_quality": ["brisque-quality"],
    "zones": [],  # Zone analysis is a context enrichment, not a Model Zoo model
    "baseline": [],  # Baseline comparison is a context enrichment, not a Model Zoo model
    "cross_camera": [],  # Cross-camera correlation is a context enrichment, not a Model Zoo model
}


async def _get_model_last_used_timestamps(
    session: AsyncSession,
) -> dict[str, datetime | None]:
    """Query EventAudit to get the most recent usage timestamp for each Model Zoo model.

    This queries the EventAudit table to find the most recent audited_at timestamp
    for each model type (based on has_* flags), then maps those to Model Zoo model names.

    Args:
        session: Database session for querying EventAudit

    Returns:
        Dictionary mapping Model Zoo model names to their last used timestamps
    """
    last_used: dict[str, datetime | None] = {}

    # Query the most recent audit timestamp for each model flag
    for audit_model, zoo_models in AUDIT_MODEL_TO_ZOO_MODELS.items():
        if not zoo_models:
            continue

        # Get the attribute name for this model (e.g., "has_florence")
        attr_name = f"has_{audit_model}"

        try:
            # Query for the most recent event where this model was used
            attr = getattr(EventAudit, attr_name, None)
            if attr is None:
                continue

            result = await session.execute(
                select(func.max(EventAudit.audited_at)).where(attr == True)  # noqa: E712
            )
            max_timestamp = result.scalar()

            # Apply this timestamp to all Model Zoo models mapped from this audit flag
            for zoo_model in zoo_models:
                # Use the most recent timestamp if we've already seen one
                existing = last_used.get(zoo_model)
                if existing is None or (max_timestamp is not None and max_timestamp > existing):
                    last_used[zoo_model] = max_timestamp

        except Exception as e:
            logger.warning(f"Failed to query last_used for {audit_model}: {e}")
            continue

    return last_used


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


async def _get_db_optional() -> AsyncGenerator[AsyncSession | None]:
    """Dependency that yields a database session or None if unavailable.

    This is used for endpoints that can operate without a database, such as
    model zoo status which can still return static model info without last_used timestamps.
    """
    try:
        async for session in get_db():
            yield session
            return
    except RuntimeError:
        # Database not initialized (e.g., unit tests without DB setup)
        yield None


@router.get(
    "/model-zoo/status",
    response_model=ModelZooStatusResponse,
    summary="Get Model Zoo Status",
)
async def get_model_zoo_status(
    db: AsyncSession | None = Depends(_get_db_optional),
) -> ModelZooStatusResponse:
    """Get status information for all Model Zoo models.

    Returns status information for all 18 Model Zoo models, including:
    - Current status (loaded, unloaded, disabled)
    - VRAM usage when loaded
    - Last usage timestamp (derived from EventAudit records, None if DB unavailable)
    - Category grouping for UI display

    This endpoint is optimized for the compact status card display
    in the AI Performance page.

    Args:
        db: Optional database session for querying EventAudit last used timestamps

    Returns:
        ModelZooStatusResponse with all model statuses
    """
    manager = get_model_manager()
    zoo = get_model_zoo()

    # Get last used timestamps from EventAudit (empty dict if DB unavailable)
    last_used_timestamps: dict[str, datetime | None] = {}
    if db is not None:
        try:
            last_used_timestamps = await _get_model_last_used_timestamps(db)
        except Exception as e:
            logger.warning(f"Failed to query last_used timestamps: {e}")

    models: list[ModelZooStatusItem] = []
    loaded_count = 0
    disabled_count = 0

    for model_name, config in zoo.items():
        # Determine status
        if not config.enabled:
            model_status = ModelStatusEnum.DISABLED
            disabled_count += 1
        elif model_name in manager.loaded_models:
            model_status = ModelStatusEnum.LOADED
            loaded_count += 1
        else:
            model_status = ModelStatusEnum.UNLOADED

        # Get category
        category = _get_model_category(model_name)

        # Get last used timestamp from EventAudit data
        last_used_at = last_used_timestamps.get(model_name)

        models.append(
            ModelZooStatusItem(
                name=config.name,
                display_name=_get_model_display_name(config.name),
                category=category,
                status=model_status,
                vram_mb=config.vram_mb,
                last_used_at=last_used_at,
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
            status_code=status.HTTP_404_NOT_FOUND,
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


# =============================================================================
# Full Health Check Endpoint (NEM-1582)
# =============================================================================

# AI Service definitions with display names and criticality
AI_SERVICES_CONFIG = [
    {
        "name": "yolo26",
        "display_name": "YOLO26 Object Detection",
        "url_attr": "yolo26_url",
        "circuit_breaker_name": "yolo26",
        "critical": True,
    },
    {
        "name": "nemotron",
        "display_name": "Nemotron LLM Risk Analysis",
        "url_attr": "nemotron_url",
        "circuit_breaker_name": "nemotron",
        "critical": True,
    },
    {
        "name": "florence",
        "display_name": "Florence-2 Vision Language",
        "url_attr": "florence_url",
        "circuit_breaker_name": "florence",
        "critical": False,
    },
    {
        "name": "clip",
        "display_name": "CLIP Embedding Service",
        "url_attr": "clip_url",
        "circuit_breaker_name": "clip",
        "critical": False,
    },
    {
        "name": "enrichment",
        "display_name": "Enrichment Service",
        "url_attr": "enrichment_url",
        "circuit_breaker_name": "enrichment",
        "critical": False,
    },
]


async def _check_ai_service_health(  # noqa: PLR0911
    service_config: dict[str, Any],
    settings: Settings,
    timeout: float = 5.0,
) -> AIServiceHealthStatus:
    """Check health of a single AI service.

    This function intentionally has multiple return statements for clarity
    in handling different health check scenarios (URL not configured,
    circuit open, HTTP success/error, connection errors, timeouts).
    """
    from backend.services.circuit_breaker import _get_registry

    name = service_config["name"]
    display_name = service_config["display_name"]
    url_attr = service_config["url_attr"]
    circuit_breaker_name = service_config.get("circuit_breaker_name", name)

    service_url = getattr(settings, url_attr, None)
    if not service_url:
        return AIServiceHealthStatus(
            name=name,
            display_name=display_name,
            status=ServiceHealthState.UNKNOWN,
            url="",
            error="Service URL not configured",
            circuit_state=CircuitState.CLOSED,
            last_check=datetime.now(UTC),
        )

    registry = _get_registry()
    circuit_state = CircuitState.CLOSED
    breaker = registry.get(circuit_breaker_name)
    if breaker is not None:
        state_value = breaker.state.value
        if state_value == "open":
            circuit_state = CircuitState.OPEN
        elif state_value == "half_open":
            circuit_state = CircuitState.HALF_OPEN

    if circuit_state == CircuitState.OPEN:
        return AIServiceHealthStatus(
            name=name,
            display_name=display_name,
            status=ServiceHealthState.UNHEALTHY,
            url=service_url,
            error="Circuit breaker is open - service unreachable",
            circuit_state=circuit_state,
            last_check=datetime.now(UTC),
        )

    start_time = time.time()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(f"{service_url}/health")
            response_time_ms = (time.time() - start_time) * 1000
            if response.status_code == 200:
                return AIServiceHealthStatus(
                    name=name,
                    display_name=display_name,
                    status=ServiceHealthState.HEALTHY,
                    url=service_url,
                    response_time_ms=round(response_time_ms, 2),
                    circuit_state=circuit_state,
                    last_check=datetime.now(UTC),
                )
            return AIServiceHealthStatus(
                name=name,
                display_name=display_name,
                status=ServiceHealthState.UNHEALTHY,
                url=service_url,
                response_time_ms=round(response_time_ms, 2),
                error=f"HTTP {response.status_code}",
                circuit_state=circuit_state,
                last_check=datetime.now(UTC),
            )
    except httpx.ConnectError:
        return AIServiceHealthStatus(
            name=name,
            display_name=display_name,
            status=ServiceHealthState.UNHEALTHY,
            url=service_url,
            error="Connection refused",
            circuit_state=circuit_state,
            last_check=datetime.now(UTC),
        )
    except httpx.TimeoutException:
        return AIServiceHealthStatus(
            name=name,
            display_name=display_name,
            status=ServiceHealthState.UNHEALTHY,
            url=service_url,
            error=f"Timeout after {timeout}s",
            circuit_state=circuit_state,
            last_check=datetime.now(UTC),
        )
    except Exception as e:
        return AIServiceHealthStatus(
            name=name,
            display_name=display_name,
            status=ServiceHealthState.UNHEALTHY,
            url=service_url,
            error=str(e),
            circuit_state=circuit_state,
            last_check=datetime.now(UTC),
        )


async def _check_postgres_health_full(db: AsyncSession) -> InfrastructureHealthStatus:
    """Check PostgreSQL database health."""
    try:
        result = await db.execute(select(func.now()))
        _ = result.scalar()
        return InfrastructureHealthStatus(
            name="postgres",
            status=ServiceHealthState.HEALTHY,
            message="Database operational",
            details=None,
        )
    except Exception as e:
        return InfrastructureHealthStatus(
            name="postgres",
            status=ServiceHealthState.UNHEALTHY,
            message=f"Database error: {e}",
            details=None,
        )


async def _check_redis_health_full(redis: RedisClient | None) -> InfrastructureHealthStatus:
    """Check Redis health."""
    if redis is None:
        return InfrastructureHealthStatus(
            name="redis",
            status=ServiceHealthState.UNHEALTHY,
            message="Redis client not available",
            details=None,
        )
    try:
        info = await redis.health_check()
        if info.get("error"):
            return InfrastructureHealthStatus(
                name="redis",
                status=ServiceHealthState.UNHEALTHY,
                message=f"Redis error: {info.get('error')}",
                details=None,
            )
        return InfrastructureHealthStatus(
            name="redis",
            status=ServiceHealthState.HEALTHY,
            message="Redis connected",
            details={"redis_version": info.get("redis_version", "unknown")},
        )
    except Exception as e:
        return InfrastructureHealthStatus(
            name="redis",
            status=ServiceHealthState.UNHEALTHY,
            message=f"Redis error: {e}",
            details=None,
        )


def _get_circuit_breaker_summary() -> CircuitBreakerSummary:
    """Get summary of all circuit breaker states."""
    from backend.services.circuit_breaker import _get_registry

    registry = _get_registry()
    all_status = registry.get_all_status()
    open_count = 0
    half_open_count = 0
    closed_count = 0
    breakers: dict[str, CircuitState] = {}

    for name, cb_status in all_status.items():
        state_value = cb_status.get("state", "closed")
        if state_value == "open":
            state = CircuitState.OPEN
            open_count += 1
        elif state_value == "half_open":
            state = CircuitState.HALF_OPEN
            half_open_count += 1
        else:
            state = CircuitState.CLOSED
            closed_count += 1
        breakers[name] = state

    return CircuitBreakerSummary(
        total=len(all_status),
        open=open_count,
        half_open=half_open_count,
        closed=closed_count,
        breakers=breakers,
    )


def _get_worker_status() -> list[WorkerHealthStatus]:
    """Get status of background workers."""
    workers: list[WorkerHealthStatus] = []

    # File watcher status - check if the module is loaded and functional
    # Since FileWatcher is typically started in main.py lifespan, we check the import
    try:
        from backend.services import file_watcher  # noqa: F401

        # Module exists, assume watcher is running if we got here in a live app
        # In production this would check actual watcher state
        workers.append(
            WorkerHealthStatus(
                name="file_watcher",
                running=True,
                critical=True,
            )
        )
    except ImportError:
        workers.append(
            WorkerHealthStatus(
                name="file_watcher",
                running=False,
                critical=True,
            )
        )

    # Cleanup service status
    if _cleanup_service is not None:
        stats = _cleanup_service.get_cleanup_stats()
        workers.append(
            WorkerHealthStatus(
                name="cleanup_service",
                running=stats.get("running", False),
                critical=False,
            )
        )
    else:
        workers.append(
            WorkerHealthStatus(
                name="cleanup_service",
                running=False,
                critical=False,
            )
        )
    return workers


async def _emit_full_health_status_changes(
    postgres_status: str,
    redis_status: str,
    ai_services: list[AIServiceHealthStatus],
) -> None:
    """Emit WebSocket events for full health status changes.

    This helper function tracks health state transitions for the full health
    endpoint, which provides more detailed AI service information.

    Args:
        postgres_status: Current PostgreSQL health status
        redis_status: Current Redis health status
        ai_services: List of AI service health statuses
    """
    try:
        health_emitter = get_health_event_emitter()

        # Try to set up the WebSocket emitter if not already configured
        if health_emitter._emitter is None:
            from backend.services.websocket_emitter import get_websocket_emitter_sync

            ws_emitter = get_websocket_emitter_sync()
            if ws_emitter is not None:
                health_emitter.set_emitter(ws_emitter)

        # Build status dict for all components
        statuses: dict[str, str] = {
            "database": postgres_status,
            "redis": redis_status,
        }

        # Add individual AI service statuses
        for ai_service in ai_services:
            # Use component names that match our tracking convention
            statuses[f"ai_{ai_service.name}"] = ai_service.status.value

        # Calculate overall AI service status
        ai_healthy = all(s.status == ServiceHealthState.HEALTHY for s in ai_services)
        ai_degraded = any(s.status == ServiceHealthState.HEALTHY for s in ai_services)
        if ai_healthy:
            statuses["ai_service"] = "healthy"
        elif ai_degraded:
            statuses["ai_service"] = "degraded"
        else:
            statuses["ai_service"] = "unhealthy"

        # Update all component statuses (emits events only on changes)
        await health_emitter.update_all_components(statuses=statuses)

    except Exception as e:
        # Don't let health event emission failures break health checks
        logger.warning(f"Failed to emit full health status change events: {e}", exc_info=True)


@router.get(
    "/health/full",
    response_model=FullHealthResponse,
    responses={
        200: {"description": "System is healthy"},
        503: {"description": "One or more critical services are unhealthy"},
    },
    summary="Get Full System Health Status",
)
async def get_full_health(
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: RedisClient | None = Depends(get_redis_optional),
) -> FullHealthResponse:
    """Get comprehensive health status for all system components."""
    settings = get_settings()

    postgres_task = _check_postgres_health_full(db)
    redis_task = _check_redis_health_full(redis)
    ai_tasks = [_check_ai_service_health(config, settings) for config in AI_SERVICES_CONFIG]

    results = await asyncio.gather(
        postgres_task,
        redis_task,
        *ai_tasks,
    )
    postgres_health: InfrastructureHealthStatus = results[0]  # type: ignore[assignment]
    redis_health: InfrastructureHealthStatus = results[1]  # type: ignore[assignment]
    ai_healths: list[AIServiceHealthStatus] = list(results[2:])  # type: ignore[arg-type]

    circuit_breaker_summary = _get_circuit_breaker_summary()
    workers = _get_worker_status()

    critical_unhealthy: list[str] = []
    non_critical_unhealthy: list[str] = []

    if postgres_health.status != ServiceHealthState.HEALTHY:
        critical_unhealthy.append("postgres")
    if redis_health.status != ServiceHealthState.HEALTHY:
        critical_unhealthy.append("redis")

    for i, health in enumerate(ai_healths):
        service_config = AI_SERVICES_CONFIG[i]
        if health.status != ServiceHealthState.HEALTHY:
            if service_config.get("critical", False):
                critical_unhealthy.append(health.name)
            else:
                non_critical_unhealthy.append(health.name)

    for worker in workers:
        if worker.critical and not worker.running:
            critical_unhealthy.append(worker.name)

    if critical_unhealthy:
        overall_status = ServiceHealthState.UNHEALTHY
        ready = False
        message = f"Critical services unhealthy: {', '.join(critical_unhealthy)}"
        response.status_code = 503
    elif non_critical_unhealthy:
        overall_status = ServiceHealthState.DEGRADED
        ready = True
        message = f"Degraded: {', '.join(non_critical_unhealthy)} unavailable"
    else:
        overall_status = ServiceHealthState.HEALTHY
        ready = True
        message = "All systems operational"

    # Emit WebSocket events for health status changes
    # This integrates with the full health check to provide comprehensive status updates
    await _emit_full_health_status_changes(
        postgres_status=postgres_health.status.value,
        redis_status=redis_health.status.value,
        ai_services=ai_healths,
    )

    return FullHealthResponse(
        status=overall_status,
        ready=ready,
        message=message,
        postgres=postgres_health,
        redis=redis_health,
        ai_services=ai_healths,
        circuit_breakers=circuit_breaker_summary,
        workers=workers,
        timestamp=datetime.now(UTC),
        version=settings.app_version,
    )
