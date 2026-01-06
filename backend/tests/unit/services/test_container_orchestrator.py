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

from backend.api.schemas.services import ServiceCategory, ServiceStatus
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
        name="ai-detector",
        display_name="RT-DETRv2",
        container_id="abc123def456",
        image="ghcr.io/example/rtdetr:latest",
        port=8090,
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
        name="ai-detector",
        display_name="RT-DETRv2",
        container_id="abc123def456",
        image="ghcr.io/example/rtdetr:latest",
        port=8090,
        category=ServiceCategory.AI,
        health_endpoint="/health",
        health_cmd=None,
        status=ServiceStatus.RUNNING,
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
        assert event["data"]["name"] == "ai-detector"
        assert event["data"]["display_name"] == "RT-DETRv2"
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
        managed_service.status = ServiceStatus.RUNNING
        managed_service.last_restart_at = datetime.now(UTC)
        event = create_service_status_event(managed_service, "Test")

        # Uptime should be close to 0 (just restarted)
        assert event["data"]["uptime_seconds"] is not None
        assert event["data"]["uptime_seconds"] >= 0

    def test_no_uptime_when_not_running(self, managed_service: ManagedService) -> None:
        """Test uptime is None when service is not running."""
        managed_service.status = ServiceStatus.STOPPED
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
        assert services[0].name == "ai-detector"


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

        service = orchestrator.get_service("ai-detector")
        assert service is not None
        assert service.name == "ai-detector"


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

        result = await orchestrator.restart_service("ai-detector")
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

        await orchestrator.restart_service("ai-detector")

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
        self, orchestrator: ContainerOrchestrator, managed_service: ManagedService
    ) -> None:
        """Test enable_service enables a disabled service."""
        managed_service.enabled = False
        managed_service.status = ServiceStatus.DISABLED
        orchestrator._registry.register(managed_service)

        result = await orchestrator.enable_service("ai-detector")

        assert result is True
        service = orchestrator.get_service("ai-detector")
        assert service is not None
        assert service.enabled is True
        assert service.status == ServiceStatus.STOPPED

    @pytest.mark.asyncio
    async def test_enable_service_resets_failures(
        self, orchestrator: ContainerOrchestrator, managed_service: ManagedService
    ) -> None:
        """Test enable_service resets failure count."""
        managed_service.enabled = False
        managed_service.failure_count = 5
        orchestrator._registry.register(managed_service)

        await orchestrator.enable_service("ai-detector")

        service = orchestrator.get_service("ai-detector")
        assert service is not None
        assert service.failure_count == 0

    @pytest.mark.asyncio
    async def test_enable_service_broadcasts_status(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_broadcast_fn: AsyncMock,
    ) -> None:
        """Test enable_service broadcasts status change."""
        managed_service.enabled = False
        orchestrator._registry.register(managed_service)

        await orchestrator.enable_service("ai-detector")

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
        self, orchestrator: ContainerOrchestrator, managed_service: ManagedService
    ) -> None:
        """Test disable_service disables an enabled service."""
        orchestrator._registry.register(managed_service)

        result = await orchestrator.disable_service("ai-detector")

        assert result is True
        service = orchestrator.get_service("ai-detector")
        assert service is not None
        assert service.enabled is False
        assert service.status == ServiceStatus.DISABLED

    @pytest.mark.asyncio
    async def test_disable_service_broadcasts_status(
        self,
        orchestrator: ContainerOrchestrator,
        managed_service: ManagedService,
        mock_broadcast_fn: AsyncMock,
    ) -> None:
        """Test disable_service broadcasts status change."""
        orchestrator._registry.register(managed_service)

        await orchestrator.disable_service("ai-detector")

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

        result = await orchestrator.start_service("ai-detector")
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

        await orchestrator.start_service("ai-detector")

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

        await orchestrator.start_service("ai-detector")

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
        # Initialize hm_registry
        orchestrator._hm_registry = MagicMock()
        hm_service = MagicMock()
        hm_service.name = "ai-detector"
        hm_service.status = ServiceStatus.RUNNING
        orchestrator._hm_registry.get.return_value = hm_service

        await orchestrator._on_health_change(hm_service, True)

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
    ) -> None:
        """Test health change callback broadcasts failure."""
        orchestrator._registry.register(managed_service)
        # Initialize hm_registry
        orchestrator._hm_registry = MagicMock()
        hm_service = MagicMock()
        hm_service.name = "ai-detector"
        hm_service.status = ServiceStatus.UNHEALTHY
        orchestrator._hm_registry.get.return_value = hm_service

        await orchestrator._on_health_change(hm_service, False)

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


# =============================================================================
# State Sync Tests
# =============================================================================


class TestStateSync:
    """Tests for state synchronization between registries."""

    def test_sync_hm_state_when_no_registry(self, orchestrator: ContainerOrchestrator) -> None:
        """Test _sync_hm_state does nothing when no hm_registry."""
        orchestrator._hm_registry = None
        # Should not raise
        orchestrator._sync_hm_state("ai-detector")

    def test_sync_lm_state_when_no_registry(self, orchestrator: ContainerOrchestrator) -> None:
        """Test _sync_lm_state does nothing when no lm_registry."""
        orchestrator._lm_registry = None
        # Should not raise
        orchestrator._sync_lm_state("ai-detector")

    def test_sync_hm_state_updates_main_registry(
        self, orchestrator: ContainerOrchestrator, managed_service: ManagedService
    ) -> None:
        """Test _sync_hm_state updates main registry from hm_registry."""
        orchestrator._registry.register(managed_service)

        orchestrator._hm_registry = MagicMock()
        hm_service = MagicMock()
        hm_service.status = ServiceStatus.UNHEALTHY
        hm_service.failure_count = 3
        hm_service.last_failure_at = datetime.now(UTC)
        hm_service.last_restart_at = None
        hm_service.restart_count = 1
        orchestrator._hm_registry.get.return_value = hm_service

        orchestrator._sync_hm_state("ai-detector")

        service = orchestrator.get_service("ai-detector")
        assert service is not None
        assert service.status == ServiceStatus.UNHEALTHY
        assert service.failure_count == 3


# =============================================================================
# Conversion Tests
# =============================================================================


class TestServiceConversion:
    """Tests for service type conversion methods."""

    def test_convert_discovered_to_managed(
        self, orchestrator: ContainerOrchestrator, discovered_service: DiscoveredService
    ) -> None:
        """Test converting discovered service to managed service."""
        managed = orchestrator._convert_discovered_to_managed(discovered_service)

        assert managed.name == discovered_service.name
        assert managed.display_name == discovered_service.display_name
        assert managed.container_id == discovered_service.container_id
        assert managed.port == discovered_service.port
        assert managed.category == discovered_service.category
        assert managed.status == ServiceStatus.RUNNING
        assert managed.enabled is True

    def test_convert_to_hm_service(
        self, orchestrator: ContainerOrchestrator, managed_service: ManagedService
    ) -> None:
        """Test converting managed service to health monitor service."""
        hm_service = orchestrator._convert_to_hm_service(managed_service)

        assert hm_service.name == managed_service.name
        assert hm_service.container_id == managed_service.container_id
        assert hm_service.port == managed_service.port

    def test_convert_to_lm_service(
        self, orchestrator: ContainerOrchestrator, managed_service: ManagedService
    ) -> None:
        """Test converting managed service to lifecycle manager service."""
        lm_service = orchestrator._convert_to_lm_service(managed_service)

        assert lm_service.name == managed_service.name
        assert lm_service.display_name == managed_service.display_name
        assert lm_service.container_id == managed_service.container_id

    def test_convert_to_lm_service_with_timestamp(
        self, orchestrator: ContainerOrchestrator, managed_service: ManagedService
    ) -> None:
        """Test converting managed service preserves timestamp as float."""
        managed_service.last_failure_at = datetime.now(UTC)
        lm_service = orchestrator._convert_to_lm_service(managed_service)

        assert lm_service.last_failure_at is not None
        assert isinstance(lm_service.last_failure_at, float)


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
                status=ServiceStatus.RUNNING,
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
        assert event["data"]["status"] == ServiceStatus.RUNNING.value

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
