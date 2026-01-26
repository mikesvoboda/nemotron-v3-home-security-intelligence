"""Container Discovery Service for the Container Orchestrator.

This module provides the ContainerDiscoveryService that finds Docker containers
by name pattern and creates ManagedService objects with proper configuration.
The service is used by the container orchestrator to discover and manage
deployment containers including AI services, infrastructure, and monitoring.

Key Components:
- ServiceConfig: Configuration dataclass for service patterns (from orchestrator.models)
- ManagedService: Represents a discovered and managed container (from orchestrator.models)
- ContainerDiscoveryService: Main service for container discovery

Pre-configured Service Categories:
- INFRASTRUCTURE_CONFIGS: PostgreSQL, Redis (critical, aggressive restart)
- AI_CONFIGS: YOLO26v2, Nemotron, Florence, CLIP, Enrichment (standard backoff)
- MONITORING_CONFIGS: Prometheus, Grafana, Alertmanager, Redis Exporter, JSON Exporter,
                      Blackbox Exporter (lenient, per CATEGORY_DEFAULTS)

Usage:
    async with DockerClient() as docker:
        discovery = ContainerDiscoveryService(docker, orchestrator_settings)
        all_services = await discovery.discover_all()
        ai_services = await discovery.discover_by_category(ServiceCategory.AI)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.core.logging import get_logger
from backend.services.orchestrator import ManagedService, ServiceCategory, ServiceConfig

if TYPE_CHECKING:
    from backend.core.config import OrchestratorSettings
    from backend.core.docker_client import DockerClient

logger = get_logger(__name__)


def build_service_configs(
    settings: OrchestratorSettings | None = None,
    include_monitoring: bool = True,
) -> dict[str, ServiceConfig]:
    """Build service configurations using ports from OrchestratorSettings.

    Creates ServiceConfig objects for all managed container services. When settings
    is provided, uses configured port values; otherwise uses default ports.

    Args:
        settings: Optional OrchestratorSettings with port configuration.
                  If None, uses default port values.
        include_monitoring: If True, include monitoring service configs.
                           If False, exclude them (based on monitoring_enabled setting).

    Returns:
        Dictionary mapping service names to ServiceConfig objects.
    """
    # Default ports (used when settings is None)
    postgres_port = settings.postgres_port if settings else 5432
    redis_port = settings.redis_port if settings else 6379
    yolo26_port = settings.yolo26_port if settings else 8090
    nemotron_port = settings.nemotron_port if settings else 8091
    florence_port = settings.florence_port if settings else 8092
    clip_port = settings.clip_port if settings else 8093
    enrichment_port = settings.enrichment_port if settings else 8094
    prometheus_port = settings.prometheus_port if settings else 9090
    grafana_port = settings.grafana_port if settings else 3000
    redis_exporter_port = settings.redis_exporter_port if settings else 9121
    json_exporter_port = settings.json_exporter_port if settings else 7979
    alertmanager_port = settings.alertmanager_port if settings else 9093
    blackbox_exporter_port = settings.blackbox_exporter_port if settings else 9115
    jaeger_port = settings.jaeger_port if settings else 16686
    frontend_port = settings.frontend_port if settings else 8080

    infrastructure_configs: dict[str, ServiceConfig] = {
        "postgres": ServiceConfig(
            display_name="PostgreSQL",
            category=ServiceCategory.INFRASTRUCTURE,
            port=postgres_port,
            health_cmd="pg_isready -U security",
            startup_grace_period=10,
            max_failures=10,
            restart_backoff_base=2.0,
            restart_backoff_max=60.0,
        ),
        "redis": ServiceConfig(
            display_name="Redis",
            category=ServiceCategory.INFRASTRUCTURE,
            port=redis_port,
            health_cmd="redis-cli ping",
            startup_grace_period=10,
            max_failures=10,
            restart_backoff_base=2.0,
            restart_backoff_max=60.0,
        ),
    }

    ai_configs: dict[str, ServiceConfig] = {
        "ai-detector": ServiceConfig(
            display_name="YOLO26v2",
            category=ServiceCategory.AI,
            port=yolo26_port,
            health_endpoint="/health",
            startup_grace_period=60,
        ),
        "ai-llm": ServiceConfig(
            display_name="Nemotron",
            category=ServiceCategory.AI,
            port=nemotron_port,
            health_endpoint="/health",
            startup_grace_period=120,
        ),
        "ai-florence": ServiceConfig(
            display_name="Florence-2",
            category=ServiceCategory.AI,
            port=florence_port,
            health_endpoint="/health",
            startup_grace_period=60,
        ),
        "ai-clip": ServiceConfig(
            display_name="CLIP",
            category=ServiceCategory.AI,
            port=clip_port,
            health_endpoint="/health",
            startup_grace_period=60,
        ),
        "ai-enrichment": ServiceConfig(
            display_name="Enrichment",
            category=ServiceCategory.AI,
            port=enrichment_port,
            health_endpoint="/health",
            startup_grace_period=180,
        ),
    }

    # Monitoring configs use CATEGORY_DEFAULTS values:
    # max_failures: 5, base_backoff: 10.0, max_backoff: 120.0
    monitoring_configs: dict[str, ServiceConfig] = {
        "prometheus": ServiceConfig(
            display_name="Prometheus",
            category=ServiceCategory.MONITORING,
            port=prometheus_port,
            health_endpoint="/-/healthy",
            startup_grace_period=30,
            max_failures=5,
            restart_backoff_base=10.0,
            restart_backoff_max=120.0,
        ),
        "grafana": ServiceConfig(
            display_name="Grafana",
            category=ServiceCategory.MONITORING,
            port=grafana_port,
            health_endpoint="/api/health",
            startup_grace_period=30,
            max_failures=5,
            restart_backoff_base=10.0,
            restart_backoff_max=120.0,
        ),
        "alertmanager": ServiceConfig(
            display_name="Alertmanager",
            category=ServiceCategory.MONITORING,
            port=alertmanager_port,
            health_endpoint="/-/healthy",
            startup_grace_period=15,
            max_failures=5,
            restart_backoff_base=10.0,
            restart_backoff_max=120.0,
        ),
        "redis-exporter": ServiceConfig(
            display_name="Redis Exporter",
            category=ServiceCategory.MONITORING,
            port=redis_exporter_port,
            health_endpoint="/metrics",
            startup_grace_period=15,
            max_failures=5,
            restart_backoff_base=10.0,
            restart_backoff_max=120.0,
        ),
        "json-exporter": ServiceConfig(
            display_name="JSON Exporter",
            category=ServiceCategory.MONITORING,
            port=json_exporter_port,
            health_endpoint="/metrics",
            startup_grace_period=15,
            max_failures=5,
            restart_backoff_base=10.0,
            restart_backoff_max=120.0,
        ),
        "blackbox-exporter": ServiceConfig(
            display_name="Blackbox Exporter",
            category=ServiceCategory.MONITORING,
            port=blackbox_exporter_port,
            health_endpoint="/metrics",
            startup_grace_period=15,
            max_failures=5,
            restart_backoff_base=10.0,
            restart_backoff_max=120.0,
        ),
        "jaeger": ServiceConfig(
            display_name="Jaeger",
            category=ServiceCategory.MONITORING,
            port=jaeger_port,
            health_endpoint="/",
            startup_grace_period=15,
            max_failures=5,
            restart_backoff_base=10.0,
            restart_backoff_max=120.0,
        ),
        "frontend": ServiceConfig(
            display_name="Frontend",
            category=ServiceCategory.INFRASTRUCTURE,
            port=frontend_port,
            health_endpoint="/health",
            startup_grace_period=30,
            max_failures=10,
            restart_backoff_base=2.0,
            restart_backoff_max=60.0,
        ),
    }

    configs = {
        **infrastructure_configs,
        **ai_configs,
    }

    if include_monitoring:
        configs.update(monitoring_configs)

    return configs


# Default configs for backward compatibility (uses default port values)
# Note: Prefer using build_service_configs(settings) for configurable ports
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
    "frontend": ServiceConfig(
        display_name="Frontend",
        category=ServiceCategory.INFRASTRUCTURE,
        port=8080,
        health_endpoint="/health",
        startup_grace_period=30,
        max_failures=10,
        restart_backoff_base=2.0,
        restart_backoff_max=60.0,
    ),
}

AI_CONFIGS: dict[str, ServiceConfig] = {
    "ai-detector": ServiceConfig(
        display_name="YOLO26v2",
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

# Monitoring configs with CATEGORY_DEFAULTS values:
# max_failures: 5, base_backoff: 10.0, max_backoff: 120.0
MONITORING_CONFIGS: dict[str, ServiceConfig] = {
    "prometheus": ServiceConfig(
        display_name="Prometheus",
        category=ServiceCategory.MONITORING,
        port=9090,
        health_endpoint="/-/healthy",
        startup_grace_period=30,
        max_failures=5,
        restart_backoff_base=10.0,
        restart_backoff_max=120.0,
    ),
    "grafana": ServiceConfig(
        display_name="Grafana",
        category=ServiceCategory.MONITORING,
        port=3000,
        health_endpoint="/api/health",
        startup_grace_period=30,
        max_failures=5,
        restart_backoff_base=10.0,
        restart_backoff_max=120.0,
    ),
    "alertmanager": ServiceConfig(
        display_name="Alertmanager",
        category=ServiceCategory.MONITORING,
        port=9093,
        health_endpoint="/-/healthy",
        startup_grace_period=15,
        max_failures=5,
        restart_backoff_base=10.0,
        restart_backoff_max=120.0,
    ),
    "redis-exporter": ServiceConfig(
        display_name="Redis Exporter",
        category=ServiceCategory.MONITORING,
        port=9121,
        health_endpoint="/metrics",
        startup_grace_period=15,
        max_failures=5,
        restart_backoff_base=10.0,
        restart_backoff_max=120.0,
    ),
    "json-exporter": ServiceConfig(
        display_name="JSON Exporter",
        category=ServiceCategory.MONITORING,
        port=7979,
        health_endpoint="/metrics",
        startup_grace_period=15,
        max_failures=5,
        restart_backoff_base=10.0,
        restart_backoff_max=120.0,
    ),
    "blackbox-exporter": ServiceConfig(
        display_name="Blackbox Exporter",
        category=ServiceCategory.MONITORING,
        port=9115,
        health_endpoint="/metrics",
        startup_grace_period=15,
        max_failures=5,
        restart_backoff_base=10.0,
        restart_backoff_max=120.0,
    ),
    "jaeger": ServiceConfig(
        display_name="Jaeger",
        category=ServiceCategory.MONITORING,
        port=16686,
        health_endpoint="/",
        startup_grace_period=15,
        max_failures=5,
        restart_backoff_base=10.0,
        restart_backoff_max=120.0,
    ),
}

# Combined configs for all services (default ports for backward compatibility)
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
            # With configurable ports from OrchestratorSettings
            discovery = ContainerDiscoveryService(docker, orchestrator_settings)

            # Without settings (uses default ports for backward compatibility)
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

    def __init__(
        self,
        docker_client: DockerClient,
        settings: OrchestratorSettings | None = None,
    ) -> None:
        """Initialize the discovery service.

        Args:
            docker_client: DockerClient instance for container operations
            settings: Optional OrchestratorSettings with port configuration.
                      If None, uses default port values for backward compatibility.
                      When provided, respects monitoring_enabled setting.
        """
        self._docker_client = docker_client
        # Use configurable ports when settings provided, otherwise use defaults
        if settings:
            include_monitoring = settings.monitoring_enabled
            self._configs = build_service_configs(settings, include_monitoring)
        else:
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
