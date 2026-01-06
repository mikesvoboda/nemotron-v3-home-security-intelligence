"""Lifecycle Manager for Container Orchestrator self-healing restart logic.

This module provides the LifecycleManager class that handles container restarts
with exponential backoff, failure tracking, and automatic disabling of services
that exceed their failure limits.

Features:
- Exponential backoff for restarts (5s, 10s, 20s, 40s, 80s, 160s, capped at max)
- Category-specific defaults for Infrastructure, AI, and Monitoring services
- Automatic disabling of services after max_failures consecutive failures
- Callbacks for restart and disabled events
- State persistence to Redis for durability across backend restarts

Usage:
    from backend.services.lifecycle_manager import (
        LifecycleManager,
        ManagedService,
        ServiceRegistry,
        calculate_backoff,
    )

    # Create lifecycle manager with dependencies
    manager = LifecycleManager(
        registry=registry,
        docker_client=docker_client,
        on_restart=my_restart_handler,
        on_disabled=my_disabled_handler,
    )

    # Handle unhealthy service
    await manager.handle_unhealthy(service)

    # Check if restart is allowed
    if manager.should_restart(service):
        await manager.restart_service(service)
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.api.schemas.services import ContainerServiceStatus, ServiceCategory
from backend.core.logging import get_logger

if TYPE_CHECKING:
    from backend.core.docker_client import DockerClient

logger = get_logger(__name__)


def calculate_backoff(
    failure_count: int,
    base: float = 5.0,
    max_backoff: float = 300.0,
) -> float:
    """Calculate exponential backoff: base * 2^failure_count, capped at max.

    Args:
        failure_count: Number of consecutive failures (0 = first attempt).
        base: Base backoff in seconds (default: 5.0).
        max_backoff: Maximum backoff in seconds (default: 300.0 = 5 minutes).

    Returns:
        Backoff duration in seconds, capped at max_backoff.

    Examples:
        >>> calculate_backoff(0, base=5.0)  # First failure
        5.0
        >>> calculate_backoff(1, base=5.0)  # Second failure
        10.0
        >>> calculate_backoff(6, base=5.0, max_backoff=300.0)  # Capped
        300.0
    """
    calculated: float = base * (2**failure_count)
    return min(calculated, max_backoff)


@dataclass
class ManagedService:
    """Represents a managed container service with lifecycle tracking.

    Attributes:
        name: Service identifier (e.g., 'postgres', 'ai-detector', 'grafana').
        display_name: Human-readable name (e.g., 'PostgreSQL', 'RT-DETRv2').
        container_id: Docker container ID (short form), or None if not found.
        image: Container image (e.g., 'postgres:16-alpine').
        port: Primary service port.
        health_endpoint: HTTP health endpoint (e.g., '/health') or None.
        health_cmd: Docker exec health command (e.g., 'pg_isready -U security').
        category: Service category (INFRASTRUCTURE, AI, MONITORING).
        status: Current service status.
        enabled: Whether auto-restart is enabled for this service.
        failure_count: Consecutive failure count.
        restart_count: Total restarts since backend boot.
        last_failure_at: Unix timestamp of last failure, or None.
        last_restart_at: datetime of last restart, or None.
        max_failures: Maximum failures before disabling (varies by category).
        restart_backoff_base: Base backoff in seconds (varies by category).
        restart_backoff_max: Maximum backoff in seconds (varies by category).
    """

    # Identity
    name: str
    display_name: str
    container_id: str | None
    image: str
    port: int

    # Health checking
    health_endpoint: str | None = None
    health_cmd: str | None = None

    # Classification
    category: ServiceCategory = ServiceCategory.AI

    # State
    status: ContainerServiceStatus = ContainerServiceStatus.NOT_FOUND
    enabled: bool = True

    # Self-healing tracking
    failure_count: int = 0
    restart_count: int = 0
    last_failure_at: float | None = None  # Unix timestamp
    last_restart_at: datetime | None = None

    # Limits (defaults are AI category defaults)
    max_failures: int = 5
    restart_backoff_base: float = 5.0
    restart_backoff_max: float = 300.0


class ServiceRegistry:
    """Registry for managing ManagedService instances.

    Provides CRUD operations for services, tracking state updates,
    and persistence to Redis for durability across backend restarts.

    Attributes:
        _services: Dictionary mapping service name to ManagedService.
        _redis: Optional Redis client for state persistence.
    """

    def __init__(self, redis_client: object | None = None) -> None:
        """Initialize the service registry.

        Args:
            redis_client: Optional Redis client for state persistence.
        """
        self._services: dict[str, ManagedService] = {}
        self._redis = redis_client

    def register(self, service: ManagedService) -> None:
        """Register a service in the registry.

        Args:
            service: The ManagedService to register.
        """
        self._services[service.name] = service
        logger.debug(f"Registered service: {service.name}")

    def get(self, name: str) -> ManagedService | None:
        """Get a service by name.

        Args:
            name: Service name.

        Returns:
            The ManagedService if found, None otherwise.
        """
        return self._services.get(name)

    def get_all(self) -> list[ManagedService]:
        """Get all registered services.

        Returns:
            List of all ManagedService instances.
        """
        return list(self._services.values())

    def get_enabled_services(self) -> list[ManagedService]:
        """Get all enabled services.

        Returns:
            List of ManagedService instances with enabled=True.
        """
        return [s for s in self._services.values() if s.enabled]

    def record_restart(self, name: str) -> None:
        """Record a restart event for a service.

        Updates restart_count and last_restart_at timestamp.

        Args:
            name: Service name.
        """
        service = self._services.get(name)
        if service:
            service.restart_count += 1
            service.last_restart_at = datetime.now(UTC)
            logger.info(
                f"Recorded restart for {name}",
                extra={
                    "service": name,
                    "restart_count": service.restart_count,
                },
            )

    def increment_failure(self, name: str) -> int:
        """Increment the failure count for a service.

        Also updates last_failure_at timestamp.

        Args:
            name: Service name.

        Returns:
            The new failure count.
        """
        service = self._services.get(name)
        if service:
            service.failure_count += 1
            service.last_failure_at = datetime.now(UTC).timestamp()
            logger.warning(
                f"Incremented failure count for {name}",
                extra={
                    "service": name,
                    "failure_count": service.failure_count,
                },
            )
            return service.failure_count
        return 0

    def reset_failures(self, name: str) -> None:
        """Reset failure tracking for a service.

        Clears failure_count and last_failure_at.

        Args:
            name: Service name.
        """
        service = self._services.get(name)
        if service:
            service.failure_count = 0
            service.last_failure_at = None
            logger.info(f"Reset failures for {name}")

    def update_status(self, name: str, status: ContainerServiceStatus) -> None:
        """Update the status of a service.

        Args:
            name: Service name.
            status: New ContainerServiceStatus value.
        """
        service = self._services.get(name)
        if service:
            old_status = service.status
            service.status = status
            logger.info(
                f"Updated status for {name}: {old_status.value} -> {status.value}",
                extra={
                    "service": name,
                    "old_status": old_status.value,
                    "new_status": status.value,
                },
            )

    def set_enabled(self, name: str, enabled: bool) -> None:
        """Set the enabled flag for a service.

        Args:
            name: Service name.
            enabled: Whether auto-restart is enabled.
        """
        service = self._services.get(name)
        if service:
            service.enabled = enabled
            logger.info(f"Set enabled={enabled} for {name}")

    def update_container_id(self, name: str, container_id: str | None) -> None:
        """Update the container ID for a service.

        Args:
            name: Service name.
            container_id: New container ID or None.
        """
        service = self._services.get(name)
        if service:
            service.container_id = container_id
            logger.debug(f"Updated container_id for {name}: {container_id}")

    async def persist_state(self, name: str) -> None:
        """Persist service state to Redis.

        Args:
            name: Service name to persist.
        """
        service = self._services.get(name)
        if not service:
            return

        if self._redis is None:
            logger.debug(f"No Redis client, skipping persist for {name}")
            return

        key = f"orchestrator:service:{name}:state"
        state = {
            "failure_count": service.failure_count,
            "restart_count": service.restart_count,
            "last_failure_at": service.last_failure_at,
            "last_restart_at": (
                service.last_restart_at.isoformat() if service.last_restart_at else None
            ),
            "enabled": service.enabled,
            "status": service.status.value,
        }

        try:
            # Async Redis client
            if hasattr(self._redis, "hset"):
                await self._redis.hset(key, mapping=state)
                logger.debug(f"Persisted state for {name} to Redis")
        except Exception as e:
            logger.warning(f"Failed to persist state for {name}: {e}")

    async def load_state(self) -> None:
        """Load all service state from Redis.

        Restores failure counts, restart counts, and enabled status
        from persisted Redis state.
        """
        if self._redis is None:
            logger.debug("No Redis client, skipping load_state")
            return

        for name, service in self._services.items():
            key = f"orchestrator:service:{name}:state"
            try:
                if hasattr(self._redis, "hgetall"):
                    state = await self._redis.hgetall(key)
                    if state:
                        service.failure_count = int(state.get("failure_count", 0))
                        service.restart_count = int(state.get("restart_count", 0))
                        service.enabled = state.get("enabled", "True") == "True"
                        last_failure = state.get("last_failure_at")
                        if last_failure:
                            service.last_failure_at = float(last_failure)
                        logger.debug(f"Loaded state for {name} from Redis")
            except Exception as e:
                logger.warning(f"Failed to load state for {name}: {e}")


class LifecycleManager:
    """Manages container lifecycle with self-healing restart logic.

    Handles exponential backoff, failure tracking, automatic disabling,
    and callback invocation for restart and disabled events.

    Attributes:
        registry: ServiceRegistry for service state management.
        docker_client: DockerClient for container operations.
        on_restart: Optional callback invoked after successful restart.
        on_disabled: Optional callback invoked when service is disabled.
    """

    def __init__(
        self,
        registry: ServiceRegistry,
        docker_client: DockerClient,
        on_restart: Callable[[ManagedService], Awaitable[None]] | None = None,
        on_disabled: Callable[[ManagedService], Awaitable[None]] | None = None,
    ) -> None:
        """Initialize the lifecycle manager.

        Args:
            registry: ServiceRegistry for service state management.
            docker_client: DockerClient for container operations.
            on_restart: Optional async callback invoked after restart.
            on_disabled: Optional async callback invoked when service disabled.
        """
        self.registry = registry
        self.docker_client = docker_client
        self.on_restart = on_restart
        self.on_disabled = on_disabled

    def calculate_backoff(self, service: ManagedService) -> float:
        """Calculate exponential backoff for a service.

        Uses service-specific backoff settings (base and max).

        Args:
            service: The ManagedService to calculate backoff for.

        Returns:
            Backoff duration in seconds.
        """
        return calculate_backoff(
            failure_count=service.failure_count,
            base=service.restart_backoff_base,
            max_backoff=service.restart_backoff_max,
        )

    def should_restart(self, service: ManagedService) -> bool:
        """Determine if a service should be restarted.

        Checks:
        1. Service is enabled
        2. Failure count is below max_failures
        3. Backoff period has elapsed since last failure

        Args:
            service: The ManagedService to check.

        Returns:
            True if restart is allowed, False otherwise.
        """
        # Disabled services should not restart
        if not service.enabled:
            return False

        # At or above max failures - service should be disabled
        if service.failure_count >= service.max_failures:
            return False

        # If no prior failure, restart is allowed
        if service.last_failure_at is None:
            return True

        # Check if backoff has elapsed
        return self.backoff_remaining(service) <= 0

    def backoff_remaining(self, service: ManagedService) -> float:
        """Calculate seconds remaining in backoff period.

        Args:
            service: The ManagedService to check.

        Returns:
            Seconds remaining, or 0 if backoff has elapsed.
        """
        if service.last_failure_at is None:
            return 0.0

        backoff = self.calculate_backoff(service)
        elapsed = datetime.now(UTC).timestamp() - service.last_failure_at
        remaining = backoff - elapsed

        return max(0.0, remaining)

    async def restart_service(self, service: ManagedService) -> bool:
        """Restart a container with tracking updates.

        Stops the container gracefully, starts it, updates tracking,
        and invokes the on_restart callback if configured.

        Args:
            service: The ManagedService to restart.

        Returns:
            True if restart succeeded, False otherwise.
        """
        if not service.container_id:
            logger.error(f"Cannot restart {service.name}: no container_id")
            return False

        try:
            # Stop gracefully
            await self.docker_client.stop_container(service.container_id, timeout=10)

            # Start same container
            success = await self.docker_client.start_container(service.container_id)

            if success:
                # Update tracking
                self.registry.record_restart(service.name)
                self.registry.update_status(service.name, ContainerServiceStatus.STARTING)
                await self.registry.persist_state(service.name)

                if self.on_restart:
                    await self.on_restart(service)

                logger.info(f"Restarted service {service.name}")
                return True
            logger.error(f"Failed to start service {service.name}")
            return False
        except Exception as e:
            logger.error(f"Error restarting {service.name}: {e}")
            return False

    async def start_service(self, service: ManagedService) -> bool:
        """Start a stopped container.

        Args:
            service: The ManagedService to start.

        Returns:
            True if start succeeded, False otherwise.
        """
        if not service.container_id:
            logger.error(f"Cannot start {service.name}: no container_id")
            return False

        try:
            success = await self.docker_client.start_container(service.container_id)
            if success:
                self.registry.update_status(service.name, ContainerServiceStatus.STARTING)
                await self.registry.persist_state(service.name)
                logger.info(f"Started service {service.name}")
            return success
        except Exception as e:
            logger.error(f"Error starting {service.name}: {e}")
            return False

    async def stop_service(self, service: ManagedService) -> bool:
        """Stop a running container.

        Args:
            service: The ManagedService to stop.

        Returns:
            True if stop succeeded, False otherwise.
        """
        if not service.container_id:
            logger.error(f"Cannot stop {service.name}: no container_id")
            return False

        try:
            success = await self.docker_client.stop_container(service.container_id, timeout=10)
            if success:
                self.registry.update_status(service.name, ContainerServiceStatus.STOPPED)
                await self.registry.persist_state(service.name)
                logger.info(f"Stopped service {service.name}")
            return success
        except Exception as e:
            logger.error(f"Error stopping {service.name}: {e}")
            return False

    async def enable_service(self, name: str) -> bool:
        """Enable a disabled service and reset failures.

        Resets failure count and sets enabled flag to True.

        Args:
            name: Service name.

        Returns:
            True if service was found and enabled, False otherwise.
        """
        service = self.registry.get(name)
        if not service:
            logger.warning(f"Cannot enable unknown service: {name}")
            return False

        self.registry.reset_failures(name)
        self.registry.set_enabled(name, True)
        self.registry.update_status(name, ContainerServiceStatus.STOPPED)
        await self.registry.persist_state(name)

        logger.info(f"Enabled service {name}, ready for restart")
        return True

    async def disable_service(self, name: str) -> bool:
        """Disable a service to prevent auto-restarts.

        Sets enabled flag to False and status to DISABLED.

        Args:
            name: Service name.

        Returns:
            True if service was found and disabled, False otherwise.
        """
        service = self.registry.get(name)
        if not service:
            logger.warning(f"Cannot disable unknown service: {name}")
            return False

        self.registry.set_enabled(name, False)
        self.registry.update_status(name, ContainerServiceStatus.DISABLED)
        await self.registry.persist_state(name)

        logger.info(f"Disabled service {name}")
        return True

    async def handle_unhealthy(self, service: ManagedService) -> None:
        """Handle an unhealthy service.

        Increments failure count and either:
        - Disables the service if max_failures reached
        - Restarts the service if backoff has elapsed (based on PREVIOUS failure)
        - Skips restart if still in backoff period

        The backoff check happens BEFORE updating last_failure_at, so we're
        checking if enough time has elapsed since the previous failure.

        Args:
            service: The unhealthy ManagedService.
        """
        # Check if we should restart BEFORE incrementing failure count
        # This checks backoff from the PREVIOUS failure
        can_restart = self.should_restart(service)

        # Now increment failure count
        new_count = self.registry.increment_failure(service.name)

        if new_count >= service.max_failures:
            # Disable service
            self.registry.update_status(service.name, ContainerServiceStatus.DISABLED)
            self.registry.set_enabled(service.name, False)
            await self.registry.persist_state(service.name)

            if self.on_disabled:
                await self.on_disabled(service)

            logger.error(f"Service {service.name} disabled after {new_count} failures")
            return

        # Update service's failure_count and timestamp AFTER checking restart
        service.failure_count = new_count
        service.last_failure_at = datetime.now(UTC).timestamp()

        if can_restart:
            await self.restart_service(service)
        else:
            remaining = self.backoff_remaining(service)
            logger.warning(f"Service {service.name} in backoff, {remaining:.1f}s remaining")

    async def handle_stopped(self, service: ManagedService) -> None:
        """Handle a stopped service.

        Restarts the service if enabled and backoff has elapsed.

        Args:
            service: The stopped ManagedService.
        """
        if not service.enabled:
            logger.debug(f"Skipping restart for disabled service: {service.name}")
            return

        if self.should_restart(service):
            await self.start_service(service)
        else:
            remaining = self.backoff_remaining(service)
            logger.debug(f"Skipping restart for {service.name}, {remaining:.1f}s backoff remaining")

    async def handle_missing(self, service: ManagedService) -> None:
        """Handle a missing container (not found).

        Updates status to NOT_FOUND and clears container_id.

        Args:
            service: The missing ManagedService.
        """
        self.registry.update_status(service.name, ContainerServiceStatus.NOT_FOUND)
        self.registry.update_container_id(service.name, None)
        await self.registry.persist_state(service.name)

        logger.warning(f"Container not found for service: {service.name}")
