"""Unit tests for container orchestrator health monitor.

Tests for the HealthMonitor class that monitors container health and
triggers restarts when needed. This is separate from the existing
ServiceHealthMonitor which uses ServiceManager/ServiceConfig.

Tests cover:
- HTTP health check success/failure
- Command health check success/failure
- Container status checks
- Grace period respected
- Failure count incremented on unhealthy
- Failure count reset on healthy
- Callback invoked on health change
- Start/stop background loop
- Mock all external dependencies
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.schemas.services import ContainerServiceStatus, ServiceCategory
from backend.services.health_monitor_orchestrator import (
    HealthMonitor,
    ManagedService,
    ServiceRegistry,
    check_cmd_health,
    check_http_health,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_docker_client() -> MagicMock:
    """Create a mock DockerClient."""
    client = MagicMock()
    client.get_container = AsyncMock(return_value=MagicMock())
    client.get_container_status = AsyncMock(return_value="running")
    client.exec_run = AsyncMock(return_value=0)
    client.restart_container = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock OrchestratorSettings."""
    settings = MagicMock()
    settings.health_check_interval = 30
    settings.health_check_timeout = 5
    settings.startup_grace_period = 60
    settings.max_consecutive_failures = 5
    settings.restart_backoff_base = 5.0
    settings.restart_backoff_max = 300.0
    return settings


@pytest.fixture
def sample_service() -> ManagedService:
    """Create a sample ManagedService for testing."""
    return ManagedService(
        name="ai-yolo26",
        display_name="YOLO26",
        container_id="abc123",
        image="ghcr.io/example/yolo26:latest",
        port=8095,
        health_endpoint="/health",
        health_cmd=None,
        category=ServiceCategory.AI,
        status=ContainerServiceStatus.RUNNING,
        enabled=True,
        failure_count=0,
        last_failure_at=None,
        last_restart_at=None,
        restart_count=0,
        max_failures=5,
        restart_backoff_base=5.0,
        restart_backoff_max=300.0,
        startup_grace_period=60,
    )


@pytest.fixture
def sample_infrastructure_service() -> ManagedService:
    """Create a sample infrastructure ManagedService (uses health_cmd)."""
    return ManagedService(
        name="postgres",
        display_name="PostgreSQL",
        container_id="def456",
        image="postgres:16-alpine",
        port=5432,
        health_endpoint=None,
        health_cmd="pg_isready -U security",
        category=ServiceCategory.INFRASTRUCTURE,
        status=ContainerServiceStatus.RUNNING,
        enabled=True,
        failure_count=0,
        last_failure_at=None,
        last_restart_at=None,
        restart_count=0,
        max_failures=10,
        restart_backoff_base=2.0,
        restart_backoff_max=60.0,
        startup_grace_period=10,
    )


@pytest.fixture
def service_registry(sample_service: ManagedService) -> ServiceRegistry:
    """Create a ServiceRegistry with a sample service."""
    registry = ServiceRegistry()
    registry.register(sample_service)
    return registry


# =============================================================================
# ManagedService Tests
# =============================================================================


class TestManagedService:
    """Tests for ManagedService dataclass."""

    def test_create_ai_service(self, sample_service: ManagedService) -> None:
        """Test creating an AI service."""
        assert sample_service.name == "ai-yolo26"
        assert sample_service.category == ServiceCategory.AI
        assert sample_service.health_endpoint == "/health"
        assert sample_service.health_cmd is None

    def test_create_infrastructure_service(
        self, sample_infrastructure_service: ManagedService
    ) -> None:
        """Test creating an infrastructure service."""
        assert sample_infrastructure_service.name == "postgres"
        assert sample_infrastructure_service.category == ServiceCategory.INFRASTRUCTURE
        assert sample_infrastructure_service.health_endpoint is None
        assert sample_infrastructure_service.health_cmd == "pg_isready -U security"

    def test_default_values(self) -> None:
        """Test default values for ManagedService."""
        service = ManagedService(
            name="test",
            display_name="Test Service",
            container_id="test123",
            image="test:latest",
            port=8080,
            category=ServiceCategory.AI,
        )
        assert service.enabled is True
        assert service.failure_count == 0
        assert service.restart_count == 0
        assert service.max_failures == 5
        assert service.startup_grace_period == 60


# =============================================================================
# ServiceRegistry Tests
# =============================================================================


class TestServiceRegistry:
    """Tests for ServiceRegistry class."""

    def test_register_service(self, sample_service: ManagedService) -> None:
        """Test registering a service."""
        registry = ServiceRegistry()
        registry.register(sample_service)

        assert "ai-yolo26" in registry.list_names()
        assert registry.get("ai-yolo26") is sample_service

    def test_get_nonexistent_service(self) -> None:
        """Test getting a nonexistent service returns None."""
        registry = ServiceRegistry()
        assert registry.get("nonexistent") is None

    def test_get_enabled_services(
        self, sample_service: ManagedService, sample_infrastructure_service: ManagedService
    ) -> None:
        """Test getting only enabled services."""
        registry = ServiceRegistry()
        registry.register(sample_service)
        registry.register(sample_infrastructure_service)

        # Disable one service
        sample_service.enabled = False

        enabled = registry.get_enabled()
        assert len(enabled) == 1
        assert enabled[0].name == "postgres"

    def test_update_status(self, service_registry: ServiceRegistry) -> None:
        """Test updating service status."""
        service_registry.update_status("ai-yolo26", ContainerServiceStatus.UNHEALTHY)

        service = service_registry.get("ai-yolo26")
        assert service is not None
        assert service.status == ContainerServiceStatus.UNHEALTHY

    def test_increment_failures(self, service_registry: ServiceRegistry) -> None:
        """Test incrementing failure count."""
        service_registry.increment_failures("ai-yolo26")

        service = service_registry.get("ai-yolo26")
        assert service is not None
        assert service.failure_count == 1
        assert service.last_failure_at is not None

    def test_reset_failures(self, service_registry: ServiceRegistry) -> None:
        """Test resetting failure count."""
        # First increment
        service_registry.increment_failures("ai-yolo26")
        service_registry.increment_failures("ai-yolo26")

        # Then reset
        service_registry.reset_failures("ai-yolo26")

        service = service_registry.get("ai-yolo26")
        assert service is not None
        assert service.failure_count == 0

    def test_list_names(
        self, sample_service: ManagedService, sample_infrastructure_service: ManagedService
    ) -> None:
        """Test listing all service names."""
        registry = ServiceRegistry()
        registry.register(sample_service)
        registry.register(sample_infrastructure_service)

        names = registry.list_names()
        assert len(names) == 2
        assert "ai-yolo26" in names
        assert "postgres" in names


# =============================================================================
# HTTP Health Check Tests
# =============================================================================


class TestCheckHttpHealth:
    """Tests for check_http_health function."""

    @pytest.mark.asyncio
    async def test_http_health_check_success(self) -> None:
        """Test HTTP health check returns True on 200 status."""
        with patch("backend.services.health_monitor_orchestrator.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance

            result = await check_http_health("localhost", 8090, "/health")
            assert result is True

    @pytest.mark.asyncio
    async def test_http_health_check_failure_non_200(self) -> None:
        """Test HTTP health check returns False on non-200 status."""
        with patch("backend.services.health_monitor_orchestrator.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 503
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance

            result = await check_http_health("localhost", 8090, "/health")
            assert result is False

    @pytest.mark.asyncio
    async def test_http_health_check_timeout(self) -> None:
        """Test HTTP health check returns False on timeout."""
        import httpx

        with patch("backend.services.health_monitor_orchestrator.httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance

            result = await check_http_health("localhost", 8090, "/health")
            assert result is False

    @pytest.mark.asyncio
    async def test_http_health_check_connection_error(self) -> None:
        """Test HTTP health check returns False on connection error."""
        import httpx

        with patch("backend.services.health_monitor_orchestrator.httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                side_effect=httpx.RequestError("Connection refused")
            )
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance

            result = await check_http_health("localhost", 8090, "/health")
            assert result is False


# =============================================================================
# Command Health Check Tests
# =============================================================================


class TestCheckCmdHealth:
    """Tests for check_cmd_health function."""

    @pytest.mark.asyncio
    async def test_cmd_health_check_success(self, mock_docker_client: MagicMock) -> None:
        """Test command health check returns True on exit code 0."""
        mock_docker_client.exec_run = AsyncMock(return_value=0)

        result = await check_cmd_health(mock_docker_client, "abc123", "pg_isready -U security")
        assert result is True
        mock_docker_client.exec_run.assert_called_once_with(
            "abc123", "pg_isready -U security", timeout=5
        )

    @pytest.mark.asyncio
    async def test_cmd_health_check_failure(self, mock_docker_client: MagicMock) -> None:
        """Test command health check returns False on non-zero exit code."""
        mock_docker_client.exec_run = AsyncMock(return_value=1)

        result = await check_cmd_health(mock_docker_client, "abc123", "pg_isready -U security")
        assert result is False

    @pytest.mark.asyncio
    async def test_cmd_health_check_exception(self, mock_docker_client: MagicMock) -> None:
        """Test command health check returns False on exception."""
        mock_docker_client.exec_run = AsyncMock(side_effect=Exception("Docker error"))

        result = await check_cmd_health(mock_docker_client, "abc123", "pg_isready -U security")
        assert result is False


# =============================================================================
# HealthMonitor Tests
# =============================================================================


class TestHealthMonitorInit:
    """Tests for HealthMonitor initialization."""

    def test_init_with_defaults(
        self,
        service_registry: ServiceRegistry,
        mock_docker_client: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test HealthMonitor initialization with default values."""
        monitor = HealthMonitor(
            registry=service_registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
        )

        assert monitor.is_running is False
        assert monitor._registry is service_registry
        assert monitor._docker_client is mock_docker_client

    def test_init_with_callback(
        self,
        service_registry: ServiceRegistry,
        mock_docker_client: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test HealthMonitor initialization with callback."""
        callback = AsyncMock()
        monitor = HealthMonitor(
            registry=service_registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
            on_health_change=callback,
        )

        assert monitor._on_health_change is callback


class TestHealthMonitorCheckServiceHealth:
    """Tests for HealthMonitor.check_service_health method."""

    @pytest.mark.asyncio
    async def test_check_health_http_endpoint(
        self,
        service_registry: ServiceRegistry,
        mock_docker_client: MagicMock,
        mock_settings: MagicMock,
        sample_service: ManagedService,
    ) -> None:
        """Test checking health via HTTP endpoint."""
        monitor = HealthMonitor(
            registry=service_registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
        )

        with patch(
            "backend.services.health_monitor_orchestrator.check_http_health",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_http:
            result = await monitor.check_service_health(sample_service)

            assert result is True
            mock_http.assert_called_once_with(
                host="ai-yolo26", port=8095, endpoint="/health", timeout=5.0
            )

    @pytest.mark.asyncio
    async def test_check_health_cmd(
        self,
        mock_docker_client: MagicMock,
        mock_settings: MagicMock,
        sample_infrastructure_service: ManagedService,
    ) -> None:
        """Test checking health via command execution."""
        registry = ServiceRegistry()
        registry.register(sample_infrastructure_service)

        monitor = HealthMonitor(
            registry=registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
        )

        with patch(
            "backend.services.health_monitor_orchestrator.check_cmd_health",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_cmd:
            result = await monitor.check_service_health(sample_infrastructure_service)

            assert result is True
            mock_cmd.assert_called_once_with(
                docker_client=mock_docker_client,
                container_id="def456",
                cmd="pg_isready -U security",
                timeout=5,
            )

    @pytest.mark.asyncio
    async def test_check_health_fallback_container_running(
        self,
        mock_docker_client: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test fallback to container running check when no health endpoint or cmd."""
        service = ManagedService(
            name="simple-service",
            display_name="Simple Service",
            container_id="simple123",
            image="simple:latest",
            port=8080,
            health_endpoint=None,
            health_cmd=None,
            category=ServiceCategory.MONITORING,
        )

        registry = ServiceRegistry()
        registry.register(service)

        monitor = HealthMonitor(
            registry=registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
        )

        # Service is running
        mock_docker_client.get_container_status = AsyncMock(return_value="running")

        result = await monitor.check_service_health(service)
        assert result is True


class TestHealthMonitorCheckAllServices:
    """Tests for HealthMonitor.check_all_services method."""

    @pytest.mark.asyncio
    async def test_check_all_services(
        self,
        mock_docker_client: MagicMock,
        mock_settings: MagicMock,
        sample_service: ManagedService,
        sample_infrastructure_service: ManagedService,
    ) -> None:
        """Test checking health of all enabled services."""
        registry = ServiceRegistry()
        registry.register(sample_service)
        registry.register(sample_infrastructure_service)

        monitor = HealthMonitor(
            registry=registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
        )

        with patch.object(
            monitor, "check_service_health", new_callable=AsyncMock, return_value=True
        ):
            results = await monitor.check_all_services()

            assert len(results) == 2
            assert results["ai-yolo26"] is True
            assert results["postgres"] is True


class TestHealthMonitorGracePeriod:
    """Tests for grace period handling."""

    @pytest.mark.asyncio
    async def test_in_grace_period_skips_check(
        self,
        mock_docker_client: MagicMock,
        mock_settings: MagicMock,
        sample_service: ManagedService,
    ) -> None:
        """Test that services in grace period are skipped."""
        # Set last_restart_at to recent time
        sample_service.last_restart_at = datetime.now(UTC) - timedelta(seconds=10)
        sample_service.startup_grace_period = 60  # 60 second grace period

        registry = ServiceRegistry()
        registry.register(sample_service)

        monitor = HealthMonitor(
            registry=registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
        )

        # Should return True (skip grace period services)
        in_grace = monitor._in_grace_period(sample_service)
        assert in_grace is True

    @pytest.mark.asyncio
    async def test_past_grace_period(
        self,
        mock_docker_client: MagicMock,
        mock_settings: MagicMock,
        sample_service: ManagedService,
    ) -> None:
        """Test that services past grace period are checked."""
        # Set last_restart_at to past the grace period
        sample_service.last_restart_at = datetime.now(UTC) - timedelta(seconds=120)
        sample_service.startup_grace_period = 60

        registry = ServiceRegistry()
        registry.register(sample_service)

        monitor = HealthMonitor(
            registry=registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
        )

        in_grace = monitor._in_grace_period(sample_service)
        assert in_grace is False

    @pytest.mark.asyncio
    async def test_no_restart_not_in_grace_period(
        self,
        mock_docker_client: MagicMock,
        mock_settings: MagicMock,
        sample_service: ManagedService,
    ) -> None:
        """Test that services never restarted are not in grace period."""
        sample_service.last_restart_at = None

        registry = ServiceRegistry()
        registry.register(sample_service)

        monitor = HealthMonitor(
            registry=registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
        )

        in_grace = monitor._in_grace_period(sample_service)
        assert in_grace is False


class TestHealthMonitorFailureTracking:
    """Tests for failure tracking in HealthMonitor."""

    @pytest.mark.asyncio
    async def test_failure_count_incremented_on_unhealthy(
        self,
        mock_docker_client: MagicMock,
        mock_settings: MagicMock,
        sample_service: ManagedService,
    ) -> None:
        """Test that failure count is incremented when service is unhealthy."""
        registry = ServiceRegistry()
        registry.register(sample_service)

        monitor = HealthMonitor(
            registry=registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
        )

        with patch(
            "backend.services.health_monitor_orchestrator.check_http_health",
            new_callable=AsyncMock,
            return_value=False,
        ):
            await monitor._handle_unhealthy(sample_service)

        assert sample_service.failure_count == 1
        assert sample_service.last_failure_at is not None

    @pytest.mark.asyncio
    async def test_failure_count_reset_on_healthy(
        self,
        mock_docker_client: MagicMock,
        mock_settings: MagicMock,
        sample_service: ManagedService,
    ) -> None:
        """Test that failure count is reset when service becomes healthy."""
        # Start with some failures
        sample_service.failure_count = 3
        sample_service.last_failure_at = datetime.now(UTC)

        registry = ServiceRegistry()
        registry.register(sample_service)

        monitor = HealthMonitor(
            registry=registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
        )

        # Simulate healthy response
        with patch(
            "backend.services.health_monitor_orchestrator.check_http_health",
            new_callable=AsyncMock,
            return_value=True,
        ):
            await monitor.run_health_check_cycle()

        assert sample_service.failure_count == 0


class TestHealthMonitorCallback:
    """Tests for health change callback."""

    @pytest.mark.asyncio
    async def test_callback_invoked_on_health_change_healthy(
        self,
        mock_docker_client: MagicMock,
        mock_settings: MagicMock,
        sample_service: ManagedService,
    ) -> None:
        """Test callback is invoked when service becomes healthy."""
        sample_service.failure_count = 2  # Was unhealthy

        registry = ServiceRegistry()
        registry.register(sample_service)

        callback = AsyncMock()
        monitor = HealthMonitor(
            registry=registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
            on_health_change=callback,
        )

        with patch(
            "backend.services.health_monitor_orchestrator.check_http_health",
            new_callable=AsyncMock,
            return_value=True,
        ):
            await monitor.run_health_check_cycle()

        callback.assert_called_once_with(sample_service, True)

    @pytest.mark.asyncio
    async def test_callback_invoked_on_health_change_unhealthy(
        self,
        mock_docker_client: MagicMock,
        mock_settings: MagicMock,
        sample_service: ManagedService,
    ) -> None:
        """Test callback is invoked when service becomes unhealthy."""
        registry = ServiceRegistry()
        registry.register(sample_service)

        callback = AsyncMock()
        monitor = HealthMonitor(
            registry=registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
            on_health_change=callback,
        )

        with patch(
            "backend.services.health_monitor_orchestrator.check_http_health",
            new_callable=AsyncMock,
            return_value=False,
        ):
            await monitor.run_health_check_cycle()

        # Callback should be called with healthy=False
        callback.assert_called()
        call_args = callback.call_args[0]
        assert call_args[1] is False  # healthy parameter


class TestHealthMonitorStartStop:
    """Tests for start/stop background loop."""

    @pytest.mark.asyncio
    async def test_start_sets_running(
        self,
        service_registry: ServiceRegistry,
        mock_docker_client: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test that start sets is_running to True."""
        mock_settings.health_check_interval = 0.1  # Fast interval for testing

        monitor = HealthMonitor(
            registry=service_registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
        )

        await monitor.start()
        assert monitor.is_running is True

        # Cleanup
        await monitor.stop()

    @pytest.mark.asyncio
    async def test_stop_sets_not_running(
        self,
        service_registry: ServiceRegistry,
        mock_docker_client: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test that stop sets is_running to False."""
        mock_settings.health_check_interval = 0.1

        monitor = HealthMonitor(
            registry=service_registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
        )

        await monitor.start()
        await monitor.stop()

        assert monitor.is_running is False

    @pytest.mark.asyncio
    async def test_start_idempotent(
        self,
        service_registry: ServiceRegistry,
        mock_docker_client: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test that calling start multiple times is safe."""
        mock_settings.health_check_interval = 0.1

        monitor = HealthMonitor(
            registry=service_registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
        )

        await monitor.start()
        await monitor.start()  # Should not raise
        assert monitor.is_running is True

        await monitor.stop()

    @pytest.mark.asyncio
    async def test_stop_idempotent(
        self,
        service_registry: ServiceRegistry,
        mock_docker_client: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test that calling stop multiple times is safe."""
        monitor = HealthMonitor(
            registry=service_registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
        )

        await monitor.stop()  # Should not raise when not started
        await monitor.stop()  # Should not raise

    @pytest.mark.asyncio
    async def test_health_check_loop_runs(
        self,
        service_registry: ServiceRegistry,
        mock_docker_client: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test that health check loop runs periodically."""
        mock_settings.health_check_interval = 0.05  # 50ms for fast testing

        monitor = HealthMonitor(
            registry=service_registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
        )

        check_count = 0

        async def mock_check(*args, **kwargs):
            nonlocal check_count
            check_count += 1
            return True

        with patch.object(monitor, "check_service_health", side_effect=mock_check):
            await monitor.start()
            await asyncio.sleep(0.2)  # Let it run a few cycles
            await monitor.stop()

        assert check_count >= 2  # Should have run multiple times


class TestHealthMonitorContainerStatusChecks:
    """Tests for container status handling."""

    @pytest.mark.asyncio
    async def test_handle_missing_container(
        self,
        mock_docker_client: MagicMock,
        mock_settings: MagicMock,
        sample_service: ManagedService,
    ) -> None:
        """Test handling when container is missing."""
        mock_docker_client.get_container = AsyncMock(return_value=None)

        registry = ServiceRegistry()
        registry.register(sample_service)

        monitor = HealthMonitor(
            registry=registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
        )

        await monitor._handle_missing_container(sample_service)

        assert sample_service.status == ContainerServiceStatus.NOT_FOUND

    @pytest.mark.asyncio
    async def test_handle_stopped_container(
        self,
        mock_docker_client: MagicMock,
        mock_settings: MagicMock,
        sample_service: ManagedService,
    ) -> None:
        """Test handling when container is stopped."""
        mock_docker_client.get_container_status = AsyncMock(return_value="exited")

        registry = ServiceRegistry()
        registry.register(sample_service)

        monitor = HealthMonitor(
            registry=registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
        )

        await monitor._handle_stopped_container(sample_service)

        assert sample_service.status == ContainerServiceStatus.STOPPED


class TestHealthMonitorFullCycle:
    """Integration tests for full health check cycle."""

    @pytest.mark.asyncio
    async def test_full_cycle_healthy_service(
        self,
        mock_docker_client: MagicMock,
        mock_settings: MagicMock,
        sample_service: ManagedService,
    ) -> None:
        """Test full health check cycle for a healthy service."""
        registry = ServiceRegistry()
        registry.register(sample_service)

        monitor = HealthMonitor(
            registry=registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
        )

        with patch(
            "backend.services.health_monitor_orchestrator.check_http_health",
            new_callable=AsyncMock,
            return_value=True,
        ):
            await monitor.run_health_check_cycle()

        assert sample_service.status == ContainerServiceStatus.RUNNING
        assert sample_service.failure_count == 0

    @pytest.mark.asyncio
    async def test_full_cycle_unhealthy_service(
        self,
        mock_docker_client: MagicMock,
        mock_settings: MagicMock,
        sample_service: ManagedService,
    ) -> None:
        """Test full health check cycle for an unhealthy service."""
        registry = ServiceRegistry()
        registry.register(sample_service)

        monitor = HealthMonitor(
            registry=registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
        )

        with patch(
            "backend.services.health_monitor_orchestrator.check_http_health",
            new_callable=AsyncMock,
            return_value=False,
        ):
            await monitor.run_health_check_cycle()

        assert sample_service.status == ContainerServiceStatus.UNHEALTHY
        assert sample_service.failure_count == 1


# =============================================================================
# Health Check Dispatcher Tests
# =============================================================================


class TestHealthCheckDispatcher:
    """Tests for health check dispatcher routing logic."""

    @pytest.mark.asyncio
    async def test_dispatcher_routes_to_http_when_endpoint_present(
        self,
        mock_docker_client: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test that dispatcher routes to HTTP health check when health_endpoint is set."""
        service = ManagedService(
            name="api-service",
            display_name="API Service",
            container_id="abc123",
            image="api:latest",
            port=8080,
            health_endpoint="/health",  # HTTP endpoint specified
            health_cmd=None,
            category=ServiceCategory.AI,
        )

        registry = ServiceRegistry()
        registry.register(service)

        monitor = HealthMonitor(
            registry=registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
        )

        with patch(
            "backend.services.health_monitor_orchestrator.check_http_health",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_http:
            result = await monitor.check_service_health(service)

            assert result is True
            mock_http.assert_called_once()
            # HTTP check should be called, not command check
            assert not mock_docker_client.exec_run.called

    @pytest.mark.asyncio
    async def test_dispatcher_routes_to_cmd_when_only_cmd_present(
        self,
        mock_docker_client: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test that dispatcher routes to command check when only health_cmd is set."""
        service = ManagedService(
            name="postgres",
            display_name="PostgreSQL",
            container_id="pg123",
            image="postgres:16",
            port=5432,
            health_endpoint=None,  # No HTTP endpoint
            health_cmd="pg_isready -U security",  # Command specified
            category=ServiceCategory.INFRASTRUCTURE,
        )

        registry = ServiceRegistry()
        registry.register(service)

        monitor = HealthMonitor(
            registry=registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
        )

        with patch(
            "backend.services.health_monitor_orchestrator.check_cmd_health",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_cmd:
            result = await monitor.check_service_health(service)

            assert result is True
            mock_cmd.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatcher_falls_back_to_container_running(
        self,
        mock_docker_client: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test that dispatcher falls back to container running check."""
        service = ManagedService(
            name="simple-service",
            display_name="Simple Service",
            container_id="simple123",
            image="simple:latest",
            port=8080,
            health_endpoint=None,  # No HTTP endpoint
            health_cmd=None,  # No command either
            category=ServiceCategory.MONITORING,
        )

        registry = ServiceRegistry()
        registry.register(service)

        monitor = HealthMonitor(
            registry=registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
        )

        mock_docker_client.get_container_status = AsyncMock(return_value="running")

        result = await monitor.check_service_health(service)

        assert result is True
        mock_docker_client.get_container_status.assert_called_once_with("simple123")

    @pytest.mark.asyncio
    async def test_dispatcher_http_takes_precedence_over_cmd(
        self,
        mock_docker_client: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test that HTTP health check takes precedence when both are set."""
        service = ManagedService(
            name="dual-check-service",
            display_name="Dual Check Service",
            container_id="dual123",
            image="dual:latest",
            port=8080,
            health_endpoint="/health",  # Both specified
            health_cmd="health-check-cmd",  # Both specified
            category=ServiceCategory.AI,
        )

        registry = ServiceRegistry()
        registry.register(service)

        monitor = HealthMonitor(
            registry=registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
        )

        with (
            patch(
                "backend.services.health_monitor_orchestrator.check_http_health",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_http,
            patch(
                "backend.services.health_monitor_orchestrator.check_cmd_health",
                new_callable=AsyncMock,
            ) as mock_cmd,
        ):
            result = await monitor.check_service_health(service)

            assert result is True
            # HTTP should be called
            mock_http.assert_called_once()
            # Command should NOT be called (HTTP takes precedence)
            mock_cmd.assert_not_called()


# =============================================================================
# Grace Period STARTING Status Tests
# =============================================================================


class TestGracePeriodStartingStatus:
    """Tests for grace period behavior during STARTING status."""

    @pytest.mark.asyncio
    async def test_starting_service_in_grace_period(
        self,
        mock_docker_client: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test that STARTING service within grace period is skipped."""
        service = ManagedService(
            name="starting-service",
            display_name="Starting Service",
            container_id="start123",
            image="test:latest",
            port=8080,
            health_endpoint="/health",
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.STARTING,
            startup_grace_period=60,
            last_restart_at=datetime.now(UTC) - timedelta(seconds=10),  # 10s ago
        )

        registry = ServiceRegistry()
        registry.register(service)

        monitor = HealthMonitor(
            registry=registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
        )

        assert monitor._in_grace_period(service) is True

    @pytest.mark.asyncio
    async def test_starting_service_past_grace_period(
        self,
        mock_docker_client: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test that STARTING service past grace period is checked."""
        service = ManagedService(
            name="started-service",
            display_name="Started Service",
            container_id="started123",
            image="test:latest",
            port=8080,
            health_endpoint="/health",
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.STARTING,
            startup_grace_period=60,
            last_restart_at=datetime.now(UTC) - timedelta(seconds=120),  # 2 minutes ago
        )

        registry = ServiceRegistry()
        registry.register(service)

        monitor = HealthMonitor(
            registry=registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
        )

        assert monitor._in_grace_period(service) is False

    @pytest.mark.asyncio
    async def test_infrastructure_shorter_grace_period(
        self,
        mock_docker_client: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test that infrastructure services have shorter grace periods (10s)."""
        service = ManagedService(
            name="postgres",
            display_name="PostgreSQL",
            container_id="pg123",
            image="postgres:16",
            port=5432,
            health_cmd="pg_isready",
            category=ServiceCategory.INFRASTRUCTURE,
            status=ContainerServiceStatus.STARTING,
            startup_grace_period=10,  # Infrastructure has 10s
            last_restart_at=datetime.now(UTC) - timedelta(seconds=15),  # 15s ago
        )

        registry = ServiceRegistry()
        registry.register(service)

        monitor = HealthMonitor(
            registry=registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
        )

        # 15s > 10s grace period, so should NOT be in grace period
        assert monitor._in_grace_period(service) is False

    @pytest.mark.asyncio
    async def test_ai_longer_grace_period(
        self,
        mock_docker_client: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test that AI services have longer grace periods (60s)."""
        service = ManagedService(
            name="ai-yolo26",
            display_name="YOLO26",
            container_id="det123",
            image="yolo26:latest",
            port=8095,
            health_endpoint="/health",
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.STARTING,
            startup_grace_period=60,  # AI has 60s
            last_restart_at=datetime.now(UTC) - timedelta(seconds=30),  # 30s ago
        )

        registry = ServiceRegistry()
        registry.register(service)

        monitor = HealthMonitor(
            registry=registry,
            docker_client=mock_docker_client,
            settings=mock_settings,
        )

        # 30s < 60s grace period, so should be in grace period
        assert monitor._in_grace_period(service) is True
