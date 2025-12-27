"""Pipeline worker services for continuous detection and analysis processing.

This module provides always-on worker processes that:
- Consume from detection_queue and analysis_queue (Redis)
- Run batch timeout checks periodically
- Handle graceful shutdown (SIGTERM/SIGINT)
- Create detections and events automatically

Worker Architecture:
    The workers run as asyncio background tasks within the FastAPI lifespan.
    This in-process approach is simpler and appropriate for single-instance deployments.

    For multi-instance/scaled deployments, these workers can be extracted to
    separate processes by running them via `python -m backend.services.pipeline_workers`.

Queue Flow:
    1. FileWatcher -> detection_queue (Redis)
    2. DetectionQueueWorker consumes from detection_queue
       - Calls DetectorClient.detect_objects()
       - Calls BatchAggregator.add_detection()
    3. BatchTimeoutWorker periodically checks batch timeouts
       - Calls BatchAggregator.check_batch_timeouts()
       - Closed batches are pushed to analysis_queue
    4. AnalysisQueueWorker consumes from analysis_queue
       - Calls NemotronAnalyzer.analyze_batch()
       - Creates Event records and broadcasts via WebSocket
"""

import asyncio
import signal
from dataclasses import dataclass
from enum import Enum
from typing import Any

from backend.core.config import get_settings
from backend.core.database import get_session
from backend.core.logging import get_logger
from backend.core.metrics import (
    observe_stage_duration,
    record_pipeline_error,
    set_queue_depth,
)
from backend.core.redis import RedisClient
from backend.services.batch_aggregator import BatchAggregator
from backend.services.detector_client import DetectorClient
from backend.services.nemotron_analyzer import NemotronAnalyzer

logger = get_logger(__name__)


class WorkerState(Enum):
    """Worker lifecycle states."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class WorkerStats:
    """Statistics for a worker process."""

    items_processed: int = 0
    errors: int = 0
    last_processed_at: float | None = None
    state: WorkerState = WorkerState.STOPPED

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary."""
        return {
            "items_processed": self.items_processed,
            "errors": self.errors,
            "last_processed_at": self.last_processed_at,
            "state": self.state.value,
        }


class DetectionQueueWorker:
    """Worker that consumes images from detection_queue and runs object detection.

    This worker:
    1. Pops items from detection_queue (Redis BLPOP with timeout)
    2. Runs RT-DETRv2 detection via DetectorClient
    3. Adds detections to batch via BatchAggregator
    4. Handles errors gracefully and continues processing

    The worker runs continuously until stop() is called.
    """

    def __init__(
        self,
        redis_client: RedisClient,
        detector_client: DetectorClient | None = None,
        batch_aggregator: BatchAggregator | None = None,
        queue_name: str = "detection_queue",
        poll_timeout: int = 5,
        stop_timeout: float = 10.0,
    ) -> None:
        """Initialize detection queue worker.

        Args:
            redis_client: Redis client for queue operations
            detector_client: Client for RT-DETRv2. If None, will be created.
            batch_aggregator: Aggregator for batching detections. If None, will be created.
            queue_name: Name of the Redis queue to consume from
            poll_timeout: Timeout in seconds for BLPOP (allows checking shutdown signal)
            stop_timeout: Timeout in seconds for graceful stop before force cancel
        """
        self._redis = redis_client
        self._detector = detector_client or DetectorClient()
        self._aggregator = batch_aggregator or BatchAggregator(redis_client=redis_client)
        self._queue_name = queue_name
        self._poll_timeout = poll_timeout
        self._stop_timeout = stop_timeout

        self._running = False
        self._task: asyncio.Task | None = None
        self._stats = WorkerStats()

    @property
    def stats(self) -> WorkerStats:
        """Get worker statistics."""
        return self._stats

    @property
    def running(self) -> bool:
        """Check if worker is running."""
        return self._running

    async def start(self) -> None:
        """Start the detection queue worker.

        Creates a background task that continuously consumes from the queue.
        This method is idempotent - calling it multiple times is safe.
        """
        if self._running:
            logger.warning("DetectionQueueWorker already running")
            return

        logger.info("Starting DetectionQueueWorker", extra={"queue": self._queue_name})
        self._running = True
        self._stats.state = WorkerState.STARTING
        self._task = asyncio.create_task(self._run_loop())
        self._stats.state = WorkerState.RUNNING

    async def stop(self) -> None:
        """Stop the detection queue worker gracefully.

        Signals the worker to stop and waits for current processing to complete.
        """
        if not self._running:
            logger.debug("DetectionQueueWorker not running, nothing to stop")
            return

        logger.info("Stopping DetectionQueueWorker")
        self._stats.state = WorkerState.STOPPING
        self._running = False

        if self._task:
            # Wait for task to complete with timeout
            try:
                await asyncio.wait_for(self._task, timeout=self._stop_timeout)
            except TimeoutError:
                logger.warning("DetectionQueueWorker task did not stop in time, cancelling")
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            self._task = None

        self._stats.state = WorkerState.STOPPED
        logger.info("DetectionQueueWorker stopped")

    async def _run_loop(self) -> None:
        """Main processing loop for the detection queue worker."""
        logger.info("DetectionQueueWorker loop started")

        while self._running:
            try:
                # Pop item from queue with timeout (allows checking shutdown signal)
                item = await self._redis.get_from_queue(
                    self._queue_name,
                    timeout=self._poll_timeout,
                )

                if item is None:
                    # Timeout - no items in queue, continue loop to check shutdown
                    continue

                await self._process_detection_item(item)

            except asyncio.CancelledError:
                logger.info("DetectionQueueWorker loop cancelled")
                break
            except Exception as e:
                self._stats.errors += 1
                self._stats.state = WorkerState.ERROR
                record_pipeline_error("detection_worker_error")
                logger.error(
                    f"Error in DetectionQueueWorker loop: {e}",
                    exc_info=True,
                    extra={"error_count": self._stats.errors},
                )
                # Brief delay before retrying to prevent tight error loop
                await asyncio.sleep(1.0)
                self._stats.state = WorkerState.RUNNING

        logger.info(
            "DetectionQueueWorker loop exited",
            extra={"items_processed": self._stats.items_processed},
        )

    async def _process_detection_item(self, item: dict[str, Any]) -> None:
        """Process a single detection queue item.

        Args:
            item: Queue item with camera_id, file_path, timestamp
        """
        import time

        start_time = time.time()
        camera_id = item.get("camera_id")
        file_path = item.get("file_path")

        if not camera_id or not file_path:
            logger.warning(f"Invalid detection queue item: {item}")
            return

        logger.debug(
            f"Processing detection item: {file_path}",
            extra={"camera_id": camera_id, "file_path": file_path},
        )

        try:
            # Run object detection
            async with get_session() as session:
                detections = await self._detector.detect_objects(
                    image_path=file_path,
                    camera_id=camera_id,
                    session=session,
                )

            # Add detections to batch
            for detection in detections:
                await self._aggregator.add_detection(
                    camera_id=camera_id,
                    detection_id=str(detection.id),
                    _file_path=file_path,
                    confidence=detection.confidence,
                    object_type=detection.object_type,
                )

            self._stats.items_processed += 1
            self._stats.last_processed_at = time.time()

            # Record detect stage duration
            duration = time.time() - start_time
            observe_stage_duration("detect", duration)

            logger.debug(
                f"Processed {len(detections)} detections from {file_path}",
                extra={
                    "camera_id": camera_id,
                    "detection_count": len(detections),
                    "items_processed": self._stats.items_processed,
                },
            )

        except Exception as e:
            self._stats.errors += 1
            record_pipeline_error("detection_processing_error")
            logger.error(
                f"Failed to process detection item: {e}",
                extra={"camera_id": camera_id, "file_path": file_path},
                exc_info=True,
            )


class AnalysisQueueWorker:
    """Worker that consumes batches from analysis_queue and runs LLM analysis.

    This worker:
    1. Pops items from analysis_queue (Redis BLPOP with timeout)
    2. Runs Nemotron LLM analysis via NemotronAnalyzer
    3. Creates Event records with risk scores
    4. Broadcasts events via WebSocket

    The worker runs continuously until stop() is called.
    """

    def __init__(
        self,
        redis_client: RedisClient,
        analyzer: NemotronAnalyzer | None = None,
        queue_name: str = "analysis_queue",
        poll_timeout: int = 5,
        stop_timeout: float = 30.0,
    ) -> None:
        """Initialize analysis queue worker.

        Args:
            redis_client: Redis client for queue operations
            analyzer: NemotronAnalyzer instance. If None, will be created.
            queue_name: Name of the Redis queue to consume from
            poll_timeout: Timeout in seconds for BLPOP
            stop_timeout: Timeout in seconds for graceful stop before force cancel
        """
        self._redis = redis_client
        self._analyzer = analyzer or NemotronAnalyzer(redis_client=redis_client)
        self._queue_name = queue_name
        self._poll_timeout = poll_timeout
        self._stop_timeout = stop_timeout

        self._running = False
        self._task: asyncio.Task | None = None
        self._stats = WorkerStats()

    @property
    def stats(self) -> WorkerStats:
        """Get worker statistics."""
        return self._stats

    @property
    def running(self) -> bool:
        """Check if worker is running."""
        return self._running

    async def start(self) -> None:
        """Start the analysis queue worker."""
        if self._running:
            logger.warning("AnalysisQueueWorker already running")
            return

        logger.info("Starting AnalysisQueueWorker", extra={"queue": self._queue_name})
        self._running = True
        self._stats.state = WorkerState.STARTING
        self._task = asyncio.create_task(self._run_loop())
        self._stats.state = WorkerState.RUNNING

    async def stop(self) -> None:
        """Stop the analysis queue worker gracefully."""
        if not self._running:
            logger.debug("AnalysisQueueWorker not running, nothing to stop")
            return

        logger.info("Stopping AnalysisQueueWorker")
        self._stats.state = WorkerState.STOPPING
        self._running = False

        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=self._stop_timeout)
            except TimeoutError:
                logger.warning("AnalysisQueueWorker task did not stop in time, cancelling")
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            self._task = None

        self._stats.state = WorkerState.STOPPED
        logger.info("AnalysisQueueWorker stopped")

    async def _run_loop(self) -> None:
        """Main processing loop for the analysis queue worker."""
        logger.info("AnalysisQueueWorker loop started")

        while self._running:
            try:
                # Pop item from queue with timeout
                item = await self._redis.get_from_queue(
                    self._queue_name,
                    timeout=self._poll_timeout,
                )

                if item is None:
                    continue

                await self._process_analysis_item(item)

            except asyncio.CancelledError:
                logger.info("AnalysisQueueWorker loop cancelled")
                break
            except Exception as e:
                self._stats.errors += 1
                self._stats.state = WorkerState.ERROR
                record_pipeline_error("analysis_worker_error")
                logger.error(
                    f"Error in AnalysisQueueWorker loop: {e}",
                    exc_info=True,
                    extra={"error_count": self._stats.errors},
                )
                await asyncio.sleep(1.0)
                self._stats.state = WorkerState.RUNNING

        logger.info(
            "AnalysisQueueWorker loop exited",
            extra={"items_processed": self._stats.items_processed},
        )

    async def _process_analysis_item(self, item: dict[str, Any]) -> None:
        """Process a single analysis queue item.

        Args:
            item: Queue item with batch_id, camera_id, detection_ids
        """
        import time

        batch_id = item.get("batch_id")
        camera_id = item.get("camera_id")

        if not batch_id:
            logger.warning(f"Invalid analysis queue item: {item}")
            return

        logger.info(
            f"Processing analysis for batch {batch_id}",
            extra={"batch_id": batch_id, "camera_id": camera_id},
        )

        try:
            # Run LLM analysis
            event = await self._analyzer.analyze_batch(batch_id)

            self._stats.items_processed += 1
            self._stats.last_processed_at = time.time()

            logger.info(
                f"Created event {event.id} for batch {batch_id}: risk_score={event.risk_score}",
                extra={
                    "event_id": event.id,
                    "batch_id": batch_id,
                    "camera_id": camera_id,
                    "risk_score": event.risk_score,
                    "items_processed": self._stats.items_processed,
                },
            )

        except ValueError as e:
            # Batch not found or no detections - log warning but don't count as error
            logger.warning(
                f"Skipping batch {batch_id}: {e}",
                extra={"batch_id": batch_id, "camera_id": camera_id},
            )
        except Exception as e:
            self._stats.errors += 1
            record_pipeline_error("analysis_batch_error")
            logger.error(
                f"Failed to analyze batch {batch_id}: {e}",
                extra={"batch_id": batch_id, "camera_id": camera_id},
                exc_info=True,
            )


class BatchTimeoutWorker:
    """Worker that periodically checks and closes timed-out batches.

    This worker runs at a configurable interval and:
    1. Calls BatchAggregator.check_batch_timeouts()
    2. Closed batches are automatically pushed to analysis_queue

    This ensures batches don't stay open indefinitely when no new
    detections arrive.
    """

    def __init__(
        self,
        redis_client: RedisClient,
        batch_aggregator: BatchAggregator | None = None,
        check_interval: float = 10.0,
        stop_timeout: float = 10.0,
    ) -> None:
        """Initialize batch timeout worker.

        Args:
            redis_client: Redis client for batch operations
            batch_aggregator: Aggregator for batch timeout checks. If None, will be created.
            check_interval: How often to check for timeouts (seconds)
            stop_timeout: Timeout in seconds for graceful stop before force cancel
        """
        self._redis = redis_client
        self._aggregator = batch_aggregator or BatchAggregator(redis_client=redis_client)
        self._check_interval = check_interval
        self._stop_timeout = stop_timeout

        self._running = False
        self._task: asyncio.Task | None = None
        self._stats = WorkerStats()

    @property
    def stats(self) -> WorkerStats:
        """Get worker statistics."""
        return self._stats

    @property
    def running(self) -> bool:
        """Check if worker is running."""
        return self._running

    async def start(self) -> None:
        """Start the batch timeout worker."""
        if self._running:
            logger.warning("BatchTimeoutWorker already running")
            return

        logger.info(
            "Starting BatchTimeoutWorker",
            extra={"check_interval": self._check_interval},
        )
        self._running = True
        self._stats.state = WorkerState.STARTING
        self._task = asyncio.create_task(self._run_loop())
        self._stats.state = WorkerState.RUNNING

    async def stop(self) -> None:
        """Stop the batch timeout worker gracefully."""
        if not self._running:
            logger.debug("BatchTimeoutWorker not running, nothing to stop")
            return

        logger.info("Stopping BatchTimeoutWorker")
        self._stats.state = WorkerState.STOPPING
        self._running = False

        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=self._stop_timeout)
            except TimeoutError:
                logger.warning("BatchTimeoutWorker task did not stop in time, cancelling")
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            self._task = None

        self._stats.state = WorkerState.STOPPED
        logger.info("BatchTimeoutWorker stopped")

    async def _run_loop(self) -> None:
        """Main processing loop for the batch timeout worker."""
        import time

        logger.info("BatchTimeoutWorker loop started")

        while self._running:
            try:
                start_time = time.time()

                # Check for batch timeouts
                closed_batches = await self._aggregator.check_batch_timeouts()

                if closed_batches:
                    self._stats.items_processed += len(closed_batches)
                    self._stats.last_processed_at = time.time()

                    # Record batch stage duration
                    duration = time.time() - start_time
                    observe_stage_duration("batch", duration)

                    logger.info(
                        f"Closed {len(closed_batches)} timed-out batches",
                        extra={
                            "batch_count": len(closed_batches),
                            "batch_ids": closed_batches,
                        },
                    )

                # Wait before next check
                await asyncio.sleep(self._check_interval)

            except asyncio.CancelledError:
                logger.info("BatchTimeoutWorker loop cancelled")
                break
            except Exception as e:
                self._stats.errors += 1
                self._stats.state = WorkerState.ERROR
                record_pipeline_error("batch_timeout_error")
                logger.error(
                    f"Error in BatchTimeoutWorker loop: {e}",
                    exc_info=True,
                    extra={"error_count": self._stats.errors},
                )
                await asyncio.sleep(self._check_interval)
                self._stats.state = WorkerState.RUNNING

        logger.info(
            "BatchTimeoutWorker loop exited",
            extra={"batches_closed": self._stats.items_processed},
        )


class QueueMetricsWorker:
    """Worker that periodically updates queue depth metrics for Prometheus.

    This worker runs at a configurable interval and:
    1. Queries Redis for detection_queue and analysis_queue lengths
    2. Updates Prometheus gauge metrics with current depths

    This provides observability into queue backlogs without impacting
    the main processing workers.
    """

    def __init__(
        self,
        redis_client: RedisClient,
        update_interval: float = 5.0,
    ) -> None:
        """Initialize queue metrics worker.

        Args:
            redis_client: Redis client for queue length queries
            update_interval: How often to update metrics (seconds)
        """
        self._redis = redis_client
        self._update_interval = update_interval
        self._running = False
        self._task: asyncio.Task | None = None

    @property
    def running(self) -> bool:
        """Check if worker is running."""
        return self._running

    async def start(self) -> None:
        """Start the queue metrics worker."""
        if self._running:
            logger.warning("QueueMetricsWorker already running")
            return

        logger.info(
            "Starting QueueMetricsWorker",
            extra={"update_interval": self._update_interval},
        )
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """Stop the queue metrics worker gracefully."""
        if not self._running:
            return

        logger.info("Stopping QueueMetricsWorker")
        self._running = False

        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except TimeoutError:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            self._task = None

        logger.info("QueueMetricsWorker stopped")

    async def _run_loop(self) -> None:
        """Main loop for updating queue metrics."""
        logger.info("QueueMetricsWorker loop started")

        while self._running:
            try:
                # Get queue depths from Redis
                detection_depth = await self._redis.get_queue_length("detection_queue")
                analysis_depth = await self._redis.get_queue_length("analysis_queue")

                # Update Prometheus metrics
                set_queue_depth("detection", detection_depth)
                set_queue_depth("analysis", analysis_depth)

                logger.debug(
                    f"Updated queue metrics: detection={detection_depth}, analysis={analysis_depth}"
                )

            except asyncio.CancelledError:
                logger.info("QueueMetricsWorker loop cancelled")
                break
            except Exception as e:
                logger.warning(f"Failed to update queue metrics: {e}")

            await asyncio.sleep(self._update_interval)

        logger.info("QueueMetricsWorker loop exited")


class PipelineWorkerManager:
    """Manages all pipeline workers with unified start/stop and status reporting.

    This class provides:
    - Unified lifecycle management for all workers
    - Signal handling for graceful shutdown (SIGTERM/SIGINT)
    - Status reporting for observability
    - Configuration from settings

    Usage in main.py lifespan:
        manager = PipelineWorkerManager(redis_client)
        await manager.start()
        # ... application runs ...
        await manager.stop()
    """

    def __init__(
        self,
        redis_client: RedisClient,
        detector_client: DetectorClient | None = None,
        analyzer: NemotronAnalyzer | None = None,
        enable_detection_worker: bool = True,
        enable_analysis_worker: bool = True,
        enable_timeout_worker: bool = True,
        enable_metrics_worker: bool = True,
    ) -> None:
        """Initialize pipeline worker manager.

        Args:
            redis_client: Redis client for queue operations
            detector_client: Optional DetectorClient instance
            analyzer: Optional NemotronAnalyzer instance
            enable_detection_worker: Whether to start detection queue worker
            enable_analysis_worker: Whether to start analysis queue worker
            enable_timeout_worker: Whether to start batch timeout worker
            enable_metrics_worker: Whether to start queue metrics worker
        """
        self._redis = redis_client
        settings = get_settings()

        # Create shared batch aggregator for detection and timeout workers
        self._aggregator = BatchAggregator(redis_client=redis_client)

        # Initialize workers
        self._detection_worker: DetectionQueueWorker | None = None
        self._analysis_worker: AnalysisQueueWorker | None = None
        self._timeout_worker: BatchTimeoutWorker | None = None
        self._metrics_worker: QueueMetricsWorker | None = None

        if enable_detection_worker:
            self._detection_worker = DetectionQueueWorker(
                redis_client=redis_client,
                detector_client=detector_client,
                batch_aggregator=self._aggregator,
            )

        if enable_analysis_worker:
            self._analysis_worker = AnalysisQueueWorker(
                redis_client=redis_client,
                analyzer=analyzer,
            )

        if enable_timeout_worker:
            # Use settings for batch check interval (default 10s)
            check_interval = getattr(settings, "batch_check_interval_seconds", 10.0)
            self._timeout_worker = BatchTimeoutWorker(
                redis_client=redis_client,
                batch_aggregator=self._aggregator,
                check_interval=check_interval,
            )

        if enable_metrics_worker:
            self._metrics_worker = QueueMetricsWorker(
                redis_client=redis_client,
                update_interval=5.0,  # Update metrics every 5 seconds
            )

        self._running = False
        self._signal_handlers_installed = False

    @property
    def running(self) -> bool:
        """Check if manager is running."""
        return self._running

    def get_status(self) -> dict[str, Any]:
        """Get status of all workers.

        Returns:
            Dictionary with worker names and their stats
        """
        status: dict[str, Any] = {
            "running": self._running,
            "workers": {},
        }

        if self._detection_worker:
            status["workers"]["detection"] = self._detection_worker.stats.to_dict()

        if self._analysis_worker:
            status["workers"]["analysis"] = self._analysis_worker.stats.to_dict()

        if self._timeout_worker:
            status["workers"]["timeout"] = self._timeout_worker.stats.to_dict()

        if self._metrics_worker:
            status["workers"]["metrics"] = {"running": self._metrics_worker.running}

        return status

    async def start(self) -> None:
        """Start all enabled workers.

        Installs signal handlers for graceful shutdown.
        """
        if self._running:
            logger.warning("PipelineWorkerManager already running")
            return

        logger.info("Starting PipelineWorkerManager")
        self._running = True

        # Install signal handlers (only once)
        if not self._signal_handlers_installed:
            self._install_signal_handlers()

        # Start workers
        start_tasks = []
        if self._detection_worker:
            start_tasks.append(self._detection_worker.start())
        if self._analysis_worker:
            start_tasks.append(self._analysis_worker.start())
        if self._timeout_worker:
            start_tasks.append(self._timeout_worker.start())
        if self._metrics_worker:
            start_tasks.append(self._metrics_worker.start())

        if start_tasks:
            await asyncio.gather(*start_tasks)

        logger.info("PipelineWorkerManager started all workers")

    async def stop(self) -> None:
        """Stop all workers gracefully."""
        if not self._running:
            logger.debug("PipelineWorkerManager not running, nothing to stop")
            return

        logger.info("Stopping PipelineWorkerManager")
        self._running = False

        # Stop workers in parallel
        stop_tasks = []
        if self._detection_worker:
            stop_tasks.append(self._detection_worker.stop())
        if self._analysis_worker:
            stop_tasks.append(self._analysis_worker.stop())
        if self._timeout_worker:
            stop_tasks.append(self._timeout_worker.stop())
        if self._metrics_worker:
            stop_tasks.append(self._metrics_worker.stop())

        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)

        logger.info("PipelineWorkerManager stopped all workers")

    def _install_signal_handlers(self) -> None:
        """Install signal handlers for graceful shutdown.

        Note: Signal handlers only work in the main thread. If running in
        a background thread, signals will be handled by the main FastAPI process.
        """
        try:
            loop = asyncio.get_running_loop()

            def create_shutdown_handler(sig: signal.Signals) -> None:
                def handler() -> None:
                    logger.info(f"Received signal {sig.name}, initiating graceful shutdown")
                    asyncio.create_task(self.stop())

                loop.add_signal_handler(sig, handler)

            create_shutdown_handler(signal.SIGTERM)
            create_shutdown_handler(signal.SIGINT)
            self._signal_handlers_installed = True
            logger.debug("Signal handlers installed for SIGTERM and SIGINT")
        except (NotImplementedError, RuntimeError) as e:
            # Signal handlers not supported (e.g., Windows, not main thread)
            logger.debug(f"Could not install signal handlers: {e}")


# Global instance for singleton access
_pipeline_manager: PipelineWorkerManager | None = None


async def get_pipeline_manager(redis_client: RedisClient) -> PipelineWorkerManager:
    """Get or create the global pipeline worker manager.

    Args:
        redis_client: Redis client for queue operations

    Returns:
        PipelineWorkerManager singleton instance
    """
    global _pipeline_manager  # noqa: PLW0603

    if _pipeline_manager is None:
        _pipeline_manager = PipelineWorkerManager(redis_client=redis_client)

    return _pipeline_manager


async def stop_pipeline_manager() -> None:
    """Stop and cleanup the global pipeline worker manager."""
    global _pipeline_manager  # noqa: PLW0603

    if _pipeline_manager:
        await _pipeline_manager.stop()
        _pipeline_manager = None


if __name__ == "__main__":
    # Allow running workers as standalone process
    # Usage: python -m backend.services.pipeline_workers
    import sys

    async def main() -> None:
        """Run pipeline workers as standalone process."""
        from backend.core.database import init_db
        from backend.core.logging import setup_logging
        from backend.core.redis import init_redis

        setup_logging()
        logger.info("Starting pipeline workers as standalone process")

        try:
            await init_db()
            redis_client = await init_redis()

            manager = PipelineWorkerManager(redis_client=redis_client)
            await manager.start()

            # Wait indefinitely (signal handlers will trigger stop)
            while manager.running:
                await asyncio.sleep(1.0)

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            sys.exit(1)
        finally:
            await stop_pipeline_manager()
            from backend.core.database import close_db
            from backend.core.redis import close_redis

            await close_redis()
            await close_db()

    asyncio.run(main())
