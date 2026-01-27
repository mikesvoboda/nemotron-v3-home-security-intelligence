"""Canonical ManagedService and ServiceRegistry for Container Orchestrator.

This module provides the single, authoritative definitions of ManagedService and
ServiceRegistry used throughout the container orchestration system. All other modules
should import from here instead of defining their own versions.

Key Components:
- ServiceConfig: Configuration for service patterns used in discovery
- ManagedService: Represents a container managed by the orchestrator
- ServiceRegistry: Registry for managing ManagedService instances with Redis persistence

The ManagedService dataclass combines:
- Identity fields (name, display_name, container_id, image, port)
- Health check configuration (health_endpoint, health_cmd)
- Classification (category)
- Runtime state (status, enabled)
- Self-healing tracking (failure_count, last_failure_at, restart_count, last_restart_at)
- Limits (max_failures, restart_backoff_base, restart_backoff_max, startup_grace_period)

Usage:
    from backend.services.managed_service import (
        ManagedService,
        ServiceConfig,
        ServiceRegistry,
        get_service_registry,
    )

    # Create a managed service
    service = ManagedService(
        name="ai-yolo26",
        display_name="YOLO26v2",
        container_id="abc123",
        image="ghcr.io/.../yolo26:latest",
        port=8095,
        health_endpoint="/health",
        category=ServiceCategory.AI,
        status=ContainerServiceStatus.RUNNING,
    )

    # Register in the global registry
    registry = await get_service_registry()
    registry.register(service)

    # Update status
    registry.update_status("ai-yolo26", ContainerServiceStatus.UNHEALTHY)

    # Persist to Redis
    await registry.persist_state("ai-yolo26")
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from backend.api.schemas.services import ContainerServiceStatus, ServiceCategory

if TYPE_CHECKING:
    from backend.core.redis import RedisClient

logger = logging.getLogger(__name__)

# Redis key prefix for service state persistence
REDIS_KEY_PREFIX = "orchestrator:service"


@dataclass(slots=True)
class ServiceConfig:
    """Configuration for a service pattern used in container discovery.

    Defines how to identify and manage containers matching a specific service
    pattern. Includes health check configuration and self-healing parameters.

    Attributes:
        display_name: Human-readable name for the service (e.g., "PostgreSQL")
        category: Service category (infrastructure, ai, monitoring)
        port: Primary service port
        health_endpoint: HTTP health check endpoint (e.g., "/health")
        health_cmd: Docker exec health command (e.g., "pg_isready -U security")
        startup_grace_period: Seconds to wait before health checks after startup
        max_failures: Consecutive failures before disabling the service
        restart_backoff_base: Initial backoff delay in seconds
        restart_backoff_max: Maximum backoff delay in seconds
    """

    display_name: str
    category: ServiceCategory
    port: int
    health_endpoint: str | None = None
    health_cmd: str | None = None
    startup_grace_period: int = 60
    max_failures: int = 5
    restart_backoff_base: float = 5.0
    restart_backoff_max: float = 300.0


@dataclass(slots=True)
class ManagedService:
    """A container service managed by the orchestrator.

    This is the canonical definition used throughout the container orchestration
    system for health monitoring, self-healing, and lifecycle management.

    Attributes:
        name: Service identifier (e.g., "postgres", "ai-yolo26", "grafana")
        display_name: Human-readable name (e.g., "PostgreSQL", "YOLO26v2")
        container_id: Docker container ID or None if not yet discovered
        image: Container image (e.g., "postgres:16-alpine") or None
        port: Primary service port
        health_endpoint: HTTP health check path (e.g., "/health") or None
        health_cmd: Docker exec health command (e.g., "pg_isready") or None
        category: Service category (infrastructure, ai, monitoring)
        status: Current service status
        enabled: Whether auto-restart is enabled
        failure_count: Consecutive health check failures
        last_failure_at: Timestamp of last failure (datetime for precision)
        last_restart_at: Timestamp of last restart
        restart_count: Total restarts since backend boot
        max_failures: Disable service after this many consecutive failures
        restart_backoff_base: Base delay for exponential backoff (seconds)
        restart_backoff_max: Maximum backoff delay (seconds)
        startup_grace_period: Seconds to wait before counting health failures
    """

    # Identity fields (required)
    name: str
    display_name: str
    container_id: str | None
    image: str | None
    port: int

    # Classification (required - see ServiceCategory enum)
    category: ServiceCategory

    # Health check configuration (optional)
    health_endpoint: str | None = None
    health_cmd: str | None = None

    # Runtime state
    status: ContainerServiceStatus = field(default=ContainerServiceStatus.NOT_FOUND)
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

    def to_dict(self) -> dict[str, Any]:
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
    def from_dict(cls, data: dict[str, Any]) -> ManagedService:
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
        status = ContainerServiceStatus(data.get("status", ContainerServiceStatus.NOT_FOUND.value))

        return cls(
            name=data["name"],
            display_name=data.get("display_name", data["name"]),
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

    @classmethod
    def from_config(
        cls,
        config_key: str,
        config: ServiceConfig,
        container_id: str,
        image: str,
    ) -> ManagedService:
        """Create a ManagedService from a ServiceConfig.

        This factory method is used by ContainerDiscoveryService to create
        ManagedService instances from discovered containers.

        Args:
            config_key: Service name/identifier
            config: ServiceConfig with service settings
            container_id: Docker container ID
            image: Container image with tag

        Returns:
            New ManagedService instance
        """
        return cls(
            name=config_key,
            display_name=config.display_name,
            container_id=container_id,
            image=image,
            port=config.port,
            health_endpoint=config.health_endpoint,
            health_cmd=config.health_cmd,
            category=config.category,
            status=ContainerServiceStatus.NOT_FOUND,
            max_failures=config.max_failures,
            restart_backoff_base=config.restart_backoff_base,
            restart_backoff_max=config.restart_backoff_max,
            startup_grace_period=config.startup_grace_period,
        )

    def get_last_failure_timestamp(self) -> float | None:
        """Get last_failure_at as a Unix timestamp for backoff calculations.

        Returns:
            Unix timestamp (float) or None if no failure recorded.
        """
        if self.last_failure_at is None:
            return None
        return self.last_failure_at.timestamp()


class ServiceRegistry:
    """Registry for managed container services with optional Redis persistence.

    Provides in-memory storage for fast access during health checks,
    with optional Redis persistence for state recovery across backend restarts.

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
        registry.update_status("ai-yolo26", ContainerServiceStatus.UNHEALTHY)
        registry.increment_failure("ai-yolo26")

        # Persist to Redis
        await registry.persist_state("ai-yolo26")
    """

    def __init__(self, redis_client: RedisClient | None = None) -> None:
        """Initialize the service registry.

        Args:
            redis_client: Optional RedisClient instance for state persistence.
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
                service.failure_count += 1
                service.last_failure_at = datetime.now(UTC)
                logger.debug(
                    "Incremented failure count",
                    extra={"service_name": name, "failure_count": service.failure_count},
                )
                return service.failure_count
            return 0

    def increment_failures(self, name: str) -> None:
        """Alias for increment_failure() for compatibility.

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
                    "Updated container_id",
                    extra={"service_name": name, "container_id": container_id},
                )

    # =========================================================================
    # Redis Persistence Methods
    # =========================================================================

    async def persist_state(self, name: str) -> None:
        """Persist service state to Redis.

        Saves the runtime state (enabled, failure_count, restart tracking,
        status) to Redis for recovery across backend restarts.

        Does nothing if the service doesn't exist or no Redis client is configured.
        Logs and continues on Redis errors.

        Args:
            name: Service name to persist
        """
        if self._redis is None:
            logger.debug(f"No Redis client, skipping persist for {name}")
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

    def _apply_state_to_service(
        self, service: ManagedService, state: dict[str, Any], name: str
    ) -> None:
        """Apply loaded state dictionary to a service object.

        Args:
            service: Service to update
            state: State dictionary from Redis
            name: Service name for logging
        """
        service.enabled = state.get("enabled", True)
        service.failure_count = state.get("failure_count", 0)
        service.restart_count = state.get("restart_count", 0)

        last_failure = state.get("last_failure_at")
        service.last_failure_at = datetime.fromisoformat(last_failure) if last_failure else None

        last_restart = state.get("last_restart_at")
        service.last_restart_at = datetime.fromisoformat(last_restart) if last_restart else None

        status_str = state.get("status")
        if status_str:
            try:
                service.status = ContainerServiceStatus(status_str)
            except ValueError:
                logger.warning(
                    "Invalid status in Redis state",
                    extra={"service_name": name, "status": status_str},
                )

    async def load_state(self, name: str) -> None:
        """Load service state from Redis.

        Restores the runtime state (enabled, failure_count, restart tracking,
        status) from Redis after backend restart.

        Does nothing if the service doesn't exist, no Redis client is configured,
        or no Redis data found.
        Logs and continues on Redis errors.

        Args:
            name: Service name to load
        """
        if self._redis is None:
            logger.debug(f"No Redis client, skipping load_state for {name}")
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

            if isinstance(state, str):
                state = json.loads(state)

            with self._lock:
                service = self._services.get(name)
                if not service:
                    return
                self._apply_state_to_service(service, state, name)

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
