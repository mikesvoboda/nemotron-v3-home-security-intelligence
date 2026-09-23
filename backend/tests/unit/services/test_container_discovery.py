"""Unit tests for ContainerDiscoveryService.

Tests for the container discovery service that finds Docker containers by name
pattern and creates ManagedService objects with proper configuration.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.api.schemas.services import ServiceCategory
from backend.services.container_discovery import (
    AI_CONFIGS,
    ALL_CONFIGS,
    INFRASTRUCTURE_CONFIGS,
    MONITORING_CONFIGS,
    ContainerDiscoveryService,
    ManagedService,
    ServiceConfig,
    build_configs_from_compose,
    build_service_configs,
)

# Fixtures


@pytest.fixture
def mock_docker_client() -> MagicMock:
    """Mock DockerClient for testing."""
    client = MagicMock()
    client.list_containers = AsyncMock(return_value=[])
    return client


@pytest.fixture
def mock_container() -> MagicMock:
    """Create a mock Docker container."""
    container = MagicMock()
    container.id = "abc123def456"  # pragma: allowlist secret
    container.name = "test-container"
    container.status = "running"
    container.image.tags = ["test-image:latest"]
    return container


def create_mock_container(
    name: str,
    container_id: str = "abc123",
    status: str = "running",
    image_tags: list[str] | None = None,
) -> MagicMock:
    """Factory to create mock containers with specific attributes."""
    container = MagicMock()
    container.id = container_id
    container.name = name
    container.status = status
    container.image.tags = image_tags or ["default:latest"]
    return container


# ServiceConfig Tests


class TestServiceConfig:
    """Tests for ServiceConfig dataclass."""

    def test_service_config_defaults(self) -> None:
        """Test ServiceConfig has correct default values."""
        config = ServiceConfig(
            display_name="Test Service",
            category=ServiceCategory.AI,
            port=8080,
        )

        assert config.display_name == "Test Service"
        assert config.category == ServiceCategory.AI
        assert config.port == 8080
        assert config.health_endpoint is None
        assert config.health_cmd is None
        assert config.startup_grace_period == 60
        assert config.max_failures == 5
        assert config.restart_backoff_base == 5.0
        assert config.restart_backoff_max == 300.0

    def test_service_config_with_health_endpoint(self) -> None:
        """Test ServiceConfig with health endpoint."""
        config = ServiceConfig(
            display_name="API Service",
            category=ServiceCategory.AI,
            port=8095,
            health_endpoint="/health",
        )

        assert config.health_endpoint == "/health"
        assert config.health_cmd is None

    def test_service_config_with_health_cmd(self) -> None:
        """Test ServiceConfig with health command."""
        config = ServiceConfig(
            display_name="PostgreSQL",
            category=ServiceCategory.INFRASTRUCTURE,
            port=5432,
            health_cmd="pg_isready -U security",
        )

        assert config.health_endpoint is None
        assert config.health_cmd == "pg_isready -U security"


# Pre-configured Service Tests


class TestPreConfiguredServices:
    """Tests for pre-configured service configurations."""

    def test_infrastructure_configs_contains_postgres(self) -> None:
        """Test that INFRASTRUCTURE_CONFIGS contains postgres."""
        assert "postgres" in INFRASTRUCTURE_CONFIGS
        config = INFRASTRUCTURE_CONFIGS["postgres"]
        assert config.display_name == "PostgreSQL"
        assert config.category == ServiceCategory.INFRASTRUCTURE
        assert config.port == 5432
        assert config.health_cmd == "pg_isready -U security"
        assert config.max_failures == 10
        assert config.restart_backoff_base == 2.0
        assert config.restart_backoff_max == 60.0

    def test_infrastructure_configs_contains_redis(self) -> None:
        """Test that INFRASTRUCTURE_CONFIGS contains redis."""
        assert "redis" in INFRASTRUCTURE_CONFIGS
        config = INFRASTRUCTURE_CONFIGS["redis"]
        assert config.display_name == "Redis"
        assert config.category == ServiceCategory.INFRASTRUCTURE
        assert config.port == 6379
        assert config.health_cmd == "redis-cli ping"

    def test_ai_configs_contains_all_ai_services(self) -> None:
        """Test that AI_CONFIGS contains all expected AI services."""
        # Ports from .env.example (source of truth)
        expected_services = {
            "ai-gateway": ("AI Gateway", 8090, 120),
            "ai-llm": ("Nemotron", 8091, 120),
            "ai-llm-vllm": ("LLM vLLM", 8097, 120),
        }

        for name, (display_name, port, grace_period) in expected_services.items():
            assert name in AI_CONFIGS, f"Missing AI config: {name}"
            config = AI_CONFIGS[name]
            assert config.display_name == display_name
            assert config.category == ServiceCategory.AI
            assert config.port == port
            assert config.health_endpoint == "/health"
            assert config.startup_grace_period == grace_period

    def test_monitoring_configs_contains_prometheus(self) -> None:
        """Test that MONITORING_CONFIGS contains prometheus."""
        assert "prometheus" in MONITORING_CONFIGS
        config = MONITORING_CONFIGS["prometheus"]
        assert config.display_name == "Prometheus"
        assert config.category == ServiceCategory.MONITORING
        assert config.port == 9090
        assert config.health_endpoint == "/-/healthy"
        # CATEGORY_DEFAULTS for MONITORING: max_failures=5, base_backoff=10.0, max_backoff=120.0
        assert config.max_failures == 5
        assert config.restart_backoff_base == 10.0
        assert config.restart_backoff_max == 120.0

    def test_monitoring_configs_contains_grafana(self) -> None:
        """Test that MONITORING_CONFIGS contains grafana."""
        assert "grafana" in MONITORING_CONFIGS
        config = MONITORING_CONFIGS["grafana"]
        assert config.display_name == "Grafana"
        assert config.category == ServiceCategory.MONITORING
        assert config.port == 3002  # Port from .env.example
        assert config.health_endpoint == "/api/health"

    def test_monitoring_configs_contains_exporters(self) -> None:
        """Test that MONITORING_CONFIGS contains exporter services."""
        assert "redis-exporter" in MONITORING_CONFIGS
        assert MONITORING_CONFIGS["redis-exporter"].port == 9121

        assert "json-exporter" in MONITORING_CONFIGS
        assert MONITORING_CONFIGS["json-exporter"].port == 7979

    def test_all_configs_combines_all_categories(self) -> None:
        """Test that ALL_CONFIGS contains all services from all categories."""
        expected_count = len(INFRASTRUCTURE_CONFIGS) + len(AI_CONFIGS) + len(MONITORING_CONFIGS)
        assert len(ALL_CONFIGS) == expected_count

        # Verify all configs are present
        for name in INFRASTRUCTURE_CONFIGS:
            assert name in ALL_CONFIGS
        for name in AI_CONFIGS:
            assert name in ALL_CONFIGS
        for name in MONITORING_CONFIGS:
            assert name in ALL_CONFIGS


# ManagedService Tests


class TestManagedService:
    """Tests for ManagedService dataclass."""

    def test_managed_service_creation(self) -> None:
        """Test ManagedService can be created with required fields."""
        service = ManagedService(
            name="ai-yolo26",
            display_name="YOLO26",
            container_id="abc123",
            image="ghcr.io/test/yolo26:latest",
            port=8095,
            health_endpoint="/health",
            category=ServiceCategory.AI,
        )

        assert service.name == "ai-yolo26"
        assert service.display_name == "YOLO26"
        assert service.container_id == "abc123"
        assert service.image == "ghcr.io/test/yolo26:latest"
        assert service.port == 8095
        assert service.health_endpoint == "/health"
        assert service.health_cmd is None
        assert service.category == ServiceCategory.AI

    def test_managed_service_with_health_cmd(self) -> None:
        """Test ManagedService with health command instead of endpoint."""
        service = ManagedService(
            name="postgres",
            display_name="PostgreSQL",
            container_id="def456",
            image="postgres:16-alpine",
            port=5432,
            health_cmd="pg_isready -U security",
            category=ServiceCategory.INFRASTRUCTURE,
        )

        assert service.health_endpoint is None
        assert service.health_cmd == "pg_isready -U security"

    def test_managed_service_self_healing_defaults(self) -> None:
        """Test ManagedService has correct self-healing default values."""
        service = ManagedService(
            name="test",
            display_name="Test",
            container_id="test123",
            image="test:latest",
            port=8080,
            category=ServiceCategory.AI,
        )

        assert service.max_failures == 5
        assert service.restart_backoff_base == 5.0
        assert service.restart_backoff_max == 300.0
        assert service.startup_grace_period == 60


# ContainerDiscoveryService Tests


class TestContainerDiscoveryService:
    """Tests for ContainerDiscoveryService."""

    @pytest.mark.asyncio
    async def test_discover_all_finds_postgres_container(
        self, mock_docker_client: MagicMock
    ) -> None:
        """Test discovery finds PostgreSQL container matching pattern."""
        mock_postgres = create_mock_container(
            name="security-postgres-1",
            container_id="pg123",
            image_tags=["postgres:16-alpine"],
        )
        mock_docker_client.list_containers = AsyncMock(return_value=[mock_postgres])

        service = ContainerDiscoveryService(mock_docker_client)
        discovered = await service.discover_all()

        assert len(discovered) == 1
        assert discovered[0].name == "postgres"
        assert discovered[0].display_name == "PostgreSQL"
        assert discovered[0].container_id == "pg123"
        assert discovered[0].port == 5432
        assert discovered[0].category == ServiceCategory.INFRASTRUCTURE

    @pytest.mark.asyncio
    async def test_discover_all_finds_ai_gateway_container(
        self, mock_docker_client: MagicMock
    ) -> None:
        """Test discovery finds the AI gateway container matching pattern."""
        mock_gateway = create_mock_container(
            name="security-ai-gateway-1",
            container_id="gw123",
            image_tags=["ghcr.io/test/ai-gateway:latest"],
        )
        mock_docker_client.list_containers = AsyncMock(return_value=[mock_gateway])

        service = ContainerDiscoveryService(mock_docker_client)
        discovered = await service.discover_all()

        assert len(discovered) == 1
        assert discovered[0].name == "ai-gateway"
        assert discovered[0].display_name == "AI Gateway"
        assert discovered[0].container_id == "gw123"
        assert discovered[0].port == 8090  # Port from .env.example
        assert discovered[0].health_endpoint == "/health"
        assert discovered[0].category == ServiceCategory.AI

    @pytest.mark.asyncio
    async def test_discover_all_finds_multiple_containers(
        self, mock_docker_client: MagicMock
    ) -> None:
        """Test discovery finds multiple containers across categories."""
        containers = [
            create_mock_container("security-postgres-1", "pg123"),
            create_mock_container("security-redis-1", "redis123"),
            create_mock_container("security-ai-gateway-1", "gw123"),
            create_mock_container("security-prometheus-1", "prom123"),
        ]
        mock_docker_client.list_containers = AsyncMock(return_value=containers)

        service = ContainerDiscoveryService(mock_docker_client)
        discovered = await service.discover_all()

        assert len(discovered) == 4
        names = {s.name for s in discovered}
        assert names == {"postgres", "redis", "ai-gateway", "prometheus"}

    @pytest.mark.asyncio
    async def test_discover_all_ignores_unrecognized_containers(
        self, mock_docker_client: MagicMock
    ) -> None:
        """Test discovery ignores containers that don't match any pattern."""
        containers = [
            create_mock_container("security-postgres-1", "pg123"),
            create_mock_container("some-random-service", "rand123"),
            create_mock_container("my-custom-app", "app123"),
        ]
        mock_docker_client.list_containers = AsyncMock(return_value=containers)

        service = ContainerDiscoveryService(mock_docker_client)
        discovered = await service.discover_all()

        assert len(discovered) == 1
        assert discovered[0].name == "postgres"

    @pytest.mark.asyncio
    async def test_discover_all_returns_empty_when_no_containers(
        self, mock_docker_client: MagicMock
    ) -> None:
        """Test discovery returns empty list when no containers exist."""
        mock_docker_client.list_containers = AsyncMock(return_value=[])

        service = ContainerDiscoveryService(mock_docker_client)
        discovered = await service.discover_all()

        assert discovered == []

    @pytest.mark.asyncio
    async def test_discover_by_category_infrastructure(self, mock_docker_client: MagicMock) -> None:
        """Test discovery filtering by infrastructure category."""
        containers = [
            create_mock_container("security-postgres-1", "pg123"),
            create_mock_container("security-redis-1", "redis123"),
            create_mock_container("security-ai-gateway-1", "gw123"),
            create_mock_container("security-prometheus-1", "prom123"),
        ]
        mock_docker_client.list_containers = AsyncMock(return_value=containers)

        service = ContainerDiscoveryService(mock_docker_client)
        discovered = await service.discover_by_category(ServiceCategory.INFRASTRUCTURE)

        assert len(discovered) == 2
        names = {s.name for s in discovered}
        assert names == {"postgres", "redis"}
        for s in discovered:
            assert s.category == ServiceCategory.INFRASTRUCTURE

    @pytest.mark.asyncio
    async def test_discover_by_category_ai(self, mock_docker_client: MagicMock) -> None:
        """Test discovery filtering by AI category."""
        containers = [
            create_mock_container("security-postgres-1", "pg123"),
            create_mock_container("security-ai-gateway-1", "gw123"),
            create_mock_container("security-ai-llm-1", "llm123"),
            create_mock_container("security-ai-llm-vllm-1", "vllm123"),
        ]
        mock_docker_client.list_containers = AsyncMock(return_value=containers)

        service = ContainerDiscoveryService(mock_docker_client)
        discovered = await service.discover_by_category(ServiceCategory.AI)

        assert len(discovered) == 3
        names = {s.name for s in discovered}
        assert names == {"ai-gateway", "ai-llm", "ai-llm-vllm"}
        for s in discovered:
            assert s.category == ServiceCategory.AI

    @pytest.mark.asyncio
    async def test_discover_by_category_monitoring(self, mock_docker_client: MagicMock) -> None:
        """Test discovery filtering by monitoring category."""
        containers = [
            create_mock_container("security-prometheus-1", "prom123"),
            create_mock_container("security-grafana-1", "graf123"),
            create_mock_container("security-redis-exporter-1", "rexp123"),
            create_mock_container("security-ai-gateway-1", "gw123"),
        ]
        mock_docker_client.list_containers = AsyncMock(return_value=containers)

        service = ContainerDiscoveryService(mock_docker_client)
        discovered = await service.discover_by_category(ServiceCategory.MONITORING)

        assert len(discovered) == 3
        names = {s.name for s in discovered}
        assert names == {"prometheus", "grafana", "redis-exporter"}
        for s in discovered:
            assert s.category == ServiceCategory.MONITORING

    def test_get_config_returns_config_for_known_service(
        self, mock_docker_client: MagicMock
    ) -> None:
        """Test get_config returns config for known service name."""
        service = ContainerDiscoveryService(mock_docker_client)

        config = service.get_config("postgres")
        assert config is not None
        assert config.display_name == "PostgreSQL"
        assert config.port == 5432

        config = service.get_config("ai-gateway")
        assert config is not None
        assert config.display_name == "AI Gateway"
        assert config.port == 8090  # Port from .env.example

    def test_get_config_returns_none_for_unknown_service(
        self, mock_docker_client: MagicMock
    ) -> None:
        """Test get_config returns None for unknown service name."""
        service = ContainerDiscoveryService(mock_docker_client)

        config = service.get_config("unknown-service")
        assert config is None

        config = service.get_config("my-custom-app")
        assert config is None

    def test_match_container_name_returns_config_key(self, mock_docker_client: MagicMock) -> None:
        """Test match_container_name returns correct config key for matching names."""
        service = ContainerDiscoveryService(mock_docker_client)

        # Exact match
        assert service.match_container_name("postgres") == "postgres"
        assert service.match_container_name("ai-gateway") == "ai-gateway"

        # Prefix match
        assert service.match_container_name("security-postgres-1") == "postgres"
        assert service.match_container_name("myapp-ai-gateway-prod") == "ai-gateway"

        # Contains match
        assert service.match_container_name("my-redis-cache") == "redis"
        assert service.match_container_name("staging-prometheus-server") == "prometheus"

    def test_match_container_name_returns_none_for_no_match(
        self, mock_docker_client: MagicMock
    ) -> None:
        """Test match_container_name returns None when no pattern matches."""
        service = ContainerDiscoveryService(mock_docker_client)

        assert service.match_container_name("random-service") is None
        assert service.match_container_name("my-app") is None
        assert service.match_container_name("unknown-container") is None

    def test_match_container_name_prefers_longer_match(self, mock_docker_client: MagicMock) -> None:
        """Test match_container_name prefers longer/more specific patterns."""
        service = ContainerDiscoveryService(mock_docker_client)

        # "redis-exporter" should match "redis-exporter" not "redis"
        result = service.match_container_name("security-redis-exporter-1")
        assert result == "redis-exporter"

    @pytest.mark.asyncio
    async def test_discover_uses_image_tags_from_container(
        self, mock_docker_client: MagicMock
    ) -> None:
        """Test discovered services include correct image from container."""
        mock_container = create_mock_container(
            name="security-ai-llm-1",
            container_id="llm123",
            image_tags=["ghcr.io/myorg/nemotron:v1.2.3"],
        )
        mock_docker_client.list_containers = AsyncMock(return_value=[mock_container])

        service = ContainerDiscoveryService(mock_docker_client)
        discovered = await service.discover_all()

        assert len(discovered) == 1
        assert discovered[0].image == "ghcr.io/myorg/nemotron:v1.2.3"

    @pytest.mark.asyncio
    async def test_discover_handles_container_without_image_tags(
        self, mock_docker_client: MagicMock
    ) -> None:
        """Test discovery handles containers without image tags gracefully."""
        mock_container = create_mock_container(
            name="security-postgres-1",
            container_id="pg123",
        )
        mock_container.image.tags = []
        mock_docker_client.list_containers = AsyncMock(return_value=[mock_container])

        service = ContainerDiscoveryService(mock_docker_client)
        discovered = await service.discover_all()

        assert len(discovered) == 1
        # Should have some fallback or empty string
        assert discovered[0].image is not None

    @pytest.mark.asyncio
    async def test_discover_passes_config_values_to_managed_service(
        self, mock_docker_client: MagicMock
    ) -> None:
        """Test discovered services have config values properly set."""
        mock_container = create_mock_container(
            name="security-prometheus-1",
            container_id="prom123",
            image_tags=["prom/prometheus:v2.50.0"],
        )
        mock_docker_client.list_containers = AsyncMock(return_value=[mock_container])

        service = ContainerDiscoveryService(mock_docker_client)
        discovered = await service.discover_all()

        assert len(discovered) == 1
        prometheus = discovered[0]

        # Check all config values are transferred
        assert prometheus.name == "prometheus"
        assert prometheus.display_name == "Prometheus"
        assert prometheus.port == 9090
        assert prometheus.health_endpoint == "/-/healthy"
        assert prometheus.category == ServiceCategory.MONITORING
        # CATEGORY_DEFAULTS for MONITORING: max_failures=5, base_backoff=10.0, max_backoff=120.0
        assert prometheus.max_failures == 5
        assert prometheus.restart_backoff_base == 10.0
        assert prometheus.restart_backoff_max == 120.0
        assert prometheus.startup_grace_period == 30


# Edge Case Tests


class TestContainerDiscoveryEdgeCases:
    """Tests for edge cases in container discovery."""

    @pytest.mark.asyncio
    async def test_discover_with_duplicate_pattern_matches(
        self, mock_docker_client: MagicMock
    ) -> None:
        """Test discovery handles multiple containers matching same pattern."""
        # Two containers that both match "postgres" pattern
        containers = [
            create_mock_container("postgres-primary", "pg1"),
            create_mock_container("postgres-replica", "pg2"),
        ]
        mock_docker_client.list_containers = AsyncMock(return_value=containers)

        service = ContainerDiscoveryService(mock_docker_client)
        discovered = await service.discover_all()

        # Should discover both containers
        assert len(discovered) == 2
        for s in discovered:
            assert s.name == "postgres"

    @pytest.mark.asyncio
    async def test_discover_with_case_sensitive_matching(
        self, mock_docker_client: MagicMock
    ) -> None:
        """Test container name matching is case-sensitive."""
        containers = [
            create_mock_container("POSTGRES-1", "pg1"),  # uppercase
            create_mock_container("postgres-2", "pg2"),  # lowercase
        ]
        mock_docker_client.list_containers = AsyncMock(return_value=containers)

        service = ContainerDiscoveryService(mock_docker_client)
        discovered = await service.discover_all()

        # Only lowercase should match (patterns are lowercase)
        assert len(discovered) == 1
        assert discovered[0].container_id == "pg2"

    @pytest.mark.asyncio
    async def test_discover_all_calls_docker_client_correctly(
        self, mock_docker_client: MagicMock
    ) -> None:
        """Test discover_all calls docker client with correct parameters."""
        service = ContainerDiscoveryService(mock_docker_client)
        await service.discover_all()

        mock_docker_client.list_containers.assert_called_once_with(all=True)


# =============================================================================
# Category Priority Tests
# =============================================================================


class TestCategoryPriorityOrdering:
    """Tests for service category priority ordering.

    Infrastructure services should be processed with higher priority
    (more aggressive backoff) than AI services, and AI services should
    be processed with higher priority than Monitoring services.
    """

    def test_infrastructure_has_most_aggressive_backoff(self) -> None:
        """Test that infrastructure services have the most aggressive backoff settings."""
        # Infrastructure: 2s base, 60s max
        # AI: 5s base, 300s max
        # Monitoring: 10s base, 600s max
        for name, config in INFRASTRUCTURE_CONFIGS.items():
            assert config.restart_backoff_base == 2.0, f"{name} should have 2s base backoff"
            assert config.restart_backoff_max == 60.0, f"{name} should have 60s max backoff"

    def test_ai_has_standard_backoff(self) -> None:
        """Test that AI services have standard backoff settings."""
        for name, config in AI_CONFIGS.items():
            assert config.restart_backoff_base == 5.0, f"{name} should have 5s base backoff"
            assert config.restart_backoff_max == 300.0, f"{name} should have 300s max backoff"

    def test_monitoring_has_lenient_backoff(self) -> None:
        """Test that monitoring services have lenient backoff settings per CATEGORY_DEFAULTS."""
        for name, config in MONITORING_CONFIGS.items():
            # All monitoring services use CATEGORY_DEFAULTS: base_backoff=10.0, max_backoff=120.0
            assert config.restart_backoff_base == 10.0, f"{name} should have 10s base backoff"
            assert config.restart_backoff_max == 120.0, f"{name} should have 120s max backoff"

    def test_infrastructure_backoff_less_than_ai(self) -> None:
        """Test that infrastructure backoff is less than AI (more aggressive)."""
        infra_config = INFRASTRUCTURE_CONFIGS["postgres"]
        ai_config = AI_CONFIGS["ai-gateway"]

        assert infra_config.restart_backoff_base < ai_config.restart_backoff_base
        assert infra_config.restart_backoff_max < ai_config.restart_backoff_max

    def test_ai_backoff_less_than_monitoring(self) -> None:
        """Test that AI base backoff is less than monitoring (more aggressive base).

        Note: AI uses default max backoff (300.0) which is higher than monitoring's
        explicit max (120.0). This is intentional - AI services have aggressive
        base backoff but larger max to avoid overwhelming GPU resources.
        """
        ai_config = AI_CONFIGS["ai-gateway"]
        mon_config = MONITORING_CONFIGS["prometheus"]

        # Base backoff: AI(5.0) < monitoring(10.0) - AI restarts faster initially
        assert ai_config.restart_backoff_base < mon_config.restart_backoff_base
        # Max backoff: AI(300.0) > monitoring(120.0) - AI has higher ceiling
        assert ai_config.restart_backoff_max > mon_config.restart_backoff_max

    def test_infrastructure_has_highest_max_failures(self) -> None:
        """Test that infrastructure services tolerate more failures before disabling."""
        for name, config in INFRASTRUCTURE_CONFIGS.items():
            assert config.max_failures == 10, f"{name} should have max_failures=10"

    def test_ai_has_standard_max_failures(self) -> None:
        """Test that AI services have standard max failures."""
        for name, config in AI_CONFIGS.items():
            assert config.max_failures == 5, f"{name} should have max_failures=5"

    def test_monitoring_has_moderate_max_failures(self) -> None:
        """Test that monitoring services have moderate max failures per CATEGORY_DEFAULTS."""
        for name, config in MONITORING_CONFIGS.items():
            # CATEGORY_DEFAULTS for MONITORING: max_failures=5
            assert config.max_failures == 5, f"{name} should have max_failures=5"

    def test_category_backoff_hierarchy(self) -> None:
        """Test complete backoff hierarchy: infrastructure < ai < monitoring (base) and infra < mon < ai (max)."""
        # Get one representative from each category
        infra_base = INFRASTRUCTURE_CONFIGS["postgres"].restart_backoff_base
        ai_base = AI_CONFIGS["ai-gateway"].restart_backoff_base
        mon_base = MONITORING_CONFIGS["prometheus"].restart_backoff_base

        # Base backoff: infra(2) < ai(5) < mon(10) - more aggressive for infrastructure
        assert infra_base < ai_base < mon_base, (
            f"Expected backoff hierarchy infra({infra_base}) < ai({ai_base}) < mon({mon_base})"
        )

        infra_max = INFRASTRUCTURE_CONFIGS["postgres"].restart_backoff_max
        ai_max = AI_CONFIGS["ai-gateway"].restart_backoff_max
        mon_max = MONITORING_CONFIGS["prometheus"].restart_backoff_max

        # Max backoff: infra(60) < mon(120) < ai(300) - AI uses default 300.0
        assert infra_max < mon_max < ai_max, (
            f"Expected max backoff hierarchy infra({infra_max}) < mon({mon_max}) < ai({ai_max})"
        )

    @pytest.mark.asyncio
    async def test_discovered_services_preserve_category_settings(
        self, mock_docker_client: MagicMock
    ) -> None:
        """Test that discovered services preserve their category-specific settings."""
        containers = [
            create_mock_container("security-postgres-1", "pg123"),
            create_mock_container("security-ai-gateway-1", "gw123"),
            create_mock_container("security-prometheus-1", "prom123"),
        ]
        mock_docker_client.list_containers = AsyncMock(return_value=containers)

        service = ContainerDiscoveryService(mock_docker_client)
        discovered = await service.discover_all()

        # Find each service
        postgres = next(s for s in discovered if s.name == "postgres")
        detector = next(s for s in discovered if s.name == "ai-gateway")
        prometheus = next(s for s in discovered if s.name == "prometheus")

        # Verify category-specific settings preserved
        assert postgres.restart_backoff_base == 2.0
        assert postgres.restart_backoff_max == 60.0
        assert postgres.max_failures == 10

        assert detector.restart_backoff_base == 5.0
        assert detector.restart_backoff_max == 300.0
        assert detector.max_failures == 5

        assert prometheus.restart_backoff_base == 10.0
        assert prometheus.restart_backoff_max == 120.0
        assert prometheus.max_failures == 5


# =============================================================================
# Config Builder Kill Tests (WP4.4 — gen-2 dossier container_discovery G1-G13)
# =============================================================================


# Golden table for build_service_configs(settings=None): the .env.example default
# ports plus the hardcoded probe/grace/backoff policy. Values verified against
# shipped source on 2026-09-18 (wave-57 dossier's independently derived table
# agrees, 21/21 services on the post-tempo/live-set rebuild).
# (display_name, category, port, health_endpoint, health_cmd,
#  startup_grace_period, max_failures, restart_backoff_base, restart_backoff_max)
EXPECTED_BUILDER_TABLE: dict[str, tuple] = {
    "postgres": (
        "PostgreSQL",
        "INFRASTRUCTURE",
        5432,
        None,
        "pg_isready -U security",
        10,
        10,
        2.0,
        60.0,
    ),
    "redis": ("Redis", "INFRASTRUCTURE", 6379, None, "redis-cli ping", 10, 10, 2.0, 60.0),
    "backend": (
        "Backend API",
        "INFRASTRUCTURE",
        8000,
        "/api/system/health/ready",
        None,
        30,
        10,
        2.0,
        60.0,
    ),
    "go2rtc": ("go2rtc", "INFRASTRUCTURE", 1984, "/api", None, 15, 10, 2.0, 60.0),
    "frontend": ("Frontend", "INFRASTRUCTURE", 8080, "/health", None, 30, 10, 2.0, 60.0),
    "ai-gateway": ("AI Gateway", "AI", 8090, "/health", None, 120, 5, 5.0, 300.0),
    "ai-llm": ("Nemotron", "AI", 8091, "/health", None, 120, 5, 5.0, 300.0),
    "ai-llm-vllm": ("LLM vLLM", "AI", 8097, "/health", None, 120, 5, 5.0, 300.0),
    "prometheus": ("Prometheus", "MONITORING", 9090, "/-/healthy", None, 30, 5, 10.0, 120.0),
    "grafana": ("Grafana", "MONITORING", 3002, "/api/health", None, 30, 5, 10.0, 120.0),
    "alertmanager": ("Alertmanager", "MONITORING", 9093, "/-/healthy", None, 15, 5, 10.0, 120.0),
    "loki": ("Loki", "MONITORING", 3100, "/ready", None, 30, 5, 10.0, 120.0),
    "pyroscope": ("Pyroscope", "MONITORING", 4040, "/ready", None, 30, 5, 10.0, 120.0),
    "alloy": ("Grafana Alloy", "MONITORING", 12345, "/-/ready", None, 30, 5, 10.0, 120.0),
    "tempo": ("Tempo", "MONITORING", 3200, "/ready", None, 15, 5, 10.0, 120.0),
    "redis-exporter": ("Redis Exporter", "MONITORING", 9121, "/metrics", None, 15, 5, 10.0, 120.0),
    "json-exporter": ("JSON Exporter", "MONITORING", 7979, "/metrics", None, 15, 5, 10.0, 120.0),
    "blackbox-exporter": (
        "Blackbox Exporter",
        "MONITORING",
        9115,
        "/metrics",
        None,
        15,
        5,
        10.0,
        120.0,
    ),
    "node-exporter": ("Node Exporter", "MONITORING", 9100, "/metrics", None, 15, 5, 10.0, 120.0),
    "cadvisor": ("cAdvisor", "MONITORING", 8082, "/healthz", None, 15, 5, 10.0, 120.0),
    "dcgm-exporter": ("DCGM Exporter", "MONITORING", 9400, "/metrics", None, 30, 5, 10.0, 120.0),
}

# Every settings port distinct from every .env default, so a swallowed or
# bypassed settings object always shows up as a port mismatch.
ALL_PORTS = {
    "postgres_port": 15432,
    "redis_port": 16379,
    "backend_port": 18000,
    "go2rtc_port": 19841,
    "ai_gateway_port": 18090,
    "nemotron_port": 18091,
    "vllm_port": 18097,
    "prometheus_port": 19090,
    "grafana_port": 13002,
    "redis_exporter_port": 19121,
    "json_exporter_port": 17979,
    "alertmanager_port": 19093,
    "blackbox_exporter_port": 19115,
    "tempo_port": 13200,
    "loki_port": 13100,
    "pyroscope_port": 14040,
    "alloy_port": 12346,
    "node_exporter_port": 19100,
    "cadvisor_port": 18082,
    "dcgm_exporter_port": 19400,
    "frontend_port": 18080,
}
_KEY_TO_PORT_ATTR = {  # config key -> settings attribute feeding its port
    "postgres": "postgres_port",
    "redis": "redis_port",
    "backend": "backend_port",
    "go2rtc": "go2rtc_port",
    "frontend": "frontend_port",
    "ai-gateway": "ai_gateway_port",
    "ai-llm": "nemotron_port",
    "ai-llm-vllm": "vllm_port",
    "prometheus": "prometheus_port",
    "grafana": "grafana_port",
    "alertmanager": "alertmanager_port",
    "loki": "loki_port",
    "pyroscope": "pyroscope_port",
    "alloy": "alloy_port",
    "tempo": "tempo_port",
    "redis-exporter": "redis_exporter_port",
    "json-exporter": "json_exporter_port",
    "blackbox-exporter": "blackbox_exporter_port",
    "node-exporter": "node_exporter_port",
    "cadvisor": "cadvisor_port",
    "dcgm-exporter": "dcgm_exporter_port",
}


class TestBuildServiceConfigs:
    """Kill tests for the settings-driven config builder (WP4.4 T1/T2/T3)."""

    def test_build_service_configs_full_table_without_settings(self) -> None:
        """Every service built with settings=None must match the .env-default table."""
        configs = build_service_configs(None)
        assert set(configs) == set(EXPECTED_BUILDER_TABLE)
        for name, exp in EXPECTED_BUILDER_TABLE.items():
            cfg = configs[name]
            display, cat, port, endpoint, cmd, grace, maxf, base, mx = exp
            assert cfg.display_name == display, name
            assert cfg.category.value.upper() == cat, name
            assert cfg.port == port, name
            assert cfg.health_endpoint == endpoint, name
            assert cfg.health_cmd == cmd, name
            assert cfg.startup_grace_period == grace, name
            assert cfg.max_failures == maxf, name
            assert cfg.restart_backoff_base == base, name
            assert cfg.restart_backoff_max == mx, name

    def test_build_service_configs_uses_ports_from_settings(self) -> None:
        """With settings supplied, every port must come from settings, not .env defaults."""
        settings = SimpleNamespace(monitoring_enabled=True, **ALL_PORTS)
        configs = build_service_configs(settings)
        for key, attr in _KEY_TO_PORT_ATTR.items():
            assert configs[key].port == ALL_PORTS[attr], f"{key} must use settings.{attr}"

    def test_build_service_configs_include_monitoring_flag(self) -> None:
        """include_monitoring=False must exclude exactly the MONITORING entries."""
        with_mon = build_service_configs(None, include_monitoring=True)
        without_mon = build_service_configs(None, include_monitoring=False)
        monitoring_keys = {k for k, v in EXPECTED_BUILDER_TABLE.items() if v[1] == "MONITORING"}
        assert monitoring_keys <= set(with_mon)
        assert not (monitoring_keys & set(without_mon))
        assert set(with_mon) - monitoring_keys == set(without_mon)


class TestDiscoverySettingsWiring:
    """__init__ branches no test had ever executed (WP4.4 T3/T4)."""

    def test_init_with_settings_uses_configured_ports_and_monitoring_flag(self) -> None:
        """Settings branch: ports flow from settings; monitoring_enabled drives inclusion."""
        client = MagicMock()
        client.list_containers = AsyncMock(return_value=[])
        settings = SimpleNamespace(monitoring_enabled=True, **ALL_PORTS)
        discovery = ContainerDiscoveryService(client, settings)
        assert discovery.get_config("postgres").port == 15432
        assert discovery.get_config("prometheus") is not None

        settings_off = SimpleNamespace(monitoring_enabled=False, **ALL_PORTS)
        discovery_off = ContainerDiscoveryService(client, settings_off)
        assert discovery_off.get_config("prometheus") is None
        assert discovery_off.get_config("postgres").port == 15432

    def test_init_with_compose_file_uses_parsed_configs(self, tmp_path, monkeypatch) -> None:
        """compose_file branch: parsed configs win; the parser must receive the compose path."""
        from backend.services.compose_parser import ComposeParser

        compose_path = tmp_path / "docker-compose.yml"
        sentinel = ServiceConfig(
            display_name="Custom Compose Service",
            category=ServiceCategory.AI,
            port=45999,
            health_endpoint="/health",
        )
        seen_paths: list = []

        def spy_parse(self, path):
            seen_paths.append(path)
            return {"custom-svc": sentinel}

        monkeypatch.setattr(ComposeParser, "parse_file", spy_parse)
        client = MagicMock()
        client.list_containers = AsyncMock(return_value=[])
        discovery = ContainerDiscoveryService(client, None, compose_file=compose_path)
        # __init__ must forward the compose FILE PATH as the parser's first arg —
        # a dropped/shifted argument (settings or flag in its place) must fail here.
        assert seen_paths == [compose_path]
        assert discovery.get_config("custom-svc") is sentinel
        assert discovery.get_config("postgres") is None  # parsed set replaces hardcoded table

    def test_init_compose_branch_honors_monitoring_disabled(self, tmp_path, monkeypatch) -> None:
        """compose_file branch + monitoring_enabled=False: parsed MONITORING configs are filtered."""
        from backend.services.compose_parser import ComposeParser

        app_cfg = ServiceConfig(display_name="App", category=ServiceCategory.AI, port=45999)
        mon_cfg = ServiceConfig(display_name="Mon", category=ServiceCategory.MONITORING, port=45998)
        monkeypatch.setattr(
            ComposeParser, "parse_file", lambda _self, _path: {"app": app_cfg, "mon": mon_cfg}
        )
        client = MagicMock()
        client.list_containers = AsyncMock(return_value=[])
        settings = SimpleNamespace(monitoring_enabled=False, **ALL_PORTS)
        discovery = ContainerDiscoveryService(
            client, settings, compose_file=tmp_path / "compose.yml"
        )
        assert discovery.get_config("app") is app_cfg
        assert discovery.get_config("mon") is None  # monitoring flag must reach the compose builder


class TestBuildConfigsFromCompose:
    """Pass-through and fallback semantics of the compose builder (WP4.4 T4)."""

    def test_missing_compose_file_falls_back_to_settings_ports(self, tmp_path) -> None:
        """FileNotFoundError must fall back to build_service_configs WITH settings forwarded."""
        missing = tmp_path / "nope-compose.yml"
        settings = SimpleNamespace(monitoring_enabled=True, **ALL_PORTS)
        configs = build_configs_from_compose(missing, settings)
        assert configs["postgres"].port == 15432  # fallback must keep settings, not default ports

    def test_parse_success_passes_configs_through(self, tmp_path, monkeypatch) -> None:
        """A successful parse result must be returned verbatim, not swapped for fallback."""
        from backend.services.compose_parser import ComposeParser

        sentinel = ServiceConfig(display_name="S", category=ServiceCategory.AI, port=1)
        monkeypatch.setattr(
            ComposeParser, "parse_file", lambda _self, _path: {"only-svc": sentinel}
        )
        configs = build_configs_from_compose(tmp_path / "any.yml")
        assert configs == {"only-svc": sentinel}

    def test_parse_error_falls_back(self, tmp_path, monkeypatch) -> None:
        """Any parse exception must fall back to hardcoded configs (postgres present, default port)."""
        from backend.services.compose_parser import ComposeParser

        def boom(self, path):
            raise ValueError("bad yaml")

        monkeypatch.setattr(ComposeParser, "parse_file", boom)
        configs = build_configs_from_compose(tmp_path / "broken.yml")
        assert "postgres" in configs and configs["postgres"].port == 5432


class TestDiscoveryImageStringEdgeCases:
    """Exact untagged-image string + health_cmd passthrough (WP4.4 T5)."""

    @pytest.mark.asyncio
    async def test_untagged_container_image_string_uses_first_12_id_chars(
        self, mock_docker_client: MagicMock
    ) -> None:
        """Untagged containers must get '<untagged:{id[:12]}>' with the REAL id and health_cmd."""
        long_id = "0123456789abcdef0123456789abcdef"  # 32 hex chars, like a real docker id
        container = create_mock_container("security-postgres-1", container_id=long_id)
        container.image.tags = []
        mock_docker_client.list_containers = AsyncMock(return_value=[container])

        discovery = ContainerDiscoveryService(mock_docker_client)
        discovered = await discovery.discover_all()

        assert len(discovered) == 1
        assert discovered[0].image == f"<untagged:{long_id[:12]}>"
        # postgres uses an exec health command — it must survive the ManagedService mapping
        assert discovered[0].health_cmd == "pg_isready -U security"


class TestWP44DraftedGaps:
    """Real-gap kill-tests from the 52-survivor triage dossier (WP4.4).

    Every test here targets mutants that survived BECAUSE MagicMock fabricates
    every attribute — the getattr-default branches had zero executions. Plain
    SimpleNamespace containers are load-bearing, do not "simplify" to mocks.
    """

    @pytest.mark.parametrize("monitoring_enabled", [True, False])
    def test_compose_fallback_honors_monitoring_flag_and_settings(
        self, tmp_path, monitoring_enabled: bool
    ) -> None:
        """Compose-fallback must forward BOTH settings ports and the flag.

        Kills __init__ mutants that drop the settings arg (ports silently
        revert to defaults) or the include_monitoring arg / pass it as None
        (falsy -> prometheus wrongly excluded even when monitoring is on).
        """
        missing = tmp_path / "nope-compose.yml"
        settings = SimpleNamespace(monitoring_enabled=monitoring_enabled, **ALL_PORTS)
        configs = build_configs_from_compose(missing, settings, monitoring_enabled)
        assert configs["postgres"].port == 15432  # settings leg of the fallback
        assert ("prometheus" in configs) is monitoring_enabled
        # the service constructor must route through the same fallback
        svc = ContainerDiscoveryService(MagicMock(), settings=settings, compose_file=missing)
        assert ("prometheus" in svc._configs) is monitoring_enabled

    def test_match_container_name_length_beats_lexicographic_order(
        self, mock_docker_client: MagicMock
    ) -> None:
        """Length-priority must not silently become reverse-lexicographic.

        The older prefers-longer test used a PREFIX pair (redis/redis-exporter)
        where both sorts agree; this container matches 'postgres' (8) and
        'redis' (5) as bare substrings — plain reverse() picks 'redis'.
        """
        service = ContainerDiscoveryService(mock_docker_client)
        assert service.match_container_name("prod-redis-postgres-bridge-1") == "postgres"

    @pytest.mark.asyncio
    async def test_discover_image_object_without_tags_attribute_still_resolves(
        self, mock_docker_client: MagicMock
    ) -> None:
        """An image object without .tags must fall back to [] -> <untagged:...>.

        Kills the getattr-default-deleted mutant, which raises AttributeError
        out of discover_all. MagicMock always fabricates .tags — never let it
        stand in here.
        """
        container = SimpleNamespace(
            name="security-postgres-1", id="pg-abcdef123456", image=SimpleNamespace()
        )
        mock_docker_client.list_containers = AsyncMock(return_value=[container])

        discovery = ContainerDiscoveryService(mock_docker_client)
        discovered = await discovery.discover_all()

        assert discovered[0].image == "<untagged:pg-abcdef123>"

    @pytest.mark.asyncio
    async def test_container_without_image_falls_back_to_unknown(
        self, mock_docker_client: MagicMock
    ) -> None:
        """A container lacking .image must resolve image='<unknown>', not crash."""
        bare = SimpleNamespace(name="security-postgres-1", id="pg-abcdef123456")
        mock_docker_client.list_containers = AsyncMock(return_value=[bare])

        discovery = ContainerDiscoveryService(mock_docker_client)
        discovered = await discovery.discover_all()

        assert discovered[0].image == "<unknown>"
        assert discovered[0].container_id == "pg-abcdef123456"

    def test_idless_container_hits_defensive_id_defaults(
        self, mock_docker_client: MagicMock
    ) -> None:
        """An id-less container must get container_id='' and '<untagged:unknown>'.

        Direct _create_managed_service call BY DESIGN: discover_all's own
        observability extras read container.id, so an id-less container is not
        a discover_all-reachable state — these getattr defaults are only
        reachable through the mapping helper itself.
        """
        discovery = ContainerDiscoveryService(mock_docker_client)
        cfg = INFRASTRUCTURE_CONFIGS["postgres"]

        no_id = SimpleNamespace(name="security-postgres-1", image=SimpleNamespace(tags=[]))
        svc = discovery._create_managed_service(no_id, "postgres", cfg)
        assert svc.container_id == ""
        assert svc.image == "<untagged:unknown>"

    @pytest.mark.asyncio
    async def test_discover_all_debug_extra_dict_contract(
        self, mock_docker_client: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The debug observability payload is part of the shipped contract.

        Kills the D1 log-payload family: message -> None mutants render 'None'
        (fail the name-substring filter) and UPPER/XX-wrapped/removed extra
        keys fail the exact-value asserts.
        """
        container = SimpleNamespace(
            name="security-postgres-1", id="pg-abcdef123456", image=SimpleNamespace(tags=["pg:17"])
        )
        mock_docker_client.list_containers = AsyncMock(return_value=[container])

        discovery = ContainerDiscoveryService(mock_docker_client)
        with caplog.at_level("DEBUG", logger="backend.services.container_discovery"):
            await discovery.discover_all()

        rec = next(r for r in caplog.records if "security-postgres-1" in r.getMessage())
        assert rec.container_name == "security-postgres-1"
        assert rec.service_name == "postgres"
        assert rec.container_id == "pg-abcdef123456"
        assert rec.category == "infrastructure"
