"""Health Service Registry for dependency injection (NEM-2611).

This module provides a centralized registry for health monitoring services,
replacing the global state pattern with proper dependency injection.

The registry tracks background workers and health monitors:
- GPUMonitor: GPU resource monitoring
- CleanupService: Data cleanup service
- SystemBroadcaster: WebSocket system status broadcasting
- FileWatcher: File system monitoring for camera images
- PipelineWorkerManager: Detection/analysis pipeline workers
- BatchAggregator: Batch processing for detections
- DegradationManager: Service degradation mode management
- ServiceHealthMonitor: Auto-recovery health monitoring
- PerformanceCollector: Performance metrics collection
- HealthEventEmitter: WebSocket health status event emission

The registry is initialized during application startup via the lifespan
context manager and provides dependencies for FastAPI route handlers.

Usage:
    # Get the registry from container
    container = get_container()
    registry = await container.get_async("health_service_registry")

    # Or use FastAPI dependency
    @app.get("/health")
    async def get_health(
        registry: HealthServiceRegistry = Depends(get_health_registry),
    ):
        return registry.get_all_worker_statuses()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from backend.services.batch_aggregator import BatchAggregator
    from backend.services.cleanup_service import CleanupService
    from backend.services.degradation_manager import DegradationManager
    from backend.services.file_watcher import FileWatcher
    from backend.services.gpu_monitor import GPUMonitor
    from backend.services.health_event_emitter import HealthEventEmitter
    from backend.services.health_monitor import ServiceHealthMonitor
    from backend.services.performance_collector import PerformanceCollector
    from backend.services.pipeline_workers import PipelineWorkerManager
    from backend.services.system_broadcaster import SystemBroadcaster

logger = get_logger(__name__)


@dataclass(slots=True)
class WorkerStatus:
    """Status information for a background worker.

    Attributes:
        name: Worker identifier
        running: Whether the worker is currently running
        message: Optional status message (usually set when not running)
    """

    name: str
    running: bool
    message: str | None = None


@dataclass
class HealthCircuitBreaker:
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
    _failures: dict[str, int] = field(default_factory=dict, init=False, repr=False)
    _open_until: dict[str, datetime] = field(default_factory=dict, init=False, repr=False)
    _last_error: dict[str, str] = field(default_factory=dict, init=False, repr=False)

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


class HealthServiceRegistry:
    """Registry for health monitoring services.

    This class provides a centralized location for accessing health monitoring
    services without using global state. Services are registered during
    application startup and can be accessed via dependency injection.

    The registry follows the Service Locator pattern but is managed by the
    DI container, allowing for proper testing and service isolation.

    Attributes:
        gpu_monitor: GPU monitoring service
        cleanup_service: Data cleanup service
        system_broadcaster: WebSocket system status broadcaster
        file_watcher: File system watcher for camera images
        pipeline_manager: Detection/analysis pipeline worker manager
        batch_aggregator: Batch processing aggregator
        degradation_manager: Service degradation manager
        service_health_monitor: Auto-recovery health monitor
        performance_collector: Performance metrics collector
        health_event_emitter: WebSocket health event emitter
        circuit_breaker: Health check circuit breaker
    """

    def __init__(
        self,
        gpu_monitor: GPUMonitor | None = None,
        cleanup_service: CleanupService | None = None,
        system_broadcaster: SystemBroadcaster | None = None,
        file_watcher: FileWatcher | None = None,
        pipeline_manager: PipelineWorkerManager | None = None,
        batch_aggregator: BatchAggregator | None = None,
        degradation_manager: DegradationManager | None = None,
        service_health_monitor: ServiceHealthMonitor | None = None,
        performance_collector: PerformanceCollector | None = None,
        health_event_emitter: HealthEventEmitter | None = None,
    ) -> None:
        """Initialize the health service registry.

        Args:
            gpu_monitor: GPU monitoring service
            cleanup_service: Data cleanup service
            system_broadcaster: WebSocket system status broadcaster
            file_watcher: File system watcher
            pipeline_manager: Pipeline worker manager
            batch_aggregator: Batch processing aggregator
            degradation_manager: Service degradation manager
            service_health_monitor: Auto-recovery health monitor
            performance_collector: Performance metrics collector
            health_event_emitter: WebSocket health event emitter
        """
        self._gpu_monitor = gpu_monitor
        self._cleanup_service = cleanup_service
        self._system_broadcaster = system_broadcaster
        self._file_watcher = file_watcher
        self._pipeline_manager = pipeline_manager
        self._batch_aggregator = batch_aggregator
        self._degradation_manager = degradation_manager
        self._service_health_monitor = service_health_monitor
        self._performance_collector = performance_collector
        self._health_event_emitter = health_event_emitter
        self._circuit_breaker = HealthCircuitBreaker()

        logger.info("HealthServiceRegistry initialized")

    # ==========================================================================
    # Property accessors for services
    # ==========================================================================

    @property
    def gpu_monitor(self) -> GPUMonitor | None:
        """Get the GPU monitor service."""
        return self._gpu_monitor

    @property
    def cleanup_service(self) -> CleanupService | None:
        """Get the cleanup service."""
        return self._cleanup_service

    @property
    def system_broadcaster(self) -> SystemBroadcaster | None:
        """Get the system broadcaster."""
        return self._system_broadcaster

    @property
    def file_watcher(self) -> FileWatcher | None:
        """Get the file watcher."""
        return self._file_watcher

    @property
    def pipeline_manager(self) -> PipelineWorkerManager | None:
        """Get the pipeline worker manager."""
        return self._pipeline_manager

    @property
    def batch_aggregator(self) -> BatchAggregator | None:
        """Get the batch aggregator."""
        return self._batch_aggregator

    @property
    def degradation_manager(self) -> DegradationManager | None:
        """Get the degradation manager."""
        return self._degradation_manager

    @property
    def service_health_monitor(self) -> ServiceHealthMonitor | None:
        """Get the service health monitor."""
        return self._service_health_monitor

    @property
    def performance_collector(self) -> PerformanceCollector | None:
        """Get the performance collector."""
        return self._performance_collector

    @property
    def health_event_emitter(self) -> HealthEventEmitter | None:
        """Get the health event emitter."""
        return self._health_event_emitter

    @property
    def circuit_breaker(self) -> HealthCircuitBreaker:
        """Get the health check circuit breaker."""
        return self._circuit_breaker

    # ==========================================================================
    # Registration methods for deferred initialization
    # ==========================================================================

    def register_gpu_monitor(self, gpu_monitor: GPUMonitor) -> None:
        """Register the GPU monitor service.

        Args:
            gpu_monitor: GPU monitoring service instance
        """
        self._gpu_monitor = gpu_monitor
        logger.debug("Registered gpu_monitor in health registry")

    def register_cleanup_service(self, cleanup_service: CleanupService) -> None:
        """Register the cleanup service.

        Args:
            cleanup_service: Cleanup service instance
        """
        self._cleanup_service = cleanup_service
        logger.debug("Registered cleanup_service in health registry")

    def register_system_broadcaster(self, system_broadcaster: SystemBroadcaster) -> None:
        """Register the system broadcaster.

        Args:
            system_broadcaster: System broadcaster instance
        """
        self._system_broadcaster = system_broadcaster
        logger.debug("Registered system_broadcaster in health registry")

    def register_file_watcher(self, file_watcher: FileWatcher) -> None:
        """Register the file watcher.

        Args:
            file_watcher: File watcher instance
        """
        self._file_watcher = file_watcher
        logger.debug("Registered file_watcher in health registry")

    def register_pipeline_manager(self, pipeline_manager: PipelineWorkerManager) -> None:
        """Register the pipeline worker manager.

        Args:
            pipeline_manager: Pipeline worker manager instance
        """
        self._pipeline_manager = pipeline_manager
        logger.debug("Registered pipeline_manager in health registry")

    def register_batch_aggregator(self, batch_aggregator: BatchAggregator) -> None:
        """Register the batch aggregator.

        Args:
            batch_aggregator: Batch aggregator instance
        """
        self._batch_aggregator = batch_aggregator
        logger.debug("Registered batch_aggregator in health registry")

    def register_degradation_manager(self, degradation_manager: DegradationManager) -> None:
        """Register the degradation manager.

        Args:
            degradation_manager: Degradation manager instance
        """
        self._degradation_manager = degradation_manager
        logger.debug("Registered degradation_manager in health registry")

    def register_service_health_monitor(self, service_health_monitor: ServiceHealthMonitor) -> None:
        """Register the service health monitor.

        Args:
            service_health_monitor: Service health monitor instance
        """
        self._service_health_monitor = service_health_monitor
        logger.debug("Registered service_health_monitor in health registry")

    def register_performance_collector(self, performance_collector: PerformanceCollector) -> None:
        """Register the performance collector.

        Args:
            performance_collector: Performance collector instance
        """
        self._performance_collector = performance_collector
        logger.debug("Registered performance_collector in health registry")

    def register_health_event_emitter(self, health_event_emitter: HealthEventEmitter) -> None:
        """Register the health event emitter.

        Args:
            health_event_emitter: Health event emitter instance
        """
        self._health_event_emitter = health_event_emitter
        logger.debug("Registered health_event_emitter in health registry")

    # ==========================================================================
    # Worker status methods
    # ==========================================================================

    def get_worker_statuses(self) -> list[WorkerStatus]:
        """Get status of all registered background workers.

        Returns:
            List of WorkerStatus objects for each registered worker
        """
        statuses: list[WorkerStatus] = []

        # Check GPU monitor
        if self._gpu_monitor is not None:
            is_running = getattr(self._gpu_monitor, "running", False)
            statuses.append(
                WorkerStatus(
                    name="gpu_monitor",
                    running=is_running,
                    message=None if is_running else "Not running",
                )
            )

        # Check cleanup service
        if self._cleanup_service is not None:
            is_running = getattr(self._cleanup_service, "running", False)
            statuses.append(
                WorkerStatus(
                    name="cleanup_service",
                    running=is_running,
                    message=None if is_running else "Not running",
                )
            )

        # Check system broadcaster
        if self._system_broadcaster is not None:
            is_running = getattr(self._system_broadcaster, "_running", False)
            statuses.append(
                WorkerStatus(
                    name="system_broadcaster",
                    running=is_running,
                    message=None if is_running else "Not running",
                )
            )

        # Check file watcher
        if self._file_watcher is not None:
            is_running = getattr(self._file_watcher, "running", False)
            statuses.append(
                WorkerStatus(
                    name="file_watcher",
                    running=is_running,
                    message=None if is_running else "Not running",
                )
            )

        # Check pipeline workers (detection and analysis workers are critical)
        if self._pipeline_manager is not None:
            manager_status = self._pipeline_manager.get_status()
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

            # Batch timeout worker (non-critical)
            if "batch_timeout" in workers_dict:
                batch_state = workers_dict["batch_timeout"].get("state", "stopped")
                is_running = batch_state == "running"
                statuses.append(
                    WorkerStatus(
                        name="batch_timeout_worker",
                        running=is_running,
                        message=None if is_running else f"State: {batch_state}",
                    )
                )

        return statuses

    def are_critical_pipeline_workers_healthy(self) -> bool:
        """Check if critical pipeline workers are running.

        Returns:
            True if detection and analysis workers are running, False otherwise
        """
        if self._pipeline_manager is None:
            return False

        manager_status = self._pipeline_manager.get_status()
        workers_dict = manager_status.get("workers", {})

        detection_running: bool = workers_dict.get("detection", {}).get("state") == "running"
        analysis_running: bool = workers_dict.get("analysis", {}).get("state") == "running"

        return detection_running and analysis_running

    def get_pipeline_status(self) -> dict[str, Any]:
        """Get the full pipeline status.

        Returns:
            Dictionary with pipeline status details
        """
        if self._pipeline_manager is None:
            return {"error": "Pipeline manager not initialized"}
        return self._pipeline_manager.get_status()

    def has_batch_aggregator(self) -> bool:
        """Check if batch aggregator is registered.

        Note: Batch aggregator status is typically fetched from Redis,
        not from the aggregator instance itself.

        Returns:
            True if batch aggregator is registered
        """
        return self._batch_aggregator is not None

    def has_degradation_manager(self) -> bool:
        """Check if degradation manager is registered.

        Returns:
            True if degradation manager is registered
        """
        return self._degradation_manager is not None

    def get_health_events(self, limit: int = 50) -> list[Any]:
        """Get recent health events from the service health monitor.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of recent health events
        """
        if self._service_health_monitor is None:
            return []
        return self._service_health_monitor.get_recent_events(limit=limit)


# =============================================================================
# FastAPI Dependency Functions
# =============================================================================


async def get_health_registry() -> HealthServiceRegistry:
    """FastAPI dependency to get the health service registry.

    This function retrieves the HealthServiceRegistry from the DI container.

    Returns:
        HealthServiceRegistry instance

    Raises:
        RuntimeError: If registry is not initialized
    """
    from backend.core.container import get_container

    container = get_container()
    try:
        result = await container.get_async("health_service_registry")
        # Cast to proper type since container returns Any
        return result  # type: ignore[no-any-return]
    except Exception as e:
        logger.error(f"Failed to get health_service_registry: {e}")
        raise RuntimeError("Health service registry not initialized") from e


def get_health_registry_optional() -> HealthServiceRegistry | None:
    """Get the health service registry if available (synchronous).

    This function attempts to get the registry synchronously for backward
    compatibility with existing code.

    Returns:
        HealthServiceRegistry instance or None if not available
    """
    from backend.core.container import ServiceNotFoundError, get_container

    container = get_container()
    try:
        registration = container._registrations.get("health_service_registry")
        if registration and registration.instance is not None:
            # Cast to proper type since container stores Any
            instance: HealthServiceRegistry = registration.instance
            return instance
        return None
    except (ServiceNotFoundError, KeyError):
        return None
