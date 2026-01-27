"""Unit tests for ContainerDiscoveryService.

Tests for the container discovery service that finds Docker containers by name
pattern and creates ManagedService objects with proper configuration.
"""

from __future__ import annotations

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
        expected_services = {
            "ai-yolo26": ("YOLO26", 8090, 60),
            "ai-llm": ("Nemotron", 8091, 120),
            "ai-florence": ("Florence-2", 8092, 60),
            "ai-clip": ("CLIP", 8093, 60),
            "ai-enrichment": ("Enrichment", 8094, 180),
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
        assert config.port == 3000
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
    async def test_discover_all_finds_ai_detector_container(
        self, mock_docker_client: MagicMock
    ) -> None:
        """Test discovery finds AI detector container matching pattern."""
        mock_detector = create_mock_container(
            name="security-ai-yolo26-1",
            container_id="det123",
            image_tags=["ghcr.io/test/yolo26:latest"],
        )
        mock_docker_client.list_containers = AsyncMock(return_value=[mock_detector])

        service = ContainerDiscoveryService(mock_docker_client)
        discovered = await service.discover_all()

        assert len(discovered) == 1
        assert discovered[0].name == "ai-yolo26"
        assert discovered[0].display_name == "YOLO26"
        assert discovered[0].container_id == "det123"
        assert discovered[0].port == 8090
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
            create_mock_container("security-ai-yolo26-1", "det123"),
            create_mock_container("security-prometheus-1", "prom123"),
        ]
        mock_docker_client.list_containers = AsyncMock(return_value=containers)

        service = ContainerDiscoveryService(mock_docker_client)
        discovered = await service.discover_all()

        assert len(discovered) == 4
        names = {s.name for s in discovered}
        assert names == {"postgres", "redis", "ai-yolo26", "prometheus"}

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
            create_mock_container("security-ai-yolo26-1", "det123"),
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
            create_mock_container("security-ai-yolo26-1", "det123"),
            create_mock_container("security-ai-llm-1", "llm123"),
            create_mock_container("security-ai-florence-1", "flor123"),
        ]
        mock_docker_client.list_containers = AsyncMock(return_value=containers)

        service = ContainerDiscoveryService(mock_docker_client)
        discovered = await service.discover_by_category(ServiceCategory.AI)

        assert len(discovered) == 3
        names = {s.name for s in discovered}
        assert names == {"ai-yolo26", "ai-llm", "ai-florence"}
        for s in discovered:
            assert s.category == ServiceCategory.AI

    @pytest.mark.asyncio
    async def test_discover_by_category_monitoring(self, mock_docker_client: MagicMock) -> None:
        """Test discovery filtering by monitoring category."""
        containers = [
            create_mock_container("security-prometheus-1", "prom123"),
            create_mock_container("security-grafana-1", "graf123"),
            create_mock_container("security-redis-exporter-1", "rexp123"),
            create_mock_container("security-ai-yolo26-1", "det123"),
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

        config = service.get_config("ai-yolo26")
        assert config is not None
        assert config.display_name == "YOLO26"
        assert config.port == 8090

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
        assert service.match_container_name("ai-yolo26") == "ai-yolo26"

        # Prefix match
        assert service.match_container_name("security-postgres-1") == "postgres"
        assert service.match_container_name("myapp-ai-yolo26-prod") == "ai-yolo26"

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
        assert service.match_container_name("backend") is None

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
        ai_config = AI_CONFIGS["ai-yolo26"]

        assert infra_config.restart_backoff_base < ai_config.restart_backoff_base
        assert infra_config.restart_backoff_max < ai_config.restart_backoff_max

    def test_ai_backoff_less_than_monitoring(self) -> None:
        """Test that AI base backoff is less than monitoring (more aggressive base).

        Note: AI uses default max backoff (300.0) which is higher than monitoring's
        explicit max (120.0). This is intentional - AI services have aggressive
        base backoff but larger max to avoid overwhelming GPU resources.
        """
        ai_config = AI_CONFIGS["ai-yolo26"]
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
        ai_base = AI_CONFIGS["ai-yolo26"].restart_backoff_base
        mon_base = MONITORING_CONFIGS["prometheus"].restart_backoff_base

        # Base backoff: infra(2) < ai(5) < mon(10) - more aggressive for infrastructure
        assert infra_base < ai_base < mon_base, (
            f"Expected backoff hierarchy infra({infra_base}) < ai({ai_base}) < mon({mon_base})"
        )

        infra_max = INFRASTRUCTURE_CONFIGS["postgres"].restart_backoff_max
        ai_max = AI_CONFIGS["ai-yolo26"].restart_backoff_max
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
            create_mock_container("security-ai-yolo26-1", "det123"),
            create_mock_container("security-prometheus-1", "prom123"),
        ]
        mock_docker_client.list_containers = AsyncMock(return_value=containers)

        service = ContainerDiscoveryService(mock_docker_client)
        discovered = await service.discover_all()

        # Find each service
        postgres = next(s for s in discovered if s.name == "postgres")
        detector = next(s for s in discovered if s.name == "ai-yolo26")
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
