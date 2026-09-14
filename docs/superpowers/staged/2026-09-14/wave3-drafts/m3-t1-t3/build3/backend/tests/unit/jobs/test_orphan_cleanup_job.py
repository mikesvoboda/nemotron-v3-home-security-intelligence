"""Unit tests for the OrphanCleanupJob.

This module contains comprehensive unit tests for the OrphanCleanupJob,
which orchestrates the cleanup of orphaned files identified by OrphanedFileScanner.

Related Issues:
    - NEM-2387: Implement orphaned file cleanup background job

Test Organization:
    - CleanupReport dataclass tests
    - OrphanCleanupJob initialization tests
    - File deletion decision tests
    - File deletion tests
    - Full cleanup run tests
    - Job tracker integration tests
    - Scheduler tests
    - Edge case tests
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit


# Fixtures


@pytest.fixture(autouse=True)
def mock_settings_for_job_tests():
    """Set up minimal environment for tests."""
    from backend.core.config import get_settings

    original_db_url = os.environ.get("DATABASE_URL")

    if not original_db_url:
        os.environ["DATABASE_URL"] = (
            "postgresql+asyncpg://test:test@localhost:5432/test"  # pragma: allowlist secret
        )
        get_settings.cache_clear()

    yield

    if original_db_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = original_db_url
    get_settings.cache_clear()


@pytest.fixture
def mock_scanner():
    """Create a mock OrphanedFileScanner."""
    scanner = MagicMock()
    scanner.scan_all_directories = AsyncMock()
    return scanner


@pytest.fixture
def mock_job_tracker():
    """Create a mock JobTracker."""
    tracker = MagicMock()
    tracker.create_job = MagicMock(return_value="test-job-id")
    tracker.start_job = MagicMock()
    tracker.update_progress = MagicMock()
    tracker.complete_job = MagicMock()
    tracker.fail_job = MagicMock()
    return tracker


# =============================================================================
# CleanupReport Tests
# =============================================================================


class TestCleanupReport:
    """Tests for the CleanupReport dataclass."""

    def test_initialization_with_defaults(self):
        """Test CleanupReport initializes with zero values."""
        from backend.jobs.orphan_cleanup_job import CleanupReport

        report = CleanupReport()

        assert report.scanned_files == 0
        assert report.orphaned_files == 0
        assert report.deleted_files == 0
        assert report.deleted_bytes == 0
        assert report.failed_deletions == []
        assert report.duration_seconds == 0.0
        assert report.dry_run is True
        assert report.skipped_young == 0
        assert report.skipped_size_limit == 0

    def test_to_dict(self):
        """Test converting CleanupReport to dictionary."""
        from backend.jobs.orphan_cleanup_job import CleanupReport

        report = CleanupReport(
            scanned_files=100,
            orphaned_files=10,
            deleted_files=5,
            deleted_bytes=1024,
            failed_deletions=["/path/to/failed.jpg"],
            duration_seconds=1.5,
            dry_run=False,
            skipped_young=3,
            skipped_size_limit=2,
        )

        result = report.to_dict()

        assert result["scanned_files"] == 100
        assert result["orphaned_files"] == 10
        assert result["deleted_files"] == 5
        assert result["deleted_bytes"] == 1024
        assert result["deleted_bytes_formatted"] == "1.00 KB"
        assert result["failed_count"] == 1
        assert len(result["failed_deletions"]) == 1
        assert result["duration_seconds"] == 1.5
        assert result["dry_run"] is False
        assert result["skipped_young"] == 3
        assert result["skipped_size_limit"] == 2

    def test_format_bytes_various_sizes(self):
        """Test byte formatting for various sizes."""
        from backend.jobs.orphan_cleanup_job import CleanupReport

        assert CleanupReport._format_bytes(0) == "0 B"
        assert CleanupReport._format_bytes(512) == "512 B"
        assert CleanupReport._format_bytes(1024) == "1.00 KB"
        assert CleanupReport._format_bytes(1536) == "1.50 KB"
        assert CleanupReport._format_bytes(1048576) == "1.00 MB"
        assert CleanupReport._format_bytes(1073741824) == "1.00 GB"
        assert CleanupReport._format_bytes(-1) == "0 B"  # Negative

    def test_repr(self):
        """Test string representation."""
        from backend.jobs.orphan_cleanup_job import CleanupReport

        report = CleanupReport(
            scanned_files=100,
            orphaned_files=10,
            deleted_files=5,
            deleted_bytes=1024,
            dry_run=False,
        )

        repr_str = repr(report)

        assert "scanned=100" in repr_str
        assert "orphaned=10" in repr_str
        assert "deleted=5" in repr_str
        assert "dry_run=False" in repr_str


# =============================================================================
# OrphanCleanupJob Initialization Tests
# =============================================================================


class TestJobInitialization:
    """Tests for OrphanCleanupJob initialization."""

    def test_default_initialization(self, mock_scanner):
        """Test job initializes with default values."""
        from backend.jobs.orphan_cleanup_job import OrphanCleanupJob

        job = OrphanCleanupJob(scanner=mock_scanner)

        assert job.min_age == timedelta(hours=24)
        assert job.dry_run is True
        assert job.max_delete_bytes == 10 * 1024 * 1024 * 1024  # 10 GB

    def test_custom_initialization(self, mock_scanner, mock_job_tracker):
        """Test job with custom configuration."""
        from backend.jobs.orphan_cleanup_job import OrphanCleanupJob

        job = OrphanCleanupJob(
            min_age_hours=48,
            dry_run=False,
            max_delete_gb=5.0,
            scanner=mock_scanner,
            job_tracker=mock_job_tracker,
        )

        assert job.min_age == timedelta(hours=48)
        assert job.dry_run is False
        assert job.max_delete_bytes == 5 * 1024 * 1024 * 1024
        assert job._job_tracker is mock_job_tracker


# =============================================================================
# Should Delete Decision Tests
# =============================================================================


class TestShouldDelete:
    """Tests for _should_delete method."""

    def test_should_delete_old_file(self, mock_scanner):
        """Test that old files should be deleted."""
        from backend.jobs.orphan_cleanup_job import OrphanCleanupJob
        from backend.services.orphan_scanner_service import OrphanedFile

        job = OrphanCleanupJob(min_age_hours=24, scanner=mock_scanner)

        orphan = OrphanedFile(
            path=Path("/test/old.jpg"),
            size_bytes=1000,
            mtime=datetime.now() - timedelta(hours=48),
            age=timedelta(hours=48),
        )

        should_delete, reason = job._should_delete(orphan)

        assert should_delete is True
        assert reason == ""

    def test_should_not_delete_young_file(self, mock_scanner):
        """Test that young files should not be deleted."""
        from backend.jobs.orphan_cleanup_job import OrphanCleanupJob
        from backend.services.orphan_scanner_service import OrphanedFile

        job = OrphanCleanupJob(min_age_hours=24, scanner=mock_scanner)

        orphan = OrphanedFile(
            path=Path("/test/young.jpg"),
            size_bytes=1000,
            mtime=datetime.now() - timedelta(hours=1),
            age=timedelta(hours=1),
        )

        should_delete, reason = job._should_delete(orphan)

        assert should_delete is False
        assert "too young" in reason.lower()


# =============================================================================
# File Deletion Tests
# =============================================================================


class TestDeleteFile:
    """Tests for _delete_file method."""

    def test_delete_file_success(self, tmp_path, mock_scanner):
        """Test successful file deletion."""
        from backend.jobs.orphan_cleanup_job import OrphanCleanupJob

        job = OrphanCleanupJob(scanner=mock_scanner)

        # Create a test file
        test_file = tmp_path / "delete_me.jpg"
        test_file.write_text("test data")  # 9 bytes

        success, freed = job._delete_file(test_file)

        assert success is True
        assert freed == 9
        assert not test_file.exists()

    def test_delete_file_not_found(self, mock_scanner):
        """Test deleting nonexistent file."""
        from backend.jobs.orphan_cleanup_job import OrphanCleanupJob

        job = OrphanCleanupJob(scanner=mock_scanner)

        success, freed = job._delete_file(Path("/nonexistent/file.jpg"))

        assert success is False
        assert freed == 0

    def test_delete_file_permission_denied(self, tmp_path, mock_scanner):
        """Test handling permission denied error."""
        from backend.jobs.orphan_cleanup_job import OrphanCleanupJob

        job = OrphanCleanupJob(scanner=mock_scanner)

        test_file = tmp_path / "protected.jpg"
        test_file.write_text("test data")

        with patch("pathlib.Path.unlink", side_effect=PermissionError("Access denied")):
            success, freed = job._delete_file(test_file)

        assert success is False
        assert freed == 0


# =============================================================================
# Full Cleanup Run Tests
# =============================================================================


class TestCleanupRun:
    """Tests for the run method."""

    @pytest.mark.asyncio
    async def test_run_no_orphans(self, mock_scanner, mock_job_tracker):
        """Test run when no orphans are found."""
        from backend.jobs.orphan_cleanup_job import OrphanCleanupJob
        from backend.services.orphan_scanner_service import ScanResult

        mock_scanner.scan_all_directories.return_value = ScanResult(
            scanned_files=100,
            orphaned_files=[],
        )

        job = OrphanCleanupJob(
            scanner=mock_scanner,
            job_tracker=mock_job_tracker,
        )

        report = await job.run()

        assert report.scanned_files == 100
        assert report.orphaned_files == 0
        assert report.deleted_files == 0
        mock_job_tracker.complete_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_dry_run_mode(self, tmp_path, mock_scanner, mock_job_tracker):
        """Test run in dry run mode doesn't delete files."""
        from backend.jobs.orphan_cleanup_job import OrphanCleanupJob
        from backend.services.orphan_scanner_service import OrphanedFile, ScanResult

        # Create test file
        test_file = tmp_path / "orphan.jpg"
        test_file.write_text("test data")

        orphan = OrphanedFile(
            path=test_file,
            size_bytes=9,
            mtime=datetime.now() - timedelta(hours=48),
            age=timedelta(hours=48),
        )

        mock_scanner.scan_all_directories.return_value = ScanResult(
            scanned_files=1,
            orphaned_files=[orphan],
            total_orphaned_bytes=9,
        )

        job = OrphanCleanupJob(
            dry_run=True,
            scanner=mock_scanner,
            job_tracker=mock_job_tracker,
        )

        report = await job.run()

        assert report.deleted_files == 1
        assert report.deleted_bytes == 9
        assert report.dry_run is True
        assert test_file.exists()  # File should still exist

    @pytest.mark.asyncio
    async def test_run_actual_deletion(self, tmp_path, mock_scanner, mock_job_tracker):
        """Test run actually deletes files when dry_run=False."""
        from backend.jobs.orphan_cleanup_job import OrphanCleanupJob
        from backend.services.orphan_scanner_service import OrphanedFile, ScanResult

        # Create test file
        test_file = tmp_path / "orphan.jpg"
        test_file.write_text("test data")

        orphan = OrphanedFile(
            path=test_file,
            size_bytes=9,
            mtime=datetime.now() - timedelta(hours=48),
            age=timedelta(hours=48),
        )

        mock_scanner.scan_all_directories.return_value = ScanResult(
            scanned_files=1,
            orphaned_files=[orphan],
            total_orphaned_bytes=9,
        )

        job = OrphanCleanupJob(
            dry_run=False,
            scanner=mock_scanner,
            job_tracker=mock_job_tracker,
        )

        report = await job.run()

        assert report.deleted_files == 1
        assert report.deleted_bytes == 9
        assert report.dry_run is False
        assert not test_file.exists()  # File should be deleted

    @pytest.mark.asyncio
    async def test_run_respects_size_limit(self, tmp_path, mock_scanner, mock_job_tracker):
        """Test run respects max_delete_gb limit."""
        from backend.jobs.orphan_cleanup_job import OrphanCleanupJob
        from backend.services.orphan_scanner_service import OrphanedFile, ScanResult

        # Create orphan files
        orphans = []
        for i in range(5):
            test_file = tmp_path / f"orphan{i}.jpg"
            test_file.write_text("x" * 1024)  # 1KB each

            orphan = OrphanedFile(
                path=test_file,
                size_bytes=1024,
                mtime=datetime.now() - timedelta(hours=48),
                age=timedelta(hours=48),
            )
            orphans.append(orphan)

        mock_scanner.scan_all_directories.return_value = ScanResult(
            scanned_files=5,
            orphaned_files=orphans,
            total_orphaned_bytes=5 * 1024,
        )

        # Set max_delete to 3KB (should only delete 3 files)
        job = OrphanCleanupJob(
            dry_run=False,
            max_delete_gb=3 * 1024 / (1024 * 1024 * 1024),  # 3KB in GB
            scanner=mock_scanner,
            job_tracker=mock_job_tracker,
        )

        report = await job.run()

        assert report.deleted_files == 3
        assert report.skipped_size_limit == 2

    @pytest.mark.asyncio
    async def test_run_skips_young_files(self, tmp_path, mock_scanner, mock_job_tracker):
        """Test run skips files that are too young."""
        from backend.jobs.orphan_cleanup_job import OrphanCleanupJob
        from backend.services.orphan_scanner_service import OrphanedFile, ScanResult

        # Create young orphan
        test_file = tmp_path / "young.jpg"
        test_file.write_text("test data")

        orphan = OrphanedFile(
            path=test_file,
            size_bytes=9,
            mtime=datetime.now() - timedelta(hours=1),
            age=timedelta(hours=1),  # Only 1 hour old
        )

        mock_scanner.scan_all_directories.return_value = ScanResult(
            scanned_files=1,
            orphaned_files=[orphan],
            total_orphaned_bytes=9,
        )

        job = OrphanCleanupJob(
            dry_run=False,
            min_age_hours=24,  # Requires 24 hours
            scanner=mock_scanner,
            job_tracker=mock_job_tracker,
        )

        report = await job.run()

        assert report.deleted_files == 0
        assert report.skipped_young == 1
        assert test_file.exists()

    @pytest.mark.asyncio
    async def test_run_handles_failed_deletions(self, tmp_path, mock_scanner, mock_job_tracker):
        """Test run tracks failed deletions."""
        from backend.jobs.orphan_cleanup_job import OrphanCleanupJob
        from backend.services.orphan_scanner_service import OrphanedFile, ScanResult

        test_file = tmp_path / "protected.jpg"
        test_file.write_text("test data")

        orphan = OrphanedFile(
            path=test_file,
            size_bytes=9,
            mtime=datetime.now() - timedelta(hours=48),
            age=timedelta(hours=48),
        )

        mock_scanner.scan_all_directories.return_value = ScanResult(
            scanned_files=1,
            orphaned_files=[orphan],
            total_orphaned_bytes=9,
        )

        job = OrphanCleanupJob(
            dry_run=False,
            scanner=mock_scanner,
            job_tracker=mock_job_tracker,
        )

        # Mock _delete_file to fail
        with patch.object(job, "_delete_file", return_value=(False, 0)):
            report = await job.run()

        assert report.deleted_files == 0
        assert len(report.failed_deletions) == 1


# =============================================================================
# Job Tracker Integration Tests
# =============================================================================


class TestJobTrackerIntegration:
    """Tests for job tracker integration."""

    @pytest.mark.asyncio
    async def test_job_lifecycle(self, mock_scanner, mock_job_tracker):
        """Test job tracker methods are called in correct order."""
        from backend.jobs.orphan_cleanup_job import OrphanCleanupJob
        from backend.services.orphan_scanner_service import ScanResult

        mock_scanner.scan_all_directories.return_value = ScanResult(
            scanned_files=0,
            orphaned_files=[],
        )

        job = OrphanCleanupJob(
            scanner=mock_scanner,
            job_tracker=mock_job_tracker,
        )

        await job.run()

        # Verify job lifecycle
        mock_job_tracker.create_job.assert_called_once_with("orphan_cleanup")
        mock_job_tracker.start_job.assert_called_once()
        mock_job_tracker.complete_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_job_failure_tracking(self, mock_scanner, mock_job_tracker):
        """Test job tracker records failures."""
        from backend.jobs.orphan_cleanup_job import OrphanCleanupJob

        # Make scanner raise an exception
        mock_scanner.scan_all_directories.side_effect = Exception("Scan failed")

        job = OrphanCleanupJob(
            scanner=mock_scanner,
            job_tracker=mock_job_tracker,
        )

        with pytest.raises(Exception, match="Scan failed"):
            await job.run()

        mock_job_tracker.fail_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_without_tracker(self, mock_scanner):
        """Test run works without job tracker."""
        from backend.jobs.orphan_cleanup_job import OrphanCleanupJob
        from backend.services.orphan_scanner_service import ScanResult

        mock_scanner.scan_all_directories.return_value = ScanResult(
            scanned_files=0,
            orphaned_files=[],
        )

        job = OrphanCleanupJob(
            scanner=mock_scanner,
            job_tracker=None,  # No tracker
        )

        report = await job.run()

        assert report.scanned_files == 0


# =============================================================================
# Scheduler Tests
# =============================================================================


class TestOrphanCleanupScheduler:
    """Tests for the OrphanCleanupScheduler."""

    def test_scheduler_initialization(self, mock_job_tracker):
        """Test scheduler initializes with correct values."""
        from backend.jobs.orphan_cleanup_job import OrphanCleanupScheduler

        with patch("backend.jobs.orphan_cleanup_job.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                orphan_cleanup_enabled=True,
                orphan_cleanup_scan_interval_hours=24,
                orphan_cleanup_age_threshold_hours=24,
            )

            scheduler = OrphanCleanupScheduler(
                dry_run=True,
                job_tracker=mock_job_tracker,
            )

        assert scheduler.interval_hours == 24
        assert scheduler.min_age_hours == 24
        assert scheduler.dry_run is True
        assert scheduler.enabled is True
        assert scheduler.running is False

    def test_scheduler_custom_config(self, mock_job_tracker):
        """Test scheduler with custom configuration."""
        from backend.jobs.orphan_cleanup_job import OrphanCleanupScheduler

        with patch("backend.jobs.orphan_cleanup_job.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                orphan_cleanup_enabled=True,
                orphan_cleanup_scan_interval_hours=24,
                orphan_cleanup_age_threshold_hours=24,
            )

            scheduler = OrphanCleanupScheduler(
                interval_hours=12,
                min_age_hours=48,
                dry_run=False,
                job_tracker=mock_job_tracker,
            )

        assert scheduler.interval_hours == 12
        assert scheduler.min_age_hours == 48
        assert scheduler.dry_run is False

    @pytest.mark.asyncio
    async def test_scheduler_start_when_disabled(self, mock_job_tracker):
        """Test scheduler doesn't start when disabled."""
        from backend.jobs.orphan_cleanup_job import OrphanCleanupScheduler

        with patch("backend.jobs.orphan_cleanup_job.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                orphan_cleanup_enabled=False,
                orphan_cleanup_scan_interval_hours=24,
                orphan_cleanup_age_threshold_hours=24,
            )

            scheduler = OrphanCleanupScheduler(job_tracker=mock_job_tracker)
            await scheduler.start()

        assert scheduler.running is False
        assert scheduler._task is None

    @pytest.mark.asyncio
    async def test_scheduler_stop_when_not_running(self, mock_job_tracker):
        """Test stop is safe when scheduler is not running."""
        from backend.jobs.orphan_cleanup_job import OrphanCleanupScheduler

        with patch("backend.jobs.orphan_cleanup_job.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                orphan_cleanup_enabled=True,
                orphan_cleanup_scan_interval_hours=24,
                orphan_cleanup_age_threshold_hours=24,
            )

            scheduler = OrphanCleanupScheduler(job_tracker=mock_job_tracker)
            await scheduler.stop()  # Should not raise

        assert scheduler.running is False


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSchedulerSingleton:
    """Tests for scheduler singleton management."""

    def test_get_scheduler_returns_singleton(self):
        """Test get_orphan_cleanup_scheduler returns same instance."""
        from backend.jobs.orphan_cleanup_job import (
            get_orphan_cleanup_scheduler,
            reset_orphan_cleanup_scheduler,
        )

        reset_orphan_cleanup_scheduler()

        scheduler1 = get_orphan_cleanup_scheduler()
        scheduler2 = get_orphan_cleanup_scheduler()

        assert scheduler1 is scheduler2

        reset_orphan_cleanup_scheduler()

    def test_reset_clears_singleton(self):
        """Test reset_orphan_cleanup_scheduler clears the singleton."""
        from backend.jobs.orphan_cleanup_job import (
            get_orphan_cleanup_scheduler,
            reset_orphan_cleanup_scheduler,
        )

        scheduler1 = get_orphan_cleanup_scheduler()
        reset_orphan_cleanup_scheduler()
        scheduler2 = get_orphan_cleanup_scheduler()

        assert scheduler1 is not scheduler2

        reset_orphan_cleanup_scheduler()


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_run_with_empty_scan_result(self, mock_scanner, mock_job_tracker):
        """Test handling of empty scan result."""
        from backend.jobs.orphan_cleanup_job import OrphanCleanupJob
        from backend.services.orphan_scanner_service import ScanResult

        mock_scanner.scan_all_directories.return_value = ScanResult()

        job = OrphanCleanupJob(
            scanner=mock_scanner,
            job_tracker=mock_job_tracker,
        )

        report = await job.run()

        assert report.scanned_files == 0
        assert report.orphaned_files == 0
        assert report.deleted_files == 0

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_job_tracker):
        """Test scheduler as async context manager."""
        from backend.jobs.orphan_cleanup_job import OrphanCleanupScheduler

        with patch("backend.jobs.orphan_cleanup_job.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                orphan_cleanup_enabled=False,  # Disabled so no task starts
                orphan_cleanup_scan_interval_hours=24,
                orphan_cleanup_age_threshold_hours=24,
            )

            async with OrphanCleanupScheduler(job_tracker=mock_job_tracker) as scheduler:
                # Should have attempted to start
                pass

            # Should be stopped
            assert scheduler.running is False
