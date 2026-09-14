"""Background job for periodic job timeout checking.

This module provides a background task that periodically checks for
stuck/timed-out jobs and handles them appropriately.

The checker runs every 30 seconds by default and:
- Scans all running jobs for timeout conditions
- Marks timed-out jobs as failed
- Reschedules jobs with remaining retry attempts

Usage:
    # Start the timeout checker
    checker = get_timeout_checker_job(redis_client)
    await checker.start()

    # Stop the checker
    await checker.stop()

Integration with FastAPI:
    @app.on_event("startup")
    async def startup():
        checker = get_timeout_checker_job(get_redis_client())
        await checker.start()

    @app.on_event("shutdown")
    async def shutdown():
        checker = get_timeout_checker_job(get_redis_client())
        await checker.stop()
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from backend.core.logging import get_logger
from backend.services.job_timeout_service import JobTimeoutService

if TYPE_CHECKING:
    from backend.core.redis import RedisClient

logger = get_logger(__name__)

# Default interval between timeout checks (in seconds)
DEFAULT_CHECK_INTERVAL_SECONDS = 30


class TimeoutCheckerJob:
    """Background job that periodically checks for timed-out jobs.

    This class manages a background asyncio task that runs the timeout
    detection loop at a configurable interval.

    Attributes:
        check_interval: Seconds between timeout checks.
        is_running: Whether the checker is currently running.
    """

    def __init__(
        self,
        redis_client: RedisClient,
        timeout_service: JobTimeoutService | None = None,
        check_interval: int = DEFAULT_CHECK_INTERVAL_SECONDS,
    ) -> None:
        """Initialize the timeout checker job.

        Args:
            redis_client: Redis client for communication.
            timeout_service: Optional timeout service. If not provided,
                           a new instance will be created.
            check_interval: Seconds between timeout checks. Defaults to 30.
        """
        self._redis = redis_client
        self._timeout_service = timeout_service or JobTimeoutService(redis_client)
        self._check_interval = check_interval
        self._task: asyncio.Task[None] | None = None
        self._running = False

    @property
    def check_interval(self) -> int:
        """Get the check interval in seconds."""
        return self._check_interval

    @property
    def is_running(self) -> bool:
        """Check if the timeout checker is running."""
        return self._running

    async def start(self) -> None:
        """Start the timeout checker background task.

        If already running, this is a no-op.
        """
        if self._running:
            logger.warning("Timeout checker job already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())

        logger.info(
            "Started timeout checker job",
            extra={"check_interval_seconds": self._check_interval},
        )

    async def stop(self) -> None:
        """Stop the timeout checker background task.

        Waits for the current check cycle to complete before stopping.
        """
        if not self._running:
            return

        self._running = False

        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                # Expected when task is cancelled via cancel().
                # This is normal cleanup behavior, not an error condition.
                # See: NEM-2540 for rationale
                pass
            self._task = None

        logger.info("Stopped timeout checker job")

    async def _run_loop(self) -> None:
        """Main loop that periodically checks for timed-out jobs."""
        logger.info(
            "Timeout checker loop starting",
            extra={"interval_seconds": self._check_interval},
        )

        while self._running:
            try:
                await self._run_check()
            except asyncio.CancelledError:
                # Task was cancelled, exit loop
                break
            except Exception as e:
                logger.error(
                    "Error in timeout checker loop",
                    extra={"error": str(e), "error_type": type(e).__name__},
                )

            # Wait for next check interval
            try:
                await asyncio.sleep(self._check_interval)
            except asyncio.CancelledError:
                break

        logger.info("Timeout checker loop stopped")

    async def _run_check(self) -> None:
        """Execute a single timeout check cycle."""
        try:
            results = await self._timeout_service.check_for_timeouts()

            if results:
                logger.info(
                    "Timeout check completed",
                    extra={
                        "timed_out_jobs": len(results),
                        "rescheduled": sum(1 for r in results if r.was_rescheduled),
                        "permanently_failed": sum(1 for r in results if not r.was_rescheduled),
                    },
                )
            else:
                logger.debug("Timeout check completed - no timed out jobs")

        except Exception as e:
            logger.error(
                "Error during timeout check",
                extra={"error": str(e)},
            )
            raise

    async def run_once(self) -> int:
        """Run a single timeout check (useful for testing or manual triggering).

        Returns:
            Number of jobs that were handled.
        """
        results = await self._timeout_service.check_for_timeouts()
        return len(results)


# Module-level singleton
_timeout_checker_job: TimeoutCheckerJob | None = None


def get_timeout_checker_job(
    redis_client: RedisClient,
    check_interval: int = DEFAULT_CHECK_INTERVAL_SECONDS,
) -> TimeoutCheckerJob:
    """Get or create the singleton timeout checker job instance.

    Args:
        redis_client: Redis client for storage.
        check_interval: Seconds between checks.

    Returns:
        The timeout checker job singleton.
    """
    global _timeout_checker_job  # noqa: PLW0603
    if _timeout_checker_job is None:
        _timeout_checker_job = TimeoutCheckerJob(
            redis_client=redis_client,
            check_interval=check_interval,
        )
    return _timeout_checker_job


def reset_timeout_checker_job() -> None:
    """Reset the timeout checker job singleton. Used for testing."""
    global _timeout_checker_job  # noqa: PLW0603
    if _timeout_checker_job is not None and _timeout_checker_job.is_running:
        # Note: This is synchronous reset for test cleanup
        # In production, use await stop() before reset
        _timeout_checker_job._running = False
    _timeout_checker_job = None
