"""Unit tests for Worker Supervisor API endpoints (NEM-2462).

Tests cover:
- GET /api/system/supervisor/status - Full supervisor status
- POST /api/system/supervisor/workers/{name}/restart - Manual restart
- POST /api/system/supervisor/workers/{name}/stop - Stop worker
- POST /api/system/supervisor/workers/{name}/start - Start worker
- GET /api/system/supervisor/restart-history - Paginated restart history
- Integration with GET /api/system/health/ready
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.api.routes.system import register_workers, router
from backend.core.redis import get_redis

pytestmark = pytest.mark.unit


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create mock Redis client."""
    redis = AsyncMock()
    redis.health_check.return_value = {"status": "healthy", "connected": True}
    return redis


@pytest.fixture
def test_app(mock_redis: AsyncMock) -> FastAPI:
    """Create test FastAPI app with system router."""
    app = FastAPI()
    app.include_router(router)

    async def mock_get_redis():
        yield mock_redis

    app.dependency_overrides[get_redis] = mock_get_redis
    return app


@pytest.fixture
async def async_client(test_app: FastAPI) -> AsyncClient:
    """Create async HTTP client for testing."""
    transport = ASGITransport(app=test_app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_worker_supervisor() -> MagicMock:
    """Create mock WorkerSupervisor."""
    supervisor = MagicMock()
    supervisor.is_running = True
    supervisor.worker_count = 3

    # Mock worker info
    mock_worker_info = MagicMock()
    mock_worker_info.name = "file_watcher"
    mock_worker_info.status = MagicMock()
    mock_worker_info.status.value = "running"
    mock_worker_info.restart_count = 0
    mock_worker_info.max_restarts = 5
    mock_worker_info.last_started_at = datetime(2026, 1, 13, 10, 0, 0, tzinfo=UTC)
    mock_worker_info.last_crashed_at = None
    mock_worker_info.error = None
    mock_worker_info.circuit_open = False

    supervisor.get_all_workers.return_value = {"file_watcher": mock_worker_info}
    supervisor.get_worker_info.return_value = mock_worker_info
    supervisor.get_worker_status.return_value = MagicMock(value="running")
    supervisor.reset_worker.return_value = True
    supervisor.reset_circuit_breaker.return_value = True
    supervisor.get_restart_history.return_value = []

    return supervisor


@pytest.fixture
def register_mock_supervisor(mock_worker_supervisor: MagicMock):
    """Register mock supervisor for testing."""
    register_workers(worker_supervisor=mock_worker_supervisor)
    yield mock_worker_supervisor
    register_workers(worker_supervisor=None)


# =============================================================================
# GET /api/system/supervisor/status Tests
# =============================================================================


class TestGetSupervisorStatus:
    """Tests for GET /api/system/supervisor/status endpoint."""

    async def test_supervisor_status_returns_full_status(
        self,
        async_client: AsyncClient,
        register_mock_supervisor: MagicMock,
    ) -> None:
        """Test that supervisor status endpoint returns full status."""
        response = await async_client.get("/api/system/supervisor/status")

        assert response.status_code == 200
        data = response.json()

        assert "running" in data
        assert "worker_count" in data
        assert "workers" in data
        assert "timestamp" in data
        assert data["running"] is True
        assert data["worker_count"] == 3

    async def test_supervisor_status_includes_all_workers(
        self,
        async_client: AsyncClient,
        register_mock_supervisor: MagicMock,
    ) -> None:
        """Test that supervisor status includes all worker details."""
        response = await async_client.get("/api/system/supervisor/status")

        assert response.status_code == 200
        data = response.json()

        workers = data["workers"]
        assert len(workers) == 1
        worker = workers[0]

        assert worker["name"] == "file_watcher"
        assert worker["status"] == "running"
        assert worker["restart_count"] == 0
        assert worker["max_restarts"] == 5
        assert worker["error"] is None

    async def test_supervisor_status_when_not_initialized(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Test supervisor status when supervisor is not initialized."""
        register_workers(worker_supervisor=None)

        response = await async_client.get("/api/system/supervisor/status")

        assert response.status_code == 200
        data = response.json()
        assert data["running"] is False
        assert data["worker_count"] == 0
        assert data["workers"] == []


# =============================================================================
# POST /api/system/supervisor/workers/{name}/restart Tests
# =============================================================================


class TestRestartWorker:
    """Tests for POST /api/system/supervisor/workers/{name}/restart endpoint."""

    async def test_restart_worker_success(
        self,
        async_client: AsyncClient,
        register_mock_supervisor: MagicMock,
    ) -> None:
        """Test successful worker restart."""
        # Make restart_worker_task an async mock
        register_mock_supervisor.restart_worker_task = AsyncMock(return_value=True)

        response = await async_client.post("/api/system/supervisor/workers/file_watcher/restart")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "file_watcher" in data["message"]

    async def test_restart_worker_not_found(
        self,
        async_client: AsyncClient,
        register_mock_supervisor: MagicMock,
    ) -> None:
        """Test restart returns 404 for unknown worker."""
        register_mock_supervisor.get_worker_info.return_value = None
        register_mock_supervisor.restart_worker_task = AsyncMock(return_value=False)

        response = await async_client.post("/api/system/supervisor/workers/unknown_worker/restart")

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    async def test_restart_worker_invalid_name(
        self,
        async_client: AsyncClient,
        register_mock_supervisor: MagicMock,
    ) -> None:
        """Test restart returns 400 for invalid worker name."""
        response = await async_client.post("/api/system/supervisor/workers/invalid!name/restart")

        assert response.status_code == 400
        data = response.json()
        assert "invalid" in data["detail"].lower()

    async def test_restart_worker_supervisor_not_initialized(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Test restart returns 503 when supervisor not initialized."""
        register_workers(worker_supervisor=None)

        response = await async_client.post("/api/system/supervisor/workers/file_watcher/restart")

        assert response.status_code == 503
        data = response.json()
        assert "supervisor" in data["detail"].lower()


# =============================================================================
# POST /api/system/supervisor/workers/{name}/stop Tests
# =============================================================================


class TestStopWorker:
    """Tests for POST /api/system/supervisor/workers/{name}/stop endpoint."""

    async def test_stop_worker_success(
        self,
        async_client: AsyncClient,
        register_mock_supervisor: MagicMock,
    ) -> None:
        """Test successful worker stop."""
        register_mock_supervisor.stop_worker = AsyncMock(return_value=True)

        response = await async_client.post("/api/system/supervisor/workers/file_watcher/stop")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "stopped" in data["message"].lower()

    async def test_stop_worker_not_found(
        self,
        async_client: AsyncClient,
        register_mock_supervisor: MagicMock,
    ) -> None:
        """Test stop returns 404 for unknown worker."""
        register_mock_supervisor.get_worker_info.return_value = None
        register_mock_supervisor.stop_worker = AsyncMock(return_value=False)

        response = await async_client.post("/api/system/supervisor/workers/unknown_worker/stop")

        assert response.status_code == 404

    async def test_stop_worker_supervisor_not_initialized(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Test stop returns 503 when supervisor not initialized."""
        register_workers(worker_supervisor=None)

        response = await async_client.post("/api/system/supervisor/workers/file_watcher/stop")

        assert response.status_code == 503


# =============================================================================
# POST /api/system/supervisor/workers/{name}/start Tests
# =============================================================================


class TestStartWorker:
    """Tests for POST /api/system/supervisor/workers/{name}/start endpoint."""

    async def test_start_worker_success(
        self,
        async_client: AsyncClient,
        register_mock_supervisor: MagicMock,
    ) -> None:
        """Test successful worker start."""
        register_mock_supervisor.start_worker = AsyncMock(return_value=True)

        response = await async_client.post("/api/system/supervisor/workers/file_watcher/start")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "started" in data["message"].lower()

    async def test_start_worker_not_found(
        self,
        async_client: AsyncClient,
        register_mock_supervisor: MagicMock,
    ) -> None:
        """Test start returns 404 for unknown worker."""
        register_mock_supervisor.get_worker_info.return_value = None
        register_mock_supervisor.start_worker = AsyncMock(return_value=False)

        response = await async_client.post("/api/system/supervisor/workers/unknown_worker/start")

        assert response.status_code == 404

    async def test_start_worker_already_running(
        self,
        async_client: AsyncClient,
        register_mock_supervisor: MagicMock,
    ) -> None:
        """Test start returns 200 when worker is already running (idempotent)."""
        mock_info = register_mock_supervisor.get_worker_info.return_value
        mock_info.status = MagicMock()
        mock_info.status.value = "running"
        # start_worker returns True for already running (idempotent behavior)
        register_mock_supervisor.start_worker = AsyncMock(return_value=True)

        response = await async_client.post("/api/system/supervisor/workers/file_watcher/start")

        # Should succeed - starting an already running worker is idempotent
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# =============================================================================
# GET /api/system/supervisor/restart-history Tests
# =============================================================================


class TestGetRestartHistory:
    """Tests for GET /api/system/supervisor/restart-history endpoint."""

    async def test_restart_history_returns_empty(
        self,
        async_client: AsyncClient,
        register_mock_supervisor: MagicMock,
    ) -> None:
        """Test restart history returns empty list when no history."""
        register_mock_supervisor.get_restart_history.return_value = []

        response = await async_client.get("/api/system/supervisor/restart-history")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "pagination" in data
        assert data["items"] == []

    async def test_restart_history_returns_events(
        self,
        async_client: AsyncClient,
        register_mock_supervisor: MagicMock,
    ) -> None:
        """Test restart history returns restart events."""
        history = [
            {
                "worker_name": "file_watcher",
                "timestamp": "2026-01-13T10:30:00Z",
                "attempt": 1,
                "status": "success",
                "error": None,
            },
            {
                "worker_name": "detector",
                "timestamp": "2026-01-13T10:25:00Z",
                "attempt": 2,
                "status": "success",
                "error": "Connection timeout",
            },
        ]
        register_mock_supervisor.get_restart_history.return_value = history

        response = await async_client.get("/api/system/supervisor/restart-history")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["items"][0]["worker_name"] == "file_watcher"
        assert data["items"][1]["error"] == "Connection timeout"

    async def test_restart_history_pagination(
        self,
        async_client: AsyncClient,
        register_mock_supervisor: MagicMock,
    ) -> None:
        """Test restart history supports pagination parameters."""
        response = await async_client.get(
            "/api/system/supervisor/restart-history?limit=10&offset=5"
        )

        assert response.status_code == 200
        data = response.json()
        assert "pagination" in data
        assert data["pagination"]["limit"] == 10
        assert data["pagination"]["offset"] == 5

    async def test_restart_history_filter_by_worker(
        self,
        async_client: AsyncClient,
        register_mock_supervisor: MagicMock,
    ) -> None:
        """Test restart history can filter by worker name."""
        response = await async_client.get(
            "/api/system/supervisor/restart-history?worker_name=file_watcher"
        )

        assert response.status_code == 200
        register_mock_supervisor.get_restart_history.assert_called()

    async def test_restart_history_supervisor_not_initialized(
        self,
        async_client: AsyncClient,
    ) -> None:
        """Test restart history returns empty when supervisor not initialized."""
        register_workers(worker_supervisor=None)

        response = await async_client.get("/api/system/supervisor/restart-history")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []


# =============================================================================
# Worker Name Validation Tests
# =============================================================================


class TestWorkerNameValidation:
    """Tests for worker name validation in supervisor endpoints."""

    async def test_valid_worker_names(
        self,
        async_client: AsyncClient,
        register_mock_supervisor: MagicMock,
    ) -> None:
        """Test that valid worker names are accepted."""
        valid_names = [
            "file_watcher",
            "detector",
            "aggregator",
            "analyzer",
            "my_worker",
            "worker123",
        ]

        register_mock_supervisor.restart_worker_task = AsyncMock(return_value=True)

        for name in valid_names:
            response = await async_client.post(f"/api/system/supervisor/workers/{name}/restart")
            # Should not return 400 for valid names
            assert response.status_code != 400, f"Unexpected 400 for valid name: {name}"

    async def test_invalid_worker_names(
        self,
        async_client: AsyncClient,
        register_mock_supervisor: MagicMock,
    ) -> None:
        """Test that invalid worker names are rejected."""
        # Use URL-safe test cases that won't be mangled by routing
        invalid_names = [
            "1startswithnumber",
            "_startsunderscore",
        ]

        for name in invalid_names:
            response = await async_client.post(f"/api/system/supervisor/workers/{name}/restart")
            assert response.status_code == 400, f"Expected 400 for invalid name: {name}"

    async def test_invalid_worker_names_with_special_chars(
        self,
        async_client: AsyncClient,
        register_mock_supervisor: MagicMock,
    ) -> None:
        """Test that worker names with special characters are rejected."""
        import urllib.parse

        # These names contain characters that need URL encoding
        invalid_names = [
            "invalid!name",
            "worker@test",
        ]

        for name in invalid_names:
            encoded_name = urllib.parse.quote(name, safe="")
            response = await async_client.post(
                f"/api/system/supervisor/workers/{encoded_name}/restart"
            )
            assert response.status_code == 400, f"Expected 400 for invalid name: {name}"


# =============================================================================
# Readiness Integration Tests (Moved to integration tests)
# =============================================================================

# Note: The readiness endpoint test that requires database has been moved
# to integration tests. See backend/tests/integration/test_system_api.py
