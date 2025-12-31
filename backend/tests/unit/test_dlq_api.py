"""Unit tests for dead-letter queue (DLQ) API endpoints.

Tests cover:
- GET /api/dlq/stats - DLQ statistics
- GET /api/dlq/jobs/{queue_name} - List DLQ jobs
- POST /api/dlq/requeue/{queue_name} - Requeue single job
- POST /api/dlq/requeue-all/{queue_name} - Requeue all jobs
- DELETE /api/dlq/{queue_name} - Clear DLQ
"""

import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

# Set DATABASE_URL for tests before importing any backend modules
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")

from backend.api.routes.dlq import DLQName
from backend.core.redis import QueueAddResult
from backend.services.retry_handler import reset_retry_handler


@pytest.fixture
def mock_redis() -> MagicMock:
    """Create a mock Redis client with spec to prevent mocking non-existent attributes."""
    from backend.core.redis import RedisClient

    redis = MagicMock(spec=RedisClient)
    redis.add_to_queue = AsyncMock(return_value=1)
    redis.add_to_queue_safe = AsyncMock(return_value=QueueAddResult(success=True, queue_length=1))
    redis.get_from_queue = AsyncMock(return_value=None)
    redis.get_queue_length = AsyncMock(return_value=0)
    redis.peek_queue = AsyncMock(return_value=[])
    redis.clear_queue = AsyncMock(return_value=True)
    return redis


@pytest.fixture
def client(mock_redis: MagicMock) -> TestClient:
    """Create a test client with mocked dependencies."""
    from fastapi import FastAPI

    from backend.api.routes.dlq import router
    from backend.core.redis import get_redis

    # Reset global retry handler
    reset_retry_handler()

    app = FastAPI()
    app.include_router(router)

    # Override the Redis dependency
    async def override_get_redis():
        yield mock_redis

    app.dependency_overrides[get_redis] = override_get_redis

    with TestClient(app) as test_client:
        yield test_client

    # Cleanup
    reset_retry_handler()


class TestDLQStatsEndpoint:
    """Tests for GET /api/dlq/stats endpoint."""

    def test_get_stats_success(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test successful retrieval of DLQ statistics."""
        mock_redis.get_queue_length = AsyncMock(side_effect=[5, 3])

        response = client.get("/api/dlq/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["detection_queue_count"] == 5
        assert data["analysis_queue_count"] == 3
        assert data["total_count"] == 8

    def test_get_stats_empty_queues(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test stats with empty queues."""
        mock_redis.get_queue_length = AsyncMock(return_value=0)

        response = client.get("/api/dlq/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["detection_queue_count"] == 0
        assert data["analysis_queue_count"] == 0
        assert data["total_count"] == 0


class TestDLQJobsEndpoint:
    """Tests for GET /api/dlq/jobs/{queue_name} endpoint."""

    def test_get_jobs_detection_queue(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test getting jobs from detection DLQ."""
        mock_redis.peek_queue = AsyncMock(
            return_value=[
                {
                    "original_job": {"camera_id": "cam1", "file_path": "/path/img.jpg"},
                    "error": "Connection refused",
                    "attempt_count": 3,
                    "first_failed_at": "2025-12-23T10:00:00",
                    "last_failed_at": "2025-12-23T10:00:15",
                    "queue_name": "detection_queue",
                }
            ]
        )

        response = client.get("/api/dlq/jobs/dlq:detection_queue")

        assert response.status_code == 200
        data = response.json()
        assert data["queue_name"] == "dlq:detection_queue"
        assert data["count"] == 1
        assert len(data["jobs"]) == 1
        assert data["jobs"][0]["original_job"]["camera_id"] == "cam1"
        assert data["jobs"][0]["error"] == "Connection refused"

    def test_get_jobs_analysis_queue(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test getting jobs from analysis DLQ."""
        mock_redis.peek_queue = AsyncMock(
            return_value=[
                {
                    "original_job": {"batch_id": "batch_001"},
                    "error": "LLM timeout",
                    "attempt_count": 3,
                    "first_failed_at": "2025-12-23T10:00:00",
                    "last_failed_at": "2025-12-23T10:00:30",
                    "queue_name": "analysis_queue",
                }
            ]
        )

        response = client.get("/api/dlq/jobs/dlq:analysis_queue")

        assert response.status_code == 200
        data = response.json()
        assert data["queue_name"] == "dlq:analysis_queue"
        assert data["count"] == 1

    def test_get_jobs_empty_queue(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test getting jobs from empty DLQ."""
        mock_redis.peek_queue = AsyncMock(return_value=[])

        response = client.get("/api/dlq/jobs/dlq:detection_queue")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["jobs"] == []

    def test_get_jobs_with_pagination(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test pagination parameters are passed correctly."""
        mock_redis.peek_queue = AsyncMock(return_value=[])

        response = client.get("/api/dlq/jobs/dlq:detection_queue?start=10&limit=50")

        assert response.status_code == 200
        mock_redis.peek_queue.assert_called()

    def test_get_jobs_invalid_queue_name(self, client: TestClient) -> None:
        """Test invalid queue name returns validation error."""
        response = client.get("/api/dlq/jobs/invalid_queue")

        assert response.status_code == 422


class TestRequeueEndpoint:
    """Tests for POST /api/dlq/requeue/{queue_name} endpoint."""

    def test_requeue_single_job_success(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test successful requeue of a single job."""
        mock_redis.get_from_queue = AsyncMock(
            return_value={
                "original_job": {"camera_id": "cam1"},
                "error": "Error",
                "attempt_count": 3,
                "first_failed_at": "2025-12-23T10:00:00",
                "last_failed_at": "2025-12-23T10:00:15",
                "queue_name": "detection_queue",
            }
        )
        mock_redis.add_to_queue = AsyncMock(return_value=1)

        response = client.post("/api/dlq/requeue/dlq:detection_queue")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "requeued" in data["message"].lower()

    def test_requeue_empty_queue(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test requeue from empty queue."""
        mock_redis.get_from_queue = AsyncMock(return_value=None)

        response = client.post("/api/dlq/requeue/dlq:detection_queue")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "no jobs" in data["message"].lower()

    def test_requeue_analysis_queue(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test requeue from analysis DLQ."""
        mock_redis.get_from_queue = AsyncMock(
            return_value={
                "original_job": {"batch_id": "batch_001"},
                "error": "Error",
                "attempt_count": 3,
                "first_failed_at": "2025-12-23T10:00:00",
                "last_failed_at": "2025-12-23T10:00:30",
                "queue_name": "analysis_queue",
            }
        )
        mock_redis.add_to_queue = AsyncMock(return_value=1)

        response = client.post("/api/dlq/requeue/dlq:analysis_queue")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestRequeueAllEndpoint:
    """Tests for POST /api/dlq/requeue-all/{queue_name} endpoint."""

    def test_requeue_all_success(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test successful requeue of all jobs."""
        # First call for get_queue_length returns 2 (non-empty queue)
        # Then get_from_queue: two calls return jobs, third returns None (empty)
        job_data = {
            "original_job": {"camera_id": "cam1"},
            "error": "Error",
            "attempt_count": 3,
            "first_failed_at": "2025-12-23T10:00:00",
            "last_failed_at": "2025-12-23T10:00:15",
            "queue_name": "detection_queue",
        }
        mock_redis.get_queue_length = AsyncMock(return_value=2)
        mock_redis.get_from_queue = AsyncMock(side_effect=[job_data, job_data, None])
        mock_redis.add_to_queue = AsyncMock(return_value=1)

        response = client.post("/api/dlq/requeue-all/dlq:detection_queue")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "2" in data["message"]  # Should mention count

    def test_requeue_all_empty_queue(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test requeue all from empty queue returns early."""
        # Queue length is 0, so endpoint should return early without calling get_from_queue
        mock_redis.get_queue_length = AsyncMock(return_value=0)

        response = client.post("/api/dlq/requeue-all/dlq:detection_queue")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "no jobs" in data["message"].lower()
        # Verify get_from_queue was NOT called (early return)
        mock_redis.get_from_queue.assert_not_called()

    def test_requeue_all_respects_max_iterations(
        self, client: TestClient, mock_redis: MagicMock
    ) -> None:
        """Test that requeue-all stops at max_requeue_iterations from settings."""
        from backend.core.config import get_settings

        settings = get_settings()
        max_iterations = settings.max_requeue_iterations

        # Simulate a queue that always returns a job (never depletes)
        job_data = {
            "original_job": {"camera_id": "cam1"},
            "error": "Error",
            "attempt_count": 3,
            "first_failed_at": "2025-12-23T10:00:00",
            "last_failed_at": "2025-12-23T10:00:15",
            "queue_name": "detection_queue",
        }
        # Queue reports a large size
        mock_redis.get_queue_length = AsyncMock(return_value=max_iterations + 1000)
        # Always return a job (simulating infinite queue)
        mock_redis.get_from_queue = AsyncMock(return_value=job_data)
        mock_redis.add_to_queue = AsyncMock(return_value=1)

        response = client.post("/api/dlq/requeue-all/dlq:detection_queue")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Should mention the count equals max_iterations
        assert str(max_iterations) in data["message"]
        # Should indicate we hit the limit
        assert "hit limit" in data["message"].lower()
        # Verify get_from_queue was called exactly max_iterations times
        assert mock_redis.get_from_queue.call_count == max_iterations


class TestClearDLQEndpoint:
    """Tests for DELETE /api/dlq/{queue_name} endpoint."""

    def test_clear_dlq_success(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test successful DLQ clear."""
        mock_redis.get_queue_length = AsyncMock(return_value=5)
        mock_redis.clear_queue = AsyncMock(return_value=True)

        response = client.delete("/api/dlq/dlq:detection_queue")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["queue_name"] == "dlq:detection_queue"
        assert "5" in data["message"]

    def test_clear_empty_dlq(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test clearing empty DLQ."""
        mock_redis.get_queue_length = AsyncMock(return_value=0)
        mock_redis.clear_queue = AsyncMock(return_value=True)

        response = client.delete("/api/dlq/dlq:detection_queue")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_clear_dlq_failure(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test DLQ clear failure (e.g., Redis error)."""
        mock_redis.get_queue_length = AsyncMock(return_value=3)
        # Simulate Redis error by raising an exception
        mock_redis.clear_queue = AsyncMock(side_effect=RuntimeError("Redis error"))

        response = client.delete("/api/dlq/dlq:analysis_queue")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False


class TestDLQNameEnum:
    """Tests for DLQName enum."""

    def test_detection_queue_value(self) -> None:
        """Test detection queue enum value."""
        assert DLQName.DETECTION.value == "dlq:detection_queue"

    def test_analysis_queue_value(self) -> None:
        """Test analysis queue enum value."""
        assert DLQName.ANALYSIS.value == "dlq:analysis_queue"
