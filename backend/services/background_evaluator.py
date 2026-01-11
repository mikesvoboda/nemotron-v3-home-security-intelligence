"""Background evaluator service for AI audit evaluation when GPU is idle.

This service runs AI audit evaluations automatically in the background when
the GPU is idle, rather than requiring manual "Run Evaluation" clicks.
Event detection pipeline always takes priority.

Key features:
- Monitors GPU utilization and only processes when idle
- Detection and analysis queues take priority over evaluation
- Higher risk events are evaluated first (priority queue)
- Configurable idle threshold and duration requirements
- Job tracking with progress reporting and cancellation support

Processing flow:
1. Check if detection/analysis queues are empty
2. Check if GPU has been idle for required duration
3. Dequeue highest priority event from evaluation queue
4. Run full AI audit evaluation (4 LLM calls)
5. Repeat or wait based on queue status
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from typing import TYPE_CHECKING

from sqlalchemy import select

from backend.core.database import get_session
from backend.core.logging import get_logger
from backend.core.redis import RedisClient
from backend.models.event import Event
from backend.models.event_audit import EventAudit
from backend.services.job_status import JobStatusService, get_job_status_service

if TYPE_CHECKING:
    from backend.services.evaluation_queue import EvaluationQueue
    from backend.services.gpu_monitor import GPUMonitor
    from backend.services.pipeline_quality_audit_service import PipelineQualityAuditService

# Import JobTracker at runtime since it's used in function signatures (not just type hints)
from backend.services.job_tracker import JobTracker

logger = get_logger(__name__)


class BackgroundEvaluator:
    """Background service that runs AI audit evaluations when GPU is idle.

    This service automatically processes pending AI audit evaluations
    when the GPU is idle and no detection/analysis work is pending.
    Event detection pipeline always takes priority.

    Configuration:
        gpu_idle_threshold: GPU utilization percentage below which GPU is idle (default: 20%)
        idle_duration_required: Seconds GPU must be idle before processing (default: 5s)
        poll_interval: How often to check for work (default: 5s)
        enabled: Whether background evaluation is enabled (default: True)
        job_tracker: Optional JobTracker for reporting progress and supporting cancellation
    """

    # Queue names for priority checking
    DETECTION_QUEUE = "detection_queue"
    ANALYSIS_QUEUE = "analysis_queue"

    # Job type identifier for tracking
    JOB_TYPE = "evaluation"

    def __init__(
        self,
        redis_client: RedisClient,
        gpu_monitor: GPUMonitor,
        evaluation_queue: EvaluationQueue,
        audit_service: PipelineQualityAuditService,
        gpu_idle_threshold: int = 20,
        idle_duration_required: int = 5,
        poll_interval: float = 5.0,
        enabled: bool = True,
        job_tracker: JobTracker | None = None,
    ) -> None:
        """Initialize the background evaluator.

        Args:
            redis_client: Redis client for queue operations.
            gpu_monitor: GPU monitor for utilization checks.
            evaluation_queue: Queue of events pending evaluation.
            audit_service: Service for running AI audit evaluations.
            gpu_idle_threshold: GPU utilization % below which GPU is idle.
            idle_duration_required: Seconds GPU must be idle before processing.
            poll_interval: How often to check for work (seconds).
            enabled: Whether background evaluation is enabled.
            job_tracker: Optional job tracker for progress reporting.
        """
        self._redis = redis_client
        self._gpu_monitor = gpu_monitor
        self._evaluation_queue = evaluation_queue
        self._audit_service = audit_service
        self._job_tracker = job_tracker

        # Configuration
        self.gpu_idle_threshold = gpu_idle_threshold
        self.idle_duration_required = idle_duration_required
        self.poll_interval = poll_interval
        self.enabled = enabled

        # State tracking
        self.running = False
        self._task: asyncio.Task | None = None
        self._idle_since: float | None = None
        self._current_job_id: str | None = None

        # Job status service for tracking evaluation jobs
        self._job_status_service: JobStatusService | None = None

    def _get_job_status_service(self) -> JobStatusService:
        """Get or create the job status service.

        Returns:
            JobStatusService instance.
        """
        if self._job_status_service is None:
            self._job_status_service = get_job_status_service(self._redis)
        return self._job_status_service

    async def is_gpu_idle(self) -> bool:
        """Check if GPU utilization is below the idle threshold.

        Returns:
            True if GPU is idle (utilization <= threshold), False otherwise.
        """
        try:
            stats = await self._gpu_monitor.get_current_stats_async()
            utilization = stats.get("gpu_utilization")

            if utilization is None:
                logger.debug("GPU utilization data unavailable, assuming not idle")
                return False

            is_idle: bool = utilization <= self.gpu_idle_threshold
            logger.debug(
                f"GPU utilization: {utilization}%, threshold: {self.gpu_idle_threshold}%, idle: {is_idle}"
            )
            return is_idle

        except Exception as e:
            logger.warning(f"Failed to check GPU idle status: {e}")
            return False

    async def _are_queues_empty(self) -> bool:
        """Check if detection and analysis queues are empty.

        Returns:
            True if both queues are empty, False otherwise.
        """
        try:
            detection_len = await self._redis.llen(self.DETECTION_QUEUE)
            if detection_len > 0:
                logger.debug(f"Detection queue has {detection_len} items, skipping evaluation")
                return False

            analysis_len = await self._redis.llen(self.ANALYSIS_QUEUE)
            if analysis_len > 0:
                logger.debug(f"Analysis queue has {analysis_len} items, skipping evaluation")
                return False

            return True

        except Exception as e:
            logger.warning(f"Failed to check queue status: {e}")
            return False

    async def can_process_evaluation(self) -> bool:
        """Check if conditions are met to process an evaluation.

        Conditions:
        1. Detection and analysis queues must be empty
        2. GPU must be idle (below threshold)

        Returns:
            True if evaluation can proceed, False otherwise.
        """
        # Check queues first (quick check)
        if not await self._are_queues_empty():
            return False

        # Check GPU idle status
        return await self.is_gpu_idle()

    def _is_job_cancelled(self, job_id: str | None) -> bool:
        """Check if the current job has been cancelled.

        Args:
            job_id: The job ID to check, or None if no job tracking.

        Returns:
            True if the job was cancelled, False otherwise.
        """
        if job_id is None or self._job_tracker is None:
            return False
        return self._job_tracker.is_cancelled(job_id)

    async def process_one(self) -> bool:  # noqa: PLR0911, PLR0912
        """Process a single evaluation from the queue.

        Dequeues the highest priority event and runs full AI audit evaluation.
<<<<<<< HEAD
        Tracks job status in Redis for monitoring.
=======
        Reports progress via JobTracker if configured.

        Note: Complexity warnings (PLR0911, PLR0912) are suppressed because the
        multiple returns and branches are necessary for proper job tracking,
        progress reporting, and cancellation checking at each stage.
>>>>>>> 79a0e149b (feat: implement 4 parallel tasks - AlertsPage, FeedbackUI, JobTracking, OrphanedCleanup)

        Returns:
            True if an evaluation was processed, False if queue was empty.
        """
        # Dequeue highest priority event
        event_id = await self._evaluation_queue.dequeue()
        if event_id is None:
            return False

        # Create job for tracking this evaluation
        job_id: str | None = None
        if self._job_tracker is not None:
            job_id = self._job_tracker.create_job(self.JOB_TYPE)
            self._current_job_id = job_id
            self._job_tracker.start_job(job_id, message=f"Starting evaluation for event {event_id}")

        logger.info(
            f"Processing background evaluation for event {event_id}",
            extra={"event_id": event_id, "job_id": job_id},
        )

        # Start job tracking
        job_service = self._get_job_status_service()
        job_id = await job_service.start_job(
            job_id=f"evaluation-{event_id}",
            job_type="background_evaluation",
            metadata={"event_id": event_id},
        )

        try:
<<<<<<< HEAD
            # Update progress: starting
            await job_service.update_progress(job_id, 10, "Fetching event data")
=======
            # Check for cancellation before starting
            if self._is_job_cancelled(job_id):
                logger.info(
                    f"Evaluation cancelled for event {event_id}",
                    extra={"event_id": event_id, "job_id": job_id},
                )
                return True
>>>>>>> 79a0e149b (feat: implement 4 parallel tasks - AlertsPage, FeedbackUI, JobTracking, OrphanedCleanup)

            async with get_session() as session:
                # Update progress: fetching event (10%)
                if self._job_tracker is not None and job_id is not None:
                    self._job_tracker.update_progress(
                        job_id, 10, message=f"Fetching event {event_id}"
                    )

                # Fetch event
                result = await session.execute(select(Event).where(Event.id == event_id))
                event = result.scalar_one_or_none()

                if event is None:
                    logger.warning(
                        f"Event {event_id} not found in database, skipping evaluation",
                        extra={"event_id": event_id},
                    )
<<<<<<< HEAD
                    await job_service.fail_job(job_id, f"Event {event_id} not found")
                    return True  # Item was processed (removed from queue)

                # Update progress: event found
                await job_service.update_progress(job_id, 25, "Fetching audit record")
=======
                    if self._job_tracker is not None and job_id is not None:
                        self._job_tracker.complete_job(
                            job_id, result={"skipped": True, "reason": "event_not_found"}
                        )
                    return True  # Item was processed (removed from queue)

                # Check for cancellation
                if self._is_job_cancelled(job_id):
                    logger.info(
                        f"Evaluation cancelled for event {event_id}",
                        extra={"event_id": event_id, "job_id": job_id},
                    )
                    return True

                # Update progress: fetching audit record (20%)
                if self._job_tracker is not None and job_id is not None:
                    self._job_tracker.update_progress(
                        job_id, 20, message=f"Fetching audit record for event {event_id}"
                    )
>>>>>>> 79a0e149b (feat: implement 4 parallel tasks - AlertsPage, FeedbackUI, JobTracking, OrphanedCleanup)

                # Fetch existing audit record
                audit_result = await session.execute(
                    select(EventAudit).where(EventAudit.event_id == event_id)
                )
                audit = audit_result.scalar_one_or_none()

                if audit is None:
                    logger.warning(
                        f"No audit record for event {event_id}, skipping evaluation",
                        extra={"event_id": event_id},
                    )
<<<<<<< HEAD
                    await job_service.fail_job(job_id, f"No audit record for event {event_id}")
                    return True

                # Update progress: running evaluation
                await job_service.update_progress(job_id, 40, "Running AI evaluation")
=======
                    if self._job_tracker is not None and job_id is not None:
                        self._job_tracker.complete_job(
                            job_id, result={"skipped": True, "reason": "audit_not_found"}
                        )
                    return True

                # Check for cancellation before running evaluation
                if self._is_job_cancelled(job_id):
                    logger.info(
                        f"Evaluation cancelled for event {event_id}",
                        extra={"event_id": event_id, "job_id": job_id},
                    )
                    return True

                # Update progress: running evaluation (30%)
                if self._job_tracker is not None and job_id is not None:
                    self._job_tracker.update_progress(
                        job_id, 30, message=f"Running AI evaluation for event {event_id}"
                    )
>>>>>>> 79a0e149b (feat: implement 4 parallel tasks - AlertsPage, FeedbackUI, JobTracking, OrphanedCleanup)

                # Run full evaluation (4 LLM calls)
                await self._audit_service.run_full_evaluation(audit, event, session)

<<<<<<< HEAD
                # Update progress: complete
                await job_service.complete_job(
                    job_id,
                    result={
                        "event_id": event_id,
                        "overall_quality_score": audit.overall_quality_score,
                    },
                )
=======
                # Update progress: evaluation complete (90%)
                if self._job_tracker is not None and job_id is not None:
                    self._job_tracker.update_progress(
                        job_id, 90, message="Evaluation complete, finalizing"
                    )
>>>>>>> 79a0e149b (feat: implement 4 parallel tasks - AlertsPage, FeedbackUI, JobTracking, OrphanedCleanup)

                logger.info(
                    f"Completed background evaluation for event {event_id}",
                    extra={
                        "event_id": event_id,
                        "overall_quality_score": audit.overall_quality_score,
                        "job_id": job_id,
                    },
                )

                # Complete the job
                if self._job_tracker is not None and job_id is not None:
                    self._job_tracker.complete_job(
                        job_id,
                        result={
                            "event_id": event_id,
                            "overall_quality_score": audit.overall_quality_score,
                        },
                    )

                return True

        except Exception as e:
            logger.error(
                f"Failed to process evaluation for event {event_id}: {e}",
                extra={"event_id": event_id, "error": str(e), "job_id": job_id},
                exc_info=True,
            )
<<<<<<< HEAD
            # Mark job as failed
            await job_service.fail_job(job_id, str(e))
=======
            # Fail the job with error details
            if self._job_tracker is not None and job_id is not None:
                self._job_tracker.fail_job(job_id, str(e))
>>>>>>> 79a0e149b (feat: implement 4 parallel tasks - AlertsPage, FeedbackUI, JobTracking, OrphanedCleanup)
            # Re-queue the event for retry? For now, skip it
            return True  # Mark as processed to avoid infinite loop
        finally:
            self._current_job_id = None

    async def _run_loop(self) -> None:
        """Main processing loop that runs in the background."""
        logger.info("Background evaluator loop started")

        while self.running:
            try:
                # Check if we can process
                if self.enabled and await self.can_process_evaluation():
                    # Track idle duration
                    now = time.time()
                    if self._idle_since is None:
                        self._idle_since = now
                        logger.debug("GPU became idle, starting idle timer")

                    idle_duration = now - self._idle_since

                    if idle_duration >= self.idle_duration_required:
                        # Process one evaluation
                        processed = await self.process_one()
                        if processed:
                            logger.debug("Processed one evaluation, continuing loop")
                        else:
                            logger.debug("Evaluation queue is empty")
                    else:
                        logger.debug(
                            f"GPU idle for {idle_duration:.1f}s, "
                            f"waiting for {self.idle_duration_required}s"
                        )
                # Reset idle timer when not idle
                elif self._idle_since is not None:
                    logger.debug("GPU no longer idle, resetting timer")
                    self._idle_since = None

                # Wait before next check
                await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                logger.debug("Background evaluator loop cancelled")
                break
            except Exception as e:
                logger.error(
                    f"Error in background evaluator loop: {e}",
                    exc_info=True,
                )
                # Continue loop despite errors
                await asyncio.sleep(self.poll_interval)

        logger.info("Background evaluator loop stopped")

    async def start(self) -> None:
        """Start the background evaluator.

        This method is idempotent - calling it multiple times is safe.
        """
        if self.running:
            logger.debug("BackgroundEvaluator already running")
            return

        if not self.enabled:
            logger.info("BackgroundEvaluator is disabled, not starting")
            return

        logger.info("Starting background evaluator")
        self.running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Background evaluator started")

    async def stop(self) -> None:
        """Stop the background evaluator."""
        if not self.running:
            logger.debug("BackgroundEvaluator not running, nothing to stop")
            return

        logger.info("Stopping background evaluator")
        self.running = False

        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

        self._task = None
        self._idle_since = None
        logger.info("Background evaluator stopped")


# Singleton management
_background_evaluator: BackgroundEvaluator | None = None


def get_background_evaluator(
    redis_client: RedisClient,
    gpu_monitor: GPUMonitor,
    evaluation_queue: EvaluationQueue,
    audit_service: PipelineQualityAuditService,
    gpu_idle_threshold: int = 20,
    idle_duration_required: int = 5,
    poll_interval: float = 5.0,
    enabled: bool = True,
    job_tracker: JobTracker | None = None,
) -> BackgroundEvaluator:
    """Get or create the background evaluator singleton.

    Args:
        redis_client: Redis client for queue operations.
        gpu_monitor: GPU monitor for utilization checks.
        evaluation_queue: Queue of events pending evaluation.
        audit_service: Service for running AI audit evaluations.
        gpu_idle_threshold: GPU utilization % below which GPU is idle.
        idle_duration_required: Seconds GPU must be idle before processing.
        poll_interval: How often to check for work (seconds).
        enabled: Whether background evaluation is enabled.
        job_tracker: Optional job tracker for progress reporting.

    Returns:
        BackgroundEvaluator singleton instance.
    """
    global _background_evaluator  # noqa: PLW0603
    if _background_evaluator is None:
        _background_evaluator = BackgroundEvaluator(
            redis_client=redis_client,
            gpu_monitor=gpu_monitor,
            evaluation_queue=evaluation_queue,
            audit_service=audit_service,
            gpu_idle_threshold=gpu_idle_threshold,
            idle_duration_required=idle_duration_required,
            poll_interval=poll_interval,
            enabled=enabled,
            job_tracker=job_tracker,
        )
    return _background_evaluator


def reset_background_evaluator() -> None:
    """Reset the background evaluator singleton (for testing)."""
    global _background_evaluator  # noqa: PLW0603
    _background_evaluator = None
