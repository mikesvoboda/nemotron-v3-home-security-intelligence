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
    - batch:{batch_id}:detections - JSON list of detection IDs
    - batch:{batch_id}:started_at - Batch start timestamp (float)
    - batch:{batch_id}:last_activity - Last activity timestamp (float)

Concurrency:
    Uses per-camera locks to prevent race conditions when multiple detections
    arrive for the same camera simultaneously. Global lock protects batch
    timeout checking and closing operations.
"""

import asyncio
import json
import time
import uuid
from collections import defaultdict
from typing import Any

from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.core.redis import QueueOverflowPolicy, RedisClient

logger = get_logger(__name__)


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
        self._analysis_queue = "analysis_queue"
        self._fast_path_threshold = settings.fast_path_confidence_threshold
        self._fast_path_types = settings.fast_path_object_types

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

    async def add_detection(
        self,
        camera_id: str,
        detection_id: int | str,
        _file_path: str,
        confidence: float | None = None,
        object_type: str | None = None,
    ) -> str:
        """Add detection to batch for camera.

        Creates a new batch if none exists for the camera, or adds to existing batch.
        Updates the last_activity timestamp for the batch.

        If detection meets fast path criteria (confidence > threshold AND object_type in
        fast path list), immediately triggers analysis instead of batching.

        Args:
            camera_id: Camera identifier
            detection_id: Detection identifier (int or string, normalized to int internally)
            file_path: Path to the detection image file
            confidence: Detection confidence score (0.0-1.0)
            object_type: Detected object type (e.g., "person", "car")

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
            batch_key = f"batch:{camera_id}:current"
            batch_id = await self._redis.get(batch_key)

            if not batch_id:
                # Create new batch
                batch_id = uuid.uuid4().hex
                logger.info(
                    f"Creating new batch {batch_id} for camera {camera_id}",
                    extra={"camera_id": camera_id, "batch_id": batch_id},
                )

                # Set batch metadata with TTL for orphan cleanup
                ttl = self.BATCH_KEY_TTL_SECONDS
                await self._redis.set(batch_key, batch_id, expire=ttl)
                await self._redis.set(f"batch:{batch_id}:camera_id", camera_id, expire=ttl)
                await self._redis.set(f"batch:{batch_id}:started_at", str(current_time), expire=ttl)
                await self._redis.set(
                    f"batch:{batch_id}:last_activity", str(current_time), expire=ttl
                )
                await self._redis.set(f"batch:{batch_id}:detections", json.dumps([]), expire=ttl)

            # Add detection to batch
            detections_key = f"batch:{batch_id}:detections"
            detections_data = await self._redis.get(detections_key)

            if detections_data:
                detections = (
                    json.loads(detections_data)
                    if isinstance(detections_data, str)
                    else detections_data
                )
            else:
                detections = []

            detections.append(detection_id_int)

            # Update batch with new detection and activity timestamp (refresh TTL)
            ttl = self.BATCH_KEY_TTL_SECONDS
            await self._redis.set(detections_key, json.dumps(detections), expire=ttl)
            await self._redis.set(f"batch:{batch_id}:last_activity", str(current_time), expire=ttl)

            logger.debug(
                f"Added detection {detection_id_int} to batch {batch_id} "
                f"(camera: {camera_id}, total detections: {len(detections)})",
                extra={
                    "camera_id": camera_id,
                    "batch_id": batch_id,
                    "detection_id": detection_id_int,
                    "detection_count": len(detections),
                },
            )

            return batch_id

    async def check_batch_timeouts(self) -> list[str]:
        """Check all active batches for timeouts and close expired ones.

        A batch is closed if:
        - It has exceeded the batch window (90 seconds from start)
        - It has exceeded the idle timeout (30 seconds since last activity)

        Returns:
            List of batch IDs that were closed
        """
        if not self._redis:
            raise RuntimeError("Redis client not initialized")

        current_time = time.time()
        closed_batches = []

        # Find all active batch keys (batch:{camera_id}:current)
        # Use SCAN instead of KEYS to avoid blocking Redis on large keyspaces
        redis_client = self._redis._client
        if redis_client is None:
            raise RuntimeError("Redis client connection not initialized")
        batch_keys: list[str] = []
        async for key in redis_client.scan_iter(match="batch:*:current", count=100):
            batch_keys.append(key)

        for batch_key in batch_keys:
            try:
                # Get batch ID and metadata
                batch_id = await self._redis.get(batch_key)
                if not batch_id:
                    continue

                started_at_str = await self._redis.get(f"batch:{batch_id}:started_at")
                last_activity_str = await self._redis.get(f"batch:{batch_id}:last_activity")

                if not started_at_str:
                    logger.warning(f"Batch {batch_id} missing started_at timestamp, skipping")
                    continue

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

                detections_data = await self._redis.get(f"batch:{batch_id}:detections")
                # Handle both pre-deserialized (from redis.get) and string formats
                if detections_data:
                    detections = (
                        json.loads(detections_data)
                        if isinstance(detections_data, str)
                        else detections_data
                    )
                else:
                    detections = []

                started_at_str = await self._redis.get(f"batch:{batch_id}:started_at")
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
                    queue_item = {
                        "batch_id": batch_id,
                        "camera_id": camera_id,
                        "detection_ids": detections,
                        "timestamp": time.time(),
                    }

                    # Use add_to_queue_safe() with DLQ policy to prevent silent data loss
                    # If the queue is full, items are moved to a dead-letter queue
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
