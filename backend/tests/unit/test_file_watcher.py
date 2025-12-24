"""Unit tests for file watcher service."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from backend.services.file_watcher import (
    FileWatcher,
    is_image_file,
    is_valid_image,
)

# Fixtures


@pytest.fixture
def temp_camera_root(tmp_path):
    """Create temporary camera directory structure."""
    camera_root = tmp_path / "foscam"
    camera_root.mkdir()

    # Create camera directories
    (camera_root / "camera1").mkdir()
    (camera_root / "camera2").mkdir()

    return camera_root


@pytest.fixture
def mock_redis_client():
    """Mock Redis client."""
    mock_client = AsyncMock()
    mock_client.add_to_queue = AsyncMock(return_value=1)
    return mock_client


@pytest.fixture
def file_watcher(temp_camera_root, mock_redis_client):
    """Create FileWatcher instance with mocked dependencies."""
    watcher = FileWatcher(
        camera_root=str(temp_camera_root),
        redis_client=mock_redis_client,
        debounce_delay=0.1,  # Shorter delay for tests
    )
    return watcher


# Helper function tests


def test_is_image_file_jpg():
    """Test is_image_file recognizes JPG files."""
    assert is_image_file("/path/to/image.jpg") is True
    assert is_image_file("/path/to/image.JPG") is True
    assert is_image_file("/path/to/image.jpeg") is True
    assert is_image_file("/path/to/image.JPEG") is True


def test_is_image_file_png():
    """Test is_image_file recognizes PNG files."""
    assert is_image_file("/path/to/image.png") is True
    assert is_image_file("/path/to/image.PNG") is True


def test_is_image_file_non_image():
    """Test is_image_file rejects non-image files."""
    assert is_image_file("/path/to/file.txt") is False
    assert is_image_file("/path/to/file.pdf") is False
    assert is_image_file("/path/to/file.mp4") is False
    assert is_image_file("/path/to/file") is False


def test_is_valid_image_valid(tmp_path):
    """Test is_valid_image accepts valid images."""
    image_path = tmp_path / "test.jpg"

    # Create a valid test image
    img = Image.new("RGB", (100, 100), color="red")
    img.save(image_path)

    assert is_valid_image(str(image_path)) is True


def test_is_valid_image_empty_file(tmp_path):
    """Test is_valid_image rejects empty files."""
    image_path = tmp_path / "empty.jpg"
    image_path.touch()  # Create empty file

    assert is_valid_image(str(image_path)) is False


def test_is_valid_image_corrupted(tmp_path):
    """Test is_valid_image rejects corrupted images."""
    image_path = tmp_path / "corrupted.jpg"

    # Write invalid image data
    image_path.write_text("This is not an image file!")

    assert is_valid_image(str(image_path)) is False


def test_is_valid_image_nonexistent():
    """Test is_valid_image rejects nonexistent files."""
    assert is_valid_image("/path/that/does/not/exist.jpg") is False


# FileWatcher initialization tests


def test_file_watcher_initialization(file_watcher, temp_camera_root):
    """Test FileWatcher initializes with correct settings."""
    assert file_watcher.camera_root == str(temp_camera_root)
    assert file_watcher.debounce_delay == 0.1
    assert file_watcher.queue_name == "detection_queue"
    assert file_watcher.observer is not None
    assert file_watcher.running is False


def test_file_watcher_initialization_custom_settings():
    """Test FileWatcher initializes with custom settings."""
    mock_redis = AsyncMock()
    watcher = FileWatcher(
        camera_root="/custom/path",
        redis_client=mock_redis,
        debounce_delay=1.0,
        queue_name="custom_queue",
    )

    assert watcher.camera_root == "/custom/path"
    assert watcher.debounce_delay == 1.0
    assert watcher.queue_name == "custom_queue"


# Camera detection tests


def test_get_camera_id_from_path(file_watcher, temp_camera_root):
    """Test extracting camera ID from file path."""
    camera1_path = temp_camera_root / "camera1" / "image.jpg"
    camera_id = file_watcher._get_camera_id_from_path(str(camera1_path))

    assert camera_id == "camera1"


def test_get_camera_id_from_path_nested(file_watcher, temp_camera_root):
    """Test extracting camera ID from nested path."""
    nested_path = temp_camera_root / "camera2" / "subdir" / "image.jpg"
    camera_id = file_watcher._get_camera_id_from_path(str(nested_path))

    assert camera_id == "camera2"


def test_get_camera_id_from_path_invalid(file_watcher):
    """Test extracting camera ID from invalid path."""
    invalid_path = "/some/random/path/image.jpg"
    camera_id = file_watcher._get_camera_id_from_path(invalid_path)

    assert camera_id is None


# File processing tests


@pytest.mark.asyncio
async def test_process_file_valid_image(file_watcher, temp_camera_root, mock_redis_client):
    """Test processing a valid image file."""
    # Create valid image
    camera_dir = temp_camera_root / "camera1"
    image_path = camera_dir / "test.jpg"
    img = Image.new("RGB", (100, 100), color="blue")
    img.save(image_path)

    await file_watcher._process_file(str(image_path))

    # Verify Redis queue was called with correct data
    mock_redis_client.add_to_queue.assert_awaited_once()
    call_args = mock_redis_client.add_to_queue.call_args[0]

    assert call_args[0] == "detection_queue"
    data = call_args[1]
    assert data["camera_id"] == "camera1"
    assert data["file_path"] == str(image_path)
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_process_file_non_image(file_watcher, temp_camera_root, mock_redis_client):
    """Test processing a non-image file."""
    camera_dir = temp_camera_root / "camera1"
    text_file = camera_dir / "notes.txt"
    text_file.write_text("Not an image")

    await file_watcher._process_file(str(text_file))

    # Should not queue non-image files
    mock_redis_client.add_to_queue.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_file_invalid_image(file_watcher, temp_camera_root, mock_redis_client):
    """Test processing an invalid image file."""
    camera_dir = temp_camera_root / "camera1"
    invalid_image = camera_dir / "corrupted.jpg"
    invalid_image.write_text("This is not a valid image")

    await file_watcher._process_file(str(invalid_image))

    # Should not queue invalid images
    mock_redis_client.add_to_queue.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_file_empty_image(file_watcher, temp_camera_root, mock_redis_client):
    """Test processing an empty image file."""
    camera_dir = temp_camera_root / "camera1"
    empty_image = camera_dir / "empty.jpg"
    empty_image.touch()  # Create empty file

    await file_watcher._process_file(str(empty_image))

    # Should not queue empty files
    mock_redis_client.add_to_queue.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_file_no_camera_id(file_watcher, mock_redis_client):
    """Test processing a file without valid camera ID."""
    # File not in camera directory structure
    await file_watcher._process_file("/some/random/path/image.jpg")

    # Should not queue without camera ID
    mock_redis_client.add_to_queue.assert_not_awaited()


# Debounce tests


@pytest.mark.asyncio
async def test_debounce_multiple_events(file_watcher, temp_camera_root, mock_redis_client):
    """Test debounce prevents multiple processing of same file."""
    camera_dir = temp_camera_root / "camera1"
    image_path = camera_dir / "test.jpg"
    img = Image.new("RGB", (100, 100), color="green")
    img.save(image_path)

    # Trigger multiple events for same file
    await file_watcher._schedule_file_processing(str(image_path))
    await file_watcher._schedule_file_processing(str(image_path))
    await file_watcher._schedule_file_processing(str(image_path))

    # Wait for debounce delay + processing
    await asyncio.sleep(file_watcher.debounce_delay + 0.1)

    # Should only process once
    assert mock_redis_client.add_to_queue.await_count == 1


@pytest.mark.asyncio
async def test_debounce_different_files(file_watcher, temp_camera_root, mock_redis_client):
    """Test debounce handles different files independently."""
    camera_dir = temp_camera_root / "camera1"

    # Create two different images
    image1 = camera_dir / "test1.jpg"
    img1 = Image.new("RGB", (100, 100), color="red")
    img1.save(image1)

    image2 = camera_dir / "test2.jpg"
    img2 = Image.new("RGB", (100, 100), color="blue")
    img2.save(image2)

    # Schedule both files
    await file_watcher._schedule_file_processing(str(image1))
    await file_watcher._schedule_file_processing(str(image2))

    # Wait for debounce delay + processing
    await asyncio.sleep(file_watcher.debounce_delay + 0.1)

    # Should process both files
    assert mock_redis_client.add_to_queue.await_count == 2


# Start/Stop tests


@pytest.mark.asyncio
async def test_start_watcher(file_watcher):
    """Test starting the file watcher."""
    with patch.object(file_watcher.observer, "start") as mock_start:
        await file_watcher.start()

        assert file_watcher.running is True
        mock_start.assert_called_once()


@pytest.mark.asyncio
async def test_stop_watcher(file_watcher):
    """Test stopping the file watcher."""
    # First start it
    with patch.object(file_watcher.observer, "start"):
        await file_watcher.start()

    # Then stop it
    with (
        patch.object(file_watcher.observer, "stop") as mock_stop,
        patch.object(file_watcher.observer, "join") as mock_join,
    ):
        await file_watcher.stop()

        assert file_watcher.running is False
        mock_stop.assert_called_once()
        mock_join.assert_called_once()


@pytest.mark.asyncio
async def test_stop_watcher_cancels_pending_tasks(file_watcher, temp_camera_root):
    """Test stopping watcher cancels pending debounce tasks."""
    camera_dir = temp_camera_root / "camera1"
    image_path = camera_dir / "test.jpg"
    img = Image.new("RGB", (100, 100), color="yellow")
    img.save(image_path)

    # Start watcher
    with patch.object(file_watcher.observer, "start"):
        await file_watcher.start()

    # Schedule file processing
    await file_watcher._schedule_file_processing(str(image_path))

    # Stop immediately (before debounce completes)
    with patch.object(file_watcher.observer, "stop"), patch.object(file_watcher.observer, "join"):
        await file_watcher.stop()

    # Wait a bit to ensure task was cancelled
    await asyncio.sleep(0.2)

    # Task should be cancelled, no processing should occur
    assert file_watcher.running is False


@pytest.mark.asyncio
async def test_double_start_is_idempotent(file_watcher):
    """Test starting watcher twice doesn't cause issues."""
    with patch.object(file_watcher.observer, "start") as mock_start:
        await file_watcher.start()
        await file_watcher.start()

        # Should only start once
        assert mock_start.call_count == 1
        assert file_watcher.running is True


@pytest.mark.asyncio
async def test_stop_without_start(file_watcher):
    """Test stopping watcher that was never started."""
    with patch.object(file_watcher.observer, "stop") as _mock_stop:
        await file_watcher.stop()

        # Should not crash
        assert file_watcher.running is False


# Event handler tests


@pytest.mark.asyncio
async def test_event_handler_on_created(file_watcher, temp_camera_root):
    """Test event handler responds to file creation."""
    camera_dir = temp_camera_root / "camera1"
    image_path = camera_dir / "new_image.jpg"

    # Create valid image
    img = Image.new("RGB", (100, 100), color="purple")
    img.save(image_path)

    # Manually trigger event handler
    from watchdog.events import FileCreatedEvent

    event = FileCreatedEvent(str(image_path))

    with patch.object(file_watcher._event_handler, "_schedule_async_task") as mock_schedule:
        file_watcher._event_handler.on_created(event)
        mock_schedule.assert_called_once_with(str(image_path))


@pytest.mark.asyncio
async def test_event_handler_on_modified(file_watcher, temp_camera_root):
    """Test event handler responds to file modification."""
    camera_dir = temp_camera_root / "camera1"
    image_path = camera_dir / "image.jpg"

    # Create and modify image
    img = Image.new("RGB", (100, 100), color="orange")
    img.save(image_path)

    # Manually trigger event handler
    from watchdog.events import FileModifiedEvent

    event = FileModifiedEvent(str(image_path))

    with patch.object(file_watcher._event_handler, "_schedule_async_task") as mock_schedule:
        file_watcher._event_handler.on_modified(event)
        mock_schedule.assert_called_once_with(str(image_path))


def test_event_handler_ignores_directories(file_watcher, temp_camera_root):
    """Test event handler ignores directory events."""
    camera_dir = temp_camera_root / "camera1"
    subdir = camera_dir / "subdir"
    subdir.mkdir()

    # Manually trigger directory event
    from watchdog.events import DirCreatedEvent

    event = DirCreatedEvent(str(subdir))

    with patch.object(file_watcher, "_schedule_file_processing") as mock_schedule:
        file_watcher._event_handler.on_created(event)
        mock_schedule.assert_not_called()


# Integration-style test


@pytest.mark.asyncio
async def test_full_workflow(file_watcher, temp_camera_root, mock_redis_client):
    """Test complete workflow from file creation to queue."""
    # Start watcher
    await file_watcher.start()

    try:
        # Create valid image
        camera_dir = temp_camera_root / "camera1"
        image_path = camera_dir / "workflow_test.jpg"
        img = Image.new("RGB", (200, 200), color="cyan")
        img.save(image_path)

        # Manually schedule (simulating watchdog event)
        await file_watcher._schedule_file_processing(str(image_path))

        # Wait for debounce + processing
        await asyncio.sleep(file_watcher.debounce_delay + 0.2)

        # Verify queue was called at least once (watchdog may trigger it too)
        assert mock_redis_client.add_to_queue.await_count >= 1

        # Check that the image was queued with correct data
        found_correct_call = False
        for call in mock_redis_client.add_to_queue.call_args_list:
            if len(call[0]) >= 2:
                queue_name = call[0][0]
                data = call[0][1]
                if (
                    queue_name == "detection_queue"
                    and data["camera_id"] == "camera1"
                    and data["file_path"] == str(image_path)
                ):
                    found_correct_call = True
                    break

        assert found_correct_call, "Expected queue call with correct data not found"

    finally:
        # Stop watcher
        await file_watcher.stop()


@pytest.mark.asyncio
async def test_event_handler_without_running_loop(file_watcher, temp_camera_root):
    """Test event handler when event loop is not available."""
    camera_dir = temp_camera_root / "camera1"
    image_path = camera_dir / "test.jpg"
    img = Image.new("RGB", (100, 100), color="red")
    img.save(image_path)

    # Set loop to None to simulate no running event loop
    file_watcher._loop = None

    from watchdog.events import FileCreatedEvent

    event = FileCreatedEvent(str(image_path))

    # Should log warning but not crash
    file_watcher._event_handler.on_created(event)


@pytest.mark.asyncio
async def test_process_file_no_camera_id_warning(file_watcher, temp_camera_root, mock_redis_client):
    """Test processing file when camera ID extraction fails."""
    # Create file outside camera structure
    external_file = temp_camera_root.parent / "external.jpg"
    img = Image.new("RGB", (100, 100), color="blue")
    img.save(external_file)

    await file_watcher._process_file(str(external_file))

    # Should not queue without camera ID
    mock_redis_client.add_to_queue.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_file_queue_exception(file_watcher, temp_camera_root, mock_redis_client):
    """Test processing file when queueing raises exception."""
    camera_dir = temp_camera_root / "camera1"
    image_path = camera_dir / "test.jpg"
    img = Image.new("RGB", (100, 100), color="green")
    img.save(image_path)

    # Mock add_to_queue to raise exception
    mock_redis_client.add_to_queue.side_effect = Exception("Redis connection error")

    # Should handle exception gracefully
    await file_watcher._process_file(str(image_path))


@pytest.mark.asyncio
async def test_queue_for_detection_without_redis(file_watcher, temp_camera_root):
    """Test queueing for detection when Redis client is not configured."""
    # Set redis_client to None
    file_watcher.redis_client = None

    # Should log warning and return without error
    await file_watcher._queue_for_detection("camera1", "/path/to/image.jpg")


@pytest.mark.asyncio
async def test_start_without_event_loop(tmp_path):
    """Test starting watcher when no event loop is running."""
    mock_redis = AsyncMock()
    test_camera_root = tmp_path / "test_cameras"
    test_camera_root.mkdir()
    watcher = FileWatcher(
        camera_root=str(test_camera_root),
        redis_client=mock_redis,
        debounce_delay=0.1,
    )

    # Mock get_running_loop to raise RuntimeError
    with (
        patch("asyncio.get_running_loop", side_effect=RuntimeError("No running loop")),
        patch.object(watcher.observer, "start"),
    ):
        await watcher.start()

        # Should set _loop to None and log warning
        assert watcher._loop is None
        assert watcher.running is True


@pytest.mark.asyncio
async def test_start_creates_missing_camera_root(temp_camera_root):
    """Test starting watcher creates camera root if it doesn't exist."""
    mock_redis = AsyncMock()
    nonexistent_root = temp_camera_root / "nonexistent"

    watcher = FileWatcher(
        camera_root=str(nonexistent_root),
        redis_client=mock_redis,
        debounce_delay=0.1,
    )

    with patch.object(watcher.observer, "start"):
        await watcher.start()

        # Should create the directory
        assert nonexistent_root.exists()
        assert watcher.running is True
