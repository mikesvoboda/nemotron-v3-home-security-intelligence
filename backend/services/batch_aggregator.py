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

Redis Keys:
    - batch:{camera_id}:current - Current batch ID for camera
    - batch:{batch_id}:camera_id - Camera ID for batch
    - batch:{batch_id}:detections - JSON list of detection IDs
    - batch:{batch_id}:started_at - Batch start timestamp (float)
    - batch:{batch_id}:last_activity - Last activity timestamp (float)
"""

import json
import logging
import time
import uuid
from typing import Any

from backend.core.config import get_settings
from backend.core.redis import RedisClient

logger = logging.getLogger(__name__)


class BatchAggregator:
    """Aggregates detections into time-based batches for analysis.

    This service manages the lifecycle of detection batches, including:
    - Creating new batches for cameras
    - Adding detections to active batches
    - Checking for and closing timed-out batches
    - Pushing completed batches to the analysis queue
    """

    def __init__(self, redis_client: RedisClient | None = None):
        """Initialize batch aggregator with Redis client.

        Args:
            redis_client: Redis client instance. If None, will be injected via dependency.
        """
        self._redis = redis_client
        settings = get_settings()
        self._batch_window = settings.batch_window_seconds
        self._idle_timeout = settings.batch_idle_timeout_seconds
        self._analysis_queue = "analysis_queue"

    async def add_detection(
        self,
        camera_id: str,
        detection_id: str,
        _file_path: str,
    ) -> str:
        """Add detection to batch for camera.

        Creates a new batch if none exists for the camera, or adds to existing batch.
        Updates the last_activity timestamp for the batch.

        Args:
            camera_id: Camera identifier
            detection_id: Detection identifier
            file_path: Path to the detection image file

        Returns:
            Batch ID that the detection was added to
        """
        if not self._redis:
            raise RuntimeError("Redis client not initialized")

        current_time = time.time()

        # Check for existing active batch for this camera
        batch_key = f"batch:{camera_id}:current"
        batch_id = await self._redis.get(batch_key)

        if not batch_id:
            # Create new batch
            batch_id = uuid.uuid4().hex
            logger.info(f"Creating new batch {batch_id} for camera {camera_id}")

            # Set batch metadata
            await self._redis.set(batch_key, batch_id)
            await self._redis.set(f"batch:{batch_id}:camera_id", camera_id)
            await self._redis.set(f"batch:{batch_id}:started_at", str(current_time))
            await self._redis.set(f"batch:{batch_id}:last_activity", str(current_time))
            await self._redis.set(f"batch:{batch_id}:detections", json.dumps([]))

        # Add detection to batch
        detections_key = f"batch:{batch_id}:detections"
        detections_data = await self._redis.get(detections_key)

        if detections_data:
            detections = (
                json.loads(detections_data) if isinstance(detections_data, str) else detections_data
            )
        else:
            detections = []

        detections.append(detection_id)

        # Update batch with new detection and activity timestamp
        await self._redis.set(detections_key, json.dumps(detections))
        await self._redis.set(f"batch:{batch_id}:last_activity", str(current_time))

        logger.debug(
            f"Added detection {detection_id} to batch {batch_id} "
            f"(camera: {camera_id}, total detections: {len(detections)})"
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
        redis_client = self._redis._client
        if redis_client is None:
            raise RuntimeError("Redis client connection not initialized")
        batch_keys = await redis_client.keys("batch:*:current")

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
                    logger.info(f"Closing batch {batch_id}: {close_reason}")
                    await self.close_batch(batch_id)
                    closed_batches.append(batch_id)

            except Exception as e:
                logger.error(
                    f"Error checking timeout for batch key {batch_key}: {e}", exc_info=True
                )
                continue

        if closed_batches:
            logger.info(f"Closed {len(closed_batches)} timed-out batches")

        return closed_batches

    async def close_batch(self, batch_id: str) -> dict[str, Any]:
        """Force close a batch and push to analysis queue.

        Retrieves batch metadata, pushes to analysis queue if detections exist,
        and cleans up Redis keys.

        Args:
            batch_id: Batch identifier to close

        Returns:
            Dictionary with batch summary (batch_id, camera_id, detection_count, detections)

        Raises:
            ValueError: If batch not found
        """
        if not self._redis:
            raise RuntimeError("Redis client not initialized")

        # Get batch metadata
        camera_id = await self._redis.get(f"batch:{batch_id}:camera_id")
        if not camera_id:
            raise ValueError(f"Batch {batch_id} not found")

        detections_data = await self._redis.get(f"batch:{batch_id}:detections")
        detections = json.loads(detections_data) if detections_data else []

        started_at_str = await self._redis.get(f"batch:{batch_id}:started_at")
        started_at = float(started_at_str) if started_at_str else time.time()

        # Create summary
        summary = {
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

            await self._redis.add_to_queue(self._analysis_queue, queue_item)
            logger.info(
                f"Pushed batch {batch_id} to analysis queue "
                f"(camera: {camera_id}, detections: {len(detections)})"
            )
        else:
            logger.debug(f"Batch {batch_id} has no detections, skipping analysis queue")

        # Clean up Redis keys
        await self._redis.delete(
            f"batch:{camera_id}:current",
            f"batch:{batch_id}:camera_id",
            f"batch:{batch_id}:detections",
            f"batch:{batch_id}:started_at",
            f"batch:{batch_id}:last_activity",
        )

        logger.debug(f"Cleaned up Redis keys for batch {batch_id}")

        return summary
