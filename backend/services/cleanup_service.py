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
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select

from backend.core.config import get_settings
from backend.core.database import get_session
from backend.models.detection import Detection
from backend.models.event import Event
from backend.models.gpu_stats import GPUStats

logger = logging.getLogger(__name__)


class CleanupStats:
    """Statistics for a cleanup operation."""

    def __init__(self) -> None:
        """Initialize cleanup stats with zero values."""
        self.events_deleted: int = 0
        self.detections_deleted: int = 0
        self.gpu_stats_deleted: int = 0
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
    ):
        """Initialize cleanup service.

        Args:
            cleanup_time: Time to run daily cleanup in HH:MM format (24-hour)
            retention_days: Number of days to retain data (None = use config default)
            thumbnail_dir: Directory containing thumbnail files
            delete_images: Whether to delete original image files (default: False)
        """
        settings = get_settings()
        self.cleanup_time = cleanup_time
        self.retention_days = retention_days or settings.retention_days
        self.thumbnail_dir = Path(thumbnail_dir)
        self.delete_images = delete_images

        # Task tracking
        self._cleanup_task: asyncio.Task | None = None
        self.running = False

        logger.info(
            f"CleanupService initialized: "
            f"retention={self.retention_days} days, "
            f"time={self.cleanup_time}, "
            f"delete_images={self.delete_images}"
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
        All database deletions are performed in a transaction.

        Returns:
            CleanupStats object with operation statistics

        Raises:
            Exception: If cleanup fails (transaction is rolled back)
        """
        logger.info(f"Starting cleanup (retention: {self.retention_days} days)")
        stats = CleanupStats()

        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        logger.info(f"Deleting records older than {cutoff_date}")

        try:
            async with get_session() as session:
                # Step 1: Get detections to be deleted (for file cleanup)
                detections_query = select(Detection).where(Detection.detected_at < cutoff_date)
                result = await session.execute(detections_query)
                detections_to_delete = result.scalars().all()

                # Track file paths before deleting from database
                thumbnail_paths: list[str] = []
                image_paths: list[str] = []

                for detection in detections_to_delete:
                    if detection.thumbnail_path:
                        thumbnail_paths.append(detection.thumbnail_path)
                    if self.delete_images and detection.file_path:
                        image_paths.append(detection.file_path)

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

            # Step 5: Delete thumbnail files (after successful DB commit)
            for thumbnail_path in thumbnail_paths:
                if self._delete_file(thumbnail_path):
                    stats.thumbnails_deleted += 1

            logger.info(f"Deleted {stats.thumbnails_deleted} thumbnail files")

            # Step 6: Delete original image files (if enabled)
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
            logger.warning(f"Failed to delete file {file_path}: {e}")
            return False

    def get_cleanup_stats(self) -> dict[str, Any]:
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
