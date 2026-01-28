"""Unit tests for the OrphanedFileCleanupService.

This module contains comprehensive unit tests for the OrphanedFileCleanupService,
which manages periodic cleanup of orphaned files (files on disk without
corresponding database records).

Related Issues:
    - NEM-2260: Implement orphaned file cleanup background job

Test Organization:
    - OrphanedFileCleanupStats tests: Verify the data class for tracking cleanup metrics
    - Initialization tests: Verify service creation with default/custom settings
    - File scanning tests: Verify identification of orphaned files
    - Age threshold tests: Verify files younger than threshold are not deleted
    - Service lifecycle tests: Verify start/stop behavior and idempotency
    - Job tracking integration tests: Verify job tracker integration
    - Edge case tests: Verify boundary conditions and error handling

Acceptance Criteria:
    - Background job runs on configurable schedule
    - Identifies orphaned files correctly (files not in database)
    - Respects age threshold before deletion (configurable, default 24 hours)
    - Reports cleanup statistics via job tracking system
    - Broadcasts WebSocket notification on cleanup completion
"""

import asyncio
import contextlib
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mark all tests in this module as unit tests (use mocks, no database required)
pytestmark = pytest.mark.unit


# Fixtures


@pytest.fixture(autouse=True)
def mock_settings_for_cleanup_tests():
    """Set up minimal environment for tests that don't use test_db.

    This fixture sets DATABASE_URL so get_settings() doesn't fail when
    OrphanedFileCleanupService is instantiated without explicit parameters.
    """
    from backend.core.config import get_settings

    original_db_url = os.environ.get("DATABASE_URL")

    # Only set DATABASE_URL if not already set (e.g., by test_db fixture)
    if not original_db_url:
        os.environ["DATABASE_URL"] = (
            "postgresql+asyncpg://test:test@localhost:5432/test"  # pragma: allowlist secret
        )
        get_settings.cache_clear()

    yield

    # Restore original state
    if original_db_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = original_db_url
    get_settings.cache_clear()


@pytest.fixture
def orphan_cleanup_service():
    """Create orphan cleanup service instance with test configuration."""
    from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

    service = OrphanedFileCleanupService(
        scan_interval_hours=24,
        age_threshold_hours=24,
        clips_directory="data/clips",
    )
    return service


@pytest.fixture
def mock_job_tracker():
    """Create a mock job tracker."""
    tracker = MagicMock()
    tracker.create_job = MagicMock(return_value="test-job-id")
    tracker.start_job = MagicMock()
    tracker.update_progress = MagicMock()
    tracker.complete_job = MagicMock()
    tracker.fail_job = MagicMock()
    return tracker


@pytest.fixture
def mock_broadcast_callback():
    """Create a mock broadcast callback."""
    return MagicMock()


# =============================================================================
# OrphanedFileCleanupStats Tests
# =============================================================================


class TestOrphanedFileCleanupStats:
    """Tests for the OrphanedFileCleanupStats data class.

    OrphanedFileCleanupStats tracks metrics from an orphan cleanup operation:
    - Number of files scanned
    - Number of orphaned files found
    - Number of files deleted
    - Number of files skipped (too young)
    - Total disk space reclaimed in bytes
    """

    def test_initialization_with_zero_values(self):
        """Verify OrphanedFileCleanupStats initializes all counters to zero.

        Given: No arguments provided to OrphanedFileCleanupStats constructor
        When: A new OrphanedFileCleanupStats instance is created
        Then: All counter fields should be initialized to 0
        """
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupStats

        stats = OrphanedFileCleanupStats()

        assert stats.files_scanned == 0
        assert stats.orphans_found == 0
        assert stats.files_deleted == 0
        assert stats.files_skipped_young == 0
        assert stats.space_reclaimed == 0

    def test_to_dict_converts_all_fields(self):
        """Verify OrphanedFileCleanupStats converts to dictionary with all fields.

        Given: An OrphanedFileCleanupStats instance with populated values
        When: to_dict() is called
        Then: Returns a dictionary containing all field names and values
        """
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupStats

        stats = OrphanedFileCleanupStats()
        stats.files_scanned = 100
        stats.orphans_found = 25
        stats.files_deleted = 20
        stats.files_skipped_young = 5
        stats.space_reclaimed = 1024000

        result = stats.to_dict()

        assert result == {
            "files_scanned": 100,
            "orphans_found": 25,
            "files_deleted": 20,
            "files_skipped_young": 5,
            "space_reclaimed": 1024000,
        }

    def test_repr_includes_key_fields(self):
        """Verify OrphanedFileCleanupStats string representation includes key metrics.

        Given: An OrphanedFileCleanupStats instance with some values set
        When: repr() is called on the instance
        Then: String includes class name and key metric values
        """
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupStats

        stats = OrphanedFileCleanupStats()
        stats.files_scanned = 50
        stats.orphans_found = 10
        stats.files_deleted = 8

        repr_str = repr(stats)

        assert "OrphanedFileCleanupStats" in repr_str
        assert "scanned=50" in repr_str
        assert "orphans=10" in repr_str
        assert "deleted=8" in repr_str


# =============================================================================
# OrphanedFileCleanupService Initialization Tests
# =============================================================================


class TestOrphanedFileCleanupServiceInitialization:
    """Tests for OrphanedFileCleanupService initialization and configuration.

    The OrphanedFileCleanupService can be configured with:
    - scan_interval_hours: How often to scan for orphans (default 24)
    - age_threshold_hours: Min age before file can be deleted (default 24)
    - clips_directory: Directory to scan for orphaned files
    """

    def test_default_configuration(self):
        """Verify OrphanedFileCleanupService initializes with sensible defaults.

        Given: No configuration parameters provided
        When: A new OrphanedFileCleanupService instance is created
        Then: Uses default scan_interval=24h, age_threshold=24h
        """
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        mock_settings = MagicMock()
        mock_settings.clips_directory = "data/clips"
        mock_settings.orphan_cleanup_scan_interval_hours = 24
        mock_settings.orphan_cleanup_age_threshold_hours = 24
        mock_settings.orphan_cleanup_enabled = True

        with patch(
            "backend.services.orphan_cleanup_service.get_settings", return_value=mock_settings
        ):
            service = OrphanedFileCleanupService()

        assert service.scan_interval_hours == 24
        assert service.age_threshold_hours == 24
        assert service.enabled is True
        assert service.running is False
        assert service._cleanup_task is None

    def test_custom_configuration(self):
        """Verify OrphanedFileCleanupService accepts custom configuration values.

        Given: Custom configuration parameters
        When: A new OrphanedFileCleanupService instance is created with those parameters
        Then: Service uses the provided custom values
        """
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        service = OrphanedFileCleanupService(
            scan_interval_hours=12,
            age_threshold_hours=48,
            clips_directory="/custom/clips",
            enabled=False,
        )

        assert service.scan_interval_hours == 12
        assert service.age_threshold_hours == 48
        assert str(service.clips_directory) == "/custom/clips"
        assert service.enabled is False


# =============================================================================
# File Scanning Tests
# =============================================================================


class TestFileScanning:
    """Tests for scanning directories for clip files."""

    def test_scan_finds_all_clip_files(self, tmp_path):
        """Verify scanning finds all clip files in directory.

        Given: A directory with various clip files
        When: scan_clip_files() is called
        Then: Returns all clip file paths
        """
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        # Create test files
        (tmp_path / "clip1.mp4").write_text("clip 1")
        (tmp_path / "clip2.mp4").write_text("clip 2")
        (tmp_path / "clip3.webm").write_text("clip 3")
        (tmp_path / "other.txt").write_text("not a clip")

        service = OrphanedFileCleanupService(clips_directory=str(tmp_path))
        files = service._scan_clip_files()

        # Should find mp4 and webm files
        assert len(files) >= 2  # At least the video files

    def test_scan_handles_nonexistent_directory(self):
        """Verify scanning handles nonexistent directory gracefully.

        Given: A clips directory that does not exist
        When: scan_clip_files() is called
        Then: Returns empty list without raising exception
        """
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        service = OrphanedFileCleanupService(clips_directory="/nonexistent/path")
        files = service._scan_clip_files()

        assert files == []

    def test_scan_handles_permission_error(self, tmp_path):
        """Verify scanning handles permission errors gracefully.

        Given: A clips directory with restricted permissions
        When: scan_clip_files() is called
        Then: Returns empty list or available files without raising exception
        """
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        service = OrphanedFileCleanupService(clips_directory=str(tmp_path))

        # Mock glob to raise permission error
        with patch("pathlib.Path.glob", side_effect=PermissionError("Access denied")):
            files = service._scan_clip_files()

        assert files == []


# =============================================================================
# Age Threshold Tests
# =============================================================================


class TestAgeThreshold:
    """Tests for file age threshold enforcement."""

    def test_file_older_than_threshold_can_be_deleted(self, tmp_path):
        """Verify files older than threshold can be deleted.

        Given: A file older than the age threshold
        When: is_file_old_enough() is called
        Then: Returns True
        """
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        # Create file
        test_file = tmp_path / "old_clip.mp4"
        test_file.write_text("old clip")

        service = OrphanedFileCleanupService(age_threshold_hours=1)

        # Mock file mtime to be 2 hours ago
        old_time = datetime.now().timestamp() - (2 * 3600)  # 2 hours ago
        with patch.object(Path, "stat") as mock_stat:
            mock_stat.return_value = MagicMock(st_mtime=old_time)
            result = service._is_file_old_enough(test_file)

        assert result is True

    def test_file_younger_than_threshold_cannot_be_deleted(self, tmp_path):
        """Verify files younger than threshold cannot be deleted.

        Given: A file younger than the age threshold
        When: is_file_old_enough() is called
        Then: Returns False
        """
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        # Create file (newly created = recent mtime)
        test_file = tmp_path / "new_clip.mp4"
        test_file.write_text("new clip")

        service = OrphanedFileCleanupService(age_threshold_hours=24)

        # File was just created so mtime is very recent
        result = service._is_file_old_enough(test_file)

        assert result is False


# =============================================================================
# Orphan Detection Tests
# =============================================================================


class TestOrphanDetection:
    """Tests for detecting orphaned files (files not referenced in database)."""

    @pytest.mark.asyncio
    async def test_file_with_db_record_is_not_orphan(self, tmp_path):
        """Verify files with corresponding database records are not orphans.

        Given: A file that has a corresponding database record
        When: is_orphan() is called
        Then: Returns False
        """
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        test_file = tmp_path / "clip_event_123.mp4"
        test_file.write_text("clip with db record")

        service = OrphanedFileCleanupService(clips_directory=str(tmp_path))

        # Mock database query to return a record
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 1  # Event exists
        mock_session.execute = AsyncMock(return_value=mock_result)

        @contextlib.asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with patch("backend.services.orphan_cleanup_service.get_session", mock_get_session):
            is_orphan = await service._is_orphan(str(test_file))

        assert is_orphan is False

    @pytest.mark.asyncio
    async def test_file_without_db_record_is_orphan(self, tmp_path):
        """Verify files without corresponding database records are orphans.

        Given: A file that has no corresponding database record
        When: is_orphan() is called
        Then: Returns True
        """
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        test_file = tmp_path / "clip_event_999.mp4"
        test_file.write_text("orphan clip")

        service = OrphanedFileCleanupService(clips_directory=str(tmp_path))

        # Mock database query to return no record
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # Event does not exist
        mock_session.execute = AsyncMock(return_value=mock_result)

        @contextlib.asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with patch("backend.services.orphan_cleanup_service.get_session", mock_get_session):
            is_orphan = await service._is_orphan(str(test_file))

        assert is_orphan is True


# =============================================================================
# Service Lifecycle Tests (Start/Stop)
# =============================================================================


class TestServiceLifecycle:
    """Tests for OrphanedFileCleanupService start() and stop() methods.

    The service lifecycle should be idempotent - calling start() multiple
    times should be safe, and stop() should gracefully handle already-stopped
    services.
    """

    @pytest.mark.asyncio
    async def test_start_creates_cleanup_task(self):
        """Verify starting service creates background cleanup task.

        Given: A new OrphanedFileCleanupService instance
        When: start() is called
        Then: Service is running and cleanup task is created
        """
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        service = OrphanedFileCleanupService(enabled=True)

        await service.start()

        assert service.running is True
        assert service._cleanup_task is not None

        # Cleanup
        await service.stop()

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self):
        """Verify calling start() multiple times is safe.

        Given: An OrphanedFileCleanupService that is already running
        When: start() is called again
        Then: Same task is used, no duplicate tasks created
        """
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        service = OrphanedFileCleanupService(enabled=True)

        await service.start()
        first_task = service._cleanup_task

        await service.start()
        second_task = service._cleanup_task

        # Should be same task
        assert first_task is second_task

        # Cleanup
        await service.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_cleanup_task(self):
        """Verify stopping service cancels background task.

        Given: A running OrphanedFileCleanupService
        When: stop() is called
        Then: Service is not running and task is cleared
        """
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        service = OrphanedFileCleanupService(enabled=True)

        await service.start()
        assert service.running is True

        await service.stop()

        assert service.running is False
        assert service._cleanup_task is None

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self):
        """Verify stopping a non-running service is safe.

        Given: An OrphanedFileCleanupService that has not been started
        When: stop() is called
        Then: No exception is raised
        """
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        service = OrphanedFileCleanupService()

        # Should not raise exception
        await service.stop()

        assert service.running is False

    @pytest.mark.asyncio
    async def test_start_disabled_service_does_nothing(self):
        """Verify starting disabled service does not create task.

        Given: An OrphanedFileCleanupService with enabled=False
        When: start() is called
        Then: Service does not start and no task is created
        """
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        service = OrphanedFileCleanupService(enabled=False)

        await service.start()

        assert service.running is False
        assert service._cleanup_task is None


# =============================================================================
# run_cleanup Tests
# =============================================================================


class TestRunCleanup:
    """Tests for the run_cleanup() method."""

    @pytest.mark.asyncio
    async def test_run_cleanup_basic(self, tmp_path):
        """Test run_cleanup scans files and deletes orphans."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        # Create test files
        orphan_file = tmp_path / "orphan_clip.mp4"
        orphan_file.write_text("orphan clip data")

        # Make file "old enough" by setting mtime
        old_time = datetime.now().timestamp() - (48 * 3600)  # 48 hours ago
        os.utime(orphan_file, (old_time, old_time))

        service = OrphanedFileCleanupService(
            clips_directory=str(tmp_path),
            age_threshold_hours=24,
        )

        # Mock database to return no records (all files are orphans)
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        @contextlib.asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with patch("backend.services.orphan_cleanup_service.get_session", mock_get_session):
            stats = await service.run_cleanup()

        assert stats.files_scanned >= 1
        assert stats.orphans_found >= 1
        assert stats.files_deleted >= 1
        assert not orphan_file.exists()

    @pytest.mark.asyncio
    async def test_run_cleanup_respects_age_threshold(self, tmp_path):
        """Test run_cleanup does not delete files younger than threshold."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        # Create a brand new file
        new_orphan = tmp_path / "new_orphan_clip.mp4"
        new_orphan.write_text("new orphan clip data")

        service = OrphanedFileCleanupService(
            clips_directory=str(tmp_path),
            age_threshold_hours=24,
        )

        # Mock database to return no records
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        @contextlib.asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with patch("backend.services.orphan_cleanup_service.get_session", mock_get_session):
            stats = await service.run_cleanup()

        # File should be skipped because it's too young
        assert stats.files_skipped_young >= 1
        assert new_orphan.exists()  # File should still exist

    @pytest.mark.asyncio
    async def test_run_cleanup_does_not_delete_files_with_db_record(self, tmp_path):
        """Test run_cleanup does not delete files with database records."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        # Create test file
        valid_file = tmp_path / "valid_clip.mp4"
        valid_file.write_text("valid clip data")

        # Make file old enough
        old_time = datetime.now().timestamp() - (48 * 3600)
        os.utime(valid_file, (old_time, old_time))

        service = OrphanedFileCleanupService(
            clips_directory=str(tmp_path),
            age_threshold_hours=24,
        )

        # Mock database to return a record (file is not orphan)
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 1  # Event exists
        mock_session.execute = AsyncMock(return_value=mock_result)

        @contextlib.asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with patch("backend.services.orphan_cleanup_service.get_session", mock_get_session):
            stats = await service.run_cleanup()

        # File should NOT be deleted
        assert stats.files_deleted == 0
        assert valid_file.exists()


# =============================================================================
# Job Tracker Integration Tests
# =============================================================================


class TestJobTrackerIntegration:
    """Tests for job tracker integration."""

    @pytest.mark.asyncio
    async def test_run_cleanup_creates_job(self, tmp_path, mock_job_tracker):
        """Test run_cleanup creates and completes a job."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        service = OrphanedFileCleanupService(
            clips_directory=str(tmp_path),
            job_tracker=mock_job_tracker,
        )

        # Mock database
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        @contextlib.asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with patch("backend.services.orphan_cleanup_service.get_session", mock_get_session):
            stats = await service.run_cleanup()

        # Verify job tracker interactions
        mock_job_tracker.create_job.assert_called_once()
        mock_job_tracker.start_job.assert_called_once()
        mock_job_tracker.complete_job.assert_called_once()
        mock_job_tracker.fail_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_run_cleanup_fails_job_on_error(self, mock_job_tracker):
        """Test run_cleanup fails job when error occurs."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        service = OrphanedFileCleanupService(
            clips_directory="/some/path",
            job_tracker=mock_job_tracker,
        )

        # Mock scan_clip_files to raise an exception
        with patch.object(service, "_scan_clip_files", side_effect=Exception("Test error")):
            with pytest.raises(Exception, match="Test error"):
                await service.run_cleanup()

        # Verify job was failed
        mock_job_tracker.create_job.assert_called_once()
        mock_job_tracker.start_job.assert_called_once()
        mock_job_tracker.fail_job.assert_called_once()


# =============================================================================
# WebSocket Notification Tests
# =============================================================================


class TestWebSocketNotification:
    """Tests for WebSocket notification on cleanup completion."""

    @pytest.mark.asyncio
    async def test_broadcasts_on_cleanup_completion(self, tmp_path, mock_broadcast_callback):
        """Test service broadcasts notification on cleanup completion."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        service = OrphanedFileCleanupService(
            clips_directory=str(tmp_path),
            broadcast_callback=mock_broadcast_callback,
        )

        # Mock database
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        @contextlib.asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with patch("backend.services.orphan_cleanup_service.get_session", mock_get_session):
            await service.run_cleanup()

        # Verify broadcast was called
        mock_broadcast_callback.assert_called_once()
        call_args = mock_broadcast_callback.call_args
        assert call_args[0][0] == "orphan_cleanup_completed"
        assert "stats" in call_args[0][1]["data"]


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_handles_empty_directory(self, tmp_path):
        """Test handling of empty clips directory."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        service = OrphanedFileCleanupService(clips_directory=str(tmp_path))

        # Mock database
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()

        @contextlib.asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with patch("backend.services.orphan_cleanup_service.get_session", mock_get_session):
            stats = await service.run_cleanup()

        assert stats.files_scanned == 0
        assert stats.orphans_found == 0
        assert stats.files_deleted == 0

    @pytest.mark.asyncio
    async def test_handles_database_error(self, tmp_path):
        """Test handling of database errors during orphan check."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        # Create test file
        test_file = tmp_path / "test_clip.mp4"
        test_file.write_text("test data")

        # Make file old enough
        old_time = datetime.now().timestamp() - (48 * 3600)
        os.utime(test_file, (old_time, old_time))

        service = OrphanedFileCleanupService(
            clips_directory=str(tmp_path),
            age_threshold_hours=24,
        )

        # Mock database to raise error
        @contextlib.asynccontextmanager
        async def mock_get_session():
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(side_effect=Exception("DB error"))
            yield mock_session

        with patch("backend.services.orphan_cleanup_service.get_session", mock_get_session):
            # Should not raise - errors are logged and file is skipped
            stats = await service.run_cleanup()

        # File should NOT be deleted when DB check fails
        assert test_file.exists()

    def test_delete_file_success(self, tmp_path):
        """Test successful file deletion."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        test_file = tmp_path / "delete_me.mp4"
        test_file.write_text("delete this")

        service = OrphanedFileCleanupService()
        result, size = service._delete_file(test_file)

        assert result is True
        assert size > 0
        assert not test_file.exists()

    def test_delete_file_not_found(self):
        """Test deletion of nonexistent file."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        service = OrphanedFileCleanupService()
        result, size = service._delete_file(Path("/nonexistent/file.mp4"))

        assert result is False
        assert size == 0


# =============================================================================
# Cleanup Loop Tests
# =============================================================================


class TestCleanupLoop:
    """Tests for the cleanup loop behavior."""

    @pytest.mark.asyncio
    async def test_cleanup_loop_runs_cleanup(self):
        """Test cleanup loop runs cleanup method."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        service = OrphanedFileCleanupService(
            scan_interval_hours=1,
            enabled=True,
        )

        cleanup_called = False

        async def mock_run_cleanup():
            nonlocal cleanup_called
            cleanup_called = True
            # Stop after first run
            service.running = False
            from backend.services.orphan_cleanup_service import OrphanedFileCleanupStats

            return OrphanedFileCleanupStats()

        # Directly test the cleanup loop
        service.running = True
        with patch.object(service, "run_cleanup", side_effect=mock_run_cleanup):
            with patch(
                "backend.services.orphan_cleanup_service.asyncio.sleep",
                new_callable=AsyncMock,
            ):
                await service._cleanup_loop()

        assert cleanup_called

    @pytest.mark.asyncio
    async def test_cleanup_loop_handles_cancelled_error(self):
        """Test cleanup loop handles CancelledError gracefully."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        service = OrphanedFileCleanupService(enabled=True)
        service.running = True

        async def mock_run_cleanup_cancelled():
            raise asyncio.CancelledError()

        with patch.object(service, "run_cleanup", side_effect=mock_run_cleanup_cancelled):
            # Should exit without raising
            await service._cleanup_loop()

        # Loop should have exited
        assert True  # If we get here, CancelledError was handled

    @pytest.mark.asyncio
    async def test_cleanup_loop_continues_after_error(self):
        """Test cleanup loop continues after errors."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        service = OrphanedFileCleanupService(enabled=True)

        call_count = 0

        async def mock_run_cleanup_with_error():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Test error")
            # Stop after second call
            service.running = False
            from backend.services.orphan_cleanup_service import OrphanedFileCleanupStats

            return OrphanedFileCleanupStats()

        service.running = True
        with patch.object(service, "run_cleanup", side_effect=mock_run_cleanup_with_error):
            with patch(
                "backend.services.orphan_cleanup_service.asyncio.sleep",
                new_callable=AsyncMock,
            ):
                await service._cleanup_loop()

        # Loop should have continued after error
        assert call_count >= 2


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSingleton:
    """Tests for singleton management."""

    def test_get_orphan_cleanup_service_returns_singleton(self):
        """Should return the same instance on repeated calls."""
        from backend.services.orphan_cleanup_service import (
            get_orphan_cleanup_service,
            reset_orphan_cleanup_service,
        )

        reset_orphan_cleanup_service()

        service1 = get_orphan_cleanup_service()
        service2 = get_orphan_cleanup_service()

        assert service1 is service2

        reset_orphan_cleanup_service()

    def test_reset_clears_singleton(self):
        """Should clear the singleton on reset."""
        from backend.services.orphan_cleanup_service import (
            get_orphan_cleanup_service,
            reset_orphan_cleanup_service,
        )

        service1 = get_orphan_cleanup_service()
        reset_orphan_cleanup_service()
        service2 = get_orphan_cleanup_service()

        assert service1 is not service2

        reset_orphan_cleanup_service()


# =============================================================================
# Additional Coverage Tests
# =============================================================================


class TestEventIdExtraction:
    """Tests for extracting event IDs from file paths."""

    def test_extract_event_id_pattern_1_event_id(self):
        """Test extraction of event ID from event_<id> pattern."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        service = OrphanedFileCleanupService()

        # Test event_<id>
        assert service._extract_event_id_from_path("event_123.mp4") == 123
        assert service._extract_event_id_from_path("EVENT_456.mp4") == 456

        # Test clip_event_<id>
        assert service._extract_event_id_from_path("clip_event_789.mp4") == 789

    def test_extract_event_id_pattern_2_id_prefix(self):
        """Test extraction of event ID from <id>_ prefix pattern."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        service = OrphanedFileCleanupService()

        # Test <id>_clip
        assert service._extract_event_id_from_path("123_clip.mp4") == 123
        assert service._extract_event_id_from_path("456-event.webm") == 456

    def test_extract_event_id_pattern_3_just_number(self):
        """Test extraction of event ID when filename is just a number."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        service = OrphanedFileCleanupService()

        # Test just a number
        assert service._extract_event_id_from_path("789.mp4") == 789
        assert service._extract_event_id_from_path("123.webm") == 123

    def test_extract_event_id_returns_none_for_no_match(self):
        """Test that None is returned when no event ID can be extracted."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        service = OrphanedFileCleanupService()

        # No numeric ID
        assert service._extract_event_id_from_path("video.mp4") is None
        assert service._extract_event_id_from_path("clip_abc.mp4") is None


class TestScanErrorHandling:
    """Tests for error handling during file scanning."""

    def test_scan_handles_generic_exception(self, tmp_path):
        """Test that scanning handles generic exceptions gracefully."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        service = OrphanedFileCleanupService(clips_directory=str(tmp_path))

        # Mock glob to raise a generic exception
        with patch("pathlib.Path.glob", side_effect=RuntimeError("Generic error")):
            files = service._scan_clip_files()

        assert files == []


class TestFileAgeChecking:
    """Tests for file age checking edge cases."""

    def test_is_file_old_enough_handles_os_error(self):
        """Test that file age checking handles OS errors gracefully."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        service = OrphanedFileCleanupService(age_threshold_hours=24)
        test_file = Path("/nonexistent/file.mp4")

        # Mock stat to raise OSError
        with patch.object(Path, "stat", side_effect=OSError("Stat failed")):
            result = service._is_file_old_enough(test_file)

        assert result is False

    def test_is_file_old_enough_handles_file_not_found(self):
        """Test that file age checking handles FileNotFoundError."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        service = OrphanedFileCleanupService(age_threshold_hours=24)
        test_file = Path("/nonexistent/file.mp4")

        # File doesn't exist - should handle gracefully
        result = service._is_file_old_enough(test_file)

        assert result is False


class TestOrphanChecking:
    """Tests for orphan checking with different scenarios."""

    @pytest.mark.asyncio
    async def test_is_orphan_event_exists_but_file_not_referenced(self, tmp_path):
        """Test file is orphan when event exists but file is not referenced."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        test_file = tmp_path / "event_123.mp4"
        test_file.write_text("test")

        service = OrphanedFileCleanupService(clips_directory=str(tmp_path))

        # Mock database: event exists (first query), but clip_path doesn't match (second query)
        mock_session = AsyncMock()

        call_count = 0

        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            if call_count == 1:
                # First query: event exists
                mock_result.scalar_one_or_none.return_value = 123
            else:
                # Second query: clip_path doesn't match
                mock_result.scalar_one_or_none.return_value = None
            return mock_result

        mock_session.execute = mock_execute

        @contextlib.asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with patch("backend.services.orphan_cleanup_service.get_session", mock_get_session):
            is_orphan = await service._is_orphan(str(test_file))

        assert is_orphan is True

    @pytest.mark.asyncio
    async def test_is_orphan_handles_database_error(self, tmp_path):
        """Test that orphan checking returns False on database error (safe default)."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        test_file = tmp_path / "event_123.mp4"
        test_file.write_text("test")

        service = OrphanedFileCleanupService(clips_directory=str(tmp_path))

        # Mock database to raise error
        @contextlib.asynccontextmanager
        async def mock_get_session():
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock(side_effect=Exception("DB connection failed"))
            yield mock_session

        with patch("backend.services.orphan_cleanup_service.get_session", mock_get_session):
            is_orphan = await service._is_orphan(str(test_file))

        # Should return False (safe default - don't delete on error)
        assert is_orphan is False

    @pytest.mark.asyncio
    async def test_is_orphan_no_event_id_checks_clip_path(self, tmp_path):
        """Test orphan check falls back to clip_path lookup when event ID not extractable."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        # File without recognizable event ID pattern
        test_file = tmp_path / "unknown_clip.mp4"
        test_file.write_text("test")

        service = OrphanedFileCleanupService(clips_directory=str(tmp_path))

        # Mock database to return no matching clip_path
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        @contextlib.asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with patch("backend.services.orphan_cleanup_service.get_session", mock_get_session):
            is_orphan = await service._is_orphan(str(test_file))

        assert is_orphan is True


class TestFileDeletion:
    """Tests for file deletion edge cases."""

    def test_delete_file_handles_exception(self, tmp_path):
        """Test that file deletion handles exceptions gracefully."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        test_file = tmp_path / "test.mp4"
        test_file.write_text("test")

        service = OrphanedFileCleanupService()

        # Mock unlink to raise exception
        with patch.object(Path, "unlink", side_effect=PermissionError("Cannot delete")):
            success, size = service._delete_file(test_file)

        assert success is False
        assert size == 0


class TestBroadcasting:
    """Tests for WebSocket broadcasting edge cases."""

    @pytest.mark.asyncio
    async def test_broadcast_with_async_callback(self, tmp_path):
        """Test broadcasting with async callback."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        callback_called = False
        callback_event_type = None
        callback_data = None

        async def async_callback(event_type, data):
            nonlocal callback_called, callback_event_type, callback_data
            callback_called = True
            callback_event_type = event_type
            callback_data = data

        service = OrphanedFileCleanupService(
            clips_directory=str(tmp_path), broadcast_callback=async_callback
        )

        # Mock database
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        @contextlib.asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with patch("backend.services.orphan_cleanup_service.get_session", mock_get_session):
            await service.run_cleanup()

        # Give async callback time to execute
        await asyncio.sleep(0.1)

        assert callback_called is True
        assert callback_event_type == "orphan_cleanup_completed"
        assert "stats" in callback_data["data"]

    def test_broadcast_with_async_callback_no_running_loop(self, tmp_path):
        """Test broadcasting with async callback when no event loop is running.

        Note: This test verifies the fallback to asyncio.run when no event loop
        is running. The coroutine warning is expected in this edge case test.
        """
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        async def async_callback(event_type, data):
            pass

        service = OrphanedFileCleanupService(
            clips_directory=str(tmp_path), broadcast_callback=async_callback
        )

        # Mock get_running_loop to raise RuntimeError
        with patch("asyncio.get_running_loop", side_effect=RuntimeError("No running loop")):
            with patch("asyncio.run") as mock_asyncio_run:
                # Directly call _broadcast
                service._broadcast("test_event", {"test": "data"})

                # Should fall back to asyncio.run
                mock_asyncio_run.assert_called_once()

    def test_broadcast_handles_callback_exception(self, tmp_path):
        """Test that broadcasting handles callback exceptions gracefully."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        def failing_callback(event_type, data):
            raise Exception("Callback failed")

        service = OrphanedFileCleanupService(
            clips_directory=str(tmp_path), broadcast_callback=failing_callback
        )

        # Should not raise exception
        service._broadcast("test_event", {"test": "data"})


class TestRunCleanupProgress:
    """Tests for cleanup progress tracking."""

    @pytest.mark.asyncio
    async def test_run_cleanup_updates_progress(self, tmp_path, mock_job_tracker):
        """Test that run_cleanup updates job progress during execution."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        # Create multiple test files
        for i in range(3):
            test_file = tmp_path / f"event_{i}.mp4"
            test_file.write_text(f"test {i}")
            # Make files old enough
            old_time = datetime.now().timestamp() - (48 * 3600)
            os.utime(test_file, (old_time, old_time))

        service = OrphanedFileCleanupService(
            clips_directory=str(tmp_path), job_tracker=mock_job_tracker
        )

        # Mock database
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        @contextlib.asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with patch("backend.services.orphan_cleanup_service.get_session", mock_get_session):
            await service.run_cleanup()

        # Verify progress updates were called
        assert mock_job_tracker.update_progress.call_count >= 3

    @pytest.mark.asyncio
    async def test_run_cleanup_handles_file_processing_error(self, tmp_path):
        """Test that run_cleanup continues when individual file processing fails."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        # Create multiple test files
        for i in range(3):
            test_file = tmp_path / f"event_{i}.mp4"
            test_file.write_text(f"test {i}")
            old_time = datetime.now().timestamp() - (48 * 3600)
            os.utime(test_file, (old_time, old_time))

        service = OrphanedFileCleanupService(clips_directory=str(tmp_path))

        # Mock _is_orphan to raise exception for some files
        call_count = 0

        async def mock_is_orphan(file_path):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("Processing error")
            return True

        # Mock database
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        @contextlib.asynccontextmanager
        async def mock_get_session():
            yield mock_session

        with patch("backend.services.orphan_cleanup_service.get_session", mock_get_session):
            with patch.object(service, "_is_orphan", side_effect=mock_is_orphan):
                stats = await service.run_cleanup()

        # Should still complete and process other files
        assert stats.files_scanned == 3
        # Should have deleted some files despite error
        assert stats.files_deleted >= 1


class TestAsyncContextManager:
    """Tests for async context manager protocol."""

    @pytest.mark.asyncio
    async def test_async_context_manager_starts_and_stops(self):
        """Test that async context manager starts and stops service."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        service = OrphanedFileCleanupService(enabled=True)

        # Use as async context manager
        async with service as svc:
            assert svc is service
            assert service.running is True

        # After exit, should be stopped
        assert service.running is False


class TestGetStatus:
    """Tests for the get_status method."""

    def test_get_status_returns_service_info(self):
        """Test that get_status returns current service configuration."""
        from backend.services.orphan_cleanup_service import OrphanedFileCleanupService

        service = OrphanedFileCleanupService(
            scan_interval_hours=12,
            age_threshold_hours=48,
            clips_directory="/test/clips",
            enabled=True,
        )

        status = service.get_status()

        assert status["running"] is False
        assert status["enabled"] is True
        assert status["scan_interval_hours"] == 12
        assert status["age_threshold_hours"] == 48
        assert status["clips_directory"] == "/test/clips"
