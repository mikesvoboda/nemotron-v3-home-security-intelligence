"""Unit tests for LifecycleManager self-healing restart logic.

Tests cover:
- Backoff calculation (exponential growth, capped at max)
- should_restart respects backoff timing
- Service disabled after max failures
- Restart updates tracking fields
- handle_unhealthy increments failure count
- handle_stopped triggers restart
- Enable service resets failures
- Callbacks invoked on restart/disable
- Category-specific defaults (Infrastructure, AI, Monitoring)
- Mock DockerClient and ServiceRegistry

TDD: These tests are written FIRST, before implementing the LifecycleManager.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.api.schemas.services import ContainerServiceStatus, ServiceCategory
from backend.services.lifecycle_manager import (
    LifecycleManager,
    ManagedService,
    ServiceRegistry,
    calculate_backoff,
)

# =============================================================================
# Test Configuration and Fixtures
# =============================================================================


@pytest.fixture
def mock_docker_client() -> AsyncMock:
    """Create a mock DockerClient."""
    client = AsyncMock()
    client.stop_container = AsyncMock(return_value=True)
    client.start_container = AsyncMock(return_value=True)
    client.restart_container = AsyncMock(return_value=True)
    client.get_container = AsyncMock(return_value=MagicMock(status="running"))
    return client


@pytest.fixture
def mock_registry() -> MagicMock:
    """Create a mock ServiceRegistry."""
    registry = MagicMock(spec=ServiceRegistry)
    registry.record_restart = MagicMock()
    registry.update_status = MagicMock()
    registry.persist_state = AsyncMock()
    registry.increment_failure = MagicMock(return_value=1)
    registry.set_enabled = MagicMock()
    registry.reset_failures = MagicMock()
    return registry


@pytest.fixture
def infrastructure_service() -> ManagedService:
    """Create an infrastructure service (PostgreSQL-like)."""
    return ManagedService(
        name="postgres",
        display_name="PostgreSQL",
        container_id="abc123",
        image="postgres:16-alpine",
        port=5432,
        health_endpoint=None,
        health_cmd="pg_isready -U security",
        category=ServiceCategory.INFRASTRUCTURE,
        status=ContainerServiceStatus.RUNNING,
        enabled=True,
        failure_count=0,
        restart_count=0,
        max_failures=10,
        restart_backoff_base=2.0,
        restart_backoff_max=60.0,
    )


@pytest.fixture
def ai_service() -> ManagedService:
    """Create an AI service (YOLO26-like)."""
    return ManagedService(
        name="ai-yolo26",
        display_name="YOLO26",
        container_id="def456",
        image="ghcr.io/.../yolo26:latest",
        port=8095,
        health_endpoint="/health",
        health_cmd=None,
        category=ServiceCategory.AI,
        status=ContainerServiceStatus.RUNNING,
        enabled=True,
        failure_count=0,
        restart_count=0,
        max_failures=5,
        restart_backoff_base=5.0,
        restart_backoff_max=300.0,
    )


@pytest.fixture
def monitoring_service() -> ManagedService:
    """Create a monitoring service (Grafana-like)."""
    return ManagedService(
        name="grafana",
        display_name="Grafana",
        container_id="ghi789",
        image="grafana/grafana:10.2.3",
        port=3000,
        health_endpoint="/api/health",
        health_cmd=None,
        category=ServiceCategory.MONITORING,
        status=ContainerServiceStatus.RUNNING,
        enabled=True,
        failure_count=0,
        restart_count=0,
        max_failures=3,
        restart_backoff_base=10.0,
        restart_backoff_max=600.0,
    )


@pytest.fixture
def lifecycle_manager(mock_registry: MagicMock, mock_docker_client: AsyncMock) -> LifecycleManager:
    """Create a LifecycleManager with mocked dependencies."""
    return LifecycleManager(
        registry=mock_registry,
        docker_client=mock_docker_client,
    )


# =============================================================================
# calculate_backoff() Tests
# =============================================================================


class TestCalculateBackoff:
    """Tests for the calculate_backoff function."""

    def test_backoff_zero_failures(self) -> None:
        """Test backoff is base value for 0 failures."""
        result = calculate_backoff(failure_count=0, base=5.0, max_backoff=300.0)
        assert result == 5.0

    def test_backoff_one_failure(self) -> None:
        """Test backoff doubles for 1 failure."""
        result = calculate_backoff(failure_count=1, base=5.0, max_backoff=300.0)
        assert result == 10.0

    def test_backoff_two_failures(self) -> None:
        """Test backoff doubles again for 2 failures."""
        result = calculate_backoff(failure_count=2, base=5.0, max_backoff=300.0)
        assert result == 20.0

    def test_backoff_exponential_sequence(self) -> None:
        """Test backoff follows exponential sequence: 5, 10, 20, 40, 80, 160, 300."""
        base = 5.0
        max_backoff = 300.0
        expected = [5.0, 10.0, 20.0, 40.0, 80.0, 160.0, 300.0]

        for i, exp in enumerate(expected):
            result = calculate_backoff(failure_count=i, base=base, max_backoff=max_backoff)
            assert result == exp, f"Failed at failure_count={i}: expected {exp}, got {result}"

    def test_backoff_capped_at_max(self) -> None:
        """Test backoff never exceeds max value."""
        result = calculate_backoff(failure_count=10, base=5.0, max_backoff=300.0)
        assert result == 300.0

    def test_backoff_large_failure_count_stays_capped(self) -> None:
        """Test backoff stays capped even with very large failure counts."""
        result = calculate_backoff(failure_count=100, base=5.0, max_backoff=300.0)
        assert result == 300.0

    def test_backoff_infrastructure_defaults(self) -> None:
        """Test backoff with infrastructure defaults: base=2.0, max=60."""
        result = calculate_backoff(failure_count=5, base=2.0, max_backoff=60.0)
        # 2 * 2^5 = 64, capped at 60
        assert result == 60.0

    def test_backoff_ai_defaults(self) -> None:
        """Test backoff with AI defaults: base=5.0, max=300."""
        result = calculate_backoff(failure_count=4, base=5.0, max_backoff=300.0)
        # 5 * 2^4 = 80
        assert result == 80.0

    def test_backoff_monitoring_defaults(self) -> None:
        """Test backoff with monitoring defaults: base=10.0, max=600."""
        result = calculate_backoff(failure_count=3, base=10.0, max_backoff=600.0)
        # 10 * 2^3 = 80
        assert result == 80.0


# =============================================================================
# LifecycleManager.__init__() Tests
# =============================================================================


class TestLifecycleManagerInit:
    """Tests for LifecycleManager initialization."""

    def test_init_with_registry_and_docker(
        self, mock_registry: MagicMock, mock_docker_client: AsyncMock
    ) -> None:
        """Test initialization with required dependencies."""
        manager = LifecycleManager(
            registry=mock_registry,
            docker_client=mock_docker_client,
        )
        assert manager.registry is mock_registry
        assert manager.docker_client is mock_docker_client

    def test_init_with_callbacks(
        self, mock_registry: MagicMock, mock_docker_client: AsyncMock
    ) -> None:
        """Test initialization with optional callbacks."""
        on_restart = AsyncMock()
        on_disabled = AsyncMock()

        manager = LifecycleManager(
            registry=mock_registry,
            docker_client=mock_docker_client,
            on_restart=on_restart,
            on_disabled=on_disabled,
        )
        assert manager.on_restart is on_restart
        assert manager.on_disabled is on_disabled

    def test_init_without_callbacks(
        self, mock_registry: MagicMock, mock_docker_client: AsyncMock
    ) -> None:
        """Test initialization without callbacks defaults to None."""
        manager = LifecycleManager(
            registry=mock_registry,
            docker_client=mock_docker_client,
        )
        assert manager.on_restart is None
        assert manager.on_disabled is None


# =============================================================================
# LifecycleManager.calculate_backoff() Tests (Instance Method)
# =============================================================================


class TestLifecycleManagerCalculateBackoff:
    """Tests for LifecycleManager.calculate_backoff instance method."""

    def test_calculate_backoff_uses_service_settings(
        self, lifecycle_manager: LifecycleManager, ai_service: ManagedService
    ) -> None:
        """Test calculate_backoff uses service-specific settings."""
        ai_service.failure_count = 2
        result = lifecycle_manager.calculate_backoff(ai_service)
        # base=5.0 * 2^2 = 20.0
        assert result == 20.0

    def test_calculate_backoff_infrastructure_service(
        self, lifecycle_manager: LifecycleManager, infrastructure_service: ManagedService
    ) -> None:
        """Test calculate_backoff for infrastructure service."""
        infrastructure_service.failure_count = 3
        result = lifecycle_manager.calculate_backoff(infrastructure_service)
        # base=2.0 * 2^3 = 16.0
        assert result == 16.0

    def test_calculate_backoff_monitoring_service(
        self, lifecycle_manager: LifecycleManager, monitoring_service: ManagedService
    ) -> None:
        """Test calculate_backoff for monitoring service."""
        monitoring_service.failure_count = 1
        result = lifecycle_manager.calculate_backoff(monitoring_service)
        # base=10.0 * 2^1 = 20.0
        assert result == 20.0


# =============================================================================
# LifecycleManager.should_restart() Tests
# =============================================================================


class TestShouldRestart:
    """Tests for LifecycleManager.should_restart method."""

    def test_should_restart_when_no_prior_failure(
        self, lifecycle_manager: LifecycleManager, ai_service: ManagedService
    ) -> None:
        """Test should_restart returns True when no prior failure."""
        ai_service.last_failure_at = None
        assert lifecycle_manager.should_restart(ai_service) is True

    def test_should_restart_after_backoff_elapsed(
        self, lifecycle_manager: LifecycleManager, ai_service: ManagedService
    ) -> None:
        """Test should_restart returns True when backoff has elapsed."""
        ai_service.failure_count = 1
        # Set last failure to 30 seconds ago
        ai_service.last_failure_at = datetime.now(UTC) - timedelta(seconds=30)
        # Backoff for 1 failure is 10s (5 * 2^1), so 30s > 10s
        assert lifecycle_manager.should_restart(ai_service) is True

    def test_should_restart_during_backoff(
        self, lifecycle_manager: LifecycleManager, ai_service: ManagedService
    ) -> None:
        """Test should_restart returns False during backoff period."""
        ai_service.failure_count = 5
        # Set last failure to 1 second ago
        ai_service.last_failure_at = datetime.now(UTC) - timedelta(seconds=1)
        # Backoff for 5 failures is 160s (5 * 2^5), so 1s < 160s
        assert lifecycle_manager.should_restart(ai_service) is False

    def test_should_restart_respects_service_backoff_settings(
        self, lifecycle_manager: LifecycleManager, infrastructure_service: ManagedService
    ) -> None:
        """Test should_restart uses service-specific backoff settings."""
        infrastructure_service.failure_count = 2
        # Set last failure to 5 seconds ago
        infrastructure_service.last_failure_at = datetime.now(UTC) - timedelta(seconds=5)
        # Backoff for 2 failures with base=2.0 is 8s (2 * 2^2), so 5s < 8s
        assert lifecycle_manager.should_restart(infrastructure_service) is False

    def test_should_restart_at_max_failures(
        self, lifecycle_manager: LifecycleManager, ai_service: ManagedService
    ) -> None:
        """Test should_restart returns True even at max_failures (services retry forever)."""
        ai_service.failure_count = ai_service.max_failures
        ai_service.last_failure_at = None  # No prior failure = backoff elapsed
        assert lifecycle_manager.should_restart(ai_service) is True

    def test_should_restart_disabled_service(
        self, lifecycle_manager: LifecycleManager, ai_service: ManagedService
    ) -> None:
        """Test should_restart returns False for disabled service."""
        ai_service.enabled = False
        assert lifecycle_manager.should_restart(ai_service) is False


# =============================================================================
# LifecycleManager.backoff_remaining() Tests
# =============================================================================


class TestBackoffRemaining:
    """Tests for LifecycleManager.backoff_remaining method."""

    def test_backoff_remaining_no_prior_failure(
        self, lifecycle_manager: LifecycleManager, ai_service: ManagedService
    ) -> None:
        """Test backoff_remaining returns 0 when no prior failure."""
        ai_service.last_failure_at = None
        assert lifecycle_manager.backoff_remaining(ai_service) == 0.0

    def test_backoff_remaining_during_backoff(
        self, lifecycle_manager: LifecycleManager, ai_service: ManagedService
    ) -> None:
        """Test backoff_remaining returns positive value during backoff."""
        ai_service.failure_count = 1
        # Set last failure to 2 seconds ago
        ai_service.last_failure_at = datetime.now(UTC) - timedelta(seconds=2)
        # Backoff for 1 failure is 10s, so remaining should be ~8s
        remaining = lifecycle_manager.backoff_remaining(ai_service)
        assert 7.0 <= remaining <= 9.0  # Allow some tolerance for timing

    def test_backoff_remaining_after_elapsed(
        self, lifecycle_manager: LifecycleManager, ai_service: ManagedService
    ) -> None:
        """Test backoff_remaining returns 0 after backoff elapsed."""
        ai_service.failure_count = 1
        # Set last failure to 30 seconds ago
        ai_service.last_failure_at = datetime.now(UTC) - timedelta(seconds=30)
        # Backoff for 1 failure is 10s, so remaining should be 0
        assert lifecycle_manager.backoff_remaining(ai_service) == 0.0


# =============================================================================
# LifecycleManager.restart_service() Tests
# =============================================================================


class TestRestartService:
    """Tests for LifecycleManager.restart_service method."""

    @pytest.mark.asyncio
    async def test_restart_service_success(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
        mock_docker_client: AsyncMock,
        mock_registry: MagicMock,
    ) -> None:
        """Test restart_service stops and starts container."""
        result = await lifecycle_manager.restart_service(ai_service)

        assert result is True
        mock_docker_client.stop_container.assert_called_once_with(
            ai_service.container_id, timeout=10
        )
        mock_docker_client.start_container.assert_called_once_with(ai_service.container_id)

    @pytest.mark.asyncio
    async def test_restart_service_updates_tracking(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
        mock_registry: MagicMock,
    ) -> None:
        """Test restart_service updates tracking fields."""
        await lifecycle_manager.restart_service(ai_service)

        mock_registry.record_restart.assert_called_once_with(ai_service.name)
        mock_registry.update_status.assert_called_once_with(
            ai_service.name, ContainerServiceStatus.STARTING
        )
        mock_registry.persist_state.assert_called_once_with(ai_service.name)

    @pytest.mark.asyncio
    async def test_restart_service_invokes_callback(
        self,
        mock_registry: MagicMock,
        mock_docker_client: AsyncMock,
        ai_service: ManagedService,
    ) -> None:
        """Test restart_service invokes on_restart callback."""
        on_restart = AsyncMock()
        manager = LifecycleManager(
            registry=mock_registry,
            docker_client=mock_docker_client,
            on_restart=on_restart,
        )

        await manager.restart_service(ai_service)

        on_restart.assert_called_once_with(ai_service)

    @pytest.mark.asyncio
    async def test_restart_service_no_callback_when_none(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
    ) -> None:
        """Test restart_service works without callback."""
        # Should not raise
        result = await lifecycle_manager.restart_service(ai_service)
        assert result is True

    @pytest.mark.asyncio
    async def test_restart_service_failure_on_stop(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
        mock_docker_client: AsyncMock,
    ) -> None:
        """Test restart_service handles stop failure."""
        mock_docker_client.stop_container.side_effect = Exception("Stop failed")

        result = await lifecycle_manager.restart_service(ai_service)

        assert result is False

    @pytest.mark.asyncio
    async def test_restart_service_failure_on_start(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
        mock_docker_client: AsyncMock,
    ) -> None:
        """Test restart_service handles start failure."""
        mock_docker_client.start_container.return_value = False

        result = await lifecycle_manager.restart_service(ai_service)

        assert result is False


# =============================================================================
# LifecycleManager.start_service() Tests
# =============================================================================


class TestStartService:
    """Tests for LifecycleManager.start_service method."""

    @pytest.mark.asyncio
    async def test_start_service_success(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
        mock_docker_client: AsyncMock,
    ) -> None:
        """Test start_service starts container."""
        result = await lifecycle_manager.start_service(ai_service)

        assert result is True
        mock_docker_client.start_container.assert_called_once_with(ai_service.container_id)

    @pytest.mark.asyncio
    async def test_start_service_failure(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
        mock_docker_client: AsyncMock,
    ) -> None:
        """Test start_service handles failure."""
        mock_docker_client.start_container.return_value = False

        result = await lifecycle_manager.start_service(ai_service)

        assert result is False


# =============================================================================
# LifecycleManager.stop_service() Tests
# =============================================================================


class TestStopService:
    """Tests for LifecycleManager.stop_service method."""

    @pytest.mark.asyncio
    async def test_stop_service_success(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
        mock_docker_client: AsyncMock,
    ) -> None:
        """Test stop_service stops container."""
        result = await lifecycle_manager.stop_service(ai_service)

        assert result is True
        mock_docker_client.stop_container.assert_called_once_with(
            ai_service.container_id, timeout=10
        )

    @pytest.mark.asyncio
    async def test_stop_service_failure(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
        mock_docker_client: AsyncMock,
    ) -> None:
        """Test stop_service handles failure."""
        mock_docker_client.stop_container.return_value = False

        result = await lifecycle_manager.stop_service(ai_service)

        assert result is False


# =============================================================================
# LifecycleManager.enable_service() Tests
# =============================================================================


class TestEnableService:
    """Tests for LifecycleManager.enable_service method."""

    @pytest.mark.asyncio
    async def test_enable_service_resets_failures(
        self,
        lifecycle_manager: LifecycleManager,
        mock_registry: MagicMock,
    ) -> None:
        """Test enable_service resets failure count."""
        mock_registry.get.return_value = MagicMock()

        result = await lifecycle_manager.enable_service("ai-yolo26")

        assert result is True
        mock_registry.reset_failures.assert_called_once_with("ai-yolo26")

    @pytest.mark.asyncio
    async def test_enable_service_sets_enabled(
        self,
        lifecycle_manager: LifecycleManager,
        mock_registry: MagicMock,
    ) -> None:
        """Test enable_service sets enabled flag."""
        mock_registry.get.return_value = MagicMock()

        await lifecycle_manager.enable_service("ai-yolo26")

        mock_registry.set_enabled.assert_called_once_with("ai-yolo26", True)

    @pytest.mark.asyncio
    async def test_enable_service_updates_status(
        self,
        lifecycle_manager: LifecycleManager,
        mock_registry: MagicMock,
    ) -> None:
        """Test enable_service updates status to STOPPED."""
        mock_registry.get.return_value = MagicMock()

        await lifecycle_manager.enable_service("ai-yolo26")

        mock_registry.update_status.assert_called_once_with(
            "ai-yolo26", ContainerServiceStatus.STOPPED
        )

    @pytest.mark.asyncio
    async def test_enable_service_persists_state(
        self,
        lifecycle_manager: LifecycleManager,
        mock_registry: MagicMock,
    ) -> None:
        """Test enable_service persists state."""
        mock_registry.get.return_value = MagicMock()

        await lifecycle_manager.enable_service("ai-yolo26")

        mock_registry.persist_state.assert_called_once_with("ai-yolo26")

    @pytest.mark.asyncio
    async def test_enable_service_not_found(
        self,
        lifecycle_manager: LifecycleManager,
        mock_registry: MagicMock,
    ) -> None:
        """Test enable_service returns False for unknown service."""
        mock_registry.get.return_value = None

        result = await lifecycle_manager.enable_service("unknown")

        assert result is False


# =============================================================================
# LifecycleManager.disable_service() Tests
# =============================================================================


class TestDisableService:
    """Tests for LifecycleManager.disable_service method."""

    @pytest.mark.asyncio
    async def test_disable_service_sets_disabled(
        self,
        lifecycle_manager: LifecycleManager,
        mock_registry: MagicMock,
    ) -> None:
        """Test disable_service sets enabled to False."""
        mock_registry.get.return_value = MagicMock()

        result = await lifecycle_manager.disable_service("ai-yolo26")

        assert result is True
        mock_registry.set_enabled.assert_called_once_with("ai-yolo26", False)

    @pytest.mark.asyncio
    async def test_disable_service_updates_status(
        self,
        lifecycle_manager: LifecycleManager,
        mock_registry: MagicMock,
    ) -> None:
        """Test disable_service updates status to DISABLED."""
        mock_registry.get.return_value = MagicMock()

        await lifecycle_manager.disable_service("ai-yolo26")

        mock_registry.update_status.assert_called_once_with(
            "ai-yolo26", ContainerServiceStatus.DISABLED
        )

    @pytest.mark.asyncio
    async def test_disable_service_persists_state(
        self,
        lifecycle_manager: LifecycleManager,
        mock_registry: MagicMock,
    ) -> None:
        """Test disable_service persists state."""
        mock_registry.get.return_value = MagicMock()

        await lifecycle_manager.disable_service("ai-yolo26")

        mock_registry.persist_state.assert_called_once_with("ai-yolo26")

    @pytest.mark.asyncio
    async def test_disable_service_not_found(
        self,
        lifecycle_manager: LifecycleManager,
        mock_registry: MagicMock,
    ) -> None:
        """Test disable_service returns False for unknown service."""
        mock_registry.get.return_value = None

        result = await lifecycle_manager.disable_service("unknown")

        assert result is False


# =============================================================================
# LifecycleManager.handle_unhealthy() Tests
# =============================================================================


class TestHandleUnhealthy:
    """Tests for LifecycleManager.handle_unhealthy method."""

    @pytest.mark.asyncio
    async def test_handle_unhealthy_increments_failure(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
        mock_registry: MagicMock,
    ) -> None:
        """Test handle_unhealthy increments failure count."""
        mock_registry.increment_failure.return_value = 1

        await lifecycle_manager.handle_unhealthy(ai_service)

        mock_registry.increment_failure.assert_called_once_with(ai_service.name)

    @pytest.mark.asyncio
    async def test_handle_unhealthy_continues_retrying_at_max_failures(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
        mock_registry: MagicMock,
        mock_docker_client: AsyncMock,
    ) -> None:
        """Test handle_unhealthy continues retrying at max_failures (never disables)."""
        mock_registry.increment_failure.return_value = ai_service.max_failures  # 5
        ai_service.failure_count = ai_service.max_failures - 1
        ai_service.last_failure_at = None  # No prior failure = can restart

        await lifecycle_manager.handle_unhealthy(ai_service)

        # Service should NOT be disabled - it continues retrying
        mock_registry.set_enabled.assert_not_called()
        # Service should be restarted (status updated to STARTING)
        mock_registry.update_status.assert_called_with(
            ai_service.name, ContainerServiceStatus.STARTING
        )

    @pytest.mark.asyncio
    async def test_handle_unhealthy_does_not_invoke_on_disabled_callback(
        self,
        mock_registry: MagicMock,
        mock_docker_client: AsyncMock,
        ai_service: ManagedService,
    ) -> None:
        """Test handle_unhealthy never invokes on_disabled callback (services retry forever)."""
        on_disabled = AsyncMock()
        manager = LifecycleManager(
            registry=mock_registry,
            docker_client=mock_docker_client,
            on_disabled=on_disabled,
        )
        mock_registry.increment_failure.return_value = ai_service.max_failures
        ai_service.failure_count = ai_service.max_failures - 1
        ai_service.last_failure_at = None

        await manager.handle_unhealthy(ai_service)

        # on_disabled should NOT be called - services retry forever
        on_disabled.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_unhealthy_restarts_if_backoff_elapsed(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
        mock_registry: MagicMock,
        mock_docker_client: AsyncMock,
    ) -> None:
        """Test handle_unhealthy restarts service if backoff elapsed."""
        mock_registry.increment_failure.return_value = 1
        ai_service.failure_count = 0
        ai_service.last_failure_at = None  # No prior failure = backoff elapsed

        await lifecycle_manager.handle_unhealthy(ai_service)

        # Should have called restart
        mock_docker_client.stop_container.assert_called_once()
        mock_docker_client.start_container.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_unhealthy_skips_restart_during_backoff(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
        mock_registry: MagicMock,
        mock_docker_client: AsyncMock,
    ) -> None:
        """Test handle_unhealthy skips restart during backoff."""
        mock_registry.increment_failure.return_value = 3
        ai_service.failure_count = 3
        # Set last failure to 1 second ago (backoff for 3 failures is 40s)
        ai_service.last_failure_at = datetime.now(UTC) - timedelta(seconds=1)

        await lifecycle_manager.handle_unhealthy(ai_service)

        # Should NOT have called restart
        mock_docker_client.stop_container.assert_not_called()
        mock_docker_client.start_container.assert_not_called()


# =============================================================================
# LifecycleManager.handle_stopped() Tests
# =============================================================================


class TestHandleStopped:
    """Tests for LifecycleManager.handle_stopped method."""

    @pytest.mark.asyncio
    async def test_handle_stopped_triggers_restart(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
        mock_docker_client: AsyncMock,
    ) -> None:
        """Test handle_stopped triggers restart if allowed."""
        ai_service.last_failure_at = None  # No backoff needed

        await lifecycle_manager.handle_stopped(ai_service)

        mock_docker_client.start_container.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_stopped_skips_disabled_service(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
        mock_docker_client: AsyncMock,
    ) -> None:
        """Test handle_stopped skips disabled services."""
        ai_service.enabled = False

        await lifecycle_manager.handle_stopped(ai_service)

        mock_docker_client.start_container.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_stopped_skips_during_backoff(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
        mock_docker_client: AsyncMock,
    ) -> None:
        """Test handle_stopped skips during backoff."""
        ai_service.failure_count = 5
        ai_service.last_failure_at = datetime.now(UTC) - timedelta(seconds=1)

        await lifecycle_manager.handle_stopped(ai_service)

        mock_docker_client.start_container.assert_not_called()


# =============================================================================
# LifecycleManager.handle_missing() Tests
# =============================================================================


class TestHandleMissing:
    """Tests for LifecycleManager.handle_missing method."""

    @pytest.mark.asyncio
    async def test_handle_missing_updates_status_to_not_found(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
        mock_registry: MagicMock,
    ) -> None:
        """Test handle_missing updates status to NOT_FOUND."""
        await lifecycle_manager.handle_missing(ai_service)

        mock_registry.update_status.assert_called_once_with(
            ai_service.name, ContainerServiceStatus.NOT_FOUND
        )

    @pytest.mark.asyncio
    async def test_handle_missing_clears_container_id(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
        mock_registry: MagicMock,
    ) -> None:
        """Test handle_missing clears container_id."""
        await lifecycle_manager.handle_missing(ai_service)

        # Container ID should be cleared in registry
        mock_registry.update_container_id.assert_called_once_with(ai_service.name, None)


# =============================================================================
# ManagedService Tests
# =============================================================================


class TestManagedService:
    """Tests for ManagedService dataclass."""

    def test_managed_service_creation(self) -> None:
        """Test ManagedService can be created with required fields."""
        service = ManagedService(
            name="test-service",
            display_name="Test Service",
            container_id="abc123",
            image="test:latest",
            port=8080,
            health_endpoint="/health",
            health_cmd=None,
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.RUNNING,
        )
        assert service.name == "test-service"
        assert service.display_name == "Test Service"
        assert service.container_id == "abc123"
        assert service.category == ServiceCategory.AI
        assert service.status == ContainerServiceStatus.RUNNING

    def test_managed_service_defaults(self) -> None:
        """Test ManagedService has expected defaults."""
        service = ManagedService(
            name="test-service",
            display_name="Test Service",
            container_id=None,
            image="test:latest",
            port=8080,
            health_endpoint=None,
            health_cmd=None,
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.STOPPED,
        )
        assert service.enabled is True
        assert service.failure_count == 0
        assert service.restart_count == 0
        assert service.max_failures == 5  # AI default
        assert service.restart_backoff_base == 5.0  # AI default
        assert service.restart_backoff_max == 300.0  # AI default

    def test_managed_service_infrastructure_defaults(self) -> None:
        """Test infrastructure service has correct defaults."""
        service = ManagedService(
            name="postgres",
            display_name="PostgreSQL",
            container_id=None,
            image="postgres:16",
            port=5432,
            health_endpoint=None,
            health_cmd="pg_isready -U security",
            category=ServiceCategory.INFRASTRUCTURE,
            status=ContainerServiceStatus.STOPPED,
            max_failures=10,
            restart_backoff_base=2.0,
            restart_backoff_max=60.0,
        )
        assert service.max_failures == 10
        assert service.restart_backoff_base == 2.0
        assert service.restart_backoff_max == 60.0

    def test_managed_service_monitoring_defaults(self) -> None:
        """Test monitoring service has correct defaults."""
        service = ManagedService(
            name="grafana",
            display_name="Grafana",
            container_id=None,
            image="grafana/grafana:10",
            port=3000,
            health_endpoint="/api/health",
            health_cmd=None,
            category=ServiceCategory.MONITORING,
            status=ContainerServiceStatus.STOPPED,
            max_failures=3,
            restart_backoff_base=10.0,
            restart_backoff_max=600.0,
        )
        assert service.max_failures == 3
        assert service.restart_backoff_base == 10.0
        assert service.restart_backoff_max == 600.0


# =============================================================================
# ServiceRegistry Tests
# =============================================================================


class TestServiceRegistry:
    """Tests for ServiceRegistry class."""

    def test_register_service(self) -> None:
        """Test registering a service."""
        registry = ServiceRegistry()
        service = ManagedService(
            name="test",
            display_name="Test",
            container_id="abc",
            image="test:latest",
            port=8080,
            health_endpoint="/health",
            health_cmd=None,
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.RUNNING,
        )

        registry.register(service)

        assert registry.get("test") is service

    def test_get_nonexistent_service(self) -> None:
        """Test getting a nonexistent service returns None."""
        registry = ServiceRegistry()
        assert registry.get("unknown") is None

    def test_record_restart_updates_tracking(self) -> None:
        """Test record_restart updates restart tracking."""
        registry = ServiceRegistry()
        service = ManagedService(
            name="test",
            display_name="Test",
            container_id="abc",
            image="test:latest",
            port=8080,
            health_endpoint="/health",
            health_cmd=None,
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.RUNNING,
        )
        registry.register(service)

        registry.record_restart("test")

        assert service.restart_count == 1
        assert service.last_restart_at is not None

    def test_increment_failure_returns_new_count(self) -> None:
        """Test increment_failure returns updated count."""
        registry = ServiceRegistry()
        service = ManagedService(
            name="test",
            display_name="Test",
            container_id="abc",
            image="test:latest",
            port=8080,
            health_endpoint="/health",
            health_cmd=None,
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.RUNNING,
        )
        registry.register(service)

        result = registry.increment_failure("test")

        assert result == 1
        assert service.failure_count == 1

    def test_reset_failures_clears_failure_count(self) -> None:
        """Test reset_failures clears failure tracking."""
        registry = ServiceRegistry()
        service = ManagedService(
            name="test",
            display_name="Test",
            container_id="abc",
            image="test:latest",
            port=8080,
            health_endpoint="/health",
            health_cmd=None,
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.RUNNING,
            failure_count=5,
        )
        registry.register(service)

        registry.reset_failures("test")

        assert service.failure_count == 0
        assert service.last_failure_at is None

    def test_update_status_changes_status(self) -> None:
        """Test update_status changes service status."""
        registry = ServiceRegistry()
        service = ManagedService(
            name="test",
            display_name="Test",
            container_id="abc",
            image="test:latest",
            port=8080,
            health_endpoint="/health",
            health_cmd=None,
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.RUNNING,
        )
        registry.register(service)

        registry.update_status("test", ContainerServiceStatus.UNHEALTHY)

        assert service.status == ContainerServiceStatus.UNHEALTHY

    def test_set_enabled_toggles_flag(self) -> None:
        """Test set_enabled toggles enabled flag."""
        registry = ServiceRegistry()
        service = ManagedService(
            name="test",
            display_name="Test",
            container_id="abc",
            image="test:latest",
            port=8080,
            health_endpoint="/health",
            health_cmd=None,
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.RUNNING,
        )
        registry.register(service)

        registry.set_enabled("test", False)
        assert service.enabled is False

        registry.set_enabled("test", True)
        assert service.enabled is True

    def test_get_enabled_services(self) -> None:
        """Test get_enabled_services returns only enabled services."""
        registry = ServiceRegistry()
        service1 = ManagedService(
            name="enabled",
            display_name="Enabled",
            container_id="abc",
            image="test:latest",
            port=8080,
            health_endpoint="/health",
            health_cmd=None,
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.RUNNING,
            enabled=True,
        )
        service2 = ManagedService(
            name="disabled",
            display_name="Disabled",
            container_id="def",
            image="test:latest",
            port=8081,
            health_endpoint="/health",
            health_cmd=None,
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.DISABLED,
            enabled=False,
        )
        registry.register(service1)
        registry.register(service2)

        enabled = registry.get_enabled_services()

        assert len(enabled) == 1
        assert enabled[0].name == "enabled"

    @pytest.mark.asyncio
    async def test_persist_state(self) -> None:
        """Test persist_state saves service state."""
        # This will need mocked Redis
        registry = ServiceRegistry()
        service = ManagedService(
            name="test",
            display_name="Test",
            container_id="abc",
            image="test:latest",
            port=8080,
            health_endpoint="/health",
            health_cmd=None,
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.RUNNING,
        )
        registry.register(service)

        # Should not raise
        await registry.persist_state("test")

    @pytest.mark.asyncio
    async def test_load_state(self) -> None:
        """Test load_state restores service state from Redis.

        Note: The new shared ServiceRegistry.load_state requires a service name,
        use load_all_state() to load all services.
        """
        # This will need mocked Redis
        registry = ServiceRegistry()

        # Should not raise (no-op without Redis client)
        await registry.load_all_state()


# =============================================================================
# Category Defaults Tests
# =============================================================================


class TestCategoryDefaults:
    """Tests for category-specific default values."""

    def test_infrastructure_defaults_in_service(
        self, infrastructure_service: ManagedService
    ) -> None:
        """Test infrastructure service has correct category defaults."""
        assert infrastructure_service.max_failures == 10
        assert infrastructure_service.restart_backoff_base == 2.0
        assert infrastructure_service.restart_backoff_max == 60.0

    def test_ai_defaults_in_service(self, ai_service: ManagedService) -> None:
        """Test AI service has correct category defaults."""
        assert ai_service.max_failures == 5
        assert ai_service.restart_backoff_base == 5.0
        assert ai_service.restart_backoff_max == 300.0

    def test_monitoring_defaults_in_service(self, monitoring_service: ManagedService) -> None:
        """Test monitoring service has correct category defaults."""
        assert monitoring_service.max_failures == 3
        assert monitoring_service.restart_backoff_base == 10.0
        assert monitoring_service.restart_backoff_max == 600.0


# =============================================================================
# Manual Restart Tests
# =============================================================================


class TestManualRestart:
    """Tests for manual restart behavior."""

    @pytest.mark.asyncio
    async def test_manual_restart_resets_failures(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
        mock_registry: MagicMock,
    ) -> None:
        """Test that manual restart properly resets failure count before restart."""
        ai_service.failure_count = 3
        ai_service.last_failure_at = datetime.now(UTC)

        # Simulate a manual restart with reset
        mock_registry.reset_failures.return_value = None

        # The enable_service method resets failures
        mock_registry.get.return_value = ai_service
        await lifecycle_manager.enable_service(ai_service.name)

        mock_registry.reset_failures.assert_called_with(ai_service.name)

    @pytest.mark.asyncio
    async def test_restart_sets_status_to_starting(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
        mock_registry: MagicMock,
    ) -> None:
        """Test that restart sets status to STARTING."""
        await lifecycle_manager.restart_service(ai_service)

        mock_registry.update_status.assert_called_once_with(
            ai_service.name, ContainerServiceStatus.STARTING
        )

    @pytest.mark.asyncio
    async def test_restart_increments_restart_count(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
        mock_registry: MagicMock,
    ) -> None:
        """Test that restart increments restart_count."""
        await lifecycle_manager.restart_service(ai_service)

        mock_registry.record_restart.assert_called_once_with(ai_service.name)


# =============================================================================
# Backoff Boundary Tests
# =============================================================================


class TestBackoffBoundaries:
    """Tests for backoff boundary conditions."""

    def test_backoff_at_exactly_max(self) -> None:
        """Test backoff equals max at the exact boundary."""
        # For base=5, max=300:
        # 5 * 2^6 = 320, which exceeds 300
        result = calculate_backoff(failure_count=6, base=5.0, max_backoff=300.0)
        assert result == 300.0

    def test_backoff_just_below_max(self) -> None:
        """Test backoff just below max."""
        # For base=5, max=300:
        # 5 * 2^5 = 160, which is below 300
        result = calculate_backoff(failure_count=5, base=5.0, max_backoff=300.0)
        assert result == 160.0

    def test_backoff_infrastructure_sequence(self) -> None:
        """Test infrastructure backoff sequence: 2, 4, 8, 16, 32, 60 (capped)."""
        expected = [2.0, 4.0, 8.0, 16.0, 32.0, 60.0, 60.0]
        for i, exp in enumerate(expected):
            result = calculate_backoff(failure_count=i, base=2.0, max_backoff=60.0)
            assert result == exp, f"Failed at failure_count={i}"

    def test_backoff_ai_sequence(self) -> None:
        """Test AI backoff sequence: 5, 10, 20, 40, 80, 160, 300 (capped)."""
        expected = [5.0, 10.0, 20.0, 40.0, 80.0, 160.0, 300.0]
        for i, exp in enumerate(expected):
            result = calculate_backoff(failure_count=i, base=5.0, max_backoff=300.0)
            assert result == exp, f"Failed at failure_count={i}"

    def test_backoff_monitoring_sequence(self) -> None:
        """Test monitoring backoff sequence: 10, 20, 40, 80, 160, 320 -> 600 (capped)."""
        expected = [10.0, 20.0, 40.0, 80.0, 160.0, 320.0, 600.0]
        for i, exp in enumerate(expected):
            result = calculate_backoff(failure_count=i, base=10.0, max_backoff=600.0)
            # At i=5, 10*2^5=320, which is below 600
            # At i=6, 10*2^6=640, capped at 600
            if i == 5:
                assert result == 320.0
            elif i == 6:
                assert result == 600.0
            else:
                assert result == exp, f"Failed at failure_count={i}"


# =============================================================================
# Self-Healing Integration Tests
# =============================================================================


class TestSelfHealingIntegration:
    """Integration tests for self-healing behavior."""

    @pytest.mark.asyncio
    async def test_service_continues_retrying_at_max_failures(
        self,
        mock_registry: MagicMock,
        mock_docker_client: AsyncMock,
        ai_service: ManagedService,
    ) -> None:
        """Test service continues retrying at max failures (never auto-disabled)."""
        on_disabled = AsyncMock()
        manager = LifecycleManager(
            registry=mock_registry,
            docker_client=mock_docker_client,
            on_disabled=on_disabled,
        )

        # Set failure count to just below max
        ai_service.failure_count = ai_service.max_failures - 1  # 4
        ai_service.last_failure_at = None  # No prior failure = can restart
        mock_registry.increment_failure.return_value = ai_service.max_failures  # 5

        await manager.handle_unhealthy(ai_service)

        # Service should NOT be disabled - it continues retrying with backoff
        mock_registry.set_enabled.assert_not_called()

        # Service should be restarted
        mock_registry.update_status.assert_called_with(
            ai_service.name, ContainerServiceStatus.STARTING
        )

        # on_disabled callback should NOT be invoked
        on_disabled.assert_not_called()

    @pytest.mark.asyncio
    async def test_service_restarted_when_backoff_elapsed(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
        mock_docker_client: AsyncMock,
        mock_registry: MagicMock,
    ) -> None:
        """Test service is restarted when backoff has elapsed."""
        # Set up service with elapsed backoff
        ai_service.failure_count = 1
        ai_service.last_failure_at = None  # No prior failure = backoff elapsed

        mock_registry.increment_failure.return_value = 1

        await lifecycle_manager.handle_unhealthy(ai_service)

        # Should have triggered restart
        mock_docker_client.stop_container.assert_called_once()
        mock_docker_client.start_container.assert_called_once()

    @pytest.mark.asyncio
    async def test_service_not_restarted_during_backoff(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
        mock_docker_client: AsyncMock,
        mock_registry: MagicMock,
    ) -> None:
        """Test service is not restarted during backoff period."""
        # Set up service in backoff
        ai_service.failure_count = 3
        ai_service.last_failure_at = datetime.now(UTC) - timedelta(seconds=1)  # 1 second ago

        mock_registry.increment_failure.return_value = 4

        await lifecycle_manager.handle_unhealthy(ai_service)

        # Should NOT have triggered restart (backoff for 3 failures is 40s)
        mock_docker_client.stop_container.assert_not_called()
        mock_docker_client.start_container.assert_not_called()

    @pytest.mark.asyncio
    async def test_backoff_remaining_calculation(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
    ) -> None:
        """Test backoff remaining is calculated correctly."""
        ai_service.failure_count = 2  # Backoff = 20s
        ai_service.last_failure_at = datetime.now(UTC) - timedelta(seconds=5)  # 5 seconds ago

        remaining = lifecycle_manager.backoff_remaining(ai_service)

        # Should be approximately 15 seconds remaining
        assert 14.0 <= remaining <= 16.0

    @pytest.mark.asyncio
    async def test_should_restart_returns_false_for_disabled(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
    ) -> None:
        """Test should_restart returns False for disabled service."""
        ai_service.enabled = False

        assert lifecycle_manager.should_restart(ai_service) is False

    @pytest.mark.asyncio
    async def test_should_restart_returns_true_at_max_failures(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
    ) -> None:
        """Test should_restart returns True even at max failures (services retry forever)."""
        ai_service.failure_count = ai_service.max_failures
        ai_service.last_failure_at = None  # No prior failure = backoff elapsed

        assert lifecycle_manager.should_restart(ai_service) is True

    @pytest.mark.asyncio
    async def test_should_restart_returns_true_when_backoff_elapsed(
        self,
        lifecycle_manager: LifecycleManager,
        ai_service: ManagedService,
    ) -> None:
        """Test should_restart returns True when backoff has elapsed."""
        ai_service.failure_count = 1
        ai_service.last_failure_at = datetime.now(UTC) - timedelta(
            seconds=60
        )  # 60s ago, backoff is 10s

        assert lifecycle_manager.should_restart(ai_service) is True
