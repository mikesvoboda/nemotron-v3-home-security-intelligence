"""Queue status service for monitoring job queue health.

This service provides:
- Queue depth and processing metrics
- Worker status and throughput calculation
- Health status based on configurable thresholds
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from backend.api.schemas.queue_status import (
    OldestJobInfo,
    QueueHealthStatus,
    QueuesStatusResponse,
    QueueStatus,
    QueueStatusSummary,
    ThroughputMetrics,
)
from backend.core.constants import (
    ANALYSIS_QUEUE,
    DETECTION_QUEUE,
    DLQ_ANALYSIS_QUEUE,
    DLQ_DETECTION_QUEUE,
    get_prefixed_queue_name,
)
from backend.core.logging import get_logger
from backend.core.redis import RedisClient

logger = get_logger(__name__)


# Queue configuration with thresholds for health status determination
@dataclass(frozen=True, slots=True)
class QueueThresholds:
    """Health thresholds for a queue."""

    depth_warning: int
    depth_critical: int
    max_wait_seconds: int


QUEUE_CONFIG: dict[str, QueueThresholds] = {
    "ai_analysis": QueueThresholds(
        depth_warning=50,
        depth_critical=100,
        max_wait_seconds=300,
    ),
    "detection": QueueThresholds(
        depth_warning=50,
        depth_critical=100,
        max_wait_seconds=300,
    ),
    "export": QueueThresholds(
        depth_warning=10,
        depth_critical=25,
        max_wait_seconds=600,
    ),
    "cleanup": QueueThresholds(
        depth_warning=100,
        depth_critical=500,
        max_wait_seconds=3600,
    ),
    "dlq": QueueThresholds(
        depth_warning=10,
        depth_critical=50,
        max_wait_seconds=86400,
    ),
}

# Default thresholds for queues not explicitly configured
DEFAULT_THRESHOLDS = QueueThresholds(
    depth_warning=50,
    depth_critical=100,
    max_wait_seconds=300,
)


# Map internal queue names to display names
QUEUE_NAME_MAP: dict[str, str] = {
    ANALYSIS_QUEUE: "ai_analysis",
    DETECTION_QUEUE: "detection",
    DLQ_ANALYSIS_QUEUE: "dlq",
    DLQ_DETECTION_QUEUE: "dlq",
}


def get_thresholds(queue_name: str) -> QueueThresholds:
    """Get thresholds for a queue.

    Args:
        queue_name: Queue name (display name, not internal name)

    Returns:
        QueueThresholds for the queue
    """
    return QUEUE_CONFIG.get(queue_name, DEFAULT_THRESHOLDS)


def calculate_health(
    queue_name: str,
    depth: int,
    oldest_wait_seconds: float | None,
) -> QueueHealthStatus:
    """Calculate health status for a queue based on depth and wait time.

    Args:
        queue_name: Queue display name
        depth: Current queue depth
        oldest_wait_seconds: Wait time of oldest job in seconds (None if queue empty)

    Returns:
        Health status (healthy, warning, critical)
    """
    thresholds = get_thresholds(queue_name)

    # Critical if depth exceeds critical threshold
    if depth >= thresholds.depth_critical:
        return QueueHealthStatus.CRITICAL

    # Critical if oldest job has waited too long
    if oldest_wait_seconds is not None and oldest_wait_seconds >= thresholds.max_wait_seconds:
        return QueueHealthStatus.CRITICAL

    # Warning if depth exceeds warning threshold
    if depth >= thresholds.depth_warning:
        return QueueHealthStatus.WARNING

    # Warning if oldest job is approaching max wait time (>50%)
    if oldest_wait_seconds is not None and oldest_wait_seconds >= thresholds.max_wait_seconds * 0.5:
        return QueueHealthStatus.WARNING

    return QueueHealthStatus.HEALTHY


class QueueStatusService:
    """Service for monitoring queue health and status."""

    def __init__(self, redis: RedisClient) -> None:
        """Initialize the queue status service.

        Args:
            redis: Redis client for queue operations
        """
        self._redis = redis
        # Throughput tracking (in-memory, resets on restart)
        self._job_counts: dict[str, int] = {}
        self._last_sample_time: datetime | None = None

    async def get_queue_status(self, queue_name: str) -> QueueStatus:
        """Get status for a single queue.

        Args:
            queue_name: Internal queue name (e.g., 'detection_queue')

        Returns:
            QueueStatus with current metrics
        """
        display_name = QUEUE_NAME_MAP.get(queue_name, queue_name)
        prefixed_name = get_prefixed_queue_name(queue_name)

        # Get queue depth
        depth = await self._redis.get_queue_length(prefixed_name)

        # Get oldest job info (peek first item)
        oldest_job = await self._get_oldest_job_info(prefixed_name)

        # Calculate health status
        wait_seconds = oldest_job.wait_seconds if oldest_job else None
        health_status = calculate_health(display_name, depth, wait_seconds)

        # Get throughput metrics (currently estimated/mock)
        throughput = await self._get_throughput_metrics(queue_name)

        # Get worker count (from pipeline workers if available)
        workers, running = await self._get_worker_info(queue_name)

        return QueueStatus(
            name=display_name,
            status=health_status,
            depth=depth,
            running=running,
            workers=workers,
            throughput=throughput,
            oldest_job=oldest_job,
        )

    async def get_all_queues_status(self) -> list[QueueStatus]:
        """Get status for all monitored queues.

        Returns:
            List of QueueStatus for each queue
        """
        # Define queues to monitor
        queues_to_monitor = [
            DETECTION_QUEUE,
            ANALYSIS_QUEUE,
            DLQ_DETECTION_QUEUE,
            DLQ_ANALYSIS_QUEUE,
        ]

        statuses = []
        for queue_name in queues_to_monitor:
            try:
                status = await self.get_queue_status(queue_name)
                statuses.append(status)
            except Exception as e:
                logger.warning(
                    f"Failed to get status for queue {queue_name}: {e}",
                    extra={"queue_name": queue_name, "error": str(e)},
                )
                # Include degraded status for failed queues
                display_name = QUEUE_NAME_MAP.get(queue_name, queue_name)
                statuses.append(
                    QueueStatus(
                        name=display_name,
                        status=QueueHealthStatus.CRITICAL,
                        depth=0,
                        running=0,
                        workers=0,
                        throughput=ThroughputMetrics(
                            jobs_per_minute=0.0,
                            avg_processing_seconds=0.0,
                        ),
                        oldest_job=None,
                    )
                )

        return statuses

    async def get_queues_status_response(self) -> QueuesStatusResponse:
        """Get complete queue status response for API.

        Returns:
            QueuesStatusResponse with all queues and summary
        """
        queues = await self.get_all_queues_status()
        summary = self._calculate_summary(queues)

        return QueuesStatusResponse(
            queues=queues,
            summary=summary,
        )

    async def _get_oldest_job_info(self, prefixed_queue_name: str) -> OldestJobInfo | None:
        """Get information about the oldest job in a queue.

        Args:
            prefixed_queue_name: Prefixed queue name for Redis

        Returns:
            OldestJobInfo or None if queue is empty
        """
        try:
            # Peek at the first item (oldest) without removing
            items = await self._redis.peek_queue(prefixed_queue_name, start=0, end=0)
            if not items:
                return None

            oldest = items[0]
            job_id = None
            queued_at = None
            wait_seconds = 0.0

            # Try to extract timestamp from job data
            if isinstance(oldest, dict):
                job_id = oldest.get("id") or oldest.get("batch_id") or oldest.get("file_path")
                timestamp_str = oldest.get("timestamp") or oldest.get("queued_at")
                pipeline_start = oldest.get("pipeline_start_time")

                # Use pipeline_start_time if available (more accurate for latency)
                if pipeline_start:
                    timestamp_str = pipeline_start

                if timestamp_str:
                    try:
                        queued_at = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                        now = datetime.now(UTC)
                        if queued_at.tzinfo is None:
                            # Assume UTC if no timezone
                            queued_at = queued_at.replace(tzinfo=UTC)
                        wait_seconds = (now - queued_at).total_seconds()
                    except (ValueError, AttributeError):
                        pass

            return OldestJobInfo(
                id=str(job_id) if job_id else None,
                queued_at=queued_at,
                wait_seconds=max(0.0, wait_seconds),
            )
        except Exception as e:
            logger.debug(f"Failed to get oldest job info: {e}")
            return None

    async def _get_throughput_metrics(self, queue_name: str) -> ThroughputMetrics:
        """Get throughput metrics for a queue.

        Currently returns estimated/default values. In production, this would
        be calculated from actual processing metrics stored in Redis or a
        time-series database.

        Args:
            queue_name: Internal queue name

        Returns:
            ThroughputMetrics with current throughput data
        """
        # Default throughput values by queue type
        # In production, these would be calculated from actual metrics
        default_throughput: dict[str, tuple[float, float]] = {
            DETECTION_QUEUE: (10.0, 2.5),  # 10 jobs/min, 2.5s avg
            ANALYSIS_QUEUE: (5.0, 8.0),  # 5 jobs/min, 8s avg (LLM is slower)
            DLQ_DETECTION_QUEUE: (0.0, 0.0),  # DLQ doesn't auto-process
            DLQ_ANALYSIS_QUEUE: (0.0, 0.0),
        }

        jobs_per_min, avg_seconds = default_throughput.get(queue_name, (0.0, 0.0))

        return ThroughputMetrics(
            jobs_per_minute=jobs_per_min,
            avg_processing_seconds=avg_seconds,
        )

    async def _get_worker_info(self, queue_name: str) -> tuple[int, int]:
        """Get worker count and running jobs for a queue.

        Args:
            queue_name: Internal queue name

        Returns:
            Tuple of (worker_count, running_count)
        """
        # Default worker counts based on queue type
        # In production, these would come from the PipelineWorkerManager
        default_workers: dict[str, int] = {
            DETECTION_QUEUE: 2,  # DetectionQueueWorker instances
            ANALYSIS_QUEUE: 2,  # AnalysisQueueWorker instances
            DLQ_DETECTION_QUEUE: 0,  # DLQ doesn't have workers
            DLQ_ANALYSIS_QUEUE: 0,
        }

        workers = default_workers.get(queue_name, 1)

        # Running jobs would be tracked by the workers themselves
        # For now, estimate based on queue activity
        running = min(workers, 1) if workers > 0 else 0

        return workers, running

    def _calculate_summary(self, queues: list[QueueStatus]) -> QueueStatusSummary:
        """Calculate summary statistics across all queues.

        Args:
            queues: List of queue statuses

        Returns:
            QueueStatusSummary with aggregated metrics
        """
        total_queued = sum(q.depth for q in queues)
        total_running = sum(q.running for q in queues)
        total_workers = sum(q.workers for q in queues)

        # Overall status is the worst status across all queues
        if any(q.status == QueueHealthStatus.CRITICAL for q in queues):
            overall_status = QueueHealthStatus.CRITICAL
        elif any(q.status == QueueHealthStatus.WARNING for q in queues):
            overall_status = QueueHealthStatus.WARNING
        else:
            overall_status = QueueHealthStatus.HEALTHY

        return QueueStatusSummary(
            total_queued=total_queued,
            total_running=total_running,
            total_workers=total_workers,
            overall_status=overall_status,
        )


# Singleton factory for dependency injection
_queue_status_service: QueueStatusService | None = None


def get_queue_status_service(redis: RedisClient) -> QueueStatusService:
    """Get or create the queue status service singleton.

    Args:
        redis: Redis client

    Returns:
        QueueStatusService instance
    """
    global _queue_status_service  # noqa: PLW0603
    if _queue_status_service is None:
        _queue_status_service = QueueStatusService(redis)
    return _queue_status_service


def reset_queue_status_service() -> None:
    """Reset the queue status service singleton (for testing)."""
    global _queue_status_service  # noqa: PLW0603
    _queue_status_service = None
