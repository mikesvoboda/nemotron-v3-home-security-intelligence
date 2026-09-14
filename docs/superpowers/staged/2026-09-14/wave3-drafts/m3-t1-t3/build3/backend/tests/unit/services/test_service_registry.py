"""Unit tests for ServiceRegistry with Redis persistence.

Tests cover:
- ManagedService dataclass initialization and defaults
- ServiceRegistry registration and retrieval
- Category filtering (infrastructure, ai, monitoring)
- State updates (status, failures, restarts, enabled)
- Redis persistence (persist_state, load_state, load_all_state, clear_state)
- Error handling for Redis failures
- Thread-safe concurrent access

TDD: Write tests first, then implement to make them pass.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from backend.api.schemas.services import ContainerServiceStatus, ServiceCategory
from backend.services.service_registry import (
    ManagedService,
    ServiceRegistry,
    get_service_registry,
    reset_service_registry,
)

# =============================================================================
# Test Configuration and Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_global_registry():
    """Reset global registry before and after each test."""
    reset_service_registry()
    yield
    reset_service_registry()


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create a mock Redis client for testing."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.delete = AsyncMock(return_value=1)
    mock.keys = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def sample_service() -> ManagedService:
    """Create a sample managed service for testing."""
    return ManagedService(
        name="ai-yolo26",
        display_name="YOLO26",
        container_id="abc123",
        image="ghcr.io/.../yolo26:latest",
        port=8095,
        health_endpoint="/health",
        health_cmd=None,
        category=ServiceCategory.AI,
        status=ContainerServiceStatus.RUNNING,
    )


@pytest.fixture
def infrastructure_service() -> ManagedService:
    """Create a sample infrastructure service for testing."""
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
        max_failures=10,
        restart_backoff_base=2.0,
        restart_backoff_max=60.0,
        startup_grace_period=10,
    )


@pytest.fixture
def monitoring_service() -> ManagedService:
    """Create a sample monitoring service for testing."""
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
        max_failures=3,
        restart_backoff_base=10.0,
        restart_backoff_max=600.0,
        startup_grace_period=30,
    )


@pytest.fixture
def registry(mock_redis: AsyncMock) -> ServiceRegistry:
    """Create a ServiceRegistry with mock Redis."""
    return ServiceRegistry(redis_client=mock_redis)


# =============================================================================
# ManagedService Dataclass Tests
# =============================================================================


class TestManagedServiceInit:
    """Tests for ManagedService dataclass initialization."""

    def test_minimal_initialization(self) -> None:
        """Test ManagedService with only required fields."""
        service = ManagedService(
            name="test-service",
            display_name="Test Service",
            container_id=None,
            image=None,
            port=8080,
            health_endpoint=None,
            health_cmd=None,
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.NOT_FOUND,
        )

        assert service.name == "test-service"
        assert service.display_name == "Test Service"
        assert service.container_id is None
        assert service.image is None
        assert service.port == 8080
        assert service.health_endpoint is None
        assert service.health_cmd is None
        assert service.category == ServiceCategory.AI
        assert service.status == ContainerServiceStatus.NOT_FOUND

    def test_default_values(self) -> None:
        """Test ManagedService default values for optional fields."""
        service = ManagedService(
            name="test",
            display_name="Test",
            container_id=None,
            image=None,
            port=8080,
            health_endpoint=None,
            health_cmd=None,
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.STOPPED,
        )

        # Check default values
        assert service.enabled is True
        assert service.failure_count == 0
        assert service.last_failure_at is None
        assert service.last_restart_at is None
        assert service.restart_count == 0
        assert service.max_failures == 5
        assert service.restart_backoff_base == 5.0
        assert service.restart_backoff_max == 300.0
        assert service.startup_grace_period == 60

    def test_custom_limits(self) -> None:
        """Test ManagedService with custom limit values."""
        service = ManagedService(
            name="postgres",
            display_name="PostgreSQL",
            container_id="abc123",
            image="postgres:16",
            port=5432,
            health_endpoint=None,
            health_cmd="pg_isready",
            category=ServiceCategory.INFRASTRUCTURE,
            status=ContainerServiceStatus.RUNNING,
            max_failures=10,
            restart_backoff_base=2.0,
            restart_backoff_max=60.0,
            startup_grace_period=10,
        )

        assert service.max_failures == 10
        assert service.restart_backoff_base == 2.0
        assert service.restart_backoff_max == 60.0
        assert service.startup_grace_period == 10

    def test_tracking_fields(self) -> None:
        """Test ManagedService with tracking field values."""
        now = datetime.now(UTC)
        service = ManagedService(
            name="test",
            display_name="Test",
            container_id="abc",
            image="test:latest",
            port=8080,
            health_endpoint="/health",
            health_cmd=None,
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.UNHEALTHY,
            enabled=False,
            failure_count=3,
            last_failure_at=now,
            last_restart_at=now - timedelta(minutes=5),
            restart_count=2,
        )

        assert service.enabled is False
        assert service.failure_count == 3
        assert service.last_failure_at == now
        assert service.last_restart_at is not None
        assert service.restart_count == 2

    def test_service_categories(self) -> None:
        """Test all service categories can be used."""
        for category in ServiceCategory:
            service = ManagedService(
                name=f"test-{category.value}",
                display_name=f"Test {category.value}",
                container_id=None,
                image=None,
                port=8080,
                health_endpoint=None,
                health_cmd=None,
                category=category,
                status=ContainerServiceStatus.STOPPED,
            )
            assert service.category == category

    def test_service_statuses(self) -> None:
        """Test all service statuses can be used."""
        for status in ContainerServiceStatus:
            service = ManagedService(
                name=f"test-{status.value}",
                display_name=f"Test {status.value}",
                container_id=None,
                image=None,
                port=8080,
                health_endpoint=None,
                health_cmd=None,
                category=ServiceCategory.AI,
                status=status,
            )
            assert service.status == status


# =============================================================================
# ServiceRegistry Registration Tests
# =============================================================================


class TestServiceRegistryRegistration:
    """Tests for ServiceRegistry registration and unregistration."""

    def test_register_service(
        self, registry: ServiceRegistry, sample_service: ManagedService
    ) -> None:
        """Test registering a new service."""
        registry.register(sample_service)

        retrieved = registry.get(sample_service.name)
        assert retrieved is not None
        assert retrieved.name == sample_service.name
        assert retrieved.display_name == sample_service.display_name
        assert retrieved.category == sample_service.category

    def test_register_overwrites_existing(
        self, registry: ServiceRegistry, sample_service: ManagedService
    ) -> None:
        """Test registering a service overwrites existing one with same name."""
        registry.register(sample_service)

        # Create updated version
        updated_service = ManagedService(
            name=sample_service.name,
            display_name="Updated Name",
            container_id="new_container",
            image="new:image",
            port=9090,
            health_endpoint="/new-health",
            health_cmd=None,
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.STARTING,
        )

        registry.register(updated_service)

        retrieved = registry.get(sample_service.name)
        assert retrieved is not None
        assert retrieved.display_name == "Updated Name"
        assert retrieved.container_id == "new_container"
        assert retrieved.port == 9090

    def test_unregister_service(
        self, registry: ServiceRegistry, sample_service: ManagedService
    ) -> None:
        """Test unregistering a service removes it."""
        registry.register(sample_service)
        assert registry.get(sample_service.name) is not None

        registry.unregister(sample_service.name)
        assert registry.get(sample_service.name) is None

    def test_unregister_nonexistent_service(self, registry: ServiceRegistry) -> None:
        """Test unregistering a nonexistent service does not raise error."""
        # Should not raise
        registry.unregister("nonexistent")

    def test_get_nonexistent_service(self, registry: ServiceRegistry) -> None:
        """Test getting a nonexistent service returns None."""
        result = registry.get("nonexistent")
        assert result is None


# =============================================================================
# ServiceRegistry Retrieval Tests
# =============================================================================


class TestServiceRegistryRetrieval:
    """Tests for ServiceRegistry retrieval methods."""

    def test_get_all_empty(self, registry: ServiceRegistry) -> None:
        """Test get_all returns empty list when no services registered."""
        result = registry.get_all()
        assert result == []

    def test_get_all_returns_all_services(
        self,
        registry: ServiceRegistry,
        sample_service: ManagedService,
        infrastructure_service: ManagedService,
        monitoring_service: ManagedService,
    ) -> None:
        """Test get_all returns all registered services."""
        registry.register(sample_service)
        registry.register(infrastructure_service)
        registry.register(monitoring_service)

        result = registry.get_all()
        assert len(result) == 3
        names = [s.name for s in result]
        assert sample_service.name in names
        assert infrastructure_service.name in names
        assert monitoring_service.name in names

    def test_get_by_category_infrastructure(
        self,
        registry: ServiceRegistry,
        sample_service: ManagedService,
        infrastructure_service: ManagedService,
        monitoring_service: ManagedService,
    ) -> None:
        """Test get_by_category filters infrastructure services."""
        registry.register(sample_service)
        registry.register(infrastructure_service)
        registry.register(monitoring_service)

        result = registry.get_by_category(ServiceCategory.INFRASTRUCTURE)
        assert len(result) == 1
        assert result[0].name == infrastructure_service.name

    def test_get_by_category_ai(
        self,
        registry: ServiceRegistry,
        sample_service: ManagedService,
        infrastructure_service: ManagedService,
    ) -> None:
        """Test get_by_category filters AI services."""
        registry.register(sample_service)
        registry.register(infrastructure_service)

        result = registry.get_by_category(ServiceCategory.AI)
        assert len(result) == 1
        assert result[0].name == sample_service.name

    def test_get_by_category_monitoring(
        self,
        registry: ServiceRegistry,
        infrastructure_service: ManagedService,
        monitoring_service: ManagedService,
    ) -> None:
        """Test get_by_category filters monitoring services."""
        registry.register(infrastructure_service)
        registry.register(monitoring_service)

        result = registry.get_by_category(ServiceCategory.MONITORING)
        assert len(result) == 1
        assert result[0].name == monitoring_service.name

    def test_get_by_category_empty(self, registry: ServiceRegistry) -> None:
        """Test get_by_category returns empty list when no matches."""
        result = registry.get_by_category(ServiceCategory.AI)
        assert result == []

    def test_get_enabled_all_enabled(
        self,
        registry: ServiceRegistry,
        sample_service: ManagedService,
        infrastructure_service: ManagedService,
    ) -> None:
        """Test get_enabled returns all services when all enabled."""
        registry.register(sample_service)
        registry.register(infrastructure_service)

        result = registry.get_enabled()
        assert len(result) == 2

    def test_get_enabled_filters_disabled(
        self,
        registry: ServiceRegistry,
        sample_service: ManagedService,
        infrastructure_service: ManagedService,
    ) -> None:
        """Test get_enabled filters out disabled services."""
        registry.register(sample_service)
        registry.register(infrastructure_service)

        # Disable one service
        registry.set_enabled(sample_service.name, False)

        result = registry.get_enabled()
        assert len(result) == 1
        assert result[0].name == infrastructure_service.name

    def test_get_enabled_empty_when_all_disabled(
        self, registry: ServiceRegistry, sample_service: ManagedService
    ) -> None:
        """Test get_enabled returns empty when all disabled."""
        registry.register(sample_service)
        registry.set_enabled(sample_service.name, False)

        result = registry.get_enabled()
        assert result == []


# =============================================================================
# ServiceRegistry State Update Tests
# =============================================================================


class TestServiceRegistryStateUpdates:
    """Tests for ServiceRegistry state update methods."""

    def test_update_status(self, registry: ServiceRegistry, sample_service: ManagedService) -> None:
        """Test update_status changes service status."""
        registry.register(sample_service)
        assert registry.get(sample_service.name).status == ContainerServiceStatus.RUNNING

        registry.update_status(sample_service.name, ContainerServiceStatus.UNHEALTHY)

        assert registry.get(sample_service.name).status == ContainerServiceStatus.UNHEALTHY

    def test_update_status_nonexistent_service(self, registry: ServiceRegistry) -> None:
        """Test update_status does nothing for nonexistent service."""
        # Should not raise
        registry.update_status("nonexistent", ContainerServiceStatus.RUNNING)

    def test_increment_failure(
        self, registry: ServiceRegistry, sample_service: ManagedService
    ) -> None:
        """Test increment_failure increases failure count and returns new count."""
        registry.register(sample_service)
        assert registry.get(sample_service.name).failure_count == 0

        count1 = registry.increment_failure(sample_service.name)
        assert count1 == 1
        assert registry.get(sample_service.name).failure_count == 1

        count2 = registry.increment_failure(sample_service.name)
        assert count2 == 2
        assert registry.get(sample_service.name).failure_count == 2

    def test_increment_failure_sets_last_failure_at(
        self, registry: ServiceRegistry, sample_service: ManagedService
    ) -> None:
        """Test increment_failure sets last_failure_at timestamp."""
        registry.register(sample_service)
        assert registry.get(sample_service.name).last_failure_at is None

        before = datetime.now(UTC)
        registry.increment_failure(sample_service.name)
        after = datetime.now(UTC)

        last_failure = registry.get(sample_service.name).last_failure_at
        assert last_failure is not None
        assert before <= last_failure <= after

    def test_increment_failure_nonexistent_service(self, registry: ServiceRegistry) -> None:
        """Test increment_failure returns 0 for nonexistent service."""
        count = registry.increment_failure("nonexistent")
        assert count == 0

    def test_reset_failures(
        self, registry: ServiceRegistry, sample_service: ManagedService
    ) -> None:
        """Test reset_failures clears failure count and timestamp."""
        registry.register(sample_service)

        # Add some failures
        registry.increment_failure(sample_service.name)
        registry.increment_failure(sample_service.name)
        assert registry.get(sample_service.name).failure_count == 2
        assert registry.get(sample_service.name).last_failure_at is not None

        # Reset
        registry.reset_failures(sample_service.name)

        assert registry.get(sample_service.name).failure_count == 0
        assert registry.get(sample_service.name).last_failure_at is None

    def test_reset_failures_nonexistent_service(self, registry: ServiceRegistry) -> None:
        """Test reset_failures does nothing for nonexistent service."""
        # Should not raise
        registry.reset_failures("nonexistent")

    def test_record_restart(
        self, registry: ServiceRegistry, sample_service: ManagedService
    ) -> None:
        """Test record_restart updates restart tracking."""
        registry.register(sample_service)
        assert registry.get(sample_service.name).restart_count == 0
        assert registry.get(sample_service.name).last_restart_at is None

        before = datetime.now(UTC)
        registry.record_restart(sample_service.name)
        after = datetime.now(UTC)

        service = registry.get(sample_service.name)
        assert service.restart_count == 1
        assert service.last_restart_at is not None
        assert before <= service.last_restart_at <= after

    def test_record_restart_multiple(
        self, registry: ServiceRegistry, sample_service: ManagedService
    ) -> None:
        """Test record_restart accumulates restart count."""
        registry.register(sample_service)

        registry.record_restart(sample_service.name)
        registry.record_restart(sample_service.name)
        registry.record_restart(sample_service.name)

        assert registry.get(sample_service.name).restart_count == 3

    def test_record_restart_nonexistent_service(self, registry: ServiceRegistry) -> None:
        """Test record_restart does nothing for nonexistent service."""
        # Should not raise
        registry.record_restart("nonexistent")

    def test_set_enabled(self, registry: ServiceRegistry, sample_service: ManagedService) -> None:
        """Test set_enabled updates enabled flag."""
        registry.register(sample_service)
        assert registry.get(sample_service.name).enabled is True

        registry.set_enabled(sample_service.name, False)
        assert registry.get(sample_service.name).enabled is False

        registry.set_enabled(sample_service.name, True)
        assert registry.get(sample_service.name).enabled is True

    def test_set_enabled_nonexistent_service(self, registry: ServiceRegistry) -> None:
        """Test set_enabled does nothing for nonexistent service."""
        # Should not raise
        registry.set_enabled("nonexistent", False)


# =============================================================================
# ServiceRegistry Redis Persistence Tests
# =============================================================================


class TestServiceRegistryPersistence:
    """Tests for ServiceRegistry Redis persistence methods."""

    @pytest.mark.asyncio
    async def test_persist_state(
        self, registry: ServiceRegistry, sample_service: ManagedService, mock_redis: AsyncMock
    ) -> None:
        """Test persist_state saves service state to Redis."""
        registry.register(sample_service)
        registry.increment_failure(sample_service.name)
        registry.record_restart(sample_service.name)

        await registry.persist_state(sample_service.name)

        # Verify Redis set was called
        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args

        # Verify key format
        key = call_args[0][0]
        assert key == f"orchestrator:service:{sample_service.name}:state"

        # Verify data (RedisClient.set accepts dict, serializes internally)
        data = call_args[0][1]
        assert data["enabled"] is True
        assert data["failure_count"] == 1
        assert data["restart_count"] == 1
        assert data["status"] == "running"
        assert "last_failure_at" in data
        assert "last_restart_at" in data

    @pytest.mark.asyncio
    async def test_persist_state_nonexistent_service(
        self, registry: ServiceRegistry, mock_redis: AsyncMock
    ) -> None:
        """Test persist_state does nothing for nonexistent service."""
        await registry.persist_state("nonexistent")
        mock_redis.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_state(
        self, registry: ServiceRegistry, sample_service: ManagedService, mock_redis: AsyncMock
    ) -> None:
        """Test load_state restores service state from Redis."""
        registry.register(sample_service)

        # Prepare mock Redis data
        now = datetime.now(UTC)
        stored_state = {
            "enabled": False,
            "failure_count": 3,
            "last_failure_at": now.isoformat(),
            "last_restart_at": (now - timedelta(minutes=5)).isoformat(),
            "restart_count": 2,
            "status": "unhealthy",
        }
        mock_redis.get.return_value = json.dumps(stored_state)

        await registry.load_state(sample_service.name)

        # Verify state was loaded
        service = registry.get(sample_service.name)
        assert service.enabled is False
        assert service.failure_count == 3
        assert service.restart_count == 2
        assert service.status == ContainerServiceStatus.UNHEALTHY
        assert service.last_failure_at is not None
        assert service.last_restart_at is not None

    @pytest.mark.asyncio
    async def test_load_state_no_redis_data(
        self, registry: ServiceRegistry, sample_service: ManagedService, mock_redis: AsyncMock
    ) -> None:
        """Test load_state does nothing when no Redis data exists."""
        registry.register(sample_service)
        original_status = sample_service.status

        mock_redis.get.return_value = None

        await registry.load_state(sample_service.name)

        # Service should remain unchanged
        service = registry.get(sample_service.name)
        assert service.status == original_status
        assert service.failure_count == 0

    @pytest.mark.asyncio
    async def test_load_state_nonexistent_service(
        self, registry: ServiceRegistry, mock_redis: AsyncMock
    ) -> None:
        """Test load_state does nothing for nonexistent service."""
        await registry.load_state("nonexistent")
        mock_redis.get.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_all_state(
        self,
        registry: ServiceRegistry,
        sample_service: ManagedService,
        infrastructure_service: ManagedService,
        mock_redis: AsyncMock,
    ) -> None:
        """Test load_all_state loads state for all registered services."""
        registry.register(sample_service)
        registry.register(infrastructure_service)

        # Prepare mock Redis data
        mock_redis.get.return_value = json.dumps(
            {
                "enabled": True,
                "failure_count": 1,
                "last_failure_at": None,
                "last_restart_at": None,
                "restart_count": 0,
                "status": "running",
            }
        )

        await registry.load_all_state()

        # Verify Redis get was called for each service
        assert mock_redis.get.call_count == 2

    @pytest.mark.asyncio
    async def test_clear_state(
        self, registry: ServiceRegistry, sample_service: ManagedService, mock_redis: AsyncMock
    ) -> None:
        """Test clear_state removes state from Redis."""
        registry.register(sample_service)

        await registry.clear_state(sample_service.name)

        mock_redis.delete.assert_called_once_with(
            f"orchestrator:service:{sample_service.name}:state"
        )


# =============================================================================
# ServiceRegistry Redis Error Handling Tests
# =============================================================================


class TestServiceRegistryRedisErrorHandling:
    """Tests for ServiceRegistry graceful Redis error handling."""

    @pytest.mark.asyncio
    async def test_persist_state_redis_error_logged(
        self, registry: ServiceRegistry, sample_service: ManagedService, mock_redis: AsyncMock
    ) -> None:
        """Test persist_state logs and continues on Redis error."""
        registry.register(sample_service)
        mock_redis.set.side_effect = Exception("Redis connection failed")

        # Should not raise - error is logged and operation continues
        await registry.persist_state(sample_service.name)

    @pytest.mark.asyncio
    async def test_load_state_redis_error_logged(
        self, registry: ServiceRegistry, sample_service: ManagedService, mock_redis: AsyncMock
    ) -> None:
        """Test load_state logs and continues on Redis error."""
        registry.register(sample_service)
        mock_redis.get.side_effect = Exception("Redis connection failed")

        # Should not raise - error is logged and operation continues
        await registry.load_state(sample_service.name)

        # Service should remain with default values
        service = registry.get(sample_service.name)
        assert service.failure_count == 0

    @pytest.mark.asyncio
    async def test_clear_state_redis_error_logged(
        self, registry: ServiceRegistry, sample_service: ManagedService, mock_redis: AsyncMock
    ) -> None:
        """Test clear_state logs and continues on Redis error."""
        registry.register(sample_service)
        mock_redis.delete.side_effect = Exception("Redis connection failed")

        # Should not raise - error is logged and operation continues
        await registry.clear_state(sample_service.name)

    @pytest.mark.asyncio
    async def test_load_state_invalid_json(
        self, registry: ServiceRegistry, sample_service: ManagedService, mock_redis: AsyncMock
    ) -> None:
        """Test load_state handles invalid JSON gracefully."""
        registry.register(sample_service)
        mock_redis.get.return_value = "not valid json"

        # Should not raise - error is logged and operation continues
        await registry.load_state(sample_service.name)

        # Service should remain with default values
        service = registry.get(sample_service.name)
        assert service.failure_count == 0


# =============================================================================
# ServiceRegistry Thread Safety Tests
# =============================================================================


class TestServiceRegistryConcurrentAccess:
    """Tests for ServiceRegistry thread-safe concurrent access."""

    @pytest.mark.asyncio
    async def test_concurrent_registrations(self, mock_redis: AsyncMock) -> None:
        """Test concurrent service registrations don't cause race conditions."""
        registry = ServiceRegistry(redis_client=mock_redis)

        async def register_service(index: int) -> None:
            service = ManagedService(
                name=f"service-{index}",
                display_name=f"Service {index}",
                container_id=f"container-{index}",
                image=f"image:v{index}",
                port=8080 + index,
                health_endpoint="/health",
                health_cmd=None,
                category=ServiceCategory.AI,
                status=ContainerServiceStatus.RUNNING,
            )
            registry.register(service)

        # Register 50 services concurrently
        tasks = [register_service(i) for i in range(50)]
        await asyncio.gather(*tasks)

        # All services should be registered
        all_services = registry.get_all()
        assert len(all_services) == 50

    @pytest.mark.asyncio
    async def test_concurrent_status_updates(
        self, registry: ServiceRegistry, sample_service: ManagedService
    ) -> None:
        """Test concurrent status updates don't cause race conditions."""
        registry.register(sample_service)

        statuses = [
            ContainerServiceStatus.RUNNING,
            ContainerServiceStatus.UNHEALTHY,
            ContainerServiceStatus.STARTING,
            ContainerServiceStatus.STOPPED,
        ]

        async def update_status(status: ContainerServiceStatus) -> None:
            for _ in range(10):
                registry.update_status(sample_service.name, status)
                await asyncio.sleep(0.001)

        # Run concurrent updates
        tasks = [update_status(s) for s in statuses]
        await asyncio.gather(*tasks)

        # Service should have one of the valid statuses
        final_service = registry.get(sample_service.name)
        assert final_service.status in statuses

    @pytest.mark.asyncio
    async def test_concurrent_failure_increments(
        self, registry: ServiceRegistry, sample_service: ManagedService
    ) -> None:
        """Test concurrent failure increments maintain count integrity."""
        registry.register(sample_service)

        async def increment_failures(count: int) -> None:
            for _ in range(count):
                registry.increment_failure(sample_service.name)

        # Run 10 concurrent tasks, each incrementing 10 times
        tasks = [increment_failures(10) for _ in range(10)]
        await asyncio.gather(*tasks)

        # Total should be 100
        final_service = registry.get(sample_service.name)
        assert final_service.failure_count == 100


# =============================================================================
# Global Registry Tests
# =============================================================================


class TestGlobalRegistry:
    """Tests for global ServiceRegistry singleton functions."""

    @pytest.mark.asyncio
    async def test_get_service_registry_creates_singleton(self, mock_redis: AsyncMock) -> None:
        """Test get_service_registry creates a singleton instance."""

        async def mock_init_redis():
            return mock_redis

        with patch(
            "backend.core.redis.init_redis",
            side_effect=mock_init_redis,
        ):
            registry1 = await get_service_registry()
            registry2 = await get_service_registry()

            assert registry1 is registry2

    @pytest.mark.asyncio
    async def test_reset_service_registry_clears_singleton(self, mock_redis: AsyncMock) -> None:
        """Test reset_service_registry clears the singleton."""

        async def mock_init_redis():
            return mock_redis

        with patch(
            "backend.core.redis.init_redis",
            side_effect=mock_init_redis,
        ):
            registry1 = await get_service_registry()
            reset_service_registry()
            registry2 = await get_service_registry()

            assert registry1 is not registry2


# =============================================================================
# ManagedService Serialization Tests
# =============================================================================


class TestManagedServiceSerialization:
    """Tests for ManagedService serialization to/from dict."""

    def test_to_dict(self, sample_service: ManagedService) -> None:
        """Test ManagedService converts to dictionary correctly."""
        data = sample_service.to_dict()

        assert data["name"] == sample_service.name
        assert data["display_name"] == sample_service.display_name
        assert data["container_id"] == sample_service.container_id
        assert data["image"] == sample_service.image
        assert data["port"] == sample_service.port
        assert data["health_endpoint"] == sample_service.health_endpoint
        assert data["category"] == sample_service.category.value
        assert data["status"] == sample_service.status.value

    def test_to_dict_with_timestamps(self, sample_service: ManagedService) -> None:
        """Test ManagedService serializes timestamps correctly."""
        now = datetime.now(UTC)
        sample_service.last_failure_at = now
        sample_service.last_restart_at = now

        data = sample_service.to_dict()

        assert data["last_failure_at"] == now.isoformat()
        assert data["last_restart_at"] == now.isoformat()

    def test_from_dict(self) -> None:
        """Test ManagedService can be created from dictionary."""
        data = {
            "name": "test-service",
            "display_name": "Test Service",
            "container_id": "abc123",
            "image": "test:latest",
            "port": 8080,
            "health_endpoint": "/health",
            "health_cmd": None,
            "category": "ai",
            "status": "running",
            "enabled": True,
            "failure_count": 2,
            "last_failure_at": "2026-01-05T10:30:00+00:00",
            "last_restart_at": None,
            "restart_count": 1,
            "max_failures": 5,
            "restart_backoff_base": 5.0,
            "restart_backoff_max": 300.0,
            "startup_grace_period": 60,
        }

        service = ManagedService.from_dict(data)

        assert service.name == "test-service"
        assert service.category == ServiceCategory.AI
        assert service.status == ContainerServiceStatus.RUNNING
        assert service.failure_count == 2
        assert service.last_failure_at is not None
