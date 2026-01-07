"""Batch aggregator service for grouping detections before analysis.

This service aggregates detections from the same camera into time-based batches,
then pushes completed batches to the Nemotron analysis queue.

Batching Logic:
    - Create new batch when first detection arrives for a camera
    - Add subsequent detections within 90-second window
    - Close batch if:
        * 90 seconds elapsed from batch start (window timeout)
        * 30 seconds with no new detections (idle timeout)
    - On batch close: push to analysis_queue with batch_id, camera_id, detection_ids

Redis Keys (all keys have 1-hour TTL for orphan cleanup):
    - batch:{camera_id}:current - Current batch ID for camera
    - batch:{batch_id}:camera_id - Camera ID for batch
    - batch:{batch_id}:detections - Redis LIST of detection IDs (uses RPUSH for atomic append)
    - batch:{batch_id}:started_at - Batch start timestamp (float)
    - batch:{batch_id}:last_activity - Last activity timestamp (float)

Concurrency:
    Uses per-camera locks to prevent race conditions when multiple detections
    arrive for the same camera simultaneously. Global lock protects batch
    timeout checking and closing operations.

    For distributed environments (multiple backend instances), detection list
    updates use Redis RPUSH for atomic append operations, eliminating race
    conditions in the read-modify-write pattern.

Memory Pressure Backpressure (NEM-1727):
    When GPU memory pressure reaches CRITICAL levels, the batch aggregator can
    apply backpressure to reduce processing load. Use should_apply_backpressure()
    to check if backpressure should be applied before processing detections.
"""

import asyncio
import json
import time
import uuid
from collections import defaultdict
from typing import Any

from backend.core.config import get_settings
from backend.core.constants import ANALYSIS_QUEUE
from backend.core.logging import get_logger, sanitize_log_value
from backend.core.metrics import record_batch_max_reached
from backend.core.redis import QueueOverflowPolicy, RedisClient

logger = get_logger(__name__)

# Global GPU monitor reference for memory pressure checks
_gpu_monitor: Any = None


def set_gpu_monitor(monitor: Any) -> None:
    """Set the GPU monitor instance for memory pressure checks.

    This should be called during application startup to enable
    memory pressure backpressure in the batch aggregator.

    Args:
        monitor: GPUMonitor instance
    """
    global _gpu_monitor  # noqa: PLW0603
    _gpu_monitor = monitor
    logger.debug("GPU monitor set for batch aggregator backpressure")


async def get_memory_pressure_level() -> Any:
    """Get current GPU memory pressure level.

    Returns:
        MemoryPressureLevel enum value, or NORMAL if GPU monitor not available

    Note:
        This is a helper function that can be mocked in tests.
    """
    from backend.services.gpu_monitor import MemoryPressureLevel

    if _gpu_monitor is None:
        return MemoryPressureLevel.NORMAL

    try:
        return await _gpu_monitor.check_memory_pressure()
    except Exception as e:
        logger.debug(
            f"Failed to check memory pressure: {e}",
            extra={"error": str(e), "error_type": type(e).__name__},
        )
        return MemoryPressureLevel.NORMAL


class BatchAggregator:
    """Aggregates detections into time-based batches for analysis.

    This service manages the lifecycle of detection batches, including:
    - Creating new batches for cameras
    - Adding detections to active batches
    - Checking for and closing timed-out batches
    - Pushing completed batches to the analysis queue
    """

    # TTL for batch Redis keys (1 hour) - ensures orphan cleanup if service crashes
    BATCH_KEY_TTL_SECONDS = 3600

    def __init__(self, redis_client: RedisClient | None = None, analyzer: Any | None = None):
        """Initialize batch aggregator with Redis client.

        Args:
            redis_client: Redis client instance. If None, will be injected via dependency.
            analyzer: NemotronAnalyzer instance for fast path analysis. If None, will be created.
        """
        self._redis = redis_client
        self._analyzer = analyzer
        settings = get_settings()
        self._batch_window = settings.batch_window_seconds
        self._idle_timeout = settings.batch_idle_timeout_seconds
        self._analysis_queue = ANALYSIS_QUEUE
        self._fast_path_threshold = settings.fast_path_confidence_threshold
        self._fast_path_types = settings.fast_path_object_types
        self._batch_max_detections = settings.batch_max_detections

        # Per-camera locks to prevent race conditions when adding detections
        # Using defaultdict to lazily create locks for each camera
        self._camera_locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

        # Global lock for batch timeout checking and closing operations
        # Prevents race between check_batch_timeouts and close_batch
        self._batch_close_lock = asyncio.Lock()

        # Lock for the camera_locks dict itself to prevent race in lock creation
        self._locks_lock = asyncio.Lock()

    async def _get_camera_lock(self, camera_id: str) -> asyncio.Lock:
        """Get or create a lock for the specified camera.

        Thread-safe lock creation to prevent race conditions when
        multiple coroutines try to create locks for the same camera.

        Args:
            camera_id: Camera identifier

        Returns:
            asyncio.Lock for the specified camera
        """
        async with self._locks_lock:
            # defaultdict will create the lock if it doesn't exist
            return self._camera_locks[camera_id]

    async def _atomic_list_append(self, key: str, value: int, ttl: int) -> int:
        """Atomically append a value to a Redis list and refresh TTL.

        Uses Redis RPUSH for atomic append, eliminating race conditions
        in distributed environments.

        Args:
            key: Redis list key
            value: Value to append (will be converted to string)
            ttl: TTL in seconds to set on the key

        Returns:
            Length of the list after append
        """
        if not self._redis or not self._redis._client:
            raise RuntimeError("Redis client not initialized")

        client = self._redis._client
        # RPUSH is atomic - multiple processes can safely append
        length: int = await client.rpush(key, str(value))  # type: ignore[misc]
        # Refresh TTL
        await client.expire(key, ttl)
        return length

    async def _atomic_list_get_all(self, key: str) -> list[int]:
        """Get all values from a Redis list.

        Uses Redis LRANGE to retrieve all elements.

        Args:
            key: Redis list key

        Returns:
            List of detection IDs (integers)
        """
        if not self._redis or not self._redis._client:
            raise RuntimeError("Redis client not initialized")

        client = self._redis._client
        # LRANGE 0 -1 gets all elements
        items: list[str] = await client.lrange(key, 0, -1)  # type: ignore[misc]
        # Convert string values back to integers
        result = []
        for item in items:
            try:
                result.append(int(item))
            except (ValueError, TypeError):
                # Skip invalid entries
                logger.warning(f"Invalid detection ID in batch list: {sanitize_log_value(item)}")
        return result

    async def add_detection(
        self,
        camera_id: str,
        detection_id: int | str,
        _file_path: str,
        confidence: float | None = None,
        object_type: str | None = None,
        pipeline_start_time: str | None = None,
    ) -> str:
        """Add detection to batch for camera.

        Creates a new batch if none exists for the camera, or adds to existing batch.
        Updates the last_activity timestamp for the batch.

        If detection meets fast path criteria (confidence > threshold AND object_type in
        fast path list), immediately triggers analysis instead of batching.

        Uses atomic Redis RPUSH for detection list updates to prevent race conditions
        in distributed environments.

        Args:
            camera_id: Camera identifier
            detection_id: Detection identifier (int or string, normalized to int internally)
            _file_path: Path to the detection image file
            confidence: Detection confidence score (0.0-1.0)
            object_type: Detected object type (e.g., "person", "car")
            pipeline_start_time: ISO timestamp when the file was first detected
                (for total pipeline latency tracking). Only stored for the first
                detection in a batch.

        Returns:
            Batch ID that the detection was added to (or fast path batch ID)

        Raises:
            ValueError: If detection_id cannot be converted to int
            RuntimeError: If Redis client not initialized
        """
        if not self._redis:
            raise RuntimeError("Redis client not initialized")

        # Normalize detection_id to int for consistent storage
        # This handles both int IDs from the database and string IDs from legacy code
        try:
            detection_id_int: int = int(detection_id)
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"Invalid detection_id: {detection_id!r}. Detection IDs must be numeric."
            ) from e

        # Check if detection meets fast path criteria
        if self._should_use_fast_path(confidence, object_type):
            logger.info(
                f"Fast path triggered for detection {detection_id_int}: "
                f"confidence={confidence}, object_type={object_type}",
                extra={
                    "camera_id": camera_id,
                    "detection_id": detection_id_int,
                    "confidence": confidence,
                    "object_type": object_type,
                },
            )
            await self._process_fast_path(camera_id, detection_id_int)
            return f"fast_path_{detection_id_int}"

        # Acquire per-camera lock to prevent race conditions when multiple
        # detections arrive for the same camera simultaneously
        camera_lock = await self._get_camera_lock(camera_id)
        async with camera_lock:
            current_time = time.time()

            # Check for existing active batch for this camera
            # Uses retry with exponential backoff for Redis connection failures
            batch_key = f"batch:{camera_id}:current"
            batch_id = await self._redis.get(batch_key)

            # NEM-1726: Check if existing batch has reached max size limit
            if batch_id:
                detections_key = f"batch:{batch_id}:detections"
                current_size: int = await self._redis._client.llen(detections_key)  # type: ignore[misc,union-attr]

                if current_size >= self._batch_max_detections:
                    # Batch at max size - close it and create new batch
                    logger.info(
                        f"Batch {batch_id} reached max size {self._batch_max_detections}, closing",
                        extra={
                            "camera_id": camera_id,
                            "batch_id": batch_id,
                            "current_size": current_size,
                            "max_size": self._batch_max_detections,
                        },
                    )
                    record_batch_max_reached(camera_id)

                    # Close the current batch (releases camera lock temporarily)
                    # We need to release the lock before calling close_batch because
                    # close_batch acquires its own locks
                    await self._close_batch_for_size_limit(batch_id)

                    # Set batch_id to None so we create a new batch below
                    batch_id = None

            if not batch_id:
                # Create new batch
                batch_id = uuid.uuid4().hex
                logger.info(
                    f"Creating new batch {batch_id} for camera {camera_id}",
                    extra={"camera_id": camera_id, "batch_id": batch_id},
                )

                # Set batch metadata with TTL for orphan cleanup
                # Uses asyncio.gather to parallelize Redis SET operations for performance
                ttl = self.BATCH_KEY_TTL_SECONDS

                # Build list of Redis operations to execute in parallel
                redis_ops = [
                    self._redis.set(batch_key, batch_id, expire=ttl),
                    self._redis.set(f"batch:{batch_id}:camera_id", camera_id, expire=ttl),
                    self._redis.set(f"batch:{batch_id}:started_at", str(current_time), expire=ttl),
                    self._redis.set(
                        f"batch:{batch_id}:last_activity", str(current_time), expire=ttl
                    ),
                ]

                # Store pipeline_start_time only for the first detection in the batch
                # This captures when the first file in the batch was detected for total latency
                if pipeline_start_time:
                    redis_ops.append(
                        self._redis.set(
                            f"batch:{batch_id}:pipeline_start_time",
                            pipeline_start_time,
                            expire=ttl,
                        )
                    )

                # Use TaskGroup for structured concurrency (NEM-1656)
                # All Redis operations must succeed for batch to be valid.
                # TaskGroup automatically cancels remaining tasks if any fails.
                try:
                    async with asyncio.TaskGroup() as tg:
                        for redis_op in redis_ops:
                            tg.create_task(redis_op)
                except* Exception as eg:
                    # Log all errors from the ExceptionGroup
                    for i, exc in enumerate(eg.exceptions):
                        logger.error(
                            f"Redis operation {i} failed during batch creation",
                            extra={
                                "batch_id": batch_id,
                                "camera_id": camera_id,
                                "error": str(exc),
                            },
                        )
                    # Re-raise the first exception to maintain compatibility
                    raise eg.exceptions[0] from eg
                # Note: No need to initialize empty list - RPUSH creates it automatically

            # Add detection to batch using atomic RPUSH operation
            # This eliminates the race condition in read-modify-write pattern
            detections_key = f"batch:{batch_id}:detections"
            ttl = self.BATCH_KEY_TTL_SECONDS
            detection_count = await self._atomic_list_append(detections_key, detection_id_int, ttl)

            # Update last activity timestamp
            await self._redis.set(f"batch:{batch_id}:last_activity", str(current_time), expire=ttl)

            logger.debug(
                f"Added detection {detection_id_int} to batch {batch_id} "
                f"(camera: {camera_id}, total detections: {detection_count})",
                extra={
                    "camera_id": camera_id,
                    "batch_id": batch_id,
                    "detection_id": detection_id_int,
                    "detection_count": detection_count,
                },
            )

            return batch_id

    async def check_batch_timeouts(self) -> list[str]:  # noqa: PLR0912
        """Check all active batches for timeouts and close expired ones.

        A batch is closed if:
        - It has exceeded the batch window (90 seconds from start)
        - It has exceeded the idle timeout (30 seconds since last activity)

        Uses Redis pipelining to fetch all batch metadata in a single round trip,
        reducing network latency from O(N * 3) RTTs to O(2) RTTs where N is the
        number of active batches.

        Returns:
            List of batch IDs that were closed
        """
        if not self._redis:
            raise RuntimeError("Redis client not initialized")

        current_time = time.time()
        closed_batches: list[str] = []

        # Find all active batch keys (batch:{camera_id}:current)
        # Use SCAN instead of KEYS to avoid blocking Redis on large keyspaces
        redis_client = self._redis._client
        if redis_client is None:
            raise RuntimeError("Redis client connection not initialized")
        batch_keys: list[str] = []
        async for key in redis_client.scan_iter(match="batch:*:current", count=100):
            batch_keys.append(key)

        if not batch_keys:
            return closed_batches

        # Phase 1: Fetch all batch IDs in parallel using pipeline
        # This reduces N sequential GET calls to 1 pipeline round trip
        batch_id_pipe = redis_client.pipeline()
        for batch_key in batch_keys:
            batch_id_pipe.get(batch_key)
        batch_ids = await batch_id_pipe.execute()

        # Build list of valid batch IDs and their keys
        # Note: Redis pipeline returns bytes, so we must decode to str for f-string keys
        # Also: Values are JSON-serialized by RedisClient.set(), so we must deserialize
        valid_batches: list[tuple[str, str]] = []  # (batch_key, batch_id)
        for batch_key, batch_id in zip(batch_keys, batch_ids, strict=True):
            if batch_id:
                # Decode bytes to str
                batch_id_str = batch_id.decode() if isinstance(batch_id, bytes) else batch_id
                batch_key_str = batch_key.decode() if isinstance(batch_key, bytes) else batch_key
                # JSON-deserialize since RedisClient.set() JSON-serializes values
                # e.g., "\"abc123\"" -> "abc123"
                try:
                    batch_id_str = json.loads(batch_id_str)
                except (json.JSONDecodeError, TypeError):
                    pass  # Not JSON-encoded, use as-is
                valid_batches.append((batch_key_str, batch_id_str))

        if not valid_batches:
            return closed_batches

        # Phase 2: Fetch all batch metadata in parallel using pipeline
        # This reduces N * 2 sequential GET calls to 1 pipeline round trip
        metadata_pipe = redis_client.pipeline()
        for _batch_key, batch_id in valid_batches:
            metadata_pipe.get(f"batch:{batch_id}:started_at")
            metadata_pipe.get(f"batch:{batch_id}:last_activity")
        metadata_results = await metadata_pipe.execute()

        # Process results (2 results per batch: started_at, last_activity)
        # Note: Redis pipeline returns bytes values, decode for consistent handling
        for i, (batch_key, batch_id) in enumerate(valid_batches):
            try:
                started_at_raw = metadata_results[i * 2]
                last_activity_raw = metadata_results[i * 2 + 1]

                if not started_at_raw:
                    logger.warning(
                        f"Batch {sanitize_log_value(batch_id)} missing started_at timestamp, skipping"
                    )
                    continue

                # Decode bytes to str before float conversion
                started_at_str = (
                    started_at_raw.decode() if isinstance(started_at_raw, bytes) else started_at_raw
                )
                last_activity_str = (
                    last_activity_raw.decode()
                    if isinstance(last_activity_raw, bytes)
                    else last_activity_raw
                )
                # JSON-deserialize since RedisClient.set() JSON-serializes values
                try:
                    started_at_str = json.loads(started_at_str)
                except (json.JSONDecodeError, TypeError):
                    pass
                try:
                    last_activity_str = json.loads(last_activity_str) if last_activity_str else None
                except (json.JSONDecodeError, TypeError):
                    pass

                started_at = float(started_at_str)
                last_activity = float(last_activity_str) if last_activity_str else started_at

                # Check for timeouts
                window_elapsed = current_time - started_at
                idle_time = current_time - last_activity

                should_close = False
                close_reason = ""

                if window_elapsed >= self._batch_window:
                    should_close = True
                    close_reason = (
                        f"batch window exceeded ({window_elapsed:.1f}s >= {self._batch_window}s)"
                    )
                elif idle_time >= self._idle_timeout:
                    should_close = True
                    close_reason = (
                        f"idle timeout exceeded ({idle_time:.1f}s >= {self._idle_timeout}s)"
                    )

                if should_close:
                    # Fetch camera_id for logging (single call, not in critical path)
                    camera_id_for_log = await self._redis.get(f"batch:{batch_id}:camera_id")
                    logger.info(
                        f"Closing batch {batch_id}: {close_reason}",
                        extra={
                            "camera_id": camera_id_for_log,
                            "batch_id": batch_id,
                            "reason": close_reason,
                        },
                    )
                    await self.close_batch(batch_id)
                    closed_batches.append(batch_id)

            except Exception as e:
                logger.error(
                    f"Error checking timeout for batch key {batch_key}: {e}", exc_info=True
                )
                continue

        if closed_batches:
            logger.info(
                f"Closed {len(closed_batches)} timed-out batches",
                extra={"batch_count": len(closed_batches)},
            )

        return closed_batches

    async def close_batch(self, batch_id: str) -> dict[str, Any]:
        """Force close a batch and push to analysis queue.

        Retrieves batch metadata, pushes to analysis queue if detections exist,
        and cleans up Redis keys.

        This method acquires locks to prevent race conditions:
        - Batch close lock: prevents concurrent close_batch calls for the same batch
        - Camera lock: prevents add_detection from modifying the batch during close

        Args:
            batch_id: Batch identifier to close

        Returns:
            Dictionary with batch summary (batch_id, camera_id, detection_count, detections)

        Raises:
            ValueError: If batch not found
        """
        if not self._redis:
            raise RuntimeError("Redis client not initialized")

        # Acquire global batch close lock to prevent concurrent close operations
        async with self._batch_close_lock:
            # Get batch metadata (camera_id first to acquire camera lock)
            # Uses retry with exponential backoff for Redis connection failures
            camera_id = await self._redis.get(f"batch:{batch_id}:camera_id")
            if not camera_id:
                raise ValueError(f"Batch {batch_id} not found")

            # Acquire camera lock to prevent add_detection from modifying the batch
            camera_lock = await self._get_camera_lock(camera_id)
            async with camera_lock:
                # Re-check batch exists after acquiring lock (may have been closed already)
                camera_id_check = await self._redis.get(f"batch:{batch_id}:camera_id")
                if not camera_id_check:
                    # Batch was already closed by another coroutine
                    logger.debug(
                        f"Batch {batch_id} already closed, skipping",
                        extra={"batch_id": batch_id},
                    )
                    return {
                        "batch_id": batch_id,
                        "camera_id": camera_id,
                        "detection_count": 0,
                        "detections": [],
                        "started_at": time.time(),
                        "closed_at": time.time(),
                        "already_closed": True,
                    }

                # Get batch data in parallel using TaskGroup (NEM-1656)
                # All data fetches must succeed for batch close to be valid.
                # TaskGroup provides structured concurrency with automatic cancellation.
                detections: list[int] = []
                started_at_str: str | None = None
                pipeline_start_time: str | None = None

                async def fetch_detections() -> None:
                    nonlocal detections
                    detections = await self._atomic_list_get_all(f"batch:{batch_id}:detections")

                async def fetch_started_at() -> None:
                    nonlocal started_at_str
                    assert self._redis is not None  # Verified at function start
                    started_at_str = await self._redis.get(f"batch:{batch_id}:started_at")

                async def fetch_pipeline_time() -> None:
                    nonlocal pipeline_start_time
                    assert self._redis is not None  # Verified at function start
                    pipeline_start_time = await self._redis.get(
                        f"batch:{batch_id}:pipeline_start_time"
                    )

                try:
                    async with asyncio.TaskGroup() as tg:
                        tg.create_task(fetch_detections())
                        tg.create_task(fetch_started_at())
                        tg.create_task(fetch_pipeline_time())
                except* Exception as eg:
                    # Log all errors from the ExceptionGroup
                    for i, exc in enumerate(eg.exceptions):
                        logger.error(
                            f"Failed to fetch batch data (operation {i})",
                            extra={
                                "batch_id": batch_id,
                                "camera_id": camera_id,
                                "error": str(exc),
                            },
                        )
                    # Re-raise the first exception to maintain compatibility
                    raise eg.exceptions[0] from eg
                started_at = float(started_at_str) if started_at_str else time.time()

                # Create summary
                summary: dict[str, Any] = {
                    "batch_id": batch_id,
                    "camera_id": camera_id,
                    "detection_count": len(detections),
                    "detections": detections,
                    "started_at": started_at,
                    "closed_at": time.time(),
                }

                # Push to analysis queue if there are detections
                if detections:
                    queue_item: dict[str, Any] = {
                        "batch_id": batch_id,
                        "camera_id": camera_id,
                        "detection_ids": detections,
                        "timestamp": time.time(),
                    }

                    # Include pipeline_start_time for total pipeline latency tracking
                    if pipeline_start_time:
                        queue_item["pipeline_start_time"] = pipeline_start_time

                    # Use add_to_queue_safe() with DLQ policy to prevent silent data loss
                    # If the queue is full, items are moved to a dead-letter queue
                    # Uses retry with exponential backoff for Redis connection failures
                    result = await self._redis.add_to_queue_safe(
                        self._analysis_queue,
                        queue_item,
                        overflow_policy=QueueOverflowPolicy.DLQ,
                    )

                    if not result.success:
                        logger.error(
                            f"Failed to push batch {batch_id} to analysis queue: {result.error}",
                            extra={
                                "camera_id": camera_id,
                                "batch_id": batch_id,
                                "detection_count": len(detections),
                                "queue_name": self._analysis_queue,
                                "queue_length": result.queue_length,
                            },
                        )
                        raise RuntimeError(f"Queue operation failed: {result.error}")

                    if result.had_backpressure:
                        logger.warning(
                            f"Queue backpressure detected while pushing batch {batch_id}",
                            extra={
                                "camera_id": camera_id,
                                "batch_id": batch_id,
                                "detection_count": len(detections),
                                "queue_name": self._analysis_queue,
                                "queue_length": result.queue_length,
                                "moved_to_dlq": result.moved_to_dlq_count,
                                "warning": result.warning,
                            },
                        )

                    logger.info(
                        f"Pushed batch {batch_id} to analysis queue "
                        f"(camera: {camera_id}, detections: {len(detections)})",
                        extra={
                            "camera_id": camera_id,
                            "batch_id": batch_id,
                            "detection_count": len(detections),
                        },
                    )
                else:
                    logger.debug(
                        f"Batch {batch_id} has no detections, skipping analysis queue",
                        extra={"camera_id": camera_id, "batch_id": batch_id},
                    )

                # Clean up Redis keys
                await self._redis.delete(
                    f"batch:{camera_id}:current",
                    f"batch:{batch_id}:camera_id",
                    f"batch:{batch_id}:detections",
                    f"batch:{batch_id}:started_at",
                    f"batch:{batch_id}:last_activity",
                    f"batch:{batch_id}:pipeline_start_time",
                )

                logger.debug(
                    f"Cleaned up Redis keys for batch {batch_id}",
                    extra={"camera_id": camera_id, "batch_id": batch_id},
                )

                return summary

    async def _close_batch_for_size_limit(self, batch_id: str) -> dict[str, Any] | None:
        """Close a batch that has reached the max detection size limit.

        This is a specialized version of close_batch that is called from within
        add_detection when a batch reaches batch_max_detections. It handles the
        batch closing with reason "max_size" for proper tracking.

        NEM-1726: Prevents memory exhaustion by splitting large batches.

        Args:
            batch_id: Batch identifier to close

        Returns:
            Batch summary dict if batch was closed, None if batch not found
        """
        if not self._redis:
            raise RuntimeError("Redis client not initialized")

        # Get camera_id from batch metadata
        camera_id = await self._redis.get(f"batch:{batch_id}:camera_id")
        if not camera_id:
            logger.warning(
                f"Cannot close batch {batch_id}: camera_id not found",
                extra={"batch_id": batch_id},
            )
            return None

        # Get detection IDs from the batch
        detections_key = f"batch:{batch_id}:detections"
        raw_detections: list[bytes] = await self._redis._client.lrange(  # type: ignore[misc,union-attr]
            detections_key, 0, -1
        )

        # Parse detection IDs from Redis (handles both bytes and strings)
        detections = []
        for item in raw_detections:
            if isinstance(item, bytes):
                detections.append(int(item.decode("utf-8")))
            else:
                detections.append(int(item))

        # Get timestamps from batch metadata
        started_at_str = await self._redis.get(f"batch:{batch_id}:started_at")
        pipeline_start_time = await self._redis.get(f"batch:{batch_id}:pipeline_start_time")

        started_at: float = float(started_at_str) if started_at_str else time.time()
        ended_at: float = time.time()

        # Build batch summary
        summary = {
            "batch_id": batch_id,
            "camera_id": camera_id,
            "detection_ids": detections,
            "started_at": started_at,
            "ended_at": ended_at,
            "reason": "max_size",  # NEM-1726: Distinct reason for tracking
        }

        # Include pipeline_start_time if available (for latency tracking)
        if pipeline_start_time:
            summary["pipeline_start_time"] = pipeline_start_time

        # Only push to analysis queue if there are detections
        if detections:
            result = await self._redis.add_to_queue_safe(
                self._analysis_queue,
                summary,
                overflow_policy=QueueOverflowPolicy.DLQ,
            )
            if result.warning:
                logger.warning(
                    f"Queue overflow handling triggered for batch {batch_id}",
                    extra={
                        "camera_id": camera_id,
                        "batch_id": batch_id,
                        "detection_count": len(detections),
                        "queue_name": self._analysis_queue,
                        "queue_length": result.queue_length,
                        "moved_to_dlq": result.moved_to_dlq_count,
                        "warning": result.warning,
                    },
                )

            logger.info(
                f"Pushed batch {batch_id} to analysis queue "
                f"(camera: {camera_id}, detections: {len(detections)}, reason: max_size)",
                extra={
                    "camera_id": camera_id,
                    "batch_id": batch_id,
                    "detection_count": len(detections),
                    "reason": "max_size",
                },
            )
        else:
            logger.debug(
                f"Batch {batch_id} has no detections, skipping analysis queue",
                extra={"camera_id": camera_id, "batch_id": batch_id},
            )

        # Clean up Redis keys
        await self._redis.delete(
            f"batch:{camera_id}:current",
            f"batch:{batch_id}:camera_id",
            f"batch:{batch_id}:detections",
            f"batch:{batch_id}:started_at",
            f"batch:{batch_id}:last_activity",
            f"batch:{batch_id}:pipeline_start_time",
        )

        logger.debug(
            f"Cleaned up Redis keys for batch {batch_id}",
            extra={"camera_id": camera_id, "batch_id": batch_id},
        )

        return summary

    def _should_use_fast_path(self, confidence: float | None, object_type: str | None) -> bool:
        """Check if detection meets fast path criteria.

        Fast path is triggered when:
        - Confidence is provided and >= threshold
        - Object type is provided and in fast path types list

        Args:
            confidence: Detection confidence score
            object_type: Detected object type

        Returns:
            True if detection should use fast path, False otherwise
        """
        if confidence is None or object_type is None:
            return False

        if confidence < self._fast_path_threshold:
            return False

        return object_type.lower() in [t.lower() for t in self._fast_path_types]

    async def _process_fast_path(self, camera_id: str, detection_id: int) -> None:
        """Process detection via fast path (immediate analysis).

        Creates a fast path analyzer if needed and triggers immediate analysis
        of the single detection.

        Args:
            camera_id: Camera identifier
            detection_id: Detection identifier (integer)
        """
        if not self._analyzer:
            # Lazy import to avoid circular dependency
            from backend.services.nemotron_analyzer import NemotronAnalyzer

            self._analyzer = NemotronAnalyzer(redis_client=self._redis)

        try:
            # Call analyzer with fast path flag
            await self._analyzer.analyze_detection_fast_path(
                camera_id=camera_id,
                detection_id=detection_id,
            )
            logger.info(
                f"Fast path analysis completed for detection {detection_id}",
                extra={"camera_id": camera_id, "detection_id": detection_id},
            )
        except Exception as e:
            logger.error(
                f"Fast path analysis failed for detection {detection_id}: {e}",
                extra={"camera_id": camera_id, "detection_id": detection_id},
                exc_info=True,
            )

    # =========================================================================
    # Memory Pressure Backpressure (NEM-1727)
    # =========================================================================

    async def should_apply_backpressure(self) -> bool:
        """Check if backpressure should be applied due to GPU memory pressure.

        Returns True if GPU memory pressure is at CRITICAL level, indicating
        that processing should be throttled or delayed.

        Returns:
            True if backpressure should be applied, False otherwise

        Note:
            If GPU monitor is not available or check fails, returns False
            to avoid unnecessary throttling.
        """
        from backend.services.gpu_monitor import MemoryPressureLevel

        try:
            pressure_level = await get_memory_pressure_level()
            should_throttle: bool = pressure_level == MemoryPressureLevel.CRITICAL

            if should_throttle:
                logger.warning(
                    "Backpressure active due to critical GPU memory pressure",
                    extra={"pressure_level": pressure_level.value},
                )

            return should_throttle
        except Exception as e:
            logger.debug(
                f"Error checking backpressure: {e}",
                extra={"error": str(e), "error_type": type(e).__name__},
            )
            return False
