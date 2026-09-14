"""Service Registry with Redis persistence for Container Orchestrator.

This module provides the canonical ServiceRegistry class that manages ManagedService
objects representing containers. It provides:

1. In-memory storage for fast access during health checks
2. Redis persistence for state recovery across backend restarts
3. Thread-safe operations for concurrent access

Redis key pattern: orchestrator:service:{name}:state

This is the single source of truth for ServiceRegistry - all orchestration
modules should import from here instead of defining their own.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from typing import TYPE_CHECKING

from backend.services.orchestrator.enums import ContainerServiceStatus, ServiceCategory
from backend.services.orchestrator.models import ManagedService

if TYPE_CHECKING:
    from backend.core.redis import RedisClient

logger = logging.getLogger(__name__)

# Redis key prefix for service state
REDIS_KEY_PREFIX = "orchestrator:service"


class ServiceRegistry:
    """Registry for managed container services with Redis persistence.

    Provides in-memory storage for fast access during health checks,
    with Redis persistence for state recovery across backend restarts.

    Thread-safe for concurrent access from multiple async tasks.

    This is the canonical ServiceRegistry - all orchestration modules should
    use this class instead of defining their own.

    Example:
        registry = ServiceRegistry(redis_client)

        # Register services
        registry.register(postgres_service)
        registry.register(ai_detector_service)

        # Query services
        enabled = registry.get_enabled()
        ai_services = registry.get_by_category(ServiceCategory.AI)

        # Update state
        registry.update_status("ai-yolo26", ContainerServiceStatus.UNHEALTHY)
        registry.increment_failure("ai-yolo26")

        # Persist to Redis
        await registry.persist_state("ai-yolo26")
    """

    def __init__(self, redis_client: RedisClient | None = None) -> None:
        """Initialize the service registry.

        Args:
            redis_client: Optional Redis client for state persistence.
                          If None, persistence operations are no-ops.
        """
        self._redis = redis_client
        self._services: dict[str, ManagedService] = {}
        self._lock = threading.RLock()

    # =========================================================================
    # Registration Methods
    # =========================================================================

    def register(self, service: ManagedService) -> None:
        """Register a service in the registry.

        If a service with the same name exists, it will be overwritten.

        Args:
            service: ManagedService to register
        """
        with self._lock:
            self._services[service.name] = service
            logger.debug(
                "Registered service",
                extra={"service_name": service.name, "category": service.category.value},
            )

    def unregister(self, name: str) -> None:
        """Unregister a service from the registry.

        Does nothing if the service doesn't exist.

        Args:
            name: Service name to unregister
        """
        with self._lock:
            if name in self._services:
                del self._services[name]
                logger.debug("Unregistered service", extra={"service_name": name})

    def get(self, name: str) -> ManagedService | None:
        """Get a service by name.

        Args:
            name: Service name

        Returns:
            ManagedService or None if not found
        """
        with self._lock:
            return self._services.get(name)

    def get_all(self) -> list[ManagedService]:
        """Get all registered services.

        Returns:
            List of all ManagedService instances
        """
        with self._lock:
            return list(self._services.values())

    def get_by_category(self, category: ServiceCategory) -> list[ManagedService]:
        """Get services by category.

        Args:
            category: ServiceCategory to filter by

        Returns:
            List of services in the specified category
        """
        with self._lock:
            return [s for s in self._services.values() if s.category == category]

    def get_enabled(self) -> list[ManagedService]:
        """Get all enabled services.

        Returns:
            List of services with enabled=True
        """
        with self._lock:
            return [s for s in self._services.values() if s.enabled]

    def get_enabled_services(self) -> list[ManagedService]:
        """Alias for get_enabled() for compatibility.

        Returns:
            List of services with enabled=True
        """
        return self.get_enabled()

    def list_names(self) -> list[str]:
        """Get all registered service names.

        Returns:
            List of service names
        """
        with self._lock:
            return list(self._services.keys())

    # =========================================================================
    # State Update Methods
    # =========================================================================

    def update_status(self, name: str, status: ContainerServiceStatus) -> None:
        """Update the status of a service.

        Does nothing if the service doesn't exist.

        Args:
            name: Service name
            status: New status
        """
        with self._lock:
            service = self._services.get(name)
            if service:
                service.status = status
                logger.debug(
                    "Updated service status",
                    extra={"service_name": name, "status": status.value},
                )

    def increment_failure(self, name: str) -> int:
        """Increment the failure count for a service.

        Also updates last_failure_at timestamp.

        Args:
            name: Service name

        Returns:
            New failure count, or 0 if service not found
        """
        with self._lock:
            service = self._services.get(name)
            if service:
                service.record_failure()
                logger.debug(
                    "Incremented failure count",
                    extra={"service_name": name, "failure_count": service.failure_count},
                )
                return service.failure_count
            return 0

    def increment_failures(self, name: str) -> None:
        """Increment failure count (alias for increment_failure).

        Provided for compatibility with existing code.

        Args:
            name: Service name
        """
        self.increment_failure(name)

    def reset_failures(self, name: str) -> None:
        """Reset failure tracking for a service.

        Clears failure_count and last_failure_at.

        Args:
            name: Service name
        """
        with self._lock:
            service = self._services.get(name)
            if service:
                service.reset_failures()
                logger.debug("Reset failure tracking", extra={"service_name": name})

    def record_restart(self, name: str) -> None:
        """Record a restart for a service.

        Increments restart_count and updates last_restart_at.

        Args:
            name: Service name
        """
        with self._lock:
            service = self._services.get(name)
            if service:
                service.record_restart()
                logger.debug(
                    "Recorded restart",
                    extra={"service_name": name, "restart_count": service.restart_count},
                )

    def set_enabled(self, name: str, enabled: bool) -> None:
        """Set the enabled flag for a service.

        Args:
            name: Service name
            enabled: New enabled value
        """
        with self._lock:
            service = self._services.get(name)
            if service:
                service.enabled = enabled
                logger.debug(
                    "Set service enabled",
                    extra={"service_name": name, "enabled": enabled},
                )

    def update_container_id(self, name: str, container_id: str | None) -> None:
        """Update the container ID for a service.

        Args:
            name: Service name
            container_id: New container ID or None
        """
        with self._lock:
            service = self._services.get(name)
            if service:
                service.container_id = container_id
                logger.debug(
                    "Updated container ID",
                    extra={"service_name": name, "container_id": container_id},
                )

    # =========================================================================
    # Warmth State Tracking (NEM-1670)
    # =========================================================================

    def update_warmth_state(self, name: str, state: str) -> None:
        """Update a service's warmth state.

        Args:
            name: Service name
            state: Warmth state ('cold', 'warming', 'warm', 'unknown')
        """
        with self._lock:
            service = self._services.get(name)
            if service:
                service.warmth_state = state
                logger.debug(
                    "Updated warmth state",
                    extra={"service_name": name, "warmth_state": state},
                )

    def get_ai_warmth_states(self) -> dict[str, str]:
        """Get warmth states for all AI services.

        Returns:
            Dictionary mapping service names to their warmth states
        """
        with self._lock:
            return {
                name: service.warmth_state
                for name, service in self._services.items()
                if service.category == ServiceCategory.AI
            }

    # =========================================================================
    # Redis Persistence Methods
    # =========================================================================

    async def persist_state(self, name: str) -> None:
        """Persist service state to Redis.

        Saves the runtime state (enabled, failure_count, restart tracking,
        status) to Redis for recovery across backend restarts.

        Does nothing if the service doesn't exist or no Redis client.
        Logs and continues on Redis errors.

        Args:
            name: Service name to persist
        """
        if self._redis is None:
            logger.debug("No Redis client, skipping persist", extra={"service_name": name})
            return

        with self._lock:
            service = self._services.get(name)
            if not service:
                return

            state = {
                "enabled": service.enabled,
                "failure_count": service.failure_count,
                "last_failure_at": (
                    service.last_failure_at.isoformat() if service.last_failure_at else None
                ),
                "last_restart_at": (
                    service.last_restart_at.isoformat() if service.last_restart_at else None
                ),
                "restart_count": service.restart_count,
                "status": service.status.value,
            }

        key = f"{REDIS_KEY_PREFIX}:{name}:state"
        try:
            # RedisClient.set() handles JSON serialization internally
            await self._redis.set(key, state)
            logger.debug("Persisted service state to Redis", extra={"service_name": name})
        except Exception as e:
            logger.warning(
                "Failed to persist service state to Redis",
                extra={"service_name": name, "error": str(e)},
            )

    async def load_state(self, name: str) -> None:
        """Load service state from Redis.

        Restores the runtime state (enabled, failure_count, restart tracking,
        status) from Redis after backend restart.

        Does nothing if the service doesn't exist, no Redis client, or no data.
        Logs and continues on Redis errors.

        Args:
            name: Service name to load
        """
        if self._redis is None:
            logger.debug("No Redis client, skipping load", extra={"service_name": name})
            return

        with self._lock:
            service = self._services.get(name)
            if not service:
                return

        key = f"{REDIS_KEY_PREFIX}:{name}:state"
        try:
            state = await self._redis.get(key)
            if not state:
                logger.debug("No Redis state found for service", extra={"service_name": name})
                return

            # Parse JSON if state is a string
            if isinstance(state, str):
                state = json.loads(state)

            self._apply_loaded_state(name, state)
            logger.debug("Loaded service state from Redis", extra={"service_name": name})

        except json.JSONDecodeError as e:
            logger.warning(
                "Failed to parse Redis state JSON",
                extra={"service_name": name, "error": str(e)},
            )
        except Exception as e:
            logger.warning(
                "Failed to load service state from Redis",
                extra={"service_name": name, "error": str(e)},
            )

    def _apply_loaded_state(self, name: str, state: dict) -> None:
        """Apply loaded state to a service.

        Args:
            name: Service name
            state: State dictionary from Redis
        """
        with self._lock:
            service = self._services.get(name)
            if not service:
                return

            service.enabled = state.get("enabled", True)
            service.failure_count = state.get("failure_count", 0)
            service.restart_count = state.get("restart_count", 0)

            # Parse datetime fields
            last_failure = state.get("last_failure_at")
            service.last_failure_at = datetime.fromisoformat(last_failure) if last_failure else None

            last_restart = state.get("last_restart_at")
            service.last_restart_at = datetime.fromisoformat(last_restart) if last_restart else None

            # Parse status enum
            status_str = state.get("status")
            if status_str:
                try:
                    service.status = ContainerServiceStatus(status_str)
                except ValueError:
                    logger.warning(
                        "Invalid status in Redis state",
                        extra={"service_name": name, "status": status_str},
                    )

    async def load_all_state(self) -> None:
        """Load state for all registered services from Redis.

        Calls load_state for each registered service.
        Logs and continues on errors.
        """
        with self._lock:
            names = list(self._services.keys())

        for name in names:
            await self.load_state(name)

        logger.info(
            "Loaded state for all services from Redis",
            extra={"service_count": len(names)},
        )

    async def clear_state(self, name: str) -> None:
        """Clear service state from Redis.

        Args:
            name: Service name to clear
        """
        if self._redis is None:
            return

        key = f"{REDIS_KEY_PREFIX}:{name}:state"
        try:
            await self._redis.delete(key)
            logger.debug("Cleared service state from Redis", extra={"service_name": name})
        except Exception as e:
            logger.warning(
                "Failed to clear service state from Redis",
                extra={"service_name": name, "error": str(e)},
            )


# =============================================================================
# Global Registry Singleton
# =============================================================================

_service_registry: ServiceRegistry | None = None
_registry_lock = threading.Lock()


async def get_service_registry() -> ServiceRegistry:
    """Get the global ServiceRegistry singleton.

    Creates the registry on first call using the global Redis client.
    This is an async function because Redis initialization is async.

    Returns:
        ServiceRegistry instance
    """
    global _service_registry  # noqa: PLW0603

    with _registry_lock:
        if _service_registry is None:
            from backend.core.redis import init_redis

            redis_client = await init_redis()
            _service_registry = ServiceRegistry(redis_client=redis_client)
            logger.info("Created global ServiceRegistry singleton")

        return _service_registry


def reset_service_registry() -> None:
    """Reset the global ServiceRegistry singleton.

    Used for testing to ensure clean state between tests.
    """
    global _service_registry  # noqa: PLW0603

    with _registry_lock:
        _service_registry = None
        logger.debug("Reset global ServiceRegistry singleton")


__all__ = [
    "REDIS_KEY_PREFIX",
    "ServiceRegistry",
    "get_service_registry",
    "reset_service_registry",
]
