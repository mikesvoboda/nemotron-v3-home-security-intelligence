"""Service Registry with Redis persistence for Container Orchestrator.

This module provides the ServiceRegistry class that manages ManagedService objects
representing containers. It provides:

1. In-memory storage for fast access during health checks
2. Redis persistence for state recovery across backend restarts
3. Thread-safe operations for concurrent access

Redis key pattern: orchestrator:service:{name}:state

Example usage:
    from backend.services.service_registry import get_service_registry, ManagedService
    from backend.api.schemas.services import ContainerServiceStatus, ServiceCategory

    registry = get_service_registry()

    # Register a service
    service = ManagedService(
        name="ai-detector",
        display_name="RT-DETRv2",
        container_id="abc123",
        image="ghcr.io/.../rtdetr:latest",
        port=8090,
        health_endpoint="/health",
        health_cmd=None,
        category=ServiceCategory.AI,
        status=ContainerServiceStatus.RUNNING,
    )
    registry.register(service)

    # Update status
    registry.update_status("ai-detector", ContainerServiceStatus.UNHEALTHY)

    # Persist to Redis
    await registry.persist_state("ai-detector")

    # Load from Redis on restart
    await registry.load_all_state()
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from backend.api.schemas.services import ContainerServiceStatus, ServiceCategory

if TYPE_CHECKING:
    from backend.core.redis import RedisClient

logger = logging.getLogger(__name__)

# Redis key prefix for service state
REDIS_KEY_PREFIX = "orchestrator:service"


@dataclass(slots=True)
class ManagedService:
    """A container service managed by the orchestrator.

    Represents a container with its identity, configuration, and runtime state.
    Used by the container orchestrator for health monitoring and self-healing.

    Attributes:
        name: Service identifier (e.g., "postgres", "ai-detector", "grafana")
        display_name: Human-readable name (e.g., "PostgreSQL", "RT-DETRv2")
        container_id: Docker container ID or None if not yet discovered
        image: Container image (e.g., "postgres:16-alpine")
        port: Primary service port
        health_endpoint: HTTP health check path (e.g., "/health") or None
        health_cmd: Docker exec health command (e.g., "pg_isready") or None
        category: Service category (infrastructure, ai, monitoring)
        status: Current service status
        enabled: Whether auto-restart is enabled
        failure_count: Consecutive health check failures
        last_failure_at: Timestamp of last failure
        last_restart_at: Timestamp of last restart
        restart_count: Total restarts since backend boot
        max_failures: Disable service after this many consecutive failures
        restart_backoff_base: Base delay for exponential backoff (seconds)
        restart_backoff_max: Maximum backoff delay (seconds)
        startup_grace_period: Seconds to wait before counting health failures
    """

    name: str
    display_name: str
    container_id: str | None
    image: str | None
    port: int
    health_endpoint: str | None
    health_cmd: str | None

    category: ServiceCategory
    status: ContainerServiceStatus
    enabled: bool = True

    # Self-healing tracking
    failure_count: int = 0
    last_failure_at: datetime | None = None
    last_restart_at: datetime | None = None
    restart_count: int = 0

    # Limits (category-specific defaults)
    max_failures: int = 5
    restart_backoff_base: float = 5.0
    restart_backoff_max: float = 300.0
    startup_grace_period: int = 60

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization.

        Returns:
            Dictionary representation with enum values as strings
            and datetime values as ISO format strings.
        """
        return {
            "name": self.name,
            "display_name": self.display_name,
            "container_id": self.container_id,
            "image": self.image,
            "port": self.port,
            "health_endpoint": self.health_endpoint,
            "health_cmd": self.health_cmd,
            "category": self.category.value,
            "status": self.status.value,
            "enabled": self.enabled,
            "failure_count": self.failure_count,
            "last_failure_at": (self.last_failure_at.isoformat() if self.last_failure_at else None),
            "last_restart_at": (self.last_restart_at.isoformat() if self.last_restart_at else None),
            "restart_count": self.restart_count,
            "max_failures": self.max_failures,
            "restart_backoff_base": self.restart_backoff_base,
            "restart_backoff_max": self.restart_backoff_max,
            "startup_grace_period": self.startup_grace_period,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ManagedService:
        """Create a ManagedService from a dictionary.

        Args:
            data: Dictionary with service data (e.g., from JSON)

        Returns:
            New ManagedService instance
        """
        # Parse datetime fields
        last_failure_at = None
        if data.get("last_failure_at"):
            last_failure_at = datetime.fromisoformat(data["last_failure_at"])

        last_restart_at = None
        if data.get("last_restart_at"):
            last_restart_at = datetime.fromisoformat(data["last_restart_at"])

        # Parse enum fields
        category = ServiceCategory(data["category"])
        status = ContainerServiceStatus(data["status"])

        return cls(
            name=data["name"],
            display_name=data["display_name"],
            container_id=data.get("container_id"),
            image=data.get("image"),
            port=data["port"],
            health_endpoint=data.get("health_endpoint"),
            health_cmd=data.get("health_cmd"),
            category=category,
            status=status,
            enabled=data.get("enabled", True),
            failure_count=data.get("failure_count", 0),
            last_failure_at=last_failure_at,
            last_restart_at=last_restart_at,
            restart_count=data.get("restart_count", 0),
            max_failures=data.get("max_failures", 5),
            restart_backoff_base=data.get("restart_backoff_base", 5.0),
            restart_backoff_max=data.get("restart_backoff_max", 300.0),
            startup_grace_period=data.get("startup_grace_period", 60),
        )


class ServiceRegistry:
    """Registry for managed container services with Redis persistence.

    Provides in-memory storage for fast access during health checks,
    with Redis persistence for state recovery across backend restarts.

    Thread-safe for concurrent access from multiple async tasks.

    Example:
        registry = ServiceRegistry(redis_client)

        # Register services
        registry.register(postgres_service)
        registry.register(ai_detector_service)

        # Query services
        enabled = registry.get_enabled()
        ai_services = registry.get_by_category(ServiceCategory.AI)

        # Update state
        registry.update_status("ai-detector", ContainerServiceStatus.UNHEALTHY)
        registry.increment_failure("ai-detector")

        # Persist to Redis
        await registry.persist_state("ai-detector")
    """

    def __init__(self, redis_client: RedisClient) -> None:
        """Initialize the service registry.

        Args:
            redis_client: Connected RedisClient instance for state persistence
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
                service.failure_count += 1
                service.last_failure_at = datetime.now(UTC)
                logger.debug(
                    "Incremented failure count",
                    extra={"service_name": name, "failure_count": service.failure_count},
                )
                return service.failure_count
            return 0

    def reset_failures(self, name: str) -> None:
        """Reset failure tracking for a service.

        Clears failure_count and last_failure_at.

        Args:
            name: Service name
        """
        with self._lock:
            service = self._services.get(name)
            if service:
                service.failure_count = 0
                service.last_failure_at = None
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
                service.restart_count += 1
                service.last_restart_at = datetime.now(UTC)
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

    # =========================================================================
    # Redis Persistence Methods
    # =========================================================================

    async def persist_state(self, name: str) -> None:
        """Persist service state to Redis.

        Saves the runtime state (enabled, failure_count, restart tracking,
        status) to Redis for recovery across backend restarts.

        Does nothing if the service doesn't exist.
        Logs and continues on Redis errors.

        Args:
            name: Service name to persist
        """
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

        Does nothing if the service doesn't exist or no Redis data found.
        Logs and continues on Redis errors.

        Args:
            name: Service name to load
        """
        with self._lock:
            service = self._services.get(name)
            if not service:
                return

        key = f"{REDIS_KEY_PREFIX}:{name}:state"
        try:
            # RedisClient.get() handles JSON deserialization internally
            state = await self._redis.get(key)
            if not state:
                logger.debug("No Redis state found for service", extra={"service_name": name})
                return

            # If state is a string (raw data), parse it as JSON
            if isinstance(state, str):
                state = json.loads(state)

            with self._lock:
                # Re-check service exists (may have been unregistered)
                service = self._services.get(name)
                if not service:
                    return

                service.enabled = state.get("enabled", True)
                service.failure_count = state.get("failure_count", 0)
                service.restart_count = state.get("restart_count", 0)

                if state.get("last_failure_at"):
                    service.last_failure_at = datetime.fromisoformat(state["last_failure_at"])
                else:
                    service.last_failure_at = None

                if state.get("last_restart_at"):
                    service.last_restart_at = datetime.fromisoformat(state["last_restart_at"])
                else:
                    service.last_restart_at = None

                if state.get("status"):
                    try:
                        service.status = ContainerServiceStatus(state["status"])
                    except ValueError:
                        logger.warning(
                            "Invalid status in Redis state",
                            extra={"service_name": name, "status": state["status"]},
                        )

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
