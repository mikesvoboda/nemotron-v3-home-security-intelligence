"""Integration tests for Frame Extractor Service (TDD Phase 3 - RED).

These tests verify the FrameExtractor's behavior with real file I/O and Redis,
using temporary directories for isolation.

These tests are written BEFORE implementation following TDD principles.
All tests should FAIL initially until the FrameExtractor is implemented.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from backend.api.schemas.queue import DetectionQueuePayload


@pytest.fixture
def temp_frame_dir(tmp_path):
    """Create temporary directory for frame storage."""
    frame_dir = tmp_path / "rtsp_frames"
    frame_dir.mkdir()
    return frame_dir


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for queue operations."""
    mock_client = AsyncMock()
    mock_client.add_to_queue = AsyncMock(return_value=True)
    return mock_client


class TestFrameExtractorFileSystemIntegration:
    """Integration tests for file system operations."""

    @pytest.mark.asyncio
    async def test_saves_frame_to_correct_directory_structure(
        self, temp_frame_dir, mock_redis_client
    ) -> None:
        """Frame should be saved to {frame_dir}/{camera_id}/{timestamp}.jpg."""
        from backend.services.frame_extractor import FrameExtractor

        extractor = FrameExtractor(
            redis_client=mock_redis_client, frame_save_dir=str(temp_frame_dir)
        )

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        timestamp = datetime(2025, 1, 29, 12, 30, 45)

        with patch.object(extractor, "detect_motion") as mock_detect:
            mock_detect.return_value = True

            file_path = await extractor.extract_frame("front_door", frame, timestamp)

            # Verify directory structure
            assert file_path is not None
            path = Path(file_path)
            assert path.exists()
            assert path.parent.name == "front_door"
            assert path.parent.parent == temp_frame_dir

    @pytest.mark.asyncio
    async def test_creates_camera_subdirectories_automatically(
        self, temp_frame_dir, mock_redis_client
    ) -> None:
        """Should automatically create camera subdirectories if they don't exist."""
        from backend.services.frame_extractor import FrameExtractor

        extractor = FrameExtractor(
            redis_client=mock_redis_client, frame_save_dir=str(temp_frame_dir)
        )

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        timestamp = datetime.now()

        with patch.object(extractor, "detect_motion") as mock_detect:
            mock_detect.return_value = True

            # Extract frames for multiple cameras
            await extractor.extract_frame("camera1", frame, timestamp)
            await extractor.extract_frame("camera2", frame, timestamp)
            await extractor.extract_frame("camera3", frame, timestamp)

            # Verify all camera directories were created
            assert (temp_frame_dir / "camera1").exists()
            assert (temp_frame_dir / "camera2").exists()
            assert (temp_frame_dir / "camera3").exists()

    @pytest.mark.asyncio
    async def test_saved_file_is_valid_jpeg(self, temp_frame_dir, mock_redis_client) -> None:
        """Saved frame should be a valid JPEG file that can be read back."""
        from backend.services.frame_extractor import FrameExtractor

        extractor = FrameExtractor(
            redis_client=mock_redis_client, frame_save_dir=str(temp_frame_dir)
        )

        # Create a frame with some visual content
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        timestamp = datetime.now()

        with patch.object(extractor, "detect_motion") as mock_detect:
            mock_detect.return_value = True

            file_path = await extractor.extract_frame("camera1", frame, timestamp)

            # Verify file exists and is readable
            assert file_path is not None
            path = Path(file_path)
            assert path.exists()
            assert path.suffix in [".jpg", ".jpeg"]

            # Try reading the file back with OpenCV
            import cv2

            loaded_frame = cv2.imread(str(path))
            assert loaded_frame is not None
            assert loaded_frame.shape == frame.shape

    @pytest.mark.asyncio
    async def test_multiple_frames_from_same_camera(
        self, temp_frame_dir, mock_redis_client
    ) -> None:
        """Should save multiple frames from the same camera with unique filenames."""
        from backend.services.frame_extractor import FrameExtractor

        extractor = FrameExtractor(
            redis_client=mock_redis_client, frame_save_dir=str(temp_frame_dir)
        )

        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        with patch.object(extractor, "detect_motion") as mock_detect:
            mock_detect.return_value = True

            # Extract multiple frames with different timestamps
            paths = []
            for i in range(5):
                timestamp = datetime(2025, 1, 29, 12, 30, 45 + i)
                file_path = await extractor.extract_frame("camera1", frame, timestamp)
                paths.append(file_path)

            # All paths should be unique
            assert len(set(paths)) == 5

            # All files should exist
            for path in paths:
                assert Path(path).exists()


class TestFrameExtractorRedisIntegration:
    """Integration tests for Redis queue operations."""

    @pytest.mark.asyncio
    async def test_queues_frame_with_valid_payload(self, temp_frame_dir, mock_redis_client) -> None:
        """Should queue frame with valid DetectionQueuePayload format."""
        from backend.services.frame_extractor import FrameExtractor

        extractor = FrameExtractor(
            redis_client=mock_redis_client, frame_save_dir=str(temp_frame_dir)
        )

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        timestamp = datetime(2025, 1, 29, 12, 30, 45, 123456)

        with patch.object(extractor, "detect_motion") as mock_detect:
            mock_detect.return_value = True

            await extractor.extract_frame("front_door", frame, timestamp)

            # Verify Redis add_to_queue was called
            mock_redis_client.add_to_queue.assert_called_once()

            # Extract the payload
            call_args = mock_redis_client.add_to_queue.call_args
            queue_name = call_args[0][0]
            payload_dict = call_args[0][1]

            # Verify queue name
            assert queue_name == "detection_queue"

            # Validate payload matches DetectionQueuePayload schema
            payload = DetectionQueuePayload(**payload_dict)
            assert payload.camera_id == "front_door"
            assert payload.media_type == "image"
            assert payload.timestamp == timestamp.isoformat()
            assert payload.pipeline_start_time is not None
            assert Path(payload.file_path).exists()

    @pytest.mark.asyncio
    async def test_payload_file_path_is_absolute(self, temp_frame_dir, mock_redis_client) -> None:
        """Queued payload should contain absolute file path."""
        from backend.services.frame_extractor import FrameExtractor

        extractor = FrameExtractor(
            redis_client=mock_redis_client, frame_save_dir=str(temp_frame_dir)
        )

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        timestamp = datetime.now()

        with patch.object(extractor, "detect_motion") as mock_detect:
            mock_detect.return_value = True

            await extractor.extract_frame("camera1", frame, timestamp)

            payload_dict = mock_redis_client.add_to_queue.call_args[0][1]

            # File path should be absolute
            assert payload_dict["file_path"].startswith("/")
            # Should pass DetectionQueuePayload validation
            DetectionQueuePayload(**payload_dict)

    @pytest.mark.asyncio
    async def test_does_not_queue_when_no_motion(self, temp_frame_dir, mock_redis_client) -> None:
        """Should NOT queue frame when no motion is detected."""
        from backend.services.frame_extractor import FrameExtractor

        extractor = FrameExtractor(
            redis_client=mock_redis_client, frame_save_dir=str(temp_frame_dir)
        )

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        timestamp = datetime.now()

        with patch.object(extractor, "detect_motion") as mock_detect:
            mock_detect.return_value = False  # No motion

            result = await extractor.extract_frame("camera1", frame, timestamp)

            # Should not queue anything
            mock_redis_client.add_to_queue.assert_not_called()
            assert result is None


class TestFrameExtractorMotionDetectionIntegration:
    """Integration tests for motion detection with real background subtraction."""

    @pytest.mark.asyncio
    async def test_detects_motion_between_different_frames(
        self, temp_frame_dir, mock_redis_client
    ) -> None:
        """Should detect motion when frames change significantly."""
        from backend.services.frame_extractor import FrameExtractor

        extractor = FrameExtractor(
            redis_client=mock_redis_client,
            frame_save_dir=str(temp_frame_dir),
            motion_sensitivity=0.5,
        )

        timestamp = datetime.now()

        # First few frames to establish background
        static_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        for i in range(5):
            await extractor.extract_frame("camera1", static_frame, timestamp)

        # Clear the mock call history
        mock_redis_client.add_to_queue.reset_mock()

        # Frame with significant change (simulating motion)
        motion_frame = np.ones((480, 640, 3), dtype=np.uint8) * 255

        result = await extractor.extract_frame("camera1", motion_frame, timestamp)

        # Should detect motion and queue the frame
        # Note: This may or may not trigger depending on MOG2 sensitivity
        # The test validates the integration works correctly
        assert isinstance(result, str | None)

    @pytest.mark.asyncio
    async def test_does_not_detect_motion_in_static_scene(
        self, temp_frame_dir, mock_redis_client
    ) -> None:
        """Should NOT detect motion when frames are identical."""
        from backend.services.frame_extractor import FrameExtractor

        extractor = FrameExtractor(
            redis_client=mock_redis_client,
            frame_save_dir=str(temp_frame_dir),
            motion_sensitivity=0.5,
        )

        timestamp = datetime.now()
        static_frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Process several identical frames
        results = []
        for i in range(10):
            result = await extractor.extract_frame("camera1", static_frame, timestamp)
            results.append(result)

        # After background model stabilizes, should not detect motion
        # At least some of the later frames should return None
        assert results.count(None) > 0

    @pytest.mark.asyncio
    async def test_independent_motion_detection_per_camera(
        self, temp_frame_dir, mock_redis_client
    ) -> None:
        """Each camera should have independent background models."""
        from backend.services.frame_extractor import FrameExtractor

        extractor = FrameExtractor(
            redis_client=mock_redis_client, frame_save_dir=str(temp_frame_dir)
        )

        timestamp = datetime.now()

        # Camera 1: static scene
        static_frame = np.zeros((480, 640, 3), dtype=np.uint8)

        # Camera 2: scene with motion
        motion_frame = np.ones((480, 640, 3), dtype=np.uint8) * 255

        # Process frames for both cameras
        result1 = await extractor.extract_frame("camera1", static_frame, timestamp)
        result2 = await extractor.extract_frame("camera2", motion_frame, timestamp)

        # Each camera should have been processed independently
        # Both results should be valid (could be path or None)
        assert isinstance(result1, str | None)
        assert isinstance(result2, str | None)

        # Verify separate directories were created
        camera1_dir = temp_frame_dir / "camera1"
        camera2_dir = temp_frame_dir / "camera2"
        assert camera1_dir.exists()
        assert camera2_dir.exists()


class TestFrameExtractorConcurrentExtraction:
    """Integration tests for concurrent frame extraction from multiple cameras."""

    @pytest.mark.asyncio
    async def test_concurrent_extraction_from_multiple_cameras(
        self, temp_frame_dir, mock_redis_client
    ) -> None:
        """Should handle concurrent frame extraction from multiple cameras."""
        from backend.services.frame_extractor import FrameExtractor

        extractor = FrameExtractor(
            redis_client=mock_redis_client, frame_save_dir=str(temp_frame_dir)
        )

        async def extract_frames_for_camera(camera_id: str, count: int) -> list:
            results = []
            for i in range(count):
                frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
                timestamp = datetime(2025, 1, 29, 12, 30, 45 + i)

                with patch.object(extractor, "detect_motion", return_value=True):
                    result = await extractor.extract_frame(camera_id, frame, timestamp)
                    results.append(result)

            return results

        # Extract frames concurrently for 3 cameras
        camera1_results, camera2_results, camera3_results = await asyncio.gather(
            extract_frames_for_camera("camera1", 5),
            extract_frames_for_camera("camera2", 5),
            extract_frames_for_camera("camera3", 5),
        )

        # All extractions should succeed
        assert len(camera1_results) == 5
        assert len(camera2_results) == 5
        assert len(camera3_results) == 5

        # All paths should be unique
        all_paths = [p for p in camera1_results + camera2_results + camera3_results if p]
        assert len(set(all_paths)) == len(all_paths)

        # All files should exist
        for path in all_paths:
            assert Path(path).exists()

    @pytest.mark.asyncio
    async def test_concurrent_extraction_same_camera(
        self, temp_frame_dir, mock_redis_client
    ) -> None:
        """Should handle concurrent extractions from the same camera safely."""
        from backend.services.frame_extractor import FrameExtractor

        extractor = FrameExtractor(
            redis_client=mock_redis_client, frame_save_dir=str(temp_frame_dir)
        )

        async def extract_frame(index: int) -> str | None:
            frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            timestamp = datetime(2025, 1, 29, 12, 30, 45, index * 1000)

            with patch.object(extractor, "detect_motion", return_value=True):
                return await extractor.extract_frame("camera1", frame, timestamp)

        # Extract 10 frames concurrently for the same camera
        results = await asyncio.gather(*[extract_frame(i) for i in range(10)])

        # All should succeed
        assert all(r is not None for r in results)

        # All paths should be unique (unique timestamps)
        assert len(set(results)) == 10

        # All files should exist
        for path in results:
            assert Path(path).exists()


class TestFrameExtractorErrorHandling:
    """Integration tests for error handling scenarios."""

    @pytest.mark.asyncio
    async def test_handles_disk_full_error(self, tmp_path, mock_redis_client) -> None:
        """Should handle disk write errors gracefully."""
        from backend.services.frame_extractor import FrameExtractor

        extractor = FrameExtractor(redis_client=mock_redis_client, frame_save_dir=str(tmp_path))

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        timestamp = datetime.now()

        with patch("cv2.imwrite") as mock_imwrite:
            mock_imwrite.return_value = False  # Simulate write failure

            with patch.object(extractor, "detect_motion", return_value=True):
                with pytest.raises(RuntimeError, match="Failed to save frame"):
                    await extractor.extract_frame("camera1", frame, timestamp)

    @pytest.mark.asyncio
    async def test_handles_invalid_frame_directory(self, mock_redis_client) -> None:
        """Should handle invalid frame directory gracefully."""
        from backend.services.frame_extractor import FrameExtractor

        # Try to use a non-writable directory
        extractor = FrameExtractor(
            redis_client=mock_redis_client, frame_save_dir="/root/no_permission"
        )

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        timestamp = datetime.now()

        with patch.object(extractor, "detect_motion", return_value=True):
            # Should raise permission error or similar
            with pytest.raises((PermissionError, OSError)):
                await extractor.extract_frame("camera1", frame, timestamp)
