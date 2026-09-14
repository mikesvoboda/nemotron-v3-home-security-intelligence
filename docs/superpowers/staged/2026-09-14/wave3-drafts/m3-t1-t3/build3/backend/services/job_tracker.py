"""Job tracker service for background job lifecycle management.

This module provides tracking and WebSocket broadcasting for background jobs.
Jobs go through states: PENDING -> RUNNING -> COMPLETED/FAILED

Features:
- In-memory tracking with optional Redis persistence
- WebSocket broadcast for job progress updates (throttled to 10% increments)
- Job completion and failure notifications
- TTL-based auto-cleanup of completed jobs in Redis

WebSocket events are broadcast for:
- Job progress updates (throttled to 10% increments)
- Job completion
- Job failure
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Any, TypedDict

from backend.core.logging import get_logger

if TYPE_CHECKING:
    from backend.core.redis import RedisClient

logger = get_logger(__name__)

# Progress updates are throttled to broadcast only on 10% increments
PROGRESS_THROTTLE_INCREMENT = 10

# Redis key prefix for job storage
REDIS_JOB_KEY_PREFIX = "job:"

# TTL for completed/failed jobs in Redis (1 hour)
REDIS_JOB_TTL_SECONDS = 3600

# Type alias for broadcast callback
# Can be sync (returns None) or async (returns Awaitable)
BroadcastCallback = Callable[[str, dict[str, Any]], None | Awaitable[None]]


class JobStatus(StrEnum):
    """Status of a background job."""

    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()


class JobEventType(StrEnum):
    """Types of job-related WebSocket events."""

    JOB_PROGRESS = "job_progress"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"


class JobInfo(TypedDict):
    """Information about a tracked job."""

    job_id: str
    job_type: str
    status: JobStatus
    progress: int
    message: str | None
    created_at: str
    started_at: str | None
    completed_at: str | None
    result: Any | None
    error: str | None


class JobProgressData(TypedDict):
    """Data payload for job progress WebSocket events."""

    job_id: str
    job_type: str
    progress: int
    status: str


class JobCompletedData(TypedDict):
    """Data payload for job completed WebSocket events."""

    job_id: str
    job_type: str
    result: Any | None


class JobFailedData(TypedDict):
    """Data payload for job failed WebSocket events."""

    job_id: str
    job_type: str
    error: str


class JobTracker:
    """Tracks background job lifecycle and broadcasts WebSocket events.

    Async-safe implementation using asyncio.Lock for tracking multiple concurrent jobs.
    Progress updates are throttled to prevent excessive WebSocket traffic.

    The broadcast callback can be either sync or async. When async, it will
    be scheduled on the current event loop if available.

    Optionally supports Redis persistence for job state, enabling:
    - Job status retrieval via API endpoints
    - Crash recovery (jobs survive process restarts)
    - TTL-based auto-cleanup of completed jobs
    """

    def __init__(
        self,
        broadcast_callback: BroadcastCallback | None = None,
        redis_client: RedisClient | None = None,
    ) -> None:
        """Initialize the job tracker.

        Args:
            broadcast_callback: Optional callback for broadcasting events.
                              Signature: (event_type: str, data: dict) -> None | Awaitable
                              If None, events will be logged but not broadcast.
            redis_client: Optional Redis client for job persistence.
                         If None, jobs are only tracked in memory.
        """
        self._broadcast_callback = broadcast_callback
        self._redis_client = redis_client
        self._jobs: dict[str, JobInfo] = {}
        self._last_broadcast_progress: dict[str, int] = {}
        self._lock = asyncio.Lock()

    def set_broadcast_callback(self, callback: BroadcastCallback) -> None:
        """Set the broadcast callback after initialization.

        This allows configuring the broadcast callback later, which is useful
        when the callback depends on services not yet available at construction.

        Args:
            callback: The broadcast callback function.
        """
        self._broadcast_callback = callback
        logger.info("Job tracker broadcast callback configured")

    def set_redis_client(self, redis_client: RedisClient) -> None:
        """Set the Redis client after initialization.

        This allows configuring Redis persistence later, which is useful
        when Redis may not be available at construction time.

        Args:
            redis_client: The Redis client for job persistence.
        """
        self._redis_client = redis_client
        logger.info("Job tracker Redis client configured")

    def _broadcast(self, event_type: str, data: dict[str, Any]) -> None:
        """Broadcast an event using the configured callback.

        Handles both sync and async callbacks appropriately.
        """
        if self._broadcast_callback is None:
            return

        try:
            result = self._broadcast_callback(event_type, data)
            # If the callback returns a coroutine, schedule it
            if asyncio.iscoroutine(result):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(result)
                except RuntimeError:
                    # No running loop, run synchronously
                    asyncio.run(result)
        except Exception as e:
            logger.warning(
                "Failed to broadcast job event",
                extra={"event_type": event_type, "error": str(e)},
            )

    def _get_redis_key(self, job_id: str) -> str:
        """Get the Redis key for a job.

        Args:
            job_id: The job ID.

        Returns:
            Redis key string.
        """
        return f"{REDIS_JOB_KEY_PREFIX}{job_id}"

    async def _persist_job_async(self, job_id: str, ttl: int | None = None) -> None:
        """Persist job state to Redis asynchronously.

        Args:
            job_id: The job ID to persist.
            ttl: Optional TTL in seconds. If None, no expiry is set.
        """
        if self._redis_client is None:
            return

        # Minimal critical section - only dict access
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            # Create a copy for serialization
            job_data = dict(job)

        # Redis I/O outside the lock
        try:
            key = self._get_redis_key(job_id)
            await self._redis_client.set(key, job_data, expire=ttl)
        except Exception as e:
            logger.warning(
                "Failed to persist job to Redis",
                extra={"job_id": job_id, "error": str(e)},
            )

    def _schedule_persist(self, job_id: str, ttl: int | None = None) -> None:
        """Schedule job persistence to Redis.

        Handles the async persistence in a fire-and-forget manner.

        Args:
            job_id: The job ID to persist.
            ttl: Optional TTL in seconds.
        """
        if self._redis_client is None:
            return

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._persist_job_async(job_id, ttl))
        except RuntimeError:
            # No running event loop - skip persistence
            logger.debug("No event loop available for Redis persistence")

    async def get_job_from_redis(self, job_id: str) -> JobInfo | None:
        """Get job information from Redis.

        Falls back to in-memory storage if Redis is unavailable.

        Args:
            job_id: The job ID to look up.

        Returns:
            Job information or None if not found.
        """
        # First check in-memory cache - minimal critical section
        async with self._lock:
            if job_id in self._jobs:
                return self._jobs[job_id]

        # Redis I/O outside the lock
        if self._redis_client is None:
            return None

        try:
            key = self._get_redis_key(job_id)
            data = await self._redis_client.get(key)
            if data is not None and isinstance(data, dict):
                # Reconstruct JobInfo from Redis data
                return JobInfo(
                    job_id=data.get("job_id", job_id),
                    job_type=data.get("job_type", "unknown"),
                    status=JobStatus(data.get("status", "pending")),
                    progress=data.get("progress", 0),
                    message=data.get("message"),
                    created_at=data.get("created_at", ""),
                    started_at=data.get("started_at"),
                    completed_at=data.get("completed_at"),
                    result=data.get("result"),
                    error=data.get("error"),
                )
        except Exception as e:
            logger.warning(
                "Failed to get job from Redis",
                extra={"job_id": job_id, "error": str(e)},
            )

        return None

    def create_job(self, job_type: str, job_id: str | None = None) -> str:
        """Create a new job and return its ID.

        This method is synchronous for backward compatibility with existing code.
        Uses a simple dict assignment which is atomic in CPython due to the GIL.

        Args:
            job_type: Type of job (e.g., 'export', 'cleanup', 'backup')
            job_id: Optional job ID. If not provided, a UUID will be generated.

        Returns:
            The job ID.
        """
        if job_id is None:
            job_id = str(uuid.uuid4())

        now = datetime.now(UTC).isoformat()

        # Simple dict assignments are atomic in CPython due to GIL
        # This maintains backward compatibility while being safe
        self._jobs[job_id] = JobInfo(
            job_id=job_id,
            job_type=job_type,
            status=JobStatus.PENDING,
            progress=0,
            message=None,
            created_at=now,
            started_at=None,
            completed_at=None,
            result=None,
            error=None,
        )
        self._last_broadcast_progress[job_id] = 0

        logger.info(
            "Job created",
            extra={"job_id": job_id, "job_type": job_type},
        )

        # Persist to Redis (fire-and-forget)
        self._schedule_persist(job_id)

        return job_id

    def start_job(self, job_id: str, message: str | None = None) -> None:
        """Mark a job as started/running.

        This method is synchronous for backward compatibility.

        Args:
            job_id: The job ID to start.
            message: Optional status message.

        Raises:
            KeyError: If the job ID is not found.
        """
        now = datetime.now(UTC).isoformat()

        if job_id not in self._jobs:
            raise KeyError(f"Job not found: {job_id}")

        self._jobs[job_id]["status"] = JobStatus.RUNNING
        self._jobs[job_id]["started_at"] = now
        if message is not None:
            self._jobs[job_id]["message"] = message

        logger.info("Job started", extra={"job_id": job_id})

        # Persist to Redis
        self._schedule_persist(job_id)

    def update_progress(self, job_id: str, progress: int, message: str | None = None) -> None:
        """Update job progress and optionally broadcast.

        Progress is clamped to 0-100 range. Broadcasts are throttled to
        only occur when progress crosses a 10% threshold.

        This method is synchronous for backward compatibility.

        Args:
            job_id: The job ID to update.
            progress: New progress value (0-100).
            message: Optional status message describing current progress.

        Raises:
            KeyError: If the job ID is not found.
        """
        progress = max(0, min(100, progress))

        if job_id not in self._jobs:
            raise KeyError(f"Job not found: {job_id}")

        self._jobs[job_id]["progress"] = progress
        if message is not None:
            self._jobs[job_id]["message"] = message

        should_broadcast = self._should_broadcast_progress(job_id, progress)
        if should_broadcast:
            self._last_broadcast_progress[job_id] = progress

        if should_broadcast:
            self._broadcast_progress(job_id)
            # Persist to Redis on broadcast threshold
            self._schedule_persist(job_id)

    def _should_broadcast_progress(self, job_id: str, progress: int) -> bool:
        """Determine if progress update should be broadcast.

        Broadcasts occur when progress crosses a 10% threshold boundary.
        For example: 0->9 (no), 0->10 (yes), 10->19 (no), 10->20 (yes).

        Args:
            job_id: The job ID.
            progress: Current progress value.

        Returns:
            True if the update should be broadcast.
        """
        last_broadcast = self._last_broadcast_progress.get(job_id, 0)
        last_threshold = last_broadcast // PROGRESS_THROTTLE_INCREMENT
        current_threshold = progress // PROGRESS_THROTTLE_INCREMENT
        return current_threshold > last_threshold

    def _broadcast_progress(self, job_id: str) -> None:
        """Broadcast a job progress event via WebSocket."""
        job = self._jobs.get(job_id)
        if not job:
            return

        data = JobProgressData(
            job_id=job_id,
            job_type=job["job_type"],
            progress=job["progress"],
            status=str(job["status"]),
        )

        logger.debug(
            "Broadcasting job progress",
            extra={"job_id": job_id, "progress": data["progress"]},
        )

        self._broadcast(
            JobEventType.JOB_PROGRESS,
            {"type": JobEventType.JOB_PROGRESS, "data": dict(data)},
        )

    def complete_job(self, job_id: str, result: Any = None) -> None:
        """Mark a job as completed and broadcast.

        This method is synchronous for backward compatibility.

        Args:
            job_id: The job ID to complete.
            result: Optional result data to include in the broadcast.

        Raises:
            KeyError: If the job ID is not found.
        """
        now = datetime.now(UTC).isoformat()

        if job_id not in self._jobs:
            raise KeyError(f"Job not found: {job_id}")

        self._jobs[job_id]["status"] = JobStatus.COMPLETED
        self._jobs[job_id]["progress"] = 100
        self._jobs[job_id]["completed_at"] = now
        self._jobs[job_id]["result"] = result
        self._jobs[job_id]["message"] = "Completed successfully"

        job = self._jobs[job_id]

        logger.info(
            "Job completed",
            extra={"job_id": job_id, "job_type": job["job_type"]},
        )

        # Persist to Redis with TTL (completed jobs expire after 1 hour)
        self._schedule_persist(job_id, ttl=REDIS_JOB_TTL_SECONDS)

        data = JobCompletedData(
            job_id=job_id,
            job_type=job["job_type"],
            result=result,
        )

        self._broadcast(
            JobEventType.JOB_COMPLETED,
            {"type": JobEventType.JOB_COMPLETED, "data": dict(data)},
        )

    def fail_job(self, job_id: str, error: str) -> None:
        """Mark a job as failed and broadcast.

        This method is synchronous for backward compatibility.

        Args:
            job_id: The job ID to fail.
            error: Error message describing the failure.

        Raises:
            KeyError: If the job ID is not found.
        """
        now = datetime.now(UTC).isoformat()

        if job_id not in self._jobs:
            raise KeyError(f"Job not found: {job_id}")

        self._jobs[job_id]["status"] = JobStatus.FAILED
        self._jobs[job_id]["completed_at"] = now
        self._jobs[job_id]["error"] = error
        self._jobs[job_id]["message"] = f"Failed: {error}"

        job = self._jobs[job_id]

        logger.error(
            "Job failed",
            extra={"job_id": job_id, "job_type": job["job_type"], "error": error},
        )

        # Persist to Redis with TTL (failed jobs expire after 1 hour)
        self._schedule_persist(job_id, ttl=REDIS_JOB_TTL_SECONDS)

        data = JobFailedData(
            job_id=job_id,
            job_type=job["job_type"],
            error=error,
        )

        self._broadcast(
            JobEventType.JOB_FAILED,
            {"type": JobEventType.JOB_FAILED, "data": dict(data)},
        )

    def get_job(self, job_id: str) -> JobInfo | None:
        """Get information about a job.

        This method is synchronous for backward compatibility.
        Dict access is atomic in CPython due to the GIL.

        Args:
            job_id: The job ID to look up.

        Returns:
            Job information or None if not found.
        """
        return self._jobs.get(job_id)

    def is_cancelled(self, job_id: str) -> bool:
        """Check if a job has been cancelled.

        A job is considered cancelled if its status is FAILED and its error
        message indicates cancellation. This allows long-running tasks to
        check for cancellation and exit gracefully.

        This method is synchronous for backward compatibility.

        Args:
            job_id: The job ID to check.

        Returns:
            True if the job was cancelled, False otherwise.
            Returns False if job is not found.
        """
        job = self._jobs.get(job_id)
        if job is None:
            return False

        return job["status"] == JobStatus.FAILED and job.get("error") == "Cancelled by user"

    def get_active_jobs(self) -> list[JobInfo]:
        """Get all jobs that are pending or running.

        This method is synchronous for backward compatibility.

        Returns:
            List of active job information.
        """
        return [
            job
            for job in self._jobs.values()
            if job["status"] in (JobStatus.PENDING, JobStatus.RUNNING)
        ]

    def cleanup_completed_jobs(self) -> int:
        """Remove all completed and failed jobs from tracking.

        This method is synchronous for backward compatibility.

        Returns:
            Number of jobs removed.
        """
        to_remove = [
            job_id
            for job_id, job in self._jobs.items()
            if job["status"] in (JobStatus.COMPLETED, JobStatus.FAILED)
        ]
        for job_id in to_remove:
            del self._jobs[job_id]
            self._last_broadcast_progress.pop(job_id, None)

        if to_remove:
            logger.info("Cleaned up completed jobs", extra={"count": len(to_remove)})

        return len(to_remove)

    def get_all_jobs(
        self,
        job_type: str | None = None,
        status_filter: JobStatus | None = None,
    ) -> list[JobInfo]:
        """Get all jobs with optional filtering.

        This method is synchronous for backward compatibility.

        Args:
            job_type: Optional filter by job type (e.g., 'export', 'cleanup')
            status_filter: Optional filter by job status

        Returns:
            List of jobs matching the filters, sorted by created_at descending
        """
        jobs = list(self._jobs.values())

        # Apply filters
        if job_type is not None:
            jobs = [j for j in jobs if j["job_type"] == job_type]

        if status_filter is not None:
            jobs = [j for j in jobs if j["status"] == status_filter]

        # Sort by created_at descending (most recent first)
        jobs.sort(key=lambda j: j["created_at"], reverse=True)

        return jobs

    def cancel_job(self, job_id: str) -> bool:
        """Request cancellation of a job.

        This marks the job as failed with a cancellation message.
        Note: Actual cancellation of running tasks depends on the task
        implementation checking for cancellation status.

        This method is synchronous for backward compatibility.

        Args:
            job_id: The job ID to cancel.

        Returns:
            True if the job was cancelled, False if already completed/failed.

        Raises:
            KeyError: If the job ID is not found.
        """
        now = datetime.now(UTC).isoformat()

        if job_id not in self._jobs:
            raise KeyError(f"Job not found: {job_id}")

        job = self._jobs[job_id]

        # Can only cancel pending or running jobs
        if job["status"] in (JobStatus.COMPLETED, JobStatus.FAILED):
            return False

        self._jobs[job_id]["status"] = JobStatus.FAILED
        self._jobs[job_id]["completed_at"] = now
        self._jobs[job_id]["error"] = "Cancelled by user"
        self._jobs[job_id]["message"] = "Job cancelled by user request"

        logger.info(
            "Job cancelled",
            extra={"job_id": job_id, "job_type": job["job_type"]},
        )

        # Persist to Redis with TTL (cancelled jobs expire after 1 hour)
        self._schedule_persist(job_id, ttl=REDIS_JOB_TTL_SECONDS)

        # Broadcast cancellation as a failure event
        data = JobFailedData(
            job_id=job_id,
            job_type=job["job_type"],
            error="Cancelled by user",
        )

        self._broadcast(
            JobEventType.JOB_FAILED,
            {"type": JobEventType.JOB_FAILED, "data": dict(data)},
        )

        return True

    def cancel_queued_job(self, job_id: str) -> tuple[bool, str]:
        """Cancel a queued (pending) job.

        Only cancels jobs that are in PENDING status. Running jobs should
        be aborted instead using abort_job().

        This method is synchronous for backward compatibility.

        Args:
            job_id: The job ID to cancel.

        Returns:
            Tuple of (success, error_message). success is True if cancelled,
            False if validation failed. error_message contains details on failure.

        Raises:
            KeyError: If the job ID is not found.
        """
        now = datetime.now(UTC).isoformat()

        if job_id not in self._jobs:
            raise KeyError(f"Job not found: {job_id}")

        job = self._jobs[job_id]
        status = job["status"]

        # Can only cancel pending/queued jobs
        if status == JobStatus.RUNNING:
            return False, "Cannot cancel running job - use abort instead"
        if status in (JobStatus.COMPLETED, JobStatus.FAILED):
            return False, f"Cannot cancel job with status: {status}"

        self._jobs[job_id]["status"] = JobStatus.FAILED
        self._jobs[job_id]["completed_at"] = now
        self._jobs[job_id]["error"] = "Cancelled by user"
        self._jobs[job_id]["message"] = "Job cancelled by user request"
        job_type = job["job_type"]

        logger.info(
            "Queued job cancelled",
            extra={"job_id": job_id, "job_type": job_type},
        )

        # Persist to Redis with TTL
        self._schedule_persist(job_id, ttl=REDIS_JOB_TTL_SECONDS)

        # Broadcast cancellation as a failure event
        data = JobFailedData(
            job_id=job_id,
            job_type=job_type,
            error="Cancelled by user",
        )

        self._broadcast(
            JobEventType.JOB_FAILED,
            {"type": JobEventType.JOB_FAILED, "data": dict(data)},
        )

        return True, ""

    async def abort_job(self, job_id: str, reason: str = "User requested") -> tuple[bool, str]:
        """Abort a running job by signaling the worker via Redis pub/sub.

        Only aborts jobs that are in RUNNING status. Queued jobs should
        be cancelled instead using cancel_queued_job().

        The abort signal is sent via Redis pub/sub to channel job:{job_id}:control.
        Workers processing the job should subscribe to this channel and check
        for abort signals periodically.

        Args:
            job_id: The job ID to abort.
            reason: Reason for abortion (default: "User requested").

        Returns:
            Tuple of (success, error_message). success is True if abort signal
            was sent, False if validation failed.

        Raises:
            KeyError: If the job ID is not found.
        """
        import json

        if job_id not in self._jobs:
            raise KeyError(f"Job not found: {job_id}")

        job = self._jobs[job_id]
        status = job["status"]

        # Can only abort running jobs
        if status == JobStatus.PENDING:
            return False, "Cannot abort queued job - use cancel instead"
        if status in (JobStatus.COMPLETED, JobStatus.FAILED):
            return False, f"Cannot abort job with status: {status}"

        job_type = job["job_type"]

        # Send abort signal via Redis pub/sub (I/O operation)
        if self._redis_client is not None:
            try:
                channel = f"job:{job_id}:control"
                message = json.dumps({"action": "abort", "reason": reason})
                await self._redis_client.publish(channel, message)
                logger.info(
                    "Job abort signal sent",
                    extra={"job_id": job_id, "job_type": job_type, "channel": channel},
                )
            except Exception as e:
                logger.error(
                    "Failed to send abort signal",
                    extra={"job_id": job_id, "error": str(e)},
                )
                return False, f"Failed to send abort signal: {e}"
        else:
            logger.warning(
                "No Redis client - abort signal not sent via pub/sub",
                extra={"job_id": job_id},
            )

        # Mark job as aborting (will be set to FAILED when worker acknowledges)
        self._jobs[job_id]["message"] = f"Aborting: {reason}"

        logger.info(
            "Job abort requested",
            extra={"job_id": job_id, "job_type": job_type, "reason": reason},
        )

        # Persist to Redis
        self._schedule_persist(job_id)

        return True, ""

    def get_job_status_string(self, job_id: str) -> str | None:
        """Get the status string of a job.

        This method is synchronous for backward compatibility.

        Args:
            job_id: The job ID to look up.

        Returns:
            Job status string or None if not found.
        """
        job = self._jobs.get(job_id)
        if job is None:
            return None
        return str(job["status"])


# Module-level singleton
_job_tracker: JobTracker | None = None


def get_job_tracker(
    broadcast_callback: BroadcastCallback | None = None,
    redis_client: RedisClient | None = None,
) -> JobTracker:
    """Get or create the singleton job tracker instance.

    Args:
        broadcast_callback: Optional callback for broadcasting events.
                          Only used when creating the singleton for the first time.
        redis_client: Optional Redis client for job persistence.
                     Only used when creating the singleton for the first time.

    Returns:
        The job tracker singleton.
    """
    global _job_tracker  # noqa: PLW0603
    if _job_tracker is None:
        _job_tracker = JobTracker(broadcast_callback, redis_client)
    return _job_tracker


def reset_job_tracker() -> None:
    """Reset the job tracker singleton. Used for testing."""
    global _job_tracker  # noqa: PLW0603
    _job_tracker = None


def create_websocket_broadcast_callback() -> BroadcastCallback:
    """Create a broadcast callback that sends job events via SystemBroadcaster.

    This creates an async callback function that broadcasts job events
    to all connected WebSocket clients through the SystemBroadcaster.

    The callback formats job events to match the WebSocket event format
    expected by the frontend (type, data structure).

    Returns:
        An async callback function suitable for JobTracker.
    """
    from backend.services.system_broadcaster import get_system_broadcaster

    async def broadcast_job_event(event_type: str, data: dict[str, Any]) -> None:
        """Broadcast a job event via WebSocket.

        Args:
            event_type: The job event type (job_progress, job_completed, job_failed)
            data: The event payload containing type and data fields
        """
        broadcaster = get_system_broadcaster()
        # Send directly to local clients (this is immediate, fire-and-forget)
        await broadcaster._send_to_local_clients(data)
        logger.debug(
            "Broadcast job event via WebSocket",
            extra={"event_type": event_type, "job_id": data.get("data", {}).get("job_id")},
        )

    return broadcast_job_event


async def init_job_tracker_websocket(redis_client: RedisClient | None = None) -> JobTracker:
    """Initialize the job tracker singleton with WebSocket broadcasting.

    This should be called during application startup to configure the
    job tracker with WebSocket broadcasting capability.

    Args:
        redis_client: Optional Redis client for job persistence.

    Returns:
        The configured job tracker singleton.
    """
    tracker = get_job_tracker(redis_client=redis_client)

    # Set the broadcast callback if not already set
    if tracker._broadcast_callback is None:
        callback = create_websocket_broadcast_callback()
        tracker.set_broadcast_callback(callback)
        logger.info("Job tracker initialized with WebSocket broadcasting")

    # Set Redis client if provided and not already set
    if redis_client is not None and tracker._redis_client is None:
        tracker.set_redis_client(redis_client)

    return tracker
