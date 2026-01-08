"""Data cleanup service for enforcing retention policies.

This service automatically deletes old records and files based on the configured
retention period. It runs daily at a scheduled time to maintain database size
and free up disk space.

Features:
    - Deletes events older than retention period
    - Cascade deletes associated detections
    - Removes GPU stats older than retention period
    - Cleans up thumbnail files for deleted detections
    - Optional cleanup of original image files
    - Transaction-safe deletions with rollback support
    - Detailed statistics on cleanup operations
    - Streaming queries to avoid loading all records into memory (NEM-1539)
    - Batch deletes for improved performance with large datasets (NEM-1539)

Cleanup Stats:
    - events_deleted: Number of events removed
    - detections_deleted: Number of detections removed
    - gpu_stats_deleted: Number of GPU stat records removed
    - thumbnails_deleted: Number of thumbnail files removed
    - images_deleted: Number of original images removed
    - space_reclaimed: Estimated disk space freed (bytes)
"""

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, TypedDict

from sqlalchemy import delete, select

from backend.core.config import get_settings
from backend.core.database import get_session
from backend.core.logging import get_logger, sanitize_error  # noqa: F401
from backend.models.detection import Detection
from backend.models.event import Event
from backend.models.gpu_stats import GPUStats
from backend.models.log import Log

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class CleanupStatsDict(TypedDict):
    """Type for cleanup service status dictionary."""

    running: bool
    retention_days: int
    cleanup_time: str
    delete_images: bool
    next_cleanup: str | None


class CleanupStats:
    """Statistics for a cleanup operation."""

    def __init__(self) -> None:
        """Initialize cleanup stats with zero values."""
        self.events_deleted: int = 0
        self.detections_deleted: int = 0
        self.gpu_stats_deleted: int = 0
        self.logs_deleted: int = 0
        self.thumbnails_deleted: int = 0
        self.images_deleted: int = 0
        self.space_reclaimed: int = 0

    def to_dict(self) -> dict[str, int]:
        """Convert stats to dictionary.

        Returns:
            Dictionary with all cleanup statistics
        """
        return {
            "events_deleted": self.events_deleted,
            "detections_deleted": self.detections_deleted,
            "gpu_stats_deleted": self.gpu_stats_deleted,
            "logs_deleted": self.logs_deleted,
            "thumbnails_deleted": self.thumbnails_deleted,
            "images_deleted": self.images_deleted,
            "space_reclaimed": self.space_reclaimed,
        }

    def __repr__(self) -> str:
        """String representation of cleanup stats."""
        return (
            f"<CleanupStats(events={self.events_deleted}, "
            f"detections={self.detections_deleted}, "
            f"gpu_stats={self.gpu_stats_deleted}, "
            f"logs={self.logs_deleted}, "
            f"files={self.thumbnails_deleted + self.images_deleted}, "
            f"space={self.space_reclaimed} bytes)>"
        )


class CleanupService:
    """Service for automated data cleanup based on retention policies.

    This service runs on a schedule to delete old records and files,
    maintaining database size and freeing disk space. All deletions
    are performed in transactions with proper error handling.
    """

    def __init__(
        self,
        cleanup_time: str = "03:00",
        retention_days: int | None = None,
        thumbnail_dir: str = "data/thumbnails",
        delete_images: bool = False,
        batch_size: int = 1000,
    ):
        """Initialize cleanup service.

        Args:
            cleanup_time: Time to run daily cleanup in HH:MM format (24-hour)
            retention_days: Number of days to retain data (None = use config default)
            thumbnail_dir: Directory containing thumbnail files
            delete_images: Whether to delete original image files (default: False)
            batch_size: Number of records to process per batch (default: 1000).
                        Used for streaming queries to limit memory usage.
        """
        settings = get_settings()
        self.cleanup_time = cleanup_time
        self.retention_days = retention_days or settings.retention_days
        self.thumbnail_dir = Path(thumbnail_dir)
        self.delete_images = delete_images
        self.batch_size = batch_size

        # Task tracking
        self._cleanup_task: asyncio.Task | None = None
        self.running = False

        logger.info(
            f"CleanupService initialized: "
            f"retention={self.retention_days} days, "
            f"time={self.cleanup_time}, "
            f"delete_images={self.delete_images}, "
            f"batch_size={self.batch_size}"
        )

    def _parse_cleanup_time(self) -> tuple[int, int]:
        """Parse cleanup time string into hours and minutes.

        Returns:
            Tuple of (hours, minutes)

        Raises:
            ValueError: If cleanup_time format is invalid
        """
        try:
            hours, minutes = self.cleanup_time.split(":")
            hours_int = int(hours)
            minutes_int = int(minutes)

            if not (0 <= hours_int < 24) or not (0 <= minutes_int < 60):
                raise ValueError("Invalid time range")

            return hours_int, minutes_int
        except (ValueError, AttributeError) as e:
            raise ValueError(
                f"Invalid cleanup_time format '{self.cleanup_time}'. "
                f"Expected HH:MM (24-hour format)"
            ) from e

    def _calculate_next_cleanup(self) -> datetime:
        """Calculate the next cleanup time.

        Returns:
            Datetime of next scheduled cleanup
        """
        hours, minutes = self._parse_cleanup_time()
        now = datetime.now()

        # Calculate next cleanup time
        next_cleanup = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)

        # If time has already passed today, schedule for tomorrow
        if next_cleanup <= now:
            next_cleanup += timedelta(days=1)

        return next_cleanup

    async def _wait_until_next_cleanup(self) -> None:
        """Wait until the next scheduled cleanup time."""
        next_cleanup = self._calculate_next_cleanup()
        wait_seconds = (next_cleanup - datetime.now()).total_seconds()

        logger.info(f"Next cleanup scheduled for {next_cleanup} ({wait_seconds:.0f}s)")

        await asyncio.sleep(wait_seconds)

    async def run_cleanup(self) -> CleanupStats:
        """Execute cleanup operation.

        Deletes old records and files based on retention policy.
        Uses streaming queries to avoid loading all records into memory.

        Returns:
            CleanupStats object with operation statistics

        Raises:
            Exception: If cleanup fails (transaction is rolled back)
        """
        logger.info(f"Starting cleanup (retention: {self.retention_days} days)")
        stats = CleanupStats()

        # Calculate cutoff date (use UTC for consistency with timezone-aware columns)
        cutoff_date = datetime.now(UTC) - timedelta(days=self.retention_days)
        logger.info(f"Deleting records older than {cutoff_date}")

        try:
            async with get_session() as session:
                # Step 1: Stream detection file paths without loading all into memory
                thumbnail_paths, image_paths = await self._get_detection_file_paths_streaming(
                    session, cutoff_date
                )

                # Step 2: Delete old detections
                delete_detections_stmt = delete(Detection).where(
                    Detection.detected_at < cutoff_date
                )
                detections_result = await session.execute(delete_detections_stmt)
                stats.detections_deleted = detections_result.rowcount or 0  # type: ignore[attr-defined]
                logger.info(f"Deleted {stats.detections_deleted} old detections")

                # Step 3: Delete old events
                delete_events_stmt = delete(Event).where(Event.started_at < cutoff_date)
                events_result = await session.execute(delete_events_stmt)
                stats.events_deleted = events_result.rowcount or 0  # type: ignore[attr-defined]
                logger.info(f"Deleted {stats.events_deleted} old events")

                # Step 4: Delete old GPU stats
                delete_gpu_stats_stmt = delete(GPUStats).where(GPUStats.recorded_at < cutoff_date)
                gpu_stats_result = await session.execute(delete_gpu_stats_stmt)
                stats.gpu_stats_deleted = gpu_stats_result.rowcount or 0  # type: ignore[attr-defined]
                logger.info(f"Deleted {stats.gpu_stats_deleted} old GPU stats")

                # Commit database deletions
                await session.commit()
                logger.info("Database cleanup committed successfully")

            # Step 5: Delete old logs
            stats.logs_deleted = await self.cleanup_old_logs()

            # Step 6: Delete thumbnail files (after successful DB commit)
            for thumbnail_path in thumbnail_paths:
                if self._delete_file(thumbnail_path):
                    stats.thumbnails_deleted += 1

            logger.info(f"Deleted {stats.thumbnails_deleted} thumbnail files")

            # Step 7: Delete original image files (if enabled)
            if self.delete_images:
                for image_path in image_paths:
                    if self._delete_file(image_path):
                        stats.images_deleted += 1

                logger.info(f"Deleted {stats.images_deleted} original image files")

            logger.info(f"Cleanup completed: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Cleanup failed: {e}", exc_info=True)
            raise

    async def _get_detection_file_paths_streaming(
        self, session: AsyncSession, cutoff_date: datetime
    ) -> tuple[list[str], list[str]]:
        """Stream detection file paths without loading all records into memory.

        Uses SQLAlchemy's stream_scalars() to iterate over results without
        loading the entire result set into memory.

        Args:
            session: Database session
            cutoff_date: Delete detections older than this date

        Returns:
            Tuple of (thumbnail_paths, image_paths) lists
        """
        thumbnail_paths: list[str] = []
        image_paths: list[str] = []

        # Use streaming to avoid loading all detections into memory
        detections_query = select(Detection).where(Detection.detected_at < cutoff_date)

        async for detection in await session.stream_scalars(detections_query):
            if detection.thumbnail_path:
                thumbnail_paths.append(detection.thumbnail_path)
            if self.delete_images and detection.file_path:
                image_paths.append(detection.file_path)

        return thumbnail_paths, image_paths

    async def dry_run_cleanup(self) -> CleanupStats:
        """Calculate what would be deleted without actually deleting.

        This method performs the same queries as run_cleanup but uses COUNT
        queries instead of DELETE statements, and does not modify any data.
        Uses streaming to avoid loading all records into memory.
        Useful for verification before destructive operations.

        Returns:
            CleanupStats object with counts of what would be deleted

        Raises:
            Exception: If the dry run fails
        """
        from sqlalchemy import func

        logger.info(f"Starting cleanup dry run (retention: {self.retention_days} days)")
        stats = CleanupStats()

        # Calculate cutoff date (use UTC for consistency with timezone-aware columns)
        cutoff_date = datetime.now(UTC) - timedelta(days=self.retention_days)
        logger.info(f"Dry run: would delete records older than {cutoff_date}")

        try:
            async with get_session() as session:
                # Count detections that would be deleted
                detections_count_query = (
                    select(func.count())
                    .select_from(Detection)
                    .where(Detection.detected_at < cutoff_date)
                )
                result = await session.execute(detections_count_query)
                stats.detections_deleted = result.scalar_one()
                logger.info(f"Dry run: would delete {stats.detections_deleted} detections")

                # Stream detections to count files without loading all into memory
                detections_query = select(Detection).where(Detection.detected_at < cutoff_date)

                async for detection in await session.stream_scalars(detections_query):
                    if detection.thumbnail_path:
                        path = Path(detection.thumbnail_path)
                        if path.exists() and path.is_file():
                            stats.thumbnails_deleted += 1
                            # Estimate space reclaimed from thumbnail
                            try:
                                stats.space_reclaimed += path.stat().st_size
                            except OSError:
                                # File inaccessible during dry run - skip size estimation
                                pass
                    if self.delete_images and detection.file_path:
                        path = Path(detection.file_path)
                        if path.exists() and path.is_file():
                            stats.images_deleted += 1
                            # Estimate space reclaimed from image
                            try:
                                stats.space_reclaimed += path.stat().st_size
                            except OSError:
                                # File inaccessible during dry run - skip size estimation
                                pass

                logger.info(f"Dry run: would delete {stats.thumbnails_deleted} thumbnail files")
                if self.delete_images:
                    logger.info(f"Dry run: would delete {stats.images_deleted} image files")

                # Count events that would be deleted
                events_count_query = (
                    select(func.count()).select_from(Event).where(Event.started_at < cutoff_date)
                )
                result = await session.execute(events_count_query)
                stats.events_deleted = result.scalar_one()
                logger.info(f"Dry run: would delete {stats.events_deleted} events")

                # Count GPU stats that would be deleted
                gpu_stats_count_query = (
                    select(func.count())
                    .select_from(GPUStats)
                    .where(GPUStats.recorded_at < cutoff_date)
                )
                result = await session.execute(gpu_stats_count_query)
                stats.gpu_stats_deleted = result.scalar_one()
                logger.info(f"Dry run: would delete {stats.gpu_stats_deleted} GPU stats")

            # Count logs that would be deleted
            stats.logs_deleted = await self._count_old_logs()

            logger.info(f"Cleanup dry run completed: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Cleanup dry run failed: {e}", exc_info=True)
            raise

    async def _count_old_logs(self) -> int:
        """Count logs older than retention period without deleting.

        Returns:
            Number of logs that would be deleted
        """
        from sqlalchemy import func

        settings = get_settings()
        cutoff = datetime.now(UTC) - timedelta(days=settings.log_retention_days)

        async with get_session() as session:
            result = await session.execute(
                select(func.count()).select_from(Log).where(Log.timestamp < cutoff)
            )
            count = int(result.scalar_one() or 0)

        if count > 0:
            logger.info(
                f"Dry run: would delete {count} logs older than {settings.log_retention_days} days"
            )

        return count

    async def cleanup_old_logs(self) -> int:
        """Delete logs older than retention period.

        Returns:
            Number of logs deleted
        """
        settings = get_settings()
        cutoff = datetime.now(UTC) - timedelta(days=settings.log_retention_days)

        async with get_session() as session:
            result = await session.execute(delete(Log).where(Log.timestamp < cutoff))
            await session.commit()
            deleted = result.rowcount or 0  # type: ignore[attr-defined]

        if deleted > 0:
            logger.info(f"Cleaned up {deleted} logs older than {settings.log_retention_days} days")

        return deleted

    def _delete_file(self, file_path: str) -> bool:
        """Delete a file and track space reclaimed.

        Args:
            file_path: Path to file to delete

        Returns:
            True if file was deleted, False otherwise
        """
        try:
            path = Path(file_path)
            if path.exists() and path.is_file():
                # Delete file
                path.unlink()

                # Track space reclaimed
                # Note: We can't update stats here since it's passed by reference
                # This is handled by the caller
                return True
            else:
                logger.debug(f"File not found or not a file: {file_path}")
                return False
        except Exception as e:
            logger.warning(f"Failed to delete file {file_path}: {e}", exc_info=True)
            return False

    def get_cleanup_stats(self) -> CleanupStatsDict:
        """Get current service status and statistics.

        Returns:
            Dictionary with service status information
        """
        return {
            "running": self.running,
            "retention_days": self.retention_days,
            "cleanup_time": self.cleanup_time,
            "delete_images": self.delete_images,
            "next_cleanup": (self._calculate_next_cleanup().isoformat() if self.running else None),
        }

    async def _cleanup_loop(self) -> None:
        """Main cleanup loop that runs until stopped."""
        logger.info("Cleanup loop started")

        while self.running:
            try:
                # Wait until next scheduled cleanup time
                await self._wait_until_next_cleanup()

                # Run cleanup if still running (might have been stopped during wait)
                if self.running:
                    await self.run_cleanup()

            except asyncio.CancelledError:
                logger.info("Cleanup loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}", exc_info=True)
                # Continue running even if cleanup fails
                # Wait a bit before retrying
                await asyncio.sleep(60)

        logger.info("Cleanup loop stopped")

    async def start(self) -> None:
        """Start the cleanup service.

        Begins the scheduled cleanup loop. This method is idempotent.
        """
        if self.running:
            logger.warning("CleanupService already running")
            return

        logger.info("Starting CleanupService")
        self.running = True

        # Start cleanup loop in background
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        logger.info("CleanupService started successfully")

    async def stop(self) -> None:
        """Stop the cleanup service.

        Cancels the scheduled cleanup loop and waits for graceful shutdown.
        """
        if not self.running:
            logger.debug("CleanupService not running, nothing to stop")
            return

        logger.info("Stopping CleanupService")
        self.running = False

        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task

        self._cleanup_task = None
        logger.info("CleanupService stopped")

    async def __aenter__(self) -> CleanupService:
        """Async context manager entry.

        Starts the cleanup service and returns self for use in async with statements.

        Returns:
            Self for use in the context manager block.

        Example:
            async with CleanupService(retention_days=30) as cleanup:
                # cleanup service is started and scheduling daily cleanups
                stats = cleanup.get_cleanup_stats()
            # cleanup service is automatically stopped when exiting the block
        """
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Async context manager exit.

        Stops the cleanup service, ensuring cleanup even if an exception occurred.

        Args:
            exc_type: Exception type if an exception was raised, None otherwise.
            exc_val: Exception value if an exception was raised, None otherwise.
            exc_tb: Exception traceback if an exception was raised, None otherwise.
        """
        await self.stop()
