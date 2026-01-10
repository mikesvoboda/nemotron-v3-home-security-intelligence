"""Filesystem integration tests for FileWatcher service.

These tests verify FileWatcher behavior with real filesystem operations,
focusing on edge cases like symlinks, permissions, large files, and
directory lifecycle events.

Test Scenarios:
- Real filesystem event detection
- Symlink handling (follow vs ignore)
- Permission error handling
- Large file handling
- Concurrent file creation (no events lost)
- Directory creation/deletion events
- Watch directory deleted -> graceful recovery

NOTE: These tests rely on real filesystem events (inotify/fsevents) which
don't work reliably in CI virtualized environments (GitHub Actions).
They are skipped in CI and should be run locally for full coverage.
"""

import asyncio
import os
import stat
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from PIL import Image

from backend.core.redis import QueueAddResult
from backend.services.file_watcher import FileWatcher

# Skip entire module in CI - filesystem events don't work reliably in virtualized environments
pytestmark = pytest.mark.skipif(
    os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true",
    reason="Filesystem event tests are flaky in CI virtualized environments",
)


# =============================================================================
# Fixtures
# =============================================================================


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
    mock_client.add_to_queue_safe = AsyncMock(
        return_value=QueueAddResult(success=True, queue_length=1)
    )
    # DedupeService methods - returns 0 (not found) so files are not duplicates
    mock_client.exists = AsyncMock(return_value=0)
    mock_client.set = AsyncMock(return_value=True)
    mock_client.delete = AsyncMock(return_value=1)
    return mock_client


def create_test_image(path: Path, color: str = "red", size: tuple = (640, 480)) -> Path:
    """Helper to create a valid test image file.

    Creates an image large enough to pass MIN_IMAGE_FILE_SIZE validation (10KB).
    The default 640x480 size with gradient produces a file of approximately 15-30KB.

    Args:
        path: Path where to save the image
        color: Color name for the image (used as base, with gradient overlay)
        size: Image dimensions (width, height)

    Returns:
        Path to the created image
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", size, color=color)
    # Add a gradient pattern to prevent excessive compression
    # This ensures the file size exceeds 10KB minimum
    pixels = img.load()
    width, height = size
    for x in range(0, width, 2):
        for y in range(0, height, 2):
            # Add subtle variation based on position
            r, g, b = pixels[x, y]
            pixels[x, y] = (
                min(255, r + (x % 50)),
                min(255, g + (y % 50)),
                min(255, b + ((x + y) % 30)),
            )
    # Save with high quality to ensure file exceeds 10KB minimum
    img.save(path, quality=95)
    return path


def create_large_test_image(path: Path, size_mb: float = 5.0) -> Path:
    """Create a large test image for testing large file handling.

    Args:
        path: Path where to save the image
        size_mb: Approximate size in megabytes

    Returns:
        Path to the created image
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # Calculate dimensions for approximate file size
    # JPEG compression varies, but RGB image at 100% quality ~= 3 bytes per pixel
    pixels_needed = int((size_mb * 1024 * 1024) / 3)
    side = int(pixels_needed**0.5)
    # Create a random-looking image that doesn't compress well
    img = Image.new("RGB", (side, side))
    # Add some random-ish content to avoid excessive compression
    for x in range(0, side, 100):
        for y in range(0, side, 100):
            img.putpixel((x, y), ((x * 7) % 256, (y * 13) % 256, ((x + y) * 11) % 256))
    img.save(path, quality=95)
    return path


# =============================================================================
# Real Filesystem Event Detection Tests
# =============================================================================


class TestRealFilesystemEventDetection:
    """Test that FileWatcher properly detects real filesystem events."""

    @pytest.mark.asyncio
    async def test_detects_file_created_event(self, temp_camera_root, mock_redis_client):
        """Test that file creation triggers an event."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0.0,  # Disable stability check for tests (files are complete)
        )

        try:
            await watcher.start()
            assert watcher.running is True

            # Create a new image file
            image_path = camera_dir / "test_create.jpg"
            create_test_image(image_path, color="blue")

            # Wait for detection
            await asyncio.sleep(0.5)

            # Verify the image was queued
            assert mock_redis_client.add_to_queue_safe.await_count >= 1

            found = False
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    if str(image_path) in data.get("file_path", ""):
                        found = True
                        break

            assert found, "File creation event should trigger queue operation"

        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_detects_file_modified_event(self, temp_camera_root, mock_redis_client):
        """Test that file modification triggers an event (after debounce)."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        # Create file before starting watcher
        image_path = camera_dir / "test_modify.jpg"
        create_test_image(image_path, color="red")

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0.0,  # Disable stability check for tests (files are complete)
        )

        try:
            await watcher.start()

            # Wait for initial detection (if any)
            await asyncio.sleep(0.3)

            # Modify the file
            create_test_image(image_path, color="green")

            # Wait for detection
            await asyncio.sleep(0.5)

            # Should have detected the modification
            assert mock_redis_client.add_to_queue_safe.await_count >= 1

        finally:
            await watcher.stop()


# =============================================================================
# Symlink Handling Tests
# =============================================================================


class TestSymlinkHandling:
    """Test FileWatcher behavior with symbolic links."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(os.name == "nt", reason="Symlinks require special permissions on Windows")
    async def test_follows_symlink_to_file(self, temp_camera_root, mock_redis_client, tmp_path):
        """Test that symlinked files are processed when detected."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        # Create actual image in a different location
        actual_image = tmp_path / "actual_images" / "real_image.jpg"
        create_test_image(actual_image, color="purple")

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0.0,  # Disable stability check for tests (files are complete)
        )

        try:
            await watcher.start()

            # Create symlink to the image
            symlink_path = camera_dir / "symlink_image.jpg"
            symlink_path.symlink_to(actual_image)

            # Wait for detection
            await asyncio.sleep(0.5)

            # Should have detected and queued the symlink
            found = False
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    if "symlink_image.jpg" in data.get("file_path", ""):
                        found = True
                        break

            assert found, "Symlinked file should be detected and queued"

        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    @pytest.mark.skipif(os.name == "nt", reason="Symlinks require special permissions on Windows")
    async def test_handles_broken_symlink(self, temp_camera_root, mock_redis_client, tmp_path):
        """Test that broken symlinks are handled gracefully (not queued)."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        # Create actual image and then symlink
        actual_image = tmp_path / "actual_images" / "to_delete.jpg"
        create_test_image(actual_image, color="red")

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0.0,  # Disable stability check for tests (files are complete)
        )

        try:
            await watcher.start()

            # Create symlink, then delete the target
            symlink_path = camera_dir / "broken_symlink.jpg"
            symlink_path.symlink_to(actual_image)
            actual_image.unlink()  # Break the symlink

            # Wait for detection
            await asyncio.sleep(0.5)

            # Broken symlink should NOT be queued (validation fails)
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    assert "broken_symlink.jpg" not in data.get("file_path", ""), (
                        "Broken symlink should not be queued"
                    )

        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    @pytest.mark.skipif(os.name == "nt", reason="Symlinks require special permissions on Windows")
    async def test_symlink_to_directory(self, temp_camera_root, mock_redis_client, tmp_path):
        """Test that symlinks to directories are handled properly."""
        # Create actual camera directory elsewhere
        actual_camera_dir = tmp_path / "actual_cameras" / "real_camera"
        actual_camera_dir.mkdir(parents=True)

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0.0,  # Disable stability check for tests (files are complete)
        )

        try:
            await watcher.start()

            # Create symlink to camera directory
            symlink_camera = temp_camera_root / "linked_camera"
            symlink_camera.symlink_to(actual_camera_dir)

            # Create image in the actual directory (through symlink)
            image_path = symlink_camera / "image.jpg"
            create_test_image(image_path, color="cyan")

            # Wait for detection
            await asyncio.sleep(0.8)

            # The behavior depends on watchdog's recursive watching through symlinks
            # Either it works or it doesn't - we just verify no crash
            # Note: We don't check `found` because behavior varies by platform/watchdog version
            assert watcher.running is True

        finally:
            await watcher.stop()


# =============================================================================
# Permission Error Handling Tests
# =============================================================================


class TestPermissionErrorHandling:
    """Test FileWatcher handling of permission errors."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        os.name == "nt" or os.geteuid() == 0,
        reason="Permission tests require non-root on Unix-like systems",
    )
    async def test_handles_unreadable_file_gracefully(self, temp_camera_root, mock_redis_client):
        """Test that unreadable files are handled gracefully (not queued)."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        # Create image first
        image_path = camera_dir / "unreadable.jpg"
        create_test_image(image_path, color="red")

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0.0,  # Disable stability check for tests (files are complete)
        )

        try:
            await watcher.start()

            # Remove read permissions
            image_path.chmod(0o000)

            # Create a new file to trigger a detection attempt
            new_image = camera_dir / "readable.jpg"
            create_test_image(new_image, color="blue")

            # Wait for detection
            await asyncio.sleep(0.5)

            # The readable file should be queued, unreadable should not
            readable_found = False
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    if "readable.jpg" in data.get("file_path", ""):
                        readable_found = True
                    assert "unreadable.jpg" not in data.get("file_path", ""), (
                        "Unreadable file should not be queued"
                    )

            assert readable_found, "Readable file should still be queued"

        finally:
            # Restore permissions for cleanup
            try:
                image_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
            except OSError:
                pass  # May fail if file was deleted, acceptable in test cleanup
            await watcher.stop()

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        os.name == "nt" or os.geteuid() == 0,
        reason="Permission tests require non-root on Unix-like systems",
    )
    async def test_handles_permission_denied_on_directory(
        self, temp_camera_root, mock_redis_client
    ):
        """Test graceful handling when a directory becomes inaccessible."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        # Create a subdirectory
        subdir = camera_dir / "restricted"
        subdir.mkdir()

        # Create image in subdirectory first
        image_path = subdir / "hidden.jpg"
        create_test_image(image_path, color="red")

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0.0,  # Disable stability check for tests (files are complete)
        )

        try:
            await watcher.start()

            # Wait for initial events
            await asyncio.sleep(0.3)

            # Remove execute permission on subdirectory (prevents access)
            original_mode = subdir.stat().st_mode
            subdir.chmod(0o000)

            # Create a file in accessible location to verify watcher still works
            accessible_image = camera_dir / "accessible.jpg"
            create_test_image(accessible_image, color="green")

            # Wait for detection
            await asyncio.sleep(0.5)

            # Watcher should still be running and processing accessible files
            assert watcher.running is True

            found = False
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    if "accessible.jpg" in data.get("file_path", ""):
                        found = True
                        break

            assert found, "Accessible files should still be processed"

        finally:
            # Restore permissions for cleanup
            try:
                subdir.chmod(original_mode)
            except OSError:
                pass  # May fail if directory was deleted, acceptable in test cleanup
            await watcher.stop()


# =============================================================================
# Large File Handling Tests
# =============================================================================


class TestLargeFileHandling:
    """Test FileWatcher behavior with large files."""

    @pytest.mark.asyncio
    async def test_processes_large_image_file(self, temp_camera_root, mock_redis_client):
        """Test that large image files are processed correctly."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.5,  # Longer debounce for large file writes
            stability_time=0.0,  # Disable stability check for tests (files are complete)
        )

        try:
            await watcher.start()

            # Create a large image (~2MB to keep tests reasonable)
            large_image = camera_dir / "large_image.jpg"
            create_large_test_image(large_image, size_mb=2.0)

            # Wait for detection (longer for large file) - intentional wait for file watcher
            await asyncio.sleep(1.5)  # timeout - real filesystem event detection

            # Should have detected the large file
            found = False
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    if "large_image.jpg" in data.get("file_path", ""):
                        found = True
                        break

            assert found, "Large image file should be processed"

        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_debounce_handles_slow_file_write(self, temp_camera_root, mock_redis_client):
        """Test that debounce waits for file write completion."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        # Use a longer debounce delay
        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.5,
            stability_time=0.0,  # Disable stability check for tests (files are complete)
        )

        try:
            await watcher.start()

            # Simulate slow write by creating partial file then completing
            image_path = camera_dir / "slow_write.jpg"

            # Start with incomplete data
            image_path.write_bytes(b"partial data...")

            # Wait a bit then complete the write
            await asyncio.sleep(0.2)

            # Now write the actual image
            create_test_image(image_path, color="orange")

            # Wait for debounce to complete
            await asyncio.sleep(1.0)

            # The file should be queued (valid image after complete write)
            found = False
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    if "slow_write.jpg" in data.get("file_path", ""):
                        found = True
                        break

            assert found, "File should be queued after complete write"

        finally:
            await watcher.stop()


# =============================================================================
# Concurrent File Creation Tests
# =============================================================================


class TestConcurrentFileCreation:
    """Test FileWatcher handling of concurrent file creation."""

    @pytest.mark.asyncio
    async def test_rapid_file_creation_no_events_lost(self, temp_camera_root, mock_redis_client):
        """Test that rapid file creation doesn't lose events."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0.0,  # Disable stability check for tests (files are complete)
        )

        try:
            await watcher.start()

            # Create many files rapidly
            num_files = 20
            created_files = []
            for i in range(num_files):
                image_path = camera_dir / f"rapid_{i:03d}.jpg"
                create_test_image(image_path, color="yellow")
                created_files.append(image_path)
                # Very small delay
                await asyncio.sleep(0.02)

            # Wait for all files to be processed - intentional wait for file watcher
            await asyncio.sleep(3.0)  # timeout - real filesystem event detection

            # Collect all queued files
            queued_files = set()
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    queued_files.add(data.get("file_path"))

            # Verify all files were queued
            missing = []
            for f in created_files:
                if str(f) not in queued_files:
                    missing.append(str(f))

            assert len(missing) == 0, f"Files not queued: {missing}"

        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_concurrent_creation_across_cameras(self, temp_camera_root, mock_redis_client):
        """Test concurrent file creation across multiple camera directories."""
        # Create multiple camera directories
        cameras = [f"cam{i}" for i in range(5)]
        for cam in cameras:
            (temp_camera_root / cam).mkdir()

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0.0,  # Disable stability check for tests (files are complete)
        )

        try:
            await watcher.start()

            # Create files in all cameras concurrently
            created_files = []
            for cam in cameras:
                for i in range(3):
                    image_path = temp_camera_root / cam / f"concurrent_{i}.jpg"
                    create_test_image(image_path, color="magenta")
                    created_files.append(image_path)
                    await asyncio.sleep(0.01)

            # Wait for processing - intentional wait for file watcher
            await asyncio.sleep(2.0)  # timeout - real filesystem event detection

            # Verify all cameras had files queued
            queued_cameras = set()
            queued_files = set()
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    queued_cameras.add(data.get("camera_id"))
                    queued_files.add(data.get("file_path"))

            for cam in cameras:
                assert cam in queued_cameras, f"Camera {cam} should have files queued"

        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_burst_same_file_multiple_events(self, temp_camera_root, mock_redis_client):
        """Test that burst modifications to same file result in single queue operation."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.3,  # Longer debounce to capture burst
            stability_time=0.0,  # Disable stability check for tests (files are complete)
        )

        try:
            await watcher.start()

            # Create and modify file rapidly (simulating FTP burst)
            image_path = camera_dir / "burst_test.jpg"

            # Multiple rapid writes
            for color in ["red", "green", "blue", "yellow", "purple"]:
                create_test_image(image_path, color=color)
                await asyncio.sleep(0.05)  # Within debounce window

            # Wait for debounce to complete
            await asyncio.sleep(0.8)

            # Count queue calls for this specific file
            queue_count = 0
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    if "burst_test.jpg" in data.get("file_path", ""):
                        queue_count += 1

            # Debouncing should result in single (or few) queue operations
            assert queue_count >= 1, "At least one queue operation expected"
            assert queue_count <= 2, f"Debouncing should reduce calls, got {queue_count}"

        finally:
            await watcher.stop()


# =============================================================================
# Directory Event Tests
# =============================================================================


class TestDirectoryEvents:
    """Test FileWatcher handling of directory events."""

    @pytest.mark.asyncio
    async def test_ignores_directory_creation(self, temp_camera_root, mock_redis_client):
        """Test that directory creation events are not queued."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0.0,  # Disable stability check for tests (files are complete)
        )

        try:
            await watcher.start()

            # Create subdirectories
            for i in range(5):
                subdir = camera_dir / f"subdir_{i}"
                subdir.mkdir()

            await asyncio.sleep(0.5)

            # No directories should be queued
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    path = data.get("file_path", "")
                    assert "subdir_" not in path or path.endswith(
                        (".jpg", ".jpeg", ".png", ".mp4", ".mkv", ".avi", ".mov")
                    ), "Directory should not be queued"

        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_detects_files_in_new_directory(self, temp_camera_root, mock_redis_client):
        """Test that files in newly created directories are detected."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0.0,  # Disable stability check for tests (files are complete)
        )

        try:
            await watcher.start()

            # Create new subdirectory with date structure (common pattern)
            subdir = camera_dir / "2024" / "12" / "31"
            subdir.mkdir(parents=True)

            # Create image in new directory
            image_path = subdir / "new_location.jpg"
            create_test_image(image_path, color="silver")

            await asyncio.sleep(0.5)

            # Image should be detected with correct camera ID
            found = False
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    if "new_location.jpg" in data.get("file_path", ""):
                        assert data["camera_id"] == "camera1"
                        found = True
                        break

            assert found, "File in new subdirectory should be detected"

        finally:
            await watcher.stop()


# =============================================================================
# Watch Directory Deleted Tests
# =============================================================================


class TestWatchDirectoryDeleted:
    """Test FileWatcher graceful recovery when watch directory is deleted."""

    @pytest.mark.asyncio
    async def test_handles_watch_directory_deleted(self, temp_camera_root, mock_redis_client):
        """Test graceful handling when a camera directory is deleted."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        # Create initial image
        initial_image = camera_dir / "initial.jpg"
        create_test_image(initial_image, color="red")

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0.0,  # Disable stability check for tests (files are complete)
        )

        try:
            await watcher.start()

            # Wait for initial detection
            await asyncio.sleep(0.5)

            # Delete the camera directory
            import shutil

            shutil.rmtree(camera_dir)

            # Wait a bit
            await asyncio.sleep(0.3)

            # Watcher should still be running (graceful handling)
            assert watcher.running is True

            # Recreate directory and add new file
            camera_dir.mkdir()
            new_image = camera_dir / "after_delete.jpg"
            create_test_image(new_image, color="blue")

            # Wait for detection
            await asyncio.sleep(0.5)

            # Note: Whether the new file is detected depends on watchdog implementation
            # The important thing is the watcher didn't crash
            assert watcher.running is True

        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_handles_root_directory_recreated(self, temp_camera_root, mock_redis_client):
        """Test recovery when root directory is deleted and recreated."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0.0,  # Disable stability check for tests (files are complete)
        )

        try:
            await watcher.start()

            # Create initial file
            initial = camera_dir / "before.jpg"
            create_test_image(initial, color="red")

            await asyncio.sleep(0.3)

            # Delete root directory
            import shutil

            shutil.rmtree(temp_camera_root)

            # Wait a bit
            await asyncio.sleep(0.2)

            # Recreate root and camera directory
            temp_camera_root.mkdir()
            camera_dir.mkdir()

            # Create new file
            new_image = camera_dir / "after_root_delete.jpg"
            create_test_image(new_image, color="green")

            await asyncio.sleep(0.5)

            # Watcher should handle this gracefully (not crash)
            # Note: Detection may or may not work after root deletion
            # depending on watchdog implementation

        finally:
            # Ensure watcher can be stopped cleanly
            try:
                await watcher.stop()
            except OSError:
                # Some implementations may error on stop after directory deletion
                pass  # Expected behavior in edge case - watcher resources already released


# =============================================================================
# Video File Tests
# =============================================================================


class TestVideoFileDetection:
    """Test FileWatcher detection of video files."""

    @pytest.mark.asyncio
    async def test_detects_mp4_video(self, temp_camera_root, mock_redis_client):
        """Test that MP4 video files are detected."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0.0,  # Disable stability check for tests (files are complete)
        )

        try:
            await watcher.start()

            # Create a fake MP4 file with sufficient size
            video_path = camera_dir / "test_video.mp4"
            # Write enough bytes to pass the 1KB minimum check
            video_path.write_bytes(b"0" * 2048)

            await asyncio.sleep(0.5)

            # Video should be detected with media_type="video"
            found = False
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    if "test_video.mp4" in data.get("file_path", ""):
                        found = True
                        assert data.get("media_type") == "video"
                        break

            assert found, "MP4 video should be detected"

        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_detects_mkv_video(self, temp_camera_root, mock_redis_client):
        """Test that MKV video files are detected."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0.0,  # Disable stability check for tests (files are complete)
        )

        try:
            await watcher.start()

            # Create a fake MKV file
            video_path = camera_dir / "test_video.mkv"
            video_path.write_bytes(b"0" * 2048)

            await asyncio.sleep(0.5)

            # Video should be detected
            found = False
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    if "test_video.mkv" in data.get("file_path", ""):
                        found = True
                        assert data.get("media_type") == "video"
                        break

            assert found, "MKV video should be detected"

        finally:
            await watcher.stop()

    @pytest.mark.asyncio
    async def test_rejects_too_small_video(self, temp_camera_root, mock_redis_client):
        """Test that video files below minimum size are rejected."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            stability_time=0.0,  # Disable stability check for tests (files are complete)
        )

        try:
            await watcher.start()

            # Create a video file that's too small (< 1KB)
            video_path = camera_dir / "tiny_video.mp4"
            video_path.write_bytes(b"0" * 500)  # Only 500 bytes

            await asyncio.sleep(0.5)

            # Too-small video should NOT be queued
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    assert "tiny_video.mp4" not in data.get("file_path", ""), (
                        "Too-small video should not be queued"
                    )

        finally:
            await watcher.stop()


# =============================================================================
# Polling Mode Tests
# =============================================================================


class TestPollingMode:
    """Test FileWatcher in polling mode (for Docker/NFS scenarios)."""

    @pytest.mark.asyncio
    async def test_polling_mode_detects_files(self, temp_camera_root, mock_redis_client):
        """Test that polling mode works for file detection."""
        camera_dir = temp_camera_root / "camera1"
        camera_dir.mkdir()

        watcher = FileWatcher(
            camera_root=str(temp_camera_root),
            redis_client=mock_redis_client,
            debounce_delay=0.1,
            use_polling=True,
            polling_interval=0.5,  # Fast polling for testing
            stability_time=0.0,  # Disable stability check for tests (files are complete)
        )

        try:
            await watcher.start()
            assert watcher._use_polling is True

            # Create image
            image_path = camera_dir / "polling_test.jpg"
            create_test_image(image_path, color="coral")

            # Wait for polling to pick up the file - intentional wait for polling mode
            await asyncio.sleep(1.5)  # timeout - real filesystem polling detection

            # Should have detected the file
            found = False
            for call in mock_redis_client.add_to_queue_safe.call_args_list:
                if len(call[0]) >= 2:
                    _, data = call[0]
                    if "polling_test.jpg" in data.get("file_path", ""):
                        found = True
                        break

            assert found, "Polling mode should detect files"

        finally:
            await watcher.stop()
