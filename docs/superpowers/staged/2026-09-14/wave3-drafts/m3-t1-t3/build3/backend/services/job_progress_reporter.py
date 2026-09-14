"""Job progress reporter for WebSocket event emission.

This module provides a reusable reporter class for emitting WebSocket events
during background job execution. It handles:
- Job start/progress/completion/failure events
- Progress throttling (max 1 event per second)
- Automatic duration tracking
- Integration with the WebSocket emitter service

Example Usage:
    from backend.services.job_progress_reporter import JobProgressReporter

    reporter = await JobProgressReporter.create(
        job_id=uuid.uuid4(),
        job_type="export",
        total_items=1000,
    )

    await reporter.start()
    for i, item in enumerate(items):
        process(item)
        await reporter.report_progress(i + 1, current_step="Processing items")
    await reporter.complete(result_summary={"items_processed": len(items)})
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from backend.core.logging import get_logger
from backend.core.websocket.event_types import WebSocketEventType

if TYPE_CHECKING:
    from backend.services.websocket_emitter import WebSocketEmitterService

logger = get_logger(__name__)

# Minimum interval between progress updates in seconds
PROGRESS_THROTTLE_INTERVAL = 1.0


class JobProgressReporter:
    """Reusable progress reporter for background jobs with WebSocket events.

    This class provides a clean interface for reporting job progress through
    WebSocket events. It handles:
    - Emitting job.started when the job begins
    - Emitting job.progress updates (throttled to max 1/second)
    - Emitting job.completed or job.failed when the job finishes
    - Automatic duration tracking

    The reporter is designed to be used as a context manager or via explicit
    start/complete/fail methods.

    Attributes:
        job_id: Unique identifier for the job
        job_type: Type of job (export, cleanup, sync, etc.)
        total_items: Total number of items to process (for progress calculation)
        emitter: WebSocket emitter service for event broadcasting
    """

    def __init__(
        self,
        job_id: UUID | str,
        job_type: str,
        total_items: int,
        emitter: WebSocketEmitterService | None = None,
    ) -> None:
        """Initialize the job progress reporter.

        Args:
            job_id: Unique identifier for the job.
            job_type: Type of job (export, cleanup, backup, sync, etc.).
            total_items: Total number of items to process.
            emitter: Optional WebSocket emitter service. If not provided,
                    the global emitter will be used when events are emitted.
        """
        self._job_id = str(job_id)
        self._job_type = job_type
        self._total_items = max(1, total_items)  # Avoid division by zero
        self._emitter = emitter

        # Timing tracking
        self._started_at: datetime | None = None
        self._last_progress_time: float = 0.0
        self._last_progress_percent: int = -1

        # State tracking
        self._is_started = False
        self._is_completed = False

    @classmethod
    async def create(
        cls,
        job_id: UUID | str,
        job_type: str,
        total_items: int,
    ) -> JobProgressReporter:
        """Create a new JobProgressReporter with the global WebSocket emitter.

        This is the recommended way to create a reporter, as it automatically
        obtains the global emitter instance.

        Args:
            job_id: Unique identifier for the job.
            job_type: Type of job (export, cleanup, backup, sync, etc.).
            total_items: Total number of items to process.

        Returns:
            Configured JobProgressReporter instance.
        """
        from backend.services.websocket_emitter import get_websocket_emitter

        emitter = await get_websocket_emitter()
        return cls(job_id, job_type, total_items, emitter)

    @property
    def job_id(self) -> str:
        """Get the job ID."""
        return self._job_id

    @property
    def job_type(self) -> str:
        """Get the job type."""
        return self._job_type

    @property
    def total_items(self) -> int:
        """Get the total items count."""
        return self._total_items

    @property
    def is_started(self) -> bool:
        """Check if the job has been started."""
        return self._is_started

    @property
    def is_completed(self) -> bool:
        """Check if the job has been completed or failed."""
        return self._is_completed

    @property
    def duration_seconds(self) -> float | None:
        """Get the job duration in seconds, or None if not started."""
        if self._started_at is None:
            return None
        end_time = datetime.now(UTC)
        return (end_time - self._started_at).total_seconds()

    async def _get_emitter(self) -> WebSocketEmitterService:
        """Get the WebSocket emitter, fetching global instance if needed."""
        if self._emitter is None:
            from backend.services.websocket_emitter import get_websocket_emitter

            self._emitter = await get_websocket_emitter()
        return self._emitter

    async def start(
        self,
        *,
        estimated_duration: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Mark the job as started and emit job.started event.

        Args:
            estimated_duration: Optional estimated duration in seconds.
            metadata: Optional additional metadata for the job.

        Raises:
            RuntimeError: If the job has already been started.
        """
        if self._is_started:
            raise RuntimeError(f"Job {self._job_id} has already been started")

        self._started_at = datetime.now(UTC)
        self._is_started = True
        self._last_progress_time = time.monotonic()

        logger.info(
            f"Job started: {self._job_type}",
            extra={
                "job_id": self._job_id,
                "job_type": self._job_type,
                "total_items": self._total_items,
            },
        )

        emitter = await self._get_emitter()
        await emitter.emit(
            WebSocketEventType.JOB_STARTED,
            {
                "job_id": self._job_id,
                "job_type": self._job_type,
                "started_at": self._started_at.isoformat(),
                "estimated_duration": estimated_duration,
                "metadata": metadata,
            },
        )

    async def report_progress(
        self,
        items_processed: int,
        current_step: str | None = None,
        *,
        force: bool = False,
    ) -> bool:
        """Report job progress and optionally emit job.progress event.

        Progress updates are throttled to a maximum of 1 per second unless
        force=True or the progress percentage has changed by 10% or more.

        Args:
            items_processed: Number of items processed so far.
            current_step: Optional description of the current step.
            force: If True, emit event regardless of throttling.

        Returns:
            True if an event was emitted, False if throttled.

        Raises:
            RuntimeError: If the job has not been started or is already completed.
        """
        if not self._is_started:
            raise RuntimeError(f"Job {self._job_id} has not been started")
        if self._is_completed:
            raise RuntimeError(f"Job {self._job_id} has already completed")

        # Calculate progress percentage
        progress_percent = min(100, int((items_processed / self._total_items) * 100))

        # Check if we should emit based on throttling
        current_time = time.monotonic()
        time_since_last = current_time - self._last_progress_time
        progress_delta = abs(progress_percent - self._last_progress_percent)

        # Emit if:
        # 1. Forced
        # 2. Enough time has passed (>= 1 second)
        # 3. Progress jumped by 10% or more
        should_emit = force or time_since_last >= PROGRESS_THROTTLE_INTERVAL or progress_delta >= 10

        if not should_emit:
            return False

        self._last_progress_time = current_time
        self._last_progress_percent = progress_percent

        logger.debug(
            f"Job progress: {progress_percent}%",
            extra={
                "job_id": self._job_id,
                "job_type": self._job_type,
                "progress": progress_percent,
                "items_processed": items_processed,
                "total_items": self._total_items,
            },
        )

        emitter = await self._get_emitter()
        await emitter.emit(
            WebSocketEventType.JOB_PROGRESS,
            {
                "job_id": self._job_id,
                "job_type": self._job_type,
                "progress": progress_percent,
                "status": "running",
                "message": current_step,
            },
        )
        return True

    async def complete(
        self,
        result_summary: dict[str, Any] | None = None,
    ) -> None:
        """Mark the job as completed and emit job.completed event.

        Args:
            result_summary: Optional summary of the job results.

        Raises:
            RuntimeError: If the job has not been started or is already completed.
        """
        if not self._is_started:
            raise RuntimeError(f"Job {self._job_id} has not been started")
        if self._is_completed:
            raise RuntimeError(f"Job {self._job_id} has already completed")

        self._is_completed = True
        completed_at = datetime.now(UTC)
        duration = self.duration_seconds

        logger.info(
            f"Job completed: {self._job_type}",
            extra={
                "job_id": self._job_id,
                "job_type": self._job_type,
                "duration_seconds": duration,
            },
        )

        emitter = await self._get_emitter()
        await emitter.emit(
            WebSocketEventType.JOB_COMPLETED,
            {
                "job_id": self._job_id,
                "job_type": self._job_type,
                "completed_at": completed_at.isoformat(),
                "result": result_summary,
                "duration_seconds": duration,
            },
        )

    async def fail(
        self,
        error: BaseException | str,
        *,
        retryable: bool = False,
        error_code: str | None = None,
    ) -> None:
        """Mark the job as failed and emit job.failed event.

        Args:
            error: The exception or error message describing the failure.
            retryable: Whether the job can be retried.
            error_code: Optional error code for categorization.

        Raises:
            RuntimeError: If the job has not been started or is already completed.
        """
        if not self._is_started:
            raise RuntimeError(f"Job {self._job_id} has not been started")
        if self._is_completed:
            raise RuntimeError(f"Job {self._job_id} has already completed")

        self._is_completed = True
        failed_at = datetime.now(UTC)

        error_message = str(error)
        if isinstance(error, BaseException):
            error_message = f"{type(error).__name__}: {error}"

        logger.error(
            f"Job failed: {self._job_type}",
            extra={
                "job_id": self._job_id,
                "job_type": self._job_type,
                "error": error_message,
            },
        )

        emitter = await self._get_emitter()
        await emitter.emit(
            WebSocketEventType.JOB_FAILED,
            {
                "job_id": self._job_id,
                "job_type": self._job_type,
                "failed_at": failed_at.isoformat(),
                "error": error_message,
                "error_code": error_code,
                "retryable": retryable,
            },
        )

    async def __aenter__(self) -> JobProgressReporter:
        """Async context manager entry - starts the job.

        Returns:
            Self for use in the context manager block.
        """
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> bool:
        """Async context manager exit - completes or fails the job.

        If an exception occurred, the job is marked as failed.
        Otherwise, it is marked as completed.

        Args:
            exc_type: Exception type if an exception was raised.
            exc_val: Exception value if an exception was raised.
            exc_tb: Exception traceback if an exception was raised.

        Returns:
            False to propagate exceptions, True would suppress them.
        """
        if exc_val is not None:
            # An exception occurred, mark as failed
            await self.fail(exc_val)
        elif not self._is_completed:
            # No exception and not already completed, mark as completed
            await self.complete()
        return False  # Don't suppress exceptions


async def create_job_progress_reporter(
    job_id: UUID | str,
    job_type: str,
    total_items: int,
) -> JobProgressReporter:
    """Create a job progress reporter with the global WebSocket emitter.

    Convenience function for creating reporters without using the class method.

    Args:
        job_id: Unique identifier for the job.
        job_type: Type of job (export, cleanup, backup, sync, etc.).
        total_items: Total number of items to process.

    Returns:
        Configured JobProgressReporter instance.
    """
    return await JobProgressReporter.create(job_id, job_type, total_items)
