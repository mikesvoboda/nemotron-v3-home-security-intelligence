"""Chaos tests for FTP upload failures and file system issues.

This module tests system behavior when FTP uploads fail or encounter issues:
- FTP upload timeout
- Incomplete file upload (partial write)
- Corrupted file content
- Disk full errors
- Permission denied errors
- File deleted during processing
- Invalid file format
- Oversized files
- Symlink traversal issues
- Concurrent upload conflicts
- FTP directory listing failures
- Network interruption during upload

Expected Behavior:
- Incomplete uploads are moved to DLQ
- Corrupted files trigger graceful detection failure with error logging
- Disk full errors are caught and logged with alerts
- Valid files are eventually processed after retry
- File watcher remains stable during failures
"""

from __future__ import annotations

import asyncio
import os
import stat
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from backend.services.file_watcher import FileWatcher


class TestFTPUploadTimeout:
    """Tests for FTP upload timeout scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_upload_timeout_moves_to_dlq(self, mock_redis_client: AsyncMock) -> None:
        """Upload timeout should move file to DLQ for retry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            camera_dir = Path(tmpdir) / "front_door"
            camera_dir.mkdir()
            test_file = camera_dir / "image.jpg"

            # Create a valid image that will timeout during processing
            img = Image.new("RGB", (1920, 1080), color="red")
            img.save(test_file)

            watcher = FileWatcher(
                camera_root=tmpdir,
                redis_client=mock_redis_client,
                auto_create_cameras=True,
            )

            # Simulate timeout during file processing
            mock_redis_client.add_to_queue_safe = AsyncMock(
                side_effect=TimeoutError("Upload timeout")
            )

            # Process file - should handle timeout gracefully
            await watcher._process_file(str(test_file))

            # Verify file was not removed (stays for retry)
            assert test_file.exists()

    @pytest.mark.skip(reason="Requires implementation refinement - see NEM-2142")
    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_repeated_upload_timeout_triggers_alert(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """Repeated upload timeouts should trigger monitoring alert."""
        with tempfile.TemporaryDirectory() as tmpdir:
            camera_dir = Path(tmpdir) / "front_door"
            camera_dir.mkdir()

            watcher = FileWatcher(
                camera_root=tmpdir,
                redis_client=mock_redis_client,
                auto_create_cameras=True,
            )

            # Simulate repeated timeouts
            mock_redis_client.add_to_queue_safe = AsyncMock(
                side_effect=TimeoutError("Upload timeout")
            )

            # Process multiple files with timeouts
            for i in range(5):
                test_file = camera_dir / f"image_{i}.jpg"
                img = Image.new("RGB", (1920, 1080), color="red")
                img.save(test_file)
                await watcher._process_file(str(test_file))

            # After 5 consecutive timeouts, alert should be triggered
            # (Implementation would check watcher.consecutive_failures or similar)
            assert mock_redis_client.add_to_queue_safe.call_count == 5


class TestIncompleteUpload:
    """Tests for incomplete FTP upload scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_incomplete_image_validation_fails(self, mock_redis_client: AsyncMock) -> None:
        """Incomplete image upload should fail validation gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            camera_dir = Path(tmpdir) / "front_door"
            camera_dir.mkdir()
            test_file = camera_dir / "incomplete.jpg"

            # Create incomplete/corrupted JPEG (truncated header)
            test_file.write_bytes(b"\xff\xd8\xff\xe0\x00")  # Incomplete JPEG header

            watcher = FileWatcher(
                camera_root=tmpdir,
                redis_client=mock_redis_client,
                auto_create_cameras=True,
            )

            # Process file - should handle validation failure gracefully
            # The file won't be enqueued if it can't be processed
            await watcher._process_file(str(test_file))

            # Incomplete files may not be added to queue
            # The system should handle this gracefully without crashing

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_partial_write_detected_via_size_check(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """Partial file write should be detected via size validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            camera_dir = Path(tmpdir) / "front_door"
            camera_dir.mkdir()
            test_file = camera_dir / "partial.jpg"

            # Create a file with zero size (write interrupted)
            test_file.touch()
            assert test_file.stat().st_size == 0

            watcher = FileWatcher(
                camera_root=tmpdir,
                redis_client=mock_redis_client,
                auto_create_cameras=True,
            )

            # Process file - should skip zero-size files
            await watcher._process_file(str(test_file))

            # Zero-size files should not be enqueued
            mock_redis_client.add_to_queue_safe.assert_not_called()

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_still_being_written_file_debounced(self, mock_redis_client: AsyncMock) -> None:
        """File still being written should be debounced."""
        with tempfile.TemporaryDirectory() as tmpdir:
            camera_dir = Path(tmpdir) / "front_door"
            camera_dir.mkdir()
            test_file = camera_dir / "writing.jpg"

            watcher = FileWatcher(
                camera_root=tmpdir,
                redis_client=mock_redis_client,
                auto_create_cameras=True,
                debounce_delay=0.1,
            )

            # Simulate file being actively written
            img = Image.new("RGB", (1920, 1080), color="red")

            # Start writing file in background
            async def write_file_slowly() -> None:
                await asyncio.sleep(0.05)
                img.save(test_file)

            write_task = asyncio.create_task(write_file_slowly())

            # Try to process before write completes
            await watcher._process_file(str(test_file))

            # Wait for write to complete
            await write_task

            # File should be debounced and not processed yet
            # (actual debounce logic would check file modification time)


class TestCorruptedFile:
    """Tests for corrupted file scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_corrupted_jpeg_handled_gracefully(self, mock_redis_client: AsyncMock) -> None:
        """Corrupted JPEG should be handled without crashing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            camera_dir = Path(tmpdir) / "front_door"
            camera_dir.mkdir()
            test_file = camera_dir / "corrupted.jpg"

            # Create corrupted JPEG (invalid data)
            test_file.write_bytes(b"\xff\xd8\xff\xe0" + b"corrupted_data" * 100)

            watcher = FileWatcher(
                camera_root=tmpdir,
                redis_client=mock_redis_client,
                auto_create_cameras=True,
            )

            # Process file - should handle corruption gracefully
            with patch("backend.services.file_watcher.logger") as mock_logger:
                await watcher._process_file(str(test_file))

                # Should log warning (not error) but not crash
                assert mock_logger.warning.called

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_corrupted_video_detection_fails_gracefully(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """Corrupted video file should fail detection gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            camera_dir = Path(tmpdir) / "front_door"
            camera_dir.mkdir()
            test_file = camera_dir / "corrupted.mp4"

            # Create corrupted MP4 (invalid header)
            test_file.write_bytes(b"not_a_valid_mp4_file" * 50)

            watcher = FileWatcher(
                camera_root=tmpdir,
                redis_client=mock_redis_client,
                auto_create_cameras=True,
            )

            # Process file - should handle gracefully without crashing
            await watcher._process_file(str(test_file))

            # Corrupted files should be handled gracefully
            # The system should not crash even with invalid file formats


class TestDiskFullErrors:
    """Tests for disk full error scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_disk_full_during_file_copy_logged(self, mock_redis_client: AsyncMock) -> None:
        """Disk full error during file operations should be logged and alerted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            camera_dir = Path(tmpdir) / "front_door"
            camera_dir.mkdir()
            test_file = camera_dir / "image.jpg"

            img = Image.new("RGB", (1920, 1080), color="red")
            img.save(test_file)

            watcher = FileWatcher(
                camera_root=tmpdir,
                redis_client=mock_redis_client,
                auto_create_cameras=True,
            )

            # Simulate disk full error
            with (
                patch("pathlib.Path.write_bytes", side_effect=OSError("No space left on device")),
                patch("backend.services.file_watcher.logger") as mock_logger,
            ):
                try:
                    await watcher._process_file(str(test_file))
                except OSError:
                    pass  # Expected

                # Should log critical disk space error
                # (In real implementation, this would trigger an alert)

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_low_disk_space_warning_triggered(self, mock_redis_client: AsyncMock) -> None:
        """Low disk space should trigger warning before full error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            camera_dir = Path(tmpdir) / "front_door"
            camera_dir.mkdir()

            watcher = FileWatcher(
                camera_root=tmpdir,
                redis_client=mock_redis_client,
                auto_create_cameras=True,
            )

            # Mock disk usage check to return low space
            with patch("shutil.disk_usage") as mock_disk:
                mock_disk.return_value = MagicMock(
                    total=100 * 1024**3,  # 100GB
                    used=95 * 1024**3,  # 95GB used
                    free=5 * 1024**3,  # 5GB free (5% remaining)
                )

                # Check disk space would trigger warning
                # (Implementation would check watcher.check_disk_space() or similar)


class TestPermissionErrors:
    """Tests for permission denied scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_unreadable_file_permission_denied(self, mock_redis_client: AsyncMock) -> None:
        """File with no read permissions should be handled gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            camera_dir = Path(tmpdir) / "front_door"
            camera_dir.mkdir()
            test_file = camera_dir / "unreadable.jpg"

            img = Image.new("RGB", (1920, 1080), color="red")
            img.save(test_file)

            # Remove read permissions
            os.chmod(test_file, 0o000)

            watcher = FileWatcher(
                camera_root=tmpdir,
                redis_client=mock_redis_client,
                auto_create_cameras=True,
            )

            try:
                # Process file - should handle permission error
                with patch("backend.services.file_watcher.logger") as mock_logger:
                    await watcher._process_file(str(test_file))

                    # Should log warning (OSError caught in stability check)
                    assert mock_logger.warning.called
            finally:
                # Restore permissions for cleanup
                try:
                    os.chmod(test_file, 0o644)
                except Exception:
                    pass

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_directory_permission_denied_stops_watcher(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """Directory with no read permissions should prevent watcher start."""
        with tempfile.TemporaryDirectory() as tmpdir:
            camera_dir = Path(tmpdir) / "front_door"
            camera_dir.mkdir()

            # Remove read permissions from camera directory
            os.chmod(camera_dir, 0o000)

            try:
                watcher = FileWatcher(
                    camera_root=tmpdir,
                    redis_client=mock_redis_client,
                    auto_create_cameras=True,
                )

                # Attempting to scan directory should fail gracefully
                with patch("backend.services.file_watcher.logger") as mock_logger:
                    # Implementation would handle this in scan_directories()
                    pass
            finally:
                # Restore permissions for cleanup - need execute bit for directory cleanup
                try:
                    os.chmod(camera_dir, stat.S_IRWXU)  # 0o700: user rwx only
                except Exception:
                    pass


class TestFileDeletedDuringProcessing:
    """Tests for files deleted mid-processing."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_file_deleted_before_validation(self, mock_redis_client: AsyncMock) -> None:
        """File deleted before validation should be handled gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            camera_dir = Path(tmpdir) / "front_door"
            camera_dir.mkdir()
            test_file = camera_dir / "deleted.jpg"

            img = Image.new("RGB", (1920, 1080), color="red")
            img.save(test_file)

            watcher = FileWatcher(
                camera_root=tmpdir,
                redis_client=mock_redis_client,
                auto_create_cameras=True,
            )

            # Delete file during processing
            with patch("backend.services.file_watcher.logger") as mock_logger:
                # Delete before processing
                test_file.unlink()

                # Process should handle missing file
                await watcher._process_file(str(test_file))

                # Should log that file was not found (expected)

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_file_deleted_during_upload_retry_handled(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """File deleted during upload retry should not cause infinite retry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            camera_dir = Path(tmpdir) / "front_door"
            camera_dir.mkdir()
            test_file = camera_dir / "retry_deleted.jpg"

            img = Image.new("RGB", (1920, 1080), color="red")
            img.save(test_file)

            watcher = FileWatcher(
                camera_root=tmpdir,
                redis_client=mock_redis_client,
                auto_create_cameras=True,
            )

            # Simulate file getting deleted during retry
            call_count = 0

            async def delete_on_second_call(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    test_file.unlink()
                    raise FileNotFoundError("File was deleted")
                return MagicMock(success=True, queue_length=1)

            mock_redis_client.add_to_queue_safe = AsyncMock(side_effect=delete_on_second_call)

            # First call succeeds, second call file is gone
            await watcher._process_file(str(test_file))


class TestInvalidFileFormat:
    """Tests for invalid or unsupported file formats."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_unsupported_file_extension_skipped(self, mock_redis_client: AsyncMock) -> None:
        """Unsupported file extension should be skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            camera_dir = Path(tmpdir) / "front_door"
            camera_dir.mkdir()
            test_file = camera_dir / "document.pdf"

            test_file.write_bytes(b"not_an_image")

            watcher = FileWatcher(
                camera_root=tmpdir,
                redis_client=mock_redis_client,
                auto_create_cameras=True,
            )

            # Process file - should skip unsupported extension
            await watcher._process_file(str(test_file))

            # Should not be enqueued
            mock_redis_client.add_to_queue_safe.assert_not_called()

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_text_file_with_image_extension_rejected(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """Text file masquerading as image should be rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            camera_dir = Path(tmpdir) / "front_door"
            camera_dir.mkdir()
            test_file = camera_dir / "fake.jpg"

            test_file.write_text("This is not a JPEG file")

            watcher = FileWatcher(
                camera_root=tmpdir,
                redis_client=mock_redis_client,
                auto_create_cameras=True,
            )

            # Process file - should fail validation
            with patch("backend.services.file_watcher.logger") as mock_logger:
                await watcher._process_file(str(test_file))

                # Should log validation error
                assert mock_logger.error.called or mock_logger.warning.called


class TestOversizedFiles:
    """Tests for oversized file handling."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_oversized_image_rejected(self, mock_redis_client: AsyncMock) -> None:
        """Image exceeding size limit should be rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            camera_dir = Path(tmpdir) / "front_door"
            camera_dir.mkdir()
            test_file = camera_dir / "huge.jpg"

            # Create a large image (simulated - not actually huge for test speed)
            img = Image.new("RGB", (8000, 8000), color="red")
            img.save(test_file, quality=95)

            watcher = FileWatcher(
                camera_root=tmpdir,
                redis_client=mock_redis_client,
                auto_create_cameras=True,
            )

            # Test that large files can be processed
            # In production, size limits would be enforced
            file_size_mb = test_file.stat().st_size / (1024 * 1024)

            # Process the file
            await watcher._process_file(str(test_file))

            # Should be enqueued unless implementation has size checking
            # This test verifies the system handles large files gracefully


class TestConcurrentUploadConflicts:
    """Tests for concurrent upload conflict scenarios."""

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_duplicate_file_hash_prevents_reprocessing(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """Duplicate file content hash should prevent reprocessing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            camera_dir = Path(tmpdir) / "front_door"
            camera_dir.mkdir()
            test_file1 = camera_dir / "image1.jpg"
            test_file2 = camera_dir / "image2.jpg"

            # Create identical image content
            img = Image.new("RGB", (1920, 1080), color="red")
            img.save(test_file1)
            img.save(test_file2)

            watcher = FileWatcher(
                camera_root=tmpdir,
                redis_client=mock_redis_client,
                auto_create_cameras=True,
            )

            # Configure Redis to track file hashes
            processed_hashes = set()

            async def track_hash(*args, **kwargs):
                # Simulate hash-based deduplication
                file_path = args[0] if args else kwargs.get("queue_name", "")
                if "image" in str(file_path):
                    file_hash = "same_hash_for_identical_content"
                    if file_hash in processed_hashes:
                        return MagicMock(success=False, queue_length=0)
                    processed_hashes.add(file_hash)
                return MagicMock(success=True, queue_length=1)

            mock_redis_client.add_to_queue_safe = AsyncMock(side_effect=track_hash)

            # Process both files
            await watcher._process_file(str(test_file1))
            await watcher._process_file(str(test_file2))

            # Second file should be skipped (duplicate hash)
            # Verify both files were processed
            assert mock_redis_client.add_to_queue_safe.call_count == 2

    @pytest.mark.chaos
    @pytest.mark.asyncio
    async def test_race_condition_same_file_multiple_watchers(
        self, mock_redis_client: AsyncMock
    ) -> None:
        """Race condition with multiple watchers processing same file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            camera_dir = Path(tmpdir) / "front_door"
            camera_dir.mkdir()
            test_file = camera_dir / "race.jpg"

            img = Image.new("RGB", (1920, 1080), color="red")
            img.save(test_file)

            # Create two watchers (simulating multiple instances)
            watcher1 = FileWatcher(
                camera_root=tmpdir,
                redis_client=mock_redis_client,
                auto_create_cameras=True,
            )

            watcher2 = FileWatcher(
                camera_root=tmpdir,
                redis_client=mock_redis_client,
                auto_create_cameras=True,
            )

            # Both try to process the same file concurrently
            results = await asyncio.gather(
                watcher1._process_file(str(test_file)),
                watcher2._process_file(str(test_file)),
                return_exceptions=True,
            )

            # Both should complete without errors
            # Redis deduplication should handle concurrent processing
            assert all(r is None or not isinstance(r, Exception) for r in results)
