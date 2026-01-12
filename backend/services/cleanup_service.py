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
    - Job status tracking via Redis for monitoring (NEM-2292)

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

    from backend.core.redis import RedisClient
    from backend.services.job_status import JobStatusService
    from backend.services.job_tracker import JobTracker

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
        redis_client: RedisClient | None = None,
    ):
        """Initialize cleanup service.

        Args:
            cleanup_time: Time to run daily cleanup in HH:MM format (24-hour)
            retention_days: Number of days to retain data (None = use config default)
            thumbnail_dir: Directory containing thumbnail files
            delete_images: Whether to delete original image files (default: False)
            batch_size: Number of records to process per batch (default: 1000).
                        Used for streaming queries to limit memory usage.
            redis_client: Optional Redis client for job status tracking.
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

        # Optional Redis client for job status tracking
        self._redis_client = redis_client
        self._job_status_service: JobStatusService | None = None

        logger.info(
            f"CleanupService initialized: "
            f"retention={self.retention_days} days, "
            f"time={self.cleanup_time}, "
            f"delete_images={self.delete_images}, "
            f"batch_size={self.batch_size}"
        )

    def _get_job_status_service(self) -> JobStatusService | None:
        """Get job status service if Redis is available.

        Returns:
            JobStatusService instance or None if Redis not configured.
        """
        if self._redis_client is None:
            return None

        if self._job_status_service is None:
            from backend.services.job_status import get_job_status_service

            self._job_status_service = get_job_status_service(self._redis_client)
        return self._job_status_service

    def set_redis_client(self, redis_client: RedisClient) -> None:
        """Set the Redis client for job status tracking.

        This allows configuring Redis after initialization.

        Args:
            redis_client: Redis client instance.
        """
        self._redis_client = redis_client
        self._job_status_service = None  # Reset to recreate with new client

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

    async def run_cleanup(self) -> CleanupStats:  # noqa: PLR0912
        """Execute cleanup operation.

        Deletes old records and files based on retention policy.
        Uses streaming queries to avoid loading all records into memory.
        Tracks job status in Redis if available.

        Returns:
            CleanupStats object with operation statistics

        Raises:
            Exception: If cleanup fails (transaction is rolled back)
        """
        logger.info(f"Starting cleanup (retention: {self.retention_days} days)")
        stats = CleanupStats()

        # Start job tracking if Redis is available
        job_service = self._get_job_status_service()
        job_id: str | None = None
        if job_service is not None:
            job_id = await job_service.start_job(
                job_id=f"cleanup-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}",
                job_type="data_cleanup",
                metadata={"retention_days": self.retention_days},
            )

        # Calculate cutoff date (use UTC for consistency with timezone-aware columns)
        cutoff_date = datetime.now(UTC) - timedelta(days=self.retention_days)
        logger.info(f"Deleting records older than {cutoff_date}")

        try:
            if job_service is not None and job_id is not None:
                await job_service.update_progress(job_id, 5, "Scanning for files to delete")

            async with get_session() as session:
                # Step 1: Stream detection file paths without loading all into memory
                thumbnail_paths, image_paths = await self._get_detection_file_paths_streaming(
                    session, cutoff_date
                )

                if job_service is not None and job_id is not None:
                    await job_service.update_progress(job_id, 15, "Deleting old detections")

                # Step 2: Delete old detections
                delete_detections_stmt = delete(Detection).where(
                    Detection.detected_at < cutoff_date
                )
                detections_result = await session.execute(delete_detections_stmt)
                stats.detections_deleted = detections_result.rowcount or 0  # type: ignore[attr-defined]
                logger.info(f"Deleted {stats.detections_deleted} old detections")

                if job_service is not None and job_id is not None:
                    await job_service.update_progress(job_id, 30, "Deleting old events")

                # Step 3: Delete old events
                delete_events_stmt = delete(Event).where(Event.started_at < cutoff_date)
                events_result = await session.execute(delete_events_stmt)
                stats.events_deleted = events_result.rowcount or 0  # type: ignore[attr-defined]
                logger.info(f"Deleted {stats.events_deleted} old events")

                if job_service is not None and job_id is not None:
                    await job_service.update_progress(job_id, 45, "Deleting old GPU stats")

                # Step 4: Delete old GPU stats
                delete_gpu_stats_stmt = delete(GPUStats).where(GPUStats.recorded_at < cutoff_date)
                gpu_stats_result = await session.execute(delete_gpu_stats_stmt)
                stats.gpu_stats_deleted = gpu_stats_result.rowcount or 0  # type: ignore[attr-defined]
                logger.info(f"Deleted {stats.gpu_stats_deleted} old GPU stats")

                # Commit database deletions
                await session.commit()
                logger.info("Database cleanup committed successfully")

            if job_service is not None and job_id is not None:
                await job_service.update_progress(job_id, 55, "Deleting old logs")

            # Step 5: Delete old logs
            stats.logs_deleted = await self.cleanup_old_logs()

            if job_service is not None and job_id is not None:
                await job_service.update_progress(job_id, 70, "Deleting thumbnail files")

            # Step 6: Delete thumbnail files (after successful DB commit)
            for thumbnail_path in thumbnail_paths:
                if self._delete_file(thumbnail_path):
                    stats.thumbnails_deleted += 1

            logger.info(f"Deleted {stats.thumbnails_deleted} thumbnail files")

            # Step 7: Delete original image files (if enabled)
            if self.delete_images:
                if job_service is not None and job_id is not None:
                    await job_service.update_progress(job_id, 85, "Deleting image files")

                for image_path in image_paths:
                    if self._delete_file(image_path):
                        stats.images_deleted += 1

                logger.info(f"Deleted {stats.images_deleted} original image files")

            # Mark job as completed
            if job_service is not None and job_id is not None:
                await job_service.complete_job(job_id, result=stats.to_dict())

            logger.info(f"Cleanup completed: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Cleanup failed: {e}", exc_info=True)
            # Mark job as failed
            if job_service is not None and job_id is not None:
                await job_service.fail_job(job_id, str(e))
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


def format_bytes(size: int) -> str:
    """Convert bytes to human-readable format.

    Args:
        size: Size in bytes

    Returns:
        Human-readable string (e.g., "1.5 GB", "500 MB")
    """
    if size < 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    unit_index = 0

    size_float = float(size)
    while size_float >= 1024 and unit_index < len(units) - 1:
        size_float /= 1024
        unit_index += 1

    if unit_index == 0:
        return f"{int(size_float)} {units[unit_index]}"
    return f"{size_float:.2f} {units[unit_index]}"


class OrphanedFileCleanupStats:
    """Statistics for an orphaned file cleanup operation."""

    def __init__(self) -> None:
        """Initialize cleanup stats with zero values."""
        self.orphaned_count: int = 0
        self.total_size: int = 0
        self.dry_run: bool = True
        self.orphaned_files: list[str] = []

    def to_dict(self) -> dict[str, int | bool | str | list[str]]:
        """Convert stats to dictionary.

        Returns:
            Dictionary with all cleanup statistics
        """
        return {
            "orphaned_count": self.orphaned_count,
            "total_size": self.total_size,
            "total_size_formatted": format_bytes(self.total_size),
            "dry_run": self.dry_run,
            "orphaned_files": self.orphaned_files[:100],  # Limit to first 100 files
        }

    def __repr__(self) -> str:
        """String representation of cleanup stats."""
        return (
            f"<OrphanedFileCleanupStats("
            f"orphaned_count={self.orphaned_count}, "
            f"total_size={format_bytes(self.total_size)}, "
            f"dry_run={self.dry_run})>"
        )


class OrphanedFileCleanup:
    """Service for finding and cleaning up orphaned files.

    Orphaned files are files that exist on disk but are not referenced
    in the database (Events, Detections tables).

    This service:
    - Scans configured storage directories recursively
    - Compares files against database references
    - Optionally deletes orphaned files (when dry_run=False)
    - Reports progress via job_tracker

    Storage directories scanned:
    - Thumbnails directory (video_thumbnails_dir setting)
    - Clips directory (clips_directory setting)
    """

    def __init__(
        self,
        job_tracker: JobTracker | None = None,
        storage_paths: list[str] | None = None,
    ):
        """Initialize orphaned file cleanup service.

        Args:
            job_tracker: Optional job tracker for progress reporting.
                        If None, progress is only logged.
            storage_paths: List of directories to scan for orphaned files.
                          If None, uses settings defaults (thumbnails, clips).
        """
        self._job_tracker = job_tracker
        self._storage_paths = storage_paths or self._get_default_storage_paths()

        logger.info(f"OrphanedFileCleanup initialized with storage paths: {self._storage_paths}")

    def _get_default_storage_paths(self) -> list[str]:
        """Get default storage paths from settings.

        Returns:
            List of storage directory paths to scan
        """
        settings = get_settings()
        paths = []

        # Add thumbnails directory
        if settings.video_thumbnails_dir:
            paths.append(settings.video_thumbnails_dir)

        # Add clips directory
        if settings.clips_directory:
            paths.append(settings.clips_directory)

        return paths

    async def _get_referenced_files(self) -> set[str]:
        """Query all file paths referenced in the database.

        Queries:
        - Detection.file_path (source images)
        - Detection.thumbnail_path (thumbnails)
        - Event.clip_path (generated clips)

        Returns:
            Set of all referenced file paths (absolute paths)
        """
        referenced: set[str] = set()

        async with get_session() as session:
            # Get detection file paths
            detection_query = select(Detection.file_path, Detection.thumbnail_path)
            result = await session.execute(detection_query)

            for file_path, thumbnail_path in result.all():
                if file_path:
                    # Convert to absolute path if relative
                    abs_path = str(Path(file_path).resolve())
                    referenced.add(abs_path)
                if thumbnail_path:
                    abs_path = str(Path(thumbnail_path).resolve())
                    referenced.add(abs_path)

            # Get event clip paths
            event_query = select(Event.clip_path).where(Event.clip_path.isnot(None))
            result = await session.execute(event_query)

            for (clip_path,) in result.all():
                if clip_path:
                    abs_path = str(Path(clip_path).resolve())
                    referenced.add(abs_path)

        return referenced

    def _scan_storage_directories(self) -> list[tuple[str, int]]:
        """Scan storage directories recursively for all files.

        Returns:
            List of tuples (file_path, file_size) for all files found
        """
        files_found: list[tuple[str, int]] = []

        for storage_path in self._storage_paths:
            path = Path(storage_path)
            if not path.exists():
                logger.warning(f"Storage path does not exist: {storage_path}")
                continue

            if not path.is_dir():
                logger.warning(f"Storage path is not a directory: {storage_path}")
                continue

            # Recursively find all files
            for file_path in path.rglob("*"):
                if file_path.is_file():
                    try:
                        file_size = file_path.stat().st_size
                        abs_path = str(file_path.resolve())
                        files_found.append((abs_path, file_size))
                    except OSError as e:
                        logger.warning(f"Could not stat file {file_path}: {e}")

        return files_found

    def _update_job_progress(self, job_id: str | None, progress: int, message: str) -> None:
        """Update job progress if job tracker is available.

        Args:
            job_id: The job ID, or None if no job tracking
            progress: Progress percentage (0-100)
            message: Status message
        """
        if job_id and self._job_tracker:
            self._job_tracker.update_progress(job_id, progress, message)

    def _delete_orphaned_files(self, orphaned_files: list[tuple[str, int]]) -> int:
        """Delete orphaned files and return count of successfully deleted.

        Args:
            orphaned_files: List of (file_path, file_size) tuples

        Returns:
            Number of files successfully deleted
        """
        deleted_count = 0
        for file_path, _ in orphaned_files:
            try:
                Path(file_path).unlink()
                deleted_count += 1
            except OSError as e:
                logger.warning(f"Failed to delete orphaned file {file_path}: {e}")
        return deleted_count

    async def run_cleanup(self, dry_run: bool = True) -> OrphanedFileCleanupStats:
        """Execute orphaned file cleanup operation.

        Args:
            dry_run: If True, only report what would be deleted without
                    actually deleting files. Default is True for safety.

        Returns:
            OrphanedFileCleanupStats with operation statistics
        """
        job_id: str | None = None
        if self._job_tracker:
            job_id = self._job_tracker.create_job("orphaned_file_cleanup")
            self._job_tracker.start_job(job_id, "Starting orphaned file cleanup")

        stats = OrphanedFileCleanupStats()
        stats.dry_run = dry_run

        try:
            # Step 1: Get all referenced files from database
            self._update_job_progress(job_id, 10, "Querying database for referenced files")
            logger.info("Querying database for referenced files...")
            referenced_files = await self._get_referenced_files()
            logger.info(f"Found {len(referenced_files)} referenced files in database")

            # Step 2: Scan storage directories
            self._update_job_progress(job_id, 30, "Scanning storage directories")
            logger.info(f"Scanning storage directories: {self._storage_paths}")
            all_files = self._scan_storage_directories()
            logger.info(f"Found {len(all_files)} files on disk")

            # Step 3: Find orphaned files
            self._update_job_progress(job_id, 50, "Identifying orphaned files")
            orphaned_files: list[tuple[str, int]] = []
            for file_path, file_size in all_files:
                if file_path not in referenced_files:
                    orphaned_files.append((file_path, file_size))
                    stats.orphaned_files.append(file_path)
                    stats.total_size += file_size

            stats.orphaned_count = len(orphaned_files)
            logger.info(
                f"Found {stats.orphaned_count} orphaned files ({format_bytes(stats.total_size)})"
            )

            # Step 4: Delete orphaned files if not dry run
            if not dry_run and orphaned_files:
                self._update_job_progress(job_id, 70, "Deleting orphaned files")
                deleted_count = self._delete_orphaned_files(orphaned_files)
                logger.info(f"Deleted {deleted_count} of {stats.orphaned_count} orphaned files")

            # Complete job
            if job_id and self._job_tracker:
                result = stats.to_dict()
                self._job_tracker.complete_job(job_id, result)

            logger.info(f"Orphaned file cleanup completed: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Orphaned file cleanup failed: {e}", exc_info=True)
            if job_id and self._job_tracker:
                self._job_tracker.fail_job(job_id, str(e))
            raise
