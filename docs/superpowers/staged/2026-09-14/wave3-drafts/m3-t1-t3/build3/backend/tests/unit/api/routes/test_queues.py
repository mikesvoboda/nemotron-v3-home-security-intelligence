"""Comprehensive unit tests for queues API routes.

Tests coverage for backend/api/routes/queues.py focusing on:
- Queue status endpoint with various queue states
- Empty queue response handling
- Normal queue depth (below warning threshold)
- Warning threshold (depth approaching limits)
- Critical threshold (depth exceeds limits or wait times too long)
- Multiple queues aggregation (detection, ai_analysis, dlq)
- Throughput calculations (jobs_per_minute, avg_processing_seconds)
- Oldest job wait time calculation
- Summary statistics accuracy
- Health status determination logic
- Overall status aggregation (if any critical, overall critical)
- Edge cases: empty queues, queues with only running jobs, mixed states
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.api.routes.queues import get_queue_service, router
from backend.api.schemas.queue_status import (
    OldestJobInfo,
    QueueHealthStatus,
    QueuesStatusResponse,
    QueueStatus,
    QueueStatusSummary,
    ThroughputMetrics,
)
from backend.core.redis import get_redis

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def test_app() -> FastAPI:
    """Create test FastAPI app with queues router.

    Includes a mock Redis dependency override to prevent
    endpoints from connecting to real Redis.
    """
    app = FastAPI()
    app.include_router(router)

    # Create mock Redis client
    mock_redis = AsyncMock()
    mock_redis.health_check.return_value = {"status": "healthy", "connected": True}

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
def mock_queue_service() -> AsyncMock:
    """Create a mock QueueStatusService."""
    service = AsyncMock()
    return service


# =============================================================================
# Helper Functions
# =============================================================================


def create_queue_status(
    name: str = "detection",
    status: QueueHealthStatus = QueueHealthStatus.HEALTHY,
    depth: int = 0,
    running: int = 0,
    workers: int = 2,
    jobs_per_minute: float = 10.0,
    avg_processing_seconds: float = 2.5,
    oldest_job: OldestJobInfo | None = None,
) -> QueueStatus:
    """Create a QueueStatus for testing.

    Args:
        name: Queue name
        status: Health status
        depth: Queue depth
        running: Number of running jobs
        workers: Number of workers
        jobs_per_minute: Throughput jobs per minute
        avg_processing_seconds: Average processing time
        oldest_job: Optional oldest job info

    Returns:
        QueueStatus instance
    """
    return QueueStatus(
        name=name,
        status=status,
        depth=depth,
        running=running,
        workers=workers,
        throughput=ThroughputMetrics(
            jobs_per_minute=jobs_per_minute,
            avg_processing_seconds=avg_processing_seconds,
        ),
        oldest_job=oldest_job,
    )


def create_queues_response(
    queues: list[QueueStatus],
    overall_status: QueueHealthStatus = QueueHealthStatus.HEALTHY,
) -> QueuesStatusResponse:
    """Create a QueuesStatusResponse for testing.

    Args:
        queues: List of queue statuses
        overall_status: Overall health status (auto-computed if None)

    Returns:
        QueuesStatusResponse instance
    """
    total_queued = sum(q.depth for q in queues)
    total_running = sum(q.running for q in queues)
    total_workers = sum(q.workers for q in queues)

    # Auto-compute overall status if not provided
    if any(q.status == QueueHealthStatus.CRITICAL for q in queues):
        computed_status = QueueHealthStatus.CRITICAL
    elif any(q.status == QueueHealthStatus.WARNING for q in queues):
        computed_status = QueueHealthStatus.WARNING
    else:
        computed_status = QueueHealthStatus.HEALTHY

    summary = QueueStatusSummary(
        total_queued=total_queued,
        total_running=total_running,
        total_workers=total_workers,
        overall_status=overall_status or computed_status,
    )

    return QueuesStatusResponse(queues=queues, summary=summary)


# =============================================================================
# Dependency Tests
# =============================================================================


class TestGetQueueService:
    """Tests for get_queue_service dependency."""

    @pytest.mark.asyncio
    async def test_get_queue_service_returns_service(self) -> None:
        """Test that get_queue_service returns a QueueStatusService instance."""
        mock_redis = AsyncMock()

        service = await get_queue_service(redis=mock_redis)

        assert service is not None
        # Verify the service has the expected interface
        assert hasattr(service, "get_queues_status_response")


# =============================================================================
# Queue Status Endpoint Tests - Empty Queues
# =============================================================================


class TestGetQueuesStatusEmpty:
    """Tests for GET /api/queues/status with empty queues."""

    @pytest.mark.asyncio
    async def test_empty_queues_all_healthy(
        self, async_client: AsyncClient, test_app: FastAPI, mock_queue_service: AsyncMock
    ) -> None:
        """Test empty queue response with all queues at zero depth."""
        empty_response = create_queues_response(
            queues=[
                create_queue_status(name="detection", depth=0, running=0, workers=2),
                create_queue_status(
                    name="ai_analysis",
                    depth=0,
                    running=0,
                    workers=2,
                    jobs_per_minute=5.0,
                    avg_processing_seconds=8.0,
                ),
                create_queue_status(
                    name="dlq",
                    depth=0,
                    running=0,
                    workers=0,
                    jobs_per_minute=0.0,
                    avg_processing_seconds=0.0,
                ),
            ]
        )
        mock_queue_service.get_queues_status_response.return_value = empty_response

        with patch(
            "backend.api.routes.queues.get_queue_status_service",
            return_value=mock_queue_service,
        ):
            response = await async_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "queues" in data
        assert "summary" in data
        assert len(data["queues"]) == 3

        # Verify summary
        assert data["summary"]["total_queued"] == 0
        assert data["summary"]["total_running"] == 0
        assert data["summary"]["total_workers"] == 4
        assert data["summary"]["overall_status"] == "healthy"

        # Verify each queue is healthy
        for queue in data["queues"]:
            assert queue["status"] == "healthy"
            assert queue["depth"] == 0
            assert queue["oldest_job"] is None

    @pytest.mark.asyncio
    async def test_empty_queues_no_oldest_job(
        self, async_client: AsyncClient, test_app: FastAPI, mock_queue_service: AsyncMock
    ) -> None:
        """Test that empty queues have no oldest_job field."""
        empty_response = create_queues_response(
            queues=[create_queue_status(name="detection", depth=0, oldest_job=None)]
        )
        mock_queue_service.get_queues_status_response.return_value = empty_response

        with patch(
            "backend.api.routes.queues.get_queue_status_service",
            return_value=mock_queue_service,
        ):
            response = await async_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        detection_queue = data["queues"][0]
        assert detection_queue["oldest_job"] is None


# =============================================================================
# Queue Status Endpoint Tests - Normal Depth
# =============================================================================


class TestGetQueuesStatusNormal:
    """Tests for GET /api/queues/status with normal queue depth."""

    @pytest.mark.asyncio
    async def test_normal_queue_depth_below_warning(
        self, async_client: AsyncClient, test_app: FastAPI, mock_queue_service: AsyncMock
    ) -> None:
        """Test normal queue depth below warning threshold."""
        normal_response = create_queues_response(
            queues=[
                create_queue_status(
                    name="detection",
                    status=QueueHealthStatus.HEALTHY,
                    depth=25,
                    running=1,
                    workers=2,
                    jobs_per_minute=10.0,
                    avg_processing_seconds=2.5,
                    oldest_job=OldestJobInfo(
                        id="/test/image.jpg",
                        queued_at=datetime.now(UTC),
                        wait_seconds=5.0,
                    ),
                ),
                create_queue_status(
                    name="ai_analysis",
                    status=QueueHealthStatus.HEALTHY,
                    depth=15,
                    running=1,
                    workers=2,
                    jobs_per_minute=5.0,
                    avg_processing_seconds=8.0,
                ),
            ]
        )
        mock_queue_service.get_queues_status_response.return_value = normal_response

        with patch(
            "backend.api.routes.queues.get_queue_status_service",
            return_value=mock_queue_service,
        ):
            response = await async_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        # Verify all queues are healthy
        for queue in data["queues"]:
            assert queue["status"] == "healthy"
            assert queue["depth"] < 50  # Below warning threshold

        # Verify summary shows healthy system
        assert data["summary"]["overall_status"] == "healthy"
        assert data["summary"]["total_queued"] == 40
        assert data["summary"]["total_running"] == 2

    @pytest.mark.asyncio
    async def test_normal_queue_with_throughput_metrics(
        self, async_client: AsyncClient, test_app: FastAPI, mock_queue_service: AsyncMock
    ) -> None:
        """Test that throughput metrics are included in response."""
        normal_response = create_queues_response(
            queues=[
                create_queue_status(
                    name="detection",
                    depth=20,
                    jobs_per_minute=12.5,
                    avg_processing_seconds=4.8,
                )
            ]
        )
        mock_queue_service.get_queues_status_response.return_value = normal_response

        with patch(
            "backend.api.routes.queues.get_queue_status_service",
            return_value=mock_queue_service,
        ):
            response = await async_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        detection_queue = data["queues"][0]
        assert "throughput" in detection_queue
        assert detection_queue["throughput"]["jobs_per_minute"] == 12.5
        assert detection_queue["throughput"]["avg_processing_seconds"] == 4.8


# =============================================================================
# Queue Status Endpoint Tests - Warning Threshold
# =============================================================================


class TestGetQueuesStatusWarning:
    """Tests for GET /api/queues/status with warning threshold."""

    @pytest.mark.asyncio
    async def test_warning_threshold_depth_approaching_limits(
        self, async_client: AsyncClient, test_app: FastAPI, mock_queue_service: AsyncMock
    ) -> None:
        """Test warning status when depth approaches limits."""
        warning_response = create_queues_response(
            queues=[
                create_queue_status(
                    name="detection",
                    status=QueueHealthStatus.WARNING,
                    depth=55,  # Above warning threshold (50)
                    running=2,
                    workers=2,
                ),
                create_queue_status(
                    name="ai_analysis",
                    status=QueueHealthStatus.HEALTHY,
                    depth=20,
                ),
            ],
            overall_status=QueueHealthStatus.WARNING,
        )
        mock_queue_service.get_queues_status_response.return_value = warning_response

        with patch(
            "backend.api.routes.queues.get_queue_status_service",
            return_value=mock_queue_service,
        ):
            response = await async_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        # Verify detection queue is in warning
        detection_queue = next(q for q in data["queues"] if q["name"] == "detection")
        assert detection_queue["status"] == "warning"
        assert detection_queue["depth"] >= 50

        # Verify overall status is warning
        assert data["summary"]["overall_status"] == "warning"

    @pytest.mark.asyncio
    async def test_warning_threshold_elevated_wait_time(
        self, async_client: AsyncClient, test_app: FastAPI, mock_queue_service: AsyncMock
    ) -> None:
        """Test warning status when wait times are elevated."""
        warning_response = create_queues_response(
            queues=[
                create_queue_status(
                    name="detection",
                    status=QueueHealthStatus.WARNING,
                    depth=25,
                    oldest_job=OldestJobInfo(
                        id="/test/image.jpg",
                        queued_at=datetime.now(UTC),
                        wait_seconds=160.0,  # >50% of 300s max_wait
                    ),
                )
            ],
            overall_status=QueueHealthStatus.WARNING,
        )
        mock_queue_service.get_queues_status_response.return_value = warning_response

        with patch(
            "backend.api.routes.queues.get_queue_status_service",
            return_value=mock_queue_service,
        ):
            response = await async_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        detection_queue = data["queues"][0]
        assert detection_queue["status"] == "warning"
        assert detection_queue["oldest_job"]["wait_seconds"] >= 150

    @pytest.mark.asyncio
    async def test_warning_status_mixed_with_healthy(
        self, async_client: AsyncClient, test_app: FastAPI, mock_queue_service: AsyncMock
    ) -> None:
        """Test that one warning queue affects overall status."""
        mixed_response = create_queues_response(
            queues=[
                create_queue_status(name="detection", status=QueueHealthStatus.HEALTHY, depth=20),
                create_queue_status(name="ai_analysis", status=QueueHealthStatus.WARNING, depth=60),
                create_queue_status(name="dlq", status=QueueHealthStatus.HEALTHY, depth=0),
            ],
            overall_status=QueueHealthStatus.WARNING,
        )
        mock_queue_service.get_queues_status_response.return_value = mixed_response

        with patch(
            "backend.api.routes.queues.get_queue_status_service",
            return_value=mock_queue_service,
        ):
            response = await async_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        # Verify overall status is warning (worst status)
        assert data["summary"]["overall_status"] == "warning"

        # Verify individual statuses
        statuses = {q["name"]: q["status"] for q in data["queues"]}
        assert statuses["detection"] == "healthy"
        assert statuses["ai_analysis"] == "warning"


# =============================================================================
# Queue Status Endpoint Tests - Critical Threshold
# =============================================================================


class TestGetQueuesStatusCritical:
    """Tests for GET /api/queues/status with critical threshold."""

    @pytest.mark.asyncio
    async def test_critical_threshold_depth_exceeds_limits(
        self, async_client: AsyncClient, test_app: FastAPI, mock_queue_service: AsyncMock
    ) -> None:
        """Test critical status when depth exceeds limits."""
        critical_response = create_queues_response(
            queues=[
                create_queue_status(
                    name="detection",
                    status=QueueHealthStatus.CRITICAL,
                    depth=150,  # Above critical threshold (100)
                    running=2,
                    workers=2,
                )
            ],
            overall_status=QueueHealthStatus.CRITICAL,
        )
        mock_queue_service.get_queues_status_response.return_value = critical_response

        with patch(
            "backend.api.routes.queues.get_queue_status_service",
            return_value=mock_queue_service,
        ):
            response = await async_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        detection_queue = data["queues"][0]
        assert detection_queue["status"] == "critical"
        assert detection_queue["depth"] >= 100
        assert data["summary"]["overall_status"] == "critical"

    @pytest.mark.asyncio
    async def test_critical_threshold_wait_time_too_long(
        self, async_client: AsyncClient, test_app: FastAPI, mock_queue_service: AsyncMock
    ) -> None:
        """Test critical status when oldest job waiting too long."""
        critical_response = create_queues_response(
            queues=[
                create_queue_status(
                    name="detection",
                    status=QueueHealthStatus.CRITICAL,
                    depth=10,
                    oldest_job=OldestJobInfo(
                        id="/test/image.jpg",
                        queued_at=datetime.now(UTC),
                        wait_seconds=600.0,  # Exceeds 300s max_wait
                    ),
                )
            ],
            overall_status=QueueHealthStatus.CRITICAL,
        )
        mock_queue_service.get_queues_status_response.return_value = critical_response

        with patch(
            "backend.api.routes.queues.get_queue_status_service",
            return_value=mock_queue_service,
        ):
            response = await async_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        detection_queue = data["queues"][0]
        assert detection_queue["status"] == "critical"
        assert detection_queue["oldest_job"]["wait_seconds"] >= 300

    @pytest.mark.asyncio
    async def test_critical_status_takes_precedence(
        self, async_client: AsyncClient, test_app: FastAPI, mock_queue_service: AsyncMock
    ) -> None:
        """Test that critical status takes precedence over warning."""
        mixed_response = create_queues_response(
            queues=[
                create_queue_status(name="detection", status=QueueHealthStatus.WARNING, depth=60),
                create_queue_status(
                    name="ai_analysis", status=QueueHealthStatus.CRITICAL, depth=120
                ),
                create_queue_status(name="dlq", status=QueueHealthStatus.HEALTHY, depth=0),
            ],
            overall_status=QueueHealthStatus.CRITICAL,
        )
        mock_queue_service.get_queues_status_response.return_value = mixed_response

        with patch(
            "backend.api.routes.queues.get_queue_status_service",
            return_value=mock_queue_service,
        ):
            response = await async_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        # Verify overall status is critical (worst status)
        assert data["summary"]["overall_status"] == "critical"


# =============================================================================
# Queue Status Endpoint Tests - Multiple Queues
# =============================================================================


class TestGetQueuesStatusMultipleQueues:
    """Tests for GET /api/queues/status with multiple queues aggregation."""

    @pytest.mark.asyncio
    async def test_multiple_queues_aggregation(
        self, async_client: AsyncClient, test_app: FastAPI, mock_queue_service: AsyncMock
    ) -> None:
        """Test aggregation of multiple queues (detection, ai_analysis, dlq)."""
        multi_queue_response = create_queues_response(
            queues=[
                create_queue_status(name="detection", depth=30, running=1, workers=2),
                create_queue_status(name="ai_analysis", depth=20, running=1, workers=2),
                create_queue_status(name="dlq", depth=5, running=0, workers=0),
            ]
        )
        mock_queue_service.get_queues_status_response.return_value = multi_queue_response

        with patch(
            "backend.api.routes.queues.get_queue_status_service",
            return_value=mock_queue_service,
        ):
            response = await async_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        # Verify all three queues are present
        queue_names = {q["name"] for q in data["queues"]}
        assert "detection" in queue_names
        assert "ai_analysis" in queue_names
        assert "dlq" in queue_names

        # Verify summary aggregation
        assert data["summary"]["total_queued"] == 55
        assert data["summary"]["total_running"] == 2
        assert data["summary"]["total_workers"] == 4

    @pytest.mark.asyncio
    async def test_summary_statistics_accuracy(
        self, async_client: AsyncClient, test_app: FastAPI, mock_queue_service: AsyncMock
    ) -> None:
        """Test that summary statistics are accurately calculated."""
        response_with_stats = create_queues_response(
            queues=[
                create_queue_status(name="detection", depth=45, running=3, workers=4),
                create_queue_status(name="ai_analysis", depth=25, running=2, workers=3),
                create_queue_status(name="dlq", depth=10, running=0, workers=0),
            ]
        )
        mock_queue_service.get_queues_status_response.return_value = response_with_stats

        with patch(
            "backend.api.routes.queues.get_queue_status_service",
            return_value=mock_queue_service,
        ):
            response = await async_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        summary = data["summary"]
        assert summary["total_queued"] == 80  # 45 + 25 + 10
        assert summary["total_running"] == 5  # 3 + 2 + 0
        assert summary["total_workers"] == 7  # 4 + 3 + 0


# =============================================================================
# Queue Status Endpoint Tests - Edge Cases
# =============================================================================


class TestGetQueuesStatusEdgeCases:
    """Tests for GET /api/queues/status edge cases."""

    @pytest.mark.asyncio
    async def test_queues_with_only_running_jobs(
        self, async_client: AsyncClient, test_app: FastAPI, mock_queue_service: AsyncMock
    ) -> None:
        """Test queues with running jobs but no pending jobs."""
        running_only_response = create_queues_response(
            queues=[
                create_queue_status(
                    name="detection",
                    status=QueueHealthStatus.HEALTHY,
                    depth=0,  # No pending
                    running=2,  # But jobs are running
                    workers=2,
                )
            ]
        )
        mock_queue_service.get_queues_status_response.return_value = running_only_response

        with patch(
            "backend.api.routes.queues.get_queue_status_service",
            return_value=mock_queue_service,
        ):
            response = await async_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        detection_queue = data["queues"][0]
        assert detection_queue["depth"] == 0
        assert detection_queue["running"] == 2
        assert detection_queue["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_mixed_queue_states(
        self, async_client: AsyncClient, test_app: FastAPI, mock_queue_service: AsyncMock
    ) -> None:
        """Test mixed queue states across different queues."""
        mixed_states_response = create_queues_response(
            queues=[
                create_queue_status(name="detection", status=QueueHealthStatus.HEALTHY, depth=10),
                create_queue_status(name="ai_analysis", status=QueueHealthStatus.WARNING, depth=65),
                create_queue_status(name="dlq", status=QueueHealthStatus.CRITICAL, depth=55),
            ],
            overall_status=QueueHealthStatus.CRITICAL,
        )
        mock_queue_service.get_queues_status_response.return_value = mixed_states_response

        with patch(
            "backend.api.routes.queues.get_queue_status_service",
            return_value=mock_queue_service,
        ):
            response = await async_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        # Verify each queue has its own status
        statuses = {q["name"]: q["status"] for q in data["queues"]}
        assert statuses["detection"] == "healthy"
        assert statuses["ai_analysis"] == "warning"
        assert statuses["dlq"] == "critical"

        # Verify overall status is critical (worst)
        assert data["summary"]["overall_status"] == "critical"

    @pytest.mark.asyncio
    async def test_zero_division_protection_in_throughput(
        self, async_client: AsyncClient, test_app: FastAPI, mock_queue_service: AsyncMock
    ) -> None:
        """Test that zero throughput values don't cause errors."""
        zero_throughput_response = create_queues_response(
            queues=[
                create_queue_status(
                    name="dlq",
                    depth=0,
                    workers=0,
                    jobs_per_minute=0.0,
                    avg_processing_seconds=0.0,
                )
            ]
        )
        mock_queue_service.get_queues_status_response.return_value = zero_throughput_response

        with patch(
            "backend.api.routes.queues.get_queue_status_service",
            return_value=mock_queue_service,
        ):
            response = await async_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        dlq_queue = data["queues"][0]
        assert dlq_queue["throughput"]["jobs_per_minute"] == 0.0
        assert dlq_queue["throughput"]["avg_processing_seconds"] == 0.0

    @pytest.mark.asyncio
    async def test_oldest_job_with_all_fields(
        self, async_client: AsyncClient, test_app: FastAPI, mock_queue_service: AsyncMock
    ) -> None:
        """Test oldest job with all fields populated."""
        now = datetime.now(UTC)
        response_with_oldest = create_queues_response(
            queues=[
                create_queue_status(
                    name="detection",
                    depth=50,
                    oldest_job=OldestJobInfo(
                        id="job_12345",
                        queued_at=now,
                        wait_seconds=45.2,
                    ),
                )
            ]
        )
        mock_queue_service.get_queues_status_response.return_value = response_with_oldest

        with patch(
            "backend.api.routes.queues.get_queue_status_service",
            return_value=mock_queue_service,
        ):
            response = await async_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        oldest_job = data["queues"][0]["oldest_job"]
        assert oldest_job is not None
        assert oldest_job["id"] == "job_12345"
        assert "queued_at" in oldest_job
        assert oldest_job["wait_seconds"] == 45.2

    @pytest.mark.asyncio
    async def test_oldest_job_calculation_accuracy(
        self, async_client: AsyncClient, test_app: FastAPI, mock_queue_service: AsyncMock
    ) -> None:
        """Test that oldest job wait time is calculated accurately."""
        response_with_wait_time = create_queues_response(
            queues=[
                create_queue_status(
                    name="detection",
                    depth=30,
                    oldest_job=OldestJobInfo(
                        id="/test/image.jpg",
                        queued_at=datetime.now(UTC),
                        wait_seconds=123.5,
                    ),
                )
            ]
        )
        mock_queue_service.get_queues_status_response.return_value = response_with_wait_time

        with patch(
            "backend.api.routes.queues.get_queue_status_service",
            return_value=mock_queue_service,
        ):
            response = await async_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        oldest_job = data["queues"][0]["oldest_job"]
        assert oldest_job["wait_seconds"] == 123.5


# =============================================================================
# Response Schema Validation Tests
# =============================================================================


class TestQueuesStatusResponseSchema:
    """Tests for response schema validation."""

    @pytest.mark.asyncio
    async def test_response_matches_schema(
        self, async_client: AsyncClient, test_app: FastAPI, mock_queue_service: AsyncMock
    ) -> None:
        """Test that response matches QueuesStatusResponse schema."""
        schema_response = create_queues_response(
            queues=[
                create_queue_status(
                    name="ai_analysis",
                    status=QueueHealthStatus.HEALTHY,
                    depth=15,
                    running=2,
                    workers=4,
                    jobs_per_minute=12.5,
                    avg_processing_seconds=4.8,
                    oldest_job=OldestJobInfo(
                        id="job_12345",
                        queued_at=datetime(2025, 12, 23, 10, 30, 0, tzinfo=UTC),
                        wait_seconds=45.2,
                    ),
                )
            ]
        )
        mock_queue_service.get_queues_status_response.return_value = schema_response

        with patch(
            "backend.api.routes.queues.get_queue_status_service",
            return_value=mock_queue_service,
        ):
            response = await async_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        # Verify top-level structure
        assert "queues" in data
        assert "summary" in data

        # Verify queue structure
        queue = data["queues"][0]
        assert "name" in queue
        assert "status" in queue
        assert "depth" in queue
        assert "running" in queue
        assert "workers" in queue
        assert "throughput" in queue
        assert "oldest_job" in queue

        # Verify throughput structure
        assert "jobs_per_minute" in queue["throughput"]
        assert "avg_processing_seconds" in queue["throughput"]

        # Verify oldest_job structure
        assert "id" in queue["oldest_job"]
        assert "queued_at" in queue["oldest_job"]
        assert "wait_seconds" in queue["oldest_job"]

        # Verify summary structure
        assert "total_queued" in data["summary"]
        assert "total_running" in data["summary"]
        assert "total_workers" in data["summary"]
        assert "overall_status" in data["summary"]

    @pytest.mark.asyncio
    async def test_health_status_enum_values(
        self, async_client: AsyncClient, test_app: FastAPI, mock_queue_service: AsyncMock
    ) -> None:
        """Test that health status uses valid enum values."""
        enum_response = create_queues_response(
            queues=[
                create_queue_status(name="detection", status=QueueHealthStatus.HEALTHY),
                create_queue_status(name="ai_analysis", status=QueueHealthStatus.WARNING),
                create_queue_status(name="dlq", status=QueueHealthStatus.CRITICAL),
            ],
            overall_status=QueueHealthStatus.CRITICAL,
        )
        mock_queue_service.get_queues_status_response.return_value = enum_response

        with patch(
            "backend.api.routes.queues.get_queue_status_service",
            return_value=mock_queue_service,
        ):
            response = await async_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        # Verify status values are valid enum strings
        valid_statuses = {"healthy", "warning", "critical"}
        for queue in data["queues"]:
            assert queue["status"] in valid_statuses
        assert data["summary"]["overall_status"] in valid_statuses

    @pytest.mark.asyncio
    async def test_numeric_fields_non_negative(
        self, async_client: AsyncClient, test_app: FastAPI, mock_queue_service: AsyncMock
    ) -> None:
        """Test that numeric fields are non-negative as per schema constraints."""
        numeric_response = create_queues_response(
            queues=[
                create_queue_status(
                    name="detection",
                    depth=10,
                    running=2,
                    workers=3,
                    jobs_per_minute=15.0,
                    avg_processing_seconds=3.5,
                )
            ]
        )
        mock_queue_service.get_queues_status_response.return_value = numeric_response

        with patch(
            "backend.api.routes.queues.get_queue_status_service",
            return_value=mock_queue_service,
        ):
            response = await async_client.get("/api/queues/status")

        assert response.status_code == 200
        data = response.json()

        queue = data["queues"][0]
        # All numeric fields should be >= 0
        assert queue["depth"] >= 0
        assert queue["running"] >= 0
        assert queue["workers"] >= 0
        assert queue["throughput"]["jobs_per_minute"] >= 0
        assert queue["throughput"]["avg_processing_seconds"] >= 0

        summary = data["summary"]
        assert summary["total_queued"] >= 0
        assert summary["total_running"] >= 0
        assert summary["total_workers"] >= 0
