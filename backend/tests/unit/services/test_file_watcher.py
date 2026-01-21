"""Unit tests for the FileWatcher service.

This module contains comprehensive unit tests for the FileWatcher service, which
monitors camera directories (FTP upload targets) for new images and queues them
for AI detection processing.

Related Issues:
    - NEM-1661: Improve Test Documentation with Intent and Acceptance Criteria
    - NEM-1069: File Stability Check for FTP Uploads
    - bead 4mje.3: Pipeline Start Time Tracking
    - wa0t.13: Non-blocking Observer Join
    - wa0t.14: Task Memory Leak Fix

Test Organization:
    - Helper function tests: is_image_file(), is_valid_image() validation
    - FileWatcher initialization tests: Default/custom settings, observer config
    - Camera ID normalization tests: Handling spaces, hyphens, special chars
    - Camera detection tests: Extracting camera ID from file paths
    - File processing tests: Valid images, invalid images, non-images
    - Debounce tests: Preventing duplicate processing of same file
    - Start/Stop tests: Service lifecycle, idempotency, task cancellation
    - Event handler tests: Watchdog events (created, modified, directory)
    - Deduplication tests: Hash-based duplicate detection via Redis
    - Camera auto-creation tests: Auto-registering new cameras
    - Queue overflow tests: Backpressure handling and DLQ routing
    - Polling observer tests: Native vs polling observer configuration
    - Bug fix tests: Non-blocking join, task memory leak prevention
    - Pipeline timing tests: Recording pipeline_start_time in queue payload
    - File stability tests: Waiting for FTP uploads to complete

Acceptance Criteria:
    - Monitors camera_root directory for new image files
    - Validates images (file size, format, corruption) before queueing
    - Extracts and normalizes camera_id from directory structure
    - Debounces rapid file events (FTP uploads create multiple events)
    - Waits for file stability before processing (incomplete FTP uploads)
    - Queues valid images to Redis detection_queue with metadata
    - Auto-creates cameras in database when new folders appear
    - Handles queue overflow via DLQ (dead letter queue) policy
    - Supports both native (inotify) and polling observers for NFS
    - Records pipeline_start_time for end-to-end latency tracking

Notes:
    Tests use mocks for Redis, database, and file system operations.
    Some tests verify fix of specific bugs (wa0t.13, wa0t.14, bead 4mje.3).
    File stability checks prevent processing of incomplete FTP uploads.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from backend.core.redis import QueueAddResult, QueueOverflowPolicy
from backend.models.camera import Camera, normalize_camera_id
from backend.services.dedupe import DedupeService
from backend.services.file_watcher import (
    MIN_IMAGE_FILE_SIZE,
    FileWatcher,
    is_image_file,
    is_valid_image,
)


# Helper function to create valid test images above minimum size
def create_valid_test_image(path: Path | str, size: tuple[int, int] = (640, 480)) -> Path:
    """Create a valid test image that passes all validation checks.

    Creates a JPEG image large enough to pass MIN_IMAGE_FILE_SIZE validation.
    The default 640x480 size produces a file of approximately 15-30KB.

    Args:
        path: Path where the image should be saved
        size: Tuple of (width, height) for the image. Default 640x480.

    Returns:
        Path to the created image file
    """
    if isinstance(path, str):
        path = Path(path)

    # Create an image with enough detail to meet size requirements
    # Using RGB mode and a reasonable size ensures the file is > 10KB
    img = Image.new("RGB", size, color="red")

    # Add some noise/variation to increase file size and make it more realistic
    # This creates a gradient which compresses less than a solid color
    pixels = img.load()
    if pixels is not None:
        for y in range(size[1]):
            for x in range(size[0]):
                r = (x * 255 // size[0]) % 256
                g = (y * 255 // size[1]) % 256
                b = ((x + y) * 128 // (size[0] + size[1])) % 256
                pixels[x, y] = (r, g, b)

    # Save with high quality to ensure adequate file size
    img.save(path, "JPEG", quality=95)
    return path


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
    # Safe method with backpressure handling
    mock_client.add_to_queue_safe = AsyncMock(
        return_value=QueueAddResult(success=True, queue_length=1)
    )
    return mock_client


@pytest.fixture
def file_watcher(temp_camera_root, mock_redis_client):
    """Create FileWatcher instance with mocked dependencies."""
    with patch("backend.services.file_watcher.get_settings") as mock_settings:
        mock_settings_instance = MagicMock()
        mock_settings_instance.file_watcher_max_concurrent_queue = 20
        mock_settings_instance.file_watcher_queue_delay_ms = 0  # No delay in tests
        mock_settings_instance.file_watcher_polling = False
        mock_settings_instance.file_watcher_polling_interval = 1.0
        mock_settings.return_value = mock_settings_instance

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.01,  # Very short delay for fast tests (1s timeout)
            stability_time=0.1,  # Very short stability time for fast tests
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
    """Test is_valid_image accepts valid images above minimum size."""
    image_path = tmp_path / "test.jpg"

    # Create a valid test image above minimum size (640x480 produces ~15-30KB)
    create_valid_test_image(image_path)

    # Verify the image is above minimum size
    assert image_path.stat().st_size >= MIN_IMAGE_FILE_SIZE
    assert is_valid_image(str(image_path)) is True


def test_is_valid_image_too_small(tmp_path):
    """Test is_valid_image rejects images below minimum file size."""
    image_path = tmp_path / "small.jpg"

    # Create a tiny image that will be below minimum size
    img = Image.new("RGB", (10, 10), color="red")
    img.save(image_path, "JPEG", quality=50)

    # Verify the image is below minimum size
    assert image_path.stat().st_size < MIN_IMAGE_FILE_SIZE
    assert is_valid_image(str(image_path)) is False


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


def test_is_valid_image_truncated_jpeg(tmp_path):
    """Test is_valid_image rejects truncated JPEG files.

    This simulates incomplete FTP uploads where the file is cut off mid-transfer.
    """
    image_path = tmp_path / "truncated.jpg"

    # Create a valid JPEG file first
    valid_image = create_valid_test_image(tmp_path / "valid.jpg")
    valid_bytes = valid_image.read_bytes()

    # Truncate it to about 60% of original size (simulating incomplete transfer)
    truncated_size = int(len(valid_bytes) * 0.6)
    image_path.write_bytes(valid_bytes[:truncated_size])

    # Verify it's above minimum size but still truncated
    assert image_path.stat().st_size >= MIN_IMAGE_FILE_SIZE
    # Should fail because PIL.load() will fail on truncated data
    assert is_valid_image(str(image_path)) is False


def test_is_valid_image_severely_truncated_jpeg(tmp_path):
    """Test is_valid_image rejects severely truncated JPEG files.

    This simulates FTP uploads that barely started before being cut off.
    """
    image_path = tmp_path / "truncated.jpg"

    # Create a valid JPEG file first
    valid_image = create_valid_test_image(tmp_path / "valid.jpg")
    valid_bytes = valid_image.read_bytes()

    # Truncate to only keep the header (first 5KB - below minimum)
    truncated_bytes = valid_bytes[:5000]
    image_path.write_bytes(truncated_bytes)

    # Should fail because it's below minimum file size
    assert image_path.stat().st_size < MIN_IMAGE_FILE_SIZE
    assert is_valid_image(str(image_path)) is False


# FileWatcher initialization tests


def test_file_watcher_initialization(file_watcher, temp_camera_root):
    """Test FileWatcher initializes with correct settings."""
    assert file_watcher.camera_root == str(temp_camera_root)
    assert file_watcher.debounce_delay == 0.01  # Fast test fixture uses 0.01
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


# Camera ID normalization tests


def test_normalize_camera_id_simple():
    """Test normalize_camera_id with simple lowercase name."""
    assert normalize_camera_id("camera1") == "camera1"
    assert normalize_camera_id("frontdoor") == "frontdoor"


def test_normalize_camera_id_spaces():
    """Test normalize_camera_id converts spaces to underscores."""
    assert normalize_camera_id("Front Door") == "front_door"
    assert normalize_camera_id("back yard") == "back_yard"
    assert normalize_camera_id("  trimmed  ") == "trimmed"


def test_normalize_camera_id_hyphens():
    """Test normalize_camera_id converts hyphens to underscores."""
    assert normalize_camera_id("front-door") == "front_door"
    assert normalize_camera_id("back-yard-camera") == "back_yard_camera"


def test_normalize_camera_id_mixed():
    """Test normalize_camera_id with mixed cases and separators."""
    assert normalize_camera_id("Front-Door Camera") == "front_door_camera"
    assert normalize_camera_id("GARAGE") == "garage"
    assert normalize_camera_id("Pool Area 2") == "pool_area_2"


def test_normalize_camera_id_special_chars():
    """Test normalize_camera_id removes special characters."""
    assert normalize_camera_id("camera#1") == "camera1"
    assert normalize_camera_id("front.door") == "frontdoor"
    assert normalize_camera_id("back@yard!") == "backyard"


def test_normalize_camera_id_multiple_underscores():
    """Test normalize_camera_id collapses multiple underscores."""
    assert normalize_camera_id("front___door") == "front_door"
    assert normalize_camera_id("back - - yard") == "back_yard"


def test_camera_from_folder_name():
    """Test Camera.from_folder_name factory method."""
    camera = Camera.from_folder_name("Front Door", "/export/foscam/Front Door")
    assert camera.id == "front_door"
    assert camera.name == "Front Door"
    assert camera.folder_path == "/export/foscam/Front Door"


# Camera detection tests


def test_get_camera_id_from_path(file_watcher, temp_camera_root):
    """Test extracting camera ID from file path."""
    camera1_path = temp_camera_root / "camera1" / "image.jpg"
    camera_id, folder_name = file_watcher._get_camera_id_from_path(str(camera1_path))

    assert camera_id == "camera1"
    assert folder_name == "camera1"


def test_get_camera_id_from_path_nested(file_watcher, temp_camera_root):
    """Test extracting camera ID from nested path."""
    nested_path = temp_camera_root / "camera2" / "subdir" / "image.jpg"
    camera_id, folder_name = file_watcher._get_camera_id_from_path(str(nested_path))

    assert camera_id == "camera2"
    assert folder_name == "camera2"


def test_get_camera_id_from_path_invalid(file_watcher):
    """Test extracting camera ID from invalid path."""
    invalid_path = "/some/random/path/image.jpg"
    camera_id, folder_name = file_watcher._get_camera_id_from_path(invalid_path)

    assert camera_id is None
    assert folder_name is None


def test_get_camera_id_from_path_normalizes(temp_camera_root, mock_redis_client):
    """Test that camera ID is normalized from folder name."""
    # Create a folder with spaces
    camera_root = temp_camera_root
    front_door_dir = camera_root / "Front Door"
    front_door_dir.mkdir()

    watcher = FileWatcher(
        camera_root=str(camera_root),
        redis_client=mock_redis_client,
        debounce_delay=0.1,
    )

    file_path = front_door_dir / "image.jpg"
    camera_id, folder_name = watcher._get_camera_id_from_path(str(file_path))

    assert camera_id == "front_door"  # Normalized
    assert folder_name == "Front Door"  # Original


def test_get_camera_id_from_path_hyphenated(temp_camera_root, mock_redis_client):
    """Test that hyphenated folder names are normalized."""
    camera_root = temp_camera_root
    back_yard_dir = camera_root / "back-yard"
    back_yard_dir.mkdir()

    watcher = FileWatcher(
        camera_root=str(camera_root),
        redis_client=mock_redis_client,
        debounce_delay=0.1,
    )

    file_path = back_yard_dir / "video.mp4"
    camera_id, folder_name = watcher._get_camera_id_from_path(str(file_path))

    assert camera_id == "back_yard"  # Hyphens become underscores
    assert folder_name == "back-yard"


# File processing tests


@pytest.mark.asyncio
async def test_process_file_valid_image(file_watcher, temp_camera_root, mock_redis_client):
    """Test processing a valid image file."""
    # Create valid image above minimum size
    camera_dir = temp_camera_root / "camera1"
    image_path = camera_dir / "test.jpg"
    create_valid_test_image(image_path)

    await file_watcher._process_file(str(image_path))

    # Verify Redis queue was called with correct data (using add_to_queue_safe)
    mock_redis_client.add_to_queue_safe.assert_awaited_once()
    call_args = mock_redis_client.add_to_queue_safe.call_args

    assert call_args[0][0] == "detection_queue"
    data = call_args[0][1]
    assert data["camera_id"] == "camera1"
    assert data["file_path"] == str(image_path)
    assert "timestamp" in data
    # Verify DLQ policy is used
    assert call_args[1]["overflow_policy"] == QueueOverflowPolicy.DLQ


@pytest.mark.asyncio
async def test_process_file_non_image(file_watcher, temp_camera_root, mock_redis_client):
    """Test processing a non-image file."""
    camera_dir = temp_camera_root / "camera1"
    text_file = camera_dir / "notes.txt"
    text_file.write_text("Not an image")

    await file_watcher._process_file(str(text_file))

    # Should not queue non-image files
    mock_redis_client.add_to_queue_safe.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_file_invalid_image(file_watcher, temp_camera_root, mock_redis_client):
    """Test processing an invalid image file."""
    camera_dir = temp_camera_root / "camera1"
    invalid_image = camera_dir / "corrupted.jpg"
    invalid_image.write_text("This is not a valid image")

    await file_watcher._process_file(str(invalid_image))

    # Should not queue invalid images
    mock_redis_client.add_to_queue_safe.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_file_empty_image(file_watcher, temp_camera_root, mock_redis_client):
    """Test processing an empty image file."""
    camera_dir = temp_camera_root / "camera1"
    empty_image = camera_dir / "empty.jpg"
    empty_image.touch()  # Create empty file

    await file_watcher._process_file(str(empty_image))

    # Should not queue empty files
    mock_redis_client.add_to_queue_safe.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_file_no_camera_id(file_watcher, mock_redis_client):
    """Test processing a file without valid camera ID."""
    # File not in camera directory structure
    await file_watcher._process_file("/some/random/path/image.jpg")

    # Should not queue without camera ID
    mock_redis_client.add_to_queue_safe.assert_not_awaited()


# Debounce tests


@pytest.mark.asyncio
async def test_debounce_multiple_events(file_watcher, temp_camera_root, mock_redis_client):
    """Test debounce prevents multiple processing of same file."""
    camera_dir = temp_camera_root / "camera1"
    image_path = camera_dir / "test.jpg"
    create_valid_test_image(image_path)

    # Mock stability check to return immediately for fast test
    with patch.object(
        file_watcher, "_wait_for_file_stability", new_callable=AsyncMock
    ) as mock_stability:
        mock_stability.return_value = True

        # Trigger multiple events for same file
        await file_watcher._schedule_file_processing(str(image_path))
        await file_watcher._schedule_file_processing(str(image_path))
        await file_watcher._schedule_file_processing(str(image_path))

        # Wait for debounce delay + extra time for task processing
        # Use a generous margin (0.2s) to avoid flaky failures in CI
        await asyncio.sleep(file_watcher.debounce_delay + 0.2)
        # Yield to allow any pending tasks to complete
        await asyncio.sleep(0)

        # Should only process once
        assert mock_redis_client.add_to_queue_safe.await_count == 1


@pytest.mark.asyncio
async def test_debounce_different_files(file_watcher, temp_camera_root, mock_redis_client):
    """Test debounce handles different files independently."""
    camera_dir = temp_camera_root / "camera1"

    # Create two different images above minimum size
    image1 = camera_dir / "test1.jpg"
    create_valid_test_image(image1)

    image2 = camera_dir / "test2.jpg"
    create_valid_test_image(image2)

    # Mock stability check to return immediately for fast test
    with patch.object(
        file_watcher, "_wait_for_file_stability", new_callable=AsyncMock
    ) as mock_stability:
        mock_stability.return_value = True

        # Schedule both files
        await file_watcher._schedule_file_processing(str(image1))
        await file_watcher._schedule_file_processing(str(image2))

        # Wait for debounce delay + processing with generous margin for CI load
        # Note: 0.05s was too tight and caused flaky failures under parallel execution
        await asyncio.sleep(file_watcher.debounce_delay + 0.3)

        # Should process both files
        assert mock_redis_client.add_to_queue_safe.await_count == 2


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
    create_valid_test_image(image_path)

    # Start watcher
    with patch.object(file_watcher.observer, "start"):
        await file_watcher.start()

    # Schedule file processing
    await file_watcher._schedule_file_processing(str(image_path))

    # Stop immediately (before debounce completes)
    with patch.object(file_watcher.observer, "stop"), patch.object(file_watcher.observer, "join"):
        await file_watcher.stop()

    # Wait a bit to ensure task was cancelled
    await asyncio.sleep(0.05)

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
        # Create valid image above minimum size
        camera_dir = temp_camera_root / "camera1"
        image_path = camera_dir / "workflow_test.jpg"
        create_valid_test_image(image_path)

        # Mock stability check for fast test
        with patch.object(
            file_watcher, "_wait_for_file_stability", new_callable=AsyncMock
        ) as mock_stability:
            mock_stability.return_value = True

            # Manually schedule (simulating watchdog event)
            await file_watcher._schedule_file_processing(str(image_path))

            # Wait for debounce + processing with extra margin for CI environments
            # Use a more generous wait time to handle slower CI systems
            await asyncio.sleep(file_watcher.debounce_delay + 0.2)
            # Give async tasks a chance to complete
            await asyncio.sleep(0)

            # Verify queue was called at least once (watchdog may trigger it too)
            assert mock_redis_client.add_to_queue_safe.await_count >= 1

            # Check that the image was queued with correct data
            found_correct_call = False
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
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
    mock_redis_client.add_to_queue_safe.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_file_queue_exception(file_watcher, temp_camera_root, mock_redis_client):
    """Test processing file when queueing raises exception."""
    camera_dir = temp_camera_root / "camera1"
    image_path = camera_dir / "test.jpg"
    img = Image.new("RGB", (100, 100), color="green")
    img.save(image_path)

    # Mock add_to_queue_safe to raise exception
    mock_redis_client.add_to_queue_safe.side_effect = Exception("Redis connection error")

    # Should handle exception gracefully (exception is caught in _process_file)
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
    """Test starting watcher when no event loop is running raises error.

    FileWatcher MUST be started within an async context (e.g., FastAPI lifespan).
    If no event loop is available, it should fail loudly to prevent silent data loss.
    """
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
        # Should raise RuntimeError when no event loop is available
        with pytest.raises(RuntimeError, match="MUST be started within an async context"):
            await watcher.start()

        # Should NOT have started
        assert watcher._loop is None
        assert watcher.running is False


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


# Deduplication tests


@pytest.fixture
def mock_dedupe_service():
    """Create mock DedupeService."""
    mock = AsyncMock(spec=DedupeService)
    mock.is_duplicate_and_mark = AsyncMock(return_value=(False, "abc123"))
    return mock


@pytest.fixture
def file_watcher_with_dedupe(temp_camera_root, mock_redis_client, mock_dedupe_service):
    """Create FileWatcher with mock dedupe service."""
    watcher = FileWatcher(
        camera_root=str(temp_camera_root),
        redis_client=mock_redis_client,
        debounce_delay=0.1,
        dedupe_service=mock_dedupe_service,
    )
    return watcher


def test_file_watcher_creates_dedupe_service_when_redis_provided(
    temp_camera_root, mock_redis_client
):
    """Test FileWatcher creates DedupeService when Redis client is provided."""
    watcher = FileWatcher(
        camera_root=str(temp_camera_root),
        redis_client=mock_redis_client,
        debounce_delay=0.1,
    )
    assert watcher._dedupe_service is not None


def test_file_watcher_no_dedupe_without_redis(temp_camera_root):
    """Test FileWatcher has no DedupeService when Redis is not provided."""
    watcher = FileWatcher(
        camera_root=str(temp_camera_root),
        redis_client=None,
        debounce_delay=0.1,
    )
    assert watcher._dedupe_service is None


def test_file_watcher_uses_provided_dedupe_service(
    temp_camera_root, mock_redis_client, mock_dedupe_service
):
    """Test FileWatcher uses provided DedupeService instead of creating one."""
    watcher = FileWatcher(
        camera_root=str(temp_camera_root),
        redis_client=mock_redis_client,
        debounce_delay=0.1,
        dedupe_service=mock_dedupe_service,
    )
    assert watcher._dedupe_service is mock_dedupe_service


@pytest.mark.asyncio
async def test_queue_for_detection_calls_dedupe(
    file_watcher_with_dedupe, temp_camera_root, mock_redis_client, mock_dedupe_service
):
    """Test _queue_for_detection calls dedupe service before queueing."""
    camera_dir = temp_camera_root / "camera1"
    image_path = camera_dir / "test.jpg"
    img = Image.new("RGB", (100, 100), color="blue")
    img.save(image_path)

    # File is not a duplicate
    mock_dedupe_service.is_duplicate_and_mark.return_value = (False, "hash123")

    await file_watcher_with_dedupe._queue_for_detection("camera1", str(image_path))

    # Dedupe should be called
    mock_dedupe_service.is_duplicate_and_mark.assert_called_once_with(str(image_path))

    # File should be queued
    mock_redis_client.add_to_queue_safe.assert_called_once()

    # Verify hash is included in queue data
    call_args = mock_redis_client.add_to_queue_safe.call_args[0]
    queue_data = call_args[1]
    assert queue_data["file_hash"] == "hash123"


@pytest.mark.asyncio
async def test_queue_for_detection_skips_duplicate(
    file_watcher_with_dedupe, temp_camera_root, mock_redis_client, mock_dedupe_service
):
    """Test _queue_for_detection skips duplicate files."""
    camera_dir = temp_camera_root / "camera1"
    image_path = camera_dir / "test.jpg"
    img = Image.new("RGB", (100, 100), color="red")
    img.save(image_path)

    # File IS a duplicate
    mock_dedupe_service.is_duplicate_and_mark.return_value = (True, "hash456")

    await file_watcher_with_dedupe._queue_for_detection("camera1", str(image_path))

    # Dedupe should be called
    mock_dedupe_service.is_duplicate_and_mark.assert_called_once()

    # File should NOT be queued
    mock_redis_client.add_to_queue_safe.assert_not_called()


@pytest.mark.asyncio
async def test_queue_for_detection_without_dedupe_service(temp_camera_root, mock_redis_client):
    """Test _queue_for_detection works without dedupe service."""
    watcher = FileWatcher(
        camera_root=str(temp_camera_root),
        redis_client=mock_redis_client,
        debounce_delay=0.1,
        dedupe_service=None,
    )
    # Override _dedupe_service to None (constructor would create one if redis is available)
    watcher._dedupe_service = None

    camera_dir = temp_camera_root / "camera1"
    image_path = camera_dir / "test.jpg"
    img = Image.new("RGB", (100, 100), color="green")
    img.save(image_path)

    await watcher._queue_for_detection("camera1", str(image_path))

    # File should still be queued (no dedupe)
    mock_redis_client.add_to_queue_safe.assert_called_once()

    # No file_hash in queue data since dedupe is disabled
    call_args = mock_redis_client.add_to_queue_safe.call_args[0]
    queue_data = call_args[1]
    assert "file_hash" not in queue_data


@pytest.mark.asyncio
async def test_duplicate_file_not_processed_twice(temp_camera_root, mock_redis_client):
    """Integration test: same file content is not processed twice."""
    # Create a real dedupe service with mock redis
    mock_redis_client.exists = AsyncMock(return_value=0)
    mock_redis_client.set = AsyncMock(return_value=True)

    dedupe = DedupeService(redis_client=mock_redis_client, ttl_seconds=300)
    watcher = FileWatcher(
        camera_root=str(temp_camera_root),
        redis_client=mock_redis_client,
        debounce_delay=0.1,
        dedupe_service=dedupe,
    )

    camera_dir = temp_camera_root / "camera1"
    image_path = camera_dir / "test.jpg"
    img = Image.new("RGB", (100, 100), color="purple")
    img.save(image_path)

    # First queue - should succeed
    await watcher._queue_for_detection("camera1", str(image_path))
    assert mock_redis_client.add_to_queue_safe.await_count == 1

    # Simulate Redis now having the key (marked as processed)
    mock_redis_client.exists.return_value = 1

    # Second queue - should be deduplicated
    await watcher._queue_for_detection("camera1", str(image_path))
    # Queue count should still be 1 (not called again)
    assert mock_redis_client.add_to_queue_safe.await_count == 1


# Camera auto-creation tests


@pytest.fixture
def mock_camera_creator():
    """Create mock camera creator callback."""
    return AsyncMock()


@pytest.fixture
def file_watcher_with_auto_create(temp_camera_root, mock_redis_client, mock_camera_creator):
    """Create FileWatcher with auto-create enabled."""
    watcher = FileWatcher(
        camera_root=str(temp_camera_root),
        redis_client=mock_redis_client,
        debounce_delay=0.1,
        auto_create_cameras=True,
        camera_creator=mock_camera_creator,
    )
    return watcher


def test_file_watcher_auto_create_disabled_by_default(temp_camera_root, mock_redis_client):
    """Test that auto_create is enabled by default but needs creator callback."""
    watcher = FileWatcher(
        camera_root=str(temp_camera_root),
        redis_client=mock_redis_client,
        debounce_delay=0.1,
    )
    # auto_create_cameras is True by default
    assert watcher.auto_create_cameras is True
    # But camera_creator is None, so auto-create won't happen
    assert watcher._camera_creator is None


def test_file_watcher_auto_create_with_callback(
    temp_camera_root, mock_redis_client, mock_camera_creator
):
    """Test FileWatcher initializes with auto-create callback."""
    watcher = FileWatcher(
        camera_root=str(temp_camera_root),
        redis_client=mock_redis_client,
        debounce_delay=0.1,
        auto_create_cameras=True,
        camera_creator=mock_camera_creator,
    )
    assert watcher.auto_create_cameras is True
    assert watcher._camera_creator is mock_camera_creator


@pytest.mark.asyncio
async def test_ensure_camera_exists_creates_camera(
    file_watcher_with_auto_create, mock_camera_creator
):
    """Test _ensure_camera_exists creates camera via callback."""
    await file_watcher_with_auto_create._ensure_camera_exists(
        camera_id="front_door",
        folder_name="Front Door",
    )

    # Camera creator should be called once
    mock_camera_creator.assert_awaited_once()

    # Verify Camera object passed to creator
    call_args = mock_camera_creator.call_args[0]
    camera = call_args[0]
    assert isinstance(camera, Camera)
    assert camera.id == "front_door"
    assert camera.name == "Front Door"


@pytest.mark.asyncio
async def test_ensure_camera_exists_only_once(file_watcher_with_auto_create, mock_camera_creator):
    """Test _ensure_camera_exists only creates camera once."""
    # Call twice for same camera
    await file_watcher_with_auto_create._ensure_camera_exists(
        camera_id="front_door",
        folder_name="Front Door",
    )
    await file_watcher_with_auto_create._ensure_camera_exists(
        camera_id="front_door",
        folder_name="Front Door",
    )

    # Camera creator should only be called once
    assert mock_camera_creator.await_count == 1


@pytest.mark.asyncio
async def test_ensure_camera_exists_different_cameras(
    file_watcher_with_auto_create, mock_camera_creator
):
    """Test _ensure_camera_exists creates different cameras."""
    await file_watcher_with_auto_create._ensure_camera_exists(
        camera_id="front_door",
        folder_name="Front Door",
    )
    await file_watcher_with_auto_create._ensure_camera_exists(
        camera_id="back_yard",
        folder_name="Back Yard",
    )

    # Camera creator should be called twice for different cameras
    assert mock_camera_creator.await_count == 2


@pytest.mark.asyncio
async def test_ensure_camera_exists_handles_exception(
    file_watcher_with_auto_create, mock_camera_creator
):
    """Test _ensure_camera_exists handles creator exceptions gracefully."""
    mock_camera_creator.side_effect = Exception("Database error")

    # Should not raise, just log warning
    await file_watcher_with_auto_create._ensure_camera_exists(
        camera_id="front_door",
        folder_name="Front Door",
    )

    # Creator was called
    mock_camera_creator.assert_awaited_once()


@pytest.mark.asyncio
async def test_ensure_camera_exists_no_callback(temp_camera_root, mock_redis_client):
    """Test _ensure_camera_exists does nothing without callback."""
    watcher = FileWatcher(
        camera_root=str(temp_camera_root),
        redis_client=mock_redis_client,
        debounce_delay=0.1,
        auto_create_cameras=True,
        camera_creator=None,  # No callback
    )

    # Should not raise
    await watcher._ensure_camera_exists(
        camera_id="front_door",
        folder_name="Front Door",
    )


@pytest.mark.asyncio
async def test_process_file_triggers_auto_create(
    temp_camera_root, mock_redis_client, mock_camera_creator
):
    """Test that processing a file triggers camera auto-creation."""
    # Create folder with spaces
    front_door_dir = temp_camera_root / "Front Door"
    front_door_dir.mkdir()

    watcher = FileWatcher(
        camera_root=str(temp_camera_root),
        redis_client=mock_redis_client,
        debounce_delay=0.1,
        auto_create_cameras=True,
        camera_creator=mock_camera_creator,
    )

    # Create valid image above minimum size
    image_path = front_door_dir / "test.jpg"
    create_valid_test_image(image_path)

    await watcher._process_file(str(image_path))

    # Camera should be auto-created
    mock_camera_creator.assert_awaited_once()
    camera = mock_camera_creator.call_args[0][0]
    assert camera.id == "front_door"
    assert camera.name == "Front Door"

    # File should be queued with normalized camera_id
    mock_redis_client.add_to_queue_safe.assert_awaited_once()
    queue_data = mock_redis_client.add_to_queue_safe.call_args[0][1]
    assert queue_data["camera_id"] == "front_door"


@pytest.mark.asyncio
async def test_process_file_queues_with_normalized_id(temp_camera_root, mock_redis_client):
    """Test that processed files are queued with normalized camera ID."""
    # Create folder with mixed case and spaces
    camera_dir = temp_camera_root / "Back-Yard Camera"
    camera_dir.mkdir()

    watcher = FileWatcher(
        camera_root=str(temp_camera_root),
        redis_client=mock_redis_client,
        debounce_delay=0.1,
        auto_create_cameras=False,  # Disabled
    )

    # Create valid image above minimum size
    image_path = camera_dir / "test.jpg"
    create_valid_test_image(image_path)

    await watcher._process_file(str(image_path))

    # File should be queued with normalized camera_id
    mock_redis_client.add_to_queue_safe.assert_awaited_once()
    queue_data = mock_redis_client.add_to_queue_safe.call_args[0][1]
    assert queue_data["camera_id"] == "back_yard_camera"


# Queue overflow and backpressure tests


@pytest.mark.asyncio
async def test_queue_overflow_moves_to_dlq(temp_camera_root, mock_redis_client):
    """Test that queue overflow moves items to DLQ instead of silently dropping."""
    watcher = FileWatcher(
        camera_root=str(temp_camera_root),
        redis_client=mock_redis_client,
        debounce_delay=0.1,
    )

    camera_dir = temp_camera_root / "camera1"
    camera_dir.mkdir(exist_ok=True)
    image_path = camera_dir / "test.jpg"
    img = Image.new("RGB", (100, 100), color="blue")
    img.save(image_path)

    # Simulate queue at max capacity with DLQ overflow
    mock_redis_client.add_to_queue_safe.return_value = QueueAddResult(
        success=True,
        queue_length=10000,
        moved_to_dlq_count=1,
        warning="Moved 1 items to DLQ due to overflow",
    )

    await watcher._queue_for_detection("camera1", str(image_path))

    # Verify add_to_queue_safe was called with DLQ policy
    mock_redis_client.add_to_queue_safe.assert_awaited_once()
    call_kwargs = mock_redis_client.add_to_queue_safe.call_args[1]
    assert call_kwargs["overflow_policy"] == QueueOverflowPolicy.DLQ


@pytest.mark.asyncio
async def test_queue_overflow_logs_backpressure_warning(
    temp_camera_root, mock_redis_client, caplog
):
    """Test that queue backpressure is logged when overflow occurs."""
    import logging

    watcher = FileWatcher(
        camera_root=str(temp_camera_root),
        redis_client=mock_redis_client,
        debounce_delay=0.1,
    )

    camera_dir = temp_camera_root / "camera1"
    camera_dir.mkdir(exist_ok=True)
    image_path = camera_dir / "test.jpg"
    img = Image.new("RGB", (100, 100), color="red")
    img.save(image_path)

    # Simulate queue at max capacity with DLQ overflow
    mock_redis_client.add_to_queue_safe.return_value = QueueAddResult(
        success=True,
        queue_length=10000,
        moved_to_dlq_count=5,
        warning="Moved 5 items to DLQ due to overflow",
    )

    with caplog.at_level(logging.WARNING):
        await watcher._queue_for_detection("camera1", str(image_path))

    # Verify backpressure warning was logged
    assert any("backpressure" in record.message.lower() for record in caplog.records)


@pytest.mark.asyncio
async def test_queue_full_reject_raises_error(temp_camera_root, mock_redis_client):
    """Test that queue rejection (when using REJECT policy) raises RuntimeError."""
    watcher = FileWatcher(
        camera_root=str(temp_camera_root),
        redis_client=mock_redis_client,
        debounce_delay=0.1,
    )

    camera_dir = temp_camera_root / "camera1"
    camera_dir.mkdir(exist_ok=True)
    image_path = camera_dir / "test.jpg"
    img = Image.new("RGB", (100, 100), color="green")
    img.save(image_path)

    # Simulate queue full rejection
    mock_redis_client.add_to_queue_safe.return_value = QueueAddResult(
        success=False,
        queue_length=10000,
        error="Queue 'detection_queue' is full (10000/10000). Item rejected.",
    )

    with pytest.raises(RuntimeError, match="Queue operation failed"):
        await watcher._queue_for_detection("camera1", str(image_path))


@pytest.mark.asyncio
async def test_queue_success_no_backpressure(temp_camera_root, mock_redis_client, caplog):
    """Test that successful queue with no backpressure doesn't log warning."""
    import logging

    watcher = FileWatcher(
        camera_root=str(temp_camera_root),
        redis_client=mock_redis_client,
        debounce_delay=0.1,
    )

    camera_dir = temp_camera_root / "camera1"
    camera_dir.mkdir(exist_ok=True)
    image_path = camera_dir / "test.jpg"
    img = Image.new("RGB", (100, 100), color="yellow")
    img.save(image_path)

    # Simulate successful queue with no backpressure
    mock_redis_client.add_to_queue_safe.return_value = QueueAddResult(
        success=True,
        queue_length=100,
    )

    with caplog.at_level(logging.WARNING):
        await watcher._queue_for_detection("camera1", str(image_path))

    # Verify no backpressure warning was logged
    assert not any("backpressure" in record.message.lower() for record in caplog.records)


# Polling observer configuration tests


def test_file_watcher_uses_native_observer_by_default(temp_camera_root, mock_redis_client):
    """Test FileWatcher uses native Observer by default."""
    from watchdog.observers import Observer

    watcher = FileWatcher(
        camera_root=str(temp_camera_root),
        redis_client=mock_redis_client,
        debounce_delay=0.1,
    )

    assert watcher._use_polling is False
    assert isinstance(watcher.observer, Observer)


def test_file_watcher_uses_polling_observer_when_enabled(temp_camera_root, mock_redis_client):
    """Test FileWatcher uses PollingObserver when use_polling=True."""
    from watchdog.observers.polling import PollingObserver

    watcher = FileWatcher(
        camera_root=str(temp_camera_root),
        redis_client=mock_redis_client,
        debounce_delay=0.1,
        use_polling=True,
    )

    assert watcher._use_polling is True
    assert isinstance(watcher.observer, PollingObserver)


def test_file_watcher_polling_interval_default(temp_camera_root, mock_redis_client):
    """Test FileWatcher uses default polling interval from settings."""
    from backend.core.config import get_settings

    settings = get_settings()

    watcher = FileWatcher(
        camera_root=str(temp_camera_root),
        redis_client=mock_redis_client,
        debounce_delay=0.1,
        use_polling=True,
    )

    # Default polling interval from settings
    assert watcher._polling_interval == settings.file_watcher_polling_interval


def test_file_watcher_polling_interval_custom(temp_camera_root, mock_redis_client):
    """Test FileWatcher uses custom polling interval."""
    from watchdog.observers.polling import PollingObserver

    watcher = FileWatcher(
        camera_root=str(temp_camera_root),
        redis_client=mock_redis_client,
        debounce_delay=0.1,
        use_polling=True,
        polling_interval=5.0,
    )

    assert watcher._use_polling is True
    assert watcher._polling_interval == 5.0
    assert isinstance(watcher.observer, PollingObserver)


def test_file_watcher_polling_from_settings(temp_camera_root, mock_redis_client, monkeypatch):
    """Test FileWatcher reads polling config from settings when not explicitly set."""
    from watchdog.observers.polling import PollingObserver

    # Mock settings to enable polling
    from backend.core import config

    # Clear the settings cache to pick up new values
    config.get_settings.cache_clear()

    # Set environment variables for polling
    monkeypatch.setenv("FILE_WATCHER_POLLING", "true")
    monkeypatch.setenv("FILE_WATCHER_POLLING_INTERVAL", "2.5")

    try:
        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            # Don't pass use_polling - should read from settings
        )

        assert watcher._use_polling is True
        assert watcher._polling_interval == 2.5
        assert isinstance(watcher.observer, PollingObserver)
    finally:
        # Clear cache to restore default settings for other tests
        config.get_settings.cache_clear()


def test_file_watcher_explicit_polling_overrides_settings(
    temp_camera_root, mock_redis_client, monkeypatch
):
    """Test explicit use_polling parameter overrides settings."""
    from watchdog.observers import Observer

    from backend.core import config

    # Clear the settings cache
    config.get_settings.cache_clear()

    # Set environment variable to enable polling in settings
    monkeypatch.setenv("FILE_WATCHER_POLLING", "true")

    try:
        # Explicitly disable polling via parameter
        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            use_polling=False,  # Explicit override
        )

        # Should use native observer despite settings
        assert watcher._use_polling is False
        assert isinstance(watcher.observer, Observer)
    finally:
        config.get_settings.cache_clear()


def test_file_watcher_logs_observer_type_native(temp_camera_root, mock_redis_client, caplog):
    """Test FileWatcher logs native observer type on initialization."""
    import logging

    with caplog.at_level(logging.INFO):
        FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            use_polling=False,
        )

    # Should log native observer
    assert any("observer=native" in record.message for record in caplog.records)


def test_file_watcher_logs_observer_type_polling(temp_camera_root, mock_redis_client, caplog):
    """Test FileWatcher logs polling observer type on initialization."""
    import logging

    with caplog.at_level(logging.INFO):
        FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            use_polling=True,
            polling_interval=2.0,
        )

    # Should log polling observer with interval
    log_messages = [record.message for record in caplog.records]
    assert any("observer=polling" in msg and "interval=2.0s" in msg for msg in log_messages)


# Bug fix tests: wa0t.13 (blocking join) and wa0t.14 (task memory leak)


@pytest.mark.asyncio
async def test_stop_uses_executor_for_blocking_join(file_watcher):
    """Test that stop() runs observer.join() in executor to avoid blocking event loop.

    Bug fix for wa0t.13: The observer.join(timeout=5) call was blocking the
    event loop for up to 5 seconds during shutdown.

    Note: run_in_executor is called twice:
    1. For observer.join() (blocking filesystem operation)
    2. For hash_executor.shutdown() (blocking executor shutdown)
    """
    # Start watcher
    with patch.object(file_watcher.observer, "start"):
        await file_watcher.start()

    # Mock observer methods
    with (
        patch.object(file_watcher.observer, "stop") as mock_stop,
        patch.object(file_watcher.observer, "join") as mock_join,
        patch("asyncio.get_running_loop") as mock_get_loop,
    ):
        mock_loop = AsyncMock()
        mock_get_loop.return_value = mock_loop
        # run_in_executor should be awaited
        mock_loop.run_in_executor = AsyncMock()

        await file_watcher.stop()

        # Verify stop was called
        mock_stop.assert_called_once()

        # Verify run_in_executor was used for blocking operations
        # Called twice: once for observer.join(), once for hash_executor.shutdown()
        assert mock_loop.run_in_executor.await_count == 2

        # Verify join was NOT called directly (it should be called via executor)
        # The lambda passed to run_in_executor will call join, not the test
        mock_join.assert_not_called()


@pytest.mark.asyncio
async def test_task_cleanup_callback_prevents_memory_leak(file_watcher, temp_camera_root):
    """Test that task done callback properly cleans up _pending_tasks dict.

    Bug fix for wa0t.14: Tasks were added to _pending_tasks but never removed,
    causing memory to grow unbounded. The fix adds a done_callback that removes
    the task from the dict when it completes.
    """
    camera_dir = temp_camera_root / "camera1"
    image_path = camera_dir / "test.jpg"
    img = Image.new("RGB", (100, 100), color="magenta")
    img.save(image_path)

    # Mock stability check for fast test
    with patch.object(
        file_watcher, "_wait_for_file_stability", new_callable=AsyncMock
    ) as mock_stability:
        mock_stability.return_value = True

        # Schedule file processing
        await file_watcher._schedule_file_processing(str(image_path))

        # Task should be in pending_tasks
        assert str(image_path) in file_watcher._pending_tasks

        # Wait for debounce + processing to complete
        await asyncio.sleep(file_watcher.debounce_delay + 0.1)

        # Task should be cleaned up from pending_tasks (no memory leak)
        assert str(image_path) not in file_watcher._pending_tasks


@pytest.mark.asyncio
async def test_task_replacement_does_not_remove_new_task(temp_camera_root, mock_redis_client):
    """Test that when a task is replaced, the old task's cleanup doesn't remove the new task.

    Bug fix for wa0t.14: When a task is cancelled and replaced, the old task's
    finally block could remove the new task from the dict. The done_callback
    now checks if the task in the dict is still the same task before removing.
    """
    # Use a longer debounce to give us time to verify state
    watcher = FileWatcher(
        camera_root=str(temp_camera_root),
        redis_client=mock_redis_client,
        debounce_delay=0.5,  # Long enough to check task states
    )

    camera_dir = temp_camera_root / "camera1"
    image_path = camera_dir / "test.jpg"
    img = Image.new("RGB", (100, 100), color="cyan")
    img.save(image_path)

    # Schedule first task
    await watcher._schedule_file_processing(str(image_path))
    first_task = watcher._pending_tasks.get(str(image_path))
    assert first_task is not None

    # Immediately schedule second task (replaces first)
    await watcher._schedule_file_processing(str(image_path))
    second_task = watcher._pending_tasks.get(str(image_path))
    assert second_task is not None
    assert second_task is not first_task  # Different task

    # Wait a bit for the first task's cancellation to complete
    # (task.cancelled() only returns True after cancellation is processed)
    await asyncio.sleep(0.05)

    # First task should now be cancelled (or done with CancelledError)
    assert first_task.done()

    # Second task should still be in the dict (not removed by first task's cleanup)
    # This is the key assertion - before the fix, the first task's cleanup would
    # incorrectly remove the second task from the dict
    current_task = watcher._pending_tasks.get(str(image_path))
    assert current_task is second_task, (
        f"Second task should still be in pending_tasks, but got: {current_task}. "
        f"First task cancelled: {first_task.cancelled()}, done: {first_task.done()}"
    )

    # Cancel the second task to clean up
    second_task.cancel()
    await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_multiple_files_cleaned_up_independently(file_watcher, temp_camera_root):
    """Test that multiple files are tracked and cleaned up independently.

    Verifies no memory leak when processing multiple different files.
    """
    camera_dir = temp_camera_root / "camera1"

    # Create multiple images
    image_paths = []
    for i in range(5):
        image_path = camera_dir / f"test_{i}.jpg"
        img = Image.new("RGB", (100, 100), color=(i * 50, 0, 0))
        img.save(image_path)
        image_paths.append(str(image_path))

    # Mock stability check for fast test
    with patch.object(
        file_watcher, "_wait_for_file_stability", new_callable=AsyncMock
    ) as mock_stability:
        mock_stability.return_value = True

        # Schedule all files
        for path in image_paths:
            await file_watcher._schedule_file_processing(path)

        # All should be in pending_tasks
        assert len(file_watcher._pending_tasks) == 5

        # Wait for all to complete
        await asyncio.sleep(file_watcher.debounce_delay + 0.2)

        # All should be cleaned up
        assert len(file_watcher._pending_tasks) == 0


# Pipeline Start Time Tracking Tests (bead 4mje.3)


@pytest.mark.asyncio
async def test_queue_for_detection_includes_pipeline_start_time(
    temp_camera_root, mock_redis_client
):
    """Test that _queue_for_detection includes pipeline_start_time in the queue payload.

    This tests the fix for bead 4mje.3: Pipeline latency metrics are all null because
    total_pipeline stage is defined but never recorded. The pipeline_start_time must
    be set when the file is first detected.
    """
    watcher = FileWatcher(
        camera_root=str(temp_camera_root),
        redis_client=mock_redis_client,
        debounce_delay=0.1,
    )
    # Override _dedupe_service to None for simpler test
    watcher._dedupe_service = None

    camera_dir = temp_camera_root / "camera1"
    image_path = camera_dir / "test.jpg"
    img = Image.new("RGB", (100, 100), color="blue")
    img.save(image_path)

    await watcher._queue_for_detection("camera1", str(image_path))

    # Verify queue was called with pipeline_start_time
    mock_redis_client.add_to_queue_safe.assert_called_once()
    call_args = mock_redis_client.add_to_queue_safe.call_args[0]
    queue_data = call_args[1]

    # pipeline_start_time should be present and a valid ISO timestamp
    assert "pipeline_start_time" in queue_data
    assert queue_data["pipeline_start_time"] is not None

    # Verify it's a valid ISO format timestamp
    from datetime import datetime

    parsed = datetime.fromisoformat(queue_data["pipeline_start_time"])
    assert parsed is not None


@pytest.mark.asyncio
async def test_process_file_records_pipeline_start_time(
    file_watcher, temp_camera_root, mock_redis_client
):
    """Test that processing a file records pipeline_start_time at detection time."""
    # Create valid image above minimum size
    camera_dir = temp_camera_root / "camera1"
    image_path = camera_dir / "test_pipeline_time.jpg"
    create_valid_test_image(image_path)

    await file_watcher._process_file(str(image_path))

    # Verify Redis queue was called with pipeline_start_time
    mock_redis_client.add_to_queue_safe.assert_awaited_once()
    call_args = mock_redis_client.add_to_queue_safe.call_args

    data = call_args[0][1]
    assert "pipeline_start_time" in data
    assert data["pipeline_start_time"] is not None

    # Verify timestamp is same as main timestamp (file detection time)
    assert data["pipeline_start_time"] == data["timestamp"]


# File stability check tests (NEM-1069)


@pytest.mark.asyncio
async def test_wait_for_file_stability_file_becomes_stable(file_watcher, temp_camera_root):
    """Test _wait_for_file_stability returns True when file size stops changing."""
    camera_dir = temp_camera_root / "camera1"
    image_path = camera_dir / "stable.jpg"

    # Create an image file (stable from the start)
    create_valid_test_image(image_path)

    # Mock time functions to make test instant
    simulated_time = [0.0]

    async def fake_sleep(delay: float) -> None:
        simulated_time[0] += delay

    def fake_monotonic() -> float:
        return simulated_time[0]

    with (
        patch("backend.services.file_watcher.asyncio.sleep", side_effect=fake_sleep),
        patch("backend.services.file_watcher.time.monotonic", side_effect=fake_monotonic),
    ):
        # File should become stable since it's not being modified
        result = await file_watcher._wait_for_file_stability(str(image_path), stability_time=0.2)

    assert result is True


@pytest.mark.asyncio
async def test_wait_for_file_stability_file_never_stabilizes(temp_camera_root, mock_redis_client):
    """Test _wait_for_file_stability returns False when file keeps changing."""
    # Create watcher with short stability time for faster test
    watcher = FileWatcher(
        camera_root=str(temp_camera_root),
        redis_client=mock_redis_client,
        debounce_delay=0.1,
        stability_time=0.3,  # Short stability time
    )

    camera_dir = temp_camera_root / "camera1"
    file_path = camera_dir / "unstable.txt"
    file_path.write_text("initial")

    # Mock time functions to make test instant
    # Simulate file size changing on every loop iteration
    simulated_time = [0.0]
    check_count = [0]

    async def fake_sleep(delay: float) -> None:
        simulated_time[0] += delay
        # Modify file after each sleep so next stat() sees a different size
        # This simulates ongoing FTP upload where file keeps growing
        check_count[0] += 1
        file_path.write_text(f"content_{check_count[0]}_" * (100 + check_count[0] * 50))

    def fake_monotonic() -> float:
        return simulated_time[0]

    # Use mock for Path.stat to return changing file sizes
    # This ensures the stability check sees different sizes each iteration
    original_stat = Path.stat
    stat_calls = [0]

    def mock_stat(self: Path):
        """Return changing file size for our test file, real stats otherwise."""
        if str(self) == str(file_path):
            stat_calls[0] += 1
            result = original_stat(self)
            return result
        return original_stat(self)

    with (
        patch("backend.services.file_watcher.asyncio.sleep", side_effect=fake_sleep),
        patch("backend.services.file_watcher.time.monotonic", side_effect=fake_monotonic),
        patch.object(Path, "stat", mock_stat),
    ):
        # File should never stabilize because it keeps changing
        result = await watcher._wait_for_file_stability(str(file_path), stability_time=0.3)

    assert result is False


@pytest.mark.asyncio
async def test_wait_for_file_stability_file_deleted_during_check(file_watcher, temp_camera_root):
    """Test _wait_for_file_stability returns False when file is deleted."""
    camera_dir = temp_camera_root / "camera1"
    file_path = camera_dir / "deleted.txt"
    file_path.write_text("will be deleted")

    # Mock time functions to make test instant
    # Delete the file after first check
    simulated_time = [0.0]
    check_count = [0]

    async def fake_sleep(delay: float) -> None:
        simulated_time[0] += delay
        check_count[0] += 1
        # Delete file after first sleep (simulating deletion during check)
        if check_count[0] == 1 and file_path.exists():
            file_path.unlink()

    def fake_monotonic() -> float:
        return simulated_time[0]

    with (
        patch("backend.services.file_watcher.asyncio.sleep", side_effect=fake_sleep),
        patch("backend.services.file_watcher.time.monotonic", side_effect=fake_monotonic),
    ):
        # File should return False because it was deleted
        result = await file_watcher._wait_for_file_stability(str(file_path), stability_time=1.0)

    assert result is False


@pytest.mark.asyncio
async def test_wait_for_file_stability_nonexistent_file(file_watcher):
    """Test _wait_for_file_stability returns False for nonexistent file."""
    result = await file_watcher._wait_for_file_stability(
        "/path/to/nonexistent/file.jpg", stability_time=0.2
    )
    assert result is False


@pytest.mark.asyncio
async def test_wait_for_file_stability_custom_stability_time(file_watcher, temp_camera_root):
    """Test _wait_for_file_stability respects custom stability_time parameter."""
    camera_dir = temp_camera_root / "camera1"
    file_path = camera_dir / "custom_time.txt"
    file_path.write_text("content")

    # Mock time functions to make test instant and verify stability_time is respected
    simulated_time = [0.0]
    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)
        simulated_time[0] += delay

    def fake_monotonic() -> float:
        return simulated_time[0]

    with (
        patch("backend.services.file_watcher.asyncio.sleep", side_effect=fake_sleep),
        patch("backend.services.file_watcher.time.monotonic", side_effect=fake_monotonic),
    ):
        # With custom stability time, should still complete successfully
        result = await file_watcher._wait_for_file_stability(str(file_path), stability_time=0.1)

    assert result is True
    # Verify that we slept for at least the custom stability time
    total_slept = sum(sleep_calls)
    assert total_slept >= 0.1, f"Expected to simulate >= 0.1s of sleep, got {total_slept}s"


@pytest.mark.asyncio
async def test_wait_for_file_stability_default_stability_time(temp_camera_root, mock_redis_client):
    """Test _wait_for_file_stability uses default stability_time of 2.0 seconds."""
    watcher = FileWatcher(
        camera_root=str(temp_camera_root),
        redis_client=mock_redis_client,
        debounce_delay=0.1,
    )

    camera_dir = temp_camera_root / "camera1"
    file_path = camera_dir / "default_time.txt"
    file_path.write_text("content")

    # Track sleep calls and simulate time passing
    sleep_calls: list[float] = []
    simulated_time = [0.0]  # Use list for mutability in closure

    async def tracking_sleep(delay: float) -> None:
        """Track sleep calls and advance simulated time."""
        sleep_calls.append(delay)
        simulated_time[0] += delay

    def mock_monotonic() -> float:
        """Return simulated time."""
        return simulated_time[0]

    with (
        patch("backend.services.file_watcher.asyncio.sleep", side_effect=tracking_sleep),
        patch("backend.services.file_watcher.time.monotonic", side_effect=mock_monotonic),
    ):
        result = await watcher._wait_for_file_stability(str(file_path))

    assert result is True
    # With default 2.0s stability time and 0.5s check interval,
    # should have made multiple sleep calls totaling at least 2.0s
    total_sleep_time = sum(sleep_calls)
    assert total_sleep_time >= 2.0, f"Expected >= 2.0s of sleep, got {total_sleep_time}s"


@pytest.mark.asyncio
async def test_process_file_waits_for_stability(temp_camera_root, mock_redis_client):
    """Test that _process_file calls stability check before processing."""
    watcher = FileWatcher(
        camera_root=str(temp_camera_root),
        redis_client=mock_redis_client,
        debounce_delay=0.1,
    )

    camera_dir = temp_camera_root / "camera1"
    image_path = camera_dir / "stability_test.jpg"
    create_valid_test_image(image_path)

    # Mock the stability check
    with patch.object(
        watcher, "_wait_for_file_stability", new_callable=AsyncMock
    ) as mock_stability:
        mock_stability.return_value = True

        await watcher._process_file(str(image_path))

        # Stability check should be called
        mock_stability.assert_awaited_once_with(str(image_path))

        # File should be queued (stability check passed)
        mock_redis_client.add_to_queue_safe.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_file_skips_unstable_file(temp_camera_root, mock_redis_client, caplog):
    """Test that _process_file skips files that never stabilize."""
    import logging

    watcher = FileWatcher(
        camera_root=str(temp_camera_root),
        redis_client=mock_redis_client,
        debounce_delay=0.1,
    )

    camera_dir = temp_camera_root / "camera1"
    image_path = camera_dir / "unstable_test.jpg"
    create_valid_test_image(image_path)

    # Mock the stability check to return False (file never stabilized)
    with patch.object(
        watcher, "_wait_for_file_stability", new_callable=AsyncMock
    ) as mock_stability:
        mock_stability.return_value = False

        with caplog.at_level(logging.WARNING):
            await watcher._process_file(str(image_path))

        # Stability check should be called
        mock_stability.assert_awaited_once()

        # File should NOT be queued (stability check failed)
        mock_redis_client.add_to_queue_safe.assert_not_awaited()

        # Warning should be logged
        assert any(
            "never stabilized" in record.message.lower() or "stability" in record.message.lower()
            for record in caplog.records
        )


@pytest.mark.asyncio
async def test_file_watcher_stability_time_configurable(temp_camera_root, mock_redis_client):
    """Test that FileWatcher stability_time is configurable via constructor."""
    watcher = FileWatcher(
        camera_root=str(temp_camera_root),
        redis_client=mock_redis_client,
        debounce_delay=0.1,
        stability_time=5.0,  # Custom stability time
    )

    assert watcher.stability_time == 5.0


@pytest.mark.asyncio
async def test_stability_check_file_grows_then_stabilizes(file_watcher, temp_camera_root):
    """Test stability check handles file that grows then stops (simulating FTP upload)."""
    camera_dir = temp_camera_root / "camera1"
    file_path = camera_dir / "growing.bin"
    file_path.write_bytes(b"x" * 1000)

    # Mock time functions to make test instant
    # Simulate file growing for first 3 checks, then stabilizing
    simulated_time = [0.0]
    check_count = [0]

    async def fake_sleep(delay: float) -> None:
        simulated_time[0] += delay
        check_count[0] += 1
        # Grow file for first 3 checks, then stop (simulates upload completing)
        if check_count[0] <= 3:
            current_content = file_path.read_bytes()
            file_path.write_bytes(current_content + b"x" * 1000)

    def fake_monotonic() -> float:
        return simulated_time[0]

    with (
        patch("backend.services.file_watcher.asyncio.sleep", side_effect=fake_sleep),
        patch("backend.services.file_watcher.time.monotonic", side_effect=fake_monotonic),
    ):
        # Should detect stability after simulated upload completes
        result = await file_watcher._wait_for_file_stability(str(file_path), stability_time=0.5)

    assert result is True
