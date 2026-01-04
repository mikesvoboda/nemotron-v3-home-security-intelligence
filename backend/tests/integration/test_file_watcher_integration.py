"""Integration tests for FileWatcher service.

These tests verify the FileWatcher's behavior with real filesystem operations,
using temporary directories for isolation. The detection pipeline is mocked
to focus on the file watching and callback triggering functionality.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from backend.core.redis import QueueAddResult
from backend.services.file_watcher import FileWatcher

# Fixtures


@pytest.fixture
def temp_camera_root(tmp_path, integration_env):
    """Create temporary camera directory structure for integration tests.

    Depends on integration_env to ensure DATABASE_URL is set before
    FileWatcher.__init__ calls get_settings().
    """
    camera_root = tmp_path / "foscam"
    camera_root.mkdir()
    return camera_root


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for capturing queue operations."""
    mock_client = AsyncMock()
    # Safe method with backpressure handling - this is what FileWatcher actually uses
    mock_client.add_to_queue_safe = AsyncMock(
        return_value=QueueAddResult(success=True, queue_length=1)
    )
    # DedupeService methods - FileWatcher auto-creates DedupeService when redis_client is provided
    # exists() returns 0 (not found) so files are not considered duplicates
    mock_client.exists = AsyncMock(return_value=0)
    # set() for marking files as processed
    mock_client.set = AsyncMock(return_value=True)
    # delete() for clearing hash from dedupe cache
    mock_client.delete = AsyncMock(return_value=1)
    return mock_client


def create_test_image(path: Path, color: str = "red", size: tuple = (640, 480)) -> Path:
    """Helper to create a valid test image file above minimum size threshold.

    Creates a JPEG image with a gradient pattern to ensure the file size
    is above the 10KB minimum required by image validation.

    Args:
        path: Path where to save the image
        color: Base color name for the image (used as starting point)
        size: Image dimensions (width, height), default 640x480 for ~15-30KB files

    Returns:
        Path to the created image
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", size, color=color)
    # Add gradient pattern to increase file size (solid colors compress too well)
    pixels = img.load()
    if pixels is not None:
        for y in range(size[1]):
            for x in range(size[0]):
                r = (x * 255 // size[0]) % 256
                g = (y * 255 // size[1]) % 256
                b = ((x + y) * 128 // (size[0] + size[1])) % 256
                pixels[x, y] = (r, g, b)
    img.save(path, "JPEG", quality=95)
    return path


class TestFileWatcherDetectsNewImage:
    """Test that FileWatcher properly detects new image files."""

    @pytest.mark.asyncio
    async def test_file_watcher_detects_new_image(self, temp_camera_root, mock_redis_client):
        """Test that a single new image file triggers the callback."""
        # Setup: Create camera directory
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        # Create file watcher with short debounce and no stability check for testing
        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0,  # Disable stability check for fast integration tests
        )

        try:
            # Start the watcher
            await watcher.start()
            assert watcher.running is True

            # Create a new image file
            image_path = camera_dir / "test_image.jpg"
            create_test_image(image_path, color="blue")

            # Wait for watchdog to detect and debounce to complete
            await asyncio.sleep(0.5)

            # Verify the image was queued
            assert mock_redis_client.add_to_queue_safe.await_count >= 1

            # Find the call with our image
            found = False
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    queue_name, data = call[0]
                    if (
                        queue_name == "detection_queue"
                        and data["camera_id"] == "camera1"
                        and data["file_path"] == str(image_path)
                    ):
                        found = True
                        assert "timestamp" in data
                        break

            assert found, "Expected image to be queued with correct data"

        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_file_watcher_detects_png_image(self, temp_camera_root, mock_redis_client):
        """Test that PNG files are also detected."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0,  # Disable stability check for fast integration tests
        )

        try:
            await watcher.start()

            # Create PNG image
            image_path = camera_dir / "test_image.png"
            create_test_image(image_path, color="green")

            await asyncio.sleep(0.5)

            # Verify PNG was detected
            assert mock_redis_client.add_to_queue_safe.await_count >= 1

            found = False
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    if str(image_path) in data.get("file_path", ""):
                        found = True
                        break

            assert found, "PNG image should be queued"

        finally:
            await watcher.stop()


class TestFileWatcherIgnoresNonMediaFiles:
    """Test that FileWatcher properly ignores non-media files."""

    @pytest.mark.asyncio
    async def test_file_watcher_ignores_txt_files(self, temp_camera_root, mock_redis_client):
        """Test that .txt files are ignored."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0,  # Disable stability check for fast integration tests
        )

        try:
            await watcher.start()

            # Create a text file
            text_file = camera_dir / "notes.txt"
            text_file.write_text("This is not an image")

            await asyncio.sleep(0.5)

            # Verify no calls were made to queue
            # (only image files should trigger)
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    assert "notes.txt" not in data.get("file_path", ""), (
                        "Text file should not be queued"
                    )

        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_file_watcher_ignores_tmp_files(self, temp_camera_root, mock_redis_client):
        """Test that .tmp files are ignored."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0,  # Disable stability check for fast integration tests
        )

        try:
            await watcher.start()

            # Create a tmp file
            tmp_file = camera_dir / "upload.tmp"
            tmp_file.write_bytes(b"temporary data")

            await asyncio.sleep(0.5)

            # Verify tmp file was not queued
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    assert ".tmp" not in data.get("file_path", ""), "Tmp file should not be queued"

        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_file_watcher_ignores_mp4_files(self, temp_camera_root, mock_redis_client):
        """Test that .mp4 files are ignored (FileWatcher only handles images)."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0,  # Disable stability check for fast integration tests
        )

        try:
            await watcher.start()

            # Create a fake mp4 file
            mp4_file = camera_dir / "video.mp4"
            mp4_file.write_bytes(b"fake video data")

            await asyncio.sleep(0.5)

            # Verify mp4 was not queued
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    assert ".mp4" not in data.get("file_path", ""), "MP4 file should not be queued"

        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_file_watcher_ignores_directories(self, temp_camera_root, mock_redis_client):
        """Test that directory creation events are ignored."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0,  # Disable stability check for fast integration tests
        )

        try:
            await watcher.start()

            # Create a subdirectory
            subdir = camera_dir / "subdir"
            subdir.mkdir()

            await asyncio.sleep(0.5)

            # Verify no directory paths were queued
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    assert "subdir" not in data.get("file_path", ""), (
                        "Directory should not be queued"
                    )

        finally:
            await watcher.stop()


class TestFileWatcherMultipleCameras:
    """Test FileWatcher handling multiple camera directories."""

    @pytest.mark.asyncio
    async def test_file_watcher_multiple_cameras(self, temp_camera_root, mock_redis_client):
        """Test that the watcher monitors multiple camera directories concurrently."""
        # Create multiple camera directories
        camera1_dir = temp_camera_root / "front_door"
        camera2_dir = temp_camera_root / "backyard"
        camera3_dir = temp_camera_root / "garage"

        camera1_dir.mkdir()
        camera2_dir.mkdir()
        camera3_dir.mkdir()

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0,  # Disable stability check for fast integration tests
        )

        try:
            await watcher.start()

            # Create images in each camera directory
            img1 = camera1_dir / "img1.jpg"
            img2 = camera2_dir / "img2.jpg"
            img3 = camera3_dir / "img3.jpg"

            create_test_image(img1, color="red")
            create_test_image(img2, color="green")
            create_test_image(img3, color="blue")

            # Wait for all detections
            await asyncio.sleep(1.0)  # timeout - intentional wait for file watcher

            # Collect all camera IDs from queued items
            camera_ids = set()
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    camera_ids.add(data.get("camera_id"))

            # Verify all three cameras were detected
            assert "front_door" in camera_ids, "front_door camera should be detected"
            assert "backyard" in camera_ids, "backyard camera should be detected"
            assert "garage" in camera_ids, "garage camera should be detected"

        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_file_watcher_camera_subdirectories(self, temp_camera_root, mock_redis_client):
        """Test that images in camera subdirectories are properly attributed."""
        camera_dir = temp_camera_root / "front_porch"
        subdir = camera_dir / "2024" / "12" / "26"
        subdir.mkdir(parents=True)

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0,  # Disable stability check for fast integration tests
        )

        try:
            await watcher.start()

            # Create image in subdirectory
            nested_image = subdir / "snapshot.jpg"
            create_test_image(nested_image, color="purple")

            await asyncio.sleep(0.5)

            # Verify the correct camera ID was extracted
            found = False
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    if data.get("camera_id") == "front_porch":
                        found = True
                        assert str(nested_image) == data["file_path"]
                        break

            assert found, "Image in subdirectory should have correct camera ID"

        finally:
            await watcher.stop()


class TestFileWatcherStartStopLifecycle:
    """Test FileWatcher lifecycle management."""

    @pytest.mark.asyncio
    async def test_file_watcher_start_stop_lifecycle(self, temp_camera_root, mock_redis_client):
        """Test clean start/stop cycle."""
        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0,  # Disable stability check for fast integration tests
        )

        # Initially not running
        assert watcher.running is False

        # Start
        await watcher.start()
        assert watcher.running is True
        assert watcher._loop is not None

        # Stop
        await watcher.stop()
        assert watcher.running is False
        assert watcher._loop is None

    @pytest.mark.asyncio
    async def test_file_watcher_double_start_idempotent(self, temp_camera_root, mock_redis_client):
        """Test that calling start twice is safe."""
        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0,  # Disable stability check for fast integration tests
        )

        try:
            await watcher.start()
            assert watcher.running is True

            # Start again - should not error
            await watcher.start()
            assert watcher.running is True

        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_file_watcher_stop_without_start(self, temp_camera_root, mock_redis_client):
        """Test that stopping without starting is safe."""
        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0,  # Disable stability check for fast integration tests
        )

        # Should not error
        await watcher.stop()
        assert watcher.running is False

    @pytest.mark.asyncio
    async def test_file_watcher_restart(self, temp_camera_root, mock_redis_client):
        """Test that watcher can be restarted after stopping."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0,  # Disable stability check for fast integration tests
        )

        # First cycle
        await watcher.start()
        assert watcher.running is True
        await watcher.stop()
        assert watcher.running is False

        # Need to create a new observer since watchdog observers can't be restarted
        watcher.observer = __import__("watchdog.observers", fromlist=["Observer"]).Observer()
        watcher._event_handler = watcher._create_event_handler()

        # Second cycle
        await watcher.start()
        assert watcher.running is True

        # Create file to verify functionality
        image = camera_dir / "restart_test.jpg"
        create_test_image(image, color="orange")

        await asyncio.sleep(0.5)

        # Verify detection still works after restart
        assert mock_redis_client.add_to_queue_safe.await_count >= 1

        await watcher.stop()

    @pytest.mark.asyncio
    async def test_file_watcher_creates_missing_directory(
        self, tmp_path, mock_redis_client, integration_env
    ):
        """Test that watcher creates camera root if it doesn't exist."""
        nonexistent_root = tmp_path / "nonexistent" / "cameras"

        watcher = FileWatcher(
            camera_root=str(nonexistent_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0,  # Disable stability check for fast integration tests
        )

        try:
            await watcher.start()

            # Directory should now exist
            assert nonexistent_root.exists()
            assert watcher.running is True

        finally:
            await watcher.stop()


class TestFileWatcherRapidFileCreation:
    """Test FileWatcher handling rapid/burst file creation."""

    @pytest.mark.asyncio
    async def test_file_watcher_handles_rapid_file_creation(
        self, temp_camera_root, mock_redis_client
    ):
        """Test handling a burst of files created in quick succession."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0,  # Disable stability check for fast integration tests
        )

        try:
            await watcher.start()

            # Create multiple files in rapid succession
            num_files = 10
            created_files = []
            for i in range(num_files):
                image_path = camera_dir / f"burst_{i:03d}.jpg"
                create_test_image(image_path, color="cyan")
                created_files.append(image_path)
                # Small delay to simulate rapid but not instant creation
                await asyncio.sleep(0.02)

            # Wait for all files to be processed (debounce + processing)
            await asyncio.sleep(2.0)  # timeout - intentional wait for debounce

            # Verify all files were queued
            queued_files = set()
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    queued_files.add(data.get("file_path"))

            for f in created_files:
                assert str(f) in queued_files, f"File {f} should be queued"

        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_file_watcher_debounce_reduces_queue_calls(
        self, temp_camera_root, mock_redis_client
    ):
        """Test that debouncing reduces the number of queue operations.

        The debounce mechanism cancels pending tasks when a new event arrives
        for the same file. This test verifies that without debouncing, we would
        get more queue calls than with debouncing.

        Note: Due to asyncio task scheduling, exact counts may vary, but
        debouncing should significantly reduce redundant processing.
        """
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        # Create the image before starting (so observer doesn't see it)
        image_path = camera_dir / "debounce_test.jpg"
        create_test_image(image_path, color="red")

        # Test WITH debouncing (short delay, no stability check for fast tests)
        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.3,
            stability_time=0,  # Disable stability check for fast integration tests
        )

        # Mock the observer to prevent real filesystem events
        with (
            patch.object(watcher.observer, "schedule"),
            patch.object(watcher.observer, "start"),
            patch.object(watcher.observer, "stop"),
            patch.object(watcher.observer, "join"),
        ):
            await watcher.start()

            try:
                num_events = 10
                # Schedule many events for the same file
                for _ in range(num_events):
                    await watcher._schedule_file_processing(str(image_path))
                    await asyncio.sleep(0.01)  # Very rapid, within debounce window

                # Wait for processing to complete
                await asyncio.sleep(0.5)

                # Count queue calls for this file
                queue_count = 0
                for call in mock_redis_client.add_to_queue_safe.call_args_list:
                    if len(call[0]) >= 2:
                        _, data = call[0]
                        if data.get("file_path") == str(image_path):
                            queue_count += 1

                # Debouncing should result in fewer queue calls than events
                # (exact count depends on timing, but should be less than num_events)
                assert queue_count < num_events, (
                    f"Debouncing should reduce queue calls. "
                    f"Got {queue_count} calls for {num_events} events"
                )
                # At least one queue call should happen
                assert queue_count >= 1, "At least one queue call expected"

            finally:
                await watcher.stop()

    @pytest.mark.asyncio
    async def test_file_watcher_concurrent_camera_files(self, temp_camera_root, mock_redis_client):
        """Test concurrent file creation across multiple cameras."""
        # Create camera directories
        cameras = ["cam1", "cam2", "cam3", "cam4"]
        for cam in cameras:
            (temp_camera_root / cam).mkdir()

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0,  # Disable stability check for fast integration tests
        )

        try:
            await watcher.start()

            # Create files in all cameras concurrently
            created_files = {}
            for cam in cameras:
                image_path = temp_camera_root / cam / "concurrent.jpg"
                create_test_image(image_path, color="magenta")
                created_files[cam] = image_path

            # Wait for processing
            await asyncio.sleep(1.0)  # timeout - intentional wait for file watcher

            # Verify all cameras had files queued
            queued_cameras = set()
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    queued_cameras.add(data.get("camera_id"))

            for cam in cameras:
                assert cam in queued_cameras, f"Camera {cam} should have file queued"

        finally:
            await watcher.stop()


class TestFileWatcherEdgeCases:
    """Test FileWatcher edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_file_watcher_empty_file(self, temp_camera_root, mock_redis_client):
        """Test that empty image files are not queued."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0,  # Disable stability check for fast integration tests
        )

        try:
            await watcher.start()

            # Create an empty file with image extension
            empty_image = camera_dir / "empty.jpg"
            empty_image.touch()

            await asyncio.sleep(0.5)

            # Empty files should not be queued
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    assert "empty.jpg" not in data.get("file_path", ""), (
                        "Empty file should not be queued"
                    )

        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_file_watcher_corrupted_image(self, temp_camera_root, mock_redis_client):
        """Test that corrupted image files are not queued."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0,  # Disable stability check for fast integration tests
        )

        try:
            await watcher.start()

            # Create a file with image extension but invalid content
            corrupted_image = camera_dir / "corrupted.jpg"
            corrupted_image.write_text("This is not a valid image file!")

            await asyncio.sleep(0.5)

            # Corrupted files should not be queued
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    assert "corrupted.jpg" not in data.get("file_path", ""), (
                        "Corrupted file should not be queued"
                    )

        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_file_watcher_no_redis_client(self, temp_camera_root):
        """Test watcher operates without Redis client (logs warning)."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        # Create watcher without Redis client
        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=None,
            debounce_delay=0.1,
            stability_time=0,  # Disable stability check for fast integration tests
        )

        try:
            await watcher.start()

            # Create valid image
            image = camera_dir / "no_redis.jpg"
            create_test_image(image, color="navy")

            # Should not crash
            await asyncio.sleep(0.5)

            assert watcher.running is True

        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_file_watcher_redis_exception(self, temp_camera_root, mock_redis_client):
        """Test watcher handles Redis exceptions gracefully."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        # Make Redis client raise exception
        mock_redis_client.add_to_queue_safe.side_effect = Exception("Redis connection failed")

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0,  # Disable stability check for fast integration tests
        )

        try:
            await watcher.start()

            # Create valid image
            image = camera_dir / "redis_fail.jpg"
            create_test_image(image, color="olive")

            # Should not crash despite Redis error
            await asyncio.sleep(0.5)

            assert watcher.running is True

        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_file_watcher_stop_cancels_pending_tasks(
        self, temp_camera_root, mock_redis_client
    ):
        """Test that stopping the watcher cancels pending debounce tasks."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=1.0,  # Long debounce
            stability_time=0,  # Disable stability check for fast integration tests
        )

        try:
            await watcher.start()

            # Create image
            image = camera_dir / "pending.jpg"
            create_test_image(image, color="teal")

            # Give time for event to be received but not processed
            await asyncio.sleep(0.1)

            # Stop immediately (before debounce completes)
            await watcher.stop()

            # Pending tasks should be cancelled
            assert len(watcher._pending_tasks) == 0

        finally:
            if watcher.running:
                await watcher.stop()

    @pytest.mark.asyncio
    async def test_file_watcher_without_event_loop(self, temp_camera_root, mock_redis_client):
        """Test event handling when event loop reference is lost."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0,  # Disable stability check for fast integration tests
        )

        # Manually test the scenario where loop is None
        watcher._loop = None

        from watchdog.events import FileCreatedEvent

        image = camera_dir / "no_loop.jpg"
        create_test_image(image, color="coral")

        event = FileCreatedEvent(str(image))

        # Should log warning but not crash
        watcher._event_handler.on_created(event)


class TestFileWatcherFileTypes:
    """Test FileWatcher file type filtering."""

    @pytest.mark.asyncio
    async def test_accepts_jpg_uppercase(self, temp_camera_root, mock_redis_client):
        """Test that uppercase JPG extension is accepted."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0,  # Disable stability check for fast integration tests
        )

        try:
            await watcher.start()

            image = camera_dir / "TEST.JPG"
            create_test_image(image, color="lime")

            await asyncio.sleep(0.5)

            found = False
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    if "TEST.JPG" in data.get("file_path", ""):
                        found = True
                        break

            assert found, "Uppercase JPG should be accepted"

        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_accepts_jpeg_extension(self, temp_camera_root, mock_redis_client):
        """Test that .jpeg extension is accepted."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0,  # Disable stability check for fast integration tests
        )

        try:
            await watcher.start()

            image = camera_dir / "photo.jpeg"
            create_test_image(image, color="maroon")

            await asyncio.sleep(0.5)

            found = False
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    if "photo.jpeg" in data.get("file_path", ""):
                        found = True
                        break

            assert found, ".jpeg extension should be accepted"

        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_rejects_gif_files(self, temp_camera_root, mock_redis_client):
        """Test that GIF files are not processed (not in allowed extensions)."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0,  # Disable stability check for fast integration tests
        )

        try:
            await watcher.start()

            # Create GIF file
            gif = camera_dir / "animation.gif"
            img = Image.new("RGB", (100, 100), color="pink")
            img.save(gif, format="GIF")

            await asyncio.sleep(0.5)

            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    assert ".gif" not in data.get("file_path", ""), "GIF files should not be queued"

        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_rejects_webp_files(self, temp_camera_root, mock_redis_client):
        """Test that WebP files are not processed."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0,  # Disable stability check for fast integration tests
        )

        try:
            await watcher.start()

            # Create WebP file
            webp = camera_dir / "image.webp"
            img = Image.new("RGB", (100, 100), color="gold")
            img.save(webp, format="WEBP")

            await asyncio.sleep(0.5)

            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    assert ".webp" not in data.get("file_path", ""), (
                        "WebP files should not be queued"
                    )

        finally:
            await watcher.stop()
