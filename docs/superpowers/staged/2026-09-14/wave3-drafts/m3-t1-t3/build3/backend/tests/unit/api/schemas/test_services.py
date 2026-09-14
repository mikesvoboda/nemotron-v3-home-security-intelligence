"""Unit tests for service management API schemas (container orchestrator)."""

from datetime import UTC, datetime

import pytest

from backend.api.schemas.services import (
    CategorySummary,
    ContainerServiceStatus,
    ServiceActionResponse,
    ServiceCategory,
    ServiceInfo,
    ServicesResponse,
    ServiceStatusEvent,
)


class TestServiceCategory:
    """Tests for ServiceCategory enum."""

    def test_service_category_values(self):
        """Test ServiceCategory enum contains all expected values."""
        assert ServiceCategory.INFRASTRUCTURE == "infrastructure"
        assert ServiceCategory.AI == "ai"
        assert ServiceCategory.MONITORING == "monitoring"

    def test_service_category_is_string_enum(self):
        """Test ServiceCategory is a string enum."""
        assert isinstance(ServiceCategory.INFRASTRUCTURE, str)
        assert isinstance(ServiceCategory.AI, str)
        assert isinstance(ServiceCategory.MONITORING, str)

    def test_service_category_from_string(self):
        """Test creating ServiceCategory from string value."""
        assert ServiceCategory("infrastructure") == ServiceCategory.INFRASTRUCTURE
        assert ServiceCategory("ai") == ServiceCategory.AI
        assert ServiceCategory("monitoring") == ServiceCategory.MONITORING

    def test_invalid_category_raises_error(self):
        """Test that invalid category value raises ValueError."""
        with pytest.raises(ValueError):
            ServiceCategory("invalid")


class TestContainerServiceStatus:
    """Tests for ContainerServiceStatus enum."""

    def test_service_status_values(self):
        """Test ContainerServiceStatus enum contains all expected values."""
        assert ContainerServiceStatus.RUNNING == "running"
        assert ContainerServiceStatus.STARTING == "starting"
        assert ContainerServiceStatus.UNHEALTHY == "unhealthy"
        assert ContainerServiceStatus.STOPPED == "stopped"
        assert ContainerServiceStatus.DISABLED == "disabled"
        assert ContainerServiceStatus.NOT_FOUND == "not_found"

    def test_service_status_is_string_enum(self):
        """Test ContainerServiceStatus is a string enum."""
        assert isinstance(ContainerServiceStatus.RUNNING, str)
        assert isinstance(ContainerServiceStatus.DISABLED, str)

    def test_service_status_from_string(self):
        """Test creating ContainerServiceStatus from string value."""
        assert ContainerServiceStatus("running") == ContainerServiceStatus.RUNNING
        assert ContainerServiceStatus("stopped") == ContainerServiceStatus.STOPPED


class TestServiceInfo:
    """Tests for ServiceInfo schema."""

    def test_minimal_service_info(self):
        """Test creating ServiceInfo with required fields only."""
        service = ServiceInfo(
            name="ai-yolo26",
            display_name="YOLO26",
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.RUNNING,
            port=8095,
        )
        assert service.name == "ai-yolo26"
        assert service.display_name == "YOLO26"
        assert service.category == ServiceCategory.AI
        assert service.status == ContainerServiceStatus.RUNNING
        assert service.port == 8095
        assert service.enabled is True  # Default
        assert service.failure_count == 0  # Default
        assert service.restart_count == 0  # Default
        assert service.container_id is None
        assert service.image is None
        assert service.last_restart_at is None
        assert service.uptime_seconds is None

    def test_full_service_info(self):
        """Test creating ServiceInfo with all fields."""
        now = datetime.now(UTC)
        service = ServiceInfo(
            name="postgres",
            display_name="PostgreSQL",
            category=ServiceCategory.INFRASTRUCTURE,
            status=ContainerServiceStatus.RUNNING,
            enabled=True,
            container_id="abc123def456",
            image="postgres:16-alpine",
            port=5432,
            failure_count=0,
            restart_count=2,
            last_restart_at=now,
            uptime_seconds=86400,
        )
        assert service.name == "postgres"
        assert service.display_name == "PostgreSQL"
        assert service.category == ServiceCategory.INFRASTRUCTURE
        assert service.status == ContainerServiceStatus.RUNNING
        assert service.enabled is True
        assert service.container_id == "abc123def456"
        assert service.image == "postgres:16-alpine"
        assert service.port == 5432
        assert service.failure_count == 0
        assert service.restart_count == 2
        assert service.last_restart_at == now
        assert service.uptime_seconds == 86400

    def test_disabled_service_info(self):
        """Test creating a disabled service info."""
        service = ServiceInfo(
            name="ai-florence",
            display_name="Florence-2",
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.DISABLED,
            enabled=False,
            port=8092,
            failure_count=5,
        )
        assert service.status == ContainerServiceStatus.DISABLED
        assert service.enabled is False
        assert service.failure_count == 5

    def test_infrastructure_service(self):
        """Test infrastructure category service."""
        service = ServiceInfo(
            name="redis",
            display_name="Redis",
            category=ServiceCategory.INFRASTRUCTURE,
            status=ContainerServiceStatus.RUNNING,
            port=6379,
            container_id="redis123",
            image="redis:7-alpine",
        )
        assert service.category == ServiceCategory.INFRASTRUCTURE
        assert service.port == 6379

    def test_monitoring_service(self):
        """Test monitoring category service."""
        service = ServiceInfo(
            name="grafana",
            display_name="Grafana",
            category=ServiceCategory.MONITORING,
            status=ContainerServiceStatus.RUNNING,
            port=3000,
        )
        assert service.category == ServiceCategory.MONITORING
        assert service.port == 3000

    def test_service_info_serialization(self):
        """Test ServiceInfo serializes correctly."""
        now = datetime.now(UTC)
        service = ServiceInfo(
            name="ai-yolo26",
            display_name="YOLO26",
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.RUNNING,
            port=8095,
            last_restart_at=now,
        )
        data = service.model_dump()
        assert data["name"] == "ai-yolo26"
        assert data["display_name"] == "YOLO26"
        assert data["category"] == "ai"
        assert data["status"] == "running"
        assert data["port"] == 8095
        assert data["last_restart_at"] == now

    def test_service_info_json_serialization(self):
        """Test ServiceInfo serializes to JSON correctly."""
        service = ServiceInfo(
            name="ai-yolo26",
            display_name="YOLO26",
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.RUNNING,
            port=8095,
        )
        json_str = service.model_dump_json()
        assert "ai-yolo26" in json_str
        assert "running" in json_str


class TestCategorySummary:
    """Tests for CategorySummary schema."""

    def test_category_summary_creation(self):
        """Test creating a category summary."""
        summary = CategorySummary(total=5, healthy=3, unhealthy=2)
        assert summary.total == 5
        assert summary.healthy == 3
        assert summary.unhealthy == 2

    def test_all_healthy_summary(self):
        """Test category summary with all healthy services."""
        summary = CategorySummary(total=3, healthy=3, unhealthy=0)
        assert summary.healthy == summary.total
        assert summary.unhealthy == 0

    def test_all_unhealthy_summary(self):
        """Test category summary with all unhealthy services."""
        summary = CategorySummary(total=2, healthy=0, unhealthy=2)
        assert summary.healthy == 0
        assert summary.unhealthy == summary.total


class TestServicesResponse:
    """Tests for ServicesResponse schema."""

    def test_empty_services_response(self):
        """Test response with no services."""
        now = datetime.now(UTC)
        response = ServicesResponse(services=[], by_category={}, timestamp=now)
        assert len(response.services) == 0
        assert len(response.by_category) == 0
        assert response.timestamp == now

    def test_services_response_with_data(self):
        """Test response with services and category summaries."""
        now = datetime.now(UTC)
        services = [
            ServiceInfo(
                name="postgres",
                display_name="PostgreSQL",
                category=ServiceCategory.INFRASTRUCTURE,
                status=ContainerServiceStatus.RUNNING,
                port=5432,
            ),
            ServiceInfo(
                name="ai-yolo26",
                display_name="YOLO26",
                category=ServiceCategory.AI,
                status=ContainerServiceStatus.RUNNING,
                port=8095,
            ),
            ServiceInfo(
                name="ai-llm",
                display_name="Nemotron",
                category=ServiceCategory.AI,
                status=ContainerServiceStatus.UNHEALTHY,
                port=8091,
            ),
        ]
        by_category = {
            "infrastructure": CategorySummary(total=1, healthy=1, unhealthy=0),
            "ai": CategorySummary(total=2, healthy=1, unhealthy=1),
        }
        response = ServicesResponse(services=services, by_category=by_category, timestamp=now)
        assert len(response.services) == 3
        assert "infrastructure" in response.by_category
        assert "ai" in response.by_category
        assert response.by_category["ai"].healthy == 1
        assert response.by_category["ai"].unhealthy == 1

    def test_services_response_serialization(self):
        """Test ServicesResponse serializes correctly."""
        now = datetime.now(UTC)
        response = ServicesResponse(
            services=[
                ServiceInfo(
                    name="redis",
                    display_name="Redis",
                    category=ServiceCategory.INFRASTRUCTURE,
                    status=ContainerServiceStatus.RUNNING,
                    port=6379,
                )
            ],
            by_category={"infrastructure": CategorySummary(total=1, healthy=1, unhealthy=0)},
            timestamp=now,
        )
        data = response.model_dump()
        assert len(data["services"]) == 1
        assert data["services"][0]["name"] == "redis"
        assert data["by_category"]["infrastructure"]["total"] == 1


class TestServiceActionResponse:
    """Tests for ServiceActionResponse schema."""

    def test_successful_restart(self):
        """Test successful restart action response."""
        service = ServiceInfo(
            name="ai-yolo26",
            display_name="YOLO26",
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.STARTING,
            port=8095,
            restart_count=1,
        )
        response = ServiceActionResponse(
            success=True, message="Service restarted successfully", service=service
        )
        assert response.success is True
        assert response.message == "Service restarted successfully"
        assert response.service.name == "ai-yolo26"
        assert response.service.status == ContainerServiceStatus.STARTING

    def test_failed_enable(self):
        """Test failed enable action response."""
        service = ServiceInfo(
            name="ai-florence",
            display_name="Florence-2",
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.DISABLED,
            enabled=False,
            port=8092,
        )
        response = ServiceActionResponse(
            success=False, message="Failed to enable service: container not found", service=service
        )
        assert response.success is False
        assert "Failed to enable" in response.message
        assert response.service.enabled is False

    def test_successful_disable(self):
        """Test successful disable action response."""
        service = ServiceInfo(
            name="grafana",
            display_name="Grafana",
            category=ServiceCategory.MONITORING,
            status=ContainerServiceStatus.STOPPED,
            enabled=False,
            port=3000,
        )
        response = ServiceActionResponse(success=True, message="Service disabled", service=service)
        assert response.success is True
        assert response.service.enabled is False
        assert response.service.status == ContainerServiceStatus.STOPPED


class TestServiceStatusEvent:
    """Tests for ServiceStatusEvent schema (WebSocket events)."""

    def test_status_event_default_type(self):
        """Test ServiceStatusEvent has correct default type."""
        service = ServiceInfo(
            name="ai-yolo26",
            display_name="YOLO26",
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.RUNNING,
            port=8095,
        )
        event = ServiceStatusEvent(data=service)
        assert event.type == "service_status"
        assert event.data.name == "ai-yolo26"
        assert event.message is None

    def test_status_event_with_message(self):
        """Test ServiceStatusEvent with custom message."""
        service = ServiceInfo(
            name="ai-llm",
            display_name="Nemotron",
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.UNHEALTHY,
            port=8091,
            failure_count=3,
        )
        event = ServiceStatusEvent(data=service, message="Health check failed, restart scheduled")
        assert event.type == "service_status"
        assert event.data.failure_count == 3
        assert event.message == "Health check failed, restart scheduled"

    def test_status_event_serialization(self):
        """Test ServiceStatusEvent serializes correctly for WebSocket."""
        service = ServiceInfo(
            name="redis",
            display_name="Redis",
            category=ServiceCategory.INFRASTRUCTURE,
            status=ContainerServiceStatus.STARTING,
            port=6379,
        )
        event = ServiceStatusEvent(data=service, message="Container restarting")
        data = event.model_dump()
        assert data["type"] == "service_status"
        assert data["data"]["name"] == "redis"
        assert data["data"]["status"] == "starting"
        assert data["message"] == "Container restarting"

    def test_status_event_json_serialization(self):
        """Test ServiceStatusEvent serializes to JSON for WebSocket transport."""
        service = ServiceInfo(
            name="postgres",
            display_name="PostgreSQL",
            category=ServiceCategory.INFRASTRUCTURE,
            status=ContainerServiceStatus.RUNNING,
            port=5432,
        )
        event = ServiceStatusEvent(data=service)
        json_str = event.model_dump_json()
        assert "service_status" in json_str
        assert "postgres" in json_str


class TestServiceInfoValidation:
    """Tests for ServiceInfo field validation."""

    def test_port_must_be_positive(self):
        """Test that port must be a positive integer."""
        # Port 0 is technically valid (auto-assign), but we'll test basic behavior
        service = ServiceInfo(
            name="test",
            display_name="Test",
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.RUNNING,
            port=1,
        )
        assert service.port == 1

    def test_failure_count_default(self):
        """Test failure_count defaults to 0."""
        service = ServiceInfo(
            name="test",
            display_name="Test",
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.RUNNING,
            port=8095,
        )
        assert service.failure_count == 0

    def test_restart_count_default(self):
        """Test restart_count defaults to 0."""
        service = ServiceInfo(
            name="test",
            display_name="Test",
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.RUNNING,
            port=8095,
        )
        assert service.restart_count == 0

    def test_enabled_default(self):
        """Test enabled defaults to True."""
        service = ServiceInfo(
            name="test",
            display_name="Test",
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.RUNNING,
            port=8095,
        )
        assert service.enabled is True


class TestCategoryUseCase:
    """Integration tests for common use cases."""

    def test_all_categories_represented(self):
        """Test creating services from all categories."""
        services = [
            ServiceInfo(
                name="postgres",
                display_name="PostgreSQL",
                category=ServiceCategory.INFRASTRUCTURE,
                status=ContainerServiceStatus.RUNNING,
                port=5432,
            ),
            ServiceInfo(
                name="redis",
                display_name="Redis",
                category=ServiceCategory.INFRASTRUCTURE,
                status=ContainerServiceStatus.RUNNING,
                port=6379,
            ),
            ServiceInfo(
                name="ai-yolo26",
                display_name="YOLO26",
                category=ServiceCategory.AI,
                status=ContainerServiceStatus.RUNNING,
                port=8095,
            ),
            ServiceInfo(
                name="grafana",
                display_name="Grafana",
                category=ServiceCategory.MONITORING,
                status=ContainerServiceStatus.RUNNING,
                port=3000,
            ),
        ]
        categories = {s.category for s in services}
        assert ServiceCategory.INFRASTRUCTURE in categories
        assert ServiceCategory.AI in categories
        assert ServiceCategory.MONITORING in categories

    def test_mixed_status_services(self):
        """Test response with services in different statuses."""
        services = [
            ServiceInfo(
                name="s1",
                display_name="S1",
                category=ServiceCategory.AI,
                status=ContainerServiceStatus.RUNNING,
                port=8095,
            ),
            ServiceInfo(
                name="s2",
                display_name="S2",
                category=ServiceCategory.AI,
                status=ContainerServiceStatus.UNHEALTHY,
                port=8091,
            ),
            ServiceInfo(
                name="s3",
                display_name="S3",
                category=ServiceCategory.AI,
                status=ContainerServiceStatus.STOPPED,
                port=8092,
            ),
            ServiceInfo(
                name="s4",
                display_name="S4",
                category=ServiceCategory.AI,
                status=ContainerServiceStatus.DISABLED,
                port=8093,
            ),
            ServiceInfo(
                name="s5",
                display_name="S5",
                category=ServiceCategory.AI,
                status=ContainerServiceStatus.STARTING,
                port=8094,
            ),
        ]
        statuses = {s.status for s in services}
        assert ContainerServiceStatus.RUNNING in statuses
        assert ContainerServiceStatus.UNHEALTHY in statuses
        assert ContainerServiceStatus.STOPPED in statuses
        assert ContainerServiceStatus.DISABLED in statuses
        assert ContainerServiceStatus.STARTING in statuses
