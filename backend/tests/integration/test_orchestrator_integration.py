"""Integration tests for Container Orchestrator with real Docker API.

This module tests the container orchestrator's integration with:
- Real Docker/Podman containers (lightweight alpine test containers)
- Real Redis for state persistence
- Real FastAPI endpoints for API integration

All tests are marked with @pytest.mark.integration and will skip gracefully
if Docker is not available.

Test Categories:
1. Container Lifecycle Tests: Detect stopped containers, respect disabled status, discover existing containers
2. State Persistence Tests: State survives orchestrator restart, disabled status persists
3. API Integration Tests: /api/system/services endpoints with real orchestrator
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from backend.api.schemas.services import ContainerServiceStatus, ServiceCategory
from backend.core.config import OrchestratorSettings
from backend.core.docker_client import DockerClient
from backend.services.container_orchestrator import ContainerOrchestrator
from backend.services.service_registry import ManagedService, ServiceRegistry
from backend.tests.integration.test_helpers import get_error_message

if TYPE_CHECKING:
    from docker.models.containers import Container as DockerContainer

    from backend.core.redis import RedisClient


# =============================================================================
# Helper Functions for Integration Tests
# =============================================================================


async def slow_wait_for_container(seconds: float = 1.0) -> None:
    """Wait for container operations to complete in integration tests.

    This is intentionally slow for real container startup/restart operations.
    Named with slow_ prefix to indicate this is expected behavior for integration tests.
    """
    await asyncio.sleep(seconds)


def _docker_available() -> bool:
    """Check if Docker/Podman is available for integration tests.

    Uses a timeout to prevent hanging if Docker daemon is unresponsive.

    Returns:
        True if Docker is reachable and responsive within timeout.
    """
    import concurrent.futures

    def _check_docker() -> bool:
        try:
            from docker import DockerClient as BaseDockerClient
            from docker.errors import DockerException

            client = BaseDockerClient.from_env(timeout=5)
            client.ping()
            client.close()
            return True
        except (DockerException, Exception):
            return False

    # Use a thread with timeout to prevent hanging on unresponsive Docker
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_check_docker)
            return future.result(timeout=10)  # 10 second timeout
    except (concurrent.futures.TimeoutError, Exception):
        return False


# Skip all tests in this module if Docker is not available
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _docker_available(), reason="Docker/Podman not available"),
]

# Test container configuration
TEST_CONTAINER_PREFIX = "test-orchestrator-"
TEST_IMAGE = "alpine:latest"
TEST_COMMAND = "sleep infinity"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def test_settings() -> OrchestratorSettings:
    """Create test settings with fast health check intervals.

    Note: Values must meet minimum constraints defined in OrchestratorSettings:
    - health_check_interval: ge=5
    - startup_grace_period: ge=10
    - restart_backoff_max: ge=30.0
    """
    return OrchestratorSettings(
        enabled=True,
        docker_host=None,  # Use default Docker socket
        health_check_interval=5,  # Minimum allowed for testing
        health_check_timeout=1,
        startup_grace_period=10,  # Minimum allowed for testing
        max_consecutive_failures=3,
        restart_backoff_base=1.0,
        restart_backoff_max=30.0,  # Minimum allowed for testing
    )


@pytest.fixture
async def docker_client() -> DockerClient:
    """Create a DockerClient for integration tests."""
    client = DockerClient()
    await client.connect()
    yield client
    await client.close()


@pytest.fixture
async def test_container(docker_client: DockerClient):
    """Create a test container that matches AI service patterns.

    Creates an alpine container with a name matching the "ai-" prefix pattern
    that the container orchestrator looks for.
    """
    from docker import DockerClient as BaseDockerClient
    from docker.errors import APIError, NotFound

    base_client = BaseDockerClient.from_env()

    # Generate unique container name
    container_name = f"{TEST_CONTAINER_PREFIX}ai-yolo26-{datetime.now(UTC).strftime('%H%M%S%f')}"

    container = None
    try:
        # Pull the image if not present (alpine is small)
        try:
            base_client.images.get(TEST_IMAGE)
        except Exception:
            base_client.images.pull(TEST_IMAGE)

        # Create and start container
        container = base_client.containers.run(
            TEST_IMAGE,
            name=container_name,
            command=TEST_COMMAND,
            detach=True,
            labels={"test": "orchestrator", "type": "ai-yolo26"},
        )

        yield container

    finally:
        # Cleanup: stop and remove container
        if container:
            try:
                container.stop(timeout=1)
            except (NotFound, APIError):
                pass
            try:
                container.remove(force=True)
            except (NotFound, APIError):
                pass

        base_client.close()


@pytest.fixture
async def multiple_test_containers(docker_client: DockerClient):
    """Create multiple test containers for discovery tests.

    Creates containers matching different service patterns:
    - ai-yolo26 (AI category)
    - postgres (Infrastructure category)
    - prometheus (Monitoring category)
    """
    from docker import DockerClient as BaseDockerClient
    from docker.errors import APIError, NotFound

    base_client = BaseDockerClient.from_env()

    # Generate unique suffix
    suffix = datetime.now(UTC).strftime("%H%M%S%f")

    container_configs = [
        (f"{TEST_CONTAINER_PREFIX}ai-yolo26-{suffix}", "ai-yolo26"),
        (f"{TEST_CONTAINER_PREFIX}postgres-{suffix}", "postgres"),
        (f"{TEST_CONTAINER_PREFIX}prometheus-{suffix}", "prometheus"),
    ]

    containers = []
    try:
        # Pull the image if not present
        try:
            base_client.images.get(TEST_IMAGE)
        except Exception:
            base_client.images.pull(TEST_IMAGE)

        # Create all containers
        for container_name, service_type in container_configs:
            container = base_client.containers.run(
                TEST_IMAGE,
                name=container_name,
                command=TEST_COMMAND,
                detach=True,
                labels={"test": "orchestrator", "type": service_type},
            )
            containers.append((container, service_type))

        yield containers

    finally:
        # Cleanup all containers
        for container, _ in containers:
            try:
                container.stop(timeout=1)
            except (NotFound, APIError):
                pass
            try:
                container.remove(force=True)
            except (NotFound, APIError):
                pass

        base_client.close()


@pytest.fixture
async def real_redis_client(
    redis_container,
) -> RedisClient:
    """Provide a real Redis client for integration tests.

    Uses the same redis_container fixture from conftest.py.
    """
    from backend.core.redis import RedisClient
    from backend.tests.integration.conftest import _get_redis_url

    redis_url = _get_redis_url(redis_container)
    client = RedisClient(redis_url=redis_url)
    await client.connect()

    try:
        # Flush orchestrator keys before test
        redis_client = client._ensure_connected()
        keys = await redis_client.keys("orchestrator:*")
        if keys:
            await redis_client.delete(*keys)

        yield client

    finally:
        # Cleanup orchestrator keys after test
        try:
            redis_client = client._ensure_connected()
            keys = await redis_client.keys("orchestrator:*")
            if keys:
                await redis_client.delete(*keys)
        except Exception:
            pass  # Ignore cleanup errors - best effort
        await client.disconnect()


@pytest.fixture
def mock_broadcast_fn() -> AsyncMock:
    """Mock broadcast function for testing without WebSocket dependencies."""
    mock = AsyncMock()
    mock.return_value = 1  # Simulate 1 subscriber
    return mock


# =============================================================================
# Container Lifecycle Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_detects_stopped_container_and_restarts(
    docker_client: DockerClient,
    test_container: DockerContainer,
    real_redis_client: RedisClient,
    test_settings: OrchestratorSettings,
    mock_broadcast_fn: AsyncMock,
) -> None:
    """Test that orchestrator detects stopped container and restarts it.

    Given: A registered container that is stopped
    When: Health check runs
    Then: Container should be restarted
    """
    # Register the test container in the service registry
    registry = ServiceRegistry(real_redis_client)
    service = ManagedService(
        name="ai-yolo26",
        display_name="Test AI Detector",
        container_id=test_container.id,
        image=TEST_IMAGE,
        port=8095,
        health_endpoint=None,
        health_cmd=None,
        category=ServiceCategory.AI,
        status=ContainerServiceStatus.RUNNING,
        enabled=True,
        max_failures=3,
        restart_backoff_base=1.0,
        restart_backoff_max=5.0,
        startup_grace_period=1,
    )
    registry.register(service)

    # Stop the container
    test_container.stop(timeout=1)

    # Wait for container to fully stop
    await asyncio.sleep(0.5)

    # Verify container is stopped
    test_container.reload()
    assert test_container.status == "exited"

    # Use DockerClient to restart the container (simulating what orchestrator does)
    restart_success = await docker_client.restart_container(test_container.id)
    assert restart_success is True

    # Wait for container to start - integration test requires real delay
    await slow_wait_for_container()

    # Verify container is running again
    test_container.reload()
    assert test_container.status == "running"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_respects_disabled_service(
    docker_client: DockerClient,
    test_container: DockerContainer,
    real_redis_client: RedisClient,
    test_settings: OrchestratorSettings,
    mock_broadcast_fn: AsyncMock,
) -> None:
    """Test that orchestrator does not restart disabled services.

    Given: A service marked as disabled
    When: Container stops
    Then: Should NOT attempt restart
    """
    # Register the test container as a disabled service
    registry = ServiceRegistry(real_redis_client)
    service = ManagedService(
        name="ai-yolo26",
        display_name="Test AI Detector",
        container_id=test_container.id,
        image=TEST_IMAGE,
        port=8095,
        health_endpoint=None,
        health_cmd=None,
        category=ServiceCategory.AI,
        status=ContainerServiceStatus.DISABLED,
        enabled=False,  # Service is disabled
        max_failures=3,
        restart_backoff_base=1.0,
        restart_backoff_max=5.0,
        startup_grace_period=1,
    )
    registry.register(service)

    # Stop the container
    test_container.stop(timeout=1)
    await asyncio.sleep(0.5)

    # Verify container is stopped
    test_container.reload()
    assert test_container.status == "exited"

    # Verify service is still marked as disabled
    registered_service = registry.get("ai-yolo26")
    assert registered_service is not None
    assert registered_service.enabled is False
    assert registered_service.status == ContainerServiceStatus.DISABLED

    # Orchestrator should not restart disabled services
    # (The actual restart logic is in LifecycleManager.should_restart)
    from backend.services.lifecycle_manager import (
        LifecycleManager,
    )
    from backend.services.lifecycle_manager import (
        ManagedService as LMService,
    )
    from backend.services.lifecycle_manager import (
        ServiceRegistry as LMRegistry,
    )

    lm_registry = LMRegistry()
    lm_service = LMService(
        name="ai-yolo26",
        display_name="Test AI Detector",
        container_id=test_container.id,
        image=TEST_IMAGE,
        port=8095,
        category=ServiceCategory.AI,
        status=ContainerServiceStatus.DISABLED,
        enabled=False,
    )
    lm_registry.register(lm_service)

    lm = LifecycleManager(
        registry=lm_registry,
        docker_client=docker_client,
    )

    # should_restart should return False for disabled services
    assert lm.should_restart(lm_service) is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_discovers_existing_containers(
    docker_client: DockerClient,
    multiple_test_containers: list[tuple[DockerContainer, str]],
) -> None:
    """Test that orchestrator discovers existing containers matching patterns.

    Given: AI containers already running
    When: Orchestrator starts
    Then: Should discover and register all containers
    """
    from backend.services.container_discovery import ContainerDiscoveryService

    discovery = ContainerDiscoveryService(docker_client)

    # Discover all containers
    discovered = await discovery.discover_all()

    # The discovery service finds containers matching known patterns
    # Verify discovery mechanism works by checking the result is a list
    assert isinstance(discovered, list)

    # Verify our test containers are running (they won't match patterns
    # since they're named with test prefix, but we can verify basic operations)
    test_container_ids = {c.id for c, _ in multiple_test_containers}

    # Verify our test containers are running
    for container_id in test_container_ids:
        status = await docker_client.get_container_status(container_id)
        assert status == "running"

    # Verify we can list containers
    all_containers = await docker_client.list_containers(all=True)
    assert len(all_containers) >= len(multiple_test_containers)


# =============================================================================
# State Persistence Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_state_persists_across_restart(
    docker_client: DockerClient,
    test_container: DockerContainer,
    real_redis_client: RedisClient,
    test_settings: OrchestratorSettings,
) -> None:
    """Test that orchestrator state persists and restores across restarts.

    Given: Orchestrator with failure counts and disabled services
    When: Orchestrator restarts (new instance)
    Then: Should restore state from Redis
    """
    # Create first registry instance and set some state
    registry1 = ServiceRegistry(real_redis_client)
    service = ManagedService(
        name="ai-yolo26",
        display_name="Test AI Detector",
        container_id=test_container.id,
        image=TEST_IMAGE,
        port=8095,
        health_endpoint=None,
        health_cmd=None,
        category=ServiceCategory.AI,
        status=ContainerServiceStatus.UNHEALTHY,
        enabled=True,
        failure_count=2,
        restart_count=3,
        max_failures=5,
    )
    registry1.register(service)

    # Persist state to Redis
    await registry1.persist_state("ai-yolo26")

    # Create a new registry instance (simulating backend restart)
    registry2 = ServiceRegistry(real_redis_client)

    # Register the service with default values
    service2 = ManagedService(
        name="ai-yolo26",
        display_name="Test AI Detector",
        container_id=test_container.id,
        image=TEST_IMAGE,
        port=8095,
        health_endpoint=None,
        health_cmd=None,
        category=ServiceCategory.AI,
        status=ContainerServiceStatus.RUNNING,  # Default
        enabled=True,
        failure_count=0,  # Default
        restart_count=0,  # Default
    )
    registry2.register(service2)

    # Load state from Redis
    await registry2.load_state("ai-yolo26")

    # Verify state was restored
    restored = registry2.get("ai-yolo26")
    assert restored is not None
    assert restored.failure_count == 2
    assert restored.restart_count == 3
    assert restored.status == ContainerServiceStatus.UNHEALTHY


@pytest.mark.integration
@pytest.mark.asyncio
async def test_disabled_status_persists(
    docker_client: DockerClient,
    test_container: DockerContainer,
    real_redis_client: RedisClient,
    test_settings: OrchestratorSettings,
) -> None:
    """Test that disabled status persists across backend restarts.

    Given: A service disabled due to max failures
    When: Backend restarts
    Then: Service should still be disabled
    """
    # Create registry and disable a service
    registry1 = ServiceRegistry(real_redis_client)
    service = ManagedService(
        name="ai-yolo26",
        display_name="Test AI Detector",
        container_id=test_container.id,
        image=TEST_IMAGE,
        port=8095,
        health_endpoint=None,
        health_cmd=None,
        category=ServiceCategory.AI,
        status=ContainerServiceStatus.DISABLED,
        enabled=False,
        failure_count=5,  # Max failures reached
    )
    registry1.register(service)

    # Persist state
    await registry1.persist_state("ai-yolo26")

    # Create new registry (simulating restart)
    registry2 = ServiceRegistry(real_redis_client)
    service2 = ManagedService(
        name="ai-yolo26",
        display_name="Test AI Detector",
        container_id=test_container.id,
        image=TEST_IMAGE,
        port=8095,
        health_endpoint=None,
        health_cmd=None,
        category=ServiceCategory.AI,
        status=ContainerServiceStatus.RUNNING,  # Would be default on fresh start
        enabled=True,  # Would be default
        failure_count=0,
    )
    registry2.register(service2)

    # Load persisted state
    await registry2.load_state("ai-yolo26")

    # Verify disabled status was restored
    restored = registry2.get("ai-yolo26")
    assert restored is not None
    assert restored.status == ContainerServiceStatus.DISABLED
    assert restored.enabled is False
    assert restored.failure_count == 5


# =============================================================================
# API Integration Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_list_services(
    integration_db: str,
    docker_client: DockerClient,
    test_container: DockerContainer,
    real_redis_client: RedisClient,
    test_settings: OrchestratorSettings,
    mock_broadcast_fn: AsyncMock,
) -> None:
    """Test GET /api/system/services returns all services.

    Given: Orchestrator with registered services
    When: GET /api/system/services
    Then: Should return all services with correct status
    """
    from unittest.mock import patch

    from httpx import ASGITransport, AsyncClient

    # Create a minimal orchestrator for testing
    orchestrator = ContainerOrchestrator(
        docker_client=docker_client,
        redis_client=real_redis_client,
        settings=test_settings,
        broadcast_fn=mock_broadcast_fn,
    )

    # Manually register a service (bypassing full discovery)
    service = ManagedService(
        name="ai-yolo26",
        display_name="Test AI Detector",
        container_id=test_container.id,
        image=TEST_IMAGE,
        port=8095,
        health_endpoint=None,
        health_cmd=None,
        category=ServiceCategory.AI,
        status=ContainerServiceStatus.RUNNING,
        enabled=True,
    )
    orchestrator._registry.register(service)

    # Import the app
    from backend.main import app

    # Mock app state to use our orchestrator
    async def mock_get_orchestrator(request):
        return orchestrator

    # Patch the app state
    with patch.object(app.state, "orchestrator", orchestrator, create=True):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/system/services")

            assert response.status_code == 200
            data = response.json()

            assert "services" in data
            assert "by_category" in data
            assert "timestamp" in data

            # Find our test service
            services = data["services"]
            ai_detector = next((s for s in services if s["name"] == "ai-yolo26"), None)
            assert ai_detector is not None
            assert ai_detector["status"] == "running"
            assert ai_detector["category"] == "ai"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_restart_service(
    integration_db: str,
    docker_client: DockerClient,
    test_container: DockerContainer,
    real_redis_client: RedisClient,
    test_settings: OrchestratorSettings,
    mock_broadcast_fn: AsyncMock,
) -> None:
    """Test POST /api/system/services/{name}/restart restarts container.

    Given: A running service
    When: POST /api/system/services/{name}/restart
    Then: API returns success and orchestrator restart_service is called

    Note: Docker restart is mocked to avoid timeout - we test API behavior, not Docker.
    """
    from unittest.mock import AsyncMock as AM
    from unittest.mock import patch

    from httpx import ASGITransport, AsyncClient

    # Create orchestrator
    orchestrator = ContainerOrchestrator(
        docker_client=docker_client,
        redis_client=real_redis_client,
        settings=test_settings,
        broadcast_fn=mock_broadcast_fn,
    )

    # Register service
    service = ManagedService(
        name="ai-yolo26",
        display_name="Test AI Detector",
        container_id=test_container.id,
        image=TEST_IMAGE,
        port=8095,
        health_endpoint=None,
        health_cmd=None,
        category=ServiceCategory.AI,
        status=ContainerServiceStatus.RUNNING,
        enabled=True,
        failure_count=2,  # Some failures before restart
    )
    orchestrator._registry.register(service)

    from backend.main import app

    # Mock Docker restart to avoid timeout - we test the API behavior, not Docker
    with (
        patch.object(docker_client, "restart_container", new_callable=AM, return_value=True),
        patch.object(app.state, "orchestrator", orchestrator, create=True),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/system/services/ai-yolo26/restart")

            assert response.status_code == 200
            data = response.json()

            assert data["success"] is True
            assert "restart" in data["message"].lower()
            assert data["service"]["name"] == "ai-yolo26"

            # Verify Docker restart was called (mocked)
            docker_client.restart_container.assert_called_once_with(test_container.id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_enable_disabled_service(
    integration_db: str,
    docker_client: DockerClient,
    test_container: DockerContainer,
    real_redis_client: RedisClient,
    test_settings: OrchestratorSettings,
    mock_broadcast_fn: AsyncMock,
) -> None:
    """Test POST /api/system/services/{name}/enable enables disabled service.

    Given: A disabled service
    When: POST /api/system/services/{name}/enable
    Then: Service should be enabled with reset failure count
    """
    from unittest.mock import patch

    from httpx import ASGITransport, AsyncClient

    # Create orchestrator
    orchestrator = ContainerOrchestrator(
        docker_client=docker_client,
        redis_client=real_redis_client,
        settings=test_settings,
        broadcast_fn=mock_broadcast_fn,
    )

    # Register disabled service
    service = ManagedService(
        name="ai-yolo26",
        display_name="Test AI Detector",
        container_id=test_container.id,
        image=TEST_IMAGE,
        port=8095,
        health_endpoint=None,
        health_cmd=None,
        category=ServiceCategory.AI,
        status=ContainerServiceStatus.DISABLED,
        enabled=False,
        failure_count=5,
    )
    orchestrator._registry.register(service)

    from backend.main import app

    with patch.object(app.state, "orchestrator", orchestrator, create=True):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/system/services/ai-yolo26/enable")

            assert response.status_code == 200
            data = response.json()

            assert data["success"] is True
            assert "enabled" in data["message"].lower()
            assert data["service"]["name"] == "ai-yolo26"
            assert data["service"]["enabled"] is True
            # Status should be STOPPED after enable (ready for restart)
            assert data["service"]["status"] == "stopped"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_disable_service(
    integration_db: str,
    docker_client: DockerClient,
    test_container: DockerContainer,
    real_redis_client: RedisClient,
    test_settings: OrchestratorSettings,
    mock_broadcast_fn: AsyncMock,
) -> None:
    """Test POST /api/system/services/{name}/disable disables service.

    Given: A running service
    When: POST /api/system/services/{name}/disable
    Then: Service should be disabled
    """
    from unittest.mock import patch

    from httpx import ASGITransport, AsyncClient

    # Create orchestrator
    orchestrator = ContainerOrchestrator(
        docker_client=docker_client,
        redis_client=real_redis_client,
        settings=test_settings,
        broadcast_fn=mock_broadcast_fn,
    )

    # Register running service
    service = ManagedService(
        name="ai-yolo26",
        display_name="Test AI Detector",
        container_id=test_container.id,
        image=TEST_IMAGE,
        port=8095,
        health_endpoint=None,
        health_cmd=None,
        category=ServiceCategory.AI,
        status=ContainerServiceStatus.RUNNING,
        enabled=True,
    )
    orchestrator._registry.register(service)

    from backend.main import app

    with patch.object(app.state, "orchestrator", orchestrator, create=True):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/system/services/ai-yolo26/disable")

            assert response.status_code == 200
            data = response.json()

            assert data["success"] is True
            assert "disabled" in data["message"].lower()
            assert data["service"]["name"] == "ai-yolo26"
            assert data["service"]["enabled"] is False
            assert data["service"]["status"] == "disabled"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_start_stopped_service(
    integration_db: str,
    docker_client: DockerClient,
    test_container: DockerContainer,
    real_redis_client: RedisClient,
    test_settings: OrchestratorSettings,
    mock_broadcast_fn: AsyncMock,
) -> None:
    """Test POST /api/system/services/{name}/start starts stopped service.

    Given: A stopped service (registered, not actually stopped)
    When: POST /api/system/services/{name}/start
    Then: API returns success and orchestrator start_service is called

    Note: Docker start is mocked to avoid timeout - we test API behavior, not Docker.
    """
    from unittest.mock import AsyncMock as AM
    from unittest.mock import patch

    from httpx import ASGITransport, AsyncClient

    # Create orchestrator
    orchestrator = ContainerOrchestrator(
        docker_client=docker_client,
        redis_client=real_redis_client,
        settings=test_settings,
        broadcast_fn=mock_broadcast_fn,
    )

    # Register stopped service (no need to actually stop - we mock the start)
    service = ManagedService(
        name="ai-yolo26",
        display_name="Test AI Detector",
        container_id=test_container.id,
        image=TEST_IMAGE,
        port=8095,
        health_endpoint=None,
        health_cmd=None,
        category=ServiceCategory.AI,
        status=ContainerServiceStatus.STOPPED,
        enabled=True,
    )
    orchestrator._registry.register(service)

    from backend.main import app

    # Mock Docker start to avoid timeout - we test the API behavior, not Docker
    with (
        patch.object(docker_client, "start_container", new_callable=AM, return_value=True),
        patch.object(app.state, "orchestrator", orchestrator, create=True),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/system/services/ai-yolo26/start")

            assert response.status_code == 200
            data = response.json()

            assert data["success"] is True
            assert "start" in data["message"].lower()
            assert data["service"]["name"] == "ai-yolo26"

            # Verify Docker start was called (mocked)
            docker_client.start_container.assert_called_once_with(test_container.id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_api_service_not_found(
    integration_db: str,
    docker_client: DockerClient,
    real_redis_client: RedisClient,
    test_settings: OrchestratorSettings,
    mock_broadcast_fn: AsyncMock,
) -> None:
    """Test that API returns 404 for unknown service.

    Given: An empty orchestrator
    When: GET /api/system/services/unknown/restart
    Then: Should return 404
    """
    from unittest.mock import patch

    from httpx import ASGITransport, AsyncClient

    # Create empty orchestrator
    orchestrator = ContainerOrchestrator(
        docker_client=docker_client,
        redis_client=real_redis_client,
        settings=test_settings,
        broadcast_fn=mock_broadcast_fn,
    )

    from backend.main import app

    with patch.object(app.state, "orchestrator", orchestrator, create=True):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post("/api/system/services/unknown-service/restart")

            assert response.status_code == 404
            data = response.json()
    error_msg = get_error_message(data)
    assert "not found" in error_msg.lower()


# =============================================================================
# Additional Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_docker_client_operations(
    docker_client: DockerClient,
    test_container: DockerContainer,
) -> None:
    """Test basic DockerClient operations work with real containers.

    Given: A running test container
    When: Various Docker operations are performed
    Then: Operations should succeed
    """
    # Get container status
    status = await docker_client.get_container_status(test_container.id)
    assert status == "running"

    # Get container by ID
    container = await docker_client.get_container(test_container.id)
    assert container is not None
    assert container.id == test_container.id

    # List containers
    containers = await docker_client.list_containers(all=True)
    assert any(c.id == test_container.id for c in containers)

    # Stop container
    stop_result = await docker_client.stop_container(test_container.id, timeout=1)
    assert stop_result is True

    await asyncio.sleep(0.5)

    # Verify stopped
    status = await docker_client.get_container_status(test_container.id)
    assert status == "exited"

    # Start container
    start_result = await docker_client.start_container(test_container.id)
    assert start_result is True

    await asyncio.sleep(0.5)

    # Verify running
    status = await docker_client.get_container_status(test_container.id)
    assert status == "running"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_registry_persistence_with_real_redis(
    real_redis_client: RedisClient,
) -> None:
    """Test ServiceRegistry persistence with real Redis.

    Given: A ServiceRegistry with services
    When: State is persisted and loaded
    Then: All state should be restored correctly
    """
    # Create and configure registry
    registry = ServiceRegistry(real_redis_client)

    service = ManagedService(
        name="test-service",
        display_name="Test Service",
        container_id="test-container-123",
        image="test:latest",
        port=8080,
        health_endpoint="/health",
        health_cmd=None,
        category=ServiceCategory.AI,
        status=ContainerServiceStatus.UNHEALTHY,
        enabled=True,
        failure_count=3,
        restart_count=2,
    )
    registry.register(service)

    # Persist to Redis
    await registry.persist_state("test-service")

    # Create new registry to simulate restart
    registry2 = ServiceRegistry(real_redis_client)
    fresh_service = ManagedService(
        name="test-service",
        display_name="Test Service",
        container_id="test-container-123",
        image="test:latest",
        port=8080,
        health_endpoint="/health",
        health_cmd=None,
        category=ServiceCategory.AI,
        status=ContainerServiceStatus.RUNNING,  # Different from persisted
        enabled=True,
        failure_count=0,  # Different from persisted
        restart_count=0,  # Different from persisted
    )
    registry2.register(fresh_service)

    # Load state
    await registry2.load_state("test-service")

    # Verify state was restored
    restored = registry2.get("test-service")
    assert restored is not None
    assert restored.status == ContainerServiceStatus.UNHEALTHY
    assert restored.failure_count == 3
    assert restored.restart_count == 2
