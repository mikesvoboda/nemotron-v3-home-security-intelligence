"""Job log emitter service for real-time log streaming via WebSocket.

This module provides a service for emitting job logs to Redis pub/sub channels,
enabling real-time log streaming through the WebSocket endpoint at
/ws/jobs/{job_id}/logs.

The emitter publishes log entries to job-specific channels (job:{job_id}:logs)
that the WebSocket endpoint subscribes to for each connected client.

Example Usage:
    from backend.services.job_log_emitter import get_job_log_emitter

    # Get the emitter service
    emitter = await get_job_log_emitter()

    # Emit a log entry
    await emitter.emit_log(
        job_id="550e8400-e29b-41d4-a716-446655440000",
        level="INFO",
        message="Processing batch 2/3",
        context={"batch_id": "abc123"},
    )

    # Emit log when job completes
    await emitter.emit_job_completed(
        job_id="550e8400-e29b-41d4-a716-446655440000",
        result={"items_processed": 100},
    )
"""

from __future__ import annotations

import asyncio
import json
import threading
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from backend.core.redis import RedisClient

logger = get_logger(__name__)


class JobLogEmitter:
    """Service for emitting job logs to Redis pub/sub for real-time streaming.

    This service provides methods for publishing job log entries to Redis
    pub/sub channels. Each job has its own channel (job:{job_id}:logs) that
    WebSocket clients can subscribe to for real-time log streaming.

    Features:
    - Emits structured log messages with timestamp, level, message, and context
    - Supports job lifecycle events (started, completed, failed)
    - Thread-safe singleton pattern
    - Graceful handling of Redis unavailability

    Attributes:
        _redis_client: Redis client for pub/sub operations
    """

    def __init__(self, redis_client: RedisClient | None = None) -> None:
        """Initialize the job log emitter.

        Args:
            redis_client: Optional Redis client for pub/sub operations.
                If not provided, the emitter will silently skip emission.
        """
        self._redis_client = redis_client
        self._emit_count = 0
        self._emit_errors = 0

    def set_redis_client(self, redis_client: RedisClient) -> None:
        """Set the Redis client after initialization.

        Args:
            redis_client: Redis client instance.
        """
        self._redis_client = redis_client

    @property
    def emit_count(self) -> int:
        """Get the total number of log entries emitted."""
        return self._emit_count

    @property
    def emit_errors(self) -> int:
        """Get the total number of emission errors."""
        return self._emit_errors

    def _get_channel_name(self, job_id: str | UUID) -> str:
        """Get the Redis pub/sub channel name for a job.

        Args:
            job_id: The job ID (string or UUID).

        Returns:
            Channel name in format "job:{job_id}:logs".
        """
        return f"job:{job_id!s}:logs"

    def _create_log_message(
        self,
        level: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a structured log message.

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR).
            message: The log message.
            context: Optional context data.

        Returns:
            Structured log message dict.
        """
        return {
            "type": "log",
            "data": {
                "timestamp": datetime.now(UTC).isoformat(),
                "level": level.upper(),
                "message": message,
                "context": context,
            },
        }

    async def emit_log(
        self,
        job_id: str | UUID,
        level: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> bool:
        """Emit a log entry for a job.

        Publishes a log message to the job's Redis pub/sub channel for
        real-time streaming to WebSocket clients.

        Args:
            job_id: The job ID to emit log for.
            level: Log level (DEBUG, INFO, WARNING, ERROR).
            message: The log message.
            context: Optional context data to include.

        Returns:
            True if the log was successfully emitted, False otherwise.
        """
        if self._redis_client is None:
            logger.debug(
                "Redis client not available, skipping job log emission",
                extra={"job_id": str(job_id)},
            )
            return False

        try:
            channel = self._get_channel_name(job_id)
            log_message = self._create_log_message(level, message, context)

            # Serialize and publish
            serialized = json.dumps(log_message)
            await self._redis_client.publish(channel, serialized)

            self._emit_count += 1

            logger.debug(
                f"Emitted job log: {message[:50]}...",
                extra={
                    "job_id": str(job_id),
                    "level": level.upper(),
                    "channel": channel,
                },
            )

            return True

        except Exception as e:
            self._emit_errors += 1
            logger.error(
                f"Failed to emit job log: {e}",
                extra={"job_id": str(job_id)},
                exc_info=True,
            )
            return False

    async def emit_job_started(
        self,
        job_id: str | UUID,
        job_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Emit a job started event.

        Args:
            job_id: The job ID.
            job_type: Type of job (e.g., 'export', 'cleanup').
            metadata: Optional job metadata.

        Returns:
            True if the event was successfully emitted, False otherwise.
        """
        return await self.emit_log(
            job_id=job_id,
            level="INFO",
            message=f"Job started: {job_type}",
            context={"job_type": job_type, "metadata": metadata},
        )

    async def emit_job_progress(
        self,
        job_id: str | UUID,
        progress_percent: int,
        current_step: str | None = None,
        items_processed: int | None = None,
        items_total: int | None = None,
    ) -> bool:
        """Emit a job progress update.

        Args:
            job_id: The job ID.
            progress_percent: Current progress (0-100).
            current_step: Description of current step.
            items_processed: Number of items processed.
            items_total: Total number of items.

        Returns:
            True if the event was successfully emitted, False otherwise.
        """
        message = f"Progress: {progress_percent}%"
        if current_step:
            message = f"{current_step}: {progress_percent}%"

        context: dict[str, Any] = {"progress_percent": progress_percent}
        if current_step:
            context["current_step"] = current_step
        if items_processed is not None:
            context["items_processed"] = items_processed
        if items_total is not None:
            context["items_total"] = items_total

        return await self.emit_log(
            job_id=job_id,
            level="INFO",
            message=message,
            context=context,
        )

    async def emit_job_completed(
        self,
        job_id: str | UUID,
        result: dict[str, Any] | None = None,
        duration_seconds: float | None = None,
    ) -> bool:
        """Emit a job completed event.

        Args:
            job_id: The job ID.
            result: Optional result summary.
            duration_seconds: Optional job duration in seconds.

        Returns:
            True if the event was successfully emitted, False otherwise.
        """
        message = "Job completed successfully"
        if duration_seconds is not None:
            message = f"Job completed successfully in {duration_seconds:.1f}s"

        return await self.emit_log(
            job_id=job_id,
            level="INFO",
            message=message,
            context={"status": "completed", "result": result, "duration_seconds": duration_seconds},
        )

    async def emit_job_failed(
        self,
        job_id: str | UUID,
        error: str,
        error_code: str | None = None,
        retryable: bool = False,
    ) -> bool:
        """Emit a job failed event.

        Args:
            job_id: The job ID.
            error: Error message.
            error_code: Optional error code for categorization.
            retryable: Whether the job can be retried.

        Returns:
            True if the event was successfully emitted, False otherwise.
        """
        return await self.emit_log(
            job_id=job_id,
            level="ERROR",
            message=f"Job failed: {error}",
            context={
                "status": "failed",
                "error": error,
                "error_code": error_code,
                "retryable": retryable,
            },
        )

    def get_stats(self) -> dict[str, Any]:
        """Get emitter statistics.

        Returns:
            Dictionary with emit counts, error counts, and Redis status.
        """
        return {
            "emit_count": self._emit_count,
            "emit_errors": self._emit_errors,
            "redis_client_available": self._redis_client is not None,
        }


# =============================================================================
# Global Singleton Instance
# =============================================================================

_emitter: JobLogEmitter | None = None
_emitter_lock: asyncio.Lock | None = None
_init_lock = threading.Lock()


def _get_emitter_lock() -> asyncio.Lock:
    """Get the emitter initialization lock (lazy initialization).

    Thread-safe creation of the asyncio lock for emitter initialization.

    Returns:
        asyncio.Lock for emitter initialization
    """
    global _emitter_lock  # noqa: PLW0603
    if _emitter_lock is None:
        with _init_lock:
            if _emitter_lock is None:
                _emitter_lock = asyncio.Lock()
    return _emitter_lock


async def get_job_log_emitter(
    redis_client: RedisClient | None = None,
) -> JobLogEmitter:
    """Get or create the global job log emitter instance.

    This function provides a thread-safe singleton pattern for the
    JobLogEmitter. On first call, it creates a new instance.
    Subsequent calls return the existing singleton.

    If a Redis client is provided, it will be set on the existing
    singleton (useful for lazy initialization).

    Args:
        redis_client: Optional Redis client instance.

    Returns:
        JobLogEmitter instance.

    Example:
        # During application startup
        from backend.core.redis import init_redis

        redis = await init_redis()
        emitter = await get_job_log_emitter(redis)

        # Later in application code
        emitter = await get_job_log_emitter()
        await emitter.emit_log(job_id, "INFO", "Processing...")
    """
    global _emitter  # noqa: PLW0603

    # Fast path: emitter already exists
    if _emitter is not None:
        # Update Redis client if provided
        if redis_client is not None:
            _emitter.set_redis_client(redis_client)
        return _emitter

    # Slow path: need to initialize with lock
    lock = _get_emitter_lock()
    async with lock:
        # Double-check after acquiring lock
        if _emitter is None:
            _emitter = JobLogEmitter(redis_client=redis_client)
            logger.info("Global job log emitter initialized")
        elif redis_client is not None:
            _emitter.set_redis_client(redis_client)

    return _emitter


def get_job_log_emitter_sync() -> JobLogEmitter | None:
    """Get the global job log emitter instance synchronously.

    Returns the existing singleton if it has been initialized,
    or None if not yet initialized.

    This is useful for checking if the emitter is available without
    async context.

    Returns:
        JobLogEmitter instance or None.
    """
    return _emitter


def reset_emitter_state() -> None:
    """Reset the global emitter state for testing purposes.

    Warning: Only use this in test teardown, never in production code.
    """
    global _emitter, _emitter_lock  # noqa: PLW0603
    _emitter = None
    _emitter_lock = None
