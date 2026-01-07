"""Container Discovery Service for the Container Orchestrator.

This module provides the ContainerDiscoveryService that finds Docker containers
by name pattern and creates ManagedService objects with proper configuration.
The service is used by the container orchestrator to discover and manage
deployment containers including AI services, infrastructure, and monitoring.

Key Components:
- ServiceConfig: Configuration dataclass for service patterns
- ManagedService: Represents a discovered and managed container
- ContainerDiscoveryService: Main service for container discovery

Pre-configured Service Categories:
- INFRASTRUCTURE_CONFIGS: PostgreSQL, Redis (critical, aggressive restart)
- AI_CONFIGS: RT-DETRv2, Nemotron, Florence, CLIP, Enrichment (standard backoff)
- MONITORING_CONFIGS: Prometheus, Grafana, Redis Exporter, JSON Exporter (lenient)

Usage:
    async with DockerClient() as docker:
        discovery = ContainerDiscoveryService(docker)
        all_services = await discovery.discover_all()
        ai_services = await discovery.discover_by_category(ServiceCategory.AI)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.api.schemas.services import ServiceCategory
from backend.core.logging import get_logger

if TYPE_CHECKING:
    from backend.core.docker_client import DockerClient

logger = get_logger(__name__)


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
    """Represents a discovered container that is managed by the orchestrator.

    Contains identity, configuration, and self-healing settings for a container.
    This is created by the discovery service and used by the orchestrator for
    health monitoring and lifecycle management.

    Attributes:
        name: Service identifier from config (e.g., "ai-detector", "postgres")
        display_name: Human-readable display name
        container_id: Docker container ID
        image: Container image with tag
        port: Primary service port
        health_endpoint: HTTP health check endpoint (optional)
        health_cmd: Docker exec health command (optional)
        category: Service category for restart policy
        max_failures: Consecutive failures before disabling
        restart_backoff_base: Initial backoff delay in seconds
        restart_backoff_max: Maximum backoff delay in seconds
        startup_grace_period: Seconds to wait before health checks
    """

    name: str
    display_name: str
    container_id: str
    image: str
    port: int
    category: ServiceCategory
    health_endpoint: str | None = None
    health_cmd: str | None = None
    max_failures: int = 5
    restart_backoff_base: float = 5.0
    restart_backoff_max: float = 300.0
    startup_grace_period: int = 60


# =============================================================================
# Pre-configured Service Configurations
# =============================================================================

INFRASTRUCTURE_CONFIGS: dict[str, ServiceConfig] = {
    "postgres": ServiceConfig(
        display_name="PostgreSQL",
        category=ServiceCategory.INFRASTRUCTURE,
        port=5432,
        health_cmd="pg_isready -U security",
        startup_grace_period=10,
        max_failures=10,
        restart_backoff_base=2.0,
        restart_backoff_max=60.0,
    ),
    "redis": ServiceConfig(
        display_name="Redis",
        category=ServiceCategory.INFRASTRUCTURE,
        port=6379,
        health_cmd="redis-cli ping",
        startup_grace_period=10,
        max_failures=10,
        restart_backoff_base=2.0,
        restart_backoff_max=60.0,
    ),
}

AI_CONFIGS: dict[str, ServiceConfig] = {
    "ai-detector": ServiceConfig(
        display_name="RT-DETRv2",
        category=ServiceCategory.AI,
        port=8090,
        health_endpoint="/health",
        startup_grace_period=60,
    ),
    "ai-llm": ServiceConfig(
        display_name="Nemotron",
        category=ServiceCategory.AI,
        port=8091,
        health_endpoint="/health",
        startup_grace_period=120,
    ),
    "ai-florence": ServiceConfig(
        display_name="Florence-2",
        category=ServiceCategory.AI,
        port=8092,
        health_endpoint="/health",
        startup_grace_period=60,
    ),
    "ai-clip": ServiceConfig(
        display_name="CLIP",
        category=ServiceCategory.AI,
        port=8093,
        health_endpoint="/health",
        startup_grace_period=60,
    ),
    "ai-enrichment": ServiceConfig(
        display_name="Enrichment",
        category=ServiceCategory.AI,
        port=8094,
        health_endpoint="/health",
        startup_grace_period=180,
    ),
}

MONITORING_CONFIGS: dict[str, ServiceConfig] = {
    "prometheus": ServiceConfig(
        display_name="Prometheus",
        category=ServiceCategory.MONITORING,
        port=9090,
        health_endpoint="/-/healthy",
        startup_grace_period=30,
        max_failures=3,
        restart_backoff_base=10.0,
        restart_backoff_max=600.0,
    ),
    "grafana": ServiceConfig(
        display_name="Grafana",
        category=ServiceCategory.MONITORING,
        port=3000,
        health_endpoint="/api/health",
        startup_grace_period=30,
        max_failures=3,
        restart_backoff_base=10.0,
        restart_backoff_max=600.0,
    ),
    "redis-exporter": ServiceConfig(
        display_name="Redis Exporter",
        category=ServiceCategory.MONITORING,
        port=9121,
        health_endpoint="/metrics",
        startup_grace_period=15,
        max_failures=3,
    ),
    "json-exporter": ServiceConfig(
        display_name="JSON Exporter",
        category=ServiceCategory.MONITORING,
        port=7979,
        health_endpoint="/metrics",
        startup_grace_period=15,
        max_failures=3,
    ),
}

# Combined configs for all services
ALL_CONFIGS: dict[str, ServiceConfig] = {
    **INFRASTRUCTURE_CONFIGS,
    **AI_CONFIGS,
    **MONITORING_CONFIGS,
}


class ContainerDiscoveryService:
    """Service for discovering Docker containers by name pattern.

    The discovery service finds running containers that match pre-configured
    service patterns and creates ManagedService objects with proper configuration.
    It supports filtering by service category and provides config lookup.

    Attributes:
        _docker_client: Docker client for container operations
        _configs: Dictionary of service configurations keyed by pattern name

    Usage:
        async with DockerClient() as docker:
            discovery = ContainerDiscoveryService(docker)

            # Discover all services
            all_services = await discovery.discover_all()

            # Discover by category
            ai_services = await discovery.discover_by_category(ServiceCategory.AI)

            # Check if a container name matches any pattern
            config_key = discovery.match_container_name("security-postgres-1")
            if config_key:
                config = discovery.get_config(config_key)
    """

    def __init__(self, docker_client: DockerClient) -> None:
        """Initialize the discovery service.

        Args:
            docker_client: DockerClient instance for container operations
        """
        self._docker_client = docker_client
        self._configs = ALL_CONFIGS

    async def discover_all(self) -> list[ManagedService]:
        """Discover all containers matching known service patterns.

        Lists all containers (running and stopped) and matches them against
        pre-configured service patterns. Creates ManagedService objects for
        each matched container.

        Returns:
            List of ManagedService objects for discovered containers
        """
        containers = await self._docker_client.list_containers(all=True)
        discovered: list[ManagedService] = []

        for container in containers:
            config_key = self.match_container_name(container.name)
            if config_key is None:
                continue

            config = self._configs[config_key]
            managed_service = self._create_managed_service(container, config_key, config)
            discovered.append(managed_service)

            logger.debug(
                f"Discovered container '{container.name}' as service '{config_key}'",
                extra={
                    "container_name": container.name,
                    "service_name": config_key,
                    "container_id": container.id,
                    "category": config.category.value,
                },
            )

        logger.info(
            f"Discovered {len(discovered)} containers",
            extra={"count": len(discovered)},
        )

        return discovered

    async def discover_by_category(self, category: ServiceCategory) -> list[ManagedService]:
        """Discover containers matching patterns in a specific category.

        Args:
            category: ServiceCategory to filter by

        Returns:
            List of ManagedService objects in the specified category
        """
        all_services = await self.discover_all()
        return [s for s in all_services if s.category == category]

    def get_config(self, name: str) -> ServiceConfig | None:
        """Get service configuration by name.

        Args:
            name: Service name (config key like "postgres", "ai-detector")

        Returns:
            ServiceConfig if found, None otherwise
        """
        return self._configs.get(name)

    def match_container_name(self, container_name: str) -> str | None:
        """Match a container name against known service patterns.

        Searches for config keys that appear in the container name.
        Prefers longer/more specific matches when multiple patterns match.

        Args:
            container_name: Docker container name to match

        Returns:
            Config key (service name) if a pattern matches, None otherwise
        """
        matches: list[str] = []

        for pattern in self._configs:
            if pattern in container_name:
                matches.append(pattern)

        if not matches:
            return None

        # Prefer longer matches (more specific patterns)
        # e.g., "redis-exporter" should match over "redis"
        matches.sort(key=len, reverse=True)
        return matches[0]

    def _create_managed_service(
        self,
        container: object,
        config_key: str,
        config: ServiceConfig,
    ) -> ManagedService:
        """Create a ManagedService from container and config.

        Args:
            container: Docker container object
            config_key: Service name/config key
            config: ServiceConfig for this service

        Returns:
            ManagedService instance
        """
        # Get image tag, handling empty tags list
        image_tags = getattr(container, "image", None)
        if image_tags is not None:
            tags = getattr(image_tags, "tags", [])
            image = tags[0] if tags else f"<untagged:{getattr(container, 'id', 'unknown')[:12]}>"
        else:
            image = "<unknown>"

        return ManagedService(
            name=config_key,
            display_name=config.display_name,
            container_id=getattr(container, "id", ""),
            image=image,
            port=config.port,
            health_endpoint=config.health_endpoint,
            health_cmd=config.health_cmd,
            category=config.category,
            max_failures=config.max_failures,
            restart_backoff_base=config.restart_backoff_base,
            restart_backoff_max=config.restart_backoff_max,
            startup_grace_period=config.startup_grace_period,
        )
