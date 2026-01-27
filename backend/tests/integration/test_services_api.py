"""Integration tests for services API endpoints.

Tests the /api/system/services endpoints for container orchestrator service management.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.schemas.services import ContainerServiceStatus, ServiceCategory
from backend.tests.integration.test_helpers import get_error_message


@pytest.fixture
async def mock_orchestrator_client(client):
    """Fixture that provides client with ability to override orchestrator dependency."""
    from backend.main import app

    # Store original dependency overrides
    original_overrides = app.dependency_overrides.copy()

    # Yield both client and app for dependency overriding
    yield client, app

    # Restore original dependency overrides
    app.dependency_overrides = original_overrides


# =============================================================================
# List Services Endpoint Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_services_orchestrator_not_available(mock_orchestrator_client, mock_redis):
    """Test GET /api/system/services returns 503 when orchestrator is not available."""
    client, app = mock_orchestrator_client

    # Mock get_orchestrator to raise HTTPException
    async def mock_get_orchestrator_unavailable():
        from fastapi import HTTPException

        raise HTTPException(503, "Container orchestrator not available")

    from backend.api.routes.services import get_orchestrator

    app.dependency_overrides[get_orchestrator] = mock_get_orchestrator_unavailable

    response = await client.get("/api/system/services")

    assert response.status_code == 503
    data = response.json()
    error_msg = get_error_message(data).lower()
    assert "orchestrator" in error_msg or "not available" in error_msg


@pytest.mark.asyncio
async def test_list_services_returns_valid_structure(mock_orchestrator_client, mock_redis):
    """Test GET /api/system/services returns valid response structure."""
    client, app = mock_orchestrator_client

    # Mock orchestrator
    mock_orchestrator = MagicMock()
    mock_service = MagicMock()
    mock_service.name = "test-service"
    mock_service.display_name = "Test Service"
    mock_service.category = ServiceCategory.AI
    mock_service.status = ContainerServiceStatus.RUNNING
    mock_service.enabled = True
    mock_service.container_id = "abc123def456"
    mock_service.image = "test:latest"
    mock_service.port = 8090
    mock_service.failure_count = 0
    mock_service.restart_count = 0
    mock_service.last_restart_at = None

    mock_orchestrator.get_all_services.return_value = [mock_service]

    async def mock_get_orchestrator():
        return mock_orchestrator

    from backend.api.routes.services import get_orchestrator

    app.dependency_overrides[get_orchestrator] = mock_get_orchestrator

    response = await client.get("/api/system/services")

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "services" in data
    assert "by_category" in data
    assert "timestamp" in data

    # Verify services list
    assert isinstance(data["services"], list)
    assert len(data["services"]) == 1

    service = data["services"][0]
    assert service["name"] == "test-service"
    assert service["display_name"] == "Test Service"
    assert service["category"] == "ai"
    assert service["status"] == "running"
    assert service["enabled"] is True
    assert service["port"] == 8090

    # Verify category summary
    assert "ai" in data["by_category"]
    assert data["by_category"]["ai"]["total"] == 1
    assert data["by_category"]["ai"]["healthy"] == 1
    assert data["by_category"]["ai"]["unhealthy"] == 0

    # Verify timestamp format
    timestamp = datetime.fromisoformat(data["timestamp"])
    assert isinstance(timestamp, datetime)


@pytest.mark.asyncio
async def test_list_services_filter_by_category(client, mock_redis):
    """Test GET /api/system/services with category filter."""
    # Mock orchestrator with multiple services
    mock_orchestrator = MagicMock()

    mock_ai_service = MagicMock()
    mock_ai_service.name = "ai-service"
    mock_ai_service.display_name = "AI Service"
    mock_ai_service.category = ServiceCategory.AI
    mock_ai_service.status = ContainerServiceStatus.RUNNING
    mock_ai_service.enabled = True
    mock_ai_service.container_id = "abc123"
    mock_ai_service.image = "ai:latest"
    mock_ai_service.port = 8090
    mock_ai_service.failure_count = 0
    mock_ai_service.restart_count = 0
    mock_ai_service.last_restart_at = None

    mock_infra_service = MagicMock()
    mock_infra_service.name = "postgres"
    mock_infra_service.display_name = "PostgreSQL"
    mock_infra_service.category = ServiceCategory.INFRASTRUCTURE
    mock_infra_service.status = ContainerServiceStatus.RUNNING
    mock_infra_service.enabled = True
    mock_infra_service.container_id = "def456"
    mock_infra_service.image = "postgres:16"
    mock_infra_service.port = 5432
    mock_infra_service.failure_count = 0
    mock_infra_service.restart_count = 0
    mock_infra_service.last_restart_at = None

    mock_orchestrator.get_all_services.return_value = [mock_ai_service, mock_infra_service]

    async def mock_get_orchestrator(request):
        return mock_orchestrator

    with patch("backend.api.routes.services.get_orchestrator", mock_get_orchestrator):
        # Filter by AI category
        response = await client.get("/api/system/services?category=ai")

        assert response.status_code == 200
        data = response.json()

        # Should only return AI service
        assert len(data["services"]) == 1
        assert data["services"][0]["name"] == "ai-service"
        assert data["services"][0]["category"] == "ai"

        # But category summaries should include all services
        assert data["by_category"]["ai"]["total"] == 1
        assert data["by_category"]["infrastructure"]["total"] == 1


@pytest.mark.asyncio
async def test_list_services_with_unhealthy_services(client, mock_redis):
    """Test GET /api/system/services correctly counts healthy/unhealthy services."""
    mock_orchestrator = MagicMock()

    # Create healthy service
    mock_healthy = MagicMock()
    mock_healthy.name = "healthy-service"
    mock_healthy.display_name = "Healthy Service"
    mock_healthy.category = ServiceCategory.AI
    mock_healthy.status = ContainerServiceStatus.RUNNING
    mock_healthy.enabled = True
    mock_healthy.container_id = "abc123"
    mock_healthy.image = "test:latest"
    mock_healthy.port = 8090
    mock_healthy.failure_count = 0
    mock_healthy.restart_count = 0
    mock_healthy.last_restart_at = None

    # Create unhealthy service
    mock_unhealthy = MagicMock()
    mock_unhealthy.name = "unhealthy-service"
    mock_unhealthy.display_name = "Unhealthy Service"
    mock_unhealthy.category = ServiceCategory.AI
    mock_unhealthy.status = ContainerServiceStatus.UNHEALTHY
    mock_unhealthy.enabled = True
    mock_unhealthy.container_id = "def456"
    mock_unhealthy.image = "test:latest"
    mock_unhealthy.port = 8091
    mock_unhealthy.failure_count = 3
    mock_unhealthy.restart_count = 1
    mock_unhealthy.last_restart_at = datetime.now(UTC)

    mock_orchestrator.get_all_services.return_value = [mock_healthy, mock_unhealthy]

    async def mock_get_orchestrator(request):
        return mock_orchestrator

    with patch("backend.api.routes.services.get_orchestrator", mock_get_orchestrator):
        response = await client.get("/api/system/services")

        assert response.status_code == 200
        data = response.json()

        # Verify category summary
        assert data["by_category"]["ai"]["total"] == 2
        assert data["by_category"]["ai"]["healthy"] == 1
        assert data["by_category"]["ai"]["unhealthy"] == 1


@pytest.mark.asyncio
async def test_list_services_calculates_uptime(client, mock_redis):
    """Test GET /api/system/services correctly calculates uptime."""
    mock_orchestrator = MagicMock()

    # Service with recent restart
    last_restart = datetime.now(UTC)

    mock_service = MagicMock()
    mock_service.name = "test-service"
    mock_service.display_name = "Test Service"
    mock_service.category = ServiceCategory.AI
    mock_service.status = ContainerServiceStatus.RUNNING
    mock_service.enabled = True
    mock_service.container_id = "abc123"
    mock_service.image = "test:latest"
    mock_service.port = 8090
    mock_service.failure_count = 0
    mock_service.restart_count = 1
    mock_service.last_restart_at = last_restart

    mock_orchestrator.get_all_services.return_value = [mock_service]

    async def mock_get_orchestrator(request):
        return mock_orchestrator

    with patch("backend.api.routes.services.get_orchestrator", mock_get_orchestrator):
        response = await client.get("/api/system/services")

        assert response.status_code == 200
        data = response.json()

        service = data["services"][0]
        # Uptime should be a small number (seconds since last_restart)
        assert service["uptime_seconds"] is not None
        assert service["uptime_seconds"] >= 0
        assert service["uptime_seconds"] < 60  # Should be less than a minute


@pytest.mark.asyncio
async def test_list_services_stopped_service_has_null_uptime(client, mock_redis):
    """Test GET /api/system/services returns null uptime for stopped services."""
    mock_orchestrator = MagicMock()

    mock_service = MagicMock()
    mock_service.name = "stopped-service"
    mock_service.display_name = "Stopped Service"
    mock_service.category = ServiceCategory.AI
    mock_service.status = ContainerServiceStatus.STOPPED
    mock_service.enabled = True
    mock_service.container_id = None
    mock_service.image = "test:latest"
    mock_service.port = 8090
    mock_service.failure_count = 0
    mock_service.restart_count = 0
    mock_service.last_restart_at = None

    mock_orchestrator.get_all_services.return_value = [mock_service]

    async def mock_get_orchestrator(request):
        return mock_orchestrator

    with patch("backend.api.routes.services.get_orchestrator", mock_get_orchestrator):
        response = await client.get("/api/system/services")

        assert response.status_code == 200
        data = response.json()

        service = data["services"][0]
        assert service["uptime_seconds"] is None


# =============================================================================
# Restart Service Endpoint Tests
# =============================================================================


@pytest.mark.asyncio
async def test_restart_service_success(client, mock_redis):
    """Test POST /api/system/services/{name}/restart successfully restarts a service."""
    mock_orchestrator = AsyncMock()

    mock_service = MagicMock()
    mock_service.name = "test-service"
    mock_service.display_name = "Test Service"
    mock_service.category = ServiceCategory.AI
    mock_service.status = ContainerServiceStatus.RUNNING
    mock_service.enabled = True
    mock_service.container_id = "abc123"
    mock_service.image = "test:latest"
    mock_service.port = 8090
    mock_service.failure_count = 0
    mock_service.restart_count = 0
    mock_service.last_restart_at = None

    mock_orchestrator.get_service.return_value = mock_service
    mock_orchestrator.restart_service.return_value = True

    async def mock_get_orchestrator(request):
        return mock_orchestrator

    with patch("backend.api.routes.services.get_orchestrator", mock_get_orchestrator):
        response = await client.post("/api/system/services/test-service/restart")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "restart initiated" in data["message"].lower()
        assert data["service"]["name"] == "test-service"

        # Verify restart_service was called with reset_failures=True
        mock_orchestrator.restart_service.assert_called_once_with(
            "test-service", reset_failures=True
        )


@pytest.mark.asyncio
async def test_restart_service_not_found(client, mock_redis):
    """Test POST /api/system/services/{name}/restart returns 404 for non-existent service."""
    mock_orchestrator = AsyncMock()
    mock_orchestrator.get_service.return_value = None

    async def mock_get_orchestrator(request):
        return mock_orchestrator

    with patch("backend.api.routes.services.get_orchestrator", mock_get_orchestrator):
        response = await client.post("/api/system/services/nonexistent/restart")

        assert response.status_code == 404
        data = response.json()
        error_msg = get_error_message(data).lower()
        assert "not found" in error_msg


@pytest.mark.asyncio
async def test_restart_service_disabled(client, mock_redis):
    """Test POST /api/system/services/{name}/restart returns 400 for disabled service."""
    mock_orchestrator = AsyncMock()

    mock_service = MagicMock()
    mock_service.name = "disabled-service"
    mock_service.display_name = "Disabled Service"
    mock_service.category = ServiceCategory.AI
    mock_service.status = ContainerServiceStatus.DISABLED
    mock_service.enabled = False
    mock_service.container_id = None
    mock_service.image = "test:latest"
    mock_service.port = 8090
    mock_service.failure_count = 10
    mock_service.restart_count = 5
    mock_service.last_restart_at = None

    mock_orchestrator.get_service.return_value = mock_service

    async def mock_get_orchestrator(request):
        return mock_orchestrator

    with patch("backend.api.routes.services.get_orchestrator", mock_get_orchestrator):
        response = await client.post("/api/system/services/disabled-service/restart")

        assert response.status_code == 400
        data = response.json()
        error_msg = get_error_message(data).lower()
        assert "disabled" in error_msg


@pytest.mark.asyncio
async def test_restart_service_orchestrator_not_available(client, mock_redis):
    """Test POST /api/system/services/{name}/restart returns 503 when orchestrator unavailable."""

    async def mock_get_orchestrator_unavailable(request):
        from fastapi import HTTPException

        raise HTTPException(503, "Container orchestrator not available")

    with patch("backend.api.routes.services.get_orchestrator", mock_get_orchestrator_unavailable):
        response = await client.post("/api/system/services/test-service/restart")

        assert response.status_code == 503
        data = response.json()
        error_msg = get_error_message(data).lower()
        assert "orchestrator" in error_msg or "not available" in error_msg


# =============================================================================
# Enable Service Endpoint Tests
# =============================================================================


@pytest.mark.asyncio
async def test_enable_service_success(client, mock_redis):
    """Test POST /api/system/services/{name}/enable successfully enables a service."""
    mock_orchestrator = AsyncMock()

    mock_service = MagicMock()
    mock_service.name = "test-service"
    mock_service.display_name = "Test Service"
    mock_service.category = ServiceCategory.AI
    mock_service.status = ContainerServiceStatus.DISABLED
    mock_service.enabled = False
    mock_service.container_id = None
    mock_service.image = "test:latest"
    mock_service.port = 8090
    mock_service.failure_count = 10
    mock_service.restart_count = 5
    mock_service.last_restart_at = None

    mock_orchestrator.get_service.return_value = mock_service
    mock_orchestrator.enable_service.return_value = True

    async def mock_get_orchestrator(request):
        return mock_orchestrator

    with patch("backend.api.routes.services.get_orchestrator", mock_get_orchestrator):
        response = await client.post("/api/system/services/test-service/enable")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "enabled" in data["message"].lower()
        assert data["service"]["name"] == "test-service"

        # Verify enable_service was called
        mock_orchestrator.enable_service.assert_called_once_with("test-service")


@pytest.mark.asyncio
async def test_enable_service_not_found(client, mock_redis):
    """Test POST /api/system/services/{name}/enable returns 404 for non-existent service."""
    mock_orchestrator = AsyncMock()
    mock_orchestrator.get_service.return_value = None

    async def mock_get_orchestrator(request):
        return mock_orchestrator

    with patch("backend.api.routes.services.get_orchestrator", mock_get_orchestrator):
        response = await client.post("/api/system/services/nonexistent/enable")

        assert response.status_code == 404
        data = response.json()
        error_msg = get_error_message(data).lower()
        assert "not found" in error_msg


# =============================================================================
# Disable Service Endpoint Tests
# =============================================================================


@pytest.mark.asyncio
async def test_disable_service_success(client, mock_redis):
    """Test POST /api/system/services/{name}/disable successfully disables a service."""
    mock_orchestrator = AsyncMock()

    mock_service = MagicMock()
    mock_service.name = "test-service"
    mock_service.display_name = "Test Service"
    mock_service.category = ServiceCategory.AI
    mock_service.status = ContainerServiceStatus.RUNNING
    mock_service.enabled = True
    mock_service.container_id = "abc123"
    mock_service.image = "test:latest"
    mock_service.port = 8090
    mock_service.failure_count = 0
    mock_service.restart_count = 0
    mock_service.last_restart_at = None

    mock_orchestrator.get_service.return_value = mock_service
    mock_orchestrator.disable_service.return_value = True

    async def mock_get_orchestrator(request):
        return mock_orchestrator

    with patch("backend.api.routes.services.get_orchestrator", mock_get_orchestrator):
        response = await client.post("/api/system/services/test-service/disable")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "disabled" in data["message"].lower()
        assert data["service"]["name"] == "test-service"

        # Verify disable_service was called
        mock_orchestrator.disable_service.assert_called_once_with("test-service")


@pytest.mark.asyncio
async def test_disable_service_not_found(client, mock_redis):
    """Test POST /api/system/services/{name}/disable returns 404 for non-existent service."""
    mock_orchestrator = AsyncMock()
    mock_orchestrator.get_service.return_value = None

    async def mock_get_orchestrator(request):
        return mock_orchestrator

    with patch("backend.api.routes.services.get_orchestrator", mock_get_orchestrator):
        response = await client.post("/api/system/services/nonexistent/disable")

        assert response.status_code == 404
        data = response.json()
        error_msg = get_error_message(data).lower()
        assert "not found" in error_msg


# =============================================================================
# Start Service Endpoint Tests
# =============================================================================


@pytest.mark.asyncio
async def test_start_service_success(client, mock_redis):
    """Test POST /api/system/services/{name}/start successfully starts a stopped service."""
    mock_orchestrator = AsyncMock()

    mock_service = MagicMock()
    mock_service.name = "test-service"
    mock_service.display_name = "Test Service"
    mock_service.category = ServiceCategory.AI
    mock_service.status = ContainerServiceStatus.STOPPED
    mock_service.enabled = True
    mock_service.container_id = None
    mock_service.image = "test:latest"
    mock_service.port = 8090
    mock_service.failure_count = 0
    mock_service.restart_count = 0
    mock_service.last_restart_at = None

    mock_orchestrator.get_service.return_value = mock_service
    mock_orchestrator.start_service.return_value = True

    async def mock_get_orchestrator(request):
        return mock_orchestrator

    with patch("backend.api.routes.services.get_orchestrator", mock_get_orchestrator):
        response = await client.post("/api/system/services/test-service/start")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "start initiated" in data["message"].lower()
        assert data["service"]["name"] == "test-service"

        # Verify start_service was called
        mock_orchestrator.start_service.assert_called_once_with("test-service")


@pytest.mark.asyncio
async def test_start_service_already_running(client, mock_redis):
    """Test POST /api/system/services/{name}/start returns 400 for already running service."""
    mock_orchestrator = AsyncMock()

    mock_service = MagicMock()
    mock_service.name = "running-service"
    mock_service.display_name = "Running Service"
    mock_service.category = ServiceCategory.AI
    mock_service.status = ContainerServiceStatus.RUNNING
    mock_service.enabled = True
    mock_service.container_id = "abc123"
    mock_service.image = "test:latest"
    mock_service.port = 8090
    mock_service.failure_count = 0
    mock_service.restart_count = 0
    mock_service.last_restart_at = None

    mock_orchestrator.get_service.return_value = mock_service

    async def mock_get_orchestrator(request):
        return mock_orchestrator

    with patch("backend.api.routes.services.get_orchestrator", mock_get_orchestrator):
        response = await client.post("/api/system/services/running-service/start")

        assert response.status_code == 400
        data = response.json()
        error_msg = get_error_message(data).lower()
        assert "already running" in error_msg


@pytest.mark.asyncio
async def test_start_service_disabled(client, mock_redis):
    """Test POST /api/system/services/{name}/start returns 400 for disabled service."""
    mock_orchestrator = AsyncMock()

    mock_service = MagicMock()
    mock_service.name = "disabled-service"
    mock_service.display_name = "Disabled Service"
    mock_service.category = ServiceCategory.AI
    mock_service.status = ContainerServiceStatus.DISABLED
    mock_service.enabled = False
    mock_service.container_id = None
    mock_service.image = "test:latest"
    mock_service.port = 8090
    mock_service.failure_count = 10
    mock_service.restart_count = 5
    mock_service.last_restart_at = None

    mock_orchestrator.get_service.return_value = mock_service

    async def mock_get_orchestrator(request):
        return mock_orchestrator

    with patch("backend.api.routes.services.get_orchestrator", mock_get_orchestrator):
        response = await client.post("/api/system/services/disabled-service/start")

        assert response.status_code == 400
        data = response.json()
        error_msg = get_error_message(data).lower()
        assert "disabled" in error_msg


@pytest.mark.asyncio
async def test_start_service_not_found(client, mock_redis):
    """Test POST /api/system/services/{name}/start returns 404 for non-existent service."""
    mock_orchestrator = AsyncMock()
    mock_orchestrator.get_service.return_value = None

    async def mock_get_orchestrator(request):
        return mock_orchestrator

    with patch("backend.api.routes.services.get_orchestrator", mock_get_orchestrator):
        response = await client.post("/api/system/services/nonexistent/start")

        assert response.status_code == 404
        data = response.json()
        error_msg = get_error_message(data).lower()
        assert "not found" in error_msg


# =============================================================================
# Edge Cases and Additional Tests
# =============================================================================


@pytest.mark.asyncio
async def test_list_services_with_container_id_truncation(client, mock_redis):
    """Test that container IDs are truncated to 12 characters."""
    mock_orchestrator = MagicMock()

    mock_service = MagicMock()
    mock_service.name = "test-service"
    mock_service.display_name = "Test Service"
    mock_service.category = ServiceCategory.AI
    mock_service.status = ContainerServiceStatus.RUNNING
    mock_service.enabled = True
    # Full container ID (64 characters)
    mock_service.container_id = "abc123def456789012345678901234567890123456789012345678901234"
    mock_service.image = "test:latest"
    mock_service.port = 8090
    mock_service.failure_count = 0
    mock_service.restart_count = 0
    mock_service.last_restart_at = None

    mock_orchestrator.get_all_services.return_value = [mock_service]

    async def mock_get_orchestrator(request):
        return mock_orchestrator

    with patch("backend.api.routes.services.get_orchestrator", mock_get_orchestrator):
        response = await client.get("/api/system/services")

        assert response.status_code == 200
        data = response.json()

        # Container ID should be truncated to 12 characters
        service = data["services"][0]
        assert len(service["container_id"]) == 12
        assert service["container_id"] == "abc123def456"


@pytest.mark.asyncio
async def test_list_services_with_multiple_categories(client, mock_redis):
    """Test list services with services from all three categories."""
    mock_orchestrator = MagicMock()

    # Infrastructure service
    mock_infra = MagicMock()
    mock_infra.name = "postgres"
    mock_infra.display_name = "PostgreSQL"
    mock_infra.category = ServiceCategory.INFRASTRUCTURE
    mock_infra.status = ContainerServiceStatus.RUNNING
    mock_infra.enabled = True
    mock_infra.container_id = "abc123"
    mock_infra.image = "postgres:16"
    mock_infra.port = 5432
    mock_infra.failure_count = 0
    mock_infra.restart_count = 0
    mock_infra.last_restart_at = None

    # AI service
    mock_ai = MagicMock()
    mock_ai.name = "ai-yolo26"
    mock_ai.display_name = "YOLO26"
    mock_ai.category = ServiceCategory.AI
    mock_ai.status = ContainerServiceStatus.RUNNING
    mock_ai.enabled = True
    mock_ai.container_id = "def456"
    mock_ai.image = "yolo26:latest"
    mock_ai.port = 8095
    mock_ai.failure_count = 0
    mock_ai.restart_count = 0
    mock_ai.last_restart_at = None

    # Monitoring service
    mock_monitoring = MagicMock()
    mock_monitoring.name = "grafana"
    mock_monitoring.display_name = "Grafana"
    mock_monitoring.category = ServiceCategory.MONITORING
    mock_monitoring.status = ContainerServiceStatus.RUNNING
    mock_monitoring.enabled = True
    mock_monitoring.container_id = "ghi789"
    mock_monitoring.image = "grafana:latest"
    mock_monitoring.port = 3000
    mock_monitoring.failure_count = 0
    mock_monitoring.restart_count = 0
    mock_monitoring.last_restart_at = None

    mock_orchestrator.get_all_services.return_value = [mock_infra, mock_ai, mock_monitoring]

    async def mock_get_orchestrator(request):
        return mock_orchestrator

    with patch("backend.api.routes.services.get_orchestrator", mock_get_orchestrator):
        response = await client.get("/api/system/services")

        assert response.status_code == 200
        data = response.json()

        # Verify all services are present
        assert len(data["services"]) == 3

        # Verify category summaries for all three categories
        assert "infrastructure" in data["by_category"]
        assert "ai" in data["by_category"]
        assert "monitoring" in data["by_category"]

        assert data["by_category"]["infrastructure"]["total"] == 1
        assert data["by_category"]["ai"]["total"] == 1
        assert data["by_category"]["monitoring"]["total"] == 1
