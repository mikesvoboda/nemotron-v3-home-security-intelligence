"""Orphan cleanup job for removing orphaned files from disk.

This job periodically scans for and removes files that have no corresponding
database records. It uses the OrphanedFileScanner to identify orphaned files
and applies safety measures before deletion.

Safety measures:
    - Age threshold: Only delete files older than configurable threshold (default 24h)
    - Dry run mode: Log what would be deleted without actually deleting
    - Size limit: Stop if would delete more than configurable limit in one run
    - File patterns: Only process known file patterns (images/videos)

Related Issues:
    - NEM-2387: Implement orphaned file cleanup background job
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.services.orphan_scanner_service import OrphanedFile, OrphanedFileScanner

if TYPE_CHECKING:
    from backend.services.job_tracker import JobTracker

logger = get_logger(__name__)

# Default configuration values
DEFAULT_MIN_AGE_HOURS = 24
DEFAULT_MAX_DELETE_GB = 10.0  # Maximum GB to delete in one run

# Job type constant for job tracker
JOB_TYPE_ORPHAN_CLEANUP = "orphan_cleanup"


@dataclass
class CleanupReport:
    """Report generated after an orphan cleanup operation.

    Attributes:
        scanned_files: Total number of files scanned
        orphaned_files: Number of orphaned files found
        deleted_files: Number of files actually deleted
        deleted_bytes: Total bytes deleted
        failed_deletions: List of files that failed to delete
        duration_seconds: Time taken for the cleanup operation
        dry_run: Whether this was a dry run (no actual deletions)
        skipped_young: Files skipped because they were too young
        skipped_size_limit: Files skipped due to size limit
    """

    scanned_files: int = 0
    orphaned_files: int = 0
    deleted_files: int = 0
    deleted_bytes: int = 0
    failed_deletions: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    dry_run: bool = True
    skipped_young: int = 0
    skipped_size_limit: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "scanned_files": self.scanned_files,
            "orphaned_files": self.orphaned_files,
            "deleted_files": self.deleted_files,
            "deleted_bytes": self.deleted_bytes,
            "deleted_bytes_formatted": self._format_bytes(self.deleted_bytes),
            "failed_deletions": self.failed_deletions[:50],  # Limit to 50
            "failed_count": len(self.failed_deletions),
            "duration_seconds": round(self.duration_seconds, 2),
            "dry_run": self.dry_run,
            "skipped_young": self.skipped_young,
            "skipped_size_limit": self.skipped_size_limit,
        }

    @staticmethod
    def _format_bytes(size: int) -> str:
        """Format bytes into human-readable string."""
        if size < 0:
            return "0 B"
        units = ["B", "KB", "MB", "GB", "TB"]
        unit_index = 0
        size_float = float(size)
        while size_float >= 1024 and unit_index < len(units) - 1:
            size_float /= 1024
            unit_index += 1
        if unit_index == 0:
            return f"{int(size_float)} {units[unit_index]}"
        return f"{size_float:.2f} {units[unit_index]}"

    def __repr__(self) -> str:
        """String representation of cleanup report."""
        return (
            f"<CleanupReport(scanned={self.scanned_files}, "
            f"orphaned={self.orphaned_files}, "
            f"deleted={self.deleted_files}, "
            f"bytes={self._format_bytes(self.deleted_bytes)}, "
            f"dry_run={self.dry_run})>"
        )


class OrphanCleanupJob:
    """Background job for cleaning up orphaned files.

    This job uses the OrphanedFileScanner to identify orphaned files
    and then deletes them according to configured safety rules.

    Safety features:
    - Age threshold: Only delete files older than min_age (default 24 hours)
    - Dry run mode: When enabled, only logs what would be deleted
    - Size limit: Stops if cumulative deletion would exceed max_delete_bytes
    - Job tracking: Progress and status reported via JobTracker

    Example usage:
        job = OrphanCleanupJob(min_age_hours=24, dry_run=False)
        report = await job.run()
        print(f"Deleted {report.deleted_files} files")
    """

    def __init__(
        self,
        min_age_hours: int = DEFAULT_MIN_AGE_HOURS,
        dry_run: bool = True,
        max_delete_gb: float = DEFAULT_MAX_DELETE_GB,
        scanner: OrphanedFileScanner | None = None,
        job_tracker: JobTracker | None = None,
        base_path: str | Path | None = None,
    ) -> None:
        """Initialize the orphan cleanup job.

        Args:
            min_age_hours: Minimum age in hours before a file can be deleted.
                          Files younger than this are skipped to avoid race
                          conditions with active processing. Default: 24 hours.
            dry_run: If True, only log what would be deleted without actually
                    deleting files. Default: True for safety.
            max_delete_gb: Maximum gigabytes to delete in a single run. If this
                          limit is reached, remaining files are skipped. This
                          prevents accidentally deleting too much data. Default: 10 GB.
            scanner: Optional OrphanedFileScanner instance. If None, one is created.
            job_tracker: Optional JobTracker for progress reporting.
            base_path: Base path to scan. If None, uses settings default.
        """
        self.min_age = timedelta(hours=min_age_hours)
        self.dry_run = dry_run
        self.max_delete_bytes = int(max_delete_gb * 1024 * 1024 * 1024)
        self._scanner = scanner or OrphanedFileScanner(base_path=base_path)
        self._job_tracker = job_tracker

        logger.info(
            f"OrphanCleanupJob initialized: min_age={min_age_hours}h, "
            f"dry_run={dry_run}, max_delete={max_delete_gb}GB"
        )

    def _should_delete(self, orphan: OrphanedFile) -> tuple[bool, str]:
        """Determine if an orphaned file should be deleted.

        Applies age threshold check.

        Args:
            orphan: The orphaned file to check

        Returns:
            Tuple of (should_delete, reason_if_skipped)
        """
        if orphan.age < self.min_age:
            return False, f"File too young: age={orphan.age}, min_age={self.min_age}"

        return True, ""

    def _delete_file(self, path: Path) -> tuple[bool, int]:
        """Delete a file and return the bytes freed.

        Args:
            path: Path to the file to delete

        Returns:
            Tuple of (success, bytes_freed)
        """
        try:
            if not path.exists():
                return False, 0

            size = path.stat().st_size
            path.unlink()

            logger.debug(f"Deleted orphan file: {path} ({size} bytes)")
            return True, size
        except PermissionError as e:
            logger.warning(f"Permission denied deleting {path}: {e}")
            return False, 0
        except OSError as e:
            logger.warning(f"Failed to delete {path}: {e}")
            return False, 0

    def _update_job_progress(self, job_id: str | None, progress: int, message: str) -> None:
        """Update job tracker progress if available."""
        if self._job_tracker and job_id:
            self._job_tracker.update_progress(job_id, progress, message)

    def _complete_job(self, job_id: str | None, report: CleanupReport) -> None:
        """Complete job tracking if available."""
        if self._job_tracker and job_id:
            self._job_tracker.complete_job(job_id, result=report.to_dict())

    def _process_orphan_dry_run(self, orphan: OrphanedFile, report: CleanupReport) -> int:
        """Process an orphan in dry run mode. Returns bytes that would be freed."""
        logger.info(f"[DRY RUN] Would delete: {orphan.path} ({orphan.size_bytes} bytes)")
        report.deleted_files += 1
        report.deleted_bytes += orphan.size_bytes
        return orphan.size_bytes

    def _process_orphan_actual(self, orphan: OrphanedFile, report: CleanupReport) -> int:
        """Process an orphan by actually deleting it. Returns bytes freed."""
        success, freed_bytes = self._delete_file(orphan.path)
        if success:
            report.deleted_files += 1
            report.deleted_bytes += freed_bytes
            return freed_bytes
        report.failed_deletions.append(str(orphan.path))
        return 0

    async def run(self) -> CleanupReport:
        """Execute the orphan cleanup job.

        This method:
        1. Scans for orphaned files using OrphanedFileScanner
        2. Filters to files older than min_age
        3. Deletes files (or logs if dry_run)
        4. Returns a detailed report

        Returns:
            CleanupReport with operation statistics
        """
        import time

        start_time = time.monotonic()
        report = CleanupReport(dry_run=self.dry_run)
        job_id: str | None = None

        # Create job if tracker available
        if self._job_tracker:
            job_id = self._job_tracker.create_job(JOB_TYPE_ORPHAN_CLEANUP)
            self._job_tracker.start_job(
                job_id, message=f"Starting orphan cleanup (dry_run={self.dry_run})"
            )

        try:
            logger.info(
                f"Starting orphan cleanup job (dry_run={self.dry_run}, min_age={self.min_age})"
            )

            # Step 1: Scan for orphaned files
            self._update_job_progress(job_id, 10, "Scanning for orphaned files...")

            scan_result = await self._scanner.scan_all_directories()
            report.scanned_files = scan_result.scanned_files
            report.orphaned_files = len(scan_result.orphaned_files)

            if not scan_result.orphaned_files:
                logger.info("No orphaned files found")
                report.duration_seconds = time.monotonic() - start_time
                self._complete_job(job_id, report)
                return report

            # Step 2: Process each orphaned file
            total_orphans = len(scan_result.orphaned_files)
            cumulative_deleted_bytes = 0

            for i, orphan in enumerate(scan_result.orphaned_files):
                # Update progress
                progress = 10 + int((i / total_orphans) * 80)  # 10-90%
                self._update_job_progress(
                    job_id, progress, f"Processing file {i + 1}/{total_orphans}"
                )

                # Check size limit
                if cumulative_deleted_bytes >= self.max_delete_bytes:
                    report.skipped_size_limit += 1
                    logger.debug(f"Size limit reached, skipping: {orphan.path}")
                    continue

                # Check if file should be deleted
                should_delete, skip_reason = self._should_delete(orphan)
                if not should_delete:
                    report.skipped_young += 1
                    logger.debug(f"Skipping file: {orphan.path} - {skip_reason}")
                    continue

                # Delete or log
                if self.dry_run:
                    cumulative_deleted_bytes += self._process_orphan_dry_run(orphan, report)
                else:
                    cumulative_deleted_bytes += self._process_orphan_actual(orphan, report)

            # Step 3: Complete
            report.duration_seconds = time.monotonic() - start_time

            logger.info(
                f"Orphan cleanup completed: {report} "
                f"(skipped_young={report.skipped_young}, "
                f"skipped_size_limit={report.skipped_size_limit})"
            )

            self._complete_job(job_id, report)

            return report

        except Exception as e:
            logger.error(f"Orphan cleanup job failed: {e}", exc_info=True)
            report.duration_seconds = time.monotonic() - start_time

            if self._job_tracker and job_id:
                self._job_tracker.fail_job(job_id, str(e))

            raise


class OrphanCleanupScheduler:
    """Scheduler for running orphan cleanup jobs periodically.

    This class manages the lifecycle of periodic orphan cleanup,
    running cleanup jobs at configured intervals.
    """

    def __init__(
        self,
        interval_hours: int | None = None,
        min_age_hours: int | None = None,
        dry_run: bool = False,
        job_tracker: JobTracker | None = None,
    ) -> None:
        """Initialize the cleanup scheduler.

        Args:
            interval_hours: Hours between cleanup runs. If None, uses settings.
            min_age_hours: Minimum file age before deletion. If None, uses settings.
            dry_run: If True, don't actually delete files.
            job_tracker: Optional job tracker for progress reporting.
        """
        settings = get_settings()
        self.interval_hours = interval_hours or settings.orphan_cleanup_scan_interval_hours
        self.min_age_hours = min_age_hours or settings.orphan_cleanup_age_threshold_hours
        self.dry_run = dry_run
        self._job_tracker = job_tracker
        self._task: asyncio.Task | None = None
        self.running = False
        self.enabled = settings.orphan_cleanup_enabled

        logger.info(
            f"OrphanCleanupScheduler initialized: interval={self.interval_hours}h, "
            f"min_age={self.min_age_hours}h, dry_run={dry_run}, enabled={self.enabled}"
        )

    async def _cleanup_loop(self) -> None:
        """Main loop that runs cleanup periodically."""
        logger.info("Orphan cleanup scheduler loop started")

        while self.running:
            try:
                # Create and run cleanup job
                job = OrphanCleanupJob(
                    min_age_hours=self.min_age_hours,
                    dry_run=self.dry_run,
                    job_tracker=self._job_tracker,
                )
                await job.run()

                # Wait for next run
                wait_seconds = self.interval_hours * 3600
                logger.info(f"Next orphan cleanup in {self.interval_hours} hours")
                await asyncio.sleep(wait_seconds)

            except asyncio.CancelledError:
                logger.info("Orphan cleanup scheduler loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in orphan cleanup loop: {e}", exc_info=True)
                # Wait before retrying
                await asyncio.sleep(60)

        logger.info("Orphan cleanup scheduler loop stopped")

    async def start(self) -> None:
        """Start the scheduled cleanup.

        This method is idempotent - calling it multiple times is safe.
        """
        if self.running:
            logger.warning("Orphan cleanup scheduler already running")
            return

        if not self.enabled:
            logger.info("Orphan cleanup scheduler is disabled, not starting")
            return

        logger.info("Starting orphan cleanup scheduler")
        self.running = True
        self._task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        """Stop the scheduled cleanup.

        Cancels the cleanup loop and waits for graceful shutdown.
        """
        if not self.running:
            logger.debug("Orphan cleanup scheduler not running, nothing to stop")
            return

        logger.info("Stopping orphan cleanup scheduler")
        self.running = False

        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        logger.info("Orphan cleanup scheduler stopped")

    async def __aenter__(self) -> OrphanCleanupScheduler:
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
_scheduler: OrphanCleanupScheduler | None = None


def get_orphan_cleanup_scheduler(
    interval_hours: int | None = None,
    min_age_hours: int | None = None,
    dry_run: bool = False,
    job_tracker: JobTracker | None = None,
) -> OrphanCleanupScheduler:
    """Get or create the singleton cleanup scheduler instance.

    Args:
        interval_hours: Hours between cleanup runs.
        min_age_hours: Minimum file age before deletion.
        dry_run: If True, don't actually delete files.
        job_tracker: Optional job tracker for progress reporting.

    Returns:
        The cleanup scheduler singleton.
    """
    global _scheduler  # noqa: PLW0603
    if _scheduler is None:
        _scheduler = OrphanCleanupScheduler(
            interval_hours=interval_hours,
            min_age_hours=min_age_hours,
            dry_run=dry_run,
            job_tracker=job_tracker,
        )
    return _scheduler


def reset_orphan_cleanup_scheduler() -> None:
    """Reset the cleanup scheduler singleton. Used for testing."""
    global _scheduler  # noqa: PLW0603
    _scheduler = None
