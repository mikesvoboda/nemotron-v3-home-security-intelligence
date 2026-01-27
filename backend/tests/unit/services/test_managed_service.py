"""Unit tests for the canonical ManagedService and ServiceRegistry.

This module tests the consolidated ManagedService and ServiceRegistry classes
that serve as the single source of truth for container orchestration.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from backend.api.schemas.services import ContainerServiceStatus, ServiceCategory
from backend.services.managed_service import (
    REDIS_KEY_PREFIX,
    ManagedService,
    ServiceConfig,
    ServiceRegistry,
    get_service_registry,
    reset_service_registry,
)

# =============================================================================
# ServiceConfig Tests
# =============================================================================


class TestServiceConfig:
    """Tests for ServiceConfig dataclass."""

    def test_create_minimal_config(self) -> None:
        """Test creating a ServiceConfig with required fields only."""
        config = ServiceConfig(
            display_name="PostgreSQL",
            category=ServiceCategory.INFRASTRUCTURE,
            port=5432,
        )

        assert config.display_name == "PostgreSQL"
        assert config.category == ServiceCategory.INFRASTRUCTURE
        assert config.port == 5432
        assert config.health_endpoint is None
        assert config.health_cmd is None
        assert config.startup_grace_period == 60
        assert config.max_failures == 5
        assert config.restart_backoff_base == 5.0
        assert config.restart_backoff_max == 300.0

    def test_create_full_config(self) -> None:
        """Test creating a ServiceConfig with all fields."""
        config = ServiceConfig(
            display_name="YOLO26",
            category=ServiceCategory.AI,
            port=8095,
            health_endpoint="/health",
            health_cmd="curl localhost:8095/health",
            startup_grace_period=120,
            max_failures=10,
            restart_backoff_base=2.0,
            restart_backoff_max=600.0,
        )

        assert config.display_name == "YOLO26"
        assert config.category == ServiceCategory.AI
        assert config.port == 8095
        assert config.health_endpoint == "/health"
        assert config.health_cmd == "curl localhost:8095/health"
        assert config.startup_grace_period == 120
        assert config.max_failures == 10
        assert config.restart_backoff_base == 2.0
        assert config.restart_backoff_max == 600.0


# =============================================================================
# ManagedService Tests
# =============================================================================


class TestManagedService:
    """Tests for ManagedService dataclass."""

    def test_create_minimal_service(self) -> None:
        """Test creating a ManagedService with required fields only."""
        service = ManagedService(
            name="postgres",
            display_name="PostgreSQL",
            container_id="abc123",
            image="postgres:16-alpine",
            port=5432,
            category=ServiceCategory.INFRASTRUCTURE,
        )

        assert service.name == "postgres"
        assert service.display_name == "PostgreSQL"
        assert service.container_id == "abc123"
        assert service.image == "postgres:16-alpine"
        assert service.port == 5432
        assert service.category == ServiceCategory.INFRASTRUCTURE
        assert service.status == ContainerServiceStatus.NOT_FOUND
        assert service.enabled is True
        assert service.failure_count == 0
        assert service.last_failure_at is None
        assert service.last_restart_at is None
        assert service.restart_count == 0
        assert service.max_failures == 5
        assert service.restart_backoff_base == 5.0
        assert service.restart_backoff_max == 300.0
        assert service.startup_grace_period == 60

    def test_create_full_service(self) -> None:
        """Test creating a ManagedService with all fields."""
        now = datetime.now(UTC)
        service = ManagedService(
            name="ai-yolo26",
            display_name="YOLO26",
            container_id="def456",
            image="ghcr.io/ai/yolo26:latest",
            port=8095,
            category=ServiceCategory.AI,
            health_endpoint="/health",
            health_cmd=None,
            status=ContainerServiceStatus.RUNNING,
            enabled=True,
            failure_count=2,
            last_failure_at=now,
            last_restart_at=now - timedelta(hours=1),
            restart_count=5,
            max_failures=10,
            restart_backoff_base=10.0,
            restart_backoff_max=600.0,
            startup_grace_period=120,
        )

        assert service.name == "ai-yolo26"
        assert service.health_endpoint == "/health"
        assert service.status == ContainerServiceStatus.RUNNING
        assert service.failure_count == 2
        assert service.last_failure_at == now
        assert service.restart_count == 5
        assert service.max_failures == 10

    def test_to_dict(self) -> None:
        """Test serialization to dictionary."""
        now = datetime.now(UTC)
        service = ManagedService(
            name="redis",
            display_name="Redis",
            container_id="xyz789",
            image="redis:7-alpine",
            port=6379,
            category=ServiceCategory.INFRASTRUCTURE,
            health_cmd="redis-cli ping",
            status=ContainerServiceStatus.RUNNING,
            failure_count=1,
            last_failure_at=now,
            last_restart_at=now,
            restart_count=3,
        )

        data = service.to_dict()

        assert data["name"] == "redis"
        assert data["display_name"] == "Redis"
        assert data["container_id"] == "xyz789"
        assert data["image"] == "redis:7-alpine"
        assert data["port"] == 6379
        assert data["category"] == "infrastructure"
        assert data["health_cmd"] == "redis-cli ping"
        assert data["status"] == "running"
        assert data["enabled"] is True
        assert data["failure_count"] == 1
        assert data["last_failure_at"] == now.isoformat()
        assert data["last_restart_at"] == now.isoformat()
        assert data["restart_count"] == 3

    def test_from_dict(self) -> None:
        """Test deserialization from dictionary."""
        now = datetime.now(UTC)
        data = {
            "name": "prometheus",
            "display_name": "Prometheus",
            "container_id": "prom123",
            "image": "prom/prometheus:latest",
            "port": 9090,
            "category": "monitoring",
            "health_endpoint": "/-/healthy",
            "status": "running",
            "enabled": True,
            "failure_count": 0,
            "last_failure_at": now.isoformat(),
            "last_restart_at": None,
            "restart_count": 0,
            "max_failures": 3,
            "restart_backoff_base": 10.0,
            "restart_backoff_max": 600.0,
            "startup_grace_period": 30,
        }

        service = ManagedService.from_dict(data)

        assert service.name == "prometheus"
        assert service.display_name == "Prometheus"
        assert service.container_id == "prom123"
        assert service.category == ServiceCategory.MONITORING
        assert service.health_endpoint == "/-/healthy"
        assert service.status == ContainerServiceStatus.RUNNING
        assert service.last_failure_at is not None
        assert service.last_restart_at is None
        assert service.max_failures == 3

    def test_from_dict_minimal(self) -> None:
        """Test deserialization with minimal required fields."""
        data = {
            "name": "grafana",
            "port": 3000,
            "category": "monitoring",
        }

        service = ManagedService.from_dict(data)

        assert service.name == "grafana"
        assert service.display_name == "grafana"  # Falls back to name
        assert service.container_id is None
        assert service.image is None
        assert service.port == 3000
        assert service.category == ServiceCategory.MONITORING
        assert service.status == ContainerServiceStatus.NOT_FOUND
        assert service.enabled is True

    def test_from_config(self) -> None:
        """Test creating ManagedService from ServiceConfig."""
        config = ServiceConfig(
            display_name="YOLO26",
            category=ServiceCategory.AI,
            port=8095,
            health_endpoint="/health",
            startup_grace_period=120,
            max_failures=10,
        )

        service = ManagedService.from_config(
            config_key="ai-yolo26",
            config=config,
            container_id="abc123",
            image="ghcr.io/ai/yolo26:v1.0",
        )

        assert service.name == "ai-yolo26"
        assert service.display_name == "YOLO26"
        assert service.container_id == "abc123"
        assert service.image == "ghcr.io/ai/yolo26:v1.0"
        assert service.port == 8095
        assert service.category == ServiceCategory.AI
        assert service.health_endpoint == "/health"
        assert service.startup_grace_period == 120
        assert service.max_failures == 10
        assert service.status == ContainerServiceStatus.NOT_FOUND

    def test_get_last_failure_timestamp(self) -> None:
        """Test getting last_failure_at as Unix timestamp."""
        now = datetime.now(UTC)
        service = ManagedService(
            name="test",
            display_name="Test",
            container_id=None,
            image=None,
            port=8080,
            category=ServiceCategory.AI,
            last_failure_at=now,
        )

        timestamp = service.get_last_failure_timestamp()
        assert timestamp is not None
        assert abs(timestamp - now.timestamp()) < 0.001

    def test_get_last_failure_timestamp_none(self) -> None:
        """Test getting last_failure_at when None."""
        service = ManagedService(
            name="test",
            display_name="Test",
            container_id=None,
            image=None,
            port=8080,
            category=ServiceCategory.AI,
        )

        assert service.get_last_failure_timestamp() is None

    def test_roundtrip_serialization(self) -> None:
        """Test that to_dict and from_dict are inverse operations."""
        now = datetime.now(UTC)
        original = ManagedService(
            name="roundtrip-test",
            display_name="Roundtrip Test",
            container_id="container123",
            image="test:latest",
            port=9999,
            category=ServiceCategory.AI,
            health_endpoint="/status",
            health_cmd="check",
            status=ContainerServiceStatus.UNHEALTHY,
            enabled=False,
            failure_count=7,
            last_failure_at=now,
            last_restart_at=now,
            restart_count=12,
            max_failures=15,
            restart_backoff_base=3.0,
            restart_backoff_max=120.0,
            startup_grace_period=45,
        )

        data = original.to_dict()
        restored = ManagedService.from_dict(data)

        assert restored.name == original.name
        assert restored.display_name == original.display_name
        assert restored.container_id == original.container_id
        assert restored.image == original.image
        assert restored.port == original.port
        assert restored.category == original.category
        assert restored.health_endpoint == original.health_endpoint
        assert restored.health_cmd == original.health_cmd
        assert restored.status == original.status
        assert restored.enabled == original.enabled
        assert restored.failure_count == original.failure_count
        assert restored.restart_count == original.restart_count
        assert restored.max_failures == original.max_failures
        assert restored.restart_backoff_base == original.restart_backoff_base
        assert restored.restart_backoff_max == original.restart_backoff_max
        assert restored.startup_grace_period == original.startup_grace_period


# =============================================================================
# ServiceRegistry Tests
# =============================================================================


class TestServiceRegistry:
    """Tests for ServiceRegistry class."""

    def test_register_and_get(self) -> None:
        """Test registering and retrieving a service."""
        registry = ServiceRegistry()
        service = ManagedService(
            name="test-service",
            display_name="Test Service",
            container_id="abc",
            image="test:latest",
            port=8080,
            category=ServiceCategory.AI,
        )

        registry.register(service)
        retrieved = registry.get("test-service")

        assert retrieved is not None
        assert retrieved.name == "test-service"

    def test_get_nonexistent(self) -> None:
        """Test getting a non-existent service."""
        registry = ServiceRegistry()
        assert registry.get("nonexistent") is None

    def test_unregister(self) -> None:
        """Test unregistering a service."""
        registry = ServiceRegistry()
        service = ManagedService(
            name="to-remove",
            display_name="To Remove",
            container_id="xyz",
            image="test:latest",
            port=8080,
            category=ServiceCategory.AI,
        )

        registry.register(service)
        assert registry.get("to-remove") is not None

        registry.unregister("to-remove")
        assert registry.get("to-remove") is None

    def test_unregister_nonexistent(self) -> None:
        """Test unregistering a non-existent service (no error)."""
        registry = ServiceRegistry()
        registry.unregister("nonexistent")  # Should not raise

    def test_get_all(self) -> None:
        """Test getting all registered services."""
        registry = ServiceRegistry()

        for i in range(3):
            registry.register(
                ManagedService(
                    name=f"service-{i}",
                    display_name=f"Service {i}",
                    container_id=f"container-{i}",
                    image="test:latest",
                    port=8080 + i,
                    category=ServiceCategory.AI,
                )
            )

        all_services = registry.get_all()
        assert len(all_services) == 3
        names = {s.name for s in all_services}
        assert names == {"service-0", "service-1", "service-2"}

    def test_get_by_category(self) -> None:
        """Test filtering services by category."""
        registry = ServiceRegistry()

        # Register services in different categories
        registry.register(
            ManagedService(
                name="postgres",
                display_name="PostgreSQL",
                container_id="pg",
                image="postgres:16",
                port=5432,
                category=ServiceCategory.INFRASTRUCTURE,
            )
        )
        registry.register(
            ManagedService(
                name="ai-yolo26",
                display_name="YOLO26",
                container_id="ai",
                image="yolo26:latest",
                port=8095,
                category=ServiceCategory.AI,
            )
        )
        registry.register(
            ManagedService(
                name="prometheus",
                display_name="Prometheus",
                container_id="prom",
                image="prom:latest",
                port=9090,
                category=ServiceCategory.MONITORING,
            )
        )

        ai_services = registry.get_by_category(ServiceCategory.AI)
        assert len(ai_services) == 1
        assert ai_services[0].name == "ai-yolo26"

        infra_services = registry.get_by_category(ServiceCategory.INFRASTRUCTURE)
        assert len(infra_services) == 1
        assert infra_services[0].name == "postgres"

    def test_get_enabled(self) -> None:
        """Test getting only enabled services."""
        registry = ServiceRegistry()

        registry.register(
            ManagedService(
                name="enabled-service",
                display_name="Enabled",
                container_id="e1",
                image="test:latest",
                port=8080,
                category=ServiceCategory.AI,
                enabled=True,
            )
        )
        registry.register(
            ManagedService(
                name="disabled-service",
                display_name="Disabled",
                container_id="d1",
                image="test:latest",
                port=8081,
                category=ServiceCategory.AI,
                enabled=False,
            )
        )

        enabled = registry.get_enabled()
        assert len(enabled) == 1
        assert enabled[0].name == "enabled-service"

    def test_get_enabled_services_alias(self) -> None:
        """Test that get_enabled_services() is an alias for get_enabled()."""
        registry = ServiceRegistry()
        registry.register(
            ManagedService(
                name="service",
                display_name="Service",
                container_id="c1",
                image="test:latest",
                port=8080,
                category=ServiceCategory.AI,
                enabled=True,
            )
        )

        assert registry.get_enabled_services() == registry.get_enabled()

    def test_list_names(self) -> None:
        """Test listing all registered service names."""
        registry = ServiceRegistry()

        for name in ["alpha", "beta", "gamma"]:
            registry.register(
                ManagedService(
                    name=name,
                    display_name=name.title(),
                    container_id=name,
                    image="test:latest",
                    port=8080,
                    category=ServiceCategory.AI,
                )
            )

        names = registry.list_names()
        assert set(names) == {"alpha", "beta", "gamma"}

    def test_update_status(self) -> None:
        """Test updating service status."""
        registry = ServiceRegistry()
        registry.register(
            ManagedService(
                name="status-test",
                display_name="Status Test",
                container_id="st",
                image="test:latest",
                port=8080,
                category=ServiceCategory.AI,
                status=ContainerServiceStatus.NOT_FOUND,
            )
        )

        registry.update_status("status-test", ContainerServiceStatus.RUNNING)

        service = registry.get("status-test")
        assert service is not None
        assert service.status == ContainerServiceStatus.RUNNING

    def test_update_status_nonexistent(self) -> None:
        """Test updating status of non-existent service (no error)."""
        registry = ServiceRegistry()
        registry.update_status("nonexistent", ContainerServiceStatus.RUNNING)  # Should not raise

    def test_increment_failure(self) -> None:
        """Test incrementing failure count."""
        registry = ServiceRegistry()
        registry.register(
            ManagedService(
                name="failure-test",
                display_name="Failure Test",
                container_id="ft",
                image="test:latest",
                port=8080,
                category=ServiceCategory.AI,
                failure_count=0,
            )
        )

        new_count = registry.increment_failure("failure-test")
        assert new_count == 1

        service = registry.get("failure-test")
        assert service is not None
        assert service.failure_count == 1
        assert service.last_failure_at is not None

    def test_increment_failure_nonexistent(self) -> None:
        """Test incrementing failure of non-existent service."""
        registry = ServiceRegistry()
        count = registry.increment_failure("nonexistent")
        assert count == 0

    def test_increment_failures_alias(self) -> None:
        """Test that increment_failures() is an alias for increment_failure()."""
        registry = ServiceRegistry()
        registry.register(
            ManagedService(
                name="service",
                display_name="Service",
                container_id="c1",
                image="test:latest",
                port=8080,
                category=ServiceCategory.AI,
            )
        )

        registry.increment_failures("service")
        service = registry.get("service")
        assert service is not None
        assert service.failure_count == 1

    def test_reset_failures(self) -> None:
        """Test resetting failure tracking."""
        registry = ServiceRegistry()
        now = datetime.now(UTC)
        registry.register(
            ManagedService(
                name="reset-test",
                display_name="Reset Test",
                container_id="rt",
                image="test:latest",
                port=8080,
                category=ServiceCategory.AI,
                failure_count=5,
                last_failure_at=now,
            )
        )

        registry.reset_failures("reset-test")

        service = registry.get("reset-test")
        assert service is not None
        assert service.failure_count == 0
        assert service.last_failure_at is None

    def test_record_restart(self) -> None:
        """Test recording a restart."""
        registry = ServiceRegistry()
        registry.register(
            ManagedService(
                name="restart-test",
                display_name="Restart Test",
                container_id="rt",
                image="test:latest",
                port=8080,
                category=ServiceCategory.AI,
                restart_count=0,
            )
        )

        registry.record_restart("restart-test")

        service = registry.get("restart-test")
        assert service is not None
        assert service.restart_count == 1
        assert service.last_restart_at is not None

    def test_set_enabled(self) -> None:
        """Test setting enabled flag."""
        registry = ServiceRegistry()
        registry.register(
            ManagedService(
                name="enable-test",
                display_name="Enable Test",
                container_id="et",
                image="test:latest",
                port=8080,
                category=ServiceCategory.AI,
                enabled=True,
            )
        )

        registry.set_enabled("enable-test", False)
        service = registry.get("enable-test")
        assert service is not None
        assert service.enabled is False

        registry.set_enabled("enable-test", True)
        service = registry.get("enable-test")
        assert service is not None
        assert service.enabled is True

    def test_update_container_id(self) -> None:
        """Test updating container ID."""
        registry = ServiceRegistry()
        registry.register(
            ManagedService(
                name="container-test",
                display_name="Container Test",
                container_id="old-id",
                image="test:latest",
                port=8080,
                category=ServiceCategory.AI,
            )
        )

        registry.update_container_id("container-test", "new-id")
        service = registry.get("container-test")
        assert service is not None
        assert service.container_id == "new-id"

        registry.update_container_id("container-test", None)
        service = registry.get("container-test")
        assert service is not None
        assert service.container_id is None


# =============================================================================
# ServiceRegistry Redis Persistence Tests
# =============================================================================


class TestServiceRegistryPersistence:
    """Tests for ServiceRegistry Redis persistence."""

    @pytest.mark.asyncio
    async def test_persist_state(self) -> None:
        """Test persisting service state to Redis."""
        mock_redis = AsyncMock()
        registry = ServiceRegistry(redis_client=mock_redis)

        now = datetime.now(UTC)
        registry.register(
            ManagedService(
                name="persist-test",
                display_name="Persist Test",
                container_id="pt",
                image="test:latest",
                port=8080,
                category=ServiceCategory.AI,
                status=ContainerServiceStatus.RUNNING,
                enabled=True,
                failure_count=3,
                last_failure_at=now,
                last_restart_at=now,
                restart_count=2,
            )
        )

        await registry.persist_state("persist-test")

        mock_redis.set.assert_called_once()
        call_args = mock_redis.set.call_args
        key = call_args[0][0]
        state = call_args[0][1]

        assert key == f"{REDIS_KEY_PREFIX}:persist-test:state"
        assert state["enabled"] is True
        assert state["failure_count"] == 3
        assert state["restart_count"] == 2
        assert state["status"] == "running"
        assert state["last_failure_at"] == now.isoformat()
        assert state["last_restart_at"] == now.isoformat()

    @pytest.mark.asyncio
    async def test_persist_state_no_redis(self) -> None:
        """Test persist_state with no Redis client (no-op)."""
        registry = ServiceRegistry(redis_client=None)
        registry.register(
            ManagedService(
                name="no-redis-test",
                display_name="No Redis Test",
                container_id="nrt",
                image="test:latest",
                port=8080,
                category=ServiceCategory.AI,
            )
        )

        # Should not raise
        await registry.persist_state("no-redis-test")

    @pytest.mark.asyncio
    async def test_persist_state_nonexistent_service(self) -> None:
        """Test persist_state for non-existent service (no-op)."""
        mock_redis = AsyncMock()
        registry = ServiceRegistry(redis_client=mock_redis)

        await registry.persist_state("nonexistent")
        mock_redis.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_state(self) -> None:
        """Test loading service state from Redis."""
        now = datetime.now(UTC)
        state = {
            "enabled": False,
            "failure_count": 5,
            "restart_count": 3,
            "last_failure_at": now.isoformat(),
            "last_restart_at": now.isoformat(),
            "status": "unhealthy",
        }

        mock_redis = AsyncMock()
        mock_redis.get.return_value = state

        registry = ServiceRegistry(redis_client=mock_redis)
        registry.register(
            ManagedService(
                name="load-test",
                display_name="Load Test",
                container_id="lt",
                image="test:latest",
                port=8080,
                category=ServiceCategory.AI,
            )
        )

        await registry.load_state("load-test")

        service = registry.get("load-test")
        assert service is not None
        assert service.enabled is False
        assert service.failure_count == 5
        assert service.restart_count == 3
        assert service.status == ContainerServiceStatus.UNHEALTHY
        assert service.last_failure_at is not None
        assert service.last_restart_at is not None

    @pytest.mark.asyncio
    async def test_load_state_no_redis(self) -> None:
        """Test load_state with no Redis client (no-op)."""
        registry = ServiceRegistry(redis_client=None)
        registry.register(
            ManagedService(
                name="no-redis-test",
                display_name="No Redis Test",
                container_id="nrt",
                image="test:latest",
                port=8080,
                category=ServiceCategory.AI,
            )
        )

        # Should not raise
        await registry.load_state("no-redis-test")

    @pytest.mark.asyncio
    async def test_load_state_no_data(self) -> None:
        """Test load_state when no Redis data exists."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        registry = ServiceRegistry(redis_client=mock_redis)
        registry.register(
            ManagedService(
                name="no-data-test",
                display_name="No Data Test",
                container_id="ndt",
                image="test:latest",
                port=8080,
                category=ServiceCategory.AI,
                enabled=True,
                failure_count=0,
            )
        )

        await registry.load_state("no-data-test")

        # Service should be unchanged
        service = registry.get("no-data-test")
        assert service is not None
        assert service.enabled is True
        assert service.failure_count == 0

    @pytest.mark.asyncio
    async def test_load_all_state(self) -> None:
        """Test loading state for all registered services."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = {"enabled": True, "failure_count": 1}

        registry = ServiceRegistry(redis_client=mock_redis)

        for name in ["service-a", "service-b", "service-c"]:
            registry.register(
                ManagedService(
                    name=name,
                    display_name=name,
                    container_id=name,
                    image="test:latest",
                    port=8080,
                    category=ServiceCategory.AI,
                )
            )

        await registry.load_all_state()

        # Should have called get() for each service
        assert mock_redis.get.call_count == 3

    @pytest.mark.asyncio
    async def test_clear_state(self) -> None:
        """Test clearing service state from Redis."""
        mock_redis = AsyncMock()
        registry = ServiceRegistry(redis_client=mock_redis)

        await registry.clear_state("test-service")

        mock_redis.delete.assert_called_once_with(f"{REDIS_KEY_PREFIX}:test-service:state")

    @pytest.mark.asyncio
    async def test_clear_state_no_redis(self) -> None:
        """Test clear_state with no Redis client (no-op)."""
        registry = ServiceRegistry(redis_client=None)

        # Should not raise
        await registry.clear_state("test-service")


# =============================================================================
# Global Registry Singleton Tests
# =============================================================================


class TestGlobalRegistry:
    """Tests for global registry singleton functions."""

    def test_reset_service_registry(self) -> None:
        """Test resetting the global registry singleton."""
        # Simply verify the function doesn't raise
        reset_service_registry()

    @pytest.mark.asyncio
    async def test_get_service_registry_creates_singleton(self) -> None:
        """Test that get_service_registry creates a singleton."""
        from unittest.mock import patch

        # Reset first
        reset_service_registry()

        # Mock Redis initialization to avoid actual connection attempts
        # which can crash test workers in parallel mode
        mock_redis = AsyncMock()
        with patch(
            "backend.core.redis.init_redis",
            return_value=mock_redis,
        ):
            registry = await get_service_registry()
            assert isinstance(registry, ServiceRegistry)

            # Calling again should return the same singleton
            registry2 = await get_service_registry()
            assert registry is registry2

        # Clean up
        reset_service_registry()
