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

from backend.api.schemas.services import ServiceInfo, ServiceStatusEvent
from backend.core.logging import get_logger
from backend.services.container_discovery import ContainerDiscoveryService
from backend.services.health_monitor_orchestrator import HealthMonitor
from backend.services.lifecycle_manager import LifecycleManager
from backend.services.orchestrator import (
    ContainerServiceStatus,
    ManagedService,
    ServiceRegistry,
)

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
    if service.status == ContainerServiceStatus.RUNNING and service.last_restart_at:
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
        # All modules now use the same shared ManagedService and ServiceRegistry types
        # from backend.services.orchestrator, so we use a single registry
        self._registry = ServiceRegistry(redis_client)
        self._discovery_service = ContainerDiscoveryService(docker_client)

        # These are created during start() after discovery
        self._health_monitor: HealthMonitor | None = None
        self._lifecycle_manager: LifecycleManager | None = None

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

    async def _on_health_change(self, service: ManagedService, is_healthy: bool) -> None:
        """Callback when health status changes.

        Called by HealthMonitor when a service health status changes.
        Since all modules now use the shared ManagedService type from
        backend.services.orchestrator, no type conversion is needed.

        Args:
            service: The service whose health changed
            is_healthy: True if service is now healthy, False if unhealthy
        """
        if is_healthy:
            await self._broadcast_status(service, "Service recovered")
        else:
            # Delegate to lifecycle manager for restart handling
            if self._lifecycle_manager:
                if service.status == ContainerServiceStatus.STOPPED:
                    await self._lifecycle_manager.handle_stopped(service)
                else:
                    await self._lifecycle_manager.handle_unhealthy(service)

            await self._broadcast_status(service, "Health check failed")

    async def _on_restart(self, service: ManagedService) -> None:
        """Callback after container restart.

        Called by LifecycleManager after a successful restart.

        Args:
            service: The service that was restarted
        """
        await self._broadcast_status(service, "Restart completed")

    async def _on_disabled(self, service: ManagedService) -> None:
        """Callback when service is disabled due to max failures.

        Called by LifecycleManager when a service exceeds max_failures.

        Args:
            service: The service that was disabled
        """
        await self._broadcast_status(service, "Service disabled - max failures reached")

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
        Uses the lifecycle manager which operates on the shared registry.

        Args:
            name: Service name

        Returns:
            True if service was enabled, False if not found
        """
        service = self._registry.get(name)
        if not service:
            logger.warning(f"Cannot enable unknown service: {name}")
            return False

        # Use lifecycle manager (operates on shared registry)
        if self._lifecycle_manager:
            await self._lifecycle_manager.enable_service(name)

        # Broadcast status change
        updated_service = self._registry.get(name)
        if updated_service:
            await self._broadcast_status(updated_service, "Service enabled")

        return True

    async def disable_service(self, name: str) -> bool:
        """Disable a service.

        Sets enabled flag to False and status to DISABLED.
        Uses the lifecycle manager which operates on the shared registry.

        Args:
            name: Service name

        Returns:
            True if service was disabled, False if not found
        """
        service = self._registry.get(name)
        if not service:
            logger.warning(f"Cannot disable unknown service: {name}")
            return False

        # Use lifecycle manager (operates on shared registry)
        if self._lifecycle_manager:
            await self._lifecycle_manager.disable_service(name)

        # Broadcast status change
        updated_service = self._registry.get(name)
        if updated_service:
            await self._broadcast_status(updated_service, "Service disabled")

        return True

    async def restart_service(self, name: str, reset_failures: bool = False) -> bool:
        """Manually restart a service.

        Broadcasts restart initiated, then success/failure.
        Uses the lifecycle manager which operates on the shared registry.

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

        # Broadcast restart initiated
        await self._broadcast_status(service, "Manual restart initiated")

        # Use lifecycle manager (operates on shared registry)
        if self._lifecycle_manager:
            success = await self._lifecycle_manager.restart_service(service)
            if success:
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
            self._registry.update_status(name, ContainerServiceStatus.STARTING)
            await self._registry.persist_state(name)
            updated_service = self._registry.get(name)
            if updated_service:
                await self._broadcast_status(updated_service, "Restart succeeded")
        else:
            await self._broadcast_status(service, "Restart failed")

        return success

    async def start_service(self, name: str) -> bool:
        """Start a stopped service.

        Uses the lifecycle manager which operates on the shared registry.

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

        # Use lifecycle manager (operates on shared registry)
        if self._lifecycle_manager:
            success = await self._lifecycle_manager.start_service(service)
            if success:
                updated_service = self._registry.get(name)
                if updated_service:
                    await self._broadcast_status(updated_service, "Service started")
            return success

        # Fallback: direct start via docker client
        success = await self._docker_client.start_container(service.container_id)
        if success:
            self._registry.update_status(name, ContainerServiceStatus.STARTING)
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
        # ContainerDiscoveryService now returns ManagedService directly
        # (from the shared orchestrator module), no conversion needed
        for svc in discovered:
            # Set initial status to RUNNING since we discovered it
            svc.status = ContainerServiceStatus.RUNNING
            self._registry.register(svc)

        # 4. Load persisted state from Redis
        await self._registry.load_all_state()
        logger.info("Loaded service state from Redis")

        # 5. Broadcast discovery for all services
        for svc in self._registry.get_all():
            await self._on_service_discovered(svc)

        # 6. Create lifecycle manager using the shared registry
        self._lifecycle_manager = LifecycleManager(
            registry=self._registry,
            docker_client=self._docker_client,
            on_restart=self._on_restart,
            on_disabled=self._on_disabled,
        )

        # 7. Create health monitor using the shared registry
        self._health_monitor = HealthMonitor(
            registry=self._registry,
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

    # Note: All modules (container_discovery, health_monitor_orchestrator,
    # lifecycle_manager, service_registry) now use the shared ManagedService
    # and ServiceRegistry types from backend.services.orchestrator.
    # This eliminates the need for type conversion or state synchronization
    # between multiple registries - all components operate on the same shared
    # registry instance.
