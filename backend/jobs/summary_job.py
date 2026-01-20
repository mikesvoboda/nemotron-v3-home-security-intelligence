"""Background job for generating dashboard summaries.

This job runs every 5 minutes to generate both hourly and daily summaries
of high/critical security events using the Nemotron LLM.

The job:
1. Calls SummaryGenerator.generate_all_summaries() to create summaries
2. Broadcasts updates via WebSocket to connected clients
3. Invalidates the Redis cache for summaries
4. Logs success/failure metrics

Safety features:
    - 60-second timeout to prevent hanging if LLM is unresponsive
    - Graceful error handling with logging
    - Circuit breaker integration (via SummaryGenerator)

Related Issues:
    - NEM-2891: Create scheduled job for generating summaries
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any

from backend.core.async_context import generate_task_id, set_job_id
from backend.core.logging import get_logger, log_context
from backend.services.cache_service import CacheService
from backend.services.summary_generator import SummaryGenerator, get_summary_generator

if TYPE_CHECKING:
    from backend.core.redis import RedisClient
    from backend.models.summary import Summary
    from backend.services.event_broadcaster import EventBroadcaster

logger = get_logger(__name__)

# Default configuration values
DEFAULT_INTERVAL_MINUTES = 5
DEFAULT_TIMEOUT_SECONDS = 60

# Job type constant for job system integration
JOB_TYPE_GENERATE_SUMMARIES = "generate_summaries"

# Cache keys that need to be invalidated when summaries are generated
# These match the keys defined in backend/api/routes/summaries.py
SUMMARY_CACHE_KEYS = [
    "summaries:latest",
    "summaries:hourly",
    "summaries:daily",
]


async def invalidate_summary_cache(cache_service: CacheService) -> int:
    """Invalidate all summary-related cache keys.

    Args:
        cache_service: Cache service instance

    Returns:
        Number of keys invalidated
    """
    invalidated = 0
    for key in SUMMARY_CACHE_KEYS:
        try:
            if await cache_service.invalidate(key):
                invalidated += 1
        except Exception as e:
            logger.warning(f"Failed to invalidate cache key {key}: {e}")

    if invalidated > 0:
        logger.debug(f"Invalidated {invalidated} summary cache keys")

    return invalidated


async def broadcast_summary_update(
    broadcaster: EventBroadcaster,
    summaries: dict[str, Summary],
) -> int:
    """Broadcast summary update to all connected WebSocket clients.

    Sends a message with type "summary_update" containing the latest
    hourly and daily summaries via the EventBroadcaster's built-in method.

    Args:
        broadcaster: EventBroadcaster instance
        summaries: Dictionary with 'hourly' and 'daily' Summary objects

    Returns:
        Number of Redis subscribers that received the message
    """
    from backend.api.schemas.summaries import SummaryResponse

    try:
        # Convert Summary models to response format
        hourly = summaries.get("hourly")
        daily = summaries.get("daily")

        hourly_data = None
        if hourly:
            hourly_data = SummaryResponse(
                id=hourly.id,
                content=hourly.content,
                event_count=hourly.event_count,
                window_start=hourly.window_start,
                window_end=hourly.window_end,
                generated_at=hourly.generated_at,
            ).model_dump(mode="json")

        daily_data = None
        if daily:
            daily_data = SummaryResponse(
                id=daily.id,
                content=daily.content,
                event_count=daily.event_count,
                window_start=daily.window_start,
                window_end=daily.window_end,
                generated_at=daily.generated_at,
            ).model_dump(mode="json")

        # Use EventBroadcaster's built-in method for summary updates
        # This method handles validation and proper message formatting
        subscriber_count = await broadcaster.broadcast_summary_update(
            hourly=hourly_data,
            daily=daily_data,
        )

        logger.debug(
            "Broadcast summary update to WebSocket clients",
            extra={"subscriber_count": subscriber_count},
        )
        return subscriber_count

    except Exception as e:
        logger.warning(f"Failed to broadcast summary update: {e}")
        return 0


class SummaryJob:
    """Background job that generates dashboard summaries periodically.

    This class manages the execution of summary generation, including
    timeout handling, cache invalidation, and WebSocket broadcasting.

    Attributes:
        timeout: Maximum seconds to wait for summary generation
        generator: SummaryGenerator instance
    """

    def __init__(
        self,
        generator: SummaryGenerator | None = None,
        redis_client: RedisClient | None = None,
        broadcaster: EventBroadcaster | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        """Initialize the summary job.

        Args:
            generator: Optional SummaryGenerator instance. If not provided,
                uses the singleton instance.
            redis_client: Optional Redis client for cache invalidation.
            broadcaster: Optional EventBroadcaster for WebSocket updates.
            timeout: Timeout in seconds for summary generation. Default: 60s.
        """
        self._generator = generator or get_summary_generator()
        self._redis_client = redis_client
        self._broadcaster = broadcaster
        self._timeout = timeout

    async def run(self) -> dict[str, Any]:
        """Execute the summary generation job.

        Generates both hourly and daily summaries, invalidates the cache,
        and broadcasts updates to WebSocket clients.

        Returns:
            Dictionary with job results including:
                - success: bool indicating if generation succeeded
                - hourly_event_count: number of events in hourly summary
                - daily_event_count: number of events in daily summary
                - cache_invalidated: number of cache keys invalidated
                - error: error message if failed (only present on failure)

        Raises:
            asyncio.TimeoutError: If generation exceeds timeout
            Exception: Any other error from SummaryGenerator
        """
        import time

        # Generate unique job_id for log correlation
        job_id = generate_task_id("summary-job")
        set_job_id(job_id)

        start_time = time.monotonic()
        result: dict[str, Any] = {
            "success": False,
            "hourly_event_count": 0,
            "daily_event_count": 0,
            "cache_invalidated": 0,
        }

        # Use log_context to enrich all logs with job context
        with log_context(job_id=job_id, job_type=JOB_TYPE_GENERATE_SUMMARIES):
            logger.info(
                f"Starting summary generation job (timeout={self._timeout}s)",
                extra={"timeout": self._timeout},
            )

            try:
                # Generate summaries with timeout
                async with asyncio.timeout(self._timeout):
                    summaries = await self._generator.generate_all_summaries()

                hourly = summaries.get("hourly")
                daily = summaries.get("daily")

                result["hourly_event_count"] = hourly.event_count if hourly else 0
                result["daily_event_count"] = daily.event_count if daily else 0

                # Invalidate cache if Redis client is available
                if self._redis_client is not None:
                    try:
                        cache_service = CacheService(self._redis_client)
                        result["cache_invalidated"] = await invalidate_summary_cache(cache_service)
                    except Exception as e:
                        logger.warning(f"Cache invalidation failed: {e}")

                # Broadcast update if broadcaster is available
                if self._broadcaster is not None:
                    await broadcast_summary_update(self._broadcaster, summaries)

                result["success"] = True
                duration = time.monotonic() - start_time

                logger.info(
                    "Summary generation job completed successfully",
                    extra={
                        "duration_seconds": round(duration, 2),
                        "hourly_event_count": result["hourly_event_count"],
                        "daily_event_count": result["daily_event_count"],
                        "cache_invalidated": result["cache_invalidated"],
                    },
                )

                return result

            except TimeoutError:
                duration = time.monotonic() - start_time
                error_msg = f"Summary generation timed out after {self._timeout}s"
                result["error"] = error_msg

                logger.error(
                    error_msg,
                    extra={
                        "duration_seconds": round(duration, 2),
                        "timeout": self._timeout,
                    },
                )
                raise

            except Exception as e:
                duration = time.monotonic() - start_time
                result["error"] = str(e)

                logger.error(
                    f"Summary generation job failed: {e}",
                    extra={
                        "duration_seconds": round(duration, 2),
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                    exc_info=True,
                )
                raise
            finally:
                # Clear job_id context when job completes
                set_job_id(None)


class SummaryJobScheduler:
    """Scheduler for running summary jobs periodically.

    This class manages the lifecycle of periodic summary generation,
    running jobs at configured intervals (default: every 5 minutes).
    """

    def __init__(
        self,
        interval_minutes: int = DEFAULT_INTERVAL_MINUTES,
        redis_client: RedisClient | None = None,
        broadcaster: EventBroadcaster | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        """Initialize the summary job scheduler.

        Args:
            interval_minutes: Minutes between job runs. Default: 5 minutes.
            redis_client: Optional Redis client for cache invalidation.
            broadcaster: Optional EventBroadcaster for WebSocket updates.
            timeout: Timeout in seconds for each job run. Default: 60s.
        """
        self.interval_minutes = interval_minutes
        self._redis_client = redis_client
        self._broadcaster = broadcaster
        self._timeout = timeout
        self._task: asyncio.Task[None] | None = None
        self._running = False

        logger.info(
            f"SummaryJobScheduler initialized: interval={interval_minutes}min, timeout={timeout}s"
        )

    @property
    def is_running(self) -> bool:
        """Check if the scheduler is running."""
        return self._running

    async def _job_loop(self) -> None:
        """Main loop that runs summary jobs periodically."""
        logger.info(
            "Summary job scheduler loop started",
            extra={"interval_minutes": self.interval_minutes},
        )

        while self._running:
            try:
                # Create and run job
                job = SummaryJob(
                    redis_client=self._redis_client,
                    broadcaster=self._broadcaster,
                    timeout=self._timeout,
                )
                await job.run()

            except asyncio.CancelledError:
                logger.info("Summary job scheduler loop cancelled")
                break
            except Exception as e:
                # Log error but continue running
                logger.error(
                    f"Error in summary job loop: {e}",
                    extra={"error": str(e), "error_type": type(e).__name__},
                )

            # Wait for next run
            try:
                wait_seconds = self.interval_minutes * 60
                logger.debug(f"Next summary job in {self.interval_minutes} minutes")
                await asyncio.sleep(wait_seconds)
            except asyncio.CancelledError:
                break

        logger.info("Summary job scheduler loop stopped")

    async def start(self) -> None:
        """Start the scheduled job.

        This method is idempotent - calling it multiple times is safe.
        """
        if self._running:
            logger.warning("Summary job scheduler already running")
            return

        logger.info("Starting summary job scheduler")
        self._running = True
        self._task = asyncio.create_task(self._job_loop())

    async def stop(self) -> None:
        """Stop the scheduled job.

        Cancels the job loop and waits for graceful shutdown.
        """
        if not self._running:
            logger.debug("Summary job scheduler not running, nothing to stop")
            return

        logger.info("Stopping summary job scheduler")
        self._running = False

        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        logger.info("Summary job scheduler stopped")

    async def run_once(self) -> dict[str, Any]:
        """Run a single summary job (useful for testing or manual triggering).

        Returns:
            Job result dictionary
        """
        job = SummaryJob(
            redis_client=self._redis_client,
            broadcaster=self._broadcaster,
            timeout=self._timeout,
        )
        return await job.run()

    async def __aenter__(self) -> SummaryJobScheduler:
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Async context manager exit."""
        await self.stop()


# Module-level singleton
_scheduler: SummaryJobScheduler | None = None


def get_summary_job_scheduler(
    interval_minutes: int = DEFAULT_INTERVAL_MINUTES,
    redis_client: RedisClient | None = None,
    broadcaster: EventBroadcaster | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> SummaryJobScheduler:
    """Get or create the singleton summary job scheduler instance.

    Args:
        interval_minutes: Minutes between job runs.
        redis_client: Optional Redis client for cache invalidation.
        broadcaster: Optional EventBroadcaster for WebSocket updates.
        timeout: Timeout in seconds for each job run.

    Returns:
        The summary job scheduler singleton.
    """
    global _scheduler  # noqa: PLW0603
    if _scheduler is None:
        _scheduler = SummaryJobScheduler(
            interval_minutes=interval_minutes,
            redis_client=redis_client,
            broadcaster=broadcaster,
            timeout=timeout,
        )
    return _scheduler


def reset_summary_job_scheduler() -> None:
    """Reset the summary job scheduler singleton. Used for testing."""
    global _scheduler  # noqa: PLW0603
    if _scheduler is not None and _scheduler.is_running:
        # Note: This is synchronous reset for test cleanup
        # In production, use await stop() before reset
        _scheduler._running = False
    _scheduler = None
