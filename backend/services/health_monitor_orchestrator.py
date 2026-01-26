"""Health monitoring loop for container orchestrator.

This module provides health monitoring for Docker/Podman containers managed by
the container orchestrator. It periodically checks the health of all enabled
services and triggers restarts when needed.

Key Features:
- HTTP health endpoint checks for AI services (YOLO26v2, Nemotron, Florence, etc.)
- Command-based health checks for infrastructure (PostgreSQL, Redis)
- Container running status as fallback health check
- Grace period support for recently started containers
- Failure tracking with automatic status updates
- Callback support for health change notifications
- Background loop with configurable check interval

This is separate from ServiceHealthMonitor which uses ServiceManager/ServiceConfig
for a different purpose (AI service restart scripts). This module uses DockerClient
for container management through Docker API.

Usage:
    registry = ServiceRegistry()
    registry.register(managed_service)

    async with DockerClient() as docker:
        monitor = HealthMonitor(
            registry=registry,
            docker_client=docker,
            settings=orchestrator_settings,
            on_health_change=my_callback,
        )
        await monitor.start()
        # ... monitor runs in background
        await monitor.stop()
"""

from __future__ import annotations

import asyncio
import contextlib
from collections import deque
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import httpx

from backend.core.logging import get_logger
from backend.services.health_monitor import HealthEvent
from backend.services.orchestrator import (
    ContainerServiceStatus,
    ManagedService,
    ServiceRegistry,
)

if TYPE_CHECKING:
    from backend.core.config import OrchestratorSettings
    from backend.core.docker_client import DockerClient

logger = get_logger(__name__)


# =============================================================================
# Health Check Functions
# =============================================================================


async def check_http_health(
    host: str,
    port: int,
    endpoint: str,
    timeout: float = 5.0,
) -> bool:
    """HTTP GET to health endpoint, returns True if status 200.

    Args:
        host: Host to connect to (e.g., 'localhost', '127.0.0.1')
        port: Port number (e.g., 8090)
        endpoint: Health endpoint path (e.g., '/health')
        timeout: Request timeout in seconds

    Returns:
        True if the health endpoint returns HTTP 200, False otherwise.
    """
    url = f"http://{host}:{port}{endpoint}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.get(url)
            return bool(response.status_code == 200)
        except (httpx.RequestError, httpx.TimeoutException) as e:
            logger.debug(f"HTTP health check failed for {url}: {e}")
            return False


async def check_cmd_health(
    docker_client: DockerClient,
    container_id: str,
    cmd: str,
    timeout: int = 5,
) -> bool:
    """Execute health command inside container, returns True if exit code 0.

    Args:
        docker_client: DockerClient instance for container operations
        container_id: Docker container ID
        cmd: Command to execute (e.g., 'pg_isready -U security')
        timeout: Timeout for command execution

    Returns:
        True if command exits with code 0, False otherwise.
    """
    try:
        exit_code = await docker_client.exec_run(container_id, cmd, timeout=timeout)
        return exit_code == 0
    except Exception as e:
        logger.debug(f"Command health check failed for {container_id}: {e}")
        return False


# Note: ManagedService and ServiceRegistry are imported from
# backend.services.orchestrator - the shared domain models module.
# The classes provide all the functionality needed for health monitoring,
# including warmth state tracking (NEM-1670).


# =============================================================================
# HealthMonitor Class
# =============================================================================


class HealthMonitor:
    """Health monitoring loop for container orchestrator.

    Runs every N seconds (default 30), checking all enabled services and
    triggering status updates when health changes.

    Health Check Methods (in priority order):
    1. HTTP health check - For services with health_endpoint
    2. Command health check - For services with health_cmd
    3. Container running check - Fallback if neither defined

    Grace Period:
    Services are not health-checked during their startup grace period
    (e.g., 60 seconds for AI services, 10 seconds for PostgreSQL).
    This allows time for the service to initialize.
    """

    def __init__(
        self,
        registry: ServiceRegistry,
        docker_client: DockerClient,
        settings: OrchestratorSettings,
        on_health_change: Callable[[ManagedService, bool], Awaitable[None]] | None = None,
        max_events: int = 100,
    ) -> None:
        """Initialize the health monitor.

        Args:
            registry: ServiceRegistry containing managed services
            docker_client: DockerClient for container operations
            settings: OrchestratorSettings with health check configuration
            on_health_change: Optional callback invoked when health status changes.
                              Called with (service, is_healthy).
            max_events: Maximum number of health events to track (default: 100)
        """
        self._registry = registry
        self._docker_client = docker_client
        self._settings = settings
        self._on_health_change = on_health_change
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._health_events: deque[HealthEvent] = deque(maxlen=max_events)

        logger.info(
            "HealthMonitor initialized",
            extra={
                "health_check_interval": settings.health_check_interval,
                "health_check_timeout": settings.health_check_timeout,
            },
        )

    @property
    def is_running(self) -> bool:
        """Check if the health monitor is running."""
        return self._running

    async def start(self) -> None:
        """Start the health check background loop.

        This method is idempotent - calling it when already running has no effect.
        """
        if self._running:
            logger.warning("HealthMonitor already running")
            return

        logger.info("Starting HealthMonitor")
        self._running = True
        self._task = asyncio.create_task(self._health_check_loop())
        logger.info("HealthMonitor started successfully")

    async def stop(self) -> None:
        """Stop the health check loop gracefully.

        Cancels the background task and waits for it to complete.
        """
        if not self._running:
            logger.debug("HealthMonitor not running, nothing to stop")
            return

        logger.info("Stopping HealthMonitor")
        self._running = False

        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        logger.info("HealthMonitor stopped")

    async def check_service_health(self, service: ManagedService) -> bool:
        """Check health of a single service.

        Uses the appropriate health check method based on service configuration:
        1. HTTP endpoint if health_endpoint is set
        2. Command execution if health_cmd is set
        3. Container running status as fallback

        Args:
            service: ManagedService to check

        Returns:
            True if service is healthy, False otherwise
        """
        # HTTP health check
        if service.health_endpoint:
            return await check_http_health(
                host=service.name,
                port=service.port,
                endpoint=service.health_endpoint,
                timeout=float(self._settings.health_check_timeout),
            )

        # Command health check
        if service.health_cmd and service.container_id:
            return await check_cmd_health(
                docker_client=self._docker_client,
                container_id=service.container_id,
                cmd=service.health_cmd,
                timeout=self._settings.health_check_timeout,
            )

        # Fallback: container running = healthy
        if service.container_id:
            status = await self._docker_client.get_container_status(service.container_id)
            return status == "running"

        return False

    async def check_all_services(self) -> dict[str, bool]:
        """Check health of all enabled services.

        Returns:
            Dictionary mapping service name to health status (True = healthy)
        """
        results: dict[str, bool] = {}
        for service in self._registry.get_enabled():
            try:
                healthy = await self.check_service_health(service)
                results[service.name] = healthy
            except Exception as e:
                logger.error(f"Error checking health of {service.name}: {e}")
                results[service.name] = False
        return results

    async def run_health_check_cycle(self) -> None:
        """Run a single health check cycle for all enabled services.

        This method:
        1. Iterates through all enabled services
        2. Skips services in grace period
        3. Checks container existence
        4. Checks container running status
        5. Checks service-specific health
        6. Updates status and failure counts
        7. Invokes callback on health changes
        """
        for service in self._registry.get_enabled():
            try:
                # Skip services in grace period
                if self._in_grace_period(service):
                    logger.debug(f"Skipping {service.name} - in grace period")
                    continue

                # Check container exists
                if service.container_id:
                    container = await self._docker_client.get_container(service.container_id)
                    if container is None:
                        await self._handle_missing_container(service)
                        continue

                    # Check container running
                    status = await self._docker_client.get_container_status(service.container_id)
                    if status != "running":
                        await self._handle_stopped_container(service)
                        continue

                # Check health
                healthy = await self.check_service_health(service)

                if healthy:
                    if service.failure_count > 0:
                        # Service recovered
                        self._registry.reset_failures(service.name)
                        self._registry.update_status(service.name, ContainerServiceStatus.RUNNING)
                        self._record_event(service.name, "recovery", "Service recovered")
                        logger.info(f"Service {service.name} recovered")
                        if self._on_health_change:
                            await self._on_health_change(service, True)
                    elif service.status != ContainerServiceStatus.RUNNING:
                        # Already healthy - update status if not already RUNNING
                        self._registry.update_status(service.name, ContainerServiceStatus.RUNNING)
                else:
                    await self._handle_unhealthy(service)

            except Exception as e:
                logger.error(f"Error in health check cycle for {service.name}: {e}", exc_info=True)

    def _in_grace_period(self, service: ManagedService) -> bool:
        """Check if service is still in startup grace period.

        Args:
            service: ManagedService to check

        Returns:
            True if service is in grace period, False otherwise
        """
        if service.last_restart_at:
            elapsed = (datetime.now(UTC) - service.last_restart_at).total_seconds()
            return elapsed < service.startup_grace_period
        return False

    async def _handle_missing_container(self, service: ManagedService) -> None:
        """Handle case when container is not found.

        Args:
            service: ManagedService with missing container
        """
        logger.warning(f"Container not found for {service.name}")
        self._registry.update_status(service.name, ContainerServiceStatus.NOT_FOUND)
        self._registry.increment_failures(service.name)
        self._record_event(service.name, "failure", "Container not found")

        if self._on_health_change:
            await self._on_health_change(service, False)

    async def _handle_stopped_container(self, service: ManagedService) -> None:
        """Handle case when container is stopped.

        Args:
            service: ManagedService with stopped container
        """
        logger.warning(f"Container stopped for {service.name}")
        self._registry.update_status(service.name, ContainerServiceStatus.STOPPED)
        self._registry.increment_failures(service.name)
        self._record_event(service.name, "failure", "Container stopped")

        if self._on_health_change:
            await self._on_health_change(service, False)

    async def _handle_unhealthy(self, service: ManagedService) -> None:
        """Handle case when service fails health check.

        Args:
            service: ManagedService that failed health check
        """
        logger.warning(f"Health check failed for {service.name}")
        self._registry.update_status(service.name, ContainerServiceStatus.UNHEALTHY)
        self._registry.increment_failures(service.name)
        self._record_event(service.name, "failure", "Health check failed")

        if self._on_health_change:
            await self._on_health_change(service, False)

    async def _health_check_loop(self) -> None:
        """Main loop - check all services every N seconds.

        Runs continuously until stopped, checking the health of each
        enabled service and handling status changes appropriately.
        """
        logger.info("Health check loop started")

        while self._running:
            try:
                await self.run_health_check_cycle()
                await asyncio.sleep(self._settings.health_check_interval)
            except asyncio.CancelledError:
                logger.info("Health check loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}", exc_info=True)
                # Continue running even after errors
                await asyncio.sleep(self._settings.health_check_interval)

        logger.info("Health check loop stopped")

    def _record_event(
        self,
        service: str,
        event_type: str,
        message: str | None = None,
    ) -> None:
        """Record a health event in the event history.

        Args:
            service: Name of the service
            event_type: Type of event ("failure", "recovery", "restart")
            message: Optional descriptive message
        """
        event = HealthEvent(
            timestamp=datetime.now(UTC),
            service=service,
            event_type=event_type,
            message=message,
        )
        self._health_events.append(event)

    def get_recent_events(self, limit: int = 50) -> list[HealthEvent]:
        """Get recent health events.

        Args:
            limit: Maximum number of events to return (default: 50)

        Returns:
            List of recent HealthEvent objects, most recent first
        """
        # Return events in reverse order (most recent first)
        events = list(self._health_events)
        events.reverse()
        return events[:limit]
