"""Unit tests for services API routes.

Tests the container orchestrator service management endpoints using
mocked orchestrator dependency.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.api.routes.services import (
    _build_category_summaries,
    _calculate_uptime,
    _to_service_info,
    router,
)
from backend.api.schemas.services import ContainerServiceStatus, ServiceCategory


class MockManagedService:
    """Mock ManagedService for testing."""

    def __init__(
        self,
        name: str = "test-service",
        display_name: str = "Test Service",
        category: ServiceCategory = ServiceCategory.AI,
        status: ContainerServiceStatus = ContainerServiceStatus.RUNNING,
        enabled: bool = True,
        container_id: str | None = "abc123def456789",
        image: str | None = "test/image:latest",
        port: int = 8080,
        failure_count: int = 0,
        restart_count: int = 0,
        last_restart_at: datetime | None = None,
    ):
        self.name = name
        self.display_name = display_name
        self.category = category
        self.status = status
        self.enabled = enabled
        self.container_id = container_id
        self.image = image
        self.port = port
        self.failure_count = failure_count
        self.restart_count = restart_count
        self.last_restart_at = last_restart_at


def create_test_app(orchestrator: MagicMock | None = None) -> FastAPI:
    """Create a test FastAPI app with the services router.

    Args:
        orchestrator: Optional mock orchestrator to attach to app state

    Returns:
        FastAPI app configured for testing
    """
    app = FastAPI()
    app.include_router(router)
    if orchestrator is not None:
        app.state.orchestrator = orchestrator
    return app


class TestCalculateUptime:
    """Tests for _calculate_uptime helper function."""

    def test_returns_none_when_not_running(self) -> None:
        """Test that uptime is None when service is not running."""
        service = MockManagedService(status=ContainerServiceStatus.STOPPED)
        assert _calculate_uptime(service) is None

    def test_returns_none_when_no_last_restart(self) -> None:
        """Test that uptime is None when service has no last_restart_at."""
        service = MockManagedService(
            status=ContainerServiceStatus.RUNNING,
            last_restart_at=None,
        )
        assert _calculate_uptime(service) is None

    def test_calculates_uptime_correctly(self) -> None:
        """Test that uptime is calculated correctly in seconds."""
        # Set last restart to 60 seconds ago
        last_restart = datetime.now(UTC).replace(microsecond=0)
        service = MockManagedService(
            status=ContainerServiceStatus.RUNNING,
            last_restart_at=last_restart,
        )
        uptime = _calculate_uptime(service)
        assert uptime is not None
        # Should be close to 0 (just started)
        assert uptime >= 0
        assert uptime < 5  # Allow for test execution time


class TestToServiceInfo:
    """Tests for _to_service_info helper function."""

    def test_converts_service_correctly(self) -> None:
        """Test conversion of ManagedService to ServiceInfo."""
        service = MockManagedService(
            name="ai-yolo26",
            display_name="YOLO26",
            category=ServiceCategory.AI,
            status=ContainerServiceStatus.RUNNING,
            enabled=True,
            container_id="abc123def456789",
            image="ghcr.io/test/yolo26:latest",
            port=8095,
            failure_count=2,
            restart_count=5,
            last_restart_at=datetime(2025, 1, 5, 10, 30, 0, tzinfo=UTC),
        )

        info = _to_service_info(service)

        assert info.name == "ai-yolo26"
        assert info.display_name == "YOLO26"
        assert info.category == ServiceCategory.AI
        assert info.status == ContainerServiceStatus.RUNNING
        assert info.enabled is True
        assert info.container_id == "abc123def456"  # Truncated to 12 chars
        assert info.image == "ghcr.io/test/yolo26:latest"
        assert info.port == 8095
        assert info.failure_count == 2
        assert info.restart_count == 5

    def test_handles_none_container_id(self) -> None:
        """Test conversion when container_id is None."""
        service = MockManagedService(container_id=None)
        info = _to_service_info(service)
        assert info.container_id is None


class TestBuildCategorySummaries:
    """Tests for _build_category_summaries helper function."""

    def test_empty_services_list(self) -> None:
        """Test summary with empty services list."""
        summaries = _build_category_summaries([])

        assert len(summaries) == 3  # All categories present
        for category in ServiceCategory:
            assert category.value in summaries
            assert summaries[category.value].total == 0
            assert summaries[category.value].healthy == 0
            assert summaries[category.value].unhealthy == 0

    def test_mixed_services(self) -> None:
        """Test summary with mixed healthy and unhealthy services."""
        services = [
            MockManagedService(
                name="postgres",
                category=ServiceCategory.INFRASTRUCTURE,
                status=ContainerServiceStatus.RUNNING,
            ),
            MockManagedService(
                name="redis",
                category=ServiceCategory.INFRASTRUCTURE,
                status=ContainerServiceStatus.RUNNING,
            ),
            MockManagedService(
                name="ai-yolo26",
                category=ServiceCategory.AI,
                status=ContainerServiceStatus.RUNNING,
            ),
            MockManagedService(
                name="ai-nemotron",
                category=ServiceCategory.AI,
                status=ContainerServiceStatus.UNHEALTHY,
            ),
            MockManagedService(
                name="ai-florence",
                category=ServiceCategory.AI,
                status=ContainerServiceStatus.STOPPED,
            ),
            MockManagedService(
                name="grafana",
                category=ServiceCategory.MONITORING,
                status=ContainerServiceStatus.DISABLED,
            ),
        ]

        summaries = _build_category_summaries(services)

        # Infrastructure: 2 running
        assert summaries["infrastructure"].total == 2
        assert summaries["infrastructure"].healthy == 2
        assert summaries["infrastructure"].unhealthy == 0

        # AI: 1 running, 2 unhealthy/stopped
        assert summaries["ai"].total == 3
        assert summaries["ai"].healthy == 1
        assert summaries["ai"].unhealthy == 2

        # Monitoring: 1 disabled (unhealthy)
        assert summaries["monitoring"].total == 1
        assert summaries["monitoring"].healthy == 0
        assert summaries["monitoring"].unhealthy == 1


class TestListServicesEndpoint:
    """Tests for GET /api/system/services endpoint."""

    @pytest.mark.asyncio
    async def test_returns_services_list(self) -> None:
        """Test that endpoint returns list of services."""
        services = [
            MockManagedService(
                name="postgres",
                display_name="PostgreSQL",
                category=ServiceCategory.INFRASTRUCTURE,
                status=ContainerServiceStatus.RUNNING,
                port=5432,
            ),
            MockManagedService(
                name="ai-yolo26",
                display_name="YOLO26",
                category=ServiceCategory.AI,
                status=ContainerServiceStatus.RUNNING,
                port=8095,
            ),
        ]

        mock_orchestrator = MagicMock()
        mock_orchestrator.get_all_services = MagicMock(return_value=services)

        app = create_test_app(mock_orchestrator)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/system/services")

        assert response.status_code == 200
        data = response.json()
        assert len(data["services"]) == 2
        assert data["services"][0]["name"] == "postgres"
        assert data["services"][1]["name"] == "ai-yolo26"
        assert "by_category" in data
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_filters_by_category(self) -> None:
        """Test that endpoint filters services by category."""
        services = [
            MockManagedService(
                name="postgres",
                category=ServiceCategory.INFRASTRUCTURE,
            ),
            MockManagedService(
                name="ai-yolo26",
                category=ServiceCategory.AI,
            ),
            MockManagedService(
                name="ai-nemotron",
                category=ServiceCategory.AI,
            ),
        ]

        mock_orchestrator = MagicMock()
        mock_orchestrator.get_all_services = MagicMock(return_value=services)

        app = create_test_app(mock_orchestrator)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/system/services?category=ai")

        assert response.status_code == 200
        data = response.json()
        assert len(data["services"]) == 2
        assert all(s["category"] == "ai" for s in data["services"])
        # by_category should still show all categories
        assert data["by_category"]["infrastructure"]["total"] == 1

    @pytest.mark.asyncio
    async def test_returns_503_when_orchestrator_unavailable(self) -> None:
        """Test that endpoint returns 503 when orchestrator is not available."""
        app = create_test_app(orchestrator=None)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/system/services")

        assert response.status_code == 503
        assert "orchestrator" in response.json()["detail"].lower()


class TestRestartServiceEndpoint:
    """Tests for POST /api/system/services/{name}/restart endpoint."""

    @pytest.mark.asyncio
    async def test_restart_success(self) -> None:
        """Test successful service restart."""
        service = MockManagedService(
            name="ai-yolo26",
            status=ContainerServiceStatus.RUNNING,
        )

        mock_orchestrator = MagicMock()
        mock_orchestrator.get_service = MagicMock(return_value=service)
        mock_orchestrator.restart_service = AsyncMock(return_value=True)

        app = create_test_app(mock_orchestrator)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/system/services/ai-yolo26/restart")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "restart initiated" in data["message"]
        mock_orchestrator.restart_service.assert_called_once_with("ai-yolo26", reset_failures=True)

    @pytest.mark.asyncio
    async def test_restart_service_not_found(self) -> None:
        """Test restart returns 404 for unknown service."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.get_service = MagicMock(return_value=None)

        app = create_test_app(mock_orchestrator)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/system/services/unknown/restart")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_restart_disabled_service_returns_400(self) -> None:
        """Test restart returns 400 for disabled service."""
        service = MockManagedService(
            name="ai-yolo26",
            status=ContainerServiceStatus.DISABLED,
        )

        mock_orchestrator = MagicMock()
        mock_orchestrator.get_service = MagicMock(return_value=service)

        app = create_test_app(mock_orchestrator)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/system/services/ai-yolo26/restart")

        assert response.status_code == 400
        assert "disabled" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_restart_returns_503_when_orchestrator_unavailable(self) -> None:
        """Test restart returns 503 when orchestrator is not available."""
        app = create_test_app(orchestrator=None)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/system/services/ai-yolo26/restart")

        assert response.status_code == 503


class TestEnableServiceEndpoint:
    """Tests for POST /api/system/services/{name}/enable endpoint."""

    @pytest.mark.asyncio
    async def test_enable_success(self) -> None:
        """Test successful service enable."""
        service = MockManagedService(
            name="ai-yolo26",
            status=ContainerServiceStatus.DISABLED,
            enabled=False,
        )

        mock_orchestrator = MagicMock()
        mock_orchestrator.get_service = MagicMock(return_value=service)
        mock_orchestrator.enable_service = AsyncMock(return_value=True)

        app = create_test_app(mock_orchestrator)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/system/services/ai-yolo26/enable")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "enabled" in data["message"]
        mock_orchestrator.enable_service.assert_called_once_with("ai-yolo26")

    @pytest.mark.asyncio
    async def test_enable_service_not_found(self) -> None:
        """Test enable returns 404 for unknown service."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.get_service = MagicMock(return_value=None)

        app = create_test_app(mock_orchestrator)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/system/services/unknown/enable")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestDisableServiceEndpoint:
    """Tests for POST /api/system/services/{name}/disable endpoint."""

    @pytest.mark.asyncio
    async def test_disable_success(self) -> None:
        """Test successful service disable."""
        service = MockManagedService(
            name="ai-yolo26",
            status=ContainerServiceStatus.RUNNING,
            enabled=True,
        )

        mock_orchestrator = MagicMock()
        mock_orchestrator.get_service = MagicMock(return_value=service)
        mock_orchestrator.disable_service = AsyncMock(return_value=True)

        app = create_test_app(mock_orchestrator)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/system/services/ai-yolo26/disable")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "disabled" in data["message"]
        mock_orchestrator.disable_service.assert_called_once_with("ai-yolo26")

    @pytest.mark.asyncio
    async def test_disable_service_not_found(self) -> None:
        """Test disable returns 404 for unknown service."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.get_service = MagicMock(return_value=None)

        app = create_test_app(mock_orchestrator)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/system/services/unknown/disable")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestStartServiceEndpoint:
    """Tests for POST /api/system/services/{name}/start endpoint."""

    @pytest.mark.asyncio
    async def test_start_success(self) -> None:
        """Test successful service start."""
        service = MockManagedService(
            name="ai-yolo26",
            status=ContainerServiceStatus.STOPPED,
        )

        mock_orchestrator = MagicMock()
        mock_orchestrator.get_service = MagicMock(return_value=service)
        mock_orchestrator.start_service = AsyncMock(return_value=True)

        app = create_test_app(mock_orchestrator)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/system/services/ai-yolo26/start")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "start initiated" in data["message"]
        mock_orchestrator.start_service.assert_called_once_with("ai-yolo26")

    @pytest.mark.asyncio
    async def test_start_service_not_found(self) -> None:
        """Test start returns 404 for unknown service."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.get_service = MagicMock(return_value=None)

        app = create_test_app(mock_orchestrator)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/system/services/unknown/start")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_start_already_running_returns_400(self) -> None:
        """Test start returns 400 if service is already running."""
        service = MockManagedService(
            name="ai-yolo26",
            status=ContainerServiceStatus.RUNNING,
        )

        mock_orchestrator = MagicMock()
        mock_orchestrator.get_service = MagicMock(return_value=service)

        app = create_test_app(mock_orchestrator)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/system/services/ai-yolo26/start")

        assert response.status_code == 400
        assert "already running" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_start_disabled_service_returns_400(self) -> None:
        """Test start returns 400 for disabled service."""
        service = MockManagedService(
            name="ai-yolo26",
            status=ContainerServiceStatus.DISABLED,
        )

        mock_orchestrator = MagicMock()
        mock_orchestrator.get_service = MagicMock(return_value=service)

        app = create_test_app(mock_orchestrator)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/system/services/ai-yolo26/start")

        assert response.status_code == 400
        assert "disabled" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_start_returns_503_when_orchestrator_unavailable(self) -> None:
        """Test start returns 503 when orchestrator is not available."""
        app = create_test_app(orchestrator=None)

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/system/services/ai-yolo26/start")

        assert response.status_code == 503
