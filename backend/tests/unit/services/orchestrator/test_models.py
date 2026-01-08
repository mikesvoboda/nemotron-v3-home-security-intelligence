"""Unit tests for orchestrator models module.

Tests for ManagedService and ServiceConfig dataclasses.
"""

from datetime import UTC, datetime, timedelta

import pytest

from backend.services.orchestrator import (
    ContainerServiceStatus,
    ManagedService,
    ServiceCategory,
    ServiceConfig,
)


class TestServiceConfig:
    """Tests for ServiceConfig dataclass."""

    def test_create_minimal(self) -> None:
        """ServiceConfig can be created with required fields only."""
        config = ServiceConfig(
            display_name="PostgreSQL",
            category=ServiceCategory.INFRASTRUCTURE,
            port=5432,
        )
        assert config.display_name == "PostgreSQL"
        assert config.category == ServiceCategory.INFRASTRUCTURE
        assert config.port == 5432

    def test_default_values(self) -> None:
        """ServiceConfig has expected default values."""
        config = ServiceConfig(
            display_name="Test",
            category=ServiceCategory.AI,
            port=8080,
        )
        assert config.health_endpoint is None
        assert config.health_cmd is None
        assert config.startup_grace_period == 60
        assert config.max_failures == 5
        assert config.restart_backoff_base == 5.0
        assert config.restart_backoff_max == 300.0

    def test_create_with_all_fields(self) -> None:
        """ServiceConfig can be created with all fields."""
        config = ServiceConfig(
            display_name="PostgreSQL",
            category=ServiceCategory.INFRASTRUCTURE,
            port=5432,
            health_endpoint="/health",
            health_cmd="pg_isready -U security",
            startup_grace_period=10,
            max_failures=10,
            restart_backoff_base=2.0,
            restart_backoff_max=60.0,
        )
        assert config.health_endpoint == "/health"
        assert config.health_cmd == "pg_isready -U security"
        assert config.startup_grace_period == 10
        assert config.max_failures == 10
        assert config.restart_backoff_base == 2.0
        assert config.restart_backoff_max == 60.0


class TestManagedService:
    """Tests for ManagedService dataclass."""

    @pytest.fixture
    def minimal_service(self) -> ManagedService:
        """Create a minimal ManagedService instance."""
        return ManagedService(
            name="test-service",
            display_name="Test Service",
            container_id="abc123",
            image="test:latest",
            port=8080,
            health_endpoint="/health",
            health_cmd=None,
            category=ServiceCategory.AI,
        )

    def test_create_minimal(self, minimal_service: ManagedService) -> None:
        """ManagedService can be created with required fields."""
        assert minimal_service.name == "test-service"
        assert minimal_service.display_name == "Test Service"
        assert minimal_service.container_id == "abc123"
        assert minimal_service.image == "test:latest"
        assert minimal_service.port == 8080
        assert minimal_service.category == ServiceCategory.AI

    def test_default_values(self, minimal_service: ManagedService) -> None:
        """ManagedService has expected default values."""
        assert minimal_service.status == ContainerServiceStatus.NOT_FOUND
        assert minimal_service.enabled is True
        assert minimal_service.failure_count == 0
        assert minimal_service.restart_count == 0
        assert minimal_service.last_failure_at is None
        assert minimal_service.last_restart_at is None
        assert minimal_service.max_failures == 5
        assert minimal_service.restart_backoff_base == 5.0
        assert minimal_service.restart_backoff_max == 300.0
        assert minimal_service.startup_grace_period == 60

    def test_to_dict(self, minimal_service: ManagedService) -> None:
        """to_dict returns dictionary representation."""
        data = minimal_service.to_dict()
        assert data["name"] == "test-service"
        assert data["display_name"] == "Test Service"
        assert data["container_id"] == "abc123"
        assert data["category"] == "ai"
        assert data["status"] == "not_found"
        assert data["enabled"] is True

    def test_to_dict_with_timestamps(self) -> None:
        """to_dict handles datetime fields correctly."""
        now = datetime.now(UTC)
        service = ManagedService(
            name="test",
            display_name="Test",
            container_id="abc",
            image="test:latest",
            port=8080,
            health_endpoint=None,
            health_cmd=None,
            category=ServiceCategory.AI,
            last_failure_at=now,
            last_restart_at=now,
        )
        data = service.to_dict()
        assert data["last_failure_at"] == now.isoformat()
        assert data["last_restart_at"] == now.isoformat()

    def test_from_dict(self) -> None:
        """from_dict creates ManagedService from dictionary."""
        data = {
            "name": "test",
            "display_name": "Test",
            "container_id": "abc123",
            "image": "test:latest",
            "port": 8080,
            "health_endpoint": "/health",
            "health_cmd": None,
            "category": "ai",
            "status": "running",
            "enabled": True,
            "failure_count": 2,
            "restart_count": 1,
        }
        service = ManagedService.from_dict(data)
        assert service.name == "test"
        assert service.category == ServiceCategory.AI
        assert service.status == ContainerServiceStatus.RUNNING
        assert service.failure_count == 2
        assert service.restart_count == 1

    def test_from_dict_with_timestamps(self) -> None:
        """from_dict parses ISO format timestamps."""
        now = datetime.now(UTC)
        data = {
            "name": "test",
            "display_name": "Test",
            "container_id": "abc",
            "image": "test:latest",
            "port": 8080,
            "category": "ai",
            "status": "not_found",
            "last_failure_at": now.isoformat(),
            "last_restart_at": now.isoformat(),
        }
        service = ManagedService.from_dict(data)
        assert service.last_failure_at is not None
        assert service.last_restart_at is not None
        # Compare timestamps (allow small differences due to parsing)
        assert abs((service.last_failure_at - now).total_seconds()) < 1

    def test_from_config(self) -> None:
        """from_config creates ManagedService from ServiceConfig."""
        config = ServiceConfig(
            display_name="PostgreSQL",
            category=ServiceCategory.INFRASTRUCTURE,
            port=5432,
            health_cmd="pg_isready -U security",
            max_failures=10,
            startup_grace_period=10,
        )
        service = ManagedService.from_config(
            config_key="postgres",
            config=config,
            container_id="abc123",
            image="postgres:16-alpine",
        )
        assert service.name == "postgres"
        assert service.display_name == "PostgreSQL"
        assert service.container_id == "abc123"
        assert service.image == "postgres:16-alpine"
        assert service.category == ServiceCategory.INFRASTRUCTURE
        assert service.max_failures == 10
        assert service.startup_grace_period == 10

    def test_record_failure(self, minimal_service: ManagedService) -> None:
        """record_failure increments failure count and sets timestamp."""
        assert minimal_service.failure_count == 0
        assert minimal_service.last_failure_at is None

        minimal_service.record_failure()

        assert minimal_service.failure_count == 1
        assert minimal_service.last_failure_at is not None

    def test_record_restart(self, minimal_service: ManagedService) -> None:
        """record_restart increments restart count and sets timestamp."""
        assert minimal_service.restart_count == 0
        assert minimal_service.last_restart_at is None

        minimal_service.record_restart()

        assert minimal_service.restart_count == 1
        assert minimal_service.last_restart_at is not None

    def test_reset_failures(self, minimal_service: ManagedService) -> None:
        """reset_failures clears failure tracking."""
        minimal_service.failure_count = 5
        minimal_service.last_failure_at = datetime.now(UTC)

        minimal_service.reset_failures()

        assert minimal_service.failure_count == 0
        assert minimal_service.last_failure_at is None

    def test_in_grace_period_no_restart(self, minimal_service: ManagedService) -> None:
        """in_grace_period returns False when never restarted."""
        assert minimal_service.in_grace_period() is False

    def test_in_grace_period_recently_restarted(self) -> None:
        """in_grace_period returns True when recently restarted."""
        service = ManagedService(
            name="test",
            display_name="Test",
            container_id="abc",
            image="test:latest",
            port=8080,
            health_endpoint=None,
            health_cmd=None,
            category=ServiceCategory.AI,
            last_restart_at=datetime.now(UTC),
            startup_grace_period=60,
        )
        assert service.in_grace_period() is True

    def test_in_grace_period_expired(self) -> None:
        """in_grace_period returns False when grace period expired."""
        service = ManagedService(
            name="test",
            display_name="Test",
            container_id="abc",
            image="test:latest",
            port=8080,
            health_endpoint=None,
            health_cmd=None,
            category=ServiceCategory.AI,
            last_restart_at=datetime.now(UTC) - timedelta(seconds=120),
            startup_grace_period=60,
        )
        assert service.in_grace_period() is False

    def test_last_failure_timestamp_property(self) -> None:
        """last_failure_timestamp returns Unix timestamp."""
        now = datetime.now(UTC)
        service = ManagedService(
            name="test",
            display_name="Test",
            container_id="abc",
            image="test:latest",
            port=8080,
            health_endpoint=None,
            health_cmd=None,
            category=ServiceCategory.AI,
            last_failure_at=now,
        )
        assert service.last_failure_timestamp is not None
        assert abs(service.last_failure_timestamp - now.timestamp()) < 1

    def test_last_failure_timestamp_none(self, minimal_service: ManagedService) -> None:
        """last_failure_timestamp returns None when no failure."""
        assert minimal_service.last_failure_timestamp is None

    def test_roundtrip_to_from_dict(self) -> None:
        """to_dict and from_dict are inverse operations."""
        original = ManagedService(
            name="test",
            display_name="Test Service",
            container_id="abc123",
            image="test:latest",
            port=8080,
            health_endpoint="/health",
            health_cmd="curl /health",
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.RUNNING,
            enabled=True,
            failure_count=3,
            restart_count=2,
            last_failure_at=datetime.now(UTC),
            last_restart_at=datetime.now(UTC),
            max_failures=10,
            restart_backoff_base=2.0,
            restart_backoff_max=120.0,
            startup_grace_period=30,
        )

        data = original.to_dict()
        restored = ManagedService.from_dict(data)

        assert restored.name == original.name
        assert restored.display_name == original.display_name
        assert restored.container_id == original.container_id
        assert restored.category == original.category
        assert restored.status == original.status
        assert restored.failure_count == original.failure_count
        assert restored.restart_count == original.restart_count
        assert restored.max_failures == original.max_failures
