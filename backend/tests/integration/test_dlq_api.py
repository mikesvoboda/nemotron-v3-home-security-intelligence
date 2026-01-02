"""Integration tests for Dead-Letter Queue (DLQ) API endpoints.

This module tests the DLQ API endpoints (/api/dlq/*) including:
- GET /api/dlq/stats - DLQ statistics
- GET /api/dlq/jobs/{queue_name} - List jobs in a DLQ
- POST /api/dlq/requeue/{queue_name} - Requeue a single job
- POST /api/dlq/requeue-all/{queue_name} - Requeue all jobs
- DELETE /api/dlq/{queue_name} - Clear a DLQ

Destructive operations (requeue, clear) require API key authentication
when api_key_enabled is True in settings.
"""

import os
from collections.abc import AsyncGenerator
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.core.config import Settings, get_settings
from backend.core.constants import (
    ANALYSIS_QUEUE,
    DETECTION_QUEUE,
    DLQ_ANALYSIS_QUEUE,
    DLQ_DETECTION_QUEUE,
)
from backend.services.retry_handler import JobFailure, reset_retry_handler

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


# =============================================================================
# Helper Functions
# =============================================================================


def create_mock_services() -> dict:
    """Create mock services for the app."""
    mock_system_broadcaster = MagicMock()
    mock_system_broadcaster.start_broadcasting = AsyncMock()
    mock_system_broadcaster.stop_broadcasting = AsyncMock()

    mock_gpu_monitor = MagicMock()
    mock_gpu_monitor.start = AsyncMock()
    mock_gpu_monitor.stop = AsyncMock()

    mock_cleanup_service = MagicMock()
    mock_cleanup_service.start = AsyncMock()
    mock_cleanup_service.stop = AsyncMock()

    mock_file_watcher = MagicMock()
    mock_file_watcher.start = AsyncMock()
    mock_file_watcher.stop = AsyncMock()
    mock_file_watcher.configure_mock(
        running=False,
        camera_root="/mock/foscam",
        _use_polling=False,
        _pending_tasks={},
    )

    mock_file_watcher_class = MagicMock(return_value=mock_file_watcher)

    mock_file_watcher_for_routes = MagicMock()
    mock_file_watcher_for_routes.configure_mock(
        running=False,
        camera_root="/mock/foscam",
        _use_polling=False,
        _pending_tasks={},
    )

    mock_pipeline_manager = MagicMock()
    mock_pipeline_manager.start = AsyncMock()
    mock_pipeline_manager.stop = AsyncMock()

    mock_event_broadcaster = MagicMock()
    mock_event_broadcaster.start = AsyncMock()
    mock_event_broadcaster.stop = AsyncMock()
    mock_event_broadcaster.channel_name = "security_events"

    mock_service_health_monitor = MagicMock()
    mock_service_health_monitor.start = AsyncMock()
    mock_service_health_monitor.stop = AsyncMock()

    return {
        "system_broadcaster": mock_system_broadcaster,
        "gpu_monitor": mock_gpu_monitor,
        "cleanup_service": mock_cleanup_service,
        "file_watcher": mock_file_watcher,
        "file_watcher_class": mock_file_watcher_class,
        "file_watcher_for_routes": mock_file_watcher_for_routes,
        "pipeline_manager": mock_pipeline_manager,
        "event_broadcaster": mock_event_broadcaster,
        "service_health_monitor": mock_service_health_monitor,
    }


def get_patches(
    test_settings: Settings,
    mock_redis: AsyncMock,
    mock_services: dict,
) -> list:
    """Get all patches needed for the test fixtures."""
    return [
        patch("backend.main.init_db", AsyncMock(return_value=None)),
        patch("backend.main.close_db", AsyncMock(return_value=None)),
        patch("backend.main.init_redis", AsyncMock(return_value=mock_redis)),
        patch("backend.main.close_redis", AsyncMock(return_value=None)),
        patch(
            "backend.main.get_system_broadcaster",
            return_value=mock_services["system_broadcaster"],
        ),
        patch("backend.main.GPUMonitor", return_value=mock_services["gpu_monitor"]),
        patch("backend.main.CleanupService", return_value=mock_services["cleanup_service"]),
        patch("backend.main.FileWatcher", mock_services["file_watcher_class"]),
        patch(
            "backend.main.get_pipeline_manager",
            AsyncMock(return_value=mock_services["pipeline_manager"]),
        ),
        patch("backend.main.stop_pipeline_manager", AsyncMock()),
        patch(
            "backend.main.get_broadcaster",
            AsyncMock(return_value=mock_services["event_broadcaster"]),
        ),
        patch("backend.main.stop_broadcaster", AsyncMock()),
        patch(
            "backend.main.ServiceHealthMonitor",
            return_value=mock_services["service_health_monitor"],
        ),
        patch(
            "backend.api.routes.system._file_watcher",
            mock_services["file_watcher_for_routes"],
        ),
        patch("backend.core.config.get_settings", return_value=test_settings),
        patch("backend.api.routes.dlq.get_settings", return_value=test_settings),
        patch("backend.core.redis._redis_client", mock_redis),
        patch("backend.core.redis.init_redis", return_value=mock_redis),
        patch("backend.core.redis.close_redis", return_value=None),
        patch("backend.core.redis.get_redis", return_value=mock_redis),
    ]


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_redis_for_dlq() -> AsyncMock:
    """Create a mock Redis client configured for DLQ operations."""
    mock_redis_client = AsyncMock()
    mock_redis_client.health_check.return_value = {
        "status": "healthy",
        "connected": True,
        "redis_version": "7.0.0",
    }
    # Default to empty queues
    mock_redis_client.get_queue_length.return_value = 0
    mock_redis_client.peek_queue.return_value = []
    mock_redis_client.clear_queue.return_value = True
    return mock_redis_client


@pytest.fixture
async def dlq_client(
    integration_db: str, mock_redis_for_dlq: AsyncMock
) -> AsyncGenerator[AsyncClient]:
    """Async HTTP client for DLQ API tests without API key authentication.

    This fixture creates an HTTP client with api_key_enabled=False.
    """
    from backend.main import app

    # Create settings with API key disabled
    test_settings = Settings(
        api_key_enabled=False,
        database_url=os.environ.get("DATABASE_URL", ""),
        redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/15"),
    )

    # Reset the global retry handler before each test
    reset_retry_handler()

    # Create mock services
    mock_services = create_mock_services()

    # Get all patches
    patches = get_patches(test_settings, mock_redis_for_dlq, mock_services)

    # Use ExitStack to manage the patches
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)

        get_settings.cache_clear()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
        get_settings.cache_clear()
        reset_retry_handler()


@pytest.fixture
async def api_key_client(
    integration_db: str, mock_redis_for_dlq: AsyncMock
) -> AsyncGenerator[AsyncClient]:
    """Async HTTP client for DLQ API tests with API key authentication enabled.

    This fixture creates an HTTP client with api_key_enabled=True and
    a test API key configured.
    """
    from backend.main import app

    # Create settings with API key enabled
    test_settings = Settings(
        api_key_enabled=True,
        api_keys=["test-secret-key-12345"],
        database_url=os.environ.get("DATABASE_URL", ""),
        redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/15"),
    )

    # Reset the global retry handler before each test
    reset_retry_handler()

    # Create mock services
    mock_services = create_mock_services()

    # Get all patches
    patches = get_patches(test_settings, mock_redis_for_dlq, mock_services)

    # Use ExitStack to manage the patches
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)

        get_settings.cache_clear()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
        get_settings.cache_clear()
        reset_retry_handler()


def create_sample_job_failure(
    camera_id: str = "front_door",
    file_path: str = "/export/foscam/front_door/image_001.jpg",
    error: str = "Connection refused: detector service unavailable",
    attempt_count: int = 3,
    queue_name: str = DETECTION_QUEUE,
) -> JobFailure:
    """Create a sample JobFailure for testing."""
    return JobFailure(
        original_job={
            "camera_id": camera_id,
            "file_path": file_path,
            "timestamp": "2025-12-23T10:30:00.000000",
        },
        error=error,
        attempt_count=attempt_count,
        first_failed_at="2025-12-23T10:30:05.000000",
        last_failed_at="2025-12-23T10:30:15.000000",
        queue_name=queue_name,
    )


# =============================================================================
# GET /api/dlq/stats Tests
# =============================================================================


class TestGetDLQStats:
    """Tests for GET /api/dlq/stats endpoint."""

    @pytest.mark.asyncio
    async def test_stats_empty_dlq(
        self, dlq_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test stats endpoint returns zeros when DLQs are empty."""
        # Configure mock to return empty queues
        mock_redis_for_dlq.get_queue_length.return_value = 0

        response = await dlq_client.get("/api/dlq/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["detection_queue_count"] == 0
        assert data["analysis_queue_count"] == 0
        assert data["total_count"] == 0

    @pytest.mark.asyncio
    async def test_stats_populated_dlq(
        self, dlq_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test stats endpoint returns correct counts when DLQs have jobs."""

        # Configure mock to return counts based on queue name
        async def get_queue_length_side_effect(queue_name: str) -> int:
            if queue_name == DLQ_DETECTION_QUEUE:
                return 5
            elif queue_name == DLQ_ANALYSIS_QUEUE:
                return 3
            return 0

        mock_redis_for_dlq.get_queue_length.side_effect = get_queue_length_side_effect

        response = await dlq_client.get("/api/dlq/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["detection_queue_count"] == 5
        assert data["analysis_queue_count"] == 3
        assert data["total_count"] == 8

    @pytest.mark.asyncio
    async def test_stats_only_detection_queue_populated(
        self, dlq_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test stats when only detection DLQ has jobs."""

        async def get_queue_length_side_effect(queue_name: str) -> int:
            if queue_name == DLQ_DETECTION_QUEUE:
                return 10
            return 0

        mock_redis_for_dlq.get_queue_length.side_effect = get_queue_length_side_effect

        response = await dlq_client.get("/api/dlq/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["detection_queue_count"] == 10
        assert data["analysis_queue_count"] == 0
        assert data["total_count"] == 10


# =============================================================================
# GET /api/dlq/jobs/{queue_name} Tests
# =============================================================================


class TestGetDLQJobs:
    """Tests for GET /api/dlq/jobs/{queue_name} endpoint."""

    @pytest.mark.asyncio
    async def test_jobs_invalid_queue_name(self, dlq_client: AsyncClient) -> None:
        """Test that invalid queue name returns 422."""
        response = await dlq_client.get("/api/dlq/jobs/invalid_queue")

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_jobs_empty_detection_queue(
        self, dlq_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test listing jobs from empty detection DLQ."""
        mock_redis_for_dlq.peek_queue.return_value = []

        response = await dlq_client.get(f"/api/dlq/jobs/{DLQ_DETECTION_QUEUE}")

        assert response.status_code == 200
        data = response.json()
        assert data["queue_name"] == DLQ_DETECTION_QUEUE
        assert data["jobs"] == []
        assert data["count"] == 0

    @pytest.mark.asyncio
    async def test_jobs_empty_analysis_queue(
        self, dlq_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test listing jobs from empty analysis DLQ."""
        mock_redis_for_dlq.peek_queue.return_value = []

        response = await dlq_client.get(f"/api/dlq/jobs/{DLQ_ANALYSIS_QUEUE}")

        assert response.status_code == 200
        data = response.json()
        assert data["queue_name"] == DLQ_ANALYSIS_QUEUE
        assert data["jobs"] == []
        assert data["count"] == 0

    @pytest.mark.asyncio
    async def test_jobs_with_data(
        self, dlq_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test listing jobs from DLQ with data."""
        sample_job = create_sample_job_failure()
        mock_redis_for_dlq.peek_queue.return_value = [sample_job.to_dict()]

        response = await dlq_client.get(f"/api/dlq/jobs/{DLQ_DETECTION_QUEUE}")

        assert response.status_code == 200
        data = response.json()
        assert data["queue_name"] == DLQ_DETECTION_QUEUE
        assert data["count"] == 1
        assert len(data["jobs"]) == 1

        job = data["jobs"][0]
        assert job["original_job"]["camera_id"] == "front_door"
        assert job["error"] == "Connection refused: detector service unavailable"
        assert job["attempt_count"] == 3
        assert job["queue_name"] == DETECTION_QUEUE

    @pytest.mark.asyncio
    async def test_jobs_pagination_default(
        self, dlq_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test default pagination (start=0, limit=100)."""
        # Create multiple jobs
        jobs = [create_sample_job_failure(camera_id=f"cam_{i}").to_dict() for i in range(5)]
        mock_redis_for_dlq.peek_queue.return_value = jobs

        response = await dlq_client.get(f"/api/dlq/jobs/{DLQ_DETECTION_QUEUE}")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 5

    @pytest.mark.asyncio
    async def test_jobs_pagination_custom(
        self, dlq_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test custom pagination parameters."""
        jobs = [create_sample_job_failure(camera_id=f"cam_{i}").to_dict() for i in range(3)]
        mock_redis_for_dlq.peek_queue.return_value = jobs

        response = await dlq_client.get(f"/api/dlq/jobs/{DLQ_DETECTION_QUEUE}?start=2&limit=10")

        assert response.status_code == 200
        # Verify peek_queue was called with correct indices
        mock_redis_for_dlq.peek_queue.assert_called()

    @pytest.mark.asyncio
    async def test_jobs_pagination_invalid_start(self, dlq_client: AsyncClient) -> None:
        """Test that negative start parameter returns 422."""
        response = await dlq_client.get(f"/api/dlq/jobs/{DLQ_DETECTION_QUEUE}?start=-1")

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_jobs_pagination_invalid_limit(self, dlq_client: AsyncClient) -> None:
        """Test that invalid limit parameter returns 422."""
        # Limit must be >= 1
        response = await dlq_client.get(f"/api/dlq/jobs/{DLQ_DETECTION_QUEUE}?limit=0")
        assert response.status_code == 422

        # Limit must be <= 1000
        response = await dlq_client.get(f"/api/dlq/jobs/{DLQ_DETECTION_QUEUE}?limit=1001")
        assert response.status_code == 422


# =============================================================================
# POST /api/dlq/requeue/{queue_name} Tests
# =============================================================================


class TestRequeueDLQJob:
    """Tests for POST /api/dlq/requeue/{queue_name} endpoint."""

    @pytest.mark.asyncio
    async def test_requeue_missing_api_key_when_enabled(self, api_key_client: AsyncClient) -> None:
        """Test that requeue endpoint returns 401 when API key is missing."""
        response = await api_key_client.post(f"/api/dlq/requeue/{DLQ_DETECTION_QUEUE}")

        assert response.status_code == 401
        data = response.json()
        assert "API key required" in data["detail"]

    @pytest.mark.asyncio
    async def test_requeue_invalid_api_key(self, api_key_client: AsyncClient) -> None:
        """Test that requeue endpoint returns 401 with invalid API key."""
        response = await api_key_client.post(
            f"/api/dlq/requeue/{DLQ_DETECTION_QUEUE}",
            headers={"X-API-Key": "wrong-key"},
        )

        assert response.status_code == 401
        data = response.json()
        assert "Invalid API key" in data["detail"]

    @pytest.mark.asyncio
    async def test_requeue_valid_api_key_empty_dlq(
        self, api_key_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test requeue with valid API key on empty DLQ."""
        # Configure mock to return empty queue and no job to requeue
        mock_redis_for_dlq.get_queue_length.return_value = 0
        mock_redis_for_dlq.get_from_queue.return_value = None

        response = await api_key_client.post(
            f"/api/dlq/requeue/{DLQ_DETECTION_QUEUE}",
            headers={"X-API-Key": "test-secret-key-12345"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "No jobs to requeue" in data["message"]

    @pytest.mark.asyncio
    async def test_requeue_via_query_param(
        self, api_key_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test requeue with API key provided via query parameter."""
        mock_redis_for_dlq.get_queue_length.return_value = 0
        mock_redis_for_dlq.get_from_queue.return_value = None

        response = await api_key_client.post(
            f"/api/dlq/requeue/{DLQ_DETECTION_QUEUE}?api_key=test-secret-key-12345"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False  # Empty DLQ

    @pytest.mark.asyncio
    async def test_requeue_no_auth_when_disabled(
        self, dlq_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test requeue works without API key when auth is disabled."""
        mock_redis_for_dlq.get_queue_length.return_value = 0
        mock_redis_for_dlq.get_from_queue.return_value = None

        response = await dlq_client.post(f"/api/dlq/requeue/{DLQ_DETECTION_QUEUE}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False  # Empty DLQ

    @pytest.mark.asyncio
    async def test_requeue_invalid_queue_name(self, dlq_client: AsyncClient) -> None:
        """Test that invalid queue name returns 422."""
        response = await dlq_client.post("/api/dlq/requeue/invalid_queue")

        assert response.status_code == 422


# =============================================================================
# POST /api/dlq/requeue-all/{queue_name} Tests
# =============================================================================


class TestRequeueAllDLQJobs:
    """Tests for POST /api/dlq/requeue-all/{queue_name} endpoint."""

    @pytest.mark.asyncio
    async def test_requeue_all_missing_api_key(self, api_key_client: AsyncClient) -> None:
        """Test that requeue-all endpoint returns 401 when API key is missing."""
        response = await api_key_client.post(f"/api/dlq/requeue-all/{DLQ_DETECTION_QUEUE}")

        assert response.status_code == 401
        data = response.json()
        assert "API key required" in data["detail"]

    @pytest.mark.asyncio
    async def test_requeue_all_invalid_api_key(self, api_key_client: AsyncClient) -> None:
        """Test that requeue-all endpoint returns 401 with invalid API key."""
        response = await api_key_client.post(
            f"/api/dlq/requeue-all/{DLQ_DETECTION_QUEUE}",
            headers={"X-API-Key": "wrong-key"},
        )

        assert response.status_code == 401
        data = response.json()
        assert "Invalid API key" in data["detail"]

    @pytest.mark.asyncio
    async def test_requeue_all_empty_dlq(
        self, api_key_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test requeue-all with valid API key on empty DLQ."""
        mock_redis_for_dlq.get_queue_length.return_value = 0

        response = await api_key_client.post(
            f"/api/dlq/requeue-all/{DLQ_DETECTION_QUEUE}",
            headers={"X-API-Key": "test-secret-key-12345"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "No jobs to requeue" in data["message"]

    @pytest.mark.asyncio
    async def test_requeue_all_no_auth_when_disabled(
        self, dlq_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test requeue-all works without API key when auth is disabled."""
        mock_redis_for_dlq.get_queue_length.return_value = 0

        response = await dlq_client.post(f"/api/dlq/requeue-all/{DLQ_DETECTION_QUEUE}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False  # Empty DLQ

    @pytest.mark.asyncio
    async def test_requeue_all_invalid_queue_name(self, dlq_client: AsyncClient) -> None:
        """Test that invalid queue name returns 422."""
        response = await dlq_client.post("/api/dlq/requeue-all/invalid_queue")

        assert response.status_code == 422


# =============================================================================
# DELETE /api/dlq/{queue_name} Tests
# =============================================================================


class TestClearDLQ:
    """Tests for DELETE /api/dlq/{queue_name} endpoint."""

    @pytest.mark.asyncio
    async def test_clear_missing_api_key(self, api_key_client: AsyncClient) -> None:
        """Test that clear endpoint returns 401 when API key is missing."""
        response = await api_key_client.delete(f"/api/dlq/{DLQ_DETECTION_QUEUE}")

        assert response.status_code == 401
        data = response.json()
        assert "API key required" in data["detail"]

    @pytest.mark.asyncio
    async def test_clear_invalid_api_key(self, api_key_client: AsyncClient) -> None:
        """Test that clear endpoint returns 401 with invalid API key."""
        response = await api_key_client.delete(
            f"/api/dlq/{DLQ_DETECTION_QUEUE}",
            headers={"X-API-Key": "wrong-key"},
        )

        assert response.status_code == 401
        data = response.json()
        assert "Invalid API key" in data["detail"]

    @pytest.mark.asyncio
    async def test_clear_empty_dlq(
        self, api_key_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test clear on empty DLQ with valid API key."""
        mock_redis_for_dlq.get_queue_length.return_value = 0
        mock_redis_for_dlq.clear_queue.return_value = True

        response = await api_key_client.delete(
            f"/api/dlq/{DLQ_DETECTION_QUEUE}",
            headers={"X-API-Key": "test-secret-key-12345"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["queue_name"] == DLQ_DETECTION_QUEUE
        assert "Cleared 0 jobs" in data["message"]

    @pytest.mark.asyncio
    async def test_clear_populated_dlq(
        self, api_key_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test clear on populated DLQ with valid API key."""
        mock_redis_for_dlq.get_queue_length.return_value = 5
        mock_redis_for_dlq.clear_queue.return_value = True

        response = await api_key_client.delete(
            f"/api/dlq/{DLQ_DETECTION_QUEUE}",
            headers={"X-API-Key": "test-secret-key-12345"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Cleared 5 jobs" in data["message"]

    @pytest.mark.asyncio
    async def test_clear_no_auth_when_disabled(
        self, dlq_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test clear works without API key when auth is disabled."""
        mock_redis_for_dlq.get_queue_length.return_value = 0
        mock_redis_for_dlq.clear_queue.return_value = True

        response = await dlq_client.delete(f"/api/dlq/{DLQ_DETECTION_QUEUE}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_clear_invalid_queue_name(self, dlq_client: AsyncClient) -> None:
        """Test that invalid queue name returns 422."""
        response = await dlq_client.delete("/api/dlq/invalid_queue")

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_clear_via_query_param(
        self, api_key_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test clear with API key provided via query parameter."""
        mock_redis_for_dlq.get_queue_length.return_value = 0
        mock_redis_for_dlq.clear_queue.return_value = True

        response = await api_key_client.delete(
            f"/api/dlq/{DLQ_DETECTION_QUEUE}?api_key=test-secret-key-12345"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# =============================================================================
# Authentication Edge Cases
# =============================================================================


class TestDLQAuthentication:
    """Tests for DLQ API authentication edge cases."""

    @pytest.mark.asyncio
    async def test_empty_api_key_rejected(self, api_key_client: AsyncClient) -> None:
        """Test that empty API key string is rejected."""
        response = await api_key_client.post(
            f"/api/dlq/requeue/{DLQ_DETECTION_QUEUE}",
            headers={"X-API-Key": ""},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_read_endpoints_no_auth_required(
        self, api_key_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test that GET endpoints don't require authentication even when enabled."""
        mock_redis_for_dlq.get_queue_length.return_value = 0
        mock_redis_for_dlq.peek_queue.return_value = []

        # Stats endpoint should work without API key
        stats_response = await api_key_client.get("/api/dlq/stats")
        assert stats_response.status_code == 200

        # Jobs endpoint should work without API key
        jobs_response = await api_key_client.get(f"/api/dlq/jobs/{DLQ_DETECTION_QUEUE}")
        assert jobs_response.status_code == 200

    @pytest.mark.asyncio
    async def test_destructive_endpoints_require_auth(self, api_key_client: AsyncClient) -> None:
        """Test that all destructive endpoints require authentication when enabled."""
        # Requeue single
        response = await api_key_client.post(f"/api/dlq/requeue/{DLQ_DETECTION_QUEUE}")
        assert response.status_code == 401

        # Requeue all
        response = await api_key_client.post(f"/api/dlq/requeue-all/{DLQ_DETECTION_QUEUE}")
        assert response.status_code == 401

        # Clear
        response = await api_key_client.delete(f"/api/dlq/{DLQ_DETECTION_QUEUE}")
        assert response.status_code == 401


# =============================================================================
# Response Schema Validation Tests
# =============================================================================


class TestDLQResponseSchemas:
    """Tests validating response schemas match expected structure."""

    @pytest.mark.asyncio
    async def test_stats_response_schema(
        self, dlq_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test that stats response matches DLQStatsResponse schema."""
        mock_redis_for_dlq.get_queue_length.return_value = 0

        response = await dlq_client.get("/api/dlq/stats")

        assert response.status_code == 200
        data = response.json()

        # Verify required fields
        assert "detection_queue_count" in data
        assert "analysis_queue_count" in data
        assert "total_count" in data

        # Verify types
        assert isinstance(data["detection_queue_count"], int)
        assert isinstance(data["analysis_queue_count"], int)
        assert isinstance(data["total_count"], int)

    @pytest.mark.asyncio
    async def test_jobs_response_schema(
        self, dlq_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test that jobs response matches DLQJobsResponse schema."""
        sample_job = create_sample_job_failure()
        mock_redis_for_dlq.peek_queue.return_value = [sample_job.to_dict()]

        response = await dlq_client.get(f"/api/dlq/jobs/{DLQ_DETECTION_QUEUE}")

        assert response.status_code == 200
        data = response.json()

        # Verify required fields
        assert "queue_name" in data
        assert "jobs" in data
        assert "count" in data

        # Verify job structure
        job = data["jobs"][0]
        assert "original_job" in job
        assert "error" in job
        assert "attempt_count" in job
        assert "first_failed_at" in job
        assert "last_failed_at" in job
        assert "queue_name" in job

    @pytest.mark.asyncio
    async def test_requeue_response_schema(
        self, dlq_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test that requeue response matches DLQRequeueResponse schema."""
        mock_redis_for_dlq.get_queue_length.return_value = 0
        mock_redis_for_dlq.get_from_queue.return_value = None

        response = await dlq_client.post(f"/api/dlq/requeue/{DLQ_DETECTION_QUEUE}")

        assert response.status_code == 200
        data = response.json()

        # Verify required fields
        assert "success" in data
        assert "message" in data
        assert "job" in data

        # Verify types
        assert isinstance(data["success"], bool)
        assert isinstance(data["message"], str)

    @pytest.mark.asyncio
    async def test_clear_response_schema(
        self, dlq_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test that clear response matches DLQClearResponse schema."""
        mock_redis_for_dlq.get_queue_length.return_value = 0
        mock_redis_for_dlq.clear_queue.return_value = True

        response = await dlq_client.delete(f"/api/dlq/{DLQ_DETECTION_QUEUE}")

        assert response.status_code == 200
        data = response.json()

        # Verify required fields
        assert "success" in data
        assert "message" in data
        assert "queue_name" in data

        # Verify types
        assert isinstance(data["success"], bool)
        assert isinstance(data["message"], str)
        assert isinstance(data["queue_name"], str)


# =============================================================================
# Full Cycle Tests (Verify Operations Actually Modify State)
# =============================================================================


class TestDLQFullCycleOperations:
    """Tests that verify DLQ operations actually modify queue state correctly.

    These tests verify:
    1. Requeue operations remove jobs from DLQ and add to target queue
    2. Clear operations result in zero stats
    3. Stats are correctly updated after each operation
    """

    @pytest.mark.asyncio
    async def test_requeue_single_job_decrements_dlq_count(
        self, dlq_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test that requeuing a single job decrements the DLQ count.

        Scenario: DLQ has 3 jobs, requeue one, verify count is now 2.
        """
        # Track call sequence to simulate state changes
        call_count = {"get_queue_length": 0, "get_from_queue": 0}
        sample_job = create_sample_job_failure()

        async def get_queue_length_dynamic(queue_name: str) -> int:
            # First call returns 3, subsequent calls return 2 (after requeue)
            if queue_name == DLQ_DETECTION_QUEUE:
                call_count["get_queue_length"] += 1
                return 3 if call_count["get_queue_length"] == 1 else 2
            return 0

        async def get_from_queue_dynamic(queue_name: str, timeout: int = 0) -> dict | None:
            call_count["get_from_queue"] += 1
            return sample_job.to_dict()

        mock_redis_for_dlq.get_queue_length.side_effect = get_queue_length_dynamic
        mock_redis_for_dlq.get_from_queue.side_effect = get_from_queue_dynamic
        mock_redis_for_dlq.add_to_queue_safe.return_value = MagicMock(
            success=True, had_backpressure=False, queue_length=1, moved_to_dlq_count=0, error=None
        )

        # Perform requeue operation
        requeue_response = await dlq_client.post(f"/api/dlq/requeue/{DLQ_DETECTION_QUEUE}")
        assert requeue_response.status_code == 200

        data = requeue_response.json()
        assert data["success"] is True
        assert "Job requeued" in data["message"]

    @pytest.mark.asyncio
    async def test_requeue_all_empties_dlq(
        self, dlq_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test that requeue-all removes all jobs from DLQ.

        Scenario: DLQ has 3 jobs, requeue all, verify DLQ is empty.
        """
        # Simulate 3 jobs being requeued one by one
        remaining_jobs = [3, 2, 1, 0]  # Count decrements each call
        job_index = {"value": 0}
        sample_job = create_sample_job_failure()

        async def get_queue_length_dynamic(queue_name: str) -> int:
            if queue_name == DLQ_DETECTION_QUEUE:
                return remaining_jobs[min(job_index["value"], len(remaining_jobs) - 1)]
            return 0

        async def get_from_queue_dynamic(queue_name: str, timeout: int = 0) -> dict | None:
            if job_index["value"] < 3:
                job_index["value"] += 1
                return sample_job.to_dict()
            return None  # No more jobs

        mock_redis_for_dlq.get_queue_length.side_effect = get_queue_length_dynamic
        mock_redis_for_dlq.get_from_queue.side_effect = get_from_queue_dynamic
        mock_redis_for_dlq.add_to_queue_safe.return_value = MagicMock(
            success=True, had_backpressure=False, queue_length=1, moved_to_dlq_count=0, error=None
        )

        # Perform requeue-all operation
        requeue_response = await dlq_client.post(f"/api/dlq/requeue-all/{DLQ_DETECTION_QUEUE}")
        assert requeue_response.status_code == 200

        data = requeue_response.json()
        assert data["success"] is True
        assert "Requeued 3 jobs" in data["message"]

    @pytest.mark.asyncio
    async def test_clear_dlq_results_in_zero_stats(
        self, dlq_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test that clearing DLQ results in zero stats.

        Scenario: DLQ has 5 jobs, clear it, verify stats show 0.
        """
        # First call returns 5, subsequent calls return 0 (after clear)
        call_count = {"value": 0}

        async def get_queue_length_dynamic(queue_name: str) -> int:
            if queue_name == DLQ_DETECTION_QUEUE:
                call_count["value"] += 1
                return 5 if call_count["value"] == 1 else 0
            return 0

        mock_redis_for_dlq.get_queue_length.side_effect = get_queue_length_dynamic
        mock_redis_for_dlq.clear_queue.return_value = True

        # Clear the DLQ
        clear_response = await dlq_client.delete(f"/api/dlq/{DLQ_DETECTION_QUEUE}")
        assert clear_response.status_code == 200

        clear_data = clear_response.json()
        assert clear_data["success"] is True
        assert "Cleared 5 jobs" in clear_data["message"]

        # Now verify stats endpoint returns 0
        stats_response = await dlq_client.get("/api/dlq/stats")
        assert stats_response.status_code == 200

        stats_data = stats_response.json()
        # Detection queue should now be empty
        assert stats_data["detection_queue_count"] == 0

    @pytest.mark.asyncio
    async def test_requeue_all_hits_max_iterations_limit(
        self, dlq_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test that requeue-all respects max iterations limit.

        When there are more jobs than max_requeue_iterations, only that many are requeued.
        """
        sample_job = create_sample_job_failure()

        # Simulate infinite jobs (always return a job)
        mock_redis_for_dlq.get_queue_length.return_value = 10000  # More than limit
        mock_redis_for_dlq.get_from_queue.return_value = sample_job.to_dict()
        mock_redis_for_dlq.add_to_queue_safe.return_value = MagicMock(
            success=True, had_backpressure=False, queue_length=1, moved_to_dlq_count=0, error=None
        )

        requeue_response = await dlq_client.post(f"/api/dlq/requeue-all/{DLQ_DETECTION_QUEUE}")
        assert requeue_response.status_code == 200

        data = requeue_response.json()
        assert data["success"] is True
        # Should hit the limit and report it
        assert "hit limit" in data["message"]


# =============================================================================
# Error Handling Edge Cases
# =============================================================================


class TestDLQErrorHandling:
    """Tests for error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_requeue_when_target_queue_full(
        self, dlq_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test requeue behavior when target queue is at capacity."""
        sample_job = create_sample_job_failure()

        mock_redis_for_dlq.get_queue_length.return_value = 1
        mock_redis_for_dlq.get_from_queue.return_value = sample_job.to_dict()
        # Simulate target queue being full - add_to_queue_safe returns failure
        mock_redis_for_dlq.add_to_queue_safe.return_value = MagicMock(
            success=False,
            had_backpressure=True,
            queue_length=1000,
            moved_to_dlq_count=0,
            error="Queue at capacity",
        )

        requeue_response = await dlq_client.post(f"/api/dlq/requeue/{DLQ_DETECTION_QUEUE}")
        assert requeue_response.status_code == 200

        data = requeue_response.json()
        # Operation should fail gracefully
        assert data["success"] is False

    @pytest.mark.asyncio
    async def test_clear_dlq_failure(
        self, dlq_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test clear endpoint when Redis clear operation fails.

        The retry handler's clear_dlq method only returns False when an exception
        is raised, so we need to simulate an exception to test the failure path.
        """
        mock_redis_for_dlq.get_queue_length.return_value = 5
        # Simulate failure by raising an exception
        mock_redis_for_dlq.clear_queue.side_effect = Exception("Redis connection lost")

        clear_response = await dlq_client.delete(f"/api/dlq/{DLQ_DETECTION_QUEUE}")
        assert clear_response.status_code == 200

        data = clear_response.json()
        assert data["success"] is False
        assert "Failed to clear" in data["message"]

    @pytest.mark.asyncio
    async def test_jobs_with_multiple_pages(
        self, dlq_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test listing jobs with pagination across multiple pages."""
        # Create 10 sample jobs
        jobs = [
            create_sample_job_failure(
                camera_id=f"cam_{i}", file_path=f"/path/image_{i}.jpg"
            ).to_dict()
            for i in range(10)
        ]

        # First page: jobs 0-4
        async def peek_queue_paginated(
            queue_name: str, start: int = 0, end: int = -1
        ) -> list[dict]:
            return jobs[start : end + 1] if end != -1 else jobs[start:]

        mock_redis_for_dlq.peek_queue.side_effect = peek_queue_paginated

        # Get first page (5 items)
        response1 = await dlq_client.get(f"/api/dlq/jobs/{DLQ_DETECTION_QUEUE}?start=0&limit=5")
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["count"] == 5

        # Get second page (remaining 5 items)
        response2 = await dlq_client.get(f"/api/dlq/jobs/{DLQ_DETECTION_QUEUE}?start=5&limit=5")
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["count"] == 5

    @pytest.mark.asyncio
    async def test_stats_with_only_analysis_queue_populated(
        self, dlq_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test stats when only analysis DLQ has jobs."""

        async def get_queue_length_side_effect(queue_name: str) -> int:
            if queue_name == DLQ_ANALYSIS_QUEUE:
                return 7
            return 0

        mock_redis_for_dlq.get_queue_length.side_effect = get_queue_length_side_effect

        response = await dlq_client.get("/api/dlq/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["detection_queue_count"] == 0
        assert data["analysis_queue_count"] == 7
        assert data["total_count"] == 7

    @pytest.mark.asyncio
    async def test_jobs_with_various_error_types(
        self, dlq_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test listing jobs with various error types."""
        jobs = [
            create_sample_job_failure(
                camera_id="cam_1",
                error="Connection refused: detector service unavailable",
            ).to_dict(),
            create_sample_job_failure(
                camera_id="cam_2",
                error="Timeout: request took longer than 30s",
            ).to_dict(),
            create_sample_job_failure(
                camera_id="cam_3",
                error="Model loading failed: insufficient GPU memory",
            ).to_dict(),
        ]
        mock_redis_for_dlq.peek_queue.return_value = jobs

        response = await dlq_client.get(f"/api/dlq/jobs/{DLQ_DETECTION_QUEUE}")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3

        # Verify each job has the correct error type
        errors = [job["error"] for job in data["jobs"]]
        assert "Connection refused" in errors[0]
        assert "Timeout" in errors[1]
        assert "GPU memory" in errors[2]


# =============================================================================
# Analysis Queue Specific Tests
# =============================================================================


class TestAnalysisQueueOperations:
    """Tests specifically for analysis DLQ operations."""

    @pytest.mark.asyncio
    async def test_list_analysis_queue_jobs(
        self, dlq_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test listing jobs from the analysis DLQ."""
        sample_job = JobFailure(
            original_job={
                "batch_id": "batch_123",
                "camera_id": "front_door",
                "detections": [{"object_type": "person", "confidence": 0.95}],
            },
            error="LLM inference failed: model not loaded",
            attempt_count=3,
            first_failed_at="2025-12-23T10:30:05.000000",
            last_failed_at="2025-12-23T10:30:15.000000",
            queue_name=ANALYSIS_QUEUE,
        )
        mock_redis_for_dlq.peek_queue.return_value = [sample_job.to_dict()]

        response = await dlq_client.get(f"/api/dlq/jobs/{DLQ_ANALYSIS_QUEUE}")

        assert response.status_code == 200
        data = response.json()
        assert data["queue_name"] == DLQ_ANALYSIS_QUEUE
        assert data["count"] == 1

        job = data["jobs"][0]
        assert "batch_id" in job["original_job"]
        assert "detections" in job["original_job"]
        assert "LLM inference failed" in job["error"]

    @pytest.mark.asyncio
    async def test_requeue_analysis_job(
        self, dlq_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test requeuing a job from the analysis DLQ."""
        sample_job = JobFailure(
            original_job={"batch_id": "batch_123"},
            error="LLM timeout",
            attempt_count=3,
            first_failed_at="2025-12-23T10:30:05.000000",
            last_failed_at="2025-12-23T10:30:15.000000",
            queue_name=ANALYSIS_QUEUE,
        )

        mock_redis_for_dlq.get_queue_length.return_value = 1
        mock_redis_for_dlq.get_from_queue.return_value = sample_job.to_dict()
        mock_redis_for_dlq.add_to_queue_safe.return_value = MagicMock(
            success=True, had_backpressure=False, queue_length=1, moved_to_dlq_count=0, error=None
        )

        response = await dlq_client.post(f"/api/dlq/requeue/{DLQ_ANALYSIS_QUEUE}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert ANALYSIS_QUEUE in data["message"]

    @pytest.mark.asyncio
    async def test_clear_analysis_queue(
        self, dlq_client: AsyncClient, mock_redis_for_dlq: AsyncMock
    ) -> None:
        """Test clearing the analysis DLQ."""
        mock_redis_for_dlq.get_queue_length.return_value = 3
        mock_redis_for_dlq.clear_queue.return_value = True

        response = await dlq_client.delete(f"/api/dlq/{DLQ_ANALYSIS_QUEUE}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["queue_name"] == DLQ_ANALYSIS_QUEUE
        assert "Cleared 3 jobs" in data["message"]
