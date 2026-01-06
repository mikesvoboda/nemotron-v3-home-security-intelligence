"""Container Orchestrator with WebSocket event broadcasting.

This module provides the ContainerOrchestrator class that coordinates container
discovery, health monitoring, lifecycle management, and real-time WebSocket
broadcasting of service status changes.

Key Features:
- Service discovery using container name patterns
- Health monitoring with configurable intervals
- Self-healing restart logic with exponential backoff
- WebSocket broadcast of service status changes
- Integration with HealthMonitor and LifecycleManager components

Usage:
    from backend.services.container_orchestrator import (
        ContainerOrchestrator,
        create_service_status_event,
    )

    # Create orchestrator with broadcast function
    orchestrator = ContainerOrchestrator(
        docker_client=docker_client,
        redis_client=redis_client,
        settings=settings,
        broadcast_fn=event_broadcaster.broadcast_service_status,
    )

    # Start orchestrator (discovery + monitoring)
    await orchestrator.start()

    # ... orchestrator runs in background

    await orchestrator.stop()
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from backend.api.schemas.services import ServiceInfo, ServiceStatus, ServiceStatusEvent
from backend.core.logging import get_logger
from backend.services.container_discovery import ContainerDiscoveryService
from backend.services.container_discovery import ManagedService as DiscoveredService
from backend.services.health_monitor_orchestrator import HealthMonitor
from backend.services.health_monitor_orchestrator import (
    ManagedService as HealthMonitorService,
)
from backend.services.health_monitor_orchestrator import ServiceRegistry as HMServiceRegistry
from backend.services.lifecycle_manager import LifecycleManager
from backend.services.lifecycle_manager import ManagedService as LifecycleService
from backend.services.lifecycle_manager import ServiceRegistry as LMServiceRegistry
from backend.services.service_registry import ManagedService, ServiceRegistry

if TYPE_CHECKING:
    from backend.core.config import OrchestratorSettings
    from backend.core.docker_client import DockerClient
    from backend.core.redis import RedisClient

logger = get_logger(__name__)


def create_service_status_event(
    service: ManagedService,
    message: str,
) -> dict[str, Any]:
    """Create a WebSocket event for service status change.

    Creates a ServiceStatusEvent with the current service state, suitable
    for broadcasting via WebSocket to connected clients.

    Args:
        service: The ManagedService that changed
        message: Human-readable message about the change

    Returns:
        Dictionary suitable for WebSocket broadcast (JSON-serializable)
    """
    # Calculate uptime if running
    uptime_seconds = None
    if service.status == ServiceStatus.RUNNING and service.last_restart_at:
        uptime_seconds = int((datetime.now(UTC) - service.last_restart_at).total_seconds())

    service_info = ServiceInfo(
        name=service.name,
        display_name=service.display_name,
        category=service.category,
        status=service.status,
        enabled=service.enabled,
        container_id=service.container_id[:12] if service.container_id else None,
        image=service.image,
        port=service.port,
        failure_count=service.failure_count,
        restart_count=service.restart_count,
        last_restart_at=service.last_restart_at,
        uptime_seconds=uptime_seconds,
    )

    event = ServiceStatusEvent(
        type="service_status",
        data=service_info,
        message=message,
    )

    return event.model_dump(mode="json")


class ContainerOrchestrator:
    """Orchestrates container discovery, health monitoring, lifecycle, and broadcasting.

    This class integrates:
    - ContainerDiscoveryService: Discover containers by name pattern
    - ServiceRegistry: Store and manage service state
    - HealthMonitor: Periodic health checks
    - LifecycleManager: Restart logic with backoff
    - EventBroadcaster: WebSocket event distribution

    Broadcasts service status events when:
    - Service discovered on startup
    - Health check passes after failure (recovery)
    - Health check fails
    - Container restart initiated
    - Container restart succeeded
    - Container restart failed
    - Service disabled (max failures)
    - Service manually enabled
    - Service manually disabled
    - Service manually restarted

    Lifecycle:
    - start(): Discover containers, load Redis state, start monitoring
    - stop(): Stop monitoring, persist final state
    - get_all_services(): List all services
    - get_service(name): Get single service
    - restart_service(name): Manual restart
    - enable_service(name): Re-enable disabled service
    - disable_service(name): Manually disable service
    - start_service(name): Start stopped service
    """

    def __init__(
        self,
        docker_client: DockerClient,
        redis_client: RedisClient,
        settings: OrchestratorSettings,
        broadcast_fn: Callable[[dict[str, Any]], Awaitable[int]] | None = None,
    ) -> None:
        """Initialize the container orchestrator.

        Args:
            docker_client: DockerClient for container operations
            redis_client: RedisClient for state persistence
            settings: OrchestratorSettings with configuration
            broadcast_fn: Optional async function to broadcast events via WebSocket.
                          Should accept a dict and return number of subscribers.
                          If None, broadcasting is disabled.
        """
        self._docker_client = docker_client
        self._redis_client = redis_client
        self._settings = settings
        self._broadcast_fn = broadcast_fn
        self._running = False

        # Create components - registry needs Redis client
        self._registry = ServiceRegistry(redis_client)
        self._discovery_service = ContainerDiscoveryService(docker_client)

        # These are created during start() after discovery
        self._health_monitor: HealthMonitor | None = None
        self._lifecycle_manager: LifecycleManager | None = None

        # Internal registries for health monitor and lifecycle manager
        self._hm_registry: HMServiceRegistry | None = None
        self._lm_registry: LMServiceRegistry | None = None

        logger.info("ContainerOrchestrator initialized")

    @property
    def is_running(self) -> bool:
        """Check if the orchestrator is running."""
        return self._running

    # =========================================================================
    # Service Query Methods
    # =========================================================================

    def get_all_services(self) -> list[ManagedService]:
        """Get all registered services.

        Returns:
            List of all ManagedService instances
        """
        return self._registry.get_all()

    def get_service(self, name: str) -> ManagedService | None:
        """Get a service by name.

        Args:
            name: Service name

        Returns:
            ManagedService or None if not found
        """
        return self._registry.get(name)

    # =========================================================================
    # Broadcasting
    # =========================================================================

    async def _broadcast_status(self, service: ManagedService, message: str) -> None:
        """Broadcast service status change via WebSocket.

        Args:
            service: The ManagedService that changed
            message: Human-readable message about the change
        """
        if self._broadcast_fn is None:
            logger.debug(f"Broadcast disabled, skipping: {message} for {service.name}")
            return

        try:
            event = create_service_status_event(service, message)
            subscriber_count = await self._broadcast_fn(event)
            logger.debug(
                f"Broadcast service status: {message} for {service.name} "
                f"(subscribers: {subscriber_count})"
            )
        except Exception as e:
            # Log but don't fail - broadcasting is non-critical
            logger.warning(f"Failed to broadcast service status for {service.name}: {e}")

    # =========================================================================
    # Callbacks
    # =========================================================================

    async def _on_health_change(self, service: HealthMonitorService, is_healthy: bool) -> None:
        """Callback when health status changes.

        Called by HealthMonitor when a service health status changes.

        Args:
            service: The service whose health changed
            is_healthy: True if service is now healthy, False if unhealthy
        """
        # Sync state to main registry
        self._sync_hm_state(service.name)

        # Get the main registry service for broadcasting
        main_service = self._registry.get(service.name)
        if not main_service:
            return

        if is_healthy:
            await self._broadcast_status(main_service, "Service recovered")
        else:
            # Delegate to lifecycle manager for restart handling
            if self._lifecycle_manager and self._lm_registry:
                lm_service = self._lm_registry.get(service.name)
                if lm_service:
                    if service.status == ServiceStatus.STOPPED:
                        await self._lifecycle_manager.handle_stopped(lm_service)
                    else:
                        await self._lifecycle_manager.handle_unhealthy(lm_service)
                    # Sync lifecycle state back
                    self._sync_lm_state(service.name)

            await self._broadcast_status(main_service, "Health check failed")

    async def _on_restart(self, service: LifecycleService) -> None:
        """Callback after container restart.

        Called by LifecycleManager after a successful restart.

        Args:
            service: The service that was restarted
        """
        self._sync_lm_state(service.name)
        main_service = self._registry.get(service.name)
        if main_service:
            await self._broadcast_status(main_service, "Restart completed")

    async def _on_disabled(self, service: LifecycleService) -> None:
        """Callback when service is disabled due to max failures.

        Called by LifecycleManager when a service exceeds max_failures.

        Args:
            service: The service that was disabled
        """
        self._sync_lm_state(service.name)
        main_service = self._registry.get(service.name)
        if main_service:
            await self._broadcast_status(main_service, "Service disabled - max failures reached")

    async def _on_service_discovered(self, service: ManagedService) -> None:
        """Callback when a service is discovered during startup.

        Args:
            service: The ManagedService that was discovered
        """
        await self._broadcast_status(service, "Service discovered")

    # =========================================================================
    # Service Control Methods
    # =========================================================================

    async def enable_service(self, name: str) -> bool:
        """Enable a disabled service.

        Resets failure count and sets enabled flag to True.

        Args:
            name: Service name

        Returns:
            True if service was enabled, False if not found
        """
        service = self._registry.get(name)
        if not service:
            logger.warning(f"Cannot enable unknown service: {name}")
            return False

        # Update main registry
        self._registry.reset_failures(name)
        self._registry.set_enabled(name, True)
        self._registry.update_status(name, ServiceStatus.STOPPED)
        await self._registry.persist_state(name)

        # Update lifecycle registry if available
        if self._lifecycle_manager:
            await self._lifecycle_manager.enable_service(name)
            self._sync_lm_state(name)

        # Broadcast status change
        updated_service = self._registry.get(name)
        if updated_service:
            await self._broadcast_status(updated_service, "Service enabled")

        return True

    async def disable_service(self, name: str) -> bool:
        """Disable a service.

        Sets enabled flag to False and status to DISABLED.

        Args:
            name: Service name

        Returns:
            True if service was disabled, False if not found
        """
        service = self._registry.get(name)
        if not service:
            logger.warning(f"Cannot disable unknown service: {name}")
            return False

        # Update main registry
        self._registry.set_enabled(name, False)
        self._registry.update_status(name, ServiceStatus.DISABLED)
        await self._registry.persist_state(name)

        # Update lifecycle registry if available
        if self._lifecycle_manager:
            await self._lifecycle_manager.disable_service(name)
            self._sync_lm_state(name)

        # Broadcast status change
        updated_service = self._registry.get(name)
        if updated_service:
            await self._broadcast_status(updated_service, "Service disabled")

        return True

    async def restart_service(self, name: str, reset_failures: bool = False) -> bool:
        """Manually restart a service.

        Broadcasts restart initiated, then success/failure.

        Args:
            name: Service name
            reset_failures: If True, reset failure count before restart

        Returns:
            True if restart succeeded, False otherwise
        """
        service = self._registry.get(name)
        if not service:
            logger.warning(f"Cannot restart unknown service: {name}")
            return False

        if not service.container_id:
            logger.warning(f"Cannot restart {name}: no container_id")
            return False

        if reset_failures:
            self._registry.reset_failures(name)
            if self._lm_registry:
                self._lm_registry.reset_failures(name)

        # Broadcast restart initiated
        await self._broadcast_status(service, "Manual restart initiated")

        # Use lifecycle manager if available
        if self._lifecycle_manager and self._lm_registry:
            lm_service = self._lm_registry.get(name)
            if lm_service:
                success = await self._lifecycle_manager.restart_service(lm_service)
                if success:
                    self._sync_lm_state(name)
                    updated_service = self._registry.get(name)
                    if updated_service:
                        await self._broadcast_status(updated_service, "Restart succeeded")
                else:
                    await self._broadcast_status(service, "Restart failed")
                return success

        # Fallback: direct restart via docker client
        success = await self._docker_client.restart_container(service.container_id)
        if success:
            self._registry.record_restart(name)
            self._registry.update_status(name, ServiceStatus.STARTING)
            await self._registry.persist_state(name)
            updated_service = self._registry.get(name)
            if updated_service:
                await self._broadcast_status(updated_service, "Restart succeeded")
        else:
            await self._broadcast_status(service, "Restart failed")

        return success

    async def start_service(self, name: str) -> bool:
        """Start a stopped service.

        Args:
            name: Service name

        Returns:
            True if start succeeded, False otherwise
        """
        service = self._registry.get(name)
        if not service:
            logger.warning(f"Cannot start unknown service: {name}")
            return False

        if not service.container_id:
            logger.warning(f"Cannot start {name}: no container_id")
            return False

        # Use lifecycle manager if available
        if self._lifecycle_manager and self._lm_registry:
            lm_service = self._lm_registry.get(name)
            if lm_service:
                success = await self._lifecycle_manager.start_service(lm_service)
                if success:
                    self._sync_lm_state(name)
                    updated_service = self._registry.get(name)
                    if updated_service:
                        await self._broadcast_status(updated_service, "Service started")
                return success

        # Fallback: direct start via docker client
        success = await self._docker_client.start_container(service.container_id)
        if success:
            self._registry.update_status(name, ServiceStatus.STARTING)
            await self._registry.persist_state(name)
            updated_service = self._registry.get(name)
            if updated_service:
                await self._broadcast_status(updated_service, "Service started")

        return success

    # =========================================================================
    # Startup / Shutdown
    # =========================================================================

    async def start(self) -> None:
        """Start the orchestrator.

        Full startup sequence:
        1. Check if enabled in settings
        2. Verify Docker connection with ping
        3. Run container discovery
        4. Load persisted state from Redis
        5. Create HealthMonitor with callback that uses LifecycleManager
        6. Start the health monitor

        This method is idempotent - calling when running has no effect.
        """
        if not self._settings.enabled:
            logger.info("Container orchestrator disabled in settings")
            return

        if self._running:
            logger.warning("ContainerOrchestrator already running")
            return

        logger.info("Starting ContainerOrchestrator")

        # 1. Verify Docker connection
        connected = await self._docker_client.connect()
        if not connected:
            logger.error("Failed to connect to Docker daemon - orchestrator not starting")
            return

        logger.info("Connected to Docker daemon")

        # 2. Discover containers
        discovered = await self._discovery_service.discover_all()
        logger.info(f"Discovered {len(discovered)} containers")

        # 3. Register discovered services in our registry
        for disc_svc in discovered:
            managed = self._convert_discovered_to_managed(disc_svc)
            self._registry.register(managed)

        # 4. Load persisted state from Redis
        await self._registry.load_all_state()
        logger.info("Loaded service state from Redis")

        # 5. Create internal registries and populate them
        self._hm_registry = HMServiceRegistry()
        self._lm_registry = LMServiceRegistry(redis_client=self._redis_client)

        for svc in self._registry.get_all():
            # Convert to health monitor service type
            hm_service = self._convert_to_hm_service(svc)
            self._hm_registry.register(hm_service)

            # Convert to lifecycle manager service type
            lm_service = self._convert_to_lm_service(svc)
            self._lm_registry.register(lm_service)

            # Broadcast discovery
            await self._on_service_discovered(svc)

        # 6. Create lifecycle manager
        self._lifecycle_manager = LifecycleManager(
            registry=self._lm_registry,
            docker_client=self._docker_client,
            on_restart=self._on_restart,
            on_disabled=self._on_disabled,
        )

        # 7. Create health monitor with callback
        self._health_monitor = HealthMonitor(
            registry=self._hm_registry,
            docker_client=self._docker_client,
            settings=self._settings,
            on_health_change=self._on_health_change,
        )

        # 8. Start health monitor
        await self._health_monitor.start()
        self._running = True

        logger.info("ContainerOrchestrator started")

    async def stop(self) -> None:
        """Stop the orchestrator gracefully.

        Shutdown sequence:
        1. Stop health monitor
        2. Persist final state for all services
        3. Do NOT stop containers (they run independently)
        """
        if not self._running:
            logger.debug("ContainerOrchestrator not running")
            return

        logger.info("Stopping ContainerOrchestrator")

        # 1. Stop health monitor
        if self._health_monitor:
            await self._health_monitor.stop()
            self._health_monitor = None

        # 2. Persist final state for all services
        for svc in self._registry.get_all():
            await self._registry.persist_state(svc.name)

        logger.info("Persisted final state for all services")

        # Note: We do NOT stop containers - they run independently

        self._running = False
        logger.info("ContainerOrchestrator stopped")

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _convert_discovered_to_managed(self, discovered: DiscoveredService) -> ManagedService:
        """Convert a DiscoveredService to ManagedService for our registry.

        Args:
            discovered: Service from ContainerDiscoveryService

        Returns:
            ManagedService for ServiceRegistry
        """
        return ManagedService(
            name=discovered.name,
            display_name=discovered.display_name,
            container_id=discovered.container_id,
            image=discovered.image,
            port=discovered.port,
            health_endpoint=discovered.health_endpoint,
            health_cmd=discovered.health_cmd,
            category=discovered.category,
            status=ServiceStatus.RUNNING,  # Assume running since we discovered it
            enabled=True,
            max_failures=discovered.max_failures,
            restart_backoff_base=discovered.restart_backoff_base,
            restart_backoff_max=discovered.restart_backoff_max,
            startup_grace_period=discovered.startup_grace_period,
        )

    def _convert_to_hm_service(self, service: ManagedService) -> HealthMonitorService:
        """Convert ManagedService to HealthMonitorService.

        Args:
            service: Service from our registry

        Returns:
            ManagedService for HealthMonitor registry
        """
        return HealthMonitorService(
            name=service.name,
            container_id=service.container_id,
            image=service.image or "",
            port=service.port,
            category=service.category,
            health_endpoint=service.health_endpoint,
            health_cmd=service.health_cmd,
            status=service.status,
            enabled=service.enabled,
            failure_count=service.failure_count,
            last_failure_at=service.last_failure_at,
            last_restart_at=service.last_restart_at,
            restart_count=service.restart_count,
            max_failures=service.max_failures,
            restart_backoff_base=service.restart_backoff_base,
            restart_backoff_max=service.restart_backoff_max,
            startup_grace_period=service.startup_grace_period,
        )

    def _convert_to_lm_service(self, service: ManagedService) -> LifecycleService:
        """Convert ManagedService to LifecycleService.

        Args:
            service: Service from our registry

        Returns:
            ManagedService for LifecycleManager registry
        """
        # LifecycleService uses Unix timestamp for last_failure_at
        last_failure_ts = None
        if service.last_failure_at:
            last_failure_ts = service.last_failure_at.timestamp()

        return LifecycleService(
            name=service.name,
            display_name=service.display_name,
            container_id=service.container_id,
            image=service.image or "",
            port=service.port,
            health_endpoint=service.health_endpoint,
            health_cmd=service.health_cmd,
            category=service.category,
            status=service.status,
            enabled=service.enabled,
            failure_count=service.failure_count,
            restart_count=service.restart_count,
            last_failure_at=last_failure_ts,
            last_restart_at=service.last_restart_at,
            max_failures=service.max_failures,
            restart_backoff_base=service.restart_backoff_base,
            restart_backoff_max=service.restart_backoff_max,
        )

    def _sync_hm_state(self, name: str) -> None:
        """Sync state from health monitor registry to main registry.

        Args:
            name: Service name to sync
        """
        if not self._hm_registry:
            return

        hm_service = self._hm_registry.get(name)
        main_service = self._registry.get(name)

        if not hm_service or not main_service:
            return

        # Update main registry state
        main_service.status = hm_service.status
        main_service.failure_count = hm_service.failure_count
        main_service.last_failure_at = hm_service.last_failure_at
        main_service.last_restart_at = hm_service.last_restart_at
        main_service.restart_count = hm_service.restart_count

    def _sync_lm_state(self, name: str) -> None:
        """Sync state from lifecycle registry to main registry.

        Args:
            name: Service name to sync
        """
        if not self._lm_registry:
            return

        lm_service = self._lm_registry.get(name)
        main_service = self._registry.get(name)

        if not lm_service or not main_service:
            return

        # Update main registry state
        main_service.status = lm_service.status
        main_service.enabled = lm_service.enabled
        main_service.failure_count = lm_service.failure_count
        main_service.restart_count = lm_service.restart_count
        main_service.last_restart_at = lm_service.last_restart_at
