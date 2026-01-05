"""Unit tests for dead-letter queue (DLQ) API endpoints.

Tests cover:
- GET /api/dlq/stats - DLQ statistics
- GET /api/dlq/jobs/{queue_name} - List DLQ jobs
- POST /api/dlq/requeue/{queue_name} - Requeue single job
- POST /api/dlq/requeue-all/{queue_name} - Requeue all jobs
- DELETE /api/dlq/{queue_name} - Clear DLQ
- API key authentication for destructive operations
- Edge cases and error handling
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Set DATABASE_URL for tests before importing any backend modules
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")

from backend.api.routes.dlq import DLQName
from backend.core.constants import ANALYSIS_QUEUE, DETECTION_QUEUE
from backend.core.redis import QueueAddResult
from backend.services.retry_handler import reset_retry_handler


@pytest.fixture
def mock_redis() -> MagicMock:
    """Create a mock Redis client with spec to prevent mocking non-existent attributes."""
    from backend.core.redis import RedisClient

    redis = MagicMock(spec=RedisClient)
    redis.add_to_queue_safe = AsyncMock(return_value=QueueAddResult(success=True, queue_length=1))
    redis.get_from_queue = AsyncMock(return_value=None)
    redis.pop_from_queue_nonblocking = AsyncMock(return_value=None)
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


@pytest.fixture
def client_with_auth_enabled(mock_redis: MagicMock) -> TestClient:
    """Create a test client with API key authentication enabled."""
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

    # Patch settings to enable API key auth
    with patch("backend.api.routes.dlq.get_settings") as mock_settings:
        settings = MagicMock()
        settings.api_key_enabled = True
        settings.api_keys = ["test-api-key-12345"]
        settings.max_requeue_iterations = 1000
        mock_settings.return_value = settings

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
        mock_redis.pop_from_queue_nonblocking = AsyncMock(
            return_value={
                "original_job": {"camera_id": "cam1"},
                "error": "Error",
                "attempt_count": 3,
                "first_failed_at": "2025-12-23T10:00:00",
                "last_failed_at": "2025-12-23T10:00:15",
                "queue_name": "detection_queue",
            }
        )
        response = client.post("/api/dlq/requeue/dlq:detection_queue")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "requeued" in data["message"].lower()

    def test_requeue_empty_queue(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test requeue from empty queue."""
        mock_redis.pop_from_queue_nonblocking = AsyncMock(return_value=None)

        response = client.post("/api/dlq/requeue/dlq:detection_queue")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "no jobs" in data["message"].lower()

    def test_requeue_analysis_queue(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test requeue from analysis DLQ."""
        mock_redis.pop_from_queue_nonblocking = AsyncMock(
            return_value={
                "original_job": {"batch_id": "batch_001"},
                "error": "Error",
                "attempt_count": 3,
                "first_failed_at": "2025-12-23T10:00:00",
                "last_failed_at": "2025-12-23T10:00:30",
                "queue_name": "analysis_queue",
            }
        )
        response = client.post("/api/dlq/requeue/dlq:analysis_queue")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestRequeueAllEndpoint:
    """Tests for POST /api/dlq/requeue-all/{queue_name} endpoint."""

    def test_requeue_all_success(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test successful requeue of all jobs."""
        # First call for get_queue_length returns 2 (non-empty queue)
        # Then pop_from_queue_nonblocking: two calls return jobs, third returns None (empty)
        job_data = {
            "original_job": {"camera_id": "cam1"},
            "error": "Error",
            "attempt_count": 3,
            "first_failed_at": "2025-12-23T10:00:00",
            "last_failed_at": "2025-12-23T10:00:15",
            "queue_name": "detection_queue",
        }
        mock_redis.get_queue_length = AsyncMock(return_value=2)
        mock_redis.pop_from_queue_nonblocking = AsyncMock(side_effect=[job_data, job_data, None])
        response = client.post("/api/dlq/requeue-all/dlq:detection_queue")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "2" in data["message"]  # Should mention count

    def test_requeue_all_empty_queue(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test requeue all from empty queue returns early."""
        # Queue length is 0, so endpoint should return early without calling pop_from_queue_nonblocking
        mock_redis.get_queue_length = AsyncMock(return_value=0)

        response = client.post("/api/dlq/requeue-all/dlq:detection_queue")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "no jobs" in data["message"].lower()
        # Verify pop_from_queue_nonblocking was NOT called (early return)
        mock_redis.pop_from_queue_nonblocking.assert_not_called()

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
        mock_redis.pop_from_queue_nonblocking = AsyncMock(return_value=job_data)
        response = client.post("/api/dlq/requeue-all/dlq:detection_queue")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Should mention the count equals max_iterations
        assert str(max_iterations) in data["message"]
        # Should indicate we hit the limit
        assert "hit limit" in data["message"].lower()
        # Verify pop_from_queue_nonblocking was called exactly max_iterations times
        assert mock_redis.pop_from_queue_nonblocking.call_count == max_iterations


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

    def test_detection_queue_target_queue(self) -> None:
        """Test detection DLQ maps to correct target queue."""
        assert DLQName.DETECTION.target_queue == DETECTION_QUEUE

    def test_analysis_queue_target_queue(self) -> None:
        """Test analysis DLQ maps to correct target queue."""
        assert DLQName.ANALYSIS.target_queue == ANALYSIS_QUEUE


class TestAPIKeyAuthentication:
    """Tests for API key authentication on destructive operations."""

    def test_requeue_without_api_key_when_auth_enabled(
        self, client_with_auth_enabled: TestClient, mock_redis: MagicMock
    ) -> None:
        """Test requeue fails without API key when auth is enabled."""
        response = client_with_auth_enabled.post("/api/dlq/requeue/dlq:detection_queue")

        assert response.status_code == 401
        assert "API key required" in response.json()["detail"]

    def test_requeue_with_invalid_api_key_when_auth_enabled(
        self, client_with_auth_enabled: TestClient, mock_redis: MagicMock
    ) -> None:
        """Test requeue fails with invalid API key."""
        response = client_with_auth_enabled.post(
            "/api/dlq/requeue/dlq:detection_queue",
            headers={"X-API-Key": "invalid-key"},
        )

        assert response.status_code == 401
        assert "Invalid API key" in response.json()["detail"]

    def test_requeue_with_valid_api_key_via_header(
        self, client_with_auth_enabled: TestClient, mock_redis: MagicMock
    ) -> None:
        """Test requeue succeeds with valid API key in header."""
        mock_redis.pop_from_queue_nonblocking = AsyncMock(
            return_value={
                "original_job": {"camera_id": "cam1"},
                "error": "Error",
                "attempt_count": 3,
                "first_failed_at": "2025-12-23T10:00:00",
                "last_failed_at": "2025-12-23T10:00:15",
                "queue_name": "detection_queue",
            }
        )
        response = client_with_auth_enabled.post(
            "/api/dlq/requeue/dlq:detection_queue",
            headers={"X-API-Key": "test-api-key-12345"},
        )

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_requeue_with_valid_api_key_via_query_param(
        self, client_with_auth_enabled: TestClient, mock_redis: MagicMock
    ) -> None:
        """Test requeue succeeds with valid API key in query parameter."""
        mock_redis.pop_from_queue_nonblocking = AsyncMock(
            return_value={
                "original_job": {"camera_id": "cam1"},
                "error": "Error",
                "attempt_count": 3,
                "first_failed_at": "2025-12-23T10:00:00",
                "last_failed_at": "2025-12-23T10:00:15",
                "queue_name": "detection_queue",
            }
        )
        response = client_with_auth_enabled.post(
            "/api/dlq/requeue/dlq:detection_queue?api_key=test-api-key-12345"
        )

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_requeue_all_without_api_key_when_auth_enabled(
        self, client_with_auth_enabled: TestClient, mock_redis: MagicMock
    ) -> None:
        """Test requeue-all fails without API key when auth is enabled."""
        response = client_with_auth_enabled.post("/api/dlq/requeue-all/dlq:detection_queue")

        assert response.status_code == 401
        assert "API key required" in response.json()["detail"]

    def test_clear_dlq_without_api_key_when_auth_enabled(
        self, client_with_auth_enabled: TestClient, mock_redis: MagicMock
    ) -> None:
        """Test clear DLQ fails without API key when auth is enabled."""
        response = client_with_auth_enabled.delete("/api/dlq/dlq:detection_queue")

        assert response.status_code == 401
        assert "API key required" in response.json()["detail"]

    def test_stats_does_not_require_api_key(
        self, client_with_auth_enabled: TestClient, mock_redis: MagicMock
    ) -> None:
        """Test stats endpoint is accessible without API key."""
        mock_redis.get_queue_length = AsyncMock(return_value=0)

        response = client_with_auth_enabled.get("/api/dlq/stats")

        assert response.status_code == 200

    def test_jobs_does_not_require_api_key(
        self, client_with_auth_enabled: TestClient, mock_redis: MagicMock
    ) -> None:
        """Test jobs endpoint is accessible without API key."""
        mock_redis.peek_queue = AsyncMock(return_value=[])

        response = client_with_auth_enabled.get("/api/dlq/jobs/dlq:detection_queue")

        assert response.status_code == 200


class TestPaginationEdgeCases:
    """Tests for pagination parameter edge cases."""

    def test_get_jobs_limit_at_minimum(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test pagination with minimum limit (1)."""
        mock_redis.peek_queue = AsyncMock(return_value=[])

        response = client.get("/api/dlq/jobs/dlq:detection_queue?limit=1")

        assert response.status_code == 200

    def test_get_jobs_limit_at_maximum(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test pagination with maximum limit (1000)."""
        mock_redis.peek_queue = AsyncMock(return_value=[])

        response = client.get("/api/dlq/jobs/dlq:detection_queue?limit=1000")

        assert response.status_code == 200

    def test_get_jobs_limit_exceeds_maximum(
        self, client: TestClient, mock_redis: MagicMock
    ) -> None:
        """Test pagination rejects limit exceeding maximum (>1000)."""
        response = client.get("/api/dlq/jobs/dlq:detection_queue?limit=1001")

        assert response.status_code == 422

    def test_get_jobs_limit_below_minimum(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test pagination rejects limit below minimum (<1)."""
        response = client.get("/api/dlq/jobs/dlq:detection_queue?limit=0")

        assert response.status_code == 422

    def test_get_jobs_negative_start(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test pagination rejects negative start index."""
        response = client.get("/api/dlq/jobs/dlq:detection_queue?start=-1")

        assert response.status_code == 422

    def test_get_jobs_large_start_offset(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test pagination with large start offset."""
        mock_redis.peek_queue = AsyncMock(return_value=[])

        response = client.get("/api/dlq/jobs/dlq:detection_queue?start=999999")

        assert response.status_code == 200
        assert response.json()["count"] == 0


class TestRedisErrorHandling:
    """Tests for Redis error handling in endpoints."""

    def test_stats_with_redis_exception(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test stats endpoint handles Redis exceptions gracefully."""
        mock_redis.get_queue_length = AsyncMock(side_effect=RuntimeError("Redis connection lost"))

        response = client.get("/api/dlq/stats")

        # Should return empty stats on error (graceful degradation)
        assert response.status_code == 200
        data = response.json()
        assert data["detection_queue_count"] == 0
        assert data["analysis_queue_count"] == 0
        assert data["total_count"] == 0

    def test_get_jobs_with_redis_exception(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test get jobs endpoint handles Redis exceptions gracefully."""
        mock_redis.peek_queue = AsyncMock(side_effect=RuntimeError("Redis connection lost"))

        response = client.get("/api/dlq/jobs/dlq:detection_queue")

        # Should return empty jobs list on error
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["jobs"] == []

    def test_requeue_with_redis_exception_on_pop(
        self, client: TestClient, mock_redis: MagicMock
    ) -> None:
        """Test requeue handles Redis exception during pop."""
        mock_redis.pop_from_queue_nonblocking = AsyncMock(
            side_effect=RuntimeError("Redis connection lost")
        )

        response = client.post("/api/dlq/requeue/dlq:detection_queue")

        # Should return failure on error
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False

    def test_clear_with_redis_exception(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test clear DLQ handles Redis exception during clear."""
        mock_redis.get_queue_length = AsyncMock(return_value=5)
        mock_redis.clear_queue = AsyncMock(side_effect=RuntimeError("Redis connection lost"))

        response = client.delete("/api/dlq/dlq:detection_queue")

        # Should return failure on error
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False


class TestRequeueAllEdgeCases:
    """Additional edge case tests for requeue-all endpoint."""

    def test_requeue_all_partial_success(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test requeue-all handles partial success (some jobs fail to requeue)."""
        # Queue reports 3 jobs
        mock_redis.get_queue_length = AsyncMock(return_value=3)
        # First two succeed, then queue depletes
        job_data = {
            "original_job": {"camera_id": "cam1"},
            "error": "Error",
            "attempt_count": 3,
            "first_failed_at": "2025-12-23T10:00:00",
            "last_failed_at": "2025-12-23T10:00:15",
            "queue_name": "detection_queue",
        }
        # Pop returns jobs twice, then stops (simulating queue depleted)
        mock_redis.pop_from_queue_nonblocking = AsyncMock(side_effect=[job_data, job_data, None])

        response = client.post("/api/dlq/requeue-all/dlq:detection_queue")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "2" in data["message"]

    def test_requeue_all_analysis_queue(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test requeue-all for analysis DLQ routes to correct target queue."""
        job_data = {
            "original_job": {"batch_id": "batch_001"},
            "error": "LLM timeout",
            "attempt_count": 3,
            "first_failed_at": "2025-12-23T10:00:00",
            "last_failed_at": "2025-12-23T10:00:30",
            "queue_name": "analysis_queue",
        }
        mock_redis.get_queue_length = AsyncMock(return_value=1)
        mock_redis.pop_from_queue_nonblocking = AsyncMock(side_effect=[job_data, None])

        response = client.post("/api/dlq/requeue-all/dlq:analysis_queue")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestMultipleJobsScenarios:
    """Tests for scenarios with multiple jobs."""

    def test_get_jobs_returns_multiple(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test getting multiple jobs from DLQ."""
        mock_redis.peek_queue = AsyncMock(
            return_value=[
                {
                    "original_job": {"camera_id": "cam1", "file_path": "/path/img1.jpg"},
                    "error": "Connection refused",
                    "attempt_count": 3,
                    "first_failed_at": "2025-12-23T10:00:00",
                    "last_failed_at": "2025-12-23T10:00:15",
                    "queue_name": "detection_queue",
                },
                {
                    "original_job": {"camera_id": "cam2", "file_path": "/path/img2.jpg"},
                    "error": "Timeout",
                    "attempt_count": 2,
                    "first_failed_at": "2025-12-23T10:01:00",
                    "last_failed_at": "2025-12-23T10:01:10",
                    "queue_name": "detection_queue",
                },
                {
                    "original_job": {"camera_id": "cam3", "file_path": "/path/img3.jpg"},
                    "error": "Service unavailable",
                    "attempt_count": 1,
                    "first_failed_at": "2025-12-23T10:02:00",
                    "last_failed_at": "2025-12-23T10:02:05",
                    "queue_name": "detection_queue",
                },
            ]
        )

        response = client.get("/api/dlq/jobs/dlq:detection_queue")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 3
        assert len(data["jobs"]) == 3
        assert data["jobs"][0]["original_job"]["camera_id"] == "cam1"
        assert data["jobs"][1]["original_job"]["camera_id"] == "cam2"
        assert data["jobs"][2]["original_job"]["camera_id"] == "cam3"

    def test_stats_with_different_queue_counts(
        self, client: TestClient, mock_redis: MagicMock
    ) -> None:
        """Test stats returns different counts for different queues."""
        mock_redis.get_queue_length = AsyncMock(side_effect=[10, 5])

        response = client.get("/api/dlq/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["detection_queue_count"] == 10
        assert data["analysis_queue_count"] == 5
        assert data["total_count"] == 15


class TestClearDLQEdgeCases:
    """Additional edge case tests for clear DLQ endpoint."""

    def test_clear_detection_dlq(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test clear works for detection DLQ."""
        mock_redis.get_queue_length = AsyncMock(return_value=3)
        mock_redis.clear_queue = AsyncMock(return_value=True)

        response = client.delete("/api/dlq/dlq:detection_queue")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["queue_name"] == "dlq:detection_queue"
        assert "3" in data["message"]

    def test_clear_analysis_dlq(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test clear works for analysis DLQ."""
        mock_redis.get_queue_length = AsyncMock(return_value=7)
        mock_redis.clear_queue = AsyncMock(return_value=True)

        response = client.delete("/api/dlq/dlq:analysis_queue")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["queue_name"] == "dlq:analysis_queue"
        assert "7" in data["message"]

    def test_clear_invalid_queue_name(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test clear rejects invalid queue name."""
        response = client.delete("/api/dlq/invalid_queue")

        assert response.status_code == 422


class TestRequeueInvalidQueueName:
    """Tests for invalid queue names in requeue endpoints."""

    def test_requeue_invalid_queue_name(self, client: TestClient, mock_redis: MagicMock) -> None:
        """Test requeue rejects invalid queue name."""
        response = client.post("/api/dlq/requeue/invalid_queue")

        assert response.status_code == 422

    def test_requeue_all_invalid_queue_name(
        self, client: TestClient, mock_redis: MagicMock
    ) -> None:
        """Test requeue-all rejects invalid queue name."""
        response = client.post("/api/dlq/requeue-all/invalid_queue")

        assert response.status_code == 422
