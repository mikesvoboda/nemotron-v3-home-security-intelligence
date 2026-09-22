"""Unit tests for queue status service.

Tests cover:
- QueueThresholds configuration
- Health status calculation based on depth and wait time
- Queue status retrieval with mocked Redis
- All queues status aggregation
- Summary calculation with overall status
- Edge cases and error handling
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from backend.api.schemas.queue_status import (
    QueueHealthStatus,
    QueuesStatusResponse,
    QueueStatus,
    ThroughputMetrics,
)
from backend.core.constants import (
    ANALYSIS_QUEUE,
    DETECTION_QUEUE,
    DLQ_ANALYSIS_QUEUE,
    DLQ_DETECTION_QUEUE,
)
from backend.services.queue_status_service import (
    DEFAULT_THRESHOLDS,
    QUEUE_CONFIG,
    QueueStatusService,
    calculate_health,
    get_queue_status_service,
    get_thresholds,
    reset_queue_status_service,
)

# =============================================================================
# QueueThresholds Tests
# =============================================================================


class TestQueueThresholds:
    """Tests for QueueThresholds configuration."""

    def test_default_thresholds(self) -> None:
        """Test default threshold values."""
        assert DEFAULT_THRESHOLDS.depth_warning == 50
        assert DEFAULT_THRESHOLDS.depth_critical == 100
        assert DEFAULT_THRESHOLDS.max_wait_seconds == 300

    def test_ai_analysis_thresholds(self) -> None:
        """Test AI analysis queue thresholds."""
        thresholds = QUEUE_CONFIG["ai_analysis"]
        assert thresholds.depth_warning == 50
        assert thresholds.depth_critical == 100
        assert thresholds.max_wait_seconds == 300

    def test_detection_thresholds(self) -> None:
        """Test detection queue thresholds."""
        thresholds = QUEUE_CONFIG["detection"]
        assert thresholds.depth_warning == 50
        assert thresholds.depth_critical == 100
        assert thresholds.max_wait_seconds == 300

    def test_dlq_thresholds(self) -> None:
        """Test DLQ thresholds with higher tolerance."""
        thresholds = QUEUE_CONFIG["dlq"]
        assert thresholds.depth_warning == 10
        assert thresholds.depth_critical == 50
        assert thresholds.max_wait_seconds == 86400  # 24 hours

    def test_export_thresholds(self) -> None:
        """Test export queue thresholds."""
        thresholds = QUEUE_CONFIG["export"]
        assert thresholds.depth_warning == 10
        assert thresholds.depth_critical == 25
        assert thresholds.max_wait_seconds == 600

    def test_cleanup_thresholds(self) -> None:
        """Test cleanup queue thresholds."""
        thresholds = QUEUE_CONFIG["cleanup"]
        assert thresholds.depth_warning == 100
        assert thresholds.depth_critical == 500
        assert thresholds.max_wait_seconds == 3600

    def test_get_thresholds_known_queue(self) -> None:
        """Test getting thresholds for a known queue."""
        thresholds = get_thresholds("ai_analysis")
        assert thresholds == QUEUE_CONFIG["ai_analysis"]

    def test_get_thresholds_unknown_queue_returns_default(self) -> None:
        """Test getting thresholds for unknown queue returns defaults."""
        thresholds = get_thresholds("unknown_queue")
        assert thresholds == DEFAULT_THRESHOLDS


# =============================================================================
# Health Calculation Tests
# =============================================================================


class TestCalculateHealth:
    """Tests for health status calculation."""

    def test_healthy_when_empty(self) -> None:
        """Test healthy status when queue is empty."""
        status = calculate_health("ai_analysis", depth=0, oldest_wait_seconds=None)
        assert status == QueueHealthStatus.HEALTHY

    def test_healthy_below_warning_threshold(self) -> None:
        """Test healthy status when below warning threshold."""
        status = calculate_health("ai_analysis", depth=30, oldest_wait_seconds=10.0)
        assert status == QueueHealthStatus.HEALTHY

    def test_warning_at_depth_warning_threshold(self) -> None:
        """Test warning status at warning threshold."""
        status = calculate_health("ai_analysis", depth=50, oldest_wait_seconds=10.0)
        assert status == QueueHealthStatus.WARNING

    def test_warning_above_depth_warning_threshold(self) -> None:
        """Test warning status above warning threshold."""
        status = calculate_health("ai_analysis", depth=75, oldest_wait_seconds=10.0)
        assert status == QueueHealthStatus.WARNING

    def test_critical_at_depth_critical_threshold(self) -> None:
        """Test critical status at critical threshold."""
        status = calculate_health("ai_analysis", depth=100, oldest_wait_seconds=10.0)
        assert status == QueueHealthStatus.CRITICAL

    def test_critical_above_depth_critical_threshold(self) -> None:
        """Test critical status above critical threshold."""
        status = calculate_health("ai_analysis", depth=150, oldest_wait_seconds=10.0)
        assert status == QueueHealthStatus.CRITICAL

    def test_warning_at_half_max_wait_time(self) -> None:
        """Test warning status when oldest job is at 50% of max wait time."""
        # max_wait_seconds for ai_analysis is 300
        status = calculate_health("ai_analysis", depth=10, oldest_wait_seconds=150.0)
        assert status == QueueHealthStatus.WARNING

    def test_critical_at_max_wait_time(self) -> None:
        """Test critical status when oldest job exceeds max wait time."""
        # max_wait_seconds for ai_analysis is 300
        status = calculate_health("ai_analysis", depth=10, oldest_wait_seconds=300.0)
        assert status == QueueHealthStatus.CRITICAL

    def test_critical_above_max_wait_time(self) -> None:
        """Test critical status when oldest job far exceeds max wait time."""
        status = calculate_health("ai_analysis", depth=10, oldest_wait_seconds=600.0)
        assert status == QueueHealthStatus.CRITICAL

    def test_depth_critical_takes_precedence(self) -> None:
        """Test that depth critical status takes precedence over wait time warning."""
        status = calculate_health("ai_analysis", depth=100, oldest_wait_seconds=100.0)
        assert status == QueueHealthStatus.CRITICAL

    def test_dlq_with_higher_tolerances(self) -> None:
        """Test DLQ health calculation with higher tolerances."""
        # DLQ has 10/50 warning/critical and 86400 max_wait
        assert (
            calculate_health("dlq", depth=5, oldest_wait_seconds=3600.0)
            == QueueHealthStatus.HEALTHY
        )
        assert (
            calculate_health("dlq", depth=10, oldest_wait_seconds=100.0)
            == QueueHealthStatus.WARNING
        )
        assert (
            calculate_health("dlq", depth=50, oldest_wait_seconds=100.0)
            == QueueHealthStatus.CRITICAL
        )


# =============================================================================
# QueueStatusService Tests
# =============================================================================


class TestQueueStatusService:
    """Tests for QueueStatusService."""

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        """Create a mock Redis client."""
        redis = AsyncMock()
        redis.get_queue_length = AsyncMock(return_value=10)
        redis.peek_queue = AsyncMock(return_value=[])
        return redis

    @pytest.fixture
    def service(self, mock_redis: AsyncMock) -> QueueStatusService:
        """Create a QueueStatusService with mocked Redis."""
        return QueueStatusService(mock_redis)

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        """Reset the singleton before each test."""
        reset_queue_status_service()

    @pytest.mark.asyncio
    async def test_get_queue_status_empty_queue(
        self, service: QueueStatusService, mock_redis: AsyncMock
    ) -> None:
        """Test getting status for an empty queue."""
        mock_redis.get_queue_length.return_value = 0
        mock_redis.peek_queue.return_value = []

        status = await service.get_queue_status(DETECTION_QUEUE)

        assert status.name == "detection"
        assert status.depth == 0
        assert status.status == QueueHealthStatus.HEALTHY
        assert status.oldest_job is None

    @pytest.mark.asyncio
    async def test_get_queue_status_with_items(
        self, service: QueueStatusService, mock_redis: AsyncMock
    ) -> None:
        """Test getting status for a queue with items."""
        mock_redis.get_queue_length.return_value = 25
        timestamp = datetime.now(UTC).isoformat()
        mock_redis.peek_queue.return_value = [
            {"file_path": "/test/image.jpg", "timestamp": timestamp}
        ]

        status = await service.get_queue_status(DETECTION_QUEUE)

        assert status.name == "detection"
        assert status.depth == 25
        assert status.status == QueueHealthStatus.HEALTHY
        assert status.oldest_job is not None
        assert status.oldest_job.id == "/test/image.jpg"

    @pytest.mark.asyncio
    async def test_get_queue_status_warning_depth(
        self, service: QueueStatusService, mock_redis: AsyncMock
    ) -> None:
        """Test warning status when depth exceeds warning threshold."""
        mock_redis.get_queue_length.return_value = 60
        mock_redis.peek_queue.return_value = []

        status = await service.get_queue_status(DETECTION_QUEUE)

        assert status.status == QueueHealthStatus.WARNING

    @pytest.mark.asyncio
    async def test_get_queue_status_critical_depth(
        self, service: QueueStatusService, mock_redis: AsyncMock
    ) -> None:
        """Test critical status when depth exceeds critical threshold."""
        mock_redis.get_queue_length.return_value = 150
        mock_redis.peek_queue.return_value = []

        status = await service.get_queue_status(DETECTION_QUEUE)

        assert status.status == QueueHealthStatus.CRITICAL

    @pytest.mark.asyncio
    async def test_get_queue_status_old_job(
        self, service: QueueStatusService, mock_redis: AsyncMock
    ) -> None:
        """Test status when oldest job has been waiting too long."""
        mock_redis.get_queue_length.return_value = 5
        # Job queued 10 minutes ago (600 seconds) - exceeds 300s max_wait
        old_timestamp = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
        mock_redis.peek_queue.return_value = [
            {"file_path": "/test/image.jpg", "timestamp": old_timestamp}
        ]

        status = await service.get_queue_status(DETECTION_QUEUE)

        assert status.status == QueueHealthStatus.CRITICAL
        assert status.oldest_job is not None
        assert status.oldest_job.wait_seconds >= 600

    @pytest.mark.asyncio
    async def test_get_queue_status_analysis_queue(
        self, service: QueueStatusService, mock_redis: AsyncMock
    ) -> None:
        """Test getting status for analysis queue."""
        mock_redis.get_queue_length.return_value = 15
        mock_redis.peek_queue.return_value = [
            {"batch_id": "batch-123", "timestamp": datetime.now(UTC).isoformat()}
        ]

        status = await service.get_queue_status(ANALYSIS_QUEUE)

        assert status.name == "ai_analysis"
        assert status.oldest_job is not None
        assert status.oldest_job.id == "batch-123"

    @pytest.mark.asyncio
    async def test_get_queue_status_dlq(
        self, service: QueueStatusService, mock_redis: AsyncMock
    ) -> None:
        """Test getting status for DLQ."""
        mock_redis.get_queue_length.return_value = 5
        mock_redis.peek_queue.return_value = []

        status = await service.get_queue_status(DLQ_DETECTION_QUEUE)

        assert status.name == "dlq"
        assert status.workers == 0  # DLQ doesn't have workers

    @pytest.mark.asyncio
    async def test_get_all_queues_status(
        self, service: QueueStatusService, mock_redis: AsyncMock
    ) -> None:
        """Test getting status for all queues."""
        mock_redis.get_queue_length.return_value = 10
        mock_redis.peek_queue.return_value = []

        statuses = await service.get_all_queues_status()

        # Should include detection, analysis, and DLQs
        assert len(statuses) == 4
        names = [s.name for s in statuses]
        assert "detection" in names
        assert "ai_analysis" in names
        # DLQs map to "dlq" display name (may appear multiple times)
        assert any(n == "dlq" for n in names)

    @pytest.mark.asyncio
    async def test_get_all_queues_status_handles_errors(
        self, service: QueueStatusService, mock_redis: AsyncMock
    ) -> None:
        """Test that errors for individual queues don't break the entire response."""
        mock_redis.get_queue_length.side_effect = [Exception("Redis error"), 10, 5, 3]
        mock_redis.peek_queue.return_value = []

        statuses = await service.get_all_queues_status()

        # Should still return statuses for all queues
        assert len(statuses) == 4
        # First queue should be marked critical due to error
        assert statuses[0].status == QueueHealthStatus.CRITICAL

    @pytest.mark.asyncio
    async def test_get_queues_status_response(
        self, service: QueueStatusService, mock_redis: AsyncMock
    ) -> None:
        """Test getting complete queue status response."""
        # Use 5 instead of 10 to stay below DLQ warning threshold (10)
        mock_redis.get_queue_length.return_value = 5
        mock_redis.peek_queue.return_value = []

        response = await service.get_queues_status_response()

        assert isinstance(response, QueuesStatusResponse)
        assert len(response.queues) == 4
        assert response.summary.total_queued == 20  # 5 * 4 queues
        assert response.summary.overall_status == QueueHealthStatus.HEALTHY


# =============================================================================
# Summary Calculation Tests
# =============================================================================


class TestSummaryCalculation:
    """Tests for summary calculation."""

    @pytest.fixture
    def service(self) -> QueueStatusService:
        """Create a QueueStatusService with mocked Redis."""
        return QueueStatusService(AsyncMock())

    def test_summary_all_healthy(self, service: QueueStatusService) -> None:
        """Test summary when all queues are healthy."""
        queues = [
            QueueStatus(
                name="q1",
                status=QueueHealthStatus.HEALTHY,
                depth=5,
                running=1,
                workers=2,
                throughput=ThroughputMetrics(jobs_per_minute=10.0, avg_processing_seconds=2.0),
                oldest_job=None,
            ),
            QueueStatus(
                name="q2",
                status=QueueHealthStatus.HEALTHY,
                depth=10,
                running=2,
                workers=3,
                throughput=ThroughputMetrics(jobs_per_minute=5.0, avg_processing_seconds=4.0),
                oldest_job=None,
            ),
        ]

        summary = service._calculate_summary(queues)

        assert summary.total_queued == 15
        assert summary.total_running == 3
        assert summary.total_workers == 5
        assert summary.overall_status == QueueHealthStatus.HEALTHY

    def test_summary_one_warning(self, service: QueueStatusService) -> None:
        """Test summary when one queue has warning status."""
        queues = [
            QueueStatus(
                name="q1",
                status=QueueHealthStatus.HEALTHY,
                depth=5,
                running=1,
                workers=2,
                throughput=ThroughputMetrics(jobs_per_minute=10.0, avg_processing_seconds=2.0),
                oldest_job=None,
            ),
            QueueStatus(
                name="q2",
                status=QueueHealthStatus.WARNING,
                depth=60,
                running=2,
                workers=3,
                throughput=ThroughputMetrics(jobs_per_minute=5.0, avg_processing_seconds=4.0),
                oldest_job=None,
            ),
        ]

        summary = service._calculate_summary(queues)

        assert summary.overall_status == QueueHealthStatus.WARNING

    def test_summary_one_critical(self, service: QueueStatusService) -> None:
        """Test summary when one queue has critical status."""
        queues = [
            QueueStatus(
                name="q1",
                status=QueueHealthStatus.WARNING,
                depth=60,
                running=1,
                workers=2,
                throughput=ThroughputMetrics(jobs_per_minute=10.0, avg_processing_seconds=2.0),
                oldest_job=None,
            ),
            QueueStatus(
                name="q2",
                status=QueueHealthStatus.CRITICAL,
                depth=150,
                running=2,
                workers=3,
                throughput=ThroughputMetrics(jobs_per_minute=5.0, avg_processing_seconds=4.0),
                oldest_job=None,
            ),
        ]

        summary = service._calculate_summary(queues)

        assert summary.overall_status == QueueHealthStatus.CRITICAL

    def test_summary_empty_queues(self, service: QueueStatusService) -> None:
        """Test summary with empty queue list."""
        summary = service._calculate_summary([])

        assert summary.total_queued == 0
        assert summary.total_running == 0
        assert summary.total_workers == 0
        assert summary.overall_status == QueueHealthStatus.HEALTHY


# =============================================================================
# Oldest Job Info Tests
# =============================================================================


class TestOldestJobInfo:
    """Tests for oldest job info extraction."""

    @pytest.fixture
    def service(self) -> QueueStatusService:
        """Create a QueueStatusService with mocked Redis."""
        mock_redis = AsyncMock()
        return QueueStatusService(mock_redis)

    @pytest.mark.asyncio
    async def test_oldest_job_with_file_path(self, service: QueueStatusService) -> None:
        """Test extracting oldest job info with file_path."""
        service._redis.peek_queue.return_value = [
            {"file_path": "/test/image.jpg", "timestamp": datetime.now(UTC).isoformat()}
        ]

        info = await service._get_oldest_job_info("test_queue")

        assert info is not None
        assert info.id == "/test/image.jpg"
        assert info.wait_seconds >= 0

    @pytest.mark.asyncio
    async def test_oldest_job_with_batch_id(self, service: QueueStatusService) -> None:
        """Test extracting oldest job info with batch_id."""
        service._redis.peek_queue.return_value = [
            {"batch_id": "batch-456", "timestamp": datetime.now(UTC).isoformat()}
        ]

        info = await service._get_oldest_job_info("test_queue")

        assert info is not None
        assert info.id == "batch-456"

    @pytest.mark.asyncio
    async def test_oldest_job_with_pipeline_start_time(self, service: QueueStatusService) -> None:
        """Test that pipeline_start_time is preferred for latency calculation."""
        # Job was queued recently but pipeline started 5 minutes ago
        pipeline_start = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
        service._redis.peek_queue.return_value = [
            {
                "file_path": "/test/image.jpg",
                "timestamp": datetime.now(UTC).isoformat(),
                "pipeline_start_time": pipeline_start,
            }
        ]

        info = await service._get_oldest_job_info("test_queue")

        assert info is not None
        # Wait time should be ~5 minutes (300 seconds)
        assert info.wait_seconds >= 290  # Allow some tolerance

    @pytest.mark.asyncio
    async def test_oldest_job_empty_queue(self, service: QueueStatusService) -> None:
        """Test getting oldest job info from empty queue."""
        service._redis.peek_queue.return_value = []

        info = await service._get_oldest_job_info("test_queue")

        assert info is None

    @pytest.mark.asyncio
    async def test_oldest_job_non_dict_item(self, service: QueueStatusService) -> None:
        """Test handling non-dict items in queue."""
        service._redis.peek_queue.return_value = ["string_item"]

        info = await service._get_oldest_job_info("test_queue")

        assert info is not None
        assert info.id is None
        assert info.wait_seconds == 0

    @pytest.mark.asyncio
    async def test_oldest_job_invalid_timestamp(self, service: QueueStatusService) -> None:
        """Test handling invalid timestamp in job."""
        service._redis.peek_queue.return_value = [
            {"file_path": "/test/image.jpg", "timestamp": "not-a-timestamp"}
        ]

        info = await service._get_oldest_job_info("test_queue")

        assert info is not None
        assert info.id == "/test/image.jpg"
        assert info.wait_seconds == 0  # Falls back to 0 on parse error

    @pytest.mark.asyncio
    async def test_oldest_job_redis_error(self, service: QueueStatusService) -> None:
        """Test handling Redis errors gracefully."""
        service._redis.peek_queue.side_effect = Exception("Redis connection failed")

        info = await service._get_oldest_job_info("test_queue")

        assert info is None


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSingleton:
    """Tests for singleton pattern."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        """Reset the singleton before each test."""
        reset_queue_status_service()

    def test_get_queue_status_service_creates_singleton(self) -> None:
        """Test that get_queue_status_service creates a singleton."""
        mock_redis = AsyncMock()

        service1 = get_queue_status_service(mock_redis)
        service2 = get_queue_status_service(mock_redis)

        assert service1 is service2

    def test_reset_clears_singleton(self) -> None:
        """Test that reset_queue_status_service clears the singleton."""
        mock_redis = AsyncMock()

        service1 = get_queue_status_service(mock_redis)
        reset_queue_status_service()
        service2 = get_queue_status_service(mock_redis)

        assert service1 is not service2


# =============================================================================
# Throughput and Worker Info Tests
# =============================================================================


class TestThroughputAndWorkers:
    """Tests for throughput and worker info retrieval."""

    @pytest.fixture
    def service(self) -> QueueStatusService:
        """Create a QueueStatusService with mocked Redis."""
        return QueueStatusService(AsyncMock())

    @pytest.mark.asyncio
    async def test_throughput_detection_queue(self, service: QueueStatusService) -> None:
        """Test throughput metrics for detection queue."""
        throughput = await service._get_throughput_metrics(DETECTION_QUEUE)

        assert throughput.jobs_per_minute > 0
        assert throughput.avg_processing_seconds > 0

    @pytest.mark.asyncio
    async def test_throughput_analysis_queue(self, service: QueueStatusService) -> None:
        """Test throughput metrics for analysis queue."""
        throughput = await service._get_throughput_metrics(ANALYSIS_QUEUE)

        # Analysis queue (LLM) should have lower throughput
        assert throughput.jobs_per_minute > 0
        assert throughput.avg_processing_seconds > 0

    @pytest.mark.asyncio
    async def test_throughput_dlq_queue(self, service: QueueStatusService) -> None:
        """Test throughput metrics for DLQ (should be 0)."""
        throughput = await service._get_throughput_metrics(DLQ_DETECTION_QUEUE)

        # DLQ doesn't auto-process
        assert throughput.jobs_per_minute == 0
        assert throughput.avg_processing_seconds == 0

    @pytest.mark.asyncio
    async def test_worker_info_detection_queue(self, service: QueueStatusService) -> None:
        """Test worker info for detection queue."""
        workers, running = await service._get_worker_info(DETECTION_QUEUE)

        assert workers > 0
        assert running >= 0

    @pytest.mark.asyncio
    async def test_worker_info_dlq_queue(self, service: QueueStatusService) -> None:
        """Test worker info for DLQ (no workers)."""
        workers, running = await service._get_worker_info(DLQ_DETECTION_QUEUE)

        assert workers == 0
        assert running == 0


# =============================================================================
# WP4.4 kill battery (frozen triage feed archive/wp25-feed/wp44-triage,
# queue_status_service.md clusters 1,3,5,7,8,10-14,16,17,21,23,25 — 50
# TEST-GAP survivors of 69; the 19 leftovers are EQUIVALENT/LOW-VALUE,
# per-cluster justified in the dossier). Root cause: every Redis call went
# through an argument-blind AsyncMock and every value assert was
# inequality-style (> 0), so call-argument mutants and table-nudge
# mutants were silent; DLQ_ANALYSIS_QUEUE was never even imported by the
# suite. Production asserted exactly as shipped.
# =============================================================================


class TestWorkerInfoContracts:
    """Clusters 12/13/14: exact worker table, fallback and running formula."""

    @pytest.fixture
    def service(self) -> QueueStatusService:
        return QueueStatusService(AsyncMock())

    @pytest.mark.asyncio
    async def test_worker_info_exact_contracts(self, service: QueueStatusService) -> None:
        """Pin worker counts for every queue class incl. DLQ_ANALYSIS and the unknown fallback."""
        from backend.core.config import get_settings

        settings = get_settings()
        for queue, expected in (
            (DETECTION_QUEUE, settings.detection_worker_count),
            (ANALYSIS_QUEUE, settings.analysis_worker_count),
            (DLQ_DETECTION_QUEUE, 0),
            (DLQ_ANALYSIS_QUEUE, 0),  # was never exercised by any test
        ):
            workers, running = await service._get_worker_info(queue)
            assert workers == expected
            assert running == (1 if expected > 0 else 0)

        # Unknown queues fall back to exactly one worker, running 1
        assert await service._get_worker_info("custom_queue") == (1, 1)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("configured", [1, 3])
    async def test_worker_running_estimate_is_capped_at_one(
        self, service: QueueStatusService, monkeypatch: pytest.MonkeyPatch, configured: int
    ) -> None:
        """running = min(workers, 1) for any workers > 0 — incl. the workers == 1 boundary.

        Kills min(workers, 2) (needs workers >= 2) and `workers > 1` (needs workers == 1).
        """
        from types import SimpleNamespace

        import backend.core.config as config_module

        monkeypatch.setattr(
            config_module,
            "get_settings",
            lambda: SimpleNamespace(
                detection_worker_count=configured, analysis_worker_count=configured
            ),
        )
        assert await service._get_worker_info(DETECTION_QUEUE) == (configured, 1)


class TestThroughputContracts:
    """Clusters 10/11: the static throughput table IS the /api/queues contract."""

    @pytest.fixture
    def service(self) -> QueueStatusService:
        return QueueStatusService(AsyncMock())

    @pytest.mark.asyncio
    async def test_throughput_metrics_pinned_values(self, service: QueueStatusService) -> None:
        """Pin every default-throughput entry incl. DLQ_ANALYSIS and the unknown-queue zeros."""
        expected = {
            DETECTION_QUEUE: (10.0, 2.5),
            ANALYSIS_QUEUE: (5.0, 8.0),
            DLQ_DETECTION_QUEUE: (0.0, 0.0),
            DLQ_ANALYSIS_QUEUE: (0.0, 0.0),
            "custom_queue": (0.0, 0.0),  # unconfigured queues fall back to zeros
        }
        for queue, (jpm, avg) in expected.items():
            throughput = await service._get_throughput_metrics(queue)
            assert throughput.jobs_per_minute == jpm, queue
            assert throughput.avg_processing_seconds == avg, queue


class TestOldestJobContracts:
    """Clusters 3/5/7/8: id-chain priority, queued_at fallback + surfacing, naive-UTC."""

    @pytest.fixture
    def service(self) -> QueueStatusService:
        return QueueStatusService(AsyncMock())

    @pytest.mark.asyncio
    async def test_oldest_job_prefers_id_key_and_exposes_queued_at(
        self, service: QueueStatusService
    ) -> None:
        """ "id" wins the job_id chain and queued_at surfaces the parsed timestamp."""
        ts = datetime.now(UTC).isoformat()
        service._redis.peek_queue.return_value = [
            {"id": "job-1", "batch_id": "b-1", "file_path": "/a.jpg", "timestamp": ts}
        ]

        info = await service._get_oldest_job_info("test_queue")

        assert info is not None
        assert info.id == "job-1"  # kills mutated first term -> falls through/None
        assert info.queued_at is not None  # kills queued_at=None / dropped kwarg

    @pytest.mark.asyncio
    async def test_oldest_job_falls_back_to_queued_at_key(
        self, service: QueueStatusService
    ) -> None:
        """A job carrying only "queued_at" must still compute wait time."""
        ts = (datetime.now(UTC) - timedelta(seconds=400)).isoformat()
        service._redis.peek_queue.return_value = [{"file_path": "/a.jpg", "queued_at": ts}]

        info = await service._get_oldest_job_info("test_queue")

        assert info is not None
        assert info.wait_seconds >= 395  # kills broken queued_at fallback -> 0.0

    @pytest.mark.asyncio
    async def test_oldest_job_assumes_utc_for_naive_timestamp(
        self, service: QueueStatusService
    ) -> None:
        """Naive timestamps are treated as UTC instead of blowing up into info=None."""
        ts = (datetime.now(UTC) - timedelta(seconds=400)).replace(tzinfo=None).isoformat()
        service._redis.peek_queue.return_value = [{"file_path": "/a.jpg", "timestamp": ts}]

        info = await service._get_oldest_job_info("test_queue")

        assert info is not None  # flipped tz branch -> TypeError swallowed -> None
        assert info.wait_seconds >= 395


class TestQueueStatusWiring:
    """Clusters 1/16/17/25: raw-name call shape, display fallback, singleton wiring."""

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        redis = AsyncMock()
        redis.get_queue_length = AsyncMock(return_value=10)
        redis.peek_queue = AsyncMock(return_value=[])
        return redis

    @pytest.fixture
    def service(self, mock_redis: AsyncMock) -> QueueStatusService:
        return QueueStatusService(mock_redis)

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        reset_queue_status_service()

    @pytest.mark.asyncio
    async def test_get_queue_status_queries_redis_with_raw_queue_name(
        self, service: QueueStatusService, mock_redis: AsyncMock
    ) -> None:
        """Depth + peek must be requested for the raw queue name with the first-item slice.

        Mocks answer any arguments, so assert the call shape itself — this pins the
        "workers use unprefixed queue names" contract at get_queue_status.
        """
        mock_redis.peek_queue.return_value = [{"id": "job-1"}]

        status = await service.get_queue_status(DETECTION_QUEUE)

        mock_redis.get_queue_length.assert_called_once_with(DETECTION_QUEUE)
        mock_redis.peek_queue.assert_called_once_with(DETECTION_QUEUE, start=0, end=0)
        # display lookup keyed by the queue name: key->None makes .get MISS and
        # the status carries the RAW name (qstatus cluster 16, key 3)
        assert status.name == "detection"
        # throughput must be looked up under the real queue name, not None
        assert status.throughput.jobs_per_minute == 10.0
        assert status.throughput.avg_processing_seconds == 2.5

    @pytest.mark.asyncio
    async def test_get_queue_status_dlq_depth_uses_dlq_thresholds(
        self, service: QueueStatusService, mock_redis: AsyncMock
    ) -> None:
        """Depth 20: WARNING under dlq thresholds (warning=10), HEALTHY under defaults (warning=50).

        Proves calculate_health receives the display name, not None.
        """
        mock_redis.get_queue_length.return_value = 20
        mock_redis.peek_queue.return_value = []

        status = await service.get_queue_status(DLQ_DETECTION_QUEUE)

        assert status.status == QueueHealthStatus.WARNING

    @pytest.mark.asyncio
    async def test_get_queue_status_unmapped_queue_falls_back_to_raw_name(
        self, service: QueueStatusService, mock_redis: AsyncMock
    ) -> None:
        """An unmapped queue keeps its raw name instead of None (and gets default metrics)."""
        status = await service.get_queue_status("custom_queue")

        assert status.name == "custom_queue"  # None default -> pydantic ValidationError = killed
        assert status.throughput.jobs_per_minute == 0.0
        assert status.workers == 1

    def test_singleton_stores_the_redis_client(self) -> None:
        """The factory must wire the passed redis client into the service."""
        mock_redis = AsyncMock()

        service = get_queue_status_service(mock_redis)

        assert service._redis is mock_redis  # QueueStatusService(None) mutant -> not mock


class TestDegradedStatuses:
    """Clusters 21/23: the error path's degraded status must carry display name + zero metrics."""

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        redis = AsyncMock()
        redis.get_queue_length = AsyncMock(return_value=10)
        redis.peek_queue = AsyncMock(return_value=[])
        return redis

    @pytest.fixture
    def service(self, mock_redis: AsyncMock) -> QueueStatusService:
        return QueueStatusService(mock_redis)

    @pytest.mark.asyncio
    async def test_all_queues_error_statuses_are_degraded_and_named(
        self, service: QueueStatusService, mock_redis: AsyncMock
    ) -> None:
        """When every queue lookup fails, each degraded status must carry display name + zero metrics."""
        mock_redis.get_queue_length.side_effect = Exception("Redis down")
        mock_redis.peek_queue.return_value = []

        statuses = await service.get_all_queues_status()

        assert [s.name for s in statuses] == ["detection", "ai_analysis", "dlq", "dlq"]
        for s in statuses:
            assert s.status == QueueHealthStatus.CRITICAL
            assert s.depth == 0
            assert s.running == 0
            assert s.workers == 0
            assert s.throughput.jobs_per_minute == 0.0
            assert s.throughput.avg_processing_seconds == 0.0
            assert s.oldest_job is None
