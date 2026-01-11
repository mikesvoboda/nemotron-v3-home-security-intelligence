"""Orphaned file cleanup service for removing files without database records.

This service periodically scans for orphaned files (files on disk without
corresponding database records) and cleans them up. It helps maintain disk
space by removing files that are no longer referenced.

Features:
    - Configurable scan interval (default: 24 hours)
    - Configurable age threshold before deletion (default: 24 hours)
    - Integration with job tracking system for progress monitoring
    - WebSocket notification on cleanup completion
    - Safe deletion with file age verification
    - Detailed statistics on cleanup operations

Related Issues:
    - NEM-2260: Implement orphaned file cleanup background job
"""

from __future__ import annotations

import asyncio
import contextlib
import re
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from backend.core.config import get_settings
from backend.core.database import get_session
from backend.core.logging import get_logger
from backend.models.event import Event

if TYPE_CHECKING:
    from backend.services.job_tracker import JobTracker

logger = get_logger(__name__)


# Type alias for broadcast callback
BroadcastCallback = Callable[[str, dict[str, Any]], None | Awaitable[None]]

# Job type constant for job tracker
JOB_TYPE_ORPHAN_CLEANUP = "orphan_cleanup"

# File extensions to scan for clip files
CLIP_FILE_EXTENSIONS = {".mp4", ".webm", ".mkv", ".avi"}


class OrphanedFileCleanupStats:
    """Statistics for an orphan cleanup operation."""

    def __init__(self) -> None:
        """Initialize cleanup stats with zero values."""
        self.files_scanned: int = 0
        self.orphans_found: int = 0
        self.files_deleted: int = 0
        self.files_skipped_young: int = 0
        self.space_reclaimed: int = 0

    def to_dict(self) -> dict[str, int]:
        """Convert stats to dictionary.

        Returns:
            Dictionary with all cleanup statistics
        """
        return {
            "files_scanned": self.files_scanned,
            "orphans_found": self.orphans_found,
            "files_deleted": self.files_deleted,
            "files_skipped_young": self.files_skipped_young,
            "space_reclaimed": self.space_reclaimed,
        }

    def __repr__(self) -> str:
        """String representation of cleanup stats."""
        return (
            f"<OrphanedFileCleanupStats(scanned={self.files_scanned}, "
            f"orphans={self.orphans_found}, "
            f"deleted={self.files_deleted}, "
            f"skipped_young={self.files_skipped_young}, "
            f"space={self.space_reclaimed} bytes)>"
        )


class OrphanedFileCleanupService:
    """Service for periodic cleanup of orphaned files.

    This service scans configured directories for files that have no
    corresponding database records and deletes them after a configurable
    age threshold. This helps reclaim disk space from files that were
    left behind due to interrupted processing or database inconsistencies.

    Configuration:
        scan_interval_hours: How often to run cleanup (default: 24)
        age_threshold_hours: Minimum file age before deletion (default: 24)
        clips_directory: Directory to scan for orphaned clips
        enabled: Whether cleanup is enabled (default: True)
    """

    def __init__(
        self,
        scan_interval_hours: int | None = None,
        age_threshold_hours: int | None = None,
        clips_directory: str | None = None,
        enabled: bool | None = None,
        job_tracker: JobTracker | None = None,
        broadcast_callback: BroadcastCallback | None = None,
    ) -> None:
        """Initialize the orphan cleanup service.

        Args:
            scan_interval_hours: Hours between cleanup scans. If None, uses config default.
            age_threshold_hours: Minimum hours before orphan can be deleted. If None, uses config default.
            clips_directory: Directory to scan for orphaned clips. If None, uses config default.
            enabled: Whether cleanup is enabled. If None, uses config default.
            job_tracker: Optional job tracker for progress monitoring.
            broadcast_callback: Optional callback for WebSocket notifications.
        """
        settings = get_settings()

        self.scan_interval_hours = (
            scan_interval_hours
            if scan_interval_hours is not None
            else getattr(settings, "orphan_cleanup_scan_interval_hours", 24)
        )
        self.age_threshold_hours = (
            age_threshold_hours
            if age_threshold_hours is not None
            else getattr(settings, "orphan_cleanup_age_threshold_hours", 24)
        )
        self.clips_directory = Path(
            clips_directory if clips_directory is not None else settings.clips_directory
        )
        self.enabled = (
            enabled if enabled is not None else getattr(settings, "orphan_cleanup_enabled", True)
        )

        self._job_tracker = job_tracker
        self._broadcast_callback = broadcast_callback

        # Task tracking
        self._cleanup_task: asyncio.Task | None = None
        self.running = False

        logger.info(
            f"OrphanedFileCleanupService initialized: "
            f"interval={self.scan_interval_hours}h, "
            f"age_threshold={self.age_threshold_hours}h, "
            f"clips_dir={self.clips_directory}, "
            f"enabled={self.enabled}"
        )

    def _scan_clip_files(self) -> list[Path]:
        """Scan the clips directory for all clip files.

        Returns:
            List of paths to clip files found in the directory.
        """
        if not self.clips_directory.exists():
            logger.debug(f"Clips directory does not exist: {self.clips_directory}")
            return []

        files: list[Path] = []
        try:
            for ext in CLIP_FILE_EXTENSIONS:
                files.extend(self.clips_directory.glob(f"**/*{ext}"))
        except PermissionError as e:
            logger.warning(f"Permission denied scanning clips directory: {e}")
            return []
        except Exception as e:
            logger.warning(f"Error scanning clips directory: {e}")
            return []

        logger.debug(f"Found {len(files)} clip files in {self.clips_directory}")
        return files

    def _is_file_old_enough(self, file_path: Path) -> bool:
        """Check if a file is old enough to be deleted.

        Args:
            file_path: Path to the file to check.

        Returns:
            True if file is older than age_threshold_hours, False otherwise.
        """
        try:
            mtime = file_path.stat().st_mtime
            file_age_hours = (datetime.now().timestamp() - mtime) / 3600
            return file_age_hours >= self.age_threshold_hours
        except (OSError, FileNotFoundError) as e:
            logger.debug(f"Could not check file age for {file_path}: {e}")
            return False

    def _extract_event_id_from_path(self, file_path: str) -> int | None:
        """Extract event ID from a clip file path.

        Clip files are typically named with event ID, e.g.:
        - event_123.mp4
        - clip_event_456.mp4
        - 789_clip.webm

        Args:
            file_path: Path to the clip file.

        Returns:
            Event ID if found in path, None otherwise.
        """
        # Try various patterns to extract event ID
        path = Path(file_path)
        filename = path.stem  # filename without extension

        # Pattern 1: event_<id> or clip_event_<id>
        match = re.search(r"event[_-]?(\d+)", filename, re.IGNORECASE)
        if match:
            return int(match.group(1))

        # Pattern 2: <id>_clip or <id>_event
        match = re.search(r"^(\d+)[_-]", filename)
        if match:
            return int(match.group(1))

        # Pattern 3: Just a number (entire filename is event ID)
        match = re.match(r"^(\d+)$", filename)
        if match:
            return int(match.group(1))

        return None

    async def _is_orphan(self, file_path: str) -> bool:
        """Check if a file is an orphan (no corresponding database record).

        A file is considered an orphan if:
        1. We can extract an event ID from its path
        2. That event ID does not exist in the database
        3. OR the event exists but has no reference to this file

        Args:
            file_path: Path to the file to check.

        Returns:
            True if file is an orphan, False if it has a database record.
        """
        event_id = self._extract_event_id_from_path(file_path)
        if event_id is None:
            # Can't determine event ID - assume it's an orphan if it's not in the clip paths
            logger.debug(f"Could not extract event ID from {file_path}, checking clip_path")
            return await self._check_file_not_in_database(file_path)

        # Check if event exists in database
        try:
            async with get_session() as session:
                result = await session.execute(select(Event.id).where(Event.id == event_id))
                event = result.scalar_one_or_none()

                if event is None:
                    logger.debug(f"Event {event_id} not found - file is orphan: {file_path}")
                    return True

                # Event exists, check if this file is referenced
                result = await session.execute(select(Event.id).where(Event.clip_path == file_path))
                clip_record = result.scalar_one_or_none()

                if clip_record is None:
                    logger.debug(f"File not referenced by event {event_id} - orphan: {file_path}")
                    return True

                return False

        except Exception as e:
            logger.error(f"Error checking orphan status for {file_path}: {e}")
            # On error, don't delete the file (safer to keep it)
            return False

    async def _check_file_not_in_database(self, file_path: str) -> bool:
        """Check if a file path is not referenced in the database.

        Args:
            file_path: Path to check.

        Returns:
            True if file is not in database, False otherwise.
        """
        try:
            async with get_session() as session:
                result = await session.execute(select(Event.id).where(Event.clip_path == file_path))
                return result.scalar_one_or_none() is None
        except Exception as e:
            logger.error(f"Error checking database for {file_path}: {e}")
            return False

    def _delete_file(self, file_path: Path) -> tuple[bool, int]:
        """Delete a file and return the space reclaimed.

        Args:
            file_path: Path to the file to delete.

        Returns:
            Tuple of (success, bytes_reclaimed).
        """
        try:
            if not file_path.exists():
                return False, 0

            size = file_path.stat().st_size
            file_path.unlink()
            logger.debug(f"Deleted orphan file: {file_path} ({size} bytes)")
            return True, size
        except Exception as e:
            logger.warning(f"Failed to delete file {file_path}: {e}")
            return False, 0

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
                "Failed to broadcast orphan cleanup event",
                extra={"event_type": event_type, "error": str(e)},
            )

    async def run_cleanup(self) -> OrphanedFileCleanupStats:
        """Execute orphan cleanup operation.

        Scans the clips directory for orphaned files and deletes those
        that are old enough.

        Returns:
            OrphanedFileCleanupStats with operation statistics.

        Raises:
            Exception: If cleanup fails critically (job is marked as failed).
        """
        stats = OrphanedFileCleanupStats()
        job_id: str | None = None

        # Create job if tracker available
        if self._job_tracker:
            job_id = self._job_tracker.create_job(JOB_TYPE_ORPHAN_CLEANUP)
            self._job_tracker.start_job(job_id, message="Starting orphan cleanup scan")

        try:
            logger.info(f"Starting orphan cleanup (age_threshold: {self.age_threshold_hours}h)")

            # Scan for files
            files = self._scan_clip_files()
            stats.files_scanned = len(files)

            if not files:
                logger.info("No clip files found to check")
                if self._job_tracker and job_id:
                    self._job_tracker.complete_job(job_id, result=stats.to_dict())
                self._broadcast_completion(stats)
                return stats

            # Process each file
            for i, file_path in enumerate(files):
                try:
                    # Update progress
                    if self._job_tracker and job_id:
                        progress = int((i + 1) / len(files) * 90)  # Reserve 10% for cleanup
                        self._job_tracker.update_progress(
                            job_id, progress, message=f"Checking file {i + 1}/{len(files)}"
                        )

                    # Check if file is old enough
                    if not self._is_file_old_enough(file_path):
                        stats.files_skipped_young += 1
                        continue

                    # Check if file is orphan
                    if await self._is_orphan(str(file_path)):
                        stats.orphans_found += 1

                        # Delete the file
                        deleted, size = self._delete_file(file_path)
                        if deleted:
                            stats.files_deleted += 1
                            stats.space_reclaimed += size

                except Exception as e:
                    logger.warning(f"Error processing file {file_path}: {e}")
                    # Continue with next file

            logger.info(f"Orphan cleanup completed: {stats}")

            # Complete job
            if self._job_tracker and job_id:
                self._job_tracker.complete_job(job_id, result=stats.to_dict())

            # Broadcast completion
            self._broadcast_completion(stats)

            return stats

        except Exception as e:
            logger.error(f"Orphan cleanup failed: {e}", exc_info=True)

            # Fail job
            if self._job_tracker and job_id:
                self._job_tracker.fail_job(job_id, str(e))

            raise

    def _broadcast_completion(self, stats: OrphanedFileCleanupStats) -> None:
        """Broadcast cleanup completion notification.

        Args:
            stats: Cleanup statistics to include in notification.
        """
        self._broadcast(
            "orphan_cleanup_completed",
            {
                "type": "orphan_cleanup_completed",
                "data": {
                    "stats": stats.to_dict(),
                    "timestamp": datetime.now().isoformat(),
                },
            },
        )

    async def _cleanup_loop(self) -> None:
        """Main cleanup loop that runs periodically."""
        logger.info("Orphan cleanup loop started")

        while self.running:
            try:
                # Run cleanup
                await self.run_cleanup()

                # Wait for next scan
                wait_seconds = self.scan_interval_hours * 3600
                logger.info(f"Next orphan cleanup in {self.scan_interval_hours} hours")
                await asyncio.sleep(wait_seconds)

            except asyncio.CancelledError:
                logger.info("Orphan cleanup loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in orphan cleanup loop: {e}", exc_info=True)
                # Wait before retrying
                await asyncio.sleep(60)

        logger.info("Orphan cleanup loop stopped")

    async def start(self) -> None:
        """Start the orphan cleanup service.

        Begins the scheduled cleanup loop. This method is idempotent.
        """
        if self.running:
            logger.warning("OrphanedFileCleanupService already running")
            return

        if not self.enabled:
            logger.info("OrphanedFileCleanupService is disabled, not starting")
            return

        logger.info("Starting OrphanedFileCleanupService")
        self.running = True

        # Start cleanup loop in background
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        logger.info("OrphanedFileCleanupService started successfully")

    async def stop(self) -> None:
        """Stop the orphan cleanup service.

        Cancels the scheduled cleanup loop and waits for graceful shutdown.
        """
        if not self.running:
            logger.debug("OrphanedFileCleanupService not running, nothing to stop")
            return

        logger.info("Stopping OrphanedFileCleanupService")
        self.running = False

        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task

        self._cleanup_task = None
        logger.info("OrphanedFileCleanupService stopped")

    async def __aenter__(self) -> OrphanedFileCleanupService:
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

    def get_status(self) -> dict[str, Any]:
        """Get current service status.

        Returns:
            Dictionary with service status information.
        """
        return {
            "running": self.running,
            "enabled": self.enabled,
            "scan_interval_hours": self.scan_interval_hours,
            "age_threshold_hours": self.age_threshold_hours,
            "clips_directory": str(self.clips_directory),
        }


# Module-level singleton
_orphan_cleanup_service: OrphanedFileCleanupService | None = None


def get_orphan_cleanup_service(
    scan_interval_hours: int | None = None,
    age_threshold_hours: int | None = None,
    clips_directory: str | None = None,
    enabled: bool | None = None,
    job_tracker: JobTracker | None = None,
    broadcast_callback: BroadcastCallback | None = None,
) -> OrphanedFileCleanupService:
    """Get or create the singleton orphan cleanup service instance.

    Args:
        scan_interval_hours: Hours between cleanup scans.
        age_threshold_hours: Minimum hours before orphan can be deleted.
        clips_directory: Directory to scan for orphaned clips.
        enabled: Whether cleanup is enabled.
        job_tracker: Optional job tracker for progress monitoring.
        broadcast_callback: Optional callback for WebSocket notifications.

    Returns:
        The orphan cleanup service singleton.
    """
    global _orphan_cleanup_service  # noqa: PLW0603
    if _orphan_cleanup_service is None:
        _orphan_cleanup_service = OrphanedFileCleanupService(
            scan_interval_hours=scan_interval_hours,
            age_threshold_hours=age_threshold_hours,
            clips_directory=clips_directory,
            enabled=enabled,
            job_tracker=job_tracker,
            broadcast_callback=broadcast_callback,
        )
    return _orphan_cleanup_service


def reset_orphan_cleanup_service() -> None:
    """Reset the orphan cleanup service singleton. Used for testing."""
    global _orphan_cleanup_service  # noqa: PLW0603
    _orphan_cleanup_service = None
