"""Unit tests for ContainerOrchestrator.

Tests cover:
- Initialization with required dependencies
- start() when disabled in settings does nothing
- start() discovers containers and starts health monitor
- stop() stops health monitor and persists state
- get_all_services() returns all registered services
- get_service() returns service or None
- restart_service() calls lifecycle manager
- enable_service() enables disabled service
- disable_service() disables service
- start_service() starts stopped service
- Integration with health monitor callback
- WebSocket broadcasting on status changes
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.schemas.services import ContainerServiceStatus, ServiceCategory
from backend.services.container_discovery import ManagedService as DiscoveredService
from backend.services.container_orchestrator import (
    ContainerOrchestrator,
    create_service_status_event,
)
from backend.services.service_registry import ManagedService

# =============================================================================
# Test Configuration and Fixtures
# =============================================================================


@pytest.fixture
def mock_docker_client() -> AsyncMock:
    """Create a mock DockerClient."""
    client = AsyncMock()
    client.connect = AsyncMock(return_value=True)
    client.close = AsyncMock()
    client.stop_container = AsyncMock(return_value=True)
    client.start_container = AsyncMock(return_value=True)
    client.restart_container = AsyncMock(return_value=True)
    client.get_container = AsyncMock(return_value=MagicMock(status="running"))
    client.list_containers = AsyncMock(return_value=[])
    return client


@pytest.fixture
def mock_redis_client() -> AsyncMock:
    """Create a mock RedisClient."""
    client = AsyncMock()
    client.set = AsyncMock()
    client.get = AsyncMock(return_value=None)
    client.delete = AsyncMock()
    return client


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock OrchestratorSettings."""
    settings = MagicMock()
    settings.enabled = True
    settings.docker_host = None
    settings.health_check_interval = 30
    settings.health_check_timeout = 5
    settings.startup_grace_period = 60
    settings.max_consecutive_failures = 5
    settings.restart_backoff_base = 5.0
    settings.restart_backoff_max = 300.0
    return settings


@pytest.fixture
def mock_broadcast_fn() -> AsyncMock:
    """Create a mock broadcast function."""
    return AsyncMock(return_value=3)


@pytest.fixture
def discovered_service() -> DiscoveredService:
    """Create a discovered service fixture."""
    return DiscoveredService(
        name="ai-yolo26",
        display_name="YOLO26",
        container_id="abc123def456",
        image="ghcr.io/example/yolo26:latest",
        port=8095,
        category=ServiceCategory.AI,
        health_endpoint="/health",
        max_failures=5,
        restart_backoff_base=5.0,
        restart_backoff_max=300.0,
        startup_grace_period=60,
    )


@pytest.fixture
def managed_service() -> ManagedService:
    """Create a managed service fixture."""
    return ManagedService(
        name="ai-yolo26",
        display_name="YOLO26",
        container_id="abc123def456",
        image="ghcr.io/example/yolo26:latest",
        port=8095,
        category=ServiceCategory.AI,
        health_endpoint="/health",
        health_cmd=None,
        status=ContainerServiceStatus.RUNNING,
        enabled=True,
        failure_count=0,
        restart_count=0,
        max_failures=5,
        restart_backoff_base=5.0,
        restart_backoff_max=300.0,
        startup_grace_period=60,
    )


@pytest.fixture
def orchestrator(
    mock_docker_client: AsyncMock,
    mock_redis_client: AsyncMock,
    mock_settings: MagicMock,
    mock_broadcast_fn: AsyncMock,
) -> ContainerOrchestrator:
    """Create a ContainerOrchestrator with mocked dependencies."""
    return ContainerOrchestrator(
        docker_client=mock_docker_client,
        redis_client=mock_redis_client,
        settings=mock_settings,
        broadcast_fn=mock_broadcast_fn,
    )


# =============================================================================
# create_service_status_event() Tests
# =============================================================================


class TestCreateServiceStatusEvent:
    """Tests for the create_service_status_event function."""

    def test_creates_valid_event(self, managed_service: ManagedService) -> None:
        """Test creating a valid service status event."""
        event = create_service_status_event(managed_service, "Test message")

        assert event["type"] == "service_status"
        assert event["data"]["name"] == "ai-yolo26"
        assert event["data"]["display_name"] == "YOLO26"
        assert event["message"] == "Test message"

    def test_includes_container_id_truncated(self, managed_service: ManagedService) -> None:
        """Test container_id is truncated to 12 characters."""
        event = create_service_status_event(managed_service, "Test")

        assert event["data"]["container_id"] == "abc123def456"[:12]

    def test_includes_none_container_id(self, managed_service: ManagedService) -> None:
        """Test handles None container_id."""
        managed_service.container_id = None
        event = create_service_status_event(managed_service, "Test")

        assert event["data"]["container_id"] is None

    def test_calculates_uptime_when_running(self, managed_service: ManagedService) -> None:
        """Test uptime is calculated when service is running."""
        managed_service.status = ContainerServiceStatus.RUNNING
        managed_service.last_restart_at = datetime.now(UTC)
        event = create_service_status_event(managed_service, "Test")

        # Uptime should be close to 0 (just restarted)
        assert event["data"]["uptime_seconds"] is not None
        assert event["data"]["uptime_seconds"] >= 0

    def test_no_uptime_when_not_running(self, managed_service: ManagedService) -> None:
        """Test uptime is None when service is not running."""
        managed_service.status = ContainerServiceStatus.STOPPED
        event = create_service_status_event(managed_service, "Test")

        assert event["data"]["uptime_seconds"] is None


# =============================================================================
# ContainerOrchestrator.__init__() Tests
# =============================================================================


class TestContainerOrchestratorInit:
    """Tests for ContainerOrchestrator initialization."""

    def test_init_with_required_dependencies(
        self,
        mock_docker_client: AsyncMock,
        mock_redis_client: AsyncMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test initialization with required dependencies."""
        orchestrator = ContainerOrchestrator(
            docker_client=mock_docker_client,
            redis_client=mock_redis_client,
            settings=mock_settings,
        )

        assert orchestrator._docker_client is mock_docker_client
        assert orchestrator._redis_client is mock_redis_client
        assert orchestrator._settings is mock_settings
        assert orchestrator._broadcast_fn is None  # None when not provided

    def test_init_with_broadcast_fn(
        self,
        mock_docker_client: AsyncMock,
        mock_redis_client: AsyncMock,
        mock_settings: MagicMock,
        mock_broadcast_fn: AsyncMock,
    ) -> None:
        """Test initialization with broadcast function."""
        orchestrator = ContainerOrchestrator(
            docker_client=mock_docker_client,
            redis_client=mock_redis_client,
            settings=mock_settings,
            broadcast_fn=mock_broadcast_fn,
        )

        assert orchestrator._broadcast_fn is mock_broadcast_fn

    def test_init_creates_registry(
        self,
        mock_docker_client: AsyncMock,
        mock_redis_client: AsyncMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test initialization creates service registry."""
        orchestrator = ContainerOrchestrator(
            docker_client=mock_docker_client,
            redis_client=mock_redis_client,
            settings=mock_settings,
        )

        assert orchestrator._registry is not None

    def test_is_running_initially_false(
        self,
        mock_docker_client: AsyncMock,
        mock_redis_client: AsyncMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test is_running is False initially."""
        orchestrator = ContainerOrchestrator(
            docker_client=mock_docker_client,
            redis_client=mock_redis_client,
            settings=mock_settings,
        )

        assert orchestrator.is_running is False


# =============================================================================
# ContainerOrchestrator.start() Tests
# =============================================================================


class TestContainerOrchestratorStart:
    """Tests for ContainerOrchestrator.start method."""

    @pytest.mark.asyncio
    async def test_start_when_disabled_does_nothing(
        self, orchestrator: ContainerOrchestrator, mock_settings: MagicMock
    ) -> None:
        """Test start() does nothing when disabled in settings."""
        mock_settings.enabled = False

        await orchestrator.start()

        assert orchestrator.is_running is False
        orchestrator._docker_client.connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_verifies_docker_connection(
        self, orchestrator: ContainerOrchestrator, mock_docker_client: AsyncMock
    ) -> None:
        """Test start() verifies Docker connection."""
        mock_docker_client.connect.return_value = True

        with patch.object(orchestrator._discovery_service, "discover_all", return_value=[]):
            await orchestrator.start()

        mock_docker_client.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_fails_gracefully_when_docker_unavailable(
        self, orchestrator: ContainerOrchestrator, mock_docker_client: AsyncMock
    ) -> None:
        """Test start() handles Docker connection failure gracefully."""
        mock_docker_client.connect.return_value = False

        await orchestrator.start()

        assert orchestrator.is_running is False

    @pytest.mark.asyncio
    async def test_start_discovers_containers(
        self,
        orchestrator: ContainerOrchestrator,
        mock_docker_client: AsyncMock,
        discovered_service: DiscoveredService,
    ) -> None:
        """Test start() discovers containers."""
        mock_docker_client.connect.return_value = True

        with patch.object(
            orchestrator._discovery_service,
            "discover_all",
            return_value=[discovered_service],
        ):
            await orchestrator.start()

        assert len(orchestrator.get_all_services()) == 1

    @pytest.mark.asyncio
    async def test_start_loads_redis_state(
        self, orchestrator: ContainerOrchestrator, mock_docker_client: AsyncMock
    ) -> None:
        """Test start() loads state from Redis."""
        mock_docker_client.connect.return_value = True

        with (
            patch.object(orchestrator._discovery_service, "discover_all", return_value=[]),
            patch.object(
                orchestrator._registry, "load_all_state", new_callable=AsyncMock
            ) as mock_load,
        ):
            await orchestrator.start()
            mock_load.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_creates_health_monitor(
        self,
        orchestrator: ContainerOrchestrator,
        mock_docker_client: AsyncMock,
        discovered_service: DiscoveredService,
    ) -> None:
        """Test start() creates and starts health monitor."""
        mock_docker_client.connect.return_value = True

        with patch.object(
            orchestrator._discovery_service,
            "discover_all",
            return_value=[discovered_service],
        ):
            await orchestrator.start()

        assert orchestrator._health_monitor is not None

    @pytest.mark.asyncio
    async def test_start_sets_running_true(
        self, orchestrator: ContainerOrchestrator, mock_docker_client: AsyncMock
    ) -> None:
        """Test start() sets is_running to True."""
        mock_docker_client.connect.return_value = True

        with patch.object(orchestrator._discovery_service, "discover_all", return_value=[]):
            await orchestrator.start()

        assert orchestrator.is_running is True

    @pytest.mark.asyncio
    async def test_start_is_idempotent(
        self, orchestrator: ContainerOrchestrator, mock_docker_client: AsyncMock
    ) -> None:
        """Test start() is idempotent."""
        mock_docker_client.connect.return_value = True

        with patch.object(orchestrator._discovery_service, "discover_all", return_value=[]):
            await orchestrator.start()
            await orchestrator.start()  # Second call should be no-op

        assert mock_docker_client.connect.call_count == 1


# =============================================================================
# ContainerOrchestrator.stop() Tests
# =============================================================================


class TestContainerOrchestratorStop:
    """Tests for ContainerOrchestrator.stop method."""

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, orchestrator: ContainerOrchestrator) -> None:
        """Test stop() when not running does nothing."""
        assert orchestrator.is_running is False

        await orchestrator.stop()  # Should not raise

    @pytest.mark.asyncio
    async def test_stop_stops_health_monitor(
        self, orchestrator: ContainerOrchestrator, mock_docker_client: AsyncMock
    ) -> None:
        """Test stop() stops the health monitor."""
        mock_docker_client.connect.return_value = True

        with patch.object(orchestrator._discovery_service, "discover_all", return_value=[]):
            await orchestrator.start()

        health_monitor = orchestrator._health_monitor
        assert health_monitor is not None

        await orchestrator.stop()

        assert orchestrator._health_monitor is None

    @pytest.mark.asyncio
    async def test_stop_persists_final_state(
        self,
        orchestrator: ContainerOrchestrator,
        mock_docker_client: AsyncMock,
        discovered_service: DiscoveredService,
    ) -> None:
        """Test stop() persists final state for all services."""
        mock_docker_client.connect.return_value = True

        with patch.object(
            orchestrator._discovery_service,
            "discover_all",
            return_value=[discovered_service],
        ):
            await orchestrator.start()

        with patch.object(
            orchestrator._registry, "persist_state", new_callable=AsyncMock
        ) as mock_persist:
            await orchestrator.stop()
            mock_persist.assert_called()

    @pytest.mark.asyncio
    async def test_stop_sets_running_false(
        self, orchestrator: ContainerOrchestrator, mock_docker_client: AsyncMock
    ) -> None:
        """Test stop() sets is_running to False."""
        mock_docker_client.connect.return_value = True

        with patch.object(orchestrator._discovery_service, "discover_all", return_value=[]):
            await orchestrator.start()

        await orchestrator.stop()

        assert orchestrator.is_running is False


# =============================================================================
# ContainerOrchestrator.get_all_services() Tests
# =============================================================================


class TestGetAllServices:
    """Tests for ContainerOrchestrator.get_all_services method."""

    @pytest.mark.asyncio
    async def test_get_all_services_empty(self, orchestrator: ContainerOrchestrator) -> None:
        """Test get_all_services returns empty list when no services."""
        services = orchestrator.get_all_services()
        assert services == []

    @pytest.mark.asyncio
    async def test_get_all_services_returns_registered(
        self,
        orchestrator: ContainerOrchestrator,
        mock_docker_client: AsyncMock,
        discovered_service: DiscoveredService,
    ) -> None:
        """Test get_all_services returns all registered services."""
        mock_docker_client.connect.return_value = True

        with patch.object(
            orchestrator._discovery_service,
            "discover_all",
            return_value=[discovered_service],
        ):
            await orchestrator.start()

        services = orchestrator.get_all_services()
        assert len(services) == 1
        assert services[0].name == "ai-yolo26"


# =============================================================================
# ContainerOrchestrator.get_service() Tests
# =============================================================================


class TestGetService:
    """Tests for ContainerOrchestrator.get_service method."""

    @pytest.mark.asyncio
    async def test_get_service_not_found(self, orchestrator: ContainerOrchestrator) -> None:
        """Test get_service returns None for unknown service."""
        service = orchestrator.get_service("unknown")
        assert service is None

    @pytest.mark.asyncio
    async def test_get_service_returns_service(
        self,
        orchestrator: ContainerOrchestrator,
        mock_docker_client: AsyncMock,
        discovered_service: DiscoveredService,
    ) -> None:
        """Test get_service returns the service by name."""
        mock_docker_client.connect.return_value = True

        with patch.object(
            orchestrator._discovery_service,
            "discover_all",
            return_value=[discovered_service],
        ):
            await orchestrator.start()

        service = orchestrator.get_service("ai-yolo26")
        assert service is not None
        assert service.name == "ai-yolo26"


# =============================================================================
# ContainerOrchestrator.restart_service() Tests
# =============================================================================


class TestRestartService:
    """Tests for ContainerOrchestrator.restart_service method."""

    @pytest.mark.asyncio
    async def test_restart_service_unknown(self, orchestrator: ContainerOrchestrator) -> None:
        """Test restart_service returns False for unknown service."""
        result = await orchestrator.restart_service("unknown")
        assert result is False

    @pytest.mark.asyncio
    async def test_restart_service_no_container_id(
        self, orchestrator: ContainerOrchestrator, managed_service: ManagedService
    ) -> None:
        """Test restart_service returns False when no container_id."""
        managed_service.container_id = None
        orchestrator._registry.register(managed_service)

        result = await orchestrator.restart_service("ai-yolo26")
        assert result is False

    @pytest.mark.asyncio
    async def test_restart_service_broadcasts_status(
        self,
        orchestrator: ContainerOrchestrator,
        mock_docker_client: AsyncMock,
        mock_broadcast_fn: AsyncMock,
        managed_service: ManagedService,
    ) -> None:
        """Test restart_service broadcasts status changes."""
        orchestrator._registry.register(managed_service)

        await orchestrator.restart_service("ai-yolo26")

        # Should have broadcast at least "Manual restart initiated"
        assert mock_broadcast_fn.call_count >= 1


# =============================================================================
# ContainerOrchestrator.enable_service() Tests
# =============================================================================


class TestEnableService:
    """Tests for ContainerOrchestrator.enable_service method."""

    @pytest.mark.asyncio
    async def test_enable_service_unknown(self, orchestrator: ContainerOrchestrator) -> None:
        """Test enable_service returns False for unknown service."""
        result = await orchestrator.enable_service("unknown")
        assert result is False

    @pytest.mark.asyncio
    async def test_enable_service_enables_disabled(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_docker_client: AsyncMock,
    ) -> None:
        """Test enable_service enables a disabled service."""
        managed_service.enabled = False
        managed_service.status = ContainerServiceStatus.DISABLED
        orchestrator._registry.register(managed_service)

        # Create lifecycle manager so enable_service can delegate to it
        mock_docker_client.connect.return_value = True
        with patch.object(orchestrator._discovery_service, "discover_all", return_value=[]):
            await orchestrator.start()

        result = await orchestrator.enable_service("ai-yolo26")

        assert result is True
        service = orchestrator.get_service("ai-yolo26")
        assert service is not None
        assert service.enabled is True
        assert service.status == ContainerServiceStatus.STOPPED

    @pytest.mark.asyncio
    async def test_enable_service_resets_failures(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_docker_client: AsyncMock,
    ) -> None:
        """Test enable_service resets failure count."""
        managed_service.enabled = False
        managed_service.failure_count = 5
        orchestrator._registry.register(managed_service)

        # Create lifecycle manager so enable_service can delegate to it
        mock_docker_client.connect.return_value = True
        with patch.object(orchestrator._discovery_service, "discover_all", return_value=[]):
            await orchestrator.start()

        await orchestrator.enable_service("ai-yolo26")

        service = orchestrator.get_service("ai-yolo26")
        assert service is not None
        assert service.failure_count == 0

    @pytest.mark.asyncio
    async def test_enable_service_broadcasts_status(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_broadcast_fn: AsyncMock,
        mock_docker_client: AsyncMock,
    ) -> None:
        """Test enable_service broadcasts status change."""
        managed_service.enabled = False
        orchestrator._registry.register(managed_service)

        # Create lifecycle manager so enable_service can delegate to it
        mock_docker_client.connect.return_value = True
        with patch.object(orchestrator._discovery_service, "discover_all", return_value=[]):
            await orchestrator.start()

        await orchestrator.enable_service("ai-yolo26")

        mock_broadcast_fn.assert_called()


# =============================================================================
# ContainerOrchestrator.disable_service() Tests
# =============================================================================


class TestDisableService:
    """Tests for ContainerOrchestrator.disable_service method."""

    @pytest.mark.asyncio
    async def test_disable_service_unknown(self, orchestrator: ContainerOrchestrator) -> None:
        """Test disable_service returns False for unknown service."""
        result = await orchestrator.disable_service("unknown")
        assert result is False

    @pytest.mark.asyncio
    async def test_disable_service_disables_enabled(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_docker_client: AsyncMock,
    ) -> None:
        """Test disable_service disables an enabled service."""
        orchestrator._registry.register(managed_service)

        # Create lifecycle manager so disable_service can delegate to it
        mock_docker_client.connect.return_value = True
        with patch.object(orchestrator._discovery_service, "discover_all", return_value=[]):
            await orchestrator.start()

        result = await orchestrator.disable_service("ai-yolo26")

        assert result is True
        service = orchestrator.get_service("ai-yolo26")
        assert service is not None
        assert service.enabled is False
        assert service.status == ContainerServiceStatus.DISABLED

    @pytest.mark.asyncio
    async def test_disable_service_broadcasts_status(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_broadcast_fn: AsyncMock,
        mock_docker_client: AsyncMock,
    ) -> None:
        """Test disable_service broadcasts status change."""
        orchestrator._registry.register(managed_service)

        # Create lifecycle manager so disable_service can delegate to it
        mock_docker_client.connect.return_value = True
        with patch.object(orchestrator._discovery_service, "discover_all", return_value=[]):
            await orchestrator.start()

        await orchestrator.disable_service("ai-yolo26")

        mock_broadcast_fn.assert_called()


# =============================================================================
# ContainerOrchestrator.start_service() Tests
# =============================================================================


class TestStartService:
    """Tests for ContainerOrchestrator.start_service method."""

    @pytest.mark.asyncio
    async def test_start_service_unknown(self, orchestrator: ContainerOrchestrator) -> None:
        """Test start_service returns False for unknown service."""
        result = await orchestrator.start_service("unknown")
        assert result is False

    @pytest.mark.asyncio
    async def test_start_service_no_container_id(
        self, orchestrator: ContainerOrchestrator, managed_service: ManagedService
    ) -> None:
        """Test start_service returns False when no container_id."""
        managed_service.container_id = None
        orchestrator._registry.register(managed_service)

        result = await orchestrator.start_service("ai-yolo26")
        assert result is False

    @pytest.mark.asyncio
    async def test_start_service_calls_docker(
        self,
        orchestrator: ContainerOrchestrator,
        mock_docker_client: AsyncMock,
        managed_service: ManagedService,
    ) -> None:
        """Test start_service calls Docker client."""
        orchestrator._registry.register(managed_service)

        await orchestrator.start_service("ai-yolo26")

        mock_docker_client.start_container.assert_called_once_with(managed_service.container_id)

    @pytest.mark.asyncio
    async def test_start_service_broadcasts_on_success(
        self,
        orchestrator: ContainerOrchestrator,
        mock_docker_client: AsyncMock,
        mock_broadcast_fn: AsyncMock,
        managed_service: ManagedService,
    ) -> None:
        """Test start_service broadcasts status on success."""
        mock_docker_client.start_container.return_value = True
        orchestrator._registry.register(managed_service)

        await orchestrator.start_service("ai-yolo26")

        mock_broadcast_fn.assert_called()


# =============================================================================
# Health Change Callback Tests
# =============================================================================


class TestHealthChangeCallback:
    """Tests for health change callback integration."""

    @pytest.mark.asyncio
    async def test_health_change_broadcasts_recovery(
        self,
        orchestrator: ContainerOrchestrator,
        mock_broadcast_fn: AsyncMock,
        managed_service: ManagedService,
    ) -> None:
        """Test health change callback broadcasts recovery."""
        orchestrator._registry.register(managed_service)

        await orchestrator._on_health_change(managed_service, True)

        # Should broadcast "Service recovered"
        mock_broadcast_fn.assert_called()
        call_args = mock_broadcast_fn.call_args[0][0]
        assert "recovered" in call_args.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_health_change_broadcasts_failure(
        self,
        orchestrator: ContainerOrchestrator,
        mock_broadcast_fn: AsyncMock,
        managed_service: ManagedService,
        mock_docker_client: AsyncMock,
    ) -> None:
        """Test health change callback broadcasts failure."""
        orchestrator._registry.register(managed_service)

        # Create lifecycle manager so health change handler can delegate to it
        mock_docker_client.connect.return_value = True
        with patch.object(orchestrator._discovery_service, "discover_all", return_value=[]):
            await orchestrator.start()

        await orchestrator._on_health_change(managed_service, False)

        # Should broadcast health check failed
        mock_broadcast_fn.assert_called()


# =============================================================================
# Broadcast Handling Tests
# =============================================================================


class TestBroadcastHandling:
    """Tests for broadcast function handling."""

    @pytest.mark.asyncio
    async def test_broadcast_handles_exception_gracefully(
        self,
        orchestrator: ContainerOrchestrator,
        mock_broadcast_fn: AsyncMock,
        managed_service: ManagedService,
    ) -> None:
        """Test broadcast handles exceptions gracefully."""
        mock_broadcast_fn.side_effect = Exception("Broadcast failed")
        orchestrator._registry.register(managed_service)

        # Should not raise
        await orchestrator._broadcast_status(managed_service, "Test")

    @pytest.mark.asyncio
    async def test_broadcast_disabled_when_no_fn(
        self,
        mock_docker_client: AsyncMock,
        mock_redis_client: AsyncMock,
        mock_settings: MagicMock,
        managed_service: ManagedService,
    ) -> None:
        """Test broadcast does nothing when no broadcast_fn."""
        orchestrator = ContainerOrchestrator(
            docker_client=mock_docker_client,
            redis_client=mock_redis_client,
            settings=mock_settings,
            broadcast_fn=None,
        )
        orchestrator._registry.register(managed_service)

        # Should not raise
        await orchestrator._broadcast_status(managed_service, "Test")


# Note: TestStateSync and TestServiceConversion classes removed.
# The refactored ContainerOrchestrator no longer has internal methods for:
# - _sync_hm_state() and _sync_lm_state() (state sync between registries)
# - _convert_discovered_to_managed(), _convert_to_hm_service(), _convert_to_lm_service()
# All modules now use the shared ManagedService and ServiceRegistry types from
# backend.services.orchestrator, eliminating the need for type conversion.


# =============================================================================
# Event Structure Tests
# =============================================================================


class TestEventStructure:
    """Tests for WebSocket event structure and format."""

    def test_event_includes_category(self, managed_service: ManagedService) -> None:
        """Test that service status event includes category field."""
        from backend.api.schemas.services import ServiceCategory

        event = create_service_status_event(managed_service, "Test message")

        assert "data" in event
        assert "category" in event["data"]
        assert event["data"]["category"] == ServiceCategory.AI.value

    def test_event_includes_all_categories(self) -> None:
        """Test that events correctly include all category types."""
        from backend.api.schemas.services import ServiceCategory

        for category in ServiceCategory:
            service = ManagedService(
                name=f"test-{category.value}",
                display_name=f"Test {category.value}",
                container_id="abc123def456",
                image="test:latest",
                port=8080,
                category=category,
                health_endpoint="/health",
                health_cmd=None,
                status=ContainerServiceStatus.RUNNING,
                enabled=True,
                failure_count=0,
                restart_count=0,
                max_failures=5,
                restart_backoff_base=5.0,
                restart_backoff_max=300.0,
                startup_grace_period=60,
            )
            event = create_service_status_event(service, "Test")

            assert event["data"]["category"] == category.value

    def test_event_timestamp_is_utc_iso_format(self, managed_service: ManagedService) -> None:
        """Test that event timestamps are in UTC ISO format."""
        managed_service.last_restart_at = datetime.now(UTC)
        event = create_service_status_event(managed_service, "Test message")

        # Check last_restart_at is in ISO format if present
        if event["data"]["last_restart_at"]:
            timestamp_str = event["data"]["last_restart_at"]
            # Should be parseable as ISO format
            parsed = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            assert parsed.tzinfo is not None  # Should have timezone

    def test_event_type_is_service_status(self, managed_service: ManagedService) -> None:
        """Test that event type is 'service_status'."""
        event = create_service_status_event(managed_service, "Test message")

        assert event["type"] == "service_status"

    def test_event_message_preserved(self, managed_service: ManagedService) -> None:
        """Test that event message is correctly preserved."""
        test_message = "Service recovered after restart"
        event = create_service_status_event(managed_service, test_message)

        assert event["message"] == test_message

    def test_event_includes_status(self, managed_service: ManagedService) -> None:
        """Test that event includes service status."""
        event = create_service_status_event(managed_service, "Test")

        assert "status" in event["data"]
        assert event["data"]["status"] == ContainerServiceStatus.RUNNING.value

    def test_event_includes_failure_count(self, managed_service: ManagedService) -> None:
        """Test that event includes failure_count."""
        managed_service.failure_count = 3
        event = create_service_status_event(managed_service, "Test")

        assert "failure_count" in event["data"]
        assert event["data"]["failure_count"] == 3

    def test_event_includes_restart_count(self, managed_service: ManagedService) -> None:
        """Test that event includes restart_count."""
        managed_service.restart_count = 5
        event = create_service_status_event(managed_service, "Test")

        assert "restart_count" in event["data"]
        assert event["data"]["restart_count"] == 5

    def test_event_includes_enabled_flag(self, managed_service: ManagedService) -> None:
        """Test that event includes enabled flag."""
        event = create_service_status_event(managed_service, "Test")

        assert "enabled" in event["data"]
        assert event["data"]["enabled"] is True

        managed_service.enabled = False
        event = create_service_status_event(managed_service, "Test")
        assert event["data"]["enabled"] is False


# =============================================================================
# Additional Coverage Tests for Missing Lines
# =============================================================================


class TestEnableServiceFallback:
    """Tests for enable_service fallback path without lifecycle manager."""

    @pytest.mark.asyncio
    async def test_enable_service_fallback_without_lifecycle_manager(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_broadcast_fn: AsyncMock,
    ) -> None:
        """Test enable_service fallback when lifecycle manager is None."""
        managed_service.enabled = False
        managed_service.failure_count = 3
        managed_service.status = ContainerServiceStatus.DISABLED
        orchestrator._registry.register(managed_service)

        # Ensure lifecycle manager is None
        orchestrator._lifecycle_manager = None

        result = await orchestrator.enable_service("ai-yolo26")

        assert result is True
        service = orchestrator.get_service("ai-yolo26")
        assert service is not None
        assert service.enabled is True
        assert service.failure_count == 0
        assert service.status == ContainerServiceStatus.STOPPED

        # Should broadcast status change
        mock_broadcast_fn.assert_called()


class TestDisableServiceFallback:
    """Tests for disable_service fallback path without lifecycle manager."""

    @pytest.mark.asyncio
    async def test_disable_service_fallback_without_lifecycle_manager(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_broadcast_fn: AsyncMock,
    ) -> None:
        """Test disable_service fallback when lifecycle manager is None."""
        orchestrator._registry.register(managed_service)

        # Ensure lifecycle manager is None
        orchestrator._lifecycle_manager = None

        result = await orchestrator.disable_service("ai-yolo26")

        assert result is True
        service = orchestrator.get_service("ai-yolo26")
        assert service is not None
        assert service.enabled is False
        assert service.status == ContainerServiceStatus.DISABLED

        # Should broadcast status change
        mock_broadcast_fn.assert_called()


class TestRestartServiceAdvanced:
    """Advanced tests for restart_service covering all code paths."""

    @pytest.mark.asyncio
    async def test_restart_service_with_reset_failures(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_docker_client: AsyncMock,
    ) -> None:
        """Test restart_service with reset_failures=True."""
        managed_service.failure_count = 3
        orchestrator._registry.register(managed_service)

        # Ensure lifecycle manager is None to test fallback
        orchestrator._lifecycle_manager = None

        await orchestrator.restart_service("ai-yolo26", reset_failures=True)

        service = orchestrator.get_service("ai-yolo26")
        assert service is not None
        assert service.failure_count == 0

    @pytest.mark.asyncio
    async def test_restart_service_with_lifecycle_manager_success(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_docker_client: AsyncMock,
        mock_broadcast_fn: AsyncMock,
    ) -> None:
        """Test restart_service with lifecycle manager succeeds."""
        orchestrator._registry.register(managed_service)

        # Create lifecycle manager
        mock_docker_client.connect.return_value = True
        with patch.object(orchestrator._discovery_service, "discover_all", return_value=[]):
            await orchestrator.start()

        # Mock lifecycle manager restart to succeed
        with patch.object(orchestrator._lifecycle_manager, "restart_service", return_value=True):
            result = await orchestrator.restart_service("ai-yolo26")

        assert result is True
        # Should broadcast restart succeeded
        calls = [call[0][0] for call in mock_broadcast_fn.call_args_list]
        messages = [call.get("message", "") for call in calls]
        assert any("succeeded" in msg.lower() for msg in messages)

    @pytest.mark.asyncio
    async def test_restart_service_with_lifecycle_manager_failure(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_docker_client: AsyncMock,
        mock_broadcast_fn: AsyncMock,
    ) -> None:
        """Test restart_service with lifecycle manager fails."""
        orchestrator._registry.register(managed_service)

        # Create lifecycle manager
        mock_docker_client.connect.return_value = True
        with patch.object(orchestrator._discovery_service, "discover_all", return_value=[]):
            await orchestrator.start()

        # Mock lifecycle manager restart to fail
        with patch.object(orchestrator._lifecycle_manager, "restart_service", return_value=False):
            result = await orchestrator.restart_service("ai-yolo26")

        assert result is False
        # Should broadcast restart failed
        calls = [call[0][0] for call in mock_broadcast_fn.call_args_list]
        messages = [call.get("message", "") for call in calls]
        assert any("failed" in msg.lower() for msg in messages)

    @pytest.mark.asyncio
    async def test_restart_service_fallback_success(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_docker_client: AsyncMock,
        mock_broadcast_fn: AsyncMock,
    ) -> None:
        """Test restart_service fallback path succeeds."""
        mock_docker_client.restart_container.return_value = True
        orchestrator._registry.register(managed_service)

        # Ensure lifecycle manager is None
        orchestrator._lifecycle_manager = None

        result = await orchestrator.restart_service("ai-yolo26")

        assert result is True
        mock_docker_client.restart_container.assert_called_once_with(managed_service.container_id)

        service = orchestrator.get_service("ai-yolo26")
        assert service is not None
        assert service.restart_count > 0

        # Should broadcast restart succeeded
        calls = [call[0][0] for call in mock_broadcast_fn.call_args_list]
        messages = [call.get("message", "") for call in calls]
        assert any("succeeded" in msg.lower() for msg in messages)

    @pytest.mark.asyncio
    async def test_restart_service_fallback_failure(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_docker_client: AsyncMock,
        mock_broadcast_fn: AsyncMock,
    ) -> None:
        """Test restart_service fallback path fails."""
        mock_docker_client.restart_container.return_value = False
        orchestrator._registry.register(managed_service)

        # Ensure lifecycle manager is None
        orchestrator._lifecycle_manager = None

        result = await orchestrator.restart_service("ai-yolo26")

        assert result is False
        # Should broadcast restart failed
        calls = [call[0][0] for call in mock_broadcast_fn.call_args_list]
        messages = [call.get("message", "") for call in calls]
        assert any("failed" in msg.lower() for msg in messages)


class TestStartServiceAdvanced:
    """Advanced tests for start_service covering all code paths."""

    @pytest.mark.asyncio
    async def test_start_service_with_lifecycle_manager_success(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_docker_client: AsyncMock,
        mock_broadcast_fn: AsyncMock,
    ) -> None:
        """Test start_service with lifecycle manager succeeds."""
        orchestrator._registry.register(managed_service)

        # Create lifecycle manager
        mock_docker_client.connect.return_value = True
        with patch.object(orchestrator._discovery_service, "discover_all", return_value=[]):
            await orchestrator.start()

        # Mock lifecycle manager start to succeed
        with patch.object(orchestrator._lifecycle_manager, "start_service", return_value=True):
            result = await orchestrator.start_service("ai-yolo26")

        assert result is True
        # Should broadcast service started
        calls = [call[0][0] for call in mock_broadcast_fn.call_args_list]
        messages = [call.get("message", "") for call in calls]
        assert any("started" in msg.lower() for msg in messages)

    @pytest.mark.asyncio
    async def test_start_service_with_lifecycle_manager_failure(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_docker_client: AsyncMock,
    ) -> None:
        """Test start_service with lifecycle manager fails."""
        orchestrator._registry.register(managed_service)

        # Create lifecycle manager
        mock_docker_client.connect.return_value = True
        with patch.object(orchestrator._discovery_service, "discover_all", return_value=[]):
            await orchestrator.start()

        # Mock lifecycle manager start to fail
        with patch.object(orchestrator._lifecycle_manager, "start_service", return_value=False):
            result = await orchestrator.start_service("ai-yolo26")

        assert result is False

    @pytest.mark.asyncio
    async def test_start_service_fallback_success(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_docker_client: AsyncMock,
        mock_broadcast_fn: AsyncMock,
    ) -> None:
        """Test start_service fallback path succeeds."""
        mock_docker_client.start_container.return_value = True
        orchestrator._registry.register(managed_service)

        # Ensure lifecycle manager is None
        orchestrator._lifecycle_manager = None

        result = await orchestrator.start_service("ai-yolo26")

        assert result is True
        mock_docker_client.start_container.assert_called_once_with(managed_service.container_id)

        service = orchestrator.get_service("ai-yolo26")
        assert service is not None
        assert service.status == ContainerServiceStatus.STARTING

        # Should broadcast service started
        calls = [call[0][0] for call in mock_broadcast_fn.call_args_list]
        messages = [call.get("message", "") for call in calls]
        assert any("started" in msg.lower() for msg in messages)

    @pytest.mark.asyncio
    async def test_start_service_fallback_failure(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_docker_client: AsyncMock,
    ) -> None:
        """Test start_service fallback path fails."""
        mock_docker_client.start_container.return_value = False
        orchestrator._registry.register(managed_service)

        # Ensure lifecycle manager is None
        orchestrator._lifecycle_manager = None

        result = await orchestrator.start_service("ai-yolo26")

        assert result is False


class TestHealthChangeCallbackAdvanced:
    """Advanced tests for health change callback covering all code paths."""

    @pytest.mark.asyncio
    async def test_health_change_delegates_to_lifecycle_manager_stopped(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_docker_client: AsyncMock,
        mock_broadcast_fn: AsyncMock,
    ) -> None:
        """Test health change callback delegates to lifecycle manager when stopped."""
        managed_service.status = ContainerServiceStatus.STOPPED
        orchestrator._registry.register(managed_service)

        # Create lifecycle manager
        mock_docker_client.connect.return_value = True
        with patch.object(orchestrator._discovery_service, "discover_all", return_value=[]):
            await orchestrator.start()

        # Mock lifecycle manager handle_stopped
        with patch.object(
            orchestrator._lifecycle_manager, "handle_stopped", new_callable=AsyncMock
        ) as mock_handle_stopped:
            await orchestrator._on_health_change(managed_service, False)

        mock_handle_stopped.assert_called_once_with(managed_service)
        # Should broadcast health check failed
        mock_broadcast_fn.assert_called()

    @pytest.mark.asyncio
    async def test_health_change_delegates_to_lifecycle_manager_unhealthy(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_docker_client: AsyncMock,
        mock_broadcast_fn: AsyncMock,
    ) -> None:
        """Test health change callback delegates to lifecycle manager when unhealthy."""
        managed_service.status = ContainerServiceStatus.RUNNING
        orchestrator._registry.register(managed_service)

        # Create lifecycle manager
        mock_docker_client.connect.return_value = True
        with patch.object(orchestrator._discovery_service, "discover_all", return_value=[]):
            await orchestrator.start()

        # Mock lifecycle manager handle_unhealthy
        with patch.object(
            orchestrator._lifecycle_manager, "handle_unhealthy", new_callable=AsyncMock
        ) as mock_handle_unhealthy:
            await orchestrator._on_health_change(managed_service, False)

        mock_handle_unhealthy.assert_called_once_with(managed_service)
        # Should broadcast health check failed
        mock_broadcast_fn.assert_called()


class TestCallbackBroadcasts:
    """Tests for callback broadcast functionality."""

    @pytest.mark.asyncio
    async def test_on_disabled_callback_broadcasts(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_broadcast_fn: AsyncMock,
    ) -> None:
        """Test on_disabled callback broadcasts status change."""
        orchestrator._registry.register(managed_service)

        await orchestrator._on_disabled(managed_service)

        # Should broadcast "Service disabled - max failures reached"
        mock_broadcast_fn.assert_called()
        call_args = mock_broadcast_fn.call_args[0][0]
        assert "disabled" in call_args.get("message", "").lower()
        assert "max failures" in call_args.get("message", "").lower()


class TestStopHealthMonitorCleanup:
    """Tests for stop method health monitor cleanup."""

    @pytest.mark.asyncio
    async def test_stop_cleans_up_health_monitor(
        self,
        orchestrator: ContainerOrchestrator,
        mock_docker_client: AsyncMock,
        discovered_service: DiscoveredService,
    ) -> None:
        """Test stop method properly cleans up health monitor."""
        mock_docker_client.connect.return_value = True

        with patch.object(
            orchestrator._discovery_service,
            "discover_all",
            return_value=[discovered_service],
        ):
            await orchestrator.start()

        assert orchestrator._health_monitor is not None

        # Mock health monitor stop
        with patch.object(
            orchestrator._health_monitor, "stop", new_callable=AsyncMock
        ) as mock_stop:
            await orchestrator.stop()
            mock_stop.assert_called_once()

        assert orchestrator._health_monitor is None
        assert orchestrator.is_running is False


class TestHealthChangeWithoutLifecycleManager:
    """Tests for health change callback without lifecycle manager."""

    @pytest.mark.asyncio
    async def test_health_change_unhealthy_without_lifecycle_manager(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_broadcast_fn: AsyncMock,
    ) -> None:
        """Test health change callback when lifecycle manager is None."""
        orchestrator._registry.register(managed_service)

        # Ensure lifecycle manager is None
        orchestrator._lifecycle_manager = None

        await orchestrator._on_health_change(managed_service, False)

        # Should still broadcast health check failed
        mock_broadcast_fn.assert_called()
        call_args = mock_broadcast_fn.call_args[0][0]
        assert "health check failed" in call_args.get("message", "").lower()


class TestBroadcastEdgeCases:
    """Tests for broadcast edge cases where service might not exist."""

    @pytest.mark.asyncio
    async def test_enable_service_broadcast_after_service_removed(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_broadcast_fn: AsyncMock,
    ) -> None:
        """Test enable_service handles case where service is removed before broadcast."""
        orchestrator._registry.register(managed_service)
        orchestrator._lifecycle_manager = None

        # Mock get to return None after enable operation (simulating concurrent removal)
        original_get = orchestrator._registry.get

        def mock_get_none_second_call(name: str):
            # First call returns service, second call returns None
            if not hasattr(mock_get_none_second_call, "call_count"):
                mock_get_none_second_call.call_count = 0
            mock_get_none_second_call.call_count += 1

            if mock_get_none_second_call.call_count == 1:
                return original_get(name)
            return None

        with patch.object(orchestrator._registry, "get", side_effect=mock_get_none_second_call):
            result = await orchestrator.enable_service("ai-yolo26")

        # Should still return True (operation succeeded)
        assert result is True
        # Broadcast should not be called since service was None
        assert mock_broadcast_fn.call_count == 0

    @pytest.mark.asyncio
    async def test_disable_service_broadcast_after_service_removed(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_broadcast_fn: AsyncMock,
    ) -> None:
        """Test disable_service handles case where service is removed before broadcast."""
        orchestrator._registry.register(managed_service)
        orchestrator._lifecycle_manager = None

        # Mock get to return None after disable operation
        original_get = orchestrator._registry.get

        def mock_get_none_second_call(name: str):
            if not hasattr(mock_get_none_second_call, "call_count"):
                mock_get_none_second_call.call_count = 0
            mock_get_none_second_call.call_count += 1

            if mock_get_none_second_call.call_count == 1:
                return original_get(name)
            return None

        with patch.object(orchestrator._registry, "get", side_effect=mock_get_none_second_call):
            result = await orchestrator.disable_service("ai-yolo26")

        assert result is True
        assert mock_broadcast_fn.call_count == 0

    @pytest.mark.asyncio
    async def test_restart_service_broadcast_after_service_removed_with_lifecycle_manager(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_docker_client: AsyncMock,
        mock_broadcast_fn: AsyncMock,
    ) -> None:
        """Test restart_service handles service removal with lifecycle manager."""
        orchestrator._registry.register(managed_service)

        # Create lifecycle manager
        mock_docker_client.connect.return_value = True
        with patch.object(orchestrator._discovery_service, "discover_all", return_value=[]):
            await orchestrator.start()

        # Mock lifecycle manager restart to succeed, but service becomes None afterward
        original_get = orchestrator._registry.get

        def mock_get_for_restart(name: str):
            if not hasattr(mock_get_for_restart, "call_count"):
                mock_get_for_restart.call_count = 0
            mock_get_for_restart.call_count += 1

            # First two calls return service (initial check and restart initiated)
            # Third call returns None (after restart success)
            if mock_get_for_restart.call_count <= 2:
                return original_get(name)
            return None

        with (
            patch.object(orchestrator._registry, "get", side_effect=mock_get_for_restart),
            patch.object(orchestrator._lifecycle_manager, "restart_service", return_value=True),
        ):
            result = await orchestrator.restart_service("ai-yolo26")

        assert result is True

    @pytest.mark.asyncio
    async def test_restart_service_fallback_broadcast_after_service_removed(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_docker_client: AsyncMock,
        mock_broadcast_fn: AsyncMock,
    ) -> None:
        """Test restart_service fallback handles service removal before broadcast."""
        mock_docker_client.restart_container.return_value = True
        orchestrator._registry.register(managed_service)
        orchestrator._lifecycle_manager = None

        # Mock get to return None after restart
        original_get = orchestrator._registry.get

        def mock_get_for_fallback(name: str):
            if not hasattr(mock_get_for_fallback, "call_count"):
                mock_get_for_fallback.call_count = 0
            mock_get_for_fallback.call_count += 1

            # First two calls return service, third returns None
            if mock_get_for_fallback.call_count <= 2:
                return original_get(name)
            return None

        with patch.object(orchestrator._registry, "get", side_effect=mock_get_for_fallback):
            result = await orchestrator.restart_service("ai-yolo26")

        assert result is True

    @pytest.mark.asyncio
    async def test_start_service_with_lifecycle_manager_broadcast_after_removal(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_docker_client: AsyncMock,
        mock_broadcast_fn: AsyncMock,
    ) -> None:
        """Test start_service with lifecycle manager handles service removal."""
        orchestrator._registry.register(managed_service)

        # Create lifecycle manager
        mock_docker_client.connect.return_value = True
        with patch.object(orchestrator._discovery_service, "discover_all", return_value=[]):
            await orchestrator.start()

        # Mock get to return None after start
        original_get = orchestrator._registry.get

        def mock_get_for_start(name: str):
            if not hasattr(mock_get_for_start, "call_count"):
                mock_get_for_start.call_count = 0
            mock_get_for_start.call_count += 1

            # First call returns service, second returns None
            if mock_get_for_start.call_count == 1:
                return original_get(name)
            return None

        with (
            patch.object(orchestrator._registry, "get", side_effect=mock_get_for_start),
            patch.object(orchestrator._lifecycle_manager, "start_service", return_value=True),
        ):
            result = await orchestrator.start_service("ai-yolo26")

        assert result is True

    @pytest.mark.asyncio
    async def test_start_service_fallback_broadcast_after_service_removed(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_docker_client: AsyncMock,
        mock_broadcast_fn: AsyncMock,
    ) -> None:
        """Test start_service fallback handles service removal before broadcast."""
        mock_docker_client.start_container.return_value = True
        orchestrator._registry.register(managed_service)
        orchestrator._lifecycle_manager = None

        # Mock get to return None after start
        original_get = orchestrator._registry.get

        def mock_get_for_fallback_start(name: str):
            if not hasattr(mock_get_for_fallback_start, "call_count"):
                mock_get_for_fallback_start.call_count = 0
            mock_get_for_fallback_start.call_count += 1

            # First call returns service, second returns None
            if mock_get_for_fallback_start.call_count == 1:
                return original_get(name)
            return None

        with patch.object(orchestrator._registry, "get", side_effect=mock_get_for_fallback_start):
            result = await orchestrator.start_service("ai-yolo26")

        assert result is True


class TestStopPersistStateIteration:
    """Tests for stop method persist state iteration."""

    @pytest.mark.asyncio
    async def test_stop_persists_multiple_services(
        self,
        orchestrator: ContainerOrchestrator,
        mock_docker_client: AsyncMock,
        discovered_service: DiscoveredService,
    ) -> None:
        """Test stop persists state for multiple services."""
        mock_docker_client.connect.return_value = True

        # Create multiple discovered services
        service2 = DiscoveredService(
            name="ai-analyzer",
            display_name="Nemotron",
            container_id="xyz789abc012",
            image="ghcr.io/example/nemotron:latest",
            port=8091,
            category=ServiceCategory.AI,
            health_endpoint="/health",
            max_failures=5,
            restart_backoff_base=5.0,
            restart_backoff_max=300.0,
            startup_grace_period=60,
        )

        with patch.object(
            orchestrator._discovery_service,
            "discover_all",
            return_value=[discovered_service, service2],
        ):
            await orchestrator.start()

        # Mock persist_state to track calls
        with patch.object(
            orchestrator._registry, "persist_state", new_callable=AsyncMock
        ) as mock_persist:
            await orchestrator.stop()

            # Should persist state for both services
            assert mock_persist.call_count == 2
            persisted_names = [call[0][0] for call in mock_persist.call_args_list]
            assert "ai-yolo26" in persisted_names
            assert "ai-analyzer" in persisted_names

    @pytest.mark.asyncio
    async def test_stop_without_health_monitor(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
    ) -> None:
        """Test stop method when health monitor is None."""
        orchestrator._registry.register(managed_service)
        orchestrator._running = True

        # Ensure health monitor is None
        orchestrator._health_monitor = None

        # Mock persist_state to verify it's called
        with patch.object(
            orchestrator._registry, "persist_state", new_callable=AsyncMock
        ) as mock_persist:
            await orchestrator.stop()

            # Should still persist state
            mock_persist.assert_called_once_with("ai-yolo26")

        assert orchestrator.is_running is False


class TestRestartFailureBroadcasts:
    """Tests for restart failure broadcast edge cases."""

    @pytest.mark.asyncio
    async def test_restart_service_with_lifecycle_manager_failure_broadcasts(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_docker_client: AsyncMock,
        mock_broadcast_fn: AsyncMock,
    ) -> None:
        """Test restart_service broadcasts failure when lifecycle manager fails."""
        orchestrator._registry.register(managed_service)

        # Create lifecycle manager
        mock_docker_client.connect.return_value = True
        with patch.object(orchestrator._discovery_service, "discover_all", return_value=[]):
            await orchestrator.start()

        # Clear previous broadcast calls
        mock_broadcast_fn.reset_mock()

        # Mock lifecycle manager restart to fail
        with patch.object(orchestrator._lifecycle_manager, "restart_service", return_value=False):
            result = await orchestrator.restart_service("ai-yolo26")

        assert result is False
        # Should broadcast restart initiated and restart failed
        assert mock_broadcast_fn.call_count >= 2
        calls = [call[0][0] for call in mock_broadcast_fn.call_args_list]
        messages = [call.get("message", "") for call in calls]
        assert any("initiated" in msg.lower() for msg in messages)
        assert any("failed" in msg.lower() for msg in messages)

    @pytest.mark.asyncio
    async def test_restart_service_fallback_failure_broadcasts(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_docker_client: AsyncMock,
        mock_broadcast_fn: AsyncMock,
    ) -> None:
        """Test restart_service fallback broadcasts failure."""
        mock_docker_client.restart_container.return_value = False
        orchestrator._registry.register(managed_service)
        orchestrator._lifecycle_manager = None

        # Clear previous calls
        mock_broadcast_fn.reset_mock()

        result = await orchestrator.restart_service("ai-yolo26")

        assert result is False
        # Should broadcast restart initiated and restart failed
        assert mock_broadcast_fn.call_count >= 2
        calls = [call[0][0] for call in mock_broadcast_fn.call_args_list]
        messages = [call.get("message", "") for call in calls]
        assert any("initiated" in msg.lower() for msg in messages)
        assert any("failed" in msg.lower() for msg in messages)

    @pytest.mark.asyncio
    async def test_restart_service_with_lifecycle_manager_success_no_broadcast(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_docker_client: AsyncMock,
        mock_broadcast_fn: AsyncMock,
    ) -> None:
        """Test restart_service with lifecycle manager success but service removed."""
        orchestrator._registry.register(managed_service)

        # Create lifecycle manager
        mock_docker_client.connect.return_value = True
        with patch.object(orchestrator._discovery_service, "discover_all", return_value=[]):
            await orchestrator.start()

        # Clear previous calls
        mock_broadcast_fn.reset_mock()

        # Mock get to return None after restart success (service removed concurrently)
        original_get = orchestrator._registry.get
        call_count = {"count": 0}

        def mock_get_with_removal(name: str):
            call_count["count"] += 1
            # First two calls return service (initial check, restart initiated)
            # Third call returns None (after restart succeeds)
            if call_count["count"] <= 2:
                return original_get(name)
            return None

        with (
            patch.object(orchestrator._registry, "get", side_effect=mock_get_with_removal),
            patch.object(orchestrator._lifecycle_manager, "restart_service", return_value=True),
        ):
            result = await orchestrator.restart_service("ai-yolo26")

        assert result is True
        # Should have broadcast initiated but not succeeded (service was None)
        assert mock_broadcast_fn.call_count >= 1

    @pytest.mark.asyncio
    async def test_restart_service_fallback_success_no_broadcast(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_docker_client: AsyncMock,
        mock_broadcast_fn: AsyncMock,
    ) -> None:
        """Test restart_service fallback success but service removed before broadcast."""
        mock_docker_client.restart_container.return_value = True
        orchestrator._registry.register(managed_service)
        orchestrator._lifecycle_manager = None

        # Clear previous calls
        mock_broadcast_fn.reset_mock()

        # Mock get to return None after restart
        original_get = orchestrator._registry.get
        call_count = {"count": 0}

        def mock_get_fallback_removal(name: str):
            call_count["count"] += 1
            # First two calls return service (initial check, restart initiated)
            # Third call (after persist_state) returns None
            if call_count["count"] <= 2:
                return original_get(name)
            return None

        with patch.object(orchestrator._registry, "get", side_effect=mock_get_fallback_removal):
            result = await orchestrator.restart_service("ai-yolo26")

        assert result is True
        # Should have broadcast initiated but not succeeded
        assert mock_broadcast_fn.call_count >= 1
