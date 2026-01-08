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
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from backend.api.routes.system import record_stage_latency
from backend.api.schemas.queue import (
    AnalysisQueuePayload,
    DetectionQueuePayload,
    validate_analysis_payload,
    validate_detection_payload,
)
from backend.core.config import get_settings
from backend.core.constants import ANALYSIS_QUEUE, DETECTION_QUEUE
from backend.core.database import get_session
from backend.core.logging import get_logger, log_context
from backend.core.metrics import (
    observe_stage_duration,
    record_pipeline_error,
    record_pipeline_stage_latency,
    set_queue_depth,
)
from backend.core.redis import RedisClient
from backend.core.telemetry import add_span_attributes, get_tracer, record_exception
from backend.services.batch_aggregator import BatchAggregator
from backend.services.detector_client import DetectorClient, DetectorUnavailableError
from backend.services.nemotron_analyzer import NemotronAnalyzer
from backend.services.retry_handler import RetryConfig, RetryHandler
from backend.services.video_processor import VideoProcessor

logger = get_logger(__name__)

# OpenTelemetry tracer for pipeline stage instrumentation (NEM-1467)
# Returns a no-op tracer if OTEL is not enabled
tracer = get_tracer(__name__)


def categorize_exception(e: Exception, worker_name: str) -> str:
    """Categorize an exception into a specific error type for metrics.

    This provides fine-grained error tracking for observability, allowing
    operators to distinguish between connection issues, timeouts, and
    processing failures.

    Args:
        e: The exception to categorize
        worker_name: Name of the worker (e.g., "detection", "analysis", "timeout")

    Returns:
        Error type string suitable for metrics labels (e.g., "detection_connection_error")
    """
    # Connection-related errors (Redis, network)
    connection_error_types = (
        "ConnectionError",
        "ConnectionRefusedError",
        "ConnectionResetError",
        "BrokenPipeError",
        "OSError",
    )
    if type(e).__name__ in connection_error_types or (
        hasattr(e, "args") and e.args and "connect" in str(e.args[0]).lower()
    ):
        return f"{worker_name}_connection_error"

    # Timeout errors
    if isinstance(e, TimeoutError) or type(e).__name__ in (
        "TimeoutError",
        "TimeoutExpired",
        "asyncio.TimeoutError",
    ):
        return f"{worker_name}_timeout_error"

    # Memory/resource errors
    if isinstance(e, MemoryError):
        return f"{worker_name}_memory_error"

    # Validation/data errors
    if isinstance(e, (ValueError, TypeError, KeyError)):
        return f"{worker_name}_validation_error"

    # Redis-specific errors (check by module name)
    if type(e).__module__ and "redis" in type(e).__module__.lower():
        return f"{worker_name}_redis_error"

    # Default: generic processing error
    return f"{worker_name}_processing_error"


class WorkerState(Enum):
    """Worker lifecycle states."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass(slots=True)
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
        video_processor: VideoProcessor | None = None,
        retry_handler: RetryHandler | None = None,
        queue_name: str = DETECTION_QUEUE,
        poll_timeout: int = 5,
        stop_timeout: float = 10.0,
    ) -> None:
        """Initialize detection queue worker.

        Args:
            redis_client: Redis client for queue operations
            detector_client: Client for RT-DETRv2. If None, will be created.
            batch_aggregator: Aggregator for batching detections. If None, will be created.
            video_processor: Processor for video frame extraction. If None, will be created.
            retry_handler: Handler for retry logic and DLQ. If None, will be created.
            queue_name: Name of the Redis queue to consume from
            poll_timeout: Timeout in seconds for BLPOP (allows checking shutdown signal)
            stop_timeout: Timeout in seconds for graceful stop before force cancel
        """
        settings = get_settings()
        self._redis = redis_client
        self._detector = detector_client or DetectorClient()
        self._aggregator = batch_aggregator or BatchAggregator(redis_client=redis_client)
        self._video_processor = video_processor or VideoProcessor(
            output_dir=settings.video_thumbnails_dir
        )
        self._queue_name = queue_name
        self._poll_timeout = poll_timeout
        self._stop_timeout = stop_timeout

        # Retry handler for transient failures (detector unavailable, etc.)
        # Uses configurable retry settings with exponential backoff
        self._retry_handler = retry_handler or RetryHandler(
            redis_client=redis_client,
            config=RetryConfig(
                max_retries=3,
                base_delay_seconds=1.0,
                max_delay_seconds=30.0,
                exponential_base=2.0,
                jitter=True,
            ),
        )

        # Video processing settings
        self._video_frame_interval = settings.video_frame_interval_seconds
        self._video_max_frames = settings.video_max_frames

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
                    # Expected after cancel() - task cleanup completed successfully
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
                # Uses retry with exponential backoff for Redis connection failures
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
                # Categorize exception for fine-grained metrics
                error_type = categorize_exception(e, "detection")
                record_pipeline_error(error_type)
                logger.error(
                    f"Error in DetectionQueueWorker loop: {e}",
                    exc_info=True,
                    extra={"error_count": self._stats.errors, "error_type": error_type},
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

        Security: Validates the queue payload using Pydantic before processing
        to prevent malicious data from reaching the AI pipeline.

        Handles both image and video files. For videos, extracts frames
        and runs detection on each frame.

        When the detector is unavailable (DetectorUnavailableError), the retry
        handler will retry with exponential backoff. After max retries, the job
        is moved to the dead-letter queue (DLQ) for later inspection/replay.

        Args:
            item: Queue item with camera_id, file_path, timestamp, media_type
        """
        import time

        start_time = time.time()

        # Security: Validate payload using Pydantic schema
        try:
            validated: DetectionQueuePayload = validate_detection_payload(item)
            camera_id = validated.camera_id
            file_path = validated.file_path
            media_type = validated.media_type
            pipeline_start_time = validated.pipeline_start_time
        except ValueError as e:
            self._stats.errors += 1
            record_pipeline_error("invalid_detection_payload")
            logger.error(
                f"SECURITY: Rejecting invalid detection queue payload: {e}",
                extra={
                    "raw_item": str(item)[:500],  # Truncate to prevent log injection
                    "error": str(e),
                },
            )
            return

        # Use log_context to enrich all logs within this scope with consistent context
        # This ensures camera_id, file_path, and media_type are included in all logs
        # OpenTelemetry span for detection processing (NEM-1467)
        with (
            log_context(camera_id=camera_id, file_path=file_path, media_type=media_type),
            tracer.start_as_current_span("detection_processing"),
        ):
            add_span_attributes(
                camera_id=camera_id,
                file_path=file_path,
                media_type=media_type,
                pipeline_stage="detection",
            )
            logger.debug(f"Processing detection item: {file_path}")

            try:
                if media_type == "video":
                    await self._process_video_detection(
                        camera_id, file_path, item, pipeline_start_time
                    )
                else:
                    await self._process_image_detection(
                        camera_id, file_path, item, pipeline_start_time
                    )

                self._stats.items_processed += 1
                self._stats.last_processed_at = time.time()

                # Record detect stage duration (Prometheus + in-memory tracker)
                duration = time.time() - start_time
                observe_stage_duration("detect", duration)
                # Record to in-memory tracker for /api/system/pipeline-latency
                record_pipeline_stage_latency("detect_to_batch", duration * 1000)
                # Record to Redis for /api/system/telemetry
                await record_stage_latency(self._redis, "detect", duration * 1000)

            except DetectorUnavailableError as e:
                # This is expected when detector is down and retries exhausted
                # The retry handler already moved the job to DLQ
                self._stats.errors += 1
                record_exception(e)
                logger.warning(f"Detection unavailable, job sent to DLQ: {e}")
                # Don't record as generic error - already recorded by retry handler

            except Exception as e:
                self._stats.errors += 1
                record_pipeline_error("detection_processing_error")
                record_exception(e)
                logger.error(
                    f"Failed to process detection item: {e}",
                    exc_info=True,
                )

    async def _process_image_detection(
        self,
        camera_id: str,
        file_path: str,
        job_data: dict[str, Any],
        pipeline_start_time: str | None = None,
    ) -> None:
        """Process a single image file for object detection.

        Uses retry handler to handle transient failures (detector unavailable).
        After max retries, the job is moved to the dead-letter queue.

        Args:
            camera_id: Camera identifier
            file_path: Path to the image file
            job_data: Original job data for DLQ tracking
            pipeline_start_time: ISO timestamp when the file was first detected
                (for total pipeline latency tracking)
        """

        async def _detect_with_session() -> list[Any]:
            """Inner function to perform detection with database session."""
            async with get_session() as session:
                return await self._detector.detect_objects(
                    image_path=file_path,
                    camera_id=camera_id,
                    session=session,
                )

        # Use retry handler to handle DetectorUnavailableError
        result = await self._retry_handler.with_retry(
            operation=_detect_with_session,
            job_data=job_data,
            queue_name=self._queue_name,
        )

        if not result.success:
            # All retries exhausted - job moved to DLQ
            logger.warning(
                f"Detection failed after {result.attempts} attempts for {file_path}, "
                f"moved to DLQ: {result.moved_to_dlq}",
                extra={
                    "camera_id": camera_id,
                    "file_path": file_path,
                    "attempts": result.attempts,
                    "moved_to_dlq": result.moved_to_dlq,
                    "error": result.error,
                },
            )
            record_pipeline_error("detection_max_retries_exceeded")
            # Re-raise to signal failure to caller
            raise DetectorUnavailableError(
                f"Detection failed after {result.attempts} retries: {result.error}"
            )

        detections = result.result or []

        # Add detections to batch
        for detection in detections:
            await self._aggregator.add_detection(
                camera_id=camera_id,
                detection_id=detection.id,  # Pass int directly (normalized in add_detection)
                _file_path=file_path,
                confidence=detection.confidence,
                object_type=detection.object_type,
                pipeline_start_time=pipeline_start_time,
            )

        logger.debug(
            f"Processed {len(detections)} detections from image {file_path}",
            extra={
                "camera_id": camera_id,
                "detection_count": len(detections),
                "items_processed": self._stats.items_processed,
                "retry_attempts": result.attempts,
            },
        )

    async def _process_video_detection(
        self,
        camera_id: str,
        video_path: str,
        job_data: dict[str, Any],
        pipeline_start_time: str | None = None,
    ) -> None:
        """Process a video file by extracting frames and running detection on each.

        Extracts frames at configured intervals, runs object detection on each frame,
        then cleans up the extracted frames.

        Uses retry handler for transient detector failures. If all retries fail,
        the video job is moved to DLQ.

        Args:
            camera_id: Camera identifier
            video_path: Path to the video file
            job_data: Original job data for DLQ tracking
            pipeline_start_time: ISO timestamp when the file was first detected
                (for total pipeline latency tracking)
        """
        logger.info(
            f"Processing video for detection: {video_path}",
            extra={"camera_id": camera_id, "video_path": video_path},
        )

        # Extract frames from video using optimized batch method (NEM-1329)
        # Uses single FFmpeg invocation instead of multiple calls per frame
        frame_paths = await self._video_processor.extract_frames_for_detection_batch(
            video_path=video_path,
            interval_seconds=self._video_frame_interval,
            max_frames=self._video_max_frames,
        )

        if not frame_paths:
            logger.warning(
                f"No frames extracted from video: {video_path}",
                extra={"camera_id": camera_id, "video_path": video_path},
            )
            return

        total_detections = 0
        detector_failed = False

        try:
            # Get video metadata for storing with detections
            video_metadata = await self._video_processor.get_video_metadata(video_path)

            # Process each extracted frame
            async with get_session() as session:
                for frame_path in frame_paths:
                    try:
                        # Capture frame_path in a closure to avoid loop variable binding issue
                        current_frame = frame_path

                        async def _detect_frame(
                            fp: str = current_frame,
                        ) -> list[Any]:
                            """Inner function for detection with retry support."""
                            return await self._detector.detect_objects(
                                image_path=fp,
                                camera_id=camera_id,
                                session=session,
                                video_path=video_path,
                                video_metadata=video_metadata,
                            )

                        # Use retry handler for each frame
                        result = await self._retry_handler.with_retry(
                            operation=_detect_frame,
                            job_data=job_data,  # Use video job data for DLQ
                            queue_name=self._queue_name,
                        )

                        if not result.success:
                            # Detector is down - fail the entire video job
                            logger.warning(
                                f"Detector unavailable during video processing: {video_path}",
                                extra={
                                    "camera_id": camera_id,
                                    "video_path": video_path,
                                    "frame_path": frame_path,
                                    "attempts": result.attempts,
                                    "moved_to_dlq": result.moved_to_dlq,
                                },
                            )
                            detector_failed = True
                            break

                        detections = result.result or []

                        # Add detections to batch
                        for detection in detections:
                            await self._aggregator.add_detection(
                                camera_id=camera_id,
                                detection_id=detection.id,  # Pass int directly (normalized in add_detection)
                                _file_path=video_path,  # Use video path, not frame
                                confidence=detection.confidence,
                                object_type=detection.object_type,
                                pipeline_start_time=pipeline_start_time,
                            )

                        total_detections += len(detections)

                    except DetectorUnavailableError:
                        # Retry handler already moved to DLQ
                        detector_failed = True
                        break
                    except Exception as e:
                        logger.warning(
                            f"Failed to process frame {frame_path}: {e}",
                            extra={"camera_id": camera_id, "frame_path": frame_path},
                        )
                        continue

        finally:
            # Clean up extracted frames
            self._video_processor.cleanup_extracted_frames(video_path)

        if detector_failed:
            raise DetectorUnavailableError(
                f"Detector unavailable during video processing: {video_path}"
            )

        logger.info(
            f"Processed video {video_path}: {total_detections} detections "
            f"from {len(frame_paths)} frames",
            extra={
                "camera_id": camera_id,
                "video_path": video_path,
                "frame_count": len(frame_paths),
                "detection_count": total_detections,
            },
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
        queue_name: str = ANALYSIS_QUEUE,
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
                    # Expected after cancel() - task cleanup completed successfully
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
                # Uses retry with exponential backoff for Redis connection failures
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
                # Categorize exception for fine-grained metrics
                error_type = categorize_exception(e, "analysis")
                record_pipeline_error(error_type)
                logger.error(
                    f"Error in AnalysisQueueWorker loop: {e}",
                    exc_info=True,
                    extra={"error_count": self._stats.errors, "error_type": error_type},
                )
                await asyncio.sleep(1.0)
                self._stats.state = WorkerState.RUNNING

        logger.info(
            "AnalysisQueueWorker loop exited",
            extra={"items_processed": self._stats.items_processed},
        )

    async def _process_analysis_item(self, item: dict[str, Any]) -> None:
        """Process a single analysis queue item.

        Security: Validates the queue payload using Pydantic before processing
        to prevent malicious data from reaching the LLM analyzer.

        Args:
            item: Queue item with batch_id, camera_id, detection_ids
        """
        import time

        start_time = time.time()

        # Security: Validate payload using Pydantic schema
        try:
            validated: AnalysisQueuePayload = validate_analysis_payload(item)
            batch_id = validated.batch_id
            camera_id = validated.camera_id
            detection_ids = validated.detection_ids
            pipeline_start_time = validated.pipeline_start_time
        except ValueError as e:
            self._stats.errors += 1
            record_pipeline_error("invalid_analysis_payload")
            logger.error(
                f"SECURITY: Rejecting invalid analysis queue payload: {e}",
                extra={
                    "raw_item": str(item)[:500],  # Truncate to prevent log injection
                    "error": str(e),
                },
            )
            return

        # Use log_context to enrich all logs within this scope with batch context
        # This ensures batch_id, camera_id are included in all logs including downstream calls
        # OpenTelemetry span for analysis processing (NEM-1467)
        with (
            log_context(batch_id=batch_id, camera_id=camera_id, operation="analysis"),
            tracer.start_as_current_span("analysis_processing"),
        ):
            # Build span attributes, excluding None values
            span_attrs: dict[str, str | int | float | bool] = {
                "batch_id": batch_id,
                "detection_count": len(detection_ids) if detection_ids else 0,
                "pipeline_stage": "analysis",
            }
            if camera_id is not None:
                span_attrs["camera_id"] = camera_id
            add_span_attributes(**span_attrs)
            logger.info(f"Processing analysis for batch {batch_id}")

            try:
                # Run LLM analysis - pass camera_id and detection_ids from queue payload
                # This avoids the need to read batch metadata from Redis (which is deleted after close_batch)
                event = await self._analyzer.analyze_batch(
                    batch_id=batch_id,
                    camera_id=camera_id,
                    detection_ids=detection_ids,
                )

                self._stats.items_processed += 1
                self._stats.last_processed_at = time.time()

                # Record analyze stage duration (Prometheus metrics are recorded in analyzer)
                duration = time.time() - start_time
                # Record to in-memory tracker for /api/system/pipeline-latency
                record_pipeline_stage_latency("batch_to_analyze", duration * 1000)
                # Record to Redis for /api/system/telemetry
                await record_stage_latency(self._redis, "analyze", duration * 1000)

                # Record total pipeline latency (from file detection to event creation)
                if pipeline_start_time:
                    try:
                        # Parse the ISO timestamp (supports both with and without timezone)
                        start_dt = datetime.fromisoformat(
                            pipeline_start_time.replace("Z", "+00:00")
                        )
                        # Make start_dt timezone-aware if it isn't already
                        if start_dt.tzinfo is None:
                            start_dt = start_dt.replace(tzinfo=UTC)
                        total_duration_ms = (datetime.now(UTC) - start_dt).total_seconds() * 1000
                        record_pipeline_stage_latency("total_pipeline", total_duration_ms)
                        logger.debug(
                            f"Total pipeline latency: {total_duration_ms:.1f}ms",
                            extra={
                                "total_pipeline_ms": total_duration_ms,
                                "pipeline_start_time": pipeline_start_time,
                            },
                        )
                    except (ValueError, TypeError) as e:
                        logger.warning(
                            f"Failed to parse pipeline_start_time '{pipeline_start_time}': {e}",
                            extra={"pipeline_start_time": pipeline_start_time},
                        )

                logger.info(
                    f"Created event {event.id}: risk_score={event.risk_score}",
                    extra={
                        "event_id": event.id,
                        "risk_score": event.risk_score,
                        "items_processed": self._stats.items_processed,
                    },
                )

            except ValueError as e:
                # Batch not found or no detections - log warning but don't count as error
                record_exception(e)
                logger.warning(f"Skipping batch: {e}")
            except Exception as e:
                self._stats.errors += 1
                record_pipeline_error("analysis_batch_error")
                record_exception(e)
                logger.error(
                    f"Failed to analyze batch: {e}",
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
                    # Expected after cancel() - task cleanup completed successfully
                    pass
            self._task = None

        self._stats.state = WorkerState.STOPPED
        logger.info("BatchTimeoutWorker stopped")

    async def _run_loop(self) -> None:
        """Main processing loop for the batch timeout worker.

        Uses elapsed-time-aware sleeping to maintain consistent check intervals.
        If processing takes longer than the interval, the next check runs immediately.
        """
        import time

        logger.info("BatchTimeoutWorker loop started")

        while self._running:
            try:
                start_time = time.time()

                # Check for batch timeouts FIRST (before sleeping)
                # This catches batches that may have timed out during startup
                # or during the previous sleep interval
                closed_batches = await self._aggregator.check_batch_timeouts()

                if closed_batches:
                    self._stats.items_processed += len(closed_batches)
                    self._stats.last_processed_at = time.time()

                    # Record batch stage duration (Prometheus + in-memory tracker + Redis)
                    duration = time.time() - start_time
                    observe_stage_duration("batch", duration)
                    # Record to in-memory tracker for /api/system/pipeline-latency
                    record_pipeline_stage_latency("detect_to_batch", duration * 1000)
                    # Record to Redis for /api/system/telemetry
                    await record_stage_latency(self._redis, "batch", duration * 1000)

                    logger.info(
                        f"Closed {len(closed_batches)} timed-out batches",
                        extra={
                            "batch_count": len(closed_batches),
                            "batch_ids": closed_batches,
                        },
                    )

                # Calculate remaining sleep time to maintain consistent check interval
                # This prevents timing drift when check_batch_timeouts() takes variable time
                elapsed = time.time() - start_time
                sleep_time = max(0.0, self._check_interval - elapsed)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                logger.info("BatchTimeoutWorker loop cancelled")
                break
            except Exception as e:
                self._stats.errors += 1
                self._stats.state = WorkerState.ERROR
                # Categorize exception for fine-grained metrics
                error_type = categorize_exception(e, "batch_timeout")
                record_pipeline_error(error_type)
                logger.error(
                    f"Error in BatchTimeoutWorker loop: {e}",
                    exc_info=True,
                    extra={"error_count": self._stats.errors, "error_type": error_type},
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
        stop_timeout: float = 5.0,
    ) -> None:
        """Initialize queue metrics worker.

        Args:
            redis_client: Redis client for queue length queries
            update_interval: How often to update metrics (seconds)
            stop_timeout: How long to wait for graceful shutdown (seconds)
        """
        self._redis = redis_client
        self._update_interval = update_interval
        self._stop_timeout = stop_timeout
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
                await asyncio.wait_for(self._task, timeout=self._stop_timeout)
            except TimeoutError:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    # Expected after cancel() - task cleanup completed successfully
                    pass
            self._task = None

        logger.info("QueueMetricsWorker stopped")

    async def _run_loop(self) -> None:
        """Main loop for updating queue metrics."""
        logger.info("QueueMetricsWorker loop started")

        while self._running:
            try:
                # Get queue depths from Redis with retry for connection failures
                detection_depth = await self._redis.get_queue_length(DETECTION_QUEUE)
                analysis_depth = await self._redis.get_queue_length(ANALYSIS_QUEUE)

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
        worker_stop_timeout: float | None = None,
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
            worker_stop_timeout: Override stop timeout for all workers (useful for tests).
                If None, workers use their default timeouts (10-30s).
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

        # Store stop timeout for workers (None means use default)
        self._worker_stop_timeout = worker_stop_timeout

        if enable_detection_worker:
            if worker_stop_timeout is not None:
                self._detection_worker = DetectionQueueWorker(
                    redis_client=redis_client,
                    detector_client=detector_client,
                    batch_aggregator=self._aggregator,
                    stop_timeout=worker_stop_timeout,
                )
            else:
                self._detection_worker = DetectionQueueWorker(
                    redis_client=redis_client,
                    detector_client=detector_client,
                    batch_aggregator=self._aggregator,
                )

        if enable_analysis_worker:
            if worker_stop_timeout is not None:
                self._analysis_worker = AnalysisQueueWorker(
                    redis_client=redis_client,
                    analyzer=analyzer,
                    stop_timeout=worker_stop_timeout,
                )
            else:
                self._analysis_worker = AnalysisQueueWorker(
                    redis_client=redis_client,
                    analyzer=analyzer,
                )

        if enable_timeout_worker:
            # Use settings for batch check interval (default 5s for reduced latency)
            check_interval = settings.batch_check_interval_seconds
            if worker_stop_timeout is not None:
                self._timeout_worker = BatchTimeoutWorker(
                    redis_client=redis_client,
                    batch_aggregator=self._aggregator,
                    check_interval=check_interval,
                    stop_timeout=worker_stop_timeout,
                )
            else:
                self._timeout_worker = BatchTimeoutWorker(
                    redis_client=redis_client,
                    batch_aggregator=self._aggregator,
                    check_interval=check_interval,
                )

        if enable_metrics_worker:
            if worker_stop_timeout is not None:
                self._metrics_worker = QueueMetricsWorker(
                    redis_client=redis_client,
                    update_interval=5.0,  # Update metrics every 5 seconds
                    stop_timeout=worker_stop_timeout,
                )
            else:
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
        Uses asyncio.TaskGroup for structured concurrency - if any worker
        fails to start, all other starting tasks are cancelled automatically.

        Raises:
            ExceptionGroup: If one or more workers fail to start.
        """
        if self._running:
            logger.warning("PipelineWorkerManager already running")
            return

        logger.info("Starting PipelineWorkerManager")
        self._running = True

        # Install signal handlers (only once)
        if not self._signal_handlers_installed:
            self._install_signal_handlers()

        # Start workers using TaskGroup for structured concurrency
        # If any worker fails to start, all others are cancelled automatically
        async with asyncio.TaskGroup() as tg:
            if self._detection_worker:
                tg.create_task(self._detection_worker.start())
            if self._analysis_worker:
                tg.create_task(self._analysis_worker.start())
            if self._timeout_worker:
                tg.create_task(self._timeout_worker.start())
            if self._metrics_worker:
                tg.create_task(self._metrics_worker.start())

        logger.info("PipelineWorkerManager started all workers")

    async def stop(self) -> None:
        """Stop all workers gracefully.

        Uses asyncio.TaskGroup for structured concurrency. If any worker fails
        to stop, exceptions are logged but all workers are still given a chance
        to shut down. The ExceptionGroup is caught and logged rather than
        propagated, since shutdown should be best-effort.
        """
        if not self._running:
            logger.debug("PipelineWorkerManager not running, nothing to stop")
            return

        logger.info("Stopping PipelineWorkerManager")
        self._running = False

        # Stop workers in parallel using TaskGroup for structured concurrency
        # Catch ExceptionGroup for best-effort shutdown (equivalent to return_exceptions=True)
        try:
            async with asyncio.TaskGroup() as tg:
                if self._detection_worker:
                    tg.create_task(self._detection_worker.stop())
                if self._analysis_worker:
                    tg.create_task(self._analysis_worker.stop())
                if self._timeout_worker:
                    tg.create_task(self._timeout_worker.stop())
                if self._metrics_worker:
                    tg.create_task(self._metrics_worker.stop())
        except ExceptionGroup as eg:
            # Log errors but continue - shutdown should be best-effort
            # This is equivalent to the previous return_exceptions=True behavior
            for exc in eg.exceptions:
                logger.error(
                    f"Error stopping worker during shutdown: {exc}",
                    exc_info=exc,
                )

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
_pipeline_manager_lock: asyncio.Lock | None = None
# Thread lock to protect initialization of _pipeline_manager_lock itself
_pipeline_init_lock = __import__("threading").Lock()


def _get_pipeline_manager_lock() -> asyncio.Lock:
    """Get the pipeline manager initialization lock (lazy initialization).

    This ensures the lock is created in a thread-safe manner and in the
    correct event loop context. Uses a threading lock to protect the
    initial creation of the asyncio lock, preventing race conditions
    when multiple coroutines attempt to initialize concurrently.

    Must be called from within an async context.

    Returns:
        asyncio.Lock for pipeline manager initialization
    """
    global _pipeline_manager_lock  # noqa: PLW0603
    if _pipeline_manager_lock is None:
        with _pipeline_init_lock:
            # Double-check after acquiring thread lock
            if _pipeline_manager_lock is None:
                _pipeline_manager_lock = asyncio.Lock()
    return _pipeline_manager_lock


async def get_pipeline_manager(redis_client: RedisClient) -> PipelineWorkerManager:
    """Get or create the global pipeline worker manager.

    This function is thread-safe and handles concurrent initialization
    attempts using an async lock to prevent race conditions.

    Args:
        redis_client: Redis client for queue operations

    Returns:
        PipelineWorkerManager singleton instance
    """
    global _pipeline_manager  # noqa: PLW0603

    # Fast path: manager already exists
    if _pipeline_manager is not None:
        return _pipeline_manager

    # Slow path: need to initialize with lock
    lock = _get_pipeline_manager_lock()
    async with lock:
        # Double-check after acquiring lock (another coroutine may have initialized)
        if _pipeline_manager is None:
            _pipeline_manager = PipelineWorkerManager(redis_client=redis_client)
            logger.info("Global pipeline worker manager initialized")

    return _pipeline_manager


async def stop_pipeline_manager() -> None:
    """Stop and cleanup the global pipeline worker manager.

    This function is thread-safe and handles concurrent stop attempts.
    """
    global _pipeline_manager  # noqa: PLW0603

    lock = _get_pipeline_manager_lock()
    async with lock:
        if _pipeline_manager:
            await _pipeline_manager.stop()
            _pipeline_manager = None
            logger.info("Global pipeline worker manager stopped")


def reset_pipeline_manager_state() -> None:
    """Reset the global pipeline manager state for testing purposes.

    This function is NOT thread-safe and should only be used in test
    fixtures to ensure clean state between tests. It resets both the
    manager instance and the asyncio lock.

    Warning: Only use this in test teardown, never in production code.
    """
    global _pipeline_manager, _pipeline_manager_lock  # noqa: PLW0603
    _pipeline_manager = None
    _pipeline_manager_lock = None


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
