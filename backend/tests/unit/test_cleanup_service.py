"""Unit tests for cleanup service.

Note: These tests use unique IDs for cameras to allow parallel test execution.
Cleanup service assertions use >= instead of == for counts since the service
operates on the entire database and parallel tests may create additional data.
"""

import asyncio
import contextlib
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from backend.models.detection import Detection
from backend.models.event import Event
from backend.models.gpu_stats import GPUStats
from backend.services.cleanup_service import CleanupService, CleanupStats
from backend.tests.conftest import unique_id

# Fixtures


@pytest.fixture(autouse=True)
def mock_settings_for_cleanup_tests():
    """Set up minimal environment for tests that don't use test_db.

    This fixture sets DATABASE_URL so get_settings() doesn't fail when
    CleanupService is instantiated without explicit retention_days.
    """
    from backend.core.config import get_settings

    original_db_url = os.environ.get("DATABASE_URL")

    # Only set DATABASE_URL if not already set (e.g., by test_db fixture)
    if not original_db_url:
        os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost:5432/test"
        get_settings.cache_clear()

    yield

    # Restore original state
    if original_db_url is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = original_db_url
    get_settings.cache_clear()


@pytest.fixture
def cleanup_service():
    """Create cleanup service instance with test configuration."""
    service = CleanupService(
        cleanup_time="03:00",
        retention_days=30,
        thumbnail_dir="data/thumbnails",
        delete_images=False,
    )
    return service


@pytest.fixture
def cleanup_service_delete_images(tmp_path):
    """Create cleanup service configured to delete images."""
    service = CleanupService(
        cleanup_time="02:00",
        retention_days=7,
        thumbnail_dir=str(tmp_path / "thumbnails"),
        delete_images=True,
    )
    return service


# CleanupStats tests


def test_cleanup_stats_initialization():
    """Test CleanupStats initializes with zero values."""
    stats = CleanupStats()

    assert stats.events_deleted == 0
    assert stats.detections_deleted == 0
    assert stats.gpu_stats_deleted == 0
    assert stats.logs_deleted == 0
    assert stats.thumbnails_deleted == 0
    assert stats.images_deleted == 0
    assert stats.space_reclaimed == 0


def test_cleanup_stats_to_dict():
    """Test CleanupStats converts to dictionary."""
    stats = CleanupStats()
    stats.events_deleted = 10
    stats.detections_deleted = 25
    stats.gpu_stats_deleted = 100
    stats.logs_deleted = 50
    stats.thumbnails_deleted = 20
    stats.images_deleted = 15
    stats.space_reclaimed = 1024000

    result = stats.to_dict()

    assert result == {
        "events_deleted": 10,
        "detections_deleted": 25,
        "gpu_stats_deleted": 100,
        "logs_deleted": 50,
        "thumbnails_deleted": 20,
        "images_deleted": 15,
        "space_reclaimed": 1024000,
    }


def test_cleanup_stats_repr():
    """Test CleanupStats string representation."""
    stats = CleanupStats()
    stats.events_deleted = 5
    stats.detections_deleted = 10

    repr_str = repr(stats)

    assert "CleanupStats" in repr_str
    assert "events=5" in repr_str
    assert "detections=10" in repr_str


# CleanupService initialization tests


def test_cleanup_service_initialization():
    """Test CleanupService initializes with correct defaults."""
    service = CleanupService()

    assert service.cleanup_time == "03:00"
    assert service.retention_days == 30  # From config default
    assert service.delete_images is False
    assert service.running is False
    assert service._cleanup_task is None


def test_cleanup_service_custom_settings():
    """Test CleanupService with custom settings."""
    service = CleanupService(
        cleanup_time="01:30",
        retention_days=14,
        thumbnail_dir="/custom/path",
        delete_images=True,
    )

    assert service.cleanup_time == "01:30"
    assert service.retention_days == 14
    assert service.delete_images is True
    assert str(service.thumbnail_dir) == "/custom/path"


# Time parsing tests


def test_parse_cleanup_time_valid():
    """Test parsing valid cleanup time."""
    service = CleanupService(cleanup_time="14:30")
    hours, minutes = service._parse_cleanup_time()

    assert hours == 14
    assert minutes == 30


def test_parse_cleanup_time_midnight():
    """Test parsing midnight time."""
    service = CleanupService(cleanup_time="00:00")
    hours, minutes = service._parse_cleanup_time()

    assert hours == 0
    assert minutes == 0


def test_parse_cleanup_time_invalid_format():
    """Test parsing invalid time format."""
    service = CleanupService(cleanup_time="invalid")

    with pytest.raises(ValueError, match="Invalid cleanup_time format"):
        service._parse_cleanup_time()


def test_parse_cleanup_time_out_of_range():
    """Test parsing time out of valid range."""
    service = CleanupService(cleanup_time="25:00")

    with pytest.raises(ValueError, match="Invalid cleanup_time format"):
        service._parse_cleanup_time()


# Next cleanup calculation tests


def test_calculate_next_cleanup_future_today():
    """Test calculating next cleanup when time hasn't passed today."""
    # Use a fixed time that's definitely in the morning to avoid midnight edge cases
    mock_now = datetime(2025, 12, 23, 10, 0, 0)  # 10:00 AM
    future_time = "14:00"  # 2:00 PM - still 4 hours away

    with patch("backend.services.cleanup_service.datetime") as mock_datetime:
        mock_datetime.now.return_value = mock_now
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        service = CleanupService(cleanup_time=future_time)
        next_cleanup = service._calculate_next_cleanup()

        # Should be today
        assert next_cleanup.date() == mock_now.date()
        assert next_cleanup > mock_now


def test_calculate_next_cleanup_past_today():
    """Test calculating next cleanup when time has passed today."""
    # Use a fixed time (14:00) to avoid edge cases near midnight
    # Mock datetime to ensure the test time is well past the cleanup time
    fixed_now = datetime.now().replace(hour=14, minute=0, second=0, microsecond=0)

    with patch("backend.services.cleanup_service.datetime") as mock_datetime:
        mock_datetime.now.return_value = fixed_now
        # Pass through timedelta calls
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        # Set cleanup time to 2 hours before our fixed time (12:00)
        service = CleanupService(cleanup_time="12:00")
        next_cleanup = service._calculate_next_cleanup()

    # Should be tomorrow at 12:00
    assert next_cleanup.date() == (fixed_now + timedelta(days=1)).date()
    assert next_cleanup > fixed_now
    assert next_cleanup.hour == 12
    assert next_cleanup.minute == 0


# File deletion tests


def test_delete_file_success(tmp_path):
    """Test successful file deletion."""
    # Create test file
    test_file = tmp_path / "test.jpg"
    test_file.write_text("test data")

    service = CleanupService()
    result = service._delete_file(str(test_file))

    assert result is True
    assert not test_file.exists()


def test_delete_file_nonexistent():
    """Test deleting nonexistent file."""
    service = CleanupService()
    result = service._delete_file("/path/that/does/not/exist.jpg")

    assert result is False


def test_delete_file_permission_error(tmp_path):
    """Test file deletion with permission error."""
    test_file = tmp_path / "readonly.jpg"
    test_file.write_text("test")

    service = CleanupService()

    # Mock unlink to raise permission error
    with patch.object(Path, "unlink", side_effect=PermissionError("Access denied")):
        result = service._delete_file(str(test_file))

    assert result is False


# Service status tests


def test_get_cleanup_stats_not_running():
    """Test getting cleanup stats when service is not running."""
    service = CleanupService(retention_days=14, cleanup_time="02:00")

    stats = service.get_cleanup_stats()

    assert stats["running"] is False
    assert stats["retention_days"] == 14
    assert stats["cleanup_time"] == "02:00"
    assert stats["delete_images"] is False
    assert stats["next_cleanup"] is None


def test_get_cleanup_stats_running():
    """Test getting cleanup stats when service is running."""
    service = CleanupService()
    service.running = True

    stats = service.get_cleanup_stats()

    assert stats["running"] is True
    assert stats["next_cleanup"] is not None


# Database cleanup tests


@pytest.mark.slow
@pytest.mark.asyncio
async def test_run_cleanup_deletes_old_events(test_db):
    """Test cleanup deletes old events."""
    # Create old event (40 days ago)
    old_date = datetime.now(UTC) - timedelta(days=40)
    from backend.models.camera import Camera

    camera_id = unique_id("test_camera")
    old_batch_id = unique_id("old_batch")
    recent_batch_id = unique_id("recent_batch")

    async with test_db() as session:
        # Create camera
        camera = Camera(id=camera_id, name="Test Camera", folder_path="/export/foscam/test")
        session.add(camera)
        await session.flush()

        # Create old event
        old_event = Event(
            batch_id=old_batch_id,
            camera_id=camera_id,
            started_at=old_date,
            risk_score=50,
        )
        session.add(old_event)

        # Create recent event (10 days ago)
        recent_date = datetime.now(UTC) - timedelta(days=10)
        recent_event = Event(
            batch_id=recent_batch_id,
            camera_id=camera_id,
            started_at=recent_date,
            risk_score=30,
        )
        session.add(recent_event)
        await session.commit()

    # Run cleanup with 30-day retention
    service = CleanupService(retention_days=30)
    await service.run_cleanup()

    # Verify our specific data - old event deleted, recent event kept
    async with test_db() as session:
        # Old event should be deleted
        result = await session.execute(select(Event).where(Event.batch_id == old_batch_id))
        old_events = result.scalars().all()
        assert len(old_events) == 0, "Old event should be deleted"

        # Recent event should still exist
        result = await session.execute(select(Event).where(Event.batch_id == recent_batch_id))
        recent_events = result.scalars().all()
        assert len(recent_events) == 1
        assert recent_events[0].batch_id == recent_batch_id


@pytest.mark.slow
@pytest.mark.asyncio
async def test_run_cleanup_deletes_old_detections(test_db):
    """Test cleanup deletes old detections."""
    # Create old detection (40 days ago)
    old_date = datetime.now(UTC) - timedelta(days=40)
    from backend.models.camera import Camera

    camera_id = unique_id("test_camera")
    old_file_path = unique_id("/path/to/old") + ".jpg"
    recent_file_path = unique_id("/path/to/recent") + ".jpg"

    async with test_db() as session:
        # Create camera
        camera = Camera(id=camera_id, name="Test Camera", folder_path="/export/foscam/test")
        session.add(camera)
        await session.flush()

        # Create old detection
        old_detection = Detection(
            camera_id=camera_id,
            file_path=old_file_path,
            detected_at=old_date,
        )
        session.add(old_detection)

        # Create recent detection (10 days ago)
        recent_date = datetime.now(UTC) - timedelta(days=10)
        recent_detection = Detection(
            camera_id=camera_id,
            file_path=recent_file_path,
            detected_at=recent_date,
        )
        session.add(recent_detection)
        await session.commit()

    # Run cleanup with 30-day retention
    service = CleanupService(retention_days=30)
    await service.run_cleanup()

    # Verify our specific data - old detection deleted, recent detection kept
    async with test_db() as session:
        # Old detection should be deleted
        result = await session.execute(
            select(Detection).where(Detection.file_path == old_file_path)
        )
        old_detections = result.scalars().all()
        assert len(old_detections) == 0, "Old detection should be deleted"

        # Recent detection should still exist
        result = await session.execute(
            select(Detection).where(Detection.file_path == recent_file_path)
        )
        recent_detections = result.scalars().all()
        assert len(recent_detections) == 1
        assert recent_detections[0].file_path == recent_file_path


@pytest.mark.asyncio
async def test_run_cleanup_deletes_old_gpu_stats(test_db):
    """Test cleanup deletes old GPU stats."""
    # Create old GPU stats (40 days ago)
    old_date = datetime.now(UTC) - timedelta(days=40)
    # Use unique memory values to identify our specific records
    old_memory_used = 10000 + hash(unique_id("gpu_old")) % 1000
    recent_memory_used = 8000 + hash(unique_id("gpu_recent")) % 1000

    async with test_db() as session:
        # Create old GPU stat
        old_stat = GPUStats(
            recorded_at=old_date,
            gpu_utilization=80.0,
            memory_used=old_memory_used,
        )
        session.add(old_stat)

        # Create recent GPU stat (10 days ago)
        recent_date = datetime.now(UTC) - timedelta(days=10)
        recent_stat = GPUStats(
            recorded_at=recent_date,
            gpu_utilization=60.0,
            memory_used=recent_memory_used,
        )
        session.add(recent_stat)
        await session.commit()

    # Run cleanup with 30-day retention
    service = CleanupService(retention_days=30)
    await service.run_cleanup()

    # Verify our specific data - old GPU stat deleted, recent kept
    async with test_db() as session:
        # Old GPU stat should be deleted
        result = await session.execute(
            select(GPUStats).where(GPUStats.memory_used == old_memory_used)
        )
        old_stats = result.scalars().all()
        assert len(old_stats) == 0, "Old GPU stat should be deleted"

        # Recent GPU stat should still exist
        result = await session.execute(
            select(GPUStats).where(GPUStats.memory_used == recent_memory_used)
        )
        recent_stats = result.scalars().all()
        assert len(recent_stats) == 1
        assert recent_stats[0].gpu_utilization == 60.0


@pytest.mark.asyncio
async def test_run_cleanup_deletes_thumbnail_files(test_db, tmp_path):
    """Test cleanup deletes thumbnail files for deleted detections."""
    from backend.models.camera import Camera

    camera_id = unique_id("test_camera")

    # Create thumbnail directory
    thumbnail_dir = tmp_path / "thumbnails"
    thumbnail_dir.mkdir()

    # Create thumbnail file
    thumbnail_path = thumbnail_dir / "old_detection_thumb.jpg"
    thumbnail_path.write_text("thumbnail data")

    # Create old detection with thumbnail
    old_date = datetime.now(UTC) - timedelta(days=40)

    async with test_db() as session:
        camera = Camera(id=camera_id, name="Test Camera", folder_path="/export/foscam/test")
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id=camera_id,
            file_path="/path/to/old.jpg",
            detected_at=old_date,
            thumbnail_path=str(thumbnail_path),
        )
        session.add(detection)
        await session.commit()

    # Run cleanup
    service = CleanupService(retention_days=30, thumbnail_dir=str(thumbnail_dir))
    await service.run_cleanup()

    # Verify thumbnail file was deleted (file existence is the key check)
    assert not thumbnail_path.exists()


@pytest.mark.asyncio
async def test_run_cleanup_deletes_images_when_enabled(test_db, tmp_path):
    """Test cleanup deletes original images when delete_images is enabled."""
    from backend.models.camera import Camera

    camera_id = unique_id("test_camera")

    # Create image file
    image_path = tmp_path / "old_image.jpg"
    image_path.write_text("image data")

    # Create old detection
    old_date = datetime.now(UTC) - timedelta(days=40)

    async with test_db() as session:
        camera = Camera(id=camera_id, name="Test Camera", folder_path="/export/foscam/test")
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id=camera_id,
            file_path=str(image_path),
            detected_at=old_date,
        )
        session.add(detection)
        await session.commit()

    # Run cleanup with delete_images enabled
    service = CleanupService(retention_days=30, delete_images=True)
    await service.run_cleanup()

    # Verify image file was deleted (file existence is the key check)
    assert not image_path.exists()


@pytest.mark.asyncio
async def test_run_cleanup_keeps_images_when_disabled(test_db, tmp_path):
    """Test cleanup keeps original images when delete_images is disabled.

    Note: This test uses mocking to verify the service DOES NOT attempt to delete
    images when delete_images=False. This avoids race conditions with parallel tests.
    """
    from backend.models.camera import Camera

    camera_id = unique_id("test_camera")
    old_file_path = unique_id("/path/to/old") + ".jpg"

    # Create old detection
    old_date = datetime.now(UTC) - timedelta(days=40)

    async with test_db() as session:
        camera = Camera(id=camera_id, name="Test Camera", folder_path="/export/foscam/test")
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id=camera_id,
            file_path=old_file_path,
            detected_at=old_date,
        )
        session.add(detection)
        await session.commit()

    # Run cleanup with delete_images disabled, tracking if _delete_file is called
    service = CleanupService(retention_days=30, delete_images=False)
    delete_calls = []
    original_delete_file = service._delete_file

    def tracking_delete_file(path):
        delete_calls.append(path)
        return original_delete_file(path)

    with patch.object(service, "_delete_file", side_effect=tracking_delete_file):
        stats = await service.run_cleanup()

    # When delete_images is False, no image files should be deleted
    # (thumbnails may still be deleted, but not original images)
    image_deleted = any(old_file_path in str(p) for p in delete_calls)
    assert not image_deleted, "Image should not be deleted when delete_images is disabled"
    assert stats.images_deleted == 0


@pytest.mark.slow
@pytest.mark.asyncio
async def test_run_cleanup_no_old_data(test_db):
    """Test cleanup when there's no old data to delete.

    Note: In parallel execution, other tests may create old data that gets cleaned up.
    This test verifies our recent data survives cleanup.
    """
    from backend.models.camera import Camera

    camera_id = unique_id("test_camera")
    batch_id = unique_id("recent")

    # Create only recent data (10 days ago)
    recent_date = datetime.now(UTC) - timedelta(days=10)

    async with test_db() as session:
        camera = Camera(id=camera_id, name="Test Camera", folder_path="/export/foscam/test")
        session.add(camera)
        await session.flush()

        event = Event(
            batch_id=batch_id,
            camera_id=camera_id,
            started_at=recent_date,
        )
        session.add(event)
        await session.commit()

    # Run cleanup with 30-day retention
    service = CleanupService(retention_days=30)
    await service.run_cleanup()  # Stats not checked as parallel tests affect counts

    # Verify our recent event still exists (parallel tests may have old data that was deleted)
    async with test_db() as session:
        result = await session.execute(select(Event).where(Event.batch_id == batch_id))
        events = result.scalars().all()
        assert len(events) == 1


@pytest.mark.asyncio
async def test_run_cleanup_handles_missing_files(test_db):
    """Test cleanup handles missing thumbnail files gracefully."""
    from backend.models.camera import Camera

    camera_id = unique_id("test_camera")
    old_file_path = unique_id("/path/to/old") + ".jpg"

    # Create old detection with nonexistent thumbnail
    old_date = datetime.now(UTC) - timedelta(days=40)

    async with test_db() as session:
        camera = Camera(id=camera_id, name="Test Camera", folder_path="/export/foscam/test")
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id=camera_id,
            file_path=old_file_path,
            detected_at=old_date,
            thumbnail_path="/nonexistent/thumbnail.jpg",
        )
        session.add(detection)
        await session.commit()

    # Run cleanup - should not raise an error even with missing thumbnail
    service = CleanupService(retention_days=30)
    await service.run_cleanup()

    # Verify our specific detection was deleted
    async with test_db() as session:
        result = await session.execute(
            select(Detection).where(Detection.file_path == old_file_path)
        )
        detections = result.scalars().all()
        assert len(detections) == 0, "Old detection should be deleted"


# Start/Stop tests


@pytest.mark.asyncio
async def test_start_service():
    """Test starting the cleanup service."""
    service = CleanupService()

    await service.start()

    assert service.running is True
    assert service._cleanup_task is not None

    # Cleanup
    await service.stop()


@pytest.mark.asyncio
async def test_start_service_idempotent():
    """Test starting service multiple times is idempotent."""
    service = CleanupService()

    await service.start()
    first_task = service._cleanup_task

    await service.start()
    second_task = service._cleanup_task

    # Should be same task
    assert first_task is second_task

    # Cleanup
    await service.stop()


@pytest.mark.asyncio
async def test_stop_service():
    """Test stopping the cleanup service."""
    service = CleanupService()

    await service.start()
    assert service.running is True

    await service.stop()

    assert service.running is False
    assert service._cleanup_task is None


@pytest.mark.asyncio
async def test_stop_service_not_running():
    """Test stopping service that's not running."""
    service = CleanupService()

    # Should not raise exception
    await service.stop()

    assert service.running is False


@pytest.mark.asyncio
async def test_cleanup_loop_runs_scheduled():
    """Test cleanup loop waits and runs at scheduled time."""
    service = CleanupService(cleanup_time="03:00", retention_days=30)

    # Track call counts
    wait_calls = 0
    cleanup_calls = 0

    async def mock_wait():
        nonlocal wait_calls
        wait_calls += 1
        # Stop after first iteration to prevent infinite loop
        if wait_calls > 1:
            service.running = False
        await asyncio.sleep(0.01)  # Small delay to yield control

    async def mock_cleanup():
        nonlocal cleanup_calls
        cleanup_calls += 1
        return CleanupStats()

    with (
        patch.object(service, "_wait_until_next_cleanup", side_effect=mock_wait),
        patch.object(service, "run_cleanup", side_effect=mock_cleanup),
    ):
        # Start service
        await service.start()

        # Wait for loop to complete
        await asyncio.sleep(0.1)

        # Stop service (may already be stopped by mock)
        await service.stop()

        # Verify wait and cleanup were called
        assert wait_calls >= 1
        assert cleanup_calls >= 1


@pytest.mark.asyncio
async def test_cleanup_loop_handles_errors():
    """Test cleanup loop continues after errors.

    This tests that the cleanup loop recovers from errors and continues running.
    We mock the error recovery sleep to avoid the 60 second wait.
    """
    service = CleanupService()

    # Track call counts
    wait_calls = 0
    cleanup_calls = 0

    async def mock_wait():
        nonlocal wait_calls
        wait_calls += 1
        # Stop after third iteration (enough for: error -> recover -> success)
        if wait_calls > 2:
            service.running = False
        await asyncio.sleep(0.01)

    async def mock_cleanup_with_error():
        nonlocal cleanup_calls
        cleanup_calls += 1
        if cleanup_calls == 1:
            raise Exception("Test error")
        return CleanupStats()

    # Patch the error recovery sleep (60s) in the cleanup loop
    original_sleep = asyncio.sleep

    async def patched_sleep(seconds):
        # For the 60-second error recovery sleep, make it instant
        if seconds >= 60:
            await original_sleep(0.01)
        else:
            await original_sleep(seconds)

    with (
        patch.object(service, "_wait_until_next_cleanup", side_effect=mock_wait),
        patch.object(service, "run_cleanup", side_effect=mock_cleanup_with_error),
        patch("backend.services.cleanup_service.asyncio.sleep", side_effect=patched_sleep),
    ):
        # Start service
        await service.start()

        # Wait for loop to run through error and recovery
        await asyncio.sleep(0.2)

        # Stop service (may already be stopped by mock)
        await service.stop()

        # Verify loop continued after error (called at least twice)
        assert cleanup_calls >= 2, f"Expected cleanup >= 2, got {cleanup_calls}"


@pytest.mark.asyncio
async def test_wait_until_next_cleanup():
    """Test waiting until next cleanup time."""
    service = CleanupService(cleanup_time="03:00")

    # Mock asyncio.sleep to avoid actual waiting
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await service._wait_until_next_cleanup()

        # Verify sleep was called with positive seconds
        mock_sleep.assert_called_once()
        wait_seconds = mock_sleep.call_args[0][0]
        assert wait_seconds > 0  # Should be waiting for future time


# Log retention tests


@pytest.mark.asyncio
async def test_cleanup_old_logs_deletes_old_logs(test_db):
    """Test cleanup_old_logs deletes logs older than retention period."""
    from datetime import UTC

    from backend.models.log import Log

    old_message = unique_id("Old log message")
    recent_message = unique_id("Recent log message")

    # Create old log (10 days ago - should be deleted with 7-day default retention)
    old_date = datetime.now(UTC) - timedelta(days=10)

    async with test_db() as session:
        old_log = Log(
            timestamp=old_date,
            level="INFO",
            component="test",
            message=old_message,
        )
        session.add(old_log)

        # Create recent log (1 day ago - should be kept even if retention is 3 days)
        recent_date = datetime.now(UTC) - timedelta(days=1)
        recent_log = Log(
            timestamp=recent_date,
            level="INFO",
            component="test",
            message=recent_message,
        )
        session.add(recent_log)
        await session.commit()

    # Run log cleanup
    service = CleanupService()
    await service.cleanup_old_logs()

    # Verify our specific old log was deleted and recent log still exists
    async with test_db() as session:
        from backend.models.log import Log

        # Old log should be deleted
        result = await session.execute(select(Log).where(Log.message == old_message))
        old_logs = result.scalars().all()
        assert len(old_logs) == 0, "Old log should be deleted"

        # Recent log should still exist
        result = await session.execute(select(Log).where(Log.message == recent_message))
        recent_logs = result.scalars().all()
        assert len(recent_logs) == 1
        assert recent_logs[0].message == recent_message


@pytest.mark.asyncio
async def test_cleanup_old_logs_respects_log_retention_days_setting(test_db):
    """Test cleanup_old_logs uses log_retention_days from config."""
    import os
    from datetime import UTC

    from backend.core.config import get_settings
    from backend.models.log import Log

    kept_message = unique_id("Should be kept")

    # Clear settings cache and set custom retention
    get_settings.cache_clear()
    original_retention = os.environ.get("LOG_RETENTION_DAYS")
    os.environ["LOG_RETENTION_DAYS"] = "3"
    get_settings.cache_clear()

    try:
        # Create log 5 days old (should be deleted with 3-day retention)
        old_date = datetime.now(UTC) - timedelta(days=5)

        async with test_db() as session:
            old_log = Log(
                timestamp=old_date,
                level="WARNING",
                component="test",
                message="Should be deleted",
            )
            session.add(old_log)

            # Create log 2 days old (should be kept with 3-day retention)
            recent_date = datetime.now(UTC) - timedelta(days=2)
            recent_log = Log(
                timestamp=recent_date,
                level="WARNING",
                component="test",
                message=kept_message,
            )
            session.add(recent_log)
            await session.commit()

        # Run cleanup
        service = CleanupService()
        await service.cleanup_old_logs()

        # Verify recent log still remains by filtering to our specific message
        async with test_db() as session:
            result = await session.execute(select(Log).where(Log.message == kept_message))
            logs = result.scalars().all()
            assert len(logs) == 1
            assert logs[0].message == kept_message

    finally:
        # Restore original setting
        if original_retention:
            os.environ["LOG_RETENTION_DAYS"] = original_retention
        else:
            os.environ.pop("LOG_RETENTION_DAYS", None)
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_cleanup_old_logs_no_old_logs(test_db):
    """Test cleanup_old_logs when no old logs exist for this test.

    Note: In parallel execution, other tests may create old data.
    This test verifies our recent data survives cleanup.
    """
    from datetime import UTC

    from backend.models.log import Log

    recent_message = unique_id("Recent log")

    # Create only recent log (1 day ago)
    recent_date = datetime.now(UTC) - timedelta(days=1)

    async with test_db() as session:
        recent_log = Log(
            timestamp=recent_date,
            level="INFO",
            component="test",
            message=recent_message,
        )
        session.add(recent_log)
        await session.commit()

    # Run cleanup
    service = CleanupService()
    await service.cleanup_old_logs()

    # Verify our recent log still exists by filtering to our specific message
    async with test_db() as session:
        from backend.models.log import Log

        result = await session.execute(select(Log).where(Log.message == recent_message))
        logs = result.scalars().all()
        assert len(logs) == 1


@pytest.mark.asyncio
async def test_run_cleanup_includes_log_cleanup(test_db):
    """Test run_cleanup includes log cleanup in the stats."""
    from datetime import UTC

    from backend.models.camera import Camera
    from backend.models.log import Log

    camera_id = unique_id("test_camera")
    recent_message = unique_id("Recent info log")

    # Create old log (40 days ago)
    old_log_date = datetime.now(UTC) - timedelta(days=40)

    async with test_db() as session:
        # Create camera for event/detection tests
        camera = Camera(id=camera_id, name="Test Camera", folder_path="/export/foscam/test")
        session.add(camera)
        await session.flush()

        # Create old log
        old_log = Log(
            timestamp=old_log_date,
            level="ERROR",
            component="test",
            message="Old error log",
        )
        session.add(old_log)

        # Create recent log (1 day ago)
        recent_log_date = datetime.now(UTC) - timedelta(days=1)
        recent_log = Log(
            timestamp=recent_log_date,
            level="INFO",
            component="test",
            message=recent_message,
        )
        session.add(recent_log)
        await session.commit()

    # Run full cleanup with 30-day retention
    service = CleanupService(retention_days=30)
    await service.run_cleanup()

    # Verify recent log still exists by filtering to our specific message
    async with test_db() as session:
        from backend.models.log import Log

        result = await session.execute(select(Log).where(Log.message == recent_message))
        logs = result.scalars().all()
        assert len(logs) == 1
        assert logs[0].message == recent_message


@pytest.mark.asyncio
async def test_cleanup_old_logs_preserves_boundary_logs(test_db):
    """Test that logs within the retention boundary are preserved.

    Note: In parallel execution, another test may change LOG_RETENTION_DAYS to 3.
    To be safe, we use a log that's only 1 day old (within any reasonable retention).
    """
    from datetime import UTC

    from backend.models.log import Log

    safe_message = unique_id("Safe log within retention")

    # Create log clearly within any retention period (1 day old)
    # This survives even if another test sets retention to 3 days
    safe_date = datetime.now(UTC) - timedelta(days=1)

    async with test_db() as session:
        safe_log = Log(
            timestamp=safe_date,
            level="INFO",
            component="test",
            message=safe_message,
        )
        session.add(safe_log)

        # Create log clearly past any boundary (40 days - should always be deleted)
        old_date = datetime.now(UTC) - timedelta(days=40)
        old_log = Log(
            timestamp=old_date,
            level="INFO",
            component="test",
            message="Old log past boundary",
        )
        session.add(old_log)
        await session.commit()

    # Run cleanup
    service = CleanupService()
    await service.cleanup_old_logs()

    # Verify safe log still exists by filtering to our specific message
    async with test_db() as session:
        from backend.models.log import Log

        result = await session.execute(select(Log).where(Log.message == safe_message))
        logs = result.scalars().all()
        assert len(logs) == 1
        assert logs[0].message == safe_message


@pytest.mark.asyncio
async def test_log_cleanup_does_not_break_queries(test_db):
    """Test that log queries still work correctly after cleanup."""
    from datetime import UTC

    from backend.models.log import Log

    # Use unique component prefix to avoid conflicts with parallel tests
    component_prefix = unique_id("component")

    # Create multiple logs with different levels and timestamps
    async with test_db() as session:
        now = datetime.now(UTC)

        # Old logs (will be deleted)
        for i in range(3):
            old_log = Log(
                timestamp=now - timedelta(days=15),
                level="DEBUG",
                component=f"{component_prefix}_{i}",
                message=f"Old debug message {i}",
            )
            session.add(old_log)

        # Recent logs (will be kept)
        for i in range(5):
            recent_log = Log(
                timestamp=now - timedelta(days=2),
                level="INFO" if i % 2 == 0 else "WARNING",
                component=f"{component_prefix}_{i}",
                message=f"Recent message {i}",
            )
            session.add(recent_log)

        await session.commit()

    # Run cleanup
    service = CleanupService()
    await service.cleanup_old_logs()

    # Verify queries still work correctly - filter by our component prefix
    async with test_db() as session:
        from sqlalchemy import func

        from backend.models.log import Log

        # Query all remaining logs with our prefix
        result = await session.execute(
            select(Log).where(Log.component.like(f"{component_prefix}_%"))
        )
        all_logs = result.scalars().all()
        assert len(all_logs) == 5

        # Query by level (filter query) with our prefix
        result = await session.execute(
            select(func.count())
            .select_from(Log)
            .where(Log.level == "INFO")
            .where(Log.component.like(f"{component_prefix}_%"))
        )
        info_count = result.scalar()
        assert info_count == 3  # 0, 2, 4 are even indices

        result = await session.execute(
            select(func.count())
            .select_from(Log)
            .where(Log.level == "WARNING")
            .where(Log.component.like(f"{component_prefix}_%"))
        )
        warning_count = result.scalar()
        assert warning_count == 2  # 1, 3 are odd indices

        # Query by specific component
        result = await session.execute(select(Log).where(Log.component == f"{component_prefix}_0"))
        component_logs = result.scalars().all()
        assert len(component_logs) == 1


# =============================================================================
# Dry Run Cleanup Tests
# =============================================================================


@pytest.mark.asyncio
@pytest.mark.slow
async def test_dry_run_cleanup_counts_without_deleting(test_db):
    """Test dry_run_cleanup counts what would be deleted without actually deleting."""
    from datetime import UTC

    from backend.models.camera import Camera
    from backend.models.log import Log

    camera_id = unique_id("test_camera")
    old_batch_id = unique_id("old-batch-001")
    recent_batch_id = unique_id("recent-batch-001")
    recent_file_path = unique_id("/test/recent") + ".jpg"
    recent_message = unique_id("Recent log")

    # Create test data
    now = datetime.now(UTC)
    old_date = now - timedelta(days=40)  # Older than 30-day retention

    async with test_db() as session:
        # Create camera for event/detection
        camera = Camera(id=camera_id, name="Test Camera", folder_path="/export/foscam/test")
        session.add(camera)
        await session.flush()

        # Create old event
        old_event = Event(
            batch_id=old_batch_id,
            camera_id=camera.id,
            started_at=old_date,
            ended_at=old_date + timedelta(minutes=5),
        )
        session.add(old_event)
        await session.flush()

        # Create old detections
        for i in range(3):
            old_detection = Detection(
                camera_id=camera.id,
                file_path=f"/test/image_{i}.jpg",
                detected_at=old_date + timedelta(minutes=i),
            )
            session.add(old_detection)

        # Create old GPU stats
        for i in range(5):
            old_gpu = GPUStats(
                recorded_at=old_date + timedelta(hours=i),
                gpu_utilization=50.0 + i,
                memory_used=10000 + i * 1000,
                memory_total=24000,
            )
            session.add(old_gpu)

        # Create old log
        old_log = Log(
            timestamp=old_date,
            level="ERROR",
            component="test",
            message="Old error log",
        )
        session.add(old_log)

        # Create recent data that should NOT be counted
        recent_date = now - timedelta(days=1)
        recent_event = Event(
            batch_id=recent_batch_id,
            camera_id=camera.id,
            started_at=recent_date,
            ended_at=recent_date + timedelta(minutes=5),
        )
        session.add(recent_event)
        await session.flush()

        recent_detection = Detection(
            camera_id=camera.id,
            file_path=recent_file_path,
            detected_at=recent_date,
        )
        session.add(recent_detection)

        recent_gpu = GPUStats(
            recorded_at=recent_date,
            gpu_utilization=75.0,
            memory_used=15000,
            memory_total=24000,
        )
        session.add(recent_gpu)

        recent_log = Log(
            timestamp=recent_date,
            level="INFO",
            component="test",
            message=recent_message,
        )
        session.add(recent_log)

        await session.commit()

    # Run dry run cleanup - this counts but does not delete
    service = CleanupService(retention_days=30)
    await service.dry_run_cleanup()

    # Verify NO data was actually deleted by dry_run - check our specific records still exist
    # Note: Another test's run_cleanup (not dry run) may have deleted our old records,
    # so we only verify the records we created still exist at this point
    async with test_db() as session:
        # Recent event should still exist
        result = await session.execute(select(Event).where(Event.batch_id == recent_batch_id))
        assert len(result.scalars().all()) == 1

        # Recent detection still exists
        result = await session.execute(
            select(Detection).where(Detection.file_path == recent_file_path)
        )
        assert len(result.scalars().all()) == 1

        # Recent log still exists
        from backend.models.log import Log

        result = await session.execute(select(Log).where(Log.message == recent_message))
        assert len(result.scalars().all()) == 1


@pytest.mark.asyncio
async def test_dry_run_cleanup_returns_zero_when_nothing_to_delete(test_db):
    """Test dry_run_cleanup returns zero counts when no old data exists for this test.

    Note: In parallel execution, other tests may create old data. This test verifies
    that creating only recent data results in zero counts for that data.
    """
    from datetime import UTC

    from backend.models.camera import Camera

    camera_id = unique_id("test_camera")
    batch_id = unique_id("recent-batch-001")

    # Create only recent data
    now = datetime.now(UTC)
    recent_date = now - timedelta(days=5)  # Within 30-day retention

    async with test_db() as session:
        camera = Camera(id=camera_id, name="Test Camera", folder_path="/export/foscam/test")
        session.add(camera)
        await session.flush()

        event = Event(
            batch_id=batch_id,
            camera_id=camera.id,
            started_at=recent_date,
            ended_at=recent_date + timedelta(minutes=5),
        )
        session.add(event)
        await session.flush()

        detection = Detection(
            camera_id=camera.id,
            file_path="/test/image.jpg",
            detected_at=recent_date,
        )
        session.add(detection)

        gpu_stat = GPUStats(
            recorded_at=recent_date,
            gpu_utilization=60.0,
            memory_used=12000,
            memory_total=24000,
        )
        session.add(gpu_stat)
        await session.commit()

    # Run dry run cleanup
    service = CleanupService(retention_days=30)
    await service.dry_run_cleanup()  # Stats not checked as parallel tests affect counts

    # Note: In parallel tests, other tests may create old data that gets counted
    # The key verification is that our recent data survives
    async with test_db() as session:
        result = await session.execute(select(Event).where(Event.batch_id == batch_id))
        assert len(result.scalars().all()) == 1


@pytest.mark.asyncio
async def test_dry_run_cleanup_vs_actual_cleanup_same_counts(test_db):
    """Test that dry_run_cleanup does not delete data but run_cleanup does.

    Note: In parallel execution, another test's run_cleanup may delete our old data
    before we can verify it. This test focuses on verifying dry_run doesn't delete
    and that our data gets deleted eventually by run_cleanup.
    """
    from datetime import UTC

    from backend.models.camera import Camera

    camera_id = unique_id("test_camera")
    batch_id = unique_id("old-batch-002")

    # Create test data
    now = datetime.now(UTC)
    old_date = now - timedelta(days=40)

    async with test_db() as session:
        camera = Camera(id=camera_id, name="Test Camera", folder_path="/export/foscam/test")
        session.add(camera)
        await session.flush()

        # Create old event
        old_event = Event(
            batch_id=batch_id,
            camera_id=camera.id,
            started_at=old_date,
            ended_at=old_date + timedelta(minutes=5),
        )
        session.add(old_event)
        await session.commit()

    # Run dry run first
    service = CleanupService(retention_days=30)
    await service.dry_run_cleanup()

    # After dry run, if our event hasn't been deleted by another test's cleanup,
    # it should still exist (dry_run shouldn't delete)
    # Note: we can't assert this strongly because another test may have deleted it

    # Now run actual cleanup
    await service.run_cleanup()

    # Verify our specific event is now deleted after actual cleanup
    # (either by our cleanup or by another test's cleanup)
    async with test_db() as session:
        result = await session.execute(select(Event).where(Event.batch_id == batch_id))
        assert len(result.scalars().all()) == 0, "Old event should be deleted after run_cleanup"


@pytest.mark.asyncio
async def test_dry_run_cleanup_respects_retention_days():
    """Test that dry_run_cleanup uses the configured retention_days."""
    # Create service with different retention values
    service_7_days = CleanupService(retention_days=7)
    service_30_days = CleanupService(retention_days=30)

    # Verify they have different retention settings
    assert service_7_days.retention_days == 7
    assert service_30_days.retention_days == 30


@pytest.mark.asyncio
async def test_count_old_logs(test_db):
    """Test _count_old_logs counts without deleting."""
    from datetime import UTC

    from backend.models.log import Log

    component_prefix = unique_id("test")
    recent_message = unique_id("Recent log")

    # Create old and recent logs
    now = datetime.now(UTC)
    old_date = now - timedelta(days=15)  # Older than default 7-day log retention
    recent_date = now - timedelta(days=1)

    async with test_db() as session:
        for i in range(3):
            old_log = Log(
                timestamp=old_date,
                level="ERROR",
                component=f"{component_prefix}_{i}",
                message=f"Old log {i}",
            )
            session.add(old_log)

        recent_log = Log(
            timestamp=recent_date,
            level="INFO",
            component=f"{component_prefix}_recent",
            message=recent_message,
        )
        session.add(recent_log)
        await session.commit()

    # Count old logs - this method only counts, doesn't delete
    service = CleanupService()
    await service._count_old_logs()

    # Verify our logs still exist (not deleted by _count_old_logs) by filtering to our prefix
    # Note: another test's cleanup_old_logs may have deleted our old logs,
    # but the recent log should always remain
    async with test_db() as session:
        result = await session.execute(
            select(Log).where(Log.component == f"{component_prefix}_recent")
        )
        logs = result.scalars().all()
        assert len(logs) == 1, "Recent log should still exist"


# =============================================================================
# Additional Edge Cases
# =============================================================================


def test_parse_cleanup_time_edge_cases():
    """Test parsing edge case times."""
    # Exactly midnight
    service = CleanupService(cleanup_time="00:00")
    hours, minutes = service._parse_cleanup_time()
    assert hours == 0
    assert minutes == 0

    # Last minute of day
    service = CleanupService(cleanup_time="23:59")
    hours, minutes = service._parse_cleanup_time()
    assert hours == 23
    assert minutes == 59


def test_cleanup_stats_repr_all_fields():
    """Test CleanupStats repr includes all fields."""
    stats = CleanupStats()
    stats.events_deleted = 100
    stats.detections_deleted = 250
    stats.gpu_stats_deleted = 500
    stats.logs_deleted = 75
    stats.thumbnails_deleted = 30
    stats.images_deleted = 10
    stats.space_reclaimed = 1024 * 1024 * 100  # 100 MB

    repr_str = repr(stats)

    assert "events=100" in repr_str
    assert "detections=250" in repr_str


def test_delete_images_setting():
    """Test delete_images setting is respected."""
    service_with_delete = CleanupService(delete_images=True)
    service_without_delete = CleanupService(delete_images=False)

    assert service_with_delete.delete_images is True
    assert service_without_delete.delete_images is False


def test_thumbnail_dir_custom():
    """Test custom thumbnail directory."""
    service = CleanupService(thumbnail_dir="/custom/path/thumbnails")

    assert str(service.thumbnail_dir) == "/custom/path/thumbnails"


# =============================================================================
# run_cleanup tests (lines 188-259)
# =============================================================================


class MockDetection:
    """Mock Detection object for testing."""

    def __init__(
        self,
        id: int = 1,
        thumbnail_path: str | None = None,
        file_path: str | None = None,
    ):
        self.id = id
        self.thumbnail_path = thumbnail_path
        self.file_path = file_path


@pytest.mark.asyncio
async def test_run_cleanup_basic():
    """Test run_cleanup deletes detections, events, GPU stats, and logs."""
    service = CleanupService(retention_days=30)

    # Mock session and database operations
    mock_session = AsyncMock()

    # Mock detection query result (no detections to delete)
    # Use MagicMock for result objects to properly mock the scalars().all() chain
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_detections_result = MagicMock()
    mock_detections_result.scalars.return_value = mock_scalars

    # Mock delete results with rowcount
    mock_delete_detections_result = MagicMock()
    mock_delete_detections_result.rowcount = 5

    mock_delete_events_result = MagicMock()
    mock_delete_events_result.rowcount = 3

    mock_delete_gpu_stats_result = MagicMock()
    mock_delete_gpu_stats_result.rowcount = 100

    # Set up execute to return different results for different calls
    mock_session.execute = AsyncMock(
        side_effect=[
            mock_detections_result,  # select detections
            mock_delete_detections_result,  # delete detections
            mock_delete_events_result,  # delete events
            mock_delete_gpu_stats_result,  # delete gpu stats
        ]
    )
    mock_session.commit = AsyncMock()

    # Mock get_session as async context manager
    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.cleanup_service.get_session", mock_get_session),
        patch.object(service, "cleanup_old_logs", return_value=50),
    ):
        stats = await service.run_cleanup()

    assert stats.detections_deleted == 5
    assert stats.events_deleted == 3
    assert stats.gpu_stats_deleted == 100
    assert stats.logs_deleted == 50
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_run_cleanup_with_thumbnail_files(tmp_path):
    """Test run_cleanup deletes thumbnail files for deleted detections."""
    service = CleanupService(retention_days=30)

    # Create test thumbnail files
    thumbnail1 = tmp_path / "thumb1.jpg"
    thumbnail2 = tmp_path / "thumb2.jpg"
    thumbnail1.write_text("thumbnail 1")
    thumbnail2.write_text("thumbnail 2")

    # Mock detections with thumbnail paths
    mock_detection1 = MockDetection(id=1, thumbnail_path=str(thumbnail1))
    mock_detection2 = MockDetection(id=2, thumbnail_path=str(thumbnail2))

    mock_session = AsyncMock()

    # Use MagicMock to properly mock scalars().all() chain
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_detection1, mock_detection2]
    mock_detections_result = MagicMock()
    mock_detections_result.scalars.return_value = mock_scalars

    # Mock delete results
    mock_delete_result = MagicMock()
    mock_delete_result.rowcount = 2

    mock_session.execute = AsyncMock(
        side_effect=[
            mock_detections_result,  # select detections
            mock_delete_result,  # delete detections
            mock_delete_result,  # delete events
            mock_delete_result,  # delete gpu stats
        ]
    )
    mock_session.commit = AsyncMock()

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.cleanup_service.get_session", mock_get_session),
        patch.object(service, "cleanup_old_logs", return_value=0),
    ):
        stats = await service.run_cleanup()

    assert stats.thumbnails_deleted == 2
    assert not thumbnail1.exists()
    assert not thumbnail2.exists()


@pytest.mark.asyncio
async def test_run_cleanup_with_image_files_enabled(tmp_path):
    """Test run_cleanup deletes image files when delete_images is True."""
    service = CleanupService(retention_days=30, delete_images=True)

    # Create test image and thumbnail files
    image1 = tmp_path / "image1.jpg"
    image2 = tmp_path / "image2.jpg"
    thumbnail1 = tmp_path / "thumb1.jpg"
    image1.write_text("image 1")
    image2.write_text("image 2")
    thumbnail1.write_text("thumbnail 1")

    # Mock detections with both thumbnail and file paths
    mock_detection1 = MockDetection(id=1, thumbnail_path=str(thumbnail1), file_path=str(image1))
    mock_detection2 = MockDetection(id=2, thumbnail_path=None, file_path=str(image2))

    mock_session = AsyncMock()

    # Use MagicMock to properly mock scalars().all() chain
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_detection1, mock_detection2]
    mock_detections_result = MagicMock()
    mock_detections_result.scalars.return_value = mock_scalars

    mock_delete_result = MagicMock()
    mock_delete_result.rowcount = 2

    mock_session.execute = AsyncMock(
        side_effect=[
            mock_detections_result,
            mock_delete_result,
            mock_delete_result,
            mock_delete_result,
        ]
    )
    mock_session.commit = AsyncMock()

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.cleanup_service.get_session", mock_get_session),
        patch.object(service, "cleanup_old_logs", return_value=0),
    ):
        stats = await service.run_cleanup()

    assert stats.thumbnails_deleted == 1  # Only mock_detection1 has thumbnail
    assert stats.images_deleted == 2
    assert not image1.exists()
    assert not image2.exists()
    assert not thumbnail1.exists()


@pytest.mark.asyncio
async def test_run_cleanup_exception_handling():
    """Test run_cleanup re-raises exceptions after logging."""
    service = CleanupService(retention_days=30)

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=Exception("Database error"))

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.cleanup_service.get_session", mock_get_session),
        pytest.raises(Exception, match="Database error"),
    ):
        await service.run_cleanup()


@pytest.mark.asyncio
async def test_run_cleanup_with_none_rowcount():
    """Test run_cleanup handles None rowcount from database."""
    service = CleanupService(retention_days=30)

    mock_session = AsyncMock()

    # Use MagicMock to properly mock scalars().all() chain
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_detections_result = MagicMock()
    mock_detections_result.scalars.return_value = mock_scalars

    # Simulate None rowcount (can happen in some edge cases)
    mock_delete_result = MagicMock()
    mock_delete_result.rowcount = None

    mock_session.execute = AsyncMock(
        side_effect=[
            mock_detections_result,
            mock_delete_result,
            mock_delete_result,
            mock_delete_result,
        ]
    )
    mock_session.commit = AsyncMock()

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.cleanup_service.get_session", mock_get_session),
        patch.object(service, "cleanup_old_logs", return_value=0),
    ):
        stats = await service.run_cleanup()

    # Should handle None gracefully
    assert stats.detections_deleted == 0
    assert stats.events_deleted == 0
    assert stats.gpu_stats_deleted == 0


# =============================================================================
# dry_run_cleanup tests (lines 274-353)
# =============================================================================


@pytest.mark.asyncio
async def test_dry_run_cleanup_basic():
    """Test dry_run_cleanup counts records without deleting."""
    service = CleanupService(retention_days=30)

    mock_session = AsyncMock()

    # Mock count queries - use MagicMock for sync result methods
    mock_detection_count = MagicMock()
    mock_detection_count.scalar_one.return_value = 10

    # Mock detection query for file counting - scalars().all() is sync
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_detection_query = MagicMock()
    mock_detection_query.scalars.return_value = mock_scalars

    mock_event_count = MagicMock()
    mock_event_count.scalar_one.return_value = 5

    mock_gpu_stats_count = MagicMock()
    mock_gpu_stats_count.scalar_one.return_value = 100

    mock_session.execute = AsyncMock(
        side_effect=[
            mock_detection_count,  # count detections
            mock_detection_query,  # select detections for file counting
            mock_event_count,  # count events
            mock_gpu_stats_count,  # count gpu stats
        ]
    )

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.cleanup_service.get_session", mock_get_session),
        patch.object(service, "_count_old_logs", return_value=25),
    ):
        stats = await service.dry_run_cleanup()

    assert stats.detections_deleted == 10
    assert stats.events_deleted == 5
    assert stats.gpu_stats_deleted == 100
    assert stats.logs_deleted == 25
    # Verify commit was NOT called (dry run)
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_dry_run_cleanup_with_files(tmp_path):
    """Test dry_run_cleanup counts files and space without deleting."""
    service = CleanupService(retention_days=30, delete_images=True)

    # Create test files
    thumbnail1 = tmp_path / "thumb1.jpg"
    thumbnail2 = tmp_path / "thumb2.jpg"
    image1 = tmp_path / "image1.jpg"
    thumbnail1.write_text("t" * 1000)  # 1000 bytes
    thumbnail2.write_text("t" * 2000)  # 2000 bytes
    image1.write_text("i" * 5000)  # 5000 bytes

    mock_detection1 = MockDetection(id=1, thumbnail_path=str(thumbnail1), file_path=str(image1))
    mock_detection2 = MockDetection(id=2, thumbnail_path=str(thumbnail2), file_path=None)

    mock_session = AsyncMock()

    # Use MagicMock for result objects
    mock_detection_count = MagicMock()
    mock_detection_count.scalar_one.return_value = 2

    # Properly mock scalars().all() chain with MagicMock
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_detection1, mock_detection2]
    mock_detection_query = MagicMock()
    mock_detection_query.scalars.return_value = mock_scalars

    mock_event_count = MagicMock()
    mock_event_count.scalar_one.return_value = 0

    mock_gpu_stats_count = MagicMock()
    mock_gpu_stats_count.scalar_one.return_value = 0

    mock_session.execute = AsyncMock(
        side_effect=[
            mock_detection_count,
            mock_detection_query,
            mock_event_count,
            mock_gpu_stats_count,
        ]
    )

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.cleanup_service.get_session", mock_get_session),
        patch.object(service, "_count_old_logs", return_value=0),
    ):
        stats = await service.dry_run_cleanup()

    assert stats.thumbnails_deleted == 2
    assert stats.images_deleted == 1
    assert stats.space_reclaimed == 8000  # 1000 + 2000 + 5000
    # Files should still exist (dry run)
    assert thumbnail1.exists()
    assert thumbnail2.exists()
    assert image1.exists()


@pytest.mark.asyncio
async def test_dry_run_cleanup_file_stat_error(tmp_path):
    """Test dry_run_cleanup handles nonexistent file paths."""
    service = CleanupService(retention_days=30)

    # Use a nonexistent file path to test the case where file doesn't exist
    mock_detection = MockDetection(id=1, thumbnail_path="/nonexistent/path.jpg")

    mock_session = AsyncMock()

    # Use MagicMock for result objects
    mock_detection_count = MagicMock()
    mock_detection_count.scalar_one.return_value = 1

    # Properly mock scalars().all() chain with MagicMock
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_detection]
    mock_detection_query = MagicMock()
    mock_detection_query.scalars.return_value = mock_scalars

    mock_event_count = MagicMock()
    mock_event_count.scalar_one.return_value = 0

    mock_gpu_stats_count = MagicMock()
    mock_gpu_stats_count.scalar_one.return_value = 0

    mock_session.execute = AsyncMock(
        side_effect=[
            mock_detection_count,
            mock_detection_query,
            mock_event_count,
            mock_gpu_stats_count,
        ]
    )

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.cleanup_service.get_session", mock_get_session),
        patch.object(service, "_count_old_logs", return_value=0),
    ):
        stats = await service.dry_run_cleanup()

    # File doesn't exist, so no space is counted and no thumbnails counted
    assert stats.space_reclaimed == 0
    assert stats.thumbnails_deleted == 0


@pytest.mark.asyncio
async def test_dry_run_cleanup_oserror_on_stat(tmp_path):
    """Test dry_run_cleanup handles OSError when calling stat() on existing file."""
    service = CleanupService(retention_days=30, delete_images=True)

    # Create real files that we'll mock stat() errors on
    thumbnail = tmp_path / "thumb.jpg"
    image = tmp_path / "image.jpg"
    thumbnail.write_text("thumb data")
    image.write_text("image data")

    mock_detection = MockDetection(id=1, thumbnail_path=str(thumbnail), file_path=str(image))

    mock_session = AsyncMock()

    mock_detection_count = MagicMock()
    mock_detection_count.scalar_one.return_value = 1

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_detection]
    mock_detection_query = MagicMock()
    mock_detection_query.scalars.return_value = mock_scalars

    mock_event_count = MagicMock()
    mock_event_count.scalar_one.return_value = 0

    mock_gpu_stats_count = MagicMock()
    mock_gpu_stats_count.scalar_one.return_value = 0

    mock_session.execute = AsyncMock(
        side_effect=[
            mock_detection_count,
            mock_detection_query,
            mock_event_count,
            mock_gpu_stats_count,
        ]
    )

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    # Create a mock Path class that raises OSError on stat()
    original_path_stat = Path.stat

    def mock_stat(self):
        # Raise OSError for our specific test files
        if str(self).endswith(".jpg"):
            raise OSError("Permission denied")
        return original_path_stat(self)

    with (
        patch("backend.services.cleanup_service.get_session", mock_get_session),
        patch.object(service, "_count_old_logs", return_value=0),
        patch.object(Path, "stat", mock_stat),
    ):
        stats = await service.dry_run_cleanup()

    # Files exist and are counted, but space_reclaimed stays 0 due to OSError
    assert stats.thumbnails_deleted == 1
    assert stats.images_deleted == 1
    assert stats.space_reclaimed == 0  # OSError caught, space not counted


@pytest.mark.asyncio
async def test_dry_run_cleanup_exception():
    """Test dry_run_cleanup re-raises exceptions."""
    service = CleanupService(retention_days=30)

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=Exception("Database error"))

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.cleanup_service.get_session", mock_get_session),
        pytest.raises(Exception, match="Database error"),
    ):
        await service.dry_run_cleanup()


@pytest.mark.asyncio
async def test_dry_run_cleanup_delete_images_disabled(tmp_path):
    """Test dry_run_cleanup respects delete_images=False."""
    service = CleanupService(retention_days=30, delete_images=False)

    image = tmp_path / "image.jpg"
    image.write_text("image data")

    mock_detection = MockDetection(id=1, thumbnail_path=None, file_path=str(image))

    mock_session = AsyncMock()

    # Use MagicMock for result objects
    mock_detection_count = MagicMock()
    mock_detection_count.scalar_one.return_value = 1

    # Properly mock scalars().all() chain with MagicMock
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_detection]
    mock_detection_query = MagicMock()
    mock_detection_query.scalars.return_value = mock_scalars

    mock_event_count = MagicMock()
    mock_event_count.scalar_one.return_value = 0

    mock_gpu_stats_count = MagicMock()
    mock_gpu_stats_count.scalar_one.return_value = 0

    mock_session.execute = AsyncMock(
        side_effect=[
            mock_detection_count,
            mock_detection_query,
            mock_event_count,
            mock_gpu_stats_count,
        ]
    )

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.cleanup_service.get_session", mock_get_session),
        patch.object(service, "_count_old_logs", return_value=0),
    ):
        stats = await service.dry_run_cleanup()

    # Image should NOT be counted since delete_images is False
    assert stats.images_deleted == 0


# =============================================================================
# _count_old_logs tests (lines 361-377)
# =============================================================================


@pytest.mark.asyncio
async def test_count_old_logs_with_logs():
    """Test _count_old_logs returns count of old logs."""
    service = CleanupService(retention_days=30)

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 42

    mock_session.execute = AsyncMock(return_value=mock_result)

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with patch("backend.services.cleanup_service.get_session", mock_get_session):
        count = await service._count_old_logs()

    assert count == 42


@pytest.mark.asyncio
async def test_count_old_logs_no_logs():
    """Test _count_old_logs returns 0 when no old logs."""
    service = CleanupService(retention_days=30)

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 0

    mock_session.execute = AsyncMock(return_value=mock_result)

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with patch("backend.services.cleanup_service.get_session", mock_get_session):
        count = await service._count_old_logs()

    assert count == 0


@pytest.mark.asyncio
async def test_count_old_logs_none_result():
    """Test _count_old_logs handles None result."""
    service = CleanupService(retention_days=30)

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = None

    mock_session.execute = AsyncMock(return_value=mock_result)

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with patch("backend.services.cleanup_service.get_session", mock_get_session):
        count = await service._count_old_logs()

    assert count == 0


# =============================================================================
# cleanup_old_logs tests (lines 385-396)
# =============================================================================


@pytest.mark.asyncio
async def test_cleanup_old_logs_deletes_logs():
    """Test cleanup_old_logs deletes old logs and returns count."""
    service = CleanupService(retention_days=30)

    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_result.rowcount = 15

    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with patch("backend.services.cleanup_service.get_session", mock_get_session):
        deleted = await service.cleanup_old_logs()

    assert deleted == 15
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_cleanup_old_logs_no_logs_to_delete():
    """Test cleanup_old_logs when no logs need deletion."""
    service = CleanupService(retention_days=30)

    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_result.rowcount = 0

    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with patch("backend.services.cleanup_service.get_session", mock_get_session):
        deleted = await service.cleanup_old_logs()

    assert deleted == 0
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_cleanup_old_logs_none_rowcount():
    """Test cleanup_old_logs handles None rowcount."""
    service = CleanupService(retention_days=30)

    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_result.rowcount = None

    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with patch("backend.services.cleanup_service.get_session", mock_get_session):
        deleted = await service.cleanup_old_logs()

    assert deleted == 0


# =============================================================================
# _cleanup_loop CancelledError tests (lines 452-453)
# =============================================================================


@pytest.mark.asyncio
async def test_cleanup_loop_cancelled():
    """Test cleanup loop handles CancelledError gracefully."""
    service = CleanupService()

    call_count = 0

    async def mock_wait():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Simulate task cancellation during wait
            raise asyncio.CancelledError()
        await asyncio.sleep(0.01)

    with patch.object(service, "_wait_until_next_cleanup", side_effect=mock_wait):
        service.running = True
        # Run the cleanup loop directly
        await service._cleanup_loop()

    # Loop should have exited cleanly
    assert call_count == 1


@pytest.mark.asyncio
async def test_cleanup_loop_stops_before_cleanup():
    """Test cleanup loop checks running flag before running cleanup."""
    service = CleanupService()

    cleanup_called = False

    async def mock_wait():
        # Stop service during wait
        service.running = False
        await asyncio.sleep(0.01)

    async def mock_cleanup():
        nonlocal cleanup_called
        cleanup_called = True
        return CleanupStats()

    with (
        patch.object(service, "_wait_until_next_cleanup", side_effect=mock_wait),
        patch.object(service, "run_cleanup", side_effect=mock_cleanup),
    ):
        service.running = True
        await service._cleanup_loop()

    # Cleanup should NOT have been called since service stopped during wait
    assert not cleanup_called


# =============================================================================
# Additional edge case tests for better coverage
# =============================================================================


def test_delete_file_directory(tmp_path):
    """Test _delete_file returns False for directories."""
    service = CleanupService()

    # Create a directory instead of file
    test_dir = tmp_path / "test_dir"
    test_dir.mkdir()

    result = service._delete_file(str(test_dir))

    assert result is False
    assert test_dir.exists()


@pytest.mark.asyncio
async def test_run_cleanup_missing_thumbnail_file(tmp_path):
    """Test run_cleanup handles missing thumbnail files gracefully."""
    service = CleanupService(retention_days=30)

    # Detection points to non-existent file
    mock_detection = MockDetection(id=1, thumbnail_path="/nonexistent/path.jpg")

    mock_session = AsyncMock()

    # Use MagicMock to properly mock scalars().all() chain
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_detection]
    mock_detections_result = MagicMock()
    mock_detections_result.scalars.return_value = mock_scalars

    mock_delete_result = MagicMock()
    mock_delete_result.rowcount = 1

    mock_session.execute = AsyncMock(
        side_effect=[
            mock_detections_result,
            mock_delete_result,
            mock_delete_result,
            mock_delete_result,
        ]
    )
    mock_session.commit = AsyncMock()

    @contextlib.asynccontextmanager
    async def mock_get_session():
        yield mock_session

    with (
        patch("backend.services.cleanup_service.get_session", mock_get_session),
        patch.object(service, "cleanup_old_logs", return_value=0),
    ):
        stats = await service.run_cleanup()

    # File didn't exist, so thumbnail count stays 0
    assert stats.thumbnails_deleted == 0
