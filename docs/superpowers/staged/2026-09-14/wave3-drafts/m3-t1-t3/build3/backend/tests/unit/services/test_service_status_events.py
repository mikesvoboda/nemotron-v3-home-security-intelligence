"""Unit tests for service status WebSocket events.

Tests cover:
- create_service_status_event creates valid event structure
- event type is "service_status"
- event data contains ServiceInfo fields
- event message is included
- uptime_seconds is calculated for running services
- uptime_seconds is None for non-running services
- container_id is truncated to 12 chars
- Orchestrator broadcasts on health recovery
- Orchestrator broadcasts on health failure
- Orchestrator broadcasts on restart
- Orchestrator broadcasts on disable
- No broadcast when broadcast_fn is None

TDD: These tests define the expected behavior for service status WebSocket events.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.schemas.services import ContainerServiceStatus, ServiceCategory
from backend.services.container_orchestrator import (
    ContainerOrchestrator,
    create_service_status_event,
)
from backend.services.health_monitor_orchestrator import (
    ManagedService as HealthMonitorService,
)
from backend.services.lifecycle_manager import ManagedService as LifecycleService
from backend.services.service_registry import ManagedService

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def running_service() -> ManagedService:
    """Create a running service with recent restart."""
    return ManagedService(
        name="ai-yolo26",
        display_name="YOLO26",
        container_id="abcdef123456789",
        image="ghcr.io/example/yolo26:latest",
        port=8095,
        health_endpoint="/health",
        health_cmd=None,
        category=ServiceCategory.AI,
        status=ContainerServiceStatus.RUNNING,
        enabled=True,
        failure_count=0,
        restart_count=2,
        last_restart_at=datetime.now(UTC) - timedelta(hours=1),
    )


@pytest.fixture
def stopped_service() -> ManagedService:
    """Create a stopped service."""
    return ManagedService(
        name="postgres",
        display_name="PostgreSQL",
        container_id="xyz789012345678",
        image="postgres:16-alpine",
        port=5432,
        health_endpoint=None,
        health_cmd="pg_isready -U security",
        category=ServiceCategory.INFRASTRUCTURE,
        status=ContainerServiceStatus.STOPPED,
        enabled=True,
        failure_count=2,
        restart_count=0,
        last_restart_at=None,
    )


@pytest.fixture
def service_without_container() -> ManagedService:
    """Create a service with no container_id."""
    return ManagedService(
        name="grafana",
        display_name="Grafana",
        container_id=None,
        image="grafana/grafana:10.2.3",
        port=3000,
        health_endpoint="/api/health",
        health_cmd=None,
        category=ServiceCategory.MONITORING,
        status=ContainerServiceStatus.NOT_FOUND,
        enabled=True,
        failure_count=0,
        restart_count=0,
        last_restart_at=None,
    )


@pytest.fixture
def hm_running_service() -> HealthMonitorService:
    """Create a HealthMonitorService for testing callbacks."""
    return HealthMonitorService(
        name="ai-yolo26",
        display_name="YOLO26",
        container_id="abcdef123456789",
        image="ghcr.io/example/yolo26:latest",
        port=8095,
        category=ServiceCategory.AI,
        health_endpoint="/health",
        status=ContainerServiceStatus.RUNNING,
        enabled=True,
        failure_count=0,
        restart_count=2,
        last_restart_at=datetime.now(UTC) - timedelta(hours=1),
    )


@pytest.fixture
def lm_running_service() -> LifecycleService:
    """Create a LifecycleService for testing callbacks."""
    return LifecycleService(
        name="ai-yolo26",
        display_name="YOLO26",
        container_id="abcdef123456789",
        image="ghcr.io/example/yolo26:latest",
        port=8095,
        health_endpoint="/health",
        category=ServiceCategory.AI,
        status=ContainerServiceStatus.RUNNING,
        enabled=True,
        failure_count=0,
        restart_count=2,
        last_restart_at=datetime.now(UTC) - timedelta(hours=1),
    )


@pytest.fixture
def mock_docker_client() -> AsyncMock:
    """Create a mock DockerClient."""
    client = AsyncMock()
    client.connect = AsyncMock(return_value=True)
    client.stop_container = AsyncMock(return_value=True)
    client.start_container = AsyncMock(return_value=True)
    client.restart_container = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_redis_client() -> AsyncMock:
    """Create a mock RedisClient."""
    client = AsyncMock()
    client.set = AsyncMock(return_value=True)
    client.get = AsyncMock(return_value=None)
    client.delete = AsyncMock(return_value=True)
    return client


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock OrchestratorSettings."""
    settings = MagicMock()
    settings.enabled = True
    settings.health_check_interval = 30
    settings.health_check_timeout = 5
    return settings


# =============================================================================
# create_service_status_event() Tests
# =============================================================================


class TestCreateServiceStatusEvent:
    """Tests for the create_service_status_event helper function."""

    def test_creates_valid_event_structure(self, running_service: ManagedService) -> None:
        """Test that event has correct structure with type, data, message."""
        event = create_service_status_event(running_service, "Service recovered")

        assert "type" in event
        assert "data" in event
        assert "message" in event

    def test_event_type_is_service_status(self, running_service: ManagedService) -> None:
        """Test that event type is 'service_status'."""
        event = create_service_status_event(running_service, "Test message")

        assert event["type"] == "service_status"

    def test_event_data_contains_service_info_fields(self, running_service: ManagedService) -> None:
        """Test that event data contains all ServiceInfo fields."""
        event = create_service_status_event(running_service, "Test message")
        data = event["data"]

        assert data["name"] == "ai-yolo26"
        assert data["display_name"] == "YOLO26"
        assert data["category"] == "ai"
        assert data["status"] == "running"
        assert data["enabled"] is True
        assert data["port"] == 8095
        assert data["failure_count"] == 0
        assert data["restart_count"] == 2
        assert data["image"] == "ghcr.io/example/yolo26:latest"

    def test_event_message_is_included(self, running_service: ManagedService) -> None:
        """Test that message is included in event."""
        event = create_service_status_event(running_service, "Service recovered")

        assert event["message"] == "Service recovered"

    def test_uptime_seconds_calculated_for_running_services(
        self, running_service: ManagedService
    ) -> None:
        """Test uptime_seconds is calculated for running services with last_restart_at."""
        event = create_service_status_event(running_service, "Status update")
        data = event["data"]

        # Service was restarted 1 hour ago
        assert data["uptime_seconds"] is not None
        # Allow some tolerance for test execution time
        assert 3590 <= data["uptime_seconds"] <= 3610  # ~1 hour

    def test_uptime_seconds_none_for_non_running_services(
        self, stopped_service: ManagedService
    ) -> None:
        """Test uptime_seconds is None for non-running services."""
        event = create_service_status_event(stopped_service, "Status update")
        data = event["data"]

        assert data["uptime_seconds"] is None

    def test_uptime_seconds_none_when_no_last_restart_at(
        self, running_service: ManagedService
    ) -> None:
        """Test uptime_seconds is None when last_restart_at is None."""
        running_service.last_restart_at = None
        event = create_service_status_event(running_service, "Status update")
        data = event["data"]

        assert data["uptime_seconds"] is None

    def test_container_id_truncated_to_12_chars(self, running_service: ManagedService) -> None:
        """Test container_id is truncated to first 12 characters."""
        event = create_service_status_event(running_service, "Status update")
        data = event["data"]

        assert data["container_id"] == "abcdef123456"
        assert len(data["container_id"]) == 12

    def test_container_id_none_when_no_container(
        self, service_without_container: ManagedService
    ) -> None:
        """Test container_id is None when service has no container."""
        event = create_service_status_event(service_without_container, "Status update")
        data = event["data"]

        assert data["container_id"] is None

    def test_event_is_json_serializable(self, running_service: ManagedService) -> None:
        """Test that event can be serialized to JSON (model_dump mode='json')."""
        import json

        event = create_service_status_event(running_service, "Test message")

        # Should not raise
        json_str = json.dumps(event)
        assert isinstance(json_str, str)

    def test_last_restart_at_is_iso_format_string(self, running_service: ManagedService) -> None:
        """Test that last_restart_at is serialized as ISO format string."""
        event = create_service_status_event(running_service, "Test message")
        data = event["data"]

        # Should be a string in ISO format
        assert isinstance(data["last_restart_at"], str)
        # Should be parseable as datetime
        datetime.fromisoformat(data["last_restart_at"].replace("Z", "+00:00"))


# =============================================================================
# ContainerOrchestrator Broadcast Tests
# =============================================================================


class TestContainerOrchestratorBroadcast:
    """Tests for ContainerOrchestrator WebSocket broadcasting."""

    @pytest.mark.asyncio
    async def test_broadcasts_on_health_recovery(
        self,
        mock_docker_client: AsyncMock,
        mock_redis_client: AsyncMock,
        mock_settings: MagicMock,
        running_service: ManagedService,
        hm_running_service: HealthMonitorService,
    ) -> None:
        """Test that orchestrator broadcasts when service recovers."""
        broadcast_fn = AsyncMock(return_value=1)

        with patch.object(ContainerOrchestrator, "__init__", lambda _self, **_kw: None):
            orchestrator = ContainerOrchestrator.__new__(ContainerOrchestrator)
            orchestrator._broadcast_fn = broadcast_fn
            orchestrator._registry = MagicMock()
            orchestrator._registry.get.return_value = running_service
            orchestrator._hm_registry = None
            orchestrator._lifecycle_manager = None
            orchestrator._lm_registry = None

            await orchestrator._on_health_change(hm_running_service, True)

            broadcast_fn.assert_called_once()
            event = broadcast_fn.call_args[0][0]
            assert event["type"] == "service_status"
            assert event["message"] == "Service recovered"
            assert event["data"]["name"] == "ai-yolo26"

    @pytest.mark.asyncio
    async def test_broadcasts_on_health_failure(
        self,
        mock_docker_client: AsyncMock,
        mock_redis_client: AsyncMock,
        mock_settings: MagicMock,
        running_service: ManagedService,
        hm_running_service: HealthMonitorService,
    ) -> None:
        """Test that orchestrator broadcasts when health check fails."""
        broadcast_fn = AsyncMock(return_value=1)

        with patch.object(ContainerOrchestrator, "__init__", lambda _self, **_kw: None):
            orchestrator = ContainerOrchestrator.__new__(ContainerOrchestrator)
            orchestrator._broadcast_fn = broadcast_fn
            orchestrator._registry = MagicMock()
            orchestrator._registry.get.return_value = running_service
            orchestrator._hm_registry = None
            orchestrator._lifecycle_manager = None
            orchestrator._lm_registry = None

            await orchestrator._on_health_change(hm_running_service, False)

            broadcast_fn.assert_called_once()
            event = broadcast_fn.call_args[0][0]
            assert event["message"] == "Health check failed"

    @pytest.mark.asyncio
    async def test_broadcasts_on_restart(
        self,
        mock_docker_client: AsyncMock,
        mock_redis_client: AsyncMock,
        mock_settings: MagicMock,
        running_service: ManagedService,
        lm_running_service: LifecycleService,
    ) -> None:
        """Test that orchestrator broadcasts after restart."""
        broadcast_fn = AsyncMock(return_value=1)

        with patch.object(ContainerOrchestrator, "__init__", lambda _self, **_kw: None):
            orchestrator = ContainerOrchestrator.__new__(ContainerOrchestrator)
            orchestrator._broadcast_fn = broadcast_fn
            orchestrator._registry = MagicMock()
            orchestrator._registry.get.return_value = running_service
            orchestrator._lm_registry = None

            await orchestrator._on_restart(lm_running_service)

            broadcast_fn.assert_called_once()
            event = broadcast_fn.call_args[0][0]
            assert event["message"] == "Restart completed"

    @pytest.mark.asyncio
    async def test_broadcasts_on_disable(
        self,
        mock_docker_client: AsyncMock,
        mock_redis_client: AsyncMock,
        mock_settings: MagicMock,
        running_service: ManagedService,
        lm_running_service: LifecycleService,
    ) -> None:
        """Test that orchestrator broadcasts when service is disabled."""
        broadcast_fn = AsyncMock(return_value=1)

        with patch.object(ContainerOrchestrator, "__init__", lambda _self, **_kw: None):
            orchestrator = ContainerOrchestrator.__new__(ContainerOrchestrator)
            orchestrator._broadcast_fn = broadcast_fn
            orchestrator._registry = MagicMock()
            orchestrator._registry.get.return_value = running_service
            orchestrator._lm_registry = None

            await orchestrator._on_disabled(lm_running_service)

            broadcast_fn.assert_called_once()
            event = broadcast_fn.call_args[0][0]
            assert event["message"] == "Service disabled - max failures reached"

    @pytest.mark.asyncio
    async def test_broadcasts_on_service_discovered(
        self,
        mock_docker_client: AsyncMock,
        mock_redis_client: AsyncMock,
        mock_settings: MagicMock,
        running_service: ManagedService,
    ) -> None:
        """Test that orchestrator broadcasts when service is discovered."""
        broadcast_fn = AsyncMock(return_value=1)

        with patch.object(ContainerOrchestrator, "__init__", lambda _self, **_kw: None):
            orchestrator = ContainerOrchestrator.__new__(ContainerOrchestrator)
            orchestrator._broadcast_fn = broadcast_fn

            await orchestrator._on_service_discovered(running_service)

            broadcast_fn.assert_called_once()
            event = broadcast_fn.call_args[0][0]
            assert event["message"] == "Service discovered"

    @pytest.mark.asyncio
    async def test_no_broadcast_when_broadcast_fn_is_none(
        self,
        mock_docker_client: AsyncMock,
        mock_redis_client: AsyncMock,
        mock_settings: MagicMock,
        running_service: ManagedService,
        hm_running_service: HealthMonitorService,
        lm_running_service: LifecycleService,
    ) -> None:
        """Test that no error occurs when broadcast_fn is None."""
        with patch.object(ContainerOrchestrator, "__init__", lambda _self, **_kw: None):
            orchestrator = ContainerOrchestrator.__new__(ContainerOrchestrator)
            orchestrator._broadcast_fn = None
            orchestrator._registry = MagicMock()
            orchestrator._registry.get.return_value = running_service
            orchestrator._hm_registry = None
            orchestrator._lifecycle_manager = None
            orchestrator._lm_registry = None

            # Should not raise any exception
            await orchestrator._on_health_change(hm_running_service, True)
            await orchestrator._on_health_change(hm_running_service, False)
            await orchestrator._on_restart(lm_running_service)
            await orchestrator._on_disabled(lm_running_service)
            await orchestrator._on_service_discovered(running_service)

    @pytest.mark.asyncio
    async def test_broadcast_failure_is_logged_not_raised(
        self,
        mock_docker_client: AsyncMock,
        mock_redis_client: AsyncMock,
        mock_settings: MagicMock,
        running_service: ManagedService,
        hm_running_service: HealthMonitorService,
    ) -> None:
        """Test that broadcast failure is logged but doesn't raise."""
        broadcast_fn = AsyncMock(side_effect=Exception("Redis connection failed"))

        with patch.object(ContainerOrchestrator, "__init__", lambda _self, **_kw: None):
            orchestrator = ContainerOrchestrator.__new__(ContainerOrchestrator)
            orchestrator._broadcast_fn = broadcast_fn
            orchestrator._registry = MagicMock()
            orchestrator._registry.get.return_value = running_service
            orchestrator._hm_registry = None
            orchestrator._lifecycle_manager = None
            orchestrator._lm_registry = None

            # Should not raise any exception
            await orchestrator._on_health_change(hm_running_service, True)


# =============================================================================
# ContainerOrchestrator Service Actions Tests
# =============================================================================


class TestContainerOrchestratorServiceActions:
    """Tests for ContainerOrchestrator service action methods."""

    @pytest.mark.asyncio
    async def test_enable_service_broadcasts_status(
        self,
        mock_docker_client: AsyncMock,
        mock_redis_client: AsyncMock,
        mock_settings: MagicMock,
        stopped_service: ManagedService,
    ) -> None:
        """Test that enable_service broadcasts status change."""
        broadcast_fn = AsyncMock(return_value=1)

        with patch.object(ContainerOrchestrator, "__init__", lambda _self, **_kw: None):
            orchestrator = ContainerOrchestrator.__new__(ContainerOrchestrator)
            orchestrator._broadcast_fn = broadcast_fn
            orchestrator._registry = MagicMock()
            orchestrator._registry.get.return_value = stopped_service
            orchestrator._registry.reset_failures = MagicMock()
            orchestrator._registry.set_enabled = MagicMock()
            orchestrator._registry.update_status = MagicMock()
            orchestrator._registry.persist_state = AsyncMock()
            orchestrator._lifecycle_manager = None
            orchestrator._lm_registry = None

            result = await orchestrator.enable_service("postgres")

            assert result is True
            broadcast_fn.assert_called_once()
            event = broadcast_fn.call_args[0][0]
            assert event["message"] == "Service enabled"

    @pytest.mark.asyncio
    async def test_disable_service_broadcasts_status(
        self,
        mock_docker_client: AsyncMock,
        mock_redis_client: AsyncMock,
        mock_settings: MagicMock,
        running_service: ManagedService,
    ) -> None:
        """Test that disable_service broadcasts status change."""
        broadcast_fn = AsyncMock(return_value=1)

        with patch.object(ContainerOrchestrator, "__init__", lambda _self, **_kw: None):
            orchestrator = ContainerOrchestrator.__new__(ContainerOrchestrator)
            orchestrator._broadcast_fn = broadcast_fn
            orchestrator._registry = MagicMock()
            orchestrator._registry.get.return_value = running_service
            orchestrator._registry.set_enabled = MagicMock()
            orchestrator._registry.update_status = MagicMock()
            orchestrator._registry.persist_state = AsyncMock()
            orchestrator._lifecycle_manager = None
            orchestrator._lm_registry = None

            result = await orchestrator.disable_service("ai-yolo26")

            assert result is True
            broadcast_fn.assert_called_once()
            event = broadcast_fn.call_args[0][0]
            assert event["message"] == "Service disabled"

    @pytest.mark.asyncio
    async def test_restart_service_broadcasts_initiated_and_success(
        self,
        mock_docker_client: AsyncMock,
        mock_redis_client: AsyncMock,
        mock_settings: MagicMock,
        running_service: ManagedService,
    ) -> None:
        """Test that restart_service broadcasts both initiated and success."""
        broadcast_fn = AsyncMock(return_value=1)

        with patch.object(ContainerOrchestrator, "__init__", lambda _self, **_kw: None):
            orchestrator = ContainerOrchestrator.__new__(ContainerOrchestrator)
            orchestrator._broadcast_fn = broadcast_fn
            orchestrator._registry = MagicMock()
            orchestrator._registry.get.return_value = running_service
            orchestrator._registry.record_restart = MagicMock()
            orchestrator._registry.update_status = MagicMock()
            orchestrator._registry.persist_state = AsyncMock()
            orchestrator._lifecycle_manager = None
            orchestrator._lm_registry = None
            orchestrator._docker_client = mock_docker_client

            result = await orchestrator.restart_service("ai-yolo26")

            assert result is True
            assert broadcast_fn.call_count == 2

            # First call: restart initiated
            first_event = broadcast_fn.call_args_list[0][0][0]
            assert first_event["message"] == "Manual restart initiated"

            # Second call: restart succeeded
            second_event = broadcast_fn.call_args_list[1][0][0]
            assert second_event["message"] == "Restart succeeded"

    @pytest.mark.asyncio
    async def test_restart_service_broadcasts_failure(
        self,
        mock_docker_client: AsyncMock,
        mock_redis_client: AsyncMock,
        mock_settings: MagicMock,
        running_service: ManagedService,
    ) -> None:
        """Test that restart_service broadcasts failure when restart fails."""
        broadcast_fn = AsyncMock(return_value=1)
        mock_docker_client.restart_container = AsyncMock(return_value=False)

        with patch.object(ContainerOrchestrator, "__init__", lambda _self, **_kw: None):
            orchestrator = ContainerOrchestrator.__new__(ContainerOrchestrator)
            orchestrator._broadcast_fn = broadcast_fn
            orchestrator._registry = MagicMock()
            orchestrator._registry.get.return_value = running_service
            orchestrator._lifecycle_manager = None
            orchestrator._lm_registry = None
            orchestrator._docker_client = mock_docker_client

            result = await orchestrator.restart_service("ai-yolo26")

            assert result is False
            assert broadcast_fn.call_count == 2

            # Second call: restart failed
            second_event = broadcast_fn.call_args_list[1][0][0]
            assert second_event["message"] == "Restart failed"

    @pytest.mark.asyncio
    async def test_start_service_broadcasts_status(
        self,
        mock_docker_client: AsyncMock,
        mock_redis_client: AsyncMock,
        mock_settings: MagicMock,
        stopped_service: ManagedService,
    ) -> None:
        """Test that start_service broadcasts status change."""
        broadcast_fn = AsyncMock(return_value=1)

        with patch.object(ContainerOrchestrator, "__init__", lambda _self, **_kw: None):
            orchestrator = ContainerOrchestrator.__new__(ContainerOrchestrator)
            orchestrator._broadcast_fn = broadcast_fn
            orchestrator._registry = MagicMock()
            orchestrator._registry.get.return_value = stopped_service
            orchestrator._registry.update_status = MagicMock()
            orchestrator._registry.persist_state = AsyncMock()
            orchestrator._lifecycle_manager = None
            orchestrator._lm_registry = None
            orchestrator._docker_client = mock_docker_client

            result = await orchestrator.start_service("postgres")

            assert result is True
            broadcast_fn.assert_called_once()
            event = broadcast_fn.call_args[0][0]
            assert event["message"] == "Service started"

    @pytest.mark.asyncio
    async def test_restart_unknown_service_returns_false(
        self,
        mock_docker_client: AsyncMock,
        mock_redis_client: AsyncMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test that restart_service returns False for unknown service."""
        with patch.object(ContainerOrchestrator, "__init__", lambda _self, **_kw: None):
            orchestrator = ContainerOrchestrator.__new__(ContainerOrchestrator)
            orchestrator._broadcast_fn = AsyncMock(return_value=1)
            orchestrator._registry = MagicMock()
            orchestrator._registry.get.return_value = None
            orchestrator._lifecycle_manager = None
            orchestrator._lm_registry = None

            result = await orchestrator.restart_service("unknown")

            assert result is False

    @pytest.mark.asyncio
    async def test_enable_unknown_service_returns_false(
        self,
        mock_docker_client: AsyncMock,
        mock_redis_client: AsyncMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test that enable_service returns False for unknown service."""
        with patch.object(ContainerOrchestrator, "__init__", lambda _self, **_kw: None):
            orchestrator = ContainerOrchestrator.__new__(ContainerOrchestrator)
            orchestrator._registry = MagicMock()
            orchestrator._registry.get.return_value = None

            result = await orchestrator.enable_service("unknown")

            assert result is False

    @pytest.mark.asyncio
    async def test_disable_unknown_service_returns_false(
        self,
        mock_docker_client: AsyncMock,
        mock_redis_client: AsyncMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test that disable_service returns False for unknown service."""
        with patch.object(ContainerOrchestrator, "__init__", lambda _self, **_kw: None):
            orchestrator = ContainerOrchestrator.__new__(ContainerOrchestrator)
            orchestrator._registry = MagicMock()
            orchestrator._registry.get.return_value = None

            result = await orchestrator.disable_service("unknown")

            assert result is False

    @pytest.mark.asyncio
    async def test_start_unknown_service_returns_false(
        self,
        mock_docker_client: AsyncMock,
        mock_redis_client: AsyncMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test that start_service returns False for unknown service."""
        with patch.object(ContainerOrchestrator, "__init__", lambda _self, **_kw: None):
            orchestrator = ContainerOrchestrator.__new__(ContainerOrchestrator)
            orchestrator._registry = MagicMock()
            orchestrator._registry.get.return_value = None

            result = await orchestrator.start_service("unknown")

            assert result is False


# =============================================================================
# ContainerOrchestrator Lifecycle Tests
# =============================================================================


class TestContainerOrchestratorLifecycle:
    """Tests for ContainerOrchestrator is_running property."""

    def test_is_running_initially_false(
        self,
        mock_docker_client: AsyncMock,
        mock_redis_client: AsyncMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test that is_running is False initially."""
        with patch.object(ContainerOrchestrator, "__init__", lambda _self, **_kw: None):
            orchestrator = ContainerOrchestrator.__new__(ContainerOrchestrator)
            orchestrator._running = False

            assert orchestrator.is_running is False

    def test_is_running_property(
        self,
        mock_docker_client: AsyncMock,
        mock_redis_client: AsyncMock,
        mock_settings: MagicMock,
    ) -> None:
        """Test that is_running reflects internal state."""
        with patch.object(ContainerOrchestrator, "__init__", lambda _self, **_kw: None):
            orchestrator = ContainerOrchestrator.__new__(ContainerOrchestrator)
            orchestrator._running = True

            assert orchestrator.is_running is True
