"""Shared data models for container orchestration.

This module provides the canonical dataclass definitions used across all
orchestration services including container discovery, health monitoring,
lifecycle management, and the main orchestrator.

Classes:
    ServiceConfig: Configuration for service discovery patterns
    ManagedService: Runtime state of a managed container service
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from backend.services.orchestrator.enums import ContainerServiceStatus, ServiceCategory

# Category-specific defaults for lifecycle management.
# Used by container_discovery to configure ManagedService instances.
# Keys: max_failures, base_backoff, max_backoff, health_check_interval
CATEGORY_DEFAULTS: dict[ServiceCategory, dict[str, int | float]] = {
    ServiceCategory.INFRASTRUCTURE: {
        "max_failures": 10,
        "base_backoff": 2.0,
        "max_backoff": 60.0,
        "health_check_interval": 30,
    },
    ServiceCategory.AI: {
        "max_failures": 5,
        "base_backoff": 5.0,
        "max_backoff": 300.0,
        "health_check_interval": 30,
    },
    ServiceCategory.MONITORING: {
        "max_failures": 5,
        "base_backoff": 10.0,
        "max_backoff": 120.0,
        "health_check_interval": 30,
    },
}


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

    Represents a container with its identity, configuration, and runtime state.
    Used by the container orchestrator for health monitoring and self-healing.

    This is the canonical ManagedService dataclass - all orchestration modules
    should use this definition instead of defining their own.

    Attributes:
        name: Service identifier (e.g., "postgres", "ai-yolo26", "grafana")
        display_name: Human-readable name (e.g., "PostgreSQL", "YOLO26v2")
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
    category: ServiceCategory
    health_endpoint: str | None = None
    health_cmd: str | None = None
    status: ContainerServiceStatus = ContainerServiceStatus.NOT_FOUND
    enabled: bool = True

    # Model warmth state (NEM-1670) - for AI services only
    # Values: 'cold', 'warming', 'warm', 'unknown'
    warmth_state: str = "unknown"

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
            "warmth_state": self.warmth_state,
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
            warmth_state=data.get("warmth_state", "unknown"),
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
        """Create a ManagedService from a ServiceConfig and container info.

        This is used during service discovery when converting a discovered
        container into a ManagedService for tracking.

        Args:
            config_key: Service name/config key (e.g., "postgres", "ai-yolo26")
            config: ServiceConfig with service settings
            container_id: Docker container ID
            image: Container image string

        Returns:
            New ManagedService instance with settings from config
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
            enabled=True,
            max_failures=config.max_failures,
            restart_backoff_base=config.restart_backoff_base,
            restart_backoff_max=config.restart_backoff_max,
            startup_grace_period=config.startup_grace_period,
        )

    @property
    def last_failure_timestamp(self) -> float | None:
        """Get last_failure_at as Unix timestamp.

        Provided for compatibility with code expecting Unix timestamps.

        Returns:
            Unix timestamp of last failure, or None if never failed.
        """
        if self.last_failure_at:
            return self.last_failure_at.timestamp()
        return None

    def record_failure(self) -> None:
        """Record a health check failure.

        Increments failure_count and updates last_failure_at.
        """
        self.failure_count += 1
        self.last_failure_at = datetime.now(UTC)

    def record_restart(self) -> None:
        """Record a service restart.

        Increments restart_count and updates last_restart_at.
        """
        self.restart_count += 1
        self.last_restart_at = datetime.now(UTC)

    def reset_failures(self) -> None:
        """Reset failure tracking.

        Clears failure_count and last_failure_at.
        """
        self.failure_count = 0
        self.last_failure_at = None

    def in_grace_period(self) -> bool:
        """Check if service is in startup grace period.

        Returns:
            True if service was restarted recently and is still in grace period.
        """
        if self.last_restart_at:
            elapsed = (datetime.now(UTC) - self.last_restart_at).total_seconds()
            return elapsed < self.startup_grace_period
        return False


__all__ = [
    "CATEGORY_DEFAULTS",
    "ManagedService",
    "ServiceConfig",
]
