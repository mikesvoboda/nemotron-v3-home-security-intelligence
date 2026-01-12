"""Integration tests for Queue Status API endpoints.

This module tests the Queue Status API endpoints (/api/queues/*) including:
- GET /api/queues/status - Get status of all job queues

Tests verify:
- Queue depth reporting
- Health status calculation
- Throughput metrics
- Worker information
- Summary statistics
"""

import os
from collections.abc import AsyncGenerator
from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
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
from backend.services.queue_status_service import reset_queue_status_service

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
        patch("backend.core.redis._redis_client", mock_redis),
        patch("backend.core.redis.init_redis", return_value=mock_redis),
        patch("backend.core.redis.close_redis", return_value=None),
        patch("backend.core.redis.get_redis", return_value=mock_redis),
    ]


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_redis_for_queues() -> AsyncMock:
    """Create a mock Redis client configured for queue operations."""
    mock_redis_client = AsyncMock()
    mock_redis_client.health_check.return_value = {
        "status": "healthy",
        "connected": True,
        "redis_version": "7.0.0",
    }
    # Default to empty queues
    mock_redis_client.get_queue_length.return_value = 0
    mock_redis_client.peek_queue.return_value = []
    return mock_redis_client


@pytest.fixture
async def queues_client(
    integration_db: str, mock_redis_for_queues: AsyncMock
) -> AsyncGenerator[AsyncClient]:
    """Async HTTP client for Queue Status API tests.

    This fixture creates an HTTP client with mocked Redis.
    """
    from backend.main import app

    # Create settings
    test_settings = Settings(
        api_key_enabled=False,
        database_url=os.environ.get("DATABASE_URL", ""),
        redis_url=os.environ.get("REDIS_URL", "redis://localhost:6379/15"),
    )

    # Reset the queue status service singleton before each test
    reset_queue_status_service()

    # Create mock services
    mock_services = create_mock_services()

    # Get all patches
    patches = get_patches(test_settings, mock_redis_for_queues, mock_services)

    # Use ExitStack to manage the patches
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)

        get_settings.cache_clear()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            yield ac
        get_settings.cache_clear()
        reset_queue_status_service()


# =============================================================================
# GET /api/queues/status Tests
# =============================================================================


class TestGetQueuesStatus:
    """Tests for GET /api/queues/status endpoint."""

    @pytest.mark.asyncio
    async def test_status_endpoint_returns_200(
        self, queues_client: AsyncClient, mock_redis_for_queues: AsyncMock
    ) -> None:
        """Test that status endpoint returns 200 OK."""
        response = await queues_client.get("/api/queues/status")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_status_empty_queues(
        self, queues_client: AsyncClient, mock_redis_for_queues: AsyncMock
    ) -> None:
        """Test status endpoint returns healthy status when queues are empty."""
        mock_redis_for_queues.get_queue_length.return_value = 0
        mock_redis_for_queues.peek_queue.return_value = []

        response = await queues_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "queues" in data
        assert "summary" in data

        # Verify all queues are healthy when empty
        for queue in data["queues"]:
            assert queue["depth"] == 0
            assert queue["status"] == "healthy"

        # Verify summary
        assert data["summary"]["total_queued"] == 0
        assert data["summary"]["overall_status"] == "healthy"

    @pytest.mark.asyncio
    async def test_status_with_queue_items(
        self, queues_client: AsyncClient, mock_redis_for_queues: AsyncMock
    ) -> None:
        """Test status endpoint with items in queues."""

        # Configure mock to return counts based on queue name
        async def get_queue_length_side_effect(queue_name: str) -> int:
            if DETECTION_QUEUE in queue_name:
                return 25
            elif ANALYSIS_QUEUE in queue_name:
                return 10
            return 0

        mock_redis_for_queues.get_queue_length.side_effect = get_queue_length_side_effect
        mock_redis_for_queues.peek_queue.return_value = []

        response = await queues_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        # Find detection queue in response
        detection_queue = next((q for q in data["queues"] if q["name"] == "detection"), None)
        assert detection_queue is not None
        assert detection_queue["depth"] == 25
        assert detection_queue["status"] == "healthy"

        # Verify summary totals
        assert data["summary"]["total_queued"] > 0

    @pytest.mark.asyncio
    async def test_status_warning_threshold(
        self, queues_client: AsyncClient, mock_redis_for_queues: AsyncMock
    ) -> None:
        """Test status shows warning when queue depth exceeds warning threshold."""

        # Configure mock to return depth at warning threshold (50 for detection)
        async def get_queue_length_side_effect(queue_name: str) -> int:
            if DETECTION_QUEUE in queue_name:
                return 60  # Above warning threshold of 50
            return 0

        mock_redis_for_queues.get_queue_length.side_effect = get_queue_length_side_effect
        mock_redis_for_queues.peek_queue.return_value = []

        response = await queues_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        # Find detection queue
        detection_queue = next((q for q in data["queues"] if q["name"] == "detection"), None)
        assert detection_queue is not None
        assert detection_queue["status"] == "warning"

        # Overall status should be warning
        assert data["summary"]["overall_status"] == "warning"

    @pytest.mark.asyncio
    async def test_status_critical_threshold(
        self, queues_client: AsyncClient, mock_redis_for_queues: AsyncMock
    ) -> None:
        """Test status shows critical when queue depth exceeds critical threshold."""

        # Configure mock to return depth at critical threshold (100 for detection)
        async def get_queue_length_side_effect(queue_name: str) -> int:
            if DETECTION_QUEUE in queue_name:
                return 150  # Above critical threshold of 100
            return 0

        mock_redis_for_queues.get_queue_length.side_effect = get_queue_length_side_effect
        mock_redis_for_queues.peek_queue.return_value = []

        response = await queues_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        # Find detection queue
        detection_queue = next((q for q in data["queues"] if q["name"] == "detection"), None)
        assert detection_queue is not None
        assert detection_queue["status"] == "critical"

        # Overall status should be critical
        assert data["summary"]["overall_status"] == "critical"

    @pytest.mark.asyncio
    async def test_status_oldest_job_tracking(
        self, queues_client: AsyncClient, mock_redis_for_queues: AsyncMock
    ) -> None:
        """Test status tracks oldest job wait time."""
        # Configure mock with an old job timestamp
        old_timestamp = (datetime.now(UTC) - timedelta(minutes=2)).isoformat()

        async def get_queue_length_side_effect(queue_name: str) -> int:
            if DETECTION_QUEUE in queue_name:
                return 5
            return 0

        async def peek_queue_side_effect(
            queue_name: str, start: int = 0, end: int = 0
        ) -> list[dict]:
            if DETECTION_QUEUE in queue_name:
                return [{"file_path": "/test/image.jpg", "timestamp": old_timestamp}]
            return []

        mock_redis_for_queues.get_queue_length.side_effect = get_queue_length_side_effect
        mock_redis_for_queues.peek_queue.side_effect = peek_queue_side_effect

        response = await queues_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        # Find detection queue
        detection_queue = next((q for q in data["queues"] if q["name"] == "detection"), None)
        assert detection_queue is not None

        # Verify oldest job info
        assert detection_queue["oldest_job"] is not None
        assert detection_queue["oldest_job"]["wait_seconds"] >= 100  # ~2 minutes

    @pytest.mark.asyncio
    async def test_status_critical_wait_time(
        self, queues_client: AsyncClient, mock_redis_for_queues: AsyncMock
    ) -> None:
        """Test status shows critical when oldest job wait time exceeds max."""
        # Configure mock with a very old job (exceeds 300s max_wait)
        old_timestamp = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()

        async def get_queue_length_side_effect(queue_name: str) -> int:
            if DETECTION_QUEUE in queue_name:
                return 5  # Low depth, should be healthy based on depth alone
            return 0

        async def peek_queue_side_effect(
            queue_name: str, start: int = 0, end: int = 0
        ) -> list[dict]:
            if DETECTION_QUEUE in queue_name:
                return [{"file_path": "/test/image.jpg", "timestamp": old_timestamp}]
            return []

        mock_redis_for_queues.get_queue_length.side_effect = get_queue_length_side_effect
        mock_redis_for_queues.peek_queue.side_effect = peek_queue_side_effect

        response = await queues_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        # Find detection queue
        detection_queue = next((q for q in data["queues"] if q["name"] == "detection"), None)
        assert detection_queue is not None

        # Status should be critical due to wait time (even with low depth)
        assert detection_queue["status"] == "critical"


# =============================================================================
# Response Schema Validation Tests
# =============================================================================


class TestQueuesResponseSchema:
    """Tests validating response schemas match expected structure."""

    @pytest.mark.asyncio
    async def test_response_structure(
        self, queues_client: AsyncClient, mock_redis_for_queues: AsyncMock
    ) -> None:
        """Test that response matches QueuesStatusResponse schema."""
        mock_redis_for_queues.get_queue_length.return_value = 10
        mock_redis_for_queues.peek_queue.return_value = []

        response = await queues_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        # Verify top-level fields
        assert "queues" in data
        assert "summary" in data
        assert isinstance(data["queues"], list)
        assert isinstance(data["summary"], dict)

    @pytest.mark.asyncio
    async def test_queue_status_fields(
        self, queues_client: AsyncClient, mock_redis_for_queues: AsyncMock
    ) -> None:
        """Test that each queue status has required fields."""
        mock_redis_for_queues.get_queue_length.return_value = 10
        mock_redis_for_queues.peek_queue.return_value = []

        response = await queues_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        for queue in data["queues"]:
            # Required fields
            assert "name" in queue
            assert "status" in queue
            assert "depth" in queue
            assert "running" in queue
            assert "workers" in queue
            assert "throughput" in queue

            # Throughput sub-fields
            assert "jobs_per_minute" in queue["throughput"]
            assert "avg_processing_seconds" in queue["throughput"]

            # Type validations
            assert isinstance(queue["name"], str)
            assert queue["status"] in ["healthy", "warning", "critical"]
            assert isinstance(queue["depth"], int)
            assert queue["depth"] >= 0

    @pytest.mark.asyncio
    async def test_summary_fields(
        self, queues_client: AsyncClient, mock_redis_for_queues: AsyncMock
    ) -> None:
        """Test that summary has required fields."""
        mock_redis_for_queues.get_queue_length.return_value = 10
        mock_redis_for_queues.peek_queue.return_value = []

        response = await queues_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        summary = data["summary"]

        # Required fields
        assert "total_queued" in summary
        assert "total_running" in summary
        assert "total_workers" in summary
        assert "overall_status" in summary

        # Type validations
        assert isinstance(summary["total_queued"], int)
        assert summary["total_queued"] >= 0
        assert summary["overall_status"] in ["healthy", "warning", "critical"]


# =============================================================================
# Queue Type Tests
# =============================================================================


class TestQueueTypes:
    """Tests for different queue types."""

    @pytest.mark.asyncio
    async def test_detection_queue_included(
        self, queues_client: AsyncClient, mock_redis_for_queues: AsyncMock
    ) -> None:
        """Test that detection queue is included in status."""
        mock_redis_for_queues.get_queue_length.return_value = 0
        mock_redis_for_queues.peek_queue.return_value = []

        response = await queues_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        queue_names = [q["name"] for q in data["queues"]]
        assert "detection" in queue_names

    @pytest.mark.asyncio
    async def test_analysis_queue_included(
        self, queues_client: AsyncClient, mock_redis_for_queues: AsyncMock
    ) -> None:
        """Test that AI analysis queue is included in status."""
        mock_redis_for_queues.get_queue_length.return_value = 0
        mock_redis_for_queues.peek_queue.return_value = []

        response = await queues_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        queue_names = [q["name"] for q in data["queues"]]
        assert "ai_analysis" in queue_names

    @pytest.mark.asyncio
    async def test_dlq_included(
        self, queues_client: AsyncClient, mock_redis_for_queues: AsyncMock
    ) -> None:
        """Test that DLQ is included in status."""
        mock_redis_for_queues.get_queue_length.return_value = 0
        mock_redis_for_queues.peek_queue.return_value = []

        response = await queues_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        queue_names = [q["name"] for q in data["queues"]]
        assert "dlq" in queue_names

    @pytest.mark.asyncio
    async def test_dlq_no_workers(
        self, queues_client: AsyncClient, mock_redis_for_queues: AsyncMock
    ) -> None:
        """Test that DLQ has 0 workers (doesn't auto-process)."""
        mock_redis_for_queues.get_queue_length.return_value = 0
        mock_redis_for_queues.peek_queue.return_value = []

        response = await queues_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        # Find DLQ
        dlq = next((q for q in data["queues"] if q["name"] == "dlq"), None)
        assert dlq is not None
        assert dlq["workers"] == 0


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestQueuesErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_redis_error_handled_gracefully(
        self, queues_client: AsyncClient, mock_redis_for_queues: AsyncMock
    ) -> None:
        """Test that Redis errors are handled gracefully."""
        # First call succeeds, second fails
        call_count = {"value": 0}

        async def get_queue_length_side_effect(queue_name: str) -> int:
            call_count["value"] += 1
            if call_count["value"] == 1:
                return 10
            raise Exception("Redis connection failed")

        mock_redis_for_queues.get_queue_length.side_effect = get_queue_length_side_effect
        mock_redis_for_queues.peek_queue.return_value = []

        response = await queues_client.get("/api/queues/status")

        # Should still return 200, just with some queues showing errors
        assert response.status_code == 200
        data = response.json()

        # Verify response still has structure
        assert "queues" in data
        assert "summary" in data

        # At least one queue should be critical due to error
        statuses = [q["status"] for q in data["queues"]]
        assert "critical" in statuses


# =============================================================================
# Summary Calculation Tests
# =============================================================================


class TestSummaryCalculation:
    """Tests for summary calculation logic."""

    @pytest.mark.asyncio
    async def test_summary_totals_correct(
        self, queues_client: AsyncClient, mock_redis_for_queues: AsyncMock
    ) -> None:
        """Test that summary totals are calculated correctly."""

        # Configure different depths for different queues
        async def get_queue_length_side_effect(queue_name: str) -> int:
            if DETECTION_QUEUE in queue_name:
                return 20
            elif ANALYSIS_QUEUE in queue_name:
                return 15
            elif DLQ_DETECTION_QUEUE in queue_name:
                return 5
            elif DLQ_ANALYSIS_QUEUE in queue_name:
                return 3
            return 0

        mock_redis_for_queues.get_queue_length.side_effect = get_queue_length_side_effect
        mock_redis_for_queues.peek_queue.return_value = []

        response = await queues_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        # Total should be sum of all queue depths
        expected_total = 20 + 15 + 5 + 3
        assert data["summary"]["total_queued"] == expected_total

    @pytest.mark.asyncio
    async def test_summary_overall_status_worst(
        self, queues_client: AsyncClient, mock_redis_for_queues: AsyncMock
    ) -> None:
        """Test that overall status reflects worst queue status."""

        # One queue healthy, one warning, one critical
        async def get_queue_length_side_effect(queue_name: str) -> int:
            if DETECTION_QUEUE in queue_name:
                return 10  # Healthy
            elif ANALYSIS_QUEUE in queue_name:
                return 60  # Warning (above 50 threshold)
            elif DLQ_DETECTION_QUEUE in queue_name:
                return 60  # Critical (above 50 for DLQ)
            return 0

        mock_redis_for_queues.get_queue_length.side_effect = get_queue_length_side_effect
        mock_redis_for_queues.peek_queue.return_value = []

        response = await queues_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        # Overall should be critical (worst status)
        assert data["summary"]["overall_status"] == "critical"


# =============================================================================
# Throughput Tests
# =============================================================================


class TestThroughputMetrics:
    """Tests for throughput metrics."""

    @pytest.mark.asyncio
    async def test_throughput_metrics_present(
        self, queues_client: AsyncClient, mock_redis_for_queues: AsyncMock
    ) -> None:
        """Test that throughput metrics are present for all queues."""
        mock_redis_for_queues.get_queue_length.return_value = 10
        mock_redis_for_queues.peek_queue.return_value = []

        response = await queues_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        for queue in data["queues"]:
            assert "throughput" in queue
            assert "jobs_per_minute" in queue["throughput"]
            assert "avg_processing_seconds" in queue["throughput"]
            assert queue["throughput"]["jobs_per_minute"] >= 0
            assert queue["throughput"]["avg_processing_seconds"] >= 0

    @pytest.mark.asyncio
    async def test_dlq_throughput_zero(
        self, queues_client: AsyncClient, mock_redis_for_queues: AsyncMock
    ) -> None:
        """Test that DLQ throughput is zero (doesn't auto-process)."""
        mock_redis_for_queues.get_queue_length.return_value = 0
        mock_redis_for_queues.peek_queue.return_value = []

        response = await queues_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        # Find DLQ
        dlq = next((q for q in data["queues"] if q["name"] == "dlq"), None)
        assert dlq is not None
        assert dlq["throughput"]["jobs_per_minute"] == 0
        assert dlq["throughput"]["avg_processing_seconds"] == 0
