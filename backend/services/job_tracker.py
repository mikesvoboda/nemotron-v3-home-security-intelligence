"""Job tracker service for background job lifecycle management.

This module provides tracking and WebSocket broadcasting for background jobs.
Jobs go through states: PENDING -> RUNNING -> COMPLETED/FAILED

WebSocket events are broadcast for:
- Job progress updates (throttled to 10% increments)
- Job completion
- Job failure
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from enum import StrEnum, auto
from typing import Any, TypedDict

from backend.core.logging import get_logger

logger = get_logger(__name__)

# Progress updates are throttled to broadcast only on 10% increments
PROGRESS_THROTTLE_INCREMENT = 10

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

    Thread-safe implementation for tracking multiple concurrent jobs.
    Progress updates are throttled to prevent excessive WebSocket traffic.

    The broadcast callback can be either sync or async. When async, it will
    be scheduled on the current event loop if available.
    """

    def __init__(self, broadcast_callback: BroadcastCallback | None = None) -> None:
        """Initialize the job tracker.

        Args:
            broadcast_callback: Optional callback for broadcasting events.
                              Signature: (event_type: str, data: dict) -> None | Awaitable
                              If None, events will be logged but not broadcast.
        """
        self._broadcast_callback = broadcast_callback
        self._jobs: dict[str, JobInfo] = {}
        self._last_broadcast_progress: dict[str, int] = {}
        self._lock = threading.Lock()

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

    def create_job(self, job_type: str, job_id: str | None = None) -> str:
        """Create a new job and return its ID.

        Args:
            job_type: Type of job (e.g., 'export', 'cleanup', 'backup')
            job_id: Optional job ID. If not provided, a UUID will be generated.

        Returns:
            The job ID.
        """
        if job_id is None:
            job_id = str(uuid.uuid4())

        now = datetime.now(UTC).isoformat()

        with self._lock:
            self._jobs[job_id] = JobInfo(
                job_id=job_id,
                job_type=job_type,
                status=JobStatus.PENDING,
                progress=0,
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
        return job_id

    def start_job(self, job_id: str) -> None:
        """Mark a job as started/running.

        Args:
            job_id: The job ID to start.

        Raises:
            KeyError: If the job ID is not found.
        """
        now = datetime.now(UTC).isoformat()

        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(f"Job not found: {job_id}")

            self._jobs[job_id]["status"] = JobStatus.RUNNING
            self._jobs[job_id]["started_at"] = now

        logger.info("Job started", extra={"job_id": job_id})

    def update_progress(self, job_id: str, progress: int) -> None:
        """Update job progress and optionally broadcast.

        Progress is clamped to 0-100 range. Broadcasts are throttled to
        only occur when progress crosses a 10% threshold.

        Args:
            job_id: The job ID to update.
            progress: New progress value (0-100).

        Raises:
            KeyError: If the job ID is not found.
        """
        progress = max(0, min(100, progress))

        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(f"Job not found: {job_id}")

            self._jobs[job_id]["progress"] = progress

            should_broadcast = self._should_broadcast_progress(job_id, progress)
            if should_broadcast:
                self._last_broadcast_progress[job_id] = progress

        if should_broadcast:
            self._broadcast_progress(job_id)

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
        with self._lock:
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

        Args:
            job_id: The job ID to complete.
            result: Optional result data to include in the broadcast.

        Raises:
            KeyError: If the job ID is not found.
        """
        now = datetime.now(UTC).isoformat()

        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(f"Job not found: {job_id}")

            self._jobs[job_id]["status"] = JobStatus.COMPLETED
            self._jobs[job_id]["progress"] = 100
            self._jobs[job_id]["completed_at"] = now
            self._jobs[job_id]["result"] = result

            job = self._jobs[job_id]

        logger.info(
            "Job completed",
            extra={"job_id": job_id, "job_type": job["job_type"]},
        )

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

        Args:
            job_id: The job ID to fail.
            error: Error message describing the failure.

        Raises:
            KeyError: If the job ID is not found.
        """
        now = datetime.now(UTC).isoformat()

        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(f"Job not found: {job_id}")

            self._jobs[job_id]["status"] = JobStatus.FAILED
            self._jobs[job_id]["completed_at"] = now
            self._jobs[job_id]["error"] = error

            job = self._jobs[job_id]

        logger.error(
            "Job failed",
            extra={"job_id": job_id, "job_type": job["job_type"], "error": error},
        )

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

        Args:
            job_id: The job ID to look up.

        Returns:
            Job information or None if not found.
        """
        with self._lock:
            return self._jobs.get(job_id)

    def get_active_jobs(self) -> list[JobInfo]:
        """Get all jobs that are pending or running.

        Returns:
            List of active job information.
        """
        with self._lock:
            return [
                job
                for job in self._jobs.values()
                if job["status"] in (JobStatus.PENDING, JobStatus.RUNNING)
            ]

    def cleanup_completed_jobs(self) -> int:
        """Remove all completed and failed jobs from tracking.

        Returns:
            Number of jobs removed.
        """
        with self._lock:
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


# Module-level singleton
_job_tracker: JobTracker | None = None


def get_job_tracker(
    broadcast_callback: BroadcastCallback | None = None,
) -> JobTracker:
    """Get or create the singleton job tracker instance.

    Args:
        broadcast_callback: Optional callback for broadcasting events.
                          Only used when creating the singleton for the first time.

    Returns:
        The job tracker singleton.
    """
    global _job_tracker  # noqa: PLW0603
    if _job_tracker is None:
        _job_tracker = JobTracker(broadcast_callback)
    return _job_tracker


def reset_job_tracker() -> None:
    """Reset the job tracker singleton. Used for testing."""
    global _job_tracker  # noqa: PLW0603
    _job_tracker = None
