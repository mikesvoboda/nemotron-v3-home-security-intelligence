"""Unit tests for cleanup service."""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from backend.models.detection import Detection
from backend.models.event import Event
from backend.models.gpu_stats import GPUStats
from backend.services.cleanup_service import CleanupService, CleanupStats

# Fixtures


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
    assert stats.thumbnails_deleted == 0
    assert stats.images_deleted == 0
    assert stats.space_reclaimed == 0


def test_cleanup_stats_to_dict():
    """Test CleanupStats converts to dictionary."""
    stats = CleanupStats()
    stats.events_deleted = 10
    stats.detections_deleted = 25
    stats.gpu_stats_deleted = 100
    stats.thumbnails_deleted = 20
    stats.images_deleted = 15
    stats.space_reclaimed = 1024000

    result = stats.to_dict()

    assert result == {
        "events_deleted": 10,
        "detections_deleted": 25,
        "gpu_stats_deleted": 100,
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


@pytest.mark.asyncio
async def test_run_cleanup_deletes_old_events(test_db):
    """Test cleanup deletes old events."""
    # Create old event (40 days ago)
    old_date = datetime.now() - timedelta(days=40)
    from backend.models.camera import Camera

    async with test_db() as session:
        # Create camera
        camera = Camera(id="test_camera", name="Test Camera", folder_path="/export/foscam/test")
        session.add(camera)
        await session.flush()

        # Create old event
        old_event = Event(
            batch_id="old_batch",
            camera_id="test_camera",
            started_at=old_date,
            risk_score=50,
        )
        session.add(old_event)

        # Create recent event (10 days ago)
        recent_date = datetime.now() - timedelta(days=10)
        recent_event = Event(
            batch_id="recent_batch",
            camera_id="test_camera",
            started_at=recent_date,
            risk_score=30,
        )
        session.add(recent_event)
        await session.commit()

    # Run cleanup with 30-day retention
    service = CleanupService(retention_days=30)
    stats = await service.run_cleanup()

    # Verify old event was deleted
    assert stats.events_deleted == 1

    # Verify recent event still exists
    async with test_db() as session:
        result = await session.execute(select(Event))
        events = result.scalars().all()
        assert len(events) == 1
        assert events[0].batch_id == "recent_batch"


@pytest.mark.asyncio
async def test_run_cleanup_deletes_old_detections(test_db):
    """Test cleanup deletes old detections."""
    # Create old detection (40 days ago)
    old_date = datetime.now() - timedelta(days=40)
    from backend.models.camera import Camera

    async with test_db() as session:
        # Create camera
        camera = Camera(id="test_camera", name="Test Camera", folder_path="/export/foscam/test")
        session.add(camera)
        await session.flush()

        # Create old detection
        old_detection = Detection(
            camera_id="test_camera",
            file_path="/path/to/old.jpg",
            detected_at=old_date,
        )
        session.add(old_detection)

        # Create recent detection (10 days ago)
        recent_date = datetime.now() - timedelta(days=10)
        recent_detection = Detection(
            camera_id="test_camera",
            file_path="/path/to/recent.jpg",
            detected_at=recent_date,
        )
        session.add(recent_detection)
        await session.commit()

    # Run cleanup with 30-day retention
    service = CleanupService(retention_days=30)
    stats = await service.run_cleanup()

    # Verify old detection was deleted
    assert stats.detections_deleted == 1

    # Verify recent detection still exists
    async with test_db() as session:
        result = await session.execute(select(Detection))
        detections = result.scalars().all()
        assert len(detections) == 1
        assert detections[0].file_path == "/path/to/recent.jpg"


@pytest.mark.asyncio
async def test_run_cleanup_deletes_old_gpu_stats(test_db):
    """Test cleanup deletes old GPU stats."""
    # Create old GPU stats (40 days ago)
    old_date = datetime.now() - timedelta(days=40)

    async with test_db() as session:
        # Create old GPU stat
        old_stat = GPUStats(
            recorded_at=old_date,
            gpu_utilization=80.0,
            memory_used=10000,
        )
        session.add(old_stat)

        # Create recent GPU stat (10 days ago)
        recent_date = datetime.now() - timedelta(days=10)
        recent_stat = GPUStats(
            recorded_at=recent_date,
            gpu_utilization=60.0,
            memory_used=8000,
        )
        session.add(recent_stat)
        await session.commit()

    # Run cleanup with 30-day retention
    service = CleanupService(retention_days=30)
    stats = await service.run_cleanup()

    # Verify old stat was deleted
    assert stats.gpu_stats_deleted == 1

    # Verify recent stat still exists
    async with test_db() as session:
        result = await session.execute(select(GPUStats))
        gpu_stats = result.scalars().all()
        assert len(gpu_stats) == 1
        assert gpu_stats[0].gpu_utilization == 60.0


@pytest.mark.asyncio
async def test_run_cleanup_deletes_thumbnail_files(test_db, tmp_path):
    """Test cleanup deletes thumbnail files for deleted detections."""
    from backend.models.camera import Camera

    # Create thumbnail directory
    thumbnail_dir = tmp_path / "thumbnails"
    thumbnail_dir.mkdir()

    # Create thumbnail file
    thumbnail_path = thumbnail_dir / "old_detection_thumb.jpg"
    thumbnail_path.write_text("thumbnail data")

    # Create old detection with thumbnail
    old_date = datetime.now() - timedelta(days=40)

    async with test_db() as session:
        camera = Camera(id="test_camera", name="Test Camera", folder_path="/export/foscam/test")
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id="test_camera",
            file_path="/path/to/old.jpg",
            detected_at=old_date,
            thumbnail_path=str(thumbnail_path),
        )
        session.add(detection)
        await session.commit()

    # Run cleanup
    service = CleanupService(retention_days=30, thumbnail_dir=str(thumbnail_dir))
    stats = await service.run_cleanup()

    # Verify detection was deleted
    assert stats.detections_deleted == 1
    assert stats.thumbnails_deleted == 1

    # Verify thumbnail file was deleted
    assert not thumbnail_path.exists()


@pytest.mark.asyncio
async def test_run_cleanup_deletes_images_when_enabled(test_db, tmp_path):
    """Test cleanup deletes original images when delete_images is enabled."""
    from backend.models.camera import Camera

    # Create image file
    image_path = tmp_path / "old_image.jpg"
    image_path.write_text("image data")

    # Create old detection
    old_date = datetime.now() - timedelta(days=40)

    async with test_db() as session:
        camera = Camera(id="test_camera", name="Test Camera", folder_path="/export/foscam/test")
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id="test_camera",
            file_path=str(image_path),
            detected_at=old_date,
        )
        session.add(detection)
        await session.commit()

    # Run cleanup with delete_images enabled
    service = CleanupService(retention_days=30, delete_images=True)
    stats = await service.run_cleanup()

    # Verify image was deleted
    assert stats.detections_deleted == 1
    assert stats.images_deleted == 1
    assert not image_path.exists()


@pytest.mark.asyncio
async def test_run_cleanup_keeps_images_when_disabled(test_db, tmp_path):
    """Test cleanup keeps original images when delete_images is disabled."""
    from backend.models.camera import Camera

    # Create image file
    image_path = tmp_path / "old_image.jpg"
    image_path.write_text("image data")

    # Create old detection
    old_date = datetime.now() - timedelta(days=40)

    async with test_db() as session:
        camera = Camera(id="test_camera", name="Test Camera", folder_path="/export/foscam/test")
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id="test_camera",
            file_path=str(image_path),
            detected_at=old_date,
        )
        session.add(detection)
        await session.commit()

    # Run cleanup with delete_images disabled
    service = CleanupService(retention_days=30, delete_images=False)
    stats = await service.run_cleanup()

    # Verify detection was deleted but image kept
    assert stats.detections_deleted == 1
    assert stats.images_deleted == 0
    assert image_path.exists()


@pytest.mark.asyncio
async def test_run_cleanup_no_old_data(test_db):
    """Test cleanup when there's no old data to delete."""
    from backend.models.camera import Camera

    # Create only recent data (10 days ago)
    recent_date = datetime.now() - timedelta(days=10)

    async with test_db() as session:
        camera = Camera(id="test_camera", name="Test Camera", folder_path="/export/foscam/test")
        session.add(camera)
        await session.flush()

        event = Event(
            batch_id="recent",
            camera_id="test_camera",
            started_at=recent_date,
        )
        session.add(event)
        await session.commit()

    # Run cleanup with 30-day retention
    service = CleanupService(retention_days=30)
    stats = await service.run_cleanup()

    # Verify nothing was deleted
    assert stats.events_deleted == 0
    assert stats.detections_deleted == 0
    assert stats.gpu_stats_deleted == 0


@pytest.mark.asyncio
async def test_run_cleanup_handles_missing_files(test_db):
    """Test cleanup handles missing thumbnail files gracefully."""
    from backend.models.camera import Camera

    # Create old detection with nonexistent thumbnail
    old_date = datetime.now() - timedelta(days=40)

    async with test_db() as session:
        camera = Camera(id="test_camera", name="Test Camera", folder_path="/export/foscam/test")
        session.add(camera)
        await session.flush()

        detection = Detection(
            camera_id="test_camera",
            file_path="/path/to/old.jpg",
            detected_at=old_date,
            thumbnail_path="/nonexistent/thumbnail.jpg",
        )
        session.add(detection)
        await session.commit()

    # Run cleanup
    service = CleanupService(retention_days=30)
    stats = await service.run_cleanup()

    # Verify detection was deleted but no files were deleted
    assert stats.detections_deleted == 1
    assert stats.thumbnails_deleted == 0


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
