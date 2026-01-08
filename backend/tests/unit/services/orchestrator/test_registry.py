"""Unit tests for orchestrator registry module.

Tests for ServiceRegistry class.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.orchestrator import (
    ContainerServiceStatus,
    ManagedService,
    ServiceCategory,
    ServiceRegistry,
    reset_service_registry,
)


@pytest.fixture
def mock_redis() -> MagicMock:
    """Create a mock Redis client."""
    redis = MagicMock()
    redis.set = AsyncMock(return_value=True)
    redis.get = AsyncMock(return_value=None)
    redis.delete = AsyncMock(return_value=1)
    return redis


@pytest.fixture
def registry(mock_redis: MagicMock) -> ServiceRegistry:
    """Create a ServiceRegistry with mock Redis."""
    return ServiceRegistry(redis_client=mock_redis)


@pytest.fixture
def sample_service() -> ManagedService:
    """Create a sample ManagedService for testing."""
    return ManagedService(
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


class TestServiceRegistry:
    """Tests for ServiceRegistry class."""

    def test_register_service(
        self, registry: ServiceRegistry, sample_service: ManagedService
    ) -> None:
        """register adds service to registry."""
        registry.register(sample_service)
        assert registry.get("test-service") is sample_service

    def test_unregister_service(
        self, registry: ServiceRegistry, sample_service: ManagedService
    ) -> None:
        """unregister removes service from registry."""
        registry.register(sample_service)
        registry.unregister("test-service")
        assert registry.get("test-service") is None

    def test_unregister_nonexistent(self, registry: ServiceRegistry) -> None:
        """unregister does nothing for nonexistent service."""
        registry.unregister("nonexistent")  # Should not raise

    def test_get_returns_none_for_missing(self, registry: ServiceRegistry) -> None:
        """get returns None for missing service."""
        assert registry.get("nonexistent") is None

    def test_get_all(self, registry: ServiceRegistry) -> None:
        """get_all returns all registered services."""
        svc1 = ManagedService(
            name="svc1",
            display_name="Service 1",
            container_id="abc",
            image="test:1",
            port=8001,
            health_endpoint=None,
            health_cmd=None,
            category=ServiceCategory.AI,
        )
        svc2 = ManagedService(
            name="svc2",
            display_name="Service 2",
            container_id="def",
            image="test:2",
            port=8002,
            health_endpoint=None,
            health_cmd=None,
            category=ServiceCategory.INFRASTRUCTURE,
        )
        registry.register(svc1)
        registry.register(svc2)

        all_services = registry.get_all()
        assert len(all_services) == 2
        assert svc1 in all_services
        assert svc2 in all_services

    def test_get_by_category(self, registry: ServiceRegistry) -> None:
        """get_by_category filters by category."""
        ai_svc = ManagedService(
            name="ai",
            display_name="AI",
            container_id="abc",
            image="ai:1",
            port=8001,
            health_endpoint=None,
            health_cmd=None,
            category=ServiceCategory.AI,
        )
        infra_svc = ManagedService(
            name="infra",
            display_name="Infra",
            container_id="def",
            image="infra:1",
            port=8002,
            health_endpoint=None,
            health_cmd=None,
            category=ServiceCategory.INFRASTRUCTURE,
        )
        registry.register(ai_svc)
        registry.register(infra_svc)

        ai_services = registry.get_by_category(ServiceCategory.AI)
        assert len(ai_services) == 1
        assert ai_services[0] is ai_svc

    def test_get_enabled(self, registry: ServiceRegistry) -> None:
        """get_enabled returns only enabled services."""
        enabled_svc = ManagedService(
            name="enabled",
            display_name="Enabled",
            container_id="abc",
            image="test:1",
            port=8001,
            health_endpoint=None,
            health_cmd=None,
            category=ServiceCategory.AI,
            enabled=True,
        )
        disabled_svc = ManagedService(
            name="disabled",
            display_name="Disabled",
            container_id="def",
            image="test:2",
            port=8002,
            health_endpoint=None,
            health_cmd=None,
            category=ServiceCategory.AI,
            enabled=False,
        )
        registry.register(enabled_svc)
        registry.register(disabled_svc)

        enabled = registry.get_enabled()
        assert len(enabled) == 1
        assert enabled[0] is enabled_svc

    def test_list_names(self, registry: ServiceRegistry, sample_service: ManagedService) -> None:
        """list_names returns all service names."""
        registry.register(sample_service)
        names = registry.list_names()
        assert "test-service" in names

    def test_update_status(self, registry: ServiceRegistry, sample_service: ManagedService) -> None:
        """update_status changes service status."""
        registry.register(sample_service)
        registry.update_status("test-service", ContainerServiceStatus.UNHEALTHY)
        assert sample_service.status == ContainerServiceStatus.UNHEALTHY

    def test_update_status_nonexistent(self, registry: ServiceRegistry) -> None:
        """update_status does nothing for nonexistent service."""
        registry.update_status("nonexistent", ContainerServiceStatus.RUNNING)  # No error

    def test_increment_failure(
        self, registry: ServiceRegistry, sample_service: ManagedService
    ) -> None:
        """increment_failure increments failure count."""
        registry.register(sample_service)
        assert sample_service.failure_count == 0

        count = registry.increment_failure("test-service")
        assert count == 1
        assert sample_service.failure_count == 1
        assert sample_service.last_failure_at is not None

    def test_increment_failure_nonexistent(self, registry: ServiceRegistry) -> None:
        """increment_failure returns 0 for nonexistent service."""
        count = registry.increment_failure("nonexistent")
        assert count == 0

    def test_reset_failures(
        self, registry: ServiceRegistry, sample_service: ManagedService
    ) -> None:
        """reset_failures clears failure tracking."""
        sample_service.failure_count = 5
        sample_service.last_failure_at = datetime.now(UTC)
        registry.register(sample_service)

        registry.reset_failures("test-service")
        assert sample_service.failure_count == 0
        assert sample_service.last_failure_at is None

    def test_record_restart(
        self, registry: ServiceRegistry, sample_service: ManagedService
    ) -> None:
        """record_restart increments restart count."""
        registry.register(sample_service)
        assert sample_service.restart_count == 0

        registry.record_restart("test-service")
        assert sample_service.restart_count == 1
        assert sample_service.last_restart_at is not None

    def test_set_enabled(self, registry: ServiceRegistry, sample_service: ManagedService) -> None:
        """set_enabled changes enabled flag."""
        registry.register(sample_service)
        assert sample_service.enabled is True

        registry.set_enabled("test-service", False)
        assert sample_service.enabled is False

    def test_update_container_id(
        self, registry: ServiceRegistry, sample_service: ManagedService
    ) -> None:
        """update_container_id changes container ID."""
        registry.register(sample_service)
        registry.update_container_id("test-service", "new123")
        assert sample_service.container_id == "new123"

    @pytest.mark.asyncio
    async def test_persist_state(
        self, registry: ServiceRegistry, sample_service: ManagedService, mock_redis: MagicMock
    ) -> None:
        """persist_state saves to Redis."""
        registry.register(sample_service)
        await registry.persist_state("test-service")

        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        assert "orchestrator:service:test-service:state" in call_args[0]

    @pytest.mark.asyncio
    async def test_persist_state_no_redis(self, sample_service: ManagedService) -> None:
        """persist_state is a no-op without Redis client."""
        registry = ServiceRegistry(redis_client=None)
        registry.register(sample_service)
        await registry.persist_state("test-service")  # Should not raise

    @pytest.mark.asyncio
    async def test_load_state(
        self, registry: ServiceRegistry, sample_service: ManagedService, mock_redis: MagicMock
    ) -> None:
        """load_state restores from Redis."""
        registry.register(sample_service)

        # Mock Redis returning stored state
        mock_redis.get.return_value = {
            "enabled": False,
            "failure_count": 3,
            "restart_count": 2,
            "status": "unhealthy",
        }

        await registry.load_state("test-service")

        assert sample_service.enabled is False
        assert sample_service.failure_count == 3
        assert sample_service.restart_count == 2
        assert sample_service.status == ContainerServiceStatus.UNHEALTHY

    @pytest.mark.asyncio
    async def test_load_state_no_data(
        self, registry: ServiceRegistry, sample_service: ManagedService, mock_redis: MagicMock
    ) -> None:
        """load_state does nothing when no Redis data."""
        registry.register(sample_service)
        original_status = sample_service.status

        mock_redis.get.return_value = None
        await registry.load_state("test-service")

        assert sample_service.status == original_status

    @pytest.mark.asyncio
    async def test_load_all_state(self, registry: ServiceRegistry, mock_redis: MagicMock) -> None:
        """load_all_state loads state for all services."""
        svc1 = ManagedService(
            name="svc1",
            display_name="Service 1",
            container_id="abc",
            image="test:1",
            port=8001,
            health_endpoint=None,
            health_cmd=None,
            category=ServiceCategory.AI,
        )
        svc2 = ManagedService(
            name="svc2",
            display_name="Service 2",
            container_id="def",
            image="test:2",
            port=8002,
            health_endpoint=None,
            health_cmd=None,
            category=ServiceCategory.AI,
        )
        registry.register(svc1)
        registry.register(svc2)

        await registry.load_all_state()

        assert mock_redis.get.call_count == 2

    @pytest.mark.asyncio
    async def test_clear_state(
        self, registry: ServiceRegistry, sample_service: ManagedService, mock_redis: MagicMock
    ) -> None:
        """clear_state removes from Redis."""
        registry.register(sample_service)
        await registry.clear_state("test-service")

        mock_redis.delete.assert_called_once()


class TestResetServiceRegistry:
    """Tests for reset_service_registry function."""

    def test_reset_clears_singleton(self) -> None:
        """reset_service_registry clears the global singleton."""
        reset_service_registry()  # Should not raise


class TestServiceRegistryThreadSafety:
    """Tests for thread safety of ServiceRegistry."""

    def test_register_is_thread_safe(self, registry: ServiceRegistry) -> None:
        """register uses locking."""
        # This is a basic test that register doesn't raise
        # Full thread safety testing would require concurrent execution
        for i in range(100):
            svc = ManagedService(
                name=f"svc{i}",
                display_name=f"Service {i}",
                container_id=f"container{i}",
                image="test:latest",
                port=8000 + i,
                health_endpoint=None,
                health_cmd=None,
                category=ServiceCategory.AI,
            )
            registry.register(svc)

        assert len(registry.get_all()) == 100
