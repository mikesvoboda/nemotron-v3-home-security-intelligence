"""Integration tests for orphan cleanup service.

These tests require a real PostgreSQL database (test_db fixture) and test
the orphan cleanup service's interaction with the database and file system.

Related Issues:
    - NEM-2260: Implement orphaned file cleanup background job

Note: These tests use unique IDs for cameras and events to allow parallel test execution.
"""

import os
from datetime import UTC, datetime, timedelta

import pytest

from backend.models.camera import Camera
from backend.models.event import Event
from backend.services.orphan_cleanup_service import (
    OrphanedFileCleanupService,
    reset_orphan_cleanup_service,
)
from backend.tests.conftest import unique_id

# Mark as integration since all tests require real PostgreSQL database (test_db fixture)
pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the orphan cleanup service singleton after each test."""
    yield
    reset_orphan_cleanup_service()


# =============================================================================
# Database integration tests
# =============================================================================


@pytest.mark.slow
@pytest.mark.asyncio
async def test_orphan_cleanup_deletes_file_without_db_record(test_db, tmp_path):
    """Test orphan cleanup deletes files without database records.

    Given: A clip file that has no corresponding event in the database
    When: Orphan cleanup runs
    Then: The file should be deleted
    """
    # Create a clip file with no database record
    orphan_file = tmp_path / "event_999999.mp4"
    orphan_file.write_text("orphan clip data")

    # Make file old enough (48 hours ago)
    old_time = datetime.now().timestamp() - (48 * 3600)
    os.utime(orphan_file, (old_time, old_time))

    # Run cleanup
    service = OrphanedFileCleanupService(
        clips_directory=str(tmp_path),
        age_threshold_hours=24,
    )
    stats = await service.run_cleanup()

    # Verify file was deleted
    assert not orphan_file.exists()
    assert stats.orphans_found >= 1
    assert stats.files_deleted >= 1


@pytest.mark.slow
@pytest.mark.asyncio
async def test_orphan_cleanup_keeps_file_with_db_record(test_db, tmp_path):
    """Test orphan cleanup keeps files that have database records.

    Given: A clip file that has a corresponding event in the database
    When: Orphan cleanup runs
    Then: The file should NOT be deleted
    """
    camera_id = unique_id("test_camera")
    batch_id = unique_id("test_batch")

    # Create camera and event in database
    async with test_db() as session:
        camera = Camera(
            id=camera_id,
            name=f"Test Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        # Create event with clip_path pointing to our file
        clip_file = tmp_path / f"event_{batch_id}.mp4"
        clip_file.write_text("valid clip data")

        # Make file old enough
        old_time = datetime.now().timestamp() - (48 * 3600)
        os.utime(clip_file, (old_time, old_time))

        event = Event(
            batch_id=batch_id,
            camera_id=camera_id,
            started_at=datetime.now(UTC) - timedelta(days=2),
            risk_score=50,
            clip_path=str(clip_file),
        )
        session.add(event)
        await session.commit()
        event_id = event.id

    # Run cleanup
    service = OrphanedFileCleanupService(
        clips_directory=str(tmp_path),
        age_threshold_hours=24,
    )
    stats = await service.run_cleanup()

    # Verify file was NOT deleted (it has a database record)
    assert clip_file.exists()
    assert stats.files_deleted == 0


@pytest.mark.slow
@pytest.mark.asyncio
async def test_orphan_cleanup_skips_young_files(test_db, tmp_path):
    """Test orphan cleanup skips files younger than threshold.

    Given: A clip file that is an orphan but too young
    When: Orphan cleanup runs
    Then: The file should NOT be deleted
    """
    # Create a brand new orphan file
    orphan_file = tmp_path / "event_999998.mp4"
    orphan_file.write_text("young orphan clip data")
    # File is created now, so it's too young

    # Run cleanup with 24-hour threshold
    service = OrphanedFileCleanupService(
        clips_directory=str(tmp_path),
        age_threshold_hours=24,
    )
    stats = await service.run_cleanup()

    # Verify file was NOT deleted (too young)
    assert orphan_file.exists()
    assert stats.files_skipped_young >= 1
    assert stats.files_deleted == 0


@pytest.mark.slow
@pytest.mark.asyncio
async def test_orphan_cleanup_reports_statistics(test_db, tmp_path):
    """Test orphan cleanup reports accurate statistics.

    Given: Multiple files - some orphans, some valid, some young
    When: Orphan cleanup runs
    Then: Statistics should accurately reflect what was processed
    """
    camera_id = unique_id("test_camera")
    batch_id = unique_id("test_batch")

    # Create camera and one valid event
    async with test_db() as session:
        camera = Camera(
            id=camera_id,
            name=f"Test Camera {camera_id[-8:]}",
            folder_path=f"/export/foscam/{camera_id}",
        )
        session.add(camera)
        await session.flush()

        # Create valid clip
        valid_file = tmp_path / f"event_{batch_id}.mp4"
        valid_file.write_text("valid clip")
        old_time = datetime.now().timestamp() - (48 * 3600)
        os.utime(valid_file, (old_time, old_time))

        event = Event(
            batch_id=batch_id,
            camera_id=camera_id,
            started_at=datetime.now(UTC) - timedelta(days=2),
            risk_score=50,
            clip_path=str(valid_file),
        )
        session.add(event)
        await session.commit()

    # Create old orphan file (should be deleted)
    old_orphan = tmp_path / "event_999997.mp4"
    old_orphan.write_text("old orphan")
    os.utime(old_orphan, (old_time, old_time))

    # Create young orphan file (should be skipped)
    young_orphan = tmp_path / "event_999996.mp4"
    young_orphan.write_text("young orphan")
    # No utime - file is brand new

    # Run cleanup
    service = OrphanedFileCleanupService(
        clips_directory=str(tmp_path),
        age_threshold_hours=24,
    )
    stats = await service.run_cleanup()

    # Verify statistics
    assert stats.files_scanned >= 3  # At least our 3 files
    assert stats.orphans_found >= 1  # At least old_orphan
    assert stats.files_deleted >= 1  # old_orphan deleted
    assert stats.files_skipped_young >= 1  # young_orphan skipped

    # Verify correct files exist/deleted
    assert valid_file.exists()  # Valid file kept
    assert not old_orphan.exists()  # Old orphan deleted
    assert young_orphan.exists()  # Young orphan kept


@pytest.mark.slow
@pytest.mark.asyncio
async def test_orphan_cleanup_handles_mixed_file_types(test_db, tmp_path):
    """Test orphan cleanup handles different video file extensions.

    Given: Clip files with different extensions (.mp4, .webm, .mkv)
    When: Orphan cleanup runs
    Then: All video file types should be processed
    """
    # Create orphan files with different extensions
    old_time = datetime.now().timestamp() - (48 * 3600)

    mp4_file = tmp_path / "event_111.mp4"
    mp4_file.write_text("mp4 orphan")
    os.utime(mp4_file, (old_time, old_time))

    webm_file = tmp_path / "event_222.webm"
    webm_file.write_text("webm orphan")
    os.utime(webm_file, (old_time, old_time))

    mkv_file = tmp_path / "event_333.mkv"
    mkv_file.write_text("mkv orphan")
    os.utime(mkv_file, (old_time, old_time))

    # Create a non-video file (should not be processed)
    txt_file = tmp_path / "notes.txt"
    txt_file.write_text("not a video")
    os.utime(txt_file, (old_time, old_time))

    # Run cleanup
    service = OrphanedFileCleanupService(
        clips_directory=str(tmp_path),
        age_threshold_hours=24,
    )
    stats = await service.run_cleanup()

    # Verify video files were processed
    assert not mp4_file.exists()
    assert not webm_file.exists()
    assert not mkv_file.exists()

    # Non-video file should remain
    assert txt_file.exists()


@pytest.mark.slow
@pytest.mark.asyncio
async def test_orphan_cleanup_handles_nested_directories(test_db, tmp_path):
    """Test orphan cleanup scans nested directories.

    Given: Clip files in nested subdirectories
    When: Orphan cleanup runs
    Then: Files in all subdirectories should be processed
    """
    old_time = datetime.now().timestamp() - (48 * 3600)

    # Create nested directory structure
    subdir1 = tmp_path / "camera1"
    subdir1.mkdir()
    subdir2 = tmp_path / "camera1" / "2024"
    subdir2.mkdir()

    # Create orphan in root
    root_orphan = tmp_path / "event_100.mp4"
    root_orphan.write_text("root orphan")
    os.utime(root_orphan, (old_time, old_time))

    # Create orphan in subdirectory
    nested_orphan = subdir2 / "event_200.mp4"
    nested_orphan.write_text("nested orphan")
    os.utime(nested_orphan, (old_time, old_time))

    # Run cleanup
    service = OrphanedFileCleanupService(
        clips_directory=str(tmp_path),
        age_threshold_hours=24,
    )
    stats = await service.run_cleanup()

    # Verify both files were deleted
    assert not root_orphan.exists()
    assert not nested_orphan.exists()
    assert stats.files_deleted >= 2


# =============================================================================
# Job tracker integration tests
# =============================================================================


@pytest.mark.slow
@pytest.mark.asyncio
async def test_orphan_cleanup_integrates_with_job_tracker(test_db, tmp_path):
    """Test orphan cleanup integrates with job tracker.

    Given: An OrphanedFileCleanupService with a job tracker
    When: Cleanup runs
    Then: Job should be created, updated, and completed
    """
    from unittest.mock import MagicMock

    mock_tracker = MagicMock()
    mock_tracker.create_job = MagicMock(return_value="test-job-123")
    mock_tracker.start_job = MagicMock()
    mock_tracker.update_progress = MagicMock()
    mock_tracker.complete_job = MagicMock()
    mock_tracker.fail_job = MagicMock()

    # Create an orphan file
    old_time = datetime.now().timestamp() - (48 * 3600)
    orphan_file = tmp_path / "event_777.mp4"
    orphan_file.write_text("orphan")
    os.utime(orphan_file, (old_time, old_time))

    # Run cleanup with job tracker
    service = OrphanedFileCleanupService(
        clips_directory=str(tmp_path),
        age_threshold_hours=24,
        job_tracker=mock_tracker,
    )
    stats = await service.run_cleanup()

    # Verify job tracker was used
    mock_tracker.create_job.assert_called_once_with("orphan_cleanup")
    mock_tracker.start_job.assert_called_once()
    mock_tracker.complete_job.assert_called_once()
    mock_tracker.fail_job.assert_not_called()

    # Verify result was passed to complete_job
    complete_call_args = mock_tracker.complete_job.call_args
    assert complete_call_args[0][0] == "test-job-123"
    assert "result" in complete_call_args[1] or len(complete_call_args[0]) > 1


# =============================================================================
# Service lifecycle tests
# =============================================================================


@pytest.mark.slow
@pytest.mark.asyncio
async def test_orphan_cleanup_service_lifecycle(test_db, tmp_path):
    """Test orphan cleanup service start/stop lifecycle.

    Given: An OrphanedFileCleanupService
    When: start() and stop() are called
    Then: Service should start and stop cleanly
    """
    service = OrphanedFileCleanupService(
        clips_directory=str(tmp_path),
        scan_interval_hours=1,
        enabled=True,
    )

    # Start service
    await service.start()
    assert service.running is True
    assert service._cleanup_task is not None

    # Stop service
    await service.stop()
    assert service.running is False
    assert service._cleanup_task is None


@pytest.mark.slow
@pytest.mark.asyncio
async def test_orphan_cleanup_context_manager(test_db, tmp_path):
    """Test orphan cleanup service context manager.

    Given: Using OrphanedFileCleanupService as async context manager
    When: Entering and exiting the context
    Then: Service should start and stop automatically
    """
    service = OrphanedFileCleanupService(
        clips_directory=str(tmp_path),
        scan_interval_hours=1,
        enabled=True,
    )

    async with service:
        assert service.running is True

    assert service.running is False


# =============================================================================
# Edge case tests
# =============================================================================


@pytest.mark.slow
@pytest.mark.asyncio
async def test_orphan_cleanup_handles_empty_directory(test_db, tmp_path):
    """Test orphan cleanup handles empty directory gracefully.

    Given: An empty clips directory
    When: Cleanup runs
    Then: Should complete without error with zero counts
    """
    service = OrphanedFileCleanupService(
        clips_directory=str(tmp_path),
        age_threshold_hours=24,
    )
    stats = await service.run_cleanup()

    assert stats.files_scanned == 0
    assert stats.orphans_found == 0
    assert stats.files_deleted == 0


@pytest.mark.slow
@pytest.mark.asyncio
async def test_orphan_cleanup_handles_nonexistent_directory(test_db):
    """Test orphan cleanup handles nonexistent directory gracefully.

    Given: A clips directory that doesn't exist
    When: Cleanup runs
    Then: Should complete without error with zero counts
    """
    service = OrphanedFileCleanupService(
        clips_directory="/nonexistent/path/that/does/not/exist",
        age_threshold_hours=24,
    )
    stats = await service.run_cleanup()

    assert stats.files_scanned == 0
    assert stats.orphans_found == 0
    assert stats.files_deleted == 0


@pytest.mark.slow
@pytest.mark.asyncio
async def test_orphan_cleanup_tracks_space_reclaimed(test_db, tmp_path):
    """Test orphan cleanup accurately tracks space reclaimed.

    Given: Multiple orphan files of known sizes
    When: Cleanup runs
    Then: space_reclaimed should match total size of deleted files
    """
    old_time = datetime.now().timestamp() - (48 * 3600)

    # Create files with known sizes
    file1 = tmp_path / "event_888.mp4"
    file1.write_bytes(b"x" * 1000)  # 1000 bytes
    os.utime(file1, (old_time, old_time))

    file2 = tmp_path / "event_889.mp4"
    file2.write_bytes(b"y" * 2000)  # 2000 bytes
    os.utime(file2, (old_time, old_time))

    # Run cleanup
    service = OrphanedFileCleanupService(
        clips_directory=str(tmp_path),
        age_threshold_hours=24,
    )
    stats = await service.run_cleanup()

    # Verify space tracking
    assert stats.space_reclaimed >= 3000  # At least 3000 bytes
